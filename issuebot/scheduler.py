#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Issue Analysis Scheduler
Detects ClickUp task state changes and triggers automatic analysis via claude -p.

Usage:
    # Fetch only (backward compatible)
    python scheduler.py --fetch-only

    # Detect triggers without running analysis
    python scheduler.py --detect-only

    # Full auto: fetch + detect + analyze
    python scheduler.py --auto

    # Dry run: show what would be analyzed
    python scheduler.py --auto --dry-run

    # Initialize state.json from existing tasks/
    python scheduler.py --init-state

    # Cron example (daily at 3am)
    0 3 * * * cd /mnt/d/jar-decompiler && .venv/bin/python issuebot/scheduler.py --auto >> logs/scheduler.log 2>&1
"""

import os
import sys
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Get script and root directories
SCRIPT_DIR = Path(__file__).parent.absolute()
ROOT_DIR = SCRIPT_DIR.parent

# Load environment variables
load_dotenv(ROOT_DIR / ".env")

# Load config
with open(ROOT_DIR / "config" / "config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# Scheduler config
SCHEDULER_CONFIG = config.get("scheduler", {})
DEFAULT_LIST_ID = SCHEDULER_CONFIG.get("list_id", "")
DEFAULT_STATUS = SCHEDULER_CONFIG.get("filter_status", "open")
WATCHED_STATUSES = SCHEDULER_CONFIG.get("watched_statuses", ["open", "qa assigned", "qa to do"])
ACTIVITY_WATCH_STATUSES = SCHEDULER_CONFIG.get("activity_watch_statuses", ["qa in review", "qa in progress"])
ANALYSIS_TIMEOUT = SCHEDULER_CONFIG.get("analysis_timeout_seconds", 600)

# Phase-based trigger classification (configurable via config.json)
PHASE_TRIAGE = set(SCHEDULER_CONFIG.get("phase_triage", ["open", "qa assigned"]))
PHASE_WATCH = set(SCHEDULER_CONFIG.get("phase_watch", ["open reviewed", "to do", "in progress", "resolved"]))
PHASE_VERIFY = set(SCHEDULER_CONFIG.get("phase_verify", ["dev deploy", "qa to do", "qa in progress"]))
PHASE_REOPEN = set(SCHEDULER_CONFIG.get("phase_reopen", ["reopened"]))
STATE_CLEANUP_DAYS = SCHEDULER_CONFIG.get("state_cleanup_days", 30)

# Directories
TASKS_DIR = ROOT_DIR / config.get("tasks_dir", "tasks")
LOGS_DIR = ROOT_DIR / "logs"
STATE_FILE = TASKS_DIR / "state.json"

# ClickUp User ID for assignee matching
CLICKUP_USER_ID = os.getenv("CLICKUP_USER_ID", "")

# Max consecutive failures before skipping a task
MAX_TRIGGER_ATTEMPTS = 3


try:
    from .shared import PATCH_STANDARD_FILES, PATCH_STANDARD_DIRS, PATCH_SOURCE_EXTENSIONS, detect_patch_presence as _shared_detect_patch
except ImportError:
    from shared import PATCH_STANDARD_FILES, PATCH_STANDARD_DIRS, PATCH_SOURCE_EXTENSIONS  # type: ignore[import-untyped,no-redef]
    _shared_detect_patch = None  # type: ignore[assignment]


def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


def _is_older_than_days(timestamp_str, days):
    """Check if an ISO timestamp string is older than N days."""
    if not timestamp_str:
        return True  # No timestamp = treat as old
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        # Make naive for comparison if needed
        if ts.tzinfo:
            ts = ts.replace(tzinfo=None)
        return (datetime.now() - ts).days > days
    except (ValueError, TypeError):
        return True


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state():
    """Load state.json, return empty state if not found"""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_run": None, "tasks": {}}


def save_state(state):
    """Save state to state.json"""
    state["last_run"] = datetime.now().isoformat()
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    log(f"State saved to {STATE_FILE}")


def build_initial_state():
    """Build state.json from existing tasks/ directory"""
    state = {"last_run": datetime.now().isoformat(), "tasks": {}}

    if not TASKS_DIR.exists():
        log("No tasks/ directory found")
        return state

    for task_dir in sorted(TASKS_DIR.iterdir()):
        if not task_dir.is_dir():
            continue
        task_json_path = task_dir / "task.json"
        if not task_json_path.exists():
            continue

        task_id = task_dir.name
        with open(task_json_path, "r", encoding="utf-8") as f:
            task_data = json.load(f)

        has_report = (task_dir / "report.md").exists()
        has_patch_review = (task_dir / "patch_review.md").exists()
        assignee_ids = [a.get("id") for a in task_data.get("assignees", []) if a.get("id")]

        state["tasks"][task_id] = {
            "status": task_data.get("status", ""),
            "assignee_ids": assignee_ids,
            "has_report": has_report,
            "has_patch_review": has_patch_review,
            "last_analysis_type": "initial" if has_report else None,
            "last_analysis_time": None,
            "trigger_attempts": {},
            "date_updated": None,
            "last_comment_date": None,
            "comment_count": 0
        }

    log(f"Built initial state: {len(state['tasks'])} tasks")
    return state


# ---------------------------------------------------------------------------
# Trigger detection
# ---------------------------------------------------------------------------

def is_my_task(assignee_ids):
    """Check if the task is assigned to me"""
    if not CLICKUP_USER_ID:
        return False
    return int(CLICKUP_USER_ID) in [int(aid) for aid in assignee_ids if aid]


def get_custom_task_id(api_task):
    """Extract custom task ID (e.g., IMX-9355) from API response"""
    custom_id = api_task.get("custom_id")
    if custom_id:
        return custom_id
    return api_task.get("id", "")


def _make_trigger(task_id, custom_id, mode, reason):
    """Helper to construct a trigger dict."""
    return {"task_id": task_id, "custom_id": custom_id, "mode": mode, "reason": reason}


def _check_attempt_limit(old_task, mode):
    """Return True if the trigger mode has NOT exceeded MAX_TRIGGER_ATTEMPTS."""
    if not old_task:
        return True
    return old_task.get("trigger_attempts", {}).get(mode, 0) < MAX_TRIGGER_ATTEMPTS


def detect_triggers(old_state, current_api_tasks):
    """Compare old state with current API tasks and detect triggers.

    Uses a Phase-based model aligned with the actual QA workflow:
    - Phase TRIAGE (open, qa assigned): initial analysis
    - Phase WATCH (open reviewed, to do, in progress, resolved): observe only
    - Phase VERIFY (dev deploy, qa to do, qa in progress): verification/patch review
    - Phase REOPEN (reopened): reopened issue analysis

    Returns list of dicts: [{"task_id": ..., "custom_id": ..., "mode": ..., "reason": ...}]
    """
    triggers = []
    old_tasks = old_state.get("tasks", {})

    for api_task in current_api_tasks:
        task_id = api_task.get("id", "")
        custom_id = get_custom_task_id(api_task)
        display_id = custom_id or task_id
        current_status = api_task.get("status", {}).get("status", "").lower()
        assignee_ids = [a.get("id") for a in api_task.get("assignees", [])]

        # Use custom_id as state key if available, else task_id
        state_key = custom_id or task_id
        old_task = old_tasks.get(state_key, None)
        old_status = (old_task or {}).get("status", "")

        # No status change for existing tasks → skip (activity_triggers handles this)
        if old_task and current_status == old_status:
            continue

        # Determine report existence (check both custom_id and task_id dirs)
        has_report = False
        task_dir = None
        for candidate_id in [custom_id, task_id]:
            if candidate_id:
                candidate_dir = TASKS_DIR / candidate_id
                if (candidate_dir / "report.md").exists():
                    has_report = True
                    task_dir = candidate_dir
                    break
                if candidate_dir.exists():
                    task_dir = candidate_dir

        # --- Phase 1: TRIAGE (초동 분석) ---
        if current_status in PHASE_TRIAGE:
            if old_task is None:
                # New task first seen in triage phase
                if _check_attempt_limit(old_task, "initial"):
                    triggers.append(_make_trigger(task_id, custom_id, "initial",
                        f"New task: {display_id}"))
            elif current_status == "qa assigned" and is_my_task(assignee_ids):
                if not has_report and _check_attempt_limit(old_task, "initial"):
                    triggers.append(_make_trigger(task_id, custom_id, "initial",
                        f"QA assigned to me, no report: {display_id}"))

        # --- Phase 2: WATCH (관찰만, 트리거 없음) ---
        elif current_status in PHASE_WATCH:
            pass  # State update only, no analysis trigger

        # --- Phase 3: VERIFY (검증 분석) ---
        elif current_status in PHASE_VERIFY:
            if is_my_task(assignee_ids):
                if has_report:
                    if _check_attempt_limit(old_task, "verify"):
                        triggers.append(_make_trigger(task_id, custom_id, "verify",
                            f"Transitioned to {current_status}: {display_id}"))
                else:
                    # No report = task never went through triage → initial analysis
                    if _check_attempt_limit(old_task, "initial"):
                        triggers.append(_make_trigger(task_id, custom_id, "initial",
                            f"{current_status} but no report: {display_id}"))

        # --- Phase 4: REOPEN (���발 분석) ---
        elif current_status in PHASE_REOPEN:
            mode = "reopen" if has_report else "initial"
            if _check_attempt_limit(old_task, mode):
                triggers.append(_make_trigger(task_id, custom_id, mode,
                    f"Reopened: {display_id}"))

        # --- Catch-all: new task in unclassified status ---
        elif old_task is None:
            # First seen in a status not in any phase — just record in state
            pass

    return triggers


def detect_activity_triggers(old_state, current_api_tasks):
    """Detect activity changes (new comments, description updates) for tasks
    in ACTIVITY_WATCH_STATUSES.

    Returns list of trigger dicts with mode="activity_update".
    Only triggers for tasks that:
    1. Are in ACTIVITY_WATCH_STATUSES
    2. Are assigned to me
    3. Already have a report.md
    4. Have a changed date_updated since last check
    """
    triggers = []
    old_tasks = old_state.get("tasks", {})

    for api_task in current_api_tasks:
        task_id = api_task.get("id", "")
        custom_id = get_custom_task_id(api_task)
        display_id = custom_id or task_id
        current_status = api_task.get("status", {}).get("status", "").lower()
        assignee_ids = [a.get("id") for a in api_task.get("assignees", [])]

        # Layer 1: Only activity-watched statuses
        if current_status not in ACTIVITY_WATCH_STATUSES:
            continue

        # Layer 2: Only my tasks
        if not is_my_task(assignee_ids):
            continue

        # Layer 3: Only tasks with existing report
        state_key = custom_id or task_id
        has_report = False
        for candidate_id in [custom_id, task_id]:
            if candidate_id and (TASKS_DIR / candidate_id / "report.md").exists():
                has_report = True
                break
        if not has_report:
            continue

        # Layer 4: Check date_updated change
        old_task = old_tasks.get(state_key)
        if not old_task:
            continue  # First time seeing this task — skip (will be tracked after this run)

        old_date_updated = old_task.get("date_updated")
        new_date_updated = api_task.get("date_updated")

        if old_date_updated is None:
            continue  # No baseline yet — skip (will be set after this run)

        if str(new_date_updated) == str(old_date_updated):
            continue  # No change

        # Check attempt limit
        attempt_count = old_task.get("trigger_attempts", {}).get("activity_update", 0)
        if attempt_count >= MAX_TRIGGER_ATTEMPTS:
            log(f"  SKIP {display_id}: exceeded {MAX_TRIGGER_ATTEMPTS} attempts for activity_update")
            continue

        triggers.append({
            "task_id": task_id,
            "custom_id": custom_id,
            "mode": "activity_update",
            "reason": f"Activity change detected (date_updated changed): {display_id}"
        })

    return triggers


def _count_all_comments(comments):
    """Count total comments including threaded replies."""
    total = len(comments)
    for c in comments:
        total += len(c.get("replies", []))
    return total


def _flatten_all_comments(comments):
    """Flatten comments and their replies into a single list for filtering."""
    flat = []
    for c in comments:
        flat.append(c)
        for r in c.get("replies", []):
            flat.append(r)
    return flat


def _latest_comment_date(comments):
    """Get the latest date across all comments and replies."""
    dates = []
    for c in comments:
        if c.get("date"):
            dates.append(c["date"])
        for r in c.get("replies", []):
            if r.get("date"):
                dates.append(r["date"])
    return max(dates, default="0")


def filter_activity_self_triggers(triggers, old_state):
    """Filter out triggers caused only by the user's own activity.

    Fetches recent comments (including threaded replies) via API and checks
    if all new comments/replies are from CLICKUP_USER_ID. If only
    self-authored activity is new, the trigger is removed.
    """
    if not CLICKUP_USER_ID:
        return triggers  # Can't filter without user ID

    from fetch import fetch_comments

    filtered = []
    for t in triggers:
        display_id = t["custom_id"] or t["task_id"]
        state_key = t["custom_id"] or t["task_id"]
        old_task = old_state.get("tasks", {}).get(state_key, {})

        # Fetch current comments (with replies)
        comments = fetch_comments(display_id, include_replies=True)
        total_count = _count_all_comments(comments)
        old_comment_count = old_task.get("comment_count", 0)
        old_last_comment_date = old_task.get("last_comment_date")

        # If comment count hasn't changed, it's a description/other update — keep trigger
        if total_count == old_comment_count:
            log(f"  ACTIVITY {display_id}: no new comments/replies, likely description update — keeping trigger")
            filtered.append(t)
            continue

        # Find new comments/replies (after last_comment_date)
        all_entries = _flatten_all_comments(comments)
        new_entries = []
        for c in all_entries:
            comment_date = c.get("date")
            if old_last_comment_date and comment_date and str(comment_date) <= str(old_last_comment_date):
                continue
            new_entries.append(c)

        if not new_entries:
            log(f"  ACTIVITY {display_id}: count changed but no new entries found — keeping trigger")
            filtered.append(t)
            continue

        # Check if all new comments/replies are from me
        all_mine = all(
            str(c.get("user", {}).get("id", "")) == str(CLICKUP_USER_ID)
            for c in new_entries
        )

        if all_mine:
            log(f"  ACTIVITY {display_id}: all {len(new_entries)} new comment(s)/reply(ies) are self-authored — skipping")
            continue

        log(f"  ACTIVITY {display_id}: {len(new_entries)} new comment(s)/reply(ies) from others — keeping trigger")
        filtered.append(t)

    return filtered


def update_activity_state(state, display_id, comments):
    """Update activity-related state fields after successful processing.

    Counts include threaded replies for accurate change detection.
    """
    state_key = display_id
    if state_key not in state.get("tasks", {}):
        return

    state["tasks"][state_key]["comment_count"] = _count_all_comments(comments)
    latest = _latest_comment_date(comments)
    if latest != "0":
        state["tasks"][state_key]["last_comment_date"] = latest


def _has_patch_review(task_id, custom_id):
    """Check if task has patch review content (in report.md or legacy patch_review.md)."""
    for candidate_id in [custom_id, task_id]:
        if not candidate_id:
            continue
        task_dir = TASKS_DIR / candidate_id
        # New style: "## 패치 리뷰" section in report.md
        report_path = task_dir / "report.md"
        if report_path.exists():
            try:
                content = report_path.read_text(encoding="utf-8")
                if "## 패치 리뷰" in content:
                    return True
            except OSError:
                pass
        # Legacy: separate patch_review.md
        if (task_dir / "patch_review.md").exists():
            return True
    return False


def update_state_from_api(state, current_api_tasks):
    """Update state with current API task data (status, assignees).

    Also prunes stale entries — tasks no longer in the API response that
    haven't been analyzed in STATE_CLEANUP_DAYS are removed.
    """
    current_keys = set()

    for api_task in current_api_tasks:
        task_id = api_task.get("id", "")
        custom_id = get_custom_task_id(api_task)
        state_key = custom_id or task_id
        current_keys.add(state_key)
        current_status = api_task.get("status", {}).get("status", "").lower()
        assignee_ids = [a.get("id") for a in api_task.get("assignees", [])]

        # Determine report existence
        has_report = False
        for candidate_id in [custom_id, task_id]:
            if candidate_id and (TASKS_DIR / candidate_id / "report.md").exists():
                has_report = True
                break

        has_pr = _has_patch_review(task_id, custom_id)
        date_updated = api_task.get("date_updated")

        if state_key not in state["tasks"]:
            state["tasks"][state_key] = {
                "status": current_status,
                "assignee_ids": assignee_ids,
                "has_report": has_report,
                "has_patch_review": has_pr,
                "last_analysis_type": None,
                "last_analysis_time": None,
                "trigger_attempts": {},
                "date_updated": date_updated,
                "last_comment_date": None,
                "comment_count": 0
            }
        else:
            state["tasks"][state_key]["status"] = current_status
            state["tasks"][state_key]["assignee_ids"] = assignee_ids
            state["tasks"][state_key]["has_report"] = has_report
            state["tasks"][state_key]["has_patch_review"] = has_pr
            state["tasks"][state_key]["date_updated"] = date_updated

    # --- Prune stale entries ---
    if STATE_CLEANUP_DAYS > 0:
        stale_keys = []
        for key, task_data in state.get("tasks", {}).items():
            if key in current_keys:
                continue
            # Task no longer in API response (status moved outside WATCHED_STATUSES)
            last_time = task_data.get("last_analysis_time") or state.get("last_run")
            if _is_older_than_days(last_time, STATE_CLEANUP_DAYS):
                stale_keys.append(key)
        for key in stale_keys:
            del state["tasks"][key]
        if stale_keys:
            log(f"  Cleaned {len(stale_keys)} stale entries from state")


# ---------------------------------------------------------------------------
# Task download
# ---------------------------------------------------------------------------

def download_task(task_id):
    """Download a single task using fetch.py"""
    log(f"Downloading task {task_id}...")
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "fetch.py"),
        "--task-id", task_id
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT_DIR)
    )
    if result.returncode != 0:
        log(f"  Download failed: {result.stderr}")
        return False
    log(f"  Download complete")
    return True


# ---------------------------------------------------------------------------
# Analysis execution
# ---------------------------------------------------------------------------

def detect_patch_presence(task_dir):
    """Check if a task directory contains patch files (non-standard files/dirs).

    Delegates to shared.detect_patch_presence when available (single source
    of truth for exclusion lists and source-root validation).
    """
    if _shared_detect_patch is not None:
        return _shared_detect_patch(task_dir)

    # Fallback for direct execution (should not normally be reached)
    if not task_dir.exists():
        return False

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
            continue
        if item.is_dir():
            continue
        ext = item.suffix.lower()
        if ext in PATCH_SOURCE_EXTENSIONS or ext in (".zip", ".jar", ".tar", ".gz"):
            return True

    return False


def try_fetch_doc_patches(display_id, task_dir):
    """Try to download patch files from ClickUp Doc.

    Returns True if patch files were downloaded.
    """
    log(f"  Attempting to fetch Doc patches for {display_id}...")
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "fetch_doc.py"),
        "--task-id", display_id
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            timeout=60, cwd=str(ROOT_DIR)
        )
        if result.returncode == 0:
            log(f"  fetch_doc.py completed")
            return detect_patch_presence(task_dir)
        else:
            log(f"  fetch_doc.py failed (exit {result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        log(f"  fetch_doc.py timed out")
        return False
    except FileNotFoundError:
        log(f"  fetch_doc.py not found")
        return False


def try_generate_patch_diff(display_id, task_dir):
    """Run patch_diff.py to generate patch_diff.json.

    Returns True if patch_diff.json was successfully created.
    """
    log(f"  Generating patch diff for {display_id}...")
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "patch_diff.py"),
        "--task-id", display_id,
        "--output-json"
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            timeout=120, cwd=str(ROOT_DIR)
        )
        if result.returncode == 0:
            diff_json = task_dir / "patch_diff.json"
            if diff_json.exists():
                log(f"  patch_diff.json generated")
                return True
            log(f"  patch_diff.py completed but no patch_diff.json created")
            return False
        else:
            log(f"  patch_diff.py failed (exit {result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        log(f"  patch_diff.py timed out")
        return False
    except FileNotFoundError:
        log(f"  patch_diff.py not found")
        return False


def build_analysis_prompt(display_id, mode, task_dir=None):
    """Build the prompt for claude -p.

    For 'verify' mode, checks patch/package readiness and resolves
    to patch_review or verification.  Returns None if deferred (pending).
    """
    if mode == "initial":
        return f"{display_id}를 agent team으로 분석해줘"

    elif mode in ("verify", "verification"):
        has_patches = task_dir and detect_patch_presence(task_dir)

        # If no local patches, try fetching from ClickUp Doc
        if not has_patches and task_dir:
            has_patches = try_fetch_doc_patches(display_id, task_dir)

        if has_patches:
            # Generate patch_diff.json for the reviewer
            diff_json = task_dir / "patch_diff.json" if task_dir else None
            if not diff_json or not diff_json.exists():
                try_generate_patch_diff(display_id, task_dir)

            return (
                f"{display_id} 패치 리뷰해줘.\n"
                f"task_dir: {task_dir}\n"
                f".claude/agents/patch-reviewer.md 에이전트 정의를 따라\n"
                f"report.md에 '## 패치 리뷰' 섹션을 append하세요.\n"
                f"patch_review.md가 아닌 report.md에 작성합니다."
            )

        # Try version diff only if patches not found
        if task_dir:
            has_version_diff = try_generate_version_diff(display_id, task_dir)
            if has_version_diff:
                return (
                    f"{display_id} 패치 리뷰해줘.\n"
                    f"task_dir: {task_dir}\n"
                    f".claude/agents/patch-reviewer.md 에이전트 정의를 따라\n"
                    f"report.md에 '## 패치 리뷰' 섹션을 append하세요.\n"
                    f"patch_review.md가 아닌 report.md에 작성합니다."
                )

        # Nothing available — return verification fallback
        return (
            f"{display_id} 팔로업: 개발자가 수정을 완료했으므로, "
            f"수정 사항이 올바르게 구현되었는지 검증 분석을 수행해줘.\n"
            f"기존 report.md의 분석 내용을 참고하여 "
            f"report.md에 '## 검증 분석' 섹션을 append해줘."
        )

    elif mode == "reopen":
        return (
            f"{display_id} 팔로업: 이 이슈가 재발(reopened)되었습니다.\n"
            f"기존 report.md의 분석 및 패치 리뷰 내용을 참고하여\n"
            f"재발 원인을 분석하고 report.md에 '## 재발 분석' 섹션을 append해줘."
        )

    elif mode == "activity_update":
        return (
            f"{display_id} 팔로업: 이 이슈에 새로운 활동이 감지되었습니다.\n"
            f"새 댓글이나 본문 업데이트가 있으므로, "
            f"기존 report.md를 참고하여 추가 분석을 수행해줘.\n"
            f"변경된 내용이 기존 분석에 영향을 미치는지 확인하고, "
            f"필요하면 report.md에 '## 추가 분석' 섹션을 append해줘."
        )

    return f"{display_id}를 agent team으로 분석해줘"


def refresh_inventory():
    """Regenerate packages/inventory.json before analysis."""
    try:
        try:
            from .inventory import generate_inventory
        except ImportError:
            if str(SCRIPT_DIR) not in sys.path:
                sys.path.insert(0, str(SCRIPT_DIR))
            from inventory import generate_inventory  # type: ignore[import-untyped]
        inv = generate_inventory()
        inv_file = Path(ROOT_DIR) / "packages" / "inventory.json"
        with open(inv_file, "w", encoding="utf-8") as f:
            json.dump(inv, f, indent=2, ensure_ascii=False)
        pkg_count = inv.get("package_count", 0)
        unextracted = sum(1 for p in inv.get("packages", []) if not p.get("extracted", True))
        msg = f"  Inventory refreshed ({pkg_count} packages"
        if unextracted:
            msg += f", {unextracted} unextracted archives"
        msg += ")"
        log(msg)
    except Exception as e:
        log(f"  Inventory refresh failed: {e} — continuing with existing inventory")


def try_generate_version_diff(display_id, task_dir):
    """Try to generate a version diff between old and new packages.

    Returns True if patch_diff.json was successfully created.
    """
    log(f"  Checking for newer package version for {display_id}...")
    try:
        try:
            from .version_diff import generate_version_diff
        except ImportError:
            if str(SCRIPT_DIR) not in sys.path:
                sys.path.insert(0, str(SCRIPT_DIR))
            from version_diff import generate_version_diff  # type: ignore[import-untyped]

        result = generate_version_diff(display_id)
        if result:
            log(f"  Version diff: {result['old_pkg']} -> {result['new_pkg']} ({result['file_count']} files)")
            return True
        log(f"  No newer package found for version diff")
        return False
    except Exception as e:
        log(f"  Version diff failed: {e}")
        return False


def auto_decompile():
    """Auto-decompile packages with needs_decompile=True."""
    try:
        try:
            from .inventory import generate_inventory
            from .decompile_runner import run_decompile_needed
        except ImportError:
            if str(SCRIPT_DIR) not in sys.path:
                sys.path.insert(0, str(SCRIPT_DIR))
            from inventory import generate_inventory  # type: ignore[import-untyped]
            from decompile_runner import run_decompile_needed  # type: ignore[import-untyped]

        inv = generate_inventory()
        needs = [
            p for p in inv.get("packages", [])
            if p.get("needs_decompile") and p.get("extracted", True)
        ]
        if not needs:
            return

        log(f"  Auto-decompiling {len(needs)} package(s)...")
        results = run_decompile_needed(inv)
        succeeded = sum(1 for r in results if r["success"])
        log(f"  Auto-decompile complete: {succeeded}/{len(results)} succeeded")

        if succeeded > 0:
            refresh_inventory()
    except Exception as e:
        log(f"  Auto-decompile failed: {e} — continuing with existing sources")


def run_analysis(display_id, mode, dry_run=False, task_dir=None):
    """Run analysis via claude -p

    Returns True if analysis succeeded (report.md created/updated).
    """
    prompt = build_analysis_prompt(display_id, mode, task_dir=task_dir)

    cmd = [
        "claude", "-p", prompt,
        "--allowedTools",
        "Read,Glob,Grep,Bash,Write,Edit,Task,SendMessage,TeamCreate,TeamDelete,TaskCreate,TaskList,TaskGet,TaskUpdate"
    ]

    if dry_run:
        log(f"  DRY RUN: {' '.join(cmd)}")
        return True

    # Refresh inventory and auto-decompile before spawning analysis
    refresh_inventory()
    auto_decompile()

    log(f"  Running analysis ({mode}): {display_id}")
    log(f"  Timeout: {ANALYSIS_TIMEOUT}s")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=ANALYSIS_TIMEOUT,
            cwd=str(ROOT_DIR)
        )
        if result.returncode != 0:
            log(f"  Analysis failed (exit code {result.returncode})")
            if result.stderr:
                log(f"  stderr: {result.stderr[:500]}")
            return False

        log(f"  Analysis completed successfully")
        return True

    except subprocess.TimeoutExpired:
        log(f"  Analysis timed out after {ANALYSIS_TIMEOUT}s")
        return False
    except FileNotFoundError:
        log(f"  Error: 'claude' command not found. Ensure Claude CLI is in PATH.")
        return False


# ---------------------------------------------------------------------------
# Fetch-only mode (backward compatible)
# ---------------------------------------------------------------------------

def fetch_new_tasks(list_id, status="open"):
    """Fetch new tasks from ClickUp (backward compatible)"""
    log(f"Fetching new tasks from list {list_id} with status '{status}'...")

    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "fetch.py"),
        "--list-id", list_id,
        "--status", status,
        "--new-only"
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT_DIR)
    )

    if result.returncode != 0:
        log(f"Fetch failed: {result.stderr}")
        return []

    output = result.stdout
    print(output)

    fetched_ids = []
    for line in output.split("\n"):
        if "Task saved to:" in line:
            parts = line.split("/")
            for i, part in enumerate(parts):
                if part == "tasks" and i + 1 < len(parts):
                    task_id = parts[i + 1]
                    if task_id and task_id not in fetched_ids:
                        fetched_ids.append(task_id)
                    break

    return fetched_ids


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Issue Analysis Scheduler - detect state changes and trigger analysis"
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--fetch-only",
        action="store_true",
        help="Fetch new tasks only (backward compatible)"
    )
    mode_group.add_argument(
        "--detect-only",
        action="store_true",
        help="Fetch + detect triggers (no analysis)"
    )
    mode_group.add_argument(
        "--auto",
        action="store_true",
        help="Full auto: fetch + detect + analyze"
    )
    mode_group.add_argument(
        "--init-state",
        action="store_true",
        help="Build initial state.json from existing tasks/"
    )

    parser.add_argument(
        "--list-id",
        default=DEFAULT_LIST_ID,
        help=f"ClickUp list ID (default: {DEFAULT_LIST_ID or 'not set'})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing analysis"
    )

    args = parser.parse_args()

    # Validate list_id for modes that need it
    if not args.init_state and not args.list_id:
        log("Error: --list-id required (or set scheduler.list_id in config.json)")
        sys.exit(1)

    # Create logs directory
    LOGS_DIR.mkdir(exist_ok=True)

    log("=" * 60)
    log("Issue Analysis Scheduler")
    log(f"Mode: {'fetch-only' if args.fetch_only else 'detect-only' if args.detect_only else 'init-state' if args.init_state else 'auto'}")
    if not args.init_state:
        log(f"List ID: {args.list_id}")
        log(f"Watched statuses: {WATCHED_STATUSES}")
        log(f"Activity watch statuses: {ACTIVITY_WATCH_STATUSES}")
    if CLICKUP_USER_ID:
        log(f"User ID: {CLICKUP_USER_ID}")
    else:
        log("Warning: CLICKUP_USER_ID not set - assignee-based triggers disabled")
    if args.dry_run:
        log("DRY RUN enabled")
    log("=" * 60)

    # --- init-state ---
    if args.init_state:
        state = build_initial_state()
        save_state(state)
        for task_id, info in state["tasks"].items():
            report_mark = "R" if info["has_report"] else "-"
            log(f"  [{report_mark}] {task_id}: {info['status']}")
        log(f"State initialized with {len(state['tasks'])} tasks")
        return

    # --- fetch-only (backward compatible) ---
    if args.fetch_only:
        new_task_ids = fetch_new_tasks(args.list_id, DEFAULT_STATUS)
        if not new_task_ids:
            log("No new tasks fetched")
        else:
            log(f"Fetched {len(new_task_ids)} new tasks: {', '.join(new_task_ids)}")
            log("To analyze, open Claude Code and say:")
            log('  "새 이슈 분석해줘" 또는 "IMX-XXXX를 agent team으로 분석해줘"')
        return

    # --- detect-only / auto ---

    # Import fetch module for raw polling
    try:
        from .fetch import fetch_tasks_by_list_raw, fetch_comments
    except ImportError:
        sys.path.insert(0, str(SCRIPT_DIR))
        from fetch import fetch_tasks_by_list_raw, fetch_comments  # type: ignore[import-untyped]

    # Phase 1: Poll ClickUp API
    log("Phase 1: Polling ClickUp API...")
    current_api_tasks = fetch_tasks_by_list_raw(args.list_id, statuses=WATCHED_STATUSES)
    if current_api_tasks is None:
        log("Error: Failed to poll ClickUp API. Aborting.")
        sys.exit(1)
    log(f"  Found {len(current_api_tasks)} tasks across statuses")

    # Phase 2: Detect triggers
    log("Phase 2: Detecting triggers...")
    old_state = load_state()
    triggers = detect_triggers(old_state, current_api_tasks)

    # Phase 2.5: Detect activity triggers
    activity_triggers = detect_activity_triggers(old_state, current_api_tasks)
    if activity_triggers:
        log(f"  {len(activity_triggers)} activity trigger(s) detected, filtering self-triggers...")
        activity_triggers = filter_activity_self_triggers(activity_triggers, old_state)
        if activity_triggers:
            triggers.extend(activity_triggers)

    if not triggers:
        log("  No triggers detected")
    else:
        log(f"  {len(triggers)} trigger(s) detected:")
        for t in triggers:
            display = t["custom_id"] or t["task_id"]
            log(f"    [{t['mode']}] {display}: {t['reason']}")

    # Update state with current API data (regardless of triggers)
    update_state_from_api(old_state, current_api_tasks)

    if args.detect_only:
        save_state(old_state)
        log("Detect-only mode - state saved, no analysis executed")
        return

    # Phase 3: Download + Analyze
    if triggers:
        log("Phase 3: Running analysis...")

        for t in triggers:
            display_id = t["custom_id"] or t["task_id"]
            state_key = t["custom_id"] or t["task_id"]
            mode = t["mode"]

            # Ensure task is downloaded locally
            task_dir = TASKS_DIR / display_id
            if not (task_dir / "task.json").exists():
                # Try downloading by custom_id first, then by task_id
                download_id = t["custom_id"] or t["task_id"]
                if not download_task(download_id):
                    log(f"  SKIP {display_id}: download failed")
                    # Increment trigger attempt
                    task_state = old_state["tasks"].get(state_key, {})
                    attempts = task_state.get("trigger_attempts", {})
                    attempts[mode] = attempts.get(mode, 0) + 1
                    if state_key in old_state["tasks"]:
                        old_state["tasks"][state_key]["trigger_attempts"] = attempts
                    continue

            # Run analysis
            success = run_analysis(display_id, mode, dry_run=args.dry_run, task_dir=task_dir)

            if success and not args.dry_run:
                # Verify report was created/updated
                report_exists = (task_dir / "report.md").exists()
                if report_exists:
                    log(f"  SUCCESS {display_id}: report.md exists")
                    if state_key in old_state["tasks"]:
                        old_state["tasks"][state_key]["has_report"] = True
                        old_state["tasks"][state_key]["last_analysis_type"] = mode
                        old_state["tasks"][state_key]["last_analysis_time"] = datetime.now().isoformat()
                        # Reset attempt counter on success
                        old_state["tasks"][state_key]["trigger_attempts"].pop(mode, None)

                    # Update activity state after successful analysis
                    if mode == "activity_update":
                        comments = fetch_comments(display_id)
                        update_activity_state(old_state, state_key, comments)
                else:
                    log(f"  WARNING {display_id}: analysis succeeded but report.md not found")
                    task_state = old_state["tasks"].get(state_key, {})
                    attempts = task_state.get("trigger_attempts", {})
                    attempts[mode] = attempts.get(mode, 0) + 1
                    if state_key in old_state["tasks"]:
                        old_state["tasks"][state_key]["trigger_attempts"] = attempts
            elif not success:
                # Increment trigger attempt on failure
                task_state = old_state["tasks"].get(state_key, {})
                attempts = task_state.get("trigger_attempts", {})
                attempts[mode] = attempts.get(mode, 0) + 1
                if state_key in old_state["tasks"]:
                    old_state["tasks"][state_key]["trigger_attempts"] = attempts
                log(f"  FAIL {display_id}: attempt {attempts.get(mode, 0)}/{MAX_TRIGGER_ATTEMPTS}")

    # Phase 4: Save state
    save_state(old_state)

    log("=" * 60)
    log("Scheduler finished")
    if triggers:
        log(f"  Triggers processed: {len(triggers)}")
    log("=" * 60)


if __name__ == "__main__":
    main()
