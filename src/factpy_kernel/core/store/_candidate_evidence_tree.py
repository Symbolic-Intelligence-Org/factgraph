from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any


AssertionDetailLookup = Callable[[str], dict[str, Any] | None]
SupportLookup = Callable[[str], dict[str, Any] | None]
_MAX_RECURSION_DEPTH = 8


def build_candidate_evidence_tree(
    *,
    candidate_id: str,
    support_digest: str,
    support_kind: str,
    support: Mapping[str, Any],
    assertion_lookup: AssertionDetailLookup,
    support_lookup: SupportLookup,
) -> dict[str, Any]:
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be non-empty string")
    if not isinstance(support_digest, str) or not support_digest:
        raise ValueError("support_digest must be non-empty string")
    if not isinstance(support_kind, str) or not support_kind:
        raise ValueError("support_kind must be non-empty string")
    if not isinstance(support, Mapping):
        raise ValueError("support must be mapping")

    binding, root_result_kind, rule_refs, rule_ref_edges, children = _build_support_sections(
        node_key=candidate_id,
        support=support,
        assertion_lookup=assertion_lookup,
        support_lookup=support_lookup,
        depth_remaining=_MAX_RECURSION_DEPTH,
        ancestry={support_digest},
    )

    return {
        "kind": "candidate_evidence_tree",
        "candidate_id": candidate_id,
        "support_digest": support_digest,
        "support_kind": support_kind,
        "root": {
            "node_id": f"cand:{candidate_id}",
            "node_kind": "candidate_result",
            "title": f"Candidate {candidate_id}",
            "root_result_kind": root_result_kind,
            "binding": binding,
            "rule_refs": rule_refs,
            "rule_ref_edges": rule_ref_edges,
            "children": children,
        },
    }


def build_degraded_candidate_evidence_tree(
    *,
    candidate_id: str,
    support_digest: str,
    support_kind: str,
) -> dict[str, Any]:
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be non-empty string")
    if not isinstance(support_digest, str) or not support_digest:
        raise ValueError("support_digest must be non-empty string")
    if not isinstance(support_kind, str) or not support_kind:
        raise ValueError("support_kind must be non-empty string")

    return {
        "kind": "candidate_evidence_tree",
        "candidate_id": candidate_id,
        "support_digest": support_digest,
        "support_kind": support_kind,
        "root": {
            "node_id": f"cand:{candidate_id}",
            "node_kind": "candidate_result",
            "title": f"Candidate {candidate_id}",
            "binding": {},
            "rule_refs": [],
            "rule_ref_edges": [],
            "children": [
                {
                    "node_id": f"support:{candidate_id}",
                    "node_kind": "support_section",
                    "title": "Support",
                    "children": [
                        {
                            "node_id": f"degraded:{candidate_id}",
                            "node_kind": "degraded_support",
                            "title": "Degraded support",
                            "support_kind": support_kind,
                            "witness_status": "degraded",
                            "children": [],
                        }
                    ],
                }
            ],
        },
    }


