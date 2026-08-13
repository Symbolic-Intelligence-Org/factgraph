from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import json
from typing import Literal, TypeAlias

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError
from .evaluation_query import EvaluationQueryFieldNavigationV0
from .policy import PolicyLineage, PolicyStructureV0
from .semantic_address import SemanticPortAddress


def _token(label: str, payload: object) -> str:
    raw = json.dumps(
        {"format": label, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
    return f"sha256:{sha256_hex(raw)}"


@dataclass(frozen=True)
class EvaluationRunRulePinV0:
    occurrence_alias: str
    rule_id: str
    rule_version: str | None
    rule_content_digest: str
    semantic_contract_digest: str

    def __post_init__(self) -> None:
        for name in ("occurrence_alias", "rule_id", "rule_content_digest", "semantic_contract_digest"):
            _text(getattr(self, name), name)
        _sha_hex(self.rule_content_digest, "rule_content_digest")
        _sha_hex(self.semantic_contract_digest, "semantic_contract_digest")
        if self.rule_version is not None:
            _text(self.rule_version, "rule_version")


@dataclass(frozen=True)
class EvaluationRunTargetV0:
    original_target_kind: Literal["rule", "policy"]
    normalization_kind: Literal["rule_lift_v0", "policy_direct_v0"]
    target_id: str
    target_version: str | None
    normalized_policy_id: str
    normalized_policy_version: str | None
    policy_digest: str
    address_space_digest: str
    schema_digest: str
    policy_structure: PolicyStructureV0
    policy_lineage: PolicyLineage
    rule_pins: tuple[EvaluationRunRulePinV0, ...]
    target_digest: str

    def __post_init__(self) -> None:
        expected = {"rule": "rule_lift_v0", "policy": "policy_direct_v0"}
        if expected.get(self.original_target_kind) != self.normalization_kind:
            raise ProtocolShapeError("EvaluationRun target kind and normalization do not match")
        for name in ("target_id", "normalized_policy_id", "policy_digest", "address_space_digest", "schema_digest"):
            _text(getattr(self, name), name)
        _sha_hex(self.policy_digest, "policy_digest")
        _sha_hex(self.address_space_digest, "address_space_digest")
        _sha_token(self.schema_digest, "schema_digest")
        for name in ("target_version", "normalized_policy_version"):
            if getattr(self, name) is not None:
                _text(getattr(self, name), name)
        if self.original_target_kind == "policy" and (
            self.target_id, self.target_version
        ) != (self.normalized_policy_id, self.normalized_policy_version):
            raise ProtocolShapeError("direct Policy target identity must remain unchanged")
        if self.original_target_kind == "rule" and (
            self.normalized_policy_id != f"__factgraph_rule_lift__:{self.target_id}"
            or self.normalized_policy_version != self.target_version
        ):
            raise ProtocolShapeError("Rule lift identity does not match the v0 normalization contract")
        if not isinstance(self.policy_structure, PolicyStructureV0) or not isinstance(self.policy_lineage, PolicyLineage):
            raise ProtocolShapeError("EvaluationRun target requires Policy structure and lineage")
        if not isinstance(self.rule_pins, tuple) or not self.rule_pins or not all(
            isinstance(pin, EvaluationRunRulePinV0) for pin in self.rule_pins
        ):
            raise ProtocolShapeError("EvaluationRun target requires Rule pins")
        pin_aliases = tuple(pin.occurrence_alias for pin in self.rule_pins)
        if len(set(pin_aliases)) != len(pin_aliases):
            raise ProtocolShapeError("EvaluationRun target Rule pins contain duplicate aliases")
        structure_kinds = {node.node_id: node.kind for node in self.policy_structure.nodes}
        lineage_kinds = {node.node_id: node.node_kind for node in self.policy_lineage.authored_nodes}
        occurrence_aliases = {node.occurrence_alias for node in self.policy_structure.nodes if node.kind == "occurrence"}
        if structure_kinds != lineage_kinds or occurrence_aliases != {pin.occurrence_alias for pin in self.rule_pins}:
            raise ProtocolShapeError("EvaluationRun target Policy structure, lineage and Rule pins disagree")
        if self.original_target_kind == "rule" and pin_aliases != ("target",):
            raise ProtocolShapeError("Rule lift v0 requires exactly one 'target' occurrence")
        if self.original_target_kind == "rule":
            pin = self.rule_pins[0]
            root = self.policy_structure.nodes[0]
            if (
                (pin.rule_id, pin.rule_version) != (self.target_id, self.target_version)
                or len(self.policy_structure.nodes) != 1
                or root.node_id != self.policy_structure.root_node_id
                or root.kind != "occurrence"
                or root.occurrence_alias != "target"
            ):
                raise ProtocolShapeError("Rule lift v0 must be one exact target occurrence")
        values = tuple(getattr(self, name) for name in self.__dataclass_fields__ if name != "target_digest")
        _seal(self.target_digest, _token("evaluation_run_target_v0", _plain(values)), "target_digest")


@dataclass(frozen=True)
class EvaluationRunBindingV0:
    address: SemanticPortAddress
    value_type: str
    value_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.address, SemanticPortAddress):
            raise ProtocolShapeError("EvaluationRun binding address is invalid")
        _text(self.value_type, "value_type")
        _sha_hex(self.value_digest, "value_digest")


@dataclass(frozen=True)
class EvaluationRunSelectionV0:
    alias: str
    address: SemanticPortAddress
    value_type: str

    def __post_init__(self) -> None:
        _text(self.alias, "alias")
        if not isinstance(self.address, SemanticPortAddress):
            raise ProtocolShapeError("EvaluationRun selection address is invalid")
        _text(self.value_type, "value_type")


@dataclass(frozen=True)
class EvaluationRunNavigationSelectionV0:
    """One sealed Query-owned field-navigation selection in a Run anchor.

    This deliberately parallels rather than extends ``EvaluationRunSelectionV0``
    so historical direct-only anchor and bundle wire shapes remain unchanged.
    ``field_predicate_id`` is the compiler-resolved field relation consumed by
    the captured native plan; the nested navigation remains the caller's typed
    intent.
    """

    alias: str
    navigation: EvaluationQueryFieldNavigationV0
    value_type: str
    field_predicate_id: str

    def __post_init__(self) -> None:
        _text(self.alias, "alias")
        if not isinstance(self.navigation, EvaluationQueryFieldNavigationV0):
            raise ProtocolShapeError("EvaluationRun navigation selection is invalid")
        _text(self.value_type, "value_type")
        _text(self.field_predicate_id, "field_predicate_id")


EvaluationRunSelectionItemV0: TypeAlias = (
    EvaluationRunSelectionV0 | EvaluationRunNavigationSelectionV0
)


@dataclass(frozen=True)
class EvaluationRunExecutionProfileV0:
    engine: str
    engine_version: str | None
    adapter_version: str | None
    config_digest: str | None
    version_pinning: Literal["complete", "incomplete"]

    def __post_init__(self) -> None:
        _text(self.engine, "engine")
        for name in ("engine_version", "adapter_version"):
            if getattr(self, name) is not None:
                _text(getattr(self, name), name)
        if self.config_digest is not None:
            _sha_token(self.config_digest, "config_digest")
        if self.version_pinning not in {"complete", "incomplete"}:
            raise ProtocolShapeError("invalid execution-profile pinning state")
        complete = self.engine_version is not None and self.adapter_version is not None
        if (self.version_pinning == "complete") != complete:
            raise ProtocolShapeError("execution-profile pinning state does not match version pins")


@dataclass(frozen=True)
class EvaluationRunRowAnchorV0:
    ordinal: int
    row_id: str
    query_digest: str
    claim_kind: str
    claim_digest: str
    bindings_digest: str
    head_scope_digest: str
    certainty_digest: str
    semantic_anchor_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool) or self.ordinal < 0:
            raise ProtocolShapeError("EvaluationRun row ordinal must be non-negative integer")
        for name in ("row_id", "query_digest", "claim_kind"):
            _text(getattr(self, name), name)
        _sha_hex(self.query_digest, "query_digest")
        if self.claim_kind not in {"fact_triple", "rule_head", "aggregate_result", "projection"}:
            raise ProtocolShapeError("EvaluationRun claim_kind is invalid")
        for name in ("claim_digest", "bindings_digest", "head_scope_digest", "certainty_digest"):
            _sha_token(getattr(self, name), name)
        values = (
            self.ordinal, self.row_id, self.query_digest, self.claim_kind,
            self.claim_digest, self.bindings_digest, self.head_scope_digest,
            self.certainty_digest,
        )
        semantic_values = values[2:]
        _seal(self.semantic_anchor_digest, _token("evaluation_run_row_anchor_v0", semantic_values), "semantic_anchor_digest")


