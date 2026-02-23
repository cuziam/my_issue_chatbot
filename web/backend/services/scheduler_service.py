"""Service layer wrapping scheduler.py functions.

All issuebot imports are done lazily inside function bodies to avoid
module-level side effects.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from ..config import TASKS_DIR, ISSUEBOT_DIR, ROOT_DIR

STATE_FILE = TASKS_DIR / "state.json"


# ---------------------------------------------------------------------------
# State file helpers (no issuebot imports needed)
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Load state.json, returning an empty state dict if the file is missing."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"last_run": None, "tasks": {}}
    return {"last_run": None, "tasks": {}}


def save_state(data: dict) -> None:
    """Write state dict to state.json."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def reset_trigger_attempts(task_id: str, mode: Optional[str] = None) -> dict:
    """Reset trigger_attempts for a task in state.json.

    If *mode* is provided, only that mode's counter is cleared.
    Otherwise all counters are cleared.
    """
    state = load_state()
    task_state = state.get("tasks", {}).get(task_id)
    if not task_state:
        return {"status": "not_found", "message": f"Task {task_id} not in state.json"}

    if mode:
        task_state.get("trigger_attempts", {}).pop(mode, None)
    else:
        task_state["trigger_attempts"] = {}

    save_state(state)
    return {"status": "ok", "message": f"Reset trigger_attempts for {task_id}"}


# ---------------------------------------------------------------------------
# Scheduler operations (lazy imports)
# ---------------------------------------------------------------------------

async def detect_triggers() -> dict:
    """Run trigger detection: fetch current tasks from ClickUp and compare
    with the saved state.
    """

    def _run() -> dict:
        sys.path.insert(0, str(ISSUEBOT_DIR))
        from scheduler import (  # type: ignore[import-untyped]
            detect_triggers as _detect_triggers,
            detect_activity_triggers as _detect_activity_triggers,
            load_state as _load_state,
            WATCHED_STATUSES,
            SCHEDULER_CONFIG,
        )
        from fetch import fetch_tasks_by_list_raw  # type: ignore[import-untyped]

        list_id = SCHEDULER_CONFIG.get("list_id", "")
        if not list_id:
            return {"status": "error", "message": "scheduler.list_id not configured"}

        old_state = _load_state()
        api_tasks = fetch_tasks_by_list_raw(list_id, statuses=WATCHED_STATUSES)
        if api_tasks is None:
            return {"status": "error", "message": "Failed to poll ClickUp API"}

        triggers = _detect_triggers(old_state, api_tasks)
        activity = _detect_activity_triggers(old_state, api_tasks)
        triggers.extend(activity)

        return {
            "status": "ok",
            "api_task_count": len(api_tasks),
            "triggers": triggers,
        }

    return await asyncio.to_thread(_run)


async def run_scheduler(dry_run: bool = True) -> dict:
    """Run the full scheduler as a subprocess.

    Defaults to *dry_run=True* for safety in the web context.
    """
    cmd = [
        sys.executable,
        str(ISSUEBOT_DIR / "scheduler.py"),
        "--auto",
    ]
    if dry_run:
        cmd.append("--dry-run")

    def _run() -> dict:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(ROOT_DIR),
            timeout=120,
        )
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }

    return await asyncio.to_thread(_run)


async def init_state() -> dict:
    """Build initial state.json from the existing tasks/ directory."""

    def _run() -> dict:
        sys.path.insert(0, str(ISSUEBOT_DIR))
        from scheduler import build_initial_state, save_state as _save_state  # type: ignore[import-untyped]

        state = build_initial_state()
        _save_state(state)
        return {"status": "ok", "task_count": len(state.get("tasks", {}))}

    return await asyncio.to_thread(_run)
