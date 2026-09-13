---
name: grepai-hybrid
description: Perform deep semantic code search across the codebase using the two-stage hybrid retrieval engine combining 137M text embeddings (synonyms), 7B code embeddings (algorithmic logic), and local LLM re-ranking.
---

# grepai-hybrid Skill

Use this skill when you need to find where functions, algorithms, data structures, or business concepts are implemented in the codebase.

## Quick CLI Execution
Run the hybrid search command using `run_command`:

```powershell
# Search default project or auto-detect from current directory
python e:\Semantic_Coding\hybrid_search.py "<query>" -n 5

# Explicitly search any registered project (e.g. praetor_silica, LDGM)
python e:\Semantic_Coding\hybrid_search.py "<query>" --project praetor_silica -n 5
python e:\Semantic_Coding\hybrid_search.py "<query>" --project LDGM -n 5
```

### With Stage 2 Local Re-Ranking (High Precision)
To eliminate unit test mocks and distractor files, add `--rerank`:

```powershell
python e:\Semantic_Coding\hybrid_search.py "<query>" --rerank -n 3
```

### Structured JSON Output
For programmatic consumption:

```powershell
python e:\Semantic_Coding\hybrid_search.py "<query>" -j -n 5
```

### Active Feedback / Triplet Mining
When you confirm a target file is the right answer, pass `--feedback-selected` to log contrastive training data:

```powershell
python e:\Semantic_Coding\hybrid_search.py "<query>" --feedback-selected "<target_file_path>" -n 3
```
