#!/usr/bin/env python3
"""
Hyperparameter Optimizer for grepai Hybrid Retrieval
Evaluates combinations of RRF smoothing constant (k) and model skew weights
(w_text, w_code) against a ground truth benchmark suite to find the optimal configuration.
"""

import argparse
import itertools
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


def normalize_path(p: str) -> str:
    return p.replace("\\", "/").lower().strip()


def prefetch_results(
    bin_path: str,
    text_dir: str,
    code_dir: str,
    cases: List[Dict[str, Any]],
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Caches search results for all cases to allow instant in-memory grid search."""
    print(f"Pre-fetching retrieval results for {len(cases)} queries from both models...")
    cache = []

    for idx, c in enumerate(cases, 1):
        q = c["query"]
        exp = normalize_path(c["expected_file"])

        # Fetch from text repo
        cmd_text = [bin_path, "search", q, "-j", "-n", str(limit)]
        p_text = subprocess.run(cmd_text, cwd=text_dir, capture_output=True, text=True, encoding="utf-8")
        try:
            res_text = json.loads(p_text.stdout) if p_text.stdout else []
        except Exception:
            res_text = []

        # Fetch from code repo
        cmd_code = [bin_path, "search", q, "-j", "-n", str(limit)]
        p_code = subprocess.run(cmd_code, cwd=code_dir, capture_output=True, text=True, encoding="utf-8")
        try:
            res_code = json.loads(p_code.stdout) if p_code.stdout else []
        except Exception:
            res_code = []

        # Extract file ranks
        files_text = {}
        for r_idx, item in enumerate(res_text):
            fp = normalize_path(item.get("file_path", item.get("file", "")))
            if fp and fp not in files_text:
                files_text[fp] = r_idx + 1

        files_code = {}
        for r_idx, item in enumerate(res_code):
            fp = normalize_path(item.get("file_path", item.get("file", "")))
            if fp and fp not in files_code:
                files_code[fp] = r_idx + 1

        cache.append({
            "id": c.get("id", f"case_{idx}"),
            "expected_file": exp,
            "files_text": files_text,
            "files_code": files_code
        })

    return cache


def evaluate_grid(
    cache: List[Dict[str, Any]],
    k: int,
    w_text: float,
    w_code: float
) -> Tuple[float, float, float, float, float]:
    """Computes Hit@1, Hit@3, Hit@5, MRR, and Composite Objective."""
    n = len(cache)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    hit_1 = 0
    hit_3 = 0
    hit_5 = 0
    mrr_sum = 0.0

    for item in cache:
        exp = item["expected_file"]
        files_text = item["files_text"]
        files_code = item["files_code"]

        all_files = set(files_text.keys()).union(set(files_code.keys()))
        scored = []
        for fp in all_files:
            score = 0.0
            if fp in files_text:
                score += w_text / (k + files_text[fp])
            if fp in files_code:
                score += w_code / (k + files_code[fp])
            scored.append((fp, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        rank = None
        for idx, (fp, score) in enumerate(scored):
            if exp in fp:
                rank = idx + 1
                break

        if rank:
            mrr_sum += 1.0 / rank
            if rank == 1:
                hit_1 += 1
            if rank <= 3:
                hit_3 += 1
            if rank <= 5:
                hit_5 += 1

    h1_rate = hit_1 / n
    h3_rate = hit_3 / n
    h5_rate = hit_5 / n
    mrr = mrr_sum / n

    # Composite objective: 60% Hit@3 (agent window) + 40% MRR
    composite = (0.6 * h3_rate) + (0.4 * mrr)
    return h1_rate, h3_rate, h5_rate, mrr, composite


def main():
    parser = argparse.ArgumentParser(description="Tune grepai Hybrid Retrieval Hyperparameters")
    parser.add_argument("--cases", type=str, default="benchmarks/cases.json", help="Benchmark cases JSON")
    parser.add_argument("--text-dir", type=str, default="repo-text", help="137M text model indexed repository")
    parser.add_argument("--code-dir", type=str, default="repo-code", help="7B code model indexed repository")
    parser.add_argument("--grepai-bin", type=str, default="bin/grepai.exe", help="Path to grepai binary")
    parser.add_argument("--output", type=str, default="benchmarks/optimal_params.json", help="Path to save best parameters")
    args = parser.parse_args()

    with open(args.cases, "r", encoding="utf-8") as f:
        cases = json.load(f)

    # Step 1: Pre-fetch search results to avoid redundant model inference
    cache = prefetch_results(args.grepai_bin, args.text_dir, args.code_dir, cases)

    # Step 2: Grid Search space
    k_vals = [5, 10, 15, 20, 25, 30, 45, 60]
    w_text_vals = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]
    w_code_vals = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]

    total_combinations = len(k_vals) * len(w_text_vals) * len(w_code_vals)
    print(f"\nRunning grid search across {total_combinations} parameter combinations...")

    best_config = None
    best_score = -1.0
    results = []

    for k, wt, wc in itertools.product(k_vals, w_text_vals, w_code_vals):
        h1, h3, h5, mrr, score = evaluate_grid(cache, k, wt, wc)
        cfg = {
            "k": k,
            "weight_text": wt,
            "weight_code": wc,
            "hit_at_1": h1,
            "hit_at_3": h3,
            "hit_at_5": h5,
            "mrr": mrr,
            "composite_score": score
        }
        results.append(cfg)
        if score > best_score:
            best_score = score
            best_config = cfg

    # Sort results by composite score
    results.sort(key=lambda x: x["composite_score"], reverse=True)

    print("\n" + "=" * 78)
    print("                     HYPERPARAMETER OPTIMIZATION LEADERBOARD")
    print("=" * 78)
    print(f"{'Rank':<5} | {'k':<4} | {'w_text':<6} | {'w_code':<6} | {'Hit@1':<8} | {'Hit@3':<8} | {'MRR':<8} | {'Score':<8}")
    print("-" * 78)
    for idx, r in enumerate(results[:8], 1):
        print(f"{idx:<5} | {r['k']:<4} | {r['weight_text']:<6.1f} | {r['weight_code']:<6.1f} | {r['hit_at_1']*100:>6.1f}% | {r['hit_at_3']*100:>6.1f}% | {r['mrr']:>7.3f} | {r['composite_score']:>7.3f}")
    print("=" * 78)

    print(f"\n[OPTIMAL CONFIGURATION FOUND]")
    print(f"  RRF Constant (k):       {best_config['k']}")
    print(f"  Weight Text (w_text):   {best_config['weight_text']}")
    print(f"  Weight Code (w_code):   {best_config['weight_code']}")
    print(f"  Resulting Hit@3:        {best_config['hit_at_3']*100:.1f}%")
    print(f"  Resulting MRR:          {best_config['mrr']:.3f}")

    out_file = Path(args.output)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(best_config, f, indent=2)

    print(f"\nSaved optimal configuration to: {args.output}")


if __name__ == "__main__":
    main()
