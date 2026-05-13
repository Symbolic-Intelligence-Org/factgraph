from __future__ import annotations

from typing import Any

from factpy.core.evidence.write_protocol import PolicyNonDeterminismError
from factpy.core.policy.active import is_active
from factpy.core.protocol.tup_v1 import claim_args_from_rest_terms
from factpy.core.store.ledger import Claim, ClaimArg, Ledger


def choose_one(ledger: Ledger, asrt_ids: list[str]) -> str:
    if not isinstance(ledger, Ledger):
        raise TypeError("ledger must be Ledger")
    if not asrt_ids:
        raise PolicyNonDeterminismError("choose_one requires at least one asrt_id")

    candidates: list[tuple[str, int]] = []
    for asrt_id in asrt_ids:
        ingested_at = _read_required_ingested_at(ledger, asrt_id)
        candidates.append((asrt_id, ingested_at))

    candidates.sort(key=lambda item: (-item[1], item[0].encode("utf-8")))
    return candidates[0][0]


def group_key_for_claim(
    schema_pred: dict,
    claim: Claim,
    ledger: Ledger | None = None,
) -> tuple:
    if not isinstance(schema_pred, dict):
        raise PolicyNonDeterminismError("schema_pred must be dict")
    if not isinstance(claim, Claim):
        raise PolicyNonDeterminismError("claim must be Claim")

    args = _args_for_claim(claim, ledger)
    group_key_indexes = _read_group_key_indexes(schema_pred, arg_count=len(args))

    key_terms: list[Any] = []
    for idx in group_key_indexes:
        if idx == 0:
            continue
        key_terms.append(args[idx])

    return (claim.pred_id, claim.e_ref, *key_terms)


def compute_chosen_for_predicate(ledger: Ledger, schema_pred: dict) -> dict[tuple, str]:
    if not isinstance(ledger, Ledger):
        raise TypeError("ledger must be Ledger")
    if not isinstance(schema_pred, dict):
        raise PolicyNonDeterminismError("schema_pred must be dict")

    pred_id = schema_pred.get("pred_id")
    if not isinstance(pred_id, str) or not pred_id:
        raise PolicyNonDeterminismError("schema_pred.pred_id must be non-empty string")

    cardinality = schema_pred.get("cardinality", "single")
    claims = [
        claim
        for claim in ledger.find_claims(pred_id=pred_id)
        if is_active(ledger, claim.asrt_id)
    ]

    if cardinality == "multi":
        chosen: dict[tuple, str] = {}
        for claim in claims:
            base_key = group_key_for_claim(schema_pred, claim, ledger=ledger)
            # Multi-value fields keep all active assertions as visible rows.
            chosen[(*base_key, claim.asrt_id)] = claim.asrt_id
        return chosen
    if cardinality != "single":
        raise PolicyNonDeterminismError(f"unsupported cardinality: {cardinality}")

    groups: dict[tuple, list[str]] = {}
    for claim in claims:
        group_key = group_key_for_claim(schema_pred, claim, ledger=ledger)
        groups.setdefault(group_key, []).append(claim.asrt_id)

    chosen_map: dict[tuple, str] = {}
    for group_key, asrt_ids in groups.items():
        chosen_map[group_key] = choose_one(ledger, asrt_ids)
    return chosen_map


def _read_required_ingested_at(ledger: Ledger, asrt_id: str) -> int:
    rows = ledger.find_meta(asrt_id=asrt_id, key="ingested_at")
    if len(rows) != 1:
        raise PolicyNonDeterminismError(
            f"asrt_id={asrt_id} must have exactly one ingested_at meta row"
        )
    row = rows[0]
    if row.kind != "time" or isinstance(row.value, bool) or not isinstance(row.value, int):
        raise PolicyNonDeterminismError(
            f"asrt_id={asrt_id} ingested_at must be meta_time int"
        )
    return row.value


def _read_group_key_indexes(schema_pred: dict, arg_count: int) -> list[int]:
    group_key_indexes = schema_pred.get("group_key_indexes")
    if not isinstance(group_key_indexes, list):
        raise PolicyNonDeterminismError("group_key_indexes must be a list")

    last = -1
    out: list[int] = []
    for idx in group_key_indexes:
        if isinstance(idx, bool) or not isinstance(idx, int):
            raise PolicyNonDeterminismError("group_key_indexes values must be int")
        if idx < 0 or idx >= arg_count:
            raise PolicyNonDeterminismError("group_key_indexes contains out-of-range value")
        if idx <= last:
            raise PolicyNonDeterminismError("group_key_indexes must be strictly ascending")
        out.append(idx)
        last = idx
    return out


def _args_for_claim(claim: Claim, ledger: Ledger | None) -> list[Any]:
    val_atoms = _val_atoms_for_claim(claim, ledger)
    return [claim.e_ref, *val_atoms]


def _val_atoms_for_claim(claim: Claim, ledger: Ledger | None) -> list[Any]:
    rows = _claim_arg_rows(ledger, claim.asrt_id) if ledger is not None else []

    if rows:
        sorted_rows = sorted(rows, key=lambda row: row.idx)
        expected_count = len(claim.rest_terms)
        if len(sorted_rows) != expected_count:
            raise PolicyNonDeterminismError(
                f"asrt_id={claim.asrt_id} claim_arg count mismatch"
            )
        for expected_idx, row in enumerate(sorted_rows):
            if row.idx != expected_idx:
                raise PolicyNonDeterminismError(
                    f"asrt_id={claim.asrt_id} claim_arg idx must be contiguous"
                )
        return [row.val_atom for row in sorted_rows]

    fallback_rows = claim_args_from_rest_terms(claim.rest_terms)
    return [val_atom for _, val_atom, _ in fallback_rows]


def _claim_arg_rows(ledger: Ledger | None, asrt_id: str) -> list[ClaimArg]:
    if ledger is None:
        return []
    return ledger.find_claim_args(asrt_id=asrt_id)
