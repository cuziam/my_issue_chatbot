"""Task file listing and browsing utilities.

Provides list_task_files(), list_chat_files(), delete_chat_file(),
and internal helpers for scanning task directories.
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from ...config import TASKS_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"}

# Directories/files to exclude from task file scans
_SCAN_EXCLUDE_DIRS = {"chat_files", "chat_uploads", "chat_sessions.json"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def list_task_files(task_id: str) -> dict:
    """Scan all categories of task files and return structured response."""
    task_dir = TASKS_DIR / task_id
    if not task_dir.exists():
        return {"categories": [], "total_count": 0}

    categories: list[dict] = []
    total = 0

    # 1. Task Images (images/)
    cat = _scan_category(
        task_dir / "images", task_dir,
        "images", "Task Images", "image",
    )
    if cat:
        categories.append(cat)

    # 2. Patches (patches/)
    cat = _scan_category(
        task_dir / "patches", task_dir,
        "patches", "Patches", "patch",
    )
    if cat:
        categories.append(cat)

    # 3. User Uploads (chat_uploads/)
    cat = _scan_category(
        task_dir / "chat_uploads", task_dir,
        "uploads", "User Uploads", "upload",
    )
    if cat:
        categories.append(cat)

    # 4. AI Files (chat_files/)
    cat = _scan_category(
        task_dir / "chat_files", task_dir,
        "ai_files", "AI Files", "ai",
    )
    if cat:
        categories.append(cat)

    # 5. Reports (root-level .md files)
    report_files: list[dict] = []
    for fname in ("report.md", "context.md", "patch_review.md", "patch_diff.md", "patch_diff.json"):
        fpath = task_dir / fname
        if fpath.is_file():
            report_files.append(_file_meta(fpath, task_dir))
    if report_files:
        categories.append({
            "id": "reports",
            "label": "Reports",
            "icon": "report",
            "files": report_files,
            "archive_groups": {},
        })

    for cat in categories:
        total += len(cat["files"])
        for group_files in cat["archive_groups"].values():
            total += len(group_files)

    return {"categories": categories, "total_count": total}


async def list_chat_files(task_id: str) -> list[dict]:
    """List files in tasks/{task_id}/chat_files/."""
    chat_files_dir = TASKS_DIR / task_id / "chat_files"
    if not chat_files_dir.exists():
        return []
    files = []
    for f in sorted(chat_files_dir.iterdir()):
        if not f.is_file():
            continue
        try:
            stat = f.stat()
            files.append({
                "name": f.name,
                "path": str(f.absolute()).replace("\\", "/"),
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except OSError:
            continue
    return files


async def delete_chat_file(task_id: str, filename: str) -> bool:
    """Delete a file from tasks/{task_id}/chat_files/."""
    file_path = TASKS_DIR / task_id / "chat_files" / filename
    if not file_path.exists() or not file_path.is_file():
        return False
    file_path.unlink()
    return True


# ---------------------------------------------------------------------------
# Internal helpers (also used by chat_runner via _build_task_files_context)
# ---------------------------------------------------------------------------

def _is_image_ext(suffix: str) -> bool:
    return suffix.lower() in _IMAGE_EXTS


def _to_preview_url(file_path: Path) -> str | None:
    """Convert an absolute path to a /files/tasks/... URL if it's an image."""
    s = str(file_path).replace("\\", "/")
    idx = s.find("tasks/")
    if idx == -1:
        return None
    return "/files/" + s[idx:]


def _file_meta(path: Path, task_dir: Path) -> dict:
    """Build metadata dict for a single file."""
    try:
        stat = path.stat()
        size = stat.st_size
        modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
    except OSError:
        size = 0
        modified_at = None

    ext = path.suffix.lower()
    is_image = _is_image_ext(ext)
    rel = str(path.relative_to(task_dir)).replace("\\", "/")

    entry: dict = {
        "name": path.name,
        "path": str(path.absolute()).replace("\\", "/"),
        "relative_path": rel,
        "size": size,
        "ext": ext,
        "is_image": is_image,
    }
    if modified_at:
        entry["modified_at"] = modified_at
    if is_image:
        entry["preview_url"] = _to_preview_url(path)
    return entry


