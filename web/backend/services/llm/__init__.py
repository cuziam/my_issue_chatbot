"""LLM backend abstraction layer.

Provides a unified interface for running Claude CLI (and potentially other
backends in the future).
"""
from .base import LLMBackend, LLMEvent
from .claude_cli import ClaudeCLIBackend
from .streaming_pool import StreamingPool

_default_backend: LLMBackend | None = None
_streaming_pool: StreamingPool | None = None


def get_llm_backend() -> LLMBackend:
    """Return the singleton LLM backend instance."""
    global _default_backend
    if _default_backend is None:
        _default_backend = ClaudeCLIBackend()
    return _default_backend


def get_streaming_pool() -> StreamingPool:
    """Return the singleton StreamingPool instance."""
    global _streaming_pool
    if _streaming_pool is None:
        _streaming_pool = StreamingPool()
    return _streaming_pool


__all__ = [
    "LLMBackend", "LLMEvent", "ClaudeCLIBackend",
    "get_llm_backend", "StreamingPool", "get_streaming_pool",
]
