"""File upload handling: validate, save, and manage uploaded files.

Provides handle_upload() plus internal helpers for sanitization,
file type detection, quota enforcement, and old-file cleanup.
"""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

from ...config import TASKS_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Upload constants
# ---------------------------------------------------------------------------
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file
MAX_TASK_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB per task
UPLOAD_MAX_AGE_DAYS = 7

ALLOWED_EXTENSIONS: dict[str, str] = {
    # image
    ".jpg": "image", ".jpeg": "image", ".png": "image",
    ".gif": "image", ".webp": "image",
    # text
    ".txt": "text", ".log": "text", ".csv": "text",
    ".xml": "text", ".json": "text", ".conf": "text",
    ".properties": "text", ".yaml": "text", ".yml": "text",
    ".md": "text", ".java": "text", ".py": "text",
    ".js": "text", ".ts": "text", ".html": "text", ".css": "text",
    # archive
    ".zip": "archive",
}

SENSITIVE_FILENAMES = {
    ".env", ".key", "credentials.json", "secrets.yaml",
    "secret.json", "secret.key",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def handle_upload(task_id: str, filename: str, content: bytes) -> dict:
    """Validate, save an uploaded file, and return metadata.

    Raises ``ValueError`` for validation failures.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {ext}")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE})")

    file_type = ALLOWED_EXTENSIONS[ext]

    upload_dir = TASKS_DIR / task_id / "chat_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Check task quota
    _check_task_quota(upload_dir, len(content))

    # Clean up old files
    _cleanup_old_uploads(upload_dir)

    # Build unique filename: sanitized_name_hash8.ext
    stem = _sanitize_filename(Path(filename).stem)
    content_hash = hashlib.md5(content).hexdigest()[:8]
    safe_name = f"{stem}_{content_hash}{ext}"
    dest = upload_dir / safe_name

    dest.write_bytes(content)

    abs_path = str(dest.absolute()).replace("\\", "/")
    return {
        "name": filename,
        "path": abs_path,
        "type": file_type,
        "size": len(content),
        "url": f"/api/chat/{task_id}/uploads/{safe_name}",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sanitize_filename(stem: str) -> str:
    """Remove unsafe characters from a filename stem."""
    import re
    sanitized = re.sub(r'[^\w\-.]', '_', stem)
    return sanitized[:60] if sanitized else "file"


def _detect_file_type(ext: str) -> str | None:
    """Return the file type category for an extension, or None."""
    return ALLOWED_EXTENSIONS.get(ext.lower())


def _check_task_quota(upload_dir: Path, new_size: int) -> None:
    """Raise ValueError if task upload quota would be exceeded."""
    total = sum(f.stat().st_size for f in upload_dir.iterdir() if f.is_file())
    if total + new_size > MAX_TASK_UPLOAD_SIZE:
        raise ValueError(
            f"Task upload quota exceeded: {total + new_size} bytes "
            f"(max {MAX_TASK_UPLOAD_SIZE})"
        )


def _cleanup_old_uploads(upload_dir: Path) -> None:
    """Delete files older than UPLOAD_MAX_AGE_DAYS."""
    cutoff = time.time() - UPLOAD_MAX_AGE_DAYS * 86400
    for f in upload_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                logger.debug("Cleaned up old upload: %s", f)
            except OSError:
                pass
