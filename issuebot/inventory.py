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
    """Find InterMax root directory within a package"""
    for d in sorted(pkg_path.iterdir()):
        if not d.is_dir():
            continue
        name = d.name.lower()
        if 'intermax' in name:
            return d
    # Check if pkg_path itself is the root (has DGServer_M, PlatformJS, etc.)
    markers = ['DGServer_M', 'PlatformJS', 'jspd', 'dotnet']
    for m in markers:
        if (pkg_path / m).exists():
            return pkg_path
    return None


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


def generate_inventory():
    """Scan packages/ and generate inventory"""
    packages = []

    if not PACKAGES_DIR.exists():
        return {"generated_at": datetime.now().isoformat(), "packages": []}

    for item in sorted(PACKAGES_DIR.iterdir()):
        if not item.is_dir():
            continue
        if item.name.startswith('_') or item.name.startswith('.') or item.name == 'nul':
            continue

        version = parse_version(item.name)
        version_tuple = parse_version_tuple(version)
        intermax_root = find_intermax_root(item)
        components = detect_components(intermax_root)

        pkg_info = {
            "name": item.name,
            "version": version or "unknown",
            "version_sort": list(version_tuple[:4]) + [version_tuple[4]],
            "components": components,
            "intermax_root": intermax_root.name if intermax_root else None,
            "path": str(item.relative_to(ROOT_DIR)),
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
    lines.append(f"{'패키지':<45} {'버전':<25} {'컴포넌트'}")
    lines.append("-" * 100)
    for pkg in inventory["packages"]:
        comp = ", ".join(pkg["components"]) if pkg["components"] else "(없음)"
        lines.append(f"{pkg['name']:<45} {pkg['version']:<25} {comp}")
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
