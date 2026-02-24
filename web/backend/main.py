"""FastAPI application for the InterMax Issue Analysis Bot Dashboard.

Run with:
    uvicorn web.backend.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import LOGS_DIR, ROOT_DIR, TASKS_DIR
from .routers import analysis, chat, patches, scheduler, settings, state, tasks


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure required directories exist on startup."""
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="InterMax Issue Analysis Bot",
    description="Backend API for the InterMax Issue Analysis Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["scheduler"])
app.include_router(patches.router, prefix="/api/patches", tags=["patches"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(state.router, prefix="/api/state", tags=["state"])

# ---------------------------------------------------------------------------
# Static file serving for task images, reports, etc.
# ---------------------------------------------------------------------------
app.mount("/files", StaticFiles(directory=str(ROOT_DIR)), name="files")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    """Simple health-check endpoint."""
    return {"status": "ok"}
