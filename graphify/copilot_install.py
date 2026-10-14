"""Idempotent repository-scoped hook installation shared by Copilot hosts."""
from __future__ import annotations
import json
from pathlib import Path
import shlex
import sys

HOOK_FILE = Path(".github/hooks/graphify.json")
EVENTS = {"userPromptSubmitted": "prompt", "userPromptTransformed": "transformed",
          "preToolUse": "pre", "postToolUse": "post", "agentStop": "stop", "sessionEnd": "end"}


def _owned(entry: object) -> bool:
    return isinstance(entry, dict) and any(
        any(marker in str(entry.get(field, "")) for marker in
            ("-m graphify.copilot_hooks ", "-m graphify.copilot hook "))
        for field in ("bash", "powershell", "command", "windows"))


def _load(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "hooks": {}}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("version", 1) != 1:
        raise ValueError(f"Unsupported hook configuration at {path}; left untouched")
    hooks = value.get("hooks", {})
    if not isinstance(hooks, dict) or any(not isinstance(v, list) for v in hooks.values()):
        raise ValueError(f"Invalid hook event lists at {path}; left untouched")
    return value


def _commands(event: str, root: Path) -> dict:
    python = Path(sys.executable).as_posix()
    root_text = root.resolve().as_posix()
    args = [python, "-m", "graphify.copilot_hooks", event, "--root", root_text]
    posix = " ".join(shlex.quote(arg) for arg in args)
    def psquote(arg):
        return "'" + arg.replace("'", "''") + "'"
    powershell = f"& {psquote(python)} -m graphify.copilot_hooks {event} --root {psquote(root_text)}"
    return {"type": "command", "bash": posix, "powershell": powershell,
            "cwd": root_text, "timeoutSec": 30}


def install(project_dir: Path) -> None:
    from graphify.install import _always_on, _replace_or_append_section
    from graphify.paths import write_text_atomic
    root = project_dir.resolve()
    path = root / HOOK_FILE
    config = _load(path)
    config["version"] = 1
    hooks = config.setdefault("hooks", {})
    for event, items in list(hooks.items()):
        hooks[event] = [entry for entry in items if not _owned(entry)]
        if not hooks[event]:
            del hooks[event]
    for event, handler in EVENTS.items():
        hooks.setdefault(event, []).append(_commands(handler, root))
    instructions = root / ".github/copilot-instructions.md"
    content = instructions.read_text(encoding="utf-8") if instructions.exists() else ""
    begin, end = "<!-- graphify-first:start -->", "<!-- graphify-first:end -->"
    while begin in content and end in content:
        start, finish = content.index(begin), content.index(end) + len(end)
        if finish <= start:
            break
        content = content[:start] + content[finish:]
    updated = _replace_or_append_section(content, "## graphify", _always_on("vscode-instructions"))
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, json.dumps(config, indent=2) + "\n")
    write_text_atomic(instructions, updated)
    print(f"  automatic hooks  ->  {path} (prompt, context, tool approval, stop, cleanup)")
    print(f"  repo instructions -> {instructions} (Graphify section updated)")
    print("  Restart Copilot in this trusted repository. Hooks must be enabled.")
    print("  Copilot CLI/Agent Host: prompt query + transformed evidence + native tool approval.")
    print("  VS Code Local Agent: prompt query + first-tool/stop evidence + native tool approval.")
    print("  Chat modes without tool hooks use instructions only; strict execution is unavailable.")


def uninstall(project_dir: Path) -> None:
    from graphify.install import _remove_marker_section
    from graphify.paths import write_text_atomic
    root = project_dir.resolve()
    path = root / HOOK_FILE
    if path.exists():
        config = _load(path)
        hooks = config.get("hooks", {})
        changed = False
        for event, entries in list(hooks.items()):
            kept = [entry for entry in entries if not _owned(entry)]
            if len(kept) != len(entries):
                changed = True
                if kept:
                    hooks[event] = kept
                else:
                    del hooks[event]
        if changed:
            if not hooks and set(config) <= {"version", "hooks"}:
                path.unlink()
            else:
                write_text_atomic(path, json.dumps(config, indent=2) + "\n")
            print(f"  automatic hooks removed -> {path}")
    instructions = root / ".github/copilot-instructions.md"
    if instructions.exists():
        cleaned = _remove_marker_section(instructions.read_text(encoding="utf-8"), "## graphify")
        if cleaned is not None:
            if cleaned:
                write_text_atomic(instructions, cleaned + "\n")
            else:
                instructions.unlink()
