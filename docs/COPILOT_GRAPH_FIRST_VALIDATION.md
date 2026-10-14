# Graph-first validation — 2026-10-12

This is the historical validation of the original mandatory integration. Its
missing-graph generation behavior is superseded by the conditional workflow
validated in [COPILOT_CONDITIONAL_VALIDATION.md](COPILOT_CONDITIONAL_VALIDATION.md).

Implementation uses the existing Java extractor, incremental updater, query
engine, reverse dependency analysis, documentation generator and MCP server.
The new integration adds no runtime dependency beyond the existing MCP extra.

| Requirement scenario | Executed validation | Result |
| --- | --- | --- |
| Explain GET /v1/remote/addons/details | Temporary Java controller → service → repository fixture; graph context and real stdio MCP call | Passed |
| Classes depending on AddonService | Stored graph neighborhood includes calling controller and directed relationships | Passed |
| Add addonStatus | Impact context includes response DTO before a simulated source edit; subsequent MCP refresh persists new field | Passed |
| Missing graph | First context request builds graph through existing Java rebuild | Passed |
| Changed graph | Edit/add/delete Java source, then incremental synchronization; unchanged graph keeps its timestamp | Passed |
| Invalid graph | Preserve corrupt JSON, rebuild; missing graph after deletion also recovers | Passed |
| Existing documentation | Existing generator produces endpoint Markdown and index including service/repository evidence; existing skill installation regressions | Passed |
| Automatic Local flow | Prompt hook queries first, pre-tool hook supplies graph evidence, Stop synchronizes edits | Passed at hook function level |
| Installation | Existing MCP server retained, JSONC accepted, instruction block idempotent, both IDE schemas generated | Passed |
| Insufficient graph evidence | Unknown symbol returns no candidate files and explicit limitations | Passed |
| Java inventory | Current-graph freshness does not read Java text | Passed |
| Changed extraction exclusions | Stops queries with scope error instead of delivering preserved stale evidence | Passed |

Final focused command:

```text
python -m pytest tests/test_graph_first.py tests/test_java_api_docs.py tests/test_repo_analyzer_install.py tests/test_serve.py tests/test_serve_http.py tests/test_java_watch.py tests/test_java_detect.py -q
236 passed
```

Real stdio MCP coverage initializes an independent server process, lists its
tools, requests repository context with a missing graph, requests impact,
changes a DTO, calls refresh, and queries the updated graph. It ran with MCP
2.3.0. Existing compatibility code for MCP 1.x was preserved; 1.x was not
separately installed/tested in this environment.

Broad suite run with bundled Git available: **1,828 passed, 66 skipped, four
failed**. One failure was the new exclusion-scope regression, corrected and
included in the final 236 passing focused tests. A final `pytest --lf` confirmed
the only remaining failures are these three unchanged Obsidian export tests:

- `test_obsidian_long_ascii_label_does_not_crash`
- `test_obsidian_distinct_long_labels_sharing_prefix_do_not_collide`
- `test_obsidian_wikilink_resolves_after_truncation`

They fail with Windows `FileNotFoundError` when the combined temporary directory
and generated 200-character filename exceeds the host's path limit. No Obsidian
export code was modified. An earlier broad run also lacked Git on PATH; after
adding the bundled Git directory, the Git hook suite passed **70 tests, eight
skipped**. Optional dependency tests account for other skips.

`graphify update .` succeeded, generating **42 nodes, 55 edges, 10 communities**
and updating graph.json, graph.html and GRAPH_REPORT.md. This analyzer is Java-only;
the checkout's own graph covers its Java fixtures/examples, not its Python
implementation. Architecture analysis therefore used the existing architecture
document and Python modules; the initially requested report/wiki were absent.

VS Code and IntelliJ configuration files were generated for the included
`examples/order-service` repository. No logged-in Copilot IDE session was
available for testing. Natural-language model compliance, IDE hook discovery,
IDE permissions, tests executed by Copilot, and the live `/repo-analyzer` slash
command remain manual acceptance checks. These are not claimed as automated
end-to-end IDE successes. See COPILOT_GRAPH_FIRST.md for setup and trace checks.