def _build_support_sections(
    *,
    node_key: str,
    support: Mapping[str, Any],
    assertion_lookup: AssertionDetailLookup,
    support_lookup: SupportLookup,
    depth_remaining: int,
    ancestry: set[str],
) -> tuple[dict[str, Any], str, list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    binding = _pairs_to_mapping(support.get("binding"), label="support.binding")
    pred_witnesses = _require_list(support.get("pred_witnesses"), label="support.pred_witnesses")
    non_fact_steps = _require_list(support.get("non_fact_steps", []), label="support.non_fact_steps")
    rule_refs = _normalize_strings(support.get("rule_refs", []), label="support.rule_refs")
    rule_ref_edges = _normalize_rule_ref_edges(support.get("rule_ref_edges", []), label="support.rule_ref_edges")
    root_result_kind = _require_non_empty_str(support.get("root_result_kind"), label="support.root_result_kind")

    support_children: list[dict[str, Any]] = []
    for witness in pred_witnesses:
        support_children.append(_build_predicate_witness_group(witness, assertion_lookup=assertion_lookup))
    for step in non_fact_steps:
        support_children.append(_build_non_fact_check(step))

    children: list[dict[str, Any]] = [
        {
            "node_id": f"support:{node_key}",
            "node_kind": "support_section",
            "title": "Support",
            "children": support_children,
        }
    ]

    if rule_ref_edges:
        children.append(
            {
                "node_id": f"rule_refs:{node_key}",
                "node_kind": "rule_ref_section",
                "title": "Rule References",
                "children": [
                    _build_rule_ref_edge_node(
                        edge,
                        assertion_lookup=assertion_lookup,
                        support_lookup=support_lookup,
                        depth_remaining=depth_remaining,
                        ancestry=ancestry,
                    )
                    for edge in rule_ref_edges
                ],
            }
        )
    elif rule_refs:
        children.append(
            {
                "node_id": f"rule_refs:{node_key}",
                "node_kind": "rule_ref_section",
                "title": "Rule References",
                "children": [_build_legacy_rule_ref_node(rule_ref_id) for rule_ref_id in rule_refs],
            }
        )

    return binding, root_result_kind, rule_refs, rule_ref_edges, children


def _build_predicate_witness_group(
    row: Mapping[str, Any],
    *,
    assertion_lookup: AssertionDetailLookup,
) -> dict[str, Any]:
    pred_atom_key = _require_non_empty_str(row.get("pred_atom_key"), label="pred_witness.pred_atom_key")
    asrt_ids = _normalize_strings(row.get("asrt_ids"), label=f"{pred_atom_key}.asrt_ids")
    pred_id = pred_atom_key.split(":", 1)[1] if ":" in pred_atom_key else pred_atom_key
    leaves = [_build_assertion_leaf(asrt_id, assertion_lookup=assertion_lookup) for asrt_id in asrt_ids]
    return {
        "node_id": f"atom:{pred_atom_key}",
        "node_kind": "predicate_witness_group",
        "title": f"Predicate witness {pred_id}",
        "pred_atom_key": pred_atom_key,
        "pred_id": pred_id,
        "assertion_count": len(leaves),
        "children": leaves,
    }


def _build_non_fact_check(row: Mapping[str, Any]) -> dict[str, Any]:
    step_key = _require_non_empty_str(row.get("step_key"), label="non_fact_step.step_key")
    step_kind = _require_non_empty_str(row.get("kind"), label=f"{step_key}.kind")
    status = _require_non_empty_str(row.get("status"), label=f"{step_key}.status")
    details = _pairs_to_mapping(row.get("details", []), label=f"{step_key}.details")
    return {
        "node_id": f"step:{step_key}",
        "node_kind": "non_fact_check",
        "title": f"Non-fact check {step_key}",
        "step_key": step_key,
        "check_kind": step_kind,
        "status": status,
        "details": details,
        "children": [],
    }


def _build_assertion_leaf(asrt_id: str, *, assertion_lookup: AssertionDetailLookup) -> dict[str, Any]:
    detail = assertion_lookup(asrt_id)
    if not isinstance(detail, Mapping):
        raise ValueError(f"assertion detail not found for asrt_id={asrt_id!r}")
    claim = detail.get("claim")
    if not isinstance(claim, Mapping):
        raise ValueError(f"assertion detail missing claim for asrt_id={asrt_id!r}")
    pred_id = _require_non_empty_str(claim.get("pred_id"), label=f"{asrt_id}.claim.pred_id")
    e_ref = _require_non_empty_str(claim.get("e_ref"), label=f"{asrt_id}.claim.e_ref")
    claim_args = _normalize_claim_args(detail.get("claim_args"), label=f"{asrt_id}.claim_args")
    return {
        "node_id": f"asrt:{asrt_id}",
        "node_kind": "assertion_fact",
        "title": f"Assertion {asrt_id}",
        "asrt_id": asrt_id,
        "pred_id": pred_id,
        "e_ref": e_ref,
        "claim_args": claim_args,
        "children": [],
    }


def _build_legacy_rule_ref_node(rule_ref_id: str) -> dict[str, Any]:
    return {
        "node_id": f"ruleref:{rule_ref_id}",
        "node_kind": "rule_ref",
        "title": f"Rule reference {rule_ref_id}",
        "rule_ref_id": rule_ref_id,
        "children": [],
    }


def _build_rule_ref_edge_node(
    edge: Mapping[str, Any],
    *,
    assertion_lookup: AssertionDetailLookup,
    support_lookup: SupportLookup,
    depth_remaining: int,
    ancestry: set[str],
) -> dict[str, Any]:
    ruleref_atom_key = _require_non_empty_str(edge.get("ruleref_atom_key"), label="rule_ref_edge.ruleref_atom_key")
    rule_ref_id = _require_non_empty_str(edge.get("rule_ref_id"), label="rule_ref_edge.rule_ref_id")
    rule_ref_version = _require_non_empty_str(
        edge.get("rule_ref_version"),
        label=f"{ruleref_atom_key}.rule_ref_version",
    )
    child_support_digest = edge.get("child_support_digest")
    unresolved_reason = edge.get("unresolved_reason")
    if child_support_digest is not None and (
        not isinstance(child_support_digest, str) or not child_support_digest
    ):
        raise ValueError(f"{ruleref_atom_key}.child_support_digest must be non-empty string when present")
    if unresolved_reason is not None and (
        not isinstance(unresolved_reason, str) or not unresolved_reason
    ):
        raise ValueError(f"{ruleref_atom_key}.unresolved_reason must be non-empty string when present")

    children: list[dict[str, Any]] = []
    if child_support_digest is None:
        children.append(
            _build_unresolved_support_node(
                node_key=ruleref_atom_key,
                reason=unresolved_reason or "child_support_unavailable",
                child_support_digest=None,
            )
        )
    else:
        children.append(
            _build_referenced_support_child(
                ruleref_atom_key=ruleref_atom_key,
                child_support_digest=child_support_digest,
                assertion_lookup=assertion_lookup,
                support_lookup=support_lookup,
                depth_remaining=depth_remaining,
                ancestry=ancestry,
            )
        )

    return {
        "node_id": f"ruleref:{ruleref_atom_key}",
        "node_kind": "rule_ref",
        "title": f"Rule reference {rule_ref_id}",
        "ruleref_atom_key": ruleref_atom_key,
        "rule_ref_id": rule_ref_id,
        "rule_ref_version": rule_ref_version,
        "child_support_digest": child_support_digest,
        "unresolved_reason": unresolved_reason,
        "children": children,
    }


def _build_referenced_support_child(
    *,
    ruleref_atom_key: str,
    child_support_digest: str,
    assertion_lookup: AssertionDetailLookup,
    support_lookup: SupportLookup,
    depth_remaining: int,
    ancestry: set[str],
) -> dict[str, Any]:
    if depth_remaining <= 0:
        return _build_recursion_boundary_node(node_key=ruleref_atom_key, reason="depth_limit")
    if child_support_digest in ancestry:
        return _build_recursion_boundary_node(node_key=ruleref_atom_key, reason="cycle")

    support = support_lookup(child_support_digest)
    if not isinstance(support, Mapping):
        return _build_unresolved_support_node(
            node_key=ruleref_atom_key,
            reason="artifact_missing",
            child_support_digest=child_support_digest,
        )

    binding, root_result_kind, rule_refs, rule_ref_edges, children = _build_support_sections(
        node_key=child_support_digest,
        support=support,
        assertion_lookup=assertion_lookup,
        support_lookup=support_lookup,
        depth_remaining=depth_remaining - 1,
        ancestry={*ancestry, child_support_digest},
    )
    return {
        "node_id": f"referenced_support:{child_support_digest}",
        "node_kind": "referenced_support",
        "title": f"Referenced support {child_support_digest}",
        "support_digest": child_support_digest,
        "root_result_kind": root_result_kind,
        "binding": binding,
        "rule_refs": rule_refs,
        "rule_ref_edges": rule_ref_edges,
        "children": children,
    }


def _build_unresolved_support_node(
    *,
    node_key: str,
    reason: str,
    child_support_digest: str | None,
) -> dict[str, Any]:
    return {
        "node_id": f"unresolved:{node_key}",
        "node_kind": "unresolved_support",
        "title": "Unresolved support",
        "reason": reason,
        "child_support_digest": child_support_digest,
        "children": [],
    }


def _build_recursion_boundary_node(*, node_key: str, reason: str) -> dict[str, Any]:
    return {
        "node_id": f"boundary:{node_key}",
        "node_kind": "recursion_boundary",
        "title": "Recursion boundary",
        "boundary_reason": reason,
        "children": [],
    }


def _normalize_claim_args(value: Any, *, label: str) -> list[dict[str, Any]]:
    rows = _require_list(value, label=label)
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"{label}[{idx}] must be mapping")
        arg_idx = row.get("idx")
        if isinstance(arg_idx, bool) or not isinstance(arg_idx, int):
            raise ValueError(f"{label}[{idx}].idx must be int")
        tag = _require_non_empty_str(row.get("tag"), label=f"{label}[{idx}].tag")
        raw_val = row.get("val")
        out.append(
            {
                "idx": arg_idx,
                "val": "" if raw_val is None else str(raw_val),
                "tag": tag,
            }
        )
    out.sort(key=lambda row: (row["idx"], row["tag"], row["val"]))
    return out


