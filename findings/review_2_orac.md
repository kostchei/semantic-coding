# Security Review Finding: Review 2 (ORAC): Safety-Critical Path Tampering & Sentinel Escapes

**Target Project:** `ORAC`
**Query Used:** `sentinel lens safety critical paths write interception human approval`
**Retrieval Latency:** 217.4 ms
**Description:** Verifies that modifications to governance files in policy.SAFETY_CRITICAL_PATHS fail closed and escalate to human approval.

## Discovered Architectural & Security Seams

### Hit [1]: `src\orac\council.py` (Lines 161-176)

- **RRF Score:** 0.3333 (Text Rank: 1, Code Rank: 1)

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

### Hit [2]: `src\orac\council.py` (Lines 172-176)

- **RRF Score:** 0.2857 (Text Rank: 2, Code Rank: 2)

```
File: src\orac\council.py

                "seed needs human approval regardless of reversibility.",
            )
        return LensVerdict(
            lens="Sentinel", decision=LensDecision.PASS, reason="no safety-critical path"
        )
```

### Hit [3]: `docs\verifier-watch-design.md` (Lines 11-25)

- **RRF Score:** 0.1875 (Text Rank: 3, Code Rank: None)

```
File: docs\verifier-watch-design.md

However, as ORAC moves toward unattended daemon runs, a critical operational failure mode emerges: **fatigued or rushed human operator review**. An operator clearing a large backlog of `notify` and `escalate` items in a single sitting late at night may approve risky actions or miss important notifications.

In external frameworks (such as `ai-literacy-superpowers`), such monitoring was categorized under a "sentinel" concept. In ORAC, **Sentinel** is already the safety-critical-file escalation lens in `src/orac/council.py`. To eliminate ambiguity and prevent
```

### Hit [4]: `docs\council-contract.md` (Lines 139-143)

- **RRF Score:** 0.1857 (Text Rank: 5, Code Rank: 9)

```
File: docs\council-contract.md

| `LLM_REVIEWED_TOOLS` | write/edit/commit/push/revert | Edges the cognition layer reasons over. |
| `SAFETY_CRITICAL_PATHS` | governor + grant-seed files | What Sentinel guards. |

Defaults are generous on purpose: brakes against runaway loops, not friction for
normal work.
```

### Hit [5]: `docs\council-contract.md` (Lines 138-143)

- **RRF Score:** 0.1667 (Text Rank: 4, Code Rank: None)

```
File: docs\council-contract.md

| `DUPLICATE_CHECKED_TOOLS` | `{repo.write_file}` | Tools whose exact repetition Efficiency blocks. |
| `LLM_REVIEWED_TOOLS` | write/edit/commit/push/revert | Edges the cognition layer reasons over. |
| `SAFETY_CRITICAL_PATHS` | governor + grant-seed files | What Sentinel guards. |

Defaults are generous on purpose: brakes against runaway loops, not friction for
normal work.
```

