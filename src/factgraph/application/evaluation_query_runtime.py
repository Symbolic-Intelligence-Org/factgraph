from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1, claim_args_from_rest_terms
from factgraph.core.rules.where_ast import Const

from .policy_runtime import CompiledPolicyV0, _assert_compiled_policy_current
from .protocol.evaluation_query import (
    EvaluationQuery,
    EvaluationQueryBinding,
    EvaluationQueryError,
    EvaluationQueryFieldNavigationV0,
    EvaluationQueryNavigationSelectionV0,
)
from .protocol.policy import PolicyError
from .protocol.rule import Rule
from .protocol.rule_expr import RuleExprError
from .protocol.rule_expr_lowering import (
    RuleExprLoweringPlan,
    _attach_evaluation_query_head,
    _RuleExprBodyPlan,
    _RuleExprQueryHeadLink,
    _RuleExprQueryNavigationLookup,
    _RuleExprQueryValueBinding,
)
from .protocol.schema_runtime import EntityRef
from .protocol.semantic_address import SemanticPortAddress
from .protocol.semantic_port import EntityIdentityEndpoint, FieldEndpoint, FunctionValueEndpointV1
from .schema_runtime import (
    SchemaIndex,
    SchemaResolutionError,
    encode_entity_ref,
    field_predicate,
    field_value_type,
    materialize_identity,
)
from .semantic_address_runtime import SemanticAddressResolutionError, SemanticAddressSpace
from .semantic_port_runtime import SemanticPortResolutionError, assert_rule_contract_current
from .value_validation import FieldValueValidationError, validate_field_value


@dataclass(frozen=True, order=True)
class EvaluationQueryPortSource:
    branch_id: str
    occurrence_alias: str
    port_name: str


@dataclass(frozen=True)
class ResolvedEvaluationQueryBinding:
    address: SemanticPortAddress
    value_type: str
    normalized_value: Any
    value_digest: str
    sources: tuple[EvaluationQueryPortSource, ...]


@dataclass(frozen=True)
class ResolvedEvaluationQuerySelection:
    alias: str
    address: SemanticPortAddress
    value_type: str
    sources: tuple[EvaluationQueryPortSource, ...]


@dataclass(frozen=True)
class ResolvedEvaluationQueryNavigationSelectionV0:
    """One compiled Query-owned scalar lookup source."""

    alias: str
    navigation: EvaluationQueryFieldNavigationV0
    value_type: str
    field_predicate_id: str
    sources: tuple[EvaluationQueryPortSource, ...]


ResolvedEvaluationQuerySelectionItem = (
    ResolvedEvaluationQuerySelection | ResolvedEvaluationQueryNavigationSelectionV0
)


