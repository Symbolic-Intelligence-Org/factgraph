from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
import base64
import binascii
from dataclasses import dataclass, field, replace
from datetime import date, datetime
import json
import math
from types import MappingProxyType
from typing import Any, Literal
import uuid
import warnings

from factgraph.application.explain.evidence_tree import (
    EvidenceGraph,
    EvidenceRule,
    EvidenceTree,
    LAYOUT_TREE,
)
from factgraph.application.protocol.common import ErrorDTO, ProtocolShapeError, WarningDTO
from factgraph.application.protocol.certainty import BOOLEAN_CERTAINTY, Certainty
from factgraph.application.protocol.evaluation_run import EvaluationRunAnchorV0
from factgraph.application.protocol.evaluation_run_bundle import EvaluationRunBundleV0
from factgraph.application.protocol.evaluation_scenario import ScenarioResolutionV0
from factgraph.application.protocol.explanation_render import narrate_evidence, walk_evidence
from factgraph.application.protocol.rule import Rule, _is_projection_rule
from factgraph.application.protocol.rule_expr import RuleExprError
from factgraph.application.protocol.rule_expr_inspect import _inspect_closed_head
from factgraph.application.protocol.schema_runtime import EntityRef
from factgraph.core.derivation.candidates import DerivationOutput
from factgraph.core.protocol.digests import sha256_hex, sha256_token
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom
from factgraph.core.semantics.profile import SemanticsProfile
from factgraph.core.store.database import view_digest_for
from factgraph.core.store._support import (
    SOUFFLE_WITNESS_KIND,
    ProvenanceEnvelope,
    ProofReceipt,
)


class DetachedRowError(RuntimeError):
    """Raised when a live-only row operation is requested from a detached row."""


ClaimKind = Literal["fact_triple", "rule_head", "aggregate_result", "projection"]
ExplanationStatus = Literal["passed", "failed", "unsupported", "invalid_request"]
ExplanationFailureClass = Literal[
    "no_matching_row",
    "closed_head_false",
    "stale_row",
    "row_not_in_result",
    "insufficient_closed_bindings",
]
_CLAIM_KINDS = frozenset({"fact_triple", "rule_head", "aggregate_result", "projection"})
_EXPLANATION_STATUSES = frozenset({"passed", "failed", "unsupported", "invalid_request"})
_EXPLANATION_FAILURE_CLASSES = frozenset(
    {"no_matching_row", "closed_head_false", "stale_row", "row_not_in_result", "insufficient_closed_bindings"}
)
_SHA256_TOKEN_PREFIX = "sha256:"
_SHA256_HEX_LEN = 64
_RESULT_ID_PREFIX = "evalr_v1:"
_EVIDENCE_REF_ID_PREFIX = "evref_v1:"
_RUN_ID_PREFIX = "run_v1:"
_EVIDENCE_GRAPH_METADATA_KEYS = (
    "result_id",
    "row_id",
    "evidence_ref_id",
    "claim_digest",
    "closed_head_digest",
    "expr_digest",
    "rule_set_digest",
    "view_snapshot_digest",
    "config_digest",
    "result_digest",
    "engine",
    "engine_version",
    "adapter_version",
    "evaluated_at",
)
_EVIDENCE_GRAPH_METADATA_KEY_SET = frozenset(_EVIDENCE_GRAPH_METADATA_KEYS)
_NATIVE_FORM1_SUPPORT_KIND = "native_binding_v1"
_FORM1_ROW_SUPPORT_KINDS = frozenset({_NATIVE_FORM1_SUPPORT_KIND, SOUFFLE_WITNESS_KIND})


