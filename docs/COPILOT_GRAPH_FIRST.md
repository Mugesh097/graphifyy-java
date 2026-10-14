# Graph-first Copilot integration

The intended developer experience is to run `/repo-analyzer <repository>` once
to generate `graphify-out/graph.json`, then ask normal Copilot questions. With
the integration configured once, subsequent questions consult the saved graph
without requiring `/repo-analyzer` again. Missing-graph generation through MCP
is also available as a recovery fallback.

## Existing architecture and reused components

Graphify is a Python package, not a replacement IDE assistant. Java tree-sitter
extraction in `extract.py` and `extractors/` records classes, methods, fields,
Spring routes, type references, call sites and conditions. `build.py` normalizes
and merges evidence into NetworkX graphs. `watch.py` performs incremental Java
rebuilds, preserving unchanged evidence and handling deleted files. The CLI in
`cli.py` exposes extraction, update, merge, query, path, explain, affected and
API documentation commands. Clustering, reports and wiki generation are separate
optional presentation layers.

The persisted schema remains unchanged: a `nodes` array and `edges` or `links`
array. Nodes contain IDs, labels, source paths/locations and Java `metadata`;
edges record source/target, relation, confidence, context and call-site evidence.
Multiple relationships can connect the same nodes. Graph loaders accept both
edge keys. No separate database or graph format was added.

`serve.py` already implements MCP with stdio/HTTP transports, graph caching,
Java call-flow queries, node lookup, neighbors, communities and paths.
`affected.py` already walks reverse dependencies, including class members.
`api_docs.py` generates deterministic Markdown from the persisted endpoint
catalog and call evidence. The existing installed `/repo-analyzer` skill and
API-documentation path remain available without changes to their implementation.

This enhancement adds `graph_first.py` for freshness and context orchestration,
three tools to the existing MCP server, and `copilot.py` for configuration and
VS Code Local hooks. No new runtime dependencies are introduced: MCP remains
the existing optional extra.

## Request and change workflows

```text
Normal repository prompt
  -> Local prompt hook OR Copilot invokes repository_context
  -> stat Java inventory, reuse or incrementally refresh graph.json
  -> existing graph query + endpoint flow + candidate file paths
  -> Copilot response or reads of specific candidate implementation files

Change prompt
  -> analyze_change_impact (or repository_context with impact=true)
  -> endpoint/call evidence + DTO/type neighborhood + reverse dependencies
  -> Copilot edits relevant source, reviews callers, validates/tests
  -> refresh_graph or Local Stop hook synchronizes persisted Java evidence
```

Candidate files are a conservative static neighborhood, not proof that every
file needs modification. Endpoint routes are resolved from the existing catalog;
all matching handlers remain candidates. Exact calls use the API-documentation
evidence traversal, including interface dispatch. Related DTOs and owners are
found through stored graph edges. Change analysis expands candidate file members
and uses the existing reverse dependency traversal. Ambiguous matches and
missing evidence require clarification or a narrower graph query. Runtime wiring,
reflection, constants that cannot be resolved and external behavior must not be
invented.

Tools:

| Tool | Purpose |
| --- | --- |
| `repository_context(question, impact=false, depth=3)` | First repository step: synchronize, query evidence, return candidate paths |
| `analyze_change_impact(question, depth=3)` | Candidate components and reverse dependents before editing |
| `refresh_graph()` | Incremental synchronization after edits; unchanged graph is reused |
| `query_graph(question, ...)` | Existing graph search and Java endpoint execution flow |
| `get_node`, `get_neighbors` | Existing class/method details and dependency relationships |
| `graph_stats` | Existing graph inventory/summary |

Every tool also accepts the existing optional `project_path`. Set
`GRAPHIFY_GRAPH_FIRST=1` to synchronize before existing tools too. Without it,
historical tools retain their behavior; the three new tools always synchronize.
Automatic synchronization requires the standard `<repository>/graphify-out/graph.json`
layout (or a simple directory-name `GRAPHIFY_OUT` override). Arbitrary graph
files and shared absolute output paths remain available through historical tools
without automatic synchronization. Point this integration at a single Java
repository. For merged service workspaces, refresh individual service graphs and
run the existing `merge-graphs` command; do not auto-refresh a merged graph as
though it belonged to one service.

