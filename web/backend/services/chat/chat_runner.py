"""Chat execution: send_message(), _run_chat(), cancel_chat().

Manages the Claude CLI subprocess lifecycle, streams output via
WebSocket, and coordinates with session_manager for persistence.
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from ...config import ROOT_DIR, TASKS_DIR, PACKAGES_DIR
from ...ws.manager import manager
from ..claude_subprocess import summarize_tool_input
from ..llm import get_llm_backend
from .session_manager import (
    _chat_sessions,
    _save_chat_session,
    _save_chat_history,
    _load_chat_history,
)
from .upload_handler import SENSITIVE_FILENAMES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory stores  (authoritative owner: this module)
# ---------------------------------------------------------------------------
_chat_processes: dict[str, subprocess.Popen] = {}

# Session size limit before auto-forking to a new session.
# CLI `-p --resume` doesn't trigger auto-compaction, so large sessions
# cause context overflow and AI "forgets" earlier messages.
SESSION_SIZE_LIMIT = 500_000  # 500 KB

# Messages larger than this are saved to a file and Claude reads them
# via the Read tool instead of having them in the conversation context.
MESSAGE_FILE_THRESHOLD = 10_000  # 10 KB


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def send_message(
    task_id: str,
    session_id: str | None,
    message: str,
    attachments: list[dict] | None = None,
) -> dict:
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

    # Ensure chat_files/ directory exists for Claude output
    chat_files_dir = TASKS_DIR / task_id / "chat_files"
    chat_files_dir.mkdir(parents=True, exist_ok=True)

    # Fire-and-forget the subprocess
    asyncio.create_task(
        _run_chat(chat_id, task_id, session_id, message, is_new_session, attachments)
    )

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
# Session size management
# ---------------------------------------------------------------------------

def _get_session_jsonl_path(session_id: str) -> Path | None:
    """Return the Claude CLI session JSONL file path, or None if not found."""
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return None
    # Claude CLI encodes the CWD into the project directory name.
    # Try all project dirs that might match ROOT_DIR.
    root_str = str(ROOT_DIR.resolve())
    # Heuristic: replace path separators and colon with dashes
    for candidate in projects_dir.iterdir():
        if not candidate.is_dir():
            continue
        session_file = candidate / f"{session_id}.jsonl"
        if session_file.exists():
            return session_file
    return None


def _get_session_size(session_id: str) -> int:
    """Return the Claude CLI session JSONL file size in bytes."""
    path = _get_session_jsonl_path(session_id)
    if path and path.exists():
        return path.stat().st_size
    return 0


def _build_conversation_summary(task_id: str, session_id: str) -> str:
    """Build a conversation summary from chat_history.json for context carry-over.

    When a session is forked due to size limits, this summary is injected
    into the new session so Claude has context about previous exchanges.
    """
    history = _load_chat_history(task_id)
    session_msgs = [m for m in history if m.get("session_id") == session_id]

    if not session_msgs:
        return "(이전 대화 없음)"

    # Keep last 10 messages — enough for context, not too much for new session
    recent = session_msgs[-10:]

    parts: list[str] = []
    for m in recent:
        role = "사용자" if m["role"] == "user" else "AI"
        content = m.get("content", "")
        # Truncate very long messages (e.g. pasted SP code)
        if len(content) > 1000:
            content = content[:400] + "\n...(중략)...\n" + content[-400:]
        parts.append(f"**{role}**: {content}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_downloadable(file_path: str) -> bool:
    """Check if a file path is within allowed download directories."""
    try:
        resolved = Path(file_path).resolve()
    except (OSError, ValueError):
        return False
    allowed = [TASKS_DIR.resolve(), PACKAGES_DIR.resolve()]
    if not any(_is_subpath(resolved, d) for d in allowed):
        return False
    if resolved.name.lower() in SENSITIVE_FILENAMES:
        return False
    return True


def _is_subpath(path: Path, parent: Path) -> bool:
    """Check if *path* is equal to or under *parent*."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _build_file_meta(file_path: str, downloadable: bool) -> dict:
    """Build metadata dict for a created/modified file."""
    p = Path(file_path)
    size = None
    try:
        if p.exists():
            size = p.stat().st_size
    except OSError:
        pass
    return {
        "name": p.name,
        "path": str(p).replace("\\", "/"),
        "size": size,
        "downloadable": downloadable,
    }


