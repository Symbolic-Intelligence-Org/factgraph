from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence, TypeAlias

from factgraph.core.protocol.digests import sha256_token

SupportRootResultKind: TypeAlias = Literal["fact", "entity", "row"]
BindingItems: TypeAlias = tuple[tuple[str, Any], ...]
DetailItems: TypeAlias = tuple[tuple[str, Any], ...]
ENGINE_NO_WITNESS_KIND = "engine_no_witness_v1"
SOUFFLE_WITNESS_KIND = "souffle_witness_v1"
PYREASON_PROVENANCE_KIND = "pyreason_provenance_v1"
PROBLOG_PROVENANCE_KIND = "problog_provenance_v1"
_DEGRADED_SUPPORT_KINDS = frozenset({"none", ENGINE_NO_WITNESS_KIND})
_WITNESS_BEARING_SUPPORT_KINDS = frozenset({"native_binding_v1", SOUFFLE_WITNESS_KIND})
_PROVENANCE_BEARING_SUPPORT_KINDS = frozenset(
    {PYREASON_PROVENANCE_KIND, PROBLOG_PROVENANCE_KIND}
)


@dataclass(frozen=True)
class ProjectedFact:
    asrt_id: str
    fact_tuple: tuple[Any, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.asrt_id, str) or not self.asrt_id:
            raise ValueError("ProjectedFact.asrt_id must be non-empty string")
        if not isinstance(self.fact_tuple, tuple):
            raise ValueError("ProjectedFact.fact_tuple must be tuple")


@dataclass(frozen=True)
class PredWitness:
    pred_atom_key: str
    asrt_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.pred_atom_key, str) or not self.pred_atom_key:
            raise ValueError("PredWitness.pred_atom_key must be non-empty string")
        if tuple(self.asrt_ids) != normalize_asrt_ids(self.asrt_ids):
            raise ValueError("PredWitness.asrt_ids must be sorted unique non-empty strings")


@dataclass(frozen=True)
class NonFactStep:
    step_key: str
    kind: str
    status: str
    details: DetailItems = ()

    def __post_init__(self) -> None:
        if not isinstance(self.step_key, str) or not self.step_key:
            raise ValueError("NonFactStep.step_key must be non-empty string")
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("NonFactStep.kind must be non-empty string")
        if not isinstance(self.status, str) or not self.status:
            raise ValueError("NonFactStep.status must be non-empty string")
        if tuple(self.details) != normalize_detail_items(self.details):
            raise ValueError("NonFactStep.details must be sorted key/value tuples")


@dataclass(frozen=True)
class RuleRefEdge:
    ruleref_atom_key: str
    rule_ref_id: str
    rule_ref_version: str
    child_support_digest: str | None = None
    unresolved_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ruleref_atom_key, str) or not self.ruleref_atom_key:
            raise ValueError("RuleRefEdge.ruleref_atom_key must be non-empty string")
        if not isinstance(self.rule_ref_id, str) or not self.rule_ref_id:
            raise ValueError("RuleRefEdge.rule_ref_id must be non-empty string")
        if not isinstance(self.rule_ref_version, str) or not self.rule_ref_version:
            raise ValueError("RuleRefEdge.rule_ref_version must be non-empty string")
        if self.child_support_digest is None and self.unresolved_reason is None:
            raise ValueError("RuleRefEdge must have child_support_digest or unresolved_reason")
        if self.child_support_digest is not None:
            if (
                not isinstance(self.child_support_digest, str)
                or not self.child_support_digest.startswith("sha256:")
            ):
                raise ValueError("RuleRefEdge.child_support_digest must be sha256 token")
            if self.unresolved_reason is not None:
                raise ValueError("resolved RuleRefEdge must not carry unresolved_reason")
        if self.unresolved_reason is not None and (
            not isinstance(self.unresolved_reason, str) or not self.unresolved_reason
        ):
            raise ValueError("RuleRefEdge.unresolved_reason must be non-empty string")


