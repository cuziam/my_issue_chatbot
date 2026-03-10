"""LLM backend abstraction layer.

Provides a unified interface for running Claude CLI (and potentially other
backends in the future).
"""
from .base import LLMBackend, LLMEvent
from .claude_cli import ClaudeCLIBackend

_default_backend: LLMBackend | None = None


def get_llm_backend() -> LLMBackend:
    """Return the singleton LLM backend instance."""
    global _default_backend
    if _default_backend is None:
        _default_backend = ClaudeCLIBackend()
    return _default_backend


__all__ = ["LLMBackend", "LLMEvent", "ClaudeCLIBackend", "get_llm_backend"]
