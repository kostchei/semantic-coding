---
name: grepai-hybrid
description: Perform deep semantic code search across indexed projects combining 137M text embeddings (synonyms) and 7B code embeddings (algorithmic logic) via Reciprocal Rank Fusion.
---

# grepai-hybrid Semantic Search Skill

Use this skill whenever you need to find where functions, algorithms, security seams, or business concepts are implemented in the codebase.

## When to Call
- **Conceptual Intent**: Call `search_codebase` for queries like "caller privilege verification", "token bucket rate limiter", "retry backoff with jitter".
- **Before Grep**: Call `search_codebase` before broad file greps. Reserve `Grep` for exact symbol names.
- **Fail Loudly**: If the tool returns that the project is currently being indexed or that the embedding service is unreachable, report the message directly to the user.

## Tool Usage
Invoke the MCP tool `search_codebase`:
- `query`: Natural language or code intent.
- `project`: Optional project name. Auto-resolves from caller directory or client session roots.
- `limit`: Number of results (default: 5).
- `rerank`: Set `true` for Stage 2 local LLM cross-encoder re-ranking when strict precision is needed.
