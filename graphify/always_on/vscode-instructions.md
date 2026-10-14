## graphify

First check whether `graphify-out/graph.json` exists. When absent, silently skip
Graphify and continue native Copilot explanations, debugging, searches, and code
changes with standard tools and permissions. Do not block, warn, request Graphify
approval, suggest `/repo-analyzer`, or automatically generate a graph.
The following graph rules apply only when the graph exists. Explicit manual
`/repo-analyzer` requests remain supported.

For any question about this repo's architecture, structure, components, or how to add/modify/find
code, your first action should be `graphify query "<question>"` when `graphify-out/graph.json`
exists. Use `graphify path "<A>" "<B>"` for relationship questions and `graphify explain "<concept>"`
for focused-concept questions. These return a scoped subgraph, usually much smaller than the full
report or raw grep output.

Triggers: "how do Iâ€¦", "where isâ€¦", "what does â€¦ do", "add/modify a <component>",
"explain the architecture", or anything that depends on how files or classes relate.

If `graphify-out/wiki/index.md` exists, use it for broad navigation. Read `graphify-out/GRAPH_REPORT.md`
only for broad architecture review or when query/path/explain do not surface enough context.
When the graph exists, answer explanations from graph evidence and report gaps.
Do not search or read Java source to replace graph analysis. For implementation or
debugging, inspect only relevant source after graph impact analysis and approval.

Use the graph for the requested repository, passed with `--graph`. Merging is optional;
do not automatically prefer merged scope. Generate reviewable Java API references with
`graphify api-docs`. Let Copilot choose presentation style; distinguish recorded evidence
from source audits and inference. Report missing graph evidence explicitly.

For code changes, analyze graph dependencies and affected callers before inspecting
source, and obtain approval once for the implementation plan before editing.
Do not repeat Graphify approval for each file, planned test or graph refresh.
Continue within the approved scope with native host permissions. A new task
requires its own approval; rejection stops edits. Update only
an existing graph after changes. Generate a graph only when explicitly requested.
