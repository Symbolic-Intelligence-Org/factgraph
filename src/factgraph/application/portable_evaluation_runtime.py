"""Narrow, deterministic three-engine execution over an isolated fact world.

``portable_deterministic_v1`` is deliberately a *small* common denominator.
It is not a general adapter abstraction and it does not claim that Native,
Soufflé, and ProbLog have identical proof models.  It does one useful thing
that the older engine adapters could not do: execute the same positive,
finite, already-materialized relation without consulting the caller's Store.

The public boundary is intentionally strict:

* one query-style ``CompiledDerivationPlan`` with one projection head;
* positive ``PredAtom`` + ``CmpAtom`` bodies only.  A finite OR-of-AND body
  is executed as one isolated, widened plan per DNF branch: public projection
  variables remain branch-total, while compiler-local witness variables stay
  local to the branch that binds them;
* no rules, aggregates, builtins, negation, engine extension/configuration, or
  confidence / probabilistic semantics;
* an exact, finite mapping of every predicate referenced by the plan to
  ``ProjectedFact`` rows;
* result parity is semantic selected-row-set parity only.  Native receipts,
  Soufflé witnesses, and ProbLog provenance deliberately remain engine-local.

The executor builds a fresh in-memory ``Store`` and ``Ledger`` for every run.
It never accepts a source Store argument, so an effective Scenario relation is
not accidentally mixed with facts outside the pinned relation.  This makes the
module a safe substrate for a later Scenario/Query runner; it is not itself a
Scenario resolver, replay format, or product assessment surface.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from factgraph.core.derivation.candidates import DerivationOutput
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1, claim_args_from_rest_terms
from factgraph.core.rules.where_ast import (
    AggregateAtom,
    BuiltinAtom,
    CmpAtom,
    Const,
    InAtom,
    NotAtom,
    PredAtom,
    RuleRefAtom,
    Term,
    Var,
    WhereASTError,
    parse_where_ir_to_ast,
)
from factgraph.core.schema.schema_ir import ensure_schema_ir
from factgraph.core.store._builders import coerce_value_for_tag
from factgraph.core.store._support import ProjectedFact
from factgraph.core.store.ledger import Claim, Ledger
from factgraph.core.store.runtime import Store

from .derivation_runtime import evaluate_derivation_plans
from .protocol.derivation import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DerivationEvaluateRequest,
)

PORTABLE_DETERMINISTIC_V1: Literal["portable_deterministic_v1"] = "portable_deterministic_v1"
PortableEngineV1 = Literal["native", "souffle", "problog"]
PortableEngineFrameStatusV1 = Literal["succeeded", "failed", "unsupported"]
_PORTABLE_ENGINES: tuple[PortableEngineV1, ...] = ("native", "souffle", "problog")


class PortableEvaluationError(ValueError):
    """A fail-closed rejection or execution failure for this narrow profile."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


@dataclass(frozen=True)
class PortableExecutionContractV1:
    """The static, engine-independent contract admitted by the profile."""

    profile: Literal["portable_deterministic_v1"]
    dependency_predicate_ids: tuple[str, ...]
    selected_head_var_names: tuple[str, ...]
    selected_value_types: tuple[str, ...]
    execution_head_var_names: tuple[str, ...]
    execution_value_types: tuple[str, ...]
    # The original fields retain the complete, deterministic execution-variable
    # envelope for callers that inspect the static contract.  A DNF body cannot
    # safely materialize that union as one physical adapter head when an ``Any``
    # branch has private variables.  These parallel inventories record the
    # actual per-branch heads used by the isolated executor instead.
    execution_branch_head_var_names: tuple[tuple[str, ...], ...] = ()
    execution_branch_value_types: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class PortableSelectedRowV1:
    """One canonical projection row, intentionally without support/proof data."""

    terms: tuple[tuple[str, object], ...]
    row_digest: str


@dataclass(frozen=True)
class PortableEngineEvaluationV1:
    """The semantic output of one real engine run over the isolated world."""

    engine: PortableEngineV1
    rows: tuple[PortableSelectedRowV1, ...]
    selected_row_set_digest: str


@dataclass(frozen=True)
class PortableEngineDiagnosticV1:
    """A stable, non-secret diagnostic for an observed engine frame.

    ``details_json`` is a canonical JSON object rather than an exception
    message.  Exception messages frequently contain temporary paths, binary
    output, or other host-specific text; accepting them as portable evidence
    would make otherwise identical observations non-deterministic.  The
    digest commits both the stable code and that canonical detail object.
    """

    code: str
    details_json: str
    detail_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code:
            raise PortableEvaluationError(
                "portable diagnostic code must be a non-empty string",
                code="PORTABLE_OBSERVATION_DIAGNOSTIC_INVALID",
            )
        if not isinstance(self.details_json, str):
            raise PortableEvaluationError(
                "portable diagnostic details must be canonical JSON text",
                code="PORTABLE_OBSERVATION_DIAGNOSTIC_INVALID",
            )
        try:
            decoded = json.loads(self.details_json)
        except (TypeError, ValueError) as exc:
            raise PortableEvaluationError(
                "portable diagnostic details must be canonical JSON text",
                code="PORTABLE_OBSERVATION_DIAGNOSTIC_INVALID",
            ) from exc
        canonical = _canonical_diagnostic_json(decoded)
        if canonical != self.details_json or not isinstance(decoded, dict):
            raise PortableEvaluationError(
                "portable diagnostic details must be a canonical JSON object",
                code="PORTABLE_OBSERVATION_DIAGNOSTIC_INVALID",
            )
        object.__setattr__(
            self,
            "detail_digest",
            _framed_digest(
                "portable_engine_diagnostic_v1",
                (self.code.encode("utf-8"), self.details_json.encode("utf-8")),
            ),
        )


@dataclass(frozen=True)
class PortableEngineObservationFrameV1:
    """One engine's independently observed outcome over the same world.

    A failed or unsupported frame deliberately has no rows.  It cannot be
    mistaken for an empty successful query result, and it never carries a
    partially-normalized output from a failed adapter invocation.
    """

    engine: PortableEngineV1
    status: PortableEngineFrameStatusV1
    evaluation: PortableEngineEvaluationV1 | None = None
    diagnostic: PortableEngineDiagnosticV1 | None = None
    frame_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.engine, str) or self.engine not in _PORTABLE_ENGINES:
            raise PortableEvaluationError(
                "portable observation frame names an unsupported engine",
                code="PORTABLE_OBSERVATION_FRAME_INVALID",
            )
        if not isinstance(self.status, str) or self.status not in {
            "succeeded",
            "failed",
            "unsupported",
        }:
            raise PortableEvaluationError(
                "portable observation frame has an unsupported status",
                code="PORTABLE_OBSERVATION_FRAME_INVALID",
            )
        if self.status == "succeeded":
            if (
                not isinstance(self.evaluation, PortableEngineEvaluationV1)
                or self.diagnostic is not None
            ):
                raise PortableEvaluationError(
                    "successful portable observation frame has invalid payload",
                    code="PORTABLE_OBSERVATION_FRAME_INVALID",
                )
            if self.evaluation.engine != self.engine:
                raise PortableEvaluationError(
                    "successful portable observation frame has an engine mismatch",
                    code="PORTABLE_OBSERVATION_FRAME_INVALID",
                )
        elif self.evaluation is not None or not isinstance(
            self.diagnostic, PortableEngineDiagnosticV1
        ):
            raise PortableEvaluationError(
                "failed/unsupported portable observation frame has invalid payload",
                code="PORTABLE_OBSERVATION_FRAME_INVALID",
            )
        object.__setattr__(
            self,
            "frame_digest",
            _framed_digest(
                "portable_engine_observation_frame_v1",
                (
                    self.engine.encode("ascii"),
                    self.status.encode("ascii"),
                    b""
                    if self.evaluation is None
                    else self.evaluation.selected_row_set_digest.encode("ascii"),
                    b""
                    if self.diagnostic is None
                    else self.diagnostic.detail_digest.encode("ascii"),
                ),
            ),
        )


