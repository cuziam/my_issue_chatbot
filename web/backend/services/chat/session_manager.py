"""Session and chat history CRUD operations.

Handles listing sessions, creating/loading chat sessions, and
persisting chat history to tasks/{task_id}/chat_history.json.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from ...config import TASKS_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory stores  (authoritative owner: this module)
# ---------------------------------------------------------------------------
_chat_sessions: dict[str, dict] = {}  # chat_id -> chat session dict


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_sessions(task_id: str) -> list[dict]:
    """Return available Claude sessions for a task.

    Merges sessions from analysis_history.jsonl and chat_sessions.json.
    """
    from ..analysis import get_history

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
    # Pre-load chat history to check which sessions actually have messages
    chat_history = _load_chat_history(task_id)
    sessions_with_messages = {
        m.get("session_id") for m in chat_history if m.get("session_id")
    }

    for cs in _load_chat_sessions(task_id):
        sid = cs.get("session_id")
        if not sid or sid in seen:
            continue
        seen.add(sid)

        # Determine actual status:
        # - If a chat process is still running for this session -> "running"
        # - If chat_history.json has messages for this session -> "completed"
        # - Otherwise -> "interrupted" (session created but messages never saved)
        if any(
            s.get("session_id") == sid and s.get("status") == "running"
            for s in _chat_sessions.values()
        ):
            status = "running"
        elif sid in sessions_with_messages:
            status = "completed"
        else:
            status = "interrupted"

        sessions.append({
            "session_id": sid,
            "job_id": sid[:8],
            "mode": "chat",
            "started_at": cs.get("started_at", ""),
            "status": status,
            "source": "chat",
        })

    return sessions


async def get_chat_history(task_id: str, session_id: str | None = None) -> list[dict]:
    """Load chat history from tasks/{task_id}/chat_history.json.

    If *session_id* is provided, only return messages for that session.
    """
    history = _load_chat_history(task_id)
    if session_id:
        history = [m for m in history if m.get("session_id") == session_id]
    return history


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


def _load_chat_history(task_id: str) -> list[dict]:
    """Load chat_history.json for a task."""
    history_file = TASKS_DIR / task_id / "chat_history.json"
    if not history_file.exists():
        return []
    try:
        return json.loads(history_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return []


def _save_user_message(
    task_id: str,
    session_id: str,
    message: str,
    attachments: list[dict] | None = None,
) -> None:
    """Immediately persist the user message to chat_history.json.

    Called as soon as the user sends a message so the history survives
    page navigation even if the assistant response hasn't finished yet.
    """
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

    user_entry: dict = {
        "role": "user", "content": message,
        "timestamp": datetime.now().isoformat(), "session_id": session_id,
    }
    if attachments:
        user_entry["attachments"] = [
            {"name": a["name"], "path": a["path"], "type": a["type"], "size": a["size"]}
            for a in attachments
        ]
    history.append(user_entry)

    history_file.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _save_chat_history(
    task_id: str,
    session_id: str,
    message: str,
    response: str,
    attachments: list[dict] | None = None,
    created_files: list[dict] | None = None,
) -> None:
    """Append the assistant response to the last user message in chat_history.json.

    The user message was already saved by ``_save_user_message`` at send time.
    This function finds that entry and appends the assistant response after it.
    If the user entry is missing (e.g. legacy flow), it appends both.
    """
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

    # Check if the user message was already saved by _save_user_message
    user_already_saved = any(
        m.get("role") == "user"
        and m.get("session_id") == session_id
        and m.get("content") == message
        for m in history
    )

    if not user_already_saved:
        # Fallback: save user message too (legacy or edge case)
        user_entry: dict = {
            "role": "user", "content": message,
            "timestamp": now, "session_id": session_id,
        }
        if attachments:
            user_entry["attachments"] = [
                {"name": a["name"], "path": a["path"], "type": a["type"], "size": a["size"]}
                for a in attachments
            ]
        history.append(user_entry)

    if response:
        assistant_entry: dict = {
            "role": "assistant", "content": response,
            "timestamp": now, "session_id": session_id,
        }
        if created_files:
            assistant_entry["created_files"] = created_files
        history.append(assistant_entry)

    history_file.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )
