# Security Review Finding: Review 2 (ash-rpg): Information Fog-of-War & State Secret Leaks

**Target Project:** `ash-rpg`
**Query Used:** `information fog of war secret room monsters traps public projection`
**Retrieval Latency:** 324.1 ms
**Description:** Verifies that room features, trap triggers, and hidden monster statistics are stripped before public projection broadcasts.

## Discovered Architectural & Security Seams

### Hit [1]: `docs\plans\table_assistant_campaign_requirements.md` (Lines 234-241)

- **RRF Score:** 0.2597 (Text Rank: 2, Code Rank: 6)

```
File: docs\plans\table_assistant_campaign_requirements.md

Verified in a browser against a running server: zoom slider to 400% with the centre held, drag-pan on both maps, and clicks still selecting a hex and a room after panning.

### Fog of war: what persists and what is current

**Owner requirement recorded 2026-09-06: when fog of war lifts, landmarks remain; sites, monsters, and NPCs may change.** Terrain, biome, elevation, landmark, roads, and rivers are permanent world truth, saved on the hex and shown from the moment the party charts it. Occupancy is not.

The hex row previously carried
```

### Hit [2]: `docs\oracles\09_outer_power_player_mechanics.md` (Lines 62-67)

- **RRF Score:** 0.2500 (Text Rank: 1, Code Rank: None)

```
File: docs\oracles\09_outer_power_player_mechanics.md

For example, rescuing a companion in exchange for a public accusation can both save that person and empower a patron to seize a suspect's office. Forged evidence has provenance and discoverable contradictions. The party can decline, negotiate narrower terms, seek independent rescue, or later revoke an endorsement through the issuer's actual procedure.

**Monster jobs.** Nightgaunts abduct witnesses; flying polyps isolate people or conceal a withdrawal; hunting horrors intercept couriers and escort the prize. Track captured people and paper
```

### Hit [3]: `zones\city_of_masks\lore.md` (Lines 28-29)

- **RRF Score:** 0.1875 (Text Rank: 3, Code Rank: None)

```
File: zones\city_of_masks\lore.md

3. **The Mask Plague and Conspiracy**: A virulent contagion led the nobility to mandate decorative persona masks, which soon hid rampant political murder.
4. **Duelists in the Shadows**: The Shroud, the Bardic College, and the Duke's Guard clash in clandestine street warfare.
```

### Hit [4]: `src\server\room-features.ts` (Lines 36-47)

- **RRF Score:** 0.1813 (Text Rank: 5, Code Rank: 11)

```
File: src\server\room-features.ts

    room.title = room.id === graph.entryRoomId ? "Site entrance" : `Area ${room.id}`;
    room.contents = {
      empty: "No immediate encounter. Describe the traces of this site's history at the table.",
      trap: "An engineered danger protects this area. Investigate how it is triggered before proceeding.",
      minor_hazard: "A local obstacle threatens a delay or a limited resource loss. Establish its nature at the table.",
      solo_monster: "A lone creature occupies this area. Determine its activity and reaction.",
      npc: "Someone is here with the
```

### Hit [5]: `docs\adventure_paths\01_domains_of_dread.md` (Lines 197-223)

- **RRF Score:** 0.1667 (Text Rank: 4, Code Rank: None)

```
File: docs\adventure_paths\01_domains_of_dread.md

A reading counts as one clue source, never as complete proof. Ignoring or distrusting the Seer does not block the campaign because every truth has other sources.

---

## Clues Without a Dungeon Master

### The Three-Source Rule

For every conclusion the party must reach, the boss dossier supplies three independent clue expressions:

1. **Witness:** A survivor, spirit, minion, lieutenant, victim, or inherited memory
2. **Record:** A journal, legal document, portrait, song, grave, experiment, map, or card reading
3. **Place or Object:** A ruin,
```

