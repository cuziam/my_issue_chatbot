"""Weekly digest: collect tasks by date range and extract report summaries."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from .config import ROOT_DIR


TASKS_DIR = ROOT_DIR / "tasks"

# Sections to INCLUDE in digest summary (case-insensitive substring match)
_INCLUDE_SECTIONS = [
    "버전 정보",
    "분석 코드베이스",
    "이슈 요약",
    "문의 내용 요약",
    "요청 내용 요약",
    "패치 요약",
    "재현 시나리오",
    "구현 상태 확인",
    "변경 파일 목록",
]

# Sections to EXCLUDE (takes priority over include)
_EXCLUDE_SECTIONS = [
    "참고:",
    "코드 레벨",
    "QA 검증",
    "추가 분석",
    "추가 확인",
    "리스크",
]


def _parse_sections(text: str) -> list[tuple[str, str]]:
    """Parse markdown into (heading, body) pairs.

    Handles both ``##`` and ``###`` level headings.
    """
    sections: list[tuple[str, str]] = []
    heading_re = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    matches = list(heading_re.finditer(text))

    for i, m in enumerate(matches):
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append((title, body))

    return sections


def _should_include(title: str) -> bool:
    """Decide whether a section should be included in digest summary."""
    title_lower = title.lower()
    for exc in _EXCLUDE_SECTIONS:
        if exc.lower() in title_lower:
            return False
    for inc in _INCLUDE_SECTIONS:
        if inc.lower() in title_lower:
            return True
    return False


def extract_report_summary(report_path: str | Path) -> dict:
    """Extract key sections from a report.md file.

    Returns a dict with extracted text sections plus the detected task type.
    """
    report_path = Path(report_path)
    if not report_path.exists():
        return {}

    text = report_path.read_text(encoding="utf-8")
    sections = _parse_sections(text)

    result: dict[str, str] = {}
    for title, body in sections:
        if not _should_include(title):
            continue
        # Normalize key
        key = title.strip()
        result[key] = body

    # Detect task type from section headings
    heading_text = " ".join(t for t, _ in sections).lower()
    if "패치" in heading_text:
        result["_task_type"] = "patch_review"
    elif "구현 상태" in heading_text or "요청 내용" in heading_text:
        result["_task_type"] = "improvement_request"
    elif "문의 내용" in heading_text or "사양" in heading_text:
        result["_task_type"] = "spec_inquiry"
    else:
        result["_task_type"] = "issue_analysis"

    return result


def collect_digest_tasks(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    issue_type: Optional[str] = None,
) -> list[dict]:
    """Collect task data for digest generation.

    Scans local tasks/ directory, filters by date_created range,
    and attaches report summary if available.

    Args:
        date_from: Start date (YYYY-MM-DD or ms epoch). Inclusive.
        date_to: End date (YYYY-MM-DD or ms epoch). Inclusive.
        issue_type: Filter by ClickUp Issue Type (Bug, Inquiry, etc.).

    Returns:
        List of task dicts with metadata and report_summary.
    """
    if not TASKS_DIR.exists():
        return []

    from_ms = _parse_date_ms(date_from)
    to_ms = _parse_date_ms(date_to)

    tasks: list[dict] = []
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

        # Date filter — require date_created for filtering.
        # Tasks without date_created are skipped when a date range is set.
        # Run POST /api/tasks/backfill-dates to populate missing dates.
        created_raw = data.get("date_created")
        if from_ms is not None or to_ms is not None:
            if not created_raw:
                continue  # no date — skip when filtering by date
            try:
                created_ms = int(created_raw)
            except (ValueError, TypeError):
                continue  # unparseable date — skip
            if from_ms is not None and created_ms < from_ms:
                continue
            if to_ms is not None and created_ms > to_ms:
                continue

        # Issue type filter (ClickUp custom field "*Issue Type")
        if issue_type:
            cf = data.get("custom_fields", {})
            task_issue_type = cf.get("*Issue Type") or cf.get("Issue Type") or ""
            if task_issue_type.lower() != issue_type.lower():
                continue

        # Build task entry
        report_path = task_dir / "report.md"
        report_summary = extract_report_summary(report_path) if report_path.exists() else None

        entry = {
            "id": data.get("id", task_dir.name),
            "name": data.get("name", ""),
            "url": data.get("url", ""),
            "status": data.get("status", ""),
            "date_created": created_raw,
            "tags": data.get("tags", []),
            "custom_fields": data.get("custom_fields", {}),
            "assignees": [
                a.get("username", "") for a in data.get("assignees", [])
            ],
            "has_report": report_path.exists(),
            "report_summary": report_summary,
        }
        tasks.append(entry)

    return tasks


def _parse_date_ms(value: Optional[str]) -> Optional[int]:
    """Convert a date value to milliseconds since epoch.

    Accepts None, ms-epoch string, or YYYY-MM-DD.
    """
    if not value:
        return None
    if value.isdigit() and len(value) > 8:
        return int(value)
    from datetime import datetime, timezone
    try:
        dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None
