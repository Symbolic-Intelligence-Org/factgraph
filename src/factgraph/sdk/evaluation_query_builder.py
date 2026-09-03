"""Typed SDK facade for resolved Rule/Policy Query targets.

The established methods on :class:`EvaluationQueryBuilderV1` retain their
native V0 compatibility contract.  The additional ``plan`` / Scenario-v1
methods below deliberately enter a separate, sealed GoalPlan path; they do
not widen the old ``eval.evaluate`` dispatch or reinterpret its capture and
Explain artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from factgraph.application.evaluation_query_target_runtime import (
    EvaluationQueryTargetError,
    ResolvedEvaluationQueryTargetV1,
    TargetedCompiledEvaluationQueryV0,
    compile_targeted_evaluation_query,
    resolve_evaluation_query_target,
)
from factgraph.application.protocol.evaluation_expectation import ContainsRowExpectationV0
from factgraph.application.protocol.evaluation_query import (
    EvaluationQueryBinding,
    EvaluationQueryError,
    EvaluationQueryFieldNavigationV0,
    EvaluationQueryNavigationSelectionV0,
    EvaluationQuerySelection,
    EvaluationQuerySelectionItem,
)
from factgraph.application.protocol.evaluation_run_v1 import EvaluationExecutionProfileV1
from factgraph.application.protocol.evaluation_scenario import (
    ScenarioFieldSubstitutionSetV0,
    ScenarioFieldSubstitutionV0,
)
from factgraph.application.protocol.execution_profile_v2 import EvaluationExecutionProfileV2
from factgraph.application.protocol.goal_plan_v1 import (
    GoalExpectationV1,
    GoalResultModeV1,
)
from factgraph.application.protocol.policy import (
    Policy,
    _lower_policy_weighted_choices_to_any_skeleton,
)
from factgraph.application.protocol.relation_provider_v1 import RelationProviderV1
from factgraph.application.protocol.scenario_v1 import EvidenceScopeV1, ScenarioSpecV1
from factgraph.application.protocol.scenario_v2 import ScenarioSpecV2
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.semantic_address_runtime import SemanticAddressSpace
from factgraph.application.semantic_port_runtime import ResolvedRuleBundle

from .errors import SDKStoreError
from .policy_authoring import (
    AuthoredPolicyTargetV1,
    PolicyFieldHandle,
    PolicyPortHandle,
)
from .product_authoring import ProductPolicyV1, ProductRuleV1, WeightedChoiceTopologyV1

if TYPE_CHECKING:
    from factgraph.application.goal_plan_v1_runtime import GoalPlanInvocationV1
    from factgraph.application.goal_plan_v2_runtime import ProductEvaluationInvocationV2

    from .store import SDKStore


@dataclass(frozen=True)
class ProviderQueryTargetV1:
    """Attach one pre-engine relation provider to a Rule-or-Policy target.

    The provider is *not* made into a Rule and it does not replace the
    underlying target's semantic address space.  It supplies one sealed
    predicate subset before Scenario resolution; the existing target compiler
    still owns structured bind/select and branch-total checks.
    """

    target: ResolvedRuleBundle | Policy | ResolvedEvaluationQueryTargetV1 | AuthoredPolicyTargetV1
    provider: RelationProviderV1

    def __post_init__(self) -> None:
        if not isinstance(self.provider, RelationProviderV1):
            raise TypeError("ProviderQueryTargetV1.provider must be RelationProviderV1")


@dataclass(frozen=True)
class EvaluationQueryBuilderV1:
    """Build typed Query intent over one resolved Rule or Policy target.

    Each method returns a new immutable builder. Authoring does not read the
    ledger or execute an engine; a terminal compiles and/or runs the captured
    intent under its explicit V0, V1, or Product V2 contract.
    """

    _graph: SDKStore
    _target: ResolvedEvaluationQueryTargetV1
    _bindings: tuple[EvaluationQueryBinding, ...] = ()
    _selections: tuple[EvaluationQuerySelectionItem, ...] = ()
    _expectations: tuple[ContainsRowExpectationV0, ...] = ()
    _provider: RelationProviderV1 | None = None
    _authored_policy_owner: object | None = None
    _weighted_choices: tuple[WeightedChoiceTopologyV1, ...] = ()
    _requires_product_v2: bool = False
    # The resolved target below is sufficient for legacy/V1 compilation, but
    # V2 capture also needs the original product envelope: AssetMeta binding,
    # WeightedChoice topology and the exact immutable wrapper.  Retain it as
    # an in-process carrier only; V2 run construction seals its own snapshot.
    _product_target: ProductRuleV1 | ProductPolicyV1 | None = None

    def bind(
        self,
        address: SemanticPortAddress | PolicyPortHandle,
        value: Any,
    ) -> EvaluationQueryBuilderV1:
        """Bind one direct input port to a typed value.

        Args:
            address: Direct semantic address or owner-bound Policy port.
            value: Value for the port's declared semantic domain.

        Returns:
            A new builder containing the binding.

        Raises:
            SDKStoreError: If the handle crosses Policy owners, the port is a
                field navigation or Function output, or the value is invalid.

        Notes:
            ``bind`` constrains an input. It never turns a selected/computed
            output into an engine input and does not execute the Query.
        """

        if isinstance(address, PolicyFieldHandle):
            raise SDKStoreError(
                "query bind accepts direct Policy ports, not field-navigation handles",
                code="INVALID_QUERY_BINDING",
            )
        if isinstance(address, PolicyPortHandle):
            self._assert_authored_policy_handle(address)
            address = address.address

        try:
            binding = EvaluationQueryBinding(address, value)
        except EvaluationQueryError as exc:
            raise SDKStoreError(f"query bind rejected: {exc}", code=exc.code) from exc
        return replace(self, _bindings=(*self._bindings, binding))

    def select(
        self,
        alias: str,
        source: (
            SemanticPortAddress
            | EvaluationQueryFieldNavigationV0
            | PolicyPortHandle
            | PolicyFieldHandle
        ),
    ) -> EvaluationQueryBuilderV1:
        """Add one ordered output projection.

        Args:
            alias: Unique output-column name.
            source: Direct port, Function output, or supported field
                navigation from this Query target.

        Returns:
            A new builder containing the ordered selection.

        Raises:
            SDKStoreError: If the alias/source is invalid or an owner-bound
                handle comes from another Policy.

        Notes:
            Projection does not reverse dataflow. A Function output can be
            selected but remains invalid as a Query binding.
        """

        try:
            selection: EvaluationQuerySelectionItem
            if isinstance(source, PolicyFieldHandle):
                self._assert_authored_policy_handle(source)
                selection = EvaluationQueryNavigationSelectionV0(
                    alias,
                    EvaluationQueryFieldNavigationV0(
                        source.navigation.base,
                        source.navigation.field,
                    ),
                )
            elif isinstance(source, PolicyPortHandle):
                self._assert_authored_policy_handle(source)
                selection = EvaluationQuerySelection(alias, source.address)
            elif isinstance(source, SemanticPortAddress):
                selection = EvaluationQuerySelection(alias, source)
            elif isinstance(source, EvaluationQueryFieldNavigationV0):
                selection = EvaluationQueryNavigationSelectionV0(alias, source)
            else:
                raise EvaluationQueryError(
                    "selection address/source must be SemanticPortAddress or "
                    "EvaluationQueryFieldNavigationV0",
                    code="INVALID_QUERY_SELECTION",
                    stage="query_construct",
                )
        except EvaluationQueryError as exc:
            raise SDKStoreError(f"query select rejected: {exc}", code=exc.code) from exc
        return replace(self, _selections=(*self._selections, selection))

    def _assert_authored_policy_handle(self, handle: PolicyPortHandle) -> None:
        """Reject a handle that was not issued by this exact authored target.

        ``SemanticPortAddress`` is intentionally structural and therefore can
        be used by advanced callers.  A façade handle additionally carries an
        in-process draft capability: otherwise two drafts with the same alias
        and a compatible schema could silently cross-wire a Query.
        """

        if self._authored_policy_owner is None or handle._owner is not self._authored_policy_owner:
            raise SDKStoreError(
                "Policy port handle belongs to a different Policy draft or target",
                code="POLICY_CROSS_DRAFT_HANDLE",
            )

    def expect_contains(
        self,
        expectation_id: str,
        /,
        **selected_values: Any,
    ) -> EvaluationQueryBuilderV1:
        """Observe whether a completed result contains a matching selected row.

        This does not modify the Policy or the Query projection.  Exact aliases
        and typed values are resolved only at compile time against ``select``.

        Args:
            expectation_id: Unique expectation identifier.
            **selected_values: Expected selected aliases and typed values.

        Returns:
            A new immutable builder containing the observation request.

        Raises:
            SDKStoreError: If the id or expected row shape is invalid.

        Notes:
            This is the V0 compatibility expectation. V1 typed expectations
            belong to ``plan(expectations=...)`` and Product V2 currently
            rejects expectations.
        """

        try:
            expectation = ContainsRowExpectationV0(
                expectation_id,
                tuple(selected_values.items()),
            )
        except (TypeError, ValueError) as exc:
            raise SDKStoreError(f"query expectation rejected: {exc}") from exc
        return replace(self, _expectations=(*self._expectations, expectation))

    def using(self, provider: RelationProviderV1) -> EvaluationQueryBuilderV1:
        """Attach one restricted pre-engine provider to a V1 GoalPlan.

        This is intentionally unavailable to the legacy terminal methods:
        providers materialize a sealed finite relation before Scenario and are
        recorded in a V1 Run/Replay payload, rather than being silently
        executed from the old live evaluator.

        Args:
            provider: Restricted typed Provider contract to attach.

        Returns:
            A new immutable builder carrying the Provider.

        Raises:
            SDKStoreError: If ``provider`` is not a ``RelationProviderV1``.

        Notes:
            A Provider is not a standalone Query target and is invoked only by
            the V1 GoalPlan terminal.
        """

        if not isinstance(provider, RelationProviderV1):
            raise SDKStoreError("query provider must be RelationProviderV1")
        return replace(self, _provider=provider)

    def plan(
        self,
        *,
        result_mode: GoalResultModeV1 = "rows",
        expectations: tuple[GoalExpectationV1, ...] = (),
        scenario: ScenarioSpecV1 | ScenarioSpecV2 | None = None,
        evidence_scope: EvidenceScopeV1 | None = None,
        profile: EvaluationExecutionProfileV1 | EvaluationExecutionProfileV2 | None = None,
        candidate: (
            ResolvedRuleBundle
            | Policy
            | ResolvedEvaluationQueryTargetV1
            | AuthoredPolicyTargetV1
            | None
        ) = None,
        candidate_address_space: SemanticAddressSpace | None = None,
        expected_view_snapshot_digest: str | None = None,
    ) -> GoalPlanInvocationV1 | ProductEvaluationInvocationV2:
        """Create an immutable V1 or Product V2 execution invocation.

        Rule and Policy targets use exactly the same typed Query compiler as
        the compatibility path.  ``scenario`` is declarative input only; its
        resolver runs later against one captured relation.  An optional
        candidate is compiled independently with the identical bind/select
        declaration for immutable policy comparison.

        Args:
            result_mode: V1 result mode. Product V2 currently accepts
                ``"rows"`` only.
            expectations: Typed V1 expectations; unsupported in Product V2.
            scenario: V1 Scenario or Product V2 Scenario matching ``profile``.
            evidence_scope: Optional V1 evidence capture scope.
            profile: Explicit V1 or Product V2 execution profile.
            candidate: Optional independently authored comparison target.
            candidate_address_space: Advanced address space for a raw Policy
                candidate.

        Returns:
            A generation-specific immutable invocation whose ``run()`` method
            performs evaluation.

        Raises:
            SDKStoreError: If generations are mixed, the target/profile pins
                disagree, or a requested feature is unsupported.

        Notes:
            Product V2 selection is explicit through
            ``EvaluationExecutionProfileV2``. No Scenario, Provider,
            expectation, or evidence contract is silently translated across
            generations.
        """

        # V2 is an explicitly separate terminal rather than an extension of
        # the V1 wire.  Select it before the established V1 checks so a mixed
        # Scenario/profile pair cannot be accidentally interpreted as legacy
        # intent.  A V2 profile always owns a sealed V2 world; ``scenario`` is
        # an optional overlay, so its absence means the explicit empty world
        # rather than a fallback to the V1 evaluator.
        is_v2 = isinstance(scenario, ScenarioSpecV2) or isinstance(
            profile, EvaluationExecutionProfileV2
        )
        if is_v2:
            return self._plan_v2(
                result_mode=result_mode,
                expectations=expectations,
                scenario=scenario,
                evidence_scope=evidence_scope,
                profile=profile,
                candidate=candidate,
                candidate_address_space=candidate_address_space,
                expected_view_snapshot_digest=expected_view_snapshot_digest,
            )

        if expected_view_snapshot_digest is not None:
            raise SDKStoreError(
                "expected_view_snapshot_digest requires Product V2",
                code="V2_EXPECTED_VIEW_REQUIRES_V2",
            )

        if self._expectations:
            raise SDKStoreError(
                "legacy expect_contains(...) cannot be mixed with GoalPlan expectations; "
                "pass typed expectations to plan(expectations=...)"
            )
        if not isinstance(expectations, tuple):
            raise SDKStoreError("GoalPlan expectations must be a tuple")
        if scenario is not None and not isinstance(scenario, ScenarioSpecV1):
            raise SDKStoreError("GoalPlan scenario must be ScenarioSpecV1")
        if evidence_scope is not None and not isinstance(evidence_scope, EvidenceScopeV1):
            raise SDKStoreError("GoalPlan evidence_scope must be EvidenceScopeV1")
        if profile is not None and not isinstance(profile, EvaluationExecutionProfileV1):
            raise SDKStoreError("GoalPlan profile must be EvaluationExecutionProfileV1")

        primary = self._compile_query(allow_provider=True)
        compiled_candidate: TargetedCompiledEvaluationQueryV0 | None = None
        if candidate is not None:
            # A provider is a pre-engine materialization receipt tied to one
            # target/query invocation.  Supporting it on a comparison arm
            # would require a second independently pinned materialization,
            # receipt and replay contract.  Do not let the wrapper disappear
            # while compiling the base target: V1 comparisons are currently
            # Rule/Policy-to-Rule/Policy only.
            if isinstance(candidate, ProviderQueryTargetV1):
                raise SDKStoreError(
                    "GoalPlan candidate cannot carry RelationProviderV1; "
                    "compare immutable Rule/Policy targets without a provider",
                    code="GOAL_PROVIDER_CANDIDATE_UNSUPPORTED",
                )
            candidate_builder = build_evaluation_query_builder(
                self._graph,
                candidate,
                address_space=candidate_address_space,
            )
            candidate_builder = replace(
                candidate_builder,
                _bindings=self._bindings,
                _selections=self._selections,
            )
            compiled_candidate = candidate_builder._compile_query(allow_provider=True)

        from factgraph.application.goal_plan_v1_runtime import build_goal_plan_invocation_v1

        try:
            return build_goal_plan_invocation_v1(
                graph=self._graph,
                primary=primary,
                result_mode=result_mode,
                expectations=expectations,
                scenario=scenario,
                evidence_scope=EvidenceScopeV1() if evidence_scope is None else evidence_scope,
                profile=profile,
                candidate=compiled_candidate,
                provider=self._provider,
            )
        except (TypeError, ValueError) as exc:
            code = getattr(exc, "code", None)
            raise SDKStoreError(f"GoalPlan construction rejected: {exc}", code=code) from exc

    def _plan_v2(
        self,
        *,
        result_mode: GoalResultModeV1,
        expectations: tuple[GoalExpectationV1, ...],
        scenario: ScenarioSpecV1 | ScenarioSpecV2 | None,
        evidence_scope: EvidenceScopeV1 | None,
        profile: EvaluationExecutionProfileV1 | EvaluationExecutionProfileV2 | None,
        candidate: (
            ResolvedRuleBundle
            | Policy
            | ResolvedEvaluationQueryTargetV1
            | AuthoredPolicyTargetV1
            | None
        ),
        candidate_address_space: SemanticAddressSpace | None,
        expected_view_snapshot_digest: str | None,
    ) -> ProductEvaluationInvocationV2:
        """Create a V2 invocation without widening the V1 GoalPlan contract."""

        if not isinstance(profile, EvaluationExecutionProfileV2) or (
            scenario is not None and not isinstance(scenario, ScenarioSpecV2)
        ):
            raise SDKStoreError(
                "V2 Query planning requires profile=EvaluationExecutionProfileV2; "
                "scenario must be ScenarioSpecV2 when supplied",
                code="V2_PLAN_COHERENT_INPUTS_REQUIRED",
            )
        if self._expectations or expectations:
            raise SDKStoreError(
                "V2 Query planning does not accept V0/V1 expectations; "
                "point-probability expectations are not implemented",
                code="V2_PLAN_EXPECTATIONS_UNSUPPORTED",
            )
        if result_mode != "rows":
            raise SDKStoreError(
                "V2 Query planning currently supports result_mode='rows' only",
                code="V2_PLAN_RESULT_MODE_UNSUPPORTED",
            )
        if evidence_scope is not None:
            raise SDKStoreError(
                "V2 Query planning does not accept V1 evidence_scope; "
                "Scenario V2 captures its own typed evidence lane",
                code="V2_PLAN_EVIDENCE_SCOPE_UNSUPPORTED",
            )
        if self._provider is not None:
            raise SDKStoreError(
                "V2 Query planning does not accept RelationProviderV1",
                code="V2_PLAN_PROVIDER_UNSUPPORTED",
            )
        if self._product_target is None:
            raise SDKStoreError(
                "V2 Query planning requires a resolved Rule/Policy product target",
                code="V2_PLAN_PRODUCT_TARGET_REQUIRED",
            )

        primary = self._compile_v2_query()
        compiled_candidate: TargetedCompiledEvaluationQueryV0 | None = None
        candidate_product_target: ProductRuleV1 | ProductPolicyV1 | None = None
        if candidate is not None:
            if isinstance(candidate, ProviderQueryTargetV1):
                raise SDKStoreError(
                    "V2 Query candidate cannot carry RelationProviderV1",
                    code="V2_PLAN_PROVIDER_UNSUPPORTED",
                )
            candidate_builder = build_evaluation_query_builder(
                self._graph,
                candidate,
                address_space=candidate_address_space,
            )
            candidate_builder = replace(
                candidate_builder,
                _bindings=self._bindings,
                _selections=self._selections,
            )
            if candidate_builder._product_target is None:
                raise SDKStoreError(
                    "V2 Query candidate requires a resolved Rule/Policy product target",
                    code="V2_PLAN_PRODUCT_TARGET_REQUIRED",
                )
            compiled_candidate = candidate_builder._compile_v2_query()
            candidate_product_target = candidate_builder._product_target

        from factgraph.application.goal_plan_v2_runtime import (
            build_product_evaluation_invocation_v2,
        )

        try:
            return build_product_evaluation_invocation_v2(
                graph=self._graph,
                primary=primary,
                product_target=self._product_target,
                profile=profile,
                scenario=scenario,
                candidate=compiled_candidate,
                candidate_product_target=candidate_product_target,
                expected_view_snapshot_digest=expected_view_snapshot_digest,
            )
        except (TypeError, ValueError) as exc:
            code = getattr(exc, "code", None)
            raise SDKStoreError(f"V2 Query planning rejected: {exc}", code=code) from exc

    def plan_v2(
        self,
        *,
        scenario: ScenarioSpecV2 | None = None,
        profile: EvaluationExecutionProfileV2,
        candidate: (
            ResolvedRuleBundle
            | Policy
            | ResolvedEvaluationQueryTargetV1
            | AuthoredPolicyTargetV1
            | None
        ) = None,
        candidate_address_space: SemanticAddressSpace | None = None,
        expected_view_snapshot_digest: str | None = None,
    ) -> ProductEvaluationInvocationV2:
        """Create an explicit Product V2 execution invocation.

        New code may use either this spelling or
        ``query.plan(scenario=v2, profile=v2)``.  ``scenario`` is optional:
        omitting it selects the sealed empty V2 world.  Both route to exactly
        the same V2 invocation factory and preserve the original product
        target.

        Args:
            scenario: Optional run-local V2 overlay; omission seals an empty
                overlay rather than falling back to V1.
            profile: Target-pinned Product V2 execution profile.
            candidate: Optional independently authored Product candidate.
            candidate_address_space: Advanced address space for a raw Policy
                candidate.

        Returns:
            A Product V2 invocation ready for ``run()``.

        Raises:
            SDKStoreError: If target, profile, Scenario, or candidate pins are
                incoherent.
        """

        return self.plan(
            scenario=scenario,
            profile=profile,
            candidate=candidate,
            candidate_address_space=candidate_address_space,
            expected_view_snapshot_digest=expected_view_snapshot_digest,
        )

    def compile(self) -> TargetedCompiledEvaluationQueryV0:
        """Compile typed Query intent into the compatibility target envelope.

        Returns:
            The compiled Query plus resolved source-target identity.

        Raises:
            SDKStoreError: If bindings, selections, target topology, Provider,
                or generation-specific features are invalid.

        Notes:
            Compilation does not execute an engine. Product V2-only Function
            and WeightedChoice targets intentionally reject this V0 terminal.
        """

        return self._compile_query(allow_provider=False)

    def _compile_query(
        self,
        *,
        allow_provider: bool,
    ) -> TargetedCompiledEvaluationQueryV0:
        """Compile the shared structured Query while guarding V0 terminals.

        A provider is a V1 pre-engine materialization contract.  Letting the
        old compiler/evaluator ignore it would make a call look successful
        while silently dropping declared input.  Only ``plan()`` may compile
        a provider-attached builder, and it later invokes/materializes the
        provider exactly once through the sealed V1 runtime.
        """

        if self._requires_product_v2:
            message = (
                "WeightedChoice targets are V2 ProbLog-only; legacy compile/evaluate/capture/"
                "what_if and V1 plan terminals reject them before deterministic Policy lowering"
                if self._weighted_choices
                else "Function targets are Product V2-only; legacy compile/evaluate/capture/"
                "what_if and V1 plan terminals cannot execute or ignore the Function"
            )
            raise SDKStoreError(
                message,
                code=("WEIGHTED_CHOICE_V2_ONLY" if self._weighted_choices else "FUNCTION_V2_ONLY"),
            )
        if self._provider is not None and not allow_provider:
            raise SDKStoreError(
                "RelationProviderV1 requires query.plan(...).run(); legacy "
                "compile/evaluate/capture/Scenario-v0 terminals cannot ignore it"
            )

        try:
            return compile_targeted_evaluation_query(
                self._target,
                bindings=self._bindings,
                selections=self._selections,
                expectations=self._expectations,
                schema_index=self._graph._application_schema_index,
            )
        except (EvaluationQueryError, EvaluationQueryTargetError, ValueError) as exc:
            code = getattr(exc, "code", None)
            raise SDKStoreError(f"query compilation rejected: {exc}", code=code) from exc

    def _compile_v2_query(self) -> TargetedCompiledEvaluationQueryV0:
        """Compile typed Query intent for V2 without reusing a V1 terminal.

        A V2 ProductPolicy may contain an intrinsic ``WeightedChoice`` node.
        The controlled private bridge derives the compiler-only skeleton for
        typed bind/select validation, while the V2 runner owns the actual
        ProbLog lowering.  Providers and legacy expectations remain rejected
        because their contracts cannot be silently reinterpreted as V2.
        """

        if self._provider is not None:
            raise SDKStoreError(
                "V2 Query compilation does not accept RelationProviderV1",
                code="V2_PLAN_PROVIDER_UNSUPPORTED",
            )
        if self._expectations:
            raise SDKStoreError(
                "V2 Query compilation does not accept legacy expectations",
                code="V2_PLAN_EXPECTATIONS_UNSUPPORTED",
            )
        try:
            return compile_targeted_evaluation_query(
                self._target,
                bindings=self._bindings,
                selections=self._selections,
                expectations=(),
                schema_index=self._graph._application_schema_index,
            )
        except (EvaluationQueryError, EvaluationQueryTargetError, ValueError) as exc:
            code = getattr(exc, "code", None)
            raise SDKStoreError(f"V2 query compilation rejected: {exc}", code=code) from exc

    def evaluate(self, **kwargs: Any) -> Any:
        """Run the legacy live evaluator over this Query.

        Args:
            **kwargs: Legacy ``fg.eval.evaluate`` keyword arguments.

        Returns:
            A legacy ``EvaluateResult``.

        Notes:
            Product V2 Function/WeightedChoice targets and attached Providers
            fail closed here. Use ``plan(profile=...).run()`` for those paths.
        """

        return self._graph.eval.evaluate(self.compile(), **kwargs)

    def capture(self) -> Any:
        """Capture this exact legacy native Query and its observations.

        This is terminal.  It does not widen ordinary ``evaluate(...,
        capture=...)``: the returned outer artifact retains the compiled
        expectation inventory separately from F4's bundle contract.

        Returns:
            A detached legacy captured-Query artifact.

        Notes:
            This is not Product V2 run capture. Function, WeightedChoice and
            V2 Scenario/profile semantics are intentionally rejected.
        """

        return self._graph.eval.capture_query(self.compile())

    def what_if(
        self,
        scenario: ScenarioFieldSubstitutionV0 | ScenarioFieldSubstitutionSetV0 | ScenarioSpecV1,
    ) -> ScenarioQueryBuilderV0 | ScenarioGoalPlanBuilderV1:
        """Freeze Query intent and enter the bounded ScenarioRun lifecycle.

        This is terminal by design: binding, projection and expectation intent
        must already be present, so there is still only one Query compiler and
        one immutable Query contract.

        Args:
            scenario: A bounded V0 field substitution or V1 Scenario spec.

        Returns:
            A generation-specific Scenario terminal wrapper.

        Raises:
            SDKStoreError: If expectations, Providers, or Scenario generation
                are incompatible with the selected terminal.

        Notes:
            Product V2 Scenarios use ``plan(profile=v2, scenario=v2)`` instead.
        """

        if isinstance(scenario, ScenarioSpecV1):
            if self._expectations:
                raise SDKStoreError(
                    "query.what_if(ScenarioSpecV1) cannot be mixed with legacy expect_contains(...); "
                    "use plan(expectations=...)"
                )
            return ScenarioGoalPlanBuilderV1(self, scenario)
        if self._provider is not None:
            raise SDKStoreError(
                "RelationProviderV1 requires ScenarioSpecV1 + GoalPlan v1; "
                "the legacy Scenario-v0 terminal cannot ignore it"
            )
        if not isinstance(scenario, (ScenarioFieldSubstitutionV0, ScenarioFieldSubstitutionSetV0)):
            raise SDKStoreError(
                "query.what_if(...) requires ScenarioFieldSubstitutionV0 "
                ", ScenarioFieldSubstitutionSetV0, or ScenarioSpecV1"
            )
        if self._expectations:
            raise SDKStoreError("query.what_if(...) does not support expect_contains(...)")
        return ScenarioQueryBuilderV0(self, scenario)


@dataclass(frozen=True)
class ScenarioQueryBuilderV0:
    """Terminal Query wrapper that runs an already-declared Scenario."""

    _query: EvaluationQueryBuilderV1
    _scenario: ScenarioFieldSubstitutionV0 | ScenarioFieldSubstitutionSetV0

    def run(self) -> Any:
        """Compile and execute the fixed V0 Scenario query.

        Returns:
            A captured ``ScenarioRunV0`` compatibility result.

        Raises:
            SDKStoreError: If Query compilation or Scenario execution fails.

        Notes:
            This is the V0 compatibility terminal. Product V2 Scenario code
            should use ``query.plan(profile=v2, scenario=v2).run()``.
        """

        return self._query._graph.eval.run_scenario(self._query.compile(), self._scenario)


@dataclass(frozen=True)
class ScenarioGoalPlanBuilderV1:
    """V1 Scenario convenience wrapper over the same GoalPlan compiler."""

    _query: EvaluationQueryBuilderV1
    _scenario: ScenarioSpecV1

    def plan(self, **kwargs: Any) -> GoalPlanInvocationV1:
        """Build a V1 GoalPlan with this Scenario already fixed.

        Args:
            **kwargs: Remaining V1 GoalPlan options except ``scenario``.

        Returns:
            A compiled V1 invocation ready for ``run()``.
        """
        if "scenario" in kwargs:
            raise SDKStoreError("Scenario is already fixed by query.what_if(ScenarioSpecV1)")
        return self._query.plan(scenario=self._scenario, **kwargs)

    def run(self, **kwargs: Any) -> Any:
        """Plan and execute this fixed V1 Scenario convenience path.

        Args:
            **kwargs: Remaining V1 GoalPlan options except ``scenario``.

        Returns:
            A completed ``GoalPlanRunV1`` or fail-closed
            ``GoalPlanFailureV1``.

        Raises:
            SDKStoreError: If the supplied planning options are invalid.

        Notes:
            This convenience method is equivalent to
            ``builder.plan(**kwargs).run()`` and never enters Product V2.
        """
        return self.plan(**kwargs).run()


def build_evaluation_query_builder(
    graph: SDKStore,
    target: (
        ResolvedRuleBundle
        | Policy
        | ResolvedEvaluationQueryTargetV1
        | AuthoredPolicyTargetV1
        | ProviderQueryTargetV1
    ),
    *,
    address_space: SemanticAddressSpace | None = None,
) -> EvaluationQueryBuilderV1:
    """Resolve an in-process target before any bind/select intent is accepted."""

    provider: RelationProviderV1 | None = None
    authored_policy_owner: object | None = None
    weighted_choices: tuple[WeightedChoiceTopologyV1, ...] = ()
    requires_product_v2 = False
    if isinstance(target, ProviderQueryTargetV1):
        provider = target.provider
        target = target.target
    # V2 runs must retain an immutable product envelope for the selected
    # target.  Product inputs retain their original object; established raw
    # resolved Rule/Policy forms receive the explicit ``AssetMeta=absent``
    # envelope instead of silently losing their identity at V2 capture.
    product_target = _product_target_for_v2(target)
    if isinstance(target, ProductPolicyV1):
        weighted_choices = target.weighted_choices
        requires_product_v2 = target.requires_v2_profile
    if isinstance(target, AuthoredPolicyTargetV1):
        if address_space is not None:
            raise SDKStoreError(
                "AuthoredPolicyTargetV1 already carries its exact SemanticAddressSpace; "
                "do not pass address_space=",
                code="AUTHORED_POLICY_ADDRESS_SPACE_OVERRIDE",
            )
        authored_target = target
        target = _query_resolution_policy_for_authored_target(authored_target)
        address_space = authored_target.address_space
        authored_policy_owner = authored_target._authoring_owner
    try:
        resolved = resolve_evaluation_query_target(
            target,
            address_space=address_space,
            schema_index=graph._application_schema_index,
        )
    except EvaluationQueryTargetError as exc:
        raise SDKStoreError(f"query target rejected: {exc}", code=exc.code) from exc
    return EvaluationQueryBuilderV1(
        graph,
        resolved,
        _provider=provider,
        _authored_policy_owner=authored_policy_owner,
        _weighted_choices=weighted_choices,
        _requires_product_v2=requires_product_v2,
        _product_target=product_target,
    )


def _product_target_for_v2(target: object) -> ProductRuleV1 | ProductPolicyV1 | None:
    """Return an exact V2 product carrier without creating a registry entry."""

    if isinstance(target, (ProductRuleV1, ProductPolicyV1)):
        return target
    if isinstance(target, ResolvedRuleBundle):
        return ProductRuleV1(target.rule, target.contract)
    if isinstance(target, AuthoredPolicyTargetV1):
        return ProductPolicyV1(
            target.policy,
            target.address_space,
            target._authoring_owner,
        )
    return None


def _query_resolution_policy_for_authored_target(
    target: AuthoredPolicyTargetV1,
) -> Policy:
    """Return the one internal plain skeleton permitted for Product V2 Query.

    A public ``ProductPolicyV1.policy`` with ``WeightedChoice`` contains an
    intrinsic V2-only node (and carries ``PolicyV2Only`` as defense in depth),
    so the legacy resolver rejects it. The SDK alone derives the private plain
    skeleton needed for typed bind/select validation before the V2 runner
    lowers the derived topology capture. The original product object remains
    held in ``_product_target`` and legacy terminals reject its AST.
    """

    if isinstance(target, ProductPolicyV1) and target.requires_v2_profile:
        return _lower_policy_weighted_choices_to_any_skeleton(target.policy)
    return target.policy


__all__ = [
    "EvaluationQueryBuilderV1",
    "ProviderQueryTargetV1",
    "ScenarioGoalPlanBuilderV1",
    "ScenarioQueryBuilderV0",
    "build_evaluation_query_builder",
]
