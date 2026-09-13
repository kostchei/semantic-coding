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
├── bin/                                # Standalone binaries (Windows AMD64)
│   └── grepai.exe                      # Official grepai v0.37.0 Windows executable
├── semcode/                            # Core production package
│   ├── creds.py                        # Windows Credential Manager Advapi32 vault interface
│   ├── grepai_runner.py                # Subprocess runner with child-only OPENAI_API_KEY injection
│   ├── registry.py                     # Atomic JSON workspace registry with corruption guard
│   ├── pipeline.py                     # Canonical RRF ranking with absolute paths and tie-breaking
│   ├── indexer.py                      # Git-aware clean indexer with exclusion filters & sync
│   ├── sync.py                         # Dual-index incremental sync runner
│   ├── auto_index.py                   # Detached background worker for auto-indexing new repos
│   └── doctor.py                       # 18-point comprehensive system diagnostic engine
├── integrations/                       # Multi-agent hands-off integration layer
│   ├── install.py                      # Idempotent integration installer (Claude, Codex, Antigravity)
│   ├── instructions.md                 # Managed instruction block for coding assistants
│   ├── hooks/                          # Claude Code hooks (prompt context injection, session start)
│   └── skill/                          # Reusable agent skill (SKILL.md)
├── config/                             # Runtime policies and configurations
│   └── auto_index.json                 # Auto-index policy, thresholds, and deny-lists
├── workspaces/                         # Multi-project dual-index storage (excluded from Git)
│   ├── registry.json                   # Central project catalog and metadata
│   ├── ORAC/                           # Dual indices for ORAC
│   ├── ash-rpg/                        # Dual indices for ash-rpg
│   ├── LDGM/                           # Dual indices for LDGM
│   └── praetor_silica/                 # Dual indices for praetor_silica
├── templates/                          # Reusable grepai configuration templates
│   ├── config.text.yaml                # LM Studio template for nomic-embed-text (no plaintext keys)
│   └── config.code.yaml                # LM Studio template for nomic-embed-code (no plaintext keys)
├── benchmarks/                         # Evaluation, ground truth, and optimization
│   ├── cases.json                      # 12 curated stress test queries across 4 IR categories
│   ├── synthetic_cases.json            # Automatically extracted AST synthetic cases
│   ├── optimal_params.json             # Mathematically optimal RRF parameters (k=5, wt=1.5, wc=0.5)
│   ├── benchmark.py                    # Multi-engine IR evaluation engine (MRR, Hit@K, Latency)
│   ├── generate_synthetic_cases.py     # AST-based synthetic benchmark expansion tool
│   ├── tune_hyperparameters.py         # Grid search hyperparameter optimizer
│   ├── live_benchmark_report.md        # Comprehensive report of live single-model test
│   └── live_benchmark_results.json     # Raw machine-readable live benchmark dataset
├── findings/                           # Automated security & architectural review audit reports
│   ├── review_1_ash-rpg.md             # Ash-RPG mutation authority audit findings
│   ├── review_2_ash-rpg.md             # Ash-RPG fog of war audit findings
│   ├── review_3_ash-rpg.md             # Ash-RPG dice roll determinism audit findings
│   ├── review_1_orac.md                # ORAC privilege enforcement audit findings
│   ├── review_2_orac.md                # ORAC cross-sandbox leakage audit findings
│   └── review_3_orac.md                # ORAC ledger tamper resistance audit findings
├── telemetry/                          # Usage tracking and training data mining
│   ├── collector.py                    # Telemetry logger and hard-negative triplet extractor
│   └── triplets.jsonl                  # Active contrastive training dataset (anchor, pos, neg)
├── training/                           # Contrastive neural fine-tuning
│   └── train_cross_encoder.py          # PyTorch Margin Ranking Loss trainer (prototype)
├── tests/                              # Automated regression test suite
│   ├── test_no_plaintext_secrets.py    # Zero-plaintext-credential regression test
│   ├── test_registry.py                # Workspace registry atomic write & corruption test
│   ├── test_auto_index.py              # Background auto-indexing worker test
│   ├── test_retrieval.py               # RRF pipeline and tie-breaking test
│   └── test_harness.ps1                # Agent harness event parser test
├── doctor.ps1                          # 1-click system diagnostics runner
├── install_integrations.ps1            # 1-click agent integration installer
├── index_project.ps1                   # Git-aware multi-project indexer wrapper
├── sync_hybrid_indices.ps1             # Incremental sync wrapper
├── hybrid_search.py                    # Two-Stage Hybrid Search CLI & Agent Engine
├── mcp_server.py                       # FastMCP Stdio server with absolute path resolution
├── run_security_audit.py               # Automated 6-case security audit benchmark runner
├── run_agent_harness.ps1               # Read-only agent verification harness
├── run_benchmark.ps1                   # End-to-end single-model benchmark orchestrator
├── run_evaluation_pipeline.ps1         # Master continuous evaluation & flywheel runner
├── secure_credentials.py               # Windows Credential Manager CLI utility
├── ASSESSMENT.md                       # Comprehensive security & harness assessment
├── PLAN_hands_off_creds_remediation.md # Hands-off remediation specification
├── HYBRID_PIPELINE_PLAN.md             # Historical hybrid pipeline architecture plan
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

