"""Resolved Rule-or-Policy targets for the native EvaluationQuery facade.

This module deliberately does not introduce another query compiler or evaluator.
It normalizes a resolved Rule or a managed Policy into the existing compiled
Policy/EvaluationQuery path, while retaining the source identity that an
``EvaluationRunAnchorV0`` needs to distinguish a Rule lift from a direct Policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json

from factgraph.core.protocol.digests import sha256_hex

from .evaluation_query_runtime import (
    CompiledEvaluationQueryV0,
    _assert_compiled_evaluation_query_current,
    compile_evaluation_query,
)
from .evaluation_expectation_runtime import (
    EvaluationExpectationError,
    assert_compiled_contains_row_expectation_current,
    compile_contains_row_expectations_v0,
)
from .protocol.evaluation_expectation import (
    CompiledContainsRowExpectationV0,
    ContainsRowExpectationV0,
)
from .evaluation_run_runtime import build_evaluation_run_target_v0
from .policy_runtime import CompiledPolicyV0, _assert_compiled_policy_current, compile_policy
from .protocol.evaluation_query import (
    EvaluationQuery,
    EvaluationQueryError,
    EvaluationQueryBinding,
    EvaluationQuerySelectionItem,
)
from .protocol.evaluation_run import EvaluationRunTargetV0
from .protocol.policy import (
    Policy,
    PolicyError,
    PolicyOccurrence,
    PolicyV2Only,
    policy_contains_weighted_choice,
)
from .schema_runtime import SchemaIndex
from .semantic_address_runtime import SemanticAddressSpace, manage_rule_occurrence
from .semantic_port_runtime import (
    ResolvedRuleBundle,
    SemanticPortResolutionError,
    assert_rule_contract_current,
)


_RULE_LIFT_PREFIX = "__factgraph_rule_lift__:"


class EvaluationQueryTargetError(ValueError):
    """A target cannot safely enter the unified native Query path."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResolvedEvaluationQueryTargetV1:
    """Trusted compiled target context retained only in-process.

    ``run_target`` seals source identity against the exact normalized Policy;
    it is not a wire DTO or a policy registry entry.
    """

    compiled_policy: CompiledPolicyV0
    address_space: SemanticAddressSpace = field(repr=False, compare=False)
    run_target: EvaluationRunTargetV0

    def __post_init__(self) -> None:
        _assert_resolved_target_current(self)


@dataclass(frozen=True)
class TargetedCompiledEvaluationQueryV0:
    """Existing compiled Query plus its independently sealed source target."""

    compiled_query: CompiledEvaluationQueryV0
    target: ResolvedEvaluationQueryTargetV1
    wrapper_digest: str
    expectations: tuple[CompiledContainsRowExpectationV0, ...] = ()

    def __post_init__(self) -> None:
        _assert_targeted_compiled_query_current(self)


