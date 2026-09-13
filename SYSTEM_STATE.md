# System State & Technical Reference: Semantic Coding & grepai Hybrid Suite

**Repository:** [https://github.com/kostchei/semantic-coding](https://github.com/kostchei/semantic-coding)  
**Upstream Project:** [https://github.com/yoanbernabeu/grepai](https://github.com/yoanbernabeu/grepai) (Fork: [https://github.com/kostchei/grepai](https://github.com/kostchei/grepai))  
**Target Rig:** Single Local GPU Server (24 GB VRAM)  
**State Snapshot Date:** September 13, 2026  

---

## 1. Executive Summary

This repository houses a production-ready, empirically verified **Two-Stage Hybrid Code Retrieval & Evaluation Suite** built around **`grepai`** (v0.37.0).

The system was conceived to solve the fundamental trade-off between lightweight general-purpose text embeddings (`nomic-embed-text`, 137M) and large specialized code embeddings (`nomic-embed-code`, 7B), while maintaining a continuous evaluation, hyperparameter optimization, and contrastive fine-tuning flywheel.

### Key Architectural Accomplishments
1. **Live Empirical Benchmark on Real Code (304 files, 3,102 chunks)**: Demonstrated that while the 7B Code model dominates pure algorithmic concepts without keyword cues (75% vs. 25% Hit@3), the 137M Text model surprisingly outperforms on colloquial English synonyms (50% vs. 0% Hit@3).
2. **Two-Stage Hybrid Retrieval Engine (`hybrid_search.py`)**: Fuses both models via document-level Reciprocal Rank Fusion (RRF), elevating Hit@3 retrieval accuracy from **50.0% to 66.7%**, with Stage 2 local LLM cross-encoder re-ranking support.
3. **Mathematical Hyperparameter Optimization (`tune_hyperparameters.py`)**: Grid search over 288 parameter sets identified the global optimum $(k=5, w_{\text{text}}=1.5, w_{\text{code}}=0.5)$, boosting MRR to **0.593**.
4. **Self-Improving Flywheel**: Implemented AST synthetic benchmark expansion, passive telemetry with hard-negative triplet mining, and PyTorch-based contrastive re-ranker training.

---

## 2. Complete File & Directory Manifest

```
Semantic_Coding/
├── bin/                                # Executables (excluded from Git)
│   └── grepai.exe                      # Official grepai v0.37.0 Windows AMD64 binary
├── grepai/                             # Cloned upstream testbed repository (excluded from Git)
├── repo-text/                          # Test workspace indexed with 137M text model (excluded from Git)
├── repo-code/                          # Test workspace indexed with 7B code model (excluded from Git)
├── templates/                          # Reusable grepai configuration templates
│   ├── config.text.yaml                # LM Studio template for nomic-embed-text (768 dims)
│   └── config.code.yaml                # LM Studio template for nomic-embed-code (4096 dims)
├── benchmarks/                         # Evaluation, ground truth, and optimization
│   ├── cases.json                      # 12 curated stress test queries across 4 IR categories
│   ├── synthetic_cases.json            # Automatically extracted AST synthetic cases
│   ├── optimal_params.json             # Mathematically optimal RRF parameters (k=5, wt=1.5, wc=0.5)
│   ├── benchmark.py                    # Multi-engine IR evaluation engine (MRR, Hit@K, Latency)
│   ├── generate_synthetic_cases.py     # AST-based synthetic benchmark expansion tool
│   ├── tune_hyperparameters.py         # Grid search hyperparameter optimizer
│   ├── live_benchmark_report.md        # Comprehensive report of live single-model test
│   ├── live_benchmark_results.json     # Raw machine-readable live benchmark dataset
│   ├── dry_run_report.md               # Dry-run validation report
│   └── dry_run_results.json            # Dry-run verification data
├── telemetry/                          # Usage tracking and training data mining
│   ├── collector.py                    # Telemetry logger and hard-negative triplet extractor
│   ├── triplets.jsonl                  # Active contrastive training dataset (anchor, pos, neg)
│   └── interactions.jsonl              # Raw query and candidate logs (excluded from Git)
├── training/                           # Contrastive neural fine-tuning
│   ├── train_cross_encoder.py          # PyTorch Margin Ranking Loss trainer
│   └── checkpoints/                    # Model weights and vocab checkpoints (excluded from Git)
├── hybrid_search.py                    # Two-Stage Hybrid Search CLI & Agent Engine
├── sync_hybrid_indices.ps1             # Continuous dual-index workspace file synchronizer
├── run_benchmark.ps1                   # End-to-end single-model benchmark orchestrator
├── run_evaluation_pipeline.ps1         # Master continuous evaluation & flywheel runner
├── index_code.ps1                      # Foreground batch indexing helper
├── HYBRID_PIPELINE_PLAN.md             # Detailed Two-Stage architectural design document
├── SYSTEM_STATE.md                     # This technical reference document
├── README.md                           # Main repository documentation & guide
├── LICENSE                             # MIT License (Copyright 2026 kostchei)
└── .gitignore                          # Strict secret, binary, and workspace exclusion rules
```

---

## 3. Empirical Benchmark Scorecard

Tested on the complete `yoanbernabeu/grepai` codebase (304 files, 3,102 AST chunks, Go) against LM Studio on local GPU:

```
==========================================================================================
Metric                  | 137M Text Model   | 7B Code Model     | Hybrid RRF (Optimized)
------------------------------------------------------------------------------------------
Hit@1 (Rank #1)         |             50.0% |             33.3% |                  50.0%
Hit@3 (Top 3)           |             50.0% |             50.0% |         🚀       66.7%
Hit@5 (Top 5)           |             66.7% |             50.0% |                  66.7%
MRR (Mean Recip. Rank)  |             0.552 |             0.429 |         🚀       0.593
Avg Latency             |          117.8 ms |          304.3 ms |               408.5 ms
Index Size on Disk      |           17.2 MB |           66.2 MB |                83.4 MB
VRAM Footprint          |           ~548 MB |           7.52 GB |                8.07 GB
==========================================================================================

Breakdown by Query Category (Hit@3):
Category                | 137M Text         | 7B Code           | Hybrid RRF
------------------------------------------------------------------------------------------
Pure Semantic Intent    |               25% |       🚀      75% |                    75%
Vocabulary Mismatch     |       🚀      50% |                0% |                    50%
Structural / Syntax     |              100% |              100% |                   100%
Distractor Separation   |               50% |               50% |                    50%
==========================================================================================
```

---

## 4. Hardware & VRAM Coexistence (24 GB Budget)

The hybrid system is architected to allow all components to stay resident in VRAM concurrently:

```
Total Available VRAM: 24.00 GB
┌─────────────────────────────────────────────────────────────┐
│ 137M Text Embedder: nomic-embed-text-v1.5@f32     (~0.55 GB)│
├─────────────────────────────────────────────────────────────┤
│ 7B Code Embedder:   nomic-embed-code              (~7.52 GB)│
├─────────────────────────────────────────────────────────────┤
│ Stage 2 Re-Ranker:  Qwen 2.5 Coder 14B Q5_K_M     (~9.80 GB)│
├─────────────────────────────────────────────────────────────┤
│ Context KV Buffer:  4K Context Window Allocation  (~2.50 GB)│
├─────────────────────────────────────────────────────────────┤
│ Free Headroom:      OS & Display Buffer           (~3.63 GB)│
└─────────────────────────────────────────────────────────────┘
Total Allocated: ~20.37 GB (Safe margin, zero disk paging)
```

---

## 5. Master Command Reference

### A. Two-Stage Hybrid Search
```powershell
# Interactive search using auto-loaded optimal parameters (k=5, wt=1.5, wc=0.5)
python hybrid_search.py "parse abstract syntax trees for multiple programming languages" -n 3

# With Stage 2 Local LLM Cross-Encoder Re-Ranking
python hybrid_search.py "throttle client queries to stay within quota limits" --rerank -n 3

# Output JSON for AI agents (Claude Code, Cursor, Windsurf, Antigravity)
python hybrid_search.py "retry HTTP requests with exponential jitter" -j -n 5

# Capture real interaction and mine training triplets
python hybrid_search.py "throttle queries" --feedback-selected "embedder/rate_limiter.go" -n 3
```

### B. Continuous Evaluation & Flywheel Automation
```powershell
# Run the complete end-to-end evaluation flywheel in one command
.\run_evaluation_pipeline.ps1

# Generate synthetic benchmark cases from source code AST
python benchmarks\generate_synthetic_cases.py --code-dir grepai --max-files 20

# Run hyperparameter grid search optimizer
python benchmarks\tune_hyperparameters.py --cases benchmarks\cases.json --text-dir repo-text --code-dir repo-code

# Execute 3-way regression benchmark
python benchmarks\benchmark.py --text-dir repo-text --code-dir repo-code --hybrid
```

### C. Workspace Synchronization & Dual Indexing
```powershell
# Continuous watcher mirroring code edits and updating both indices
.\sync_hybrid_indices.ps1 -SourceDir .\grepai -TextRepo .\repo-text -CodeRepo .\repo-code

# Single-pass index reconciliation
.\sync_hybrid_indices.ps1 -Once
```

### D. Telemetry & Fine-Tuning
```powershell
# Check telemetry volume and extracted training triplets
python telemetry\collector.py --status

# Export deduplicated contrastive training dataset
python telemetry\collector.py --export telemetry\export_triplets.json

# Train lightweight neural re-ranking model using Margin Ranking Loss
python training\train_cross_encoder.py --epochs 5 --lr 0.001 --margin 0.5
```

---

## 6. Remote Repository Synchronization

* **Remote Origin:** `https://github.com/kostchei/semantic-coding.git`
* **Branch:** `main` (tracking `origin/main`)
* **Fork:** `https://github.com/kostchei/grepai.git` (upstream: `yoanbernabeu/grepai`)
* **License:** MIT License (Copyright 2026 kostchei)
* **Secret Protection:** Zero credentials or large vector gob files are committed; Windows Credential Store integration handles local token resolution securely.

---

## 7. Desktop AI Assistant Integration (Daily Drivers)

The Two-Stage Hybrid Engine is exposed via standard Model Context Protocol (FastMCP) and native workspace skills across all three primary daily driver coding environments:

### Architecture: Zero-Friction MCP Transport
```
┌─────────────────────────────────────────────────────────────┐
│                   Desktop AI Daily Drivers                  │
│   ┌────────────────┐  ┌──────────────┐  ┌───────────────┐   │
│   │  Antigravity   │  │ Claude Code  │  │ Codex Desktop │   │
│   └───────┬────────┘  └──────┬───────┘  └───────┬───────┘   │
└───────────┼──────────────────┼──────────────────┼───────────┘
            │                  │                  │
            ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│             FastMCP Stdio Server (mcp_server.py)            │
│  - Tool: search_codebase(query, limit, rerank, feedback)    │
│  - Auto-loads optimal RRF params (k=5, wt=1.5, wc=0.5)      │
│  - Secure Windows Credential Store integration (Zero leaks) │
└──────────────────────────────┬──────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
┌───────────────────────────┐         ┌───────────────────────┐
│ 137M Text Embedder (Port  │         │ 7B Code Embedder      │
│ 1234, nomic-embed-text)   │         │ (Port 1234, 4096 dim) │
└───────────────────────────┘         └───────────────────────┘
```

### 1. Claude Code
- **Configuration File:** `~/.claude.json` (under `mcpServers`)
- **Registration Command:**
  ```powershell
  claude mcp add --scope user grepai-hybrid -- python e:\Semantic_Coding\mcp_server.py
  ```
- **Verification:** Run `claude mcp list` -> reports `grepai-hybrid: python e:\Semantic_Coding\mcp_server.py - √ Connected`.
- **Usage:** Claude Code automatically calls `search_codebase` when searching for code or algorithms, or when asked:
  > `"Use grepai-hybrid to find how rate limiting and token bucket are implemented."`

### 2. OpenAI Codex Desktop App
- **Configuration File:** `C:\Users\Admin\.codex\config.toml`
- **Configuration Entry:**
  ```toml
  [mcp_servers.grepai_hybrid]
  command = "python"
  args = ["e:\\Semantic_Coding\\mcp_server.py"]
  ```
- **Usage:** Codex invokes `grepai_hybrid.search_codebase` with full argument schema support.

### 3. Antigravity IDE & Agent
- **Native Skill:** `.gemini/skills/grepai-hybrid/SKILL.md` in repository root.
- **Global MCP Server Definition:**
  - `C:\Users\Admin\.gemini\antigravity\mcp\grepai-hybrid\search_codebase.json`
  - `C:\Users\Admin\.gemini\antigravity\mcp\grepai-hybrid\instructions.md`
  - `C:\Users\Admin\.gemini\antigravity-ide\mcp\grepai-hybrid\search_codebase.json`
- **CLI Shell Wrapper:** `bin\grepai-hybrid.cmd` accessible directly from terminal.

### 4. Zero Credential Leak Guarantee
- All authentication with local embedding daemons (LM Studio) uses Windows Credential Manager (`PraetorSilica/LMStudioDev`) or local environment variables resolved dynamically in memory at runtime.
- No bearer tokens, passwords, or private keys are written to configuration files or git-tracked trees.

---

## 8. Multi-Project Hybrid Indexing & Real-World Validation

To support arbitrary production codebases without tree pollution or file conflicts, `grepai-hybrid` features a centralized multi-project workspace architecture:

### Architecture
- **Pristine Source Repositories:** Target repositories (e.g. `E:\praetor_silica`, `E:\proj\LDGM`) remain 100% clean and untouched.
- **Central Registry:** Managed in `workspaces/registry.json` mapping project identifiers to dual-index paths and source paths.
- **Git-Ignored Workspaces:** All project embeddings and local configuration files reside under `workspaces/<project_name>/` (strictly excluded via `.gitignore`).
- **Dynamic CWD Resolution:** When Claude Code, Codex, or Antigravity executes in any indexed repository, the MCP server automatically detects the current directory and routes searches to that project's dual indices.

### Empirical Validation on Real Projects

#### Project 1: `praetor_silica` (Python / TypeScript / AI Agent Infrastructure)
- **Files Indexed:** 457 source files (6,311 code chunks)
- **Text Index (137M):** 36.5 MB (`workspaces/praetor_silica/repo-text`)
- **Code Index (7B):** 138.5 MB (`workspaces/praetor_silica/repo-code`)
- **Query Verification:**
  - *"verify LM Studio setup and authentication"* -> Rank #1: `src/praetor_silica/runtime/lmstudio_dev.py` (RRF: 0.3333, Text #1, Code #1).
  - *"platform lock file verification and path traversal prevention"* -> Rank #1: `tools/resolve_platform.py` (RRF: 0.2708).

#### Project 2: `LDGM` (C++ / CMake / Game Simulation Engine)
- **Files Indexed:** 191 source files
- **Text Index (137M):** 2.0 MB (`workspaces/LDGM/repo-text`)
- **Code Index (7B):** 7.7 MB (`workspaces/LDGM/repo-code`)
- **Query Verification:**
  - *"CMake presets and target dependencies"* -> Rank #1: `Gems/LDMChronoVehicle/Code/CMakeLists.txt`, Rank #2: `CMakePresets.json` (Code #1).
  - *"vehicle physics simulation component or chrono vehicle gem"* -> Rank #1: `Gems/LDMChronoVehicle/gem.json` (RRF: 0.2500).

### Command Reference for New Projects
```powershell
# Index any arbitrary project into the hybrid engine
.\index_project.ps1 -ProjectPath "C:\Path\To\Project" -ProjectName "my_project"

# Search a specific project
python hybrid_search.py "my query" --project my_project -n 5

# Synchronize modifications from a project
.\sync_hybrid_indices.ps1 -Project my_project -Once
```