### 5. Master Command Reference

### A. Two-Stage Hybrid Search & Agent Frontends
```powershell
# Interactive search using auto-loaded optimal parameters (k=5, wt=1.5, wc=0.5)
python hybrid_search.py "parse abstract syntax trees for multiple programming languages" -n 3

# With Stage 2 Local LLM Cross-Encoder Re-Ranking
python hybrid_search.py "throttle client queries to stay within quota limits" --rerank -n 3

# Output JSON for AI agents (Claude Code, Codex, Antigravity)
python hybrid_search.py "retry HTTP requests with exponential jitter" -j -n 5

# Capture real interaction and mine training triplets
python hybrid_search.py "throttle queries" --feedback-selected "embedder/rate_limiter.go" -n 3
```

### B. System Health & Integration Setup
```powershell
# 1-Click diagnostic health check across 18 system subsystems
.\doctor.ps1

# 1-Click hands-off integration installer for Claude Code, Codex, and Antigravity
.\install_integrations.ps1

# Verify agent autonomous retrieval in unprompted mode
.\run_agent_harness.ps1 -Agent codex -ProjectPath E:\ORAC -Prompt "Find privilege enforcement" -Mode Unprompted
```

### C. Workspace Synchronization & Dual Indexing
```powershell
# Index any arbitrary git repository into the hybrid engine
.\index_project.ps1 -ProjectPath "E:\ORAC"

# Incremental synchronization (detects additions, modifications, and deletions)
.\sync_hybrid_indices.ps1 -Project ORAC -Once
```

### D. Continuous Evaluation & Flywheel Automation
```powershell
# Run the complete end-to-end evaluation flywheel in one command
.\run_evaluation_pipeline.ps1

# Run the automated 6-case security audit benchmark across ash-rpg and ORAC
python run_security_audit.py

# Run hyperparameter grid search optimizer
python benchmarks\tune_hyperparameters.py --cases benchmarks\cases.json --text-dir repo-text --code-dir repo-code

# Execute 3-way regression benchmark
python benchmarks\benchmark.py --text-dir repo-text --code-dir repo-code --hybrid
```

### E. Telemetry & Fine-Tuning
```powershell
# Check telemetry volume and extracted training triplets
python telemetry\collector.py --status

# Export deduplicated contrastive training dataset
python telemetry\collector.py --export telemetry\export_triplets.json

# Train lightweight neural re-ranking model using Margin Ranking Loss (prototype)
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
│  - Returns absolute file paths & clickable file:/// URIs    │
│  - Deterministic tie-breaking (-rrf_score, path, line)      │
│  - Dynamic CWD project resolution via workspaces/registry   │
└──────────────────────────────┬──────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
┌───────────────────────────┐         ┌───────────────────────┐
│ 137M Text Embedder (Port  │         │ 7B Code Embedder      │
│ 1234, nomic-embed-text)   │         │ (Port 1234, 4096 dim) │
└───────────────────────────┘         └───────────────────────┘
```

### 1. Hands-Off 1-Click Installer (`install_integrations.ps1`)
Configures all environments idempotently with managed instruction blocks:
- **Claude Code:**
  - FastMCP registration in `~/.claude.json`.
  - Prompt context hooks (`~/.claude/hooks/prompt_context.py`) for automatic query injection.
  - Managed instruction block in `~/.claude/CLAUDE.md`.
- **OpenAI Codex:**
  - MCP registration in `~/.codex/config.toml`.
  - Managed instruction block in `~/.codex/AGENTS.md`.
- **Google Antigravity:**
  - Global MCP tool in `~/.gemini/antigravity/mcp/grepai-hybrid/`.
  - Native agent skill in `.gemini/skills/grepai-hybrid/SKILL.md`.