def resolve_evaluation_query_target(
    target: ResolvedRuleBundle | Policy | ResolvedEvaluationQueryTargetV1,
    *,
    address_space: SemanticAddressSpace | None = None,
    schema_index: SchemaIndex | None = None,
) -> ResolvedEvaluationQueryTargetV1:
    """Resolve a source target without executing it or consulting a registry."""

    if schema_index is not None and not isinstance(schema_index, SchemaIndex):
        raise _error("schema_index must be SchemaIndex", "INVALID_QUERY_TARGET_SCHEMA")

    if isinstance(target, ResolvedEvaluationQueryTargetV1):
        if address_space is not None:
            raise _error(
                "address_space= is not accepted for an already resolved Query target",
                "QUERY_TARGET_ADDRESS_SPACE_UNEXPECTED",
            )
        _assert_resolved_target_current(target)
        if (
            schema_index is not None
            and schema_index.schema_digest != target.run_target.schema_digest
        ):
            raise _error(
                "resolved Query target schema does not match this FactGraph",
                "QUERY_TARGET_SCHEMA_MISMATCH",
            )
        return target

    if isinstance(target, ResolvedRuleBundle):
        if address_space is not None:
            raise _error(
                "Rule targets construct their exact one-occurrence address space internally",
                "QUERY_RULE_ADDRESS_SPACE_UNEXPECTED",
            )
        try:
            assert_rule_contract_current(target.rule, target.contract)
            if (
                schema_index is not None
                and schema_index.schema_digest != target.contract.schema_digest
            ):
                raise _error(
                    "Rule target schema does not match this FactGraph",
                    "QUERY_TARGET_SCHEMA_MISMATCH",
                )
            space = SemanticAddressSpace((manage_rule_occurrence(target, "target"),))
            policy = Policy(
                f"{_RULE_LIFT_PREFIX}{target.rule.id}",
                PolicyOccurrence("target"),
                version=target.rule.version,
            )
            compiled = compile_policy(policy, address_space=space, schema_index=schema_index)
        except EvaluationQueryTargetError:
            raise
        except PolicyError as exc:
            raise _error(str(exc), exc.code) from exc
        except (SemanticPortResolutionError, ValueError) as exc:
            raise _error(
                "resolved Rule target is no longer current", "QUERY_RULE_TARGET_STALE"
            ) from exc
        run_target = build_evaluation_run_target_v0(
            compiled_policy=compiled,
            schema_digest=target.contract.schema_digest,
            original_target_kind="rule",
            target_id=target.rule.id,
            target_version=target.rule.version,
        )
        return ResolvedEvaluationQueryTargetV1(compiled, space, run_target)

    if isinstance(target, Policy):
        if isinstance(target, PolicyV2Only) or policy_contains_weighted_choice(target):
            raise _error(
                "this Policy contains a V2-only WeightedChoice; query the enclosing "
                "ProductPolicyV1 with a V2 execution profile",
                "WEIGHTED_CHOICE_V2_ONLY",
            )
        if not isinstance(address_space, SemanticAddressSpace):
            raise _error(
                "Policy targets require their exact SemanticAddressSpace via address_space=",
                "QUERY_POLICY_ADDRESS_SPACE_REQUIRED",
            )
        if target.id.startswith(_RULE_LIFT_PREFIX):
            raise _error(
                "direct Policy ids cannot use the internal Rule-lift namespace",
                "QUERY_POLICY_RESERVED_NAMESPACE",
            )
        try:
            schema_digest = _schema_digest_for_space(address_space)
            if schema_index is not None and schema_index.schema_digest != schema_digest:
                raise _error(
                    "Policy target schema does not match this FactGraph",
                    "QUERY_TARGET_SCHEMA_MISMATCH",
                )
            compiled = compile_policy(
                target,
                address_space=address_space,
                schema_index=schema_index,
            )
        except EvaluationQueryTargetError:
            raise
        except PolicyError as exc:
            raise _error(str(exc), exc.code) from exc
        except (SemanticPortResolutionError, ValueError) as exc:
            raise _error(
                "Policy target could not be resolved", "QUERY_POLICY_TARGET_INVALID"
            ) from exc
        run_target = build_evaluation_run_target_v0(
            compiled_policy=compiled,
            schema_digest=schema_digest,
            original_target_kind="policy",
            target_id=target.id,
            target_version=target.version,
        )
        return ResolvedEvaluationQueryTargetV1(compiled, address_space, run_target)

    raise _error(
        "query target must be ResolvedRuleBundle, Policy, or a resolved Query target; "
        "bare Rules, string ids, and registries are not accepted",
        "UNSUPPORTED_QUERY_TARGET",
    )


