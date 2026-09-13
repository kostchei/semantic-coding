# Plan: Hands-Off grepai, Credential Handling, and Repository Remediation

**Date:** 2026-09-13  |  **Status:** Proposal. Only this document was added; no other files changed.
**Revision 2:** Adds the "new repo" gap closure (Part A.0), automatic indexing of new repos, a fix for the hidden Claude Code tool, a genuinely unprompted harness test, and worktree exclusion. Line numbers are updated for commit `2a9963f`.
**Revision 3:** Your decisions are applied. The first grepai call in a new repo starts indexing immediately. The scan scope is accepted as proposed. Indexing follows `.gitignore` and never indexes git history.
**Constraint (global CLAUDE.md):** *No fallbacks. Throw an error.* Every design below fails loudly and names the fix. Nothing silently degrades.

---

## 0. Verified current state (what the plan is built on)

| Fact | Evidence |
|---|---|
| Hybrid MCP server is registered in Claude Code **twice**: user scope and one project entry | `~/.claude.json` (two `grepai-hybrid` blocks) |
| In Claude Code the tool is **deferred** behind ToolSearch. The model never sees its schema unless it searches for it | Observed in this session: `mcp__grepai-hybrid__search_codebase` appears in the deferred-tool list |
| Codex has `grepai_hybrid` enabled | `codex mcp list` |
| Antigravity's `mcp_config.json` does **not** register grepai-hybrid. Only a stale descriptor dir exists, and it falsely says the server "auto-resolves from caller directory" | `~/.gemini/antigravity/mcp_config.json`, `~/.gemini/antigravity/mcp/grepai-hybrid/search_codebase.json` |
| The Gemini/Antigravity skill is **repo-local**. It only loads when Semantic_Coding itself is open, never in ash-rpg/ORAC/etc. | `.gemini/skills/grepai-hybrid/SKILL.md` |
| No global instruction mentions grepai: `~/.claude/CLAUDE.md` (one line), `~/.codex/AGENTS.md` (empty), `~/.gemini/GEMINI.md` (empty). No global skills dirs | inspected |
| LM Studio token lives in Windows Credential Manager, target `PraetorSilica/LMStudioDev`, user `lmstudio-dev` | `cmdkey /list` |
| **The same token is copied in plaintext into 10 `.grepai/config.yaml` files** (`repo-text`, `repo-code`, and 4 projects x 2) | `api_key:` non-empty in every workspace config (values not printed) |
| Git history scan found no committed token | `git log -p --all` grep for api_key/Bearer/sk- |
| grepai's OpenAI-compatible embedder reads `OPENAI_API_KEY` from the environment when `api_key` is empty | `grepai/embedder/openai.go:149-150` |
| grepai v0.37 `watch` has **no `--once` flag** | `grepai.exe watch --help` |
| Tests: `python -m unittest discover -s tests` passes 6/6; `tests/test_harness.ps1` passes 6/6. `python -m unittest tests.test_retrieval` fails (no `tests/__init__.py`) | run locally (before `2a9963f`; ASSESSMENT now reports 11 Python tests) |
| Only 4 projects are indexed (ORAC, praetor_silica, ash-rpg, LDGM). Nothing indexes a new repo automatically | `workspaces/registry.json` |
| No Claude Code hooks exist | `~/.claude/settings.json` |
| The only "live" agent evidence (ASSESSMENT.md:47, "read `src/orac/broker.py`") comes from `run_agent_harness.ps1`, which tells the agent to call `search_codebase`, restricts its tools, and ran on an already-indexed repo. It proves the MCP path works, not hands-off adoption | `run_agent_harness.ps1` request text and tool flags |
| The ORAC index contains a stale Claude worktree copy (`.claude\worktrees\sad-gould-f315a4\src\orac\broker.py`) that competes with the real file | `findings/review_1_orac.md`, `findings/review_2_orac.md` |
| Commit `2a9963f` added `secure_credentials.py`, which stores the Claude harness OAuth token in Credential Manager (`SemanticCoding/ClaudeCodeOAuth`) and injects it into child CLI processes only | `secure_credentials.py:12` |

---

## Part A: Using grepai without saying "use grepai" every time

### A.0 Gap closure: "I open a new repo in Claude Code, Codex or Antigravity"

Every gap found in the new-repo walkthrough, the fix, and the test that proves it's closed. Nothing here is done until its test passes.

