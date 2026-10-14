## Conditional activation

For ordinary repository explanations, debugging, searches, or changes, first check
whether graphify-out/graph.json exists. When present, automatically query the graph
before reading Java source; use recorded classes, methods, APIs, dependencies and
flows for explanations. For changes, analyze affected callers and dependencies
before inspecting relevant source, and follow the existing user-approval process
before editing. Refresh only an existing graph after approved changes.

When absent, silently skip Graphify and use native Copilot tools and standard
permissions to read, search, debug, explain, and modify Java source. Do not block,
warn, ask for Graphify approval, suggest /repo-analyzer, or automatically generate
a graph. This fallback takes precedence over graph-evidence and refresh rules for
ordinary prompts. Explicit manual /repo-analyzer extraction, update, query, merge,
and API documentation requests retain their existing workflows.
