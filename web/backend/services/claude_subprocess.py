"""Shared utilities for Claude CLI subprocess management.

Extracted from analysis_service.py and chat_service.py to eliminate
duplication of environment cleaning, stream-json parsing, and tool
invocation summarization.
"""
from __future__ import annotations

import json
import os
from datetime import datetime


def clean_env() -> dict[str, str]:
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


def summarize_tool_input(tool: str, inp: dict) -> str:
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


def parse_stream_events(line: str) -> list[dict]:
    """Parse a ``stream-json`` line into human-readable progress events.

    Returns a list of event dicts with keys like ``event``, ``tool``,
    ``detail``, ``subtype``, etc.  Used by both analysis and chat services.
    """
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
                detail = summarize_tool_input(tool, item.get("input", {}))
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


def parse_chat_events(line: str) -> list[dict]:
    """Parse a ``stream-json`` line into chat-specific events.

    Returns events with ``type`` key (``"text"`` or ``"progress"``).
    Text events carry the assistant's response content; progress events
    carry tool-use summaries.
    """
    try:
        event = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return []

    results: list[dict] = []
    etype = event.get("type")

    if etype == "assistant":
        for item in event.get("message", {}).get("content", []):
            kind = item.get("type")
            if kind == "text":
                text = item.get("text", "")
                if text:
                    results.append({"type": "text", "content": text})
            elif kind == "tool_use":
                tool = item.get("name", "")
                inp = item.get("input", {})
                detail = summarize_tool_input(tool, inp)
                results.append({
                    "type": "progress",
                    "event": "tool_use",
                    "tool": tool,
                    "detail": detail,
                })

    elif etype == "result":
        results.append({
            "type": "progress",
            "event": "result",
            "detail": f"Done ({event.get('num_turns', '?')} turns, ${event.get('cost_usd', '?')})",
        })

    return results
