# Conditional Graphify and scoped approval

This change starts from the restored `11f4a231` implementation (branch restore
commit `052f266`). It retains the existing query engine, hook schema, lifecycle
events, installers, MCP tools and graph-generation commands.

## Root causes and fixes

1. **Missing graph:** `analyze()` emitted a `/repo-analyzer` prerequisite, while
   `handle()` created state before availability checks and reached denial gates.
   Availability is now checked before state, queries, source scans or permissions.
   Missing graphs return an empty hook result and leave native Copilot in control.
2. **Repeated approval:** every implementation tool returned `ask`, with no
   request-scoped approval state. One explicit approval now covers the full agreed
   implementation plan. A matching host-completed operation records approval;
   later operations return no Graphify permission override. Failed or unmatched
   post events, tool-provided approval flags and a bare conversational yes do not
   create approval. New prompts reset it; short continuations retain only existing
   approval. Repository/session isolation and state expiry remain intact.
3. **Instruction updates:** the shared automatic installer and `vscode_install()`
   both wrote the file. The second pass could report “no change” after the first
   pass updated it. Legacy heading replacement also kept earlier duplicates.
   The shared installer is now the single writer. It creates, updates or reports
   `already up to date` using explicit managed boundaries, migrates exact legacy
   `## graphify` sections, removes duplicates and preserves other project sections.
   A current block stays in place. Unbalanced markers leave the file untouched.

## Managed instructions

```md
<!-- graphify:start -->
## graphify
...latest packaged Graphify instructions...
<!-- graphify:end -->
```

The human-edited templates live under `tools/skillgen/fragments/`. Packaged skills,
always-on instructions and expected snapshots are regenerated together.

## Approval boundaries

The agent must present the exact agreed scope and remain within it. The hook latch
is scoped by repository, session and current request, not a permanent permission.
It relies on host completion of the matching operation that received the initial
`ask`. It does not parse transcripts or claim to prove approval of a particular
natural-language plan. There is no native hook API attesting the complete plan or
its file list; plan fidelity remains an agent/host responsibility. Graphify never
returns `allow` to bypass mandatory host permissions. Rejection continues to deny
source operations and no edit is executed by Graphify itself.

Missing graphs use the host's ordinary approval policy rather than adding a
Graphify-specific request. Manual extraction, updates, API docs and queries remain
available when requested.

## Modified files

- `graphify/copilot_hooks.py`: availability-first fallback and request approval.
- `graphify/copilot_install.py`: managed instruction updates and migration.
- `graphify/install.py`: remove the redundant VS Code instruction writer.
- `tools/skillgen/fragments/copilot-automatic.md` and
  `tools/skillgen/fragments/always-on/vscode-instructions.md`: current policies.
- `graphify/skill-copilot.md`, `graphify/skill-vscode.md`,
  `graphify/always_on/vscode-instructions.md` and their three expected snapshots.
- `tests/test_copilot_automatic.py` and `tests/test_copilot_instruction_markers.py`.
- `README.md`, `docs/COPILOT_AUTOMATIC.md`, and this report.

## Installation and verification

Install the latest branch into your selected Python environment, then activate it.
For a uv-managed installation from this repository:

```powershell
uv tool install --force --from "git+https://github.com/Mugesh097/graphifyy-java.git@feat/automatic-copilot-graph-first" graphifyy
```

From the Java repository run the installer for your host:

```powershell
graphify copilot install --project
# Or:
graphify vscode install
```

Restart Copilot with hooks enabled and the workspace trusted. For CLI, inspect
`/hooks`; for VS Code, inspect the hook output/debug channel in an Agent-capable
session. Ask ordinary explanation and change prompts; no Graphify slash command
is required. Graph queries occur inside the prompt hook, not necessarily as a
separate visible model tool call.

Verification cases:

1. With a graph, an explanation retrieves graph evidence before Java searches.
2. Approve a change plan once; subsequent related edits use normal permissions
   without more Graphify asks. A different request asks again.
3. Reject the change and verify no source edits occur.
4. In a disposable graph-less repository, prompts and source tools proceed normally.
5. Install over stale/duplicate instructions; project rules survive and one managed
   block remains. Install again and verify `already up to date` and identical bytes.

Automated coverage launches registered commands from Java repositories without
`PYTHONPATH` overrides and checks both CLI and VS Code payload formats. Native
permission boundaries are simulated; no logged-in Copilot UI was driven. Disabled
hooks, unsupported Ask/inline modes and host indexing cannot be intercepted by this
adapter. Intent classification retains the existing common-English-verb behavior.

The final regression run passed **311 tests**, covering all three requirements,
existing installation upgrades, MCP stdio/HTTP, Java watch/update/detection and API
documentation. All **50** generated artifacts matched their templates and snapshots.
`graphify update .` completed with 42 nodes, 55 edges and 10 communities.
