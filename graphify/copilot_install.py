"""Idempotent repository-scoped hook installation shared by Copilot hosts."""
from __future__ import annotations
import json
import re
from pathlib import Path
import shlex
import sys

HOOK_FILE = Path(".github/hooks/graphify.json")
INSTRUCTION_START = "<!-- graphify:start -->"
INSTRUCTION_END = "<!-- graphify:end -->"
_MANAGED_PATTERN = re.compile(r"^" + re.escape(INSTRUCTION_START) + r"[ \t]*\r?\n.*?^" + re.escape(INSTRUCTION_END) + r"[ \t]*(?:\r?\n|$)", re.M | re.S)
EVENTS = {"userPromptSubmitted": "prompt", "userPromptTransformed": "transformed",
          "preToolUse": "pre", "postToolUse": "post", "agentStop": "stop", "sessionEnd": "end"}


def _owned(entry: object) -> bool:
    return isinstance(entry, dict) and any(
        "-m graphify.copilot_hooks " in str(entry.get(field, ""))
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
    from graphify.install import _always_on
    from graphify.paths import write_text_atomic
    root = project_dir.resolve()
    path = root / HOOK_FILE
    config = _load(path)
    config["version"] = 1
    hooks = config.setdefault("hooks", {})
    for event, items in list(hooks.items()):
        hooks[event] = [entry for entry in items if not _owned(entry)]
    for event, handler in EVENTS.items():
        hooks.setdefault(event, []).append(_commands(handler, root))
    instructions = root / ".github/copilot-instructions.md"
    content = instructions.read_text(encoding="utf-8") if instructions.exists() else ""
    block = INSTRUCTION_START + "\n" + _always_on("vscode-instructions").strip() + "\n" + INSTRUCTION_END + "\n"
    retained = _without_graphify_instructions(content)
    matches = list(_MANAGED_PATTERN.finditer(content))
    if len(matches) == 1 and retained == _MANAGED_PATTERN.sub("", content):
        match = matches[0]
        updated = content[:match.start()] + block + content[match.end():]
    else:
        updated = (retained.rstrip() + "\n\n" if retained.strip() else "") + block
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, json.dumps(config, indent=2) + "\n")
    if updated != content:
        write_text_atomic(instructions, updated)
        print(f"  repo instructions -> {instructions} ({'updated' if content else 'created'})")
    else:
        print(f"  repo instructions -> {instructions} (already up to date)")
    print(f"  automatic hooks  ->  {path} (prompt, context, tool approval, stop, cleanup)")
    print("  Restart Copilot in this trusted repository. Hooks must be enabled.")
    print("  Copilot CLI/Agent Host: prompt query + transformed evidence + native tool approval.")
    print("  VS Code Local Agent: prompt query + first-tool/stop evidence + native tool approval.")
    print("  Chat modes without tool hooks use instructions only; strict execution is unavailable.")


def uninstall(project_dir: Path) -> None:
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
        original = instructions.read_text(encoding="utf-8")
        cleaned = _without_graphify_instructions(original)
        if cleaned != original:
            if cleaned:
                write_text_atomic(instructions, cleaned + "\n")
            else:
                instructions.unlink()


def _without_graphify_instructions(content: str) -> str:
    """Remove complete owned blocks and migrate legacy exact H2 sections only."""
    starts = re.findall(r"(?m)^" + re.escape(INSTRUCTION_START) + r"[ \t]*\r?$", content)
    ends = re.findall(r"(?m)^" + re.escape(INSTRUCTION_END) + r"[ \t]*\r?$", content)
    if len(starts) != len(ends):
        raise ValueError("Unbalanced Graphify instruction markers; file left untouched")
    for match in _MANAGED_PATTERN.finditer(content):
        if INSTRUCTION_START in match.group()[len(INSTRUCTION_START):]:
            raise ValueError("Nested Graphify instruction markers; file left untouched")
    content = _MANAGED_PATTERN.sub("", content)
    if re.search(r"(?m)^" + re.escape(INSTRUCTION_START) + r"[ \t]*\r?$", content) or re.search(r"(?m)^" + re.escape(INSTRUCTION_END) + r"[ \t]*\r?$", content):
        raise ValueError("Invalid Graphify instruction markers; file left untouched")
    retained, skipping, fence = [], False, None
    for line in content.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            fence = None if fence == marker else (marker if fence is None else fence)
        elif fence is None:
            if re.fullmatch(r"[ \t]*##[ \t]+graphify[ \t]*", line.rstrip("\r\n")):
                skipping = True
            elif re.match(r"^#{1,2}[ \t]+", line):
                skipping = False
        if not skipping:
            retained.append(line)
    return "".join(retained)
