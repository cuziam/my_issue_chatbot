#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Issue Analysis Scheduler
Automatically fetches new ClickUp tasks and runs analysis.
Designed to be run via cron job.

Usage:
    # Run manually
    python scheduler.py

    # Cron example (every hour)
    0 * * * * cd /mnt/d/jar-decompiler && ~/jar-decompiler-venv/bin/python issuebot/scheduler.py >> logs/scheduler.log 2>&1
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

# Scheduler config (with defaults)
SCHEDULER_CONFIG = config.get("scheduler", {})
DEFAULT_LIST_ID = SCHEDULER_CONFIG.get("list_id", "")
DEFAULT_STATUS = SCHEDULER_CONFIG.get("filter_status", "open")
AUTO_ANALYZE = SCHEDULER_CONFIG.get("auto_analyze", True)
TEMPLATE = SCHEDULER_CONFIG.get("template", "issue_analysis")

# Logs directory
LOGS_DIR = ROOT_DIR / "logs"


def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


def fetch_new_tasks(list_id, status="open"):
    """Fetch new tasks from ClickUp"""
    log(f"Fetching new tasks from list {list_id} with status '{status}'...")

    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "fetch.py"),
        "--list-id", list_id,
        "--status", status,
        "--new-only"
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT_DIR)
    )

    if result.returncode != 0:
        log(f"Fetch failed: {result.stderr}")
        return []

    # Parse output to get fetched task IDs
    output = result.stdout
    print(output)  # Show fetch output

    # Extract task IDs from "Task saved to" lines
    fetched_ids = []
    for line in output.split("\n"):
        if "Task saved to:" in line:
            # Extract task ID from path like /mnt/d/.../tasks/86xxxxx/task.json
            parts = line.split("/")
            for i, part in enumerate(parts):
                if part == "tasks" and i + 1 < len(parts):
                    task_id = parts[i + 1]
                    if task_id and task_id not in fetched_ids:
                        fetched_ids.append(task_id)
                    break

    return fetched_ids


def analyze_task(task_id, template="issue_analysis"):
    """Run analysis on a single task"""
    log(f"Analyzing task: {task_id}")

    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "analyze.py"),
        "--task-id", task_id,
        "--template", template
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT_DIR)
    )

    if result.returncode == 0:
        log(f"Analysis complete for {task_id}")
        return True
    else:
        log(f"Analysis failed for {task_id}: {result.stderr}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Automatically fetch and analyze new ClickUp tasks"
    )
    parser.add_argument(
        "--list-id",
        default=DEFAULT_LIST_ID,
        help=f"ClickUp list ID to fetch from (default: {DEFAULT_LIST_ID or 'not set'})"
    )
    parser.add_argument(
        "--status",
        default=DEFAULT_STATUS,
        help=f"Task status to filter (default: {DEFAULT_STATUS})"
    )
    parser.add_argument(
        "--template",
        default=TEMPLATE,
        choices=["issue_analysis", "spec_inquiry", "improvement_request"],
        help=f"Analysis template (default: {TEMPLATE})"
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Only fetch tasks, don't run analysis"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it"
    )

    args = parser.parse_args()

    # Validate list_id
    if not args.list_id:
        log("Error: --list-id is required (or set scheduler.list_id in config.json)")
        sys.exit(1)

    # Create logs directory
    LOGS_DIR.mkdir(exist_ok=True)

    log("=" * 60)
    log("Issue Analysis Scheduler Started")
    log(f"List ID: {args.list_id}")
    log(f"Status filter: {args.status}")
    log(f"Template: {args.template}")
    log(f"Fetch only: {args.fetch_only}")
    log(f"Dry run: {args.dry_run}")
    log("=" * 60)

    if args.dry_run:
        log("DRY RUN - No actual actions will be performed")
        log(f"Would fetch tasks from list {args.list_id} with status '{args.status}'")
        if not args.fetch_only:
            log("Would analyze any new tasks found")
        return

    # Step 1: Fetch new tasks
    new_task_ids = fetch_new_tasks(args.list_id, args.status)

    if not new_task_ids:
        log("No new tasks to process")
        log("Scheduler finished")
        return

    log(f"Found {len(new_task_ids)} new tasks: {', '.join(new_task_ids)}")

    # Step 2: Analyze tasks (if not fetch-only)
    if args.fetch_only:
        log("Fetch-only mode, skipping analysis")
    else:
        log("Starting analysis...")
        success_count = 0
        fail_count = 0

        for task_id in new_task_ids:
            success = analyze_task(task_id, args.template)
            if success:
                success_count += 1
            else:
                fail_count += 1

        log("-" * 60)
        log(f"Analysis complete: {success_count} success, {fail_count} failed")

    log("=" * 60)
    log("Scheduler finished")


if __name__ == "__main__":
    main()
