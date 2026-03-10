"""Claude CLI backend implementation.

Wraps the ``claude`` CLI tool invoked via subprocess.Popen with
stream-json output parsing.
"""
from __future__ import annotations

import shutil
import subprocess

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
    ) -> tuple[subprocess.Popen, str]:
        """Start a ``claude -p`` subprocess.

        Returns (process, session_id). The caller reads process.stdout.
        """
        import asyncio

        cmd = [self._cmd]

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

        env = clean_env()
        loop = asyncio.get_running_loop()

        process = await loop.run_in_executor(
            None,
            lambda: subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=cwd or None,
                env=env,
            ),
        )

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
