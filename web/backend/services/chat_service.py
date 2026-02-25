"""Chat service — resume Claude sessions for follow-up conversations.

Uses ``claude --resume SESSION_ID`` to continue previous analysis sessions,
preserving full context from the original analysis.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path

from ..config import ROOT_DIR, TASKS_DIR, PACKAGES_DIR
from ..ws.manager import manager
from .claude_subprocess import clean_env, summarize_tool_input

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Upload constants
# ---------------------------------------------------------------------------
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file
MAX_TASK_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB per task
UPLOAD_MAX_AGE_DAYS = 7

ALLOWED_EXTENSIONS: dict[str, str] = {
    # image
    ".jpg": "image", ".jpeg": "image", ".png": "image",
    ".gif": "image", ".webp": "image",
    # text
    ".txt": "text", ".log": "text", ".csv": "text",
    ".xml": "text", ".json": "text", ".conf": "text",
    ".properties": "text", ".yaml": "text", ".yml": "text",
    ".md": "text", ".java": "text", ".py": "text",
    ".js": "text", ".ts": "text", ".html": "text", ".css": "text",
    # archive
    ".zip": "archive",
}

SENSITIVE_FILENAMES = {
    ".env", ".key", "credentials.json", "secrets.yaml",
    "secret.json", "secret.key",
}

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


async def handle_upload(task_id: str, filename: str, content: bytes) -> dict:
    """Validate, save an uploaded file, and return metadata.

    Raises ``ValueError`` for validation failures.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {ext}")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE})")

    file_type = ALLOWED_EXTENSIONS[ext]

    upload_dir = TASKS_DIR / task_id / "chat_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Check task quota
    _check_task_quota(upload_dir, len(content))

    # Clean up old files
    _cleanup_old_uploads(upload_dir)

    # Build unique filename: sanitized_name_hash8.ext
    stem = _sanitize_filename(Path(filename).stem)
    content_hash = hashlib.md5(content).hexdigest()[:8]
    safe_name = f"{stem}_{content_hash}{ext}"
    dest = upload_dir / safe_name

    dest.write_bytes(content)

    abs_path = str(dest.absolute()).replace("\\", "/")
    return {
        "name": filename,
        "path": abs_path,
        "type": file_type,
        "size": len(content),
        "url": f"/api/chat/{task_id}/uploads/{safe_name}",
    }


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


