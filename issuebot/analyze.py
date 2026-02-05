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
import platform
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Get script and root directories
SCRIPT_DIR = Path(__file__).parent.absolute()
ROOT_DIR = SCRIPT_DIR.parent

# Load environment variables
load_dotenv(ROOT_DIR / ".env")

# Load config
with open(ROOT_DIR / "config" / "config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# Load prompts
with open(ROOT_DIR / "config" / "prompts.json", "r", encoding="utf-8") as f:
    prompts = json.load(f)

TASKS_DIR = ROOT_DIR / config["tasks_dir"]
PACKAGES_DIR = ROOT_DIR / config["packages_dir"]
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


def render_prompt(template_name, task_data, version_paths, task_id):
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

    # Format images with absolute paths
    images_list = task_data.get("attachments", [])
    if images_list:
        images_text = "\n".join([
            f"- {Path(img).absolute()}"
            for img in images_list
        ])
        images_text += "\n\n(위 이미지들을 Read 도구로 읽어서 분석해주세요)"
    else:
        images_text = "(No images attached)"

    # Format comments
    comments_text = "\n".join([
        f"[{comment['date']}] {comment['user']}: {comment['comment']}"
        for comment in task_data.get("comments", [])
    ]) or "(No comments)"

    # Format version paths
    paths_text = "\n".join([f"- {path}" for path in version_paths])
    if not paths_text:
        paths_text = f"(Warning: No matching package directories found)\nPlease search in: {PACKAGES_DIR}"

    # Report path for Claude to write directly
    report_path = Path(TASKS_DIR) / task_id / "report.md"

    # Render template
    prompt = template.format(
        title=task_data["name"],
        description=task_data.get("description", "(No description)"),
        images=images_text,
        comments=comments_text,
        versions=versions_text,
        version_paths=paths_text,
        report_path=str(report_path.absolute())
    )

    return prompt


def run_claude_analysis(prompt, task_id):
    """Run Claude Code CLI with real-time streaming output.

    Uses --output-format stream-json for real-time progress display.
    Claude will write the report directly to report.md file.
    Returns True if successful, False otherwise.
    """
    print("\n" + "="*60)
    print("Starting Claude Code analysis...")
    print("="*60 + "\n")

    print("This may take several minutes. Progress will appear below:\n")
    print("-" * 60)
    sys.stdout.flush()

    try:
        # Run claude with stream-json for real-time output
        process = subprocess.Popen(
            [
                "claude", "-p", prompt,
                "--allowedTools", CLAUDE_CONFIG["allowed_tools"],
                "--output-format", "stream-json",
                "--verbose"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1
        )

        # Parse JSON stream and display progress
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                msg_type = data.get("type")

                if msg_type == "system":
                    subtype = data.get("subtype", "")
                    if subtype == "init":
                        print("[System] Initialized")

                elif msg_type == "assistant":
                    message = data.get("message", {})
                    content = message.get("content", [])
                    for item in content:
                        if item.get("type") == "text":
                            text = item.get("text", "")
                            # Show first 200 chars of text
                            preview = text[:200] + "..." if len(text) > 200 else text
                            print(f"[Claude] {preview}")
                        elif item.get("type") == "tool_use":
                            tool_name = item.get("name", "unknown")
                            tool_input = item.get("input", {})
                            # Show tool usage
                            if tool_name == "Read":
                                print(f"[Tool] Reading: {tool_input.get('file_path', '')[:60]}...")
                            elif tool_name == "Glob":
                                print(f"[Tool] Searching: {tool_input.get('pattern', '')}")
                            elif tool_name == "Grep":
                                print(f"[Tool] Grep: {tool_input.get('pattern', '')}")
                            elif tool_name == "Write":
                                print(f"[Tool] Writing: {tool_input.get('file_path', '')[:60]}...")
                            elif tool_name == "Bash":
                                cmd = tool_input.get('command', '')[:50]
                                print(f"[Tool] Bash: {cmd}...")
                            else:
                                print(f"[Tool] {tool_name}")

                elif msg_type == "result":
                    duration = data.get("duration_ms", 0) / 1000
                    num_turns = data.get("num_turns", 0)
                    print(f"\n[Done] Completed in {duration:.1f}s ({num_turns} turns)")

            except json.JSONDecodeError:
                # Non-JSON output, just print it
                if line:
                    print(f"[Output] {line[:100]}")

            sys.stdout.flush()

        # Wait for process to complete
        return_code = process.wait(timeout=CLAUDE_CONFIG["timeout_seconds"])

        print("-" * 60)

        if return_code != 0:
            print(f"\nClaude exited with code {return_code}")
            return False

        return True

    except subprocess.TimeoutExpired:
        process.kill()
        print(f"\nError: Timed out after {CLAUDE_CONFIG['timeout_seconds']} seconds")
        return False
    except FileNotFoundError:
        print("Error: Claude Code CLI not found")
        print("Please install Claude Code: https://claude.ai/download")
        return False
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


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
        help="Analysis template to use (issue_analysis: 이슈 분석, spec_inquiry: 사양 문의, improvement_request: 개선 요청)"
    )
    args = parser.parse_args()

    print(f"Analyzing task: {args.task_id}")
    print(f"Template: {args.template}")

    # Load task
    task_data = load_task(args.task_id)

    # Find package directories
    version_paths = find_package_dirs(task_data["custom_fields"])

    # Render prompt (includes report_path for Claude to write directly)
    prompt = render_prompt(args.template, task_data, version_paths, args.task_id)

    # Save prompt for debugging
    prompt_file = Path(TASKS_DIR) / args.task_id / "prompt.txt"
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"Prompt saved to: {prompt_file}")

    # Run Claude analysis
    success = run_claude_analysis(prompt, args.task_id)

    report_file = Path(TASKS_DIR) / args.task_id / "report.md"

    if success and report_file.exists():
        print(f"\nReport saved to: {report_file}")
        print("\nAnalysis complete!")
    elif success:
        print("\nClaude finished but report.md was not created.")
        print("Check if Claude was instructed to write the report file.")
        sys.exit(1)
    else:
        print("\nAnalysis failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
