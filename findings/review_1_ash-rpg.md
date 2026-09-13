# Security Review Finding: Review 1 (ash-rpg): Mutation Authority & Caller Verification

**Target Project:** `ash-rpg`
**Query Used:** `mutation authority caller privilege verification action receipt`
**Retrieval Latency:** 317.7 ms
**Description:** Verifies that player socket connections cannot forge caller mutations or bypass action receipt idempotency locks.

## Discovered Architectural & Security Seams

### Hit [1]: `docs\plans\path_campaign_engineering.md` (Lines 94-103)

- **RRF Score:** 0.2500 (Text Rank: 1, Code Rank: None)

```
File: docs\plans\path_campaign_engineering.md

6. Site outcomes execute adapter effects and +1 story awards once when qualifying conditions resolve. An act transition similarly records +3 once and reveals earned travel information. The same transaction records receipt, source state, events, and path effects before broadcasting.

Expose operations through existing socket conventions with `actionId` and expected revision. Add `combat:end`, source discovery/secure, privileged treasure corrections, and level-up/choice resolution to the mutation receipt contract where missing. `treasure:generate` b
```

### Hit [2]: `src\server\app.ts` (Lines 675-701)

- **RRF Score:** 0.2500 (Text Rank: 4, Code Rank: 1)

```
File: src\server\app.ts

      options: { auth?: "callerOrHost" | "none" } = {},
    ) => action((raw: unknown) => {
      if (options.auth !== "none") {
        callerOrHostOnly();
      }
      if (!RECEIPTED_ACTIONS.has(event)) throw new Error("Unknown mutation action");
      const envelope = z.object({
        actionId: z.string().min(1).max(160),
        expectedRevision: z.number().int().nonnegative(),
      }).parse(raw);
      const payloadKey = mutationPayloadKey(raw as Record<string, unknown>);
      const receipt = db.executeMutation(
        identity.campaignId, identity.token, `$
```

### Hit [3]: `docs\table_companion.md` (Lines 93-99)

- **RRF Score:** 0.2143 (Text Rank: 2, Code Rank: None)

```
File: docs\table_companion.md

The React/Vite client provides responsive host and phone surfaces. Express serves the API and production client, while Socket.IO is the sole live mutation channel. The server validates every action, performs every random roll, writes the resulting campaign state and audit record to SQLite, and then broadcasts a role-aware snapshot.

Device tokens reconnect phones to their character and remain in browser storage. They are not campaign data. Host authorization uses a random server token recovered with the campaign PIN; the PIN itself is stored only as a salted sc
```

### Hit [4]: `src\shared\mutations.ts` (Lines 1-33)

- **RRF Score:** 0.1875 (Text Rank: 3, Code Rank: None)

```
File: src\shared\mutations.ts

/** Actions migrated to transactional receipts. Keep client and server in sync. */
export const RECEIPTED_ACTIONS = new Set([
  "path_encounters:start",
  "path_encounters:arrive",
  "path_encounters:interact",
  "travel:move",
  "dungeon:claim_treasure",
  "dungeon:record_outcome",
  "dungeon:recruit_rescued",
  "dungeon:light_torch",
  "session:award_xp",
  "session:return_sanctuary",
  "party:rest",
  "expedition:camp",
  "expedition:camp_night",
  "site:enter",
  "dungeon:move_room",
  "treasure:allocate",
  "combat:update_hp",
  "combat:de
```

### Hit [5]: `docs\oracles\10_connected_path_encounters.md` (Lines 49-55)

- **RRF Score:** 0.1500 (Text Rank: 5, Code Rank: None)

```
File: docs\oracles\10_connected_path_encounters.md

Future integration should bind each site to persistent regional coordinates, feed its sources into the existing tavern leads, send groups directly into combat, and apply inventory/time/character effects through the existing authoritative services. Full campaign adapters must additionally supply their level 1–10 content and XP audits. Those capabilities are not implied by the encounter packs being selectable.

## Verification

[Content and persistence tests](https://github.com/kostchei/ash-rpg/blob/main/tests/path-encounters.test.ts) exerc
```

