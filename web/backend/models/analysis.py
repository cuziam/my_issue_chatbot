"""Pydantic models for analysis job management."""
from __future__ import annotations

from typing import Optional
from enum import Enum
from pydantic import BaseModel


class AnalysisMode(str, Enum):
    initial = "initial"
    verify = "verify"              # Readiness-checked review (replaces "review")
    activity_update = "activity_update"
    reopen = "reopen"              # Reopened issue analysis
    # Internal resolved modes (set by pipeline after readiness check)
    patch_review = "patch_review"
    verification = "verification"
    # Backward compat aliases (accepted from API, mapped internally)
    review = "review"              # → mapped to verify


class AnalysisStartRequest(BaseModel):
    task_id: str
    mode: AnalysisMode = AnalysisMode.initial


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    pending_resources = "pending_resources"  # Deferred: waiting for patches/packages


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
