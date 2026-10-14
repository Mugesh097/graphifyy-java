# Conditional Copilot graph-first validation — 2026-10-14

## Findings and implementation

The blocking integration was `graphify/copilot.py`: its instructions required
Graphify before every repository operation, `hook()` called `ensure_graph()`
before any event handling, and a missing prompt sidecar returned `continue: false`.
The hook entrypoint also stopped sessions on exceptions. `ensure_graph()` generated
missing graphs, and graph-first MCP calls in `graphify/serve.py` invoked it
unconditionally. Thus this checkout combined mandatory graph instructions,
automatic generation, and fail-closed hooks; it did not have a single universal
missing-graph branch that only suggested `/repo-analyzer`.

Legacy Copilot/VS Code skills offered re-extraction when evidence was absent.
The VS Code always-on instructions allowed source reads without a graph but also
suggested `/repo-analyzer`; the shared AGENTS instructions required updates after
changes and restricted skipping Graphify. These paths now explicitly skip all
ordinary Graphify requirements when the graph is absent.

The minimal runtime change adds `existing_only` to `ensure_graph()`, keeping
explicit generation behavior backward compatible. Copilot hooks check graph
availability before synchronization or prompt-state checks. Missing-graph MCP
calls return `available: false, continue_native: true` without creating output or
closing the server. This applies to repository context, impact, refresh and
graph-first-enabled query tools. Creating a graph manually activates graph-first
on subsequent calls; deleting it immediately restores native fallback.

Existing graph synchronization, queries, impact analysis, invalid-graph recovery,
API documentation and explicit extraction/update/merge commands are retained.
Instructions preserve existing user approval for graph-present source changes;
missing graphs add no permission gate. Existing read/search guard tests confirm
their missing-graph behavior remains permissive. No Copilot native tool permission
configuration was added or changed.

## Modified files

- `graphify/copilot.py`
- `graphify/graph_first.py`
- `graphify/serve.py`
- `graphify/skill-copilot.md`
- `graphify/skill-vscode.md`
- `graphify/always_on/agents-md.md`
- `graphify/always_on/vscode-instructions.md`
- `tools/skillgen/gen.py`
- `tools/skillgen/fragments/core/copilot-availability.md` (new)
- `tools/skillgen/fragments/always-on/agents-md.md`
- `tools/skillgen/fragments/always-on/vscode-instructions.md`
- `tools/skillgen/expected/graphify__skill-copilot.md`
- `tools/skillgen/expected/graphify__skill-vscode.md`
- `tools/skillgen/expected/graphify__always_on__agents-md.md`
- `tools/skillgen/expected/graphify__always_on__vscode-instructions.md`
- `tests/test_graph_first.py`
- `docs/COPILOT_GRAPH_FIRST.md`
- `docs/COPILOT_GRAPH_FIRST_VALIDATION.md`
- `docs/COPILOT_CONDITIONAL_VALIDATION.md` (new)

The required explicit `graphify update .` also creates/refreshes generated state
under `graphify-out/`. This downloaded checkout has no `.git` metadata, so a Git
diff/status is unavailable. Generated references were re-rendered without content
changes; skill-generator checks verify all packaged artifacts match their sources
and snapshots.

## Verification

The focused regression command covering graph-first, skill installation, Java API
documentation, MCP stdio/HTTP, Java watch/detection and read/search/strict guards
passed **368 tests**. Real MCP subprocess tests ran with MCP 2.3.0, including
missing-graph explanation/debug/change/refresh/query calls, later explicit graph
creation and graph deletion during the same connection.

A follow-up run including the final legacy CLI/VS Code repeated-install tests,
instruction upgrades, installation strings and section replacement passed
**41 tests**. This overlaps the focused run; the counts are not additive.

`python -m tools.skillgen --check` passed: all 50 artifacts match committed output
and snapshots. `graphify update .` succeeded with 42 nodes, 55 edges and 10
communities. Initial test execution hit sandbox temporary-directory restrictions;
the approved unsandboxed regression run passed.

Missing-graph hook tests forbid graph loading, generation and context queries and
verify no output directory is created. Graph-present tests verify Java evidence
for explanation, debugging and modification prompts. Reinstallation tests retain
existing instructions, MCP servers and approval policies without generating graphs.

No authenticated Copilot CLI or VS Code Chat session was driven. Automated tests
confirm the integration permits native operations, but model compliance and live
host hook discovery remain manual acceptance checks. Reinstall existing skills
and repository integrations, then restart/reload Copilot to pick up the changes.