## Install in a Spring Boot repository

Use Python 3.10+ and install this checkout into a dedicated environment:

```sh
python -m venv .venv
# Windows: .venv\Scripts\python.exe; Unix: .venv/bin/python
python -m pip install -e '/absolute/path/to/this/graphify-checkout[mcp]'
python -m graphify.copilot install --root /absolute/path/to/spring-repository --ide vscode
```

Run both Python commands using the dedicated environment's interpreter. The
installer records that interpreter's absolute path and the target graph's
absolute path, so the IDE does not need the Graphify checkout as its working
directory. Configurations are machine-specific; rerun installation after moving
the repository or environment. Existing MCP servers and unrelated repository
instructions are retained. Reinstallation replaces the Graphify managed block
and its dedicated hook/agent files. The installer does not remove or reinstall
the existing `/repo-analyzer` skill.

Every ordinary repository request checks for `graphify-out/graph.json`. When
absent, Graphify is silently skipped: Copilot continues native source searches,
explanations, debugging and changes with its standard tools and permissions.
There is no generation, warning, `/repo-analyzer` suggestion or Graphify approval
gate. Manual graph generation and `/repo-analyzer` commands remain available.
When present, the graph is queried first and an existing current graph is loaded
without regeneration. Changes require graph impact analysis before inspecting
relevant source and the existing user-approval process before source edits.

## VS Code

Installation creates:

- `.vscode/mcp.json`: existing Graphify stdio server with freshness enabled.
- `.github/copilot-instructions.md`: repository-wide graph-first instructions.
- `.github/agents/graphify.agent.md`: optional Graphify custom agent.
- `.github/hooks/graphify.json`: **Local harness** hooks for prompt, pre-tool and stop.

Open the target repository. Trust/start the MCP server using **MCP: List Servers**,
enable Graphify tools, and use Copilot Agent mode. Ensure workspace hooks are
enabled/trusted and use the **Local** session target for these hook files.
The Graphify custom agent makes the workflow explicit, but the repository
instructions also apply in normal Agent sessions without a slash command.

For each Local prompt with an existing graph, `UserPromptSubmit` queries the graph and records the
question in a session-keyed sidecar. `PreToolUse` synchronizes again and injects
graph context using the documented `additionalContext` output. It stops the
session if the prompt hook did not run or graph preparation fails while a graph exists. `Stop`
synchronizes actual Java changes, including changes made outside Copilot.
These hooks do not approve tools, run tests or edit Java. The agent still selects
implementation files and performs validation. Check the IDE hook output and MCP
tool trace to confirm ordering. All hooks immediately allow native tools when
the graph is missing, including if it is deleted during the session. Graph-first
MCP calls return `available: false, continue_native: true` in that case and keep
the server running; a later manually generated graph is picked up automatically.

## IntelliJ IDEA / GitHub Copilot plugin

```sh
python -m graphify.copilot install --root /absolute/path/to/spring-repository --ide intellij
```

This creates the same instructions/custom agent plus `graphify-copilot-mcp.json`.
In Copilot Chat, choose **Agent**, open **Configure your MCP server**, select
**Add MCP Tools**, and merge the generated `servers.graphify` entry into the
plugin's `mcp.json`. Restart the server and verify the three new tools are
listed/enabled. Where supported, select the Graphify custom agent once, then ask
normal questions. The standalone generated JSON is an import example, not an
automatically discovered IntelliJ configuration file. Enable repository custom
instructions in the plugin. An organization may need to enable its MCP policy.

The generated Local hooks are for VS Code, not IntelliJ or Copilot CLI/Agent
Host. No unsupported JetBrains interception API is claimed. In IntelliJ the
repository instructions/custom agent request Graphify first and the MCP tools
perform deterministic graph preparation once invoked. Verify the first tool call
in Chat; this workflow is model-mediated.

