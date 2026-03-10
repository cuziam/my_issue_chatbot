"""Job CRUD operations and shared state for analysis jobs.

Manages in-memory job storage, process tracking, history persistence,
and job lifecycle operations (get, cancel, log retrieval).
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from ...config import LOGS_DIR
from ...ws.manager import manager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory stores (shared across the analysis package)
# ---------------------------------------------------------------------------
_jobs: dict[str, dict] = {}
_processes: dict[str, subprocess.Popen] = {}
_cancelled_jobs: set[str] = set()  # Explicit cancel tracking

HISTORY_FILE = LOGS_DIR / "analysis_history.jsonl"
JOB_LOGS_DIR = LOGS_DIR / "jobs"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_jobs() -> list[dict]:
    """Return all in-memory jobs (running + recently finished)."""
    return list(_jobs.values())


def get_job(job_id: str) -> dict | None:
    """Return a single job by ID, or None."""
    return _jobs.get(job_id)


async def cancel_job(job_id: str) -> bool:
    """Cancel a running analysis job. Returns True if cancellation was issued."""
    _cancelled_jobs.add(job_id)  # Flag BEFORE terminating -- prevents race

    process = _processes.get(job_id)
    if not process:
        _cancelled_jobs.discard(job_id)
        return False

    process.terminate()
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, process.wait), timeout=5
        )
    except asyncio.TimeoutError:
        process.kill()

    job = _jobs.get(job_id)
    if job:
        job["status"] = "cancelled"
        job["finished_at"] = datetime.now().isoformat()

    return True


def get_job_log(job_id: str) -> dict:
    """Read the persisted log file for a job."""
    log_file = JOB_LOGS_DIR / f"{job_id}.log"
    if not log_file.exists():
        return {"lines": [], "exists": False}
    lines = log_file.read_text(encoding="utf-8").splitlines()
    return {"lines": lines, "exists": True}


def get_history() -> list[dict]:
    """Read all entries from analysis_history.jsonl."""
    if not HISTORY_FILE.exists():
        return []
    entries: list[dict] = []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def append_history(job: dict) -> None:
    """Append a completed job summary to analysis_history.jsonl."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": job["id"],
        "task_id": job["task_id"],
        "mode": job["mode"],
        "status": job["status"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "exit_code": job["exit_code"],
        "exit_reason": job.get("exit_reason"),
        "session_id": job.get("session_id"),
        "retry_job_id": job.get("retry_job_id"),
        "output_line_count": len(job["output_lines"]),
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