@dataclass(frozen=True)
class CompiledEvaluationQueryV0:
    query_digest: str
    policy_digest: str
    address_space_digest: str
    schema_digest: str
    bindings: tuple[ResolvedEvaluationQueryBinding, ...]
    selections: tuple[ResolvedEvaluationQuerySelectionItem, ...]
    projection_head: Rule
    compiled_policy: CompiledPolicyV0 = field(repr=False)
    _lowering_plan: RuleExprLoweringPlan = field(repr=False, compare=False)
    applicable_branch_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (
            self.query_digest,
            self.policy_digest,
            self.address_space_digest,
            self.schema_digest,
        )
        if any(not isinstance(value, str) or not value for value in values):
            raise ValueError("compiled EvaluationQuery digests must be non-empty strings")
        if not self.selections or not isinstance(self.projection_head, Rule):
            raise ValueError("compiled EvaluationQuery requires selections and a projection head")
        if not isinstance(self.compiled_policy, CompiledPolicyV0) or not isinstance(
            self._lowering_plan, RuleExprLoweringPlan
        ):
            raise ValueError("compiled EvaluationQuery requires trusted Policy and lowering plan")
        _assert_compiled_policy_current(self.compiled_policy)
        if (
            self.policy_digest != self.compiled_policy.policy_digest
            or self.address_space_digest != self.compiled_policy.address_space_digest
        ):
            raise ValueError("compiled EvaluationQuery Policy pins do not match its Policy")
        if not isinstance(self.bindings, tuple) or not all(
            isinstance(item, ResolvedEvaluationQueryBinding) for item in self.bindings
        ):
            raise ValueError("compiled EvaluationQuery bindings are malformed")
        if not isinstance(self.selections, tuple) or not all(
            isinstance(
                item,
                (ResolvedEvaluationQuerySelection, ResolvedEvaluationQueryNavigationSelectionV0),
            )
            for item in self.selections
        ):
            raise ValueError("compiled EvaluationQuery selections are malformed")
        if not _valid_sources(self.bindings) or not _valid_sources(self.selections):
            raise ValueError("compiled EvaluationQuery branch sources are malformed")
        all_branch_ids = tuple(branch.branch_id for branch in self.compiled_policy.branches)
        applicable_branch_ids = self.applicable_branch_ids or all_branch_ids
        if (
            not isinstance(self.applicable_branch_ids, tuple)
            or not applicable_branch_ids
            or len(set(applicable_branch_ids)) != len(applicable_branch_ids)
            or any(branch_id not in all_branch_ids for branch_id in applicable_branch_ids)
            or applicable_branch_ids != tuple(
                branch_id for branch_id in all_branch_ids if branch_id in applicable_branch_ids
            )
        ):
            raise ValueError("compiled EvaluationQuery applicable branches are malformed")
        expected_source_ids = set(applicable_branch_ids)
        if any(
            {source.branch_id for source in item.sources} != expected_source_ids
            for item in (*self.bindings, *self.selections)
        ):
            raise ValueError("compiled EvaluationQuery sources are not case-total")
        for item in self.bindings:
            canonical_value, value_digest = _canonical_value(item.value_type, item.normalized_value)
            if item.normalized_value != canonical_value or item.value_digest != value_digest:
                raise ValueError("compiled EvaluationQuery binding digest does not match its value")
        expected_head = Rule.projection(*(item.alias for item in self.selections))
        if self.projection_head != expected_head:
            raise ValueError("compiled EvaluationQuery projection head does not match selections")
        if self.query_digest != _digest(
            self.policy_digest,
            self.address_space_digest,
            self.schema_digest,
            self.bindings,
            self.selections,
            self.applicable_branch_ids,
        ):
            raise ValueError("compiled EvaluationQuery digest does not match query intent")
        expected_plan = _attach_evaluation_query_head(
            _applicable_body(self.compiled_policy, self.applicable_branch_ids),
            head=expected_head,
            query_digest=self.query_digest,
            head_links=_query_head_links(self.selections),
            value_bindings=_query_value_bindings(self.bindings),
            navigation_lookups=_query_navigation_lookups(self.selections),
            policy_conditions=_applicable_policy_conditions(
                self.compiled_policy, self.applicable_branch_ids
            ),
        )
        if self._lowering_plan != expected_plan:
            raise ValueError("compiled EvaluationQuery lowering plan is not compiler-derived")


def _assert_compiled_evaluation_query_current(compiled_query: CompiledEvaluationQueryV0) -> None:
    if not isinstance(compiled_query, CompiledEvaluationQueryV0):
        raise ValueError("compiled_query must be CompiledEvaluationQueryV0")
    CompiledEvaluationQueryV0.__post_init__(compiled_query)


