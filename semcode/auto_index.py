"""Automatic background indexing engine for newly opened repositories (G1)."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from semcode.indexer import get_git_files
from semcode.registry import get_registry_path, load_registry

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "auto_index.json"
WORKSPACES_DIR = Path(__file__).resolve().parent.parent / "workspaces"
LOCK_FILE = WORKSPACES_DIR / "auto_index.lock"


def load_config() -> Dict[str, Any]:
    default_cfg = {
        "max_files": 5000,
        "roots": ["D:\\Code", "E:\\proj"],
        "max_commit_age_days": 30,
        "deny_patterns": [
            r"^[A-Za-z]:\\$",
            r"^[A-Za-z]:\\Windows",
            r"^[A-Za-z]:\\Users\\[^\\]+$",
            r"^[A-Za-z]:\\Program Files",
            r"^[A-Za-z]:\\AppData",
        ]
    }
    if not CONFIG_PATH.is_file():
        return default_cfg
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Corrupt or unreadable auto-index config at '{CONFIG_PATH}': {exc}\n"
            f"Remediation: fix or delete the file (defaults apply when it is absent)."
        ) from exc


def get_git_repo_root(path: str) -> Optional[Path]:
    """Resolves git top-level directory. Returns None if not inside a git repository."""
    try:
        proc = subprocess.run(
            ["git", "-C", path, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        resolved = proc.stdout.strip()
        if resolved:
            return Path(resolved).resolve()
    except Exception:
        pass
    return None


def check_eligibility(repo_path: Path) -> Tuple[bool, str, List[str]]:
    """
    Validates if a git repository is eligible for automatic indexing.
    Returns (eligible: bool, reason: str, files: List[str]).
    """
    cfg = load_config()
    str_path = str(repo_path)

    # 1. Check deny patterns
    for pat in cfg.get("deny_patterns", []):
        if re.search(pat, str_path, re.IGNORECASE):
            return False, f"Path '{str_path}' matches auto-index deny list pattern '{pat}'.", []

    # 2. Check git file count
    try:
        files = get_git_files(repo_path)
    except Exception as exc:
        return False, f"Could not inspect git files in '{str_path}': {exc}", []

    max_files = cfg.get("max_files", 5000)
    if len(files) > max_files:
        return (
            False,
            f"Repository '{str_path}' contains {len(files)} files (exceeds auto-index limit of {max_files}). "
            f"Run `index_project.ps1 -ProjectPath '{str_path}'` to index manually.",
            files
        )

    if not files:
        return False, f"Repository '{str_path}' contains 0 indexable source files.", []

    return True, "Eligible", files


def get_job_path(project_name: str) -> Path:
    return WORKSPACES_DIR / project_name / "job.json"


def get_job_status(project_name: str) -> Optional[Dict[str, Any]]:
    path = get_job_path(project_name)
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def trigger_auto_index(repo_path: Path, files: List[str]) -> str:
    """
    Spawns background indexing for an unregistered git repository and returns informative status.
    """
    project_name = repo_path.name
    job_file = get_job_path(project_name)
    job_file.parent.mkdir(parents=True, exist_ok=True)

    # Check if existing job is running
    existing = get_job_status(project_name)
    if existing and existing.get("status") == "running":
        eta = existing.get("eta_minutes", 1)
        return (
            f"'{repo_path}' is currently being indexed (job {existing.get('job_id')}, ~{eta} min). "
            f"Status: `python -m semcode.auto_index status --project {project_name}`."
        )

    file_count = len(files)
    # Estimate ~1.5 seconds per file across both 137M text + 7B code models
    eta_minutes = max(1, round((file_count * 1.5) / 60.0))
    job_id = f"job-{int(time.time())}"

    job_data = {
        "job_id": job_id,
        "project": project_name,
        "source_path": str(repo_path),
        "file_count": file_count,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "eta_minutes": eta_minutes,
        "error": None,
    }
    job_file.write_text(json.dumps(job_data, indent=2), encoding="utf-8")

    # Launch background indexer detached
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    cmd = [sys.executable, "-m", "semcode.indexer", str(repo_path), "--name", project_name]
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            close_fds=True,
        )
    except Exception as exc:
        job_data["status"] = "failed"
        job_data["error"] = str(exc)
        job_file.write_text(json.dumps(job_data, indent=2), encoding="utf-8")
        raise RuntimeError(f"Failed to start auto-index background process: {exc}") from exc

    return (
        f"'{repo_path}' is not indexed yet. Auto-indexing started immediately "
        f"(job {job_id}, ~{eta_minutes} min for {file_count} files). "
        f"Retry after it finishes; status: `python -m semcode.auto_index status --project {project_name}`."
    )


def maybe_auto_index(path: str) -> Optional[str]:
    """
    Called when an unregistered path is encountered.
    If inside an eligible git repo, triggers auto-indexing and returns status message.
    Otherwise returns None.
    """
    repo_root = get_git_repo_root(path)
    if not repo_root:
        return None

    # Check if already registered. An empty registry is only valid when
    # registry.json doesn't exist yet -- if it exists, load_registry() must
    # succeed or raise loudly rather than silently treating a corrupt
    # registry as "nothing registered" and triggering a duplicate index.
    reg = load_registry() if get_registry_path().is_file() else {}
    norm_target = str(repo_root).lower().rstrip(os.sep)
    for _, pinfo in reg.items():
        sp = os.path.abspath(pinfo.get("source_path", "")).lower().rstrip(os.sep)
        if norm_target == sp or norm_target.startswith(sp + os.sep):
            return None  # Already registered

    eligible, reason, files = check_eligibility(repo_root)
    if not eligible:
        return f"Cannot auto-index '{repo_root}': {reason}"

    return trigger_auto_index(repo_root, files)


def discover_and_index_active_repos() -> List[str]:
    """
    Scheduled Task discovery: Scans configured roots for repos with commits in last 30 days.
    """
    cfg = load_config()
    roots = cfg.get("roots", [])
    max_days = cfg.get("max_commit_age_days", 30)
    discovered: List[str] = []

    reg = load_registry()
    registered_paths = {os.path.abspath(p["source_path"]).lower().rstrip(os.sep) for p in reg.values()}

    for root_str in roots:
        root_dir = Path(root_str)
        if not root_dir.is_dir():
            continue

        for child in root_dir.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            git_root = get_git_repo_root(str(child))
            if not git_root:
                continue

            norm_sp = str(git_root).lower().rstrip(os.sep)
            if norm_sp in registered_paths:
                continue

            # Check recent commit age
            try:
                log_proc = subprocess.run(
                    ["git", "-C", str(git_root), "log", "-1", "--format=%ct"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                commit_ts = int(log_proc.stdout.strip())
                days_old = (time.time() - commit_ts) / 86400.0
                if days_old > max_days:
                    continue
            except Exception:
                continue

            # Eligible for indexing
            eligible, _, files = check_eligibility(git_root)
            if eligible:
                print(f"Auto-discovered active repo: {git_root} (committed {days_old:.1f}d ago, {len(files)} files)")
                trigger_auto_index(git_root, files)
                discovered.append(str(git_root))

    return discovered


def main():
    parser = argparse.ArgumentParser(description="Auto-index management and background discovery")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    status_parser = subparsers.add_parser("status", help="Check auto-index job status")
    status_parser.add_argument("--project", "-p", required=True, help="Project name")

    subparsers.add_parser("discover", help="Scan configured roots for active repositories")

    args = parser.parse_args()

    if args.subcommand == "status":
        st = get_job_status(args.project)
        if not st:
            print(f"No job found for project '{args.project}'")
        else:
            print(json.dumps(st, indent=2))

    elif args.subcommand == "discover":
        discovered = discover_and_index_active_repos()
        print(f"Discovery complete. Triggered {len(discovered)} auto-index jobs.")


if __name__ == "__main__":
    main()
