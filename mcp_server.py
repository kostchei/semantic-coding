#!/usr/bin/env python3
"""
grepai-hybrid MCP Server
Exposes the Two-Stage Hybrid Search Engine (137M Text + 7B Code + Local Re-Rank)
as a standard Model Context Protocol (MCP) server for Antigravity, Claude Code, and Codex.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

# Ensure local imports work
script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir))

import hybrid_search

# Initialize FastMCP Server
mcp = FastMCP(
    "grepai-hybrid",
    dependencies=["mcp", "numpy", "torch"]
)

# Workspace directories
DEFAULT_TEXT_DIR = str(script_dir / "repo-text")
DEFAULT_CODE_DIR = str(script_dir / "repo-code")


@mcp.tool()
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
        project: Optional registered project name (e.g. 'praetor_silica') or path. Auto-resolves from caller CWD if omitted.
        limit: Max number of top code snippets to return (default: 5).
        rerank: Set to True to enable Stage 2 local LLM cross-encoder re-ranking for strict false-positive filtering.
        feedback_file: Optional file path that was confirmed relevant, to log training triplets for fine-tuning.

    Returns:
        Formatted markdown containing top matching code chunks, line numbers, scores, and relevance reasoning.
    """
    text_dir, code_dir, resolved_proj = hybrid_search.resolve_project_dirs(project=project)
    bin_path = hybrid_search.find_binary()
    token = hybrid_search.get_stored_credential("PraetorSilica/LMStudioDev")

    # Load optimal hyperparameters
    k_val = 5
    w_text = 1.5
    w_code = 0.5
    optimal_file = script_dir / "benchmarks" / "optimal_params.json"
    if optimal_file.is_file():
        try:
            with open(optimal_file, "r", encoding="utf-8") as f:
                opt = json.load(f)
                k_val = opt.get("k", 5)
                w_text = opt.get("weight_text", 1.5)
                w_code = opt.get("weight_code", 0.5)
        except Exception:
            pass

    # Stage 1: Parallel Dense Retrieval
    with hybrid_search.ThreadPoolExecutor(max_workers=2) as executor:
        f_text = executor.submit(hybrid_search.run_single_search, bin_path, text_dir, query, 15)
        f_code = executor.submit(hybrid_search.run_single_search, bin_path, code_dir, query, 15)
        text_res = f_text.result()
        code_res = f_code.result()

    fused = hybrid_search.reciprocal_rank_fusion(
        text_res, code_res, k=k_val, weight_text=w_text, weight_code=w_code, limit=10
    )

    # Stage 2: Local Re-ranking if requested
    if rerank:
        fused = hybrid_search.rerank_with_llm(
            candidates=fused,
            query=query,
            token=token,
            timeout=20
        )

    # Telemetry logging
    try:
        from telemetry.collector import log_interaction
        log_interaction(
            query=query,
            candidates=fused,
            selected_file=feedback_file
        )
    except Exception:
        pass

    results = fused[:limit]
    if not results:
        return f"No matching code snippets found for query: \"{query}\""

    # Format as clean markdown for AI agent ingestion
    mode_str = "Hybrid RRF + Local Re-Rank" if rerank else f"Hybrid RRF (k={k_val}, wt={w_text:.1f}, wc={w_code:.1f})"
    proj_tag = f" [Project: {resolved_proj}]" if resolved_proj != "default" else ""
    output = [f"### grepai Hybrid Search Results: `{query}` ({mode_str}){proj_tag}\n"]

    for idx, r in enumerate(results, 1):
        fp = r["file_path"]
        lines = f"L{r['start_line']}-{r['end_line']}"
        score = r["rrf_score"]
        t_rank = f"#{r['text_rank']}" if r.get("text_rank") else "miss"
        c_rank = f"#{r['code_rank']}" if r.get("code_rank") else "miss"

        header = f"#### {idx}. [{fp} ({lines})](file:///{fp}#L{r['start_line']}-L{r['end_line']})\n"
        meta = f"- **RRF Score:** `{score:.4f}` | **Text Rank:** `{t_rank}` | **Code Rank:** `{c_rank}`"
        if r.get("rerank_score") is not None:
            meta += f" | **Re-Rank Score:** `{r['rerank_score']:.2f}`"
        if r.get("rerank_reason"):
            meta += f"\n- **Reasoning:** {r['rerank_reason']}"

        snippet = f"\n```go\n{r.get('content', '').strip()}\n```\n"
        output.append(f"{header}{meta}\n{snippet}")

    return "\n".join(output)


if __name__ == "__main__":
    # Run via FastMCP standard stdio transport
    mcp.run(transport="stdio")
