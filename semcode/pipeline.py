"""Unified two-stage hybrid retrieval pipeline (Dense RRF + Local Re-Rank)."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

from semcode.creds import get_lmstudio_token
from semcode.grepai_runner import run_grepai_search
from semcode.registry import resolve_project


def reciprocal_rank_fusion(
    text_results: List[Dict[str, Any]],
    code_results: List[Dict[str, Any]],
    k: int = 15,
    weight_text: float = 1.0,
    weight_code: float = 1.1,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Perform Reciprocal Rank Fusion (RRF) on text (137M) and code (7B) search results.
    Guarantees deterministic tie-breaking on score, file path, and start line.
    """
    candidates: Dict[str, Dict[str, Any]] = {}

    def _chunk_key(res: Dict[str, Any]) -> str:
        fp = str(res.get("file_path", "")).replace("\\", "/").lower()
        sl = res.get("start_line", 0)
        el = res.get("end_line", 0)
        return f"{fp}::{sl}-{el}"

    # Process text results (137M nomic-embed-text)
    for rank, res in enumerate(text_results, 1):
        key = _chunk_key(res)
        if key not in candidates:
            candidates[key] = {
                "file_path": res.get("file_path", ""),
                "start_line": res.get("start_line", 0),
                "end_line": res.get("end_line", 0),
                "content": res.get("content", ""),
                "score_text": res.get("score", 0.0),
                "score_code": 0.0,
                "text_rank": rank,
                "code_rank": None,
                "rrf_score": 0.0,
            }
        else:
            candidates[key]["text_rank"] = rank
            candidates[key]["score_text"] = res.get("score", 0.0)
        candidates[key]["rrf_score"] += weight_text * (1.0 / (k + rank))

    # Process code results (7B nomic-embed-code)
    for rank, res in enumerate(code_results, 1):
        key = _chunk_key(res)
        if key not in candidates:
            candidates[key] = {
                "file_path": res.get("file_path", ""),
                "start_line": res.get("start_line", 0),
                "end_line": res.get("end_line", 0),
                "content": res.get("content", ""),
                "score_text": 0.0,
                "score_code": res.get("score", 0.0),
                "text_rank": None,
                "code_rank": rank,
                "rrf_score": 0.0,
            }
        else:
            candidates[key]["code_rank"] = rank
            candidates[key]["score_code"] = res.get("score", 0.0)
            if not candidates[key]["content"] and res.get("content"):
                candidates[key]["content"] = res.get("content")
        candidates[key]["rrf_score"] += weight_code * (1.0 / (k + rank))

    # Deterministic sorting: highest rrf_score first, then file_path ascending, then start_line ascending
    fused = sorted(
        candidates.values(),
        key=lambda c: (-c["rrf_score"], str(c["file_path"]).lower(), c["start_line"])
    )
    return fused[:limit]


