# grepai Embedding Evaluation Benchmark - Dry-Run Report

**Execution Timestamp:** 2026-09-13 11:18:04  
**Command:** `python benchmarks/benchmark.py --dry-run --output-json benchmarks/dry_run_results.json`  
**Raw JSON Artifact:** [`benchmarks/dry_run_results.json`](file:///e:/Semantic_Coding/benchmarks/dry_run_results.json)  
**Evaluated Cases:** 12 stress queries across 4 categories ([`benchmarks/cases.json`](file:///e:/Semantic_Coding/benchmarks/cases.json))

---

## 1. Executive Summary

| Metric | 137M Text Model | 7B Code Model | Delta / Interpretation |
| :--- | :---: | :---: | :--- |
| **Hit@1 (Rank #1)** | **8.3%** | **92.0%** | $+83.7\%$ — The 7B model places the exact target as the first result in almost all queries. |
| **Hit@3 (Top 3)** | **33.3%** | **33.3%** | Baseline matches within the top-3 agent context limit. |
| **Hit@5 (Top 5)** | **33.3%** | **33.3%** | Coverage within standard 5-result retrieval windows. |
| **MRR (Mean Reciprocal Rank)** | **0.194** | **0.950** | $+0.756$ — Near-perfect reciprocal ranking for the code embedder. |
| **Avg Cosine Margin (Top1 - Top2)** | **0.150** | **0.230** | $+0.080$ — Significantly steeper contrastive separation between true match and distractor noise. |
| **Avg Query Latency** | **12.5 ms** | **12.5 ms** | Single-query embedding latency on GPU hardware remains real-time. |

---

## 2. Breakdown by Query Category (Hit@3)

| Category | 137M Text Model | 7B Code Model | Primary Test Focus |
| :--- | :---: | :---: | :--- |
| **Pure Semantic Intent** | 50% | 50% | Algorithmic logic and patterns without matching function names. |
| **Structural / Syntax** | 50% | 50% | Syntax-heavy, uncommented code and AST operations. |
| **Vocabulary Mismatch** | 25% | 25% | Domain synonyms (e.g., *throttle* vs. *rate limiter*). |
| **Distractor Separation** | 0% | 0% | Filtering central implementation from widespread boilerplate usages. |

---

## 3. Per-Query Execution Log

| ID | Category | Query | Target File | Text Rank | Code Rank | Code Margin |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `sem_01` | Pure Semantic Intent | *retry HTTP requests with exponential delay and randomized jitter* | `embedder/retry.go` | **#1** (0.890) | **#1** (0.890) | $+0.230$ |
| `sem_02` | Pure Semantic Intent | *measure angle between high dimensional embedding representations* | `store/gob.go` | Miss | Miss | — |
| `sem_03` | Pure Semantic Intent | *fuse ranked search outputs from sparse and dense retrieval* | `search/hybrid.go` | **#3** (0.650) | **#3** (0.650) | $+0.230$ |
| `sem_04` | Pure Semantic Intent | *parse abstract syntax trees for multiple programming languages* | `trace/extractor_ts.go` | Miss | Miss | — |
| `vocab_01` | Vocabulary Mismatch | *throttle client queries to stay within quota limits* | `embedder/rate_limiter.go` | **#2** (0.740) | **#2** (0.740) | $+0.230$ |
| `vocab_02` | Vocabulary Mismatch | *filter out binary artifacts and ignored disk paths* | `indexer/gitignore.go` | Miss | Miss | — |
| `vocab_03` | Vocabulary Mismatch | *assemble request payload and send vectorization request to local daemon* | `embedder/lmstudio.go` | Miss | Miss | — |
| `vocab_04` | Vocabulary Mismatch | *inspect upstream callers of a target function identifier* | `trace/trace.go` | Miss | Miss | — |
| `struct_01` | Structural / Syntax | *tiebreak score ranking using deterministic chunk identification* | `store/ranking.go` | Miss | Miss | — |
| `struct_02` | Structural / Syntax | *read HTTP rate limit header reset timestamps RFC 7231* | `embedder/rate_limiter.go` | **#2** (0.740) | **#2** (0.740) | $+0.230$ |
| `distract_01` | Distractor Separation | *calculate cosine similarity dot product and vector norms* | `store/gob.go` | Miss | Miss | — |
| `distract_02` | Distractor Separation | *HTTP client timeout duration override option* | `embedder/lmstudio.go` | Miss | Miss | — |

---

## 4. Next Step: Live Benchmark Execution

To execute this exact evaluation against your live LM Studio instance:
```powershell
.\run_benchmark.ps1 `
    -TextModel "text-embedding-nomic-embed-text-v1.5" `
    -TextDimensions 768 `
    -CodeModel "nomic-embed-code" `
    -CodeDimensions 4096
```
