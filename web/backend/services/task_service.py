"""Service layer for reading/listing tasks from the local filesystem."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..config import TASKS_DIR


def list_tasks(
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    has_report: Optional[bool] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[dict]:
    """Scan tasks/ directory and return task summaries.

    All filters are optional and combined with AND logic.
    ``date_from`` / ``date_to`` filter by ``date_created`` (ms timestamp).
    Accepts either millisecond-epoch strings or ISO-8601 date strings
    (``YYYY-MM-DD``).
    """
    tasks: list[dict] = []
    if not TASKS_DIR.exists():
        return tasks

    date_from_ms = _parse_date_ms(date_from)
    date_to_ms = _parse_date_ms(date_to)

    for task_dir in sorted(TASKS_DIR.iterdir()):
        if not task_dir.is_dir():
            continue
        task_json = task_dir / "task.json"
        if not task_json.exists():
            continue

        try:
            with open(task_json, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        task_has_report = (task_dir / "report.md").exists()
        task_has_patch_review = (task_dir / "patch_review.md").exists()
        task_has_context = (task_dir / "context.md").exists()

        # Apply filters
        if status_filter and data.get("status", "").lower() != status_filter.lower():
            continue
        if has_report is not None and task_has_report != has_report:
            continue
        if search:
            needle = search.lower()
            haystack_name = data.get("name", "").lower()
            haystack_id = data.get("id", "").lower()
            if needle not in haystack_name and needle not in haystack_id:
                continue

        # Date range filter (based on date_created)
        if date_from_ms is not None or date_to_ms is not None:
            created_raw = data.get("date_created")
            if not created_raw:
                continue
            try:
                created_ms = int(created_raw)
            except (ValueError, TypeError):
                continue
            if date_from_ms is not None and created_ms < date_from_ms:
                continue
            if date_to_ms is not None and created_ms > date_to_ms:
                continue

        summary = {
            "id": data.get("id", task_dir.name),
            "name": data.get("name", ""),
            "status": data.get("status", ""),
            "date_created": data.get("date_created"),
            "assignees": [
                a.get("username", "") for a in data.get("assignees", [])
            ],
            "tags": data.get("tags", []),
            "has_report": task_has_report,
            "has_patch_review": task_has_patch_review,
            "has_context": task_has_context,
            "url": data.get("url", ""),
        }
        tasks.append(summary)

    return tasks


def _parse_date_ms(value: Optional[str]) -> Optional[int]:
    """Convert a date string to milliseconds since epoch.

    Accepts:
      - ``None`` → ``None``
      - Millisecond-epoch string (e.g. ``"1711929600000"``)
      - ISO date ``YYYY-MM-DD`` (interpreted as start of day UTC)
    """
    if not value:
        return None
    # Already a numeric timestamp?
    if value.isdigit() and len(value) > 8:
        return int(value)
    # Try ISO date
    from datetime import datetime, timezone
    try:
        dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def get_task_detail(task_id: str) -> Optional[dict]:
    """Get full task detail including report/patch-review content."""
    task_dir = TASKS_DIR / task_id
    task_json = task_dir / "task.json"
    if not task_json.exists():
        return None

    try:
        with open(task_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    detail: dict = {
        "id": data.get("id", task_id),
        "name": data.get("name", ""),
        "status": data.get("status", ""),
        "description": data.get("description", ""),
        "markdown_description": data.get("markdown_description", ""),
        "assignees": [
            a.get("username", "") for a in data.get("assignees", [])
        ],
        "tags": data.get("tags", []),
        "custom_fields": data.get("custom_fields", {}),
        "comments": data.get("comments", []),
        "attachments": data.get("attachments", []),
        "linked_docs": data.get("linked_docs", []),
        "url": data.get("url", ""),
        "has_report": (task_dir / "report.md").exists(),
        "has_patch_review": (task_dir / "patch_review.md").exists(),
        "has_context": (task_dir / "context.md").exists(),
    }

    # Read markdown files if they exist
    for filename, key in [
        ("report.md", "report_content"),
        ("patch_review.md", "patch_review_content"),
        ("context.md", "context_content"),
        ("patch_diff.md", "patch_diff_content"),
    ]:
        filepath = task_dir / filename
        if filepath.exists():
            try:
                detail[key] = filepath.read_text(encoding="utf-8")
            except OSError:
                detail[key] = None
        else:
            detail[key] = None

    return detail
