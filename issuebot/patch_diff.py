#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch Diff Generator
Detects patch files in task directories, matches them against existing source in packages/,
and generates unified diffs for AI-powered patch review.

Usage:
    python issuebot/patch_diff.py --task-id IMX-9380
    python issuebot/patch_diff.py --task-id IMX-9380 --output-json
    python issuebot/patch_diff.py --task-id IMX-9380 --dry-run
"""

import os
import re
import sys
import json
import difflib
import zipfile
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.absolute()
ROOT_DIR = SCRIPT_DIR.parent

try:
    from .inventory import parse_version_tuple
except ImportError:
    # Direct execution fallback
    sys.path.insert(0, str(SCRIPT_DIR))
    from inventory import parse_version_tuple  # type: ignore[import-untyped]

with open(ROOT_DIR / "config" / "config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

TASKS_DIR = ROOT_DIR / config.get("tasks_dir", "tasks")
PACKAGES_DIR = ROOT_DIR / config.get("packages_dir", "packages")
INVENTORY_FILE = PACKAGES_DIR / "inventory.json"

# Standard files/dirs to skip when scanning for patches
STANDARD_FILES = {
    "task.json", "report.md", "context.md",
    "patch_diff.md", "patch_diff.json", "patch_review.md",
    "chat_history.json", "chat_sessions.json",
}
STANDARD_DIRS = {"images", ".patch_temp", "chat_files", "chat_uploads"}

# Directory names that indicate actual InterMax source roots
KNOWN_SOURCE_ROOTS = {"intermax", "com", "org", "jdg", "webapp", "web-inf", "meta-inf", "src"}

# Patch note filename patterns (case-insensitive)
PATCH_NOTE_PATTERNS = [
    re.compile(r"패치노트", re.IGNORECASE),
    re.compile(r"patch.?note", re.IGNORECASE),
    re.compile(r"release.?note", re.IGNORECASE),
]

# Path prefix mapping: patch path prefix -> (component, packages/ relative location)
PATH_PREFIX_MAP = [
    ("intermax/", "PlatformJS-frontend", "{pkg}/InterMax*/PlatformJS/intermax/"),
    ("jdg/", "DataGather", "{pkg}/InterMax*/decompiled/datagather/jdg/"),
    ("com/exem/platform/", "PlatformJS-backend", "{pkg}/InterMax*/decompiled/PlatformJS/com/exem/platform/"),
    ("com/exem/intermax/", "PlatformJS-backend", "{pkg}/InterMax*/decompiled/PlatformJS/com/exem/intermax/"),
    ("com/exem/jspd/", "JSPD", "{pkg}/InterMax*/decompiled/jspd/com/exem/jspd/"),
    ("org/bsp/", "JSPD", "{pkg}/InterMax*/decompiled/jspd/org/bsp/"),
]

# File extensions recognized as source code
SOURCE_EXTENSIONS = {".js", ".java", ".xml", ".json", ".properties", ".conf", ".css", ".html", ".jsp", ".sql"}

# Max diff lines per file (default)
DEFAULT_MAX_DIFF_LINES = 500


def log(message):
    print(f"[patch_diff] {message}")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Patch Note Parsing
# ---------------------------------------------------------------------------

def is_patch_note(filename):
    """Check if filename looks like a patch note"""
    for pattern in PATCH_NOTE_PATTERNS:
        if pattern.search(filename):
            return True
    return False


def parse_patch_note(filepath):
    """Parse patch note file and extract metadata"""
    info = {
        "file": str(filepath),
        "author": None,
        "date": None,
        "version": None,
        "content": [],
    }

    try:
        text = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = filepath.read_text(encoding="euc-kr")
        except Exception:
            return info

    for line in text.splitlines():
        line_stripped = line.strip()

        # Author
        if "작업자" in line_stripped:
            m = re.search(r"작업자\s*[:：]\s*(.+)", line_stripped)
            if m:
                info["author"] = m.group(1).strip()

        # Date
        if "작업일시" in line_stripped or "작업일" in line_stripped:
            m = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", line_stripped)
            if m:
                info["date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

        # Version
        if "반영버전" in line_stripped or "반영 버전" in line_stripped:
            # The version might be on this line or the next non-empty line
            m = re.search(r"(\d+\.\d+\.\d+\.\d+(?:-[\w.]+)?)", line_stripped)
            if m:
                info["version"] = m.group(1)

        # Version on a standalone line (for multi-line patch notes)
        if info["version"] is None:
            m = re.search(r"^\s*-?\s*(\d+\.\d+\.\d+\.\d+(?:-[\w.]+)?)", line_stripped)
            if m and ("패치" in text[:text.find(line_stripped)] or "반영" in text[:text.find(line_stripped)]):
                info["version"] = m.group(1)

        # Content lines (처리내용, 패치내용)
        if line_stripped.startswith("->") or line_stripped.startswith("→"):
            info["content"].append(line_stripped)

    return info


# ---------------------------------------------------------------------------
# Patch Detection
# ---------------------------------------------------------------------------

def detect_patches(task_dir):
    """Detect patch files/directories in task directory.

    Scans tasks/{ID}/patches/ (from fetch_doc.py) first, then task root.

    Returns dict with:
        - patch_dirs: list of patch directory paths
        - patch_files: list of individual source files (with relative paths)
        - patch_notes: list of parsed patch note info
        - archives: list of unextracted archives
        - jars: list of JAR files needing decompilation
    """
    result = {
        "patch_dirs": [],
        "patch_files": [],
        "patch_notes": [],
        "archives": [],
        "jars": [],
    }

    # Priority: scan patches/ directory first (created by fetch_doc.py)
    patches_dir = task_dir / "patches"
    if patches_dir.exists() and patches_dir.is_dir():
        log(f"  Scanning patches/ directory (from fetch_doc.py)")
        for item in sorted(patches_dir.iterdir()):
            name = item.name
            if name == "doc_content.md":
                continue
            if item.is_file():
                ext = item.suffix.lower()
                if ext in (".zip", ".tar", ".gz", ".7z"):
                    result["archives"].append(str(item))
                elif ext == ".jar":
                    result["jars"].append(str(item))
                elif ext in SOURCE_EXTENSIONS:
                    result["patch_files"].append({
                        "absolute": str(item),
                        "relative": name,
                    })
            elif item.is_dir():
                result["patch_dirs"].append(str(item))

    # Also scan task root for direct patch files
    for item in sorted(task_dir.iterdir()):
        name = item.name

        # Skip standard files and directories
        if name in STANDARD_FILES:
            continue
        if name in STANDARD_DIRS:
            continue
        if name == "patches":
            continue  # Already scanned above

        if item.is_file():
            ext = item.suffix.lower()
            if ext in (".zip", ".tar", ".gz", ".7z"):
                result["archives"].append(str(item))
            elif ext == ".jar":
                result["jars"].append(str(item))
            elif ext in SOURCE_EXTENSIONS:
                result["patch_files"].append({
                    "absolute": str(item),
                    "relative": name,
                })
        elif item.is_dir():
            # Only scan directories that look like InterMax source roots
            if name.lower() in KNOWN_SOURCE_ROOTS:
                result["patch_dirs"].append(str(item))

    # Recursively scan patch directories for source files, patch notes, JARs
    for patch_dir_str in result["patch_dirs"]:
        patch_dir = Path(patch_dir_str)
        _scan_patch_dir(patch_dir, patch_dir, result)

    return result


def _scan_patch_dir(base_dir, current_dir, result):
    """Recursively scan a patch directory for files"""
    for item in sorted(current_dir.iterdir()):
        if item.is_file():
            ext = item.suffix.lower()

            # Patch note
            if is_patch_note(item.name):
                note = parse_patch_note(item)
                result["patch_notes"].append(note)
                continue

            # JAR
            if ext == ".jar":
                result["jars"].append(str(item))
                continue

            # ZIP (auto-extract)
            if ext == ".zip":
                extract_dir = item.parent / item.stem
                if not extract_dir.exists():
                    try:
                        _extract_zip(item, extract_dir)
                        log(f"  Extracted ZIP: {item.name} -> {extract_dir.name}/")
                        _scan_patch_dir(base_dir, extract_dir, result)
                    except zipfile.BadZipFile:
                        log(f"  Warning: {item.name} is not a valid ZIP")
                        result["archives"].append(str(item))
                else:
                    _scan_patch_dir(base_dir, extract_dir, result)
                continue

            # Source file
            if ext in SOURCE_EXTENSIONS or ext in (".txt", ".log"):
                # Skip non-source text files that aren't in a meaningful path
                if ext in (".txt", ".log") and not _looks_like_source_path(item, base_dir):
                    continue

                rel_path = _compute_source_relative_path(item, base_dir)
                if rel_path:
                    result["patch_files"].append({
                        "absolute": str(item),
                        "relative": rel_path,
                    })

        elif item.is_dir():
            _scan_patch_dir(base_dir, item, result)


def _extract_zip(zip_path, extract_dir):
    """Extract ZIP file"""
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)


def _looks_like_source_path(filepath, base_dir):
    """Check if a .txt/.log file is in a path that looks like source code"""
    rel = filepath.relative_to(base_dir)
    parts = rel.parts
    # Source-like directories
    source_indicators = {"com", "org", "jdg", "intermax", "src", "java", "webapp"}
    return any(p.lower() in source_indicators for p in parts)


def _compute_source_relative_path(filepath, base_dir):
    """Compute the meaningful relative path for a source file.

    Strips the patch directory wrapper and finds the source-meaningful path.
    For example:
      base_dir/[Intermax][foo]20260220_01/intermax/PA/view/Foo.js
      -> intermax/PA/view/Foo.js
    """
    rel = filepath.relative_to(base_dir)
    parts = list(rel.parts)

    # Known source root markers
    source_roots = {"intermax", "com", "org", "jdg", "webapp", "WEB-INF", "META-INF", "src"}

    for i, part in enumerate(parts):
        if part.lower() in {s.lower() for s in source_roots}:
            return "/".join(parts[i:])

    # Fallback: use just the filename
    return filepath.name


# ---------------------------------------------------------------------------
# JAR Decompilation
# ---------------------------------------------------------------------------

def decompile_jar(jar_path, task_dir):
    """Decompile a JAR file using CFR and return path to decompiled sources"""
    temp_dir = task_dir / ".patch_temp" / Path(jar_path).stem
    if temp_dir.exists():
        log(f"  Decompiled output already exists: {temp_dir}")
        return temp_dir

    temp_dir.mkdir(parents=True, exist_ok=True)

    # Find CFR
    cfr_jar = ROOT_DIR / "tools" / "cfr-0.152.jar"
    if not cfr_jar.exists():
        log(f"  Warning: CFR not found at {cfr_jar}, skipping JAR decompilation")
        return None

    # Find Java
    java_cmd = _find_java()
    if not java_cmd:
        log("  Warning: Java not found, skipping JAR decompilation")
        return None

    log(f"  Decompiling JAR: {Path(jar_path).name}")
    try:
        result = subprocess.run(
            [java_cmd, "-jar", str(cfr_jar), str(jar_path), "--outputdir", str(temp_dir)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            log(f"  Warning: CFR decompilation failed (exit {result.returncode})")
            return None
        log(f"  Decompilation complete: {temp_dir}")
        return temp_dir
    except subprocess.TimeoutExpired:
        log("  Warning: JAR decompilation timed out")
        return None
    except FileNotFoundError:
        log(f"  Warning: Java command not found: {java_cmd}")
        return None


def _find_java():
    """Find java executable"""
    # Check JAVA_HOME
    java_home = os.environ.get("JAVA_HOME", "")
    if java_home:
        java_bin = Path(java_home) / "bin" / "java"
        if java_bin.exists():
            return str(java_bin)

    # Check PATH
    try:
        result = subprocess.run(
            ["java", "-version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return "java"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


# ---------------------------------------------------------------------------
# Source Matching
# ---------------------------------------------------------------------------

def load_inventory():
    """Load packages/inventory.json"""
    if not INVENTORY_FILE.exists():
        log("Warning: inventory.json not found, run: python issuebot/inventory.py")
        return {"packages": []}

    with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_version_from_task(task_data):
    """Extract version info from task.json custom_fields"""
    cf = task_data.get("custom_fields", {})
    versions = {}

    for field_name, value in cf.items():
        if not value or "Version" not in field_name:
            continue
        # Extract version number from value like "5.4.7.4 패키지" or "5.4.12.0-alpha.2"
        m = re.search(r"(\d+\.\d+\.\d+\.\d+(?:-[\w.]+)?)", str(value))
        if m:
            versions[field_name] = m.group(1)

    return versions


def _try_direct_package_match(target_version, component):
    """Try to find package by direct filesystem glob (when inventory is outdated).

    Looks for packages/package_v{version}/ directory.
    """
    base_version = target_version.split("-")[0]  # Strip -patch.N, -alpha.N etc.
    patterns = [
        f"package_v{target_version}",
        f"package_v{base_version}",
        f"package_v{base_version}*",
    ]

    for pattern in patterns:
        matches = list(PACKAGES_DIR.glob(pattern))
        matches = [m for m in matches if m.is_dir() and m.name != "_incoming"]
        if matches:
            return matches[0].name

    return None


def find_matching_package(target_version, component, inventory):
    """Find the best matching package for a given version and component.

    Returns (package_name, match_type) or (None, None)
    """
    if target_version:
        target_tuple = parse_version_tuple(target_version)
        target_major, target_minor, target_patch, target_build = target_tuple[:4]

        # Step 0: Try direct filesystem match (inventory may be out of date)
        direct_match = _try_direct_package_match(target_version, component)
        if direct_match:
            return direct_match, "exact"
    else:
        target_tuple = None

    # Component to inventory component name mapping
    component_names = {
        "PlatformJS-frontend": ["PlatformJS-frontend"],
        "PlatformJS-backend": ["PlatformJS"],
        "DataGather": ["datagather"],
        "JSPD": ["jspd"],
    }
    required_components = component_names.get(component, [component])

    candidates = []
    for pkg in inventory.get("packages", []):
        # Check component availability
        has_component = any(c in pkg.get("components", []) for c in required_components)
        if not has_component:
            continue

        pkg_version = pkg.get("version", "unknown")
        if pkg_version == "unknown":
            continue

        pkg_tuple = parse_version_tuple(pkg_version)
        candidates.append((pkg, pkg_tuple))

    if not candidates:
        return None, None

    # No target version — use the latest package with matching component
    if target_tuple is None:
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]["name"], "latest"

    # 1. Exact match
    for pkg, pt in candidates:
        if pt[:4] == (target_major, target_minor, target_patch, target_build) and pt[4] == target_tuple[4]:
            return pkg["name"], "exact"

    # 2. Same major.minor.patch, closest build
    same_patch = [(pkg, pt) for pkg, pt in candidates
                  if pt[0] == target_major and pt[1] == target_minor and pt[2] == target_patch]
    if same_patch:
        same_patch.sort(key=lambda x: abs(x[1][3] - target_build))
        return same_patch[0][0]["name"], "nearest"

    # 3. Same major.minor, latest
    same_minor = [(pkg, pt) for pkg, pt in candidates
                  if pt[0] == target_major and pt[1] == target_minor]
    if same_minor:
        same_minor.sort(key=lambda x: x[1], reverse=True)
        return same_minor[0][0]["name"], "nearest"

    # 4. Latest overall
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]["name"], "latest"


def match_source(patch_file, task_versions, inventory):
    """Match a patch file to its original source in packages/.

    Args:
        patch_file: dict with 'absolute' and 'relative' keys
        task_versions: dict from extract_version_from_task()
        inventory: inventory data

    Returns dict with match info or None
    """
    rel_path = patch_file["relative"]

    # Determine component and base path from prefix
    component = None
    pkg_path_template = None

    for prefix, comp, template in PATH_PREFIX_MAP:
        if rel_path.startswith(prefix):
            component = comp
            pkg_path_template = template
            break

    if not component:
        # No known InterMax path prefix — cannot meaningfully match
        return {
            "patch_file": patch_file["absolute"],
            "patch_relative": rel_path,
            "source_file": None,
            "package": None,
            "component": None,
            "target_version": None,
            "match_type": "not_found",
        }

    # Determine target version based on component
    target_version = None
    if component in ("PlatformJS-frontend", "PlatformJS-backend"):
        target_version = task_versions.get("PlatformJS Version")
    elif component == "DataGather":
        target_version = task_versions.get("DataGather Version")
    elif component == "JSPD":
        target_version = task_versions.get("Agent Version")

    # If no version from custom_fields, try patch note version
    if not target_version:
        # Fall back to any available version
        for v in task_versions.values():
            target_version = v
            break

    # Find matching package
    pkg_name, match_type = find_matching_package(target_version, component, inventory)

    if not pkg_name:
        # Fallback: glob search by filename
        return _fallback_glob_match(patch_file, rel_path)

    # Build the expected source path
    source_path = _find_source_in_package(pkg_name, rel_path, component)

    if source_path:
        return {
            "patch_file": patch_file["absolute"],
            "patch_relative": rel_path,
            "source_file": str(source_path),
            "package": pkg_name,
            "component": component,
            "target_version": target_version,
            "match_type": match_type,
        }

    # Fallback: glob search
    return _fallback_glob_match(patch_file, rel_path)


def _find_source_in_package(pkg_name, rel_path, component):
    """Find the source file in a specific package"""
    pkg_dir = PACKAGES_DIR / pkg_name

    # Try direct path construction based on component
    if component == "PlatformJS-frontend":
        # rel_path: intermax/PA/view/TxnDetail/XMTransactionPath.js
        # source:   {pkg}/InterMax*/PlatformJS/{rel_path}
        candidates = list(pkg_dir.glob(f"InterMax*/PlatformJS/{rel_path}"))
        if candidates:
            return candidates[0]

    elif component == "PlatformJS-backend":
        candidates = list(pkg_dir.glob(f"InterMax*/decompiled/PlatformJS/{rel_path}"))
        if candidates:
            return candidates[0]

    elif component == "DataGather":
        candidates = list(pkg_dir.glob(f"InterMax*/decompiled/datagather/{rel_path}"))
        if candidates:
            return candidates[0]

    elif component == "JSPD":
        candidates = list(pkg_dir.glob(f"InterMax*/decompiled/jspd/{rel_path}"))
        if candidates:
            return candidates[0]

    # Try broader search within the package — only if we have directory context
    filename = Path(rel_path).name
    rel_parts = set(Path(rel_path).parts[:-1])  # directory parts only

    if not rel_parts:
        # Bare filename (no directory context) — skip rglob to avoid false matches
        return None

    candidates = list(pkg_dir.rglob(filename))
    # Require at least one directory part to match
    candidates = [c for c in candidates if rel_parts & set(c.parts)]

    if len(candidates) == 1:
        return candidates[0]

    if candidates:
        best = max(candidates, key=lambda c: len(rel_parts & set(c.parts)))
        return best

    return None


def _fallback_glob_match(patch_file, rel_path):
    """Disabled — cross-package filename glob produced false matches
    (e.g. pom.xml matching PeakVisor, application.properties matching
    unrelated products). Always returns not_found now.
    """
    return {
        "patch_file": patch_file["absolute"],
        "patch_relative": rel_path,
        "source_file": None,
        "package": None,
        "component": None,
        "target_version": None,
        "match_type": "not_found",
    }


# ---------------------------------------------------------------------------
# Diff Generation
# ---------------------------------------------------------------------------

def read_file_lines(filepath):
    """Read file and return lines, handling encoding"""
    for encoding in ("utf-8", "euc-kr", "cp949", "latin-1"):
        try:
            with open(filepath, "r", encoding=encoding) as f:
                return f.readlines()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return []


def generate_diff(match, max_lines=DEFAULT_MAX_DIFF_LINES):
    """Generate unified diff between source and patch file.

    Returns dict with diff info and statistics.
    """
    patch_path = match["patch_file"]
    source_path = match.get("source_file")

    patch_lines = read_file_lines(patch_path)

    if source_path and Path(source_path).exists():
        source_lines = read_file_lines(source_path)
    else:
        source_lines = []

    # Generate unified diff
    source_label = match.get("source_file", "/dev/null")
    patch_label = match["patch_file"]

    diff_lines = list(difflib.unified_diff(
        source_lines, patch_lines,
        fromfile=f"a/{match['patch_relative']} (기존: {match.get('package', 'N/A')})",
        tofile=f"b/{match['patch_relative']} (패치)",
        lineterm=""
    ))

    # Statistics (always computed on full diff)
    added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    total_hunks = sum(1 for line in diff_lines if line.startswith("@@"))

    stats = {
        "added": added,
        "removed": removed,
        "hunks": total_hunks,
        "source_lines": len(source_lines),
        "patch_lines": len(patch_lines),
        "source_size": Path(source_path).stat().st_size if source_path and Path(source_path).exists() else 0,
        "patch_size": Path(patch_path).stat().st_size,
    }

    # Truncate diff if too long
    truncated = False
    if max_lines and len(diff_lines) > max_lines:
        diff_lines = diff_lines[:max_lines]
        truncated = True

    return {
        "diff": "\n".join(diff_lines),
        "stats": stats,
        "truncated": truncated,
        "is_new_file": source_path is None or not Path(source_path).exists() if source_path else True,
    }


# ---------------------------------------------------------------------------
# Output Generation
# ---------------------------------------------------------------------------

def generate_markdown_output(task_id, patch_info, matches, diffs, patch_notes):
    """Generate patch_diff.md"""
    lines = []
    lines.append(f"# Patch Diff: {task_id}")
    lines.append(f"")
    lines.append(f"**생성일**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"")

    # Patch notes
    if patch_notes:
        lines.append("## 패치노트 정보")
        for note in patch_notes:
            if note.get("author"):
                lines.append(f"- **작업자**: {note['author']}")
            if note.get("date"):
                lines.append(f"- **작업일**: {note['date']}")
            if note.get("version"):
                lines.append(f"- **반영버전**: {note['version']}")
            if note.get("content"):
                lines.append(f"- **처리내용**:")
                for c in note["content"]:
                    lines.append(f"  - {c}")
        lines.append("")

    # Summary table
    lines.append("## 변경 파일 요약")
    lines.append("")
    lines.append("| # | 파일 | 컴포넌트 | 매칭 패키지 | 매칭 유형 | +추가 | -삭제 |")
    lines.append("|---|------|---------|------------|----------|-------|-------|")

    for i, (match, diff) in enumerate(zip(matches, diffs), 1):
        rel = match["patch_relative"]
        comp = match.get("component") or "-"
        pkg = match.get("package") or "-"
        mt = match.get("match_type") or "-"
        added = diff["stats"]["added"]
        removed = diff["stats"]["removed"]
        lines.append(f"| {i} | `{rel}` | {comp} | {pkg} | {mt} | +{added} | -{removed} |")

    lines.append("")

    # Unmatched JARs
    if patch_info.get("jars"):
        lines.append("## JAR 파일 (디컴파일 필요)")
        for jar in patch_info["jars"]:
            lines.append(f"- `{Path(jar).name}`")
        lines.append("")

    # Unmatched archives
    if patch_info.get("archives"):
        lines.append("## 미처리 아카이브")
        for arc in patch_info["archives"]:
            lines.append(f"- `{Path(arc).name}`")
        lines.append("")

    # Diffs
    lines.append("## 상세 Diff")
    lines.append("")

    for i, (match, diff) in enumerate(zip(matches, diffs), 1):
        rel = match["patch_relative"]
        stats = diff["stats"]

        lines.append(f"### {i}. `{rel}`")
        lines.append("")

        if diff["is_new_file"]:
            lines.append("> **새 파일** (기존 소스 없음)")
            lines.append("")
        else:
            lines.append(f"- 기존: {stats['source_lines']}줄 ({stats['source_size']:,} bytes)")
            lines.append(f"- 패치: {stats['patch_lines']}줄 ({stats['patch_size']:,} bytes)")
            lines.append(f"- 변경: +{stats['added']} / -{stats['removed']} ({stats['hunks']} hunks)")
            lines.append("")

        if diff["diff"]:
            lines.append("```diff")
            lines.append(diff["diff"])
            lines.append("```")
        else:
            lines.append("> (변경 없음)")

        if diff["truncated"]:
            lines.append("")
            lines.append(f"> **참고**: diff가 {DEFAULT_MAX_DIFF_LINES}줄을 초과하여 잘렸습니다. 전체 diff는 `--max-diff-lines 0`으로 확인하세요.")

        lines.append("")

    return "\n".join(lines)


def generate_json_output(task_id, patch_info, matches, diffs, patch_notes):
    """Generate patch_diff.json for agent consumption"""
    files = []
    for match, diff in zip(matches, diffs):
        files.append({
            "patch_file": match["patch_file"],
            "patch_relative": match["patch_relative"],
            "source_file": match.get("source_file"),
            "package": match.get("package"),
            "component": match.get("component"),
            "target_version": match.get("target_version"),
            "match_type": match.get("match_type"),
            "stats": diff["stats"],
            "is_new_file": diff["is_new_file"],
            "truncated": diff["truncated"],
            "diff": diff["diff"],
        })

    return {
        "task_id": task_id,
        "generated_at": datetime.now().isoformat(),
        "patch_notes": patch_notes,
        "jars": patch_info.get("jars", []),
        "archives": patch_info.get("archives", []),
        "file_count": len(files),
        "total_added": sum(f["stats"]["added"] for f in files),
        "total_removed": sum(f["stats"]["removed"] for f in files),
        "files": files,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Patch Diff Generator")
    parser.add_argument("--task-id", required=True, help="Task ID (e.g., IMX-9380)")
    parser.add_argument("--output-json", action="store_true", help="Also generate patch_diff.json")
    parser.add_argument("--dry-run", action="store_true", help="Show detection/matching results without generating diff")
    parser.add_argument("--max-diff-lines", type=int, default=DEFAULT_MAX_DIFF_LINES,
                        help=f"Max diff lines per file (0=unlimited, default={DEFAULT_MAX_DIFF_LINES})")

    args = parser.parse_args()
    task_id = args.task_id

    task_dir = TASKS_DIR / task_id
    if not task_dir.exists():
        log(f"Error: Task directory not found: {task_dir}")
        sys.exit(1)

    task_json_path = task_dir / "task.json"
    if not task_json_path.exists():
        log(f"Error: task.json not found in {task_dir}")
        sys.exit(1)

    # Load task data
    with open(task_json_path, "r", encoding="utf-8") as f:
        task_data = json.load(f)

    log(f"Task: {task_id} - {task_data.get('name', '')}")

    # Step 1: Detect patches
    log("Step 1: Detecting patch files...")
    patch_info = detect_patches(task_dir)

    n_files = len(patch_info["patch_files"])
    n_notes = len(patch_info["patch_notes"])
    n_jars = len(patch_info["jars"])
    n_archives = len(patch_info["archives"])

    log(f"  Found: {n_files} source files, {n_notes} patch notes, {n_jars} JARs, {n_archives} archives")

    if n_files == 0 and n_jars == 0:
        log("No patch files detected. Nothing to do.")
        sys.exit(0)

    # Print patch notes
    for note in patch_info["patch_notes"]:
        if note.get("author"):
            log(f"  Patch Note - Author: {note['author']}, Date: {note.get('date', '?')}, Version: {note.get('version', '?')}")

    # Step 2: Decompile JARs if needed
    if n_jars > 0:
        log("Step 2: Decompiling JARs...")
        for jar_path in patch_info["jars"]:
            decompiled_dir = decompile_jar(jar_path, task_dir)
            if decompiled_dir:
                # Scan decompiled directory for source files
                for java_file in decompiled_dir.rglob("*.java"):
                    rel = _compute_source_relative_path(java_file, decompiled_dir)
                    patch_info["patch_files"].append({
                        "absolute": str(java_file),
                        "relative": rel,
                    })

    # Step 3: Match sources
    log("Step 3: Matching against existing sources...")
    inventory = load_inventory()

    # Get version info from task.json + patch notes
    task_versions = extract_version_from_task(task_data)

    # Override with patch note version if available
    for note in patch_info["patch_notes"]:
        if note.get("version"):
            # Use patch note version for PlatformJS (most common patch target)
            if "PlatformJS Version" not in task_versions:
                task_versions["PlatformJS Version"] = note["version"]
            log(f"  Patch note version: {note['version']}")

    matches = []
    for pf in patch_info["patch_files"]:
        match = match_source(pf, task_versions, inventory)
        if match:
            matches.append(match)
            status = "MATCHED" if match["match_type"] != "not_found" else "NOT FOUND"
            log(f"  [{status}] {pf['relative']} -> {match.get('package', 'N/A')} ({match.get('match_type', 'N/A')})")

    if args.dry_run:
        log("Dry run complete. No files written.")
        return

    # Step 4: Generate diffs
    log("Step 4: Generating diffs...")
    max_lines = args.max_diff_lines if args.max_diff_lines > 0 else None
    diffs = []
    for match in matches:
        diff = generate_diff(match, max_lines=max_lines)
        diffs.append(diff)

    # Write outputs
    md_output = generate_markdown_output(task_id, patch_info, matches, diffs, patch_info["patch_notes"])
    md_path = task_dir / "patch_diff.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_output)
    log(f"Written: {md_path}")

    if args.output_json:
        json_output = generate_json_output(task_id, patch_info, matches, diffs, patch_info["patch_notes"])
        json_path = task_dir / "patch_diff.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_output, f, indent=2, ensure_ascii=False)
        log(f"Written: {json_path}")

    log("Done!")


if __name__ == "__main__":
    main()
