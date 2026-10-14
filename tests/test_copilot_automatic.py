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


def test_missing_graph_requires_explicit_initial_skill(repo):
    hooks.graph_path(repo).unlink()
    result = prompt(repo, "Explain cancellation")
    assert "/repo-analyzer first" in result["systemMessage"]
    tool(repo)
    assert tool(repo, "bash", {"command": "graphify extract . --no-cluster"})["permissionDecision"] == "deny"
    prompt(repo, "/repo-analyzer .")
    tool(repo)
    assert tool(repo, "skill", {"name": "repo-analyzer"}) == {}
    assert tool(repo, "bash", {"command": "graphify extract . --no-cluster"})["permissionDecision"] == "ask"
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
    assert tool(repo, "bash", {"command": "graphify update ."})["permissionDecision"] == "deny"


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
    assert hooks.handle("pre", {"sessionId": "session", "toolName": "edit"}, other)["permissionDecision"] == "deny"


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
