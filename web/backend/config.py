"""App configuration singleton.

Supports environment variable overrides for Docker deployment:
  ISSUEBOT_ROOT       — project root directory
  ISSUEBOT_TASKS_DIR  — tasks storage directory
  ISSUEBOT_PACKAGES_DIR — packages directory
  ISSUEBOT_LOGS_DIR   — logs directory
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(
    os.getenv("ISSUEBOT_ROOT", str(Path(__file__).parent.parent.parent.absolute()))
)

# Load .env before anything else
load_dotenv(ROOT_DIR / ".env")

CONFIG_FILE = ROOT_DIR / "config" / "config.json"
TASKS_DIR = Path(os.getenv("ISSUEBOT_TASKS_DIR", str(ROOT_DIR / "tasks")))
PACKAGES_DIR = Path(os.getenv("ISSUEBOT_PACKAGES_DIR", str(ROOT_DIR / "packages")))
LOGS_DIR = Path(os.getenv("ISSUEBOT_LOGS_DIR", str(ROOT_DIR / "logs")))
ENV_FILE = ROOT_DIR / ".env"


def load_config() -> dict:
    """Load config.json and return as dict."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data: dict) -> None:
    """Write dict back to config.json."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
