"""Pydantic models for chat session management."""
from typing import Optional

from pydantic import BaseModel


class ChatAttachment(BaseModel):
    name: str
    path: str
    type: str  # "image" | "text" | "archive"
    size: int


class ChatMessageRequest(BaseModel):
    session_id: Optional[str] = None  # None => create new session
    message: str = ""
    attachments: list[ChatAttachment] = []


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    timestamp: str
