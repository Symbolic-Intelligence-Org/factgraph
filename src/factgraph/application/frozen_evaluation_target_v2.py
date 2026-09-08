"""Restart-safe executable targets for branch-aware Product V2 evaluation.

This is an internal persistence protocol.  It does not accept arbitrary Python
objects, import classes named by a payload, compile a Policy during decode, or
consult a Rule/schema registry.  The codec supports one deliberately closed
set of deterministic Product Policy compiler values and carries the normalized
schema material needed to restore their trusted execution context.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, NoReturn, cast

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules.where_ast import (
    AggregateAtom,
    AndExpr,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    OrExpr,
    Origin,
    PredAtom,
    RuleRefAtom,
    Var,
)
from factgraph.sdk.product_authoring import (
    AssetMeta,
    AssetMetaAbsentV1,
    ProductPolicyV1,
)

from .branch_input_case_runtime import (
    CompiledBranchSemanticSourceV1,
    CompiledInputCaseFieldV1,
    CompiledInputCaseTemplateV1,
    CompiledResultCaseFieldV1,
    instantiate_compiled_input_case_v1,
)
from .evaluation_query_target_runtime import (
    ResolvedEvaluationQueryTargetV1,
    TargetedCompiledEvaluationQueryV0,
)
from .goal_plan_v2_runtime import GOAL_PLAN_V2_COMPILER_DIGEST
from .policy_runtime import (
    CompiledPolicyV0,
    PolicyCompiledBranch,
    PolicyRulePin,
    _PolicyBranchVariant,
    _ResolvedPolicyCompare,
    _ResolvedPolicyOperand,
)
from .protocol.evaluation_run import EvaluationRunRulePinV0, EvaluationRunTargetV0
from .protocol.policy import (
    Policy,
    PolicyAll,
    PolicyAny,
    PolicyCompare,
    PolicyCompareStructureNodeV0,
    PolicyConditionLoweredRefV0,
    PolicyFieldNavigation,
    PolicyLineage,
    PolicyLiteral,
    PolicyLoweredRef,
    PolicyNodeLineage,
    PolicyOccurrence,
    PolicyStructureNodeV0,
    PolicyStructureV0,
    PolicyUnify,
)
from .protocol.rule import PortType, Rule, RuleOccurrence, RulePortRef
from .protocol.rule_expr import RuleJoinConstraint, _AndGroup, _OrGroup, _RuleOperand
from .protocol.rule_expr_lowering import (
    RuleExprAdapterSupport,
    RuleExprDeclaredPort,
    RuleExprDeclaredPortBranchSource,
    RuleExprEvaluationTrace,
    RuleExprHeadBinding,
    RuleExprHeadPortLinkMaterialization,
    RuleExprHeadValidation,
    RuleExprJoinMaterialization,
    RuleExprLoweringBranch,
    RuleExprLoweringPlan,
    RuleExprOccurrenceBinding,
    RuleExprPolicyCondition,
    RuleExprPolicyConditionMaterialization,
    RuleExprPortBinding,
    RuleExprQueryNavigationMaterialization,
    _DNFBranch,
    _RuleExprBodyPlan,
    _RuleExprQueryHeadLink,
    _RuleExprQueryNavigationLookup,
    _RuleExprQueryValueBinding,
)
from .protocol.schema_runtime import FieldPath
from .protocol.semantic_address import SemanticPortAddress
from .protocol.semantic_port import (
    EntityIdentityEndpoint,
    FieldEndpoint,
    ResolvedRuleContract,
    SemanticRulePort,
)
from .schema_runtime import SchemaIndex, build_schema_index
from .semantic_address_runtime import ManagedRuleOccurrence, SemanticAddressSpace

FROZEN_EVALUATION_TARGET_V2_FORMAT = "frozen_evaluation_target_v2"
FROZEN_EVALUATION_TARGET_V2_VERSION = 1
FROZEN_EVALUATION_TARGET_V2_COMPILER_ABI = "sha256:" + sha256_hex(
    (
        "factgraph.frozen-evaluation-target-v2.compiler-abi.1|"
        + GOAL_PLAN_V2_COMPILER_DIGEST
    ).encode("utf-8")
)
FROZEN_EVALUATION_TARGET_V2_RUNTIME_ABI = "sha256:" + sha256_hex(
    b"factgraph.frozen-evaluation-target-v2.runtime-abi.1"
)
_MAX_CARRIER_BYTES = 32 * 1024 * 1024


class FrozenEvaluationTargetError(ValueError):
    """A frozen executable target cannot be encoded or restored safely."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