def compile_evaluation_query(
    query: EvaluationQuery,
    *,
    compiled_policy: CompiledPolicyV0,
    address_space: SemanticAddressSpace,
    schema_index: SchemaIndex,
) -> CompiledEvaluationQueryV0:
    """Compile typed direct-port bind/select intent without executing an engine."""
    if not isinstance(query, EvaluationQuery):
        raise _error("query must be EvaluationQuery", "INVALID_EVALUATION_QUERY", "query_compile")
    if not isinstance(compiled_policy, CompiledPolicyV0):
        raise _error(
            "compiled_policy must be CompiledPolicyV0", "INVALID_COMPILED_POLICY", "query_compile"
        )
    if not isinstance(address_space, SemanticAddressSpace) or not isinstance(
        schema_index, SchemaIndex
    ):
        raise _error(
            "address_space and schema_index must be trusted runtime values",
            "INVALID_QUERY_CONTEXT",
            "query_compile",
        )
    _assert_context(query, compiled_policy, address_space, schema_index)

    bindings: list[ResolvedEvaluationQueryBinding] = []
    for item in query.bindings:
        resolved = _resolve(item.address, address_space)
        value_type, value, value_digest = _normalize_binding(item, resolved.endpoint, schema_index)
        bindings.append(
            ResolvedEvaluationQueryBinding(
                item.address,
                value_type,
                value,
                value_digest,
                _branch_sources(compiled_policy, item.address),
            )
        )
    selections: list[ResolvedEvaluationQuerySelectionItem] = []
    for selection in query.selections:
        if isinstance(selection, EvaluationQueryNavigationSelectionV0):
            selections.append(
                _resolve_navigation_selection(
                    selection,
                    compiled_policy,
                    address_space,
                    schema_index,
                )
            )
        else:
            resolved = _resolve(selection.address, address_space)
            selections.append(
                ResolvedEvaluationQuerySelection(
                    selection.alias,
                    selection.address,
                    _endpoint_value_type(resolved.endpoint, schema_index),
                    _branch_sources(compiled_policy, selection.address),
                )
            )

    normalized_bindings, normalized_selections = tuple(bindings), tuple(selections)
    query_digest = _digest(
        compiled_policy.policy_digest,
        address_space.address_space_digest,
        schema_index.schema_digest,
        normalized_bindings,
        normalized_selections,
        (),
    )
    head = Rule.projection(*(item.alias for item in normalized_selections))
    if head.id in schema_index.predicates_by_id:
        raise _error(
            "query projection id collides with the trusted schema namespace",
            "QUERY_PROJECTION_NAMESPACE_COLLISION",
            "query_admission",
        )
    try:
        plan = _attach_evaluation_query_head(
            compiled_policy._body_plan,
            head=head,
            query_digest=query_digest,
            head_links=_query_head_links(normalized_selections),
            value_bindings=_query_value_bindings(normalized_bindings),
            navigation_lookups=_query_navigation_lookups(normalized_selections),
            policy_conditions=compiled_policy._policy_conditions,
        )
        return CompiledEvaluationQueryV0(
            query_digest,
            compiled_policy.policy_digest,
            address_space.address_space_digest,
            schema_index.schema_digest,
            normalized_bindings,
            normalized_selections,
            head,
            compiled_policy,
            plan,
        )
    except (PolicyError, RuleExprError, ValueError) as exc:
        raise _error(
            "query lowering rejected trusted compiled inputs",
            "QUERY_LOWERING_INVARIANT",
            "query_compiler_invariant",
            details={"cause_type": type(exc).__name__},
        ) from exc


def _assert_context(
    query: EvaluationQuery,
    policy: CompiledPolicyV0,
    space: SemanticAddressSpace,
    index: SchemaIndex,
) -> None:
    try:
        _assert_compiled_policy_current(policy)
    except PolicyError as exc:
        raise _error(
            "compiled Policy failed its structural integrity check",
            "QUERY_POLICY_CONTEXT_STALE",
            "query_admission",
            details={"policy_code": exc.code},
        ) from exc
    if query.policy_digest != policy.policy_digest:
        raise _error(
            "query does not reference this compiled Policy",
            "QUERY_POLICY_DIGEST_MISMATCH",
            "query_admission",
        )
    if space.address_space_digest != policy.address_space_digest:
        raise _error(
            "address space does not match compiled Policy",
            "QUERY_ADDRESS_SPACE_MISMATCH",
            "query_admission",
        )
    pins, schema_digests = {pin.occurrence_alias: pin for pin in policy.rule_pins}, set()
    try:
        for managed in space.occurrences:
            assert_rule_contract_current(managed.occurrence.rule, managed.contract)
            alias, rule = managed.occurrence.alias, managed.occurrence.rule
            pin = pins.get(alias)
            pinned = (
                None
                if pin is None
                else (
                    pin.rule_id,
                    pin.rule_version,
                    pin.rule_content_digest,
                    pin.semantic_contract_digest,
                )
            )
            current = (
                rule.id,
                rule.version,
                rule.content_digest,
                managed.contract.semantic_contract_digest,
            )
            if pinned != current:
                raise _error(
                    "compiled Policy Rule pins are stale",
                    "QUERY_POLICY_CONTEXT_STALE",
                    "query_admission",
                )
            schema_digests.add(managed.contract.schema_digest)
    except SemanticPortResolutionError as exc:
        raise _error(
            "managed Rule contract is stale", "QUERY_POLICY_CONTEXT_STALE", "query_admission"
        ) from exc
    aliases = {item.occurrence.alias for item in space.occurrences}
    if set(pins) != aliases or schema_digests != {index.schema_digest}:
        raise _error(
            "compiled Policy and trusted schema context do not agree",
            "QUERY_SCHEMA_CONTEXT_MISMATCH",
            "query_admission",
        )


