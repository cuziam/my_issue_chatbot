"""Claude CLI backend implementation.

Wraps the ``claude`` CLI tool invoked via subprocess.Popen with
stream-json output parsing.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..claude_subprocess import clean_env
from .base import LLMBackend


class ClaudeCLIBackend(LLMBackend):
    """LLM backend that uses the Claude Code CLI (``claude``)."""

    def __init__(self, claude_cmd: str = "claude"):
        self._cmd = claude_cmd

    async def run_prompt(
        self,
        prompt: str,
        *,
        session_id: str,
        resume: bool = False,
        allowed_tools: list[str] | None = None,
        cwd: str = "",
        system_prompt: str = "",
        use_stdin: bool = False,
        model: str = "",
        include_partial: bool = False,
    ) -> tuple[subprocess.Popen, str]:
        """Start a ``claude -p`` subprocess.

        Returns (process, session_id). The caller reads process.stdout.

        When *use_stdin* is True the prompt is written to a temporary file
        and piped via stdin file handle to avoid both the Windows
        command-line length limit (~32 KB) and stdin pipe deadlocks
        with large prompts.
        """
        import asyncio

        cmd = [self._cmd]

        if use_stdin:
            # Prompt fed via stdin from a temp file.
            # ``claude -p`` (no argument) reads prompt from stdin.
            if resume:
                cmd += ["-p", "--verbose", "--output-format", "stream-json",
                        "--resume", session_id]
            else:
                cmd += ["-p", "--verbose", "--output-format", "stream-json",
                        "--session-id", session_id]
        else:
            if resume:
                cmd += ["-p", prompt, "--verbose", "--output-format", "stream-json",
                        "--resume", session_id]
            else:
                cmd += ["-p", prompt, "--verbose", "--output-format", "stream-json",
                        "--session-id", session_id]

        if allowed_tools:
            cmd += ["--allowedTools", ",".join(allowed_tools)]

        if system_prompt:
            cmd += ["--append-system-prompt", system_prompt]

        if model:
            cmd += ["--model", model]

        if include_partial:
            cmd += ["--include-partial-messages"]

        env = clean_env()
        loop = asyncio.get_running_loop()

        # For large prompts: write to temp file and open as stdin file
        # handle.  This avoids both the Windows command-line length limit
        # AND the stdin pipe deadlock that occurs when the write buffer
        # fills up before the child process reads it.
        stdin_fh = None
        if use_stdin:
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8",
            )
            tmp.write(prompt)
            tmp.close()
            stdin_fh = open(tmp.name, "r", encoding="utf-8")
            # Store path for cleanup after process finishes
            self._stdin_tmp_path = Path(tmp.name)

        process = await loop.run_in_executor(
            None,
            lambda: subprocess.Popen(
                cmd,
                stdin=stdin_fh,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=cwd or None,
                env=env,
            ),
        )

        # Close our copy of the file handle (process has its own)
        if stdin_fh:
            stdin_fh.close()

        return process, session_id

    def is_available(self) -> bool:
        """Check if ``claude`` CLI is on PATH."""
        return shutil.which(self._cmd) is not None

    def cancel(self, process: subprocess.Popen) -> None:
        """Terminate a running claude process."""
        try:
            process.terminate()
        except OSError:
            pass

    def cleanup_stdin_tmp(self) -> None:
        """Remove the temporary stdin file if it exists."""
        tmp = getattr(self, "_stdin_tmp_path", None)
        if tmp and tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
            self._stdin_tmp_path = None
