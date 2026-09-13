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

import semcode.pipeline as pipeline

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

    # Let the pipeline resolve the project itself (semcode.registry.resolve_project):
    # this is what supports MCP client roots and triggers background auto-indexing
    # for an unregistered-but-eligible git repo. Resolving here instead (e.g. via
    # hybrid_search.resolve_project_dirs) would bypass both.
    res = pipeline.execute_hybrid_search(
        query=query,
        project=project,
        cwd=os.getcwd(),
        limit=limit,
        rerank=rerank,
        feedback_file=feedback_file,
    )

    return pipeline.format_search_markdown(res)


if __name__ == "__main__":
    # Run via FastMCP standard stdio transport
    mcp.run(transport="stdio")
