#!/usr/bin/env python3
"""
grepai-hybrid: Multi-Model Reciprocal Rank Fusion (RRF) & Re-Ranking Engine
Combines 137M Text (nomic-embed-text) and 7B Code (nomic-embed-code) with
optional Stage 2 local LLM / Cross-Encoder re-ranking for maximum recall and precision.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_stored_credential(target_name: str = "PraetorSilica/LMStudioDev") -> str:
    """Safely retrieves API token from Windows Credential Store if on Windows."""
    if os.name != "nt":
        return os.environ.get("LM_API_TOKEN", "")

    try:
        import ctypes
        from ctypes import wintypes

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ('Flags', wintypes.DWORD),
                ('Type', wintypes.DWORD),
                ('TargetName', wintypes.LPWSTR),
                ('Comment', wintypes.LPWSTR),
                ('LastWritten', wintypes.FILETIME),
                ('CredentialBlobSize', wintypes.DWORD),
                ('CredentialBlob', ctypes.POINTER(ctypes.c_byte)),
                ('Persist', wintypes.DWORD),
                ('AttributeCount', wintypes.DWORD),
                ('Attributes', ctypes.c_void_p),
                ('TargetAlias', wintypes.LPWSTR),
                ('UserName', wintypes.LPWSTR),
            ]

        pcred = ctypes.POINTER(CREDENTIAL)()
        if ctypes.windll.advapi32.CredReadW(target_name, 1, 0, ctypes.byref(pcred)):
            blob = ctypes.string_at(pcred.contents.CredentialBlob, pcred.contents.CredentialBlobSize)
            ctypes.windll.advapi32.CredFree(pcred)
            try:
                return blob.decode('utf-16le').strip()
            except UnicodeDecodeError:
                return blob.decode('utf-8').strip()
    except Exception:
        pass

    return os.environ.get("LM_API_TOKEN", "")


def find_binary(custom_path: Optional[str] = None) -> str:
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
            cmd, cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", check=False, timeout=60
        )
        if proc.returncode != 0:
            raise RuntimeError(f"grepai search failed in {repo_dir} (exit {proc.returncode}); check the index and embedding service")
        if not proc.stdout.strip():
            raise ValueError("grepai returned empty output instead of JSON")
        data = json.loads(proc.stdout)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and isinstance(data.get("results"), list):
            return data["results"]
        raise ValueError("grepai returned an unsupported result format")
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        raise RuntimeError(f"grepai search unavailable in {repo_dir}: {type(exc).__name__}") from exc


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
            "content": chunk_info.get("content", ""),
            "rerank_score": None,
            "rerank_reason": None
        })

    scored_files.sort(key=lambda x: (-x["rrf_score"], x["file_path"]))
    return scored_files[:limit]


def rerank_with_llm(
    candidates: List[Dict[str, Any]],
    query: str,
    endpoint: str = "http://127.0.0.1:1234/v1",
    model: Optional[str] = None,
    token: Optional[str] = None,
    timeout: int = 15
) -> List[Dict[str, Any]]:
    """
    Stage 2 Re-Ranking: Evaluates candidate snippets with a local LLM in LM Studio.
    Gracefully falls back to original order on timeout or failure.
    """
    if not candidates:
        return candidates

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Auto-resolve chat model if not specified
    if not model:
        try:
            req_models = urllib.request.Request(f"{endpoint}/models", headers=headers)
            with urllib.request.urlopen(req_models, timeout=5) as resp:
                models_data = json.loads(resp.read().decode("utf-8"))
                for m in models_data.get("data", []):
                    mid = m.get("id", "")
                    if "embed" not in mid.lower():
                        model = mid
                        break
        except Exception:
            pass

    if not model:
        return candidates

    candidate_prompts = []
    for idx, c in enumerate(candidates, 1):
        snippet = "\n".join(c.get("content", "").split("\n")[:12])
        candidate_prompts.append(
            f"--- Candidate [{idx}] ---\nFile: {c.get('file_path')} (Lines {c.get('start_line')}-{c.get('end_line')})\n{snippet}"
        )

    prompt = (
        f"You are an expert code search ranking assistant.\n\n"
        f"Search Query: \"{query}\"\n\n"
        f"Evaluate which of the following candidates best and most directly implements or matches the query intent.\n\n"
        f"{chr(10).join(candidate_prompts)}\n\n"
        f"Respond ONLY with a JSON object in this exact schema without extra text:\n"
        f"{{\n"
        f'  "rankings": [\n'
        f'    {{"candidate_id": 1, "relevance_score": 0.95, "reason": "concise explanation"}},\n'
        f'    ...\n'
        f'  ]\n'
        f"}}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a code retrieval relevance judge. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 512
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{endpoint}/chat/completions", headers=headers, data=data)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            content = res_json["choices"][0]["message"]["content"].strip()

            # Clean markdown JSON block if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed = json.loads(content)
            rankings = parsed.get("rankings", [])
            rank_map = {r["candidate_id"]: r for r in rankings if "candidate_id" in r}

            reranked = []
            for idx, c in enumerate(candidates, 1):
                item = dict(c)
                if idx in rank_map:
                    item["rerank_score"] = float(rank_map[idx].get("relevance_score", 0.0))
                    item["rerank_reason"] = rank_map[idx].get("reason", "")
                else:
                    item["rerank_score"] = 0.0
                reranked.append(item)

            reranked.sort(key=lambda x: (x["rerank_score"] is not None, x["rerank_score"]), reverse=True)
            return reranked

    except Exception:
        # Graceful fallback: return candidates unchanged
        return candidates


def resolve_project_dirs(
    project: Optional[str] = None,
    project_path: Optional[str] = None,
    text_dir: Optional[str] = None,
    code_dir: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Resolves (text_dir, code_dir, project_name) given project name, path, or explicit dirs.
    Auto-detects from CWD if possible, falling back to default repo-text/repo-code.
    """
    script_dir = Path(__file__).resolve().parent
    registry_file = script_dir / "workspaces" / "registry.json"
    registry = {}
    if registry_file.is_file():
        try:
            with open(registry_file, "r", encoding="utf-8-sig") as f:
                registry = json.load(f)
        except (OSError, ValueError) as exc:
            raise ValueError(f"Cannot read project registry: {registry_file}") from exc

    if text_dir is not None or code_dir is not None:
        if not text_dir or not code_dir:
            raise ValueError("Supply both text_dir and code_dir")
        return text_dir, code_dir, "explicit"

    # Prefer the most specific source root for nested projects.
    registry = dict(sorted(registry.items(), key=lambda pair: len(pair[1].get("source_path", "")), reverse=True))

    # 1. Direct project name match
    if project and project in registry:
        return registry[project]["text_dir"], registry[project]["code_dir"], project

    # 2. Match by source_path (or project_path)
    target_path = project_path or project
    if target_path:
        norm_target = os.path.abspath(target_path).lower()
        for pname, pinfo in registry.items():
            if not pinfo.get("source_path"):
                continue
            sp = os.path.abspath(pinfo["source_path"]).lower()
            if sp == norm_target or norm_target.startswith(sp.rstrip(os.sep) + os.sep):
                return pinfo["text_dir"], pinfo["code_dir"], pname
        raise ValueError(f"Project is not registered: {target_path}. Run index_project.ps1 first.")

    # 3. Auto-detect from caller's current working directory
    cwd = os.path.abspath(os.getcwd()).lower()
    for pname, pinfo in registry.items():
        if not pinfo.get("source_path"):
            continue
        sp = os.path.abspath(pinfo["source_path"]).lower()
        if sp and (cwd == sp or cwd.startswith(sp + os.sep)):
            return pinfo["text_dir"], pinfo["code_dir"], pname

    # 4. Fallback to passed text_dir/code_dir or defaults
    resolved_text = text_dir if text_dir is not None else str(script_dir / "repo-text")
    resolved_code = code_dir if code_dir is not None else str(script_dir / "repo-code")
    return resolved_text, resolved_code, "default"


