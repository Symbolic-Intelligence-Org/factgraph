from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factgraph.core.policy.active import is_active
from factgraph.core.store.ledger import Claim, Ledger
from factgraph.core.view.projector import build_args_for_claim


class MappingResolveError(Exception):
    pass


class MappingConflictError(MappingResolveError):
    def __init__(self, message: str, conflicts: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.conflicts = list(conflicts)


@dataclass(frozen=True)
class MappingCandidate:
    asrt_id: str
    key_tuple: tuple[Any, ...]
    value_tuple: tuple[Any, ...]
    source: str | None
    ingested_at: int


@dataclass(frozen=True)
class MappingDecision:
    key_tuple: tuple[Any, ...]
    chosen_asrt_id: str
    chosen_value_tuple: tuple[Any, ...]
    reason: str
    candidate_asrt_ids: tuple[str, ...]


@dataclass(frozen=True)
class MappingResolution:
    pred_id: str
    chosen_map: dict[tuple[Any, ...], tuple[Any, ...]]
    candidates: list[MappingCandidate]
    decisions: list[MappingDecision]
    conflicts: list[dict[str, Any]]


def resolve_mapping_predicate(ledger: Ledger, schema_pred: dict) -> MappingResolution:
    if not isinstance(ledger, Ledger):
        raise MappingResolveError("ledger must be Ledger")
    if not isinstance(schema_pred, dict):
        raise MappingResolveError("schema_pred must be dict")

    pred_id = schema_pred.get("pred_id")
    if not isinstance(pred_id, str) or not pred_id:
        raise MappingResolveError("schema_pred.pred_id must be non-empty string")
    if schema_pred.get("is_mapping") is not True:
        raise MappingResolveError("schema_pred must declare is_mapping=true")
    if schema_pred.get("mapping_kind") != "single_valued":
        raise MappingResolveError("mapping_kind must be 'single_valued'")

    arg_specs = schema_pred.get("arg_specs")
    if not isinstance(arg_specs, list) or not arg_specs:
        raise MappingResolveError("arg_specs must be non-empty list")
    arg_count = len(arg_specs)

    key_positions = _normalize_positions(schema_pred.get("mapping_key_positions"), arg_count, "mapping_key_positions")
    value_positions = _normalize_positions(
        schema_pred.get("mapping_value_positions"), arg_count, "mapping_value_positions"
    )
    if not key_positions:
        raise MappingResolveError("mapping_key_positions must be non-empty")
    if not value_positions:
        raise MappingResolveError("mapping_value_positions must be non-empty")

    tie_break_mode, tie_break_conf = _normalize_tie_break(schema_pred.get("tie_break"))

    claims = [
        claim
        for claim in ledger.find_claims(pred_id=pred_id)
        if is_active(ledger, claim.asrt_id)
    ]

    grouped: dict[tuple[Any, ...], list[MappingCandidate]] = {}
    all_candidates: list[MappingCandidate] = []
    for claim in claims:
        cand = _candidate_from_claim(ledger, claim, key_positions, value_positions)
        all_candidates.append(cand)
        grouped.setdefault(cand.key_tuple, []).append(cand)

    chosen_map: dict[tuple[Any, ...], tuple[Any, ...]] = {}
    decisions: list[MappingDecision] = []
    conflicts: list[dict[str, Any]] = []

    for key_tuple, candidates in grouped.items():
        distinct_values = {cand.value_tuple for cand in candidates}
        if len(distinct_values) <= 1:
            chosen = candidates[0]
            chosen_map[key_tuple] = chosen.value_tuple
            decisions.append(
                MappingDecision(
                    key_tuple=key_tuple,
                    chosen_asrt_id=chosen.asrt_id,
                    chosen_value_tuple=chosen.value_tuple,
                    reason="single_value",
                    candidate_asrt_ids=tuple(sorted(c.asrt_id for c in candidates)),
                )
            )
            continue

        if tie_break_mode == "error":
            conflicts.append(
                {
                    "key_tuple": key_tuple,
                    "candidate_values": sorted(distinct_values, key=lambda tup: tuple(str(x) for x in tup)),
                    "candidate_asrt_ids": sorted(c.asrt_id for c in candidates),
                }
            )
            continue

        chosen = _choose_with_tie_break(candidates, tie_break_mode, tie_break_conf, ledger)
        chosen_map[key_tuple] = chosen.value_tuple
        decisions.append(
            MappingDecision(
                key_tuple=key_tuple,
                chosen_asrt_id=chosen.asrt_id,
                chosen_value_tuple=chosen.value_tuple,
                reason=tie_break_mode,
                candidate_asrt_ids=tuple(sorted(c.asrt_id for c in candidates)),
            )
        )

    if conflicts:
        raise MappingConflictError(
            f"mapping conflict for {pred_id}: {len(conflicts)} key(s)",
            conflicts,
        )

    return MappingResolution(
        pred_id=pred_id,
        chosen_map=chosen_map,
        candidates=sorted(all_candidates, key=lambda c: (tuple(str(x) for x in c.key_tuple), c.asrt_id)),
        decisions=sorted(decisions, key=lambda d: (tuple(str(x) for x in d.key_tuple), d.chosen_asrt_id)),
        conflicts=conflicts,
    )


def _candidate_from_claim(
    ledger: Ledger,
    claim: Claim,
    key_positions: tuple[int, ...],
    value_positions: tuple[int, ...],
) -> MappingCandidate:
    args = build_args_for_claim(ledger, claim)
    key_tuple = tuple(args[idx] for idx in key_positions)
    value_tuple = tuple(args[idx] for idx in value_positions)
    ingested_at = _required_meta_time(ledger, claim.asrt_id, "ingested_at")
    source = _optional_meta_str(ledger, claim.asrt_id, "source")
    return MappingCandidate(
        asrt_id=claim.asrt_id,
        key_tuple=key_tuple,
        value_tuple=value_tuple,
        source=source,
        ingested_at=ingested_at,
    )


def _normalize_positions(raw: Any, arg_count: int, field_name: str) -> tuple[int, ...]:
    if not isinstance(raw, list):
        raise MappingResolveError(f"{field_name} must be list")
    out: list[int] = []
    last = -1
    for idx, value in enumerate(raw):
        if isinstance(value, bool) or not isinstance(value, int):
            raise MappingResolveError(f"{field_name}[{idx}] must be int")
        if value < 0 or value >= arg_count:
            raise MappingResolveError(f"{field_name}[{idx}] out of range")
        if value <= last:
            raise MappingResolveError(f"{field_name} must be strictly ascending")
        out.append(value)
        last = value
    return tuple(out)


def _normalize_tie_break(raw: Any) -> tuple[str, dict[str, Any]]:
    if raw is None:
        return "error", {}
    if isinstance(raw, str):
        mode = raw
        conf: dict[str, Any] = {}
    elif isinstance(raw, dict):
        mode = raw.get("mode")
        conf = dict(raw)
    else:
        raise MappingResolveError("tie_break must be null|string|object")

    if mode == "max_confidence":
        raise MappingResolveError("max_confidence tie_break was removed")
    if mode not in {"error", "latest_by_ingested_at_then_min_assertion_id", "prefer_source"}:
        raise MappingResolveError(f"unsupported tie_break mode: {mode}")
    return mode, conf


def _choose_with_tie_break(
    candidates: list[MappingCandidate],
    mode: str,
    conf: dict[str, Any],
    ledger: Ledger,
) -> MappingCandidate:
    if mode == "latest_by_ingested_at_then_min_assertion_id":
        return max(
            candidates,
            key=lambda c: (c.ingested_at, _invert_for_min_asrt(c.asrt_id)),
        )

    if mode == "prefer_source":
        source_rank = conf.get("source_rank")
        if not isinstance(source_rank, list) or not all(isinstance(x, str) for x in source_rank):
            raise MappingResolveError("prefer_source requires tie_break.source_rank string list")
        order = {name: idx for idx, name in enumerate(source_rank)}
        rank_sorted = sorted(
            candidates,
            key=lambda c: (
                order.get(c.source, len(order)),
                -c.ingested_at,
                c.asrt_id,
            ),
        )
        return rank_sorted[0]

    raise MappingResolveError(f"unsupported tie_break mode: {mode}")


def _required_meta_time(ledger: Ledger, asrt_id: str, key: str) -> int:
    rows = ledger._effective_meta_rows(asrt_id=asrt_id, key=key)
    if len(rows) != 1:
        raise MappingResolveError(f"{asrt_id} requires exactly one {key}")
    row = rows[0]
    if row.kind != "time" or isinstance(row.value, bool) or not isinstance(row.value, int):
        raise MappingResolveError(f"{asrt_id}.{key} must be meta_time int")
    return row.value


def _optional_meta_str(ledger: Ledger, asrt_id: str, key: str) -> str | None:
    rows = ledger._effective_meta_rows(asrt_id=asrt_id, key=key, kind="str")
    if not rows:
        return None
    value = rows[-1].value
    if not isinstance(value, str):
        return None
    return value


def _invert_for_min_asrt(asrt_id: str) -> tuple[int, ...]:
    return tuple(-ord(ch) for ch in asrt_id)