@dataclass(frozen=True)
class EvaluateRow:
    row_id: str
    bindings: Mapping[str, Any]
    kind: ClaimKind
    digest: str
    closed_head_digest: str
    certainty: Certainty | None
    _result_resolver: Callable[[], EvaluateResult] | None = field(default=None, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        _require_non_empty_str(self.row_id, field_name="EvaluateRow.row_id")
        object.__setattr__(self, "bindings", _freeze_mapping(self.bindings, field_name="EvaluateRow.bindings"))
        if self.kind not in _CLAIM_KINDS:
            raise ProtocolShapeError("EvaluateRow.kind must be one of fact_triple, rule_head, aggregate_result, projection")
        _require_sha256_token(self.digest, field_name="EvaluateRow.digest")
        _require_sha256_token(self.closed_head_digest, field_name="EvaluateRow.closed_head_digest")
        if self.certainty is not None and not isinstance(self.certainty, Certainty):
            raise ProtocolShapeError("EvaluateRow.certainty must be Certainty or None")
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
class ResultFingerprint:
    expr_digest: str
    rule_set_digest: str
    view_snapshot_digest: str
    config_digest: str | None
    result_digest: str
    run_id: str

    def __post_init__(self) -> None:
        _require_sha256_token(self.expr_digest, field_name="ResultFingerprint.expr_digest")
        _require_sha256_token(self.rule_set_digest, field_name="ResultFingerprint.rule_set_digest")
        _require_sha256_token(self.view_snapshot_digest, field_name="ResultFingerprint.view_snapshot_digest")
        if self.config_digest is not None:
            _require_sha256_token(self.config_digest, field_name="ResultFingerprint.config_digest")
        _require_sha256_token(self.result_digest, field_name="ResultFingerprint.result_digest")
        _require_token_prefix(self.run_id, prefix=_RUN_ID_PREFIX, field_name="ResultFingerprint.run_id")


@dataclass(frozen=True)
class EvaluateResult:
    result_id: str
    rows: tuple[EvaluateRow, ...]
    head: Rule
    engine: str
    evaluated_at: object
    fingerprint: ResultFingerprint
    engine_meta: Mapping[str, Any]
    run_anchor: EvaluationRunAnchorV0 | None = field(default=None, kw_only=True)
    run_bundle: EvaluationRunBundleV0 | None = field(default=None, kw_only=True, repr=False)
    scenario: ScenarioResolutionV0 | None = field(default=None, kw_only=True, repr=False)
    _schema_index: object | None = field(default=None, repr=False, compare=False, hash=False)
    _row_close_builder: Callable[[EvaluateRow, EvaluateResult], Rule] | None = field(
        default=None,
        repr=False,
        compare=False,
        hash=False,
    )
    _row_graph_builder: Callable[[EvaluateRow, EvaluateResult, Mapping[str, Any]], EvidenceGraph] | None = field(
        default=None,
        repr=False,
        compare=False,
        hash=False,
    )
    _row_support_artifacts: Mapping[str, ProofReceipt] | None = field(
        default=None,
        repr=False,
        compare=False,
        hash=False,
    )
    _row_provenance_envelopes: Mapping[str, ProvenanceEnvelope] | None = field(
        default=None,
        repr=False,
        compare=False,
        hash=False,
    )

    def __post_init__(self) -> None:
        _require_token_prefix(self.result_id, prefix=_RESULT_ID_PREFIX, field_name="EvaluateResult.result_id")
        if not isinstance(self.head, Rule):
            raise ProtocolShapeError("EvaluateResult.head must be application protocol Rule")
        _require_non_empty_str(self.engine, field_name="EvaluateResult.engine")
        if not isinstance(self.fingerprint, ResultFingerprint):
            raise ProtocolShapeError("EvaluateResult.fingerprint must be ResultFingerprint")
        object.__setattr__(
            self,
            "engine_meta",
            _validate_engine_meta(self.engine_meta, field_name="EvaluateResult.engine_meta"),
        )
        if self._row_close_builder is not None and not callable(self._row_close_builder):
            raise ProtocolShapeError("EvaluateResult._row_close_builder must be callable or None")
        if self._row_graph_builder is not None and not callable(self._row_graph_builder):
            raise ProtocolShapeError("EvaluateResult._row_graph_builder must be callable or None")
        if self.scenario is not None:
            if not isinstance(self.scenario, ScenarioResolutionV0):
                raise ProtocolShapeError("EvaluateResult.scenario must be ScenarioResolutionV0 or None")
            if self.run_anchor is not None or self.run_bundle is not None:
                raise ProtocolShapeError(
                    "Scenario EvaluateResult must not carry EvaluationRun anchor or bundle"
                )

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
            bound_rows.append(replace(row, _result_resolver=lambda self_ref=self: self_ref))
        row_support_artifacts = _validate_row_support_artifacts(
            self._row_support_artifacts,
            valid_row_ids=seen,
        )
        row_provenance_envelopes = _validate_row_provenance_envelopes(
            self._row_provenance_envelopes,
            valid_row_ids=seen,
        )
        object.__setattr__(self, "_row_support_artifacts", row_support_artifacts)
        object.__setattr__(self, "_row_provenance_envelopes", row_provenance_envelopes)
        object.__setattr__(self, "rows", tuple(bound_rows))
        _validate_scenario_result(
            self,
            support_artifacts=row_support_artifacts,
            provenance_envelopes=row_provenance_envelopes,
        )
        _validate_run_anchor(self)
        _validate_run_bundle(self)

    @property
    def run_id(self) -> str:
        _warn_deprecated_result_field("run_id", "EvaluateResult.fingerprint.run_id")
        return self.fingerprint.run_id

    @property
    def engine_version(self) -> str | None:
        _warn_deprecated_result_field("engine_version", "EvaluateResult.engine_meta['engine_version']")
        return _engine_meta_optional_str(self.engine_meta, "engine_version")

    @property
    def adapter_version(self) -> str | None:
        _warn_deprecated_result_field("adapter_version", "EvaluateResult.engine_meta['adapter_version']")
        return _engine_meta_optional_str(self.engine_meta, "adapter_version")

    @property
    def expr_digest(self) -> str:
        _warn_deprecated_result_field("expr_digest", "EvaluateResult.fingerprint.expr_digest")
        return self.fingerprint.expr_digest

    @property
    def rule_set_digest(self) -> str:
        _warn_deprecated_result_field("rule_set_digest", "EvaluateResult.fingerprint.rule_set_digest")
        return self.fingerprint.rule_set_digest

    @property
    def view_snapshot_digest(self) -> str:
        _warn_deprecated_result_field("view_snapshot_digest", "EvaluateResult.fingerprint.view_snapshot_digest")
        return self.fingerprint.view_snapshot_digest

    @property
    def config_digest(self) -> str | None:
        _warn_deprecated_result_field("config_digest", "EvaluateResult.fingerprint.config_digest")
        return self.fingerprint.config_digest

    @property
    def result_digest(self) -> str:
        _warn_deprecated_result_field("result_digest", "EvaluateResult.fingerprint.result_digest")
        return self.fingerprint.result_digest

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
    row: EvaluateRow | None
    result_id: str | None
    failure_class: ExplanationFailureClass | None = None
    checked_scope: Mapping[str, Any] | None = None
    suggested_next_steps: tuple[str, ...] = ()
    errors: tuple[ErrorDTO, ...] = ()
    warnings: tuple[WarningDTO, ...] = ()
    _repr_cache: tuple[str, ...] | None = field(default=None, init=False, repr=False, compare=False, hash=False)
    _narrate_cache: tuple[str, ...] | None = field(default=None, init=False, repr=False, compare=False, hash=False)

    def __post_init__(self) -> None:
        if self.status not in _EXPLANATION_STATUSES:
            raise ProtocolShapeError("Explanation.status must be one of passed, failed, unsupported, invalid_request")
        if (self.status in {"passed", "failed"}) != (self.evidence is not None):
            raise ProtocolShapeError("Explanation.status in {passed, failed} iff Explanation.evidence is not None")
        if self.evidence is not None and not isinstance(self.evidence, EvidenceGraph):
            raise ProtocolShapeError("Explanation.evidence must be EvidenceGraph or None")
        if self.row is not None and not isinstance(self.row, EvaluateRow):
            raise ProtocolShapeError("Explanation.row must be EvaluateRow or None")

        _require_optional_token_prefix(self.result_id, prefix=_RESULT_ID_PREFIX, field_name="Explanation.result_id")

        if self.status == "passed":
            if self.row is None:
                raise ProtocolShapeError("Explanation.row is required when status is passed")
            _require_non_empty_str(self.result_id, field_name="Explanation.result_id")
        if self.status == "failed":
            _require_non_empty_str(self.result_id, field_name="Explanation.result_id")
        if self.status == "failed":
            if self.failure_class not in _EXPLANATION_FAILURE_CLASSES:
                raise ProtocolShapeError("Explanation.failure_class is required when status is failed")
        elif self.failure_class is not None:
            raise ProtocolShapeError("Explanation.failure_class must be None unless status is failed")
        if self.status in {"unsupported", "invalid_request"} and not self.errors:
            raise ProtocolShapeError("Explanation.errors must be non-empty when status is unsupported or invalid_request")

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

    @property
    def repr(self) -> tuple[str, ...] | None:
        if self.status in {"unsupported", "invalid_request"}:
            return None
        if self._repr_cache is not None:
            return self._repr_cache
        assert self.evidence is not None
        lines = walk_evidence(self.evidence, row=self.row, status=self.status, failure_class=self.failure_class)
        object.__setattr__(self, "_repr_cache", lines)
        return lines

    def narrate(self) -> tuple[str, ...] | None:
        if self.status in {"unsupported", "invalid_request"}:
            return None
        if self._narrate_cache is not None:
            return self._narrate_cache
        assert self.evidence is not None
        lines = narrate_evidence(self.evidence, row=self.row, status=self.status, failure_class=self.failure_class)
        object.__setattr__(self, "_narrate_cache", lines)
        return lines


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
    config_digest: str | None,
    engine: str,
    head_id: str,
    head_content_digest: str,
) -> str:
    _require_token_prefix(run_id, prefix=_RUN_ID_PREFIX, field_name="run_id")
    _require_sha256_token(expr_digest, field_name="expr_digest")
    _require_sha256_token(rule_set_digest, field_name="rule_set_digest")
    _require_sha256_token(view_snapshot_digest, field_name="view_snapshot_digest")
    if config_digest is not None:
        _require_sha256_token(config_digest, field_name="config_digest")
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
                "config_digest": config_digest,
                "view_snapshot_digest": view_snapshot_digest,
            },
        )
    )
    return f"{_RESULT_ID_PREFIX}{digest}"


