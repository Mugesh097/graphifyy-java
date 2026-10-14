"""Executable-hook contract tests; host UI behavior still needs a live smoke test."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from graphify import copilot_hooks as hooks
from graphify import copilot_install as integration
from graphify import install as installer


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks.tempfile, "gettempdir", lambda: str(tmp_path / "runtime"))
    root = tmp_path / "repo"
    root.mkdir()
    java = root / "CancellationService.java"
    java.write_text("class CancellationService {}", encoding="utf-8")
    graph = hooks.graph_path(root)
    graph.parent.mkdir()
    graph.write_text(json.dumps({"directed": False, "multigraph": False, "graph": {},
        "nodes": [{"id": "cancel", "label": "CancellationService.cancelTransaction",
                   "source_file": java.name, "source_location": "L1", "file_type": "code"},
                  {"id": "api", "label": "CancellationController.cancel",
                   "source_file": java.name, "source_location": "L1", "file_type": "code"}],
        "links": [{"source": "api", "target": "cancel", "relation": "calls"}]}), encoding="utf-8")
    os.utime(java, (1, 1))
    return root


def prompt(repo, question, host="cli", query=hooks.analyze):
    key = "sessionId" if host == "cli" else "session_id"
    return hooks.handle("prompt", {key: "session", "prompt": question}, repo, query=query)


def tool(repo, name="view", args=None, host="cli", event="pre"):
    payload = ({"sessionId": "session", "toolName": name, "toolArgs": args or {"path": "CancellationService.java"}}
               if host == "cli" else
               {"session_id": "session", "tool_name": name, "tool_input": args or {"filePath": "CancellationService.java"}})
    return hooks.handle(event, payload, repo, query=hooks.analyze)


@pytest.mark.parametrize("host", ["cli", "vscode"])
@pytest.mark.parametrize("question", [
    "What is CancellationService?", "Explain the cancellation API.",
    "Explain future transaction cancellation handling.", "Where is cancelTransaction called?",
    "Debug the cancellation failure.", "Fix CancellationService.cancelTransaction.",
    "Add cancellation validation.", "Explain the complete project flow.",
])
def test_automatic_prompt_queries_actual_question_without_source_reads(repo, host, question, monkeypatch):
    seen = []
    original_read = Path.read_text
    def guarded_read(path, *args, **kwargs):
        assert path.suffix != ".java", "Java source was read before graph evidence"
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    def query(root, actual):
        seen.append(actual)
        return hooks.analyze(root, actual)
    result = prompt(repo, question, host, query)
    assert seen == [question]
    assert "Graph evidence" in result["systemMessage"]
    first = tool(repo, host=host)
    assert first["permissionDecision"] == "deny"
    assert first["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert question in first["permissionDecisionReason"]
    second = tool(repo, host=host)
    assert second["permissionDecision"] == ("ask" if hooks._IMPLEMENT.search(question) else "deny")


@pytest.mark.parametrize("host", ["cli", "vscode"])
def test_graph_impact_contains_callers_and_callees(repo, host):
    prompt(repo, "Fix cancelTransaction", host)
    result = tool(repo, host=host)
    assert "CancellationController" in result["permissionDecisionReason"]
    assert "CancellationService" in result["permissionDecisionReason"]


@pytest.mark.parametrize("name", ["edit", "apply_patch", "powershell", "run_in_terminal", "mcp_custom_tool", "task"])
def test_native_approval_never_inferred_from_tool_arguments(repo, name):
    prompt(repo, "Fix cancellation")
    tool(repo)
    result = tool(repo, name, {"approved": True, "command": "arbitrary code"})
    assert result["permissionDecision"] == "ask"
    assert "explicit approval" in result["permissionDecisionReason"]


@pytest.mark.parametrize("host", ["cli", "vscode"])
def test_one_approval_covers_multiple_files_tests_and_refresh(repo, host):
    prompt(repo, "Fix cancellation", host)
    tool(repo, host=host)  # deliver graph evidence first
    assert tool(repo, host=host)["permissionDecision"] == "ask"
    tool(repo, host=host, event="post")  # host completed the approved operation
    for name, args in [
        ("view", {"path": "Other.java"}),
        ("grep", {"pattern": "cancel"}),
        ("edit", {"path": "CancellationService.java"}),
        ("apply_patch", {"path": "Other.java"}),
        ("bash", {"command": "pytest"}),
        ("mcp_custom_tool", {}),
        ("bash", {"command": "graphify update ."}),
    ]:
        assert tool(repo, name, args, host) == {}


def test_continuation_preserves_approval_but_new_task_resets_it(repo):
    prompt(repo, "Fix cancellation")
    tool(repo)
    assert tool(repo)["permissionDecision"] == "ask"
    tool(repo, event="post")
    prompt(repo, "Continue")
    tool(repo)
    assert tool(repo, "edit") == {}
    prompt(repo, "Add cancellation validation")
    tool(repo)
    assert tool(repo, "edit")["permissionDecision"] == "ask"


def test_yes_without_host_completion_does_not_approve(repo):
    prompt(repo, "Fix cancellation")
    tool(repo)
    tool(repo)
    prompt(repo, "Yes")
    tool(repo)
    assert tool(repo, "edit")["permissionDecision"] == "ask"


def test_unrelated_post_or_unapproved_tool_does_not_grant_approval(repo):
    prompt(repo, "Fix cancellation")
    tool(repo)
    assert tool(repo)["permissionDecision"] == "ask"
    tool(repo, "edit", event="post")
    assert tool(repo, "edit")["permissionDecision"] == "ask"
    # Denied/cancelled native asks have no matching completed post event.
    assert tool(repo, "edit")["permissionDecision"] == "ask"


def test_rejection_and_session_end_clear_existing_task_approval(repo):
    prompt(repo, "Fix cancellation")
    tool(repo)
    tool(repo)
    tool(repo, event="post")
    prompt(repo, "No")
    tool(repo)
    assert tool(repo, "edit")["permissionDecision"] == "deny"
    hooks.handle("end", {"sessionId": "session"}, repo)
    prompt(repo, "Fix cancellation")
    tool(repo)
    assert tool(repo, "edit")["permissionDecision"] == "ask"


@pytest.mark.parametrize("approve", [True, False])
def test_host_permission_contract_only_executes_approved_edit(repo, approve):
    prompt(repo, "Fix cancellation")
    tool(repo)
    source = repo / "CancellationService.java"
    before = source.read_bytes()
    decision = tool(repo, "edit")["permissionDecision"]
    # Simulate the documented host contract, not a Graphify-issued permission.
    if decision == "ask" and approve:
        source.write_text("class CancellationService { void cancel() {} }", encoding="utf-8")
        tool(repo, "edit", event="post")
    assert (source.read_bytes() != before) == approve
    if approve:
        result = hooks.handle("stop", {"sessionId": "session"}, repo, query=hooks.analyze)
        assert result["decision"] == "block"
        assert "graphify update" in result["reason"]


def test_rejection_blocks_source_and_mutations(repo):
    prompt(repo, "Fix cancellation")
    tool(repo)
    before = (repo / "CancellationService.java").read_bytes()
    prompt(repo, "No")
    tool(repo)
    assert tool(repo, "edit")["permissionDecision"] == "deny"
    assert tool(repo, "view")["permissionDecision"] == "deny"
    assert (repo / "CancellationService.java").read_bytes() == before


def test_missing_graph_silently_preserves_native_workflow_and_manual_skill(repo):
    hooks.graph_path(repo).unlink()
    result = prompt(repo, "Explain cancellation")
    assert result == {}
    assert tool(repo) == {}
    assert tool(repo, "edit") == {}
    assert prompt(repo, "/repo-analyzer .") == {}
    assert tool(repo, "skill", {"name": "repo-analyzer"}) == {}
    assert tool(repo, "bash", {"command": "graphify extract . --no-cluster"}) == {}
    assert not hooks.graph_path(repo).exists()


@pytest.mark.parametrize("kind", ["mtime", "marker", "deleted"])
def test_stale_graph_queries_persisted_evidence_but_blocks_source(repo, kind):
    java = repo / "CancellationService.java"
    if kind == "mtime":
        future = hooks.graph_path(repo).stat().st_mtime + 10
        os.utime(java, (future, future))
    elif kind == "marker":
        (hooks.graph_path(repo).parent / "needs_update").touch()
    else:
        java.unlink()
    result = prompt(repo, "Fix cancellation")
    assert "outdated" in result["systemMessage"]
    assert "CancellationService" in result["systemMessage"]
    tool(repo)
    assert tool(repo)["permissionDecision"] == "deny"
    assert tool(repo, "bash", {"command": "graphify update ."})["permissionDecision"] == "ask"
    assert tool(repo, "bash", {"command": "graphify update .; cat CancellationService.java"})["permissionDecision"] == "deny"


def test_source_changed_after_query_is_blocked(repo):
    prompt(repo, "Fix cancellation")
    tool(repo)
    (repo / "New.java").write_text("class New {}")
    assert tool(repo)["permissionDecision"] == "deny"


def test_transformed_context_preserves_actual_prompt(repo):
    question = "Explain cancellation"
    prompt(repo, question)
    output = hooks.handle("transformed", {"sessionId": "session", "prompt": question,
        "transformedPrompt": "Original model content"}, repo)
    assert output["modifiedTransformedPrompt"].startswith("Original model content")
    assert "CancellationService" in output["modifiedTransformedPrompt"]
    assert tool(repo)["permissionDecision"] == "deny"  # explanation source reads remain denied


def test_stop_delivers_evidence_without_tools_once(repo):
    prompt(repo, "Explain cancellation")
    payload = {"session_id": "session", "stop_hook_active": False}
    result = hooks.handle("stop", payload, repo)
    assert result["hookSpecificOutput"]["decision"] == "block"
    assert "CancellationService" in result["reason"]
    assert hooks.handle("stop", payload, repo) == {}


def test_failed_query_does_not_reuse_previous_readiness(repo):
    prompt(repo, "Fix cancellation")
    tool(repo)
    def fail(*args):
        raise TimeoutError("timed out")
    prompt(repo, "Fix another issue", query=fail)
    assert "timed out" in tool(repo)["permissionDecisionReason"]
    assert tool(repo, "edit")["permissionDecision"] == "deny"


def test_corrupt_graph_reports_error_without_source_fallback(repo):
    hooks.graph_path(repo).write_text("{broken")
    result = prompt(repo, "Fix cancellation")
    assert "failed" in result["systemMessage"]
    tool(repo)
    assert tool(repo)["permissionDecision"] == "deny"


def test_insufficient_evidence_does_not_authorize_source_fallback(repo):
    result = prompt(repo, "Fix nonexistentUnrelatedSymbolXYZ")
    assert "No matching nodes" in result["systemMessage"]
    tool(repo)
    assert tool(repo)["permissionDecision"] == "deny"


def test_explanation_about_update_method_is_not_an_edit_request(repo):
    prompt(repo, "What does the cancellation update method do?")
    tool(repo)
    assert tool(repo)["permissionDecision"] == "deny"


def test_graph_refinement_preserves_manual_commands_without_shell_bypass(repo):
    prompt(repo, "Explain cancellation")
    tool(repo)
    assert tool(repo, "bash", {"command": 'graphify query "cancellation" --graph graphify-out/graph.json'}) == {}
    assert tool(repo, "bash", {"command": 'graphify explain "cancellation"; cat CancellationService.java'})["permissionDecision"] == "deny"
    assert tool(repo, "bash", {"command": 'graphify query "cancellation" --graph ../other.json'})["permissionDecision"] == "deny"
    assert tool(repo, "bash", {"command": 'graphify query "cancellation"', "cwd": "../elsewhere"})["permissionDecision"] == "deny"


def test_existing_api_documentation_still_uses_native_write_approval(repo):
    prompt(repo, "/repo-analyzer api-docs")
    tool(repo)
    assert tool(repo, "bash", {"command": "graphify api-docs --graph graphify-out/graph.json --output api-docs"})["permissionDecision"] == "ask"


def test_no_prompt_cannot_authorize_graph_creation(repo):
    hooks.graph_path(repo).unlink()
    tool(repo)
    assert tool(repo, "bash", {"command": "graphify update ."}) == {}
    assert not hooks.graph_path(repo).exists()


def test_missing_session_pre_hook_returns_explicit_deny(repo):
    proc = subprocess.run([sys.executable, "-m", "graphify.copilot_hooks", "pre", "--root", str(repo)],
        input=json.dumps({"tool_name": "edit"}), text=True, capture_output=True, timeout=30)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["permissionDecision"] == "deny"


def test_state_isolated_by_session_and_repository(repo):
    prompt(repo, "Fix cancellation")
    tool(repo)
    result = hooks.handle("pre", {"sessionId": "other", "toolName": "edit"}, repo)
    assert result["permissionDecision"] == "deny"
    other = repo.parent / "other"
    other.mkdir()
    assert hooks.handle("pre", {"sessionId": "session", "toolName": "edit"}, other) == {}


def test_hook_entrypoint_real_subprocess(repo):
    proc = subprocess.run([sys.executable, "-m", "graphify.copilot_hooks", "prompt", "--root", str(repo)],
        input=json.dumps({"sessionId": "real-process", "prompt": "Explain cancellation"}),
        text=True, capture_output=True, encoding="utf-8", timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert "CancellationService" in json.loads(proc.stdout)["systemMessage"]


@pytest.mark.parametrize("surface", ["cli", "cli-project", "vscode"])
def test_installer_routes_install_hooks_preserve_configuration_and_repeat(repo, monkeypatch, surface):
    monkeypatch.chdir(repo)
    target = repo / integration.HOOK_FILE
    target.parent.mkdir(parents=True)
    unrelated = {"type": "command", "bash": "echo user-hook"}
    target.write_text(json.dumps({"version": 1, "hooks": {"preToolUse": [unrelated]}}))
    instructions = repo / ".github/copilot-instructions.md"
    instructions.write_text("# Team rules\nKeep this.\n\n## graphify\nOld rules\n\n## Other\nKeep too.\n")
    def install():
        if surface == "vscode":
            installer.vscode_install(repo)
        elif surface == "cli-project":
            installer._project_install("copilot", repo)
        else:
            installer.install(platform="copilot", project_dir=repo)
    install()
    first = target.read_bytes(), instructions.read_bytes()
    install()
    assert first == (target.read_bytes(), instructions.read_bytes())
    config = json.loads(target.read_text())
    assert config["hooks"]["preToolUse"][0] == unrelated
    assert set(integration.EVENTS) <= config["hooks"].keys()
    assert all(sum(integration._owned(e) for e in config["hooks"][event]) == 1 for event in integration.EVENTS)
    assert instructions.read_text().count("## graphify") == 1
    assert "Keep this." in instructions.read_text() and "Keep too." in instructions.read_text()
    assert "Old rules" not in instructions.read_text()
    integration.uninstall(repo)
    assert json.loads(target.read_text())["hooks"] == {"preToolUse": [unrelated]}
    assert "Keep this." in instructions.read_text() and "## graphify" not in instructions.read_text()


@pytest.mark.parametrize("bad", ["{", "[]", '{"hooks": {"preToolUse": 1}}', '{"version": 99}'])
def test_invalid_config_left_untouched(repo, bad):
    path = repo / integration.HOOK_FILE
    path.parent.mkdir(parents=True)
    path.write_text(bad)
    with pytest.raises(ValueError):
        integration.install(repo)
    assert path.read_text() == bad


def test_commands_quote_paths_and_do_not_interpolate_user_prompt(repo, monkeypatch):
    monkeypatch.setattr(sys, "executable", "C:/Program Files/Python/python.exe")
    command = integration._commands("prompt", repo)
    assert command["powershell"].startswith("& 'C:/Program Files/Python/python.exe'")
    assert "-m graphify.copilot_hooks prompt" in command["bash"]
    assert "$" not in command["powershell"]


@pytest.mark.parametrize("surface", ["cli", "cli-project", "vscode", "dedicated-vscode"])
@pytest.mark.parametrize("available", [True, False])
def test_installed_hook_commands_query_graph_before_source_or_silently_skip(repo, monkeypatch, surface, available):
    import shlex
    from graphify.copilot import install as install_mcp
    monkeypatch.chdir(repo)
    if not available:
        hooks.graph_path(repo).unlink()
    for _ in range(2):
        if surface == "cli":
            installer.install(platform="copilot", project_dir=repo)
        elif surface == "cli-project":
            installer._project_install("copilot", repo)
        elif surface == "vscode":
            installer.vscode_install(repo)
        else:
            install_mcp(repo, "vscode")
    config = json.loads((repo / integration.HOOK_FILE).read_text())
    env = dict(os.environ, PYTHONPATH=str(Path(hooks.__file__).resolve().parent.parent))
    outputs = []
    for event, payload in [
        ("userPromptSubmitted", {"sessionId": "installed", "prompt": "Explain cancelTransaction"}),
        ("preToolUse", {"sessionId": "installed", "toolName": "view", "toolArgs": {"path": "CancellationService.java"}}),
    ]:
        entries = [entry for entry in config["hooks"][event] if integration._owned(entry)]
        assert len(entries) == 1
        proc = subprocess.run(shlex.split(entries[0]["bash"]), cwd=repo, env=env,
            input=json.dumps(payload), text=True, capture_output=True, timeout=30)
        assert proc.returncode == 0, proc.stderr
        outputs.append(json.loads(proc.stdout))
    if available:
        # cancelTransaction exists only in graph.json, not in the Java fixture.
        assert "CancellationService.cancelTransaction" in outputs[0]["systemMessage"]
        assert str(hooks.graph_path(repo).resolve()) in outputs[0]["systemMessage"]
        assert outputs[1]["permissionDecision"] == "deny"
        assert "Queried existing graph" in outputs[1]["permissionDecisionReason"]
    else:
        assert outputs == [{}, {}]
        assert not hooks.graph_path(repo).exists()


def test_installer_migrates_old_hooks_without_duplicates_and_preserves_user_hooks(repo):
    from graphify.copilot import install as install_mcp
    path = repo / integration.HOOK_FILE
    path.parent.mkdir(parents=True)
    user = {"type": "command", "command": "echo user-hook"}
    old = {"type": "command", "command": "python -m graphify.copilot hook --event PreToolUse"}
    path.write_text(json.dumps({"hooks": {"PreToolUse": [user, old]}}))
    instructions = repo / ".github/copilot-instructions.md"
    instructions.write_text("Team rules.\n<!-- graphify-first:start -->\nOld conflicting policy.\n<!-- graphify-first:end -->\n")
    for run in (install_mcp, integration.install, install_mcp):
        run(repo, "vscode") if run is install_mcp else run(repo)
    config = json.loads(path.read_text())
    assert config["hooks"]["PreToolUse"] == [user]
    assert "Old conflicting policy" not in instructions.read_text()
    assert "Team rules." in instructions.read_text()
    for event in integration.EVENTS:
        assert sum(integration._owned(e) for e in config["hooks"][event]) == 1


def test_missing_graph_does_not_query_scan_or_create_session_state(repo, monkeypatch):
    hooks.graph_path(repo).unlink()
    def forbidden(*args, **kwargs):
        raise AssertionError("Graphify ran without a graph")
    monkeypatch.setattr(hooks, "_state_path", forbidden)
    monkeypatch.setattr(hooks, "_source_signature", forbidden)
    for event in ("prompt", "pre", "post", "transformed", "stop", "end"):
        assert hooks.handle(event, {"prompt": "Fix cancellation"}, repo, query=forbidden) == {}


def test_graph_deleted_during_session_restores_native_operations(repo):
    prompt(repo, "Fix cancellation")
    tool(repo)
    hooks.graph_path(repo).unlink()
    assert tool(repo, "edit") == {}
    assert hooks.handle("stop", {"sessionId": "session"}, repo) == {}


@pytest.mark.parametrize("host", ["cli", "vscode"])
@pytest.mark.parametrize("question", ["Explain cancellation", "Debug cancellation", "Modify cancellation"])
def test_current_repository_graph_wins_over_installation_path(repo, host, question):
    configured = repo.parent / "previous-repository"
    configured.mkdir()
    key = "sessionId" if host == "cli" else "session_id"
    observed = []
    def query(root, prompt):
        observed.append(root)
        return hooks.analyze(root, prompt)
    result = hooks.handle("prompt", {key: "current", "cwd": str(repo), "prompt": question},
                          configured, query=query)
    assert observed == [repo]
    assert str(hooks.graph_path(repo)) in result["systemMessage"]
    assert "CancellationService.cancelTransaction" in result["systemMessage"]


@pytest.mark.parametrize("event", ["prompt", "transformed", "pre", "post", "stop", "end"])
def test_current_repository_without_graph_ignores_old_repository_graph(repo, event):
    current = repo.parent / "current-repository"
    current.mkdir()
    (current / ".git").write_text("gitdir: elsewhere")
    def forbidden(*args):
        raise AssertionError("Queried the old repository instead of skipping Graphify")
    assert hooks.handle(event, {"cwd": str(current), "prompt": "Explain cancellation"},
                        repo, query=forbidden) == {}
    assert not hooks.graph_path(current).exists()


def test_subdirectory_uses_repository_graph_and_nested_repo_does_not_inherit_it(repo):
    nested = repo / "src/main/java"
    nested.mkdir(parents=True)
    assert hooks._repository_root(repo, {"cwd": str(nested)}) == repo
    separate = repo / "nested-repository"
    separate.mkdir()
    (separate / ".git").mkdir()
    assert hooks._repository_root(repo, {"cwd": str(separate)}) == separate
    assert hooks.handle("pre", {"cwd": str(separate)}, repo) == {}


@pytest.mark.parametrize("available", [True, False])
def test_hook_entrypoint_resolves_host_repository_before_availability_check(repo, available):
    configured = repo.parent / "previous-repository"
    configured.mkdir()
    if not available:
        hooks.graph_path(repo).unlink()
    proc = subprocess.run([sys.executable, "-m", "graphify.copilot_hooks", "prompt",
        "--root", str(configured)], input=json.dumps({"session_id": "host-current",
        "cwd": str(repo), "prompt": "Explain cancellation"}), text=True,
        capture_output=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert ("Queried existing graph" in result.get("systemMessage", "")) is available
    if not available:
        assert result == {}
