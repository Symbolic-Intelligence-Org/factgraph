from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class CandidateEvidenceStepsError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Phase 1: Traversal -> _StepRecord (N-EED1: traversal decoupled from render)
# ---------------------------------------------------------------------------


@dataclass
class _StepRecord:
    """Intermediate representation from tree traversal, before description rendering."""

    step_kind_raw: str
    node_id: str
    depth: int
    parent_node_id: str | None
    data: dict[str, Any] = field(default_factory=dict)


_STEP_GENERATING_KINDS = frozenset(
    {
        "assertion_fact",
        "support_section",
        "proof_goal",
        "proof_leaf",
        "candidate_result",
    }
)

_TRANSPARENT_KINDS = frozenset(
    {
        "predicate_witness_group",
        "rule_ref",
        "referenced_support",
        "rule_ref_section",
    }
)


def _traverse_evidence_tree_node(
    node: Any,
    records: list[_StepRecord],
    depth: int,
    parent_node_id: str | None,
) -> None:
    if not isinstance(node, Mapping):
        return
    node_kind = str(node.get("node_kind", ""))
    node_id = str(node.get("node_id", ""))
    children = [c for c in node.get("children", []) if isinstance(c, Mapping)]

    if node_kind in _TRANSPARENT_KINDS:
        for child in children:
            _traverse_evidence_tree_node(child, records, depth, parent_node_id)
        return

    if node_kind not in _STEP_GENERATING_KINDS:
        for child in children:
            _traverse_evidence_tree_node(child, records, depth, parent_node_id)
        return

    for child in children:
        _traverse_evidence_tree_node(child, records, depth + 1, node_id)

    data: dict[str, Any] = {}

    if node_kind == "assertion_fact":
        data["pred_id"] = str(node.get("pred_id", ""))
        data["e_ref"] = str(node.get("e_ref", ""))
        data["asrt_id"] = str(node.get("asrt_id", ""))
        data["claim_args"] = node.get("claim_args", [])
        data["confidence"] = node.get("confidence")
        fact_meta = node.get("fact_meta")
        if isinstance(fact_meta, Mapping):
            data["fact_meta"] = dict(fact_meta)

    elif node_kind == "support_section":
        data["witness_count"] = _count_assertion_facts(node)
        data["rule_ref_ids"] = _normalize_rule_ref_ids(node.get("rule_ref_ids"))

    elif node_kind == "proof_goal":
        data["goal"] = str(node.get("goal", ""))
        data["goal_args"] = list(node.get("goal_args", []))
        data["pred_id"] = str(node.get("pred_id", ""))

    elif node_kind == "proof_leaf":
        data["goal"] = str(node.get("goal", ""))
        data["goal_args"] = list(node.get("goal_args", []))
        data["pred_id"] = str(node.get("pred_id", ""))

    elif node_kind == "candidate_result":
        node_id_str = str(node.get("node_id", ""))
        cid = node_id_str.split(":", 1)[1] if ":" in node_id_str else node_id_str
        data["candidate_id"] = cid
        data["root_result_kind"] = str(node.get("root_result_kind") or "")
        binding = node.get("binding")
        if isinstance(binding, Mapping):
            data["binding"] = dict(binding)

    records.append(
        _StepRecord(
            step_kind_raw=node_kind,
            node_id=node_id,
            depth=depth,
            parent_node_id=parent_node_id,
            data=data,
        )
    )


def _count_assertion_facts(node: Any) -> int:
    if not isinstance(node, Mapping):
        return 0
    count = 1 if node.get("node_kind") == "assertion_fact" else 0
    for child in node.get("children", []):
        count += _count_assertion_facts(child)
    return count


# ---------------------------------------------------------------------------
# Phase 2: _StepRecord -> step dict (description rendering)
# ---------------------------------------------------------------------------


_STEP_KIND_MAP: dict[str, str] = {
    "assertion_fact": "fact_check",
    "support_section": "rule_apply",
    "proof_goal": "proof_goal_derive",
    "proof_leaf": "proof_leaf_check",
    "candidate_result": "conclusion",
}


