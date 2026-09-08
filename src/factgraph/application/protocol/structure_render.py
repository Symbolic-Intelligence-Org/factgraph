from __future__ import annotations

from collections.abc import Mapping

from factgraph.application.protocol.rule import _PROJECTION_ID_PREFIX

from .rule_structure import (
    RuleStructure,
    StructureAtom,
    StructureBranch,
    StructureJoin,
    StructureOccurrence,
)


def narrate_structure(structure: RuleStructure) -> tuple[str, ...]:
    """Render static RuleStructure lines aligned to Explanation.narrate()."""
    if not isinstance(structure, RuleStructure):
        raise ValueError("structure must be RuleStructure")  # noqa: TRY004 - Public renderer; shares the evidence codec ValueError contract.
    if not structure.branches:
        return ()

    lines: list[str] = []
    head = _first_head_occurrence(structure)
    conclusion_text = _rule_label(head) if head is not None else structure.head_rule_id
    lines.append(f"Structure ── {conclusion_text}")

    global_derivation = _global_derivation_line(structure.branches)
    if global_derivation is not None:
        lines.append(global_derivation)

    include_path_header = len(structure.branches) > 1
    for path_index, branch in enumerate(structure.branches):
        lines.extend(
            _narrate_branch(
                branch,
                path_index=path_index,
                include_path_header=include_path_header,
                include_derivation=not include_path_header,
            )
        )
    return tuple(lines)


def _narrate_branch(
    branch: StructureBranch,
    *,
    path_index: int,
    include_path_header: bool,
    include_derivation: bool,
) -> tuple[str, ...]:
    labels = _occurrence_labels_for_branch(branch)
    degenerate_body = _degenerate_branch_body(branch)
    degenerate_title = _degenerate_branch_title(branch) if degenerate_body is not None else None
    lines: list[str] = []
    if include_path_header:
        lines.append(f"▸ Path {branch.branch_id or f'c{path_index}'}")
    if include_derivation and degenerate_body is None:
        derivation = _derivation_line(branch, labels=labels)
        if derivation is not None:
            lines.append(derivation)
    for join in branch.joins:
        lines.append(_join_line(join, labels=labels))
    for occurrence in sorted(branch.occurrences, key=_occurrence_sort_key):
        if occurrence.role == "head" and degenerate_body is not None:
            continue
        omit_label = occurrence is degenerate_body and occurrence.repr_text == degenerate_title
        lines.extend(_narrate_occurrence(occurrence, labels=labels, omit_label=omit_label))
    return tuple(lines)


def _first_head_occurrence(structure: RuleStructure) -> StructureOccurrence | None:
    for branch in structure.branches:
        for occurrence in branch.occurrences:
            if occurrence.role == "head":
                return occurrence
    return None


def _occurrence_sort_key(occurrence: StructureOccurrence) -> tuple[int, str]:
    role_rank = 0 if occurrence.role == "head" else 1
    return (role_rank, occurrence.occurrence_alias)


def _occurrence_labels_for_branch(branch: StructureBranch) -> Mapping[str, str]:
    counts: dict[str, int] = {}
    for occurrence in branch.occurrences:
        if occurrence.role == "head":
            continue
        counts[occurrence.rule_id] = counts.get(occurrence.rule_id, 0) + 1

    labels: dict[str, str] = {}
    for occurrence in branch.occurrences:
        label = _rule_id_label(occurrence)
        if counts.get(occurrence.rule_id, 0) > 1 and occurrence.role != "head":
            label = f"{label}[{occurrence.occurrence_alias}]"
        labels[occurrence.occurrence_alias] = label
    return labels


def _degenerate_branch_body(branch: StructureBranch) -> StructureOccurrence | None:
    head = next((occurrence for occurrence in branch.occurrences if occurrence.role == "head"), None)
    bodies = tuple(occurrence for occurrence in branch.occurrences if occurrence.role == "body")
    if head is None or len(bodies) != 1:
        return None
    body = bodies[0]
    if body.rule_id == head.rule_id and not head.atoms:
        return body
    return None


