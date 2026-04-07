"""Wiki updater - detect wiki-eligible tasks and spawn wiki-writer agent."""

import json
import subprocess
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.absolute()
ROOT_DIR = SCRIPT_DIR.parent

# Load config
with open(ROOT_DIR / "config" / "config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

WIKI_CONFIG = config.get("scheduler", {}).get("wiki", {})
WIKI_ENABLED = WIKI_CONFIG.get("enabled", False)
WIKI_STATUSES = set(WIKI_CONFIG.get("wiki_statuses", ["closed"]))
WIKI_ELAPSED_STATUSES = set(WIKI_CONFIG.get("wiki_elapsed_statuses", ["qa deploy", "qa completed"]))
WIKI_ELAPSED_DAYS = WIKI_CONFIG.get("wiki_elapsed_days", 14)

TASKS_DIR = ROOT_DIR / config.get("tasks_dir", "tasks")
WIKI_DIR = ROOT_DIR / "wiki"
STATE_FILE = TASKS_DIR / "state.json"

ANALYSIS_TIMEOUT = config.get("scheduler", {}).get("analysis_timeout_seconds", 600)


def log(message):
    print(f"[wiki] {datetime.now().strftime('%H:%M:%S')} {message}")


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_run": None, "tasks": {}}


def save_state(state):
    state["last_run"] = datetime.now().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def check_wiki_triggers(tasks_state: dict) -> list:
    """Scan state.json tasks and return list of wiki-eligible triggers.

    A task is eligible when:
    1. status in WIKI_STATUSES (e.g. "closed") - immediate trigger
    2. status in WIKI_ELAPSED_STATUSES (e.g. "qa deploy") AND
       date_updated is older than WIKI_ELAPSED_DAYS - elapsed trigger

    Filters:
    - has_report must be True
    - wiki_updated must not be True (already processed)
    """
    if not WIKI_ENABLED:
        return []

    triggers = []
    now = datetime.now()

    for task_id, info in tasks_state.items():
        # Skip if already wiki-updated or no report
        if info.get("wiki_updated"):
            continue
        if not info.get("has_report"):
            continue

        status = (info.get("status") or "").lower()

        # Immediate trigger: closed
        if status in WIKI_STATUSES:
            triggers.append({
                "task_id": task_id,
                "reason": f"status={status}",
            })
            continue

        # Elapsed trigger: qa deploy / qa completed + N days
        if status in WIKI_ELAPSED_STATUSES:
            date_updated_str = info.get("date_updated")
            if not date_updated_str:
                continue

            # ClickUp date_updated is millisecond timestamp string
            try:
                date_updated = datetime.fromtimestamp(int(date_updated_str) / 1000)
            except (ValueError, TypeError, OSError):
                continue

            elapsed = now - date_updated
            if elapsed >= timedelta(days=WIKI_ELAPSED_DAYS):
                triggers.append({
                    "task_id": task_id,
                    "reason": f"status={status}, elapsed={elapsed.days}d",
                })

    return triggers


def run_wiki_update(task_id: str, dry_run: bool = False) -> bool:
    """Spawn wiki-writer agent to update wiki for a given task.

    Returns True on success.
    """
    task_dir = TASKS_DIR / task_id
    if not (task_dir / "report.md").exists():
        log(f"SKIP {task_id}: no report.md")
        return False

    prompt = (
        f"{task_id} 위키 갱신해줘.\n"
        f"task_dir: {task_dir}\n"
        f"wiki_dir: {WIKI_DIR}\n"
        f".claude/agents/wiki-writer.md 에이전트 정의를 따라\n"
        f"wiki/ 디렉토리의 페이지를 갱신하세요."
    )

    cmd = [
        "claude", "-p", prompt,
        "--allowedTools",
        "Read,Glob,Grep,Write,Edit"
    ]

    if dry_run:
        log(f"DRY RUN: {task_id} - would run wiki-writer agent")
        return True

    log(f"Running wiki-writer for {task_id}...")
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
            log(f"FAIL {task_id}: exit code {result.returncode}")
            if result.stderr:
                log(f"  stderr: {result.stderr[:500]}")
            return False

        log(f"SUCCESS {task_id}: wiki updated")
        return True

    except subprocess.TimeoutExpired:
        log(f"TIMEOUT {task_id}: wiki update timed out after {ANALYSIS_TIMEOUT}s")
        return False
    except FileNotFoundError:
        log(f"ERROR: 'claude' command not found")
        return False


def mark_wiki_updated(state: dict, task_id: str) -> None:
    """Mark a task as wiki-updated in state.json."""
    if task_id in state.get("tasks", {}):
        state["tasks"][task_id]["wiki_updated"] = True
        state["tasks"][task_id]["wiki_updated_at"] = datetime.now().isoformat()


def process_wiki_triggers(triggers: list, dry_run: bool = False) -> list:
    """Process wiki triggers: run wiki-writer for each, update state.

    Returns list of successfully processed task IDs.
    """
    if not triggers:
        return []

    state = load_state()
    processed = []

    for t in triggers:
        task_id = t["task_id"]
        log(f"Processing {task_id} ({t['reason']})")

        success = run_wiki_update(task_id, dry_run=dry_run)
        if success and not dry_run:
            mark_wiki_updated(state, task_id)
            processed.append(task_id)

    if processed:
        save_state(state)

    return processed


def _is_wiki_eligible_status(task_dir: Path) -> tuple:
    """Check if a task's status qualifies for wiki update.

    Returns (eligible: bool, reason: str).
    Uses task.json status field since state.json may not have all tasks.
    """
    task_json = task_dir / "task.json"
    if not task_json.exists():
        return False, "no task.json"

    with open(task_json, "r", encoding="utf-8") as f:
        task_data = json.load(f)

    status = (task_data.get("status", "") or "").lower()

    # Immediate: closed
    if status in WIKI_STATUSES:
        return True, f"status={status}"

    # Elapsed: qa deploy / qa completed + N days
    if status in WIKI_ELAPSED_STATUSES:
        date_updated_str = task_data.get("date_updated")
        if date_updated_str:
            try:
                date_updated = datetime.fromtimestamp(int(date_updated_str) / 1000)
                elapsed = datetime.now() - date_updated
                if elapsed >= timedelta(days=WIKI_ELAPSED_DAYS):
                    return True, f"status={status}, elapsed={elapsed.days}d"
                return False, f"status={status}, only {elapsed.days}d elapsed (need {WIKI_ELAPSED_DAYS})"
            except (ValueError, TypeError, OSError):
                pass

    return False, f"status={status} (not eligible)"


def seed_wiki(dry_run: bool = False) -> None:
    """Seed wiki from wiki-eligible tasks in tasks/.

    Only processes tasks that meet wiki trigger criteria:
    - status is closed, OR
    - status is qa deploy/qa completed AND 14+ days elapsed
    """
    if not TASKS_DIR.exists():
        log("No tasks/ directory found")
        return

    all_tasks = []
    candidates = []
    skipped_status = 0

    for task_dir in sorted(TASKS_DIR.iterdir()):
        if not task_dir.is_dir():
            continue
        if not (task_dir / "report.md").exists():
            continue
        if not (task_dir / "task.json").exists():
            continue

        all_tasks.append(task_dir.name)

        eligible, reason = _is_wiki_eligible_status(task_dir)
        if eligible:
            candidates.append({"task_id": task_dir.name, "reason": reason})
        else:
            skipped_status += 1

    log(f"Found {len(all_tasks)} tasks with report.md")
    log(f"  Wiki-eligible: {len(candidates)}, skipped (status): {skipped_status}")

    if not candidates:
        return

    state = load_state()
    processed = 0

    for c in candidates:
        task_id = c["task_id"]

        # Skip already wiki-updated
        task_state = state.get("tasks", {}).get(task_id, {})
        if task_state.get("wiki_updated"):
            log(f"SKIP {task_id}: already wiki-updated")
            continue

        log(f"Seeding {task_id} ({c['reason']})")
        success = run_wiki_update(task_id, dry_run=dry_run)
        if success and not dry_run:
            # Ensure task exists in state
            if task_id not in state.get("tasks", {}):
                state.setdefault("tasks", {})[task_id] = {}
            mark_wiki_updated(state, task_id)
            processed += 1
            save_state(state)  # Save after each to preserve progress

    log(f"Seeding complete: {processed}/{len(candidates)} eligible tasks processed")


def main():
    parser = argparse.ArgumentParser(
        description="Wiki Updater - maintain wiki from analyzed issues"
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--check",
        action="store_true",
        help="Check for wiki-eligible triggers (no update)"
    )
    mode_group.add_argument(
        "--run",
        action="store_true",
        help="Check and run wiki updates"
    )
    mode_group.add_argument(
        "--seed",
        action="store_true",
        help="Seed wiki from all existing report.md files"
    )
    mode_group.add_argument(
        "--update-task",
        metavar="TASK_ID",
        help="Run wiki update for a specific task"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing"
    )

    args = parser.parse_args()

    log("=" * 50)
    log("Wiki Updater")
    log("=" * 50)

    if args.seed:
        seed_wiki(dry_run=args.dry_run)
        return

    if args.update_task:
        success = run_wiki_update(args.update_task, dry_run=args.dry_run)
        if success and not args.dry_run:
            state = load_state()
            mark_wiki_updated(state, args.update_task)
            save_state(state)
        return

    # --check or --run
    state = load_state()
    triggers = check_wiki_triggers(state.get("tasks", {}))

    if not triggers:
        log("No wiki-eligible triggers found")
        return

    log(f"Found {len(triggers)} wiki-eligible trigger(s):")
    for t in triggers:
        log(f"  {t['task_id']}: {t['reason']}")

    if args.check:
        log("Check-only mode - no updates executed")
        return

    # --run
    processed = process_wiki_triggers(triggers, dry_run=args.dry_run)
    log(f"Processed: {len(processed)} task(s)")


if __name__ == "__main__":
    main()
