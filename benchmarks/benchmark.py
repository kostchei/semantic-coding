#!/usr/bin/env python3
"""
grepai Comparative Embedding Benchmark Harness
Compares retrieval accuracy and latency between embedding models (e.g. nomic-embed-text vs 7B code embedder),
with full support for evaluating Hybrid Multi-Model RRF retrieval.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def find_grepai_binary(custom_path: Optional[str] = None) -> str:
    """Locates the grepai binary."""
    if custom_path and os.path.isfile(custom_path):
        return custom_path

    # Check ../bin/grepai.exe relative to this script
    script_dir = Path(__file__).resolve().parent
    local_bin = script_dir.parent / "bin" / "grepai.exe"
    if local_bin.is_file():
        return str(local_bin)

    which_bin = shutil.which("grepai")
    if which_bin:
        return which_bin

    raise FileNotFoundError(
        "Could not find grepai executable. Please specify --grepai-bin or place grepai.exe in bin/"
    )


def normalize_path(p: str) -> str:
    """Normalize file paths for cross-platform comparison."""
    return p.replace("\\", "/").lower().strip()


def run_grepai_search(
    bin_path: str,
    target_dir: str,
    query: str,
    limit: int = 10,
    dry_run: bool = False
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Executes grepai search with JSON output.
    Returns (results, latency_ms).
    """
    if dry_run:
        time.sleep(0.01)
        return [
            {"file_path": "embedder/retry.go", "score": 0.89, "start_line": 25, "end_line": 60},
            {"file_path": "embedder/rate_limiter.go", "score": 0.74, "start_line": 10, "end_line": 40},
            {"file_path": "search/hybrid.go", "score": 0.65, "start_line": 1, "end_line": 30}
        ], 12.5

    start_time = time.perf_counter()
    cmd = [bin_path, "search", query, "-j", "-n", str(limit)]

    try:
        proc = subprocess.run(
            cmd,
            cwd=target_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if proc.returncode != 0:
            sys.stderr.write(f"Search warning for query '{query}': {proc.stderr.strip()}\n")
            return [], latency_ms

        raw_output = proc.stdout.strip()
        if not raw_output:
            return [], latency_ms

        parsed = json.loads(raw_output)
        if isinstance(parsed, list):
            return parsed, latency_ms
        elif isinstance(parsed, dict) and "results" in parsed:
            return parsed["results"], latency_ms
        return [], latency_ms

    except Exception as e:
        sys.stderr.write(f"Error executing grepai search: {e}\n")
        return [], 0.0


def evaluate_directory(
    bin_path: str,
    target_dir: str,
    cases: List[Dict[str, Any]],
    limit: int = 10,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Evaluates a test suite against a single indexed directory."""
    evaluations = []
    mrr_sum = 0.0
    hit_1_count = 0
    hit_3_count = 0
    hit_5_count = 0
    total_margin = 0.0
    valid_margins = 0
    latencies = []

    for case in cases:
        query = case["query"]
        expected_file = normalize_path(case["expected_file"])
        category = case.get("category", "General")

        results, latency_ms = run_grepai_search(
            bin_path=bin_path,
            target_dir=target_dir,
            query=query,
            limit=limit,
            dry_run=dry_run
        )
        latencies.append(latency_ms)

        found_rank = None
        target_score = 0.0
        top_score = 0.0
        score_margin = 0.0

        if results:
            top_score = float(results[0].get("score", 0.0))

            for idx, item in enumerate(results):
                item_file = normalize_path(item.get("file_path", item.get("file", item.get("path", ""))))
                if expected_file in item_file:
                    found_rank = idx + 1
                    target_score = float(item.get("score", 0.0))
                    break

            if len(results) > 1:
                second_score = float(results[1].get("score", 0.0))
                score_margin = top_score - second_score
                total_margin += score_margin
                valid_margins += 1

        reciprocal_rank = 1.0 / found_rank if found_rank else 0.0
        mrr_sum += reciprocal_rank

        if found_rank == 1:
            hit_1_count += 1
        if found_rank and found_rank <= 3:
            hit_3_count += 1
        if found_rank and found_rank <= 5:
            hit_5_count += 1

        evaluations.append({
            "id": case.get("id", ""),
            "category": category,
            "query": query,
            "expected_file": case["expected_file"],
            "rank": found_rank,
            "target_score": target_score,
            "top_score": top_score,
            "score_margin": score_margin,
            "latency_ms": latency_ms,
            "hit": found_rank is not None
        })

    n = len(cases)
    avg_mrr = mrr_sum / n if n > 0 else 0.0
    avg_latency = sum(latencies) / n if n > 0 else 0.0
    avg_margin = total_margin / valid_margins if valid_margins > 0 else 0.0

    return {
        "target_dir": target_dir,
        "total_queries": n,
        "mrr": avg_mrr,
        "hit_at_1": hit_1_count / n if n > 0 else 0.0,
        "hit_at_3": hit_3_count / n if n > 0 else 0.0,
        "hit_at_5": hit_5_count / n if n > 0 else 0.0,
        "avg_score_margin": avg_margin,
        "avg_latency_ms": avg_latency,
        "details": evaluations
    }


def evaluate_hybrid(
    bin_path: str,
    text_dir: str,
    code_dir: str,
    cases: List[Dict[str, Any]],
    limit: int = 10,
    k: int = 15,
    w_text: float = 1.0,
    w_code: float = 1.1,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Evaluates Document-Level Reciprocal Rank Fusion (RRF) combining both models."""
    evaluations = []
    mrr_sum = 0.0
    hit_1_count = 0
    hit_3_count = 0
    hit_5_count = 0
    latencies = []

    for case in cases:
        query = case["query"]
        expected_file = normalize_path(case["expected_file"])
        category = case.get("category", "General")

        start_time = time.perf_counter()
        res_text, lat_text = run_grepai_search(bin_path, text_dir, query, limit=15, dry_run=dry_run)
        res_code, lat_code = run_grepai_search(bin_path, code_dir, query, limit=15, dry_run=dry_run)
        total_lat = (time.perf_counter() - start_time) * 1000.0
        latencies.append(total_lat)

        # Document-Level RRF
        files_text = {}
        for rank, item in enumerate(res_text):
            fp = normalize_path(item.get("file_path", item.get("file", "")))
            if fp and fp not in files_text:
                files_text[fp] = rank + 1

        files_code = {}
        for rank, item in enumerate(res_code):
            fp = normalize_path(item.get("file_path", item.get("file", "")))
            if fp and fp not in files_code:
                files_code[fp] = rank + 1

        all_files = set(files_text.keys()).union(set(files_code.keys()))
        fused = []
        for fp in all_files:
            score = 0.0
            if fp in files_text:
                score += w_text / (k + files_text[fp])
            if fp in files_code:
                score += w_code / (k + files_code[fp])
            fused.append((fp, score))

        fused.sort(key=lambda x: (-x[1], x[0]))
        fused = fused[:limit]

        found_rank = None
        target_score = 0.0
        top_score = fused[0][1] if fused else 0.0

        for idx, (fp, score) in enumerate(fused):
            if expected_file in fp:
                found_rank = idx + 1
                target_score = score
                break

        reciprocal_rank = 1.0 / found_rank if found_rank else 0.0
        mrr_sum += reciprocal_rank

        if found_rank == 1:
            hit_1_count += 1
        if found_rank and found_rank <= 3:
            hit_3_count += 1
        if found_rank and found_rank <= 5:
            hit_5_count += 1

        evaluations.append({
            "id": case.get("id", ""),
            "category": category,
            "query": query,
            "expected_file": case["expected_file"],
            "rank": found_rank,
            "target_score": target_score,
            "top_score": top_score,
            "latency_ms": total_lat,
            "hit": found_rank is not None
        })

    n = len(cases)
    return {
        "target_dir": "hybrid-rrf",
        "total_queries": n,
        "mrr": mrr_sum / n if n > 0 else 0.0,
        "hit_at_1": hit_1_count / n if n > 0 else 0.0,
        "hit_at_3": hit_3_count / n if n > 0 else 0.0,
        "hit_at_5": hit_5_count / n if n > 0 else 0.0,
        "avg_score_margin": 0.0,
        "avg_latency_ms": sum(latencies) / n if n > 0 else 0.0,
        "details": evaluations
    }


def print_comparison(
    text_metrics: Optional[Dict[str, Any]],
    code_metrics: Optional[Dict[str, Any]],
    hybrid_metrics: Optional[Dict[str, Any]] = None
):
    """Prints a comparison table between models and optional hybrid fusion."""
    if text_metrics and code_metrics and hybrid_metrics:
        print("\n" + "=" * 76)
        print("           GREPAI EMBEDDING EVALUATION BENCHMARK RESULTS")
        print("=" * 76)
        print(f"{'Metric':<22} | {'137M Text':<14} | {'7B Code':<14} | {'Hybrid RRF':<16}")
        print("-" * 76)
        print(f"{'Hit@1 (Rank #1)':<22} | {text_metrics['hit_at_1'] * 100:>12.1f}% | {code_metrics['hit_at_1'] * 100:>12.1f}% | {hybrid_metrics['hit_at_1'] * 100:>14.1f}%")
        print(f"{'Hit@3 (Top 3)':<22} | {text_metrics['hit_at_3'] * 100:>12.1f}% | {code_metrics['hit_at_3'] * 100:>12.1f}% | {hybrid_metrics['hit_at_3'] * 100:>14.1f}%")
        print(f"{'Hit@5 (Top 5)':<22} | {text_metrics['hit_at_5'] * 100:>12.1f}% | {code_metrics['hit_at_5'] * 100:>12.1f}% | {hybrid_metrics['hit_at_5'] * 100:>14.1f}%")
        print(f"{'MRR (Mean Recip)':<22} | {text_metrics['mrr']:>14.3f} | {code_metrics['mrr']:>14.3f} | {hybrid_metrics['mrr']:>16.3f}")
        print(f"{'Avg Latency':<22} | {text_metrics['avg_latency_ms']:>11.1f} ms | {code_metrics['avg_latency_ms']:>11.1f} ms | {hybrid_metrics['avg_latency_ms']:>13.1f} ms")
        print("=" * 76)

        categories = sorted(list(set(c["category"] for c in text_metrics["details"])))
        print("\nBreakdown by Query Category (Hit@3):")
        print(f"{'Category':<24} | {'137M Text':<12} | {'7B Code':<12} | {'Hybrid RRF':<14}")
        print("-" * 70)
        for cat in categories:
            t_hits = [c for c in text_metrics["details"] if c["category"] == cat and c["rank"] and c["rank"] <= 3]
            c_hits = [c for c in code_metrics["details"] if c["category"] == cat and c["rank"] and c["rank"] <= 3]
            h_hits = [c for c in hybrid_metrics["details"] if c["category"] == cat and c["rank"] and c["rank"] <= 3]
            t_tot = len([c for c in text_metrics["details"] if c["category"] == cat])
            t_pct = (len(t_hits) / t_tot * 100) if t_tot > 0 else 0
            c_pct = (len(c_hits) / t_tot * 100) if t_tot > 0 else 0
            h_pct = (len(h_hits) / t_tot * 100) if t_tot > 0 else 0
            print(f"{cat:<24} | {t_pct:>10.0f}% | {c_pct:>10.0f}% | {h_pct:>12.0f}%")
        print("=" * 70)

    elif text_metrics and code_metrics:
        print("\n" + "=" * 68)
        print("           GREPAI EMBEDDING EVALUATION BENCHMARK RESULTS")
        print("=" * 68)
        print(f"{'Metric':<24} | {'137M Text Model':<18} | {'7B Code Model':<18}")
        print("-" * 68)
        print(f"{'Hit@1 (Rank #1)':<24} | {text_metrics['hit_at_1'] * 100:>16.1f}% | {code_metrics['hit_at_1'] * 100:>16.1f}%")
        print(f"{'Hit@3 (Top 3)':<24} | {text_metrics['hit_at_3'] * 100:>16.1f}% | {code_metrics['hit_at_3'] * 100:>16.1f}%")
        print(f"{'Hit@5 (Top 5)':<24} | {text_metrics['hit_at_5'] * 100:>16.1f}% | {code_metrics['hit_at_5'] * 100:>16.1f}%")
        print(f"{'MRR (Mean Recip. Rank)':<24} | {text_metrics['mrr']:>18.3f} | {code_metrics['mrr']:>18.3f}")
        print(f"{'Avg Latency':<24} | {text_metrics['avg_latency_ms']:>15.1f} ms | {code_metrics['avg_latency_ms']:>15.1f} ms")
        print("=" * 68)

        categories = sorted(list(set(c["category"] for c in text_metrics["details"])))
        print("\nBreakdown by Query Category (Hit@3):")
        print(f"{'Category':<28} | {'137M Text':<14} | {'7B Code':<14}")
        print("-" * 62)
        for cat in categories:
            t_hits = [c for c in text_metrics["details"] if c["category"] == cat and c["rank"] and c["rank"] <= 3]
            c_hits = [c for c in code_metrics["details"] if c["category"] == cat and c["rank"] and c["rank"] <= 3]
            t_tot = len([c for c in text_metrics["details"] if c["category"] == cat])
            t_pct = (len(t_hits) / t_tot * 100) if t_tot > 0 else 0
            c_pct = (len(c_hits) / t_tot * 100) if t_tot > 0 else 0
            print(f"{cat:<28} | {t_pct:>12.0f}% | {c_pct:>12.0f}%")
        print("=" * 62)


def main():
    parser = argparse.ArgumentParser(description="grepai Embedding Model Benchmark")
    parser.add_argument("--cases", type=str, default="cases.json", help="Path to cases JSON file")
    parser.add_argument("--text-dir", type=str, help="Path to repo indexed with text embedder")
    parser.add_argument("--code-dir", type=str, help="Path to repo indexed with code embedder")
    parser.add_argument("--target-dir", type=str, help="Path to a single indexed repo to test")
    parser.add_argument("--grepai-bin", type=str, help="Path to grepai executable")
    parser.add_argument("--limit", type=int, default=10, help="Max search results to retrieve (default: 10)")
    parser.add_argument("--hybrid", action="store_true", help="Also evaluate hybrid RRF combining text-dir and code-dir")
    parser.add_argument("--dry-run", action="store_true", help="Simulate searches with mock data")
    parser.add_argument("--output-json", type=str, help="Save detailed results to JSON file")
    args = parser.parse_args()

    # Resolve cases path
    cases_path = Path(args.cases)
    if not cases_path.is_file():
        script_dir = Path(__file__).resolve().parent
        cases_path = script_dir / "cases.json"
        if not cases_path.is_file():
            sys.exit(f"Error: cases file not found at {args.cases} or {cases_path}")

    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if not args.dry_run:
        bin_path = find_grepai_binary(args.grepai_bin)
    else:
        bin_path = "grepai-mock"

    text_metrics = None
    code_metrics = None
    hybrid_metrics = None

    if args.target_dir:
        text_metrics = evaluate_directory(bin_path, args.target_dir, cases, args.limit, args.dry_run)
    else:
        if args.text_dir:
            print(f"Evaluating Text Embedder Index: {args.text_dir}")
            text_metrics = evaluate_directory(bin_path, args.text_dir, cases, args.limit, args.dry_run)
        if args.code_dir:
            print(f"Evaluating Code Embedder Index: {args.code_dir}")
            code_metrics = evaluate_directory(bin_path, args.code_dir, cases, args.limit, args.dry_run)
        if args.hybrid and args.text_dir and args.code_dir:
            print(f"Evaluating Hybrid RRF Fusion: {args.text_dir} + {args.code_dir}")
            hybrid_metrics = evaluate_hybrid(bin_path, args.text_dir, args.code_dir, cases, args.limit, dry_run=args.dry_run)

    if not text_metrics and not code_metrics and not args.dry_run:
        sys.exit("Error: Please provide at least one of --text-dir, --code-dir, or --target-dir (or use --dry-run)")

    if args.dry_run and not text_metrics and not code_metrics:
        print("Running mock evaluation dry-run...")
        text_metrics = evaluate_directory(bin_path, "mock-text", cases, args.limit, dry_run=True)
        code_metrics = evaluate_directory(bin_path, "mock-code", cases, args.limit, dry_run=True)
        if args.hybrid:
            hybrid_metrics = evaluate_hybrid(bin_path, "mock-text", "mock-code", cases, args.limit, dry_run=True)

    print_comparison(text_metrics, code_metrics, hybrid_metrics)

    if args.output_json:
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "text_model": text_metrics,
            "code_model": code_metrics,
            "hybrid_model": hybrid_metrics
        }
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nDetailed JSON report saved to: {args.output_json}")


if __name__ == "__main__":
    main()