def _format_val(claim_args: Any) -> str:
    if not isinstance(claim_args, list):
        return ""
    return ", ".join(str(a.get("val", "")) for a in claim_args if isinstance(a, Mapping))


def _describe_step(record: _StepRecord) -> str:
    kind = record.step_kind_raw
    d = record.data

    if kind == "assertion_fact":
        pred_id = d.get("pred_id", "")
        e_ref = d.get("e_ref", "")
        val = _format_val(d.get("claim_args", []))
        entity_part = f"({e_ref})" if e_ref else ""
        val_part = f" = {val}" if val else ""
        return f"Fact {pred_id}{entity_part}{val_part} \u2713"

    if kind == "support_section":
        n = d.get("witness_count", 0)
        ids = d.get("rule_ref_ids", [])
        if len(ids) == 1:
            return f"Rule {ids[0]}: {n} condition(s) met"
        if len(ids) > 1:
            joined = ", ".join(ids)
            return f"Rules [{joined}]: {n} condition(s) met"
        return f"Support group satisfied: {n} condition(s) met"

    if kind == "proof_leaf":
        goal = d.get("goal", "")
        return f"Proof leaf: {goal} (base fact)"

    if kind == "proof_goal":
        goal = d.get("goal", "")
        return f"Proof goal: {goal} derived"

    if kind == "candidate_result":
        cid = d.get("candidate_id", "")
        rrk = d.get("root_result_kind", "")
        suffix = f" ({rrk})" if rrk else ""
        return f"Candidate {cid} established{suffix}"

    return f"Step ({kind})"


def _record_to_step(record: _StepRecord, step_num: int) -> dict[str, Any]:
    step_kind = _STEP_KIND_MAP.get(record.step_kind_raw, record.step_kind_raw)
    description = _describe_step(record)

    detail: dict[str, Any] = {
        "depth": record.depth,
        "parent_node_ref": record.parent_node_id,
    }

    if record.step_kind_raw == "assertion_fact":
        detail["pred_id"] = record.data.get("pred_id", "")
        detail["e_ref"] = record.data.get("e_ref", "")
        detail["claim_args"] = record.data.get("claim_args", [])
        conf = record.data.get("confidence")
        if conf is not None:
            detail["confidence"] = conf
        fm = record.data.get("fact_meta")
        if fm is not None:
            detail["fact_meta"] = fm
    elif record.step_kind_raw == "support_section":
        detail["witness_count"] = record.data.get("witness_count", 0)
        detail["rule_ref_ids"] = record.data.get("rule_ref_ids", [])
    elif record.step_kind_raw in ("proof_goal", "proof_leaf"):
        detail["goal"] = record.data.get("goal", "")
        detail["goal_args"] = record.data.get("goal_args", [])

    node_ref: str | None = (
        record.data.get("asrt_id") or record.node_id if record.step_kind_raw == "assertion_fact" else record.node_id
    )

    return {
        "step_num": step_num,
        "step_kind": step_kind,
        "description": description,
        "node_ref": node_ref,
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_candidate_evidence_steps(tree: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Build a flat, ordered list of steps from a candidate_evidence_tree dict.
    Traversal is DFS post-order (leaf facts first, conclusion last).
    Compatible with native, souffle, and problog tree shapes.
    """
    if not isinstance(tree, Mapping):
        raise CandidateEvidenceStepsError("tree must be object")
    if tree.get("kind") != "candidate_evidence_tree":
        raise CandidateEvidenceStepsError("tree.kind must be candidate_evidence_tree")
    root = tree.get("root")
    if not isinstance(root, Mapping):
        raise CandidateEvidenceStepsError("tree.root must be object")
    records: list[_StepRecord] = []
    _traverse_evidence_tree_node(root, records, depth=0, parent_node_id=None)
    return [_record_to_step(r, i + 1) for i, r in enumerate(records)]


def _normalize_rule_ref_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item:
            out.append(item)
    return out


__all__ = [
    "CandidateEvidenceStepsError",
    "build_candidate_evidence_steps",
]
