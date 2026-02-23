"""Service layer for managing Claude analysis subprocess jobs.

Jobs are stored in-memory while running and persisted to analysis_history.jsonl
upon completion.  Real-time output is streamed to WebSocket clients via the
shared ConnectionManager.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import ROOT_DIR, TASKS_DIR, LOGS_DIR
from ..ws.manager import manager

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
_jobs: dict[str, dict] = {}
_processes: dict[str, subprocess.Popen] = {}

HISTORY_FILE = LOGS_DIR / "analysis_history.jsonl"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_jobs() -> list[dict]:
    """Return all in-memory jobs (running + recently finished)."""
    return list(_jobs.values())


def get_job(job_id: str) -> Optional[dict]:
    """Return a single job by ID, or None."""
    return _jobs.get(job_id)


async def start_analysis(task_id: str, mode: str) -> dict:
    """Start a ``claude -p`` analysis subprocess and return the job dict.

    Pre-validates that task.json exists and ``claude`` CLI is available.
    Returns an error dict (status="error") on validation failure instead of
    spawning a doomed subprocess.
    """
    # --- Pre-validation ---
    task_dir = TASKS_DIR / task_id
    task_json = task_dir / "task.json"
    if not task_json.exists():
        return {
            "status": "error",
            "message": f"task.json not found for {task_id}. Run Fetch Task first.",
        }

    if not shutil.which("claude"):
        return {
            "status": "error",
            "message": "claude CLI not found in PATH. Install Claude Code first.",
        }

    job_id = str(uuid.uuid4())[:8]

    # Build prompt based on mode (mirrors scheduler.build_analysis_prompt)
    if mode == "initial":
        prompt = f"{task_id}를 agent team으로 분석해줘"
    elif mode == "patch_review":
        prompt = (
            f"{task_id} 패치 리뷰해줘.\n"
            f"task_dir: {task_dir}\n"
            f".claude/agents/patch-reviewer.md 에이전트 정의를 따라 patch_review.md를 작성하세요."
        )
    elif mode == "verification":
        prompt = (
            f"{task_id} 팔로업: 이 이슈는 \"qa to do\" 상태로 전환되었습니다.\n"
            f"개발자가 수정을 완료했으므로, 수정 사항이 올바르게 구현되었는지 검증 분석을 수행해줘.\n"
            f"기존 report.md의 \"참고: 코드 레벨 원인\"에 명시된 수정 방안이 실제로 반영되었는지 확인하고,\n"
            f"QA 검증 시나리오를 업데이트해줘."
        )
    elif mode == "activity_update":
        prompt = (
            f"{task_id} 팔로업: 이 이슈에 새로운 활동이 감지되었습니다.\n"
            f"새 댓글이나 본문 업데이트가 있으므로, "
            f"기존 report.md를 참고하여 추가 분석을 수행해줘.\n"
            f"변경된 내용이 기존 분석에 영향을 미치는지 확인하고, "
            f"필요하면 report.md에 추가 분석을 append해줘."
        )
    else:
        prompt = f"{task_id}를 agent team으로 분석해줘"

    cmd = [
        "claude",
        "-p",
        prompt,
        "--verbose",
        "--output-format", "stream-json",
        "--allowedTools",
        (
            "Read,Glob,Grep,Bash,Write,Edit,Task,SendMessage,"
            "TeamCreate,TeamDelete,TaskCreate,TaskList,TaskGet,TaskUpdate"
        ),
    ]

    job: dict = {
        "id": job_id,
        "task_id": task_id,
        "mode": mode,
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "output_lines": [],
        "progress_events": [],
        "exit_code": None,
        "error": None,
    }
    _jobs[job_id] = job

    # Notify connected clients
    await manager.broadcast({"type": "job_started", "job": job})

    # Fire-and-forget the subprocess task
    asyncio.create_task(_run_process(job_id, cmd))

    return job


async def cancel_job(job_id: str) -> bool:
    """Cancel a running analysis job. Returns True if cancellation was issued."""
    process = _processes.get(job_id)
    if not process:
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_env() -> dict[str, str]:
    """Return a copy of os.environ with ALL Claude Code env vars removed.

    Claude CLI refuses to start inside another Claude Code session.
    Multiple env vars are set (CLAUDECODE, CLAUDE_CODE_ENTRYPOINT, etc.)
    and ALL of them must be removed.
    """
    env = os.environ.copy()
    for key in list(env):
        if key.upper().startswith("CLAUDE"):
            del env[key]
    return env


async def _run_process(job_id: str, cmd: list[str]) -> None:
    """Run the subprocess, streaming stdout to the WebSocket manager.

    Uses ``subprocess.Popen`` with ``run_in_executor`` for reliable
    cross-platform support (asyncio subprocess can be unreliable on
    Windows inside uvicorn's event loop).
    """
    job = _jobs[job_id]
    loop = asyncio.get_running_loop()
    try:
        env = _clean_env()

        # Start process (blocking call, run in executor)
        process = await loop.run_in_executor(
            None,
            lambda: subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(ROOT_DIR),
                env=env,
            ),
        )
        _processes[job_id] = process

        # Read stdout line-by-line in executor to avoid blocking the loop
        assert process.stdout is not None
        while True:
            raw_line = await loop.run_in_executor(None, process.stdout.readline)
            if not raw_line:
                break
            decoded = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
            job["output_lines"].append(decoded)
            await manager.broadcast(
                {"type": "output", "job_id": job_id, "line": decoded}
            )

            # Parse stream-json events for structured progress
            for progress in _parse_stream_events(decoded):
                progress["timestamp"] = datetime.now().isoformat()
                job["progress_events"].append(progress)
                await manager.broadcast(
                    {"type": "progress", "job_id": job_id, **progress}
                )

        exit_code = await loop.run_in_executor(None, process.wait)
        job["exit_code"] = exit_code
        job["status"] = "completed" if exit_code == 0 else "failed"

    except asyncio.CancelledError:
        job["status"] = "cancelled"
    except Exception as e:
        job["status"] = "failed"
        job["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
    finally:
        job["finished_at"] = datetime.now().isoformat()
        _processes.pop(job_id, None)

        await manager.broadcast({"type": "job_finished", "job": job})

        _append_history(job)


def _parse_stream_events(line: str) -> list[dict]:
    """Parse a ``stream-json`` line into human-readable progress events."""
    try:
        event = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return []

    results: list[dict] = []
    etype = event.get("type")

    if etype == "assistant":
        content_items = event.get("message", {}).get("content", [])
        for item in content_items:
            kind = item.get("type")
            if kind == "tool_use":
                tool = item.get("name", "")
                detail = _summarize_tool_input(tool, item.get("input", {}))
                results.append({"event": "tool_use", "tool": tool, "detail": detail})
            elif kind == "text":
                text = item.get("text", "").strip()
                if text:
                    results.append({"event": "text", "detail": text[:200]})

    elif etype == "result":
        results.append({
            "event": "result",
            "subtype": event.get("subtype", ""),
            "duration_ms": event.get("duration_ms"),
            "num_turns": event.get("num_turns"),
            "cost_usd": event.get("cost_usd"),
        })

    return results


def _summarize_tool_input(tool: str, inp: dict) -> str:
    """Return a short human-readable summary of a tool invocation."""
    if tool in ("Read", "Write", "Edit"):
        return inp.get("file_path", "")
    if tool == "Glob":
        return inp.get("pattern", "")
    if tool == "Grep":
        pat = inp.get("pattern", "")
        path = inp.get("path", "")
        return f'"{pat}" in {path}' if path else f'"{pat}"'
    if tool == "Bash":
        return inp.get("command", "")[:100]
    if tool == "Task":
        desc = inp.get("description", "")
        name = inp.get("name", "")
        atype = inp.get("subagent_type", "")
        if name:
            return f"{name} ({atype}): {desc}"
        return f"{atype}: {desc}" if atype else desc
    if tool == "SendMessage":
        recipient = inp.get("recipient", "")
        summary = inp.get("summary", "")
        mtype = inp.get("type", "message")
        if mtype == "shutdown_request":
            return f"shutdown → {recipient}"
        return f"→ {recipient}: {summary}" if summary else f"→ {recipient}"
    if tool == "TeamCreate":
        return f"team: {inp.get('team_name', '')}"
    if tool == "TaskCreate":
        return inp.get("subject", "")
    if tool in ("TaskUpdate", "TaskGet"):
        return inp.get("taskId", "")
    return ""


def _append_history(job: dict) -> None:
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
        "output_line_count": len(job["output_lines"]),
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
