"""Scheduler control endpoints: detect triggers, poller control, trigger management."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..services import scheduler_service
from ..services.scheduler_service import poller

router = APIRouter()


# ---------------------------------------------------------------------------
# Existing endpoints (detect + init-state)
# ---------------------------------------------------------------------------

@router.post("/detect")
async def detect_triggers():
    """Poll the ClickUp API and compare with local state to detect triggers."""
    async with poller._lock:
        result = await scheduler_service.detect_triggers()
    # Strip internal _api_tasks before returning
    result.pop("_api_tasks", None)
    return result


@router.post("/init-state")
async def init_state():
    """Build initial state.json from the existing tasks/ directory."""
    return await scheduler_service.init_state()


# ---------------------------------------------------------------------------
# Poller control endpoints
# ---------------------------------------------------------------------------

class PollerStartRequest(BaseModel):
    interval_minutes: int = 30
    auto_analyze: bool = True


class PollerConfigUpdate(BaseModel):
    interval_minutes: Optional[int] = None
    auto_analyze: Optional[bool] = None


@router.get("/poller/status")
async def get_poller_status():
    """Return current poller status."""
    return poller.status


@router.post("/poller/start")
async def start_poller(req: PollerStartRequest):
    """Start the background polling loop."""
    await poller.start(
        interval_minutes=req.interval_minutes,
        auto_analyze=req.auto_analyze,
    )
    return {"status": "ok", **poller.status}


@router.post("/poller/stop")
async def stop_poller():
    """Stop the background polling loop."""
    await poller.stop()
    return {"status": "ok", **poller.status}


@router.post("/poller/poll-now")
async def poll_now():
    """Execute a single poll cycle immediately."""
    result = await poller.poll_once()
    return result


@router.put("/poller/config")
async def update_poller_config(req: PollerConfigUpdate):
    """Update poller configuration at runtime."""
    await poller.update_config(
        interval_minutes=req.interval_minutes,
        auto_analyze=req.auto_analyze,
    )
    return {"status": "ok", **poller.status}


# ---------------------------------------------------------------------------
# Trigger management endpoints
# ---------------------------------------------------------------------------

class TriggerItem(BaseModel):
    task_id: str
    custom_id: Optional[str] = None
    mode: str
    reason: Optional[str] = None


class AnalyzeTriggersRequest(BaseModel):
    triggers: list[TriggerItem]


class DismissTriggersRequest(BaseModel):
    triggers: list[TriggerItem]


@router.post("/triggers/analyze")
async def analyze_triggers(req: AnalyzeTriggersRequest):
    """Start analysis for selected triggers."""
    trigger_dicts = [t.model_dump() for t in req.triggers]
    started_jobs = await poller.analyze_triggers(trigger_dicts)
    return {"status": "ok", "started_jobs": started_jobs}


@router.post("/triggers/dismiss")
async def dismiss_triggers(req: DismissTriggersRequest):
    """Dismiss selected triggers (prevent re-triggering)."""
    trigger_dicts = [t.model_dump() for t in req.triggers]
    count = await poller.dismiss_triggers(trigger_dicts)
    return {"status": "ok", "dismissed": count}
