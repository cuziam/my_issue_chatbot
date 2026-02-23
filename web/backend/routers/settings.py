"""Settings endpoints: config.json, .env, and package inventory management."""
from __future__ import annotations

import asyncio
import json
import sys

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import (
    CONFIG_FILE,
    ENV_FILE,
    ISSUEBOT_DIR,
    PACKAGES_DIR,
    load_config,
    save_config,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# config.json
# ---------------------------------------------------------------------------

@router.get("/config")
async def get_config():
    """Return the current config.json contents."""
    return load_config()


class ConfigUpdate(BaseModel):
    data: dict


@router.put("/config")
async def update_config(update: ConfigUpdate):
    """Overwrite config.json with the provided data dict."""
    save_config(update.data)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# .env
# ---------------------------------------------------------------------------

@router.get("/env")
async def get_env():
    """Read .env file with sensitive values (KEY/SECRET/TOKEN) masked."""
    if not ENV_FILE.exists():
        return {"variables": {}}

    variables: dict[str, str] = {}
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            # Mask sensitive values
            if any(kw in key.upper() for kw in ("KEY", "SECRET", "TOKEN")):
                if len(value) > 8:
                    variables[key] = value[:4] + "*" * (len(value) - 8) + value[-4:]
                else:
                    variables[key] = "****"
            else:
                variables[key] = value

    return {"variables": variables}


class EnvUpdate(BaseModel):
    variables: dict[str, str]


@router.put("/env")
async def update_env(update: EnvUpdate):
    """Update .env file, preserving comments and not overwriting masked values."""
    # Read existing lines to preserve comments and ordering
    lines: list[str] = []
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

    existing_keys: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in update.variables:
                value = update.variables[key]
                # Don't overwrite with masked values
                if "****" not in value:
                    new_lines.append(f"{key}={value}\n")
                else:
                    new_lines.append(line)  # Keep original
                existing_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Append new variables that weren't already in the file
    for key, value in update.variables.items():
        if key not in existing_keys and "****" not in value:
            new_lines.append(f"{key}={value}\n")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Package inventory
# ---------------------------------------------------------------------------

@router.get("/inventory")
async def get_inventory():
    """Return the current packages/inventory.json."""
    inv_file = PACKAGES_DIR / "inventory.json"
    if inv_file.exists():
        with open(inv_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"packages": [], "generated_at": None}


@router.post("/inventory/refresh")
async def refresh_inventory():
    """Regenerate inventory.json by scanning the packages/ directory."""

    def _run() -> dict:
        sys.path.insert(0, str(ISSUEBOT_DIR))
        from inventory import generate_inventory  # type: ignore[import-untyped]

        inv = generate_inventory()

        inv_file = PACKAGES_DIR / "inventory.json"
        inv_file.parent.mkdir(parents=True, exist_ok=True)
        with open(inv_file, "w", encoding="utf-8") as f:
            json.dump(inv, f, indent=2, ensure_ascii=False)

        return inv

    return await asyncio.to_thread(_run)
