#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClickUp Task Fetcher
Fetches task data from ClickUp API and saves to local storage
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CLICKUP_API_KEY = os.getenv("CLICKUP_API_KEY")
if not CLICKUP_API_KEY:
    print("Error: CLICKUP_API_KEY not found in .env file")
    sys.exit(1)

# Load config
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

BASE_URL = config["clickup"]["base_url"]
TASKS_DIR = config["tasks_dir"]
VERSION_FIELDS = config["version_fields"]

HEADERS = {
    "Authorization": CLICKUP_API_KEY,
    "Content-Type": "application/json"
}


def fetch_task(task_id):
    """Fetch task data from ClickUp API"""
    url = f"{BASE_URL}/task/{task_id}"
    params = {
        "include_subtasks": "false"
    }

    print(f"Fetching task: {task_id}")
    response = requests.get(url, headers=HEADERS, params=params)

    if response.status_code != 200:
        print(f"Error: Failed to fetch task {task_id}")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return None

    return response.json()


def fetch_comments(task_id):
    """Fetch task comments from ClickUp API"""
    url = f"{BASE_URL}/task/{task_id}/comment"

    print(f"Fetching comments for task: {task_id}")
    response = requests.get(url, headers=HEADERS)

    if response.status_code != 200:
        print(f"Warning: Failed to fetch comments for task {task_id}")
        return []

    data = response.json()
    return data.get("comments", [])


def download_attachment(url, save_path):
    """Download attachment from URL"""
    print(f"Downloading: {save_path}")

    response = requests.get(url, stream=True)
    if response.status_code != 200:
        print(f"Warning: Failed to download {url}")
        return False

    with open(save_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return True


def extract_custom_fields(task_data):
    """Extract custom fields into a simple dict"""
    custom_fields = {}

    for field in task_data.get("custom_fields", []):
        field_name = field.get("name", "")
        field_value = None

        # Extract value based on type
        if field.get("type") == "drop_down":
            options = field.get("type_config", {}).get("options", [])
            value_id = field.get("value")
            for option in options:
                if str(option.get("id")) == str(value_id):
                    field_value = option.get("name")
                    break
        else:
            field_value = field.get("value")

        if field_value:
            custom_fields[field_name] = field_value

    return custom_fields


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
                downloaded_images.append(str(save_path))

    # Prepare task JSON
    task_json = {
        "id": task_id,
        "name": task_data.get("name", ""),
        "description": task_data.get("description", ""),
        "status": task_data.get("status", {}).get("status", ""),
        "tags": [tag.get("name") for tag in task_data.get("tags", [])],
        "custom_fields": custom_fields,
        "attachments": downloaded_images,
        "comments": [
            {
                "date": comment.get("date"),
                "user": comment.get("user", {}).get("username", ""),
                "comment": comment.get("comment_text", "")
            }
            for comment in comments
        ],
        "url": task_data.get("url", "")
    }

    # Save to file
    task_file = task_dir / "task.json"
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump(task_json, f, indent=2, ensure_ascii=False)

    print(f"Task saved to: {task_file}")
    return task_file


def fetch_tasks_by_list(list_id, tags=None, status=None):
    """Fetch all tasks from a list with optional filters"""
    url = f"{BASE_URL}/list/{list_id}/task"
    params = {}

    if tags:
        params["tags[]"] = tags
    if status:
        params["statuses[]"] = status

    print(f"Fetching tasks from list: {list_id}")
    response = requests.get(url, headers=HEADERS, params=params)

    if response.status_code != 200:
        print(f"Error: Failed to fetch tasks from list {list_id}")
        return []

    data = response.json()
    return data.get("tasks", [])


def main():
    parser = argparse.ArgumentParser(description="Fetch ClickUp tasks")
    parser.add_argument("--task-id", help="Specific task ID to fetch")
    parser.add_argument("--list-id", help="Fetch all tasks from a list")
    parser.add_argument("--tags", help="Filter by tags (comma-separated)")
    parser.add_argument("--status", help="Filter by status")

    args = parser.parse_args()

    if args.task_id:
        # Fetch single task
        task_data = fetch_task(args.task_id)
        if task_data:
            comments = fetch_comments(args.task_id)
            save_task(args.task_id, task_data, comments)
            print("Done!")

    elif args.list_id:
        # Fetch multiple tasks from list
        tags = args.tags.split(",") if args.tags else None
        tasks = fetch_tasks_by_list(args.list_id, tags=tags, status=args.status)

        print(f"Found {len(tasks)} tasks")
        for task in tasks:
            task_id = task.get("id")
            print(f"\nProcessing task: {task_id}")

            # Fetch full task data
            task_data = fetch_task(task_id)
            if task_data:
                comments = fetch_comments(task_id)
                save_task(task_id, task_data, comments)

        print("\nAll tasks fetched!")

    else:
        parser.print_help()
        print("\nExample usage:")
        print("  python fetch.py --task-id abc123")
        print("  python fetch.py --list-id 123456 --tags needs-analysis")
        sys.exit(1)


if __name__ == "__main__":
    main()