def row_id_for(run_id: str, bindings: Mapping[str, Any]) -> str:
    _require_token_prefix(run_id, prefix=_RUN_ID_PREFIX, field_name="run_id")
    frozen = _freeze_mapping(bindings, field_name="bindings")
    digest = sha256_hex(canonical_bytes_for_evaluate("evaluate_row_id_v2", frozen))[:16]
    return f"{run_id}:{digest}"


def claim_digest_for(kind: ClaimKind, name: str, arguments: Mapping[str, Any]) -> str:
    if kind not in _CLAIM_KINDS:
        raise ProtocolShapeError("kind must be one of fact_triple, rule_head, aggregate_result, projection")
    _require_non_empty_str(name, field_name="name")
    frozen = _freeze_mapping(arguments, field_name="arguments")
    return sha256_token(canonical_bytes_for_evaluate("evaluate_claim_v2", kind, name, frozen))


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


def _warn_deprecated_result_field(field_name: str, replacement: str) -> None:
    warnings.warn(
        f"EvaluateResult.{field_name} is deprecated; use {replacement}",
        DeprecationWarning,
        stacklevel=2,
    )


def _claim_name_for_row_result(row: EvaluateRow, result: EvaluateResult) -> str:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    if not isinstance(result, EvaluateResult):
        raise ProtocolShapeError("result must be EvaluateResult")
    return result.head.id


def _claim_arguments_for_row(row: EvaluateRow) -> Mapping[str, Any]:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    return row.bindings


