#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch Task Analyzer
Process multiple ClickUp tasks in batch mode
"""

import os
import sys
import json
import argparse
import subprocess
import platform
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load config
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

TASKS_DIR = config["tasks_dir"]
MAX_CONCURRENT = config["max_concurrent"]


def get_local_task_ids():
    """Get all task IDs from local storage"""
    tasks_path = Path(TASKS_DIR)

    if not tasks_path.exists():
        return []

    task_ids = []
    for task_dir in tasks_path.iterdir():
        if task_dir.is_dir():
            task_file = task_dir / "task.json"
            if task_file.exists():
                task_ids.append(task_dir.name)

    return task_ids


def launch_in_terminal(task_id, template):
    """Launch analysis in a separate terminal window"""
    try:
        system = platform.system()
        cwd = os.getcwd()
        python_exe = sys.executable

        # Build the analyze command
        analyze_cmd = f'{python_exe} analyze.py --task-id {task_id} --template {template}'

        if system == "Windows":
            # PowerShell Start-Process for Windows
            # Keep terminal open after execution with Read-Host
            ps_command = (
                f'Start-Process powershell -ArgumentList '
                f'\'-NoExit\', \'-Command\', '
                f'\'cd "{cwd}"; '
                f'{analyze_cmd}; '
                f'Write-Host ""; '
                f'Write-Host "Analysis complete. Press Enter to close..."; '
                f'Read-Host\''
            )

            terminal_cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                ps_command
            ]

        elif system == "Linux":
            # Try common Linux terminals
            terminals = [
                ("gnome-terminal", ["gnome-terminal", "--", "bash", "-c",
                                   f'cd "{cwd}" && {analyze_cmd}; echo ""; echo "Analysis complete. Press Enter to close..."; read']),
                ("konsole", ["konsole", "--hold", "-e", "bash", "-c",
                            f'cd "{cwd}" && {analyze_cmd}']),
                ("xterm", ["xterm", "-hold", "-e", "bash", "-c",
                          f'cd "{cwd}" && {analyze_cmd}'])
            ]

            terminal_cmd = None
            for term_name, cmd in terminals:
                try:
                    # Check if terminal is available
                    subprocess.run(["which", term_name], capture_output=True, check=True)
                    terminal_cmd = cmd
                    break
                except:
                    continue

            if not terminal_cmd:
                print(f"[{task_id}] Warning: No supported terminal found (gnome-terminal, konsole, xterm)")
                return False

        elif system == "Darwin":
            # macOS Terminal.app via osascript
            apple_script = (
                f'tell application "Terminal" to do script '
                f'"cd \\"{cwd}\\" && {analyze_cmd} && '
                f'echo \\"\\" && '
                f'echo \\"Analysis complete. Press Enter to close...\\" && read"'
            )

            terminal_cmd = [
                "osascript",
                "-e",
                apple_script
            ]

        else:
            print(f"[{task_id}] Warning: Unsupported platform: {system}")
            return False

        # Launch terminal
        subprocess.Popen(
            terminal_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print(f"[{task_id}] Launched in separate terminal")
        return True

    except Exception as e:
        print(f"[{task_id}] Failed to launch terminal: {e}")
        return False


def analyze_single_task(task_id, template):
    """Analyze a single task (for parallel execution)"""
    try:
        print(f"\n[{task_id}] Starting analysis...")

        cmd = [
            sys.executable,  # Use same Python interpreter
            "analyze.py",
            "--task-id", task_id,
            "--template", template
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )

        if result.returncode == 0:
            print(f"[{task_id}] Analysis complete")
            return task_id, True, None
        else:
            error = result.stderr or result.stdout
            print(f"[{task_id}] Analysis failed: {error}")
            return task_id, False, error

    except Exception as e:
        print(f"[{task_id}] Exception: {e}")
        return task_id, False, str(e)


def main():
    parser = argparse.ArgumentParser(description="Batch analyze ClickUp tasks")
    parser.add_argument(
        "--template",
        choices=["issue_analysis", "spec_inquiry", "improvement_request"],
        default="issue_analysis",
        help="Analysis template to use"
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel processes (default: 1)"
    )
    parser.add_argument(
        "--task-ids",
        help="Comma-separated list of task IDs (if not specified, analyze all local tasks)"
    )
    parser.add_argument(
        "--separate-terminals",
        action="store_true",
        help="Launch each analysis in a separate terminal window (병렬실행)"
    )

    args = parser.parse_args()

    # Get task IDs
    if args.task_ids:
        task_ids = args.task_ids.split(",")
    else:
        task_ids = get_local_task_ids()

    if not task_ids:
        print("No tasks found to analyze")
        print("Run fetch.py first to download tasks")
        sys.exit(1)

    print(f"Found {len(task_ids)} tasks to analyze")
    print(f"Template: {args.template}")
    print(f"Parallel processes: {args.parallel}")
    if args.separate_terminals:
        print("Mode: Separate terminal windows")
    print("")

    # Separate terminal mode
    if args.separate_terminals:
        # Get launch delay from config
        launch_delay = config.get("terminal_launch_delay_seconds", 0.5)

        print(f"Launching {len(task_ids)} analyses in separate terminal windows...")
        print("")

        launched = 0
        for task_id in task_ids:
            success = launch_in_terminal(task_id, args.template)
            if success:
                launched += 1
            # Delay between launches to prevent window manager overload
            if task_id != task_ids[-1]:  # Don't delay after last task
                time.sleep(launch_delay)

        print("")
        print("="*60)
        print(f"Launched {launched}/{len(task_ids)} analyses in separate terminals")
        print("Monitor each terminal window for progress")
        print("="*60)
        return

    # Limit concurrent processes
    max_workers = min(args.parallel, MAX_CONCURRENT)

    if max_workers == 1:
        # Sequential execution
        results = []
        for task_id in task_ids:
            result = analyze_single_task(task_id, args.template)
            results.append(result)
    else:
        # Parallel execution
        results = []
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyze_single_task, task_id, args.template): task_id
                for task_id in task_ids
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

    # Print summary
    print("\n" + "="*60)
    print("Batch Analysis Summary")
    print("="*60)

    success_count = sum(1 for _, success, _ in results if success)
    failed_count = len(results) - success_count

    print(f"Total: {len(results)}")
    print(f"Success: {success_count}")
    print(f"Failed: {failed_count}")

    if failed_count > 0:
        print("\nFailed tasks:")
        for task_id, success, error in results:
            if not success:
                print(f"  - {task_id}: {error}")

    print("")


if __name__ == "__main__":
    main()