@dataclass(frozen=True)
class EvaluationRunSummaryAnchorV0:
    query_digest: str
    row_count: int
    row_anchor_digests: tuple[str, ...]
    truth_interpretation: Literal["not_asserted"]
    completeness: Literal["unknown"]
    ordering: Literal["unspecified"]
    summary_anchor_digest: str

    def __post_init__(self) -> None:
        _text(self.query_digest, "query_digest")
        _sha_hex(self.query_digest, "query_digest")
        if not isinstance(self.row_count, int) or isinstance(self.row_count, bool) or self.row_count < 0:
            raise ProtocolShapeError("EvaluationRun row_count must be non-negative integer")
        if not isinstance(self.row_anchor_digests, tuple) or len(self.row_anchor_digests) != self.row_count:
            raise ProtocolShapeError("EvaluationRun summary row inventory does not match row_count")
        if tuple(sorted(self.row_anchor_digests)) != self.row_anchor_digests:
            raise ProtocolShapeError("EvaluationRun summary row anchors must be sorted")
        if (self.truth_interpretation, self.completeness, self.ordering) != ("not_asserted", "unknown", "unspecified"):
            raise ProtocolShapeError("EvaluationRun summary semantics are outside v0")
        for digest in self.row_anchor_digests:
            _sha_token(digest, "row_anchor_digest")
        values = tuple(getattr(self, name) for name in self.__dataclass_fields__ if name != "summary_anchor_digest")
        _seal(self.summary_anchor_digest, _token("evaluation_run_summary_anchor_v0", values), "summary_anchor_digest")