def _legacy_candidate_payload_for_row_result(row: EvaluateRow, result: EvaluateResult) -> Mapping[str, Any]:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    if not isinstance(result, EvaluateResult):
        raise ProtocolShapeError("result must be EvaluateResult")
    terms: list[Any] = []
    for port_name in result.head.ports:
        if port_name in row.bindings:
            terms.append(row.bindings[port_name])
            continue
        legacy_terms = row.bindings.get("terms")
        if isinstance(legacy_terms, Sequence):
            port_names = tuple(result.head.ports)
            idx = port_names.index(port_name)
            if idx < len(legacy_terms):
                terms.append(legacy_terms[idx])
                continue
        raise ProtocolShapeError(f"row binding is missing head port {port_name!r}")
    return {"pred_id": result.head.id, "terms": terms}


def _claim_repr_for_row_result(row: EvaluateRow, result: EvaluateResult) -> str:
    return _claim_repr_for_row_name(row, _claim_name_for_row_result(row, result))


def _claim_repr_for_row_name(row: EvaluateRow, claim_name: str) -> str:
    _require_non_empty_str(claim_name, field_name="claim_name")
    return f"{claim_name}{dict(_claim_arguments_for_row(row))!r}"


def _evidence_ref_result_id_for_row_result(row: EvaluateRow, result: EvaluateResult) -> str:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    if not isinstance(result, EvaluateResult):
        raise ProtocolShapeError("result must be EvaluateResult")
    return result.result_id


def _evidence_ref_row_id_for_row(row: EvaluateRow) -> str:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    return row.row_id


def _evidence_ref_fact_digest_for_row(row: EvaluateRow) -> str:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    return row.digest


def _evidence_ref_id_for_row_result(row: EvaluateRow, result: EvaluateResult) -> str:
    return evidence_ref_id_for(
        _evidence_ref_result_id_for_row_result(row, result),
        _evidence_ref_row_id_for_row(row),
        _evidence_ref_fact_digest_for_row(row),
        row.closed_head_digest,
    )


def _legacy_raw_kind_bound_for_certainty(
    certainty: Certainty | None,
) -> tuple[str | None, tuple[float, float] | None]:
    if certainty is None or certainty.kind == "boolean":
        return None, None
    raw_kind = "probabilistic" if certainty.kind == "probabilistic" else "possibilistic"
    return raw_kind, (certainty.lo, certainty.hi)


def _certainty_payload(certainty: Certainty | None) -> Mapping[str, Any] | None:
    if certainty is None:
        return None
    return {"lo": certainty.lo, "hi": certainty.hi, "kind": certainty.kind}


def _row_digest_for(row: EvaluateRow, *, result_id: str, claim_name: str) -> str:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    _require_token_prefix(result_id, prefix=_RESULT_ID_PREFIX, field_name="result_id")
    _require_non_empty_str(claim_name, field_name="claim_name")
    raw_kind, bound = _legacy_raw_kind_bound_for_certainty(row.certainty)
    return sha256_token(
        canonical_bytes_for_evaluate(
            "evaluate_row_digest_v2",
            {
                "bindings": row.bindings,
                "bound": bound,
                "claim": {
                    "arguments": _claim_arguments_for_row(row),
                    "digest": row.digest,
                    "kind": row.kind,
                    "name": claim_name,
                    "repr": _claim_repr_for_row_name(row, claim_name),
                },
                "evidence_ref": {
                    "closed_head_digest": row.closed_head_digest,
                    "fact_digest": _evidence_ref_fact_digest_for_row(row),
                    "result_id": result_id,
                    "row_id": _evidence_ref_row_id_for_row(row),
                },
                "raw_kind": raw_kind,
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
    config_digest: str | None,
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
    if config_digest is not None:
        _require_sha256_token(config_digest, field_name="config_digest")
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
                "config_digest": config_digest,
                "view_snapshot_digest": view_snapshot_digest,
            },
        )
    )


def config_digest_for(profile: SemanticsProfile | None) -> str | None:
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


