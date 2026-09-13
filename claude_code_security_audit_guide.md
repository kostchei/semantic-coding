# AI-Assisted Security & Architectural Invariant Audit Guide: Claude Code + grepai-hybrid

> **Adapted specifically for `ash-rpg` (Distributed Tabletop Companion) and `ORAC` (Autonomous Agent Governance Spine).**

Claude Code and `grepai-hybrid` work together for continuous AI-assisted security and architectural code audits. Claude leverages the two-stage hybrid retrieval engine (137M text model for terminology/synonyms + 7B code model for AST and execution semantics fused via Reciprocal Rank Fusion) to pinpoint critical security seams, analyze execution traces, and generate auditable markdown reports under `findings/`.

---

## 1. Connect grepai / grepai-hybrid to Claude Code

Claude Code can be configured to use `grepai` and the multi-project `grepai-hybrid` engine in both target repositories.

### Terminal Setup

Execute in either repository root (`D:\Code\ash-rpg` or `D:\Code\ORAC`):

```bash
# 1. Ensure CLAUDE.md exists
touch CLAUDE.md

# 2. Configure Claude Code agent and subagent instructions
e:\Semantic_Coding\bin\grepai.exe agent-setup --with-subagent
```

This updates `CLAUDE.md` with instructions directing Claude Code to leverage semantic search instead of brute-force directory listings, and installs `.claude/agents/deep-explore.md` with grepai access.

### Global MCP Registration

Claude Code connects to the central multi-project hybrid server via `~/.claude.json`:

```json
{
  "mcpServers": {
    "grepai-hybrid": {
      "type": "stdio",
      "command": "python",
      "args": ["e:\\Semantic_Coding\\mcp_server.py"],
      "env": {}
    }
  }
}
```

When Claude Code launches in `D:\Code\ash-rpg` or `D:\Code\ORAC`, `mcp_server.py` auto-detects the working directory and queries that project's dual vector store in `E:\Semantic_Coding\workspaces\`.

---

## 2. Target 1: `ash-rpg` Security & Invariant Reviews

`ash-rpg` is a cooperative tabletop companion system (Express, Socket.IO, TypeScript, SQLite) where untrusted player phone browsers communicate with a host table.

### Review 1: Mutation Authority & Caller Verification

#### Prompt: Send to Claude Code in `D:\Code\ash-rpg`
```markdown
Review the client-to-server mutation authority and caller verification in this repository for security and privilege escalation issues.

Use grepai search and grepai trace to:
- Locate every socket action handler in `src/server/app.ts` and mutation contract in `src/shared/mutations.ts`.
- Trace the complete execution path of a shared action from client socket dispatch to server state commit.
- Identify how the host vs. caller vs. player identity is resolved and verified.

Check for:
- Missing caller authorization (`auth: "callerOrHost"` bypassed or missing on consequential actions)
- Forged player or character IDs in mutation payloads
- Replay vulnerabilities (missing or unvalidated `actionId` transactional receipts)
- State revision desync where concurrent player actions overwrite table state

For every finding, report the affected file, the execution path, the security impact, and a remediation diff.
Save the complete findings as Markdown to findings/ash-rpg-mutation-authority-review.md.
```

**Expected grepai usage:**
```bash
python e:\Semantic_Coding\hybrid_search.py "mutation authority caller privilege verification action receipt" --project ash-rpg
```
- **Discovered Seams:**
  - `src/server/app.ts` (`options: { auth?: "callerOrHost" | "none" }`)
  - `src/shared/mutations.ts` (`ACTIONS_REQUIRING_CALLER`, transactional receipts)
  - `docs/plans/path_campaign_engineering.md`

---

### Review 2: Information Fog of War & GM State Secret Leaks

