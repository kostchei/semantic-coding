#!/usr/bin/env python3
"""
Automated Security & Architectural Invariant Audit Benchmark for ash-rpg and ORAC.
Executes 6 domain-adapted security review queries against the dual-vector hybrid indices
(137M text + 7B code with Reciprocal Rank Fusion) and verifies that critical security
and architectural seams are surfaced in the top results.
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import semcode.pipeline as pipeline


AUDIT_BENCHMARK_CASES = [
    # --- ASH-RPG AUDIT SUITE ---
    {
        "project": "ash-rpg",
        "review_id": "Review 1 (ash-rpg): Mutation Authority & Caller Verification",
        "query": "mutation authority caller privilege verification action receipt",
        "expected_seams": ["src/server/app.ts", "src/shared/mutations.ts", "docs/plans/path_campaign_engineering.md"],
        "description": "Verifies that player socket connections cannot forge caller mutations or bypass action receipt idempotency locks."
    },
    {
        "project": "ash-rpg",
        "review_id": "Review 2 (ash-rpg): Information Fog-of-War & State Secret Leaks",
        "query": "information fog of war secret room monsters traps public projection",
        "expected_seams": ["docs/plans/table_assistant_campaign_requirements.md", "src/server/room-features.ts"],
        "description": "Verifies that room features, trap triggers, and hidden monster statistics are stripped before public projection broadcasts."
    },
    {
        "project": "ash-rpg",
        "review_id": "Review 3 (ash-rpg): State Replay, Desync & Concurrency Invariants",
        "query": "transaction sqlite concurrency state revision race condition",
        "expected_seams": ["src/server/database.ts", "tests/multiplayer-mutations.test.ts", "docs/plans/product_quality_engineering_plan.md"],
        "description": "Verifies atomic database transactions, state revision increments, and replay rejection on identical actionId."
    },

    # --- ORAC AUDIT SUITE ---
    {
        "project": "ORAC",
        "review_id": "Review 1 (ORAC): Privilege Separation & Doer Grant Isolation",
        "query": "tool broker privilege separation per-agent allowlist write grant isolation",
        "expected_seams": ["docs/tool-broker-plan-review.md", "tests/test_builder.py", "docs/edge-check-council-design.md"],
        "description": "Verifies that reviewer and orchestrator agents hold zero write grants and that ToolBroker strictly enforces allowlists."
    },
    {
        "project": "ORAC",
        "review_id": "Review 2 (ORAC): Safety-Critical Path Tampering & Sentinel Escapes",
        "query": "sentinel lens safety critical paths write interception human approval",
        "expected_seams": ["src/orac/council.py", "docs/council-contract.md"],
        "description": "Verifies that modifications to governance files in policy.SAFETY_CRITICAL_PATHS fail closed and escalate to human approval."
    },
    {
        "project": "ORAC",
        "review_id": "Review 3 (ORAC): Destructive Boundary Violations & Compensating Actions",
        "query": "compensating actions physical emergency stop uninvertible tool drift",
        "expected_seams": ["docs/compensating-actions.md", "src/orac/prompts/operator.md", "docs/physical-plan.md"],
        "description": "Verifies that uninvertible physical and external actions require approval-first gating, cooldowns, and emergency stop."
    }
]


def run_audit_suite(limit: int = 5, verbose: bool = True) -> List[Dict[str, Any]]:
    results_summary = []

    print("=" * 80)
    print("      grepai-hybrid Security & Invariant Code Audit Runner")
    print("         Target Codebases: ash-rpg (TSX/Node) & ORAC (Python)")
    print("=" * 80)

    findings_dir = Path(__file__).resolve().parent / "findings"
    findings_dir.mkdir(parents=True, exist_ok=True)

    for case in AUDIT_BENCHMARK_CASES:
        proj_name = case["project"]
        query = case["query"]
        review_id = case["review_id"]
        expected_seams = case["expected_seams"]

        t0 = time.perf_counter()
        res = pipeline.execute_hybrid_search(
            query=query,
            project=proj_name,
            limit=limit,
            k=5,
            w_text=1.5,
            w_code=0.5
        )
        fused = res["results"]
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Evaluate hit against expected seams
        retrieved_files = [item["file_path"].replace("\\", "/") for item in fused]
        hit = any(
            any(expected.lower() in rf.lower() for rf in retrieved_files)
            for expected in expected_seams
        )

        status_str = "[PASS]" if hit else "[MISS]"
        print(f"\n{status_str} {review_id}")
        print(f"       Project: {proj_name} | Latency: {elapsed_ms:.1f} ms | Query: \"{query}\"")
        
        for idx, item in enumerate(fused[:3], 1):
            fp = item["file_path"]
            lines = f"L{item['start_line']}-{item['end_line']}"
            t_rank = f"#{item['text_rank']}" if item["text_rank"] else "miss"
            c_rank = f"#{item['code_rank']}" if item["code_rank"] else "miss"
            print(f"       [{idx}] {fp}:{lines} (RRF: {item['rrf_score']:.4f} | Text: {t_rank} | Code: {c_rank})")

        # Write finding report file
        safe_name = review_id.split(":")[0].replace(" ", "_").replace("(", "").replace(")", "").lower()
        finding_file = findings_dir / f"{safe_name}.md"
        with open(finding_file, "w", encoding="utf-8") as f:
            f.write(f"# Security Review Finding: {review_id}\n\n")
            f.write(f"**Target Project:** `{proj_name}`\n")
            f.write(f"**Query Used:** `{query}`\n")
            f.write(f"**Retrieval Latency:** {elapsed_ms:.1f} ms\n")
            f.write(f"**Description:** {case['description']}\n\n")
            f.write("## Discovered Architectural & Security Seams\n\n")
            for idx, item in enumerate(fused, 1):
                f.write(f"### Hit [{idx}]: `{item['file_path']}` (Lines {item['start_line']}-{item['end_line']})\n\n")
                f.write(f"- **RRF Score:** {item['rrf_score']:.4f} (Text Rank: {item['text_rank']}, Code Rank: {item['code_rank']})\n\n")
                f.write("```\n" + item["content"][:600] + "\n```\n\n")

        results_summary.append({
            "review_id": review_id,
            "project": proj_name,
            "hit": hit,
            "latency_ms": elapsed_ms,
            "top_file": retrieved_files[0] if retrieved_files else "none"
        })

    print("\n" + "=" * 80)
    print("                    AUDIT SUITE EXECUTION SUMMARY")
    print("=" * 80)
    passed_count = sum(1 for r in results_summary if r["hit"])
    total_count = len(results_summary)
    avg_latency = sum(r["latency_ms"] for r in results_summary) / total_count

    print(f"Total Reviews Executed: {total_count}")
    print(f"Target Seams Discovered: {passed_count}/{total_count} ({passed_count/total_count*100:.1f}%)")
    print(f"Average Retrieval Latency: {avg_latency:.1f} ms")
    print("Findings markdown reports written to: findings/")
    print("=" * 80)

    return results_summary


if __name__ == "__main__":
    summary = run_audit_suite()
    all_passed = all(r["hit"] for r in summary)
    sys.exit(0 if all_passed else 1)