_CLASSES: tuple[type[Any], ...] = (
    AggregateAtom,
    AndExpr,
    AssetMeta,
    AssetMetaAbsentV1,
    BuiltinAtom,
    CmpAtom,
    CompiledBranchSemanticSourceV1,
    CompiledInputCaseFieldV1,
    CompiledPolicyV0,
    CompiledResultCaseFieldV1,
    Const,
    EntityIdentityEndpoint,
    EvaluationRunRulePinV0,
    EvaluationRunTargetV0,
    FieldEndpoint,
    FieldPath,
    InAtom,
    ManagedRuleOccurrence,
    NotAtom,
    OrExpr,
    Origin,
    Policy,
    PolicyAll,
    PolicyAny,
    PolicyCompare,
    PolicyCompareStructureNodeV0,
    PolicyCompiledBranch,
    PolicyConditionLoweredRefV0,
    PolicyFieldNavigation,
    PolicyLineage,
    PolicyLiteral,
    PolicyLoweredRef,
    PolicyNodeLineage,
    PolicyOccurrence,
    PolicyRulePin,
    PolicyStructureNodeV0,
    PolicyStructureV0,
    PolicyUnify,
    PredAtom,
    PortType,
    ProductPolicyV1,
    ResolvedEvaluationQueryTargetV1,
    ResolvedRuleContract,
    Rule,
    RuleExprAdapterSupport,
    RuleExprDeclaredPort,
    RuleExprDeclaredPortBranchSource,
    RuleExprEvaluationTrace,
    RuleExprHeadBinding,
    RuleExprHeadPortLinkMaterialization,
    RuleExprHeadValidation,
    RuleExprJoinMaterialization,
    RuleExprLoweringBranch,
    RuleExprLoweringPlan,
    RuleExprOccurrenceBinding,
    RuleExprPolicyCondition,
    RuleExprPolicyConditionMaterialization,
    RuleExprPortBinding,
    RuleExprQueryNavigationMaterialization,
    RuleJoinConstraint,
    RuleOccurrence,
    RulePortRef,
    RuleRefAtom,
    SemanticAddressSpace,
    SemanticPortAddress,
    SemanticRulePort,
    Var,
    _AndGroup,
    _DNFBranch,
    _OrGroup,
    _PolicyBranchVariant,
    _ResolvedPolicyCompare,
    _ResolvedPolicyOperand,
    _RuleExprBodyPlan,
    _RuleExprQueryHeadLink,
    _RuleExprQueryNavigationLookup,
    _RuleExprQueryValueBinding,
    _RuleOperand,
)
_CLASS_BY_NAME: dict[str, type[Any]] = {
    f"{kind.__module__}.{kind.__qualname__}": kind for kind in _CLASSES
}
_CLASS_NAME: dict[type[Any], str] = {
    kind: name for name, kind in _CLASS_BY_NAME.items()
}
_SKIPPED_FIELDS = {
    (ProductPolicyV1, "_authoring_owner"),
    (SemanticAddressSpace, "_by_alias"),
}


def _fail(message: str, code: str) -> NoReturn:
    raise FrozenEvaluationTargetError(message, code=code)


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise FrozenEvaluationTargetError(
            "frozen target material is not canonical",
            code="FROZEN_TARGET_NONCANONICAL",
        ) from exc


