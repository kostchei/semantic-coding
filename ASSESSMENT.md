# Repository assessment

Reviewed 2026-09-13. This is a useful retrieval prototype with benchmark fixtures, a small MCP adapter, and local indexing scripts. It is not yet a validated self-improving production pipeline.

## Confirmed and addressed

- Claude: the historical report records the expired OAuth error; the installed CLI currently reports `loggedIn: false`. Print mode does not categorically require an API key. The new `run_agent_harness.ps1` checks authentication before running and explains login/setup-token recovery without storing credentials.
- Codex: `codex mcp get grepai_hybrid --json` confirms the enabled server. The historical report records shell-first exploration. Registration exposes tools; it does not mandate their use. The new harness explicitly supplies the MCP server and project, requests hybrid retrieval before exploration, and rejects runs without recorded MCP usage. This is an instructed retrieval experiment, distinct from measuring unprompted tool adoption.
- Retrieval errors and timeouts now surface as failures instead of empty matches. Unknown explicit projects fail instead of silently falling back. Path matching observes directory boundaries and prefers nested projects; explicit index pairs take precedence.
- MCP documentation now states that omitted project selection uses the **server** working directory. MCP does not implicitly receive the client working directory. Requests above ten results are no longer silently capped at ten (supported range 1–15).
- Fusion ties have a deterministic order. Hybrid benchmark metrics respect the requested result limit. Dry-run reports no longer replace computed metrics with fabricated high scores.
- Telemetry defaults resolve beside the collector rather than writing into whichever project launched the process. The server dependency list no longer unnecessarily includes torch/numpy.

## Remaining limitations

- Indexing and synchronization need a separate lifecycle repair: index-size stability is not proof of completed ingestion; forced process termination and lock deletion are fragile. The synchronizer misses deletion-only changes and its `-Once` path does not mirror source changes. Avoid treating its success text as proof of freshness.
- Tuning and evaluation reuse the same small curated cases. Reported tuned results are in-sample, not evidence of generalization. Hybrid ranking logic is duplicated in the tuner/benchmark and runtime.
- Neural training writes a checkpoint that the live LLM reranker never loads. Small-data training silently substitutes synthetic triplets. The advertised training feedback loop is not connected end to end.
- Security audit queries check whether expected files appear; they do not verify the security invariants stated in their descriptions.
- The original CLI traces are summarized in report.md, not preserved as raw events. Historical behavior is corroborated by that report, not independently reproduced here.

## Validation

Run `python -m unittest discover -s tests -v` for backend failures, timeout handling, project boundaries, deterministic fusion, and benchmark truncation. Run `python benchmarks/benchmark.py --dry-run --hybrid` for a smoke check. Harness scripts can be syntax checked without credentials; a successful live agent run still requires valid authentication and live embedding/index services.

Validation completed: six Python regression tests, six structured-event harness checks (`.\tests\test_harness.ps1`), benchmark dry-run, Python compilation, and PowerShell parsing passed. An actual MCP stdio client initialized the server, discovered the tool, and verified that an unknown project returns an MCP tool error. No complete live agent/index retrieval run was performed.

Sources: [Claude authentication](https://code.claude.com/docs/en/authentication), [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
