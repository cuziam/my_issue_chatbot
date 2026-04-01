"""Digest generation and management endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services import digest_service

router = APIRouter()


class GenerateRequest(BaseModel):
    date_from: str
    date_to: str
    issue_type: str | None = None


class UpdateRequest(BaseModel):
    content: str


@router.get("")
async def list_digests():
    """List all generated digests, newest first."""
    digests = digest_service.list_digests()
    return {"digests": digests, "total": len(digests)}


@router.post("/generate")
async def generate_digest(request: GenerateRequest):
    """Start digest generation for a date range."""
    job = await digest_service.generate_digest(
        request.date_from, request.date_to, issue_type=request.issue_type,
    )
    return job


@router.get("/jobs")
async def list_digest_jobs():
    """List all in-memory digest jobs (running + recently completed)."""
    jobs = digest_service.get_digest_jobs()
    return {"jobs": jobs}


@router.get("/jobs/{job_id}")
async def get_digest_job(job_id: str):
    """Get the status of a digest generation job."""
    job = digest_service.get_digest_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Digest job {job_id} not found")
    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_digest_job(job_id: str):
    """Cancel a running digest generation job."""
    success = await digest_service.cancel_digest(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"No running digest job {job_id}")
    return {"status": "cancelled", "job_id": job_id}


@router.get("/{digest_id}")
async def get_digest(digest_id: str):
    """Get a single digest with its markdown content."""
    result = digest_service.get_digest(digest_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Digest {digest_id} not found")
    return result


@router.delete("/{digest_id}")
async def delete_digest(digest_id: str):
    """Delete a digest from history."""
    success = digest_service.delete_digest(digest_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Digest {digest_id} not found")
    return {"status": "deleted", "digest_id": digest_id}


@router.put("/{digest_id}")
async def update_digest(digest_id: str, request: UpdateRequest):
    """Update digest content (edit feature)."""
    result = digest_service.update_digest(digest_id, request.content)
    if not result:
        raise HTTPException(status_code=404, detail=f"Digest {digest_id} not found")
    return result