@dataclass(frozen=True)
class EvaluationRunAnchorV0:
    target: EvaluationRunTargetV0
    query_digest: str
    bindings: tuple[EvaluationRunBindingV0, ...]
    selections: tuple[EvaluationRunSelectionItemV0, ...]
    execution_profile: EvaluationRunExecutionProfileV0
    projection_head_id: str
    projection_head_content_digest: str
    view_snapshot_digest: str
    result_id: str
    result_digest: str
    run_id: str
    evaluated_at: str
    row_anchors: tuple[EvaluationRunRowAnchorV0, ...]
    summary: EvaluationRunSummaryAnchorV0
    capture_level: Literal["identity_only"]
    view_capture: Literal["digest_only_live_guard"]
    replay_availability: Literal["not_available"]
    explain_availability: Literal["live_recomputable_while_current"]
    anchor_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.target, EvaluationRunTargetV0):
            raise ProtocolShapeError("EvaluationRun anchor target is invalid")
        if (self.capture_level, self.view_capture, self.replay_availability, self.explain_availability) != (
            "identity_only", "digest_only_live_guard", "not_available", "live_recomputable_while_current",
        ):
            raise ProtocolShapeError("EvaluationRun availability semantics are outside v0")
        for name in ("query_digest", "projection_head_id", "projection_head_content_digest", "result_id", "run_id", "evaluated_at"):
            _text(getattr(self, name), name)
        _sha_hex(self.query_digest, "query_digest")
        _sha_hex(self.projection_head_content_digest, "projection_head_content_digest")
        _prefixed_hex(self.result_id, "evalr_v1:", "result_id")
        _prefixed_hex(self.run_id, "run_v1:", "run_id")
        for name in ("view_snapshot_digest", "result_digest"):
            _sha_token(getattr(self, name), name)
        if not isinstance(self.execution_profile, EvaluationRunExecutionProfileV0):
            raise ProtocolShapeError("EvaluationRun execution profile is invalid")
        if not isinstance(self.bindings, tuple) or not all(isinstance(item, EvaluationRunBindingV0) for item in self.bindings):
            raise ProtocolShapeError("EvaluationRun bindings are invalid")
        if (
            not isinstance(self.selections, tuple)
            or not self.selections
            or not all(
                isinstance(item, (EvaluationRunSelectionV0, EvaluationRunNavigationSelectionV0))
                for item in self.selections
            )
            or len({item.alias for item in self.selections}) != len(self.selections)
        ):
            raise ProtocolShapeError("EvaluationRun selections are invalid")
        if not isinstance(self.row_anchors, tuple) or not all(isinstance(item, EvaluationRunRowAnchorV0) for item in self.row_anchors):
            raise ProtocolShapeError("EvaluationRun row anchors are invalid")
        if tuple(item.ordinal for item in self.row_anchors) != tuple(range(len(self.row_anchors))):
            raise ProtocolShapeError("EvaluationRun row ordinals are not contiguous")
        if len({item.row_id for item in self.row_anchors}) != len(self.row_anchors):
            raise ProtocolShapeError("EvaluationRun row ids are not unique")
        if any(item.query_digest != self.query_digest for item in self.row_anchors):
            raise ProtocolShapeError("EvaluationRun row query identity mismatch")
        expected = tuple(sorted(item.semantic_anchor_digest for item in self.row_anchors))
        if not isinstance(self.summary, EvaluationRunSummaryAnchorV0) or self.summary.query_digest != self.query_digest or self.summary.row_anchor_digests != expected:
            raise ProtocolShapeError("EvaluationRun summary does not match rows")
        values = tuple(getattr(self, name) for name in self.__dataclass_fields__ if name != "anchor_digest")
        _seal(self.anchor_digest, _token("evaluation_run_anchor_v0", _plain(values)), "anchor_digest")


