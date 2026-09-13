#!/usr/bin/env python3
"""
Telemetry and Hard-Negative Triplet Collector for grepai
Captures real query interactions, user/agent selections, and automatically extracts
(anchor: query, positive: selected_code, negative: distractor_code) triplets for fine-tuning.
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_TELEMETRY_LOG = Path(__file__).resolve().parent / "interactions.jsonl"
DEFAULT_TRIPLETS_FILE = Path(__file__).resolve().parent / "triplets.jsonl"


def log_interaction(
    query: str,
    candidates: List[Dict[str, Any]],
    selected_file: Optional[str] = None,
    log_path: Path = DEFAULT_TELEMETRY_LOG,
    triplets_path: Path = DEFAULT_TRIPLETS_FILE
) -> Dict[str, Any]:
    """
    Logs an interaction and automatically derives contrastive training triplets
    if a positive selection is identified.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    triplets_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": timestamp,
        "query": query,
        "selected_file": selected_file,
        "candidates": [
            {
                "file_path": c.get("file_path"),
                "start_line": c.get("start_line"),
                "end_line": c.get("end_line"),
                "score": c.get("rrf_score", c.get("score")),
                "content": c.get("content", "")[:500]
            }
            for c in candidates
        ]
    }

    # Append to interaction log
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # If a selected file was confirmed, extract triplets
    triplets_count = 0
    if selected_file:
        norm_selected = selected_file.replace("\\", "/").lower()
        positives = [c for c in candidates if norm_selected in c.get("file_path", "").replace("\\", "/").lower()]
        negatives = [c for c in candidates if norm_selected not in c.get("file_path", "").replace("\\", "/").lower()]

        if positives:
            pos_chunk = positives[0].get("content", "")
            with open(triplets_path, "a", encoding="utf-8") as f:
                for neg in negatives[:3]:  # Top 3 highest-ranking distractors become hard negatives
                    triplet = {
                        "timestamp": timestamp,
                        "anchor": query,
                        "positive": pos_chunk,
                        "negative": neg.get("content", ""),
                        "positive_file": positives[0].get("file_path"),
                        "negative_file": neg.get("file_path")
                    }
                    f.write(json.dumps(triplet) + "\n")
                    triplets_count += 1

    return {"status": "success", "triplets_extracted": triplets_count}


def export_triplets(triplets_path: Path = DEFAULT_TRIPLETS_FILE, min_samples: int = 1) -> List[Dict[str, str]]:
    """Reads and deduplicates training triplets."""
    if not triplets_path.is_file():
        return []

    triplets = []
    seen = set()
    with open(triplets_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            key = (item["anchor"], item["positive"][:100], item["negative"][:100])
            if key not in seen:
                seen.add(key)
                triplets.append(item)

    return triplets


def main():
    parser = argparse.ArgumentParser(description="Telemetry and Triplet Collector CLI")
    parser.add_argument("--status", action="store_true", help="Print summary of collected telemetry and triplets")
    parser.add_argument("--export", type=str, help="Export deduplicated triplets to a JSON file")
    args = parser.parse_args()

    inter_count = 0
    if DEFAULT_TELEMETRY_LOG.is_file():
        with open(DEFAULT_TELEMETRY_LOG, "r", encoding="utf-8") as f:
            inter_count = sum(1 for line in f if line.strip())

    triplets = export_triplets(DEFAULT_TRIPLETS_FILE)

    print("=" * 60)
    print("         grepai Telemetry & Training Data Status")
    print("=" * 60)
    print(f"Logged Interactions:   {inter_count}")
    print(f"Deduplicated Triplets: {len(triplets)}")
    print(f"Interactions Log File: {DEFAULT_TELEMETRY_LOG}")
    print(f"Training Triplets File:{DEFAULT_TRIPLETS_FILE}")
    print("=" * 60)

    if args.export:
        out = Path(args.export)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(triplets, f, indent=2)
        print(f"Exported {len(triplets)} triplets to {args.export}")


if __name__ == "__main__":
    main()
