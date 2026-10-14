# Automatic Graphify integration for Copilot

## Setup and use

Install this branch into the Python environment used by your Copilot host:

```sh
python -m pip install -e .
# Run in the Java repository to be analyzed. Choose the host you use:
graphify copilot install --project
# OR (preserves the existing VS Code user-scope skill installation):
graphify vscode install
```

`graphify copilot install` without `--project` still installs the personal skill;
it also configures automatic hooks/instructions in the current repository. The
project variant keeps the existing project skill scope. Both Copilot hosts share
one `.github/hooks/graphify.json`; installing both does not duplicate hooks.
Hook launchers pin the installing Python and repository paths so GUI sessions do
not depend on PATH. Reinstall after cloning, moving the checkout, changing Python,
or opening it through WSL/SSH/containers. Install inside the execution environment.

Trust the workspace and enable hooks in the selected host. Restart the session.
In VS Code select an Agent-capable session target and inspect the Hooks page.
Copilot CLI users can inspect the installed hooks with `/hooks`.

Initial graph generation is optional. If the graph is absent, all hooks silently
defer to normal Copilot. Explicit `/repo-analyzer .` requests retain the existing
Java extraction workflow. The hooks never generate a graph from an ordinary
question. Approval is requested once per scoped implementation request; new
requests require new approval and native permissions remain in effect. See the
[implementation report](COPILOT_SCOPED_APPROVAL.md) for current details.

After generation, use normal prompts:

```text
Explain future transaction cancellation handling.
What does CancellationService.cancelTransaction do?
Where is this method called?
Debug the cancellation failure.
Add validation to the cancellation API.
```

No `/graphify query`, `/repo-analyzer query`, or terminal query is required for
these prompts. Manual queries, API documents, paths, explanation commands, exports,
and all other existing functionality remain available.

## Runtime sequence

1. The host invokes a prompt hook before the agent starts using tools. The hook
   checks `graphify-out/graph.json` first, then queries the existing Graphify engine
   with the actual user question, including graph callers/callees and API evidence.
   It does not open Java source contents or run a shell built from user input.
2. Repository/session-specific temporary state records the result and prompt. It
   never records a reusable edit approval. Each prompt invalidates old readiness.
   For short continuation prompts, previous request context accompanies the actual
   follow-up; a conversational "yes" does not grant tool permission.
3. Copilot CLI/Agent Host uses `userPromptTransformed` to append evidence to the
   model-facing prompt. VS Code Local receives it through the first pre-tool denial
   and/or a bounded Stop continuation. The same pre-tool fallback supports CLI
   versions without transformed-prompt support. A stop hook supplies evidence if
   the model attempted to finish without using tools; it never loops indefinitely.
4. Explanation turns deny repository tools after graph analysis, so the model must
   answer from the evidence or report missing detail. Implementation turns request
   native permission for source tools, edit tools, arbitrary shell, MCP operations,
   and delegation. The instructions require a concrete graph-based plan and user
   approval before targeted source inspection, then approved edits and tests.
5. Successful edits trigger a reminder to test and request permission for
   `graphify update .`. Updating is never automatic without permission. A successful
   update is re-queried. Declining refresh leaves the graph stale and must be reported.

Known communication/planning tools keep the host's ordinary permission behavior.
Unknown tools never receive an automatic allow decision. The adapter does not
execute or rewrite agent tool arguments. Actual approval/rejection is processed by
the host's permission UI. Graph maintenance is an explicitly recognized, exact
`graphify update .` or `graphify extract . --no-cluster` command; compound shell
commands cannot masquerade as maintenance. Initial extraction additionally requires
an explicit `/repo-analyzer` prompt.

Missing graphs bypass Graphify without warnings or permission gates. Unreadable,
corrupt or timed-out existing graphs produce an actionable error. Stale graphs require
update approval. Stale persisted evidence is labeled as outdated. Freshness checks
use the existing `needs_update` marker, Java file metadata and missing recorded paths,
without reading source contents. In-turn metadata signatures detect new/deleted or
changed Java files. They are conservative checks, not cryptographic proof of freshness:
preserved timestamps, excluded/generated sources, merged foreign graphs, and missing
extraction metadata may need a user-approved rebuild. This automatic integration targets
the standard repository-local `graphify-out/graph.json`; other CLI graph paths and
`GRAPHIFY_OUT` workflows still work manually but require a standard local graph for
this integration.