def _branch_sources(
    policy: CompiledPolicyV0,
    address: SemanticPortAddress,
) -> tuple[EvaluationQueryPortSource, ...]:
    sources: list[EvaluationQueryPortSource] = []
    for branch in policy.branches:
        try:
            offset = branch.authored_occurrence_aliases.index(address.occurrence_alias)
        except ValueError as exc:
            raise _error(
                "query address is not present in every Policy branch",
                "PARTIAL_BRANCH_QUERY_ADDRESS",
                "query_admission",
                ("address", address.occurrence_alias, address.port_name),
                {"missing_branch_id": branch.branch_id},
            ) from exc
        sources.append(
            EvaluationQueryPortSource(
                branch.branch_id,
                branch.lowered_occurrence_aliases[offset],
                address.port_name,
            )
        )
    return tuple(sources)


def _resolve(address: SemanticPortAddress, space: SemanticAddressSpace) -> Any:
    try:
        return space.resolve(address)
    except SemanticAddressResolutionError as exc:
        raise _error(
            str(exc),
            "UNRESOLVED_QUERY_ADDRESS",
            "query_admission",
            ("address", address.occurrence_alias, address.port_name),
            {"semantic_address_code": exc.code},
        ) from exc


def _endpoint_value_type(endpoint: object, index: SchemaIndex) -> str:
    if isinstance(endpoint, EntityIdentityEndpoint):
        return "entity_ref"
    if isinstance(endpoint, FieldEndpoint):
        return str(
            field_predicate(index, endpoint.entity_type, endpoint.field_name).value_type_domain
        )
    if isinstance(endpoint, FunctionValueEndpointV1):
        return endpoint.scalar_domain
    raise _error("unsupported semantic endpoint", "UNSUPPORTED_QUERY_ENDPOINT", "query_admission")


def _resolve_navigation_selection(
    selection: EvaluationQueryNavigationSelectionV0,
    policy: CompiledPolicyV0,
    space: SemanticAddressSpace,
    index: SchemaIndex,
) -> ResolvedEvaluationQueryNavigationSelectionV0:
    navigation = selection.navigation
    resolved = _resolve(navigation.base, space)
    if not isinstance(resolved.endpoint, EntityIdentityEndpoint):
        raise _error(
            "Query field navigation must start at an EntityIdentity port",
            "INVALID_QUERY_NAVIGATION",
            "query_admission",
            ("selections", selection.alias, "base"),
        )
    if resolved.endpoint.entity_type != navigation.field.entity_type:
        raise _error(
            "Query field navigation must stay on the identity endpoint entity type",
            "INVALID_QUERY_NAVIGATION",
            "query_admission",
            ("selections", selection.alias, "field"),
            {
                "base_entity_type": resolved.endpoint.entity_type,
                "field_entity_type": navigation.field.entity_type,
            },
        )
    try:
        predicate = field_predicate(
            index, navigation.field.entity_type, navigation.field.field_name
        )
        value_type = field_value_type(
            index, navigation.field.entity_type, navigation.field.field_name
        )
    except SchemaResolutionError as exc:
        raise _error(
            str(exc),
            "INVALID_QUERY_NAVIGATION",
            "query_admission",
            ("selections", selection.alias, "field"),
            {"schema_code": exc.code},
        ) from exc
    if (
        value_type.value_kind != "scalar"
        or value_type.cardinality != "single"
        or value_type.scalar_domain is None
        or predicate.is_identity_field
    ):
        raise _error(
            "Query field navigation must select one non-identity scalar field",
            "UNSUPPORTED_QUERY_NAVIGATION",
            "query_admission",
            ("selections", selection.alias, "field"),
            {"value_kind": value_type.value_kind, "cardinality": value_type.cardinality},
        )
    return ResolvedEvaluationQueryNavigationSelectionV0(
        selection.alias,
        navigation,
        value_type.scalar_domain,
        predicate.pred_id,
        _branch_sources(policy, navigation.base),
    )


