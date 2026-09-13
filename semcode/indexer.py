"""Git-based mirror and indexing lifecycle manager for grepai-hybrid."""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from semcode.creds import get_lmstudio_token
from semcode.grepai_runner import find_binary, run_grepai_command
from semcode.registry import get_registry_path, load_registry, save_registry

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKSPACES_DIR = REPO_ROOT / "workspaces"

TEXT_MODEL = "text-embedding-nomic-embed-text-v1.5@f32"
CODE_MODEL = "nomic-embed-code-v1.5@f32"
EMBED_DIMENSIONS = 768

MANDATORY_EXCLUDES = {
    ".grepai",
    ".claude",
    ".codex",
    ".gemini",
}


def get_git_files(repo_path: Path) -> List[str]:
    """
    Get all tracked and untracked-not-ignored files using git.
    Obedient to .gitignore, .git/info/exclude, and global gitignore.
    Filters out mandatory exclude directories and nested git worktrees/submodules.
    """
    cmd = ["git", "-C", str(repo_path), "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as exc:
        stderr_msg = exc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files failed in '{repo_path}': {stderr_msg}") from exc
    except FileNotFoundError:
        raise RuntimeError("git executable not found on PATH. Git is required for file selection.")

    raw_files = [f for f in proc.stdout.decode("utf-8", errors="replace").split("\0") if f]

    # Identify nested worktrees or submodules (directories containing a .git file or folder)
    nested_worktrees: Set[str] = set()
    for root, dirs, files in os.walk(str(repo_path)):
        rel_dir = os.path.relpath(root, str(repo_path)).replace("\\", "/")
        if rel_dir == ".":
            continue
        if ".git" in files or ".git" in dirs:
            nested_worktrees.add(rel_dir.lower())

    filtered_files: List[str] = []
    for rel in raw_files:
        norm_rel = rel.replace("\\", "/")
        parts = [p.lower() for p in norm_rel.split("/")]

        # Mandatory directory exclusions
        if any(exc in parts for exc in MANDATORY_EXCLUDES):
            continue

        # Nested git worktrees or submodules exclusion
        is_nested = False
        for nw in nested_worktrees:
            if norm_rel.lower() == nw or norm_rel.lower().startswith(nw + "/"):
                is_nested = True
                break
        if is_nested:
            continue

        filtered_files.append(norm_rel)

    return filtered_files


def mirror_repository(source_root: Path, mirror_root: Path, file_list: List[str]) -> Tuple[int, int, int]:
    """
    Mirrors files from source_root to mirror_root.
    Preserves .grepai directory and watch logs.
    Removes files from mirror_root that no longer exist in file_list.
    Returns (copied_count, unchanged_count, deleted_count).
    """
    mirror_root.mkdir(parents=True, exist_ok=True)
    target_set = set(file_list)
    copied = 0
    unchanged = 0
    deleted = 0

    # 1. Synchronize deletions in mirror_root
    for root, dirs, files in os.walk(str(mirror_root)):
        rel_dir = os.path.relpath(root, str(mirror_root)).replace("\\", "/")
        if rel_dir.startswith(".grepai") or rel_dir == ".grepai":
            dirs.clear()
            continue
        for f in files:
            if f.endswith(".log") and f.startswith("watch_"):
                continue
            rel_file = (rel_dir + "/" + f) if rel_dir != "." else f
            if rel_file not in target_set:
                try:
                    (mirror_root / rel_file).unlink()
                    deleted += 1
                except Exception:
                    pass

    # 2. Synchronize additions and modifications
    for rel in file_list:
        src_path = source_root / rel
        dst_path = mirror_root / rel

        if not src_path.is_file():
            continue

        src_stat = src_path.stat()
        needs_copy = True

        if dst_path.is_file():
            dst_stat = dst_path.stat()
            if src_stat.st_size == dst_stat.st_size and abs(src_stat.st_mtime - dst_stat.st_mtime) < 0.01:
                needs_copy = False

        if needs_copy:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst_path)
            copied += 1
        else:
            unchanged += 1

    return copied, unchanged, deleted


def write_grepai_config(
    workspace_dir: Path,
    model: str,
    dimensions: int,
    parallelism: int,
    endpoint: str = "http://127.0.0.1:1234/v1"
) -> None:
    """Write .grepai/config.yaml with empty api_key (OPENAI_API_KEY injected at runtime)."""
    grepai_dir = workspace_dir / ".grepai"
    grepai_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = grepai_dir / "config.yaml"

    config_yaml = f"""version: 1
embedder:
    provider: openai
    model: {model}
    endpoint: {endpoint}
    api_key: ""
    dimensions: {dimensions}
    parallelism: {parallelism}
    request_timeout_seconds: 600
    max_retries: 5
store:
    backend: gob
chunking:
    size: 300
    overlap: 50
search:
    hybrid:
        enabled: false
"""
    cfg_path.write_text(config_yaml, encoding="utf-8")


