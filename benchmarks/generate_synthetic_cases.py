#!/usr/bin/env python3
"""
Synthetic Ground Truth Benchmark Generator for grepai
Extracts functions, methods, and structs from a codebase and generates
multi-category stress test queries using local LLM prompts or AST heuristics.
"""

import argparse
import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional


def find_go_declarations(code_dir: str, max_files: int = 20) -> List[Dict[str, Any]]:
    """Scans Go files and extracts functions, methods, structs with comments."""
    declarations = []
    root = Path(code_dir)

    func_pattern = re.compile(
        r'(?:(?://[^\n]*\n)*)(?:func\s+(?:\([^)]+\)\s+)?([A-Z][a-zA-Z0-9_]*)\s*\([^)]*\)[^{]*\{)',
        re.MULTILINE
    )
    struct_pattern = re.compile(
        r'(?:(?://[^\n]*\n)*)(?:type\s+([A-Z][a-zA-Z0-9_]*)\s+struct\s*\{)',
        re.MULTILINE
    )

    count = 0
    for go_file in root.rglob("*.go"):
        # Skip vendor, git, and tests unless specified
        rel = go_file.relative_to(root).as_posix()
        parts = rel.lower().split("/")
        if any(p in parts for p in [".git", "vendor", "test", "tests"]) or rel.endswith("_test.go"):
            continue

        try:
            with open(go_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        # Extract functions
        for match in func_pattern.finditer(content):
            fn_name = match.group(1)
            full_match = match.group(0)
            comments = "\n".join([line.strip("/ ") for line in full_match.split("\n") if line.strip().startswith("//")])
            declarations.append({
                "type": "function",
                "name": fn_name,
                "file": rel,
                "comments": comments,
                "snippet": full_match[:250]
            })

        # Extract structs
        for match in struct_pattern.finditer(content):
            struct_name = match.group(1)
            full_match = match.group(0)
            comments = "\n".join([line.strip("/ ") for line in full_match.split("\n") if line.strip().startswith("//")])
            declarations.append({
                "type": "struct",
                "name": struct_name,
                "file": rel,
                "comments": comments,
                "snippet": full_match[:250]
            })

        count += 1
        if count >= max_files:
            break

    return declarations


def generate_queries_heuristic(decl: Dict[str, Any]) -> List[Dict[str, str]]:
    """Rule-based query generator using comment semantics and symbol inversion."""
    queries = []
    comments = decl["comments"].strip()
    name = decl["name"]

    # Split camelCase name into words
    words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+', name)
    words_lower = [w.lower() for w in words]

    if comments:
        # First sentence of docstring without the function name
        first_line = comments.split(".")[0].strip()
        cleaned = re.sub(rf'\b{name}\b', 'this component', first_line, flags=re.IGNORECASE)
        cleaned = re.sub(r'^(returns|performs|calculates|handles|manages|creates)\s+', '', cleaned, flags=re.IGNORECASE)
        if len(cleaned.split()) >= 4:
            queries.append({
                "category": "Pure Semantic Intent",
                "query": cleaned.lower()
            })

    # Algorithmic / structural description
    if words_lower:
        name_phrase = " ".join(words_lower)
        queries.append({
            "category": "Structural / Syntax",
            "query": f"implementation of {name_phrase} definition"
        })

    return queries


def generate_queries_with_llm(
    decl: Dict[str, Any],
    endpoint: str = "http://127.0.0.1:1234/v1",
    model: Optional[str] = None,
    token: Optional[str] = None,
    timeout: int = 15
) -> List[Dict[str, str]]:
    """Generates 3 challenging queries using local LLM."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    prompt = (
        f"You are a developer creating a search retrieval benchmark for a code search engine.\n"
        f"Analyze this Go {decl['type']} in {decl['file']}:\n\n"
        f"```go\n{decl['snippet']}\n```\n\n"
        f"Doc comments: {decl['comments']}\n\n"
        f"Generate exactly 2 distinct search queries that a developer who DOES NOT KNOW the function name '{decl['name']}' would type:\n"
        f"1. A pure conceptual query describing the underlying algorithm or purpose without using '{decl['name']}'.\n"
        f"2. A colloquial synonym query using informal English phrases.\n\n"
        f"Respond ONLY with a JSON object in this exact format:\n"
        f'{{"queries": [{{"category": "Pure Semantic Intent", "query": "..."}}, {{"category": "Vocabulary Mismatch", "query": "..."}}]}}'
    )

    payload = {
        "model": model or "qwen/qwen3-coder-next",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 256
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{endpoint}/chat/completions", headers=headers, data=data)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            parsed = json.loads(content)
            return parsed.get("queries", [])
    except Exception:
        return generate_queries_heuristic(decl)


def main():
    parser = argparse.ArgumentParser(description="Generate Synthetic grepai Benchmark Test Cases")
    parser.add_argument("--code-dir", type=str, default="grepai", help="Path to source codebase to analyze")
    parser.add_argument("--max-files", type=int, default=15, help="Max source files to scan")
    parser.add_argument("--use-llm", action="store_true", help="Use local LLM in LM Studio to generate queries")
    parser.add_argument("--llm-model", type=str, help="Model name for LM Studio")
    parser.add_argument("--output-cases", type=str, default="benchmarks/synthetic_cases.json", help="Output JSON path")
    parser.add_argument("--merge-with", type=str, help="Existing cases.json to merge with")
    args = parser.parse_args()

    print(f"Scanning {args.code_dir} for Go declarations...")
    decls = find_go_declarations(args.code_dir, max_files=args.max_files)
    print(f"Found {len(decls)} significant declarations.")

    cases = []
    case_idx = 1

    for decl in decls:
        if args.use_llm:
            generated = generate_queries_with_llm(decl, model=args.llm_model)
        else:
            generated = generate_queries_heuristic(decl)

        for q in generated:
            cases.append({
                "id": f"synth_{case_idx:03d}",
                "category": q.get("category", "Synthetic Intent"),
                "query": q["query"],
                "expected_file": decl["file"],
                "description": f"Generated for {decl['type']} {decl['name']} in {decl['file']}"
            })
            case_idx += 1

    if args.merge_with and os.path.isfile(args.merge_with):
        with open(args.merge_with, "r", encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Merging with {len(existing)} existing cases...")
        cases = existing + cases

    out_path = Path(args.output_cases)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)

    print(f"\n[SUCCESS] Generated {len(cases)} total benchmark cases saved to: {args.output_cases}")


if __name__ == "__main__":
    main()
