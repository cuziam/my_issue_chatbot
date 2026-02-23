"""Analysis job management endpoints and WebSocket for real-time streaming."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..models.analysis import AnalysisStartRequest
from ..services import analysis_service
from ..ws.manager import manager

router = APIRouter()


@router.post("/start")
async def start_analysis(request: AnalysisStartRequest):
    """Start a new Claude analysis subprocess."""
    job = await analysis_service.start_analysis(request.task_id, request.mode.value)
    return job


@router.get("/jobs")
async def list_jobs():
    """List all in-memory jobs (running and recently finished)."""
    return {"jobs": analysis_service.get_jobs()}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get a single job by ID."""
    job = analysis_service.get_job(job_id)
    if not job:
        return {"error": "Job not found"}
    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running analysis job."""
    success = await analysis_service.cancel_job(job_id)
    return {"status": "ok" if success else "not_found"}


@router.get("/history")
async def get_history():
    """Return the persisted analysis history from analysis_history.jsonl."""
    return {"history": analysis_service.get_history()}


@router.get("/diagnostic")
async def diagnostic():
    """Test that the claude CLI can be spawned as a subprocess.

    Returns environment info, PATH resolution, and a quick ``claude --version``
    test so problems can be diagnosed from the browser.
    """
    env = analysis_service._clean_env()
    claude_path = shutil.which("claude", path=env.get("PATH"))

    result: dict = {
        "claude_in_path": claude_path,
        "removed_env_vars": [k for k in os.environ if k.upper().startswith("CLAUDE")],
    }

    if not claude_path:
        result["error"] = "claude not found in PATH"
        return result

    loop = asyncio.get_running_loop()
    try:
        proc = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                env=env,
                timeout=10,
            ),
        )
        result["version_test"] = {
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as e:
        result["version_test"] = {"error": f"{type(e).__name__}: {e}"}

    return result


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time analysis output streaming.

    Clients can send JSON messages with ``{"type": "cancel", "job_id": "..."}``
    to cancel a running job.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "cancel" and msg.get("job_id"):
                await analysis_service.cancel_job(msg["job_id"])
    except WebSocketDisconnect:
        manager.disconnect(websocket)
