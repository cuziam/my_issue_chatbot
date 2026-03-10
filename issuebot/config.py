"""Centralized configuration for issuebot modules.

Replaces the duplicated config loading pattern found in 6+ modules.
Uses lazy initialization to avoid import-time side effects.
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent.absolute()

# Load .env once
load_dotenv(ROOT_DIR / ".env")

_config = None


def get_config() -> dict:
    """Lazy-load and cache config.json."""
    global _config
    if _config is None:
        with open(ROOT_DIR / "config" / "config.json", "r", encoding="utf-8") as f:
            _config = json.load(f)
    return _config


def reload_config() -> dict:
    """Force-reload config.json (e.g. after settings change)."""
    global _config
    _config = None
    return get_config()


def get_root_dir() -> Path:
    return ROOT_DIR


# Derived directories (lazy via config)
def get_tasks_dir() -> Path:
    return ROOT_DIR / get_config().get("tasks_dir", "tasks")


def get_packages_dir() -> Path:
    return ROOT_DIR / get_config().get("packages_dir", "packages")


# Convenience constants (these don't depend on config.json)
TASKS_DIR = ROOT_DIR / "tasks"
PACKAGES_DIR = ROOT_DIR / "packages"
LOGS_DIR = ROOT_DIR / "logs"
CONFIG_FILE = ROOT_DIR / "config" / "config.json"
