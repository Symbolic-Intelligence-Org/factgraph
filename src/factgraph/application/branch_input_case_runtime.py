"""Compile heterogeneous Product input cases without runtime Policy analysis.

This is the provider-neutral seam used by Meander V3.  A caller supplies
display-safe case/field keys plus already resolved semantic addresses at
freeze time.  The compiler seals applicability and per-branch mappings.  Run
time can only fill typed values and choose declared optional result fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NoReturn, cast

from factgraph.core.protocol.digests import sha256_hex

from .evaluation_query_runtime import (
    CompiledEvaluationQueryV0,
    EvaluationQueryPortSource,
    ResolvedEvaluationQueryBinding,
    ResolvedEvaluationQuerySelection,
    _applicable_body,
    _applicable_policy_conditions,
    _attach_evaluation_query_head,
    _digest,
    _endpoint_value_type,
    _normalize_binding,
    _query_head_links,
    _query_value_bindings,
    _resolve,
)
from .evaluation_query_target_runtime import (
    ResolvedEvaluationQueryTargetV1,
    TargetedCompiledEvaluationQueryV0,
    targeted_evaluation_query_wrapper_digest_v0,
)
from .protocol.evaluation_query import EvaluationQueryBinding
from .protocol.rule import Rule
from .protocol.schema_runtime import EntityRef
from .protocol.semantic_address import SemanticPortAddress
from .schema_runtime import SchemaIndex


class BranchInputCaseError(ValueError):
    """A branch-aware case cannot be compiled or instantiated safely."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, order=True)
class BranchSemanticMappingV1:
    compiled_branch_id: str
    address: SemanticPortAddress


@dataclass(frozen=True)
class InputCaseFieldDefinitionV1:
    key: str
    required: bool
    branch_mappings: tuple[BranchSemanticMappingV1, ...]


@dataclass(frozen=True)
class ResultCaseFieldDefinitionV1:
    key: str
    always_returned: bool
    branch_mappings: tuple[BranchSemanticMappingV1, ...]


@dataclass(frozen=True)
class BranchAwareInputCaseDefinitionV1:
    case_key: str
    applicable_branch_ids: tuple[str, ...]
    inputs: tuple[InputCaseFieldDefinitionV1, ...]
    results: tuple[ResultCaseFieldDefinitionV1, ...]


@dataclass(frozen=True, order=True)
class CompiledBranchSemanticSourceV1:
    compiled_branch_id: str
    authored_address: SemanticPortAddress
    lowered_occurrence_alias: str
    value_type: str


@dataclass(frozen=True)
class CompiledInputCaseFieldV1:
    key: str
    required: bool
    sources: tuple[CompiledBranchSemanticSourceV1, ...]


@dataclass(frozen=True)
class CompiledResultCaseFieldV1:
    key: str
    always_returned: bool
    sources: tuple[CompiledBranchSemanticSourceV1, ...]


@dataclass(frozen=True)
class CompiledInputCaseTemplateV1:
    """Frozen applicability/mapping template; no authored Policy is consulted later."""

    case_key: str
    policy_digest: str
    address_space_digest: str
    schema_digest: str
    applicable_branch_ids: tuple[str, ...]
    inputs: tuple[CompiledInputCaseFieldV1, ...]
    results: tuple[CompiledResultCaseFieldV1, ...]
    template_digest: str
    target: ResolvedEvaluationQueryTargetV1 = field(repr=False, compare=False)
    schema_index: SchemaIndex = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        expected = _template_digest(
            self.case_key,
            self.policy_digest,
            self.address_space_digest,
            self.schema_digest,
            self.applicable_branch_ids,
            self.inputs,
            self.results,
        )
        if self.template_digest != expected:
            raise BranchInputCaseError(
                "compiled Input Case template seal is stale",
                code="INPUT_CASE_TEMPLATE_STALE",
            )
        if (
            self.target.compiled_policy.policy_digest != self.policy_digest
            or self.target.address_space.address_space_digest != self.address_space_digest
            or self.schema_index.schema_digest != self.schema_digest
        ):
            raise BranchInputCaseError(
                "compiled Input Case context is stale",
                code="INPUT_CASE_TEMPLATE_CONTEXT_STALE",
            )


