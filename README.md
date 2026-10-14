# Graphify Java

Build source-linked knowledge graphs from Java backend code and generate API
documentation with HTTP mappings, request/response details, call flows and
unresolved dependencies.

The Python package is **graphifyy**, the CLI is **graphify**, and the agent skill
is **repo-analyzer**. Java AST extraction works locally without an LLM key.

## Installation

Requires Python 3.10+, Git and [uv](https://docs.astral.sh/uv/).

```powershell
git clone --branch feat/automatic-copilot-graph-first https://github.com/Mugesh097/graphifyy-java.git
cd graphifyy-java
uv venv
uv pip install -e ".[mcp]"
uv run graphify --version
```

The MCP extra enables the Copilot integration. Java, Maven and Gradle are not
required to parse source files.

## Quick start

Run the included Java example from the repository root:

```powershell
uv run graphify extract ./examples/order-service --no-cluster
uv run graphify query "Explain POST /orders" --graph ./examples/order-service/graphify-out/graph.json
uv run graphify api-docs --graph ./examples/order-service/graphify-out/graph.json --output ./api-docs/order-service --strict
```

Replace the example path with your Java repository. After source changes:

```powershell
uv run graphify update ./examples/order-service
```

Use `--endpoint "POST /orders"` to document one endpoint and `--force` to
intentionally overwrite generated documents. See the
[example service](examples/order-service/README.md) and
[sample API reference](docs/example-api/index.md).

## Copilot setup

For conditional graph-first behavior in VS Code Local Agent:

```powershell
uv run python -m graphify.copilot install --root "C:/path/to/java-repository" --ide vscode
```

Enable the workspace hooks and Graphify MCP tools, then restart Copilot.

| Graph availability | Behavior |
| --- | --- |
| `graphify-out/graph.json` exists | Query the graph first and analyze impact before relevant source inspection |
| Graph is absent | Silently continue native Copilot work without requesting or generating a graph |

Request approval once for the implementation plan, covering its files, tests and
graph refresh. Graphify does not repeat approval for each file; Copilot's native
permissions still apply. A new task requires new approval.

Copilot CLI: activate the installed Python environment, change to your Java
repository, and run `graphify copilot install --project`. The standard
`graphify vscode install` command and the installer above now use the same
conditional graph-first hooks. Reinstall after upgrading and restart the session.
See the
[conditional integration guide](docs/COPILOT_GRAPH_FIRST.md) and
[automatic-hook guide](docs/COPILOT_AUTOMATIC.md) for setup and limitations.

Manual agent commands remain available:

```text
/repo-analyzer .
/repo-analyzer api-docs
/repo-analyzer query Explain POST /orders
```

## Core commands

| Command | Purpose |
| --- | --- |
| `extract SERVICE --no-cluster` | Build Java AST evidence |
| `update SERVICE` | Refresh the graph after changes |
| `query QUESTION --graph GRAPH` | Retrieve graph evidence |
| `api-docs --graph GRAPH --output DIR` | Generate Markdown API references |
| `path SOURCE TARGET --graph GRAPH` | Inspect relationships |
| `explain SYMBOL --graph GRAPH` | Inspect a class or method |
| `affected SYMBOL --graph GRAPH` | Analyze dependency impact |
| `merge-graphs GRAPH1 GRAPH2 ...` | Combine service graphs |
| `serve` | Expose graph queries through MCP |

Use `uv run graphify --help` for additional commands and integrations.

## Documentation and development

- [Architecture](ARCHITECTURE.md)
- [Technical guide](docs/TECHNICAL_GUIDE.md)
- [Accuracy and limitations](docs/ACCURACY.md)
- [Conditional integration validation](docs/COPILOT_CONDITIONAL_VALIDATION.md)

```powershell
uv pip install pytest hypothesis
uv run python -m pytest -q
uv run python -m tools.skillgen --check
```

Edit instruction sources under `tools/skillgen/fragments/`, then regenerate with
`python -m tools.skillgen` and `python -m tools.skillgen --bless`.

Graphify provides static evidence, not guaranteed runtime behavior. Graphs and
documents may contain sensitive source details.

Licensing and attribution: [LICENSE](LICENSE), [LICENSE-MIT](LICENSE-MIT),
[NOTICE](NOTICE).
