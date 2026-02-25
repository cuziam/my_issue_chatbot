"""Chat endpoints for interactive follow-up conversations."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pathlib import Path

from ..config import TASKS_DIR, PACKAGES_DIR
from ..models.chat import ChatMessageRequest
from ..services import chat_service

router = APIRouter()


@router.get("/{task_id}/sessions")
async def list_sessions(task_id: str):
    """List available Claude sessions for a task."""
    sessions = await chat_service.get_sessions(task_id)
    return {"sessions": sessions}


@router.get("/{task_id}/history")
async def get_history(task_id: str):
    """Get chat history for a task."""
    messages = await chat_service.get_chat_history(task_id)
    return {"messages": messages}


@router.post("/{task_id}/upload")
async def upload_file(task_id: str, file: UploadFile):
    """Upload a file for chat attachment."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    content = await file.read()
    try:
        meta = await chat_service.handle_upload(task_id, file.filename, content)
    except ValueError as e:
        status = 413 if "too large" in str(e) or "quota" in str(e) else 400
        raise HTTPException(status_code=status, detail=str(e))

    return meta


@router.get("/{task_id}/uploads/{filename}")
async def serve_upload(task_id: str, filename: str):
    """Serve an uploaded file (for image previews)."""
    file_path = TASKS_DIR / task_id / "chat_uploads" / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    # Prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return FileResponse(file_path)


@router.post("/{task_id}/send")
async def send_message(task_id: str, body: ChatMessageRequest):
    """Send a message to a Claude session, streaming the response via WS."""
    attachments = [a.model_dump() for a in body.attachments] if body.attachments else None
    result = await chat_service.send_message(
        task_id, body.session_id, body.message, attachments=attachments
    )
    return result


@router.get("/{task_id}/task-files")
async def list_task_files(task_id: str):
    """List all task files across categories (images, patches, uploads, AI, reports)."""
    return await chat_service.list_task_files(task_id)


@router.get("/{task_id}/files")
async def list_chat_files(task_id: str):
    """List files in the chat_files/ directory for a task."""
    files = await chat_service.list_chat_files(task_id)
    return {"files": files}


@router.delete("/{task_id}/files/{filename}")
async def delete_chat_file(task_id: str, filename: str):
    """Delete a file from the chat_files/ directory."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    success = await chat_service.delete_chat_file(task_id, filename)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "deleted"}


@router.post("/active/{chat_id}/cancel")
async def cancel_chat(chat_id: str):
    """Cancel a running chat process."""
    success = await chat_service.cancel_chat(chat_id)
    return {"status": "ok" if success else "not_found"}


# ---------------------------------------------------------------------------
# File download (for Claude-created files)
# ---------------------------------------------------------------------------

_ALLOWED_DOWNLOAD_DIRS = [TASKS_DIR, PACKAGES_DIR]
_SENSITIVE_FILENAMES = {
    ".env", ".key", "credentials.json", "secrets.yaml",
    "secret.json", "secret.key",
}
_MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


@router.get("/download")
async def download_file(path: str):
    """Download a file created by Claude (restricted to tasks/ and packages/)."""
    try:
        resolved = Path(path).resolve(strict=True)
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="File not found")

    # Check allowed directories
    allowed = False
    for d in _ALLOWED_DOWNLOAD_DIRS:
        try:
            resolved.relative_to(d.resolve())
            allowed = True
            break
        except ValueError:
            continue
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Access denied: file outside allowed directories",
        )

    # Sensitive file check
    if resolved.name.lower() in _SENSITIVE_FILENAMES:
        raise HTTPException(status_code=403, detail="Access denied: sensitive file")

    # Size check
    try:
        size = resolved.stat().st_size
    except OSError:
        raise HTTPException(status_code=404, detail="File not found")
    if size > _MAX_DOWNLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {size} bytes (max {_MAX_DOWNLOAD_SIZE})",
        )

    return FileResponse(
        path=str(resolved),
        filename=resolved.name,
        media_type="application/octet-stream",
    )
