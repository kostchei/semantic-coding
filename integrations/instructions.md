<!-- grepai-hybrid:begin -->
## Semantic Code Search Policy (grepai-hybrid)
- For conceptual questions ("where is X implemented?", "how does Y work?"), call `search_codebase` BEFORE using Grep or Glob.
- Use `Grep` only for known exact identifier names, symbol definitions, or literal strings.
- Never silently work around search errors. If `search_codebase` reports that indexing is in progress or that a service is offline, surface that status immediately rather than guessing or falling back.
<!-- grepai-hybrid:end -->