def _derivation_output_to_evaluate_row(
    output: DerivationOutput,
    *,
    head: Rule,
    result_id: str,
    run_id: str,
    closed_head_digest: str,
    claim_kind: ClaimKind = "fact_triple",
    claim_name: str | None = None,
    binding_types: Mapping[str, str] | None = None,
) -> EvaluateRow:
    if not isinstance(output, DerivationOutput):
        raise ProtocolShapeError("output must be DerivationOutput")
    if not isinstance(head, Rule):
        raise ProtocolShapeError("head must be application protocol Rule")
    _require_token_prefix(result_id, prefix=_RESULT_ID_PREFIX, field_name="result_id")
    _require_token_prefix(run_id, prefix=_RUN_ID_PREFIX, field_name="run_id")
    _require_sha256_token(closed_head_digest, field_name="closed_head_digest")
    if binding_types is not None:
        if output.candidate_kind != "fact" or output.target != head.id or output.payload.get("pred_id") != head.id:
            raise ProtocolShapeError("derivation output projection target must exactly match its query head")
        terms = output.payload.get("terms")
        if not isinstance(terms, Sequence) or isinstance(terms, (str, bytes)) or len(terms) != len(head.ports):
            raise ProtocolShapeError("derivation output projection terms must exactly align with head ports")
    bindings = _bindings_from_output(output, head=head)
    if binding_types is not None:
        bindings = _typed_projection_bindings(bindings, head=head, binding_types=binding_types)
    effective_claim_name = output.target if claim_name is None else claim_name
    digest = claim_digest_for(claim_kind, effective_claim_name, bindings)
    row_id = row_id_for(run_id, bindings)
    certainty = _certainty_from_output(output)
    return EvaluateRow(
        row_id=row_id,
        bindings=bindings,
        kind=claim_kind,
        digest=digest,
        closed_head_digest=closed_head_digest,
        certainty=certainty,
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

    if result.scenario is not None:
        return Explanation(
            status="unsupported",
            evidence=None,
            row=row,
            result_id=result.result_id,
            errors=(
                ErrorDTO(
                    code="SCENARIO_EXPLAIN_UNSUPPORTED",
                    message="ScenarioFieldSubstitutionV0 rows have no ledger-backed EvidenceGraph",
                    details={"row_id": row.row_id},
                ),
            ),
        )

    checked_scope = _checked_scope_for_row_result(result, row)
    matched = next((candidate for candidate in result.rows if candidate.row_id == row.row_id), None)
    if matched is None:
        return Explanation(
            status="unsupported",
            evidence=None,
            row=row,
            result_id=result.result_id,
            checked_scope=checked_scope,
            suggested_next_steps=("Re-evaluate the expression and explain a row from the returned result.",),
            errors=(
                ErrorDTO(
                    code="ROW_NOT_IN_RESULT",
                    message="row is not present in the current EvaluateResult",
                    details={"row_id": row.row_id},
                ),
            ),
        )

    if not _row_anchor_matches(matched, row, result):
        return Explanation(
            status="unsupported",
            evidence=None,
            row=row,
            result_id=result.result_id,
            checked_scope=checked_scope,
            suggested_next_steps=("Use a row from the current EvaluateResult before calling explain().",),
            errors=(
                ErrorDTO(
                    code="STALE_ROW",
                    message="row no longer matches the current EvaluateResult anchor",
                    details={"row_id": row.row_id},
                ),
            ),
        )

    metadata = _evidence_metadata_for_row_result(row, result)
    builder = graph_builder or result._row_graph_builder or _build_minimal_row_evidence_graph
    try:
        evidence = builder(row, result, metadata)
        if isinstance(evidence, EvidenceGraph):
            _validate_evidence_metadata_for_row_result(evidence.metadata, row, result)
    except ValueError as exc:
        return Explanation(
            status="unsupported",
            evidence=None,
            row=row,
            result_id=result.result_id,
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
        row=row,
        result_id=result.result_id,
        checked_scope=checked_scope,
    )


def _close_live_row(row: EvaluateRow, result: EvaluateResult) -> Rule:
    if not isinstance(row, EvaluateRow):
        raise ProtocolShapeError("row must be EvaluateRow")
    if not isinstance(result, EvaluateResult):
        raise ProtocolShapeError("result must be EvaluateResult")
    if result.scenario is not None:
        raise DetachedRowError(
            "ScenarioFieldSubstitutionV0 rows cannot be closed against ledger facts"
        )
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

    base_where = () if _is_projection_rule(head) else tuple(head.when)
    closed = Rule(
        id=f"{head.id}_closed_{row.row_id}",
        when=tuple(base_where) + tuple(closure_atoms),
        ports=dict(head.ports),
        version=head.version,
        repr=head.repr,
    )
    inspected = _inspect_closed_head(closed, schema_index=schema_index)
    if not inspected.is_closed:
        missing = ", ".join(inspected.unbound_ports)
        raise RuleExprError(f"closed head construction left unbound ports: {missing}")
    return closed


def _binding_value_for_head_port(row: EvaluateRow, head: Rule, port_name: str) -> object:
    if port_name in row.bindings:
        return _public_term_value(row.bindings[port_name])
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
    if not identity_fields:
        raise RuleExprError(f"cannot close entity-ref port for {entity_type}: no identity fields")
    for field_info in identity_fields:
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
        and left.digest == right.digest
        and _evidence_ref_id_for_row_result(left, result) == _evidence_ref_id_for_row_result(right, result)
        and left.closed_head_digest == right.closed_head_digest
    )


def _build_minimal_row_evidence_graph(
    row: EvaluateRow,
    result: EvaluateResult,
    metadata: Mapping[str, Any],
) -> EvidenceGraph:
    _validate_evidence_metadata_for_row_result(metadata, row, result)
    status: Literal["holds"] = "holds"
    return EvidenceGraph(
        graph_id=f"{result.result_id}:{row.row_id}",
        engine=result.engine,
        layout_hint=LAYOUT_TREE,
        subject_binding=row.bindings,
        paths=(
            EvidenceTree(
                tree_id=row.row_id,
                status=status,
                rules=(
                    EvidenceRule(
                        occurrence_alias=result.head.id,
                        rule_id=result.head.id,
                        role="head",
                        status=status,
                        ports=row.bindings,
                        atoms=(),
                    ),
                ),
                joins=(),
                certainty=row.certainty,
                metadata={"fallback": "minimal_row_evidence"},
            ),
        ),
        certainty=row.certainty,
        metadata=metadata,
    )


def _evidence_metadata_for_row_result(row: EvaluateRow, result: EvaluateResult) -> Mapping[str, Any]:
    metadata = _freeze_mapping(_evidence_metadata_payload_for_row_result(row, result), field_name="EvidenceGraph.metadata")
    _validate_evidence_metadata_for_row_result(metadata, row, result)
    return metadata