@dataclass(frozen=True)
class ProofReceipt:
    kind: str
    root_result_kind: SupportRootResultKind
    binding_items: BindingItems
    pred_witnesses: tuple[PredWitness, ...]
    non_fact_steps: tuple[NonFactStep, ...] = ()
    rule_refs: tuple[str, ...] = ()
    rule_ref_edges: tuple[RuleRefEdge, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("ProofReceipt.kind must be non-empty string")
        if self.root_result_kind not in {"fact", "entity", "row"}:
            raise ValueError("ProofReceipt.root_result_kind must be 'fact', 'entity', or 'row'")
        if tuple(self.binding_items) != normalize_binding_items(self.binding_items):
            raise ValueError("ProofReceipt.binding_items must be sorted binding tuples")
        if tuple(self.pred_witnesses) != tuple(
            sorted(self.pred_witnesses, key=lambda row: row.pred_atom_key)
        ):
            raise ValueError("ProofReceipt.pred_witnesses must be sorted by pred_atom_key")
        if tuple(self.non_fact_steps) != tuple(
            sorted(self.non_fact_steps, key=lambda row: (row.step_key, row.kind, row.status, row.details))
        ):
            raise ValueError("ProofReceipt.non_fact_steps must be sorted")
        normalized_rule_refs = tuple(sorted(_normalize_non_empty_strings(self.rule_refs)))
        if tuple(self.rule_refs) != normalized_rule_refs:
            raise ValueError("ProofReceipt.rule_refs must be sorted unique non-empty strings")
        normalized_rule_ref_edges = tuple(sorted(self.rule_ref_edges, key=_rule_ref_edge_sort_key))
        if tuple(self.rule_ref_edges) != normalized_rule_ref_edges:
            raise ValueError("ProofReceipt.rule_ref_edges must be sorted")


@dataclass(frozen=True)
class BindingSupportCapture:
    binding_items: BindingItems
    support_digest: str
    support_kind: str

    def __post_init__(self) -> None:
        if tuple(self.binding_items) != normalize_binding_items(self.binding_items):
            raise ValueError("BindingSupportCapture.binding_items must be sorted binding tuples")
        if not isinstance(self.support_kind, str) or not self.support_kind:
            raise ValueError("BindingSupportCapture.support_kind must be non-empty string")
        if not isinstance(self.support_digest, str) or not self.support_digest.startswith("sha256:"):
            raise ValueError("BindingSupportCapture.support_digest must be sha256 token")

    def binding_dict(self) -> dict[str, Any]:
        return binding_dict_from_items(self.binding_items)


@dataclass(frozen=True)
class ProvenanceEnvelope:
    candidate_id: str
    engine: str
    payload_type: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_id, str) or not self.candidate_id:
            raise ValueError("ProvenanceEnvelope.candidate_id must be non-empty string")
        if not isinstance(self.engine, str) or not self.engine:
            raise ValueError("ProvenanceEnvelope.engine must be non-empty string")
        if not isinstance(self.payload_type, str) or not self.payload_type:
            raise ValueError("ProvenanceEnvelope.payload_type must be non-empty string")
        if not isinstance(self.payload, dict):
            raise ValueError("ProvenanceEnvelope.payload must be dict")


def normalize_binding_items(binding: Mapping[str, Any] | Sequence[tuple[str, Any]]) -> BindingItems:
    if isinstance(binding, Mapping):
        items = list(binding.items())
    else:
        items = list(binding)
    normalized: list[tuple[str, Any]] = []
    for key, value in items:
        if not isinstance(key, str) or not key:
            raise ValueError("binding keys must be non-empty strings")
        normalized.append((key, value))
    normalized.sort(key=lambda item: item[0])
    return tuple(normalized)


