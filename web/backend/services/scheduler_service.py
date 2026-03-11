"""Service layer wrapping scheduler.py functions.

All issuebot imports are done lazily inside function bodies to avoid
module-level side effects.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from ..config import TASKS_DIR, ROOT_DIR, load_config
from ..ws.manager import manager

logger = logging.getLogger(__name__)

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

    Returns dict with status, api_task_count, triggers, and _api_tasks
    (the raw API task list for state updates).
    """

    def _run() -> dict:
        from issuebot.scheduler import (
            detect_triggers as _detect_triggers,
            detect_activity_triggers as _detect_activity_triggers,
            load_state as _load_state,
            WATCHED_STATUSES,
            SCHEDULER_CONFIG,
        )
        from issuebot.fetch import fetch_tasks_by_list_raw

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
            "_api_tasks": api_tasks,  # raw API data for state updates
        }

    return await asyncio.to_thread(_run)


async def update_state_from_api(api_tasks: list) -> None:
    """Update state.json with current API task data."""

    def _run() -> None:
        from issuebot.scheduler import (
            update_state_from_api as _update_state,
            save_state as _save_state,
            load_state as _load_state,
        )
        state = _load_state()
        _update_state(state, api_tasks)
        _save_state(state)

    await asyncio.to_thread(_run)


async def increment_trigger_attempt(task_id: str, mode: str) -> None:
    """Increment trigger_attempts[mode] for a task in state.json."""

    def _run() -> None:
        state = load_state()
        tasks = state.get("tasks", {})
        if task_id in tasks:
            attempts = tasks[task_id].setdefault("trigger_attempts", {})
            attempts[mode] = attempts.get(mode, 0) + 1
            save_state(state)

    await asyncio.to_thread(_run)


async def dismiss_trigger(task_id: str, mode: str) -> None:
    """Set trigger_attempts[mode] to max (3) to prevent re-triggering.

    Creates a minimal state entry if the task doesn't exist yet (e.g. new
    open tasks that haven't been added to state.json via update_state_from_api).
    """

    def _run() -> None:
        state = load_state()
        tasks = state.setdefault("tasks", {})
        if task_id not in tasks:
            # Create minimal entry so the dismiss persists
            tasks[task_id] = {
                "status": "unknown",
                "assignee_ids": [],
                "has_report": False,
                "has_patch_review": False,
                "last_analysis_type": None,
                "last_analysis_time": None,
                "trigger_attempts": {},
                "date_updated": None,
                "last_comment_date": None,
                "comment_count": 0,
            }
        attempts = tasks[task_id].setdefault("trigger_attempts", {})
        attempts[mode] = 3  # MAX_TRIGGER_ATTEMPTS
        save_state(state)

    await asyncio.to_thread(_run)


async def ensure_task_downloaded(task_id: str, refresh: bool = False) -> bool:
    """Ensure task data is downloaded. Returns True if ready.

    Uses fetch.py's fetch_task + fetch_comments + save_task to download
    and persist the task data, matching the pattern used by the tasks router.

    If *refresh* is True and task.json already exists, metadata and comments
    are refreshed from the ClickUp API while preserving existing attachments.
    """
    task_dir = TASKS_DIR / task_id
    if (task_dir / "task.json").exists():
        if refresh:
            def _refresh() -> None:
                from issuebot.fetch import refresh_task
                try:
                    refresh_task(task_id)
                except Exception as e:
                    logger.warning("Failed to refresh task %s: %s", task_id, e)
            await asyncio.to_thread(_refresh)
        return True

    # Try to download
    def _download() -> bool:
        from issuebot.fetch import (
            fetch_task as _fetch,
            fetch_comments as _fetch_comments,
            save_task as _save,
        )
        try:
            data = _fetch(task_id)
            if not data:
                logger.warning("fetch_task returned None for %s", task_id)
                return False
            comments = _fetch_comments(task_id)
            _save(task_id, data, comments)
            return (task_dir / "task.json").exists()
        except Exception as e:
            logger.error("Failed to download task %s: %s", task_id, e)
            return False

    return await asyncio.to_thread(_download)


async def init_state() -> dict:
    """Build initial state.json from the existing tasks/ directory."""

    def _run() -> dict:
        from issuebot.scheduler import build_initial_state, save_state as _save_state

        state = build_initial_state()
        _save_state(state)
        return {"status": "ok", "task_count": len(state.get("tasks", {}))}

    return await asyncio.to_thread(_run)


