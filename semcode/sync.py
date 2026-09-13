"""Incremental synchronization for registered semcode projects."""

import argparse
from datetime import datetime
from pathlib import Path
import time
from typing import Any, Dict, Optional

from semcode.indexer import get_git_files, mirror_repository, run_indexing_daemon
from semcode.registry import load_registry, save_registry


def sync_project(project_name: str, force: bool = False, timeout_seconds: int = 180) -> Dict[str, Any]:
    """
    Incrementally sync a single registered project.
    Detects additions, modifications, and deletions from the git tree.
    Updates the grepai vector store incrementally if changes occurred.
    """
    registry = load_registry()
    if project_name not in registry:
        raise ValueError(f"Project '{project_name}' not found in registry. Index it first.")

    info = registry[project_name]
    source_path = Path(info["source_path"])
    text_dir = Path(info["text_dir"])
    code_dir = Path(info["code_dir"])

    if not source_path.is_dir():
        raise RuntimeError(f"Source path '{source_path}' does not exist on disk for project '{project_name}'")

    # Get latest git files
    files = get_git_files(source_path)
    print(f"[{project_name}] Syncing {len(files)} files...")

    text_copied, text_unchanged, text_deleted = mirror_repository(source_path, text_dir, files)
    code_copied, code_unchanged, code_deleted = mirror_repository(source_path, code_dir, files)

    changes_detected = (text_copied > 0 or text_deleted > 0 or code_copied > 0 or code_deleted > 0)

    if changes_detected or force:
        print(f"[{project_name}] Changes detected (copied: {text_copied}, deleted: {text_deleted}). Updating index...")
        text_size_kb, text_file_count = run_indexing_daemon(text_dir, timeout_seconds=timeout_seconds)
        code_size_kb, code_file_count = run_indexing_daemon(code_dir, timeout_seconds=timeout_seconds)

        info["last_synced_at"] = datetime.now().isoformat()
        info["text_size_kb"] = text_size_kb
        info["code_size_kb"] = code_size_kb
        info["file_count"] = max(text_file_count, code_file_count, len(files))
        registry[project_name] = info
        save_registry(registry)
        print(f"[{project_name}] Sync complete. New index size: Text {text_size_kb}KB, Code {code_size_kb}KB.")
    else:
        print(f"[{project_name}] No changes detected. Index is up to date.")
        info["last_synced_at"] = datetime.now().isoformat()
        registry[project_name] = info
        save_registry(registry)

    return {
        "project": project_name,
        "copied": text_copied,
        "deleted": text_deleted,
        "unchanged": text_unchanged,
        "changes_detected": changes_detected,
    }


def sync_all(force: bool = False, watch: bool = False, interval_seconds: int = 300, project: Optional[str] = None) -> None:
    """Sync all registered projects (or just `project`, if given), optionally continuously in watch mode."""
    while True:
        if project:
            targets = [project]
        else:
            targets = list(load_registry().keys())

        for pname in targets:
            try:
                sync_project(pname, force=force)
            except Exception as exc:
                print(f"Error syncing {pname}: {exc}")

        if not watch:
            break
        print(f"Watch mode: sleeping for {interval_seconds}s...")
        time.sleep(interval_seconds)


def main():
    parser = argparse.ArgumentParser(description="Incrementally synchronize semcode projects")
    parser.add_argument("--project", "-p", type=str, help="Specific project to sync")
    parser.add_argument("--all", "-a", action="store_true", help="Sync all registered projects")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-index even if no files changed")
    parser.add_argument("--watch", "-w", action="store_true", help="Continuously poll and sync in background")
    parser.add_argument("--interval", "-i", type=int, default=300, help="Poll interval in seconds for --watch")
    args = parser.parse_args()

    if args.watch:
        # --watch applies whether scoped to one --project or --all; a single sync
        # branch for --project used to silently swallow --watch and exit after one pass.
        sync_all(force=args.force, watch=True, interval_seconds=args.interval, project=args.project)
    elif args.project:
        sync_project(args.project, force=args.force)
    elif args.all:
        sync_all(force=args.force, watch=False)
    else:
        parser.error("Specify --project <name> or --all")


if __name__ == "__main__":
    main()
