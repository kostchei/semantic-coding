# Repository assessment

Reviewed 2026-09-13. This is a useful retrieval prototype with benchmark fixtures, a small MCP adapter, and local indexing scripts. It is not yet a validated self-improving production pipeline.

## Confirmed and addressed

- Claude: the historical report records the expired OAuth error; the installed CLI currently reports `loggedIn: false`. Print mode does not categorically require an API key. The new `run_agent_harness.ps1` checks authentication before running and explains login/setup-token recovery without storing credentials.
- Codex: `codex mcp get semcode --json` confirms the enabled server. The historical report records shell-first exploration. Registration exposes tools; it does not mandate their use. The new harness explicitly supplies the MCP server and project, requests hybrid retrieval before exploration, and rejects runs without recorded MCP usage. This is an instructed retrieval experiment, distinct from measuring unprompted tool adoption.
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

## Follow-up live validation

The first checks above were insufficient to establish live-agent success. Actual
testing found and fixed two additional integration failures:

- MCP search subprocesses inherited the protocol stdin. `grepai search` waited for
  input and timed out while ordinary CLI search succeeded. They now receive
  `DEVNULL`; a real stdio regression test verifies child EOF and continuing MCP
  protocol operation.
- Codex CLI 0.147.0 could not use the configured `gpt-6-astra` model. The local CLI
  was updated to 0.154.0. The next run exposed missing headless tool approval;
  the harness now approves only `semcode.search_codebase` for that invocation.
  A full live ORAC run then called MCP, read a returned file, and completed successfully.
  *Note:* This was an **instructed** run where the harness prompt explicitly instructed
  the agent to call `search_codebase` with a restricted toolset on an already-indexed
  repo; it verified headless MCP execution and tool connectivity, not unprompted hands-off adoption.

Claude Desktop was running its own Claude Code executable (2.1.266); the npm CLI
used by the harness had no credentials. Secure setup now stores its inference
token in Windows Credential Manager and supplies it to child CLI processes only.
A live Claude ORAC run authenticated, called MCP, read `src/orac/broker.py`, and
completed successfully (again as an instructed verification run on an indexed repo,
proving OAuth injection and protocol transport rather than unprompted adoption).
The earlier ordinary login's newly issued access/refresh credentials were also secured
in Credential Manager and removed from its plaintext cache. This did not log out or restart Desktop.
After clearing that cache, a second live Claude run on ash-rpg also passed using
only the Credential Manager token. All Python tests and harness event checks
passed after the follow-up fixes.

Antigravity's documented CLI retrieval route was tested against ORAC and ash-rpg.
Both projects returned identical top-three paths and RRF scores to the pre-fix
commit. The shared MCP route also passed a live query after the stdin fix. The
Antigravity IDE's conversational agent itself was not driven through a complete
new task, so this establishes integration compatibility, not full IDE behavior.
Already-running MCP server processes must restart to load changed Python code.

Credential tests cover actual Windows store round-trip with a unique disposable
test target, child-only injection, explicit credential precedence, and suppression
of setup-token output. No real credentials or raw agent transcripts are committed.
