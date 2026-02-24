"""Chat service — resume Claude sessions for follow-up conversations.

Uses ``claude --resume SESSION_ID`` to continue previous analysis sessions,
preserving full context from the original analysis.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import ROOT_DIR, TASKS_DIR
from ..ws.manager import manager

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
_chat_sessions: dict[str, dict] = {}  # chat_id → chat session dict
_chat_processes: dict[str, subprocess.Popen] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_sessions(task_id: str) -> list[dict]:
    """Return available Claude sessions for a task.

    Merges sessions from analysis_history.jsonl and chat_sessions.json.
    """
    from .analysis_service import get_history

    history = get_history()
    sessions = []
    seen: set[str] = set()

    for entry in reversed(history):
        if entry.get("task_id") != task_id:
            continue
        sid = entry.get("session_id")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        sessions.append({
            "session_id": sid,
            "job_id": entry["id"],
            "mode": entry.get("mode", "unknown"),
            "started_at": entry.get("started_at", ""),
            "status": entry.get("status", "unknown"),
            "source": "analysis",
        })

    # Merge chat-only sessions from chat_sessions.json
    for cs in _load_chat_sessions(task_id):
        sid = cs.get("session_id")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        sessions.append({
            "session_id": sid,
            "job_id": sid[:8],
            "mode": "chat",
            "started_at": cs.get("started_at", ""),
            "status": "completed",
            "source": "chat",
        })

    return sessions


async def get_chat_history(task_id: str) -> list[dict]:
    """Load chat history from tasks/{task_id}/chat_history.json."""
    return _load_chat_history(task_id)


async def send_message(task_id: str, session_id: Optional[str], message: str) -> dict:
    """Send a message via ``claude`` and stream the response.

    If *session_id* is ``None``, creates a new session with task context.
    Otherwise, resumes an existing session.
    Returns a chat_id, session_id, and is_new_session flag.
    """
    is_new_session = session_id is None
    if is_new_session:
        session_id = str(uuid.uuid4())
        _save_chat_session(task_id, session_id)

    chat_id = str(uuid.uuid4())[:8]

    chat_session: dict = {
        "id": chat_id,
        "task_id": task_id,
        "session_id": session_id,
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "message": message,
        "response_lines": [],
        "response_text": "",
    }
    _chat_sessions[chat_id] = chat_session

    # Fire-and-forget the subprocess
    asyncio.create_task(_run_chat(chat_id, task_id, session_id, message, is_new_session))

    return {
        "chat_id": chat_id,
        "session_id": session_id,
        "status": "started",
        "is_new_session": is_new_session,
    }


async def cancel_chat(chat_id: str) -> bool:
    """Cancel a running chat process."""
    process = _chat_processes.get(chat_id)
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

    session = _chat_sessions.get(chat_id)
    if session:
        session["status"] = "cancelled"

    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_env() -> dict[str, str]:
    """Return a copy of os.environ with ALL Claude Code env vars removed."""
    env = os.environ.copy()
    for key in list(env):
        if key.upper().startswith("CLAUDE"):
            del env[key]
    return env


def _build_task_context(task_id: str) -> str:
    """Build a markdown preamble with task metadata for new chat sessions."""
    task_file = TASKS_DIR / task_id / "task.json"
    if not task_file.exists():
        return f"# Task Context: {task_id}\n(task.json not found)"

    try:
        data = json.loads(task_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return f"# Task Context: {task_id}\n(failed to parse task.json)"

    parts: list[str] = [f"# Task Context: {task_id}"]

    name = data.get("name", "")
    if name:
        parts.append(f"**Name**: {name}")

    status = data.get("status", {})
    if isinstance(status, dict):
        parts.append(f"**Status**: {status.get('status', '')}")
    elif isinstance(status, str):
        parts.append(f"**Status**: {status}")

    # Version info from custom_fields
    custom_fields = data.get("custom_fields", [])
    versions: list[str] = []
    for cf in custom_fields:
        if not isinstance(cf, dict):
            continue
        cf_name = cf.get("name", "")
        cf_value = cf.get("value")
        if "version" in cf_name.lower() and cf_value:
            versions.append(f"{cf_name}: {cf_value}")
    if versions:
        parts.append(f"**Versions**: {', '.join(versions)}")

    # Description (truncated)
    desc = data.get("markdown_description") or data.get("description") or ""
    if desc:
        if len(desc) > 3000:
            desc = desc[:3000] + "\n...(truncated)"
        parts.append(f"\n**Description**:\n{desc}")

    # Recent comments (last 5)
    comments = data.get("comments", [])
    if comments:
        recent = comments[-5:]
        parts.append("\n**Recent Comments**:")
        for c in recent:
            user = c.get("user", "unknown")
            text = c.get("comment_text", c.get("comment", ""))
            if len(text) > 500:
                text = text[:500] + "..."
            parts.append(f"- **{user}**: {text}")

    # Available artifacts
    task_dir = TASKS_DIR / task_id
    artifacts: list[str] = []
    for fname in ("report.md", "context.md", "patch_review.md", "patch_diff.md"):
        if (task_dir / fname).exists():
            artifacts.append(fname)
    if artifacts:
        parts.append(f"\n**Available artifacts**: {', '.join(artifacts)}")

    return "\n".join(parts)


def _save_chat_session(task_id: str, session_id: str) -> None:
    """Append a chat session entry to tasks/{task_id}/chat_sessions.json."""
    task_dir = TASKS_DIR / task_id
    if not task_dir.exists():
        return
    sessions_file = task_dir / "chat_sessions.json"

    sessions: list[dict] = []
    if sessions_file.exists():
        try:
            sessions = json.loads(sessions_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            sessions = []

    sessions.append({
        "session_id": session_id,
        "started_at": datetime.now().isoformat(),
    })

    sessions_file.write_text(
        json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_chat_sessions(task_id: str) -> list[dict]:
    """Load chat_sessions.json for a task."""
    sessions_file = TASKS_DIR / task_id / "chat_sessions.json"
    if not sessions_file.exists():
        return []
    try:
        return json.loads(sessions_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return []


async def _run_chat(
    chat_id: str,
    task_id: str,
    session_id: str,
    message: str,
    is_new_session: bool = False,
) -> None:
    """Run ``claude`` subprocess and stream output via WebSocket.

    For new sessions, injects task context as a preamble and uses
    ``--session-id``.  For existing sessions, uses ``--resume``.
    """
    session = _chat_sessions[chat_id]
    loop = asyncio.get_running_loop()

    try:
        if is_new_session:
            context = _build_task_context(task_id)
            prompt = f"{context}\n---\n**User question**: {message}"
            cmd = [
                "claude",
                "-p", prompt,
                "--session-id", session_id,
                "--output-format", "stream-json",
                "--allowedTools",
                "Read,Glob,Grep,Bash,Write,Edit",
            ]
        else:
            cmd = [
                "claude",
                "-p", message,
                "--resume", session_id,
                "--output-format", "stream-json",
                "--allowedTools",
                "Read,Glob,Grep,Bash,Write,Edit",
            ]

        env = _clean_env()

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
        _chat_processes[chat_id] = process

        assert process.stdout is not None
        full_response: list[str] = []

        while True:
            raw_line = await loop.run_in_executor(None, process.stdout.readline)
            if not raw_line:
                break
            decoded = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
            session["response_lines"].append(decoded)

            # Broadcast raw output for real-time display
            await manager.broadcast({
                "type": "chat_output",
                "chat_id": chat_id,
                "task_id": task_id,
                "line": decoded,
            })

            # Parse stream-json for text content and progress events
            for event in _parse_chat_events(decoded):
                if event["type"] == "text":
                    full_response.append(event["content"])
                    await manager.broadcast({
                        "type": "chat_response",
                        "chat_id": chat_id,
                        "task_id": task_id,
                        "content": event["content"],
                        "done": False,
                    })
                elif event["type"] == "progress":
                    await manager.broadcast({
                        "type": "chat_progress",
                        "chat_id": chat_id,
                        "task_id": task_id,
                        "event": event["event"],
                        "tool": event.get("tool", ""),
                        "detail": event.get("detail", ""),
                        "timestamp": datetime.now().isoformat(),
                    })

        exit_code = await loop.run_in_executor(None, process.wait)
        session["exit_code"] = exit_code
        session["status"] = "completed" if exit_code == 0 else "failed"
        session["response_text"] = "".join(full_response)

        # Final response signal
        await manager.broadcast({
            "type": "chat_response",
            "chat_id": chat_id,
            "task_id": task_id,
            "content": session["response_text"],
            "done": True,
        })

    except Exception as e:
        session["status"] = "failed"
        session["error"] = str(e)
    finally:
        _chat_processes.pop(chat_id, None)
        session["finished_at"] = datetime.now().isoformat()

        # Persist to chat_history.json
        _save_chat_history(
            task_id, session_id, message, session.get("response_text", "")
        )


def _parse_chat_events(line: str) -> list[dict]:
    """Parse a stream-json line into chat-relevant events."""
    try:
        event = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return []

    results: list[dict] = []
    etype = event.get("type")

    if etype == "assistant":
        for item in event.get("message", {}).get("content", []):
            kind = item.get("type")
            if kind == "text":
                text = item.get("text", "")
                if text:
                    results.append({"type": "text", "content": text})
            elif kind == "tool_use":
                tool = item.get("name", "")
                inp = item.get("input", {})
                detail = _summarize_tool(tool, inp)
                results.append({
                    "type": "progress",
                    "event": "tool_use",
                    "tool": tool,
                    "detail": detail,
                })

    elif etype == "result":
        results.append({
            "type": "progress",
            "event": "result",
            "detail": f"Done ({event.get('num_turns', '?')} turns, ${event.get('cost_usd', '?')})",
        })

    return results


def _summarize_tool(tool: str, inp: dict) -> str:
    """Brief summary of a tool invocation."""
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
    return ""


def _save_chat_history(
    task_id: str, session_id: str, message: str, response: str
) -> None:
    """Append a message/response pair to tasks/{task_id}/chat_history.json."""
    task_dir = TASKS_DIR / task_id
    if not task_dir.exists():
        return
    history_file = task_dir / "chat_history.json"

    history: list[dict] = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            history = []

    now = datetime.now().isoformat()
    history.append({"role": "user", "content": message, "timestamp": now, "session_id": session_id})
    if response:
        history.append({"role": "assistant", "content": response, "timestamp": now, "session_id": session_id})

    history_file.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_chat_history(task_id: str) -> list[dict]:
    """Load chat_history.json for a task."""
    history_file = TASKS_DIR / task_id / "chat_history.json"
    if not history_file.exists():
        return []
    try:
        return json.loads(history_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return []