## Supported enforcement and limits

| Surface | Automatic execution | Enforcement |
| --- | --- | --- |
| Copilot CLI, interactive, hooks enabled | Prompt hook executes the graph query; transformed-prompt hook supplies evidence | Pre-tool deny/ask decisions gate tools; user approval occurs in the host |
| VS Code Copilot on Agent Host | Copilot provider hooks, where supported by the installed runtime | Same provider permission contract; verify runtime hook support |
| VS Code Local Agent | Copilot-compatible hook configuration mapped to Local events | Prompt query, first-tool deny/context, native ask, Stop continuation |
| VS Code Chat/Ask without tool hooks or terminal execution | Repository instructions and installed skill only | Cannot guarantee automatic execution or block preloaded context; use an Agent-capable target for enforcement |
| Hooks disabled, untrusted workspace, unsupported host version | No guaranteed hook execution | Instructions explicitly report the limitation and require graph-first fallback if tools are available |

Important boundaries:

- Hooks constrain agent tool operations, not the host's indexing, editor selections,
  already attached source context, extensions, or the model's prior knowledge.
- Native permission `ask` is the executable write gate. Plan quality, exact intent,
  which files are necessary, answer fidelity, and running the correct tests still
  depend on the agent following instructions. No supported hook API attests that a
  specific natural-language plan was approved. This implementation does not pretend
  to provide that guarantee or parse an unstable chat transcript as consent.
- The conservative intent classifier recognizes common English implementation verbs
  and short rejection/continuation responses. Other prompts remain explanation-only.
  It is not a universal semantic classifier. Every repository prompt is queried,
  including non-code questions, to avoid silently missing repository requests.
- CLI command-hook timeouts are fail-open in the host. The query worker has a
  20-second timeout, below the 30-second hook timeout, and pre-tool failures return
  explicit denials, but a killed/hung hook runtime cannot guarantee enforcement.
  Do not disable hooks or bypass native permission prompts. CLI autopilot/noninteractive
  sessions cannot supply human approval and may deny `ask` decisions.
- Configured CLI `userPromptSubmitted` stdout is ignored. Context delivery therefore
  uses the documented transformed-prompt event plus pre-tool/Stop fallbacks; it does
  not rely on unsupported `modifiedPrompt` output. VS Code Local prompt hooks only
  document common outputs, so the adapter does not invent a prompt `additionalContext`
  schema. The system message is informational; pre-tool/Stop carry model context.
- Runtime state is stored in the OS temporary directory, scoped by repository and
  session. It includes the prompt and graph evidence. Readiness expires after 24 hours;
  session-end cleanup runs where supported, otherwise OS temporary-file cleanup applies.
- Hook files are user-editable configuration, not an OS security boundary. This is
  an automation/approval workflow, not protection against a malicious local process.

## Why these integrations

The existing MCP server exposes graph query, traversal and other graph tools. MCP
provides tools but does not force the model to call them before another tool, so it
is preserved rather than used as an enforcement claim. A custom agent or skill
requires selection or model routing; neither guarantees automatic activation for
ordinary questions. Repository hooks provide actual lifecycle execution and tool
permission decisions. Skills/instructions carry explanation and change-plan policy.

Reference contracts checked during implementation:

