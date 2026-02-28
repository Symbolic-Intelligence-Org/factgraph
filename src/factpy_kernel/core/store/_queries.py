from __future__ import annotations

from typing import Any

from factpy_kernel.core.mapping.canon import MappingResolution, resolve_mapping_predicate
from factpy_kernel.core.policy.active import is_active
from factpy_kernel.core.policy.chosen import compute_chosen_for_predicate
from factpy_kernel.core.rules.where_eval import WhereValidationError
from factpy_kernel.core.store import builders
from factpy_kernel.core.view.projector import build_args_for_claim


def explain_fact(store: Any, pred_id: str, e_ref: str, *val_atoms: Any) -> dict[str, Any]:
    schema_pred = builders.find_schema_pred(store, pred_id)

    active_claims = [
        claim
        for claim in store.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)
        if is_active(store.ledger, claim.asrt_id)
    ]

    claim_rows: list[dict[str, Any]] = []
    for claim in active_claims:
        args = build_args_for_claim(store.ledger, claim)
        if val_atoms and tuple(args[1:]) != tuple(val_atoms):
            continue
        claim_rows.append(
            {
                "asrt_id": claim.asrt_id,
                "args": args,
                "meta": meta_subset(store, claim.asrt_id),
            }
        )

    chosen_asrt_id: str | None = None
    if schema_pred is not None and claim_rows:
        chosen_map = compute_chosen_for_predicate(store.ledger, schema_pred)
        chosen_ids = set(chosen_map.values())
        matching = [row["asrt_id"] for row in claim_rows if row["asrt_id"] in chosen_ids]
        if matching:
            chosen_asrt_id = sorted(matching)[0]

    return {
        "pred_id": pred_id,
        "e_ref": e_ref,
        "active_claims": claim_rows,
        "chosen_asrt_id": chosen_asrt_id,
    }


def conflicts(store: Any, pred_id: str, e_ref: str) -> dict[str, Any]:
    schema_pred = builders.find_schema_pred(store, pred_id)
    active_claims = [
        claim
        for claim in store.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)
        if is_active(store.ledger, claim.asrt_id)
    ]
    active_asrt_ids = [claim.asrt_id for claim in active_claims]

    chosen_asrt_id: str | None = None
    if schema_pred is not None and active_asrt_ids:
        chosen_map = compute_chosen_for_predicate(store.ledger, schema_pred)
        chosen_ids = set(chosen_map.values())
        overlap = sorted([asrt_id for asrt_id in active_asrt_ids if asrt_id in chosen_ids])
        if overlap:
            chosen_asrt_id = overlap[0]

    return {
        "pred_id": pred_id,
        "e_ref": e_ref,
        "active_asrt_ids": active_asrt_ids,
        "chosen_asrt_id": chosen_asrt_id,
    }


def resolve_mapping(store: Any, pred_id: str, *, policy_mode: str = "edb") -> MappingResolution:
    if policy_mode not in {"edb", "idb"}:
        raise ValueError("policy_mode must be 'edb' or 'idb'")
    schema_pred = builders.find_schema_pred(store, pred_id)
    if schema_pred is None:
        raise WhereValidationError(f"target predicate not found: {pred_id}")

    tie_break = schema_pred.get("tie_break")
    tie_break_mode: str | None = None
    if isinstance(tie_break, dict):
        mode = tie_break.get("mode")
        if isinstance(mode, str):
            tie_break_mode = mode
    elif isinstance(tie_break, str):
        tie_break_mode = tie_break
    elif tie_break is None:
        tie_break_mode = "error"

    if policy_mode == "idb" and tie_break_mode not in {"error", None}:
        raise NotImplementedError(
            "mapping tie-break requires policy_mode='edb' for deterministic precompute"
        )

    return resolve_mapping_predicate(store.ledger, schema_pred)


def meta_subset(store: Any, asrt_id: str) -> dict[str, Any]:
    wanted = {"ingested_at", "source", "run_id", "materialize_id", "cand_key_digest"}
    out: dict[str, Any] = {}
    for row in store.ledger.find_meta(asrt_id=asrt_id):
        if row.key in wanted and row.key not in out:
            out[row.key] = row.value
    return out
