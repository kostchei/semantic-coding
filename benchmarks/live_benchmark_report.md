# Empirical Benchmark Report: 137M Text vs. 7B Code Embedding in grepai

**Date:** September 13, 2026  
**Testbed Codebase:** `grepai` repository (304 files, 3,102 indexed chunks)  
**Host Hardware:** Local GPU Server (24GB VRAM)  
**Embedding Daemon:** LM Studio (`http://127.0.0.1:1234`) via Bearer Auth  

---

## 1. Executive Summary

We conducted a live, end-to-end comparative benchmark evaluating retrieval accuracy, latency, and memory footprint between:
1. **Lightweight Text Embedder:** `text-embedding-nomic-embed-text-v1.5@f32` (137M params, ~548 MB, 768 dims)
2. **Dedicated Large Code Embedder:** `text-embedding-nomic-embed-code` (7.1B params, ~7.52 GB, 4096 dims)

Both models indexed identical source code trees using `grepai` v0.37.0. A test suite of 12 stress queries across 4 information retrieval categories was executed against both vector indices.

### The Big Takeaway
- **The 7B Code Model is 3x superior on Pure Semantic Intent** (75% Hit@3 vs. 25% for text). When searching for conceptual algorithmic behavior without explicit symbol names (e.g. AST parsing, dense/sparse score fusion), the 7B code model placed the true implementation in the Top 3 (or #1).
- **The 137M Text Model wins on Vocabulary/Synonym Mismatch** (50% Hit@3 vs. 0% for code). General language embedders possess broader semantic web knowledge mapping English synonyms (e.g., "throttle" ↔ "rate limit", "ignored disk paths" ↔ "gitignore") to code identifiers.
- **`grepai`'s Tree-sitter AST parser levels the playing field for syntax:** In structural queries, both models achieved 100% Hit@3 because AST chunking preserves function signatures and token context explicitly.
- **Latency & Footprint:** The 137M model responded in **121 ms** (index size 17 MB), whereas the 7B model took **302 ms** (index size 66 MB) with 14x larger VRAM consumption.

---

## 2. Quantitative Results

```
====================================================================
           GREPAI EMBEDDING EVALUATION BENCHMARK RESULTS
====================================================================
Metric                   | 137M Text Model    | 7B Code Model     
--------------------------------------------------------------------
Hit@1 (Rank #1)          |              50.0% |              33.3%
Hit@3 (Top 3)            |              50.0% |              50.0%
Hit@5 (Top 5)            |              66.7% |              50.0%
MRR (Mean Recip. Rank)   |              0.552 |              0.429
Avg Cosine Margin        |              0.027 |              0.023
Avg Query Latency        |           121.3 ms |           302.1 ms
Index File Size          |            17.2 MB |            66.2 MB
VRAM Footprint           |            ~548 MB |            7.52 GB
====================================================================
```

### Breakdown by Query Category (Hit@3)

```
Category                     | 137M Text      | 7B Code       | Key Insight
-----------------------------------------------------------------------------------------
Pure Semantic Intent         |            25% |            75% | 7B Code model excels 3x
Vocabulary Mismatch          |            50% |             0% | Text model handles English synonyms
Structural / Syntax          |           100% |           100% | Tie (Tree-sitter AST aids both)
Distractor Separation        |            50% |            50% | Tie
================================================================================---------
```

---

## 3. Query-by-Query Deep Dive

### Category 1: Pure Semantic Intent (No Identifier Overlap)

| Query ID | Query Description | Expected File | 137M Text Rank | 7B Code Rank | Analysis |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `sem_01` | *retry HTTP requests with exponential delay and randomized jitter* | `embedder/retry.go` | **#1** (0.781) | **#1** (0.411) | Both models cleanly found the retry implementation. |
| `sem_02` | *measure angle between high dimensional embedding representations* | `store/gob.go` | Miss | Miss | Neither model mapped "angle between embeddings" to cosine dot product within top 10. |
| `sem_03` | *fuse ranked search outputs from sparse and dense retrieval* | `search/hybrid.go` | #4 (0.604) | **#2** (0.465) | **7B Code Wins**: Ranked in agent-usable Top 3. |
| `sem_04` | *parse abstract syntax trees for multiple programming languages* | `trace/extractor_ts.go` | #4 (0.617) | **#1** (0.386) | **7B Code Wins**: 7B model recognizes AST multi-language parsing directly at #1. |

### Category 2: Vocabulary Mismatch (English Synonyms vs Domain Code)

| Query ID | Query Description | Expected File | 137M Text Rank | 7B Code Rank | Analysis |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `vocab_01` | *throttle client queries to stay within quota limits* | `embedder/rate_limiter.go` | **#1** (0.582) | #7 (0.261) | **Text Wins**: Text model strongly links "throttle/quota" to "rate_limiter". |
| `vocab_02` | *filter out binary artifacts and ignored disk paths* | `indexer/gitignore.go` | **#1** (0.587) | Miss | **Text Wins**: Text model associates "artifacts / ignored disk paths" with `.gitignore`. |
| `vocab_03` | *assemble request payload and send vectorization request to local daemon* | `embedder/lmstudio.go` | Miss | Miss | Dispersed across generic HTTP client files. |
| `vocab_04` | *inspect upstream callers of a target function identifier* | `trace/trace.go` | #8 (0.550) | Miss | Both struggled; text model kept target in top 10. |

### Category 3: Structural / Syntax

| Query ID | Query Description | Expected File | 137M Text Rank | 7B Code Rank | Analysis |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `struct_01` | *tiebreak score ranking using deterministic chunk identification* | `store/ranking.go` | **#1** (0.646) | **#1** (0.550) | Tie: Both placed the exact ranking function at Rank 1. |
| `struct_02` | *read HTTP rate limit header reset timestamps RFC 7231* | `embedder/rate_limiter.go` | **#1** (0.704) | **#2** (0.513) | Tie: Both placed the parser in Top 2. |

### Category 4: Distractor Separation

| Query ID | Query Description | Expected File | 137M Text Rank | 7B Code Rank | Analysis |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `distract_01`| *calculate cosine similarity dot product and vector norms* | `store/gob.go` | **#1** (0.588) | **#1** (0.414) | Tie: Isolated the core math function from generic callers. |
| `distract_02`| *HTTP client timeout duration override option* | `embedder/lmstudio.go` | Miss | Miss | Missed due to 30+ files sharing HTTP client options. |

---

## 4. Diagnostics & Log Analysis

### Addressing the LM Studio GGUF Log Warning
During the run, LM Studio logged:
```
[WARNING] At least one last token in strings embedded is not SEP. 'tokenizer.ggml.add_eos_token' should be set to 'true' in the GGUF header
```
- **Root Cause:** In the GGUF conversion of `text-embedding-nomic-embed-code`, the metadata flag `tokenizer.ggml.add_eos_token` was omitted or set to `false`. Llama.cpp's BERT embedding pipeline expects a terminal separator token (`[SEP]`).
- **Impact Assessment:** The server automatically proceeded with pooling and returned 200 OK with valid 4096-dimensional vectors. The warning is non-fatal and does not corrupt vectors, though appending an explicit EOS token could yield marginal boundary accuracy improvements in future GGUF releases.

---

## 5. Architectural Recommendation for Your 24GB VRAM Rig

Given your 24GB VRAM budget and development environment:

1. **For General Pair Programming & Fast Search:**
   - **`nomic-embed-text` (137M)** is the recommended default. At 121 ms and ~500 MB VRAM, it leaves **23.5 GB of VRAM completely free** for large coding LLMs (e.g. Qwen 2.5 Coder 14B or 32B quantized).
   - Its natural language synonym performance is superior for colloquial searches ("throttle requests", "find where we ignore files").

2. **When to Switch to the 7B Code Embedder:**
   - When building **autonomous agent tools** that search for obscure, uncommented algorithmic patterns, AST transforms, or dense vector transformations where developers describe *what the code does mathematically* rather than *what it is named*.
   - Because you have 24GB VRAM, the 7.52 GB footprint of `nomic-embed-code` leaves **16.5 GB VRAM**, which is plenty to co-host a 14B Q5_K_M coding LLM concurrently.
