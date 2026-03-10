#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Decompile Runner — Python wrapper for decompile.ps1 / decompile.sh

Checks prerequisites (Java, CFR, ILSpy) and invokes the appropriate
decompile script for packages that need decompilation.

Usage:
    python issuebot/decompile_runner.py --package package_v5.4.12.0
    python issuebot/decompile_runner.py --all          # decompile all needs_decompile
    python issuebot/decompile_runner.py --check        # check prerequisites only
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.absolute()
ROOT_DIR = SCRIPT_DIR.parent

try:
    from .inventory import generate_inventory
except ImportError:
    # Direct execution fallback
    sys.path.insert(0, str(SCRIPT_DIR))
    from inventory import generate_inventory  # type: ignore[import-untyped]

DECOMPILER_DIR = ROOT_DIR / "decompiler"
TOOLS_DIR = ROOT_DIR / "tools"
PACKAGES_DIR = ROOT_DIR / "packages"

# Timeout for a single package decompilation (10 minutes)
DECOMPILE_TIMEOUT = 600


def log(message):
    print(f"[decompile_runner] {message}")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

def _find_java():
    """Find java executable. Returns path or None."""
    # JAVA_HOME
    java_home = os.environ.get("JAVA_HOME", "")
    if java_home:
        java_bin = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if java_bin.exists():
            return str(java_bin)

    # PATH
    java = shutil.which("java")
    if java:
        return java

    return None


def _find_cfr():
    """Find CFR JAR. Returns path or None."""
    cfr = TOOLS_DIR / "cfr-0.152.jar"
    if cfr.exists():
        return str(cfr)
    return None


def _find_ilspy():
    """Find ILSpyCMD executable. Returns path or None."""
    ilspy_dir = TOOLS_DIR / "ilspycmd"
    ilspy_exe = ilspy_dir / ("ilspycmd.exe" if os.name == "nt" else "ilspycmd")
    if ilspy_exe.exists():
        return str(ilspy_exe)
    return None


def check_prerequisites():
    """Check availability of decompilation tools.

    Returns dict with:
        java: str|None — java path
        cfr: str|None — CFR JAR path
        ilspy: str|None — ILSpyCMD path
        can_decompile_jar: bool
        can_decompile_dll: bool
        script: str|None — path to decompile.ps1 or decompile.sh
    """
    java = _find_java()
    cfr = _find_cfr()
    ilspy = _find_ilspy()

    # Find decompile script
    if os.name == "nt":
        script = DECOMPILER_DIR / "decompile.ps1"
    else:
        script = DECOMPILER_DIR / "decompile.sh"

    script_path = str(script) if script.exists() else None

    return {
        "java": java,
        "cfr": cfr,
        "ilspy": ilspy,
        "can_decompile_jar": bool(java and cfr),
        "can_decompile_dll": bool(ilspy),
        "script": script_path,
    }


# ---------------------------------------------------------------------------
# Decompilation
# ---------------------------------------------------------------------------

def run_decompile(package_name, overwrite=False):
    """Decompile a single package by invoking the platform decompile script.

    Returns dict with:
        success: bool
        package: str
        output: str (stdout/stderr)
        error: str|None
    """
    prereqs = check_prerequisites()
    if not prereqs["script"]:
        return {
            "success": False,
            "package": package_name,
            "output": "",
            "error": "Decompile script not found",
        }

    pkg_dir = PACKAGES_DIR / package_name
    if not pkg_dir.exists():
        return {
            "success": False,
            "package": package_name,
            "output": "",
            "error": f"Package directory not found: {pkg_dir}",
        }

    log(f"Decompiling: {package_name}")

    if os.name == "nt":
        # PowerShell -File mode cannot pass [bool] params from external
        # processes (strings like "$true" are not interpreted as PS variables).
        # Use -Command to invoke the script so $true/$false are evaluated.
        overwrite_val = "$true" if overwrite else "$false"
        ps_command = (
            f"& '{prereqs['script']}'"
            f" -PackageName '{package_name}'"
            f" -NonInteractive $true"
            f" -OverwriteExisting {overwrite_val}"
        )
        cmd = [
            "pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-Command", ps_command,
        ]
        # Fallback to powershell.exe if pwsh not available
        if not shutil.which("pwsh"):
            cmd[0] = "powershell"
    else:
        cmd = [
            "bash", prereqs["script"],
            "-p", package_name,
        ]
        if overwrite:
            cmd.append("-o")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=DECOMPILE_TIMEOUT,
            cwd=str(ROOT_DIR),
        )

        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr

        success = result.returncode == 0
        if success:
            log(f"  Decompilation completed: {package_name}")
        else:
            log(f"  Decompilation failed (exit {result.returncode}): {package_name}")

        return {
            "success": success,
            "package": package_name,
            "output": output,
            "error": None if success else f"Exit code {result.returncode}",
        }

    except subprocess.TimeoutExpired:
        log(f"  Decompilation timed out: {package_name}")
        return {
            "success": False,
            "package": package_name,
            "output": "",
            "error": f"Timed out after {DECOMPILE_TIMEOUT}s",
        }
    except FileNotFoundError as e:
        log(f"  Command not found: {e}")
        return {
            "success": False,
            "package": package_name,
            "output": "",
            "error": str(e),
        }


def run_decompile_needed(inventory=None):
    """Decompile all packages with needs_decompile=True.

    Args:
        inventory: Pre-loaded inventory dict. If None, generates fresh.

    Returns list of result dicts from run_decompile().
    """
    if inventory is None:
        inventory = generate_inventory()

    needs = [
        p for p in inventory.get("packages", [])
        if p.get("needs_decompile") and p.get("extracted", True)
    ]

    if not needs:
        log("No packages need decompilation")
        return []

    prereqs = check_prerequisites()
    # Check if we have the right tools for the targets
    has_jar_targets = any(
        t["type"] == "jar"
        for p in needs
        for t in p.get("decompile_targets", [])
    )
    has_dll_targets = any(
        t["type"] == "dll"
        for p in needs
        for t in p.get("decompile_targets", [])
    )

    if has_jar_targets and not prereqs["can_decompile_jar"]:
        log("Warning: JAR targets found but Java/CFR not available")
    if has_dll_targets and not prereqs["can_decompile_dll"]:
        log("Warning: DLL targets found but ILSpyCMD not available")

    log(f"Decompiling {len(needs)} package(s)...")
    results = []
    for pkg in needs:
        result = run_decompile(pkg["name"])
        results.append(result)

    succeeded = sum(1 for r in results if r["success"])
    log(f"Decompilation complete: {succeeded}/{len(results)} succeeded")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Decompile Runner")
    parser.add_argument("--package", help="Decompile a specific package")
    parser.add_argument("--all", action="store_true", help="Decompile all needs_decompile packages")
    parser.add_argument("--check", action="store_true", help="Check prerequisites only")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing decompiled output")
    args = parser.parse_args()

    if args.check:
        prereqs = check_prerequisites()
        print(json.dumps(prereqs, indent=2))
        return

    if args.package:
        result = run_decompile(args.package, overwrite=args.overwrite)
        if result["output"]:
            print(result["output"])
        if not result["success"]:
            log(f"Error: {result['error']}")
            sys.exit(1)
        return

    if args.all:
        results = run_decompile_needed()
        failed = [r for r in results if not r["success"]]
        if failed:
            for r in failed:
                log(f"  FAILED: {r['package']} — {r['error']}")
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