def _evidence_metadata_payload_for_row_result(row: EvaluateRow, result: EvaluateResult) -> dict[str, Any]:
    fingerprint = result.fingerprint
    return {
        "result_id": result.result_id,
        "row_id": row.row_id,
        "evidence_ref_id": _evidence_ref_id_for_row_result(row, result),
        "claim_digest": row.digest,
        "closed_head_digest": row.closed_head_digest,
        "expr_digest": fingerprint.expr_digest,
        "rule_set_digest": fingerprint.rule_set_digest,
        "view_snapshot_digest": fingerprint.view_snapshot_digest,
        "config_digest": fingerprint.config_digest,
        "result_digest": fingerprint.result_digest,
        "engine": result.engine,
        "engine_version": _engine_meta_optional_str(result.engine_meta, "engine_version"),
        "adapter_version": _engine_meta_optional_str(result.engine_meta, "adapter_version"),
        "evaluated_at": _metadata_value(result.evaluated_at),
    }


def _validate_evidence_metadata_for_row_result(
    metadata: Mapping[str, Any],
    row: EvaluateRow,
    result: EvaluateResult,
) -> None:
    if not isinstance(metadata, Mapping):
        raise ValueError("EvidenceGraph.metadata must be a mapping")
    actual_keys = set(metadata)
    if actual_keys != _EVIDENCE_GRAPH_METADATA_KEY_SET:
        missing = tuple(key for key in _EVIDENCE_GRAPH_METADATA_KEYS if key not in actual_keys)
        extra = tuple(sorted(actual_keys - _EVIDENCE_GRAPH_METADATA_KEY_SET))
        details: list[str] = []
        if missing:
            details.append(f"missing {missing!r}")
        if extra:
            details.append(f"extra {extra!r}")
        suffix = "; ".join(details) if details else "key mismatch"
        raise ValueError(f"EvidenceGraph.metadata must contain exactly the v1 row-result keys: {suffix}")

    expected = _evidence_metadata_payload_for_row_result(row, result)
    for key in _EVIDENCE_GRAPH_METADATA_KEYS:
        if metadata[key] != expected[key]:
            raise ValueError(f"EvidenceGraph.metadata[{key!r}] must match EvaluateResult/EvaluateRow context")


def _validate_row_support_artifacts(
    artifacts: Mapping[str, ProofReceipt] | None,
    *,
    valid_row_ids: set[str],
) -> Mapping[str, ProofReceipt]:
    if artifacts is None:
        return MappingProxyType({})
    if not isinstance(artifacts, Mapping):
        raise ProtocolShapeError("EvaluateResult._row_support_artifacts must be mapping or None")
    normalized: dict[str, ProofReceipt] = {}
    for row_id, artifact in artifacts.items():
        _require_non_empty_str(row_id, field_name="EvaluateResult._row_support_artifacts key")
        if row_id not in valid_row_ids:
            raise ProtocolShapeError("EvaluateResult._row_support_artifacts contains unknown row_id")
        if not isinstance(artifact, ProofReceipt):
            raise ProtocolShapeError("EvaluateResult._row_support_artifacts values must be ProofReceipt")
        normalized[row_id] = artifact
    return MappingProxyType(normalized)


def _validate_row_provenance_envelopes(
    envelopes: Mapping[str, ProvenanceEnvelope] | None,
    *,
    valid_row_ids: set[str],
) -> Mapping[str, ProvenanceEnvelope]:
    if envelopes is None:
        return MappingProxyType({})
    if not isinstance(envelopes, Mapping):
        raise ProtocolShapeError("EvaluateResult._row_provenance_envelopes must be mapping or None")
    normalized: dict[str, ProvenanceEnvelope] = {}
    for row_id, envelope in envelopes.items():
        _require_non_empty_str(row_id, field_name="EvaluateResult._row_provenance_envelopes key")
        if row_id not in valid_row_ids:
            raise ProtocolShapeError("EvaluateResult._row_provenance_envelopes contains unknown row_id")
        if not isinstance(envelope, ProvenanceEnvelope):
            raise ProtocolShapeError("EvaluateResult._row_provenance_envelopes values must be ProvenanceEnvelope")
        if (envelope.engine, envelope.payload_type) not in {("problog", "proof_trace"), ("pyreason", "event_log")}:
            raise ProtocolShapeError(
                "EvaluateResult._row_provenance_envelopes values must be adapter provenance envelopes"
            )
        normalized[row_id] = envelope
    return MappingProxyType(normalized)


def _scenario_semantic_rows_digest(rows: Sequence[EvaluateRow]) -> str:
    """Stable Scenario result identity excluding run/result/proof identities."""

    row_tokens: list[str] = []
    for row in rows:
        payload = {
            "kind": row.kind,
            "claim_digest": row.digest,
            "bindings": row.bindings,
            "closed_head_digest": row.closed_head_digest,
            "certainty": _certainty_payload(row.certainty),
        }
        row_tokens.append(
            sha256_token(canonical_bytes_for_evaluate("scenario_query_row_semantic_v0", payload))
        )
    return sha256_token(
        canonical_bytes_for_evaluate("scenario_query_row_multiset_v0", tuple(sorted(row_tokens)))
    )