def rerank_with_llm(
    candidates: List[Dict[str, Any]],
    query: str,
    endpoint: str = "http://127.0.0.1:1234/v1",
    model: Optional[str] = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """
    Stage 2 re-ranking using LM Studio local LLM.
    Fails loudly with clear error details if the LLM service is unreachable or errors.
    """
    if not candidates:
        return []

    token = get_lmstudio_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # Resolve model name if not explicitly passed
    if not model:
        req = urllib.request.Request(f"{endpoint}/models", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                models_data = json.loads(resp.read().decode())
                for m in models_data.get("data", []):
                    mid = m.get("id", "")
                    if "embed" not in mid.lower():
                        model = mid
                        break
        except Exception as exc:
            raise RuntimeError(
                f"Failed to query LM Studio models at {endpoint}: {exc}\n"
                f"Remediation: Ensure LM Studio is running on {endpoint} with a loaded LLM."
            ) from exc

    if not model:
        raise RuntimeError(
            f"No suitable chat/instruct model found loaded in LM Studio at {endpoint}.\n"
            f"Remediation: Load a chat model in LM Studio for Stage 2 re-ranking."
        )

    for cand in candidates:
        content_snippet = cand.get("content", "")[:1200]
        prompt = (
            f"Query: {query}\n"
            f"File: {cand.get('file_path')}:{cand.get('start_line')}-{cand.get('end_line')}\n"
            f"Code snippet:\n```\n{content_snippet}\n```\n\n"
            "Evaluate whether this code directly answers or implements the query.\n"
            "Respond ONLY with a valid JSON object in this format:\n"
            '{"score": <float between 0.0 and 1.0>, "reason": "<one-line explanation>"}'
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a code search relevance evaluator. Output only JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 100,
        }

        req = urllib.request.Request(
            f"{endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res_data = json.loads(resp.read().decode())
                text = res_data["choices"][0]["message"]["content"].strip()
                # Parse JSON out of response text
                if "{" in text and "}" in text:
                    text = text[text.find("{"):text.rfind("}") + 1]
                eval_obj = json.loads(text)
                cand["rerank_score"] = float(eval_obj.get("score", 0.0))
                cand["rerank_reason"] = str(eval_obj.get("reason", ""))
        except Exception as exc:
            raise RuntimeError(
                f"Stage 2 LLM re-ranking failed for candidate '{cand.get('file_path')}': {exc}\n"
                f"Remediation: Verify LM Studio status and loaded model '{model}'."
            ) from exc

    # Sort candidates by rerank_score descending, then rrf_score
    return sorted(
        candidates,
        key=lambda c: (-c.get("rerank_score", 0.0), -c.get("rrf_score", 0.0), str(c["file_path"]).lower())
    )


def execute_hybrid_search(
    query: str,
    project: Optional[str] = None,
    project_path: Optional[str] = None,
    text_dir: Optional[str] = None,
    code_dir: Optional[str] = None,
    limit: int = 5,
    rerank: bool = False,
    roots: Optional[List[str]] = None,
    cwd: Optional[str] = None,
    k: Optional[int] = None,
    w_text: Optional[float] = None,
    w_code: Optional[float] = None,
    endpoint: str = "http://127.0.0.1:1234/v1",
    rerank_model: Optional[str] = None,
    feedback_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute end-to-end hybrid semantic search.
    Returns dictionary with results, resolved paths, and project metadata.
    """
    if not 1 <= limit <= 15:
        raise ValueError(f"Limit must be between 1 and 15, got {limit}")

    source_path: Optional[str] = None
    project_name: Optional[str] = None

    if text_dir and code_dir:
        resolved_text, resolved_code = text_dir, code_dir
        project_name = "explicit"
    else:
        resolved_text, resolved_code, project_name, source_path = resolve_project(
            project=project,
            project_path=project_path,
            cwd=cwd,
            roots=roots
        )

    # Resolve hyperparameters (auto-load from optimal_params.json if available)
    if k is None or w_text is None or w_code is None:
        opt_path = Path(__file__).resolve().parent.parent / "benchmarks" / "optimal_params.json"
        if opt_path.is_file():
            try:
                opt_data = json.loads(opt_path.read_text(encoding="utf-8"))
                if k is None: k = int(opt_data.get("k", 15))
                if w_text is None: w_text = float(opt_data.get("weight_text", 1.0))
                if w_code is None: w_code = float(opt_data.get("weight_code", 1.1))
            except Exception:
                pass
    if k is None: k = 15
    if w_text is None: w_text = 1.0
    if w_code is None: w_code = 1.1

    # Stage 1: Parallel Dense Retrieval
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_text = executor.submit(run_grepai_search, resolved_text, query, 15)
        f_code = executor.submit(run_grepai_search, resolved_code, query, 15)
        text_hits = f_text.result()
        code_hits = f_code.result()

    fused = reciprocal_rank_fusion(
        text_results=text_hits,
        code_results=code_hits,
        k=k,
        weight_text=w_text,
        weight_code=w_code,
        limit=max(10, limit)
    )

    # Stage 2: Local Re-ranking if requested
    if rerank:
        fused = rerank_with_llm(
            candidates=fused,
            query=query,
            endpoint=endpoint,
            model=rerank_model,
        )

    # Resolve absolute paths and working links
    final_candidates = fused[:limit]
    for c in final_candidates:
        rel_fp = str(c.get("file_path", "")).replace("/", os.sep).replace("\\", os.sep)
        if source_path:
            abs_fp = (Path(source_path) / rel_fp).resolve()
            c["absolute_path"] = str(abs_fp)
            c["file_url"] = f"file:///{str(abs_fp).replace(os.sep, '/')}"
        else:
            c["absolute_path"] = rel_fp
            c["file_url"] = f"file:///{rel_fp.replace(os.sep, '/')}"

    # Telemetry logging (opt-in)
    try:
        from telemetry.collector import log_interaction
        log_interaction(
            query=query,
            candidates=final_candidates,
            selected_file=feedback_file
        )
    except Exception:
        pass

    return {
        "query": query,
        "project": project_name,
        "source_path": source_path,
        "text_dir": resolved_text,
        "code_dir": resolved_code,
        "k": k,
        "weight_text": w_text,
        "weight_code": w_code,
        "rerank": rerank,
        "results": final_candidates,
    }


def format_search_markdown(search_data: Dict[str, Any]) -> str:
    """Format search results as clean markdown for AI agent ingestion."""
    query = search_data["query"]
    results = search_data["results"]
    project = search_data.get("project")
    rerank = search_data.get("rerank", False)
    k = search_data.get("k", 15)
    wt = search_data.get("weight_text", 1.0)
    wc = search_data.get("weight_code", 1.1)

    if not results:
        return f"No matching code snippets found for query: \"{query}\""

    mode_str = "Hybrid RRF + Local Re-Rank" if rerank else f"Hybrid RRF (k={k}, wt={wt:.1f}, wc={wc:.1f})"
    proj_tag = f" [Project: {project}]" if project and project != "default" else ""
    lines = [f"### grepai Hybrid Search Results: `{query}` ({mode_str}){proj_tag}\n"]

    for idx, r in enumerate(results, 1):
        fp = r.get("absolute_path") or r.get("file_path")
        file_url = r.get("file_url") or f"file:///{str(fp).replace(os.sep, '/')}"
        line_range = f"L{r['start_line']}-{r['end_line']}"
        score = r.get("rrf_score", 0.0)
        t_rank = f"#{r['text_rank']}" if r.get("text_rank") else "miss"
        c_rank = f"#{r['code_rank']}" if r.get("code_rank") else "miss"

        header = f"#### {idx}. [{fp} ({line_range})]({file_url}#L{r['start_line']}-L{r['end_line']})\n"
        meta = f"- **RRF Score:** `{score:.4f}` | **Text Rank:** `{t_rank}` | **Code Rank:** `{c_rank}`"
        if r.get("rerank_score") is not None:
            meta += f" | **Re-Rank Score:** `{r['rerank_score']:.2f}`"
        if r.get("rerank_reason"):
            meta += f"\n- **Reasoning:** {r['rerank_reason']}"

        snippet = f"\n```\n{r.get('content', '').strip()}\n```\n"
        lines.append(f"{header}{meta}\n{snippet}")

    return "\n".join(lines)