@dataclass(frozen=True)
class PortableEvaluationObservationV1:
    """All independent engine frames for one validated isolated Store.

    This is an observation surface, not a parity claim.  Consumers that need
    the original all-or-nothing portable profile must continue to call
    :func:`execute_portable_deterministic_v1`.
    """

    profile: Literal["portable_deterministic_v1"]
    contract: PortableExecutionContractV1
    frames: tuple[PortableEngineObservationFrameV1, ...]
    observation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.profile != PORTABLE_DETERMINISTIC_V1:
            raise PortableEvaluationError(
                "portable observation has an unsupported profile",
                code="PORTABLE_OBSERVATION_INVALID",
            )
        if not isinstance(self.contract, PortableExecutionContractV1):
            raise PortableEvaluationError(
                "portable observation must retain its static execution contract",
                code="PORTABLE_OBSERVATION_INVALID",
            )
        if (
            not isinstance(self.frames, tuple)
            or not all(isinstance(item, PortableEngineObservationFrameV1) for item in self.frames)
            or tuple(item.engine for item in self.frames) != _PORTABLE_ENGINES
        ):
            raise PortableEvaluationError(
                "portable observation must contain exactly one ordered frame per engine",
                code="PORTABLE_OBSERVATION_INVALID",
            )
        object.__setattr__(
            self,
            "observation_digest",
            _framed_digest(
                "portable_evaluation_observation_v1",
                (
                    _portable_execution_contract_digest_v1(self.contract).encode("ascii"),
                    *(item.frame_digest.encode("ascii") for item in self.frames),
                ),
            ),
        )


@dataclass(frozen=True)
class PortableEvaluationResultV1:
    """A successfully parity-checked portable deterministic evaluation.

    ``proof_parity`` is intentionally fixed to ``not_claimed``.  A shared
    selected-row set says nothing about equality of Native proof receipts,
    Soufflé witness artifacts, or ProbLog probability/provenance traces.
    """

    profile: Literal["portable_deterministic_v1"]
    executions: tuple[PortableEngineEvaluationV1, ...]
    selected_row_set_digest: str
    proof_parity: Literal["not_claimed"] = "not_claimed"


def validate_portable_deterministic_v1(
    plan: CompiledDerivationPlan,
    *,
    schema_ir: dict[str, Any],
    effective_relations: Mapping[str, Sequence[ProjectedFact]],
) -> PortableExecutionContractV1:
    """Validate the profile without evaluating or reading any source Store.

    The relation keyset must exactly equal the plan's direct predicate
    dependencies, including an explicit empty sequence for an empty relation.
    That makes a missing fact source distinguishable from a logically empty
    source and prevents a later executor from falling back to another Store.
    """

    validated = _validate_input(
        plan,
        schema_ir=schema_ir,
        effective_relations=effective_relations,
    )
    return validated.contract


def portable_dependency_predicate_ids_v1(
    plan: CompiledDerivationPlan,
    *,
    schema_ir: dict[str, Any],
) -> tuple[str, ...]:
    """Return the exact finite relation inventory required by ``plan``.

    This is deliberately a *compiler preflight*, not a permissive dependency
    guess.  It applies the same positive deterministic profile checks as the
    executor, but it does not accept a relation or read a Store.  A caller can
    therefore select and seal exactly these predicates before Scenario or a
    relation provider is resolved, rather than materializing a broad live
    world and letting an adapter choose its own inputs.
    """

    if not isinstance(plan, CompiledDerivationPlan):
        raise PortableEvaluationError(
            "plan must be CompiledDerivationPlan",
            code="PORTABLE_PLAN_TYPE_INVALID",
        )
    if not isinstance(schema_ir, dict):
        raise PortableEvaluationError(
            "schema_ir must be a schema dict",
            code="PORTABLE_SCHEMA_INVALID",
        )
    try:
        schema = ensure_schema_ir(schema_ir)
    except Exception as exc:
        raise PortableEvaluationError(
            "schema_ir is not a valid FactGraph schema",
            code="PORTABLE_SCHEMA_INVALID",
            details={"cause_type": type(exc).__name__},
        ) from exc
    _validate_plan_shape(plan, schema)
    dependencies, _ = _validate_positive_body(plan, schema)
    return _expand_virtual_entity_dependencies(dependencies, schema=schema)


def _expand_virtual_entity_dependencies(
    dependency_ids: tuple[str, ...],
    *,
    schema: dict[str, Any],
) -> tuple[str, ...]:
    predicates = tuple(
        item for item in schema.get("predicates", ()) if isinstance(item, dict)
    )
    by_id = {
        item["pred_id"]: item for item in predicates if isinstance(item.get("pred_id"), str)
    }
    expanded = set(dependency_ids)
    for predicate_id in dependency_ids:
        predicate = by_id.get(predicate_id)
        if predicate is None or predicate.get("is_entity_exists") is not True:
            continue
        owner = predicate.get("owner_type")
        expanded.update(
            item["pred_id"]
            for item in predicates
            if item.get("owner_type") == owner
            and item.get("is_identity_field") is True
            and isinstance(item.get("pred_id"), str)
        )
    return tuple(sorted(expanded))


def materialize_portable_effective_world_v1(
    plan: CompiledDerivationPlan,
    *,
    schema_ir: dict[str, Any],
    effective_relations: Mapping[str, Sequence[ProjectedFact]],
) -> Store:
    """Build a fresh Store containing *only* the portable effective relation.

    The returned Store is intentionally detached from callers.  Original
    ``ProjectedFact.asrt_id`` values are input witnesses, not durable ids in
    the fresh ledger; result parity below is therefore defined only over the
    selected typed rows, never over assertion or proof identifiers.
    """

    validated = _validate_input(
        plan,
        schema_ir=schema_ir,
        effective_relations=effective_relations,
    )
    return _materialize_store(validated)


def observe_portable_deterministic_v1(
    plan: CompiledDerivationPlan,
    *,
    schema_ir: dict[str, Any],
    effective_relations: Mapping[str, Sequence[ProjectedFact]],
) -> PortableEvaluationObservationV1:
    """Observe Native, Soufflé, and ProbLog independently over one sealed world.

    Static contract errors still raise before any adapter is invoked: there is
    no meaningful per-engine frame for a malformed plan or an ambiguous input
    relation.  Once the relation has passed that common compiler gate, this
    function materializes exactly one fresh Store and always returns all three
    frames in ``native, souffle, problog`` order.  Missing adapter/CLI
    capability is ``unsupported``; an adapter or output failure is ``failed``.

    This deliberately does *not* compare rows or raise because a frame did not
    succeed.  It is intended for an assessment layer which needs to report a
    complete engine inventory.  ``execute_portable_deterministic_v1`` remains
    the all-success, parity-checked API and retains its existing fail-closed
    behavior.
    """

    validated = _validate_input(
        plan,
        schema_ir=schema_ir,
        effective_relations=effective_relations,
    )
    # Every engine receives this same fresh Store instance.  It is already
    # detached from the caller and no engine can fall back to a live Store.
    store = _materialize_store(validated)
    frames = tuple(
        _observe_portable_engine_v1(
            engine,
            validated=validated,
            store=store,
        )
        for engine in _PORTABLE_ENGINES
    )
    return PortableEvaluationObservationV1(
        profile=PORTABLE_DETERMINISTIC_V1,
        contract=validated.contract,
        frames=frames,
    )


