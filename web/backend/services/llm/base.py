"""Abstract base for LLM backends."""
from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class LLMEvent:
    """A single event from an LLM streaming response.

    Attributes:
        type: Event type — "text", "tool_use", "result", "error", "heartbeat"
        content: Text content (for "text" events)
        tool_name: Tool being invoked (for "tool_use" events)
        tool_summary: Human-readable summary of tool invocation
        raw_data: Original parsed event data from the backend
    """
    type: str
    content: str = ""
    tool_name: str = ""
    tool_summary: str = ""
    raw_data: dict = field(default_factory=dict)


class LLMBackend(ABC):
    """Abstract interface for LLM execution backends."""

    @abstractmethod
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
        """Start an LLM process and return (process, effective_session_id).

        The caller is responsible for reading stdout and managing the process
        lifecycle. This keeps the existing streaming patterns intact while
        centralizing process creation.

        When *use_stdin* is True, the prompt is piped via stdin instead of
        the ``-p`` argument.  This avoids Windows command-line length limits
        for very large prompts (e.g. digest generation).
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend CLI/API is available."""
        ...

    @abstractmethod
    def cancel(self, process: subprocess.Popen) -> None:
        """Cancel a running process."""
        ...
