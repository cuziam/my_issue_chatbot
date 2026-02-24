"""Chat endpoints for interactive follow-up conversations."""
from __future__ import annotations

from fastapi import APIRouter

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


@router.post("/{task_id}/send")
async def send_message(task_id: str, body: ChatMessageRequest):
    """Send a message to a Claude session, streaming the response via WS."""
    result = await chat_service.send_message(task_id, body.session_id, body.message)
    return result


@router.post("/active/{chat_id}/cancel")
async def cancel_chat(chat_id: str):
    """Cancel a running chat process."""
    success = await chat_service.cancel_chat(chat_id)
    return {"status": "ok" if success else "not_found"}