def _normalize_binding(
    binding: EvaluationQueryBinding,
    endpoint: object,
    index: SchemaIndex,
) -> tuple[str, Any, str]:
    if isinstance(endpoint, FunctionValueEndpointV1) and endpoint.mode == "output":
        raise _error(
            "Function output ports are derived values and cannot be Query inputs",
            "EVALUATION_QUERY_OUTPUT_BINDING_UNSUPPORTED",
            "query_admission",
            ("bindings", binding.address.occurrence_alias, binding.address.port_name),
        )
    try:
        if isinstance(endpoint, EntityIdentityEndpoint):
            if (
                not isinstance(binding.value, EntityRef)
                or binding.value.entity_type != endpoint.entity_type
            ):
                raise ValueError(f"expected EntityRef[{endpoint.entity_type}]")
            identity = materialize_identity(
                endpoint.entity_type, binding.value.identity, index=index
            )
            typed_value: Any = encode_entity_ref(
                EntityRef(endpoint.entity_type, identity), index=index
            )
            value_type = "entity_ref"
        elif isinstance(endpoint, FieldEndpoint):
            if isinstance(binding.value, EntityRef):
                raise ValueError("field endpoint expects scalar value")
            pred = field_predicate(index, endpoint.entity_type, endpoint.field_name)
            value_type, typed_value = str(pred.value_type_domain), binding.value
            if value_type == "uuid" and isinstance(typed_value, str):
                typed_value = typed_value.lower()
        elif isinstance(endpoint, FunctionValueEndpointV1):
            if isinstance(binding.value, EntityRef):
                raise ValueError("function scalar endpoint expects scalar value")
            value_type, typed_value = endpoint.scalar_domain, binding.value
            if value_type == "uuid" and isinstance(typed_value, str):
                typed_value = typed_value.lower()
        else:
            raise ValueError("unsupported semantic endpoint")
        normalized = claim_args_from_rest_terms([(value_type, typed_value)])[0][1]
        if isinstance(normalized, str) and normalized.startswith("$"):
            raise ValueError("native lowering cannot preserve a '$'-prefixed string constant")
        _canonical, value_digest = _canonical_value(value_type, normalized)
        if isinstance(endpoint, FieldEndpoint):
            validate_field_value(normalized, pred_info=pred)
        return value_type, normalized, value_digest
    except (ValueError, SchemaResolutionError, FieldValueValidationError) as exc:
        raise _error(
            f"query binding is incompatible with its semantic endpoint: {exc}",
            "QUERY_BINDING_TYPE_MISMATCH",
            "query_admission",
            ("bindings", binding.address.occurrence_alias, binding.address.port_name),
        ) from exc


def _digest(
    policy_digest: str,
    address_space_digest: str,
    schema_digest: str,
    bindings: tuple[ResolvedEvaluationQueryBinding, ...],
    selections: tuple[ResolvedEvaluationQuerySelectionItem, ...],
    applicable_branch_ids: tuple[str, ...] = (),
) -> str:
    def address(item: Any) -> list[Any]:
        return [
            item.address.occurrence_alias,
            item.address.port_name,
            tuple(
                (source.branch_id, source.occurrence_alias, source.port_name)
                for source in item.sources
            ),
        ]

    def selection(item: ResolvedEvaluationQuerySelectionItem) -> list[Any]:
        if isinstance(item, ResolvedEvaluationQuerySelection):
            # Preserve direct-selection v0 payload bytes: old compiled Query
            # digests must not change merely because navigation is now supported.
            return [item.alias, *address(item), item.value_type]
        navigation = item.navigation
        return [
            "field_navigation_v0",
            item.alias,
            navigation.base.occurrence_alias,
            navigation.base.port_name,
            navigation.field.entity_type,
            navigation.field.field_name,
            item.field_predicate_id,
            tuple(
                (source.branch_id, source.occurrence_alias, source.port_name)
                for source in item.sources
            ),
            item.value_type,
        ]

    payload = {
        "format": "compiled_evaluation_query_v0",
        "policy_digest": policy_digest,
        "address_space_digest": address_space_digest,
        "schema_digest": schema_digest,
        "bindings": [[*address(item), item.value_type, item.value_digest] for item in bindings],
        "selections": [selection(item) for item in selections],
    }
    # Empty means the historical all-branch Query and intentionally preserves
    # every pre-V3 digest byte.  A non-empty inventory seals an Input Case's
    # compile-time applicability decision.
    if applicable_branch_ids:
        payload["applicable_branch_ids"] = list(applicable_branch_ids)
    return sha256_hex(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    )