def _token(domain: str, value: object) -> str:
    return "sha256:" + sha256_hex(
        _canonical_bytes({"domain": domain, "value": value})
    )


def _encoded_sort_key(value: object) -> bytes:
    return _canonical_bytes(value)


def _encode(value: object) -> object:
    if value is None or type(value) in {bool, int, float, str}:
        return value
    if isinstance(value, bytes):
        return {"$bytes": base64.b64encode(value).decode("ascii")}
    if isinstance(value, tuple):
        return {"$tuple": [_encode(item) for item in value]}
    if isinstance(value, list):
        return {"$list": [_encode(item) for item in value]}
    if isinstance(value, frozenset):
        items = sorted((_encode(item) for item in value), key=_encoded_sort_key)
        return {"$frozenset": items}
    if isinstance(value, Mapping):
        # Mapping iteration order is execution material for a few already
        # compiled records (notably Rule ports).  Store it explicitly as a
        # sequence; canonical JSON object-key sorting must not reorder it.
        mapping = cast(Mapping[object, object], value)
        mapping_items = [
            (_encode(key), _encode(item)) for key, item in mapping.items()
        ]
        return {"$map": [[key, item] for key, item in mapping_items]}
    kind = type(value)
    name = _CLASS_NAME.get(kind)
    if name is None or not is_dataclass(value):
        _fail(
            f"unsupported frozen target material: {kind.__module__}.{kind.__qualname__}",
            "FROZEN_TARGET_MATERIAL_UNSUPPORTED",
        )
    initial: dict[str, object] = {}
    derived: dict[str, object] = {}
    for item in fields(value):
        if (kind, item.name) in _SKIPPED_FIELDS:
            continue
        target = initial if item.init else derived
        target[item.name] = _encode(getattr(value, item.name))
    return {
        "$record": name,
        "fields": initial,
        "derived": derived,
    }


def _decode(value: object) -> object:
    if value is None or type(value) in {bool, int, float, str}:
        return value
    if type(value) is not dict:
        _fail("frozen target encoded value is malformed", "FROZEN_TARGET_DECODE_INVALID")
    is_single_marker = len(value) == 1
    is_record = set(value) == {"$record", "fields", "derived"}
    if not is_single_marker and not is_record:
        _fail("frozen target encoded value is malformed", "FROZEN_TARGET_DECODE_INVALID")
    if "$bytes" in value:
        raw = value["$bytes"]
        try:
            return base64.b64decode(raw, validate=True)
        except (TypeError, ValueError):
            _fail("frozen target bytes are malformed", "FROZEN_TARGET_DECODE_INVALID")
    for marker, factory in (
        ("$tuple", tuple),
        ("$list", list),
        ("$frozenset", frozenset),
    ):
        if marker in value:
            raw = value[marker]
            if type(raw) is not list:
                _fail("frozen target collection is malformed", "FROZEN_TARGET_DECODE_INVALID")
            return factory(_decode(item) for item in raw)
    if "$map" in value:
        raw = value["$map"]
        if type(raw) is not list:
            _fail("frozen target mapping is malformed", "FROZEN_TARGET_DECODE_INVALID")
        output: dict[object, object] = {}
        for pair in raw:
            if type(pair) is not list or len(pair) != 2:
                _fail("frozen target mapping entry is malformed", "FROZEN_TARGET_DECODE_INVALID")
            key, item = _decode(pair[0]), _decode(pair[1])
            if key in output:
                _fail("frozen target mapping keys repeat", "FROZEN_TARGET_DECODE_INVALID")
            output[key] = item
        return output
    if set(value) != {"$record", "fields", "derived"}:
        _fail("frozen target record is malformed", "FROZEN_TARGET_DECODE_INVALID")
    name, raw_fields, raw_derived = (
        value["$record"],
        value["fields"],
        value["derived"],
    )
    if type(name) is not str or type(raw_fields) is not dict or type(raw_derived) is not dict:
        _fail("frozen target record is malformed", "FROZEN_TARGET_DECODE_INVALID")
    kind = _CLASS_BY_NAME.get(name)
    if kind is None:
        _fail("frozen target record type is unknown", "FROZEN_TARGET_RECORD_UNKNOWN")
    expected_initial = {
        item.name
        for item in fields(kind)
        if item.init and (kind, item.name) not in _SKIPPED_FIELDS
    }
    expected_derived = {
        item.name
        for item in fields(kind)
        if not item.init and (kind, item.name) not in _SKIPPED_FIELDS
    }
    if set(raw_fields) != expected_initial or set(raw_derived) != expected_derived:
        _fail("frozen target record field set is invalid", "FROZEN_TARGET_MATERIAL_MISSING")
    try:
        restored = kind(**{key: _decode(item) for key, item in raw_fields.items()})
    except FrozenEvaluationTargetError:
        raise
    except (TypeError, ValueError, KeyError) as exc:
        raise FrozenEvaluationTargetError(
            "frozen target record failed validation",
            code="FROZEN_TARGET_MATERIAL_INVALID",
        ) from exc
    if {
        key: _encode(getattr(restored, key)) for key in expected_derived
    } != raw_derived:
        _fail("frozen target derived seal is stale", "FROZEN_TARGET_DIGEST_MISMATCH")
    return restored


