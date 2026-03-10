"""Chat service package — re-exports all public API for backward compatibility.

Modules:
    session_manager  — Session/history CRUD
    chat_runner      — Chat execution (send_message, cancel_chat)
    upload_handler   — File upload handling
    task_files       — Task/chat file listing
"""
from .session_manager import get_sessions, get_chat_history
from .chat_runner import send_message, cancel_chat
from .upload_handler import handle_upload
from .task_files import list_task_files, list_chat_files, delete_chat_file

__all__ = [
    "get_sessions",
    "get_chat_history",
    "send_message",
    "cancel_chat",
    "handle_upload",
    "list_task_files",
    "list_chat_files",
    "delete_chat_file",
]
