"""FastAPI application for the InterMax Issue Analysis Bot Dashboard.

Run with:
    uvicorn web.backend.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import LOGS_DIR, ROOT_DIR, TASKS_DIR

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
from .routers import analysis, chat, digest, packages, patches, scheduler, settings, state, tasks


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

    # Clean up incomplete uploads from previous sessions
    from .services.package_service import cleanup_incoming
    cleaned = cleanup_incoming()
    if cleaned:
        logging.getLogger(__name__).info("Cleaned %d leftover files from _incoming/", cleaned)

    # Start streaming pool cleanup loop for chat
    from .services.llm import get_streaming_pool
    streaming_pool = get_streaming_pool()
    streaming_pool.start_cleanup_loop()

    # Auto-start scheduler poller if configured
    from .config import load_config
    from .services.scheduler_service import poller
    try:
        cfg = load_config()
        poller_cfg = cfg.get("scheduler", {}).get("poller", {})
        if poller_cfg.get("enabled_on_startup", False):
            interval = poller_cfg.get("interval_minutes", 30)
            auto_analyze = poller_cfg.get("auto_analyze", True)
            await poller.start(interval_minutes=interval, auto_analyze=auto_analyze)
            logging.getLogger(__name__).info(
                "SchedulerPoller auto-started: interval=%dm, auto_analyze=%s",
                interval, auto_analyze,
            )
    except Exception:
        logging.getLogger(__name__).warning("Failed to auto-start SchedulerPoller", exc_info=True)

    yield

    # Shutdown: stop streaming pool
    try:
        await streaming_pool.shutdown()
    except Exception:
        pass

    # Shutdown: stop poller gracefully
    try:
        await poller.stop()
    except Exception:
        pass


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
app.include_router(packages.router, prefix="/api/packages", tags=["packages"])
app.include_router(digest.router, prefix="/api/digests", tags=["digests"])

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


# ---------------------------------------------------------------------------
# Frontend SPA serving (production build)
# ---------------------------------------------------------------------------
if FRONTEND_DIST.is_dir():
    # Serve static assets (JS, CSS, images) from the Vite build output
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA catch-all: serve index.html for any non-API, non-file route.

        This must be registered AFTER all API routes and static mounts so
        that /api/*, /files/*, and /assets/* are matched first.
        """
        # Try to serve an exact file from dist (e.g. favicon.ico)
        file_path = FRONTEND_DIST / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise, serve index.html for SPA client-side routing
        return FileResponse(FRONTEND_DIST / "index.html")
