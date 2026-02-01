#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Code Analyzer
Analyzes ClickUp tasks using Claude Code CLI
"""

import os
import sys
import json
import re
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("Error: ANTHROPIC_API_KEY not found in .env file")
    sys.exit(1)

# Load config
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# Load prompts
with open("prompts.json", "r", encoding="utf-8") as f:
    prompts = json.load(f)

TASKS_DIR = config["tasks_dir"]
PACKAGES_DIR = config["packages_dir"]
VERSION_FIELDS = config["version_fields"]
CLAUDE_CONFIG = config["claude"]


def extract_version(version_string):
    """Extract version number from string"""
    if not version_string or version_string == "-":
        return None

    # Pattern: numbers separated by dots (e.g., 5.3.231227.05)
    match = re.search(r'(\d+\.\d+\.\d+(?:\.\d+)?)', str(version_string))
    return match.group(1) if match else None


def find_decompiled_dir(package_dir):
    """Find decompiled directory within a package"""
    package_path = Path(package_dir)

    if not package_path.exists():
        return None

    # Walk through directory to find 'decompiled' folder
    for root, dirs, files in os.walk(package_path):
        if "decompiled" in dirs:
            return str(Path(root) / "decompiled")

    return None


def find_package_dirs(custom_fields):
    """Find package directories based on version information"""
    versions = set()

    # Extract all versions from custom fields
    for field_name, field_value in custom_fields.items():
        if field_name in VERSION_FIELDS:
            version = extract_version(field_value)
            if version:
                versions.add(version)

    if not versions:
        print("Warning: No version information found in task")
        return []

    print(f"Extracted versions: {', '.join(versions)}")

    # Find matching package directories
    packages_path = Path(PACKAGES_DIR)
    if not packages_path.exists():
        print(f"Warning: Packages directory not found: {PACKAGES_DIR}")
        return []

    found_dirs = []
    package_items = list(packages_path.iterdir())

    for version in versions:
        for package_dir in package_items:
            if package_dir.is_dir() and version in package_dir.name:
                decompiled = find_decompiled_dir(package_dir)
                if decompiled:
                    found_dirs.append(decompiled)
                    print(f"Found package for {version}: {decompiled}")
                    break

    return found_dirs


def load_task(task_id):
    """Load task data from local storage"""
    task_file = Path(TASKS_DIR) / task_id / "task.json"

    if not task_file.exists():
        print(f"Error: Task file not found: {task_file}")
        print("Run fetch.py first to download the task")
        sys.exit(1)

    with open(task_file, "r", encoding="utf-8") as f:
        return json.load(f)


def render_prompt(template_name, task_data, version_paths):
    """Render prompt template with task data"""
    if template_name not in prompts:
        print(f"Error: Template '{template_name}' not found in prompts.json")
        sys.exit(1)

    template = prompts[template_name]["template"]

    # Format version information
    versions_text = "\n".join([
        f"- {key}: {value}"
        for key, value in task_data["custom_fields"].items()
        if key in VERSION_FIELDS
    ])

    # Format images
    images_text = "\n".join([
        f"- {img}"
        for img in task_data.get("attachments", [])
    ]) or "(No images attached)"

    # Format comments
    comments_text = "\n".join([
        f"[{comment['date']}] {comment['user']}: {comment['comment']}"
        for comment in task_data.get("comments", [])
    ]) or "(No comments)"

    # Format version paths
    paths_text = "\n".join([f"- {path}" for path in version_paths])
    if not paths_text:
        paths_text = f"(Warning: No matching package directories found)\nPlease search in: {PACKAGES_DIR}"

    # Render template
    prompt = template.format(
        title=task_data["name"],
        description=task_data.get("description", "(No description)"),
        images=images_text,
        comments=comments_text,
        versions=versions_text,
        version_paths=paths_text
    )

    return prompt


def run_claude_analysis(prompt, task_id):
    """Run Claude Code CLI to analyze the task"""
    print("\n" + "="*60)
    print("Starting Claude Code analysis...")
    print("="*60 + "\n")

    # Prepare command
    cmd = [
        "claude",
        "-p", prompt,
        "--allowedTools", CLAUDE_CONFIG["allowed_tools"],
        "--max-turns", str(CLAUDE_CONFIG["max_turns"])
    ]

    # Run Claude
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CLAUDE_CONFIG["timeout_seconds"],
            encoding="utf-8"
        )

        if result.returncode != 0:
            print("Error: Claude Code execution failed")
            print(f"stderr: {result.stderr}")
            return None

        return result.stdout

    except subprocess.TimeoutExpired:
        print(f"Error: Claude Code execution timed out after {CLAUDE_CONFIG['timeout_seconds']} seconds")
        return None
    except FileNotFoundError:
        print("Error: Claude Code CLI not found")
        print("Please install Claude Code: https://claude.ai/download")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def save_report(task_id, report_content):
    """Save analysis report to file"""
    report_file = Path(TASKS_DIR) / task_id / "report.md"

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"\nReport saved to: {report_file}")
    return report_file


def main():
    parser = argparse.ArgumentParser(description="Analyze ClickUp tasks with Claude Code")
    parser.add_argument("--task-id", required=True, help="Task ID to analyze")
    parser.add_argument(
        "--template",
        choices=["issue_analysis", "spec_inquiry", "improvement_request"],
        default="issue_analysis",
        help="Analysis template to use"
    )

    args = parser.parse_args()

    print(f"Analyzing task: {args.task_id}")
    print(f"Template: {args.template}")

    # Load task
    task_data = load_task(args.task_id)

    # Find package directories
    version_paths = find_package_dirs(task_data["custom_fields"])

    # Render prompt
    prompt = render_prompt(args.template, task_data, version_paths)

    # Save prompt for debugging
    prompt_file = Path(TASKS_DIR) / args.task_id / "prompt.txt"
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"Prompt saved to: {prompt_file}")

    # Run Claude analysis
    report = run_claude_analysis(prompt, args.task_id)

    if report:
        save_report(args.task_id, report)
        print("\nAnalysis complete!")
    else:
        print("\nAnalysis failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
