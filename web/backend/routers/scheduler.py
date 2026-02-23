"""Scheduler control endpoints: detect triggers, run scheduler, init state."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..services import scheduler_service

router = APIRouter()


@router.post("/detect")
async def detect_triggers():
    """Poll the ClickUp API and compare with local state to detect triggers."""
    return await scheduler_service.detect_triggers()


@router.post("/run")
async def run_scheduler(
    dry_run: bool = Query(True, description="If True, only show what would be done"),
):
    """Run the full scheduler (detect + optionally analyze).

    Defaults to dry_run=True for safety.
    """
    return await scheduler_service.run_scheduler(dry_run=dry_run)


@router.post("/init-state")
async def init_state():
    """Build initial state.json from the existing tasks/ directory."""
    return await scheduler_service.init_state()
