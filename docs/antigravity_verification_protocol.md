# Antigravity Unprompted Verification Protocol

This manual verification protocol tests organic, unprompted adoption of grepai-hybrid in the Antigravity IDE agent.

## Prerequisites
1. Run `powershell -File doctor.ps1` to ensure all 18 checks are `[PASS]`.
2. Ensure Antigravity has `grepai-hybrid` loaded (configured via `~/.gemini/antigravity/mcp_config.json` and `~/.gemini/GEMINI.md`).

## Verification Scenarios

### Scenario 1: Conceptual Search in Indexed Repo (ash-rpg)
1. Open workspace `D:\Code\ash-rpg` in Antigravity.
2. Enter the unprompted query in chat:
   > *"Where is caller mutation authority and action receipt verification enforced in the server?"*
3. **Evaluation Criteria:**
   - [ ] Agent invokes `search_codebase` (or utilizes semantic retrieval) before running broad `Grep` or `find_by_name`.
   - [ ] Agent reads and inspects `src/server/app.ts` or `docs/plans/path_campaign_engineering.md`.
   - [ ] Agent does not claim file paths from workspaces mirrors or broken URLs.

### Scenario 2: Security Boundary Review (ORAC)
1. Open workspace `D:\Code\ORAC` in Antigravity.
2. Enter the unprompted query in chat:
   > *"How does the council sentinel intercept safety-critical path modifications?"*
3. **Evaluation Criteria:**
   - [ ] Agent invokes `search_codebase` for semantic exploration.
   - [ ] Results reference `src/orac/council.py` with valid absolute file paths.
   - [ ] No stale worktree paths (`.claude/worktrees`) appear in citations or answers.

### Scenario 3: Throwaway / Newly Opened Git Repository (Auto-Index Test)
1. Initialize a small throwaway git repository:
   ```powershell
   mkdir $env:TEMP\throwaway_repo; cd $env:TEMP\throwaway_repo; git init
   echo "function calculateTax() { return 0.15; }" > tax.js; git add tax.js; git commit -m "initial"
   ```
2. Open the throwaway repo in Antigravity.
3. Enter query:
   > *"Where is tax calculation handled in this project?"*
4. **Evaluation Criteria:**
   - [ ] Agent invokes `search_codebase`.
   - [ ] First response cleanly informs that auto-indexing has started (`~1 min for 1 files`).
   - [ ] After completion, subsequent queries return exact matches from `tax.js`.

## Recording Results
Record the conversation transcript IDs and tool invocations in `harness-results/antigravity_log.md`.
Target acceptance: $\ge 80\%$ tool-first semantic searches across 5 consecutive conceptual prompts.
