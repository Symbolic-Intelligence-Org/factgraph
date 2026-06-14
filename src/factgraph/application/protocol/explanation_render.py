from __future__ import annotations

from collections.abc import Mapping
from math import prod
from typing import Any

from factgraph.application.explain.evidence_tree import (
    EvidenceAtom,
    EvidenceGraph,
    EvidenceJoin,
    EvidenceRule,
    EvidenceTree,
    EvidenceTimeline,
)
from factgraph.application.protocol.certainty import Certainty
from factgraph.application.protocol.rule import _PROJECTION_ID_PREFIX


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


def narrate_evidence(
    graph: EvidenceGraph,
    *,
    row: object | None = None,
    status: str = "passed",
    failure_class: str | None = None,
) -> tuple[str, ...]:
    """Render a human narrative for a paths-model EvidenceGraph."""
    if not isinstance(graph, EvidenceGraph):
        raise ValueError("graph must be EvidenceGraph")
    if not graph.paths:
        return ()
    lines: list[str] = []
    trees = tuple(path for path in graph.paths if isinstance(path, EvidenceTree))
    conclusion_rule = _first_head_rule(graph)
    conclusion_text = _rule_label(conclusion_rule) if conclusion_rule is not None else graph.graph_id
    prefix = "Conclusion" if status == "passed" else "NOT concluded"
    failure_suffix = f" ({failure_class})" if status == "failed" and failure_class else ""
    lines.append(f"{prefix} ── {conclusion_text}{failure_suffix}")
    context = _graph_context_line(graph, row=row, trees=trees, head_rule=conclusion_rule)
    if context is not None:
        lines.append(f"              {context}")
    produces = _produces_line(graph.subject_binding, head_rule=conclusion_rule)
    if produces is not None:
        lines.append(f"      {produces}")
    global_derivation = _global_derivation_line(trees)
    if global_derivation is not None:
        lines.append(global_derivation)
    lines.extend(_multi_path_probability_lines(graph, trees=trees))

    for path_index, path in enumerate(graph.paths):
        if isinstance(path, EvidenceTree):
            lines.extend(
                _narrate_tree(
                    path,
                    path_index=path_index,
                    include_path_header=len(trees) > 1,
                    include_derivation=len(trees) <= 1,
                )
            )
        elif isinstance(path, EvidenceTimeline):
            lines.extend(_narrate_timeline(path))
    return tuple(lines)


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


def _first_head_rule(graph: EvidenceGraph) -> EvidenceRule | None:
    for path in graph.paths:
        if not isinstance(path, EvidenceTree):
            continue
        for rule in path.rules:
            if rule.role == "head":
                return rule
    return None


def _rule_label(rule: EvidenceRule) -> str:
    if _is_projection_rule_id(rule.rule_id):
        return _projection_label(rule)
    return rule.repr_text or rule.rule_id


def _rule_id_label(rule: EvidenceRule) -> str:
    if _is_projection_rule_id(rule.rule_id):
        return _projection_label(rule)
    return rule.rule_id


def _is_projection_rule_id(rule_id: str) -> bool:
    return rule_id.startswith(_PROJECTION_ID_PREFIX)


def _projection_label(rule: EvidenceRule) -> str:
    ports = ", ".join(str(port) for port in rule.ports)
    return f"projection({ports})" if ports else "projection"


def _graph_context_line(
    graph: EvidenceGraph,
    *,
    row: object | None,
    trees: tuple[EvidenceTree, ...],
    head_rule: EvidenceRule | None,
) -> str | None:
    run_token = _run_token(graph, row=row)
    if run_token is None:
        return None
    head_label = _rule_id_label(head_rule) if head_rule is not None else "head"
    path_label = _path_tail_label(trees)
    status = _tail_status(trees) if trees else _paths_tail_status(graph.paths)
    certainty = _certainty_suffix(_row_or_graph_certainty(row, graph), context="summary")
    return f"[{head_label} · {run_token} · {path_label}]  {status}{certainty}"


def _row_or_graph_certainty(row: object | None, graph: EvidenceGraph) -> Certainty | None:
    row_certainty = getattr(row, "certainty", None)
    if isinstance(row_certainty, Certainty):
        return row_certainty
    return graph.certainty if isinstance(graph.certainty, Certainty) else None


def _run_token(graph: EvidenceGraph, *, row: object | None) -> str | None:
    metadata_run_id = graph.metadata.get("run_id")
    if isinstance(metadata_run_id, str) and metadata_run_id:
        return _run_token_from_string(metadata_run_id)
    row_id = getattr(row, "row_id", None)
    if isinstance(row_id, str) and row_id:
        token = _run_token_from_string(row_id)
        if token is not None:
            return token
    return _metadata_token(graph)


