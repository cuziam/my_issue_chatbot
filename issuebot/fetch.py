#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClickUp Task Fetcher
Fetches task data from ClickUp API and saves to local storage
"""

import os
import re
import sys
import json
import argparse
import zipfile
import requests
from pathlib import Path
from dotenv import load_dotenv

# Get script and root directories
SCRIPT_DIR = Path(__file__).parent.absolute()
ROOT_DIR = SCRIPT_DIR.parent

# Load environment variables
load_dotenv(ROOT_DIR / ".env")

CLICKUP_API_KEY = os.getenv("CLICKUP_API_KEY")
if not CLICKUP_API_KEY:
    print("Error: CLICKUP_API_KEY not found in .env file")
    sys.exit(1)

# Load config
with open(ROOT_DIR / "config" / "config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

BASE_URL = config["clickup"]["base_url"]
TEAM_ID = config["clickup"].get("team_id", "")
TASKS_DIR = ROOT_DIR / config["tasks_dir"]
VERSION_FIELDS = config["version_fields"]

HEADERS = {
    "Authorization": CLICKUP_API_KEY,
    "Content-Type": "application/json"
}

# Reuse a single Session for connection pooling — prevents
# Windows ephemeral port exhaustion (WinError 10048).
_session = requests.Session()
_session.headers.update(HEADERS)


def fetch_task(task_id, team_id=None):
    """Fetch task data from ClickUp API

    Supports both numeric task IDs and custom task IDs (e.g., IMX-9326)
    For custom IDs, team_id is required.
    """
    url = f"{BASE_URL}/task/{task_id}"
    params = {
        "include_subtasks": "false",
        "include_markdown_description": "true"
    }

    # Check if this looks like a custom task ID (contains letters/hyphens)
    is_custom_id = not task_id.isdigit()

    if is_custom_id:
        params["custom_task_ids"] = "true"

        # Use provided team_id or global TEAM_ID
        tid = team_id or TEAM_ID
        if tid:
            params["team_id"] = tid
            print(f"Fetching task: {task_id} (custom ID, team: {tid})")
        else:
            print(f"Warning: Custom task ID '{task_id}' requires team_id")
            print("Set team_id in config.json or use --team-id option")
    else:
        print(f"Fetching task: {task_id} (numeric ID)")

    response = _session.get(url, params=params)

    if response.status_code != 200:
        print(f"Error: Failed to fetch task {task_id}")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return None

    return response.json()


def fetch_comments(task_id, team_id=None, include_replies=True):
    """Fetch task comments from ClickUp API

    Supports both numeric task IDs and custom task IDs (e.g., IMX-9326)
    For custom IDs, team_id is required.
    When include_replies=True, threaded replies are fetched for each comment.
    """
    url = f"{BASE_URL}/task/{task_id}/comment"
    params = {}

    # Check if this looks like a custom task ID (contains letters/hyphens)
    is_custom_id = not task_id.isdigit()

    if is_custom_id:
        params["custom_task_ids"] = "true"

        # Use provided team_id or global TEAM_ID
        tid = team_id or TEAM_ID
        if tid:
            params["team_id"] = tid

    print(f"Fetching comments for task: {task_id}")
    response = _session.get(url, params=params)

    if response.status_code != 200:
        print(f"Warning: Failed to fetch comments for task {task_id}")
        print(f"Status: {response.status_code}, Response: {response.text}")
        return []

    data = response.json()
    comments = data.get("comments", [])

    if include_replies:
        for comment in comments:
            reply_count = comment.get("reply_count", 0)
            if reply_count > 0:
                comment_id = comment.get("id")
                replies = fetch_comment_replies(comment_id)
                comment["replies"] = replies

    return comments


def fetch_comment_replies(comment_id):
    """Fetch threaded replies for a comment from ClickUp API."""
    url = f"{BASE_URL}/comment/{comment_id}/reply"
    print(f"  Fetching replies for comment: {comment_id}")
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"  Warning: Failed to fetch replies for comment {comment_id}")
        return []

    data = response.json()
    return data.get("comments", [])


def download_attachment(url, save_path):
    """Download attachment from URL"""
    print(f"Downloading: {save_path}")

    response = _session.get(url, stream=True)
    if response.status_code != 200:
        print(f"Warning: Failed to download {url}")
        return False

    with open(save_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return True


def classify_file_type(ext):
    """Classify file type by extension"""
    ext = ext.lower()
    if ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'):
        return 'image'
    if ext in ('.zip', '.tar', '.gz', '.7z', '.rar'):
        return 'archive'
    if ext in ('.pdf',):
        return 'document'
    if ext in ('.txt', '.log', '.csv', '.xml', '.json', '.conf', '.properties'):
        return 'text'
    return 'other'


def extract_zip(zip_path, extract_dir):
    """Extract ZIP file and return list of extracted files"""
    extract_dir.mkdir(exist_ok=True)
    extracted = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            zf.extract(info, extract_dir)
            extracted.append({
                "name": info.filename,
                "size": info.file_size
            })
    return extracted


def extract_custom_fields(task_data):
    """Extract custom fields into a simple dict"""
    custom_fields = {}

    for field in task_data.get("custom_fields", []):
        field_name = field.get("name", "")
        field_value = None

        # Extract value based on type
        if field.get("type") == "drop_down":
            options = field.get("type_config", {}).get("options", [])
            raw_value = field.get("value")
            if raw_value is not None:
                for option in options:
                    # ClickUp returns orderindex (int) as value for drop_down
                    if option.get("orderindex") == raw_value:
                        field_value = option.get("name")
                        break
                    # Fallback: also match by option id (UUID)
                    if str(option.get("id")) == str(raw_value):
                        field_value = option.get("name")
                        break
        else:
            field_value = field.get("value")

        if field_value:
            custom_fields[field_name] = field_value

    return custom_fields


def _extract_linked_docs(markdown_desc):
    """Extract linked ClickUp Doc URLs from markdown description."""
    linked_docs = []
    if markdown_desc:
        doc_links = re.findall(
            r"https://app\.clickup\.com/\d+/docs/([a-z0-9]+-\d+)/([a-z0-9]+-\d+)",
            markdown_desc
        )
        seen = set()
        for doc_id, page_id in doc_links:
            key = (doc_id, page_id)
            if key not in seen:
                seen.add(key)
                linked_docs.append({"doc_id": doc_id, "page_id": page_id})
    return linked_docs


CLICKUP_IMAGE_RE = re.compile(
    r'!\[[^\]]*\]\((https://t\d+\.p\.clickup-attachments\.com/[^)]+)\)'
)


def _download_inline_images(markdown, images_dir, existing_attachments, start_idx):
    """Download ClickUp inline images from markdown that aren't already in attachments.

    Returns list of new attachment dicts with url→local path mapping.
    """
    # Build set of already-downloaded URLs
    existing_urls = {a.get("url") for a in existing_attachments if a.get("url")}

    # Find all ClickUp image URLs in markdown
    inline_urls = CLICKUP_IMAGE_RE.findall(markdown)
    if not inline_urls:
        return []

    new_attachments = []
    idx = start_idx
    seen = set()

    for url in inline_urls:
        if url in existing_urls or url in seen:
            continue
        seen.add(url)

        # Extract filename from URL (last path segment)
        url_filename = url.rsplit("/", 1)[-1]
        # URL-decode for display name
        from urllib.parse import unquote
        original_name = unquote(url_filename)
        ext = Path(original_name).suffix or ".png"
        filename = f"image_{idx}{ext}"
        save_path = images_dir / filename

        if download_attachment(url, save_path):
            new_attachments.append({
                "path": str(save_path),
                "original_name": original_name,
                "type": classify_file_type(ext),
                "url": url,
            })
            idx += 1

    return new_attachments


def _extract_doc_links_from_comment(raw_comment):
    """Extract Doc URLs from structured comment data (link_preview items).

    ClickUp stores Doc embeds as structured items with type="link_preview"
    in the comment array.  The comment_text field only contains flattened
    text like "Document preview rbeb5-XXXXX", losing the full URL.
    """
    doc_links = []
    if not isinstance(raw_comment, list):
        return doc_links
    for item in raw_comment:
        if isinstance(item, dict) and item.get("type") == "link_preview":
            url = item.get("link_preview", {}).get("url", "")
            if url:
                doc_links.append(url)
    return doc_links


def _format_comments(comments):
    """Format raw ClickUp API comments into simplified dicts.

    Includes threaded replies if present.
    Extracts Doc link_preview URLs into doc_links field.
    """
    formatted = []
    for comment in comments:
        entry = {
            "date": comment.get("date"),
            "user": comment.get("user", {}).get("username", ""),
            "user_id": comment.get("user", {}).get("id"),
            "comment": comment.get("comment_text", ""),
        }
        # Extract Doc link_preview URLs from structured comment data
        doc_links = _extract_doc_links_from_comment(comment.get("comment", []))
        if doc_links:
            entry["doc_links"] = doc_links
        # Include threaded replies
        raw_replies = comment.get("replies", [])
        if raw_replies:
            reply_list = []
            for r in raw_replies:
                reply_entry = {
                    "date": r.get("date"),
                    "user": r.get("user", {}).get("username", ""),
                    "user_id": r.get("user", {}).get("id"),
                    "comment": r.get("comment_text", ""),
                }
                reply_doc_links = _extract_doc_links_from_comment(r.get("comment", []))
                if reply_doc_links:
                    reply_entry["doc_links"] = reply_doc_links
                reply_list.append(reply_entry)
            entry["replies"] = reply_list
        formatted.append(entry)
    return formatted


def save_task(task_id, task_data, comments):
    """Save task data to local storage"""
    task_dir = Path(TASKS_DIR) / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    images_dir = task_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # Extract custom fields
    custom_fields = extract_custom_fields(task_data)

    # Download attachments
    attachments = task_data.get("attachments", [])
    downloaded_images = []

    for i, attachment in enumerate(attachments):
        url = attachment.get("url")
        title = attachment.get("title", f"attachment_{i}")

        if url:
            # Determine file extension
            ext = Path(title).suffix or ".png"
            filename = f"image_{i}{ext}"
            save_path = images_dir / filename

            if download_attachment(url, save_path):
                file_info = {
                    "path": str(save_path),
                    "original_name": title,
                    "type": classify_file_type(ext),
                    "url": url,
                }

                # ZIP 파일이면 자동 해제
                if ext.lower() == ".zip":
                    extract_dir = images_dir / f"image_{i}"
                    try:
                        extracted = extract_zip(save_path, extract_dir)
                        file_info["extracted_dir"] = str(extract_dir)
                        file_info["extracted_files"] = extracted
                        print(f"  Extracted {len(extracted)} files from {filename}")
                    except zipfile.BadZipFile:
                        print(f"  Warning: {filename} is not a valid ZIP file")

                downloaded_images.append(file_info)

    # Download inline images from markdown that aren't in API attachments
    markdown_desc = task_data.get("markdown_description", "")
    next_idx = len(downloaded_images)
    inline_images = _download_inline_images(
        markdown_desc, images_dir, downloaded_images, next_idx
    )
    downloaded_images.extend(inline_images)
    if inline_images:
        print(f"  Downloaded {len(inline_images)} additional inline images from description")
    linked_docs = _extract_linked_docs(markdown_desc)

    # Prepare task JSON
    task_json = {
        "id": task_id,
        "name": task_data.get("name", ""),
        "description": task_data.get("description", ""),
        "markdown_description": markdown_desc,
        "linked_docs": linked_docs,
        "status": task_data.get("status", {}).get("status", ""),
        "date_created": task_data.get("date_created"),
        "date_updated": task_data.get("date_updated"),
        "assignees": [
            {"id": a.get("id"), "username": a.get("username", ""), "email": a.get("email", "")}
            for a in task_data.get("assignees", [])
        ],
        "tags": [tag.get("name") for tag in task_data.get("tags", [])],
        "custom_fields": custom_fields,
        "attachments": downloaded_images,
        "comments": _format_comments(comments),
        "url": task_data.get("url", "")
    }

    # Save to file
    task_file = task_dir / "task.json"
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump(task_json, f, indent=2, ensure_ascii=False)

    print(f"Task saved to: {task_file}")
    return task_file


def refresh_task(task_id, team_id=None):
    """Refresh task metadata and comments without re-downloading existing attachments.

    Fetches latest data from ClickUp API and updates task.json in-place.
    Existing attachments are preserved; only new attachments are downloaded.
    """
    task_dir = Path(TASKS_DIR) / task_id
    task_file = task_dir / "task.json"

    if not task_file.exists():
        print(f"No existing task.json for {task_id}, doing full fetch")
        task_data = fetch_task(task_id, team_id=team_id)
        if task_data:
            comments = fetch_comments(task_id, team_id=team_id)
            return save_task(task_id, task_data, comments)
        return None

    # Load existing task.json
    with open(task_file, "r", encoding="utf-8") as f:
        existing = json.load(f)

    # Fetch latest from API
    task_data = fetch_task(task_id, team_id=team_id)
    if not task_data:
        print(f"Warning: Failed to refresh task {task_id}, keeping existing data")
        return task_file

    comments = fetch_comments(task_id, team_id=team_id)

    # Update metadata fields
    markdown_desc = task_data.get("markdown_description", "")
    existing["name"] = task_data.get("name", "")
    existing["description"] = task_data.get("description", "")
    existing["markdown_description"] = markdown_desc
    existing["linked_docs"] = _extract_linked_docs(markdown_desc)
    existing["status"] = task_data.get("status", {}).get("status", "")
    existing["date_created"] = task_data.get("date_created")
    existing["date_updated"] = task_data.get("date_updated")
    existing["assignees"] = [
        {"id": a.get("id"), "username": a.get("username", ""), "email": a.get("email", "")}
        for a in task_data.get("assignees", [])
    ]
    existing["tags"] = [tag.get("name") for tag in task_data.get("tags", [])]
    existing["custom_fields"] = extract_custom_fields(task_data)
    existing["url"] = task_data.get("url", "")

    # Replace comments
    existing["comments"] = _format_comments(comments)

    # Preserve existing attachments, download only new ones
    existing_urls = {a.get("path") for a in existing.get("attachments", [])}
    images_dir = task_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # Determine next image index from existing attachments
    existing_indices = set()
    for a in existing.get("attachments", []):
        path = a.get("path", "")
        m = re.search(r"image_(\d+)", path)
        if m:
            existing_indices.add(int(m.group(1)))
    next_idx = max(existing_indices, default=-1) + 1

    api_attachments = task_data.get("attachments", [])
    # Build set of already-downloaded original filenames
    existing_names = {a.get("original_name") for a in existing.get("attachments", [])}

    # Also track existing URLs for dedup
    existing_att_urls = {a.get("url") for a in existing.get("attachments", []) if a.get("url")}

    for attachment in api_attachments:
        url = attachment.get("url")
        title = attachment.get("title", f"attachment_{next_idx}")

        if not url or (title in existing_names and url in existing_att_urls):
            continue

        ext = Path(title).suffix or ".png"
        filename = f"image_{next_idx}{ext}"
        save_path = images_dir / filename

        if download_attachment(url, save_path):
            file_info = {
                "path": str(save_path),
                "original_name": title,
                "type": classify_file_type(ext),
                "url": url,
            }

            if ext.lower() == ".zip":
                extract_dir = images_dir / f"image_{next_idx}"
                try:
                    extracted = extract_zip(save_path, extract_dir)
                    file_info["extracted_dir"] = str(extract_dir)
                    file_info["extracted_files"] = extracted
                    print(f"  Extracted {len(extracted)} files from {filename}")
                except zipfile.BadZipFile:
                    print(f"  Warning: {filename} is not a valid ZIP file")

            existing.setdefault("attachments", []).append(file_info)
            next_idx += 1

    # Download inline images from markdown not already in attachments
    all_attachments = existing.get("attachments", [])
    inline_images = _download_inline_images(
        markdown_desc, images_dir, all_attachments, next_idx
    )
    if inline_images:
        existing.setdefault("attachments", []).extend(inline_images)
        print(f"  Downloaded {len(inline_images)} additional inline images from description")

    # Save updated task.json
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"Task refreshed: {task_file}")
    return task_file


def fetch_tasks_by_list(list_id, tags=None, status=None, statuses=None):
    """Fetch all tasks from a list with optional filters

    Args:
        list_id: ClickUp list ID
        tags: Filter by tags (list of tag names)
        status: Filter by single status (backward compatible)
        statuses: Filter by multiple statuses (list of status strings)
    """
    url = f"{BASE_URL}/list/{list_id}/task"
    params = {"include_subtasks": "false"}

    if tags:
        params["tags[]"] = tags
    if statuses:
        params["statuses[]"] = statuses
    elif status:
        params["statuses[]"] = status

    print(f"Fetching tasks from list: {list_id}")

    all_tasks = []
    page = 0
    while True:
        params["page"] = page
        response = _session.get(url, params=params)

        if response.status_code != 200:
            print(f"Error: Failed to fetch tasks from list {list_id}")
            print(f"Status: {response.status_code}, Response: {response.text}")
            break

        data = response.json()
        tasks = data.get("tasks", [])
        if not tasks:
            break
        all_tasks.extend(tasks)
        page += 1

    return all_tasks


def fetch_tasks_by_list_raw(list_id, statuses=None):
    """Fetch task metadata from ClickUp API (no downloads, with pagination)

    Returns raw API response tasks for lightweight polling.
    """
    url = f"{BASE_URL}/list/{list_id}/task"
    params = {"include_subtasks": "false"}

    if statuses:
        params["statuses[]"] = statuses

    print(f"Polling tasks from list: {list_id} (statuses: {statuses})")

    all_tasks = []
    page = 0
    while True:
        params["page"] = page
        response = _session.get(url, params=params)

        if response.status_code != 200:
            print(f"Error: Failed to poll tasks from list {list_id}")
            print(f"Status: {response.status_code}, Response: {response.text}")
            return None

        data = response.json()
        tasks = data.get("tasks", [])
        if not tasks:
            break
        all_tasks.extend(tasks)
        page += 1

    print(f"Polled {len(all_tasks)} tasks")
    return all_tasks


def get_local_task_ids():
    """Get all task IDs already downloaded locally"""
    tasks_path = Path(TASKS_DIR)
    if not tasks_path.exists():
        return set()

    return {d.name for d in tasks_path.iterdir() if d.is_dir() and (d / "task.json").exists()}


def main():
    parser = argparse.ArgumentParser(description="Fetch ClickUp tasks")
    parser.add_argument("--task-id", help="Specific task ID to fetch (numeric or custom like IMX-9326)")
    parser.add_argument("--team-id", help="Team ID (required for custom task IDs, or set in config.json)")
    parser.add_argument("--list-id", help="Fetch all tasks from a list")
    parser.add_argument("--tags", help="Filter by tags (comma-separated)")
    parser.add_argument("--status", help="Filter by single status")
    parser.add_argument("--statuses", help="Filter by multiple statuses (comma-separated, e.g. 'open,qa assigned')")
    parser.add_argument("--new-only", action="store_true", help="Skip tasks already downloaded locally")

    args = parser.parse_args()

    if args.task_id:
        # Fetch single task
        task_data = fetch_task(args.task_id, team_id=args.team_id)
        if task_data:
            comments = fetch_comments(args.task_id, team_id=args.team_id)
            save_task(args.task_id, task_data, comments)
            print("Done!")

    elif args.list_id:
        # Fetch multiple tasks from list
        tags = args.tags.split(",") if args.tags else None
        statuses_list = [s.strip() for s in args.statuses.split(",")] if args.statuses else None
        tasks = fetch_tasks_by_list(args.list_id, tags=tags, status=args.status, statuses=statuses_list)

        # Filter out already downloaded tasks if --new-only
        local_task_ids = get_local_task_ids() if args.new_only else set()
        new_tasks = []
        skipped = 0

        for task in tasks:
            task_id = task.get("id")
            if task_id in local_task_ids:
                skipped += 1
            else:
                new_tasks.append(task)

        if args.new_only and skipped > 0:
            print(f"Skipped {skipped} already downloaded tasks")

        print(f"Found {len(new_tasks)} new tasks to fetch")

        fetched_ids = []
        for task in new_tasks:
            task_id = task.get("id")
            print(f"\nProcessing task: {task_id}")

            # Fetch full task data
            task_data = fetch_task(task_id, team_id=args.team_id)
            if task_data:
                comments = fetch_comments(task_id, team_id=args.team_id)
                save_task(task_id, task_data, comments)
                fetched_ids.append(task_id)

        print(f"\nFetched {len(fetched_ids)} tasks!")

        # Return fetched task IDs for scheduler use
        return fetched_ids

    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python fetch.py --task-id 123456789  # Numeric ID")
        print("  python fetch.py --task-id IMX-9326 --team-id 25540965  # Custom ID")
        print("  python fetch.py --list-id 123456 --status open --new-only")
        sys.exit(1)

    return []


if __name__ == "__main__":
    main()
