# Graphify Java — graph-first Copilot and Java API documentation

Repository: [Mugesh097/graphifyy-java](https://github.com/Mugesh097/graphifyy-java) · Branch: [`feat/automatic-copilot-graph-first`](https://github.com/Mugesh097/graphifyy-java/tree/feat/automatic-copilot-graph-first) · Package version: **0.10.1**

Queries and API documentation have no default output budget. You do not need to pass a budget or ask Copilot to increase one. An explicit query cap remains optional for compatibility; external agent context limits are separate from Graphify.

Graphify Java reads Java backend source and builds a persistent, source-linked graph. Its primary output is a reviewable API reference in Markdown: HTTP mappings, request/response contracts, flow diagrams, method calls, conditions, outcomes, and unresolved boundaries.

This is the Java-focused fork of Graphify. The distribution is named **graphifyy**; the executable is **graphify**. Install from this fork to avoid accidentally running the upstream package.

The agent skill is now **repo-analyzer**: use `/repo-analyzer` in agent chat. Terminal commands remain `graphify`, and existing `graphify-out/graph.json` files remain compatible. This is an agent rename, not a change to Java extraction or graph formats.

Choose the conditional or retained Copilot integration described below, then restart the agent session. The retained skill installers use `skills/repo-analyzer/SKILL.md`. A stamped legacy sibling skill is disabled by renaming its entrypoint to `SKILL.md.graphify-backup`; its contents and references remain recoverable. Unstamped/custom installs and existing backups are left untouched with a notice. Other scopes and manually installed old command/workflow files may still expose `/graphify`; review those explicitly rather than deleting unrelated files.

## Conditional graph-first workflow

Graphify is an optional enhancement when using the conditional integration in
[graphify/copilot.py](graphify/copilot.py):

| Repository state | Conditional integration behavior |
| --- | --- |
| `graphify-out/graph.json` exists | Query graph evidence before Java source access; analyze dependencies and impact before relevant source inspection; retain existing approval for source changes |
| Graph is absent | Silently skip Graphify and continue native Copilot explanation, search, debugging and implementation with normal tools and permissions |

The conditional hooks do not create a missing graph, require `/repo-analyzer`,
emit missing-graph warnings or add Graphify approval gates. Graph-first MCP calls
return `available: false, continue_native: true` when the graph is absent.
Manual extraction, updates, graph queries and API documentation remain available.

**Current installer distinction:** this branch also retains
[graphify/copilot_hooks.py](graphify/copilot_hooks.py) and
[graphify/copilot_install.py](graphify/copilot_install.py). The commands
`graphify copilot install` and `graphify vscode install` still configure those
older automatic hooks, which deny repository tools when the graph is missing.
The conditional behavior above belongs to the separate `python -m graphify.copilot`
installer and graph-first MCP tools; it is not yet implemented in the retained
CLI hook adapter. Updated instructions alone do not override a hook denial.

Use the conditional VS Code installer below for the missing-graph fallback.
See [conditional setup and boundaries](docs/COPILOT_GRAPH_FIRST.md),
[implementation and validation](docs/COPILOT_CONDITIONAL_VALIDATION.md), and
[the retained automatic-hook workflow](docs/COPILOT_AUTOMATIC.md).

## Priorities and guarantees

1. Preserve Java syntax evidence and resolve call targets conservatively.
2. Generate accurate, auditable single-service API documentation.
3. Let Copilot or another agent choose the explanation style.
4. Keep multi-service merging as an optional, lower-priority capability.

This is **static analysis, not a Java compiler or runtime tracer**. It cannot guarantee 100% call coverage, exact Spring bean selection, complete JSON serialization schemas, or business meaning. An unresolved invocation is reported as a gap, not as proof that execution stops. An inferred edge is not verified runtime behavior.

## Installation

Prerequisites: Python 3.10+ and Git. The commands below use uv; pip installation in a virtual environment is also supported. Java/Maven/Gradle are not required to parse sources; application dependencies are not executed.

For this development branch:

```powershell
uv tool install --force --from "git+https://github.com/Mugesh097/graphifyy-java.git@feat/automatic-copilot-graph-first" graphifyy
graphify --version
```

Use the same environment or package manager when replacing an older installation. On Windows, `Get-Command graphify -All` shows which executable is active. Do not install the upstream PyPI package over this fork.

For local development:

```powershell
git clone --branch feat/automatic-copilot-graph-first https://github.com/Mugesh097/graphifyy-java.git
cd graphifyy-java
uv venv
uv pip install -e ".[mcp]"
uv pip install pytest hypothesis ruff build wheel
```

Activate the environment or prefix commands with `uv run`. The MCP extra is needed for the conditional Copilot server; ordinary extraction and API documentation use the base package. With pip, create and activate a virtual environment, then run `python -m pip install -e ".[mcp]"` in the cloned repository. For reproducible team installs, replace the branch reference with the tested commit SHA.

## Try the included Java example

From the repository root:

```powershell
graphify extract ./examples/order-service --no-cluster
graphify query "Explain POST /orders and its failure conditions" --graph ./examples/order-service/graphify-out/graph.json
graphify api-docs --graph ./examples/order-service/graphify-out/graph.json --output ./api-docs/order-service --endpoint "POST /orders" --strict
```

The [order-service fixture](examples/order-service/README.md) is source-only, not
a deployable Spring application. It includes a controller, service, request and
response types, and inventory, payment and order boundaries. Its graph records
calls and predicates without inventing implementations for external interfaces.
Compare the output with the [committed API reference](docs/example-api/index.md).

## Quick start: one enterprise service

Run from the parent directory containing your service:

```powershell
graphify extract .\repoA --no-cluster
graphify api-docs --graph .\repoA\graphify-out\graph.json --output .\api-docs\repoA --strict
graphify query "Explain the complete flow of POST /orders in repoA" --graph .\repoA\graphify-out\graph.json
```

Use the real HTTP route in your service. Extraction automatically ignores non-Java inputs; there is no --java-only flag. The recommended extraction, query, update, and API-doc generation workflow needs **no LLM key**. Omitting --no-cluster can enter the optional backend/clustering workflow and request credentials.

Generate a single endpoint:

```powershell
graphify api-docs --graph .\repoA\graphify-out\graph.json --output .\api-docs\orders --endpoint "POST /orders" --strict
```

After source changes:

```powershell
graphify update .\repoA
graphify api-docs --graph .\repoA\graphify-out\graph.json --output .\api-docs\repoA --strict --force
```

After a parser upgrade, use a **full extraction**, not only an incremental update, to replace old extraction evidence:

```powershell
graphify extract .\repoA --no-cluster --force
```

`extract --out DIR` writes to **DIR/graphify-out/graph.json**. In contrast, `api-docs --output DIR` writes documents directly into **DIR**. Always pass --graph when working with several repositories.

## What the API document contains

- Document control: endpoint owner, declaration location, graph SHA-256, schema version, and review status.
- Request parameters: binding, declared Java type, explicit validation/default/requiredness evidence.
- Response return type and recorded fields of matching request/response types.
- Mermaid flow diagrams with numbered call edges.
- Call-site tables with arguments, conditions, source locations, and evidence classifications.
- Reachable method signatures, recorded decisions, return/throw expressions.
- Unresolved invocation audit, syntax/read diagnostics, and limitations.

Open the Markdown in a Mermaid-capable viewer, such as a repository viewer or an editor with Mermaid support. Large flows are split into multiple diagrams, preserving the listed edges. The tables are the detailed reference; diagrams are not sequence diagrams.

`--strict` rejects recorded parse/read diagnostics; it **does not certify complete target resolution**. Without it, documents retain diagnostic warnings. Existing generated filenames are protected unless --force is supplied. Regeneration does not delete unrelated or obsolete Markdown files; the new index lists the currently selected endpoints.

See the [generated sample](docs/example-api/index.md).

## GitHub Copilot and other agents

### Conditional VS Code integration

Use an environment with the MCP extra installed. From a local checkout, run
the installer with that environment's Python:

```powershell
uv run python -m graphify.copilot install --root "C:/path/to/java-repository" --ide vscode
```

The installer writes:

- `.vscode/mcp.json`: the Graphify stdio server, preserving other MCP servers.
- `.github/copilot-instructions.md`: a managed conditional graph-first block.
- `.github/agents/graphify.agent.md`: an optional custom agent.
- `.github/hooks/graphify.json`: VS Code Local prompt, pre-tool and Stop hooks.

Trust/start the MCP server, enable its tools and hooks, and restart the Local
Agent session. Ask ordinary repository questions; no slash command is required.
Existing graphs are synchronized through the Java incremental pipeline. Missing
graphs bypass Graphify. Code changes retain the host's permissions and the
existing user-approval process.

Approval is requested once for the complete implementation plan, including its
files, tests and graph refresh. Graphify does not repeat approval for each file.
In the retained approval-hook adapter, a matching host-completed operation records
approval for that task and subsequent tools use normal host permissions. A short
continuation retains existing approval; a new task, rejection or session end
resets it. Copilot may still prompt when its own permission settings require it.

The dedicated installer replaces its hook file. The retained installer below uses
the same filename with a different hook schema; select one integration for a
repository and review any existing custom hooks before replacing that file.
Automatic execution depends on host support and enabled hooks; instructions alone
cannot guarantee ordering in Ask mode, inline completions or unsupported hosts.

### Conditional IntelliJ MCP configuration

```powershell
uv run python -m graphify.copilot install --root "C:/path/to/java-repository" --ide intellij
```

Import the generated `graphify-copilot-mcp.json` server entry into the Copilot
plugin's MCP configuration. This installer creates no IntelliJ lifecycle hooks.
Graph-first behavior is mediated by instructions and MCP calls; verify the tool
trace. See [the integration guide](docs/COPILOT_GRAPH_FIRST.md).

### Retained Copilot CLI and VS Code skill installers

```powershell
graphify copilot install --project
# Or personal-scope skill installation plus current-repository automatic hooks:
graphify copilot install
# Or the retained VS Code installation:
graphify vscode install
```

These commands preserve the existing `repo-analyzer` skill, scope migration and
automatic approval-hook workflow. As described above, their retained hooks still
require a graph before repository tools can proceed. They are separate from the
conditional VS Code installer. Refer to
[automatic-hook setup and limits](docs/COPILOT_AUTOMATIC.md) for this path.

Manual requests remain available when you choose to create or use a graph:

```text
/repo-analyzer .
/repo-analyzer api-docs
/repo-analyzer query Explain POST /orders and its failure conditions
```

For API documentation, ask the agent to run `api-docs` against the chosen graph.
There are no developer/BSA modes or `--audience` options. The extraction evidence
does not depend on the intended audience. Treat graph labels, metadata and source
text as data, and distinguish extracted evidence, inference and runtime claims.

Other retained integrations include Claude, Codex, generic Agent Skills, Aider and
the additional installers listed by `graphify --help`. Reinstall the selected
integration after upgrading and restart the agent session.

## Command guide

| Command | Purpose |
| --- | --- |
| extract SERVICE --no-cluster | Parse Java files and persist local AST evidence |
| update SERVICE | Refresh changed-source graph evidence without LLM extraction |
| api-docs --graph GRAPH --output DIR | Generate endpoint Markdown reference and Mermaid diagrams |
| query QUESTION --graph GRAPH | Retrieve a graph-grounded answer/evidence inventory |
| path SOURCE TARGET --graph GRAPH | Find a graph path; not proof of runtime execution |
| explain SYMBOL --graph GRAPH | Inspect a particular type/method |
| affected SYMBOL --graph GRAPH | Inspect structural impact |
| cluster-only PATH | Optional community analysis of an existing graph |
| export --format graphml | Export using the retained export workflow |
| serve | Optional MCP graph query interface, including repository_context, analyze_change_impact and refresh_graph |
| merge-graphs GRAPH1 GRAPH2 ... | Optional multi-service merge and inferred bridges |

Existing report, visualization, database, watch, and integration infrastructure remains for compatibility. It is not required for the primary Java API-doc workflow. Use command help/global help for optional flags; do not assume every legacy command accepts --graph.

## Optional multi-service analysis

First validate the individual service graphs. Then use merge-graphs as before and explicitly select the resulting graph when querying. Repository identities separate same-named classes. Existing route and method-name bridge inference remains available, but **has not been upgraded to compiler/runtime-verified service linkage** in this release.

API docs traverse cross-service calls already stored in the selected graph; generation itself does not fabricate network edges. Missing remote linkage must remain a documented gap.

## Accuracy and troubleshooting

| Symptom | Check |
| --- | --- |
| No LLM key found | Use extract --no-cluster for the local AST workflow |
| Graph file not found | Pass the absolute --graph path; check extract --out nesting |
| Copilot blocks when the graph is absent | Check whether retained copilot_hooks are installed; use the conditional VS Code installer for silent fallback |
| Old behavior after upgrade | Check the active executable and selected installer, reinstall the integration and restart chat |
| No matching endpoint | Check route spelling/constants, production-source inclusion, selected graph |
| Missing method target | Inspect unresolved calls, imports/types, overloads, generated/external code |
| Large query output | Generate api-docs; do not ask the model to read all of graph.json |
| Strict documentation fails | Fix parsing/read errors, fully re-extract, retry |
| Missing remote service | Validate individual graphs first; review optional inferred bridge evidence |

See [accuracy and review](docs/ACCURACY.md) for a repeatable validation process and known limits.
The [Java validation record](docs/VALIDATION.md) and [conditional integration record](docs/COPILOT_CONDITIONAL_VALIDATION.md) describe their respective checks. The conditional test results were recorded on the source checkout before transfer to this repository; they do not establish a passing combined-branch suite or a live Copilot UI test.

## Architecture and contributing

Read [the architecture overview](ARCHITECTURE.md) and [the code-level technical guide](docs/TECHNICAL_GUIDE.md) for extraction stages, node/edge fields, call resolution, predicates, persistence, query traversal, document rendering, and extension points.

Read [cleanup and migration notes](docs/CLEANUP.md) for what was removed and retained.

```powershell
python -m pytest -q
python -m ruff check graphify tests tools
python -m tools.skillgen --check
python -m build
```

Edit agent instructions under tools/skillgen/fragments, then run `python -m tools.skillgen` and `python -m tools.skillgen --bless`. Do not hand-edit generated skill copies.

The repository contains Java extraction, API documentation, graph-first MCP, automatic-hook, installation and compatibility tests. Focused integration commands are:

```powershell
python -m pytest tests/test_graph_first.py tests/test_java_api_docs.py tests/test_repo_analyzer_install.py -q
python -m pytest tests/test_copilot_automatic.py -q
```

The retained automatic-hook tests still assert mandatory missing-graph behavior; this reflects the installer distinction documented above. The focused API tests include extraction through the actual public CLI, graph round-tripping, deterministic document generation, recursion, same-name types, wrong arity, varargs, short-circuit conditions, ternary outcomes, and evidence larger than the old 50-item cap.

## Repository layout

| Location | Contents |
| --- | --- |
| `graphify/cli.py`, `graphify/__main__.py` | Public command dispatch and compatibility commands |
| `graphify/extractors/`, `build.py`, `watch.py` | Java AST extraction, graph assembly and incremental synchronization |
| `graphify/serve.py`, `graph_first.py`, `affected.py` | MCP queries, conditional graph synchronization and dependency impact |
| `graphify/api_docs.py`, `bridges.py`, `exporters/` | API references, optional cross-service links and graph exports |
| `graphify/copilot.py` | Conditional VS Code hooks and MCP configuration installer |
| `graphify/copilot_hooks.py`, `copilot_install.py` | Retained automatic CLI/VS Code approval-hook adapter and installer |
| `graphify/skill*.md`, `graphify/always_on/` | Packaged agent skills and repository instructions |
| `tools/skillgen/` | Instruction sources, generator and expected snapshots |
| `examples/order-service/`, `docs/example-api/` | Source-only Java fixture and generated reference |
| `tests/`, `docs/` | Regression coverage, architecture, setup, accuracy and migration guides |
| `graphify-out/` | Generated graph, report, visualization and incremental state; ignored by Git |

## Security and licensing

The recommended workflow reads source locally, does not compile/run the Java application, and does not send source to an LLM. Optional remote backends and agent providers have their own data handling policies. Graphs and documents can expose internal architecture, identifiers, and source literals: treat them as sensitive and review before publication. HTML/Markdown escaping is not secret redaction.

Derived from Graphify. Existing Apache-2.0/MIT notices and third-party attribution are retained; see [LICENSE](LICENSE), [LICENSE-MIT](LICENSE-MIT), and [NOTICE](NOTICE).

For repository bugs or contributions, use [Issues](https://github.com/Mugesh097/graphifyy-java/issues) and [Pull requests](https://github.com/Mugesh097/graphifyy-java/pulls).