def _validate_scenario_result(
    result: EvaluateResult,
    *,
    support_artifacts: Mapping[str, ProofReceipt],
    provenance_envelopes: Mapping[str, ProvenanceEnvelope],
) -> None:
    """Bind the hypothetical effective relation and its diff to this result."""

    scenario = result.scenario
    if scenario is None:
        return
    if result.fingerprint.view_snapshot_digest != scenario.effective_relation_digest:
        raise ProtocolShapeError(
            "Scenario EvaluateResult fingerprint must commit its effective relation digest"
        )
    if support_artifacts or provenance_envelopes:
        raise ProtocolShapeError(
            "Scenario EvaluateResult must not carry ledger-backed support or provenance"
        )
    if scenario.result_diff is None:
        raise ProtocolShapeError("Scenario EvaluateResult requires a result diff")
    if scenario.result_diff.effective_row_count != len(result.rows):
        raise ProtocolShapeError(
            "Scenario result diff effective row count must match EvaluateResult rows"
        )
    if scenario.result_diff.effective_semantic_rows_digest != _scenario_semantic_rows_digest(result.rows):
        raise ProtocolShapeError(
            "Scenario result diff effective rows must match EvaluateResult rows"
        )


def _checked_scope_for_row_result(result: EvaluateResult, row: EvaluateRow) -> Mapping[str, Any]:
    fingerprint = result.fingerprint
    scope = {
        "config_digest": fingerprint.config_digest,
        "semantics_source": "row_result",
        "evaluate_config_digest": fingerprint.config_digest,
        "explain_config_digest": fingerprint.config_digest,
        "semantics_match": True,
        "result_id": result.result_id,
        "row_id": row.row_id,
        "expr_digest": fingerprint.expr_digest,
        "rule_set_digest": fingerprint.rule_set_digest,
        "view_snapshot_digest": fingerprint.view_snapshot_digest,
        "closed_head_digest": row.closed_head_digest,
    }
    if result.run_anchor is not None:
        scope["evaluation_run_anchor_digest"] = result.run_anchor.anchor_digest
    return _freeze_mapping(
        scope,
        field_name="Explanation.checked_scope",
    )


def _validate_run_anchor(result: EvaluateResult) -> None:
    anchor = result.run_anchor
    if anchor is None:
        return
    if not isinstance(anchor, EvaluationRunAnchorV0):
        raise ProtocolShapeError("EvaluateResult.run_anchor must be EvaluationRunAnchorV0 or None")
    fingerprint = result.fingerprint
    actual = (
        result.result_id, fingerprint.result_digest, fingerprint.run_id,
        fingerprint.view_snapshot_digest, result.engine, result.head.id,
        result.head.content_digest, tuple(row.row_id for row in result.rows),
        tuple(row.digest for row in result.rows),
        tuple(row.closed_head_digest for row in result.rows),
    )
    expected = (
        anchor.result_id, anchor.result_digest, anchor.run_id,
        anchor.view_snapshot_digest, anchor.execution_profile.engine,
        anchor.projection_head_id, anchor.projection_head_content_digest,
        tuple(row.row_id for row in anchor.row_anchors),
        tuple(row.claim_digest for row in anchor.row_anchors),
        tuple(row.head_scope_digest for row in anchor.row_anchors),
    )
    row_semantics_match = all(
        row.kind == row_anchor.claim_kind
        and sha256_token(canonical_bytes_for_evaluate("evaluation_run_bindings_v0", row.bindings))
            == row_anchor.bindings_digest
        and sha256_token(canonical_bytes_for_evaluate(
            "evaluation_run_certainty_v0", _certainty_payload(row.certainty),
        )) == row_anchor.certainty_digest
        for row, row_anchor in zip(result.rows, anchor.row_anchors, strict=True)
    )
    evaluated_at = result.evaluated_at.isoformat() if isinstance(result.evaluated_at, (datetime, date)) else result.evaluated_at
    anchored_rule_set = rule_set_digest_for_entries((
        (f"compiled-policy:{anchor.target.normalized_policy_id}", anchor.target.policy_digest),
        (f"query-projection:{anchor.projection_head_id}", anchor.projection_head_content_digest),
    ))
    if (
        actual != expected
        or not row_semantics_match
        or anchor.execution_profile.engine_version != result.engine_meta["engine_version"]
        or anchor.execution_profile.adapter_version != result.engine_meta["adapter_version"]
        or anchor.execution_profile.config_digest != fingerprint.config_digest
        or anchor.evaluated_at != evaluated_at
        or fingerprint.expr_digest != f"sha256:{anchor.query_digest}"
        or fingerprint.rule_set_digest != anchored_rule_set
    ):
        raise ProtocolShapeError("EvaluateResult.run_anchor does not match this result")


def _validate_run_bundle(result: EvaluateResult) -> None:
    bundle = result.run_bundle
    if bundle is None:
        return
    # Keep the codec import local: EvaluateResult is also used while the bundle
    # protocol itself initializes.
    from factgraph.application.evaluation_run_bundle_runtime import (
        _assert_evaluation_run_bundle_current,
    )

    if not isinstance(bundle, EvaluationRunBundleV0):
        raise ProtocolShapeError("EvaluateResult.run_bundle must be EvaluationRunBundleV0 or None")
    _assert_evaluation_run_bundle_current(bundle)
    if result.run_anchor is None or bundle.run_anchor != result.run_anchor:
        raise ProtocolShapeError("EvaluateResult.run_bundle does not match this result")


