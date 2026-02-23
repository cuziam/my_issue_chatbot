"""Pydantic models for analysis job management."""
from __future__ import annotations

from typing import Optional
from enum import Enum
from pydantic import BaseModel


class AnalysisMode(str, Enum):
    initial = "initial"
    verification = "verification"
    activity_update = "activity_update"
    patch_review = "patch_review"
    review = "review"  # Meta mode: auto-resolves to patch_review or verification


class AnalysisStartRequest(BaseModel):
    task_id: str
    mode: AnalysisMode = AnalysisMode.initial


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AnalysisJob(BaseModel):
    id: str
    task_id: str
    mode: str
    status: JobStatus
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    output_lines: list[str] = []
    exit_code: Optional[int] = None
    error: Optional[str] = None
