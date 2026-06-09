from __future__ import annotations

from factgraph.application.explain.evidence_tree import EvidenceGraph, EvidenceRule, EvidenceTree


def walk_evidence(
    graph: EvidenceGraph,
    *,
    row: object | None = None,
    status: str = "passed",
    failure_class: str | None = None,
) -> tuple[str, ...]:
    """Walk a paths-model EvidenceGraph and produce deterministic NL lines."""
    if not isinstance(graph, EvidenceGraph):
        raise ValueError("graph must be EvidenceGraph")
    return _walk_paths_evidence(graph, row=row, status=status, failure_class=failure_class)


def _walk_paths_evidence(
    graph: EvidenceGraph,
    *,
    row: object | None,
    status: str,
    failure_class: str | None,
) -> tuple[str, ...]:
    lines: list[str] = []
    for path_index, path in enumerate(graph.paths):
        if not isinstance(path, EvidenceTree):
            lines.append(f"Timeline[{path_index}]: {path.status}")
            continue
        prefix = "Conclusion" if status == "passed" else "NOT concluded"
        row_id = getattr(row, "row_id", None)
        row_suffix = f" [{row_id}]" if isinstance(row_id, str) and row_id else ""
        failure_suffix = f" ({failure_class})" if status == "failed" and failure_class else ""
        lines.append(f"{prefix}: {path.tree_id}{row_suffix}{failure_suffix}")
        for rule in sorted(path.rules, key=_paths_rule_sort_key):
            lines.extend(_render_paths_rule(rule))
        for join in path.joins:
            lines.append(
                f"  Join: {join.left.rule_occurrence_alias}.{join.left.port_name} = "
                f"{join.right.rule_occurrence_alias}.{join.right.port_name} — {join.status}"
            )
    return tuple(lines)


def _paths_rule_sort_key(rule: EvidenceRule) -> tuple[int, str]:
    role_rank = 0 if rule.role == "head" else 1
    return (role_rank, rule.occurrence_alias)


def _render_paths_rule(rule: EvidenceRule) -> tuple[str, ...]:
    label = f'Rule "{rule.rule_id}"' if rule.role == "head" else f'Body "{rule.occurrence_alias}"'
    lines = [f"  {label}: {rule.status}"]
    for atom in rule.atoms:
        rendered = atom.repr_text or type(atom.form).__name__
        lines.append(f"    Atom: {rendered} — {_paths_verdict_status(atom.verdict)}")
    return tuple(lines)


def _paths_verdict_status(verdict: object) -> str:
    name = type(verdict).__name__
    if name == "Holds":
        return "holds"
    if name == "NotReached":
        return "not_reached"
    return "fails"
