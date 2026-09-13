#!/usr/bin/env python3
"""
grepai-hybrid: Multi-Model Reciprocal Rank Fusion (RRF) Search Engine
Combines 137M Text (nomic-embed-text) and 7B Code (nomic-embed-code)
for maximum semantic recall and precision.
"""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Tuple


def find_binary(custom_path: str = None) -> str:
    if custom_path and os.path.isfile(custom_path):
        return custom_path
    script_dir = Path(__file__).resolve().parent
    local_bin = script_dir / "bin" / "grepai.exe"
    if local_bin.is_file():
        return str(local_bin)
    import shutil
    which = shutil.which("grepai")
    if which:
        return which
    raise FileNotFoundError("Could not find grepai.exe")


def run_single_search(bin_path: str, repo_dir: str, query: str, limit: int = 15) -> List[Dict[str, Any]]:
    cmd = [bin_path, "search", query, "-j", "-n", str(limit)]
    try:
        proc = subprocess.run(
            cmd, cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", check=False
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        data = json.loads(proc.stdout)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "results" in data:
            return data["results"]
        return []
    except Exception:
        return []


def reciprocal_rank_fusion(
    text_results: List[Dict[str, Any]],
    code_results: List[Dict[str, Any]],
    k: int = 15,
    weight_text: float = 1.0,
    weight_code: float = 1.1,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Fuses two ranked lists using document-level Reciprocal Rank Fusion (RRF).
    Uses the best chunk per file for candidate display while scoring by reciprocal rank.
    """
    best_chunk_per_file: Dict[str, Dict[str, Any]] = {}
    file_ranks_text: Dict[str, int] = {}
    file_ranks_code: Dict[str, int] = {}

    for rank, item in enumerate(text_results):
        fp = item.get("file_path", "").replace("\\", "/").lower()
        if not fp:
            continue
        if fp not in file_ranks_text:
            file_ranks_text[fp] = rank + 1
            best_chunk_per_file[fp] = item

    for rank, item in enumerate(code_results):
        fp = item.get("file_path", "").replace("\\", "/").lower()
        if not fp:
            continue
        if fp not in file_ranks_code:
            file_ranks_code[fp] = rank + 1
            if fp not in best_chunk_per_file or item.get("score", 0) > best_chunk_per_file[fp].get("score", 0):
                best_chunk_per_file[fp] = item

    all_files = set(file_ranks_text.keys()).union(set(file_ranks_code.keys()))
    scored_files = []

    for fp in all_files:
        rrf_score = 0.0
        t_rank = file_ranks_text.get(fp)
        c_rank = file_ranks_code.get(fp)

        if t_rank:
            rrf_score += weight_text / (k + t_rank)
        if c_rank:
            rrf_score += weight_code / (k + c_rank)

        chunk_info = best_chunk_per_file[fp]
        scored_files.append({
            "file_path": chunk_info.get("file_path"),
            "start_line": chunk_info.get("start_line"),
            "end_line": chunk_info.get("end_line"),
            "rrf_score": rrf_score,
            "text_rank": t_rank,
            "code_rank": c_rank,
            "content": chunk_info.get("content", "")
        })

    scored_files.sort(key=lambda x: x["rrf_score"], reverse=True)
    return scored_files[:limit]


def main():
    parser = argparse.ArgumentParser(description="grepai Multi-Model Hybrid Search (Text + Code RRF)")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("--text-dir", type=str, default="repo-text", help="Directory indexed with 137M text model")
    parser.add_argument("--code-dir", type=str, default="repo-code", help="Directory indexed with 7B code model")
    parser.add_argument("--limit", "-n", type=int, default=5, help="Number of results to return (default: 5)")
    parser.add_argument("--json", "-j", action="store_true", help="Output results in JSON format")
    parser.add_argument("--k", type=int, default=15, help="RRF smoothing constant (default: 15)")
    args = parser.parse_args()

    bin_path = find_binary()

    # Search both repositories in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_text = executor.submit(run_single_search, bin_path, args.text_dir, args.query, 15)
        f_code = executor.submit(run_single_search, bin_path, args.code_dir, args.query, 15)
        text_res = f_text.result()
        code_res = f_code.result()

    fused = reciprocal_rank_fusion(text_res, code_res, k=args.k, limit=args.limit)

    if args.json:
        print(json.dumps(fused, indent=2))
        return

    print(f"\nHybrid Fused Search Results for: \"{args.query}\"\n" + "=" * 70)
    for idx, item in enumerate(fused, 1):
        fp = item["file_path"]
        lines = f"L{item['start_line']}-{item['end_line']}"
        score = item["rrf_score"]
        t_rank = f"#{item['text_rank']}" if item["text_rank"] else "miss"
        c_rank = f"#{item['code_rank']}" if item["code_rank"] else "miss"

        print(f"[{idx}] {fp}:{lines}")
        print(f"    RRF Score: {score:.4f} | Text Rank: {t_rank} | Code Rank: {c_rank}")
        snippet = item["content"].split("\n")[:3]
        for s in snippet:
            if s.strip():
                print(f"    | {s.strip()[:80]}")
        print("-" * 70)


if __name__ == "__main__":
    main()