def _build_task_context(task_id: str) -> str:
    """Build a markdown preamble with task metadata for new chat sessions."""
    from .task_files import _build_task_files_context

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

    # Recent comments (last 5, including threaded replies)
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
            # Include threaded replies
            for r in c.get("replies", []):
                r_user = r.get("user", "unknown")
                r_text = r.get("comment_text", r.get("comment", ""))
                if len(r_text) > 500:
                    r_text = r_text[:500] + "..."
                parts.append(f"  - **{r_user}** (reply): {r_text}")

    # Available artifacts
    task_dir = TASKS_DIR / task_id
    artifacts: list[str] = []
    for fname in ("report.md", "context.md", "patch_review.md", "patch_diff.md"):
        if (task_dir / fname).exists():
            artifacts.append(fname)
    if artifacts:
        parts.append(f"\n**Available artifacts**: {', '.join(artifacts)}")

    # Task files listing for Claude context
    files_ctx = _build_task_files_context(task_id)
    if files_ctx:
        parts.append(files_ctx)

    return "\n".join(parts)


def _build_attachment_section(attachments: list[dict] | None) -> str:
    """Build a prompt section listing attached files for Claude to Read."""
    if not attachments:
        return ""
    lines = ["**\uccb4\ubd80 \ud30c\uc77c** (Read \ub3c4\uad6c\ub85c \ud655\uc778\ud558\uc138\uc694):"]
    for att in attachments:
        lines.append(f"- [{att['type']}] {att['path']}")
    return "\n".join(lines)


