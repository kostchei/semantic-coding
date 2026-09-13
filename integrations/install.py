#!/usr/bin/env python3
"""Cross-agent integration installer implementation in Python."""

from datetime import datetime
import json
from pathlib import Path
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
USER_HOME = Path.home()


def backup_file(path: Path) -> None:
    if path.is_file():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = path.with_name(f"{path.name}.{ts}.bak")
        shutil.copy2(path, bak)
        print(f"Backed up: {path} -> {bak}")


def install_instructions():
    tmpl_path = REPO_ROOT / "integrations" / "instructions.md"
    block = tmpl_path.read_text(encoding="utf-8").strip()

    targets = [
        USER_HOME / ".claude" / "CLAUDE.md",
        USER_HOME / ".codex" / "AGENTS.md",
        USER_HOME / ".gemini" / "GEMINI.md",
    ]

    for t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        content = ""
        if t.is_file():
            content = t.read_text(encoding="utf-8")
            backup_file(t)

        marker_begin = "<!-- grepai-hybrid:begin -->"
        marker_end = "<!-- grepai-hybrid:end -->"

        if marker_begin in content and marker_end in content:
            idx_start = content.find(marker_begin)
            idx_end = content.find(marker_end) + len(marker_end)
            new_content = content[:idx_start].rstrip() + "\n\n" + block + "\n" + content[idx_end:].lstrip()
        else:
            sep = "\n\n" if content.strip() else ""
            new_content = content.rstrip() + sep + block + "\n"

        t.write_text(new_content, encoding="utf-8")
        print(f"Updated instructions in {t}")


def install_claude_json():
    path = USER_HOME / ".claude.json"
    data = {}
    if path.is_file():
        backup_file(path)
        data = json.loads(path.read_text(encoding="utf-8"))

    # Deduplicate: Remove project-level grepai-hybrid if present
    projects = data.get("projects", {})
    for proj_key, proj_data in list(projects.items()):
        if "semantic_coding" in proj_key.lower():
            if "mcpServers" in proj_data and "grepai-hybrid" in proj_data["mcpServers"]:
                del proj_data["mcpServers"]["grepai-hybrid"]
                print(f"Removed duplicate project-level grepai-hybrid from {proj_key}")

    # Ensure user-level registration
    if "mcpServers" not in data:
        data["mcpServers"] = {}

    mcp_script = str(REPO_ROOT / "mcp_server.py")
    data["mcpServers"]["grepai-hybrid"] = {
        "command": sys.executable,
        "args": [mcp_script]
    }

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Verified global grepai-hybrid in {path}")


def install_claude_settings():
    path = USER_HOME / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {}
    if path.is_file():
        backup_file(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    hook_script = str(REPO_ROOT / "integrations" / "hooks" / "prompt_context.py")
    if "hooks" not in data:
        data["hooks"] = {}

    # Claude Code's settings.json hooks schema wraps each command in a
    # matcher-group with an inner "hooks" array -- a bare {"command": ...}
    # entry is silently discarded rather than executed.
    data["hooks"]["UserPromptSubmit"] = [
        {"hooks": [{"type": "command", "command": f'"{sys.executable}" "{hook_script}" --event UserPromptSubmit'}]}
    ]
    data["hooks"]["SessionStart"] = [
        {"hooks": [{"type": "command", "command": f'"{sys.executable}" "{hook_script}" --event SessionStart'}]}
    ]

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Installed prompt hooks in {path}")


def install_antigravity():
    # 1. Register in mcp_config.json
    cfg_path = USER_HOME / ".gemini" / "antigravity" / "mcp_config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    data = {"mcpServers": {}}
    if cfg_path.is_file():
        backup_file(cfg_path)
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            data = {"mcpServers": {}}

    if "mcpServers" not in data:
        data["mcpServers"] = {}

    mcp_script = str(REPO_ROOT / "mcp_server.py")
    data["mcpServers"]["grepai-hybrid"] = {
        "command": sys.executable,
        "args": [mcp_script]
    }
    cfg_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    print(f"Registered grepai-hybrid in {cfg_path}")

    # 2. Delete stale descriptor
    stale_dir = USER_HOME / ".gemini" / "antigravity" / "mcp" / "grepai-hybrid"
    if stale_dir.is_dir():
        shutil.rmtree(stale_dir, ignore_errors=True)
        print(f"Deleted stale descriptor: {stale_dir}")


def install_skills():
    skill_src = REPO_ROOT / "integrations" / "skill" / "SKILL.md"

    targets = [
        USER_HOME / ".gemini" / "config" / "skills" / "grepai-hybrid" / "SKILL.md",
        USER_HOME / ".codex" / "skills" / "grepai-hybrid" / "SKILL.md",
    ]

    for t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_src, t)
        print(f"Installed skill: {t}")


def main():
    print("Installing grepai-hybrid integrations...")
    install_instructions()
    install_claude_json()
    install_claude_settings()
    install_antigravity()
    install_skills()
    print("Integration install complete!")


if __name__ == "__main__":
    main()
