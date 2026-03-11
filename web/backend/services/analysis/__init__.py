"""Analysis service package -- re-exports all public API for backward compatibility.

Existing code using ``from ..services.analysis_service import X`` should
be updated to ``from ..services.analysis import X``.  The module-level
attribute access pattern ``analysis_service.start_analysis(...)`` also
works when importing this package as a module.
"""
from .job_manager import (
    get_jobs,
    get_job,
    cancel_job,
    get_job_log,
    get_history,
    append_history,
    clear_completed_jobs,
    prune_completed_jobs,
    # Shared state (exposed for direct access if needed)
    _jobs,
    _processes,
    _cancelled_jobs,
    HISTORY_FILE,
    JOB_LOGS_DIR,
)
from .pipeline import start_analysis

__all__ = [
    "get_jobs",
    "get_job",
    "cancel_job",
    "get_job_log",
    "get_history",
    "append_history",
    "clear_completed_jobs",
    "prune_completed_jobs",
    "start_analysis",
    "_jobs",
    "_processes",
    "_cancelled_jobs",
    "HISTORY_FILE",
    "JOB_LOGS_DIR",
]