| # | Gap today | Fix (details in A.2) | Proof |
|---|---|---|---|
| G1 | New repo isn't indexed; only 4 projects in the registry | **Auto-index** (Layer 5b): the first session start or first MCP call in an unregistered git repo queues a background index job and returns an explicit "indexing in progress" error with ETA. The Scheduled Task also discovers repos under configured roots | E2E: fresh throwaway repo → open session → index job starts → search works once it finishes, with no manual command |
| G2 | `~/.codex/AGENTS.md` empty | Managed instruction block (Layer 2) | `doctor.ps1` finds the block; Codex unprompted run passes (G9) |
| G3 | `~/.gemini/GEMINI.md` empty | Managed instruction block (Layer 2) | `doctor.ps1`; Antigravity manual protocol passes (G9) |
| G4 | `~/.claude/CLAUDE.md` only has "no fallbacks" | Managed instruction block appended below your line, never replacing it (Layer 2) | `doctor.ps1`; your existing line is unchanged |
| G5 | No Claude Code hooks | `UserPromptSubmit` + `SessionStart` hooks at user scope (Layer 3) | Hook unit tests; a prompt in a registered repo shows injected hits; a prompt in an unrelated dir injects nothing |
| G6 | Antigravity doesn't register grepai-hybrid | Add it to `~/.gemini/antigravity/mcp_config.json`, install a global skill, delete the stale descriptor (Layer 4) | `doctor.ps1`; the tool appears in a new Antigravity conversation |
| G7 | Claude Code hides (defers) the tool | Server `instructions=` (these reach the system prompt even while the tool is deferred; seen in this session), a "when to use" tool description, and the prompt hook, which makes deferral irrelevant. Also check whether Claude Code has a setting to always load this server's tools (e.g. the `ENABLE_TOOL_SEARCH` env setting) and use it if it exists (Layer 1) | Unprompted Claude run calls the tool before Grep/Glob (G9) |
| G8 | No `project` → silently searches the grepai Go testbed (`hybrid_search.py:312-315`) | Delete the default. Resolution is explicit arg → MCP roots → server CWD → **error** naming the path and the auto-index status. Same for the CLI and `sync_hybrid_indices.ps1` defaults (Layer 1) | Unit tests: unknown cwd raises; no code path returns `repo-text`/`repo-code` |
| G9 | Only "instructed" harness evidence exists | New **unprompted** harness mode: prompts never mention grepai, the agent's normal toolset and your real global config, plus a never-indexed repo scenario. Correct ASSESSMENT.md so it no longer implies hands-off use (Layer 6) | ≥80% tool-first across Claude and Codex × ash-rpg, ORAC and one new repo; results stored in `harness-results/` |
| G11 | Mirrors ignore `.gitignore`: they copy ignored files (`.env`, build output, caches) and rely on a guessed list of folder names | Build the file list from git itself (Layer 5, "File selection"). Only tracked files and untracked-but-not-ignored files are mirrored, never `.git` or history | Test repo with a `.gitignore`d `.env` and `dist/`: neither appears in the mirror or in search results; no `.git` directory in any workspace |
| G10 | Worktree copies pollute the ORAC index | Exclude `.claude/`, nested git worktrees (any dir containing a `.git` *file*) and other agent scratch dirs; re-sync ORAC; regenerate findings (C.2) | Search for "ToolBroker dispatch" in ORAC returns only `src/orac/broker.py`, no `worktrees` paths |

### A.1 Root causes (why agents don't use it unprompted)

1. **Not in always-loaded context.** No global instructions, no global skills, and Claude Code defers the tool. Antigravity isn't registered at all.
2. **Calling it without `project` silently searches the wrong corpus.** With no project, `resolve_project_dirs` falls back to the server process CWD, then to `repo-text/repo-code` (the grepai Go testbed) (`hybrid_search.py:312-315`). An agent that tries it in ash-rpg and gets Go results learns to ignore it.
3. **Stale indexes.** Workspaces are mirrors that are only refreshed by hand (`index_project.ps1`), and `sync_hybrid_indices.ps1` is broken (see C). Stale hits erode trust.
4. **Output isn't directly actionable.** Paths are relative to the *mirror*, and the markdown link `file:///{relative}` is broken (`mcp_server.py:124`). The agent must guess the real source path.
5. **The harness measures the wrong thing.** `run_agent_harness.ps1` explicitly tells the agent to call the tool, restricts its tools, and only ran on indexed repos, so it can't tell whether the setup is actually hands-off.
6. **New repos are never indexed.** Even a perfectly instructed agent has nothing to search in a repo you just opened.
7. **Indexes include junk copies.** Claude worktrees under `.claude/worktrees` get mirrored and indexed, so agents may be sent to a stale copy of a file.

### A.2 Design: layered, ordered by leverage