#### Prompt: Send to Claude Code in `D:\Code\ash-rpg`
```markdown
Perform an information disclosure and Fog-of-War review of this repository.

Use grepai search and grepai trace to:
- Locate the public projection and state serialization logic in `src/server/` and `src/shared/slices.ts`.
- Trace how room features, secret doors, hidden traps, and monster stats are generated and filtered before broadcast.
- Verify whether connected player phone sockets receive unredacted campaign truth.

Check for:
- Secret room descriptions, hidden hazards, or undiscovered exits sent to client state prior to exploration
- Monster Armor Class (AC), maximum HP, or secret traits exposed before being tested in combat
- Future adventure path nodes, clues, or boss identities leaked in client network bundles
- Missing projection boundaries between Host (all-seeing) and Player (fog-of-war) views

Provide the complete data flow and execution path for every finding.
Save the complete findings as Markdown to findings/ash-rpg-fog-of-war-review.md.
```

**Expected grepai usage:**
```bash
python e:\Semantic_Coding\hybrid_search.py "information fog of war secret room monsters traps public projection" --project ash-rpg
```
- **Discovered Seams:**
  - `docs/plans/table_assistant_campaign_requirements.md` (Fog-of-war specifications)
  - `src/server/room-features.ts` (Entry room vs unexplored room feature generation)
  - `src/shared/slices.ts` (Slice diffing and projection models)

---

### Review 3: State Replay, Desync & Concurrency Invariants

#### Prompt: Send to Claude Code in `D:\Code\ash-rpg`
```markdown
Review this repository for database concurrency, replay vulnerabilities, and state desync bugs.

Use grepai search and grepai trace to:
- Locate the SQLite transaction boundaries and database storage routines in `src/server/database.ts`.
- Trace how concurrent character HP updates, inventory loot claims, and movement ticks are serialized.
- Inspect the test suite in `tests/multiplayer-mutations.test.ts` for concurrency assertions.

Check for:
- Race conditions when two players claim the same dungeon treasure item simultaneously
- Missing database transactions around multi-table mutations (e.g. character inventory + room state)
- Stale revision overwrites during concurrent HP healing/damage deltas
- Idempotency failure on replayed action receipts

Explain the complete execution path and failure conditions for every finding.
Save the complete findings as Markdown to findings/ash-rpg-concurrency-review.md.
```

**Expected grepai usage:**
```bash
python e:\Semantic_Coding\hybrid_search.py "transaction sqlite concurrency state revision race condition" --project ash-rpg
```
- **Discovered Seams:**
  - `src/server/database.ts` (`ON CONFLICT(campaign_id, slice_name) DO UPDATE SET revision = revision + 1`)
  - `tests/multiplayer-mutations.test.ts` (Replay call with identical `actionId`)
  - `docs/plans/product_quality_engineering_plan.md`

---

## 3. Target 2: `ORAC` Security & Governance Reviews

`ORAC` is an autonomous AI agent governance system (Python, FastAPI, SQLite) featuring a single-entry ToolBroker, Edge-Check Council, and risk throttling.

### Review 1: Privilege Separation & Doer Grant Isolation

#### Prompt: Send to Claude Code in `D:\Code\ORAC`
```markdown
Perform a privilege separation and grant isolation audit of the ORAC broker and council architecture.

Use grepai search and grepai trace to:
- Locate the ToolBroker dispatch gate and per-agent grant checks in `src/orac/broker.py`.
- Trace how agent roles are loaded from `src/orac/prompts/agents.json` and verified on every `_use()` call.
- Inspect `tests/test_builder.py` and `tests/test_broker.py` for grant enforcement tests.

Check for:
- Any reviewer, orchestrator, or council agent holding file-write or subprocess execution grants (the "one-writer" invariant requires only Builder to hold write grants)
- Bypasses of `broker._decide` or direct unbrokered adapter invocations
- Grant leakage or elevation through agent delegation or subtask spawning (`src/orac/subtasks.py`)
- Missing permission checks on new tool capabilities

Provide the complete execution path and assertion points for every finding.
Save the complete findings as Markdown to findings/orac-privilege-separation-review.md.
```

**Expected grepai usage:**
```bash
python e:\Semantic_Coding\hybrid_search.py "tool broker privilege separation per-agent allowlist write grant isolation" --project ORAC
```
- **Discovered Seams:**
  - `docs/tool-broker-plan-review.md` (One-writer invariant architecture)
  - `tests/test_builder.py` (Assertions verifying no reviewer holds write grants)
  - `docs/edge-check-council-design.md`

---

