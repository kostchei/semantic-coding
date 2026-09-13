#!/usr/bin/env python3
"""
grepai-hybrid MCP Server
Exposes the Two-Stage Hybrid Search Engine (137M Text + 7B Code + Local Re-Rank)
as a standard Model Context Protocol (MCP) server for Antigravity, Claude Code, and Codex.
"""

import os
from pathlib import Path
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Ensure local imports work
script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir))

import hybrid_search
import semcode.pipeline as pipeline
import semcode.registry as registry

# Initialize FastMCP Server with prompt instructions
mcp = FastMCP(
    "grepai-hybrid",
    instructions=(
        "For conceptual 'where/how is X implemented' questions in an indexed project, "
        "call search_codebase before Grep/Glob. Use Grep only for exact identifiers."
    ),
    dependencies=["mcp"]
)


@mcp.tool(
    description=(
        "Deep semantic code search across indexed projects. Call this tool BEFORE Grep/Glob "
        "for conceptual, algorithmic, architectural, or business logic questions (e.g. 'where is authentication handled?', "
        "'how are retry backoffs implemented?'). Use Grep only for known exact identifier names."
    )
)
def search_codebase(
    query: str,
    project: Optional[str] = None,
    limit: int = 5,
    rerank: bool = False,
    feedback_file: Optional[str] = None
) -> str:
    """
    Performs deep semantic code search across the codebase using a Two-Stage Hybrid Engine.
    Combines nomic-embed-text (137M) for natural language synonyms and nomic-embed-code (7B)
    for algorithmic code logic via Reciprocal Rank Fusion (RRF).

    Args:
        query: The search query (e.g. 'platform lock file verification' or 'throttle client queries').
        project: Optional registered project name or source path. Auto-resolves from caller directory if omitted.
        limit: Max number of top code snippets to return (default: 5, max: 15).
        rerank: Set to True to enable Stage 2 local LLM cross-encoder re-ranking for strict false-positive filtering.
        feedback_file: Optional file path that was confirmed relevant, to log training triplets for fine-tuning.

    Returns:
        Formatted markdown containing top matching code chunks, absolute source paths, line numbers, scores, and links.
    """
    if not 1 <= limit <= 15:
        raise ValueError("limit must be between 1 and 15")

    # Resolve project text_dir and code_dir (compatible with test harness monkey-patching)
    text_dir, code_dir, resolved_proj = hybrid_search.resolve_project_dirs(project=project)
    source_path = None
    try:
        reg = registry.load_registry()
        if resolved_proj in reg:
            source_path = reg[resolved_proj].get("source_path")
    except Exception:
        pass

    res = pipeline.execute_hybrid_search(
        query=query,
        project=resolved_proj,
        text_dir=text_dir,
        code_dir=code_dir,
        limit=limit,
        rerank=rerank,
        feedback_file=feedback_file,
    )
    if source_path and not res.get("source_path"):
        res["source_path"] = source_path
        # Re-resolve absolute paths and URLs with source_path
        for c in res.get("results", []):
            rel_fp = str(c.get("file_path", "")).replace("/", "\\")
            abs_fp = (Path(source_path) / rel_fp).resolve()
            c["absolute_path"] = str(abs_fp)
            c["file_url"] = f"file:///{str(abs_fp).replace(os.sep, '/')}"

    return pipeline.format_search_markdown(res)


if __name__ == "__main__":
    # Run via FastMCP standard stdio transport
    mcp.run(transport="stdio")