# ---------------------------------------------------------------------------
# SchedulerPoller — background polling loop
# ---------------------------------------------------------------------------

class SchedulerPoller:
    """FastAPI process-internal background polling loop.

    Periodically calls detect_triggers() and optionally starts analysis jobs.
    Controlled via REST endpoints; state is broadcast via WebSocket.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._enabled: bool = False
        self._interval_minutes: int = 30
        self._last_poll: datetime | None = None
        self._last_poll_result: dict | None = None
        self._poll_count: int = 0
        self._error_count: int = 0
        self._last_error: str | None = None
        self._auto_analyze: bool = True
        self._lock = asyncio.Lock()  # serialize state.json access
        self._pending_triggers: list[dict] = []
        self._poll_log: list[dict] = []  # recent poll activity log
        self._next_poll_time: datetime | None = None

    @property
    def status(self) -> dict:
        """Return current poller status for API responses / WS broadcasts."""
        return {
            "enabled": self._enabled,
            "interval_minutes": self._interval_minutes,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
            "last_poll_result": self._last_poll_result,
            "poll_count": self._poll_count,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "auto_analyze": self._auto_analyze,
            "next_poll": self._next_poll_time.isoformat() if self._next_poll_time else None,
            "pending_triggers": self._pending_triggers,
            "poll_log": self._poll_log[-20:],  # last 20 entries
        }

    async def start(self, interval_minutes: int = 30, auto_analyze: bool = True) -> None:
        """Start the background polling loop."""
        if self._enabled and self._task and not self._task.done():
            # Already running — just update config
            self._interval_minutes = interval_minutes
            self._auto_analyze = auto_analyze
            await manager.broadcast({"type": "scheduler_status", "status": self.status})
            return

        self._interval_minutes = interval_minutes
        self._auto_analyze = auto_analyze
        self._enabled = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("SchedulerPoller started: interval=%dm, auto_analyze=%s",
                     interval_minutes, auto_analyze)
        await manager.broadcast({"type": "scheduler_status", "status": self.status})

    async def stop(self) -> None:
        """Stop the background polling loop."""
        self._enabled = False
        self._next_poll_time = None
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("SchedulerPoller stopped")
        await manager.broadcast({"type": "scheduler_status", "status": self.status})

    async def poll_once(self) -> dict:
        """Execute a single poll cycle immediately (manual "Poll Now")."""
        async with self._lock:
            return await self._do_poll()

    async def update_config(
        self,
        interval_minutes: int | None = None,
        auto_analyze: bool | None = None,
    ) -> None:
        """Update poller configuration at runtime."""
        if interval_minutes is not None:
            self._interval_minutes = interval_minutes
        if auto_analyze is not None:
            self._auto_analyze = auto_analyze
        await manager.broadcast({"type": "scheduler_status", "status": self.status})

    async def analyze_triggers(self, triggers: list[dict]) -> list[dict]:
        """Start analysis for the given triggers. Returns list of started jobs."""
        from . import analysis as _analysis

        started_jobs: list[dict] = []
        for t in triggers:
            task_id = t.get("custom_id") or t.get("task_id", "")
            mode = t.get("mode", "initial")

            # Ensure task is downloaded (refresh metadata since trigger = ClickUp change)
            ready = await ensure_task_downloaded(task_id, refresh=True)
            if not ready:
                logger.warning("Task %s not downloadable, skipping analysis", task_id)
                continue

            # Map trigger mode to analysis mode
            analysis_mode = mode
            if mode == "verification":
                analysis_mode = "review"  # auto-resolve patch_review vs verification
            elif mode == "activity_update":
                analysis_mode = "review"

            job = await _analysis.start_analysis(task_id, analysis_mode)
            if job.get("status") == "error":
                logger.warning("Failed to start analysis for %s: %s", task_id, job.get("message"))
                continue

            started_jobs.append({
                "job_id": job["id"],
                "task_id": task_id,
                "mode": analysis_mode,
                "trigger_reason": t.get("reason", ""),
            })

            # Increment attempt counter
            await increment_trigger_attempt(task_id, mode)

            # Remove from pending
            self._pending_triggers = [
                p for p in self._pending_triggers
                if not (p.get("custom_id", p.get("task_id")) == task_id and p.get("mode") == mode)
            ]

        return started_jobs

    async def dismiss_triggers(self, triggers: list[dict]) -> int:
        """Dismiss triggers (set attempts to max to prevent re-triggering)."""
        count = 0
        for t in triggers:
            task_id = t.get("custom_id") or t.get("task_id", "")
            mode = t.get("mode", "")
            await dismiss_trigger(task_id, mode)

            # Remove from pending
            self._pending_triggers = [
                p for p in self._pending_triggers
                if not (p.get("custom_id", p.get("task_id")) == task_id and p.get("mode") == mode)
            ]
            count += 1

        await manager.broadcast({"type": "scheduler_status", "status": self.status})
        return count

    # ---- Internal ----

    async def _poll_loop(self) -> None:
        """Main polling loop. Runs until stopped or cancelled."""
        try:
            while self._enabled:
                async with self._lock:
                    await self._do_poll()

                # Calculate next poll time and sleep
                if not self._enabled:
                    break
                self._next_poll_time = datetime.now(timezone.utc) + \
                    timedelta(minutes=self._interval_minutes)
                await manager.broadcast({"type": "scheduler_status", "status": self.status})

                # Sleep in small increments so we can stop quickly
                remaining = self._interval_minutes * 60
                while remaining > 0 and self._enabled:
                    await asyncio.sleep(min(remaining, 5))
                    remaining -= 5

        except asyncio.CancelledError:
            logger.info("SchedulerPoller loop cancelled")
        except Exception:
            logger.exception("SchedulerPoller loop crashed")
            self._enabled = False
            self._error_count += 1
            await manager.broadcast({"type": "scheduler_status", "status": self.status})

    async def _do_poll(self) -> dict:
        """Execute a single poll: detect triggers, optionally start analyses."""
        self._poll_count += 1
        now = datetime.now(timezone.utc)
        self._last_poll = now

        await manager.broadcast({
            "type": "scheduler_poll_started",
            "poll_count": self._poll_count,
            "timestamp": now.isoformat(),
        })

        try:
            result = await detect_triggers()
        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)
            error_result = {
                "status": "error",
                "message": str(e),
                "trigger_count": 0,
                "triggers": [],
                "started_jobs": [],
                "timestamp": now.isoformat(),
            }
            self._last_poll_result = error_result
            self._poll_log.append({
                "poll_count": self._poll_count,
                "timestamp": now.isoformat(),
                "status": "error",
                "error": str(e),
            })
            await manager.broadcast({
                "type": "scheduler_poll_completed",
                "result": error_result,
                "timestamp": now.isoformat(),
            })
            return error_result

        if result.get("status") != "ok":
            self._error_count += 1
            self._last_error = result.get("message", "Unknown error")
            self._last_poll_result = result
            self._poll_log.append({
                "poll_count": self._poll_count,
                "timestamp": now.isoformat(),
                "status": "error",
                "error": result.get("message"),
            })
            await manager.broadcast({
                "type": "scheduler_poll_completed",
                "result": result,
                "timestamp": now.isoformat(),
            })
            return result

        triggers = result.get("triggers", [])
        api_tasks = result.pop("_api_tasks", [])

        # Update state.json with current API data
        if api_tasks:
            try:
                await update_state_from_api(api_tasks)
            except Exception as e:
                logger.warning("Failed to update state from API: %s", e)

        # Handle triggers
        started_jobs: list[dict] = []
        if triggers:
            if self._auto_analyze:
                # Auto-analyze: start jobs immediately (sequential)
                started_jobs = await self.analyze_triggers(triggers)
            else:
                # Detect-only: accumulate to pending list
                for t in triggers:
                    # Avoid duplicates
                    tid = t.get("custom_id", t.get("task_id"))
                    mode = t.get("mode")
                    exists = any(
                        (p.get("custom_id", p.get("task_id")) == tid and p.get("mode") == mode)
                        for p in self._pending_triggers
                    )
                    if not exists:
                        self._pending_triggers.append(t)

        self._last_error = None
        poll_result = {
            "status": "ok",
            "api_task_count": result.get("api_task_count", 0),
            "trigger_count": len(triggers),
            "triggers": triggers,
            "started_jobs": started_jobs,
            "timestamp": now.isoformat(),
        }
        self._last_poll_result = poll_result
        self._poll_log.append({
            "poll_count": self._poll_count,
            "timestamp": now.isoformat(),
            "status": "ok",
            "trigger_count": len(triggers),
            "started_jobs_count": len(started_jobs),
        })

        # Trim log to last 50
        if len(self._poll_log) > 50:
            self._poll_log = self._poll_log[-50:]

        await manager.broadcast({
            "type": "scheduler_poll_completed",
            "result": poll_result,
            "timestamp": now.isoformat(),
        })
        return poll_result


# Module-level singleton
poller = SchedulerPoller()
