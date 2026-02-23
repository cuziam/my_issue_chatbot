"""Patch management endpoints: fetch Doc patches and generate diffs."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..services import patch_service

router = APIRouter()


@router.post("/{task_id}/fetch-doc")
async def fetch_doc(
    task_id: str,
    dry_run: bool = Query(False, description="If True, only show what would be downloaded"),
):
    """Download patch files from ClickUp Docs linked to this task."""
    return await patch_service.fetch_doc_patches(task_id, dry_run=dry_run)


@router.post("/{task_id}/generate-diff")
async def generate_diff(task_id: str):
    """Detect patches, match against existing source, and generate unified diffs."""
    return await patch_service.generate_diff(task_id)
