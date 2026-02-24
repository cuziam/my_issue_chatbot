"""Pydantic models for chat session management."""
from typing import Optional

from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    session_id: Optional[str] = None  # None => create new session
    message: str


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    timestamp: str
