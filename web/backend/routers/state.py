"""State management endpoints for viewing/modifying scheduler state."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ..services.scheduler_service import load_state, reset_trigger_attempts

router = APIRouter()


@router.get("")
async def get_state():
    """Return the current state.json contents."""
    return load_state()


@router.put("/tasks/{task_id}/reset-attempts")
async def reset_attempts(
    task_id: str,
    mode: Optional[str] = Query(None, description="Specific mode to reset, or omit to reset all"),
):
    """Reset trigger_attempts for a task in state.json."""
    return reset_trigger_attempts(task_id, mode)
