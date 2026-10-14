"""Graph-first orchestration over the existing Java extractor and MCP queries."""
from __future__ import annotations

import contextlib
import io
import json
import logging
import os
import re
from pathlib import Path
import threading

from graphify.paths import GRAPHIFY_OUT

log = logging.getLogger(__name__)
_lock = threading.RLock()


@contextlib.contextmanager
def _synchronization_lock(out: Path):
    """Serialize hooks and MCP refreshes across processes, including Windows."""
    out.mkdir(parents=True, exist_ok=True)
    with (out / ".graph_first.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def ensure_graph(root: Path, *, refresh: bool = False, existing_only: bool = False) -> dict:
    """Stat Java files; extract only changed files. Never read source to answer queries.

    A legacy graph without our inventory is compared against its generation time.
    File discovery honours the same exclusions as update/watch. Stat inventory
    detects additions/deletions as well as edits; it is not a source-content scan.
    """
    from graphify.detect import detect
    from graphify.watch import _read_build_excludes, _read_build_gitignore, _rebuild_code
    from graphify.serve import _load_graph

    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Repository directory does not exist: {root}")
    out = root / GRAPHIFY_OUT
    path = out / "graph.json"
    # Optional integrations must not create output directories, inventories or
    # graphs when there is no graph. Explicit generation retains legacy behavior.
    if existing_only and not path.is_file():
        return {"graph_path": str(path), "available": False, "refreshed": False,
                "changed_files": []}
    inventory = out / ".graph_first_inventory.json"
    with _lock, _synchronization_lock(out):
        if existing_only and not path.is_file():
            return {"graph_path": str(path), "available": False, "refreshed": False,
                    "changed_files": []}
        detected = detect(root, extra_excludes=_read_build_excludes(out) or None,
                          gitignore=_read_build_gitignore(out), java_inventory=True)
        if detected.get("walk_errors"):
            raise RuntimeError("Cannot check graph freshness: incomplete repository enumeration")
        current = {}
        for raw in detected["files"]["code"]:
            file = Path(raw).resolve()
            if file.suffix.lower() == ".java" and file.is_relative_to(root):
                stat = file.stat()
                current[file.relative_to(root).as_posix()] = [stat.st_mtime_ns, stat.st_size]
        valid = False
        if path.exists():
            try:
                _load_graph(str(path))
                valid = True
            except (SystemExit, Exception):
                log.warning("Invalid graph at %s; rebuilding Java evidence", path)
        previous = None
        try:
            saved = json.loads(inventory.read_text(encoding="utf-8"))
            if saved.get("graph_stamp") == [path.stat().st_mtime_ns, path.stat().st_size]:
                previous = saved["files"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        if previous is not None:
            changed = [root / f for f in current.keys() | previous.keys()
                       if current.get(f) != previous.get(f)]
        elif valid:
            graph = _load_graph(str(path))
            known = set()
            for _, data in graph.nodes(data=True):
                raw = data.get("source_file")
                if raw:
                    file = Path(raw)
                    file = (file if file.is_absolute() else root / file).resolve()
                    if file.suffix.lower() == ".java" and file.is_relative_to(root):
                        known.add(file.relative_to(root).as_posix())
            changed = [root / f for f, stamp in current.items()
                       if stamp[0] > path.stat().st_mtime_ns or f not in known]
            changed += [root / f for f in known - current.keys()]
        else:
            changed = []
        # An excluded-but-still-existing file is a scope change, not a deletion.
        # The existing builder preserves such paths; do not serve evidence that
        # silently violates the new scope or discard semantic evidence ourselves.
        scope_changed = any(file.exists() and file.relative_to(root).as_posix() not in current
                            for file in changed)
        if scope_changed:
            raise RuntimeError("Java extraction scope changed. Regenerate the graph with the new "
                               "exclusions before querying; existing evidence was preserved.")
        rebuilt = refresh or not valid or bool(changed)
        if rebuilt:
            backup = None
            if not valid and path.exists():
                # The incremental merge refuses corrupt JSON. Preserve it for
                # diagnostics and allow the existing builder to start cleanly.
                import time
                backup = path.with_name(f"graph.invalid-{time.time_ns()}.json")
                path.replace(backup)
            # Keep extraction/report logs off the MCP protocol's stdout.
            try:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    ok = _rebuild_code(root, changed_paths=changed if valid and not refresh else None,
                                       no_cluster=True, block_on_lock=True)
                if not ok:
                    raise RuntimeError("Graph refresh failed: " + output.getvalue()[-2000:])
                _load_graph(str(path))
            except BaseException:
                if backup is not None:
                    backup.replace(path)
                raise
            log.info("Graph refresh %s: %s", root, output.getvalue())
        out.mkdir(parents=True, exist_ok=True)
        stamp = path.stat()
        temp = inventory.with_suffix(".tmp")
        temp.write_text(json.dumps({"files": current,
                                   "graph_stamp": [stamp.st_mtime_ns, stamp.st_size]}), encoding="utf-8")
        os.replace(temp, inventory)
        return {"graph_path": str(path), "refreshed": rebuilt,
                "changed_files": [str(f.relative_to(root)) for f in changed]}


def repository_context(graph, question: str, *, impact: bool = False, depth: int = 3) -> dict:
    """Return persisted evidence and candidate files, preserving ambiguity."""
    from graphify.serve import _query_graph_text, _score_nodes, _query_terms, _bfs, _true_edge_records
    from graphify.api_docs import endpoint_catalog, evidence
    depth = max(1, min(int(depth), 6))
    verbs = set(re.findall(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b", question.upper()))
    endpoints = [n for n, verb, route in endpoint_catalog(graph)
                 if re.search(r"(?<![\w/])" + re.escape(route) + r"(?![\w/])", question)
                 and (not verbs or verb in verbs or verb == "*")]
    seeds = endpoints or [n for score, n in _score_nodes(graph, _query_terms(question))[:8]
                          if score > 0]
    nodes, _ = _bfs(graph.to_undirected(as_view=True), seeds, depth) if seeds else (set(), [])
    for endpoint in endpoints:
        flow_nodes, _ = evidence(graph, endpoint)
        nodes.update(flow_nodes)
    # Include every member of candidate files (DTO fields, owners and mappings),
    # then reverse dependency traversal for impact. No guessed edges are added.
    files = {graph.nodes[n].get("source_file") for n in nodes}
    if impact:
        members = [n for n, d in graph.nodes(data=True) if d.get("source_file") in files]
        from graphify.affected import affected_nodes
        for member in members:
            nodes.update(hit.node_id for hit in affected_nodes(graph, member, depth=depth))
    files = sorted({str(graph.nodes[n]["source_file"]) for n in nodes
                    if graph.nodes[n].get("source_file")})
    relationships = [{"source": s, "target": t, "relation": d.get("relation"),
                      "confidence": d.get("confidence"), "source_file": d.get("source_file"),
                      "source_location": d.get("source_location")}
                     for s, t, d in _true_edge_records(graph) if s in nodes and t in nodes]
    return {"question": question, "intent": "change" if impact else "understanding",
            "context": _query_graph_text(graph, question, depth=depth, token_budget=6000),
            "candidate_files": files, "candidate_nodes": sorted(nodes, key=str),
            "relationships": relationships[:500],
            "relationships_truncated": len(relationships) > 500,
            "limitations": "Static graph evidence only. Candidates are not proof of runtime impact. "
                            "Resolve ambiguous symbols; read candidate files for missing implementation details. "
                            "Validate changes and call refresh_graph before finishing."}
