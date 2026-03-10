#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version Diff Generator — Compare source files between two package versions.

When explicit patch files are unavailable but a newer package version exists,
this module generates patch_diff.md / patch_diff.json showing changes between
the old (analyzed) and new package versions.  The output format is identical
to patch_diff.py so existing UI tabs work unchanged.

Usage:
    python issuebot/version_diff.py --task-id IMX-9227
    python issuebot/version_diff.py --task-id IMX-9227 --dry-run
"""

import json
import re
import sys
import difflib
import argparse
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.absolute()
ROOT_DIR = SCRIPT_DIR.parent

try:
    from .inventory import parse_version_tuple, generate_inventory
except ImportError:
    # Direct execution fallback
    sys.path.insert(0, str(SCRIPT_DIR))
    from inventory import parse_version_tuple, generate_inventory  # type: ignore[import-untyped]

with open(ROOT_DIR / "config" / "config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

TASKS_DIR = ROOT_DIR / config.get("tasks_dir", "tasks")
PACKAGES_DIR = ROOT_DIR / config.get("packages_dir", "packages")

# Max diff lines per file
MAX_DIFF_LINES = 500
# Max files to compare when no focus files specified
MAX_DIFF_FILES = 50


def log(message):
    print(f"[version_diff] {message}")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Package extraction from report / context
# ---------------------------------------------------------------------------

_PKG_NAME_RE = re.compile(r'(package_v[\d.]+(?:-[\w.]+)?)')


def find_analyzed_package(task_dir):
    """Extract the primary analyzed package name from context.md or report.md.

    Looks for patterns like ``package_v5.4.12.0-alpha.5`` in:
    1. report.md ``분석 코드베이스`` table (분석 패키지 column)
    2. context.md ``Explored Files`` section
    3. Any package_v reference in report.md

    Returns the package name string or None.
    """
    # Strategy 1: report.md 분석 코드베이스 table
    report = task_dir / "report.md"
    if report.exists():
        try:
            text = report.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = ""

        # Look for table rows after "분석 코드베이스"
        in_table = False
        for line in text.splitlines():
            if "분석 코드베이스" in line:
                in_table = True
                continue
            if in_table:
                if line.startswith("|") and "---" not in line:
                    m = _PKG_NAME_RE.search(line)
                    if m:
                        return m.group(1)
                elif not line.startswith("|") and not line.strip() == "":
                    in_table = False

    # Strategy 2: context.md Explored Files
    context = task_dir / "context.md"
    if context.exists():
        try:
            text = context.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = ""

        # Find first package_v reference under "Explored Files" or "Critical"
        in_files = False
        for line in text.splitlines():
            if "Explored Files" in line or "Critical" in line:
                in_files = True
                continue
            if in_files:
                m = _PKG_NAME_RE.search(line)
                if m:
                    return m.group(1)
                if line.startswith("## ") and "File" not in line:
                    in_files = False

    # Strategy 3: Any package_v reference in report.md
    if report.exists():
        try:
            text = report.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = ""
        m = _PKG_NAME_RE.search(text)
        if m:
            return m.group(1)

    return None


def find_newer_package(old_name, inventory):
    """Find a newer package version in the same major.minor line.

    Args:
        old_name: e.g. 'package_v5.4.12.0-alpha.5'
        inventory: inventory dict

    Returns package name string or None.
    """
    # Extract version from old package name
    m = re.search(r'v(\d+\.\d+\.\d+\.\d+(?:-[\w.]+)?)', old_name)
    if not m:
        return None
    old_version = m.group(1)
    old_tuple = parse_version_tuple(old_version)
    old_major, old_minor = old_tuple[0], old_tuple[1]

    candidates = []
    for pkg in inventory.get("packages", []):
        name = pkg["name"]
        if name == old_name:
            continue
        if not pkg.get("extracted", True):
            continue  # skip unextracted archives

        version = pkg.get("version", "unknown")
        if version == "unknown":
            continue

        vtuple = parse_version_tuple(version)
        # Same major.minor, strictly newer
        if vtuple[0] == old_major and vtuple[1] == old_minor:
            if vtuple[:4] > old_tuple[:4]:
                candidates.append((pkg, vtuple))
            elif vtuple[:4] == old_tuple[:4]:
                # Same numeric, compare suffix (alpha.5 < alpha.6, "" > "alpha")
                old_suffix = old_tuple[4]
                new_suffix = vtuple[4]
                # Release ("") is newer than any pre-release
                if not new_suffix and old_suffix:
                    candidates.append((pkg, vtuple))
                elif new_suffix and old_suffix and new_suffix > old_suffix:
                    candidates.append((pkg, vtuple))

    if not candidates:
        return None

    # Pick the closest newer version (smallest increase)
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]["name"]


# ---------------------------------------------------------------------------
# Relevant files from report
# ---------------------------------------------------------------------------

_FILE_REF_RE = re.compile(
    r'`(?:packages/[^`]+/)?'   # optional packages/ prefix
    r'((?:intermax|com|org|jdg)/[^`:]+)'  # source path
    r'(?::\d+(?:-\d+)?)?`'    # optional :line-line
)

_FULL_PATH_RE = re.compile(
    r'packages/package_v[^/]+/[^/]+/(?:decompiled/|PlatformJS/)?'
    r'((?:intermax|com|org|jdg)/[^\s:`]+)'
)


def find_relevant_files(task_dir):
    """Extract source file relative paths from report.md and context.md.

    Looks for patterns like:
    - `intermax/Exem/wasDBTreeComboForPa.js:101`
    - `packages/package_v.../PlatformJS/intermax/Exem/Foo.js`
    - `com/exem/platform/Foo.java:45`

    Returns list of relative source paths (e.g. ['intermax/Exem/Foo.js']).
    """
    paths = set()

    for filename in ("report.md", "context.md"):
        filepath = task_dir / filename
        if not filepath.exists():
            continue
        try:
            text = filepath.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for m in _FILE_REF_RE.finditer(text):
            paths.add(m.group(1))
        for m in _FULL_PATH_RE.finditer(text):
            paths.add(m.group(1))

    return sorted(paths)


# ---------------------------------------------------------------------------
# Package diffing
# ---------------------------------------------------------------------------

def _find_intermax_root(pkg_dir):
    """Find InterMax root within a package directory."""
    # Check direct children first
    for d in sorted(pkg_dir.iterdir()):
        if d.is_dir() and "intermax" in d.name.lower():
            return d
    # Check if pkg_dir itself has markers
    markers = ["DGServer_M", "PlatformJS", "jspd", "dotnet"]
    for m in markers:
        if (pkg_dir / m).exists():
            return pkg_dir
    # Check 2 levels
    for d in sorted(pkg_dir.iterdir()):
        if not d.is_dir():
            continue
        for d2 in sorted(d.iterdir()):
            if d2.is_dir() and "intermax" in d2.name.lower():
                return d2
    return None


def _resolve_source_path(pkg_dir, rel_path):
    """Resolve a relative source path within a package.

    rel_path examples:
    - intermax/Exem/Foo.js  → {pkg}/InterMax*/PlatformJS/intermax/Exem/Foo.js
    - com/exem/platform/Bar.java → {pkg}/InterMax*/decompiled/PlatformJS/com/exem/...
    - jdg/dgs/Baz.java → {pkg}/InterMax*/decompiled/datagather/jdg/dgs/...
    """
    root = _find_intermax_root(pkg_dir)
    if not root:
        return None

    # Try direct paths based on prefix
    prefix_map = [
        ("intermax/", root / "PlatformJS"),
        ("com/exem/platform/", root / "decompiled" / "PlatformJS"),
        ("com/exem/intermax/", root / "decompiled" / "PlatformJS"),
        ("com/exem/jspd/", root / "decompiled" / "jspd"),
        ("org/bsp/", root / "decompiled" / "jspd"),
        ("jdg/", root / "decompiled" / "datagather"),
    ]

    for prefix, base in prefix_map:
        if rel_path.startswith(prefix):
            full = base / rel_path
            if full.exists():
                return full

    # Fallback: search by filename
    filename = Path(rel_path).name
    candidates = list(pkg_dir.rglob(filename))
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        # Pick best match by path overlap
        rel_parts = Path(rel_path).parts
        best = max(candidates, key=lambda c: sum(1 for p in rel_parts if p in c.parts))
        return best

    return None


def _read_file_lines(filepath):
    """Read file lines with encoding fallback."""
    for enc in ("utf-8", "euc-kr", "cp949", "latin-1"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.readlines()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return []


def diff_packages(old_pkg_name, new_pkg_name, relevant_files=None):
    """Generate diffs between two package versions.

    Args:
        old_pkg_name: e.g. 'package_v5.4.12.0-alpha.5'
        new_pkg_name: e.g. 'package_v5.4.12.1-alpha.0'
        relevant_files: list of relative source paths to focus on.
            If None, compares all files in decompiled/ and PlatformJS/intermax/.

    Returns list of dicts compatible with patch_diff.py output format.
    """
    old_dir = PACKAGES_DIR / old_pkg_name
    new_dir = PACKAGES_DIR / new_pkg_name

    if not old_dir.exists() or not new_dir.exists():
        log(f"Package directory missing: old={old_dir.exists()}, new={new_dir.exists()}")
        return []

    results = []

    if relevant_files:
        # Compare specific files
        for rel_path in relevant_files:
            old_file = _resolve_source_path(old_dir, rel_path)
            new_file = _resolve_source_path(new_dir, rel_path)

            if not old_file and not new_file:
                continue

            old_lines = _read_file_lines(old_file) if old_file else []
            new_lines = _read_file_lines(new_file) if new_file else []

            # Skip if identical
            if old_lines == new_lines:
                continue

            diff_lines = list(difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"a/{rel_path} ({old_pkg_name})",
                tofile=f"b/{rel_path} ({new_pkg_name})",
                lineterm=""
            ))

            if not diff_lines:
                continue

            added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
            hunks = sum(1 for l in diff_lines if l.startswith("@@"))

            truncated = False
            if len(diff_lines) > MAX_DIFF_LINES:
                diff_lines = diff_lines[:MAX_DIFF_LINES]
                truncated = True

            results.append({
                "patch_relative": rel_path,
                "source_file": str(old_file) if old_file else None,
                "patch_file": str(new_file) if new_file else None,
                "package": old_pkg_name,
                "new_package": new_pkg_name,
                "component": _detect_component(rel_path),
                "match_type": "version_comparison",
                "stats": {
                    "added": added,
                    "removed": removed,
                    "hunks": hunks,
                    "source_lines": len(old_lines),
                    "patch_lines": len(new_lines),
                    "source_size": old_file.stat().st_size if old_file else 0,
                    "patch_size": new_file.stat().st_size if new_file else 0,
                },
                "diff": "\n".join(diff_lines),
                "truncated": truncated,
                "is_new_file": old_file is None,
            })
    else:
        # Broad comparison: scan decompiled/ and PlatformJS/intermax/
        results = _diff_all_sources(old_dir, new_dir, old_pkg_name, new_pkg_name)

    return results


def _detect_component(rel_path):
    """Detect component from relative source path."""
    if rel_path.startswith("intermax/"):
        return "PlatformJS-frontend"
    if rel_path.startswith(("com/exem/platform/", "com/exem/intermax/")):
        return "PlatformJS-backend"
    if rel_path.startswith(("com/exem/jspd/", "org/bsp/")):
        return "JSPD"
    if rel_path.startswith("jdg/"):
        return "DataGather"
    return "unknown"


def _diff_all_sources(old_dir, new_dir, old_pkg_name, new_pkg_name):
    """Diff all source files between two packages.

    Scans decompiled/ and PlatformJS/intermax/ directories.
    Limited to MAX_DIFF_FILES files.
    """
    old_root = _find_intermax_root(old_dir)
    new_root = _find_intermax_root(new_dir)
    if not old_root or not new_root:
        return []

    # Collect source files from new package (these are the "changed" files)
    source_dirs = [
        ("decompiled", [".java", ".cs"]),
        (str(Path("PlatformJS") / "intermax"), [".js", ".html", ".css"]),
    ]

    changed_files = []

    for subdir, extensions in source_dirs:
        new_src = new_root / subdir
        old_src = old_root / subdir
        if not new_src.exists() or not old_src.exists():
            continue

        for new_file in new_src.rglob("*"):
            if not new_file.is_file():
                continue
            if new_file.suffix.lower() not in extensions:
                continue

            rel = new_file.relative_to(new_root)
            old_file = old_root / rel

            if not old_file.exists():
                changed_files.append((str(rel), None, new_file))
                continue

            # Quick size check
            if old_file.stat().st_size != new_file.stat().st_size:
                changed_files.append((str(rel), old_file, new_file))
                continue

            # Content check (only if same size)
            try:
                if old_file.read_bytes() != new_file.read_bytes():
                    changed_files.append((str(rel), old_file, new_file))
            except OSError:
                pass

    if not changed_files:
        return []

    # Limit
    if len(changed_files) > MAX_DIFF_FILES:
        log(f"  Found {len(changed_files)} changed files, limiting to {MAX_DIFF_FILES}")
        changed_files = changed_files[:MAX_DIFF_FILES]

    results = []
    for rel_str, old_file, new_file in changed_files:
        old_lines = _read_file_lines(old_file) if old_file else []
        new_lines = _read_file_lines(new_file) if new_file else []

        # Convert Windows paths to forward slashes for display
        rel_display = rel_str.replace("\\", "/")

        diff_lines = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{rel_display} ({old_pkg_name})",
            tofile=f"b/{rel_display} ({new_pkg_name})",
            lineterm=""
        ))

        if not diff_lines:
            continue

        added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
        hunks = sum(1 for l in diff_lines if l.startswith("@@"))

        truncated = len(diff_lines) > MAX_DIFF_LINES
        if truncated:
            diff_lines = diff_lines[:MAX_DIFF_LINES]

        results.append({
            "patch_relative": rel_display,
            "source_file": str(old_file) if old_file else None,
            "patch_file": str(new_file),
            "package": old_pkg_name,
            "new_package": new_pkg_name,
            "component": _detect_component(rel_display),
            "match_type": "version_comparison",
            "stats": {
                "added": added,
                "removed": removed,
                "hunks": hunks,
                "source_lines": len(old_lines),
                "patch_lines": len(new_lines),
                "source_size": old_file.stat().st_size if old_file else 0,
                "patch_size": new_file.stat().st_size,
            },
            "diff": "\n".join(diff_lines),
            "truncated": truncated,
            "is_new_file": old_file is None,
        })

    return results


# ---------------------------------------------------------------------------
# Output generation (compatible with patch_diff.py format)
# ---------------------------------------------------------------------------

def _generate_markdown(task_id, old_pkg, new_pkg, diffs):
    """Generate patch_diff.md in the same format as patch_diff.py."""
    lines = [
        f"# Version Diff: {task_id}",
        "",
        f"**생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**비교**: `{old_pkg}` → `{new_pkg}`",
        "",
        "## 변경 파일 요약",
        "",
        "| # | 파일 | 컴포넌트 | +추가 | -삭제 |",
        "|---|------|---------|-------|-------|",
    ]

    for i, d in enumerate(diffs, 1):
        rel = d["patch_relative"]
        comp = d.get("component", "-")
        added = d["stats"]["added"]
        removed = d["stats"]["removed"]
        lines.append(f"| {i} | `{rel}` | {comp} | +{added} | -{removed} |")

    lines.append("")
    lines.append("## 상세 Diff")
    lines.append("")

    for i, d in enumerate(diffs, 1):
        rel = d["patch_relative"]
        stats = d["stats"]
        lines.append(f"### {i}. `{rel}`")
        lines.append("")

        if d["is_new_file"]:
            lines.append("> **새 파일** (이전 버전에 없음)")
        else:
            lines.append(f"- 이전: {stats['source_lines']}줄 ({stats['source_size']:,} bytes) — {old_pkg}")
            lines.append(f"- 이후: {stats['patch_lines']}줄 ({stats['patch_size']:,} bytes) — {new_pkg}")
            lines.append(f"- 변경: +{stats['added']} / -{stats['removed']} ({stats['hunks']} hunks)")

        lines.append("")
        if d["diff"]:
            lines.append("```diff")
            lines.append(d["diff"])
            lines.append("```")
        else:
            lines.append("> (변경 없음)")

        if d["truncated"]:
            lines.append("")
            lines.append(f"> **참고**: diff가 {MAX_DIFF_LINES}줄을 초과하여 잘렸습니다.")

        lines.append("")

    return "\n".join(lines)


def _generate_json(task_id, old_pkg, new_pkg, diffs):
    """Generate patch_diff.json in the same format as patch_diff.py."""
    files = []
    for d in diffs:
        files.append({
            "patch_file": d.get("patch_file"),
            "patch_relative": d["patch_relative"],
            "source_file": d.get("source_file"),
            "package": d.get("package"),
            "new_package": d.get("new_package"),
            "component": d.get("component"),
            "target_version": None,
            "match_type": "version_comparison",
            "stats": d["stats"],
            "is_new_file": d["is_new_file"],
            "truncated": d["truncated"],
            "diff": d["diff"],
        })

    return {
        "task_id": task_id,
        "generated_at": datetime.now().isoformat(),
        "diff_type": "version_comparison",
        "old_package": old_pkg,
        "new_package": new_pkg,
        "patch_notes": [],
        "jars": [],
        "archives": [],
        "file_count": len(files),
        "total_added": sum(f["stats"]["added"] for f in files),
        "total_removed": sum(f["stats"]["removed"] for f in files),
        "files": files,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_version_diff(task_id):
    """Main entry point: generate version diff for a task.

    1. Find analyzed package from context.md/report.md
    2. Find newer package version in inventory
    3. Extract relevant files from report
    4. Generate diffs
    5. Save patch_diff.md / patch_diff.json

    Returns dict with {old_pkg, new_pkg, file_count} or None.
    """
    task_dir = TASKS_DIR / task_id
    if not task_dir.exists():
        log(f"Task directory not found: {task_dir}")
        return None

    # Step 1: Find analyzed package
    old_pkg = find_analyzed_package(task_dir)
    if not old_pkg:
        log("Could not determine analyzed package from report/context")
        return None
    log(f"Analyzed package: {old_pkg}")

    # Step 2: Find newer package
    inventory = generate_inventory()
    new_pkg = find_newer_package(old_pkg, inventory)
    if not new_pkg:
        log(f"No newer package found for {old_pkg}")
        return None
    log(f"Newer package found: {new_pkg}")

    # Step 3: Find relevant files
    relevant = find_relevant_files(task_dir)
    if relevant:
        log(f"Found {len(relevant)} relevant files from report/context")
    else:
        log("No specific files found, will compare all sources")

    # Step 4: Generate diffs
    diffs = diff_packages(old_pkg, new_pkg, relevant_files=relevant or None)
    if not diffs:
        log("No differences found between versions")
        return None
    log(f"Generated {len(diffs)} file diffs")

    # Step 5: Save outputs
    md_output = _generate_markdown(task_id, old_pkg, new_pkg, diffs)
    md_path = task_dir / "patch_diff.md"
    md_path.write_text(md_output, encoding="utf-8")
    log(f"Written: {md_path}")

    json_output = _generate_json(task_id, old_pkg, new_pkg, diffs)
    json_path = task_dir / "patch_diff.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    log(f"Written: {json_path}")

    return {
        "old_pkg": old_pkg,
        "new_pkg": new_pkg,
        "file_count": len(diffs),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Version Diff Generator")
    parser.add_argument("--task-id", required=True, help="Task ID (e.g. IMX-9227)")
    parser.add_argument("--dry-run", action="store_true", help="Show analysis without generating files")
    args = parser.parse_args()

    task_id = args.task_id
    task_dir = TASKS_DIR / task_id

    if not task_dir.exists():
        log(f"Error: Task directory not found: {task_dir}")
        sys.exit(1)

    old_pkg = find_analyzed_package(task_dir)
    log(f"Analyzed package: {old_pkg or '(not found)'}")

    if old_pkg:
        inventory = generate_inventory()
        new_pkg = find_newer_package(old_pkg, inventory)
        log(f"Newer package: {new_pkg or '(not found)'}")

        relevant = find_relevant_files(task_dir)
        log(f"Relevant files: {len(relevant)}")
        for f in relevant[:10]:
            log(f"  - {f}")
        if len(relevant) > 10:
            log(f"  ... and {len(relevant) - 10} more")

    if args.dry_run:
        log("Dry run complete.")
        return

    result = generate_version_diff(task_id)
    if result:
        log(f"Version diff: {result['old_pkg']} → {result['new_pkg']} ({result['file_count']} files)")
    else:
        log("No version diff generated")
        sys.exit(1)


if __name__ == "__main__":
    main()
