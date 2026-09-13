"""Atomic, validating registry for semcode projects."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "workspaces" / "registry.json"


def get_registry_path(custom_path: Optional[str] = None) -> Path:
    if custom_path:
        return Path(custom_path).resolve()
    return DEFAULT_REGISTRY_PATH


def load_registry(registry_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Load and validate registry.json.
    Raises RuntimeError if the file is missing or corrupt.
    Never silently resets to an empty dict.
    """
    path = get_registry_path(registry_path)
    if not path.is_file():
        raise RuntimeError(
            f"Project registry does not exist at '{path}'.\n"
            f"Remediation: Ensure workspaces/registry.json exists or run index_project.ps1 to create it."
        )

    try:
        content = path.read_text(encoding="utf-8-sig")
        data = json.loads(content)
    except Exception as exc:
        raise RuntimeError(
            f"Corrupt or unreadable project registry at '{path}': {exc}\n"
            f"Refusing to proceed to prevent data loss or silent project drops."
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"Project registry at '{path}' must contain a JSON object, got {type(data).__name__}")

    # Validate schema of entries
    for pname, pinfo in data.items():
        if not isinstance(pinfo, dict):
            raise RuntimeError(f"Registry entry '{pname}' is not an object: {pinfo}")
        for field in ("source_path", "text_dir", "code_dir"):
            if field not in pinfo or not pinfo[field]:
                raise RuntimeError(f"Registry entry '{pname}' is missing required field '{field}'")

    return data


def save_registry(data: Dict[str, Dict[str, Any]], registry_path: Optional[str] = None) -> None:
    """
    Atomically save the registry to disk using a temporary file and replace.
    Guarantees no half-written or corrupted registry files.
    """
    path = get_registry_path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".json.tmp")

    formatted = json.dumps(data, indent=4, ensure_ascii=False)
    temp_path.write_text(formatted, encoding="utf-8")
    temp_path.replace(path)


def resolve_project(
    project: Optional[str] = None,
    project_path: Optional[str] = None,
    cwd: Optional[str] = None,
    roots: Optional[List[str]] = None,
    registry: Optional[Dict[str, Dict[str, Any]]] = None,
    registry_path: Optional[str] = None,
) -> Tuple[str, str, str, str]:
    """
    Resolves project text_dir, code_dir, project_name, source_path in strict priority order:
    1. Explicit project name matching registry key
    2. Explicit project_path or project matching registered source_path
    3. MCP roots supplied by client session
    4. Caller / server working directory (cwd)
    5. Raises ValueError naming the target path. No silent fallback to default Go testbed.

    Returns:
        (text_dir, code_dir, project_name, source_path)
    """
    if registry is None:
        registry = load_registry(registry_path)

    # Sort entries by source_path length descending so nested sub-repos match first
    sorted_entries = sorted(
        registry.items(),
        key=lambda pair: len(str(pair[1].get("source_path", ""))),
        reverse=True
    )

    # 1. Direct project name match
    if project and project in registry:
        info = registry[project]
        return info["text_dir"], info["code_dir"], project, info["source_path"]

    # 2. Match by explicit target path (project_path or project argument)
    target = project_path or project
    if target:
        norm_target = os.path.abspath(target).lower().rstrip(os.sep)
        for pname, pinfo in sorted_entries:
            sp = os.path.abspath(pinfo["source_path"]).lower().rstrip(os.sep)
            if norm_target == sp or norm_target.startswith(sp + os.sep):
                return pinfo["text_dir"], pinfo["code_dir"], pname, pinfo["source_path"]
        from semcode.auto_index import maybe_auto_index
        auto_msg = maybe_auto_index(target)
        if auto_msg:
            raise ValueError(auto_msg)
        raise ValueError(
            f"Project path '{target}' is not registered in workspaces/registry.json.\n"
            f"Remediation: Run index_project.ps1 -ProjectPath '{target}' or python -m semcode.indexer '{target}'."
        )

    # 3. Match from MCP client session roots
    if roots:
        for r in roots:
            norm_root = os.path.abspath(r).lower().rstrip(os.sep)
            for pname, pinfo in sorted_entries:
                sp = os.path.abspath(pinfo["source_path"]).lower().rstrip(os.sep)
                if norm_root == sp or norm_root.startswith(sp + os.sep) or sp.startswith(norm_root + os.sep):
                    return pinfo["text_dir"], pinfo["code_dir"], pname, pinfo["source_path"]

    # 4. Auto-detect from CWD
    active_cwd = os.path.abspath(cwd or os.getcwd()).lower().rstrip(os.sep)
    for pname, pinfo in sorted_entries:
        sp = os.path.abspath(pinfo["source_path"]).lower().rstrip(os.sep)
        if active_cwd == sp or active_cwd.startswith(sp + os.sep):
            return pinfo["text_dir"], pinfo["code_dir"], pname, pinfo["source_path"]

    # 5. Fail loudly with no silent fallback (G8) and trigger auto-index if in a git repo
    from semcode.auto_index import maybe_auto_index
    auto_msg = maybe_auto_index(active_cwd)
    if auto_msg:
        raise ValueError(auto_msg)

    raise ValueError(
        f"Directory '{active_cwd}' is not registered in workspaces/registry.json.\n"
        f"Remediation: Pass --project <name> or index this repository with `index_project.ps1 -ProjectPath <path>`."
    )
