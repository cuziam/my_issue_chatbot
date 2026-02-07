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
ANALYSIS_TIMEOUT = SCHEDULER_CONFIG.get("analysis_timeout_seconds", 600)

# Directories
TASKS_DIR = ROOT_DIR / config.get("tasks_dir", "tasks")
LOGS_DIR = ROOT_DIR / "logs"
STATE_FILE = TASKS_DIR / "state.json"

# ClickUp User ID for assignee matching
CLICKUP_USER_ID = os.getenv("CLICKUP_USER_ID", "")

# Max consecutive failures before skipping a task
MAX_TRIGGER_ATTEMPTS = 3


def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


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
        assignee_ids = [a.get("id") for a in task_data.get("assignees", []) if a.get("id")]

        state["tasks"][task_id] = {
            "status": task_data.get("status", ""),
            "assignee_ids": assignee_ids,
            "has_report": has_report,
            "last_analysis_type": "initial" if has_report else None,
            "last_analysis_time": None,
            "trigger_attempts": {}
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


def detect_triggers(old_state, current_api_tasks):
    """Compare old state with current API tasks and detect triggers

    Returns list of dicts: [{"task_id": ..., "custom_id": ..., "mode": "initial"|"verification", "reason": ...}]
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

        # Check trigger attempt limits
        if old_task:
            attempts = old_task.get("trigger_attempts", {})
            for mode, count in attempts.items():
                if count >= MAX_TRIGGER_ATTEMPTS:
                    log(f"  SKIP {display_id}: exceeded {MAX_TRIGGER_ATTEMPTS} attempts for {mode}")

        # Determine report existence
        # Check both custom_id and task_id directories
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

        # --- Trigger rules ---

        if current_status == "open":
            if old_task is None:
                # New open task
                triggers.append({
                    "task_id": task_id,
                    "custom_id": custom_id,
                    "mode": "initial",
                    "reason": f"New open task: {display_id}"
                })
            # Existing open task: no trigger (already processed)

        elif current_status == "qa assigned":
            if is_my_task(assignee_ids):
                if not has_report:
                    # Check attempt limit
                    attempt_count = (old_task or {}).get("trigger_attempts", {}).get("initial", 0)
                    if attempt_count < MAX_TRIGGER_ATTEMPTS:
                        triggers.append({
                            "task_id": task_id,
                            "custom_id": custom_id,
                            "mode": "initial",
                            "reason": f"QA assigned to me, no report: {display_id}"
                        })
                # Has report: skip (already analyzed)
            # Not my task: skip

        elif current_status == "qa to do":
            if is_my_task(assignee_ids):
                old_status = (old_task or {}).get("status", "")
                if old_status != "qa to do":
                    # Status transitioned TO qa to do
                    attempt_count = (old_task or {}).get("trigger_attempts", {}).get("verification", 0)
                    if attempt_count < MAX_TRIGGER_ATTEMPTS:
                        if has_report:
                            triggers.append({
                                "task_id": task_id,
                                "custom_id": custom_id,
                                "mode": "verification",
                                "reason": f"Transitioned to qa to do: {display_id}"
                            })
                        else:
                            triggers.append({
                                "task_id": task_id,
                                "custom_id": custom_id,
                                "mode": "initial",
                                "reason": f"Transitioned to qa to do (no report): {display_id}"
                            })

    return triggers


def update_state_from_api(state, current_api_tasks):
    """Update state with current API task data (status, assignees)"""
    for api_task in current_api_tasks:
        task_id = api_task.get("id", "")
        custom_id = get_custom_task_id(api_task)
        state_key = custom_id or task_id
        current_status = api_task.get("status", {}).get("status", "").lower()
        assignee_ids = [a.get("id") for a in api_task.get("assignees", [])]

        # Determine report existence
        has_report = False
        for candidate_id in [custom_id, task_id]:
            if candidate_id and (TASKS_DIR / candidate_id / "report.md").exists():
                has_report = True
                break

        if state_key not in state["tasks"]:
            state["tasks"][state_key] = {
                "status": current_status,
                "assignee_ids": assignee_ids,
                "has_report": has_report,
                "last_analysis_type": None,
                "last_analysis_time": None,
                "trigger_attempts": {}
            }
        else:
            state["tasks"][state_key]["status"] = current_status
            state["tasks"][state_key]["assignee_ids"] = assignee_ids
            state["tasks"][state_key]["has_report"] = has_report


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

def build_analysis_prompt(display_id, mode):
    """Build the prompt for claude -p"""
    if mode == "initial":
        return f"{display_id}를 agent team으로 분석해줘"
    elif mode == "verification":
        return (
            f"{display_id} 팔로업: 이 이슈는 \"qa to do\" 상태로 전환되었습니다.\n"
            f"개발자가 수정을 완료했으므로, 수정 사항이 올바르게 구현되었는지 검증 분석을 수행해줘.\n"
            f"기존 report.md의 \"참고: 코드 레벨 원인\"에 명시된 수정 방안이 실제로 반영되었는지 확인하고,\n"
            f"QA 검증 시나리오를 업데이트해줘."
        )
    return f"{display_id}를 agent team으로 분석해줘"


def run_analysis(display_id, mode, dry_run=False):
    """Run analysis via claude -p

    Returns True if analysis succeeded (report.md created/updated).
    """
    prompt = build_analysis_prompt(display_id, mode)

    cmd = [
        "claude", "-p", prompt,
        "--allowedTools",
        "Read,Glob,Grep,Bash,Write,Edit,Task,SendMessage,TeamCreate,TeamDelete,TaskCreate,TaskList,TaskGet,TaskUpdate"
    ]

    if dry_run:
        log(f"  DRY RUN: {' '.join(cmd)}")
        return True

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
    sys.path.insert(0, str(SCRIPT_DIR))
    from fetch import fetch_tasks_by_list_raw

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
            success = run_analysis(display_id, mode, dry_run=args.dry_run)

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
