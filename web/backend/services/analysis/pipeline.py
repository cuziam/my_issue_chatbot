"""Analysis execution pipeline: subprocess management and mode resolution.

Handles starting Claude analysis subprocesses, resolving review modes,
building prompts, refreshing inventory, and auto-decompiling packages.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import shutil
import subprocess
import traceback
import uuid
from datetime import datetime
from pathlib import Path

from ...config import ROOT_DIR, TASKS_DIR, PACKAGES_DIR
from ...ws.manager import manager
from ..claude_subprocess import parse_stream_events
from ..progress_emitter import ProgressEmitter
from ...utils.platform import interpret_exit_code as _interpret_exit_code, is_retryable_exit as _is_retryable
from ..llm import get_llm_backend

from .job_manager import (
    _jobs,
    _processes,
    _cancelled_jobs,
    JOB_LOGS_DIR,
    append_history,
)

from issuebot.shared import detect_patch_presence as _detect_local_patches

logger = logging.getLogger(__name__)

ISSUEBOT_DIR = ROOT_DIR / "issuebot"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def start_analysis(task_id: str, mode: str) -> dict:
    """Start a ``claude -p`` analysis subprocess and return the job dict.

    Pre-validates that task.json exists and ``claude`` CLI is available.
    Returns an error dict (status="error") on validation failure instead of
    spawning a doomed subprocess.

    When *mode* is ``"review"``, the actual mode (``patch_review`` or
    ``verification``) is resolved in the background inside ``_run_process``.
    """
    # --- Pre-validation ---
    task_dir = TASKS_DIR / task_id
    task_json = task_dir / "task.json"
    if not task_json.exists():
        return {
            "status": "error",
            "message": f"task.json not found for {task_id}. Run Fetch Task first.",
        }

    llm = get_llm_backend()
    if not llm.is_available():
        return {
            "status": "error",
            "message": "claude CLI not found in PATH. Install Claude Code first.",
        }

    job_id = str(uuid.uuid4())[:8]

    job: dict = {
        "id": job_id,
        "task_id": task_id,
        "mode": mode,
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "output_lines": [],
        "progress_events": [],
        "exit_code": None,
        "exit_reason": None,
        "error": None,
        "session_id": None,
        "retry_count": 0,
        "retry_job_id": None,
    }
    _jobs[job_id] = job

    # Notify connected clients
    await manager.broadcast({"type": "job_started", "job": job})

    # Fire-and-forget the subprocess task
    asyncio.create_task(_run_process(job_id, task_id, mode))

    return job


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_prompt(task_id: str, mode: str, task_dir: Path) -> str:
    """Build the ``claude -p`` prompt for a given mode.

    Mirrors ``scheduler.build_analysis_prompt`` but runs inside the web
    backend.  This is called *after* review mode resolution, so *mode*
    is always a concrete mode here.
    """
    if mode == "patch_review":
        return (
            f"{task_id} 패치 리뷰해줘.\n"
            f"task_dir: {task_dir}\n"
            f".claude/agents/patch-reviewer.md 에이전트 정의를 따라 patch_review.md를 작성하세요."
        )
    if mode == "verification":
        return (
            f"{task_id} 팔로업: 이 이슈는 \"qa to do\" 상태로 전환되었습니다.\n"
            f"개발자가 수정을 완료했으므로, 수정 사항이 올바르게 구현되었는지 검증 분석을 수행해줘.\n"
            f"기존 report.md의 \"참고: 코드 레벨 원인\"에 명시된 수정 방안이 실제로 반영되었는지 확인하고,\n"
            f"QA 검증 시나리오를 업데이트해줘."
        )
    if mode == "activity_update":
        return (
            f"{task_id} 팔로업: 이 이슈에 새로운 활동이 감지되었습니다.\n"
            f"새 댓글이나 본문 업데이트가 있으므로, "
            f"기존 report.md를 참고하여 추가 분석을 수행해줘.\n"
            f"변경된 내용이 기존 분석에 영향을 미치는지 확인하고, "
            f"필요하면 report.md에 추가 분석을 append해줘."
        )
    # initial or fallback
    return f"{task_id}를 agent team으로 분석해줘"


async def _refresh_inventory(job_id: str) -> None:
    """Regenerate packages/inventory.json before analysis.

    Ensures the researcher agent sees all available packages (including
    recently added ones).  Runs inventory.py as an import to avoid
    spawning a subprocess.
    """
    emit = ProgressEmitter(job_id, _jobs, manager).emit

    try:
        from issuebot.inventory import generate_inventory

        loop = asyncio.get_running_loop()
        inv = await loop.run_in_executor(None, generate_inventory)

        inv_file = PACKAGES_DIR / "inventory.json"
        def _write():
            with open(inv_file, "w", encoding="utf-8") as f:
                json.dump(inv, f, indent=2, ensure_ascii=False)
        await loop.run_in_executor(None, _write)

        pkg_count = inv.get("package_count", 0)
        unextracted = sum(1 for p in inv.get("packages", []) if not p.get("extracted", True))
        msg = f"Package inventory refreshed ({pkg_count} packages"
        if unextracted:
            msg += f", {unextracted} unextracted archives"
        msg += ")"
        await emit(msg)
    except Exception as e:
        await emit(f"Inventory refresh failed: {e} -- continuing with existing inventory")


async def _resolve_review_mode(
    job_id: str, task_id: str, task_dir: Path
) -> str:
    """Resolve the ``review`` meta-mode to ``patch_review`` or ``verification``.

    Mirrors the scheduler's verification routing logic:
    1. Check for local patches (instant).
    2. If none, try fetching from ClickUp Doc via ``patch_service``.
    3. If patches found, generate diff.
    4. Return ``"patch_review"`` or ``"verification"``.

    Each step broadcasts a progress event for real-time UI feedback.
    """
    from .. import patch_service  # lazy to avoid circular imports

    emit = ProgressEmitter(job_id, _jobs, manager).emit

    # Step 1: Check local patches
    await emit("Checking local patches...")
    has_patches = await asyncio.to_thread(_detect_local_patches, task_dir)

    # Step 2: If no local patches, try fetching from ClickUp Doc
    if not has_patches:
        await emit("Fetching from ClickUp Doc...")
        try:
            result = await patch_service.fetch_doc_patches(task_id)
            if result.get("status") == "ok" and result.get("files"):
                has_patches = await asyncio.to_thread(
                    _detect_local_patches, task_dir
                )
                if has_patches:
                    await emit(
                        f"Downloaded {len(result['files'])} patch files from Doc"
                    )
                else:
                    await emit("Doc fetch completed but no patch files found")
            else:
                await emit("No patch files in ClickUp Doc")
        except Exception as e:
            await emit(f"Doc fetch failed: {e} -- falling back to verification")
            return "verification"

    # Step 3: Generate diff if patches exist
    if has_patches:
        await emit("Generating patch diff...")
        try:
            diff_result = await patch_service.generate_diff(task_id)
            file_count = diff_result.get("file_count", 0)
            await emit(f"Patch diff generated ({file_count} files)")
        except Exception as e:
            await emit(f"Diff generation failed: {e} -- proceeding with patch review")
        resolved = "patch_review"
    else:
        # Step 4: Try version diff (compare old vs new package)
        version_diff_result = await _try_version_diff(job_id, task_id, task_dir)
        if version_diff_result:
            resolved = "patch_review"
        else:
            resolved = "verification"

    await emit(f"Mode resolved: QA Review -> {resolved.replace('_', ' ').title()}")
    return resolved


async def _try_version_diff(
    job_id: str, task_id: str, task_dir: Path
) -> dict | None:
    """Try generating a version diff between old and new packages.

    When no explicit patches are found, checks if a newer package version
    exists and generates patch_diff.md/json from the version comparison.
    """
    import sys

    emit = ProgressEmitter(job_id, _jobs, manager).emit

    try:
        await emit("Checking for newer package version...")

        if str(ISSUEBOT_DIR) not in sys.path:
            sys.path.insert(0, str(ISSUEBOT_DIR))
        from version_diff import generate_version_diff  # type: ignore[import-untyped]

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, generate_version_diff, task_id)

        if result:
            await emit(
                f"Version diff generated: {result['old_pkg']} -> "
                f"{result['new_pkg']} ({result['file_count']} files)"
            )
            return result
        else:
            await emit("No newer package version found -- using verification mode")
            return None
    except Exception as e:
        await emit(f"Version diff failed: {e} -- falling back to verification")
        return None


async def _auto_decompile(job_id: str) -> None:
    """Auto-decompile packages with needs_decompile=True.

    Reads inventory.json for packages needing decompilation, runs the
    decompile script, then refreshes inventory to update components.
    """
    import sys

    emit = ProgressEmitter(job_id, _jobs, manager).emit

    try:
        # Read current inventory
        inv_file = PACKAGES_DIR / "inventory.json"
        if not inv_file.exists():
            return

        with open(inv_file, "r", encoding="utf-8") as f:
            inventory = json.load(f)

        needs = [
            p for p in inventory.get("packages", [])
            if p.get("needs_decompile") and p.get("extracted", True)
        ]

        if not needs:
            return

        await emit(f"Auto-decompiling {len(needs)} package(s)...")

        if str(ISSUEBOT_DIR) not in sys.path:
            sys.path.insert(0, str(ISSUEBOT_DIR))
        from decompile_runner import run_decompile  # type: ignore[import-untyped]

        loop = asyncio.get_running_loop()
        succeeded = 0
        for pkg in needs:
            pkg_name = pkg["name"]
            await emit(f"Decompiling: {pkg_name}")
            result = await loop.run_in_executor(None, run_decompile, pkg_name)
            if result["success"]:
                succeeded += 1
                await emit(f"Decompiled: {pkg_name}")
            else:
                await emit(f"Decompile failed: {pkg_name} -- {result.get('error', 'unknown')}")

        if succeeded > 0:
            # Refresh inventory to pick up new decompiled components
            await _refresh_inventory(job_id)
            await emit(f"Auto-decompile complete: {succeeded}/{len(needs)} succeeded")

    except Exception as e:
        await emit(f"Auto-decompile error: {e} -- continuing with existing sources")


async def _run_process(job_id: str, task_id: str, mode: str) -> None:
    """Resolve mode (if needed), build prompt, and run the subprocess.

    When *mode* is ``"review"``, resolves to ``patch_review`` or
    ``verification`` by checking for local patches / fetching from ClickUp
    Doc.  Each resolution step emits a WebSocket progress event so the
    frontend can show real-time feedback.

    Uses ``subprocess.Popen`` with ``run_in_executor`` for reliable
    cross-platform support (asyncio subprocess can be unreliable on
    Windows inside uvicorn's event loop).
    """
    job = _jobs[job_id]
    loop = asyncio.get_running_loop()
    try:
        task_dir = TASKS_DIR / task_id

        # --- Resolve review meta-mode ---
        if mode == "review":
            mode = await _resolve_review_mode(job_id, task_id, task_dir)
            job["mode"] = mode
            await manager.broadcast({
                "type": "mode_resolved",
                "job_id": job_id,
                "resolved_mode": mode,
            })

        # --- Refresh package inventory before analysis ---
        await _refresh_inventory(job_id)

        # --- Auto-decompile packages that need it ---
        await _auto_decompile(job_id)

        # --- Build prompt and command ---
        prompt = _build_prompt(task_id, mode, task_dir)

        # Generate session ID for later --resume support
        session_id = str(uuid.uuid4())
        job["session_id"] = session_id

        allowed_tools = [
            "Read", "Glob", "Grep", "Bash", "Write", "Edit", "Task",
            "SendMessage", "TeamCreate", "TeamDelete",
            "TaskCreate", "TaskList", "TaskGet", "TaskUpdate",
        ]

        # Prepare log file for crash-resilient output preservation
        JOB_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_file_path = JOB_LOGS_DIR / f"{job_id}.log"

        # Start process via LLM backend
        llm = get_llm_backend()
        process, session_id = await llm.run_prompt(
            prompt,
            session_id=session_id,
            allowed_tools=allowed_tools,
            cwd=str(ROOT_DIR),
        )
        _processes[job_id] = process

        # Read stdout line-by-line with timeout-based heartbeat.
        # When subagents are running, the parent process is alive but
        # stdout is silent.  We emit heartbeat events every 30s so the
        # UI knows the process is still working.
        #
        # Post-result deadline: after the "result" event is received,
        # we give the process up to POST_RESULT_TIMEOUT seconds to
        # exit gracefully before force-terminating it.
        assert process.stdout is not None
        log_fh = open(log_file_path, "a", encoding="utf-8")
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        result_received_at: datetime | None = None
        result_subtype: str | None = None
        POST_RESULT_TIMEOUT = 20 * 60  # 20 minutes
        try:
            while True:
                try:
                    raw_line = await asyncio.wait_for(
                        loop.run_in_executor(executor, process.stdout.readline),
                        timeout=30.0,
                    )
                except asyncio.TimeoutError:
                    # 30s without output -- check if process is still alive
                    if process.poll() is not None:
                        break  # process exited

                    now = datetime.now()

                    # Post-result deadline check: force-terminate if
                    # the process hasn't exited within POST_RESULT_TIMEOUT
                    # after the result event was received.
                    if result_received_at is not None:
                        post_elapsed = (now - result_received_at).total_seconds()
                        if post_elapsed >= POST_RESULT_TIMEOUT:
                            detail = (
                                f"Force-terminating: process still running "
                                f"{int(post_elapsed)}s after result event"
                            )
                            kill_event = {
                                "event": "text",
                                "detail": detail,
                                "timestamp": now.isoformat(),
                            }
                            job["progress_events"].append(kill_event)
                            await manager.broadcast(
                                {"type": "progress", "job_id": job_id, **kill_event}
                            )
                            process.terminate()
                            try:
                                await asyncio.wait_for(
                                    loop.run_in_executor(None, process.wait),
                                    timeout=5.0,
                                )
                            except asyncio.TimeoutError:
                                process.kill()
                            break

                    # Emit heartbeat
                    elapsed = int((now - datetime.fromisoformat(job["started_at"])).total_seconds())
                    elapsed_str = f"{elapsed // 60}m {elapsed % 60}s"
                    if result_received_at is not None:
                        post_elapsed = int((now - result_received_at).total_seconds())
                        # Post-result: process cleanup phase.
                        # Only broadcast as "cleanup" -- do NOT append to
                        # progress_events so the timeline stays clean.
                        hb_event = {
                            "event": "cleanup",
                            "detail": f"Process cleanup... ({post_elapsed}s)",
                            "timestamp": now.isoformat(),
                        }
                        await manager.broadcast(
                            {"type": "progress", "job_id": job_id, **hb_event}
                        )
                    else:
                        hb_detail = f"Subagents still working... ({elapsed_str})"
                        hb_event = {
                            "event": "heartbeat",
                            "detail": hb_detail,
                            "timestamp": now.isoformat(),
                        }
                        job["progress_events"].append(hb_event)
                        await manager.broadcast(
                            {"type": "progress", "job_id": job_id, **hb_event}
                        )
                    continue

                if not raw_line:
                    break
                decoded = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                job["output_lines"].append(decoded)

                # Persist to disk immediately
                log_fh.write(decoded + "\n")
                log_fh.flush()

                await manager.broadcast(
                    {"type": "output", "job_id": job_id, "line": decoded}
                )

                # Parse stream-json events for structured progress
                for progress in parse_stream_events(decoded):
                    progress["timestamp"] = datetime.now().isoformat()
                    job["progress_events"].append(progress)
                    await manager.broadcast(
                        {"type": "progress", "job_id": job_id, **progress}
                    )
                    # Track result event for post-result deadline
                    if progress.get("event") == "result" and result_received_at is None:
                        result_received_at = datetime.now()
                        result_subtype = progress.get("subtype", "")
        finally:
            log_fh.close()
            executor.shutdown(wait=True, cancel_futures=True)

        exit_code = await loop.run_in_executor(None, process.wait)
        job["exit_code"] = exit_code

        # Determine status -- cancel flag takes priority, then result event
        if job_id in _cancelled_jobs:
            job["status"] = "cancelled"
            _cancelled_jobs.discard(job_id)
        elif result_received_at is not None:
            # Result was received -- trust the result event over exit code
            # (exit code may be non-zero due to force-termination)
            if result_subtype == "error":
                job["status"] = "failed"
            else:
                job["status"] = "completed"
            if exit_code != 0:
                job["exit_reason"] = (
                    f"Force-terminated after result "
                    f"(original exit: {_interpret_exit_code(exit_code)})"
                )
        else:
            job["status"] = "completed" if exit_code == 0 else "failed"
            # Interpret exit code for human readability
            if exit_code is not None and exit_code != 0:
                job["exit_reason"] = _interpret_exit_code(exit_code)

    except asyncio.CancelledError:
        job["status"] = "cancelled"
    except Exception as e:
        job["status"] = "failed"
        job["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
    finally:
        job["finished_at"] = datetime.now().isoformat()
        _processes.pop(job_id, None)

        await manager.broadcast({"type": "job_finished", "job": job})

        append_history(job)

        # Auto-retry for retryable failures (not user-cancelled)
        if (
            job["status"] == "failed"
            and job["exit_code"] is not None
            and _is_retryable(job["exit_code"])
            and job.get("retry_count", 0) < 1
        ):
            await manager.broadcast({
                "type": "progress", "job_id": job_id,
                "event": "text",
                "detail": f"Analysis interrupted ({job.get('exit_reason', '')}). Auto-retrying...",
                "timestamp": datetime.now().isoformat(),
            })
            await asyncio.sleep(3)
            retry_job = await start_analysis(task_id, mode)
            if retry_job.get("status") != "error":
                job["retry_job_id"] = retry_job["id"]
                retry_job_obj = _jobs.get(retry_job["id"])
                if retry_job_obj:
                    retry_job_obj["retry_count"] = job.get("retry_count", 0) + 1
