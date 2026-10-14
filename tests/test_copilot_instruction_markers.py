"""Managed-section migration, update messages and preservation regressions."""
import pytest
from graphify import copilot_install as integration
from graphify import install as installer


def test_vscode_creates_updates_and_reports_current_template(tmp_path, monkeypatch, capsys):
    original = installer._always_on
    template = [original("vscode-instructions")]
    monkeypatch.setattr(installer, "_always_on", lambda name: template[0] if name == "vscode-instructions" else original(name))
    installer.vscode_install(tmp_path)
    assert "(created)" in capsys.readouterr().out
    path = tmp_path / ".github/copilot-instructions.md"
    path.write_text("Team rules stay.\n\n" + path.read_text())
    template[0] += "\nUpdated template rule.\n"
    installer.vscode_install(tmp_path)
    output = capsys.readouterr().out
    assert "(updated)" in output and "already configured" not in output
    first = path.read_bytes()
    assert "Team rules stay." in first.decode() and "Updated template rule." in first.decode()
    installer.vscode_install(tmp_path)
    assert "already up to date" in capsys.readouterr().out
    assert path.read_bytes() == first
    assert path.read_text().count(integration.INSTRUCTION_START) == 1


@pytest.mark.parametrize("managed", [True, False])
def test_duplicate_and_legacy_sections_preserve_project_content(tmp_path, managed):
    path = tmp_path / ".github/copilot-instructions.md"
    path.parent.mkdir()
    section = "## graphify\nOld rules.\n"
    if managed:
        section = integration.INSTRUCTION_START + "\n" + section + integration.INSTRUCTION_END + "\n"
    project = "# Team\nKeep this.\n"
    middle = "## Project requirements\nKeep these too.\n"
    tail = "# Deployment\nKeep deployment instructions.\n"
    path.write_text(project + section + middle + section + tail)
    integration.install(tmp_path)
    text = path.read_text()
    assert all(part in text for part in (project, middle, tail))
    assert "Old rules" not in text
    assert text.count("## graphify") == 1
    integration.install(tmp_path)
    assert path.read_text() == text
    integration.uninstall(tmp_path)
    assert all(part in path.read_text() for part in (project, middle, tail))
    assert integration.INSTRUCTION_START not in path.read_text()


def test_literal_heading_and_marker_mentions_are_preserved(tmp_path):
    path = tmp_path / ".github/copilot-instructions.md"
    path.parent.mkdir()
    project = "Mention `## graphify` inline.\nUse `<!-- graphify:start -->` and `<!-- graphify:end -->`.\n```md\n## graphify\nExample text.\n```\n### graphify\nCustom notes.\n"
    path.write_text(project)
    integration.install(tmp_path)
    assert project in path.read_text()


def test_unbalanced_markers_leave_original_file_untouched(tmp_path):
    path = tmp_path / ".github/copilot-instructions.md"
    path.parent.mkdir()
    original = integration.INSTRUCTION_START + "\nProject rules.\n"
    path.write_text(original)
    with pytest.raises(ValueError, match="Unbalanced"):
        integration.install(tmp_path)
    assert path.read_text() == original


def test_current_managed_block_in_middle_is_not_moved(tmp_path, capsys):
    path = tmp_path / ".github/copilot-instructions.md"
    path.parent.mkdir()
    block = integration.INSTRUCTION_START + "\n" + installer._always_on("vscode-instructions").strip() + "\n" + integration.INSTRUCTION_END + "\n"
    original = "# Team\nKeep this.\n\n" + block + "\n## Deployment\nKeep this too.\n"
    path.write_text(original, encoding="utf-8")
    integration.install(tmp_path)
    assert "already up to date" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == original
