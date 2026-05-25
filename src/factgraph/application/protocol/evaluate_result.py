from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
import json
import math
from types import MappingProxyType
from typing import Any, Literal
import uuid

from factgraph.application.protocol.common import ErrorDTO, ProtocolShapeError, WarningDTO
from factgraph.application.protocol.rule import Rule, _is_projection_rule
from factgraph.application.protocol.rule_expr import RuleExprError
from factgraph.application.protocol.rule_expr_inspect import _inspect_closed_head
from factgraph.application.protocol.schema_runtime import EntityRef
from factgraph.audit.evidence_graph import EvidenceGraph, EvidenceNode, NODE_CONCLUSION
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom
from factgraph.core.semantics.profile import SemanticsProfile
from factgraph.core.store.database import view_digest_for


class DetachedRowError(RuntimeError):
    """Raised when a live-only row operation is requested from a detached row."""


ClaimKind = Literal["fact_triple", "rule_head", "aggregate_result", "projection"]
RawKind = Literal["probabilistic", "possibilistic"]
ExplanationStatus = Literal["passed", "failed", "unsupported", "invalid_request"]
ExplanationFailureClass = Literal[
    "no_matching_row",
    "closed_head_false",
    "stale_row",
    "row_not_in_result",
    "insufficient_closed_bindings",
]
_CLAIM_KINDS = frozenset({"fact_triple", "rule_head", "aggregate_result", "projection"})
_RAW_KINDS = frozenset({"probabilistic", "possibilistic"})
_EXPLANATION_STATUSES = frozenset({"passed", "failed", "unsupported", "invalid_request"})
_EXPLANATION_FAILURE_CLASSES = frozenset(
    {"no_matching_row", "closed_head_false", "stale_row", "row_not_in_result", "insufficient_closed_bindings"}
)
_SHA256_TOKEN_PREFIX = "sha256:"
_SHA256_HEX_LEN = 64
_RESULT_ID_PREFIX = "evalr_v1:"
_EVIDENCE_REF_ID_PREFIX = "evref_v1:"
_RUN_ID_PREFIX = "run_v1:"


@dataclass(frozen=True)
class Claim:
    kind: ClaimKind
    name: str
    arguments: Mapping[str, Any]
    repr: str
    digest: str

    def __post_init__(self) -> None:
        if self.kind not in _CLAIM_KINDS:
            raise ProtocolShapeError("Claim.kind must be one of fact_triple, rule_head, aggregate_result, projection")
        _require_non_empty_str(self.name, field_name="Claim.name")
        _require_non_empty_str(self.repr, field_name="Claim.repr")
        _require_sha256_token(self.digest, field_name="Claim.digest")
        object.__setattr__(self, "arguments", _freeze_mapping(self.arguments, field_name="Claim.arguments"))


@dataclass(frozen=True)
class EvidenceRef:
    ref_id: str
    result_id: str
    row_id: str
    fact_digest: str
    closed_head_digest: str

    def __post_init__(self) -> None:
        _require_token_prefix(self.ref_id, prefix=_EVIDENCE_REF_ID_PREFIX, field_name="EvidenceRef.ref_id")
        _require_token_prefix(self.result_id, prefix=_RESULT_ID_PREFIX, field_name="EvidenceRef.result_id")
        _require_non_empty_str(self.row_id, field_name="EvidenceRef.row_id")
        _require_sha256_token(self.fact_digest, field_name="EvidenceRef.fact_digest")
        _require_sha256_token(self.closed_head_digest, field_name="EvidenceRef.closed_head_digest")


@dataclass(frozen=True)
class EvaluateRow:
    row_id: str
    bindings: Mapping[str, Any]
    claim: Claim
    raw_kind: RawKind | None
    bound: tuple[float, float] | None
    evidence_ref: EvidenceRef
    _result_resolver: Callable[[], EvaluateResult] | None = field(default=None, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.row_id, field_name="EvaluateRow.row_id")
        object.__setattr__(self, "bindings", _freeze_mapping(self.bindings, field_name="EvaluateRow.bindings"))
        if not isinstance(self.claim, Claim):
            raise ProtocolShapeError("EvaluateRow.claim must be Claim")
        if not isinstance(self.evidence_ref, EvidenceRef):
            raise ProtocolShapeError("EvaluateRow.evidence_ref must be EvidenceRef")
        if self.evidence_ref.row_id != self.row_id:
            raise ProtocolShapeError("EvaluateRow.evidence_ref.row_id must equal EvaluateRow.row_id")
        if self.evidence_ref.fact_digest != self.claim.digest:
            raise ProtocolShapeError("EvaluateRow.evidence_ref.fact_digest must equal EvaluateRow.claim.digest")
        if self.raw_kind is None:
            if self.bound is not None:
                raise ProtocolShapeError("EvaluateRow.bound must be None when raw_kind is None")
        else:
            if self.raw_kind not in _RAW_KINDS:
                raise ProtocolShapeError("EvaluateRow.raw_kind must be probabilistic, possibilistic, or None")
            object.__setattr__(self, "bound", _validate_bound(self.bound))
        if self._result_resolver is not None and not callable(self._result_resolver):
            raise ProtocolShapeError("EvaluateRow._result_resolver must be callable or None")

    def _require_live_result(self) -> EvaluateResult:
        if self._result_resolver is None:
            raise DetachedRowError("EvaluateRow is detached from its EvaluateResult")
        return self._result_resolver()

    def explain(self) -> Explanation:
        return _explain_live_row(self, self._require_live_result())

    def close(self) -> Rule:
        return _close_live_row(self, self._require_live_result())