def compile_branch_aware_input_case_v1(
    definition: BranchAwareInputCaseDefinitionV1,
    *,
    target: ResolvedEvaluationQueryTargetV1,
    schema_index: SchemaIndex,
) -> CompiledInputCaseTemplateV1:
    """Seal one case-total applicability and semantic-mapping template."""

    if not isinstance(definition, BranchAwareInputCaseDefinitionV1):
        _fail("definition must be BranchAwareInputCaseDefinitionV1", "INPUT_CASE_INVALID")
    _key(definition.case_key, "case_key")
    policy = target.compiled_policy
    declared_branch_ids = tuple(branch.branch_id for branch in policy.branches)
    applicable = definition.applicable_branch_ids
    if (
        not applicable
        or len(set(applicable)) != len(applicable)
        or applicable
        != tuple(branch_id for branch_id in declared_branch_ids if branch_id in applicable)
    ):
        _fail(
            "Input Case applicable branches must be a non-empty canonical subset",
            "INPUT_CASE_APPLICABILITY_INVALID",
        )
    inputs = tuple(
        _compile_field(item, target=target, schema_index=schema_index, applicable=applicable)
        for item in definition.inputs
    )
    results = tuple(
        _compile_result_field(
            item, target=target, schema_index=schema_index, applicable=applicable
        )
        for item in definition.results
    )
    if not inputs or not results or not any(item.always_returned for item in results):
        _fail(
            "Input Case requires inputs and at least one always-returned result",
            "INPUT_CASE_SHAPE_INVALID",
        )
    if len({item.key for item in inputs}) != len(inputs) or len(
        {item.key for item in results}
    ) != len(results):
        _fail("Input Case field keys must be unique", "INPUT_CASE_FIELD_DUPLICATE")
    digest = _template_digest(
        definition.case_key,
        policy.policy_digest,
        target.address_space.address_space_digest,
        schema_index.schema_digest,
        applicable,
        inputs,
        results,
    )
    return CompiledInputCaseTemplateV1(
        definition.case_key,
        policy.policy_digest,
        target.address_space.address_space_digest,
        schema_index.schema_digest,
        applicable,
        inputs,
        results,
        digest,
        target,
        schema_index,
    )


def instantiate_compiled_input_case_v1(
    template: CompiledInputCaseTemplateV1,
    *,
    values: dict[str, object],
    optional_result_keys: tuple[str, ...] = (),
) -> TargetedCompiledEvaluationQueryV0:
    """Fill a sealed template; never infer a case or re-resolve Policy topology."""

    CompiledInputCaseTemplateV1.__post_init__(template)
    if not isinstance(values, dict) or not all(isinstance(key, str) for key in values):
        _fail("Input Case values must be an object", "INPUT_CASE_VALUES_INVALID")
    fields = {item.key: item for item in template.inputs}
    extra = set(values) - set(fields)
    missing = {item.key for item in template.inputs if item.required and item.key not in values}
    if extra:
        _fail("Input Case contains undeclared values", "INPUT_CASE_VALUE_NOT_ALLOWED")
    if missing:
        _fail("Input Case is missing required values", "INPUT_CASE_REQUIRED_VALUE_MISSING")
    result_fields = {item.key: item for item in template.results}
    if (
        not isinstance(optional_result_keys, tuple)
        or len(set(optional_result_keys)) != len(optional_result_keys)
        or any(
            key not in result_fields or result_fields[key].always_returned
            for key in optional_result_keys
        )
    ):
        _fail("optional result selection is outside the template", "INPUT_CASE_RESULT_NOT_ALLOWED")

    bindings = tuple(
        _instantiate_binding(field, values[field.key], template)
        for field in template.inputs
        if field.key in values
    )
    selected_keys = {
        item.key for item in template.results if item.always_returned
    } | set(optional_result_keys)
    selections = tuple(
        _instantiate_selection(field)
        for field in template.results
        if field.key in selected_keys
    )
    query_digest = _digest(
        template.policy_digest,
        template.address_space_digest,
        template.schema_digest,
        bindings,
        selections,
        template.applicable_branch_ids,
    )
    head = Rule.projection(*(item.alias for item in selections))
    if head.id in template.schema_index.predicates_by_id:
        _fail("projection collides with schema namespace", "INPUT_CASE_PROJECTION_COLLISION")
    policy = template.target.compiled_policy
    plan = _attach_evaluation_query_head(
        _applicable_body(policy, template.applicable_branch_ids),
        head=head,
        query_digest=query_digest,
        head_links=_query_head_links(selections),
        value_bindings=_query_value_bindings(bindings),
        policy_conditions=_applicable_policy_conditions(
            policy, template.applicable_branch_ids
        ),
    )
    compiled = CompiledEvaluationQueryV0(
        query_digest,
        template.policy_digest,
        template.address_space_digest,
        template.schema_digest,
        bindings,
        selections,
        head,
        policy,
        plan,
        template.applicable_branch_ids,
    )
    return TargetedCompiledEvaluationQueryV0(
        compiled,
        template.target,
        targeted_evaluation_query_wrapper_digest_v0(
            query_digest, template.target.run_target.target_digest, ()
        ),
    )