def execute_portable_deterministic_v1(
    plan: CompiledDerivationPlan,
    *,
    schema_ir: dict[str, Any],
    effective_relations: Mapping[str, Sequence[ProjectedFact]],
) -> PortableEvaluationResultV1:
    """Run Native, Soufflé, and ProbLog on one isolated effective relation.

    All three engines must return the same canonical selected-row set.  A
    mismatch is a fail-closed error rather than a weak "best effort" result.
    This function imports the registered adapters locally and then calls the
    existing ``evaluate_derivation_plans`` seam for each engine.
    """

    validated = _validate_input(
        plan,
        schema_ir=schema_ir,
        effective_relations=effective_relations,
    )
    store = _materialize_store(validated)
    _register_portable_adapters()

    executions: list[PortableEngineEvaluationV1] = []
    for engine in _PORTABLE_ENGINES:
        try:
            branch_outputs = _execute_portable_branch_plans(
                engine, validated=validated, store=store
            )
        except PortableEvaluationError:
            raise
        except Exception as exc:  # adapter implementation/binary errors are fail-closed.
            raise PortableEvaluationError(
                f"portable execution failed for engine {engine!r}",
                code="PORTABLE_ENGINE_EXECUTION_FAILED",
                details={"engine": engine, "cause_type": type(exc).__name__},
            ) from exc
        executions.append(_normalize_engine_outputs(engine, branch_outputs, validated.contract))

    digests = {item.selected_row_set_digest for item in executions}
    if len(digests) != 1:
        raise PortableEvaluationError(
            "portable engines produced different selected-row sets",
            code="PORTABLE_ENGINE_RESULT_MISMATCH",
            details={item.engine: item.selected_row_set_digest for item in executions},
        )
    return PortableEvaluationResultV1(
        profile=PORTABLE_DETERMINISTIC_V1,
        executions=tuple(executions),
        selected_row_set_digest=executions[0].selected_row_set_digest,
    )


def execute_native_deterministic_v1(
    plan: CompiledDerivationPlan,
    *,
    schema_ir: dict[str, Any],
    effective_relations: Mapping[str, Sequence[ProjectedFact]],
) -> PortableEngineEvaluationV1:
    """Run the same sealed positive profile through Native only.

    This is deliberately not a shortcut back to the caller's live ``Store``.
    Native-only execution still consumes the exact materialized relation and
    still applies the portable-profile compiler gate, which gives the V1
    Query/Scenario path one evaluator shape.  It simply makes no claim about
    Soufflé/ProbLog parity; callers record that as ``not_requested``.
    """

    validated = _validate_input(
        plan,
        schema_ir=schema_ir,
        effective_relations=effective_relations,
    )
    store = _materialize_store(validated)
    try:
        branch_outputs = _execute_portable_branch_plans("native", validated=validated, store=store)
    except Exception as exc:
        raise PortableEvaluationError(
            "native deterministic execution failed",
            code="NATIVE_ENGINE_EXECUTION_FAILED",
            details={"cause_type": type(exc).__name__},
        ) from exc
    return _normalize_engine_outputs("native", branch_outputs, validated.contract)


@dataclass(frozen=True)
class _ValidatedPortableInput:
    plan: CompiledDerivationPlan
    execution_branches: tuple["_PortableExecutionBranch", ...]  # noqa: UP037 - Preserve Python 3.10 runtime hint shape.
    schema_ir: dict[str, Any]
    relations: Mapping[str, tuple[ProjectedFact, ...]]
    contract: PortableExecutionContractV1


@dataclass(frozen=True)
class _PortableExecutionBranch:
    """One branch-local adapter plan plus its exact output normalization shape.

    Soufflé's support capture needs every variable in a predicate witness to
    be present in its query head.  Keeping this widening *inside* each DNF
    branch avoids inventing a value for an alias that exists only on another
    ``PolicyAny`` arm.  The public result continues to expose only the shared
    selected head prefix.
    """

    branch_index: int
    plan: CompiledDerivationPlan
    execution_head_var_names: tuple[str, ...]
    execution_value_types: tuple[str, ...]


class _PortableEvaluationLedger(Ledger):
    """A local ledger whose Soufflé witness reconstruction stays relation-only.

    The Soufflé adapter can reconstruct rich support rows by fetching the
    original claim behind each witness id.  In this profile assertion ids are
    intentionally not portable (the isolated ledger created fresh ids), while
    the public result deliberately excludes proof parity.  Returning ``None``
    from that optional lookup makes the existing adapter reconstruct its
    witness from the already-grounded query relation instead.  All ordinary
    ledger reads and writes remain inherited from ``Ledger``.
    """

    def get_claim(self, asrt_id: str) -> Claim | None:
        del asrt_id
        return None


def _validate_input(
    plan: CompiledDerivationPlan,
    *,
    schema_ir: dict[str, Any],
    effective_relations: Mapping[str, Sequence[ProjectedFact]],
) -> _ValidatedPortableInput:
    if not isinstance(plan, CompiledDerivationPlan):
        raise PortableEvaluationError(
            "plan must be CompiledDerivationPlan",
            code="PORTABLE_PLAN_TYPE_INVALID",
        )
    if not isinstance(schema_ir, dict):
        raise PortableEvaluationError(
            "schema_ir must be a schema dict",
            code="PORTABLE_SCHEMA_INVALID",
        )
    try:
        schema = ensure_schema_ir(schema_ir)
    except Exception as exc:
        raise PortableEvaluationError(
            "schema_ir is not a valid FactGraph schema",
            code="PORTABLE_SCHEMA_INVALID",
            details={"cause_type": type(exc).__name__},
        ) from exc
    _validate_plan_shape(plan, schema)
    dependencies, variable_types = _validate_positive_body(plan, schema)
    dependencies = _expand_virtual_entity_dependencies(dependencies, schema=schema)
    execution_branches = _build_portable_execution_branches(
        plan,
        schema=schema,
        selected_head_var_names=plan.heads[0].head_var_names,
    )
    relations = _normalize_relations(
        schema,
        dependency_predicate_ids=dependencies,
        effective_relations=effective_relations,
    )
    selected_head_var_names = plan.heads[0].head_var_names
    execution_head_var_names = (
        *selected_head_var_names,
        *tuple(sorted(name for name in variable_types if name not in set(selected_head_var_names))),
    )
    return _ValidatedPortableInput(
        plan=plan,
        execution_branches=execution_branches,
        schema_ir=schema,
        relations=relations,
        contract=PortableExecutionContractV1(
            profile=PORTABLE_DETERMINISTIC_V1,
            dependency_predicate_ids=dependencies,
            selected_head_var_names=selected_head_var_names,
            selected_value_types=tuple(variable_types[name] for name in selected_head_var_names),
            execution_head_var_names=execution_head_var_names,
            execution_value_types=tuple(variable_types[name] for name in execution_head_var_names),
            execution_branch_head_var_names=tuple(
                item.execution_head_var_names for item in execution_branches
            ),
            execution_branch_value_types=tuple(
                item.execution_value_types for item in execution_branches
            ),
        ),
    )