def _walk_files(directory: Path, max_depth: int = 3) -> list[Path]:
    """Recursively collect files up to *max_depth* levels deep."""
    results: list[Path] = []
    if not directory.is_dir():
        return results
    _walk_recurse(directory, results, 0, max_depth)
    return results


def _walk_recurse(d: Path, out: list[Path], depth: int, max_depth: int) -> None:
    if depth > max_depth:
        return
    try:
        entries = sorted(d.iterdir())
    except OSError:
        return
    for entry in entries:
        if entry.is_file():
            out.append(entry)
        elif entry.is_dir() and depth < max_depth:
            _walk_recurse(entry, out, depth + 1, max_depth)


def _scan_category(
    category_dir: Path,
    task_dir: Path,
    category_id: str,
    label: str,
    icon: str,
) -> dict | None:
    """Scan a directory and return a category dict with files + archive_groups."""
    if not category_dir.is_dir():
        return None

    files: list[dict] = []
    archive_groups: dict[str, list[dict]] = {}

    try:
        entries = sorted(category_dir.iterdir())
    except OSError:
        return None

    for entry in entries:
        if entry.is_file():
            files.append(_file_meta(entry, task_dir))
        elif entry.is_dir():
            # Archive group (auto-extracted directory)
            sub_files = _walk_files(entry, max_depth=2)
            if sub_files:
                archive_groups[entry.name] = [
                    _file_meta(f, task_dir) for f in sub_files
                ]

    if not files and not archive_groups:
        return None

    return {
        "id": category_id,
        "label": label,
        "icon": icon,
        "files": files,
        "archive_groups": archive_groups,
    }


def _build_task_files_context(task_id: str) -> str:
    """Build a file listing section for Claude's context prompt."""
    task_dir = TASKS_DIR / task_id
    if not task_dir.exists():
        return ""

    sections: list[str] = []

    # Images
    images_dir = task_dir / "images"
    if images_dir.is_dir():
        image_files: list[str] = []
        archive_sections: list[str] = []
        try:
            for entry in sorted(images_dir.iterdir()):
                if entry.is_file():
                    image_files.append(
                        f"  - {str(entry.absolute()).replace(chr(92), '/')}"
                    )
                    if len(image_files) >= 20:
                        break
                elif entry.is_dir():
                    sub = _walk_files(entry, max_depth=2)[:10]
                    if sub:
                        lines = [f"*Extracted archive ({entry.name}):*"]
                        for sf in sub:
                            lines.append(
                                f"  - {str(sf.absolute()).replace(chr(92), '/')}"
                            )
                        archive_sections.append("\n".join(lines))
        except OSError:
            pass
        if image_files:
            sections.append("*Images ({} files):*\n{}".format(
                len(image_files), "\n".join(image_files)
            ))
        sections.extend(archive_sections)

    # Patches
    patches_dir = task_dir / "patches"
    if patches_dir.is_dir():
        patch_files: list[str] = []
        try:
            for f in sorted(_walk_files(patches_dir, max_depth=2))[:20]:
                patch_files.append(
                    f"  - {str(f.absolute()).replace(chr(92), '/')}"
                )
        except OSError:
            pass
        if patch_files:
            sections.append("*Patches:*\n{}".format("\n".join(patch_files)))

    # User uploads
    uploads_dir = task_dir / "chat_uploads"
    if uploads_dir.is_dir():
        upload_files: list[str] = []
        try:
            for f in sorted(uploads_dir.iterdir()):
                if f.is_file():
                    upload_files.append(
                        f"  - {str(f.absolute()).replace(chr(92), '/')}"
                    )
                    if len(upload_files) >= 10:
                        break
        except OSError:
            pass
        if upload_files:
            sections.append("*User Uploads:*\n{}".format("\n".join(upload_files)))

    if not sections:
        return ""
    return "\n**Available task files** (Read tool\ub85c \ud655\uc778 \uac00\ub2a5):\n" + "\n".join(sections)
