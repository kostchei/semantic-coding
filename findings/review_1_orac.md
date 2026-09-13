# Security Review Finding: Review 1 (ORAC): Privilege Separation & Doer Grant Isolation

**Target Project:** `ORAC`
**Query Used:** `tool broker privilege separation per-agent allowlist write grant isolation`
**Retrieval Latency:** 201.6 ms
**Description:** Verifies that reviewer and orchestrator agents hold zero write grants and that ToolBroker strictly enforces allowlists.

## Discovered Architectural & Security Seams

### Hit [1]: `docs\tool-broker-plan-review.md` (Lines 19-35)

- **RRF Score:** 0.3333 (Text Rank: 1, Code Rank: 1)

```
File: docs\tool-broker-plan-review.md

   The plan is a near-rewrite of the tool layer, not an extension — treat the broker as the
   new foundation, not an add-on.

2. **Tool selection is hardcoded, not agent-driven.** `agents.py::_apply_builtin_action`
   dispatches by agent slug; the `tools: [...]` arrays in `agents.json` are prompt
   decoration, not an enforced allow-list. Prerequisite for any broker: agents must emit
   structured capability requests, and *every* tool call (including the 18 existing ones)
   must route through the broker, or the guarantee leaks through the old path.

3. 
```

### Hit [2]: `docs\tool-broker-plan-review.md` (Lines 60-80)

- **RRF Score:** 0.2500 (Text Rank: 3, Code Rank: 3)

```
File: docs\tool-broker-plan-review.md

   UI calls the engine; the engine owns grants and the pending-approval queue.

9. **Agent→capability mapping is half-right.** Optimiser→scheduling and Efficiency→grant-GC
   are clean fits. Don't make Intent the permission broker — goal ambiguity ("what does
   done mean?") is a different question from the permission ask ("may I post to #general?"),
   which belongs to the Permission Engine + approval UI.

10. **Omissions that will bite:** `storage.py` is a 48-line flat JSON board; grants, audit,
    pending-approvals, and per-day rate counters are state
```

### Hit [3]: `tests\test_builder.py` (Lines 34-72)

- **RRF Score:** 0.2143 (Text Rank: 2, Code Rank: None)

```
File: tests\test_builder.py

    return BrokerStore(path).init()


# --- privilege separation (design §4.6) ---------------------------------------


def test_only_builder_holds_write_grants() -> None:
    broker = ToolBroker.from_manifests()

    assert WRITE_TOOLS <= broker.grants["Builder"]
    for reviewer in ("Intent", "Optimiser", "Simples", "Efficiency", "Orchestrator"):
        assert not (WRITE_TOOLS & broker.grants.get(reviewer, frozenset())), (
            f"{reviewer} must not hold any write grant"
        )


def test_reviewer_write_is_denied_at_the_broker(tmp_path
```

### Hit [4]: `docs\edge-check-council-design.md` (Lines 228-247)

- **RRF Score:** 0.1750 (Text Rank: 7, Code Rank: 5)

```
File: docs\edge-check-council-design.md

- A dedicated **Builder** subagent is the *sole* holder of mutating code grants
  (`write_code`, `git_commit`, file writes). It does not plan, judge, or approve — it builds.
- The **Orchestrator** plans and spawns; the **Council** (Intent/Optimise/Simple/Efficiency)
  plans, documents, discusses, persuades, and **approves or rejects**. None of them hold a
  write grant. They can shape *what* gets built and veto it — they cannot put hands on the code.

This is not a convention to be followed faithfully; **it is the grant boundary the broker
already enfor
```

### Hit [5]: `docs\tool-broker-plan-review.md` (Lines 75-93)

- **RRF Score:** 0.1667 (Text Rank: 4, Code Rank: None)

```
File: docs\tool-broker-plan-review.md

## Reordered build plan (checklist)

Principle: make it real once, then make it general.

- [ ] Define the agent-facing capability request + result contract
      (`allowed | denied | pending | error`).
- [ ] Make agents emit structured tool-call intents instead of hardcoded dispatch.
- [ ] Build a minimal broker and migrate the 18 existing journaling tools through it
      (zero external risk; validates the interface).
- [ ] Move state to SQLite (grants, audit, pending-approvals, rate counters).
- [ ] Add a durable `pending_approval` task state + timeout
```

