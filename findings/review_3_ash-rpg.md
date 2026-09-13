# Security Review Finding: Review 3 (ash-rpg): State Replay, Desync & Concurrency Invariants

**Target Project:** `ash-rpg`
**Query Used:** `transaction sqlite concurrency state revision race condition`
**Retrieval Latency:** 313.0 ms
**Description:** Verifies atomic database transactions, state revision increments, and replay rejection on identical actionId.

## Discovered Architectural & Security Seams

### Hit [1]: `docs\plans\product_quality_engineering_plan.md` (Lines 220-236)

- **RRF Score:** 0.2750 (Text Rank: 1, Code Rank: 15)

```
File: docs\plans\product_quality_engineering_plan.md

4. **Host restart.** SQLite is the source of truth; a host process restart must restore the table with no player action beyond automatic reconnection. Covered by a test that stops and restarts the server mid-session.

### G. Guardrails that must not regress

These are the product's integrity promises and each already has tests. Every workstream above must leave them green **without editing the test**:

* No roll-to-hit or damage automation anywhere in the UI.
* Player projections omit unrevealed hex names, biomes, threat tiers, landm
```

### Hit [2]: `src\server\database.ts` (Lines 1564-1598)

- **RRF Score:** 0.2333 (Text Rank: 5, Code Rank: 1)

```
File: src\server\database.ts

      ON CONFLICT(campaign_id, slice_name) DO UPDATE SET revision = revision + 1
    `);
    for (const name of sliceNames) {
      upsert.run(campaignId, name);
    }
    return this.getSliceRevisions(campaignId);
  }

  executeMutation<T>(
    campaignId: number,
    actorToken: string,
    actionId: string,
    expectedRevision: number | undefined,
    mutate: () => T,
  ): { result: T; revision: number } {
    return this.db.transaction(() => {
      // 1. Idempotency receipt check
      const existingReceipt = this.db
        .prepare(
          "SELECT resul
```

### Hit [3]: `docs\plans\product_quality_engineering_plan.md` (Lines 211-221)

- **RRF Score:** 0.2153 (Text Rank: 3, Code Rank: 13)

```
File: docs\plans\product_quality_engineering_plan.md

5. **Scroll containment.** Every independently scrolling region gets `overscroll-behavior: contain` so a flick inside the initiative list never rubber-bands the page behind it.

### F. Session continuity

A table session runs for hours across screen locks, Wi-Fi handoffs, and a phone in a pocket. Requirements:

1. **Resume, never reload.** On reconnect the client sends its last known per-slice revisions; the server replies with the slices that moved. A full snapshot is sent only when the gap is too large to patch.
2. **Honest connect
```

### Hit [4]: `docs\table_companion.md` (Lines 93-99)

- **RRF Score:** 0.2143 (Text Rank: 2, Code Rank: None)

```
File: docs\table_companion.md

The React/Vite client provides responsive host and phone surfaces. Express serves the API and production client, while Socket.IO is the sole live mutation channel. The server validates every action, performs every random roll, writes the resulting campaign state and audit record to SQLite, and then broadcasts a role-aware snapshot.

Device tokens reconnect phones to their character and remain in browser storage. They are not campaign data. Host authorization uses a random server token recovered with the campaign PIN; the PIN itself is stored only as a salted sc
```

### Hit [5]: `src\server\database.ts` (Lines 1591-1626)

- **RRF Score:** 0.1875 (Text Rank: 7, Code Rank: 3)

```
File: src\server\database.ts

        return {
          result: JSON.parse(existingReceipt.result_json) as T,
          revision: campaignRow?.revision ?? 1,
        };
      }

      // 2. Revision check
      const campaignRow = this.db
        .prepare("SELECT revision FROM campaigns WHERE id = ?")
        .get(campaignId) as { revision: number } | undefined;
      const currentRevision = campaignRow?.revision ?? 1;

      if (expectedRevision !== undefined && expectedRevision !== currentRevision) {
        throw new Error(
          `State revision conflict: expected revision ${expectedRe
```

