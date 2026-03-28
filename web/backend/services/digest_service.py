"""Digest generation service.

Collects tasks by date range, extracts report summaries,
calls Claude CLI to classify and generate a formatted digest,
then saves the result to digests/ directory.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from ..config import ROOT_DIR, TASKS_DIR, LOGS_DIR
from ..ws.manager import manager
from .claude_subprocess import parse_stream_events
from .llm import get_llm_backend

logger = logging.getLogger(__name__)

DIGESTS_DIR = ROOT_DIR / "digests"
HISTORY_FILE = DIGESTS_DIR / "digest_history.json"
JOB_LOGS_DIR = LOGS_DIR / "jobs"

# In-memory job tracking (similar to analysis job_manager)
_digest_jobs: dict[str, dict] = {}
_digest_processes: dict[str, subprocess.Popen] = {}


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def _load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_history(entries: list[dict]) -> None:
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_digests() -> list[dict]:
    """Return all digest history entries, newest first."""
    entries = _load_history()
    entries.sort(key=lambda e: e.get("generated_at", ""), reverse=True)
    return entries


def get_digest(digest_id: str) -> dict | None:
    """Get a single digest: metadata + markdown content."""
    history = _load_history()
    meta = next((e for e in history if e["id"] == digest_id), None)
    if not meta:
        return None

    md_path = DIGESTS_DIR / f"{digest_id}.md"
    content = md_path.read_text(encoding="utf-8") if md_path.exists() else ""

    return {**meta, "content": content}


def update_digest(digest_id: str, content: str) -> dict | None:
    """Update digest markdown content (edit feature)."""
    history = _load_history()
    meta = next((e for e in history if e["id"] == digest_id), None)
    if not meta:
        return None

    md_path = DIGESTS_DIR / f"{digest_id}.md"
    md_path.write_text(content, encoding="utf-8")

    meta["edited"] = True
    meta["edited_at"] = datetime.now().isoformat()
    _save_history(history)

    return {**meta, "content": content}


def get_digest_jobs() -> list[dict]:
    """Return all in-memory digest jobs (running + recently completed)."""
    return list(_digest_jobs.values())


def get_digest_job(job_id: str) -> dict | None:
    """Get current state of a digest generation job."""
    return _digest_jobs.get(job_id)


def delete_digest(digest_id: str) -> bool:
    """Delete a digest from history and remove its markdown file."""
    history = _load_history()
    original_len = len(history)
    history = [e for e in history if e["id"] != digest_id]
    if len(history) == original_len:
        return False

    _save_history(history)

    md_path = DIGESTS_DIR / f"{digest_id}.md"
    if md_path.exists():
        md_path.unlink()

    return True


async def cancel_digest(job_id: str) -> bool:
    """Cancel a running digest generation job."""
    process = _digest_processes.get(job_id)
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

    job = _digest_jobs.get(job_id)
    if job:
        job["status"] = "cancelled"
        job["finished_at"] = datetime.now().isoformat()
        await manager.broadcast({"type": "digest_completed", "job": job})

    _digest_processes.pop(job_id, None)
    return True


async def generate_digest(date_from: str, date_to: str) -> dict:
    """Start digest generation as an async background job.

    Returns the job dict immediately with status='running'.
    """
    llm = get_llm_backend()
    if not llm.is_available():
        return {
            "status": "error",
            "message": "claude CLI not found in PATH. Install Claude Code first.",
        }

    job_id = str(uuid.uuid4())[:8]
    job: dict = {
        "id": job_id,
        "type": "digest",
        "status": "running",
        "date_from": date_from,
        "date_to": date_to,
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
        "output_lines": [],
        "progress_events": [],
        "exit_code": None,
        "error": None,
        "digest_id": None,
    }
    _digest_jobs[job_id] = job

    await manager.broadcast({"type": "digest_started", "job": job})

    asyncio.create_task(_run_digest(job_id, date_from, date_to))
    return job


# ---------------------------------------------------------------------------
# Internal: digest generation subprocess
# ---------------------------------------------------------------------------

async def _run_digest(job_id: str, date_from: str, date_to: str) -> None:
    job = _digest_jobs[job_id]
    loop = asyncio.get_running_loop()

    try:
        # --- Step 1: Collect tasks ---
        await _emit(job_id, f"Collecting tasks from {date_from} to {date_to}...")

        from issuebot.digest import collect_digest_tasks
        tasks = await loop.run_in_executor(
            None, lambda: collect_digest_tasks(date_from, date_to)
        )

        if not tasks:
            job["status"] = "failed"
            job["error"] = "No tasks found in the specified date range."
            return

        tasks_with_report = sum(1 for t in tasks if t.get("has_report"))
        await _emit(job_id, f"Found {len(tasks)} tasks ({tasks_with_report} with reports). Building prompt...")

        # --- Step 2: Build prompt ---
        prompt = _build_digest_prompt(tasks, date_from, date_to)
        prompt_kb = len(prompt.encode("utf-8")) // 1024
        await _emit(job_id, f"Prompt built: {prompt_kb} KB. Sending to Claude...")

        # --- Step 3: Call Claude CLI ---
        session_id = str(uuid.uuid4())
        llm = get_llm_backend()

        # Digest generation: pure text output, no tools needed.
        # Use stdin to pipe the prompt because it can be very large
        # (100+ tasks × 2KB each) and would exceed Windows command-line
        # length limits (~32KB) if passed via -p argument.
        # Use --include-partial-messages for real-time streaming
        # (thinking + text deltas visible in UI like Jobs tab).
        process, _ = await llm.run_prompt(
            prompt,
            session_id=session_id,
            cwd=str(ROOT_DIR),
            system_prompt=(
                "당신은 이슈 다이제스트를 작성하는 QA 엔지니어입니다. "
                "도구를 사용하지 마세요. 마크다운 형식의 다이제스트만 출력하세요."
            ),
            use_stdin=True,
            include_partial=True,
        )

        _digest_processes[job_id] = process
        await _emit(job_id, "Claude is generating (streaming enabled)...")

        # --- Step 4: Stream output ---
        JOB_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = JOB_LOGS_DIR / f"digest_{job_id}.log"

        assert process.stdout is not None
        log_fh = open(log_path, "a", encoding="utf-8")
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        collected_text: list[str] = []
        result_text: str = ""  # Fallback from result event
        thinking_buf: list[str] = []  # Buffer for batching thinking updates
        thinking_total = 0  # Total thinking chars received
        last_thinking_broadcast = 0  # Chars at last broadcast

        try:
            while True:
                try:
                    raw_line = await asyncio.wait_for(
                        loop.run_in_executor(executor, process.stdout.readline),
                        timeout=30.0,
                    )
                except asyncio.TimeoutError:
                    if process.poll() is not None:
                        break
                    elapsed = int(
                        (datetime.now() - datetime.fromisoformat(job["started_at"])).total_seconds()
                    )
                    await _emit(job_id, f"Generating... ({elapsed}s)", "heartbeat")
                    continue

                if not raw_line:
                    break

                decoded = raw_line.decode("utf-8", errors="replace").rstrip("\n\r")
                job["output_lines"].append(decoded)
                log_fh.write(decoded + "\n")
                log_fh.flush()

                # Parse stream events (tool_use, text, result)
                for progress in parse_stream_events(decoded):
                    progress["timestamp"] = datetime.now().isoformat()
                    job["progress_events"].append(progress)
                    await manager.broadcast(
                        {"type": "digest_progress", "job_id": job_id, **progress}
                    )

                try:
                    event = json.loads(decoded)
                    etype = event.get("type")

                    # Extract from assistant events (complete message)
                    if etype == "assistant":
                        for item in event.get("message", {}).get("content", []):
                            if item.get("type") == "text":
                                collected_text.append(item.get("text", ""))

                    # Extract from stream_event (real-time partial messages)
                    elif etype == "stream_event":
                        inner = event.get("event", {})
                        inner_type = inner.get("type")
                        if inner_type == "content_block_delta":
                            delta = inner.get("delta", {})
                            delta_type = delta.get("type")

                            if delta_type == "text_delta":
                                text_chunk = delta.get("text", "")
                                if text_chunk:
                                    collected_text.append(text_chunk)
                                    progress_evt = {
                                        "event": "text",
                                        "detail": text_chunk[:200],
                                        "timestamp": datetime.now().isoformat(),
                                    }
                                    job["progress_events"].append(progress_evt)
                                    await manager.broadcast(
                                        {"type": "digest_progress", "job_id": job_id, **progress_evt}
                                    )

                            elif delta_type == "thinking_delta":
                                thinking_chunk = delta.get("thinking", "")
                                if thinking_chunk:
                                    thinking_buf.append(thinking_chunk)
                                    thinking_total += len(thinking_chunk)
                                    # Broadcast every ~500 chars to avoid flooding
                                    if thinking_total - last_thinking_broadcast >= 500:
                                        snippet = "".join(thinking_buf)[-200:]
                                        progress_evt = {
                                            "event": "thinking",
                                            "detail": snippet,
                                            "timestamp": datetime.now().isoformat(),
                                        }
                                        job["progress_events"].append(progress_evt)
                                        await manager.broadcast(
                                            {"type": "digest_progress", "job_id": job_id, **progress_evt}
                                        )
                                        thinking_buf.clear()
                                        last_thinking_broadcast = thinking_total

                    # Capture result text as fallback
                    elif etype == "result":
                        r = event.get("result", "")
                        if isinstance(r, str) and r:
                            result_text = r

                except (json.JSONDecodeError, ValueError):
                    pass

        finally:
            log_fh.close()
            executor.shutdown(wait=True, cancel_futures=True)

        exit_code = await loop.run_in_executor(None, process.wait)
        job["exit_code"] = exit_code

        # --- Step 5: Save digest ---
        digest_text = "".join(collected_text).strip()

        # Fallback: use result event text if streaming extraction missed it
        if not digest_text and result_text:
            digest_text = result_text.strip()

        if not digest_text:
            job["status"] = "failed"
            job["error"] = "Claude returned empty output."
            return

        # Generate digest ID
        from datetime import date as date_cls
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d").date()
            iso_cal = d.isocalendar()
            digest_id = f"{iso_cal.year}-W{iso_cal.week:02d}"
        except ValueError:
            digest_id = f"digest-{job_id}"

        # Prevent duplicate IDs
        history = _load_history()
        if any(e["id"] == digest_id for e in history):
            digest_id = f"{digest_id}-{job_id[:4]}"

        # Save markdown
        DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
        md_path = DIGESTS_DIR / f"{digest_id}.md"
        md_path.write_text(digest_text, encoding="utf-8")

        # Parse severity counts from generated text
        severity_counts = _parse_severity_counts(digest_text)

        # Save to history
        entry = {
            "id": digest_id,
            "date_from": date_from,
            "date_to": date_to,
            "generated_at": datetime.now().isoformat(),
            "task_count": len(tasks),
            "severity_counts": severity_counts,
            "edited": False,
            "job_id": job_id,
        }
        history.append(entry)
        _save_history(history)

        job["digest_id"] = digest_id
        job["status"] = "completed"

        await _emit(job_id, f"Digest saved: {digest_id} ({len(tasks)} tasks)")

    except Exception as e:
        import traceback
        job["status"] = "failed"
        job["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
    finally:
        job["finished_at"] = datetime.now().isoformat()
        _digest_processes.pop(job_id, None)
        # Clean up temp stdin file
        llm = get_llm_backend()
        if hasattr(llm, "cleanup_stdin_tmp"):
            llm.cleanup_stdin_tmp()
        await manager.broadcast({"type": "digest_completed", "job": job})

        # Prune old jobs from memory (keep 10)
        completed = [
            jid for jid, j in _digest_jobs.items()
            if j["status"] in ("completed", "failed")
        ]
        for old_id in completed[:-10]:
            _digest_jobs.pop(old_id, None)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_digest_prompt(tasks: list[dict], date_from: str, date_to: str) -> str:
    """Build the full prompt for digest generation."""
    header = f"""아래는 {date_from} ~ {date_to} 기간에 등록된 InterMax 지원 이슈 {len(tasks)}건의 요약 데이터입니다.