def _canonical_value(value_type: str, value: Any) -> tuple[Any, str]:
    if value_type == "bytes" and isinstance(value, str):
        value = base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))
    digest = sha256_hex(canonical_bytes_tup_v1([(value_type, value)]))
    return claim_args_from_rest_terms([(value_type, value)])[0][1], digest


def _valid_sources(items: Any) -> bool:
    return all(
        isinstance(item.sources, tuple)
        and item.sources
        and all(isinstance(source, EvaluationQueryPortSource) for source in item.sources)
        for item in items
    )


def _applicable_body(
    policy: CompiledPolicyV0,
    applicable_branch_ids: tuple[str, ...],
) -> _RuleExprBodyPlan:
    if not applicable_branch_ids:
        return policy._body_plan
    selected = frozenset(applicable_branch_ids)
    return _RuleExprBodyPlan(
        source_kind=policy._body_plan.source_kind,
        branches=tuple(
            branch for branch in policy._body_plan.branches if branch.branch_id in selected
        ),
        occurrence_map=policy._body_plan.occurrence_map,
        canonical_key=(
            *policy._body_plan.canonical_key,
            "applicable_branches_v1",
            applicable_branch_ids,
        ),
    )


def _applicable_policy_conditions(
    policy: CompiledPolicyV0,
    applicable_branch_ids: tuple[str, ...],
) -> tuple[Any, ...]:
    if not applicable_branch_ids:
        return policy._policy_conditions
    selected = frozenset(applicable_branch_ids)
    return tuple(
        condition
        for condition in policy._policy_conditions
        if condition.branch_id in selected
    )


def _query_head_links(
    selections: tuple[ResolvedEvaluationQuerySelectionItem, ...],
) -> tuple[_RuleExprQueryHeadLink, ...]:
    return tuple(
        sorted(
            _RuleExprQueryHeadLink(
                source.branch_id, item.alias, source.occurrence_alias, source.port_name
            )
            for item in selections
            if isinstance(item, ResolvedEvaluationQuerySelection)
            for source in item.sources
        )
    )


def _query_navigation_lookups(
    selections: tuple[ResolvedEvaluationQuerySelectionItem, ...],
) -> tuple[_RuleExprQueryNavigationLookup, ...]:
    return tuple(
        sorted(
            _RuleExprQueryNavigationLookup(
                source.branch_id,
                item.alias,
                source.occurrence_alias,
                source.port_name,
                item.field_predicate_id,
            )
            for item in selections
            if isinstance(item, ResolvedEvaluationQueryNavigationSelectionV0)
            for source in item.sources
        )
    )


def _query_value_bindings(
    bindings: tuple[ResolvedEvaluationQueryBinding, ...],
) -> tuple[_RuleExprQueryValueBinding, ...]:
    return tuple(
        sorted(
            (
                _RuleExprQueryValueBinding(
                    source.branch_id,
                    source.occurrence_alias,
                    source.port_name,
                    Const(item.normalized_value),
                )
                for item in bindings
                for source in item.sources
            ),
            key=lambda item: (item.branch_id, item.occurrence_alias, item.port_name),
        )
    )


def _error(
    message: str,
    code: str,
    stage: str,
    path: tuple[str, ...] = (),
    details: dict[str, Any] | None = None,
) -> EvaluationQueryError:
    return EvaluationQueryError(message, code=code, stage=stage, path=path, details=details)  # type: ignore[arg-type]


__all__ = ["CompiledEvaluationQueryV0", "compile_evaluation_query"]