def run_indexing_daemon(workspace_dir: Path, timeout_seconds: int = 300) -> Tuple[float, int]:
    """
    Run grepai watch until initial scan completes and symbol index is built.
    Gracefully shuts down the daemon upon completion.
    Returns (index_size_kb, indexed_file_count).
    """
    bin_path = find_binary()
    token = get_lmstudio_token()

    child_env = os.environ.copy()
    child_env["OPENAI_API_KEY"] = token

    stdout_path = workspace_dir / "watch_stdout.log"
    stderr_path = workspace_dir / "watch_stderr.log"

    # Remove stale lock files
    for lock in (workspace_dir / ".grepai").glob("*.lock"):
        try:
            lock.unlink()
        except Exception:
            pass

    cmd = [bin_path, "watch", "--no-ui"]
    with open(stdout_path, "w", encoding="utf-8") as out_f, open(stderr_path, "w", encoding="utf-8") as err_f:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workspace_dir),
            stdin=subprocess.DEVNULL,
            stdout=out_f,
            stderr=err_f,
            text=True,
            env=child_env,
        )

        start_time = time.time()
        initial_scan_done = False

        try:
            while not initial_scan_done:
                if proc.poll() is not None:
                    # Process exited unexpectedly
                    err_text = stderr_path.read_text(encoding="utf-8", errors="replace").strip()
                    raise RuntimeError(f"grepai watch exited prematurely with code {proc.returncode}: {err_text}")

                if time.time() - start_time > timeout_seconds:
                    raise RuntimeError(f"Indexing timed out after {timeout_seconds}s in '{workspace_dir}'")

                if stdout_path.is_file():
                    content = stdout_path.read_text(encoding="utf-8", errors="replace")
                    if "Initial scan complete:" in content or "Watching for changes..." in content:
                        initial_scan_done = True
                        break

                time.sleep(1.0)

        finally:
            # Graceful termination
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:
                    pass

    # Clean up lock files after stopping
    for lock in (workspace_dir / ".grepai").glob("*.lock"):
        try:
            lock.unlink()
        except Exception:
            pass

    index_gob = workspace_dir / ".grepai" / "index.gob"
    if not index_gob.is_file():
        raise RuntimeError(f"Index file '{index_gob}' was not created. Check {stderr_path}")

    size_kb = round(index_gob.stat().st_size / 1024.0, 1)

    # Read status for file count
    status_proc = run_grepai_command(["status"], cwd=str(workspace_dir), check=False)
    file_count = 0
    if status_proc.returncode == 0:
        match = re.search(r"Files indexed:\s*(\d+)", status_proc.stdout)
        if match:
            file_count = int(match.group(1))

    return size_kb, file_count


def index_project(
    project_path: str,
    project_name: Optional[str] = None,
    timeout_seconds: int = 600,
    endpoint: str = "http://127.0.0.1:1234/v1",
) -> Dict[str, Any]:
    """
    Complete indexing of a project directory into workspaces/<name>.
    Honours .gitignore, synchronizes deletions, preserves .grepai across re-indexes.
    Updates registry.json atomically.
    """
    resolved_path = Path(project_path).resolve()
    if not (resolved_path / ".git").exists() and not (resolved_path / ".git").is_file():
        # Check if inside a git repository
        try:
            top_proc = subprocess.run(
                ["git", "-C", str(resolved_path), "rev-parse", "--show-toplevel"],
                capture_output=True,
                check=True,
                text=True
            )
            resolved_path = Path(top_proc.stdout.strip()).resolve()
        except Exception as exc:
            raise RuntimeError(f"'{project_path}' is not inside a git repository: {exc}")

    name = project_name or resolved_path.name
    workspace_root = DEFAULT_WORKSPACES_DIR / name
    text_workspace = workspace_root / "repo-text"
    code_workspace = workspace_root / "repo-code"

    text_workspace.mkdir(parents=True, exist_ok=True)
    code_workspace.mkdir(parents=True, exist_ok=True)

    # 1. Get git-filtered files
    files = get_git_files(resolved_path)
    if not files:
        raise RuntimeError(f"No source files found in git tree for '{resolved_path}'")

    print(f"[{name}] Mirroring {len(files)} files to workspaces/{name}...")
    mirror_repository(resolved_path, text_workspace, files)
    mirror_repository(resolved_path, code_workspace, files)

    # 2. Write configs without plaintext keys
    write_grepai_config(text_workspace, TEXT_MODEL, EMBED_DIMENSIONS, parallelism=4, endpoint=endpoint)
    write_grepai_config(code_workspace, CODE_MODEL, EMBED_DIMENSIONS, parallelism=2, endpoint=endpoint)

    # 3. Index text and code sequentially to prevent GPU contention
    print(f"[{name}] Indexing 137M Text model...")
    text_size_kb, text_file_count = run_indexing_daemon(text_workspace, timeout_seconds=timeout_seconds)

    print(f"[{name}] Indexing 7B Code model...")
    code_size_kb, code_file_count = run_indexing_daemon(code_workspace, timeout_seconds=timeout_seconds)

    # 4. Atomically update registry
    # An empty registry is only valid when registry.json doesn't exist yet (first-ever
    # index). If the file exists, load_registry() must succeed or raise loudly --
    # silently swallowing a corrupt-registry error here would overwrite it with only
    # this one project, dropping every other registered project.
    reg = load_registry() if get_registry_path().is_file() else {}

    reg[name] = {
        "source_path": str(resolved_path),
        "text_dir": str(text_workspace),
        "code_dir": str(code_workspace),
        "indexed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "text_size_kb": text_size_kb,
        "code_size_kb": code_size_kb,
        "file_count": max(text_file_count, code_file_count, len(files)),
    }
    save_registry(reg)
    print(f"[{name}] Indexing complete and registered ({len(files)} files, Text: {text_size_kb}KB, Code: {code_size_kb}KB).")

    return reg[name]


def main():
    parser = argparse.ArgumentParser(description="Index a repository into grepai-hybrid")
    parser.add_argument("project_path", type=str, help="Path to git project root")
    parser.add_argument("--name", "-n", type=str, help="Project name override")
    parser.add_argument("--timeout", "-t", type=int, default=600, help="Indexing timeout in seconds")
    parser.add_argument("--endpoint", default="http://127.0.0.1:1234/v1", help="LM Studio endpoint")
    args = parser.parse_args()

    index_project(
        project_path=args.project_path,
        project_name=args.name,
        timeout_seconds=args.timeout,
        endpoint=args.endpoint
    )


if __name__ == "__main__":
    main()
