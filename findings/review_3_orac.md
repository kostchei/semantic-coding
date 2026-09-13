# Security Review Finding: Review 3 (ORAC): Destructive Boundary Violations & Compensating Actions

**Target Project:** `ORAC`
**Query Used:** `compensating actions physical emergency stop uninvertible tool drift`
**Retrieval Latency:** 209.7 ms
**Description:** Verifies that uninvertible physical and external actions require approval-first gating, cooldowns, and emergency stop.

## Discovered Architectural & Security Seams

### Hit [1]: `src\orac\prompts\operator.md` (Lines 8-10)

- **RRF Score:** 0.2917 (Text Rank: 1, Code Rank: 7)

```
File: src\orac\prompts\operator.md

- Approval and Cooldowns: Physical execution (`physical.execute_action`) is approval-gated by default and requires human approval or an active standing grant. Respect per-device cooldown periods.
- Emergency Stop: Use `physical.emergency_stop` when a halt is needed. Emergency stops run automatically without approval delays and can target specific devices or all devices globally.
- Reversibility and Rollback: Compensating actions are generated only when the device explicitly supports a defined inverse; never guess an inverse.
```

### Hit [2]: `docs\physical-plan.md` (Lines 62-78)

- **RRF Score:** 0.2527 (Text Rank: 2, Code Rank: 8)

```
File: docs\physical-plan.md

  `execute_action` both check and reject inside the cooldown window.
- **E-stop is a distinct tool, not a rollback.** `physical.emergency_stop` is its own
  adapter method, always available to Operator, bypasses the prepare/execute pairing,
  and is classified `(Reversibility.REVERSIBLE, Externality.LOCAL)` → AUTO (a safety
  brake must never itself be gated behind approval).
- **Risk classification** in `_ADAPTER_RISK` (`policy.py:48-108`, new "Physical (Group 4)"
  block):
  - `physical.list_entities`, `physical.read_state` → `(REVERSIBLE, LOCAL)` → AUTO
    (rea
```

### Hit [3]: `docs\compensating-actions.md` (Lines 29-48)

- **RRF Score:** 0.2381 (Text Rank: 4, Code Rank: 2)

```
File: docs\compensating-actions.md

2. The compensation tool is registered, risk-classified, and allow-listed for
   the human principal; notification data cannot introduce an arbitrary tool.
3. Required identity and pre-state fields are present and schema-valid.
4. `expected_state` still matches. Drift fails closed and asks for manual
   reconciliation instead of applying a stale inverse.
5. The contract has not expired. A missing expiry means the adapter asserts the
   inverse remains meaningful indefinitely.
6. The compensation request passes the normal risk throttle. A physical,
   financi
```

### Hit [4]: `src\orac\tools\catalog.json` (Lines 360-370)

- **RRF Score:** 0.1919 (Text Rank: 6, Code Rank: 4)

```
File: src\orac\tools\catalog.json

      "regular_use": "Operator executes an approved physical action; enforces 3-call contract and attaches compensation contracts.",
      "inputs": ["task_id", "action_id"]
    },
    {
      "name": "physical.emergency_stop",
      "description": "Immediately trigger emergency stop/off state for a specific device or all allowlisted physical devices. Auto-run safety brake.",
      "regular_use": "Operator halts physical actuator operations immediately without approval delay.",
      "inputs": ["task_id", "device_id"]
    }
  ]
}
```

### Hit [5]: `docs\compensating-actions.md` (Lines 1-31)

- **RRF Score:** 0.1875 (Text Rank: 3, Code Rank: None)

```
File: docs\compensating-actions.md

# Compensating Actions

ORAC's `rollback` command must describe an honest inverse, not merely a second
action that might make the situation look similar. Git has a strong inverse:
`git.revert` records a new commit that undoes a known commit. Other tools need
an explicit compensation contract before they can use review-after.

## Contract carried by a completed action

A mutating adapter that can be compensated returns this object in its result
data, which is then preserved verbatim in the durable notification:

```json
{
  "rollback_contract": {
    "version
```