def _plain(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _plain(asdict(value))
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _seal(supplied: str, expected: str, name: str) -> None:
    _sha_token(supplied, name)
    if supplied != expected:
        raise ProtocolShapeError(f"EvaluationRun {name} does not match content")


def _text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ProtocolShapeError(f"EvaluationRun {name} must be non-empty string")


def _sha_token(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise ProtocolShapeError(f"EvaluationRun {name} must be sha256 token")
    _sha_hex(value[7:], name)


def _sha_hex(value: object, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ProtocolShapeError(f"EvaluationRun {name} must be sha256 hex")
    if value != value.lower():
        raise ProtocolShapeError(f"EvaluationRun {name} must be lowercase sha256 hex")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ProtocolShapeError(f"EvaluationRun {name} must be sha256 hex") from exc


def _prefixed_hex(value: object, prefix: str, name: str) -> None:
    _text(value, name)
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ProtocolShapeError(f"EvaluationRun {name} uses an invalid protocol prefix")
    _sha_hex(value[len(prefix):], name)


__all__ = [
    "EvaluationRunAnchorV0", "EvaluationRunBindingV0", "EvaluationRunExecutionProfileV0",
    "EvaluationRunNavigationSelectionV0", "EvaluationRunRowAnchorV0",
    "EvaluationRunRulePinV0", "EvaluationRunSelectionItemV0", "EvaluationRunSelectionV0",
    "EvaluationRunSummaryAnchorV0", "EvaluationRunTargetV0",
]