def _validate_plan_shape(plan: CompiledDerivationPlan, schema: Mapping[str, Any]) -> None:
    if len(plan.heads) != 1:
        raise PortableEvaluationError(
            "portable execution requires exactly one projection head",
            code="PORTABLE_MULTI_HEAD_UNSUPPORTED",
        )
    head = plan.heads[0]
    if plan.head_spec is not None:
        raise PortableEvaluationError(
            "portable execution does not support an entity or custom head_spec",
            code="PORTABLE_HEAD_SPEC_UNSUPPORTED",
        )
    if plan.engine_ext is not None or plan.engine_options:
        raise PortableEvaluationError(
            "portable execution rejects engine extensions and engine configuration",
            code="PORTABLE_ENGINE_CONFIGURATION_UNSUPPORTED",
        )
    if plan.body_confidence is not None:
        raise PortableEvaluationError(
            "portable execution rejects confidence/probabilistic body semantics",
            code="PORTABLE_SEMANTICS_UNSUPPORTED",
        )
    if not head.head_var_names or len(set(head.head_var_names)) != len(head.head_var_names):
        raise PortableEvaluationError(
            "portable projection head variables must be non-empty and unique",
            code="PORTABLE_HEAD_VARS_INVALID",
        )
    if any(not name.startswith("$") for name in head.head_var_names):
        raise PortableEvaluationError(
            "portable projection head variables must use '$' names",
            code="PORTABLE_HEAD_VARS_INVALID",
        )
    schema_predicate_ids = {
        item.get("pred_id")
        for item in schema.get("predicates", [])
        if isinstance(item, dict) and isinstance(item.get("pred_id"), str)
    }
    if head.target_pred_id in schema_predicate_ids:
        raise PortableEvaluationError(
            "portable execution requires a query-style target outside the schema namespace",
            code="PORTABLE_SCHEMA_HEAD_UNSUPPORTED",
        )


def _validate_positive_body(
    plan: CompiledDerivationPlan,
    schema: Mapping[str, Any],
) -> tuple[tuple[str, ...], dict[str, str]]:
    try:
        expression = parse_where_ir_to_ast(plan.body_ir)
    except (TypeError, ValueError, WhereASTError) as exc:
        raise PortableEvaluationError(
            "portable plan has invalid where IR",
            code="PORTABLE_WHERE_INVALID",
            details={"cause_type": type(exc).__name__},
        ) from exc

    schema_predicate_ids = {
        item.get("pred_id")
        for item in schema.get("predicates", [])
        if isinstance(item, dict) and isinstance(item.get("pred_id"), str)
    }
    dependencies: set[str] = set()
    mentioned_variables: set[str] = set()
    variable_types: dict[str, str] = {}
    equality_edges: list[tuple[str, str]] = []
    predicate_types = {
        item["pred_id"]: tuple(arg["type_domain"] for arg in item["arg_specs"])
        for item in schema["predicates"]
        if isinstance(item, dict)
        and isinstance(item.get("pred_id"), str)
        and isinstance(item.get("arg_specs"), list)
        and all(
            isinstance(arg, dict) and isinstance(arg.get("type_domain"), str)
            for arg in item["arg_specs"]
        )
    }
    branches = _walk_branches(expression)
    for branch in branches:
        for atom in branch:
            if isinstance(atom, PredAtom):
                if atom.pred_id not in schema_predicate_ids:
                    raise PortableEvaluationError(
                        "portable plan references a predicate outside the trusted schema",
                        code="PORTABLE_UNKNOWN_PREDICATE",
                        details={"predicate_id": atom.pred_id},
                    )
                if atom.pred_id == plan.heads[0].target_pred_id:
                    raise PortableEvaluationError(
                        "portable plan directly recurses through its projection target",
                        code="PORTABLE_RECURSION_UNSUPPORTED",
                    )
                dependencies.add(atom.pred_id)
                expected_types = predicate_types.get(atom.pred_id)
                if expected_types is None or len(atom.terms) != len(expected_types):
                    raise PortableEvaluationError(
                        "portable predicate atom does not match the trusted schema arity",
                        code="PORTABLE_PREDICATE_ARITY_INVALID",
                        details={
                            "predicate_id": atom.pred_id,
                            "expected_arity": 0 if expected_types is None else len(expected_types),
                            "actual_arity": len(atom.terms),
                        },
                    )
                mentioned_variables.update(
                    term.name for term in atom.terms if isinstance(term, Var)
                )
                _validate_portable_terms(atom.terms)
                for type_domain, term in zip(expected_types, atom.terms, strict=True):
                    if not isinstance(term, Var):
                        continue
                    prior = variable_types.setdefault(term.name, type_domain)
                    if prior != type_domain:
                        raise PortableEvaluationError(
                            "portable variable is assigned incompatible schema type domains",
                            code="PORTABLE_VARIABLE_TYPE_AMBIGUOUS",
                            details={"variable": term.name, "left": prior, "right": type_domain},
                        )
                continue
            if isinstance(atom, CmpAtom):
                _validate_portable_terms((atom.lhs, atom.rhs))
                mentioned_variables.update(
                    term.name for term in (atom.lhs, atom.rhs) if isinstance(term, Var)
                )
                if atom.op == "eq" and isinstance(atom.lhs, Var) and isinstance(atom.rhs, Var):
                    equality_edges.append((atom.lhs.name, atom.rhs.name))
                continue
            if isinstance(atom, NotAtom):
                raise PortableEvaluationError(
                    "portable deterministic v1 does not define closed-world negation",
                    code="PORTABLE_NEGATION_UNSUPPORTED",
                )
            if isinstance(atom, RuleRefAtom):
                raise PortableEvaluationError(
                    "portable deterministic v1 rejects rule references and recursion",
                    code="PORTABLE_RULE_REFERENCE_UNSUPPORTED",
                )
            if isinstance(atom, AggregateAtom):
                raise PortableEvaluationError(
                    "portable deterministic v1 rejects aggregate semantics",
                    code="PORTABLE_AGGREGATE_UNSUPPORTED",
                )
            if isinstance(atom, BuiltinAtom):
                raise PortableEvaluationError(
                    "portable deterministic v1 rejects builtin/code semantics",
                    code="PORTABLE_BUILTIN_UNSUPPORTED",
                )
            if isinstance(atom, InAtom):
                raise PortableEvaluationError(
                    "portable deterministic v1 rejects membership shorthand",
                    code="PORTABLE_ATOM_UNSUPPORTED",
                    details={"atom_type": "InAtom"},
                )
            raise PortableEvaluationError(
                "portable deterministic v1 encountered an unsupported atom",
                code="PORTABLE_ATOM_UNSUPPORTED",
                details={"atom_type": type(atom).__name__},
            )

    _propagate_equality_type_domains(variable_types, equality_edges)
    unresolved_variables = sorted(mentioned_variables - set(variable_types))
    if unresolved_variables:
        raise PortableEvaluationError(
            "portable plan contains a variable without a schema type source",
            code="PORTABLE_VARIABLE_TYPE_UNRESOLVED",
            details={"variables": unresolved_variables},
        )
    # Only public projection variables need a value in *every* DNF branch.
    # Query compilation independently proves that every public bind/select is
    # branch-total before it emits this plan.  Compiler-local occurrence vars
    # may legitimately differ between PolicyAny arms; widening them globally
    # would create an impossible synthetic head for Soufflé witness capture.
    _validate_branch_total_variables(
        branches,
        predicate_types=predicate_types,
        required_variables=plan.heads[0].head_var_names,
    )
    head_variables = set(plan.heads[0].head_var_names)
    if not head_variables <= set(variable_types):
        raise PortableEvaluationError(
            "portable projection head contains a variable without a schema type source",
            code="PORTABLE_UNBOUND_HEAD_VARIABLE",
            details={"unbound": sorted(head_variables - set(variable_types))},
        )
    if not dependencies:
        raise PortableEvaluationError(
            "portable execution requires at least one predicate dependency",
            code="PORTABLE_EMPTY_DEPENDENCY_SET",
        )
    ordered_head_variables = plan.heads[0].head_var_names
    missing_types = [name for name in ordered_head_variables if name not in variable_types]
    if missing_types:
        raise PortableEvaluationError(
            "portable projection head variable has no schema type source",
            code="PORTABLE_HEAD_TYPE_UNRESOLVED",
            details={"variables": missing_types},
        )
    return tuple(sorted(dependencies)), dict(variable_types)


