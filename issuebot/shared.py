"""Shared constants and utilities used across issuebot modules.

Extracted to eliminate duplication between scheduler.py and analysis_service.py.
"""
from pathlib import Path

# Standard task directory files — not considered patch content
PATCH_STANDARD_FILES = {
    "task.json", "report.md", "context.md",
    "patch_diff.md", "patch_diff.json", "patch_review.md",
    "chat_history.json", "chat_sessions.json",
}
PATCH_STANDARD_DIRS = {"images", ".patch_temp", "chat_files", "chat_uploads"}
PATCH_SOURCE_EXTENSIONS = {
    ".js", ".java", ".xml", ".json", ".properties",
    ".conf", ".css", ".html", ".jsp", ".sql",
}

# Directory names that indicate actual InterMax source roots (used to validate
# whether a directory in the task root is likely a patch, not chat artifacts).
KNOWN_SOURCE_ROOTS = {"intermax", "com", "org", "jdg", "webapp", "web-inf", "meta-inf", "src"}


def detect_patch_presence(task_dir: Path) -> bool:
    """Check if a task directory contains patch files.

    Looks for non-standard files/dirs in the task root and in ``patches/``.
    Returns True if patch-like content is found.
    """
    if not task_dir.exists():
        return False

    # Check patches/ directory first (created by fetch_doc.py)
    patches_dir = task_dir / "patches"
    if patches_dir.exists() and patches_dir.is_dir():
        for item in patches_dir.iterdir():
            if item.name == "doc_content.md":
                continue
            return True

    for item in task_dir.iterdir():
        name = item.name
        if name in PATCH_STANDARD_FILES:
            continue
        if name in PATCH_STANDARD_DIRS:
            continue
        if name == "patches":
            continue  # Already checked above
        if item.is_dir():
            # Only count directories that look like InterMax source roots
            if name.lower() in KNOWN_SOURCE_ROOTS:
                return True
            continue
        ext = item.suffix.lower()
        if ext in PATCH_SOURCE_EXTENSIONS or ext in (".zip", ".jar", ".tar", ".gz"):
            return True

    return False