이 데이터를 바탕으로 **이슈 다이제스트**를 작성하세요.

## 분류 기준

각 이슈를 아래 5등급으로 분류하세요:

| 등급 | 기준 |
|------|------|
| **Critical** | 시스템 장애, 데이터 유실, 보안 취약점, 다수 고객 영향 가능, 우회 불가 |
| **High** | 주요 기능 장애, 우회 어려움, 운영 환경에 직접 영향 |
| **Medium** | 기능 일부 제한, 우회 가능, 특정 환경/설정 한정 |
| **Low** | 경미한 UI/UX 이슈, 사용성 불편 |
| **Info** | 단순 문의, 사양 확인, 이미 해결됨, 설정 안내 |

**판단 근거**: report 요약 내용, 이슈 유형, 영향 범위, 현재 상태를 종합적으로 고려

## 출력 형식

다음 형식의 마크다운을 출력하세요. 다른 텍스트는 출력하지 마세요.

```
# 이슈 다이제스트 — {date_from} ~ {date_to}

> 등록 이슈: N건 | Critical: N | High: N | Medium: N | Low: N | Info: N

<details>
<summary>등급 분류 기준</summary>

| 등급 | 기준 |
|------|------|
| **Critical** | 시스템 장애, 데이터 유실, 보안 취약점, 다수 고객 영향, 우회 불가 |
| **High** | 주요 기능 장애, 우회 어려움, 운영 환경 직접 영향 |
| **Medium** | 기능 일부 제한, 우회 가능, 특정 환경/설정 한정 |
| **Low** | 경미한 UI/UX 이슈, 사용성 불편 |
| **Info** | 단순 문의, 사양 확인, 이미 해결됨, 설정 안내 |

</details>

---

## 🔴 Critical (N건)

### [IMX-XXXX](ClickUp URL) — 이슈 제목
- **관련 버전**: (report에서 관련 컴포넌트 버전만 추출)
- **요약**: (2-3문장 요약)
- **상태**: (현재 상태)
- **태그**: (있으면)

---

## 🟠 High (N건)

(Critical과 동일 형식)

---

## 🟡 Medium (N건)

(테이블 형식으로 간략화)
| 이슈 | 관련 버전 | 요약 | 상태 |
|------|----------|------|------|

---

## 🟢 Low / ℹ️ Info (N건)

| 이슈 | 유형 | 요약 |
|------|------|------|
```

