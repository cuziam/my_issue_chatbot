"""Task listing and detail endpoints."""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from ..services import task_service

router = APIRouter()


@router.get("")
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status (case-insensitive)"),
    search: Optional[str] = Query(None, description="Search in task name/id"),
    has_report: Optional[bool] = Query(None, description="Filter by report existence"),
    date_from: Optional[str] = Query(None, description="Filter tasks created on or after this date (YYYY-MM-DD or ms epoch)"),
    date_to: Optional[str] = Query(None, description="Filter tasks created on or before this date (YYYY-MM-DD or ms epoch)"),
):
    """List all locally downloaded tasks with optional filters."""
    tasks = task_service.list_tasks(
        status_filter=status,
        search=search,
        has_report=has_report,
        date_from=date_from,
        date_to=date_to,
    )
    return {"tasks": tasks, "total": len(tasks)}


@router.get("/{task_id}")
async def get_task(task_id: str):
    """Get full task detail including report/review/context content."""
    detail = task_service.get_task_detail(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return detail


@router.post("/{task_id}/fetch")
async def fetch_task(task_id: str):
    """Fetch a task from the ClickUp API and save it locally.

    Uses a lazy import of ``issuebot/fetch.py`` so the server can start
    even without a CLICKUP_API_KEY configured.
    """

    def _run():
        from issuebot.fetch import (
            fetch_task as _fetch,
            fetch_comments as _fetch_comments,
            save_task as _save,
        )

        data = _fetch(task_id)
        if not data:
            return None
        comments = _fetch_comments(task_id)
        _save(task_id, data, comments)
        return True

    result = await asyncio.to_thread(_run)
    if result is None:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch task {task_id} from ClickUp",
        )

    return {"status": "ok", "message": f"Task {task_id} fetched and saved"}