def _degenerate_branch_title(branch: StructureBranch) -> str | None:
    head = next((occurrence for occurrence in branch.occurrences if occurrence.role == "head"), None)
    return _rule_label(head) if head is not None else None


def _derivation_line(branch: StructureBranch, *, labels: Mapping[str, str]) -> str | None:
    head = next((occurrence for occurrence in branch.occurrences if occurrence.role == "head"), None)
    bodies = tuple(occurrence for occurrence in branch.occurrences if occurrence.role == "body")
    if head is None:
        return None
    head_label = labels.get(head.occurrence_alias, head.rule_id)
    if not bodies:
        return f"  Derivation:  {head_label}"
    body_text = " AND ".join(labels.get(occurrence.occurrence_alias, occurrence.rule_id) for occurrence in bodies)
    return f"  Derivation:  {head_label} <= ( {body_text} )"


def _global_derivation_line(branches: tuple[StructureBranch, ...]) -> str | None:
    if len(branches) <= 1:
        return None
    head = next(
        (occurrence for branch in branches for occurrence in branch.occurrences if occurrence.role == "head"),
        None,
    )
    if head is None:
        return None
    head_label = _rule_id_label(head)
    groups: list[str] = []
    for branch in branches:
        labels = _occurrence_labels_for_branch(branch)
        bodies = tuple(occurrence for occurrence in branch.occurrences if occurrence.role == "body")
        if not bodies:
            groups.append("( true )")
            continue
        body_text = " AND ".join(labels.get(occurrence.occurrence_alias, occurrence.rule_id) for occurrence in bodies)
        groups.append(f"( {body_text} )")
    return f"  Derivation:  {head_label} <= " + " OR ".join(groups)


def _join_line(join: StructureJoin, *, labels: Mapping[str, str]) -> str:
    left = labels.get(join.left.occurrence_alias, join.left.occurrence_alias)
    right = labels.get(join.right.occurrence_alias, join.right.occurrence_alias)
    return (
        "               join:  "
        f"{left}.{join.left.port_name} = "
        f"{right}.{join.right.port_name}"
    )


def _narrate_occurrence(
    occurrence: StructureOccurrence,
    *,
    labels: Mapping[str, str],
    omit_label: bool = False,
) -> tuple[str, ...]:
    head_suffix = " [head]" if occurrence.role == "head" else ""
    label = _rule_label(occurrence)
    occurrence_label = labels.get(occurrence.occurrence_alias, occurrence.rule_id)
    if omit_label:
        lines = [f"  {occurrence_label}{head_suffix}"]
    else:
        lines = [f'  {occurrence_label}{head_suffix} ── "{label}"']
    for atom in occurrence.atoms:
        lines.append(_narrate_atom(atom))
    return tuple(lines)


def _narrate_atom(atom: StructureAtom) -> str:
    rendered = atom.repr_text or atom.summary or (type(atom.form).__name__ if atom.form is not None else "")
    return f"       {rendered}  [{atom.atom_id}]"


def _rule_label(occurrence: StructureOccurrence | None) -> str:
    if occurrence is None:
        return ""
    if _is_projection_rule_id(occurrence.rule_id):
        return _projection_label(occurrence)
    if occurrence.role != "head":
        return occurrence.rule_id
    return occurrence.repr_text or occurrence.rule_id


def _rule_id_label(occurrence: StructureOccurrence) -> str:
    if _is_projection_rule_id(occurrence.rule_id):
        return _projection_label(occurrence)
    return occurrence.rule_id


def _is_projection_rule_id(rule_id: str) -> bool:
    return rule_id.startswith(_PROJECTION_ID_PREFIX)


def _projection_label(occurrence: StructureOccurrence) -> str:
    ports = ", ".join(str(port) for port in occurrence.port_names)
    return f"projection({ports})" if ports else "projection"


__all__ = ["narrate_structure"]
