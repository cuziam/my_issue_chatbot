"""StreamingPool — manages long-lived ``claude -p --input-format stream-json`` processes.

Instead of spawning a new subprocess for every chat message, this module
maintains one persistent process per session_id.  Messages are written to
stdin as stream-json user events, and stdout is read as an async generator
until the ``result`` event signals the end of a turn.

Uses subprocess.Popen (synchronous) instead of asyncio.create_subprocess_exec
because the latter's ProactorEventLoop pipe handling fails on Windows —
readline() hangs indefinitely.  Blocking I/O is wrapped in run_in_executor.
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

from ..claude_subprocess import clean_env

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IDLE_TIMEOUT_SECONDS: int = 600
"""Seconds of inactivity before an idle process is reaped (10 min)."""

SESSION_SIZE_LIMIT: int = 500_000
"""Approximate session context size limit in bytes (500 KB).

Exported so that callers (e.g. chat_runner) can decide when to start a
new session rather than resuming an existing one.
"""

_INIT_TIMEOUT: float = 60.0
"""Seconds to wait for the init event after process creation."""

_TURN_TIMEOUT: float = 300.0
"""Seconds to wait for each stdout line during a turn (tool calls can be slow)."""

_CLEANUP_INTERVAL: float = 60.0
"""Seconds between cleanup sweeps."""


# ---------------------------------------------------------------------------
# Internal data
# ---------------------------------------------------------------------------

@dataclass
class _ProcessEntry:
    """Bookkeeping for a single long-lived claude process."""

    process: subprocess.Popen
    session_id: str
    busy: bool = False
    last_active: float = field(default_factory=time.monotonic)
    # Configuration params stored for respawn on BrokenPipeError
    allowed_tools: list[str] | None = None
    system_prompt: str = ""
    model: str = ""
    cwd: str = ""


# ---------------------------------------------------------------------------
# StreamingPool
# ---------------------------------------------------------------------------

class StreamingPool:
    """Pool of long-lived ``claude`` streaming processes keyed by session_id.

    Usage::

        pool = StreamingPool()
        pool.start_cleanup_loop()

        async for line in pool.send_and_stream(session_id, "Hello"):
            process_line(line)

        await pool.shutdown()
    """

    def __init__(self, claude_cmd: str = "claude") -> None:
        self._cmd: str = claude_cmd
        self._entries: dict[str, _ProcessEntry] = {}
        self._cleanup_task: asyncio.Task | None = None
        # Fix #1: Session-level locks that outlive entries
        self._session_locks: dict[str, asyncio.Lock] = {}
        # Fix #4: Proper initialization instead of lazy AttributeError hack
        self._known_sessions: set[str] = set()

    def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        """Return the session-level lock, creating one if needed."""
        if session_id not in self._session_locks:
            self._session_locks[session_id] = asyncio.Lock()
        return self._session_locks[session_id]

    # ------------------------------------------------------------------
    # Process creation
    # ------------------------------------------------------------------

    async def _spawn(
        self,
        session_id: str,
        *,
        resume: bool = False,
        allowed_tools: list[str] | None = None,
        system_prompt: str = "",
        model: str = "",
        cwd: str = "",
    ) -> _ProcessEntry:
        """Spawn a new ``claude`` streaming process and drain the init preamble."""

        cmd: list[str] = [
            self._cmd,
            "-p",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--verbose",
        ]

        if resume:
            cmd += ["--resume", session_id]
        else:
            cmd += ["--session-id", session_id]

        if allowed_tools:
            cmd += ["--allowedTools", ",".join(allowed_tools)]

        if system_prompt:
            cmd += ["--append-system-prompt", system_prompt]

        if model:
            cmd += ["--model", model]

        env = clean_env()

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=cwd or None,
            env=env,
        )

        entry = _ProcessEntry(
            process=process,
            session_id=session_id,
            allowed_tools=allowed_tools,
            system_prompt=system_prompt,
            model=model,
            cwd=cwd,
        )

        # Fix #2: Only insert into pool AFTER successful init drain
        try:
            await self._drain_until_init(entry)
        except Exception:
            # Init failed — kill the process and don't leave an orphan entry
            await self._kill_process(entry)
            raise

        self._entries[session_id] = entry
        entry.last_active = time.monotonic()
        return entry

    async def _drain_until_init(self, entry: _ProcessEntry) -> None:
        """Read and discard stdout lines until the ``system/init`` event."""

        assert entry.process.stdout is not None
        loop = asyncio.get_running_loop()
        while True:
            try:
                raw = await asyncio.wait_for(
                    loop.run_in_executor(None, entry.process.stdout.readline),
                    timeout=_INIT_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timeout waiting for init event (session %s) — killing",
                    entry.session_id,
                )
                raise RuntimeError(
                    f"Timeout waiting for init event on session {entry.session_id}"
                )

            if not raw:
                # EOF — process died before init
                rc = entry.process.returncode
                logger.warning(
                    "Process exited (rc=%s) before init (session %s)",
                    rc, entry.session_id,
                )
                raise RuntimeError(
                    f"Process died (rc={rc}) before init on session {entry.session_id}"
                )

            line = raw.decode("utf-8", errors="replace").rstrip("\n\r")
            if not line:
                continue

            try:
                event = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                # Non-JSON preamble line — discard.
                logger.debug("Pre-init non-JSON: %s", line[:200])
                continue

            if event.get("type") == "system" and event.get("subtype") == "init":
                logger.info(
                    "Init received for session %s (tools=%d)",
                    entry.session_id,
                    len(event.get("tools", [])),
                )
                return

            # Other JSON lines before init (e.g. hook events) — discard.
            logger.debug("Pre-init event: %s", event.get("type"))

    # ------------------------------------------------------------------
    # Public: send & stream
    # ------------------------------------------------------------------

    async def send_and_stream(
        self,
        session_id: str,
        message: str,
        *,
        allowed_tools: list[str] | None = None,
        system_prompt: str = "",
        model: str = "",
        cwd: str = "",
    ) -> AsyncIterator[str]:
        """Send *message* and yield raw stdout JSON lines until the result event.

        If no process exists for *session_id*, one is created.  If the
        existing process has died, it is re-created with ``--resume``.

        Yields each raw JSON line (without trailing newline) as received.
        The final line yielded is the ``result`` event.
        """

        # Fix #1: Use session-level lock that outlives entries
        session_lock = self._get_session_lock(session_id)

        async with session_lock:
            entry = await self._get_or_create(
                session_id,
                allowed_tools=allowed_tools,
                system_prompt=system_prompt,
                model=model,
                cwd=cwd,
            )

            entry.busy = True
            entry.last_active = time.monotonic()
            try:
                async for line in self._do_turn(entry, message):
                    yield line
            finally:
                # Entry may have been replaced by _do_turn on BrokenPipeError
                # retry, so look up the current entry for this session.
                current = self._entries.get(session_id, entry)
                current.busy = False
                current.last_active = time.monotonic()

    async def _get_or_create(
        self,
        session_id: str,
        *,
        allowed_tools: list[str] | None = None,
        system_prompt: str = "",
        model: str = "",
        cwd: str = "",
    ) -> _ProcessEntry:
        """Return the existing entry or spawn a new process.

        If the existing process has died, it is cleaned up and a new one
        is created with ``--resume`` so it picks up the conversation history.
        """

        entry = self._entries.get(session_id)
        was_known = session_id in self._known_sessions

        if entry is not None:
            # Check if still alive (poll() updates returncode).
            entry.process.poll()
            if entry.process.returncode is not None:
                logger.info(
                    "Process dead (rc=%s) for session %s — will recreate with --resume",
                    entry.process.returncode, session_id,
                )
                await self._cleanup_entry(entry)
                entry = None

        if entry is None:
            entry = await self._spawn(
                session_id,
                resume=was_known,
                allowed_tools=allowed_tools,
                system_prompt=system_prompt,
                model=model,
                cwd=cwd,
            )
            self._known_sessions.add(session_id)

        return entry

    async def _do_turn(
        self,
        entry: _ProcessEntry,
        message: str,
    ) -> AsyncIterator[str]:
        """Write a user message and yield stdout lines until result."""

        proc = entry.process
        assert proc.stdin is not None
        assert proc.stdout is not None

        # Build stream-json user event.
        user_event = json.dumps(
            {"type": "user", "message": {"role": "user", "content": message}},
            ensure_ascii=False,
        )
        payload = (user_event + "\n").encode("utf-8")

        loop = asyncio.get_running_loop()

        # Write to stdin — handle BrokenPipeError.
        def _write_stdin() -> None:
            proc.stdin.write(payload)
            proc.stdin.flush()

        try:
            await loop.run_in_executor(None, _write_stdin)
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            logger.warning(
                "Stdin write failed for session %s (%s) — retrying with --resume",
                entry.session_id, exc,
            )
            await self._kill_process(entry)
            await self._cleanup_entry(entry)

            # Fix #3: Pass stored config params through on respawn
            entry = await self._spawn(
                entry.session_id,
                resume=True,
                allowed_tools=entry.allowed_tools,
                system_prompt=entry.system_prompt,
                model=entry.model,
                cwd=entry.cwd,
            )
            self._known_sessions.add(entry.session_id)
            proc = entry.process
            assert proc.stdin is not None
            assert proc.stdout is not None

            def _write_stdin_retry() -> None:
                proc.stdin.write(payload)
                proc.stdin.flush()

            try:
                await loop.run_in_executor(None, _write_stdin_retry)
            except (BrokenPipeError, ConnectionResetError, OSError) as retry_exc:
                logger.error(
                    "Stdin write failed on retry for session %s (%s)",
                    entry.session_id, retry_exc,
                )
                await self._kill_process(entry)
                raise RuntimeError(
                    f"Cannot write to claude process for session {entry.session_id}"
                ) from retry_exc

        # Read stdout lines until the result event.
        while True:
            try:
                raw = await asyncio.wait_for(
                    loop.run_in_executor(None, proc.stdout.readline),
                    timeout=_TURN_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.error(
                    "Turn readline timeout (%ss) for session %s",
                    _TURN_TIMEOUT, entry.session_id,
                )
                # Fix #7: Kill process on turn timeout so next call gets clean --resume
                await self._kill_process(entry)
                await self._cleanup_entry(entry)
                raise RuntimeError(
                    f"Timeout reading from claude process for session {entry.session_id}"
                )

            if not raw:
                # EOF — process died mid-turn.
                rc = proc.returncode
                logger.warning(
                    "Process EOF mid-turn (rc=%s) for session %s",
                    rc, entry.session_id,
                )
                raise RuntimeError(
                    f"Process died (rc={rc}) mid-turn for session {entry.session_id}"
                )

            line = raw.decode("utf-8", errors="replace").rstrip("\n\r")
            if not line:
                continue

            yield line

            # Check if this is the result event.
            try:
                event = json.loads(line)
                if event.get("type") == "result":
                    return
            except (json.JSONDecodeError, ValueError):
                pass

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------

    def start_cleanup_loop(self) -> None:
        """Start the background cleanup task.  Safe to call multiple times."""
        if self._cleanup_task is not None and not self._cleanup_task.done():
            return
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Periodically reap idle and dead processes."""
        while True:
            try:
                await asyncio.sleep(_CLEANUP_INTERVAL)
                await self._sweep()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Error in cleanup sweep")

    async def _sweep(self) -> None:
        """One sweep: kill idle / remove dead entries."""
        now = time.monotonic()
        to_remove: list[str] = []

        for sid, entry in list(self._entries.items()):
            # Dead process — just clean up.
            entry.process.poll()
            if entry.process.returncode is not None:
                logger.info("Sweeping dead process for session %s", sid)
                to_remove.append(sid)
                continue

            # Fix #6: Also check if session lock is held (turn in progress)
            session_lock = self._session_locks.get(sid)
            if session_lock is not None and session_lock.locked():
                continue

            # Idle too long?
            if not entry.busy and (now - entry.last_active) > IDLE_TIMEOUT_SECONDS:
                logger.info(
                    "Killing idle process for session %s (idle %.0fs)",
                    sid, now - entry.last_active,
                )
                await self._kill_process(entry)
                to_remove.append(sid)

        for sid in to_remove:
            self._entries.pop(sid, None)

    async def shutdown(self) -> None:
        """Kill all processes and cancel the cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        for sid, entry in list(self._entries.items()):
            await self._kill_process(entry)
        self._entries.clear()
        self._session_locks.clear()
        logger.info("StreamingPool shutdown complete")

    async def kill_session(self, session_id: str) -> None:
        """Explicitly kill the process for *session_id* (if any)."""
        entry = self._entries.pop(session_id, None)
        if entry is not None:
            await self._kill_process(entry)
            logger.info("Killed session %s", session_id)

    def is_alive(self, session_id: str) -> bool:
        """Return True if *session_id* has a live process."""
        entry = self._entries.get(session_id)
        if entry is None:
            return False
        entry.process.poll()
        return entry.process.returncode is None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _kill_process(self, entry: _ProcessEntry) -> None:
        """Terminate a process, close streams, and wait for exit."""
        proc = entry.process
        proc.poll()
        if proc.returncode is not None:
            return  # already dead

        # Close stdin first to signal the process to exit gracefully.
        if proc.stdin is not None:
            try:
                proc.stdin.close()
            except OSError:
                pass

        try:
            proc.terminate()
        except OSError:
            pass

        loop = asyncio.get_running_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, proc.wait),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Process did not exit after terminate (session %s) — killing", entry.session_id)
            try:
                proc.kill()
            except OSError:
                pass
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, proc.wait),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Process did not exit after kill (session %s)", entry.session_id)

    async def _cleanup_entry(self, entry: _ProcessEntry) -> None:
        """Remove an entry from the pool (does NOT kill — caller does that)."""
        self._entries.pop(entry.session_id, None)
