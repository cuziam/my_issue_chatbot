"""Service layer for package upload, extraction, and decompilation.

Handles streaming upload to _incoming/, archive extraction, inventory refresh,
and optional decompilation as a background pipeline.  Progress is broadcast
to WebSocket clients via the shared ConnectionManager.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import tarfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from ..config import PACKAGES_DIR
from ..ws.manager import manager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {".tar.gz", ".tar", ".zip"}
MAX_UPLOAD_SIZE = 3 * 1024 * 1024 * 1024  # 3 GB
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB
INCOMING_DIR = PACKAGES_DIR / "_incoming"
# Minimum free disk space = archive size × 3
DISK_SPACE_MULTIPLIER = 3

# ---------------------------------------------------------------------------
# In-memory job tracking
# ---------------------------------------------------------------------------
_upload_jobs: dict[str, dict] = {}


def _get_allowed_ext(filename: str) -> str | None:
    """Return the archive extension if allowed, else None."""
    lower = filename.lower()
    for ext in ALLOWED_EXTENSIONS:
        if lower.endswith(ext):
            return ext
    return None


def _strip_archive_ext(name: str) -> str:
    """Strip known archive extensions from filename."""
    for ext in (".tar.gz", ".tar", ".zip"):
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return name


def _update_job(upload_id: str, **kwargs) -> None:
    if upload_id in _upload_jobs:
        _upload_jobs[upload_id].update(kwargs)


async def _broadcast_progress(upload_id: str, uploaded: int, total: int) -> None:
    pct = round(uploaded / total * 100, 1) if total > 0 else 0
    _update_job(upload_id, percent=pct, uploaded=uploaded)
    await manager.broadcast({
        "type": "upload_progress",
        "upload_id": upload_id,
        "percent": pct,
        "phase": "uploading",
    })


async def _broadcast_phase(upload_id: str, phase: str, detail: str = "") -> None:
    _update_job(upload_id, phase=phase, detail=detail)
    await manager.broadcast({
        "type": "upload_phase",
        "upload_id": upload_id,
        "phase": phase,
        "detail": detail,
    })


async def _broadcast_completed(upload_id: str, package_name: str, components: list[str]) -> None:
    _update_job(upload_id, status="completed", phase="done", package_name=package_name,
                finished_at=datetime.now().isoformat())
    await manager.broadcast({
        "type": "upload_completed",
        "upload_id": upload_id,
        "package_name": package_name,
        "components": components,
    })


async def _broadcast_failed(upload_id: str, error: str) -> None:
    _update_job(upload_id, status="failed", error=error, phase="failed",
                finished_at=datetime.now().isoformat())
    await manager.broadcast({
        "type": "upload_failed",
        "upload_id": upload_id,
        "error": error,
    })


# ---------------------------------------------------------------------------
# Upload handler (streaming)
# ---------------------------------------------------------------------------

async def handle_upload(
    request,
    filename: str,
    file,
    content_length: int | None = None,
) -> dict:
    """Stream-write uploaded file to _incoming/, then spawn background processing.

    Args:
        request: Starlette Request (for disconnect detection)
        filename: Original filename
        file: UploadFile (Starlette)
        content_length: Optional Content-Length header value

    Returns:
        dict with upload_id and status
    """
    from starlette.requests import ClientDisconnect

    ext = _get_allowed_ext(filename)
    if ext is None:
        raise ValueError(f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Check duplicate package name
    base_name = _strip_archive_ext(filename)
    existing_dir = PACKAGES_DIR / base_name
    if existing_dir.exists() and existing_dir.is_dir():
        raise ValueError(
            f"Package '{base_name}' already exists. Delete it first before re-uploading."
        )

    # Check disk space
    total_size = content_length or 0
    if total_size > MAX_UPLOAD_SIZE:
        raise ValueError(f"File too large ({total_size:,} bytes). Max: {MAX_UPLOAD_SIZE:,} bytes")

    if total_size > 0:
        usage = shutil.disk_usage(str(PACKAGES_DIR))
        required = total_size * DISK_SPACE_MULTIPLIER
        if usage.free < required:
            raise ValueError(
                f"Insufficient disk space. Need {required:,} bytes, have {usage.free:,} bytes"
            )

    # Prepare
    upload_id = uuid.uuid4().hex[:12]
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = INCOMING_DIR / f"{upload_id}_{filename}"

    _upload_jobs[upload_id] = {
        "upload_id": upload_id,
        "filename": filename,
        "package_name": base_name,
        "status": "uploading",
        "phase": "uploading",
        "percent": 0,
        "uploaded": 0,
        "total_size": total_size,
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "error": None,
        "cancelled": False,
    }

    uploaded = 0
    try:
        with open(tmp_path, "wb") as f:
            while True:
                # Check cancel
                if _upload_jobs.get(upload_id, {}).get("cancelled"):
                    raise asyncio.CancelledError("Upload cancelled by user")

                # Check client disconnect
                if await request.is_disconnected():
                    raise ClientDisconnect()

                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break

                f.write(chunk)
                uploaded += len(chunk)

                # Enforce max size
                if uploaded > MAX_UPLOAD_SIZE:
                    raise ValueError(f"Upload exceeded max size ({MAX_UPLOAD_SIZE:,} bytes)")

                await _broadcast_progress(upload_id, uploaded, total_size or uploaded)

        # Update actual total size
        _update_job(upload_id, total_size=uploaded, percent=100)

    except (ClientDisconnect, ConnectionError, OSError) as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        error_msg = "Upload interrupted: client disconnected"
        _update_job(upload_id, status="failed", error=error_msg,
                    finished_at=datetime.now().isoformat())
        await _broadcast_failed(upload_id, error_msg)
        raise

    except asyncio.CancelledError:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        error_msg = "Upload cancelled"
        _update_job(upload_id, status="cancelled", error=error_msg,
                    finished_at=datetime.now().isoformat())
        await _broadcast_failed(upload_id, error_msg)
        raise

    except ValueError as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        _update_job(upload_id, status="failed", error=str(exc),
                    finished_at=datetime.now().isoformat())
        await _broadcast_failed(upload_id, str(exc))
        raise

    # Spawn background processing
    asyncio.create_task(_process_package(upload_id, tmp_path, filename))

    return {"upload_id": upload_id, "status": "uploading", "filename": filename}


# ---------------------------------------------------------------------------
# Background processing pipeline
# ---------------------------------------------------------------------------

async def _process_package(upload_id: str, archive_path: Path, original_filename: str) -> None:
    """Extract archive, refresh inventory, optionally decompile."""
    base_name = _strip_archive_ext(original_filename)
    target_dir = PACKAGES_DIR / base_name

    try:
        # Phase 1: Extract
        _update_job(upload_id, status="processing", phase="extracting")
        await _broadcast_phase(upload_id, "extracting", "Extracting archive...")

        await asyncio.to_thread(_extract_archive, archive_path, target_dir, base_name)

        if _upload_jobs.get(upload_id, {}).get("cancelled"):
            raise asyncio.CancelledError("Cancelled during extraction")

        # Remove archive from _incoming after successful extraction
        if archive_path.exists():
            archive_path.unlink(missing_ok=True)

        # Phase 2: Refresh inventory
        await _broadcast_phase(upload_id, "refreshing_inventory", "Updating package inventory...")
        inventory = await asyncio.to_thread(_refresh_inventory)

        if _upload_jobs.get(upload_id, {}).get("cancelled"):
            raise asyncio.CancelledError("Cancelled during inventory refresh")

        # Find the new package in inventory
        pkg_info = None
        for pkg in inventory.get("packages", []):
            if pkg.get("name") == base_name:
                pkg_info = pkg
                break

        components = pkg_info.get("components", []) if pkg_info else []
        needs_decompile = pkg_info.get("needs_decompile", False) if pkg_info else False

        # Phase 3: Decompile if needed
        if needs_decompile:
            await _broadcast_phase(upload_id, "decompiling", f"Decompiling {base_name}...")
            decompile_result = await asyncio.to_thread(_run_decompile, base_name)

            if decompile_result.get("success"):
                # Re-refresh inventory to pick up decompiled components
                inventory = await asyncio.to_thread(_refresh_inventory)
                for pkg in inventory.get("packages", []):
                    if pkg.get("name") == base_name:
                        components = pkg.get("components", [])
                        break
            else:
                logger.warning(
                    "Decompilation failed for %s: %s",
                    base_name, decompile_result.get("error"),
                )
                # Continue — extraction succeeded, decompile can be retried

        await _broadcast_completed(upload_id, base_name, components)

    except asyncio.CancelledError:
        # Clean up partial extraction
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        if archive_path.exists():
            archive_path.unlink(missing_ok=True)
        _update_job(upload_id, status="cancelled", error="Cancelled",
                    finished_at=datetime.now().isoformat())
        await _broadcast_failed(upload_id, "Processing cancelled")

    except Exception as exc:
        logger.exception("Package processing failed for %s", upload_id)
        # Clean up partial extraction
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        if archive_path.exists():
            archive_path.unlink(missing_ok=True)
        await _broadcast_failed(upload_id, str(exc))


# ---------------------------------------------------------------------------
# Extraction helpers (run in thread)
# ---------------------------------------------------------------------------

def _extract_archive(archive_path: Path, target_dir: Path, base_name: str) -> None:
    """Extract tar/zip archive, handling tar bombs."""
    filename_lower = archive_path.name.lower()

    if filename_lower.endswith(".tar.gz") or filename_lower.endswith(".tar"):
        _extract_tar(archive_path, target_dir, base_name)
    elif filename_lower.endswith(".zip"):
        _extract_zip(archive_path, target_dir, base_name)
    else:
        raise ValueError(f"Unknown archive format: {archive_path.name}")


def _extract_tar(archive_path: Path, target_dir: Path, base_name: str) -> None:
    """Extract tar archive using system tar (fast) with Python fallback."""
    if _try_system_tar(archive_path, target_dir, base_name):
        return
    _extract_tar_python(archive_path, target_dir, base_name)


def _try_system_tar(archive_path: Path, target_dir: Path, base_name: str) -> bool:
    """Try extracting with system GNU tar. Returns True if successful."""
    import subprocess as _sp

    tar_bin = shutil.which("tar")
    if not tar_bin:
        return False

    # Step 1: Check top-level dirs (fast — only reads headers, no decompression of file data)
    # --force-local: prevent 'D:' in Windows paths from being interpreted as remote host
    try:
        result = _sp.run(
            [tar_bin, "--force-local", "-tzf", str(archive_path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.warning("system tar list failed (rc=%d): %s", result.returncode, result.stderr[:300])
            return False
    except (_sp.TimeoutExpired, OSError):
        return False

    top_dirs: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.replace("\\", "/").strip("/").split("/")
        if parts and parts[0]:
            top_dirs.add(parts[0])

    # Path traversal check
    for line in result.stdout.splitlines():
        if line.startswith("/") or ".." in line.split("/"):
            raise ValueError(f"Path traversal detected in archive: {line}")

    # Step 2: Extract
    # On Windows, symlink creation fails (requires admin) — this is non-fatal.
    # We check if actual files were extracted rather than relying on exit code.
    if len(top_dirs) == 1:
        single_root = top_dirs.pop()
        temp_extract = PACKAGES_DIR / f"_incoming/_extract_{uuid.uuid4().hex[:8]}"
        temp_extract.mkdir(parents=True, exist_ok=True)
        try:
            proc = _sp.run(
                [tar_bin, "--force-local", "-xzf", str(archive_path), "-C", str(temp_extract)],
                capture_output=True, text=True, timeout=600,
            )
            extracted_dir = temp_extract / single_root
            if not extracted_dir.exists() or not any(extracted_dir.iterdir()):
                logger.warning("system tar extraction produced no files: %s", proc.stderr[:500])
                shutil.rmtree(temp_extract, ignore_errors=True)
                return False
            if proc.returncode != 0:
                logger.info("system tar had non-fatal warnings (rc=%d): %s",
                            proc.returncode, proc.stderr[:300])

            shutil.move(str(extracted_dir), str(target_dir))
        finally:
            if temp_extract.exists():
                shutil.rmtree(temp_extract, ignore_errors=True)
    else:
        target_dir.mkdir(parents=True, exist_ok=True)
        proc = _sp.run(
            [tar_bin, "--force-local", "-xzf", str(archive_path), "-C", str(target_dir)],
            capture_output=True, text=True, timeout=600,
        )
        if not any(target_dir.iterdir()):
            logger.warning("system tar extraction produced no files: %s", proc.stderr[:500])
            shutil.rmtree(target_dir, ignore_errors=True)
            return False
        if proc.returncode != 0:
            logger.info("system tar had non-fatal warnings (rc=%d): %s",
                        proc.returncode, proc.stderr[:300])

    return True


def _extract_tar_python(archive_path: Path, target_dir: Path, base_name: str) -> None:
    """Fallback: extract tar archive with Python tarfile (single-pass)."""
    import sys

    with tarfile.open(str(archive_path), "r:*") as tf:
        # Single-pass: iterate members to check top-level dirs and security,
        # then extract. For compressed archives, getmembers() and extractall()
        # both read the full stream, but we avoid calling both separately.
        members = tf.getmembers()

        top_dirs: set[str] = set()
        for m in members:
            # Path traversal check
            if m.name.startswith("/") or ".." in m.name.split("/"):
                raise ValueError(f"Path traversal detected in archive: {m.name}")
            parts = m.name.replace("\\", "/").split("/")
            if parts[0]:
                top_dirs.add(parts[0])

        if len(top_dirs) == 1:
            single_root = top_dirs.pop()
            temp_extract = PACKAGES_DIR / f"_incoming/_extract_{uuid.uuid4().hex[:8]}"
            temp_extract.mkdir(parents=True, exist_ok=True)

            if sys.version_info >= (3, 12):
                tf.extractall(str(temp_extract), members=members, filter="data")
            else:
                tf.extractall(str(temp_extract), members=members)

            extracted_dir = temp_extract / single_root
            if extracted_dir.exists():
                shutil.move(str(extracted_dir), str(target_dir))
            else:
                shutil.move(str(temp_extract), str(target_dir))

            if temp_extract.exists():
                shutil.rmtree(temp_extract, ignore_errors=True)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            if sys.version_info >= (3, 12):
                tf.extractall(str(target_dir), members=members, filter="data")
            else:
                tf.extractall(str(target_dir), members=members)


def _extract_zip(archive_path: Path, target_dir: Path, base_name: str) -> None:
    """Extract zip archive with path traversal protection."""
    with zipfile.ZipFile(str(archive_path), "r") as zf:
        # Path traversal check
        for info in zf.infolist():
            if info.filename.startswith("/") or ".." in info.filename.split("/"):
                raise ValueError(f"Path traversal detected in archive: {info.filename}")

        # Check for tar bomb equivalent
        top_dirs = set()
        for info in zf.infolist():
            parts = info.filename.replace("\\", "/").split("/")
            if parts[0]:
                top_dirs.add(parts[0])

        if len(top_dirs) == 1:
            single_root = top_dirs.pop()
            temp_extract = PACKAGES_DIR / f"_incoming/_extract_{uuid.uuid4().hex[:8]}"
            temp_extract.mkdir(parents=True, exist_ok=True)
            zf.extractall(str(temp_extract))
            extracted_dir = temp_extract / single_root
            if extracted_dir.exists():
                shutil.move(str(extracted_dir), str(target_dir))
            else:
                shutil.move(str(temp_extract), str(target_dir))
            if temp_extract.exists():
                shutil.rmtree(temp_extract, ignore_errors=True)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(str(target_dir))


# ---------------------------------------------------------------------------
# Inventory / decompile helpers (run in thread)
# ---------------------------------------------------------------------------

def _refresh_inventory() -> dict:
    """Regenerate and save inventory.json."""
    import json

    from issuebot.inventory import generate_inventory

    inv = generate_inventory()
    inv_file = PACKAGES_DIR / "inventory.json"
    inv_file.parent.mkdir(parents=True, exist_ok=True)
    with open(inv_file, "w", encoding="utf-8") as f:
        json.dump(inv, f, indent=2, ensure_ascii=False)
    return inv


def _run_decompile(package_name: str) -> dict:
    """Run decompile on a package."""
    from issuebot.decompile_runner import run_decompile

    return run_decompile(package_name)


# ---------------------------------------------------------------------------
# Job management
# ---------------------------------------------------------------------------

def get_upload_jobs() -> list[dict]:
    """Return all upload jobs (recent first)."""
    jobs = list(_upload_jobs.values())
    jobs.sort(key=lambda j: j.get("started_at", ""), reverse=True)
    return jobs


def cancel_upload(upload_id: str) -> bool:
    """Mark an upload job as cancelled."""
    if upload_id not in _upload_jobs:
        return False
    _upload_jobs[upload_id]["cancelled"] = True
    return True


async def delete_package(name: str) -> dict:
    """Delete a package directory and/or archive from packages/."""
    deleted = []

    # Delete extracted directory
    pkg_dir = PACKAGES_DIR / name
    if pkg_dir.exists() and pkg_dir.is_dir():
        await asyncio.to_thread(shutil.rmtree, str(pkg_dir), True)
        deleted.append(f"directory: {name}")

    # Delete archive files
    for ext in (".tar.gz", ".tar", ".zip"):
        archive = PACKAGES_DIR / f"{name}{ext}"
        if archive.exists():
            archive.unlink()
            deleted.append(f"archive: {name}{ext}")

    if not deleted:
        raise FileNotFoundError(f"Package '{name}' not found")

    # Refresh inventory
    await asyncio.to_thread(_refresh_inventory)

    return {"deleted": deleted}


def cleanup_incoming() -> int:
    """Remove all files in _incoming/. Returns count of files removed."""
    if not INCOMING_DIR.exists():
        return 0
    count = 0
    for item in INCOMING_DIR.iterdir():
        if item.is_file():
            item.unlink(missing_ok=True)
            count += 1
        elif item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
            count += 1
    return count
