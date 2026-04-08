#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClickUp Doc Patch Fetcher
Finds ClickUp Docs linked to a task and downloads patch files from them.

Usage:
    python issuebot/fetch_doc.py --task-id IMX-9236
    python issuebot/fetch_doc.py --task-id IMX-9236 --dry-run
    python issuebot/fetch_doc.py --doc-id rbeb5-185442 --page-id rbeb5-3475418
"""

import os
import re
import sys
import json
import zipfile
import tarfile
import argparse
import requests
from pathlib import Path
from urllib.parse import unquote

# Get script and root directories
SCRIPT_DIR = Path(__file__).parent.absolute()
ROOT_DIR = SCRIPT_DIR.parent

# Load environment variables
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

CLICKUP_API_KEY = os.getenv("CLICKUP_API_KEY")
if not CLICKUP_API_KEY:
    print("Error: CLICKUP_API_KEY not found in .env file")
    sys.exit(1)

# Load config
with open(ROOT_DIR / "config" / "config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

TEAM_ID = config["clickup"].get("team_id", "")
WORKSPACE_ID = TEAM_ID  # v3 workspace_id == v2 team_id
BASE_URL_V2 = config["clickup"]["base_url"]
BASE_URL_V3 = "https://api.clickup.com/api/v3"
TASKS_DIR = ROOT_DIR / config.get("tasks_dir", "tasks")

HEADERS = {
    "Authorization": CLICKUP_API_KEY,
    "Content-Type": "application/json"
}

# Regex patterns for extracting Doc URLs from markdown
DOC_URL_PATTERN = re.compile(
    r"https://app\.clickup\.com/\d+/docs/([a-z0-9]+-\d+)/([a-z0-9]+-\d+)"
)

# Regex for markdown links with file URLs
# ClickUp markdown escapes brackets as \[ and \], so use lazy .+? to handle them
ATTACHMENT_LINK_PATTERN = re.compile(
    r"\[(.+?)\]\((https://t\d+\.p\.clickup-attachments\.com/[^)]+)\)"
)

# File extensions that are patch files
PATCH_EXTENSIONS = {".zip", ".tar", ".gz", ".7z", ".jar", ".js", ".java", ".xml", ".json", ".css", ".html", ".jsp"}


def log(message):
    print(f"[fetch_doc] {message}")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Task description parsing
# ---------------------------------------------------------------------------

def fetch_markdown_description(task_id):
    """Fetch task markdown_description from ClickUp API"""
    url = f"{BASE_URL_V2}/task/{task_id}"
    params = {
        "include_subtasks": "false",
        "include_markdown_description": "true",
    }

    is_custom_id = not task_id.isdigit()
    if is_custom_id:
        params["custom_task_ids"] = "true"
        if TEAM_ID:
            params["team_id"] = TEAM_ID

    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        log(f"Error: Failed to fetch task {task_id} (status {response.status_code})")
        return None

    data = response.json()
    return data.get("markdown_description", "")


def extract_doc_links(markdown_text):
    """Extract ClickUp Doc URLs from markdown description.

    Returns list of (doc_id, page_id) tuples.
    """
    if not markdown_text:
        return []

    matches = DOC_URL_PATTERN.findall(markdown_text)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for doc_id, page_id in matches:
        key = (doc_id, page_id)
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def load_local_task_description(task_id):
    """Try to load markdown_description from local task.json"""
    task_json_path = TASKS_DIR / task_id / "task.json"
    if not task_json_path.exists():
        return None

    with open(task_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("markdown_description", "")


# ---------------------------------------------------------------------------
# ClickUp v3 Docs API
# ---------------------------------------------------------------------------

def fetch_doc_info(doc_id):
    """Fetch Doc metadata"""
    url = f"{BASE_URL_V3}/workspaces/{WORKSPACE_ID}/docs/{doc_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        log(f"Error: Failed to fetch doc {doc_id} (status {response.status_code})")
        return None
    return response.json()


def fetch_page_listing(doc_id):
    """Fetch hierarchical page listing for a Doc"""
    url = f"{BASE_URL_V3}/workspaces/{WORKSPACE_ID}/docs/{doc_id}/page_listing"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        log(f"Error: Failed to fetch page listing for doc {doc_id} (status {response.status_code})")
        return []
    return response.json()


def find_page_by_task_id(pages, task_id):
    """Recursively search page listing for a page matching task_id.

    Returns page_id or None.
    """
    for page in pages:
        name = page.get("name", "")
        if task_id in name:
            return page["id"]
        # Search sub-pages
        sub_pages = page.get("pages", [])
        if sub_pages:
            result = find_page_by_task_id(sub_pages, task_id)
            if result:
                return result
    return None


def fetch_page_content(doc_id, page_id):
    """Fetch page content in markdown format"""
    url = f"{BASE_URL_V3}/workspaces/{WORKSPACE_ID}/docs/{doc_id}/pages/{page_id}"
    params = {"description_format": "text/md"}
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        log(f"Error: Failed to fetch page {page_id} (status {response.status_code})")
        return None
    return response.json()


def search_docs_by_name(search_query):
    """Search workspace docs by name"""
    url = f"{BASE_URL_V3}/workspaces/{WORKSPACE_ID}/docs"
    params = {"search": search_query}
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        log(f"Error: Doc search failed (status {response.status_code})")
        return []
    data = response.json()
    return data.get("docs", [])


# ---------------------------------------------------------------------------
# File downloading
# ---------------------------------------------------------------------------

def extract_attachment_urls(content):
    """Extract file attachment URLs from page markdown content.

    Returns list of (filename, url) tuples.
    """
    if not content:
        return []

    matches = ATTACHMENT_LINK_PATTERN.findall(content)
    results = []
    for display_name, url in matches:
        # Decode URL-encoded filename
        filename = display_name.strip()
        if not filename:
            # Extract from URL path
            url_path = unquote(url.split("/")[-1].split("?")[0])
            filename = url_path
        results.append((filename, url))
    return results


def download_file(url, save_path):
    """Download a file from URL"""
    log(f"  Downloading: {save_path.name}")
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        log(f"  Error: Download failed (status {response.status_code})")
        return False

    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    size = save_path.stat().st_size
    log(f"  Downloaded: {save_path.name} ({size:,} bytes)")
    return True


def extract_archive(archive_path, extract_dir):
    """Extract ZIP or TAR archive"""
    ext = archive_path.suffix.lower()
    extract_dir.mkdir(parents=True, exist_ok=True)

    if ext == ".zip":
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(extract_dir)
            extracted = list(extract_dir.rglob("*"))
            files = [f for f in extracted if f.is_file()]
            log(f"  Extracted ZIP: {len(files)} files -> {extract_dir.name}/")
            return True
        except zipfile.BadZipFile:
            log(f"  Warning: {archive_path.name} is not a valid ZIP")
            return False

    elif ext in (".tar", ".gz", ".tgz"):
        try:
            with tarfile.open(archive_path, "r:*") as tf:
                tf.extractall(extract_dir, filter="data")
            extracted = list(extract_dir.rglob("*"))
            files = [f for f in extracted if f.is_file()]
            log(f"  Extracted TAR: {len(files)} files -> {extract_dir.name}/")
            return True
        except tarfile.TarError:
            log(f"  Warning: {archive_path.name} is not a valid TAR")
            return False

    return False


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def extract_doc_links_from_api_comments(task_id):
    """Extract Doc URLs from comment link_preview items via ClickUp API.

    ClickUp stores Doc embeds as structured items with type="link_preview"
    in the comment array.  The comment_text field only contains flattened
    text like "Document preview rbeb5-XXXXX", losing the full URL.
    """
    log(f"  Checking comments for Doc link_preview...")
    url = f"{BASE_URL_V2}/task/{task_id}/comment"
    params = {}
    is_custom_id = not task_id.isdigit()
    if is_custom_id:
        params["custom_task_ids"] = "true"
        if TEAM_ID:
            params["team_id"] = TEAM_ID

    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        log(f"  Comments API failed (status {response.status_code})")
        return []

    doc_links = []
    for comment in response.json().get("comments", []):
        raw = comment.get("comment", [])
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, dict) and item.get("type") == "link_preview":
                lp_url = item.get("link_preview", {}).get("url", "")
                matches = DOC_URL_PATTERN.findall(lp_url)
                for doc_id, page_id in matches:
                    doc_links.append((doc_id, page_id))
    return doc_links


def extract_doc_links_from_local_comments(task_id):
    """Extract Doc URLs from local task.json comments[].doc_links."""
    task_json_path = TASKS_DIR / task_id / "task.json"
    if not task_json_path.exists():
        return []

    with open(task_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    doc_links = []
    for comment in data.get("comments", []):
        for url in comment.get("doc_links", []):
            matches = DOC_URL_PATTERN.findall(url)
            doc_links.extend(matches)
        # Also check replies
        for reply in comment.get("replies", []):
            for url in reply.get("doc_links", []):
                matches = DOC_URL_PATTERN.findall(url)
                doc_links.extend(matches)
    return doc_links


def find_doc_links_for_task(task_id):
    """Find ClickUp Doc links for a task.

    Strategy:
    1. Fetch markdown_description from API (has Doc URLs embedded)
    2. Fall back to local task.json markdown_description
    3. Check comments for Doc link_preview embeds (API)
    4. Check local task.json comments for doc_links
    5. Check known patch doc by config patch_doc_id
    6. Fall back to searching Docs by task_id name
    7. Fall back to searching "패치 파일" docs by page listing

    Returns list of (doc_id, page_id) tuples.
    """
    # Strategy 1: Fetch from API with markdown_description
    log(f"Searching for Doc links in task {task_id}...")
    md = fetch_markdown_description(task_id)
    if md:
        links = extract_doc_links(md)
        if links:
            log(f"  Found {len(links)} Doc link(s) in markdown_description")
            return links, md

    # Strategy 2: Check local task.json description
    local_md = load_local_task_description(task_id)
    if local_md:
        links = extract_doc_links(local_md)
        if links:
            log(f"  Found {len(links)} Doc link(s) in local task.json")
            return links, local_md

    # Strategy 3: Check comments for Doc link_preview (API)
    links = extract_doc_links_from_api_comments(task_id)
    if links:
        # Deduplicate
        seen = set()
        unique = []
        for pair in links:
            if pair not in seen:
                seen.add(pair)
                unique.append(pair)
        log(f"  Found {len(unique)} Doc link(s) in comment link_preview")
        return unique, md

    # Strategy 4: Check local task.json comments for doc_links
    links = extract_doc_links_from_local_comments(task_id)
    if links:
        seen = set()
        unique = []
        for pair in links:
            if pair not in seen:
                seen.add(pair)
                unique.append(pair)
        log(f"  Found {len(unique)} Doc link(s) in local comment doc_links")
        return unique, None

    # Strategy 5: Check known patch doc directly (from config)
    patch_doc_id = config.get("clickup", {}).get("patch_doc_id")
    if patch_doc_id:
        log(f"  Checking known patch doc {patch_doc_id}...")
        pages = fetch_page_listing(patch_doc_id)
        if pages:
            page_id = find_page_by_task_id(pages, task_id)
            if page_id:
                log(f"  Found page '{task_id}' in known patch doc (page: {page_id})")
                return [(patch_doc_id, page_id)], None

    # Strategy 6: Search Docs API by task ID
    log(f"  No Doc links found yet, searching Docs API...")
    docs = search_docs_by_name(task_id)
    for doc in docs:
        doc_name = doc.get("name", "")
        if task_id in doc_name:
            doc_id = doc["id"]
            log(f"  Found Doc by search: '{doc_name}' (id: {doc_id})")
            # Find the page for this task
            pages = fetch_page_listing(doc_id)
            page_id = find_page_by_task_id(pages, task_id)
            if page_id:
                return [(doc_id, page_id)], None

    # Strategy 7: Search in known "패치 파일" docs by page listing (fallback)
    log(f"  Searching known patch docs for page named '{task_id}'...")
    patch_docs = search_docs_by_name("패치 파일")
    for doc in patch_docs:
        doc_id = doc["id"]
        pages = fetch_page_listing(doc_id)
        page_id = find_page_by_task_id(pages, task_id)
        if page_id:
            log(f"  Found page '{task_id}' in Doc '{doc.get('name', '')}' (doc: {doc_id}, page: {page_id})")
            return [(doc_id, page_id)], None

    return [], None


def fetch_patches_from_doc(doc_id, page_id, output_dir, dry_run=False):
    """Fetch patch files from a Doc page.

    Returns list of downloaded file paths.
    """
    # Fetch page content
    page_data = fetch_page_content(doc_id, page_id)
    if not page_data:
        return []

    page_name = page_data.get("name", "unknown")
    content = page_data.get("content", "")

    log(f"Doc page: '{page_name}'")
    log(f"Content length: {len(content)} chars")

    # Extract attachment URLs
    attachments = extract_attachment_urls(content)

    if not attachments:
        log("  No attachment URLs found in page content")
        # Still save the page content for reference
        if not dry_run:
            content_path = output_dir / "doc_content.md"
            content_path.parent.mkdir(parents=True, exist_ok=True)
            with open(content_path, "w", encoding="utf-8") as f:
                f.write(f"# {page_name}\n\n{content}")
            log(f"  Saved page content to {content_path}")
        return []

    log(f"  Found {len(attachments)} attachment(s):")
    for filename, url in attachments:
        log(f"    - {filename}")

    if dry_run:
        log("  DRY RUN: No files downloaded")
        return []

    # Download files
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []

    for filename, url in attachments:
        # Sanitize filename
        safe_name = sanitize_filename(filename)
        save_path = output_dir / safe_name

        if download_file(url, save_path):
            downloaded.append(save_path)

            # Auto-extract archives
            ext = save_path.suffix.lower()
            if ext in (".zip", ".tar", ".gz", ".tgz"):
                extract_dir = output_dir / save_path.stem
                extract_archive(save_path, extract_dir)

    # Save page content for reference
    content_path = output_dir / "doc_content.md"
    with open(content_path, "w", encoding="utf-8") as f:
        f.write(f"# {page_name}\n\n{content}")

    return downloaded


def sanitize_filename(filename):
    """Sanitize filename for safe filesystem use"""
    # Remove or replace problematic characters
    filename = filename.replace("/", "_").replace("\\", "_")
    # Keep it reasonable length
    if len(filename) > 200:
        ext = Path(filename).suffix
        filename = filename[:200 - len(ext)] + ext
    return filename


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ClickUp Doc Patch Fetcher")
    parser.add_argument("--task-id", help="Task ID (e.g., IMX-9236)")
    parser.add_argument("--doc-id", help="Direct Doc ID")
    parser.add_argument("--page-id", help="Direct Page ID (used with --doc-id)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded without downloading")
    parser.add_argument("--output-dir", help="Override output directory (default: tasks/{task-id}/patches/)")

    args = parser.parse_args()

    if not args.task_id and not args.doc_id:
        parser.print_help()
        print("\nExample usage:")
        print("  python issuebot/fetch_doc.py --task-id IMX-9236")
        print("  python issuebot/fetch_doc.py --task-id IMX-9236 --dry-run")
        print("  python issuebot/fetch_doc.py --doc-id rbeb5-185442 --page-id rbeb5-3475418")
        sys.exit(1)

    if args.doc_id:
        # Direct doc/page mode
        doc_id = args.doc_id
        page_id = args.page_id

        if not page_id:
            log(f"No --page-id specified, fetching page listing for doc {doc_id}...")
            pages = fetch_page_listing(doc_id)
            if args.task_id:
                page_id = find_page_by_task_id(pages, args.task_id)
                if not page_id:
                    log(f"Page for {args.task_id} not found in doc {doc_id}")
                    sys.exit(1)
            else:
                # Print page listing and exit
                log("Page listing:")
                _print_pages(pages, indent=2)
                sys.exit(0)

        output_dir = Path(args.output_dir) if args.output_dir else (TASKS_DIR / (args.task_id or "unknown") / "patches")
        downloaded = fetch_patches_from_doc(doc_id, page_id, output_dir, dry_run=args.dry_run)
        log(f"Downloaded {len(downloaded)} file(s)")
        return

    # Task-based mode
    task_id = args.task_id
    output_dir = Path(args.output_dir) if args.output_dir else (TASKS_DIR / task_id / "patches")

    # Find doc links
    doc_links, md_content = find_doc_links_for_task(task_id)

    if not doc_links:
        log(f"No Doc links found for task {task_id}")
        # Save markdown_description to local task.json if we fetched it
        if md_content:
            _update_local_markdown_description(task_id, md_content)
        sys.exit(0)

    total_downloaded = []
    for doc_id, page_id in doc_links:
        log(f"\nProcessing Doc: {doc_id}, Page: {page_id}")
        downloaded = fetch_patches_from_doc(doc_id, page_id, output_dir, dry_run=args.dry_run)
        total_downloaded.extend(downloaded)

    # Save markdown_description to local task.json if we fetched it
    if md_content:
        _update_local_markdown_description(task_id, md_content)

    log(f"\nTotal: {len(total_downloaded)} file(s) downloaded to {output_dir}")


def _update_local_markdown_description(task_id, md_content):
    """Update local task.json with markdown_description"""
    task_json_path = TASKS_DIR / task_id / "task.json"
    if not task_json_path.exists():
        return

    with open(task_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "markdown_description" not in data:
        data["markdown_description"] = md_content
        # Also extract and save linked_docs
        links = extract_doc_links(md_content)
        if links:
            data["linked_docs"] = [
                {"doc_id": doc_id, "page_id": page_id}
                for doc_id, page_id in links
            ]
        with open(task_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log(f"Updated {task_json_path} with markdown_description")


def _print_pages(pages, indent=0):
    """Print page listing hierarchy"""
    for page in pages:
        prefix = " " * indent
        log(f"{prefix}- {page.get('name', '?')} (id: {page['id']})")
        sub_pages = page.get("pages", [])
        if sub_pages:
            _print_pages(sub_pages, indent + 2)


if __name__ == "__main__":
    main()
