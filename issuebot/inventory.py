#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Package Inventory Generator
Scans packages/ directory and generates inventory.json with version info and available components.

Usage:
    python issuebot/inventory.py           # Generate packages/inventory.json
    python issuebot/inventory.py --print   # Print to stdout instead of file
"""

import os
import re
import json
import argparse
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.absolute()
ROOT_DIR = SCRIPT_DIR.parent

with open(ROOT_DIR / "config" / "config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

PACKAGES_DIR = ROOT_DIR / config.get("packages_dir", "packages")

# Version pattern: extracts version from directory names like
# package_v5.4.12.0-alpha.4, InterMax_v5.3_202504.linux, intermax_v53_kblife, etc.
VERSION_PATTERNS = [
    # package_v5.4.12.0-alpha.4
    re.compile(r'package_v(\d+\.\d+\.\d+\.\d+(?:-[\w.]+)?)'),
    # InterMax_v5.3_YYYYMM
    re.compile(r'[Ii]nter[Mm]ax_?v?(\d+\.\d+)(?:_(\d{6}))?'),
    # InterMax5.3_YYYYMMDD
    re.compile(r'[Ii]nter[Mm]ax(\d+\.\d+)_(\d{8})'),
    # InterMax_Daemon_YYMM.NN
    re.compile(r'Daemon_(\d{4}\.\d+(?:\.[\w.]+)?)'),
    # intermax_v53_customer
    re.compile(r'intermax_v(\d)(\d)_'),
    # jspd-YYMMDD
    re.compile(r'jspd-(\d{6})'),
]


def parse_version(name):
    """Extract version string from package directory name"""
    for pattern in VERSION_PATTERNS:
        m = pattern.search(name)
        if m:
            ver = m.group(1)
            # intermax_v53 → 5.3
            if pattern.pattern.startswith(r'intermax_v(\d)(\d)'):
                ver = f"{m.group(1)}.{m.group(2)}"
            return ver
    return None


def parse_version_tuple(version_str):
    """Parse version string into sortable tuple: (major, minor, patch, build, suffix)"""
    if not version_str:
        return (0, 0, 0, 0, "")

    # Handle YYMM.NN format (Daemon)
    if re.match(r'^\d{4}\.\d+', version_str):
        parts = version_str.split('.')
        return (0, 0, int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, "daemon")

    # Handle YYMMDD format (jspd)
    if re.match(r'^\d{6}$', version_str):
        return (0, 0, int(version_str), 0, "jspd")

    # Standard: 5.4.12.0-alpha.4
    base = version_str.split('-', 1)
    suffix = base[1] if len(base) > 1 else ""
    parts = base[0].split('.')

    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    build = int(parts[3]) if len(parts) > 3 else 0

    return (major, minor, patch, build, suffix)


def find_intermax_root(pkg_path):
    """Find InterMax root directory within a package (2-level search).

    Mirrors decompile.ps1's Get-IntermaxRoot scoring logic:
    searches pkg_path itself, 1-level children, and 2-level children
    for the directory with the highest InterMax marker score.
    """
    markers = ['DGServer_M', 'PlatformJS', 'jspd', 'dotnet']

    def _score(d):
        s = 0
        name = d.name.lower()
        if 'intermax' in name:
            s += 2
        for m in markers:
            if (d / m).exists():
                s += 10
        return s

    best, best_score = None, 0

    # Check pkg_path itself
    score = _score(pkg_path)
    if score > best_score:
        best, best_score = pkg_path, score

    # Level 1
    try:
        for d in sorted(pkg_path.iterdir()):
            if not d.is_dir():
                continue
            score = _score(d)
            if score > best_score:
                best, best_score = d, score
            # Level 2
            try:
                for d2 in sorted(d.iterdir()):
                    if not d2.is_dir():
                        continue
                    score = _score(d2)
                    if score > best_score:
                        best, best_score = d2, score
            except PermissionError:
                pass
    except PermissionError:
        pass

    return best if best_score > 0 else None


def detect_components(intermax_root):
    """Detect which decompiled components are available"""
    components = []
    if not intermax_root:
        return components

    decompiled = intermax_root / "decompiled"
    if decompiled.exists():
        for d in sorted(decompiled.iterdir()):
            if d.is_dir():
                # Count files to verify it's not empty
                file_count = sum(1 for _ in d.rglob("*") if _.is_file())
                if file_count > 0:
                    components.append(d.name)

    # Also check for frontend JS (not in decompiled/)
    platformjs_frontend = intermax_root / "PlatformJS" / "intermax"
    if platformjs_frontend.exists():
        js_count = sum(1 for _ in platformjs_frontend.rglob("*.js") if _.is_file())
        if js_count > 0 and "PlatformJS-frontend" not in components:
            components.append("PlatformJS-frontend")

    return components


# JAR/DLL target definitions (mirrors decompile.ps1)
_COLLECTOR_JARS = [
    {"name": "datagather", "paths": ["DGServer_M/bin/datagather.jar", "DGServer_M/bin/DGServer.jar"]},
    {"name": "PlatformJS", "paths": ["PlatformJS/bin/PlatformJS.jar", "PlatformJS/bin/exem_platformjs.jar"]},
    {"name": "exem_platformjs", "paths": [
        "PlatformJS/svc/www/WEB-INF/lib/exem_platformjs.jar",
        "PlatformJS/svc/www/WEB-INF/lib/exem_platformjs.jar.ori",
        "PlatformJS/bin/exem_platformjs.jar",
    ]},
    {"name": "jspd", "paths": ["jspd/jspd.jar"]},
]
_AGENT_JARS = [
    {"name": "jspd", "paths": ["jspd/lib/jspd.jar"]},
]
_DOTNET_DLLS = [
    {"name": "InterMax.NetAgent", "paths": ["dotnet/binary/InterMax.NetAgent.dll"]},
]
_DOTNET_CORE_DLLS = [
    {"name": "InterMax.NetAgent.Core.6.0", "paths": ["dotnet/binary/core/6.0/InterMax.NetAgent.Core.dll"]},
    {"name": "InterMax.NetAgent.Core.8.0", "paths": ["dotnet/binary/core/8.0/InterMax.NetAgent.Core.dll"]},
    {"name": "InterMax.Startup.Hook", "paths": ["dotnet/binary/core/startup/InterMax.Startup.Hook.dll"]},
]


def detect_binaries(intermax_root):
    """Detect JAR/DLL files and whether decompilation is needed.

    Returns dict with:
        package_type: collector|agent|dotnet-agent|dotnet-core-agent|None
        has_binaries: bool
        has_decompiled: bool
        needs_decompile: bool
        decompile_targets: list of {type, path, name}
    """
    result = {
        "package_type": None,
        "has_binaries": False,
        "has_decompiled": False,
        "needs_decompile": False,
        "decompile_targets": [],
    }
    if not intermax_root:
        return result

    # Detect package type (mirrors decompile.ps1 Get-PackageType)
    has_dgserver = (intermax_root / "DGServer_M").exists()
    has_platformjs = (intermax_root / "PlatformJS").exists()
    has_agent_jar = (intermax_root / "jspd" / "lib" / "jspd.jar").exists()
    has_collector_jar = (intermax_root / "jspd" / "jspd.jar").exists()
    has_dotnet = (intermax_root / "dotnet" / "binary" / "InterMax.NetAgent.dll").exists()
    has_dotnet_core = (intermax_root / "dotnet" / "binary" / "core").exists()

    if has_dgserver or has_platformjs:
        pkg_type = "collector"
        jar_defs = _COLLECTOR_JARS
    elif has_agent_jar:
        pkg_type = "agent"
        jar_defs = _AGENT_JARS
    elif has_collector_jar:
        pkg_type = "collector"
        jar_defs = _COLLECTOR_JARS
    elif has_dotnet:
        pkg_type = "dotnet-agent"
        jar_defs = []
    elif has_dotnet_core:
        pkg_type = "dotnet-core-agent"
        jar_defs = []
    else:
        return result

    result["package_type"] = pkg_type

    # Find JAR targets
    targets = []
    for jar_def in jar_defs:
        for rel_path in jar_def["paths"]:
            full_path = intermax_root / rel_path.replace("/", os.sep)
            if full_path.exists():
                targets.append({
                    "type": "jar",
                    "path": str(full_path),
                    "name": jar_def["name"],
                })
                break  # first match per definition

    # Find DLL targets
    dll_defs = []
    if pkg_type == "dotnet-agent":
        dll_defs = _DOTNET_DLLS
    elif pkg_type == "dotnet-core-agent":
        dll_defs = _DOTNET_CORE_DLLS

    for dll_def in dll_defs:
        for rel_path in dll_def["paths"]:
            full_path = intermax_root / rel_path.replace("/", os.sep)
            if full_path.exists():
                targets.append({
                    "type": "dll",
                    "path": str(full_path),
                    "name": dll_def["name"],
                })
                break

    result["has_binaries"] = len(targets) > 0
    result["decompile_targets"] = targets

    # Check if decompiled/ exists and has content
    decompiled_dir = intermax_root / "decompiled"
    if decompiled_dir.exists():
        has_content = any(True for _ in decompiled_dir.iterdir() if _.is_dir())
        result["has_decompiled"] = has_content
    else:
        result["has_decompiled"] = False

    result["needs_decompile"] = result["has_binaries"] and not result["has_decompiled"]

    return result


def _strip_archive_ext(name):
    """Strip archive extensions (.tar.gz, .tar, .gz, .zip) from a filename."""
    for ext in (".tar.gz", ".tar", ".gz", ".zip"):
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


def generate_inventory():
    """Scan packages/ and generate inventory.

    Scans both extracted directories and unextracted archives (.tar.gz etc.).
    Archives that have a matching extracted directory are skipped.
    Unextracted archives are included with ``extracted: false`` so that
    researchers know they exist and can request extraction.
    """
    packages = []
    seen_names = set()  # track extracted dir names to skip duplicate archives

    if not PACKAGES_DIR.exists():
        return {"generated_at": datetime.now().isoformat(), "packages": []}

    # Pass 1: extracted directories (existing behaviour)
    for item in sorted(PACKAGES_DIR.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith('_') or item.name.startswith('.') or item.name == 'nul':
            continue

        seen_names.add(item.name)

        version = parse_version(item.name)
        version_tuple = parse_version_tuple(version)
        intermax_root = find_intermax_root(item)
        components = detect_components(intermax_root)
        binaries = detect_binaries(intermax_root)

        pkg_info = {
            "name": item.name,
            "version": version or "unknown",
            "version_sort": list(version_tuple[:4]) + [version_tuple[4]],
            "components": components,
            "intermax_root": intermax_root.name if intermax_root else None,
            "path": str(item.relative_to(ROOT_DIR)),
            "extracted": True,
            "needs_decompile": binaries["needs_decompile"],
            "decompile_targets": binaries["decompile_targets"],
            "package_type": binaries["package_type"],
        }
        packages.append(pkg_info)

    # Pass 2: unextracted archives (.tar.gz, .zip, etc.)
    for item in sorted(PACKAGES_DIR.iterdir()):
        if item.is_dir():
            continue
        if not item.name.endswith((".tar.gz", ".tar", ".gz", ".zip")):
            continue

        base_name = _strip_archive_ext(item.name)
        if base_name in seen_names:
            continue  # already have an extracted directory

        version = parse_version(base_name)
        version_tuple = parse_version_tuple(version)

        pkg_info = {
            "name": base_name,
            "version": version or "unknown",
            "version_sort": list(version_tuple[:4]) + [version_tuple[4]],
            "components": [],
            "intermax_root": None,
            "path": str(item.relative_to(ROOT_DIR)),
            "extracted": False,
            "archive": item.name,
        }
        packages.append(pkg_info)

    # Sort by version (newest first)
    packages.sort(key=lambda p: p["version_sort"], reverse=True)

    return {
        "generated_at": datetime.now().isoformat(),
        "package_count": len(packages),
        "packages": packages,
    }


def format_summary(inventory):
    """Format inventory as human-readable summary"""
    lines = []
    lines.append(f"패키지 인벤토리 ({inventory['package_count']}개)")
    lines.append(f"생성: {inventory['generated_at']}")
    lines.append("")
    lines.append(f"{'패키지':<45} {'버전':<25} {'상태':<8} {'컴포넌트'}")
    lines.append("-" * 110)
    for pkg in inventory["packages"]:
        comp = ", ".join(pkg["components"]) if pkg["components"] else "(없음)"
        if not pkg.get("extracted", True):
            status = "tar.gz"
        elif pkg.get("needs_decompile"):
            status = "DECOM"
        else:
            status = "OK"
        lines.append(f"{pkg['name']:<45} {pkg['version']:<25} {status:<8} {comp}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate package inventory")
    parser.add_argument("--print", action="store_true", help="Print to stdout instead of file")
    parser.add_argument("--summary", action="store_true", help="Print human-readable summary")
    args = parser.parse_args()

    inventory = generate_inventory()

    if args.summary:
        print(format_summary(inventory))
        return

    if getattr(args, 'print'):
        print(json.dumps(inventory, indent=2, ensure_ascii=False))
        return

    output_path = PACKAGES_DIR / "inventory.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)
    print(f"Inventory saved to {output_path}")
    print(format_summary(inventory))


if __name__ == "__main__":
    main()