async def _run_chat(
    chat_id: str,
    task_id: str,
    session_id: str,
    message: str,
    is_new_session: bool = False,
    attachments: list[dict] | None = None,
) -> None:
    """Run ``claude`` subprocess and stream output via WebSocket.

    For new sessions, injects task context as a preamble and uses
    ``--session-id``.  For existing sessions, uses ``--resume``.
    """
    session = _chat_sessions[chat_id]
    loop = asyncio.get_running_loop()

    # Build attachment section for prompt
    attachment_section = _build_attachment_section(attachments)

    # --- Large message → file conversion ---
    # Huge pasted text (e.g. SP code) dominates the conversation context
    # and degrades response quality.  Save to file and let Claude Read it.
    message_for_prompt = message
    if len(message) > MESSAGE_FILE_THRESHOLD:
        uploads_dir = TASKS_DIR / task_id / "chat_uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        filename = f"pasted_text_{chat_id}.txt"
        file_path = uploads_dir / filename
        file_path.write_text(message, encoding="utf-8")
        abs_path = str(file_path.absolute()).replace("\\", "/")
        preview = message[:300].rstrip()
        message_for_prompt = (
            f"사용자가 큰 텍스트를 붙여넣었습니다 ({len(message):,}자). "
            f"전체 내용은 아래 파일에 있으니 **Read 도구로 읽어주세요**:\n"
            f"- `{abs_path}`\n\n"
            f"**미리보기** (처음 300자):\n```\n{preview}\n```"
        )
        logger.info("Large message (%d chars) saved to %s", len(message), abs_path)

    history_saved = False
    forked_session_id = None  # Set if we auto-fork due to size limit
    try:
        if is_new_session:
            context = _build_task_context(task_id)
            prompt = f"{context}\n---\n**User question**: {message_for_prompt}"
            if attachment_section:
                prompt += f"\n\n{attachment_section}"
            resume = False
        else:
            prompt = message_for_prompt
            if attachment_section:
                prompt += f"\n\n{attachment_section}"
            resume = True

            # --- Session size guard ---
            # CLI `-p --resume` doesn't auto-compact, so large sessions
            # cause context overflow. Fork to a new session with summary.
            session_size = _get_session_size(session_id)
            if session_size > SESSION_SIZE_LIMIT:
                old_session_id = session_id
                summary = _build_conversation_summary(task_id, session_id)
                # Create a fresh session with conversation context
                session_id = str(uuid.uuid4())
                forked_session_id = session_id
                _save_chat_session(task_id, session_id)
                session["session_id"] = session_id
                context = _build_task_context(task_id)
                prompt = (
                    f"{context}\n\n"
                    f"## 이전 대화 요약\n"
                    f"아래는 이전 대화의 최근 내용입니다. 이 맥락을 참고하세요.\n\n"
                    f"{summary}\n\n---\n"
                    f"**User question**: {message_for_prompt}"
                )
                if attachment_section:
                    prompt += f"\n\n{attachment_section}"
                resume = False
                logger.info(
                    "Session %s forked to %s (size %s bytes > %s limit)",
                    old_session_id, session_id, session_size, SESSION_SIZE_LIMIT,
                )
                await manager.broadcast({
                    "type": "chat_session_forked",
                    "task_id": task_id,
                    "chat_id": chat_id,
                    "old_session_id": old_session_id,
                    "new_session_id": session_id,
                    "reason": "context_limit",
                })

        # Instruct Claude to write downloadable files into chat_files/
        chat_files_dir = TASKS_DIR / task_id / "chat_files"
        chat_files_abs = str(chat_files_dir.absolute()).replace("\\", "/")
        file_system_prompt = (
            f"IMPORTANT: \ud30c\uc77c\uc744 \uc0dd\uc131\ud558\uac70\ub098 \uc800\uc7a5\ud560 \ub54c\ub294 \ubc18\ub4dc\uc2dc {chat_files_abs}/ \uc5d0 Write\ud558\uc138\uc694. "
            f"\ucf54\ub4dc, \uc2a4\ud06c\ub9bd\ud2b8, \ubb38\uc11c \ub4f1 \uc0ac\uc6a9\uc790\uac00 \ub2e4\uc6b4\ub85c\ub4dc\ud560 \uc218 \uc788\ub294 \uacb0\uacfc\ubb3c\uc740 \ud14d\uc2a4\ud2b8\ub85c\ub9cc \ubcf4\uc5ec\uc8fc\uc9c0 \ub9d0\uace0 "
            f"Write \ub3c4\uad6c\ub97c \uc0ac\uc6a9\ud558\uc5ec \ud574\ub2f9 \ub514\ub809\ud1a0\ub9ac\uc5d0 \uc800\uc7a5\ud558\uc138\uc694."
        )

        allowed_tools = ["Read", "Glob", "Grep", "Bash", "Write", "Edit"]

        llm = get_llm_backend()
        process, _ = await llm.run_prompt(
            prompt,
            session_id=session_id,
            resume=resume,
            allowed_tools=allowed_tools,
            cwd=str(ROOT_DIR),
            system_prompt=file_system_prompt,
        )
        _chat_processes[chat_id] = process

        assert process.stdout is not None
        accumulated_text = ""  # Accumulated text across all turns
        _active_tool_blocks: dict[int, dict] = {}  # index -> {name, input_chunks}
        _sent_tool_ids: set[str] = set()  # tool IDs already broadcast via content_block_stop

        while True:
            raw_line = await loop.run_in_executor(None, process.stdout.readline)
            if not raw_line:
                break
            decoded = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
            session["response_lines"].append(decoded)

            # Broadcast raw output for debugging
            await manager.broadcast({
                "type": "chat_output",
                "chat_id": chat_id,
                "task_id": task_id,
                "session_id": session_id,
                "line": decoded,
            })

            # Parse stream-json event
            try:
                event = json.loads(decoded)
            except (json.JSONDecodeError, ValueError):
                continue

            etype = event.get("type")

            # Streaming text deltas -- real-time character-by-character
            if etype == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    accumulated_text += delta.get("text", "")
                    await manager.broadcast({
                        "type": "chat_response",
                        "chat_id": chat_id,
                        "task_id": task_id,
                        "session_id": session_id,
                        "content": accumulated_text,
                        "done": False,
                    })
                elif delta.get("type") == "input_json_delta":
                    # Accumulate tool input JSON chunks
                    idx = event.get("index")
                    if idx is not None and idx in _active_tool_blocks:
                        _active_tool_blocks[idx]["input_chunks"].append(
                            delta.get("partial_json", "")
                        )

            # Tool use block started -- record tool name + id
            elif etype == "content_block_start":
                cb = event.get("content_block", {})
                if cb.get("type") == "tool_use":
                    idx = event.get("index")
                    if idx is not None:
                        _active_tool_blocks[idx] = {
                            "id": cb.get("id", ""),
                            "name": cb.get("name", ""),
                            "input_chunks": [],
                        }

            # Tool use block finished -- assemble input, broadcast immediately
            elif etype == "content_block_stop":
                idx = event.get("index")
                if idx is not None and idx in _active_tool_blocks:
                    block = _active_tool_blocks.pop(idx)
                    tool = block["name"]
                    tool_id = block["id"]
                    raw_json = "".join(block["input_chunks"])
                    try:
                        inp = json.loads(raw_json) if raw_json else {}
                    except (json.JSONDecodeError, ValueError):
                        inp = {}
                    detail = summarize_tool_input(tool, inp)
                    # Broadcast tool_use progress IMMEDIATELY (before tool executes)
                    await manager.broadcast({
                        "type": "chat_progress",
                        "chat_id": chat_id,
                        "task_id": task_id,
                        "session_id": session_id,
                        "event": "tool_use",
                        "tool": tool,
                        "detail": detail,
                        "timestamp": datetime.now().isoformat(),
                    })
                    if tool_id:
                        _sent_tool_ids.add(tool_id)

            # Full assistant message (end of each turn).
            # Fallback: broadcast tool_use progress for any tools NOT already
            # sent via content_block_stop (CLI may not emit streaming events).
            elif etype == "assistant":
                for item in event.get("message", {}).get("content", []):
                    kind = item.get("type")
                    if kind == "tool_use":
                        tool = item.get("name", "")
                        tool_id = item.get("id", "")
                        inp = item.get("input", {})
                        # Skip if already broadcast via content_block_stop
                        if tool_id and tool_id in _sent_tool_ids:
                            pass
                        else:
                            detail = summarize_tool_input(tool, inp)
                            await manager.broadcast({
                                "type": "chat_progress",
                                "chat_id": chat_id,
                                "task_id": task_id,
                                "session_id": session_id,
                                "event": "tool_use",
                                "tool": tool,
                                "detail": detail,
                                "timestamp": datetime.now().isoformat(),
                            })
                        # Track files created/modified by Write/Edit
                        if tool in ("Write", "Edit"):
                            fp = inp.get("file_path", "")
                            if fp:
                                downloadable = _is_downloadable(fp)
                                file_meta = _build_file_meta(fp, downloadable)
                                session.setdefault("created_files", []).append(file_meta)
                                await manager.broadcast({
                                    "type": "chat_file_created",
                                    "chat_id": chat_id,
                                    "task_id": task_id,
                                    "session_id": session_id,
                                    **file_meta,
                                })
                                # Notify if file is inside chat_files/
                                cf_dir = TASKS_DIR / task_id / "chat_files"
                                try:
                                    if _is_subpath(Path(fp).resolve(), cf_dir.resolve()):
                                        await manager.broadcast({
                                            "type": "chat_files_updated",
                                            "task_id": task_id,
                                            "session_id": session_id,
                                        })
                                except (OSError, ValueError):
                                    pass
                _active_tool_blocks.clear()
                _sent_tool_ids.clear()

            # Result event -- summary + canonical text
            elif etype == "result":
                cost = event.get("cost_usd", "?")
                turns = event.get("num_turns", "?")
                # Use result text as canonical source -- it's the definitive
                # final output from Claude CLI and never doubled.
                result_text = event.get("result", "")
                if result_text:
                    accumulated_text = result_text
                await manager.broadcast({
                    "type": "chat_progress",
                    "chat_id": chat_id,
                    "task_id": task_id,
                    "session_id": session_id,
                    "event": "result",
                    "detail": f"Done ({turns} turns, ${cost})",
                    "timestamp": datetime.now().isoformat(),
                })

        exit_code = await loop.run_in_executor(None, process.wait)
        session["exit_code"] = exit_code
        session["status"] = "completed" if exit_code == 0 else "failed"
        session["response_text"] = accumulated_text

        # Persist BEFORE broadcasting done so frontend can reload history
        _save_chat_history(
            task_id, session_id, message, accumulated_text,
            attachments=attachments,
            created_files=session.get("created_files"),
        )
        history_saved = True

        # Final response signal with full accumulated text
        created_files = session.get("created_files", [])
        await manager.broadcast({
            "type": "chat_response",
            "chat_id": chat_id,
            "task_id": task_id,
            "session_id": session_id,
            "content": accumulated_text,
            "done": True,
            **({"created_files": created_files} if created_files else {}),
        })

    except Exception as e:
        session["status"] = "failed"
        session["error"] = str(e)
        logger.exception("Chat %s failed", chat_id)
    finally:
        _chat_processes.pop(chat_id, None)
        session["finished_at"] = datetime.now().isoformat()

        # Fallback: persist on error/cancel if not already saved
        if not history_saved:
            _save_chat_history(
                task_id, session_id, message, session.get("response_text", ""),
                attachments=attachments,
                created_files=session.get("created_files"),
            )
