"""Progress event emitter for analysis pipeline stages.

Eliminates the duplicated ``_emit`` inner functions that were copy-pasted
across ``_refresh_inventory``, ``_resolve_review_mode``,
``_try_version_diff``, and ``_auto_decompile`` in analysis_service.py.
"""
from __future__ import annotations

from datetime import datetime


class ProgressEmitter:
    """Builds progress event dicts, appends to a job, and broadcasts via WS."""

    def __init__(self, job_id: str, jobs_store: dict, ws_manager) -> None:
        self._job_id = job_id
        self._jobs = jobs_store
        self._ws = ws_manager

    async def emit(self, detail: str, event_type: str = "text") -> None:
        """Create, store, and broadcast a progress event."""
        event = {
            "event": event_type,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        }
        self._jobs[self._job_id]["progress_events"].append(event)
        await self._ws.broadcast(
            {"type": "progress", "job_id": self._job_id, **event}
        )