### Review 2: Safety-Critical Path Tampering & Sentinel Escapes

#### Prompt: Send to Claude Code in `D:\Code\ORAC`
```markdown
Review the Sentinel safety gate and council contract in this repository for tampering escapes and policy bypasses.

Use grepai search and grepai trace to:
- Locate the deterministic Sentinel lens in `src/orac/council.py` and path classification in `src/orac/policy.py`.
- Trace how file-write tool arguments (`repo.write_file`, `repo.edit_file`, `git.commit`) are evaluated against `policy.SAFETY_CRITICAL_PATHS`.
- Verify the aggregation in `council.py` to confirm that any Sentinel ESCALATE parks the task for human approval.

Check for:
- Path traversal escapes (`../`, symlinks, or alternate path casing) that bypass `safety_critical_paths_touched()`
- Tools capable of modifying code or configuration that are omitted from `LLM_REVIEWED_TOOLS` or `SAFETY_CRITICAL_PATHS`
- Pre-empting or overriding a Sentinel BLOCK/ESCALATE through subsequent lens verdicts
- Inability to fail closed when path normalization fails

Explain the complete validation path and risk implications for every finding.
Save the complete findings as Markdown to findings/orac-sentinel-safety-review.md.
```

**Expected grepai usage:**
```bash
python e:\Semantic_Coding\hybrid_search.py "sentinel lens safety critical paths write interception human approval" --project ORAC
```
- **Discovered Seams:**
  - `src/orac/council.py` (Sentinel lens escalation to human approval)
  - `docs/council-contract.md` (Veto-not-vote aggregation spec)
  - `src/orac/policy.py` (`SAFETY_CRITICAL_PATHS`)

---

### Review 3: Destructive Boundary Violations & Compensating Actions

#### Prompt: Send to Claude Code in `D:\Code\ORAC`
```markdown
Review the physical, media, and external action adapters for boundary safety and rollback enforcement.

Use grepai search and grepai trace to:
- Locate the compensating actions specification in `docs/compensating-actions.md` and tool risk classifications in `src/orac/policy.py`.
- Trace the execution pipeline for physical device control in `src/orac/physical_adapters.py` and `src/orac/physical_store.py`.
- Inspect the emergency stop mechanism (`physical.emergency_stop`) and cooldown enforcement.

Check for:
- Physical or financial tools executing without `APPROVE` risk classification (ask-before requirement)
- Missing inverse actions or missing rollback contracts on side-effecting operations
- Cooldown bypasses during rapid sequential tool dispatch
- Failure of `emergency_stop` to halt in-flight physical commands immediately

Provide the execution path and safety contract evaluation for every finding.
Save the complete findings as Markdown to findings/orac-compensating-actions-review.md.
```

**Expected grepai usage:**
```bash
python e:\Semantic_Coding\hybrid_search.py "compensating actions physical emergency stop uninvertible tool drift" --project ORAC
```
- **Discovered Seams:**
  - `src/orac/prompts/operator.md` (Operator role, 3-call contract, cooldowns)
  - `docs/compensating-actions.md` (Approval-first posture for non-git tools)
  - `docs/physical-plan.md` (Device allowlists and emergency stop)

---

## 4. Daily Audit & Review Loop

### Session Workflow

1. **Keep Indices Fresh in Background:**
   ```powershell
   # From E:\Semantic_Coding
   .\index_project.ps1 -ProjectPath D:\Code\ash-rpg
   .\index_project.ps1 -ProjectPath D:\Code\ORAC
   ```

2. **Automated Audit Suite Run:**
   Execute the automated 6-point verification suite anytime to confirm index retrieval health:
   ```powershell
   python e:\Semantic_Coding\run_security_audit.py
   ```
   Outputs summary metrics and writes fresh audit logs to `findings/`.

3. **Open Claude Code in Target Repository:**
   ```powershell
   cd D:\Code\ash-rpg
   claude
   ```
   Dispatch any of the adapted prompts above. Claude Code queries `grepai-hybrid` via MCP to retrieve bounded, semantic context instead of scanning arbitrary files.

4. **Verify Findings in Source:**
   Confirm every finding by reading the source code directly at the returned line ranges before marking as verified.