def _compile_field(
    field: InputCaseFieldDefinitionV1,
    *,
    target: ResolvedEvaluationQueryTargetV1,
    schema_index: SchemaIndex,
    applicable: tuple[str, ...],
) -> CompiledInputCaseFieldV1:
    if not isinstance(field, InputCaseFieldDefinitionV1) or not isinstance(field.required, bool):
        _fail("Input Case input field is malformed", "INPUT_CASE_FIELD_INVALID")
    _key(field.key, "input key")
    return CompiledInputCaseFieldV1(
        field.key,
        field.required,
        _compile_sources(
            field.branch_mappings,
            target=target,
            schema_index=schema_index,
            applicable=applicable,
        ),
    )


def _compile_result_field(
    field: ResultCaseFieldDefinitionV1,
    *,
    target: ResolvedEvaluationQueryTargetV1,
    schema_index: SchemaIndex,
    applicable: tuple[str, ...],
) -> CompiledResultCaseFieldV1:
    if not isinstance(field, ResultCaseFieldDefinitionV1) or not isinstance(
        field.always_returned, bool
    ):
        _fail("Input Case result field is malformed", "INPUT_CASE_RESULT_INVALID")
    _key(field.key, "result key")
    return CompiledResultCaseFieldV1(
        field.key,
        field.always_returned,
        _compile_sources(
            field.branch_mappings,
            target=target,
            schema_index=schema_index,
            applicable=applicable,
        ),
    )


def _compile_sources(
    mappings: tuple[BranchSemanticMappingV1, ...],
    *,
    target: ResolvedEvaluationQueryTargetV1,
    schema_index: SchemaIndex,
    applicable: tuple[str, ...],
) -> tuple[CompiledBranchSemanticSourceV1, ...]:
    if not isinstance(mappings, tuple) or not all(
        isinstance(item, BranchSemanticMappingV1) for item in mappings
    ):
        _fail("branch semantic mappings are malformed", "INPUT_CASE_MAPPING_INVALID")
    by_branch = {item.compiled_branch_id: item for item in mappings}
    if len(by_branch) != len(mappings) or set(by_branch) != set(applicable):
        _fail(
            "every applicable branch requires exactly one semantic mapping",
            "INPUT_CASE_MAPPING_NOT_TOTAL",
        )
    policy_by_id = {item.branch_id: item for item in target.compiled_policy.branches}
    compiled: list[CompiledBranchSemanticSourceV1] = []
    value_type: str | None = None
    for branch_id in applicable:
        mapping = by_branch[branch_id]
        resolved = _resolve(mapping.address, target.address_space)
        resolved_type = _endpoint_value_type(resolved.endpoint, schema_index)
        if value_type is None:
            value_type = resolved_type
        elif resolved_type != value_type:
            _fail(
                "case-total semantic mappings must have one value type",
                "INPUT_CASE_MAPPING_TYPE_MISMATCH",
            )
        branch = policy_by_id[branch_id]
        try:
            offset = branch.authored_occurrence_aliases.index(
                mapping.address.occurrence_alias
            )
        except ValueError:
            _fail(
                "semantic mapping is outside its compiled branch namespace",
                "INPUT_CASE_MAPPING_BRANCH_MISMATCH",
            )
        compiled.append(
            CompiledBranchSemanticSourceV1(
                branch_id,
                mapping.address,
                branch.lowered_occurrence_aliases[offset],
                resolved_type,
            )
        )
    return tuple(compiled)