def _case_to_wire(value: CompiledInputCaseTemplateV1) -> dict[str, object]:
    return {
        "case_key": value.case_key,
        "policy_digest": value.policy_digest,
        "address_space_digest": value.address_space_digest,
        "schema_digest": value.schema_digest,
        "applicable_branch_ids": _encode(value.applicable_branch_ids),
        "inputs": _encode(value.inputs),
        "results": _encode(value.results),
        "template_digest": value.template_digest,
    }


def _case_from_wire(
    value: object,
    *,
    target: ResolvedEvaluationQueryTargetV1,
    schema_index: SchemaIndex,
) -> CompiledInputCaseTemplateV1:
    keys = {
        "case_key",
        "policy_digest",
        "address_space_digest",
        "schema_digest",
        "applicable_branch_ids",
        "inputs",
        "results",
        "template_digest",
    }
    if type(value) is not dict or set(value) != keys:
        _fail("frozen Input Case material is incomplete", "FROZEN_TARGET_MATERIAL_MISSING")
    applicable = _decode(value["applicable_branch_ids"])
    inputs = _decode(value["inputs"])
    results = _decode(value["results"])
    if (
        type(applicable) is not tuple
        or not all(type(item) is str for item in applicable)
        or type(inputs) is not tuple
        or not all(type(item) is CompiledInputCaseFieldV1 for item in inputs)
        or type(results) is not tuple
        or not all(type(item) is CompiledResultCaseFieldV1 for item in results)
    ):
        _fail("frozen Input Case material has wrong types", "FROZEN_TARGET_MATERIAL_INVALID")
    restored = CompiledInputCaseTemplateV1(
        value["case_key"],
        value["policy_digest"],
        value["address_space_digest"],
        value["schema_digest"],
        cast(tuple[str, ...], applicable),
        cast(tuple[CompiledInputCaseFieldV1, ...], inputs),
        cast(tuple[CompiledResultCaseFieldV1, ...], results),
        value["template_digest"],
        target,
        schema_index,
    )
    if _case_to_wire(restored) != value:
        _fail("frozen Input Case material is not canonical", "FROZEN_TARGET_NONCANONICAL")
    return restored