def compile_targeted_evaluation_query(
    target: ResolvedEvaluationQueryTargetV1,
    *,
    bindings: tuple[EvaluationQueryBinding, ...],
    selections: tuple[EvaluationQuerySelectionItem, ...],
    expectations: tuple[ContainsRowExpectationV0, ...] = (),
    schema_index: SchemaIndex,
) -> TargetedCompiledEvaluationQueryV0:
    """Compile through the sole F3 typed Query compiler, without execution."""

    _assert_resolved_target_current(target)
    if not isinstance(schema_index, SchemaIndex):
        raise _error("schema_index must be SchemaIndex", "INVALID_QUERY_TARGET_SCHEMA")
    if schema_index.schema_digest != target.run_target.schema_digest:
        raise _error(
            "resolved Query target schema does not match this FactGraph",
            "QUERY_TARGET_SCHEMA_MISMATCH",
        )
    try:
        query = EvaluationQuery(
            target.compiled_policy.policy_digest,
            selections=selections,
            bindings=bindings,
        )
        compiled = compile_evaluation_query(
            query,
            compiled_policy=target.compiled_policy,
            address_space=target.address_space,
            schema_index=schema_index,
        )
    except EvaluationQueryError:
        # Preserve established, actionable compiler failures (for example,
        # PARTIAL_BRANCH_QUERY_ADDRESS) through the unified facade.
        raise
    except ValueError as exc:
        raise _error(
            "typed Query compilation rejected this target intent",
            "QUERY_TARGET_COMPILATION_REJECTED",
        ) from exc
    try:
        compiled_expectations = compile_contains_row_expectations_v0(
            expectations,
            compiled_query=compiled,
            address_space=target.address_space,
            schema_index=schema_index,
        )
    except EvaluationExpectationError as exc:
        raise _error(str(exc), exc.code) from exc
    return TargetedCompiledEvaluationQueryV0(
        compiled,
        target,
        targeted_evaluation_query_wrapper_digest_v0(
            compiled.query_digest,
            target.run_target.target_digest,
            compiled_expectations,
        ),
        compiled_expectations,
    )


def _assert_targeted_compiled_query_current(
    value: TargetedCompiledEvaluationQueryV0,
) -> None:
    if not isinstance(value, TargetedCompiledEvaluationQueryV0):
        raise _error("targeted compiled Query has invalid runtime type", "INVALID_TARGETED_QUERY")
    if not isinstance(value.compiled_query, CompiledEvaluationQueryV0):
        raise _error(
            "targeted compiled Query lacks CompiledEvaluationQueryV0", "INVALID_TARGETED_QUERY"
        )
    if not isinstance(value.target, ResolvedEvaluationQueryTargetV1):
        raise _error(
            "targeted compiled Query lacks resolved target context", "INVALID_TARGETED_QUERY"
        )
    _assert_compiled_evaluation_query_current(value.compiled_query)
    _assert_resolved_target_current(value.target)
    compiled, target = value.compiled_query, value.target
    if not isinstance(value.expectations, tuple) or not all(
        isinstance(item, CompiledContainsRowExpectationV0) for item in value.expectations
    ):
        raise _error("targeted compiled Query expectations are malformed", "INVALID_TARGETED_QUERY")
    expectation_ids = tuple(item.expectation_id for item in value.expectations)
    if len(set(expectation_ids)) != len(expectation_ids):
        raise _error(
            "targeted compiled Query expectation ids are duplicated", "DUPLICATE_EXPECTATION_ID"
        )
    if any(item.query_digest != compiled.query_digest for item in value.expectations):
        raise _error(
            "targeted compiled Query expectation does not match its Query",
            "EXPECTATION_QUERY_MISMATCH",
        )
    try:
        for item in value.expectations:
            assert_compiled_contains_row_expectation_current(item)
    except EvaluationExpectationError as exc:
        raise _error(str(exc), exc.code) from exc
    if (
        compiled.compiled_policy != target.compiled_policy
        or compiled.policy_digest != target.run_target.policy_digest
        or compiled.address_space_digest != target.run_target.address_space_digest
        or compiled.schema_digest != target.run_target.schema_digest
    ):
        raise _error(
            "targeted compiled Query does not match its sealed source target",
            "TARGETED_QUERY_CONTEXT_MISMATCH",
        )
    expected_wrapper_digest = targeted_evaluation_query_wrapper_digest_v0(
        compiled.query_digest,
        target.run_target.target_digest,
        value.expectations,
    )
    if value.wrapper_digest != expected_wrapper_digest:
        raise _error(
            "targeted compiled Query integrity seal does not match its contents",
            "TARGETED_QUERY_INTEGRITY_MISMATCH",
        )


def assert_targeted_evaluation_query_current(value: TargetedCompiledEvaluationQueryV0) -> None:
    """Public runtime guard used immediately before native execution."""

    _assert_targeted_compiled_query_current(value)