def _instantiate_binding(
    field: CompiledInputCaseFieldV1,
    raw_value: object,
    template: CompiledInputCaseTemplateV1,
) -> ResolvedEvaluationQueryBinding:
    normalized: tuple[str, Any, str] | None = None
    for source in field.sources:
        current = _normalize_binding(
            EvaluationQueryBinding(
                source.authored_address,
                cast(EntityRef | str | int | float | bool | bytes, raw_value),
            ),
            _resolve(source.authored_address, template.target.address_space).endpoint,
            template.schema_index,
        )
        if normalized is None:
            normalized = current
        elif current != normalized:
            _fail(
                "one typed Input Case value normalized differently across branches",
                "INPUT_CASE_VALUE_MAPPING_MISMATCH",
            )
    assert normalized is not None
    value_type, value, value_digest = normalized
    return ResolvedEvaluationQueryBinding(
        field.sources[0].authored_address,
        value_type,
        value,
        value_digest,
        tuple(
            EvaluationQueryPortSource(
                item.compiled_branch_id,
                item.lowered_occurrence_alias,
                item.authored_address.port_name,
            )
            for item in field.sources
        ),
    )


def _instantiate_selection(
    field: CompiledResultCaseFieldV1,
) -> ResolvedEvaluationQuerySelection:
    value_type = field.sources[0].value_type
    return ResolvedEvaluationQuerySelection(
        field.key,
        field.sources[0].authored_address,
        value_type,
        tuple(
            EvaluationQueryPortSource(
                item.compiled_branch_id,
                item.lowered_occurrence_alias,
                item.authored_address.port_name,
            )
            for item in field.sources
        ),
    )


def _template_digest(
    case_key: str,
    policy_digest: str,
    address_space_digest: str,
    schema_digest: str,
    applicable: tuple[str, ...],
    inputs: tuple[CompiledInputCaseFieldV1, ...],
    results: tuple[CompiledResultCaseFieldV1, ...],
) -> str:
    payload = repr(
        (
            "compiled_input_case_template_v1",
            case_key,
            policy_digest,
            address_space_digest,
            schema_digest,
            applicable,
            tuple(
                (
                    item.key,
                    item.required,
                    tuple(
                        (
                            source.compiled_branch_id,
                            source.authored_address.occurrence_alias,
                            source.authored_address.port_name,
                            source.lowered_occurrence_alias,
                            source.value_type,
                        )
                        for source in item.sources
                    ),
                )
                for item in inputs
            ),
            tuple(
                (
                    item.key,
                    item.always_returned,
                    tuple(
                        (
                            source.compiled_branch_id,
                            source.authored_address.occurrence_alias,
                            source.authored_address.port_name,
                            source.lowered_occurrence_alias,
                            source.value_type,
                        )
                        for source in item.sources
                    ),
                )
                for item in results
            ),
        )
    ).encode("utf-8")
    return f"sha256:{sha256_hex(payload)}"


def _key(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        _fail(f"{label} must be a non-empty canonical string", "INPUT_CASE_KEY_INVALID")
    return value


def _fail(message: str, code: str) -> NoReturn:
    raise BranchInputCaseError(message, code=code)


__all__ = [
    "BranchAwareInputCaseDefinitionV1",
    "BranchInputCaseError",
    "BranchSemanticMappingV1",
    "CompiledInputCaseTemplateV1",
    "InputCaseFieldDefinitionV1",
    "ResultCaseFieldDefinitionV1",
    "compile_branch_aware_input_case_v1",
    "instantiate_compiled_input_case_v1",
]