def _metadata_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _bindings_from_output(output: DerivationOutput, *, head: Rule) -> Mapping[str, Any]:
    if not isinstance(head, Rule):
        raise ProtocolShapeError("head must be application protocol Rule")
    payload = output.payload
    if not isinstance(payload, Mapping):
        raise ProtocolShapeError("derivation_output.payload must be mapping")
    terms = payload.get("terms")
    port_names = tuple(head.ports)
    if isinstance(terms, Sequence) and not isinstance(terms, (str, bytes)):
        if len(terms) < len(port_names):
            raise ProtocolShapeError("derivation_output.payload.terms must align with head ports")
        return _freeze_mapping(
            dict(zip(port_names, terms[: len(port_names)])),
            field_name="derivation_output.payload.terms",
        )
    maybe_bindings = payload.get("bindings")
    if isinstance(maybe_bindings, Mapping):
        return _freeze_mapping(
            maybe_bindings, field_name="derivation_output.payload.bindings"
        )
    return _freeze_mapping(payload, field_name="derivation_output.payload")


def _typed_projection_bindings(
    bindings: Mapping[str, Any], *, head: Rule, binding_types: Mapping[str, str],
) -> Mapping[str, Any]:
    port_names = tuple(head.ports)
    if tuple(binding_types) != port_names:
        raise ProtocolShapeError("typed projection domains must follow the exact head-port order")
    if set(bindings) != set(port_names):
        raise ProtocolShapeError("derivation output projection bindings must exactly match head ports")
    typed: dict[str, Any] = {}
    for port_name in port_names:
        value_type = binding_types[port_name]
        source = bindings[port_name]
        if not isinstance(source, Mapping):
            raise ProtocolShapeError(f"derivation output projection term for {port_name!r} must be typed")
        source_kind = source.get("kind")
        source_type = "entity_ref" if source_kind == "entity_ref" else source.get("tag")
        if source_kind not in {"entity_ref", "literal"} or not isinstance(source_type, str):
            raise ProtocolShapeError(f"derivation output projection term for {port_name!r} is malformed")
        value = _public_term_value(source)
        try:
            claim_args_from_rest_terms([(source_type, value)])
        except ValueError as exc:
            raise ProtocolShapeError(f"derivation output projection term for {port_name!r} contradicts its runtime tag") from exc
        if value_type == "bytes" and isinstance(value, str):
            try:
                encoded_value = value.encode("ascii")
                value = base64.b64decode(encoded_value + b"=" * (-len(encoded_value) % 4), altchars=b"-_", validate=True)
                if base64.urlsafe_b64encode(value).rstrip(b"=") != encoded_value:
                    raise ValueError("bytes value is not canonical base64url")
            except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
                raise ProtocolShapeError(f"derivation output projection value for {port_name!r} is not canonical bytes") from exc
        try:
            _idx, canonical, canonical_type = claim_args_from_rest_terms([(value_type, value)])[0]
        except ValueError as exc:
            raise ProtocolShapeError(f"derivation output projection value for {port_name!r} is not {value_type!r}") from exc
        term = (
            {"kind": "entity_ref", "value": canonical}
            if canonical_type == "entity_ref"
            else {"kind": "literal", "tag": canonical_type, "value": canonical}
        )
        typed[port_name] = _freeze_mapping(
            term, field_name=f"derivation_output.typed_projection.{port_name}"
        )
    return _freeze_mapping(typed, field_name="derivation_output.typed_projection")


def _certainty_from_output(output: DerivationOutput) -> Certainty | None:
    if output.confidence is None or output.confidence_kind is None:
        return BOOLEAN_CERTAINTY
    value = _require_finite_number(output.confidence, field_name="DerivationOutput.confidence")
    if output.confidence_kind == "probability":
        return Certainty(value, value, "probabilistic")
    if output.confidence_kind == "certainty":
        return Certainty(value, value, "possibilistic")
    return None


def _freeze_mapping(value: Mapping[str, Any], *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProtocolShapeError(f"{field_name} must be Mapping[str, Any]")
    frozen: dict[str, Any] = {}
    for key, item in value.items():
        _require_non_empty_str(key, field_name=f"{field_name}.<key>")
        frozen[key] = item
    return MappingProxyType(dict(frozen))


def _validate_engine_meta(value: Mapping[str, Any], *, field_name: str) -> Mapping[str, Any]:
    frozen = dict(_freeze_mapping(value, field_name=field_name))
    for key in ("engine_version", "adapter_version"):
        if key not in frozen:
            raise ProtocolShapeError(f"{field_name} must contain {key!r}")
        _require_optional_non_empty_str(frozen[key], field_name=f"{field_name}[{key!r}]")
    return MappingProxyType(frozen)


def _engine_meta_optional_str(engine_meta: Mapping[str, Any], key: str) -> str | None:
    if key not in engine_meta:
        raise ProtocolShapeError(f"EvaluateResult.engine_meta must contain {key!r}")
    value = engine_meta[key]
    return _require_optional_non_empty_str(value, field_name=f"EvaluateResult.engine_meta[{key!r}]")


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
    "BOOLEAN_CERTAINTY",
    "Certainty",
    "DetachedRowError",
    "Explanation",
    "EvaluateResult",
    "EvaluateRow",
    "canonical_bytes_for_evaluate",
    "claim_digest_for",
    "closed_head_digest_for",
    "closed_head_digest_for_parts",
    "evidence_ref_id_for",
    "expr_digest_for_payload",
    "new_run_id",
    "result_digest_for",
    "result_id_for",
    "ResultFingerprint",
    "row_id_for",
    "rule_set_digest_for_entries",
    "config_digest_for",
    "view_snapshot_digest_for_parts",
]
