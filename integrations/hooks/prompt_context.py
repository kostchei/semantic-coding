#!/usr/bin/env python3
"""
Claude Code integration hooks for grepai-hybrid.
Supports UserPromptSubmit (injecting relevant semantic code context)
and SessionStart (displaying project index status and freshness).
"""

import argparse
import json
import os
from pathlib import Path
import sys

# Ensure semcode package is importable
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from semcode.pipeline import execute_hybrid_search
from semcode.registry import load_registry, resolve_project


def handle_user_prompt_submit(data: dict) -> dict:
    prompt = data.get("prompt", "").strip()
    cwd = data.get("cwd") or os.getcwd()

    # Ignore slash commands and trivial short queries (< 3 words)
    if prompt.startswith("/") or len(prompt.split()) < 3:
        return {}

    # Check if cwd is inside a registered project
    try:
        text_dir, code_dir, project_name, source_path = resolve_project(cwd=cwd)
    except Exception:
        # Not a registered project: out of scope, emit nothing
        return {}

    # Run fast hybrid search (k=15, limit=5, no rerank to keep p95 latency under 1s)
    try:
        res = execute_hybrid_search(
            query=prompt,
            project=project_name,
            text_dir=text_dir,
            code_dir=code_dir,
            limit=5,
            rerank=False,
            cwd=cwd,
        )
        hits = res.get("results", [])
        if not hits:
            return {}

        # Format compact additional context (under ~1.5k tokens)
        lines = [f"[grepai-hybrid context for '{prompt}' in {project_name}]:"]
        for idx, h in enumerate(hits, 1):
            fp = h.get("absolute_path") or h.get("file_path")
            lines.append(f"{idx}. {fp}:L{h.get('start_line')}-{h.get('end_line')} (RRF {h.get('rrf_score', 0):.3f})")
            snippet = h.get("content", "").strip().splitlines()
            if snippet:
                preview = " ".join(snippet[:2])[:120]
                lines.append(f"   preview: {preview}")

        return {"additionalContext": "\n".join(lines)}

    except Exception as exc:
        # If project is registered but search failed, output the error loudly
        return {"additionalContext": f"[grepai-hybrid error: {exc}]"}


def handle_session_start(data: dict) -> dict:
    cwd = data.get("cwd") or os.getcwd()
    try:
        text_dir, code_dir, project_name, source_path = resolve_project(cwd=cwd)
        reg = load_registry()
        pinfo = reg.get(project_name, {})
        indexed_at = pinfo.get("indexed_at", "unknown")
        file_count = pinfo.get("file_count", 0)
        return {
            "additionalContext": (
                f"[grepai-hybrid: Project '{project_name}' registered ({file_count} files, "
                f"indexed: {indexed_at}). Use search_codebase for semantic queries.]"
            )
        }
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(description="grepai Claude Code Hook")
    parser.add_argument("--event", choices=["UserPromptSubmit", "SessionStart"], default="UserPromptSubmit")
    args = parser.parse_args()

    input_data = {}
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read().strip()
            if raw:
                input_data = json.loads(raw)
    except Exception:
        pass

    if args.event == "UserPromptSubmit":
        out = handle_user_prompt_submit(input_data)
    elif args.event == "SessionStart":
        out = handle_session_start(input_data)
    else:
        out = {}

    if out:
        sys.stdout.write(json.dumps(out))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