def _propagate_equality_type_domains(
    variable_types: dict[str, str],
    equality_edges: Sequence[tuple[str, str]],
) -> None:
    """Propagate schema types through compiler-generated ``eq`` head links."""

    pending = list(equality_edges)
    while pending:
        next_pending: list[tuple[str, str]] = []
        made_progress = False
        for left, right in pending:
            left_type, right_type = variable_types.get(left), variable_types.get(right)
            if left_type is not None and right_type is not None:
                if left_type != right_type:
                    raise PortableEvaluationError(
                        "portable equality links incompatible schema type domains",
                        code="PORTABLE_VARIABLE_TYPE_AMBIGUOUS",
                        details={
                            "left": left,
                            "left_type": left_type,
                            "right": right,
                            "right_type": right_type,
                        },
                    )
                continue
            if left_type is not None:
                variable_types[right] = left_type
                made_progress = True
                continue
            if right_type is not None:
                variable_types[left] = right_type
                made_progress = True
                continue
            next_pending.append((left, right))
        if not made_progress:
            return
        pending = next_pending


def _walk_branches(expression: object) -> tuple[tuple[object, ...], ...]:
    # ``parse_where_ir_to_ast`` validates the outer tree, so keep the walk small
    # and explicit rather than permitting arbitrary objects through recursion.
    branches = getattr(expression, "branches", None)
    if isinstance(branches, list):
        return tuple(tuple(branch.atoms) for branch in branches)
    atoms = getattr(expression, "atoms", None)
    if isinstance(atoms, list):
        return (tuple(atoms),)
    raise PortableEvaluationError(
        "portable plan has an unsupported where expression",
        code="PORTABLE_WHERE_INVALID",
    )


def _validate_branch_total_variables(
    branches: Sequence[Sequence[object]],
    *,
    predicate_types: Mapping[str, tuple[str, ...]],
    required_variables: tuple[str, ...],
) -> None:
    """Require every public projection variable to be typed in every branch.

    A branch-private occurrence variable is not a public query value.  It is
    widened only in that branch's temporary adapter head, where it is known to
    be bound and can support Soufflé's relation-local witness capture.  This
    helper therefore deliberately validates the shared projection head rather
    than a global union of all hidden compiler variables.
    """

    required = set(required_variables)
    for branch_index, branch in enumerate(branches):
        branch_types = _branch_variable_types(
            branch,
            predicate_types=predicate_types,
            branch_index=branch_index,
        )
        missing = sorted(required - set(branch_types))
        if missing:
            raise PortableEvaluationError(
                "portable OR branch does not bind every execution variable",
                code="PORTABLE_PARTIAL_BRANCH_VARIABLE",
                details={"branch": branch_index, "variables": missing},
            )


def _branch_variable_types(
    branch: Sequence[object],
    *,
    predicate_types: Mapping[str, tuple[str, ...]],
    branch_index: int,
) -> dict[str, str]:
    """Return only the schema-resolved variables used by one DNF branch.

    The positive-profile gate has already validated the atom union.  Keeping
    the branch-local proof here still matters: an OR arm may not borrow a type
    source from a different arm, because its temporary execution head must be
    entirely bound by this arm.
    """

    branch_types: dict[str, str] = {}
    equality_edges: list[tuple[str, str]] = []
    mentioned: set[str] = set()
    for atom in branch:
        if isinstance(atom, PredAtom):
            for type_domain, term in zip(predicate_types[atom.pred_id], atom.terms, strict=True):
                if isinstance(term, Var):
                    mentioned.add(term.name)
                    prior = branch_types.setdefault(term.name, type_domain)
                    if prior != type_domain:
                        raise PortableEvaluationError(
                            "portable variable is assigned incompatible branch type domains",
                            code="PORTABLE_VARIABLE_TYPE_AMBIGUOUS",
                            details={"branch": branch_index, "variable": term.name},
                        )
        elif isinstance(atom, CmpAtom):
            if isinstance(atom.lhs, Var):
                mentioned.add(atom.lhs.name)
            if isinstance(atom.rhs, Var):
                mentioned.add(atom.rhs.name)
            if atom.op == "eq" and isinstance(atom.lhs, Var) and isinstance(atom.rhs, Var):
                equality_edges.append((atom.lhs.name, atom.rhs.name))
    _propagate_equality_type_domains(branch_types, equality_edges)
    unresolved = sorted(mentioned - set(branch_types))
    if unresolved:
        raise PortableEvaluationError(
            "portable branch contains a variable without a local schema type source",
            code="PORTABLE_VARIABLE_TYPE_UNRESOLVED",
            details={"branch": branch_index, "variables": unresolved},
        )
    return branch_types


def _build_portable_execution_branches(
    plan: CompiledDerivationPlan,
    *,
    schema: Mapping[str, Any],
    selected_head_var_names: tuple[str, ...],
) -> tuple[_PortableExecutionBranch, ...]:
    """Compile one branch-local widened head per validated positive DNF arm.

    ``evaluate_derivation_plans`` cannot ask Soufflé to reconstruct a witness
    for an unprojected predicate variable.  Executing each DNF arm separately
    is semantically the same finite OR for this positive, set-normalized
    profile, while avoiding a cross-arm "missing value" convention.  The
    caller later unions only the selected public head prefix.
    """

    try:
        expression = parse_where_ir_to_ast(plan.body_ir)
    except (TypeError, ValueError, WhereASTError) as exc:  # pragma: no cover - validated first.
        raise PortableEvaluationError(
            "portable plan has invalid where IR",
            code="PORTABLE_WHERE_INVALID",
            details={"cause_type": type(exc).__name__},
        ) from exc
    ast_branches = _walk_branches(expression)
    body_branches = _where_ir_branches(plan.body_ir)
    if len(ast_branches) != len(body_branches):  # pragma: no cover - parser shape invariant.
        raise PortableEvaluationError(
            "portable where branch structure changed during validation",
            code="PORTABLE_WHERE_INVALID",
        )
    predicate_types = _predicate_type_domains(schema)
    branches: list[_PortableExecutionBranch] = []
    selected = set(selected_head_var_names)
    for branch_index, (ast_branch, body_ir) in enumerate(
        zip(ast_branches, body_branches, strict=True)
    ):
        branch_types = _branch_variable_types(
            ast_branch,
            predicate_types=predicate_types,
            branch_index=branch_index,
        )
        missing = sorted(selected - set(branch_types))
        if missing:
            raise PortableEvaluationError(
                "portable OR branch does not bind every public projection variable",
                code="PORTABLE_PARTIAL_BRANCH_VARIABLE",
                details={"branch": branch_index, "variables": missing},
            )
        execution_head_var_names = (
            *selected_head_var_names,
            *tuple(sorted(name for name in branch_types if name not in selected)),
        )
        branches.append(
            _PortableExecutionBranch(
                branch_index=branch_index,
                plan=replace(
                    plan,
                    body_ir=list(body_ir),
                    heads=(
                        CompiledHeadCall(
                            target_pred_id=plan.heads[0].target_pred_id,
                            head_var_names=execution_head_var_names,
                        ),
                    ),
                ),
                execution_head_var_names=execution_head_var_names,
                execution_value_types=tuple(
                    branch_types[name] for name in execution_head_var_names
                ),
            )
        )
    return tuple(branches)