**Layer 1: Make the server self-sufficient** (fixes 2 and 4; benefits every harness)
- Resolve the project in this order: explicit `project` arg -> **MCP roots** (`ctx.session.list_roots()`, supplied by the client) -> the server process CWD, if it's inside a registered source path -> **error**. Delete the `repo-text/repo-code` default everywhere (MCP, CLI, sync script); the grepai testbed stays reachable only by explicitly passing `--text-dir/--code-dir` in benchmarks.
  - For an unregistered git repo, the error triggers auto-index (Layer 5b) and says so: *"<path> is not indexed yet. Indexing started (job <id>, ~N min for M files). Retry after it finishes; status: `python -m semcode.indexer status`."* For a non-repo path it says *"<path> is not a git repo; not auto-indexed. Run: index_project.ps1 -ProjectPath <path>"*.
- **Hidden-tool fix (G7):** server `instructions=` and the tool description carry the usage policy, because Claude Code shows server instructions even when the tool schema is deferred. Check the Claude Code docs for a supported way to keep this one server's tools always loaded, and apply it via `install_integrations.ps1` if one exists. Either way, the prompt hook (Layer 3) puts results in context without the model needing to find the tool.
  - *Verify first:* log `roots` and `os.getcwd()` at startup for Claude Code, Codex, and Antigravity. Claude Code normally starts stdio servers in the session directory, which would make the CWD step correct for it.