@dataclass(frozen=True)
class FrozenEvaluationTargetV2:
    """Complete deterministic Product target restored without compilation."""

    product_target: ProductPolicyV1
    target: ResolvedEvaluationQueryTargetV1
    schema_index: SchemaIndex = field(repr=False, compare=False)
    input_cases: tuple[CompiledInputCaseTemplateV1, ...] = field(repr=False)
    material_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.product_target) is not ProductPolicyV1:
            _fail("frozen target requires ProductPolicyV1", "FROZEN_TARGET_PRODUCT_INVALID")
        if self.product_target.weighted_choices or self.product_target.function_occurrences:
            _fail(
                "frozen target first version supports deterministic Rule Policies only",
                "FROZEN_TARGET_PRODUCT_UNSUPPORTED",
            )
        if type(self.target) is not ResolvedEvaluationQueryTargetV1:
            _fail("frozen resolved target is invalid", "FROZEN_TARGET_TARGET_INVALID")
        if type(self.schema_index) is not SchemaIndex:
            _fail("frozen schema material is invalid", "FROZEN_TARGET_SCHEMA_INVALID")
        if (
            self.product_target.policy.id != self.target.compiled_policy.policy_id
            or self.product_target.policy.version
            != self.target.compiled_policy.policy_version
            or self.product_target.address_space != self.target.address_space
            or self.schema_index.schema_digest != self.target.run_target.schema_digest
        ):
            _fail("frozen Product/Policy/schema material is spliced", "FROZEN_TARGET_SPLICE")
        if (
            type(self.input_cases) is not tuple
            or not self.input_cases
            or not all(type(item) is CompiledInputCaseTemplateV1 for item in self.input_cases)
        ):
            _fail("frozen target requires Input Cases", "FROZEN_TARGET_CASE_INVALID")
        ordered = tuple(sorted(self.input_cases, key=lambda item: item.case_key))
        if ordered != self.input_cases or len({item.case_key for item in ordered}) != len(ordered):
            _fail("frozen Input Case inventory is not canonical", "FROZEN_TARGET_CASE_INVALID")
        if any(
            item.target != self.target
            or item.schema_index.schema_digest != self.schema_index.schema_digest
            for item in ordered
        ):
            _fail("frozen Input Case context is spliced", "FROZEN_TARGET_SPLICE")
        object.__setattr__(
            self,
            "material_digest",
            _token("factgraph.frozen-evaluation-target-v2.material", self._material()),
        )

    def _material(self) -> dict[str, object]:
        return {
            "product_target": _encode(self.product_target),
            "resolved_target": _encode(self.target),
            "schema_ir": _encode(self.schema_index.schema_ir),
            "input_cases": [_case_to_wire(item) for item in self.input_cases],
        }

    def to_wire(self) -> dict[str, object]:
        return {
            "$type": "FrozenEvaluationTargetV2",
            "format": FROZEN_EVALUATION_TARGET_V2_FORMAT,
            "version": FROZEN_EVALUATION_TARGET_V2_VERSION,
            "compiler_abi": FROZEN_EVALUATION_TARGET_V2_COMPILER_ABI,
            "runtime_abi": FROZEN_EVALUATION_TARGET_V2_RUNTIME_ABI,
            "material": self._material(),
            "material_digest": self.material_digest,
        }

    def to_bytes(self) -> bytes:
        return _canonical_bytes(self.to_wire())

    def instantiate(
        self,
        case_key: str,
        *,
        values: dict[str, object],
        optional_result_keys: tuple[str, ...] = (),
    ) -> TargetedCompiledEvaluationQueryV0:
        template = next(
            (item for item in self.input_cases if item.case_key == case_key),
            None,
        )
        if template is None:
            _fail("frozen Input Case is absent", "FROZEN_TARGET_CASE_NOT_FOUND")
        return instantiate_compiled_input_case_v1(
            template,
            values=values,
            optional_result_keys=optional_result_keys,
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> FrozenEvaluationTargetV2:
        if type(raw) is not bytes or not raw or len(raw) > _MAX_CARRIER_BYTES:
            _fail("frozen target bytes are invalid", "FROZEN_TARGET_BYTES_INVALID")

        def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
            output: dict[str, object] = {}
            for key, item in values:
                if key in output:
                    _fail("frozen target contains duplicate keys", "FROZEN_TARGET_NONCANONICAL")
                output[key] = item
            return output

        try:
            decoded = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
        except FrozenEvaluationTargetError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise FrozenEvaluationTargetError(
                "frozen target JSON is invalid",
                code="FROZEN_TARGET_DECODE_INVALID",
            ) from exc
        keys = {
            "$type",
            "format",
            "version",
            "compiler_abi",
            "runtime_abi",
            "material",
            "material_digest",
        }
        if type(decoded) is not dict or set(decoded) != keys:
            _fail("frozen target envelope is incomplete", "FROZEN_TARGET_MATERIAL_MISSING")
        if (
            type(decoded["$type"]) is not str
            or type(decoded["format"]) is not str
            or decoded["$type"] != cls.__name__
            or decoded["format"] != FROZEN_EVALUATION_TARGET_V2_FORMAT
        ):
            _fail("frozen target format is unknown", "FROZEN_TARGET_VERSION_UNSUPPORTED")
        if (
            type(decoded["version"]) is not int
            or decoded["version"] != FROZEN_EVALUATION_TARGET_V2_VERSION
        ):
            _fail("frozen target version is unsupported", "FROZEN_TARGET_VERSION_UNSUPPORTED")
        if (
            type(decoded["compiler_abi"]) is not str
            or type(decoded["runtime_abi"]) is not str
            or decoded["compiler_abi"] != FROZEN_EVALUATION_TARGET_V2_COMPILER_ABI
            or decoded["runtime_abi"] != FROZEN_EVALUATION_TARGET_V2_RUNTIME_ABI
        ):
            _fail("frozen target ABI is incompatible", "FROZEN_TARGET_ABI_MISMATCH")
        material = decoded["material"]
        material_keys = {"product_target", "resolved_target", "schema_ir", "input_cases"}
        if type(material) is not dict or set(material) != material_keys:
            _fail("frozen target material is incomplete", "FROZEN_TARGET_MATERIAL_MISSING")
        expected_digest = _token("factgraph.frozen-evaluation-target-v2.material", material)
        if (
            type(decoded["material_digest"]) is not str
            or decoded["material_digest"] != expected_digest
        ):
            _fail("frozen target material digest is stale", "FROZEN_TARGET_DIGEST_MISMATCH")
        try:
            product = _decode(material["product_target"])
            target = _decode(material["resolved_target"])
            schema_ir = _decode(material["schema_ir"])
            if type(product) is not ProductPolicyV1 or type(target) is not ResolvedEvaluationQueryTargetV1 or type(schema_ir) is not dict:
                _fail("frozen target material has wrong types", "FROZEN_TARGET_MATERIAL_INVALID")
            schema_index = build_schema_index(schema_ir)
            raw_cases = material["input_cases"]
            if type(raw_cases) is not list:
                _fail("frozen Input Case inventory is invalid", "FROZEN_TARGET_MATERIAL_INVALID")
            cases = tuple(
                _case_from_wire(item, target=target, schema_index=schema_index)
                for item in raw_cases
            )
            restored = cls(product, target, schema_index, cases)
        except FrozenEvaluationTargetError:
            raise
        except (TypeError, ValueError, KeyError) as exc:
            raise FrozenEvaluationTargetError(
                "frozen target material failed validation",
                code="FROZEN_TARGET_MATERIAL_INVALID",
            ) from exc
        if restored.material_digest != decoded["material_digest"] or restored.to_bytes() != raw:
            _fail("frozen target bytes are not canonical", "FROZEN_TARGET_NONCANONICAL")
        return restored


__all__ = [
    "FROZEN_EVALUATION_TARGET_V2_COMPILER_ABI",
    "FROZEN_EVALUATION_TARGET_V2_FORMAT",
    "FROZEN_EVALUATION_TARGET_V2_RUNTIME_ABI",
    "FROZEN_EVALUATION_TARGET_V2_VERSION",
    "FrozenEvaluationTargetError",
    "FrozenEvaluationTargetV2",
]