def _where_ir_branches(body_ir: Sequence[object]) -> tuple[tuple[object, ...], ...]:
    """Preserve the validated source IR while splitting its outer DNF only."""

    if body_ir and all(isinstance(item, tuple) for item in body_ir):
        return (tuple(body_ir),)
    if body_ir:
        branches: list[tuple[object, ...]] = []
        for item in body_ir:
            if not isinstance(item, list):
                break
            branches.append(tuple(item))
        else:
            return tuple(branches)
    raise PortableEvaluationError(
        "portable plan has an unsupported where expression",
        code="PORTABLE_WHERE_INVALID",
    )


def _predicate_type_domains(schema: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    return {
        item["pred_id"]: tuple(arg["type_domain"] for arg in item["arg_specs"])
        for item in schema["predicates"]
        if isinstance(item, dict)
        and isinstance(item.get("pred_id"), str)
        and isinstance(item.get("arg_specs"), list)
        and all(
            isinstance(arg, dict) and isinstance(arg.get("type_domain"), str)
            for arg in item["arg_specs"]
        )
    }


def _validate_portable_terms(terms: Sequence[Term]) -> None:
    for term in terms:
        if isinstance(term, Var):
            continue
        # ``Const`` is intentionally accepted without a separate Python-type
        # gate.  The schema-specific relation normalizer below remains the
        # authority for stored values, while adapters validate comparator types.
        if isinstance(term, Const):
            continue
        if isinstance(term, AggregateAtom):
            raise PortableEvaluationError(
                "portable deterministic v1 rejects aggregate terms",
                code="PORTABLE_AGGREGATE_UNSUPPORTED",
            )
        raise PortableEvaluationError(
            "portable deterministic v1 encountered an unsupported term",
            code="PORTABLE_TERM_UNSUPPORTED",
            details={"term_type": type(term).__name__},
        )


def _normalize_relations(
    schema: Mapping[str, Any],
    *,
    dependency_predicate_ids: tuple[str, ...],
    effective_relations: Mapping[str, Sequence[ProjectedFact]],
) -> Mapping[str, tuple[ProjectedFact, ...]]:
    if not isinstance(effective_relations, Mapping):
        raise PortableEvaluationError(
            "effective_relations must be a mapping",
            code="PORTABLE_RELATION_MAPPING_INVALID",
        )
    expected = set(dependency_predicate_ids)
    actual = set(effective_relations)
    if actual != expected:
        raise PortableEvaluationError(
            "portable relation inventory must exactly cover plan dependencies",
            code="PORTABLE_RELATION_INVENTORY_MISMATCH",
            details={
                "missing": sorted(expected - actual),
                "unexpected": sorted(actual - expected),
            },
        )
    predicate_specs = {
        str(item["pred_id"]): tuple(str(arg["type_domain"]) for arg in item["arg_specs"])
        for item in schema["predicates"]
        if isinstance(item, dict)
        and isinstance(item.get("pred_id"), str)
        and isinstance(item.get("arg_specs"), list)
    }
    relation: dict[str, tuple[ProjectedFact, ...]] = {}
    seen_asrt_ids: set[str] = set()
    for predicate_id in dependency_predicate_ids:
        specs = predicate_specs.get(predicate_id)
        if specs is None or not specs or specs[0] != "entity_ref":
            raise PortableEvaluationError(
                "portable relation predicate must use an entity_ref first argument",
                code="PORTABLE_PREDICATE_CONTRACT_UNSUPPORTED",
                details={"predicate_id": predicate_id},
            )
        raw_rows = effective_relations[predicate_id]
        if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes, bytearray)):
            raise PortableEvaluationError(
                "portable relation rows must be a sequence",
                code="PORTABLE_RELATION_ROWS_INVALID",
                details={"predicate_id": predicate_id},
            )
        normalized_rows: list[ProjectedFact] = []
        for row in raw_rows:
            if not isinstance(row, ProjectedFact) or len(row.fact_tuple) != len(specs):
                raise PortableEvaluationError(
                    "portable relation row does not match predicate arity",
                    code="PORTABLE_RELATION_ROW_INVALID",
                    details={"predicate_id": predicate_id},
                )
            if row.asrt_id in seen_asrt_ids:
                raise PortableEvaluationError(
                    "portable effective relation reuses an assertion witness id",
                    code="PORTABLE_DUPLICATE_ASSERTION_WITNESS",
                    details={"asrt_id": row.asrt_id},
                )
            seen_asrt_ids.add(row.asrt_id)
            e_ref = _canonical_value("entity_ref", row.fact_tuple[0])
            values = tuple(
                _canonical_value(tag, value)
                for tag, value in zip(specs[1:], row.fact_tuple[1:], strict=True)
            )
            normalized_rows.append(ProjectedFact(row.asrt_id, (e_ref, *values)))
        relation[predicate_id] = tuple(
            sorted(
                normalized_rows,
                key=lambda item: (
                    _canonical_relation_tuple_bytes(specs, item.fact_tuple),
                    item.asrt_id,
                ),
            )
        )
    return relation


def _canonical_value(tag: str, value: object) -> object:
    try:
        rows = claim_args_from_rest_terms([(tag, value)])
    except (TypeError, ValueError) as exc:
        raise PortableEvaluationError(
            "portable relation contains a non-canonical value",
            code="PORTABLE_RELATION_VALUE_INVALID",
            details={"tag": tag, "cause_type": type(exc).__name__},
        ) from exc
    if len(rows) != 1 or rows[0][2] != tag:
        raise PortableEvaluationError(
            "portable relation value did not preserve its declared type domain",
            code="PORTABLE_RELATION_VALUE_INVALID",
            details={"tag": tag},
        )
    return rows[0][1]


def _canonical_relation_tuple_bytes(
    specs: tuple[str, ...],
    values: tuple[object, ...],
) -> bytes:
    return canonical_bytes_tup_v1(list(zip(specs, values, strict=True)))


def _materialize_store(validated: _ValidatedPortableInput) -> Store:
    store = Store(validated.schema_ir, ledger=_PortableEvaluationLedger())
    predicate_specs = {
        str(item["pred_id"]): tuple(str(arg["type_domain"]) for arg in item["arg_specs"])
        for item in validated.schema_ir["predicates"]
        if isinstance(item, dict)
        and isinstance(item.get("pred_id"), str)
        and isinstance(item.get("arg_specs"), list)
    }
    virtual_exists_predicates = {
        str(item["pred_id"])
        for item in validated.schema_ir["predicates"]
        if isinstance(item, dict)
        and isinstance(item.get("pred_id"), str)
        and item.get("is_entity_exists") is True
    }
    for predicate_id in validated.contract.dependency_predicate_ids:
        if predicate_id in virtual_exists_predicates:
            # The complete Identity bundle in the same sealed relation is the
            # sole authority.  Store view projection rematerializes :exists.
            continue
        specs = predicate_specs[predicate_id]
        # The stable sort above avoids giving ledger append order any semantic
        # role.  ``set_field`` intentionally creates fresh local assertion ids.
        for row in validated.relations[predicate_id]:
            set_field(
                store.ledger,
                predicate_id,
                row.fact_tuple[0],  # type: ignore[arg-type]
                list(zip(specs[1:], row.fact_tuple[1:], strict=True)),
            )
    return store


