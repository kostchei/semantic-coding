# Security Review Finding: Review 1 (ORAC): Privilege Separation & Doer Grant Isolation

**Target Project:** `ORAC`
**Query Used:** `tool broker privilege separation per-agent allowlist write grant isolation`
**Retrieval Latency:** 305.9 ms
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

### Hit [2]: `.claude\worktrees\sad-gould-f315a4\docs\tool-broker-plan-review.md` (Lines 19-35)

- **RRF Score:** 0.2857 (Text Rank: 2, Code Rank: 2)

```
File: .claude\worktrees\sad-gould-f315a4\docs\tool-broker-plan-review.md

   The plan is a near-rewrite of the tool layer, not an extension — treat the broker as the
   new foundation, not an add-on.

2. **Tool selection is hardcoded, not agent-driven.** `agents.py::_apply_builtin_action`
   dispatches by agent slug; the `tools: [...]` arrays in `agents.json` are prompt
   decoration, not an enforced allow-list. Prerequisite for any broker: agents must emit
   structured capability requests, and *every* tool call (including the 18 existing ones)
   must route through the broker, or the 
```

### Hit [3]: `tests\test_builder.py` (Lines 34-72)

- **RRF Score:** 0.2167 (Text Rank: 4, Code Rank: 5)

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

### Hit [4]: `.claude\worktrees\sad-gould-f315a4\docs\edge-check-council-design.md` (Lines 234-263)

- **RRF Score:** 0.1875 (Text Rank: 3, Code Rank: None)

```
File: .claude\worktrees\sad-gould-f315a4\docs\edge-check-council-design.md

This is not a convention to be followed faithfully; **it is the grant boundary the broker
already enforces.** The Builder's allow-list contains the write capabilities; the council's and
orchestrator's do not. A council agent that emitted `write_code` would be `denied` at the broker
like any ungranted call — the same mechanism that denied Optimiser `handoff_tracker` before it
was granted. Separation of privilege costs nothing extra; it is one row in the `grants` table
per agent.

The flow for any change, includin
```

### Hit [5]: `.claude\worktrees\sad-gould-f315a4\src\orac\broker.py` (Lines 32-58)

- **RRF Score:** 0.1206 (Text Rank: 14, Code Rank: 7)

```
File: .claude\worktrees\sad-gould-f315a4\src\orac\broker.py

    :class:`CapabilityRequest`, the broker decides allowed / denied / pending /
    error, and only on ``allowed`` does it dispatch to a handler. Two backends
    sit behind it: :class:`RegularToolExecutor` (in-memory journaling) and the
    real adapters (e.g. ``fs_read``, the ``repo.*``/``git.*`` code tools).

    Grants come either from the ``agents.json`` manifest (in-memory, used by
    tests and the no-DB path) or from a :class:`BrokerStore`. When a store is
    attached, every decision is written to the durable audit lo
```