def _run_token_from_string(value: str) -> str | None:
    if value.startswith("run_v1:"):
        body = value.removeprefix("run_v1:")
        head = body.split(":", 1)[0][:8]
        return f"run_v1:{head}…" if head else "run_v1:…"
    return value if value else None


def _path_tail_label(trees: tuple[EvidenceTree, ...]) -> str:
    if not trees:
        return "c0"
    labels = tuple(tree.tree_id or f"c{idx}" for idx, tree in enumerate(trees))
    base = "|".join(labels)
    if len(trees) <= 1:
        return base
    concluded = next((tree.tree_id or f"c{idx}" for idx, tree in enumerate(trees) if tree.status == "holds"), None)
    return f"{base} (concluded via {concluded})" if concluded is not None else base


def _tail_status(trees: tuple[EvidenceTree, ...]) -> str:
    if not trees:
        return "not_reached"
    if any(tree.status == "holds" for tree in trees):
        return "holds"
    if any(tree.status == "fails" for tree in trees):
        return "fails"
    return "not_reached"


def _paths_tail_status(paths: tuple[Any, ...]) -> str:
    if any(getattr(path, "status", None) == "holds" for path in paths):
        return "holds"
    if any(getattr(path, "status", None) == "fails" for path in paths):
        return "fails"
    return "not_reached"


def _metadata_token(graph: EvidenceGraph) -> str | None:
    for key in ("run_id", "result_id", "candidate_id"):
        value = graph.metadata.get(key)
        if isinstance(value, str) and value:
            return _run_token_from_string(value) or _short_token(value)
    return None


def _short_token(value: str) -> str:
    return value if len(value) <= 12 else value[:12]


def _produces_line(subject_binding: Mapping[str, Any], *, head_rule: EvidenceRule | None) -> str | None:
    values = dict(subject_binding)
    if not values and head_rule is not None:
        values = dict(head_rule.ports)
    if not values:
        return None
    ordered_keys: list[str] = []
    if head_rule is not None:
        ordered_keys.extend(str(key) for key in head_rule.ports)
        ordered_keys.extend(str(key) for key in values if str(key) not in ordered_keys)
    else:
        ordered_keys.extend(sorted(str(key) for key in values))
    parts = [f"{key} = {_display_binding_value(values[key])}" for key in ordered_keys if key in values]
    return "produces:  " + ",  ".join(parts)


def _display_binding_value(value: Any) -> str:
    if isinstance(value, Mapping) and "value" in value:
        return str(value["value"])
    return str(value)


def _narrate_tree(
    tree: EvidenceTree,
    *,
    path_index: int,
    include_path_header: bool,
    include_derivation: bool,
) -> tuple[str, ...]:
    labels = _rule_labels_for_tree(tree)
    degenerate_body = _degenerate_tree_body(tree)
    degenerate_title = _degenerate_tree_title(tree) if degenerate_body is not None else None
    lines: list[str] = []
    if include_path_header:
        certainty = _tree_path_probability_suffix(tree)
        lines.append(f"▸ Path {tree.tree_id or f'c{path_index}'}  [{tree.status}]{certainty}")
    if include_derivation and degenerate_body is None:
        derivation = _derivation_line(tree, labels=labels)
        if derivation is not None:
            lines.append(derivation)
    for join in tree.joins:
        lines.append(_join_line(join, labels=labels))
    for rule in sorted(tree.rules, key=_paths_rule_sort_key):
        if rule.role == "head" and degenerate_body is not None:
            continue
        omit_label = rule is degenerate_body and rule.repr_text == degenerate_title
        lines.extend(_narrate_rule(rule, labels=labels, tree=tree, omit_label=omit_label))
    return tuple(lines)


def _narrate_timeline(timeline: EvidenceTimeline) -> tuple[str, ...]:
    certainty = _certainty_suffix(
        timeline.certainty if isinstance(timeline.certainty, Certainty) else None,
        context="summary",
    )
    lines = [f"▸ Timeline {timeline.timeline_id}  [{timeline.status}]{certainty}"]
    events = sorted(
        (event for event in timeline.events if isinstance(event, EvidenceAtom)),
        key=lambda event: (event.timestep is None, -1 if event.timestep is None else event.timestep, event.atom_id),
    )
    for event in events:
        timestep = "?" if event.timestep is None else str(event.timestep)
        rendered = event.repr_text or type(event.form).__name__
        verdict = _paths_verdict_status(event.verdict)
        suffix = _certainty_suffix(_verdict_certainty(event.verdict), context="atom")
        lines.append(f"    t={timestep}  {rendered}  [{event.atom_id}]  {verdict}{suffix}")
    return tuple(lines)