- [GitHub Copilot hooks reference](https://docs.github.com/en/copilot/reference/hooks-reference)
- [VS Code hook configuration and host distinctions](https://code.visualstudio.com/docs/agent-customization/hooks)
- [VS Code Local hook payloads and decisions](https://code.visualstudio.com/docs/agents/reference/hooks-reference)
- [Copilot skill discovery](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills)

## Installation safety and removal

The installer updates only Graphify-owned command entries and the exact `## graphify`
legacy instruction section or its `<!-- graphify:start -->` / `<!-- graphify:end -->`
managed replacement. Old and duplicate sections migrate safely; other hooks,
custom keys and instruction sections remain. Latest content reports `already up to date`.
Repeated installation refreshes paths/instructions without duplicate hooks. Malformed
or unsupported hook JSON is rejected rather than overwritten. The existing skill
upgrade/backup behavior is retained. Other hosts and their hook guards are unchanged.

Use `graphify copilot uninstall --project`, `graphify copilot uninstall`, or
`graphify vscode uninstall` for the corresponding installed skill scope and the
current repository's shared automatic integration. Because the hook file is shared,
removing either integration removes automatic enforcement for both hosts in that
repository; reinstall the other host if it is still needed.

## Existing project review and change map

There was no graph or generated wiki in this checkout before review. The Python
implementation was inspected directly; the Java-only extractor cannot represent
the entire Python implementation. The later required update produces a graph of
the Java examples/fixtures, not a claim of full Python architecture coverage.

| Component | Existing responsibility | Integration decision |
| --- | --- | --- |
| `__main__.py`, `cli.py` | CLI dispatch; extract/update/query/path/explain/affected/API docs/export and existing hook guards | Keep command behavior; new hook module has its own `python -m` entrypoint |
| `extract.py`, `extractors/engine.py`, `detect.py` | Java discovery, AST extraction, member/type resolution, evidence and diagnostics | Reuse unchanged through the initial skill and update command |
| `build.py`, `watch.py`, `cache.py`, `paths.py` | Graph assembly, incremental updates, manifests/caches, atomic output | Reuse update pipeline and atomic configuration writes |
| `serve.py`, `affected.py` | MCP and CLI query traversal, API flow rendering, dependency impact | Reuse query engine and caller/callee evidence, no second query implementation |
| `api_docs.py`, `bridges.py`, exporters/report/wiki | API contracts, optional multi-service links, documents and graph views | Preserve unchanged |
| `install.py`, `hooks.py` | Host installation, skill migration, Git lifecycle hooks | Extend Copilot installation; preserve other hosts and Git hooks |
| `tools/skillgen`, packaged skills/always-on blocks | Generated integration instructions and drift snapshots | Append Copilot-specific workflow and regenerate artifacts |
| `copilot_hooks.py` (new) | Prompt query worker, session state, context transport, permission decisions | Shared CLI and Local input/output adapters |
| `copilot_install.py` (new) | Merge/install/uninstall hook configuration | Shared by existing Copilot and VS Code commands |

## Validation

Changed files: `README.md`, `graphify/install.py`,
`graphify/always_on/vscode-instructions.md`, `graphify/skill-copilot.md`,
`graphify/skill-vscode.md`, `tools/skillgen/gen.py`,
`tools/skillgen/fragments/always-on/vscode-instructions.md`, and the three matching
snapshots `tools/skillgen/expected/graphify__always_on__vscode-instructions.md`,
`tools/skillgen/expected/graphify__skill-copilot.md`,
`tools/skillgen/expected/graphify__skill-vscode.md`.

New files: `graphify/copilot_hooks.py`, `graphify/copilot_install.py`,
`tests/test_copilot_automatic.py`, `tools/skillgen/fragments/copilot-automatic.md`,
and this document, `docs/COPILOT_AUTOMATIC.md`.

```sh
python -m pip install -e . pytest hypothesis build wheel
python -m tools.skillgen --check
python -m pytest tests/test_copilot_automatic.py -q
python -m pytest tests/ -q --tb=short
graphify update .
```

The new tests exercise real graph queries and subprocess hook input/output, automatic
activation for simple/API/debug/change prompts, no Java content reads before graph
analysis, ask/deny decisions, a simulated native permission boundary, rejected edits,
missing/corrupt/stale graphs, context injection, no-tool responses, session isolation,
repeat-safe host installation and preservation of unrelated configuration.

Automated tests validate the adapter against documented host contracts. They do not
prove the installed Copilot UI honors every decision. Live smoke-test each supported
runtime: generate the initial graph with `/repo-analyzer .`; ask an explanation;
inspect hook diagnostics for prompt query before any source tool; ask for a fix;
reject the proposal/native prompt and verify no source change; repeat and approve;
check targeted edits, tests, and an approved graph refresh. Also test missing and
stale graphs, hook-disabled mode, and restart after repeated installation.
