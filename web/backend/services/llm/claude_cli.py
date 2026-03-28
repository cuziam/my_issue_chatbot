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
        use_stdin: bool = False,
    ) -> tuple[subprocess.Popen, str]:
        """Start a ``claude -p`` subprocess.

        Returns (process, session_id). The caller reads process.stdout.

        When *use_stdin* is True the prompt is written to the process's
        stdin (and stdin is then closed) instead of being passed as the
        ``-p`` argument.  This avoids the Windows command-line length
        limit (~32 KB) for very large prompts.
        """
        import asyncio

        cmd = [self._cmd]

        if use_stdin:
            # Prompt piped via stdin: use ``-p`` WITHOUT an argument.
            # Claude CLI reads the prompt from stdin when -p has no value.
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

        env = clean_env()
        loop = asyncio.get_running_loop()

        stdin_mode = subprocess.PIPE if use_stdin else None
        prompt_bytes = prompt.encode("utf-8") if use_stdin else None

        process = await loop.run_in_executor(
            None,
            lambda: subprocess.Popen(
                cmd,
                stdin=stdin_mode,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=cwd or None,
                env=env,
            ),
        )

        # Write prompt to stdin and close it so claude starts processing
        if use_stdin and prompt_bytes:
            await loop.run_in_executor(
                None,
                lambda: (process.stdin.write(prompt_bytes), process.stdin.close()),
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
