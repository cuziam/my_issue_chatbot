"""Service layer for managing Claude analysis subprocess jobs.

Jobs are stored in-memory while running and persisted to analysis_history.jsonl
upon completion.  Real-time output is streamed to WebSocket clients via the
shared ConnectionManager.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import ROOT_DIR, TASKS_DIR, LOGS_DIR, ISSUEBOT_DIR, PACKAGES_DIR
from ..ws.manager import manager

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
_jobs: dict[str, dict] = {}
_processes: dict[str, subprocess.Popen] = {}

HISTORY_FILE = LOGS_DIR / "analysis_history.jsonl"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_jobs() -> list[dict]:
    """Return all in-memory jobs (running + recently finished)."""
    return list(_jobs.values())


def get_job(job_id: str) -> Optional[dict]:
    """Return a single job by ID, or None."""
    return _jobs.get(job_id)


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

    if not shutil.which("claude"):
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
        "error": None,
    }
    _jobs[job_id] = job

    # Notify connected clients
    await manager.broadcast({"type": "job_started", "job": job})

    # Fire-and-forget the subprocess task
    asyncio.create_task(_run_process(job_id, task_id, mode))

    return job


async def cancel_job(job_id: str) -> bool:
    """Cancel a running analysis job. Returns True if cancellation was issued."""
    process = _processes.get(job_id)
    if not process:
        return False

    process.terminate()
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, process.wait), timeout=5
        )
    except asyncio.TimeoutError:
        process.kill()

    job = _jobs.get(job_id)
    if job:
        job["status"] = "cancelled"
        job["finished_at"] = datetime.now().isoformat()

    return True


def get_history() -> list[dict]:
    """Read all entries from analysis_history.jsonl."""
    if not HISTORY_FILE.exists():
        return []
    entries: list[dict] = []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_env() -> dict[str, str]:
    """Return a copy of os.environ with ALL Claude Code env vars removed.

    Claude CLI refuses to start inside another Claude Code session.
    Multiple env vars are set (CLAUDECODE, CLAUDE_CODE_ENTRYPOINT, etc.)
    and ALL of them must be removed.
    """
    env = os.environ.copy()
    for key in list(env):
        if key.upper().startswith("CLAUDE"):
            del env[key]
    return env


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


# Constants for patch detection (mirrors scheduler.py)
_PATCH_STANDARD_FILES = {
    "task.json", "report.md", "context.md",
    "patch_diff.md", "patch_diff.json", "patch_review.md",
}
_PATCH_STANDARD_DIRS = {"images", ".patch_temp"}
_PATCH_SOURCE_EXTENSIONS = {
    ".js", ".java", ".xml", ".json", ".properties",
    ".conf", ".css", ".html", ".jsp", ".sql",
}


def _detect_local_patches(task_dir: Path) -> bool:
    """Check if a task directory contains patch files.

    Mirrors ``scheduler.detect_patch_presence``: looks for non-standard
    files/dirs in the task root and in ``patches/``.
    """
    if not task_dir.exists():
        return False

    # Check patches/ directory first (created by fetch_doc.py)
    patches_dir = task_dir / "patches"
    if patches_dir.exists() and patches_dir.is_dir():
        for item in patches_dir.iterdir():
            if item.name == "doc_content.md":
                continue
            return True

    for item in task_dir.iterdir():
        name = item.name
        if name in _PATCH_STANDARD_FILES:
            continue
        if name in _PATCH_STANDARD_DIRS:
            continue
        if name == "patches":
            continue  # Already checked above
        if item.is_dir():
            return True
        ext = item.suffix.lower()
        if ext in _PATCH_SOURCE_EXTENSIONS or ext in (".zip", ".jar", ".tar", ".gz"):
            return True

    return False


async def _refresh_inventory(job_id: str) -> None:
    """Regenerate packages/inventory.json before analysis.

    Ensures the researcher agent sees all available packages (including
    recently added ones).  Runs inventory.py as an import to avoid
    spawning a subprocess.
    """
    import sys

    async def _emit(detail: str) -> None:
        event = {
            "event": "text",
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        }
        _jobs[job_id]["progress_events"].append(event)
        await manager.broadcast({"type": "progress", "job_id": job_id, **event})

    try:
        # Import inventory.py from issuebot/
        if str(ISSUEBOT_DIR) not in sys.path:
            sys.path.insert(0, str(ISSUEBOT_DIR))
        from inventory import generate_inventory  # type: ignore[import-untyped]

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
        await _emit(msg)
    except Exception as e:
        await _emit(f"Inventory refresh failed: {e} — continuing with existing inventory")


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
    from . import patch_service  # lazy to avoid circular imports

    async def _emit(detail: str) -> None:
        event = {
            "event": "text",
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        }
        _jobs[job_id]["progress_events"].append(event)
        await manager.broadcast({"type": "progress", "job_id": job_id, **event})

    # Step 1: Check local patches
    await _emit("Checking local patches...")
    has_patches = await asyncio.to_thread(_detect_local_patches, task_dir)

    # Step 2: If no local patches, try fetching from ClickUp Doc
    if not has_patches:
        await _emit("Fetching from ClickUp Doc...")
        try:
            result = await patch_service.fetch_doc_patches(task_id)
            if result.get("status") == "ok" and result.get("files"):
                has_patches = await asyncio.to_thread(
                    _detect_local_patches, task_dir
                )
                if has_patches:
                    await _emit(
                        f"Downloaded {len(result['files'])} patch files from Doc"
                    )
                else:
                    await _emit("Doc fetch completed but no patch files found")
            else:
                await _emit("No patch files in ClickUp Doc")
        except Exception as e:
            await _emit(f"Doc fetch failed: {e} — falling back to verification")
            return "verification"

    # Step 3: Generate diff if patches exist
    if has_patches:
        await _emit("Generating patch diff...")
        try:
            diff_result = await patch_service.generate_diff(task_id)
            file_count = diff_result.get("file_count", 0)
            await _emit(f"Patch diff generated ({file_count} files)")
        except Exception as e:
            await _emit(f"Diff generation failed: {e} — proceeding with patch review")
        resolved = "patch_review"
    else:
        # Step 4: Try version diff (compare old vs new package)
        version_diff_result = await _try_version_diff(job_id, task_id, task_dir)
        if version_diff_result:
            resolved = "patch_review"
        else:
            resolved = "verification"

    await _emit(f"Mode resolved: QA Review → {resolved.replace('_', ' ').title()}")
    return resolved


async def _try_version_diff(
    job_id: str, task_id: str, task_dir: Path
) -> Optional[dict]:
    """Try generating a version diff between old and new packages.

    When no explicit patches are found, checks if a newer package version
    exists and generates patch_diff.md/json from the version comparison.
    """
    import sys

    async def _emit(detail: str) -> None:
        event = {
            "event": "text",
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        }
        _jobs[job_id]["progress_events"].append(event)
        await manager.broadcast({"type": "progress", "job_id": job_id, **event})

    try:
        await _emit("Checking for newer package version...")

        if str(ISSUEBOT_DIR) not in sys.path:
            sys.path.insert(0, str(ISSUEBOT_DIR))
        from version_diff import generate_version_diff  # type: ignore[import-untyped]

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, generate_version_diff, task_id)

        if result:
            await _emit(
                f"Version diff generated: {result['old_pkg']} → "
                f"{result['new_pkg']} ({result['file_count']} files)"
            )
            return result
        else:
            await _emit("No newer package version found — using verification mode")
            return None
    except Exception as e:
        await _emit(f"Version diff failed: {e} — falling back to verification")
        return None


async def _auto_decompile(job_id: str) -> None:
    """Auto-decompile packages with needs_decompile=True.

    Reads inventory.json for packages needing decompilation, runs the
    decompile script, then refreshes inventory to update components.
    """
    import sys

    async def _emit(detail: str) -> None:
        event = {
            "event": "text",
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        }
        _jobs[job_id]["progress_events"].append(event)
        await manager.broadcast({"type": "progress", "job_id": job_id, **event})

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

        await _emit(f"Auto-decompiling {len(needs)} package(s)...")

        if str(ISSUEBOT_DIR) not in sys.path:
            sys.path.insert(0, str(ISSUEBOT_DIR))
        from decompile_runner import run_decompile  # type: ignore[import-untyped]

        loop = asyncio.get_running_loop()
        succeeded = 0
        for pkg in needs:
            pkg_name = pkg["name"]
            await _emit(f"Decompiling: {pkg_name}")
            result = await loop.run_in_executor(None, run_decompile, pkg_name)
            if result["success"]:
                succeeded += 1
                await _emit(f"Decompiled: {pkg_name}")
            else:
                await _emit(f"Decompile failed: {pkg_name} — {result.get('error', 'unknown')}")

        if succeeded > 0:
            # Refresh inventory to pick up new decompiled components
            await _refresh_inventory(job_id)
            await _emit(f"Auto-decompile complete: {succeeded}/{len(needs)} succeeded")

    except Exception as e:
        await _emit(f"Auto-decompile error: {e} — continuing with existing sources")


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
        cmd = [
            "claude",
            "-p",
            prompt,
            "--verbose",
            "--output-format", "stream-json",
            "--allowedTools",
            (
                "Read,Glob,Grep,Bash,Write,Edit,Task,SendMessage,"
                "TeamCreate,TeamDelete,TaskCreate,TaskList,TaskGet,TaskUpdate"
            ),
        ]

        env = _clean_env()

        # Start process (blocking call, run in executor)
        process = await loop.run_in_executor(
            None,
            lambda: subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(ROOT_DIR),
                env=env,
            ),
        )
        _processes[job_id] = process

        # Read stdout line-by-line in executor to avoid blocking the loop
        assert process.stdout is not None
        while True:
            raw_line = await loop.run_in_executor(None, process.stdout.readline)
            if not raw_line:
                break
            decoded = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
            job["output_lines"].append(decoded)
            await manager.broadcast(
                {"type": "output", "job_id": job_id, "line": decoded}
            )

            # Parse stream-json events for structured progress
            for progress in _parse_stream_events(decoded):
                progress["timestamp"] = datetime.now().isoformat()
                job["progress_events"].append(progress)
                await manager.broadcast(
                    {"type": "progress", "job_id": job_id, **progress}
                )

        exit_code = await loop.run_in_executor(None, process.wait)
        job["exit_code"] = exit_code
        job["status"] = "completed" if exit_code == 0 else "failed"

    except asyncio.CancelledError:
        job["status"] = "cancelled"
    except Exception as e:
        job["status"] = "failed"
        job["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
    finally:
        job["finished_at"] = datetime.now().isoformat()
        _processes.pop(job_id, None)

        await manager.broadcast({"type": "job_finished", "job": job})

        _append_history(job)


def _parse_stream_events(line: str) -> list[dict]:
    """Parse a ``stream-json`` line into human-readable progress events."""
    try:
        event = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return []

    results: list[dict] = []
    etype = event.get("type")

    if etype == "assistant":
        content_items = event.get("message", {}).get("content", [])
        for item in content_items:
            kind = item.get("type")
            if kind == "tool_use":
                tool = item.get("name", "")
                detail = _summarize_tool_input(tool, item.get("input", {}))
                results.append({"event": "tool_use", "tool": tool, "detail": detail})
            elif kind == "text":
                text = item.get("text", "").strip()
                if text:
                    results.append({"event": "text", "detail": text[:200]})

    elif etype == "result":
        results.append({
            "event": "result",
            "subtype": event.get("subtype", ""),
            "duration_ms": event.get("duration_ms"),
            "num_turns": event.get("num_turns"),
            "cost_usd": event.get("cost_usd"),
        })

    return results


def _summarize_tool_input(tool: str, inp: dict) -> str:
    """Return a short human-readable summary of a tool invocation."""
    if tool in ("Read", "Write", "Edit"):
        return inp.get("file_path", "")
    if tool == "Glob":
        return inp.get("pattern", "")
    if tool == "Grep":
        pat = inp.get("pattern", "")
        path = inp.get("path", "")
        return f'"{pat}" in {path}' if path else f'"{pat}"'
    if tool == "Bash":
        return inp.get("command", "")[:100]
    if tool == "Task":
        desc = inp.get("description", "")
        name = inp.get("name", "")
        atype = inp.get("subagent_type", "")
        if name:
            return f"{name} ({atype}): {desc}"
        return f"{atype}: {desc}" if atype else desc
    if tool == "SendMessage":
        recipient = inp.get("recipient", "")
        summary = inp.get("summary", "")
        mtype = inp.get("type", "message")
        if mtype == "shutdown_request":
            return f"shutdown → {recipient}"
        return f"→ {recipient}: {summary}" if summary else f"→ {recipient}"
    if tool == "TeamCreate":
        return f"team: {inp.get('team_name', '')}"
    if tool == "TaskCreate":
        return inp.get("subject", "")
    if tool in ("TaskUpdate", "TaskGet"):
        return inp.get("taskId", "")
    return ""


def _append_history(job: dict) -> None:
    """Append a completed job summary to analysis_history.jsonl."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": job["id"],
        "task_id": job["task_id"],
        "mode": job["mode"],
        "status": job["status"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"],
        "exit_code": job["exit_code"],
        "output_line_count": len(job["output_lines"]),
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