def _register_portable_adapters() -> None:
    try:
        importlib.import_module("factgraph.adapters.souffle")
        importlib.import_module("factgraph.adapters.problog")
    except Exception as exc:
        raise PortableEvaluationError(
            "portable execution could not register a required adapter",
            code="PORTABLE_ENGINE_UNAVAILABLE",
            details={"cause_type": type(exc).__name__},
        ) from exc


def _observe_portable_engine_v1(
    engine: PortableEngineV1,
    *,
    validated: _ValidatedPortableInput,
    store: Store,
) -> PortableEngineObservationFrameV1:
    """Return one terminal frame without allowing one adapter to hide another."""

    try:
        _assert_portable_engine_available_v1(engine)
    except Exception as exc:
        return _engine_observation_failure_frame_v1(
            engine,
            exc,
            status=_observation_status_for_exception_v1(exc),
        )
    try:
        branch_outputs = _execute_portable_branch_plans(engine, validated=validated, store=store)
        evaluation = _normalize_engine_outputs(engine, branch_outputs, validated.contract)
    except Exception as exc:
        return _engine_observation_failure_frame_v1(
            engine,
            exc,
            status=_observation_status_for_exception_v1(exc),
        )
    return PortableEngineObservationFrameV1(
        engine=engine,
        status="succeeded",
        evaluation=evaluation,
    )


def _execute_portable_branch_plans(
    engine: PortableEngineV1,
    *,
    validated: _ValidatedPortableInput,
    store: Store,
) -> tuple[tuple[_PortableExecutionBranch, tuple[DerivationOutput, ...]], ...]:
    """Execute each independently valid DNF branch on the same detached Store.

    This is not an adapter fallback and does not choose a preferred branch.
    Every configured engine receives every branch.  A caller only sees the
    set-union of the public selected tuples after all branch frames normalize;
    any adapter exception aborts the enclosing engine frame/result.
    """

    outputs: list[tuple[_PortableExecutionBranch, tuple[DerivationOutput, ...]]] = []
    for branch in validated.execution_branches:
        branch_outputs = evaluate_derivation_plans(
            DerivationEvaluateRequest(plans=(branch.plan,), engine=engine),
            store=store,
        )
        outputs.append((branch, tuple(branch_outputs)))
    return tuple(outputs)


def _assert_portable_engine_available_v1(engine: PortableEngineV1) -> None:
    """Preflight only absence-of-capability; execution defects remain failures."""

    if engine == "native":
        return
    module_name = f"factgraph.adapters.{engine}"
    try:
        importlib.import_module(module_name)
    except (ImportError, ModuleNotFoundError) as exc:
        raise PortableEvaluationError(
            "portable engine adapter is not importable",
            code="PORTABLE_ENGINE_UNAVAILABLE",
            details={"engine": engine, "component": "adapter"},
        ) from exc
    if engine == "souffle":
        from factgraph.adapters.souffle.runner import find_souffle_binary

        if find_souffle_binary() is None:
            raise PortableEvaluationError(
                "Souffle CLI is not available",
                code="PORTABLE_ENGINE_UNAVAILABLE",
                details={"engine": engine, "component": "souffle_cli"},
            )
        return
    if engine == "problog":
        binary_name = os.getenv("PROBLOG_BIN", "problog")
        if shutil.which(binary_name) is None:
            raise PortableEvaluationError(
                "ProbLog CLI is not available",
                code="PORTABLE_ENGINE_UNAVAILABLE",
                details={"engine": engine, "component": "problog_cli"},
            )
        return
    raise AssertionError(f"unreachable portable engine {engine!r}")


def _observation_status_for_exception_v1(
    exc: Exception,
) -> PortableEngineFrameStatusV1:
    """Classify only capability absence as unsupported, never a weak success."""

    if isinstance(exc, PortableEvaluationError) and exc.code == "PORTABLE_ENGINE_UNAVAILABLE":
        return "unsupported"
    # An adapter can import a transitive optional dependency lazily, after the
    # explicit preflight.  That remains an unavailable capability rather than
    # an execution result.  Other exceptions -- including an unexpected missing
    # intermediate artifact -- are failures after a capability was declared.
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return "unsupported"
    return "failed"


def _engine_observation_failure_frame_v1(
    engine: PortableEngineV1,
    exc: Exception,
    *,
    status: PortableEngineFrameStatusV1,
) -> PortableEngineObservationFrameV1:
    if status not in {"failed", "unsupported"}:
        raise AssertionError(f"observation failure has invalid status {status!r}")
    diagnostic = _portable_engine_diagnostic_v1(
        engine,
        exc,
        status=status,
    )
    return PortableEngineObservationFrameV1(
        engine=engine,
        status=status,
        diagnostic=diagnostic,
    )


def _portable_engine_diagnostic_v1(
    engine: PortableEngineV1,
    exc: Exception,
    *,
    status: PortableEngineFrameStatusV1,
) -> PortableEngineDiagnosticV1:
    """Project an exception to a stable, host-independent diagnostic value."""

    if isinstance(exc, PortableEvaluationError):
        code = exc.code
        details: dict[str, object] = dict(exc.details)
    elif status == "unsupported":
        code = "PORTABLE_ENGINE_UNAVAILABLE"
        details = {}
    else:
        code = "PORTABLE_ENGINE_EXECUTION_FAILED"
        details = {}
    # Never retain ``str(exc)``: both adapter commands and temporary package
    # paths are intentionally absent from portable observation material.
    details["engine"] = engine
    details["cause_type"] = type(exc).__name__
    return PortableEngineDiagnosticV1(
        code=code,
        details_json=_canonical_diagnostic_json(details),
    )


def _canonical_diagnostic_json(value: object) -> str:
    """Canonicalize bounded diagnostic data without serializing opaque objects."""

    normalized = _normalize_diagnostic_value_v1(value, active_ids=set())
    try:
        return json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise PortableEvaluationError(
            "portable diagnostic details cannot be canonically represented",
            code="PORTABLE_OBSERVATION_DIAGNOSTIC_INVALID",
        ) from exc