def _rule_labels_for_tree(tree: EvidenceTree) -> Mapping[str, str]:
    counts: dict[str, int] = {}
    for rule in tree.rules:
        if rule.role == "head":
            continue
        counts[rule.rule_id] = counts.get(rule.rule_id, 0) + 1
    labels: dict[str, str] = {}
    for rule in tree.rules:
        label = _rule_id_label(rule)
        if counts.get(rule.rule_id, 0) > 1 and rule.role != "head":
            label = f"{label}[{rule.occurrence_alias}]"
        labels[rule.occurrence_alias] = label
    return labels


def _degenerate_tree_body(tree: EvidenceTree) -> EvidenceRule | None:
    head = next((rule for rule in tree.rules if rule.role == "head"), None)
    bodies = tuple(rule for rule in tree.rules if rule.role == "body")
    if head is None or len(bodies) != 1:
        return None
    body = bodies[0]
    if body.rule_id == head.rule_id and not head.atoms:
        return body
    return None


def _degenerate_tree_title(tree: EvidenceTree) -> str | None:
    head = next((rule for rule in tree.rules if rule.role == "head"), None)
    return _rule_label(head) if head is not None else None


def _derivation_line(tree: EvidenceTree, *, labels: Mapping[str, str]) -> str | None:
    head = next((rule for rule in tree.rules if rule.role == "head"), None)
    bodies = tuple(rule for rule in tree.rules if rule.role == "body")
    if head is None:
        return None
    head_label = labels.get(head.occurrence_alias, head.rule_id)
    if not bodies:
        return f"  Derivation:  {head_label}"
    body_text = " AND ".join(labels.get(rule.occurrence_alias, rule.rule_id) for rule in bodies)
    return f"  Derivation:  {head_label} <= ( {body_text} ){_derivation_probability_suffix(tree, bodies)}"


def _global_derivation_line(trees: tuple[EvidenceTree, ...]) -> str | None:
    if len(trees) <= 1:
        return None
    head = next((rule for tree in trees for rule in tree.rules if rule.role == "head"), None)
    if head is None:
        return None
    head_label = _rule_id_label(head)
    groups: list[str] = []
    for tree in trees:
        labels = _rule_labels_for_tree(tree)
        bodies = tuple(rule for rule in tree.rules if rule.role == "body")
        if not bodies:
            groups.append("( true )")
            continue
        body_text = " AND ".join(labels.get(rule.occurrence_alias, rule.rule_id) for rule in bodies)
        groups.append(f"( {body_text} )")
    return f"  Derivation:  {head_label} <= " + " OR ".join(groups)


def _join_line(join: EvidenceJoin, *, labels: Mapping[str, str]) -> str:
    left = labels.get(join.left.rule_occurrence_alias, join.left.rule_occurrence_alias)
    right = labels.get(join.right.rule_occurrence_alias, join.right.rule_occurrence_alias)
    return (
        "               join:  "
        f"{left}.{join.left.port_name} = "
        f"{right}.{join.right.port_name}  [{join.status}]"
    )


def _narrate_rule(
    rule: EvidenceRule,
    *,
    labels: Mapping[str, str],
    tree: EvidenceTree | None = None,
    omit_label: bool = False,
) -> tuple[str, ...]:
    head_suffix = " [head]" if rule.role == "head" else ""
    label = _rule_label(rule)
    rule_label = labels.get(rule.occurrence_alias, rule.rule_id)
    probability = "" if tree is None else _rule_probability_suffix(rule, tree)
    if omit_label:
        lines = [f"  {rule_label}{head_suffix}  [{rule.status}]{probability}"]
    else:
        lines = [f'  {rule_label}{head_suffix} ── "{label}"  [{rule.status}]{probability}']
    for atom in rule.atoms:
        lines.append(_narrate_atom(atom))
    return tuple(lines)


def _narrate_atom(atom: EvidenceAtom) -> str:
    rendered = atom.repr_text or type(atom.form).__name__
    suffix = _certainty_suffix(_verdict_certainty(atom.verdict), context="atom")
    return f"       {_verdict_icon(atom.verdict)} {rendered}  [{atom.atom_id}]  {_paths_verdict_status(atom.verdict)}{suffix}"


def _verdict_certainty(verdict: object) -> Certainty | None:
    certainty = getattr(verdict, "certainty", None)
    return certainty if isinstance(certainty, Certainty) else None


def _certainty_suffix(certainty: Certainty | None, *, context: str) -> str:
    if certainty is None:
        return ""
    if certainty.lo == 1.0 and certainty.hi == 1.0:
        return ""
    if context == "atom":
        if certainty.kind == "probabilistic" and certainty.lo == certainty.hi:
            return f" (p = {_format_probability(certainty.lo)})"
        return f" [{_format_probability(certainty.lo)}, {_format_probability(certainty.hi)}]"
    if certainty.kind == "probabilistic" and certainty.lo == certainty.hi:
        return f" with probability {_format_probability(certainty.lo)}"
    return f" with bound [{_format_probability(certainty.lo)}, {_format_probability(certainty.hi)}]"