- Return **absolute source paths** (`source_path / rel`) and working `file:///` links, so `Read` works on them directly.
- Put an index-age banner in every response (from `indexed_at` and the last sync). If the source has changed since the last sync, trigger an incremental sync (Layer 5). If that sync fails, raise.
- Pass FastMCP `instructions=`. Claude Code injects server instructions into the system prompt even when the tool itself is deferred. Keep it short: *"For conceptual 'where/how is X implemented' questions in an indexed project, call search_codebase before Grep/Glob. Use Grep only for exact identifiers."*
- Rewrite the tool description around **when to use it**, not how it works internally (the 137M/7B/RRF details don't help the model decide).

**Layer 2: Global instruction blocks** (all harnesses, cheap)
- Write one managed block, fenced with `<!-- grepai-hybrid:begin/end -->`, into `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, and `~/.gemini/GEMINI.md`. It's generated from a single template in the repo (`integrations/instructions.md`). Keep it to about 6 lines: retrieval policy, the "Grep only for exact strings" rule, and "if the tool errors, report the error, don't work around it".

**Layer 3: Claude Code hooks** (the part that actually removes "remember to")
- `UserPromptSubmit` -> `integrations/hooks/prompt_context.py`
  - If `cwd` is inside a registered project and the prompt isn't a slash command or trivially short, run the hybrid search on the prompt text (limit 5) and emit `additionalContext` as a compact list: `path:Lstart-Lend (score)` plus a one-line snippet each. Keep it under about 1.5k tokens.
  - If `cwd` isn't registered, emit nothing. That's out of scope, not a fallback.
  - If the project **is** registered but the search fails (LM Studio down, missing credential, corrupt index), put the error text into context and exit non-zero so it's visible. Never skip silently.
  - Budget: RRF without rerank; hook timeout about 10 s. Measure p95 latency against the 7B model first.
- `SessionStart` -> print registration and freshness status for `cwd` (e.g. "ash-rpg indexed 2h ago, 3 files changed since").
- Install into `~/.claude/settings.json` (user scope) so it applies in every repo.
- Not doing: a PreToolUse hook that blocks Grep. Too noisy, and it would stop exact-string searches that should run.

**Layer 4: Codex and Antigravity parity**
- **Codex:** check whether this Codex build supports user-level hooks (plugin manifests already mention `hooks`, per the stderr in `harness-results/`). If it does, reuse `prompt_context.py`. If not, rely on the AGENTS.md block plus a global skill in `~/.codex/skills/grepai-hybrid/`.
- **Antigravity:** add `grepai-hybrid` to `~/.gemini/antigravity/mcp_config.json`, move the skill to the global skills location (check the path Antigravity loads globally), and delete the stale descriptor dir.
- Keep one skill source in the repo (`integrations/skill/SKILL.md`) and render it into each harness. Fix its content: it references `run_command` and the bogus default project.

**Layer 5: Freshness without manual steps**
- Replace the polling PowerShell sync with a single Python `sync` command that, per registered project, does:
  1. mtime/size diff including **deletions**
  2. mirror only what changed, using the same exclude list as indexing
  3. an incremental grepai update
  4. write `last_synced_at` to the registry
- Run it three ways: (a) on demand from the MCP server and the hook when the source is newer, (b) as a logon Scheduled Task (`sync --all --watch`), and (c) manually.
- **File selection (G10, G11):** the file list comes from `git -C <repo> ls-files -z --cached --others --exclude-standard`, not from robocopy name filters.
  - This honours `.gitignore` at every level, `.git/info/exclude`, and your global git excludes file.
  - It includes untracked work you haven't committed yet, as long as it isn't ignored.
  - **Git history is never indexed.** `.git/` is never copied, and nothing reads commits, diffs, logs or other branches. Only the current working-tree files are indexed.
  - On top of git's list, a small mandatory exclude set always applies, even if a repo forgets to ignore it: `.grepai`, `.claude` (covers `.claude/worktrees`), `.codex`, `.gemini`, and any subdirectory that is its own worktree, nested repo or submodule (has a `.git` file or dir). Submodules are separate repos and get indexed separately if you open them.
  - Deleted or newly ignored files are removed from the mirror on the next sync.
  - The old hardcoded folder-name list (`data`, `bin`, `out`, `site`, and so on) is deleted.
  - Existing indexes are re-synced once under these rules, which purges the worktree copies and any ignored files already mirrored.

**Layer 5b: Automatic indexing of new repos (G1)**
- **Triggers (decided):**
  1. The Claude `SessionStart` hook.
  2. The **first grepai call from any harness** whose resolved path is unregistered. This starts the GPU job immediately, without a confirmation step.
  3. Discovery by the Scheduled Task under configured roots (default `D:\Code`, `E:\proj`) for repos with commits in the last 30 days.
- **Eligibility, checked before queueing (each failure is an explicit error, never a silent skip):**
  - Path is the top of a git repo (resolved via `git rev-parse --show-toplevel`, so opening a subfolder indexes the whole repo).
  - Not a drive root, home dir, or a path in `config/auto_index.json` `deny` list.
  - File count from the git file list (after `.gitignore` and mandatory excludes) ≤ `max_files` (default 5,000). Larger repos return *"too large for auto-index (N files); run index_project.ps1 -ProjectPath <path> to confirm"*.
- **Job runner:** `python -m semcode.indexer enqueue <path>`. A single queue with one job at a time (both embedding models share the GPU), a lock file per project, progress and ETA in `workspaces/<name>/job.json`, detached from the harness so closing the session doesn't kill it. Uses the Credential Manager key via `grepai_runner` (Part B).
- **Registration** happens only after the index-completion check passes. A failed or timed-out job is recorded as `failed` with the reason and is not retried until the source changes or you run it manually.
- **Naming:** project name = repo folder name; a collision with a different `source_path` gets a suffix (`name-2`) instead of overwriting.
- **While a job runs:** search calls return the explicit "indexing in progress" error, and the prompt hook injects one line of status instead of hits.

**Layer 6: Installer, doctor, and a real success metric**
- `install_integrations.ps1`: idempotent. Removes the duplicate Claude project-scope entry. Registers MCP in Claude (user), Codex, and Antigravity. Writes the instruction blocks, skills, and hooks. Backs up every file it touches.
- `doctor.ps1`: checks Python and `mcp`, `grepai.exe`, that the credential exists, that LM Studio is reachable **with auth**, each harness registration, registry freshness, and one live query per project. Any failure means a non-zero exit and a remediation line.
- Add an **unprompted** mode to `run_agent_harness.ps1` (G9). It differs from the current instructed mode in every way that made the ORAC "broker.py" run weak evidence:
  - **Prompt:** the user's task only, e.g. "where is caller authorization enforced?". No mention of grepai, MCP, or search order.
  - **Tools:** the harness's normal toolset (Grep, Glob, Bash/shell, Read). No `--strict-mcp-config`, no tool allowlist, no per-tool approval beyond what the installed global config grants.
  - **Config:** the real user-level config written by `install_integrations.ps1` (instructions, hooks, MCP registration), not an injected one.
  - **Scenarios:** ash-rpg and ORAC (indexed), plus a throwaway **never-indexed** repo to exercise auto-index (G1) end to end.
  - **Metric:** whether `search_codebase` (or hook-injected results) came before the first Grep/Glob/shell search, and whether the files the agent read match returned hits. At least 5 prompts per repo per harness.
  - **Acceptance:** ≥80% tool-first for Claude Code and Codex on indexed repos. The new-repo scenario must show the auto-index job starting and a successful search after it finishes.
  - **Antigravity:** the IDE agent can't be scripted from here, so there's a written manual protocol (same prompts, record tool calls from the conversation log) run once per release.
  - Keep the existing instructed mode as the retrieval-correctness check, and relabel it that way.
- Correct ASSESSMENT.md:47 onward to say the Claude and Codex runs were **instructed** runs on indexed repos, and don't show unprompted use.

---

## Part B: Credentials

### B.1 Problems today
- The token is **written in plaintext into every workspace config** (`index_project.ps1:98`, `run_benchmark.ps1` configs). The Credential Manager copy is effectively decorative.
- There are **three separate readers**: Python ctypes (`hybrid_search.py:20-56`), C# `Add-Type` (`run_benchmark.ps1`), and `python -c` string interpolation (`index_project.ps1:53`).
- **Silent fallbacks everywhere:** exceptions swallowed and then `LM_API_TOKEN`, then `""`. A missing credential shows up later as a confusing 401 from LM Studio, or as rerank silently not running.
- `--token` is a CLI flag (`hybrid_search.py:333`), so the token can appear in process listings and shell history.
- The target name `PraetorSilica/LMStudioDev` ties this tool to an unrelated project.
- `generate_synthetic_cases.py:176` never passes a token, so with auth enabled the LLM path always fails and silently uses heuristics.

### B.2 Design: Windows Credential Manager as the single source, injected per process
- **Store:** one Generic credential, `grepai-hybrid/lmstudio`, protected by DPAPI and scoped to your Windows user. Set it once with a prompt, so the value never lands in shell history:
  ```powershell
  cmdkey /generic:grepai-hybrid/lmstudio /user:lmstudio /pass
  ```
  (or `python -m semcode.creds set lmstudio`, which uses `getpass`).
- **One reader:** `semcode/creds.py`
  - Stdlib ctypes with correct `argtypes`/`restype`, `CredFree` in `finally`, UTF-16 decode.
  - Raises `CredentialMissing("grepai-hybrid/lmstudio not found. Run: cmdkey /generic:... /pass")`. No env fallback. Non-Windows raises `NotImplementedError`.
- **Nothing on disk:** delete `api_key` from every generated config. Every grepai invocation (search, watch, index) goes through one launcher, `semcode/grepai_runner.py`, which builds `env = {**os.environ, "OPENAI_API_KEY": creds.get("lmstudio")}` for **that child process only**. grepai picks it up (`openai.go:149-150`). Nothing is set at user or machine level, and PowerShell scripts never hold the secret.
  - This also means indexing moves out of PowerShell `Start-Process` and into Python. That's needed anyway (see C).
- **Remove** the `--token` flag and `LM_API_TOKEN`.
- **Agent CLI credentials (Claude/Codex):** leave them in their own stores. For unattended harness runs, `secure_credentials.py` (commit `2a9963f`) already stores the Claude OAuth token in Credential Manager and injects it into child processes only. Fold its ctypes code into `semcode/creds.py` so there is one Credential Manager implementation, and keep its target name.
- **Alternatives considered:**
  - `keyring` (adds a dependency, uses Credential Manager underneath anyway)
  - PowerShell SecretManagement/SecretStore (extra module and a second master password)
  - a DPAPI-encrypted file (reinvents Credential Manager)
  - turning off LM Studio auth and binding to 127.0.0.1 (simplest, but gives up defence-in-depth; your call, see Part F)

### B.3 Migration (in order)
1. Create `grepai-hybrid/lmstudio` and **rotate** the LM Studio key. The old key has been sitting in plaintext in 10 files, which are also copied by any backup of `E:\`.
2. Land `creds.py` and `grepai_runner.py`, switch every caller, then delete the `PraetorSilica/LMStudioDev` reads.
3. Strip `api_key` from the 10 existing configs (script it; don't re-index).
4. Add `tests/test_no_plaintext_secrets.py`: fail if any `workspaces/**/.grepai/config.yaml`, `repo-*/.grepai/config.yaml`, or tracked file contains a non-empty `api_key`/`Bearer`. Add a doctor check for the same.
5. Delete the old credential with `cmdkey /delete:PraetorSilica/LMStudioDev`, after confirming praetor_silica itself doesn't use it.

---

## Part C: Defect inventory

Severity: **H** = wrong results, data loss, or secret exposure. **M** = broken or misleading feature. **L** = hygiene.

### C.1 Retrieval core and MCP
| Sev | Location | Problem |
|---|---|---|
| H | `hybrid_search.py:312-315` | No project match -> silently searches `repo-text/repo-code` (the grepai testbed). Must raise. |
| H | `mcp_server.py:124`; result `file_path` | Paths are relative to the mirror, and the `file:///` link is broken. Agents can't open results reliably. |
| M | `hybrid_search.py:20-56` | Credential read swallows every exception and falls back to env/empty (see B). |
| M | `hybrid_search.py:176-191, 254-256` | Rerank auto-picks the first non-embedding model and returns the unranked list on *any* error. `--rerank` can do nothing with no signal. |
| M | `hybrid_search.py:348-361` vs `mcp_server.py:63-75` vs `run_security_audit.py:98` vs `benchmark.py:196` | Four different RRF parameter sources and defaults (15/1.0/1.1 vs 5/1.5/0.5), plus swallowed `optimal_params.json` errors. `benchmark.py --hybrid` never uses the tuned values. |
| M | 5 copies | Retrieve -> fuse orchestration is duplicated in `hybrid_search.main`, `mcp_server.search_codebase`, `run_security_audit`, `benchmark.evaluate_hybrid`, and `tune_hyperparameters.evaluate_grid`. They have already drifted (different tie-breaking at `tune_hyperparameters.py:108`). |
| M | `benchmarks/optimal_params.json` | Tuned in-sample on 12 Go queries, then applied globally to TS/Python/C++ projects. Should be per project, or at least labelled as such. |
| M | `hybrid_search.py:392-402`, `mcp_server.py:98-106` | Telemetry failures swallowed. MCP always logs, with no opt-out, and stores 500 chars of private source per candidate. |
| L | `hybrid_search.py:124` | "Best chunk" compares cosine scores from two different models, which aren't comparable. |
| L | `hybrid_search.py:59-60` | `find_binary(custom_path)` silently ignores a non-existent custom path. |
| L | `hybrid_search.py:81,91` | grepai stderr is discarded, so errors say "check the index" with no cause. |
| L | `hybrid_search.py:309` vs `299` | Inconsistent boundary check (`rstrip(os.sep)` in one branch only). Breaks for drive-root sources. |
| L | `mcp_server.py:9,12,29-30` | Unused imports; `DEFAULT_TEXT_DIR/CODE_DIR` are dead. |

### C.2 Indexing and sync lifecycle
| Sev | Location | Problem |
|---|---|---|
| H | `index_project.ps1:98` | Plaintext token in config (Part B). |
| H | `index_project.ps1:81-82` | `robocopy /MIR` without `/XD .grepai` **purges the existing index and config** on re-index, forcing a full re-embed every time. It also deletes the watch logs. |
| H | `index_project.ps1:234-239` | `catch {}` on a registry parse error -> starts from an empty hashtable -> **overwrites registry.json, dropping every other project**. |
| H | `index_project.ps1:164` | On timeout it just `break`s, then still registers the project as indexed. |
| H | `index_project.ps1` and `sync_hybrid_indices.ps1` | "Done" means file size stopped changing, followed by `Stop-Process -Force` and lock deletion. Can kill grepai mid-write and leave a corrupt or partial gob. Use a grepai completion signal (`grepai status`, or the watcher's initial-scan-complete marker) and graceful shutdown. |
| H | `index_project.ps1:73-78` (missing entries) | `.claude` isn't excluded, so `.claude/worktrees/*` copies are indexed. The ORAC index returns `.claude\worktrees\sad-gould-f315a4\src\orac\broker.py` alongside the real file. Nested worktrees/repos aren't detected either. |
| H | registry / indexing | No automatic indexing: a new repo stays unsearchable until `index_project.ps1` is run by hand (fixed by Layer 5b). |
| M | `index_project.ps1:73-78`, `sync_hybrid_indices.ps1:143-144` | `.gitignore` is not honoured: ignored files such as `.env`, build output and caches are copied into mirrors (and can end up embedded). Replaced by the git file list (G11). Also: global dir-name excludes (`data`, `bin`, `out`, `site`, `User`, `Cache`, `build`) silently drop real source dirs such as `src/data`. Make excludes per project, stored in the registry. |
| M | `sync_hybrid_indices.ps1:11-13,39` | Defaults to the grepai testbed, and falls back to it when the project isn't in the registry. |
| M | `sync_hybrid_indices.ps1:118` | `-Once` re-runs watch but never mirrors source changes. |
| M | `sync_hybrid_indices.ps1:133-139` | Detects only added/modified files; deletions never trigger a sync. |
| M | `sync_hybrid_indices.ps1:143-144` | Exclude list differs from indexing (only `.git .grepai`), so a sync mirrors `node_modules`, `.venv`, etc. into workspaces indexed with filters. |
| M | `sync_hybrid_indices.ps1:72` | Only treats the index as committed above 1 MB, so small projects always hit the 180 s timeout. |
| M | `sync_hybrid_indices.ps1:104` | Regex `\.git` also matches `.github`, `.gitignore`. |
| L | `index_project.ps1:252` | Non-atomic registry write; concurrent runs race. PS 5.1 writes a BOM (the reader copes via `utf-8-sig`). |
| L | `index_code.ps1` | Dead: hardcoded `e:\` paths, superseded by `index_project.ps1`. |

### C.3 Benchmarks, tuning, training, audit
| Sev | Location | Problem |
|---|---|---|
| H | `run_benchmark.ps1:216,237`; `README.md:132` | Uses `grepai watch --once`, **which doesn't exist**. The advertised end-to-end benchmark can't run. It also writes plaintext tokens and blocks on `Read-Host`. |
| M | `benchmarks/benchmark.py:77-94` | Backend failures still become `[]` (a "miss"). ASSESSMENT.md says this was fixed; it was only fixed in `hybrid_search.py`. No subprocess timeout. |
| M | `benchmarks/tune_hyperparameters.py:40-52` | Same: exit codes ignored, JSON errors -> `[]`. A dead LM Studio gives a confident "optimal" config. |
| M | `benchmarks/benchmark.py:367-372` | Missing `--cases` silently swaps in the default `cases.json`. |
| M | `run_evaluation_pipeline.ps1:32 vs 39,48` | Phase 1 generates `synthetic_cases.json`, but phases 2-3 only read `cases.json`, so synthetic cases are never used. `ErrorActionPreference=Continue` with no `$LASTEXITCODE` checks means failed phases report "Flywheel Complete". |
| M | `benchmarks/generate_synthetic_cases.py:153-154,136,176` | LLM errors fall back to heuristics silently. Hardcoded model name. Token never passed. Go-only. |
| M | `benchmarks/generate_synthetic_cases.py:37` | `"test" in rel` excludes any path containing "test" (e.g. `attestation`). |
| M | `training/train_cross_encoder.py:206` | Fewer than 5 triplets -> silently trains on fabricated synthetic data. The checkpoint is never loaded by anything (ASSESSMENT agrees). |
| L | `training/train_cross_encoder.py:71-72` | Comment says `[q, c, abs(q-c), q*c]`; the code concatenates `[q, c]`. It's a bi-encoder plus MLP, not a cross-encoder. `checkpoint_dir` is relative to CWD (`:125`). |
| M | `telemetry/collector.py:58-60` | Selected-file match is substring (`app.ts` matches `myapp.ts`), so it produces wrong positives and negatives. |
| M | `telemetry/triplets.jsonl` (tracked) | Once feedback is used on private repos, their source gets committed. Move it to ignored storage, or gate commits. |
| L | `run_security_audit.py:98,76` | Hardcoded RRF params; overwrites the committed `findings/` on every run; a "PASS" only means a file appeared (acknowledged). |
| L | pyflakes | Unused imports in `mcp_server`, `run_security_audit`, `collector`, `tune_hyperparameters`, `generate_synthetic_cases`, `train_cross_encoder`; placeholder-less f-string at `tune_hyperparameters.py:191`. |
| L | `tests/` | No `__init__.py`; tests only run through `discover` from the repo root. No tests for registry writes, indexing, credentials, or MCP output formatting. |

### C.4 Docs, config, and integration drift
| Sev | Location | Problem |
|---|---|---|
| M | `ASSESSMENT.md:47` onward | Describes live Claude and Codex runs ("called MCP, read `src/orac/broker.py`") without saying they were instructed, tool-restricted runs on an indexed repo. Reads as proof of hands-off use. |
| M | `findings/review_1_orac.md`, `findings/review_2_orac.md` | Contain hits from the stale `.claude/worktrees` copy; regenerate after the ORAC re-sync. |
| M | `claude_code_security_audit_guide.md:44` | Claims the server auto-detects the client's working directory (false; ASSESSMENT confirms). |
| M | `claude_code_security_audit_guide.md:22` | Tells you to run `grepai agent-setup` in target repos. That writes into target trees (contradicting "never write to target trees") and wires single-model grepai, not hybrid. |
| M | `README.md` sections 4/9, `SYSTEM_STATE.md` | Stale file manifest (no MCP, workspaces, or harness). "Production-ready" (`SYSTEM_STATE.md:12`) contradicts ASSESSMENT.md. The Antigravity section describes a registration that doesn't exist. |
| L | `HYBRID_PIPELINE_PLAN.md` | Phases 2-5 still unchecked although implemented. Mark it historical or fold it into SYSTEM_STATE. |
| L | `templates/config.*.yaml` | Not used by any script (configs are generated inline, and with a different provider). Dangling. |
| L | `.gitignore` | `*token*` and `*secret*` would silently ignore legitimate files (e.g. `tokenizer.py`, `test_no_plaintext_secrets.py`). `benchmark_results.json` (written by `run_benchmark.ps1`) isn't ignored. |
| L | `~/.claude.json` | Duplicate grepai-hybrid registration (user and project scope). |
| L | `~/.gemini/antigravity/mcp/grepai-hybrid/` | Stale descriptor with a false auto-resolve claim. |

---

## Part D: Target structure

```
semcode/                     # importable package; single implementation of everything
  creds.py                   # Credential Manager read/set; raises, no fallback
  registry.py                # load/validate/atomic-write registry.json; per-project excludes & params
  grepai_runner.py           # all grepai subprocesses; env-injected key; timeouts; stderr surfaced
  pipeline.py                # resolve -> retrieve(parallel) -> fuse -> rerank; ONE RRF implementation
  indexer.py                 # mirror (incl. deletions, .grepai preserved) + index with completion signal
  sync.py                    # incremental sync; --all --watch for Scheduled Task
  telemetry.py               # opt-in, private-content-aware
hybrid_search.py             # thin CLI over semcode.pipeline
mcp_server.py                # thin MCP adapter; roots-based resolution; instructions=
integrations/
  instructions.md            # global CLAUDE.md / AGENTS.md / GEMINI.md block
  skill/SKILL.md             # rendered into each harness
  hooks/prompt_context.py    # UserPromptSubmit / SessionStart
install_integrations.ps1     # idempotent installer w/ backups
doctor.ps1                   # end-to-end health check
index_project.ps1 / sync     # thin wrappers calling python -m semcode.indexer / .sync
benchmarks/, training/       # import semcode.pipeline; no private RRF copies
```

Delete: `index_code.ps1`, `templates/` (or wire it in as the actual config source), the `DEFAULT_*_DIR` dead code, and the `run_benchmark.ps1` credential C#.

---

## Part E: Execution order

| Phase | Work | Acceptance |
|---|---|---|
| **1. Stop the bleeding** | Rotate the LM Studio key; `semcode/creds.py` (absorbing `secure_credentials.py`) + `grepai_runner.py`; strip `api_key` from the 10 configs; secrets test. **Delete the wrong-repo default (G8)**; correct ASSESSMENT.md's harness wording (G9) | No `api_key` on disk; every search and index works via the injected env; a missing credential gives a clear error; no code path returns `repo-text`/`repo-code` without explicit dirs |
| **2. Correctness core** | `registry.py` (atomic, raises on parse error); `pipeline.py` as the single RRF; absolute paths in output; benchmark/tune raise on backend failure | Unit tests: unknown cwd raises; corrupt registry raises without writing; benchmark with a dead backend exits non-zero |
| **3. Index lifecycle** | Python indexer/sync: preserve `.grepai`, handle deletions, git-based file selection honouring `.gitignore`, no `.git`/history (G11), plus mandatory `.claude`/worktree/submodule excludes (G10), real completion signal, no `Stop-Process -Force`. Re-sync all 4 projects; regenerate ORAC findings | Re-indexing an unchanged project re-embeds 0 files; deleting or newly ignoring a file removes it from results; timeout marks the project failed; no `worktrees` paths, ignored files or `.git` dirs in any workspace |
| **4. Auto-index (G1)** | Job queue, eligibility checks, `config/auto_index.json`, triggers from MCP + SessionStart, optional root discovery in the Scheduled Task | Throwaway repo: first call returns "indexing started", job completes, next call returns hits; oversized/denied/non-git paths return their explicit errors |
| **5. Hands-off integration** | MCP roots + `instructions=` + always-load setting if supported (G7); instruction blocks in CLAUDE.md/AGENTS.md/GEMINI.md (G2-G4); Claude hooks (G5); Codex hooks or skill; Antigravity registration + global skill (G6); installer + doctor | `doctor.ps1` all green on every G-row; hook adds context in a registered repo and nothing elsewhere |
| **6. Prove it** | Unprompted harness mode (G9) across Claude and Codex × ash-rpg, ORAC and a never-indexed repo; Antigravity manual protocol; Scheduled Task sync | ≥80% tool-first on indexed repos; new-repo scenario passes end to end; p95 hook latency ≤ 10 s; every row in A.0 marked proven |
| **7. Cleanup** | Fix the evaluation pipeline and synthetic generator (or delete them); training either wired into rerank or clearly marked experimental; fix telemetry matching and privacy; docs rewrite (README, SYSTEM_STATE, audit guide; archive HYBRID_PIPELINE_PLAN); `.gitignore`; pyflakes clean | Docs match `doctor.ps1` output; `python -m unittest` and `tests/test_harness.ps1` pass |

---

## Part F: Decisions needed from you

1. **LM Studio auth:** keep auth with Credential Manager injection (recommended), or disable auth and bind to 127.0.0.1 only (removes credentials entirely)?
2. **Auto-context hook scope:** inject search results on *every* prompt in registered repos (most hands-off, costs about 1-1.5k tokens and a few seconds per prompt), or only in SessionStart plus instructions (cheaper, relies on the model choosing to call the tool)?
3. **Mirrors vs in-tree index:** keep mirroring (no writes to target repos, but two full copies and sync complexity), or allow grepai's `.grepai/` inside target repos (git-ignored via `.git/info/exclude`) and drop mirroring? The latter removes most of Part C.2.
4. **Training and flywheel code:** invest (wire the checkpoint into rerank, use real feedback) or move to `experimental/` and stop advertising it?
5. **Language port:** OK to move indexing and sync from PowerShell to Python (needed for per-process credential injection and to share registry code)?
6. ~~Auto-index scope~~ **Decided:** discovery roots `D:\Code` and `E:\proj`, 30-day activity window, 5,000-file cap. Indexing follows `.gitignore`; git history is never indexed.
7. ~~Auto-index trigger~~ **Decided:** the first grepai call in a new repo starts the indexing job immediately, in every harness.
