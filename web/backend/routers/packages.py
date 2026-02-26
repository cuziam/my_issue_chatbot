"""Package management endpoints: upload, delete, job tracking."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from starlette.requests import ClientDisconnect

from ..services.package_service import (
    cancel_upload,
    delete_package,
    get_upload_jobs,
    handle_upload,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload")
async def upload_package(request: Request, file: UploadFile = File(...)):
    """Upload an archive (.tar.gz, .tar, .zip) to packages/.

    The file is streamed to disk in chunks to avoid loading into memory.
    After upload, extraction and optional decompilation run in background.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    content_length = request.headers.get("content-length")
    total_size = int(content_length) if content_length else None

    try:
        result = await handle_upload(
            request=request,
            filename=file.filename,
            file=file,
            content_length=total_size,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ClientDisconnect:
        # Client disconnected — nothing to return
        raise HTTPException(status_code=499, detail="Client disconnected")
    except Exception as exc:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/upload/jobs")
async def list_upload_jobs():
    """Return all upload jobs (in-memory, recent first)."""
    return {"jobs": get_upload_jobs()}


@router.post("/upload/jobs/{upload_id}/cancel")
async def cancel_upload_job(upload_id: str):
    """Cancel an in-progress upload or processing job."""
    if cancel_upload(upload_id):
        return {"status": "cancelled", "upload_id": upload_id}
    raise HTTPException(status_code=404, detail=f"Upload job '{upload_id}' not found")


@router.delete("/{name}")
async def delete_package_endpoint(name: str):
    """Delete a package directory and its archive(s)."""
    try:
        result = await delete_package(name)
        return {"status": "deleted", **result}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Delete failed for %s", name)
        raise HTTPException(status_code=500, detail=str(exc))
