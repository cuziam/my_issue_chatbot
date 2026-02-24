"""Pydantic models for chat session management."""
from __future__ import annotations

from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    session_id: str | None = None  # None => create new session
    message: str


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    timestamp: str