## 주의사항

- 모든 이슈 ID에 ClickUp 링크를 걸어주세요: `[IMX-XXXX](url)`
- **관련 버전**: report 내용을 보고 이 이슈와 실제로 관련된 컴포넌트 버전만 표시. UI 버그라면 PlatformJS만, 수집 이슈라면 DataGather만.
- report가 없는 이슈는 태스크 제목과 설명으로 판단하세요.
- 이슈가 0건인 등급은 섹션을 생략하세요.
- 한국어로 작성하세요.

---

## 이슈 데이터

"""

    # Build per-task data blocks
    task_blocks: list[str] = []
    for t in tasks:
        block_parts = [
            f"### {t['id']}: {t['name']}",
            f"- URL: {t['url']}",
            f"- 상태: {t['status']}",
            f"- 생성일: {t.get('date_created', 'N/A')}",
        ]

        if t.get("tags"):
            block_parts.append(f"- 태그: {', '.join(t['tags'])}")

        # Version fields from custom_fields
        cf = t.get("custom_fields", {})
        version_parts = []
        for key, val in cf.items():
            if "version" in key.lower() and val:
                version_parts.append(f"  - {key}: {val}")
        if version_parts:
            block_parts.append("- 버전 정보:")
            block_parts.extend(version_parts)

        # Report summary
        rs = t.get("report_summary")
        if rs:
            task_type = rs.get("_task_type", "unknown")
            block_parts.append(f"- 분석 유형: {task_type}")
            for key, val in rs.items():
                if key.startswith("_"):
                    continue
                # Truncate very long sections
                if len(val) > 800:
                    val = val[:800] + "..."
                block_parts.append(f"- [{key}]:\n{val}")
        else:
            block_parts.append("- (report 없음 — 제목/설명으로 판단)")

        task_blocks.append("\n".join(block_parts))

    return header + "\n\n---\n\n".join(task_blocks)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_severity_counts(text: str) -> dict[str, int]:
    """Parse severity counts from the generated digest header line."""
    counts: dict[str, int] = {}
    # Match pattern: "Critical: 2"
    for m in __import__("re").finditer(r"(Critical|High|Medium|Low|Info):\s*(\d+)", text):
        counts[m.group(1).lower()] = int(m.group(2))
    return counts


async def _emit(job_id: str, detail: str, event_type: str = "text") -> None:
    """Emit a progress event for the digest job."""
    if job_id not in _digest_jobs:
        return
    event = {
        "event": event_type,
        "detail": detail,
        "timestamp": datetime.now().isoformat(),
    }
    _digest_jobs[job_id]["progress_events"].append(event)
    await manager.broadcast(
        {"type": "digest_progress", "job_id": job_id, **event}
    )
