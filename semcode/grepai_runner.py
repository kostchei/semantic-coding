"""grepai process runner with credential injection and safe stdin/stderr handling."""

import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from semcode.creds import get_lmstudio_token


def find_binary(custom_path: Optional[str] = None) -> str:
    """Resolve the grepai executable path. Raises FileNotFoundError if not found."""
    if custom_path:
        cp = Path(custom_path).resolve()
        if cp.is_file():
            return str(cp)
        raise FileNotFoundError(f"Specified grepai binary does not exist: {custom_path}")

    # Check local bin/grepai.exe relative to repo root
    repo_root = Path(__file__).resolve().parent.parent
    local_bin = repo_root / "bin" / "grepai.exe"
    if local_bin.is_file():
        return str(local_bin)

    which = shutil.which("grepai")
    if which:
        return which

    raise FileNotFoundError(
        "Could not find grepai.exe in repo bin/ or system PATH.\n"
        "Remediation: Ensure bin/grepai.exe exists or add grepai to PATH."
    )


def run_grepai_command(
    args: List[str],
    cwd: str,
    timeout: int = 60,
    check: bool = True,
    capture_output: bool = True,
    custom_binary: Optional[str] = None,
    extra_env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    """
    Run a grepai CLI command with injected OPENAI_API_KEY for this child process only.
    Parent process environment is never modified.
    Input stdin is set to DEVNULL so child processes cannot consume the parent stream.
    """
    bin_path = find_binary(custom_binary)
    token = get_lmstudio_token()

    # Build child-only environment
    child_env = os.environ.copy()
    child_env["OPENAI_API_KEY"] = token
    if extra_env:
        child_env.update(extra_env)

    full_cmd = [bin_path] + args
    try:
        proc = subprocess.run(
            full_cmd,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=capture_output,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
            env=child_env,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"grepai command {args} timed out after {timeout}s in directory '{cwd}'."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Failed to execute grepai binary '{bin_path}' in '{cwd}': {exc}"
        ) from exc

    if check and proc.returncode != 0:
        stderr_msg = proc.stderr.strip() if proc.stderr else "No stderr output."
        stdout_msg = proc.stdout.strip() if proc.stdout else ""
        raise RuntimeError(
            f"grepai command failed (exit code {proc.returncode}) in '{cwd}':\n"
            f"Command: {' '.join(full_cmd)}\n"
            f"Error: {stderr_msg}\n"
            f"{'Output: ' + stdout_msg if stdout_msg else ''}"
        )

    return proc


def run_grepai_search(
    repo_dir: str,
    query: str,
    limit: int = 15,
    custom_binary: Optional[str] = None,
    timeout: int = 60,
) -> List[Dict[str, Any]]:
    """
    Execute a semantic search on a single grepai index directory and return parsed JSON hits.
    Raises RuntimeError on backend errors or non-zero exit codes.
    """
    proc = run_grepai_command(
        args=["search", query, "-j", "-n", str(limit)],
        cwd=repo_dir,
        timeout=timeout,
        check=True,
        capture_output=True,
        custom_binary=custom_binary,
    )

    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError(f"grepai returned empty output instead of JSON in '{repo_dir}'")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"grepai returned invalid JSON in '{repo_dir}': {exc}\nRaw output: {stdout[:500]}"
        ) from exc

    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and isinstance(data.get("results"), list):
        return data["results"]

    raise RuntimeError(f"grepai returned unrecognized JSON format in '{repo_dir}': {type(data).__name__}")