## Freshness, recovery and boundaries

- Freshness enumerates/stat-checks Java paths with existing ignore/exclusion
  rules; it does not read source content to answer a question. `detect` has an
  additive Java-inventory mode that skips content word counts and other formats.
- A sidecar `.graph_first_inventory.json` records file mtime/size and graph
  identity. Changed, new or deleted Java files use the existing incremental rebuild.
  Legacy graphs without the sidecar are checked against graph timestamps and
  recorded source paths. Missing graphs bypass this synchronization entirely.
- Invalid JSON is preserved as `graph.invalid-<timestamp>.json` before rebuilding.
  Failed recovery restores it. Extraction failures stop the new workflow instead
  of delivering stale context. Diagnostic output stays off MCP stdout; rebuild
  logs use Python logging. Source truth remains the working tree.
- A process/thread lock serializes new graph-first calls across hook and MCP
  processes on Windows and Unix. Existing independent CLI/watch processes retain
  their existing locking behavior; avoid running a separate build simultaneously.
- Stat checks cannot detect edits that deliberately preserve both mtime and size.
  Use `graphify update <repository>` for a forced full check in that situation.
  Non-Java changes are outside this Java analyzer's extraction scope.
- Changing exclusions to remove existing files stops graph-first queries until
  the graph is regenerated with the new scope. The existing incremental builder
  preserves filtered files; this integration does not silently serve that stale
  evidence or remove semantic evidence itself.
- Synchronization describes the current tree even when tests fail. Graph refresh
  is not validation and no validation success is inferred from a fresh graph.

## Supported integration limits and sources

MCP and instruction files alone do not intercept every Copilot request. A model
can omit a requested tool. The Local hooks automatically prepare evidence before
agent tools within their supported scope, but cannot control prior IDE context,
inline completions, Ask-mode answers without tools, disabled hooks, provider
harnesses, or source access outside that session. They do not technically confine
source reads to candidate paths. There is no claim of universal enforcement.

Official references checked for this implementation:

- [GitHub: MCP in VS Code and JetBrains](https://docs.github.com/en/copilot/how-tos/copilot-in-your-ide/customize-copilot/extend-copilot-with-tools-and-context/extend-copilot-chat-with-mcp)
- [VS Code: Local hook input/output schemas and harness boundaries](https://code.visualstudio.com/docs/agents/reference/hooks-reference)
- [VS Code: configuring agent hooks](https://code.visualstudio.com/docs/agent-customization/hooks)
- [GitHub: custom agent configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration)

## Example prompts and verification

1. `Explain GET /v1/remote/addons/details.` → first context call/hook, endpoint
   and complete recorded call evidence, candidate controller/service/repository.
2. `Which classes depend on AddonService?` → graph search; use `get_neighbors`
   or impact analysis to inspect reverse dependencies; no Java read required.
3. `Add addonStatus to the response of GET /v1/remote/addons/details.` → impact
   context, candidate DTO/mapping files, relevant implementation edits, tests,
   `refresh_graph`. Graphify supplies context; Copilot performs the edits.
4. With a disposable repository's graph absent, repeat prompt 1 → initial rebuild.
5. Edit a Java DTO → next context request or Stop hook incrementally refreshes.
6. `/repo-analyzer generate API documentation for GET /v1/remote/addons/details`
   → existing skill and Markdown generation remain available.

Automated regression coverage is in `tests/test_graph_first.py`: API flow,
dependency candidates, DTO impact, graph reuse, edit/add/delete detection,
invalid/missing graph recovery, hook order and post-change synchronization,
non-destructive installation, missing evidence, source-free inventory checks,
existing documentation generation and real stdio MCP requests. Run:

```sh
python -m pytest tests/test_graph_first.py tests/test_java_api_docs.py tests/test_repo_analyzer_install.py tests/test_serve.py tests/test_serve_http.py tests/test_java_watch.py -q
```

IDE model behavior requires the manual trace checks above with a logged-in
Copilot account; automated tests do not claim to validate Copilot's natural
language responses or execute its installed slash command.
