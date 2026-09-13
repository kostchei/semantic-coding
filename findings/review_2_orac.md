# Security Review Finding: Review 2 (ORAC): Safety-Critical Path Tampering & Sentinel Escapes

**Target Project:** `ORAC`
**Query Used:** `sentinel lens safety critical paths write interception human approval`
**Retrieval Latency:** 293.2 ms
**Description:** Verifies that modifications to governance files in policy.SAFETY_CRITICAL_PATHS fail closed and escalate to human approval.

## Discovered Architectural & Security Seams

### Hit [1]: `.claude\worktrees\sad-gould-f315a4\src\orac\council.py` (Lines 172-176)

- **RRF Score:** 0.3333 (Text Rank: 1, Code Rank: 1)

```
File: .claude\worktrees\sad-gould-f315a4\src\orac\council.py

                "seed needs human approval regardless of reversibility.",
            )
        return LensVerdict(
            lens="Sentinel", decision=LensDecision.PASS, reason="no safety-critical path"
        )
```

### Hit [2]: `src\orac\council.py` (Lines 161-176)

- **RRF Score:** 0.2857 (Text Rank: 2, Code Rank: 2)

```
File: src\orac\council.py

        human approves the exact request, the durable approval clears it (the
        broker's ``_check_approval`` short-circuits the re-issued call), so the
        guard escalates without trapping the work forever.
        """
        touched = safety_critical_paths_touched(ctx.request.tool, ctx.request.args)
        if touched:
            return LensVerdict(
                lens="Sentinel",
                decision=LensDecision.ESCALATE,
                reason=f"Sentinel: {ctx.request.tool} would modify safety-critical "
                f"file(s) {touched}; self-
```

### Hit [3]: `.claude\worktrees\sad-gould-f315a4\docs\council-contract.md` (Lines 17-37)

- **RRF Score:** 0.1513 (Text Rank: 7, Code Rank: 14)

```
File: .claude\worktrees\sad-gould-f315a4\docs\council-contract.md

any `escalate` parks it for a human; else it passes** to the risk model, which
decides whether the (allowed) call runs silently, runs-and-notifies, or waits for
approval. The guiding principle is **review-after, not ask-before**: code work is
not blocked waiting for a human — it runs and lands in a review queue with a
one-step rollback — and `approve` is reserved for the genuinely irreversible.

## 2. Verdict vocabulary

Each lens returns a `LensVerdict` with one decision:

| Verdict | Meaning | Council effect |
| --
```

### Hit [4]: `docs\verifier-watch-design.md` (Lines 11-25)

- **RRF Score:** 0.1500 (Text Rank: 5, Code Rank: None)

```
File: docs\verifier-watch-design.md

However, as ORAC moves toward unattended daemon runs, a critical operational failure mode emerges: **fatigued or rushed human operator review**. An operator clearing a large backlog of `notify` and `escalate` items in a single sitting late at night may approve risky actions or miss important notifications.

In external frameworks (such as `ai-literacy-superpowers`), such monitoring was categorized under a "sentinel" concept. In ORAC, **Sentinel** is already the safety-critical-file escalation lens in `src/orac/council.py`. To eliminate ambiguity and prevent
```

### Hit [5]: `.claude\worktrees\sad-gould-f315a4\docs\roadmap.md` (Lines 90-104)

- **RRF Score:** 0.1364 (Text Rank: 6, Code Rank: None)

```
File: .claude\worktrees\sad-gould-f315a4\docs\roadmap.md

breadth still holds: every item below hardens or completes the governance spine; no new surface
category starts until item 4 has produced real evidence.

1. ~~**Safety-critical-file gate (design §8.7).**~~ **Done.** `policy.SAFETY_CRITICAL_PATHS` +
   `safety_critical_paths_touched(tool, args)` classify a write/commit touching the files that
   enforce the safety model (`broker.py`, `broker_store.py`, `policy.py`, `council.py`,
   `lenses.py`, `scrum.py`, `daemon.py`, `agent_session.py`, and the grant seed
   `prompts/agents.json
```

