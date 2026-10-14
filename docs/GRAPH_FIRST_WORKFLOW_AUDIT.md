# Graph-first ordering audit — 2026-10-15

## Findings

The branch had two installers writing different configurations to the same hook
file. `graphify copilot install` and `graphify vscode install` used
`copilot_install.py` / `copilot_hooks.py`; `python -m graphify.copilot install`
wrote a separate Local hook implementation. Its pre-tool output supplied context
without a permission gate, and `ensure_graph()` could refresh Java extraction
before `repository_context()` queried persisted evidence. Instructions also allowed
explanation requests to replace insufficient graph evidence with source reads.

These are code-level routes that allowed or encouraged source-first behavior.
The user's installed hook settings and live Copilot trace were not available;
disabled hooks, stale installations or unsupported chat modes must be checked
separately. A visible Java read alone does not prove that a prior automatic query
was skipped: hook queries run outside the model's ordinary tool list.

## Changes

- All CLI, project, standard VS Code and dedicated VS Code installations now use
  the existing shared graph-query / approval adapter.
- Installation removes only old Graphify-owned entries and managed instruction
  blocks, preserves unrelated hooks and rules, and remains repeatable.
- When the graph exists, the prompt hook loads and queries it before Java source
  contents are accessed. Evidence names the queried graph path. Explanations use
  graph evidence; source tools remain blocked for explanation-only requests.
- Implementation and debugging use graph relationships before targeted source
  inspection and retain approval once per task plus normal host permissions.
- Missing graphs bypass all hook analysis, state creation and permission gates.
  Manual extraction and documentation remain available.
- The old direct hook entrypoint queries persisted evidence before synchronization.
  MCP context/impact calls also query valid persisted evidence before an automatic
  refresh can parse changed Java. Existing synchronization and recovery remain.

The review traced public CLI dispatch, installers, generated skills and instructions,
both hook implementations, MCP registration and graph selection, freshness checks,
Java extraction/update, dependency analysis, API documentation and regression tests.
The checkout had no generated report or wiki initially; its required later graph
update covers Java examples/fixtures, not the Python implementation.

## Upgrade and verify

1. Install this branch's latest package in the Python environment used by Copilot.
2. Activate that environment, change to the Java repository containing
   `graphify-out/graph.json`, and rerun `graphify copilot install --project` or
   `graphify vscode install`. Alternatively, from the Graphify checkout run
   `python -m graphify.copilot install --root <Java-repository> --ide vscode`.
3. Restart Copilot. For VS Code Local, enable `chat.useHooks`, trust the workspace
   and use an Agent-capable Local session. In CLI, inspect `/hooks`.
4. Ask an explanation. Inspect hook diagnostics for `Queried existing graph:`
   followed by the intended graph path and graph evidence before source tools.
5. Ask for a change. Verify the impact/plan approval precedes source inspection.
   Remove the graph in a disposable test copy and confirm native tools continue.

Hooks cannot control IDE indexing, already attached Java context, inline completions
or sessions where hooks are disabled. Natural-language model compliance and live
host discovery are not established by automated adapter tests.

Host contracts: [GitHub Copilot hooks](https://docs.github.com/en/copilot/reference/hooks-reference),
[VS Code Local hooks](https://code.visualstudio.com/docs/agents/reference/hooks-reference),
[hook discovery and settings](https://code.visualstudio.com/docs/agent-customization/hooks).

## Regression coverage

Real installed command entries are launched in independent subprocesses from a
Java repository for CLI, project CLI, standard VS Code and dedicated VS Code,
with both present and absent graphs. The queried method exists only in graph.json,
so the returned method evidence proves graph use rather than source reconstruction.
Other checks cover guarded Java reads, source-tool denial, exact graph paths,
installer switching, unrelated-hook preservation, graph deletion, repeated installs,
once-per-task approval, MCP stdio/HTTP, Java update and API documents.

The broad integration run passed 331 tests. All 50 generated artifacts matched
their templates and snapshots. The required graph update completed successfully.
The final instruction-block migration and installed/repeated-install checks passed
16 tests after the migration adjustment; this overlaps the broader run.