### 2. Zero Credential Leak Guarantee (Windows Credential Manager)
- Sole source of truth for LM Studio authentication is Windows Credential Manager under `grepai-hybrid/lmstudio` (User: `lmstudio`).
- Generic credential reader/writer (`semcode.creds`) uses Windows Native `Advapi32.dll` (`CredReadW` / `CredWriteW`), supporting UTF-8 and UTF-16LE without corrupting tokens.
- All 10 `.grepai/config.yaml` files have `api_key: ""` (empty).
- During indexing and querying, `semcode.grepai_runner` resolves the token from Windows Credential Manager and injects it strictly into the child process environment as `OPENAI_API_KEY`. No secrets are exposed on disk, in CLI flags, or in log files.

---

## 8. Multi-Project Hybrid Indexing & Production Workspaces

To support arbitrary production codebases without tree pollution or file conflicts, `grepai-hybrid` features a centralized multi-project workspace architecture:

### Architecture
- **Pristine Source Repositories:** Target repositories remain 100% clean and untouched.
- **Atomic Registry:** Managed in `workspaces/registry.json` with schema validation and temp-file atomic replacement to prevent corruption.
- **Git-Ignored Workspaces:** All project embeddings and local configuration files reside under `workspaces/<project_name>/` (strictly excluded via `.gitignore`).
- **Dynamic CWD Resolution:** When Claude Code, Codex, or Antigravity executes in any indexed repository, the MCP server automatically detects the current directory and routes searches to that project's dual indices.
- **Clean Git Mirroring:** `semcode.indexer` mirrors files using `git ls-files -z --cached --others --exclude-standard`, enforcing mandatory exclusions for `.claude`, `.codex`, `.gemini`, `.grepai`, submodules, and worktrees.
- **Graceful Daemon Completion:** Detects `grepai watch` stdout signal `Initial scan complete: ...` and terminates cleanly instead of polling disk size and hard-killing.

### Production Validated Projects

| Project | Domain / Languages | Tracked Files | Dual-Index Size | Verified Query Seam |
| :--- | :--- | :--- | :--- | :--- |
| **ORAC** | Autonomous Agent Governance (Python, Shell) | 193 files | ~30 MB | Privilege enforcement & sandbox gates |
| **ash-rpg** | Multiplayer Tabletop (TypeScript, Express) | 150 files | ~22 MB | Mutation authority & fog-of-war |
| **praetor_silica** | Agent Infrastructure (Python, TS) | 457 files | ~175 MB | LM Studio setup & platform locks |
| **LDGM** | Vehicle Physics Sim (C++, CMake) | 191 files | ~9.7 MB | CMake presets & ChronoVehicle gem |

---

## 9. Automatic Indexing of New Repositories (`semcode.auto_index`)

When an AI agent or developer navigates to an unindexed git repository:
1. **Eligibility Evaluation:** `semcode.auto_index.check_eligibility()` verifies that the target path is a git repository, does not match deny patterns in `config/auto_index.json` (e.g. `node_modules`, `AppData`, `.git`), and has fewer tracked files than `max_file_count` (default: 5,000).
2. **Atomic Registration:** Registers the project into `workspaces/registry.json`.
3. **Detached Background Execution:** Spawns a detached background worker running `semcode.auto_index` to index both 137M text and 7B code indices asynchronously.
4. **Job Status Tracking:** Writes job status and progress to `workspaces/<project>/job.json` (`indexing`, `complete`, `failed`).

---

## 10. 18-Point System Diagnostic Doctor (`doctor.ps1`)

The diagnostics engine (`semcode.doctor`) validates the complete operational chain:
1. Python runtime and `mcp` / `semcode` import sanity
2. `grepai.exe` binary accessibility & version verification
3. Windows Credential Manager target `grepai-hybrid/lmstudio` exists and is non-empty
4. LM Studio API connectivity on `http://127.0.0.1:1234/v1/models`
5. LM Studio embeddings generation test call with authenticated header
6. Workspace registry (`workspaces/registry.json`) schema validation & corruption check
7-10. Dual index directory and config integrity for ORAC, ash-rpg, praetor_silica, LDGM
11-14. Git tracking and exclusion rules for all registered projects
15. FastMCP server initialization test (`mcp_server.py`)
16. Claude Code integration (`~/.claude.json`, hooks, instructions)
17. OpenAI Codex integration (`~/.codex/config.toml`, instructions)
18. Antigravity IDE integration (global MCP definition, skills)