def _normalize_rule_ref_edges(value: Any, *, label: str) -> list[dict[str, Any]]:
    rows = _require_list(value, label=label)
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"{label}[{idx}] must be mapping")
        out.append(
            {
                "ruleref_atom_key": _require_non_empty_str(
                    row.get("ruleref_atom_key"),
                    label=f"{label}[{idx}].ruleref_atom_key",
                ),
                "rule_ref_id": _require_non_empty_str(row.get("rule_ref_id"), label=f"{label}[{idx}].rule_ref_id"),
                "rule_ref_version": _require_non_empty_str(
                    row.get("rule_ref_version"),
                    label=f"{label}[{idx}].rule_ref_version",
                ),
                "child_support_digest": row.get("child_support_digest"),
                "unresolved_reason": row.get("unresolved_reason"),
            }
        )
    out.sort(
        key=lambda row: (
            row["ruleref_atom_key"],
            row["rule_ref_id"],
            row["rule_ref_version"],
            row["child_support_digest"] or "",
        )
    )
    return out


def _pairs_to_mapping(value: Any, *, label: str) -> dict[str, Any]:
    pairs = _require_list(value, label=label)
    out: dict[str, Any] = {}
    for idx, item in enumerate(pairs):
        if not isinstance(item, Sequence) or isinstance(item, (str, bytes, bytearray)) or len(item) != 2:
            raise ValueError(f"{label}[{idx}] must be pair")
        key = item[0]
        if not isinstance(key, str) or not key:
            raise ValueError(f"{label}[{idx}][0] must be non-empty string")
        out[key] = item[1]
    return out


def _normalize_strings(value: Any, *, label: str) -> list[str]:
    rows = _require_list(value, label=label)
    out: list[str] = []
    for idx, item in enumerate(rows):
        if not isinstance(item, str) or not item:
            raise ValueError(f"{label}[{idx}] must be non-empty string")
        out.append(item)
    return out


def _require_list(value: Any, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be list")
    return value


def _require_non_empty_str(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be non-empty string")
    return value


__all__ = ["build_candidate_evidence_tree", "build_degraded_candidate_evidence_tree"]
