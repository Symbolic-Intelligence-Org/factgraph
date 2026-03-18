from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any


AssertionDetailLookup = Callable[[str], dict[str, Any] | None]


def build_candidate_evidence_tree(
    *,
    candidate_id: str,
    support_digest: str,
    support_kind: str,
    support: Mapping[str, Any],
    assertion_lookup: AssertionDetailLookup,
) -> dict[str, Any]:
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be non-empty string")
    if not isinstance(support_digest, str) or not support_digest:
        raise ValueError("support_digest must be non-empty string")
    if not isinstance(support_kind, str) or not support_kind:
        raise ValueError("support_kind must be non-empty string")
    if not isinstance(support, Mapping):
        raise ValueError("support must be mapping")

    binding = _pairs_to_mapping(support.get("binding"), label="support.binding")
    pred_witnesses = _require_list(support.get("pred_witnesses"), label="support.pred_witnesses")
    non_fact_steps = _require_list(support.get("non_fact_steps", []), label="support.non_fact_steps")
    rule_refs = _normalize_strings(support.get("rule_refs", []), label="support.rule_refs")
    root_result_kind = _require_non_empty_str(support.get("root_result_kind"), label="support.root_result_kind")

    children: list[dict[str, Any]] = []
    for witness in pred_witnesses:
        children.append(_build_predicate_witness_group(witness, assertion_lookup=assertion_lookup))
    for step in non_fact_steps:
        children.append(_build_non_fact_check(step))

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
            "children": children,
        },
    }


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


__all__ = ["build_candidate_evidence_tree"]