def _normalize_diagnostic_value_v1(value: object, *, active_ids: set[int]) -> object:
    """Keep stable scalar/container information, discard unstable opaque reprs."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return {"$type": "float", "finite": False}
    if isinstance(value, bytes):
        return {"$type": "bytes", "length": len(value)}
    value_id = id(value)
    if isinstance(value, Mapping):
        if value_id in active_ids:
            return {"$type": type(value).__name__, "cycle": True}
        if not all(isinstance(key, str) for key in value):
            return {
                "$type": type(value).__name__,
                "unsupported_key_types": sorted({type(key).__name__ for key in value}),
            }
        active_ids.add(value_id)
        try:
            return {
                key: _normalize_diagnostic_value_v1(item, active_ids=active_ids)
                for key, item in sorted(value.items())
            }
        finally:
            active_ids.remove(value_id)
    if isinstance(value, (list, tuple)):
        if value_id in active_ids:
            return {"$type": type(value).__name__, "cycle": True}
        active_ids.add(value_id)
        try:
            return [_normalize_diagnostic_value_v1(item, active_ids=active_ids) for item in value]
        finally:
            active_ids.remove(value_id)
    return {"$type": type(value).__name__}


def _portable_execution_contract_digest_v1(contract: PortableExecutionContractV1) -> str:
    """Return a digest of the exact static profile used by an observation."""

    payload = {
        "profile": contract.profile,
        "dependency_predicate_ids": list(contract.dependency_predicate_ids),
        "selected_head_var_names": list(contract.selected_head_var_names),
        "selected_value_types": list(contract.selected_value_types),
        "execution_head_var_names": list(contract.execution_head_var_names),
        "execution_value_types": list(contract.execution_value_types),
        "execution_branch_head_var_names": [
            list(item) for item in contract.execution_branch_head_var_names
        ],
        "execution_branch_value_types": [
            list(item) for item in contract.execution_branch_value_types
        ],
    }
    return _framed_digest(
        "portable_execution_contract_v1",
        (_canonical_diagnostic_json(payload).encode("utf-8"),),
    )


def _normalize_engine_outputs(
    engine: PortableEngineV1,
    branch_outputs: Sequence[tuple[_PortableExecutionBranch, Sequence[DerivationOutput]]],
    contract: PortableExecutionContractV1,
) -> PortableEngineEvaluationV1:
    rows_by_bytes: dict[bytes, PortableSelectedRowV1] = {}
    for branch, outputs in branch_outputs:
        for output in outputs:
            if not _is_deterministically_true_output(output):
                continue
            row = _selected_row_from_output(output, branch=branch, contract=contract)
            canonical = canonical_bytes_tup_v1(list(row.terms))
            rows_by_bytes.setdefault(canonical, row)
    ordered_items = tuple(rows_by_bytes[key] for key in sorted(rows_by_bytes))
    return PortableEngineEvaluationV1(
        engine=engine,
        rows=ordered_items,
        selected_row_set_digest=_selected_row_set_digest(rows_by_bytes),
    )


def _is_deterministically_true_output(output: DerivationOutput) -> bool:
    """Normalize engine absence without admitting probabilistic semantics.

    The current ProbLog adapter emits one syntactic, unbound zero-probability
    output for an empty deterministic query relation.  It is not a selected
    row.  Deterministic facts yield exactly ``1.0``; anything strictly between
    zero and one would be a probabilistic semantic result and is rejected by
    this profile instead of being compared with Native/Soufflé rows.
    """

    if output.confidence_kind == "none":
        if output.confidence is not None:
            raise PortableEvaluationError(
                "portable non-probabilistic output unexpectedly carries confidence",
                code="PORTABLE_OUTPUT_SEMANTICS_INVALID",
            )
        return True
    if output.confidence_kind == "probability":
        if output.confidence == 0.0:
            return False
        if output.confidence == 1.0:
            return True
    raise PortableEvaluationError(
        "portable execution received a non-deterministic engine output",
        code="PORTABLE_OUTPUT_SEMANTICS_INVALID",
        details={
            "confidence_kind": output.confidence_kind,
            "confidence": output.confidence,
        },
    )


def _selected_row_from_output(
    output: DerivationOutput,
    *,
    branch: _PortableExecutionBranch,
    contract: PortableExecutionContractV1,
) -> PortableSelectedRowV1:
    if not isinstance(output, DerivationOutput) or output.candidate_kind != "fact":
        raise PortableEvaluationError(
            "portable engine output is not a query-style fact row",
            code="PORTABLE_OUTPUT_SHAPE_INVALID",
        )
    payload = output.payload
    terms_payload = payload.get("terms") if isinstance(payload, dict) else None
    if not isinstance(terms_payload, list) or len(terms_payload) != len(
        branch.execution_head_var_names
    ):
        raise PortableEvaluationError(
            "portable engine output does not match projection head width",
            code="PORTABLE_OUTPUT_SHAPE_INVALID",
        )
    terms: list[tuple[str, object]] = []
    all_terms: list[tuple[str, object]] = []
    for item, expected_tag in zip(
        terms_payload,
        branch.execution_value_types,
        strict=True,
    ):
        if not isinstance(item, dict):
            raise PortableEvaluationError(
                "portable engine output term is malformed",
                code="PORTABLE_OUTPUT_SHAPE_INVALID",
            )
        kind = item.get("kind")
        actual_tag: object
        value: object
        if kind == "entity_ref":
            actual_tag, value = "entity_ref", item.get("value")
        elif kind == "literal":
            actual_tag, value = item.get("tag"), item.get("value")
        else:
            raise PortableEvaluationError(
                "portable engine output has a non-value projection term",
                code="PORTABLE_OUTPUT_SHAPE_INVALID",
            )
        if not isinstance(actual_tag, str):
            raise PortableEvaluationError(
                "portable engine output term has no type tag",
                code="PORTABLE_OUTPUT_SHAPE_INVALID",
            )
        if expected_tag == "entity_ref" and actual_tag != "entity_ref":
            raise PortableEvaluationError(
                "portable engine output lost an entity-ref projection",
                code="PORTABLE_OUTPUT_TYPE_MISMATCH",
            )
        if expected_tag != "entity_ref" and actual_tag == "entity_ref":
            raise PortableEvaluationError(
                "portable engine output promoted a scalar projection to entity-ref",
                code="PORTABLE_OUTPUT_TYPE_MISMATCH",
            )
        try:
            normalized = coerce_value_for_tag(expected_tag, value)
        except Exception as exc:
            raise PortableEvaluationError(
                "portable engine output cannot be restored to the selected schema type",
                code="PORTABLE_OUTPUT_TYPE_MISMATCH",
                details={"expected_tag": expected_tag, "actual_tag": actual_tag},
            ) from exc
        all_terms.append((expected_tag, _canonical_value(expected_tag, normalized)))
    terms = all_terms[: len(contract.selected_head_var_names)]
    canonical = canonical_bytes_tup_v1(terms)
    return PortableSelectedRowV1(
        terms=tuple(terms),
        row_digest=_framed_digest("portable_selected_row_v1", (canonical,)),
    )


def _selected_row_set_digest(rows_by_bytes: Mapping[bytes, PortableSelectedRowV1]) -> str:
    return _framed_digest("portable_selected_row_set_v1", tuple(sorted(rows_by_bytes)))


def _framed_digest(domain: str, parts: Sequence[bytes]) -> str:
    raw = bytearray(b"factgraph\x00")
    raw.extend(domain.encode("ascii"))
    raw.extend(b"\x00")
    for part in parts:
        raw.extend(len(part).to_bytes(8, "big"))
        raw.extend(part)
    return sha256_token(bytes(raw))


__all__ = [
    "PORTABLE_DETERMINISTIC_V1",
    "PortableEngineDiagnosticV1",
    "PortableEngineEvaluationV1",
    "PortableEngineFrameStatusV1",
    "PortableEngineObservationFrameV1",
    "PortableEvaluationError",
    "PortableEvaluationObservationV1",
    "PortableEvaluationResultV1",
    "PortableExecutionContractV1",
    "PortableSelectedRowV1",
    "execute_native_deterministic_v1",
    "execute_portable_deterministic_v1",
    "materialize_portable_effective_world_v1",
    "observe_portable_deterministic_v1",
    "portable_dependency_predicate_ids_v1",
    "validate_portable_deterministic_v1",
]
