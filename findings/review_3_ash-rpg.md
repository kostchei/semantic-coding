# Security Review Finding: Review 3 (ash-rpg): State Replay, Desync & Concurrency Invariants

**Target Project:** `ash-rpg`
**Query Used:** `transaction sqlite concurrency state revision race condition`
**Retrieval Latency:** 309.3 ms
**Description:** Verifies atomic database transactions, state revision increments, and replay rejection on identical actionId.

## Discovered Architectural & Security Seams

### Hit [1]: `docs\plans\product_quality_engineering_plan.md` (Lines 220-236)

- **RRF Score:** 0.2778 (Text Rank: 1, Code Rank: 13)

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

### Hit [3]: `docs\table_companion.md` (Lines 93-99)

- **RRF Score:** 0.2143 (Text Rank: 2, Code Rank: None)

```
File: docs\table_companion.md

The React/Vite client provides responsive host and phone surfaces. Express serves the API and production client, while Socket.IO is the sole live mutation channel. The server validates every action, performs every random roll, writes the resulting campaign state and audit record to SQLite, and then broadcasts a role-aware snapshot.

Device tokens reconnect phones to their character and remain in browser storage. They are not campaign data. Host authorization uses a random server token recovered with the campaign PIN; the PIN itself is stored only as a salted sc
```

### Hit [4]: `tests\multiplayer-mutations.test.ts` (Lines 217-235)

- **RRF Score:** 0.1709 (Text Rank: 8, Code Rank: 4)

```
File: tests\multiplayer-mutations.test.ts

    // Replay call with same actionId
    const res2 = db.executeMutation(campaignId, hostToken, "act-replay-test", undefined, mutate);
    expect(res2.result.count).toBe(1);
    expect(executionCount).toBe(1); // Not executed again!
  });

  it("preserves action receipts across database restart", () => {
    const { campaignId, hostToken } = db.createCampaign("Restart", "Borderlands", "1234", {
      selection: { mode: "single", zoneId: "the_gloaming" }, legacy: true,
    });
    const first = db.executeMutation(campaignId, hostToken, "persisted-acti
```

### Hit [5]: `docs\oracles\10_connected_path_encounters.md` (Lines 35-40)

- **RRF Score:** 0.1667 (Text Rank: 4, Code Rank: None)

```
File: docs\oracles\10_connected_path_encounters.md

The [engine](https://github.com/kostchei/ash-rpg/blob/main/src/server/paths/encounters/engine.ts) maintains separate known and visited sites, clue provenance, facts, completed actions, resolved groups, materials, accepted/released benefit history, work minutes, victories, Toll, and a journal. These records support the different authored mechanics; they are not a generic Doom track.

The [service](https://github.com/kostchei/ash-rpg/blob/main/src/server/paths/encounters/service.ts) stores definitions and state in SQLite's `path_encounter_pac
```