def main():
    parser = argparse.ArgumentParser(description="grepai Multi-Model Hybrid Search & Re-Ranking")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument("--project", "-p", type=str, help="Registered project name (e.g. praetor_silica)")
    parser.add_argument("--project-path", type=str, help="Path to project directory")
    parser.add_argument("--text-dir", type=str, default=None, help="Directory indexed with 137M text model")
    parser.add_argument("--code-dir", type=str, default=None, help="Directory indexed with 7B code model")
    parser.add_argument("--limit", "-n", type=int, default=5, help="Number of results to return (default: 5)")
    parser.add_argument("--json", "-j", action="store_true", help="Output results in JSON format")
    parser.add_argument("--k", type=int, help="RRF smoothing constant (auto-loads from optimal_params.json if omitted)")
    parser.add_argument("--w-text", type=float, help="Text model weight (auto-loads from optimal_params.json if omitted)")
    parser.add_argument("--w-code", type=float, help="Code model weight (auto-loads from optimal_params.json if omitted)")
    parser.add_argument("--rerank", action="store_true", help="Enable Stage 2 local LLM re-ranking")
    parser.add_argument("--rerank-model", type=str, help="Model name for re-ranking in LM Studio")
    parser.add_argument("--endpoint", type=str, default="http://127.0.0.1:1234/v1", help="LM Studio API endpoint")
    parser.add_argument("--token", type=str, help="API token for LM Studio (auto-resolves from Windows Credential Store if omitted)")
    parser.add_argument("--feedback-selected", type=str, help="Mark a file as the positive selection to capture a training triplet")
    parser.add_argument("--no-telemetry", action="store_true", help="Disable interaction telemetry logging")
    args = parser.parse_args()
    if not 1 <= args.limit <= 15:
        parser.error("--limit must be between 1 and 15")

    bin_path = find_binary()
    token = args.token or get_stored_credential("PraetorSilica/LMStudioDev")

    # Auto-load optimal hyperparameters if available
    k_val = args.k
    w_text = args.w_text
    w_code = args.w_code

    optimal_file = Path(__file__).resolve().parent / "benchmarks" / "optimal_params.json"
    if optimal_file.is_file():
        try:
            with open(optimal_file, "r", encoding="utf-8") as f:
                opt = json.load(f)
                if k_val is None: k_val = opt.get("k", 15)
                if w_text is None: w_text = opt.get("weight_text", 1.0)
                if w_code is None: w_code = opt.get("weight_code", 1.1)
        except Exception:
            pass

    if k_val is None: k_val = 15
    if w_text is None: w_text = 1.0
    if w_code is None: w_code = 1.1

    # Resolve workspace directories
    text_dir, code_dir, resolved_proj = resolve_project_dirs(
        project=args.project,
        project_path=args.project_path,
        text_dir=args.text_dir,
        code_dir=args.code_dir
    )

    # Stage 1: Dual Dense Parallel Retrieval
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_text = executor.submit(run_single_search, bin_path, text_dir, args.query, 15)
        f_code = executor.submit(run_single_search, bin_path, code_dir, args.query, 15)
        text_res = f_text.result()
        code_res = f_code.result()

    fused = reciprocal_rank_fusion(text_res, code_res, k=k_val, weight_text=w_text, weight_code=w_code, limit=max(10, args.limit))

    # Stage 2: Optional Local Re-ranking
    if args.rerank:
        fused = rerank_with_llm(
            candidates=fused,
            query=args.query,
            endpoint=args.endpoint,
            model=args.rerank_model,
            token=token,
            timeout=20
        )

    # Telemetry logging & triplet collection
    if not args.no_telemetry:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from telemetry.collector import log_interaction
            log_interaction(
                query=args.query,
                candidates=fused,
                selected_file=args.feedback_selected
            )
        except Exception:
            pass

    fused = fused[:args.limit]

    if args.json:
        print(json.dumps(fused, indent=2))
        return

    proj_tag = f" [Project: {resolved_proj}]" if resolved_proj != "default" else ""
    mode_label = ("Hybrid RRF + Local Re-Rank" if args.rerank else f"Hybrid RRF (k={k_val}, wt={w_text:.1f}, wc={w_code:.1f})") + proj_tag
    print(f"\n{mode_label} Results for: \"{args.query}\"\n" + "=" * 75)
    for idx, item in enumerate(fused, 1):
        fp = item["file_path"]
        lines = f"L{item['start_line']}-{item['end_line']}"
        score = item["rrf_score"]
        t_rank = f"#{item['text_rank']}" if item["text_rank"] else "miss"
        c_rank = f"#{item['code_rank']}" if item["code_rank"] else "miss"

        print(f"[{idx}] {fp}:{lines}")
        score_info = f"    RRF Score: {score:.4f} | Text Rank: {t_rank} | Code Rank: {c_rank}"
        if item.get("rerank_score") is not None:
            score_info += f" | Re-Rank Score: {item['rerank_score']:.2f}"
        print(score_info)

        if item.get("rerank_reason"):
            print(f"    Rationale: {item['rerank_reason']}")

        snippet = item["content"].split("\n")[:3]
        for s in snippet:
            if s.strip():
                print(f"    | {s.strip()[:80]}")
        print("-" * 75)


if __name__ == "__main__":
    main()
