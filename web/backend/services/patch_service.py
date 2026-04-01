"""Service layer wrapping fetch_doc.py and patch_diff.py.

All issuebot imports are done lazily inside function bodies to avoid
module-level side effects (dotenv, sys.exit, etc.).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ..config import TASKS_DIR


async def fetch_doc_patches(task_id: str, dry_run: bool = False) -> dict:
    """Download patch files from ClickUp Docs for a given task.

    Wraps ``issuebot/fetch_doc.py`` functions.
    """

    def _run() -> dict:
        from issuebot.fetch_doc import find_doc_links_for_task, fetch_patches_from_doc

        output_dir = TASKS_DIR / task_id / "patches"

        doc_links, _md = find_doc_links_for_task(task_id)

        if not doc_links:
            return {
                "status": "no_docs",
                "message": f"No Doc links found for {task_id}",
                "files": [],
            }

        all_files: list[str] = []
        for doc_id, page_id in doc_links:
            files = fetch_patches_from_doc(doc_id, page_id, output_dir, dry_run)
            all_files.extend([str(f) for f in files])

        return {
            "status": "ok",
            "message": f"Downloaded {len(all_files)} files",
            "doc_links": [{"doc_id": d, "page_id": p} for d, p in doc_links],
            "files": all_files,
        }

    return await asyncio.to_thread(_run)


async def generate_diff(task_id: str, output_json: bool = True) -> dict:
    """Run the patch_diff pipeline: detect patches, match sources, generate diffs.

    Wraps ``issuebot/patch_diff.py`` functions.
    """

    def _run() -> dict:
        from issuebot.patch_diff import (
            detect_patches,
            match_source,
            generate_diff as _gen_diff,
            load_inventory,
            extract_version_from_task,
            generate_markdown_output,
            generate_json_output,
        )

        task_dir = TASKS_DIR / task_id
        task_json_path = task_dir / "task.json"

        if not task_json_path.exists():
            return {"status": "error", "message": f"task.json not found for {task_id}"}

        with open(task_json_path, "r", encoding="utf-8") as f:
            task_data = json.load(f)

        patch_info = detect_patches(task_dir)
        if not patch_info["patch_files"] and not patch_info.get("jars"):
            # Clean up stale diff files from previous (possibly incorrect) runs
            for stale in ("patch_diff.md", "patch_diff.json"):
                stale_path = task_dir / stale
                if stale_path.exists():
                    stale_path.unlink()
            return {"status": "no_patches", "message": "No patch files detected"}

        inventory = load_inventory()
        task_versions = extract_version_from_task(task_data)

        matches = []
        for pf in patch_info["patch_files"]:
            m = match_source(pf, task_versions, inventory)
            if m:
                matches.append(m)

        diffs = [_gen_diff(m) for m in matches]

        # Write markdown output
        md = generate_markdown_output(
            task_id, patch_info, matches, diffs, patch_info.get("patch_notes", [])
        )
        (task_dir / "patch_diff.md").write_text(md, encoding="utf-8")

        # Write JSON output
        if output_json:
            json_out = generate_json_output(
                task_id, patch_info, matches, diffs, patch_info.get("patch_notes", [])
            )
            with open(task_dir / "patch_diff.json", "w", encoding="utf-8") as jf:
                json.dump(json_out, jf, indent=2, ensure_ascii=False)

        return {
            "status": "ok",
            "file_count": len(matches),
            "message": f"Generated diff for {len(matches)} files",
        }

    return await asyncio.to_thread(_run)