def binding_dict_from_items(binding_items: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    return {key: value for key, value in normalize_binding_items(binding_items)}


def normalize_detail_items(details: Mapping[str, Any] | Sequence[tuple[str, Any]]) -> DetailItems:
    if isinstance(details, Mapping):
        items = list(details.items())
    else:
        items = list(details)
    normalized: list[tuple[str, Any]] = []
    for key, value in items:
        if not isinstance(key, str) or not key:
            raise ValueError("detail keys must be non-empty strings")
        normalized.append((key, value))
    normalized.sort(key=lambda item: item[0])
    return tuple(normalized)


def normalize_asrt_ids(asrt_ids: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(_normalize_non_empty_strings(asrt_ids)))


def make_pred_atom_key(
    branch_index: int,
    atom_index: int,
    pred_id: str,
) -> str:
    if isinstance(branch_index, bool) or not isinstance(branch_index, int) or branch_index < 0:
        raise ValueError("branch_index must be non-negative int")
    if isinstance(atom_index, bool) or not isinstance(atom_index, int) or atom_index < 0:
        raise ValueError("atom_index must be non-negative int")
    if not isinstance(pred_id, str) or not pred_id:
        raise ValueError("pred_id must be non-empty string")
    return f"b{branch_index}.a{atom_index}:{pred_id}"


def make_non_fact_step_key(
    branch_index: int,
    atom_index: int,
    kind: str,
) -> str:
    if isinstance(branch_index, bool) or not isinstance(branch_index, int) or branch_index < 0:
        raise ValueError("branch_index must be non-negative int")
    if isinstance(atom_index, bool) or not isinstance(atom_index, int) or atom_index < 0:
        raise ValueError("atom_index must be non-negative int")
    if not isinstance(kind, str) or not kind:
        raise ValueError("kind must be non-empty string")
    return f"b{branch_index}.a{atom_index}:{kind}"


def support_artifact_to_dict(artifact: ProofReceipt) -> dict[str, Any]:
    # This shape is optimized for canonical digest/round-trip stability, not display formatting.
    return {
        "kind": artifact.kind,
        "root_result_kind": artifact.root_result_kind,
        "binding": [[key, _to_jsonable(value)] for key, value in artifact.binding_items],
        "pred_witnesses": [
            {
                "pred_atom_key": row.pred_atom_key,
                "asrt_ids": list(row.asrt_ids),
            }
            for row in artifact.pred_witnesses
        ],
        "non_fact_steps": [
            {
                "step_key": row.step_key,
                "kind": row.kind,
                "status": row.status,
                "details": [[key, _to_jsonable(value)] for key, value in row.details],
            }
            for row in artifact.non_fact_steps
        ],
        "rule_refs": list(artifact.rule_refs),
        "rule_ref_edges": [
            {
                "ruleref_atom_key": row.ruleref_atom_key,
                "rule_ref_id": row.rule_ref_id,
                "rule_ref_version": row.rule_ref_version,
                "child_support_digest": row.child_support_digest,
                "unresolved_reason": row.unresolved_reason,
            }
            for row in artifact.rule_ref_edges
        ],
    }


def support_artifact_from_dict(row: Mapping[str, Any]) -> ProofReceipt:
    if not isinstance(row, Mapping):
        raise ValueError("row must be Mapping[str, Any]")
    return ProofReceipt(
        kind=row["kind"],
        root_result_kind=row["root_result_kind"],
        binding_items=tuple((key, _from_jsonable(value)) for key, value in row["binding"]),
        pred_witnesses=tuple(
            PredWitness(
                pred_atom_key=item["pred_atom_key"],
                asrt_ids=tuple(item["asrt_ids"]),
            )
            for item in row["pred_witnesses"]
        ),
        non_fact_steps=tuple(
            NonFactStep(
                step_key=item["step_key"],
                kind=item["kind"],
                status=item["status"],
                details=tuple((key, _from_jsonable(value)) for key, value in item["details"]),
            )
            for item in row.get("non_fact_steps", ())
        ),
        rule_refs=tuple(row.get("rule_refs", ())),
        rule_ref_edges=tuple(
            RuleRefEdge(
                ruleref_atom_key=item["ruleref_atom_key"],
                rule_ref_id=item["rule_ref_id"],
                rule_ref_version=item["rule_ref_version"],
                child_support_digest=item.get("child_support_digest"),
                unresolved_reason=item.get("unresolved_reason"),
            )
            for item in row.get("rule_ref_edges", ())
        ),
    )


def support_artifact_bytes(artifact: ProofReceipt) -> bytes:
    return json.dumps(
        support_artifact_to_dict(artifact),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_support_digest(artifact: ProofReceipt) -> str:
    return sha256_token(support_artifact_bytes(artifact))


def provenance_envelope_to_dict(envelope: ProvenanceEnvelope) -> dict[str, Any]:
    return {
        "candidate_id": envelope.candidate_id,
        "engine": envelope.engine,
        "payload_type": envelope.payload_type,
        "payload": _to_jsonable(envelope.payload),
    }


def provenance_envelope_from_dict(row: Mapping[str, Any]) -> ProvenanceEnvelope:
    if not isinstance(row, Mapping):
        raise ValueError("row must be Mapping[str, Any]")
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("row.payload must be Mapping[str, Any]")
    return ProvenanceEnvelope(
        candidate_id=row["candidate_id"],
        engine=row["engine"],
        payload_type=row["payload_type"],
        payload={str(key): _from_jsonable(value) for key, value in payload.items()},
    )


def provenance_envelope_bytes(envelope: ProvenanceEnvelope) -> bytes:
    return json.dumps(
        provenance_envelope_to_dict(envelope),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def compute_provenance_digest(envelope: ProvenanceEnvelope) -> str:
    return sha256_token(provenance_envelope_bytes(envelope))


def _normalize_non_empty_strings(values: Sequence[str]) -> set[str]:
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value:
            raise ValueError("expected non-empty strings")
        normalized.add(value)
    return normalized


def _rule_ref_edge_sort_key(edge: RuleRefEdge) -> tuple[str, str, str, str]:
    return (
        edge.ruleref_atom_key,
        edge.rule_ref_id,
        edge.rule_ref_version,
        edge.child_support_digest or "",
    )


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _to_jsonable(item)
            for key, item in sorted(value.items(), key=lambda row: str(row[0]))
        }
    return value


def _from_jsonable(value: Any) -> Any:
    if isinstance(value, dict) and tuple(value.keys()) == ("__bytes_hex__",):
        return bytes.fromhex(value["__bytes_hex__"])
    if isinstance(value, list):
        return [_from_jsonable(item) for item in value]
    return value


__all__ = [
    "BindingSupportCapture",
    "BindingItems",
    "DetailItems",
    "ENGINE_NO_WITNESS_KIND",
    "NonFactStep",
    "PredWitness",
    "ProjectedFact",
    "PROBLOG_PROVENANCE_KIND",
    "PYREASON_PROVENANCE_KIND",
    "ProvenanceEnvelope",
    "RuleRefEdge",
    "SOUFFLE_WITNESS_KIND",
    "ProofReceipt",
    "SupportRootResultKind",
    "_DEGRADED_SUPPORT_KINDS",
    "_PROVENANCE_BEARING_SUPPORT_KINDS",
    "_WITNESS_BEARING_SUPPORT_KINDS",
    "binding_dict_from_items",
    "compute_provenance_digest",
    "compute_support_digest",
    "make_non_fact_step_key",
    "make_pred_atom_key",
    "normalize_asrt_ids",
    "normalize_binding_items",
    "normalize_detail_items",
    "provenance_envelope_bytes",
    "provenance_envelope_from_dict",
    "provenance_envelope_to_dict",
    "support_artifact_bytes",
    "support_artifact_from_dict",
    "support_artifact_to_dict",
]