async def list_chat_files(task_id: str) -> list[dict]:
    """List files in tasks/{task_id}/chat_files/."""
    chat_files_dir = TASKS_DIR / task_id / "chat_files"
    if not chat_files_dir.exists():
        return []
    files = []
    for f in sorted(chat_files_dir.iterdir()):
        if not f.is_file():
            continue
        try:
            stat = f.stat()
            files.append({
                "name": f.name,
                "path": str(f.absolute()).replace("\\", "/"),
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        except OSError:
            continue
    return files


async def delete_chat_file(task_id: str, filename: str) -> bool:
    """Delete a file from tasks/{task_id}/chat_files/."""
    file_path = TASKS_DIR / task_id / "chat_files" / filename
    if not file_path.exists() or not file_path.is_file():
        return False
    file_path.unlink()
    return True


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

    try:
        if is_new_session:
            context = _build_task_context(task_id)
            prompt = f"{context}\n---\n**User question**: {message}"
            if attachment_section:
                prompt += f"\n\n{attachment_section}"
            cmd = [
                "claude",
                "-p", prompt,
                "--verbose",
                "--output-format", "stream-json",
                "--session-id", session_id,
                "--allowedTools",
                "Read,Glob,Grep,Bash,Write,Edit",
            ]
        else:
            prompt = message
            if attachment_section:
                prompt += f"\n\n{attachment_section}"
            cmd = [
                "claude",
                "-p", prompt,
                "--verbose",
                "--output-format", "stream-json",
                "--resume", session_id,
                "--allowedTools",
                "Read,Glob,Grep,Bash,Write,Edit",
            ]

        # Instruct Claude to write downloadable files into chat_files/
        chat_files_dir = TASKS_DIR / task_id / "chat_files"
        chat_files_abs = str(chat_files_dir.absolute()).replace("\\", "/")
        file_system_prompt = (
            f"IMPORTANT: 파일을 생성하거나 저장할 때는 반드시 {chat_files_abs}/ 에 Write하세요. "
            f"코드, 스크립트, 문서 등 사용자가 다운로드할 수 있는 결과물은 텍스트로만 보여주지 말고 "
            f"Write 도구를 사용하여 해당 디렉토리에 저장하세요."
        )
        cmd += ["--append-system-prompt", file_system_prompt]

        env = clean_env()

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
        accumulated_text = ""  # Accumulated text across all turns

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
                "line": decoded,
            })

            # Parse stream-json event
            try:
                event = json.loads(decoded)
            except (json.JSONDecodeError, ValueError):
                continue

            etype = event.get("type")

            # Streaming text deltas — real-time character-by-character
            if etype == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    accumulated_text += delta.get("text", "")
                    await manager.broadcast({
                        "type": "chat_response",
                        "chat_id": chat_id,
                        "task_id": task_id,
                        "content": accumulated_text,
                        "done": False,
                    })

            # Full assistant message (end of each turn) — extract text + tool calls
            elif etype == "assistant":
                for item in event.get("message", {}).get("content", []):
                    kind = item.get("type")
                    if kind == "text":
                        text = item.get("text", "")
                        if text:
                            accumulated_text += text
                            await manager.broadcast({
                                "type": "chat_response",
                                "chat_id": chat_id,
                                "task_id": task_id,
                                "content": accumulated_text,
                                "done": False,
                            })
                    elif kind == "tool_use":
                        tool = item.get("name", "")
                        inp = item.get("input", {})
                        detail = summarize_tool_input(tool, inp)
                        await manager.broadcast({
                            "type": "chat_progress",
                            "chat_id": chat_id,
                            "task_id": task_id,
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
                                    **file_meta,
                                })
                                # Notify if file is inside chat_files/
                                cf_dir = TASKS_DIR / task_id / "chat_files"
                                try:
                                    if _is_subpath(Path(fp).resolve(), cf_dir.resolve()):
                                        await manager.broadcast({
                                            "type": "chat_files_updated",
                                            "task_id": task_id,
                                        })
                                except (OSError, ValueError):
                                    pass

            # Result event — summary
            elif etype == "result":
                cost = event.get("cost_usd", "?")
                turns = event.get("num_turns", "?")
                # Extract final text from result if accumulated_text is empty
                result_text = event.get("result", "")
                if result_text and not accumulated_text:
                    accumulated_text = result_text
                await manager.broadcast({
                    "type": "chat_progress",
                    "chat_id": chat_id,
                    "task_id": task_id,
                    "event": "result",
                    "detail": f"Done ({turns} turns, ${cost})",
                    "timestamp": datetime.now().isoformat(),
                })

        exit_code = await loop.run_in_executor(None, process.wait)
        session["exit_code"] = exit_code
        session["status"] = "completed" if exit_code == 0 else "failed"
        session["response_text"] = accumulated_text

        # Final response signal with full accumulated text
        created_files = session.get("created_files", [])
        await manager.broadcast({
            "type": "chat_response",
            "chat_id": chat_id,
            "task_id": task_id,
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

        # Persist to chat_history.json
        _save_chat_history(
            task_id, session_id, message, session.get("response_text", ""),
            attachments=attachments,
            created_files=session.get("created_files"),
        )


def _save_chat_history(
    task_id: str,
    session_id: str,
    message: str,
    response: str,
    attachments: list[dict] | None = None,
    created_files: list[dict] | None = None,
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


def _load_chat_history(task_id: str) -> list[dict]:
    """Load chat_history.json for a task."""
    history_file = TASKS_DIR / task_id / "chat_history.json"
    if not history_file.exists():
        return []
    try:
        return json.loads(history_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return []


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------

def _sanitize_filename(stem: str) -> str:
    """Remove unsafe characters from a filename stem."""
    import re
    sanitized = re.sub(r'[^\w\-.]', '_', stem)
    return sanitized[:60] if sanitized else "file"


def _check_task_quota(upload_dir: Path, new_size: int) -> None:
    """Raise ValueError if task upload quota would be exceeded."""
    total = sum(f.stat().st_size for f in upload_dir.iterdir() if f.is_file())
    if total + new_size > MAX_TASK_UPLOAD_SIZE:
        raise ValueError(
            f"Task upload quota exceeded: {total + new_size} bytes "
            f"(max {MAX_TASK_UPLOAD_SIZE})"
        )


def _cleanup_old_uploads(upload_dir: Path) -> None:
    """Delete files older than UPLOAD_MAX_AGE_DAYS."""
    cutoff = time.time() - UPLOAD_MAX_AGE_DAYS * 86400
    for f in upload_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                logger.debug("Cleaned up old upload: %s", f)
            except OSError:
                pass


def _build_attachment_section(attachments: list[dict] | None) -> str:
    """Build a prompt section listing attached files for Claude to Read."""
    if not attachments:
        return ""
    lines = ["**첨부 파일** (Read 도구로 확인하세요):"]
    for att in attachments:
        lines.append(f"- [{att['type']}] {att['path']}")
    return "\n".join(lines)