def _multi_path_probability_lines(graph: EvidenceGraph, *, trees: tuple[EvidenceTree, ...]) -> tuple[str, ...]:
    if len(trees) <= 1:
        return ()
    probability = _point_probability(graph.certainty if isinstance(graph.certainty, Certainty) else None)
    if probability is None or probability == 1.0:
        return ()
    operands = tuple(
        branch_probability
        for tree in trees
        if tree.status == "holds"
        if (branch_probability := _metadata_probability(tree.metadata.get("branch_probability"))) is not None
    )
    if len(operands) >= 2 and _matches_noisy_or(operands, probability):
        factors = " × ".join(f"(1−{_format_probability(value)})" for value in operands)
        return (f"      probability:  1 − {factors} = {_format_probability(probability)}",)
    return (f"      probability:  {_format_probability(probability)}",)


def _tree_path_probability_suffix(tree: EvidenceTree) -> str:
    probability = _metadata_probability(tree.metadata.get("branch_probability"))
    if probability is None or probability == 1.0:
        return ""
    return f" (p = {_format_probability(probability)})"


def _derivation_probability_suffix(tree: EvidenceTree, bodies: tuple[EvidenceRule, ...]) -> str:
    result = _metadata_probability(tree.metadata.get("branch_probability"))
    if result is None or result == 1.0:
        return ""
    occ_probabilities = tree.metadata.get("occ_probabilities")
    if not isinstance(occ_probabilities, Mapping):
        return f"  (p = {_format_probability(result)})"
    operands = _occurrence_probability_operands(tree, bodies, occ_probabilities)
    if operands is None:
        return f"  (p = {_format_probability(result)})"
    if len(operands) >= 2 and _matches_product(operands, result):
        return f"  (p = {_probability_product_text(operands)} = {_format_probability(result)})"
    head_probability = _metadata_probability(tree.metadata.get("head_probability"))
    if head_probability is not None:
        head_operands = (head_probability, *operands)
        if _matches_product(head_operands, result):
            return f"  (p = {_probability_product_text(head_operands)} = {_format_probability(result)})"
    return f"  (p = {_format_probability(result)})"


def _occurrence_probability_operands(
    tree: EvidenceTree,
    bodies: tuple[EvidenceRule, ...],
    occ_probabilities: Mapping[str, Any],
) -> tuple[float, ...] | None:
    operands: list[float] = []
    for rule in bodies:
        value = _metadata_probability(occ_probabilities.get(rule.occurrence_alias))
        if value is None:
            return None
        operands.append(value)
    return tuple(operands)


def _rule_probability_suffix(rule: EvidenceRule, tree: EvidenceTree) -> str:
    if rule.role == "head":
        return ""
    occ_probabilities = tree.metadata.get("occ_probabilities")
    if not isinstance(occ_probabilities, Mapping):
        return ""
    result = _metadata_probability(occ_probabilities.get(rule.occurrence_alias))
    if result is None or result == 1.0:
        return ""
    operands = tuple(_atom_probability(atom) for atom in rule.atoms)
    if not operands or any(value is None for value in operands):
        return f"  (p = {_format_probability(result)})"
    operand_values = tuple(value for value in operands if value is not None)
    if len(operand_values) > 1 and _matches_product(operand_values, result):
        return f"  (p = {_probability_product_text(operand_values)} = {_format_probability(result)})"
    return f"  (p = {_format_probability(result)})"


def _atom_probability(atom: EvidenceAtom) -> float | None:
    certainty = _verdict_certainty(atom.verdict)
    if certainty is None:
        return None
    if certainty.kind == "boolean" and certainty.lo == 1.0 and certainty.hi == 1.0:
        return 1.0
    if certainty.kind == "probabilistic" and certainty.lo == certainty.hi:
        return certainty.lo
    return None


def _point_probability(certainty: Certainty | None) -> float | None:
    if certainty is None:
        return None
    if certainty.kind != "probabilistic" or certainty.lo != certainty.hi:
        return None
    return certainty.lo


def _metadata_probability(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _matches_product(values: tuple[float, ...], result: float) -> bool:
    return abs(prod(values) - result) <= 1e-9 * max(1.0, abs(result))


def _matches_noisy_or(values: tuple[float, ...], result: float) -> bool:
    return abs((1.0 - prod(tuple(1.0 - value for value in values))) - result) <= 1e-9 * max(1.0, abs(result))


def _probability_product_text(values: tuple[float, ...]) -> str:
    return " × ".join(_format_probability(value) for value in values)


def _format_probability(value: float) -> str:
    return f"{value:g}"


def _verdict_icon(verdict: object) -> str:
    status = _paths_verdict_status(verdict)
    if status == "holds":
        return "✓"
    if status == "not_reached":
        return "○"
    return "✗"


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