def _assert_resolved_target_current(target: ResolvedEvaluationQueryTargetV1) -> None:
    if not isinstance(target, ResolvedEvaluationQueryTargetV1):
        raise _error(
            "resolved Query target has invalid runtime type", "INVALID_RESOLVED_QUERY_TARGET"
        )
    if not isinstance(target.compiled_policy, CompiledPolicyV0):
        raise _error(
            "resolved Query target lacks CompiledPolicyV0", "INVALID_RESOLVED_QUERY_TARGET"
        )
    if not isinstance(target.address_space, SemanticAddressSpace):
        raise _error(
            "resolved Query target lacks SemanticAddressSpace", "INVALID_RESOLVED_QUERY_TARGET"
        )
    if not isinstance(target.run_target, EvaluationRunTargetV0):
        raise _error(
            "resolved Query target lacks EvaluationRunTargetV0", "INVALID_RESOLVED_QUERY_TARGET"
        )
    try:
        _assert_compiled_policy_current(target.compiled_policy)
        schema_digest = _schema_digest_for_space(target.address_space)
    except (SemanticPortResolutionError, ValueError) as exc:
        raise _error("resolved Query target is stale", "QUERY_TARGET_STALE") from exc
    if target.address_space.address_space_digest != target.compiled_policy.address_space_digest:
        raise _error(
            "resolved Query target address space does not match its compiled Policy",
            "QUERY_TARGET_ADDRESS_SPACE_MISMATCH",
        )
    source = target.run_target
    expected = build_evaluation_run_target_v0(
        compiled_policy=target.compiled_policy,
        schema_digest=schema_digest,
        original_target_kind=source.original_target_kind,
        target_id=source.target_id,
        target_version=source.target_version,
    )
    if source != expected:
        raise _error(
            "resolved Query target does not match its compiled Policy or source Rule contract",
            "QUERY_TARGET_INTEGRITY_MISMATCH",
        )


def _schema_digest_for_space(space: SemanticAddressSpace) -> str:
    try:
        digests = {managed.contract.schema_digest for managed in space.occurrences}
        for managed in space.occurrences:
            assert_rule_contract_current(managed.occurrence.rule, managed.contract)
    except SemanticPortResolutionError as exc:
        raise _error("address space contains a stale Rule contract", "QUERY_TARGET_STALE") from exc
    if len(digests) != 1:
        raise _error(
            "address space must use exactly one schema digest", "QUERY_TARGET_SCHEMA_MISMATCH"
        )
    return next(iter(digests))


def _error(message: str, code: str) -> EvaluationQueryTargetError:
    return EvaluationQueryTargetError(message, code=code)


def targeted_evaluation_query_wrapper_digest_v0(
    query_digest: str,
    target_digest: str,
    expectations: tuple[CompiledContainsRowExpectationV0, ...] = (),
) -> str:
    """Return the exact v0 seal for one targeted Query wrapper.

    This is deliberately a pure, shared helper.  Detached capture can retain
    the F4 bundle's public target pin without serializing the in-process
    address space, then rederive the original wrapper seal from that pin and
    its ordered compiled expectation inventory.
    """
    payload = {
        "format": "targeted_compiled_evaluation_query_v0",
        "query_digest": query_digest,
        "target_digest": target_digest,
        "expectation_digests": [item.expectation_digest for item in expectations],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return f"sha256:{sha256_hex(encoded)}"


# Keep the old private spelling as a compatibility alias for application-local
# callers/tests.  It delegates to the public v0 helper and therefore preserves
# the exact pre-Q15 digest bytes.
def _targeted_query_digest(
    query_digest: str,
    target_digest: str,
    expectations: tuple[CompiledContainsRowExpectationV0, ...] = (),
) -> str:
    return targeted_evaluation_query_wrapper_digest_v0(
        query_digest,
        target_digest,
        expectations,
    )


__all__ = [
    "EvaluationQueryTargetError",
    "ResolvedEvaluationQueryTargetV1",
    "TargetedCompiledEvaluationQueryV0",
    "assert_targeted_evaluation_query_current",
    "compile_targeted_evaluation_query",
    "resolve_evaluation_query_target",
    "targeted_evaluation_query_wrapper_digest_v0",
]