@dataclass(frozen=True)
class EvaluateResult:
    result_id: str
    run_id: str
    rows: tuple[EvaluateRow, ...]
    head: Rule
    engine: str
    engine_version: str | None
    adapter_version: str | None
    expr_digest: str
    rule_set_digest: str
    view_snapshot_digest: str
    semantics_digest: str | None
    evaluated_at: object
    result_digest: str
    _schema_index: object | None = field(default=None, repr=False, compare=False, hash=False)
    _row_close_builder: Callable[[EvaluateRow, EvaluateResult], Rule] | None = field(
        default=None,
        repr=False,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        _require_token_prefix(self.result_id, prefix=_RESULT_ID_PREFIX, field_name="EvaluateResult.result_id")
        _require_token_prefix(self.run_id, prefix=_RUN_ID_PREFIX, field_name="EvaluateResult.run_id")
        if not isinstance(self.head, Rule):
            raise ProtocolShapeError("EvaluateResult.head must be application protocol Rule")
        _require_non_empty_str(self.engine, field_name="EvaluateResult.engine")
        _require_optional_non_empty_str(self.engine_version, field_name="EvaluateResult.engine_version")
        _require_optional_non_empty_str(self.adapter_version, field_name="EvaluateResult.adapter_version")
        _require_sha256_token(self.expr_digest, field_name="EvaluateResult.expr_digest")
        _require_sha256_token(self.rule_set_digest, field_name="EvaluateResult.rule_set_digest")
        _require_sha256_token(self.view_snapshot_digest, field_name="EvaluateResult.view_snapshot_digest")
        if self.semantics_digest is not None:
            _require_sha256_token(self.semantics_digest, field_name="EvaluateResult.semantics_digest")
        _require_sha256_token(self.result_digest, field_name="EvaluateResult.result_digest")
        if self._row_close_builder is not None and not callable(self._row_close_builder):
            raise ProtocolShapeError("EvaluateResult._row_close_builder must be callable or None")

        if not isinstance(self.rows, tuple):
            raise ProtocolShapeError("EvaluateResult.rows must be tuple[EvaluateRow, ...]")
        seen: set[str] = set()
        bound_rows: list[EvaluateRow] = []
        for idx, row in enumerate(self.rows):
            if not isinstance(row, EvaluateRow):
                raise ProtocolShapeError(f"EvaluateResult.rows[{idx}] must be EvaluateRow")
            if row.row_id in seen:
                raise ProtocolShapeError(f"EvaluateResult.rows contains duplicate row_id: {row.row_id!r}")
            seen.add(row.row_id)
            if row.evidence_ref.result_id != self.result_id:
                raise ProtocolShapeError("EvaluateRow.evidence_ref.result_id must equal EvaluateResult.result_id")
            bound_rows.append(replace(row, _result_resolver=lambda self_ref=self: self_ref))
        object.__setattr__(self, "rows", tuple(bound_rows))

    def __iter__(self) -> Iterator[EvaluateRow]:
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> EvaluateRow:
        return self.rows[index]

    def first(self) -> EvaluateRow | None:
        return self.rows[0] if self.rows else None

    def exists(self) -> bool:
        return bool(self.rows)

    def count(self) -> int:
        return len(self.rows)


@dataclass(frozen=True)
class Explanation:
    status: ExplanationStatus
    evidence: EvidenceGraph | None
    claim: Claim | None
    result_id: str | None
    row_id: str | None
    evidence_ref_id: str | None
    raw_kind: RawKind | None = None
    bound: tuple[float, float] | None = None
    failure_class: ExplanationFailureClass | None = None
    checked_scope: Mapping[str, Any] | None = None
    suggested_next_steps: tuple[str, ...] = ()
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in _EXPLANATION_STATUSES:
            raise ProtocolShapeError("Explanation.status must be one of passed, failed, unsupported, invalid_request")
        if (self.status == "passed") != (self.evidence is not None):
            raise ProtocolShapeError("Explanation.status='passed' iff Explanation.evidence is not None")
        if self.evidence is not None and not isinstance(self.evidence, EvidenceGraph):
            raise ProtocolShapeError("Explanation.evidence must be EvidenceGraph or None")
        if self.claim is not None and not isinstance(self.claim, Claim):
            raise ProtocolShapeError("Explanation.claim must be Claim or None")

        _require_optional_token_prefix(self.result_id, prefix=_RESULT_ID_PREFIX, field_name="Explanation.result_id")
        _require_optional_non_empty_str(self.row_id, field_name="Explanation.row_id")
        _require_optional_token_prefix(
            self.evidence_ref_id,
            prefix=_EVIDENCE_REF_ID_PREFIX,
            field_name="Explanation.evidence_ref_id",
        )

        if self.status == "passed":
            if self.claim is None:
                raise ProtocolShapeError("Explanation.claim is required when status is passed")
            _require_non_empty_str(self.result_id, field_name="Explanation.result_id")
        if self.status == "failed":
            if self.failure_class not in _EXPLANATION_FAILURE_CLASSES:
                raise ProtocolShapeError("Explanation.failure_class is required when status is failed")
        elif self.failure_class is not None:
            raise ProtocolShapeError("Explanation.failure_class must be None unless status is failed")
        if self.status in {"unsupported", "invalid_request"} and not self.errors:
            raise ProtocolShapeError("Explanation.errors must be non-empty when status is unsupported or invalid_request")

        if self.raw_kind is None:
            if self.bound is not None:
                raise ProtocolShapeError("Explanation.bound must be None when raw_kind is None")
        else:
            if self.raw_kind not in _RAW_KINDS:
                raise ProtocolShapeError("Explanation.raw_kind must be probabilistic, possibilistic, or None")
            object.__setattr__(self, "bound", _validate_bound(self.bound))

        if self.checked_scope is not None:
            object.__setattr__(
                self,
                "checked_scope",
                _freeze_mapping(self.checked_scope, field_name="Explanation.checked_scope"),
            )
        object.__setattr__(
            self,
            "suggested_next_steps",
            _validate_tuple_of_type(self.suggested_next_steps, str, field_name="Explanation.suggested_next_steps"),
        )
        object.__setattr__(self, "errors", _validate_tuple_of_type(self.errors, ErrorDTO, field_name="Explanation.errors"))
        object.__setattr__(
            self,
            "warnings",
            _validate_tuple_of_type(self.warnings, WarningDTO, field_name="Explanation.warnings"),
        )


def canonical_bytes_for_evaluate(*items: Any) -> bytes:
    return json.dumps(
        _normalize_for_canonical(items),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def new_run_id() -> str:
    return f"{_RUN_ID_PREFIX}{uuid.uuid4().hex}{uuid.uuid4().hex}"


def result_id_for(
    *,
    run_id: str,
    expr_digest: str,
    rule_set_digest: str,
    view_snapshot_digest: str,
    semantics_digest: str | None,
    engine: str,
    head_id: str,
    head_content_digest: str,
) -> str:
    _require_token_prefix(run_id, prefix=_RUN_ID_PREFIX, field_name="run_id")
    _require_sha256_token(expr_digest, field_name="expr_digest")
    _require_sha256_token(rule_set_digest, field_name="rule_set_digest")
    _require_sha256_token(view_snapshot_digest, field_name="view_snapshot_digest")
    if semantics_digest is not None:
        _require_sha256_token(semantics_digest, field_name="semantics_digest")
    _require_non_empty_str(engine, field_name="engine")
    _require_non_empty_str(head_id, field_name="head_id")
    _require_sha256_hex(head_content_digest, field_name="head_content_digest")
    digest = sha256_hex(
        canonical_bytes_for_evaluate(
            "evaluate_result_id_v1",
            {
                "engine": engine,
                "expr_digest": expr_digest,
                "head_content_digest": head_content_digest,
                "head_id": head_id,
                "rule_set_digest": rule_set_digest,
                "run_id": run_id,
                "semantics_digest": semantics_digest,
                "view_snapshot_digest": view_snapshot_digest,
            },
        )
    )
    return f"{_RESULT_ID_PREFIX}{digest}"


def row_id_for(run_id: str, bindings: Mapping[str, Any]) -> str:
    _require_token_prefix(run_id, prefix=_RUN_ID_PREFIX, field_name="run_id")
    frozen = _freeze_mapping(bindings, field_name="bindings")
    digest = sha256_hex(canonical_bytes_for_evaluate("evaluate_row_id_v1", frozen))[:16]
    return f"{run_id}:{digest}"


def claim_digest_for(kind: ClaimKind, name: str, arguments: Mapping[str, Any]) -> str:
    if kind not in _CLAIM_KINDS:
        raise ProtocolShapeError("kind must be one of fact_triple, rule_head, aggregate_result, projection")
    _require_non_empty_str(name, field_name="name")
    frozen = _freeze_mapping(arguments, field_name="arguments")
    return sha256_token(canonical_bytes_for_evaluate("evaluate_claim_v1", kind, name, frozen))


def closed_head_digest_for_parts(closed_head_id: str, closed_head_content_digest: str) -> str:
    _require_non_empty_str(closed_head_id, field_name="closed_head_id")
    _require_sha256_hex(closed_head_content_digest, field_name="closed_head_content_digest")
    return sha256_token(
        canonical_bytes_for_evaluate(
            "evaluate_closed_head_v1",
            {"id": closed_head_id, "content_digest": closed_head_content_digest},
        )
    )


def closed_head_digest_for(closed_head: Rule) -> str:
    if not isinstance(closed_head, Rule):
        raise ProtocolShapeError("closed_head must be application protocol Rule")
    return closed_head_digest_for_parts(closed_head.id, closed_head.content_digest)


def evidence_ref_id_for(result_id: str, row_id: str, fact_digest: str, closed_head_digest: str) -> str:
    _require_token_prefix(result_id, prefix=_RESULT_ID_PREFIX, field_name="result_id")
    _require_non_empty_str(row_id, field_name="row_id")
    _require_sha256_token(fact_digest, field_name="fact_digest")
    _require_sha256_token(closed_head_digest, field_name="closed_head_digest")
    digest = sha256_hex(
        canonical_bytes_for_evaluate(
            "evaluate_evidence_ref_v1",
            {
                "closed_head_digest": closed_head_digest,
                "fact_digest": fact_digest,
                "result_id": result_id,
                "row_id": row_id,
            },
        )
    )
    return f"{_EVIDENCE_REF_ID_PREFIX}{digest}"


def _row_digest_for(row: EvaluateRow) -> str:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    return sha256_token(
        canonical_bytes_for_evaluate(
            "evaluate_row_digest_v1",
            {
                "bindings": row.bindings,
                "bound": row.bound,
                "claim": {
                    "arguments": row.claim.arguments,
                    "digest": row.claim.digest,
                    "kind": row.claim.kind,
                    "name": row.claim.name,
                    "repr": row.claim.repr,
                },
                "evidence_ref": {
                    "closed_head_digest": row.evidence_ref.closed_head_digest,
                    "fact_digest": row.evidence_ref.fact_digest,
                    "result_id": row.evidence_ref.result_id,
                    "row_id": row.evidence_ref.row_id,
                },
                "raw_kind": row.raw_kind,
                "row_id": row.row_id,
            },
        )
    )


def result_digest_for(
    *,
    result_id: str,
    run_id: str,
    row_digests: Sequence[str],
    head_id: str,
    head_content_digest: str,
    engine: str,
    engine_version: str | None,
    adapter_version: str | None,
    expr_digest: str,
    rule_set_digest: str,
    view_snapshot_digest: str,
    semantics_digest: str | None,
) -> str:
    _require_token_prefix(result_id, prefix=_RESULT_ID_PREFIX, field_name="result_id")
    _require_token_prefix(run_id, prefix=_RUN_ID_PREFIX, field_name="run_id")
    for idx, digest in enumerate(row_digests):
        _require_sha256_token(digest, field_name=f"row_digests[{idx}]")
    _require_non_empty_str(head_id, field_name="head_id")
    _require_sha256_hex(head_content_digest, field_name="head_content_digest")
    _require_non_empty_str(engine, field_name="engine")
    _require_optional_non_empty_str(engine_version, field_name="engine_version")
    _require_optional_non_empty_str(adapter_version, field_name="adapter_version")
    _require_sha256_token(expr_digest, field_name="expr_digest")
    _require_sha256_token(rule_set_digest, field_name="rule_set_digest")
    _require_sha256_token(view_snapshot_digest, field_name="view_snapshot_digest")
    if semantics_digest is not None:
        _require_sha256_token(semantics_digest, field_name="semantics_digest")
    return sha256_token(
        canonical_bytes_for_evaluate(
            "evaluate_result_digest_v1",
            {
                "adapter_version": adapter_version,
                "engine": engine,
                "engine_version": engine_version,
                "expr_digest": expr_digest,
                "head_content_digest": head_content_digest,
                "head_id": head_id,
                "result_id": result_id,
                "row_digests": tuple(row_digests),
                "rule_set_digest": rule_set_digest,
                "run_id": run_id,
                "semantics_digest": semantics_digest,
                "view_snapshot_digest": view_snapshot_digest,
            },
        )
    )


def semantics_digest_for(profile: SemanticsProfile | None) -> str | None:
    if profile is None:
        return None
    if not isinstance(profile, SemanticsProfile):
        raise ProtocolShapeError("profile must be SemanticsProfile or None")
    payload = {
        "certainty_projection": profile.certainty_projection,
        "engine": profile.engine,
        "engine_options": profile.engine_options,
        "fallback": profile.fallback,
        "name": profile.name,
        "output_readback": profile.output_readback,
        "rule_projection": profile.rule_projection,
        "temporal_projection": profile.temporal_projection,
        "uncertainty_projection": profile.uncertainty_projection,
        "version": profile.version,
    }
    return sha256_token(canonical_bytes_for_evaluate("evaluate_semantics_profile_v1", payload))


def view_snapshot_digest_for_parts(
    *,
    db_id: str,
    base_tx_id: str,
    schema_digest: str,
    asrt_ids: Iterable[str],
) -> str:
    _require_non_empty_str(db_id, field_name="db_id")
    _require_non_empty_str(base_tx_id, field_name="base_tx_id")
    _require_sha256_token(schema_digest, field_name="schema_digest")
    normalized_asrt_ids = tuple(asrt_ids)
    return view_digest_for(db_id=db_id, base_tx_id=base_tx_id, schema_digest=schema_digest, asrt_ids=normalized_asrt_ids)


def expr_digest_for_payload(kind: str, payload: Mapping[str, Any]) -> str:
    _require_non_empty_str(kind, field_name="kind")
    frozen = _freeze_mapping(payload, field_name="payload")
    return sha256_token(canonical_bytes_for_evaluate("evaluate_expr_digest_v1", kind, frozen))


def rule_set_digest_for_entries(entries: Iterable[tuple[str, str]]) -> str:
    normalized: list[tuple[str, str]] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ProtocolShapeError(f"entries[{idx}] must be tuple[str, str]")
        rule_id, content_digest = entry
        _require_non_empty_str(rule_id, field_name=f"entries[{idx}].rule_id")
        _require_sha256_hex(content_digest, field_name=f"entries[{idx}].content_digest")
        normalized.append((rule_id, content_digest))
    if not normalized:
        raise ProtocolShapeError("entries must be non-empty")
    return sha256_token(canonical_bytes_for_evaluate("evaluate_rule_set_digest_v1", tuple(sorted(normalized))))


def _candidate_set_to_evaluate_row(
    candidate: CandidateSet,
    *,
    result_id: str,
    run_id: str,
    closed_head_digest: str,
    claim_kind: ClaimKind = "fact_triple",
    claim_name: str | None = None,
) -> EvaluateRow:
    if not isinstance(candidate, CandidateSet):
        raise ProtocolShapeError("candidate must be CandidateSet")
    _require_token_prefix(result_id, prefix=_RESULT_ID_PREFIX, field_name="result_id")
    _require_token_prefix(run_id, prefix=_RUN_ID_PREFIX, field_name="run_id")
    _require_sha256_token(closed_head_digest, field_name="closed_head_digest")
    bindings = _bindings_from_candidate(candidate)
    effective_claim_name = candidate.target if claim_name is None else claim_name
    digest = claim_digest_for(claim_kind, effective_claim_name, bindings)
    claim = Claim(
        kind=claim_kind,
        name=effective_claim_name,
        arguments=bindings,
        repr=f"{effective_claim_name}{dict(bindings)!r}",
        digest=digest,
    )
    row_id = row_id_for(run_id, bindings)
    evidence_ref = EvidenceRef(
        ref_id=evidence_ref_id_for(result_id, row_id, digest, closed_head_digest),
        result_id=result_id,
        row_id=row_id,
        fact_digest=digest,
        closed_head_digest=closed_head_digest,
    )
    raw_kind, bound = _raw_kind_and_bound_from_candidate(candidate)
    return EvaluateRow(
        row_id=row_id,
        bindings=bindings,
        claim=claim,
        raw_kind=raw_kind,
        bound=bound,
        evidence_ref=evidence_ref,
    )


def _explain_live_row(
    row: EvaluateRow,
    result: EvaluateResult,
    *,
    graph_builder: Callable[[EvaluateRow, EvaluateResult, Mapping[str, Any]], EvidenceGraph] | None = None,
) -> Explanation:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    if not isinstance(result, EvaluateResult):
        raise ProtocolShapeError("result must be EvaluateResult")

    checked_scope = _checked_scope_for_row_result(result, row)
    matched = next((candidate for candidate in result.rows if candidate.row_id == row.row_id), None)
    if matched is None:
        return Explanation(
            status="failed",
            evidence=None,
            claim=row.claim,
            result_id=result.result_id,
            row_id=row.row_id,
            evidence_ref_id=row.evidence_ref.ref_id,
            raw_kind=row.raw_kind,
            bound=row.bound,
            failure_class="row_not_in_result",
            checked_scope=checked_scope,
            suggested_next_steps=("Re-evaluate the expression and explain a row from the returned result.",),
        )

    if not _row_anchor_matches(matched, row, result):
        return Explanation(
            status="failed",
            evidence=None,
            claim=row.claim,
            result_id=result.result_id,
            row_id=row.row_id,
            evidence_ref_id=row.evidence_ref.ref_id,
            raw_kind=row.raw_kind,
            bound=row.bound,
            failure_class="stale_row",
            checked_scope=checked_scope,
            suggested_next_steps=("Use a row from the current EvaluateResult before calling explain().",),
        )

    metadata = _evidence_metadata_for_row_result(row, result)
    builder = _build_passed_row_evidence_graph if graph_builder is None else graph_builder
    try:
        evidence = builder(row, result, metadata)
    except ValueError as exc:
        return Explanation(
            status="unsupported",
            evidence=None,
            claim=row.claim,
            result_id=result.result_id,
            row_id=row.row_id,
            evidence_ref_id=row.evidence_ref.ref_id,
            raw_kind=row.raw_kind,
            bound=row.bound,
            checked_scope=checked_scope,
            errors=(
                ErrorDTO(
                    code="GRAPH_VALIDATION_FAILED",
                    message=str(exc) or "EvidenceGraph validation failed",
                    details={"row_id": row.row_id},
                ),
            ),
        )

    return Explanation(
        status="passed",
        evidence=evidence,
        claim=row.claim,
        result_id=result.result_id,
        row_id=row.row_id,
        evidence_ref_id=row.evidence_ref.ref_id,
        raw_kind=row.raw_kind,
        bound=row.bound,
        checked_scope=checked_scope,
    )


def _close_live_row(row: EvaluateRow, result: EvaluateResult) -> Rule:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    if not isinstance(result, EvaluateResult):
        raise ProtocolShapeError("result must be EvaluateResult")
    if result._row_close_builder is not None:
        return result._row_close_builder(row, result)
    return _build_closed_head_from_row(row, result, schema_index=result._schema_index)


def _build_closed_head_from_row(
    row: EvaluateRow,
    result: EvaluateResult,
    *,
    schema_index: object | None = None,
    entity_identity_resolver: Callable[[str, object, object | None], Mapping[str, Any]] | None = None,
) -> Rule:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    if not isinstance(result, EvaluateResult):
        raise ProtocolShapeError("result must be EvaluateResult")

    matched = next((candidate for candidate in result.rows if candidate.row_id == row.row_id), None)
    if matched is None or not _row_anchor_matches(matched, row, result):
        raise DetachedRowError("EvaluateRow is stale or does not belong to its EvaluateResult")

    head = result.head
    closure_atoms: list[object] = []
    for port_name, port_var in head.ports.items():
        value = _binding_value_for_head_port(row, head, port_name)
        port_type = head.port_types[port_name]
        if port_type.kind == "value":
            closure_atoms.append(CmpAtom("eq", port_var, Const(value)))
            continue
        closure_atoms.extend(
            _entity_identity_closure_atoms(
                port_var,
                port_type.entity_type,
                value,
                schema_index=schema_index,
                entity_identity_resolver=entity_identity_resolver,
            )
        )

    base_where = () if _is_projection_rule(head) else tuple(head.where)
    closed = Rule(
        id=f"{head.id}_closed_{row.row_id}",
        where=tuple(base_where) + tuple(closure_atoms),
        ports=dict(head.ports),
        version=head.version,
        desc=head.desc,
    )
    inspected = _inspect_closed_head(closed, schema_index=schema_index)
    if not inspected.is_closed:
        missing = ", ".join(inspected.unbound_ports)
        raise RuleExprError(f"closed head construction left unbound ports: {missing}")
    return closed


def _binding_value_for_head_port(row: EvaluateRow, head: Rule, port_name: str) -> object:
    if port_name in row.bindings:
        return row.bindings[port_name]
    terms = row.bindings.get("terms")
    if isinstance(terms, Sequence):
        port_names = tuple(head.ports)
        try:
            idx = port_names.index(port_name)
        except ValueError:  # pragma: no cover - guarded by head.ports iteration
            idx = -1
        if 0 <= idx < len(terms):
            return _public_term_value(terms[idx])
    raise RuleExprError(f"cannot close head port {port_name!r}: row binding is missing")


def _public_term_value(value: object) -> object:
    if isinstance(value, Mapping) and "value" in value:
        return value["value"]
    return value


def _entity_identity_closure_atoms(
    port_var: object,
    entity_type: str | None,
    value: object,
    *,
    schema_index: object | None,
    entity_identity_resolver: Callable[[str, object, object | None], Mapping[str, Any]] | None,
) -> tuple[PredAtom, ...]:
    if not entity_type:
        raise RuleExprError("cannot close entity-ref port without entity_type metadata")
    identity = _identity_mapping_for_entity_value(
        entity_type,
        value,
        schema_index=schema_index,
        entity_identity_resolver=entity_identity_resolver,
    )
    entity = _entity_info_for_close(schema_index, entity_type)
    identity_fields = getattr(entity, "identity_fields", None)
    identity_predicates = getattr(entity, "identity_predicates", None)
    if not isinstance(identity_fields, tuple) or not isinstance(identity_predicates, Mapping):
        raise RuleExprError(f"cannot close entity-ref port for {entity_type}: incomplete schema identity metadata")

    atoms: list[PredAtom] = []
    primary_fields = tuple(field for field in identity_fields if getattr(field, "primary_key", False))
    if not primary_fields:
        raise RuleExprError(f"cannot close entity-ref port for {entity_type}: no primary identity fields")
    for field_info in primary_fields:
        field_name = getattr(field_info, "name", None)
        if not isinstance(field_name, str) or not field_name:
            raise RuleExprError(f"cannot close entity-ref port for {entity_type}: invalid identity field metadata")
        if field_name not in identity:
            raise RuleExprError(f"cannot close entity-ref port for {entity_type}: missing identity field {field_name!r}")
        predicate = identity_predicates.get(field_name)
        pred_id = getattr(predicate, "pred_id", None)
        if not isinstance(pred_id, str) or not pred_id:
            raise RuleExprError(
                f"cannot close entity-ref port for {entity_type}: missing identity predicate for {field_name!r}"
            )
        atoms.append(PredAtom(pred_id, [port_var, Const(identity[field_name])]))
    return tuple(atoms)


def _identity_mapping_for_entity_value(
    entity_type: str,
    value: object,
    *,
    schema_index: object | None,
    entity_identity_resolver: Callable[[str, object, object | None], Mapping[str, Any]] | None,
) -> Mapping[str, Any]:
    if isinstance(value, EntityRef):
        if value.entity_type != entity_type:
            raise RuleExprError(
                f"cannot close entity-ref port for {entity_type}: row binding has entity_type {value.entity_type!r}"
            )
        return value.identity
    if isinstance(value, Mapping):
        identity = value.get("identity")
        if isinstance(identity, Mapping):
            return identity
        return value
    if entity_identity_resolver is not None:
        return entity_identity_resolver(entity_type, value, schema_index)
    raise RuleExprError(f"cannot close entity-ref port for {entity_type}: schema-backed identity metadata is required")


def _entity_info_for_close(schema_index: object | None, entity_type: str) -> object:
    entities = getattr(schema_index, "entities", None)
    if not isinstance(entities, Mapping):
        raise RuleExprError(f"cannot close entity-ref port for {entity_type}: missing schema index")
    entity = entities.get(entity_type)
    if entity is None:
        raise RuleExprError(f"cannot close entity-ref port for {entity_type}: unknown entity type")
    return entity


def _row_anchor_matches(left: EvaluateRow, right: EvaluateRow, result: EvaluateResult) -> bool:
    return (
        left.row_id == right.row_id
        and left.claim.digest == right.claim.digest
        and left.evidence_ref.ref_id == right.evidence_ref.ref_id
        and left.evidence_ref.result_id == result.result_id
        and left.evidence_ref.row_id == left.row_id
        and left.evidence_ref.fact_digest == left.claim.digest
        and left.evidence_ref.closed_head_digest == right.evidence_ref.closed_head_digest
    )


def _build_passed_row_evidence_graph(
    row: EvaluateRow,
    result: EvaluateResult,
    metadata: Mapping[str, Any],
) -> EvidenceGraph:
    node = EvidenceNode(
        node_id=row.row_id,
        node_kind=NODE_CONCLUSION,
        component="evaluate.row",
        label=row.claim.name,
        value_summary=row.claim.repr,
    )
    return EvidenceGraph(
        graph_id=f"{result.result_id}:{row.row_id}",
        engine=result.engine,
        root_node_id=row.row_id,
        nodes=(node,),
        edges=(),
        support_kind="evaluate_row",
        metadata=metadata,
    )


def _evidence_metadata_for_row_result(row: EvaluateRow, result: EvaluateResult) -> Mapping[str, Any]:
    return _freeze_mapping(
        {
            "result_id": result.result_id,
            "row_id": row.row_id,
            "evidence_ref_id": row.evidence_ref.ref_id,
            "claim_digest": row.claim.digest,
            "closed_head_digest": row.evidence_ref.closed_head_digest,
            "expr_digest": result.expr_digest,
            "rule_set_digest": result.rule_set_digest,
            "view_snapshot_digest": result.view_snapshot_digest,
            "semantics_digest": result.semantics_digest,
            "result_digest": result.result_digest,
            "engine": result.engine,
            "engine_version": result.engine_version,
            "adapter_version": result.adapter_version,
            "evaluated_at": _metadata_value(result.evaluated_at),
        },
        field_name="EvidenceGraph.metadata",
    )


def _checked_scope_for_row_result(result: EvaluateResult, row: EvaluateRow) -> Mapping[str, Any]:
    return _freeze_mapping(
        {
            "semantics_digest": result.semantics_digest,
            "semantics_source": "row_result",
            "evaluate_semantics_digest": result.semantics_digest,
            "explain_semantics_digest": result.semantics_digest,
            "semantics_match": True,
            "result_id": result.result_id,
            "row_id": row.row_id,
            "expr_digest": result.expr_digest,
            "rule_set_digest": result.rule_set_digest,
            "view_snapshot_digest": result.view_snapshot_digest,
            "closed_head_digest": row.evidence_ref.closed_head_digest,
        },
        field_name="Explanation.checked_scope",
    )


def _metadata_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _bindings_from_candidate(candidate: CandidateSet) -> Mapping[str, Any]:
    payload = candidate.payload
    maybe_bindings = payload.get("bindings") if isinstance(payload, Mapping) else None
    if isinstance(maybe_bindings, Mapping):
        return _freeze_mapping(maybe_bindings, field_name="candidate.payload.bindings")
    return _freeze_mapping(payload, field_name="candidate.payload")


def _raw_kind_and_bound_from_candidate(candidate: CandidateSet) -> tuple[RawKind | None, tuple[float, float] | None]:
    if candidate.confidence is None or candidate.confidence_kind is None:
        return None, None
    value = _require_finite_number(candidate.confidence, field_name="CandidateSet.confidence")
    if candidate.confidence_kind == "probability":
        return "probabilistic", (value, value)
    if candidate.confidence_kind == "certainty":
        return "possibilistic", (value, value)
    return None, None


def _freeze_mapping(value: Mapping[str, Any], *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProtocolShapeError(f"{field_name} must be Mapping[str, Any]")
    frozen: dict[str, Any] = {}
    for key, item in value.items():
        _require_non_empty_str(key, field_name=f"{field_name}.<key>")
        frozen[key] = item
    return MappingProxyType(dict(frozen))


def _validate_bound(value: tuple[float, float] | None) -> tuple[float, float]:
    if not isinstance(value, tuple) or len(value) != 2:
        raise ProtocolShapeError("EvaluateRow.bound must be tuple[float, float] when raw_kind is set")
    lower = _require_finite_number(value[0], field_name="EvaluateRow.bound[0]")
    upper = _require_finite_number(value[1], field_name="EvaluateRow.bound[1]")
    if lower > upper:
        raise ProtocolShapeError("EvaluateRow.bound lower value must be <= upper value")
    return (lower, upper)


def _normalize_for_canonical(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProtocolShapeError("canonical float values must be finite")
        return value
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, date):
        return {"__date__": value.isoformat()}
    if isinstance(value, tuple):
        return {"__tuple__": [_normalize_for_canonical(item) for item in value]}
    if isinstance(value, list):
        return [_normalize_for_canonical(item) for item in value]
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ProtocolShapeError("canonical mapping keys must be non-empty strings")
            normalized[key] = _normalize_for_canonical(item)
        return normalized
    raise ProtocolShapeError(f"unsupported canonical value type: {type(value).__name__}")


def _require_finite_number(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolShapeError(f"{field_name} must be finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ProtocolShapeError(f"{field_name} must be finite number")
    return number


def _require_non_empty_str(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProtocolShapeError(f"{field_name} must be non-empty string")
    return value


def _require_optional_non_empty_str(value: object | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_str(value, field_name=field_name)


def _require_optional_token_prefix(value: object | None, *, prefix: str, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_token_prefix(value, prefix=prefix, field_name=field_name)


def _require_token_prefix(value: object, *, prefix: str, field_name: str) -> str:
    text = _require_non_empty_str(value, field_name=field_name)
    if not text.startswith(prefix):
        raise ProtocolShapeError(f"{field_name} must start with {prefix!r}")
    suffix = text[len(prefix) :]
    if len(suffix) != _SHA256_HEX_LEN or any(ch not in "0123456789abcdef" for ch in suffix):
        raise ProtocolShapeError(f"{field_name} must end with 64 lowercase hex characters")
    return text


def _require_sha256_token(value: object, *, field_name: str) -> str:
    text = _require_non_empty_str(value, field_name=field_name)
    if not text.startswith(_SHA256_TOKEN_PREFIX):
        raise ProtocolShapeError(f"{field_name} must start with 'sha256:'")
    _require_sha256_hex(text[len(_SHA256_TOKEN_PREFIX) :], field_name=field_name)
    return text


def _require_sha256_hex(value: object, *, field_name: str) -> str:
    text = _require_non_empty_str(value, field_name=field_name)
    if len(text) != _SHA256_HEX_LEN or any(ch not in "0123456789abcdef" for ch in text):
        raise ProtocolShapeError(f"{field_name} must be 64 lowercase hex characters")
    return text


def _validate_tuple_of_type(value: object, item_type: type[Any], *, field_name: str) -> tuple[Any, ...]:
    if not isinstance(value, tuple):
        raise ProtocolShapeError(f"{field_name} must be tuple[{item_type.__name__}, ...]")
    for idx, item in enumerate(value):
        if not isinstance(item, item_type):
            raise ProtocolShapeError(f"{field_name}[{idx}] must be {item_type.__name__}")
    return value


__all__ = [
    "Claim",
    "DetachedRowError",
    "Explanation",
    "EvaluateResult",
    "EvaluateRow",
    "EvidenceRef",
    "canonical_bytes_for_evaluate",
    "claim_digest_for",
    "closed_head_digest_for",
    "closed_head_digest_for_parts",
    "evidence_ref_id_for",
    "expr_digest_for_payload",
    "new_run_id",
    "result_digest_for",
    "result_id_for",
    "row_id_for",
    "rule_set_digest_for_entries",
    "semantics_digest_for",
    "view_snapshot_digest_for_parts",
]
