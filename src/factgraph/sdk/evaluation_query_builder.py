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
from factgraph.application.protocol.evaluation_query import (
    EvaluationQueryBinding,
    EvaluationQueryError,
    EvaluationQueryFieldNavigationV0,
    EvaluationQueryNavigationSelectionV0,
    EvaluationQuerySelection,
    EvaluationQuerySelectionItem,
)
from factgraph.application.protocol.evaluation_expectation import ContainsRowExpectationV0
from factgraph.application.protocol.evaluation_scenario import (
    ScenarioFieldSubstitutionSetV0,
    ScenarioFieldSubstitutionV0,
)
from factgraph.application.protocol.evaluation_run_v1 import EvaluationExecutionProfileV1
from factgraph.application.protocol.goal_plan_v1 import (
    GoalExpectationV1,
    GoalResultModeV1,
)
from factgraph.application.protocol.policy import Policy
from factgraph.application.protocol.relation_provider_v1 import RelationProviderV1
from factgraph.application.protocol.scenario_v1 import EvidenceScopeV1, ScenarioSpecV1
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.semantic_address_runtime import SemanticAddressSpace
from factgraph.application.semantic_port_runtime import ResolvedRuleBundle

from .errors import SDKStoreError
from .policy_authoring import (
    AuthoredPolicyTargetV1,
    PolicyFieldHandle,
    PolicyPortHandle,
)

if TYPE_CHECKING:
    from factgraph.application.goal_plan_v1_runtime import GoalPlanInvocationV1

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
    """Immutable native builder that delegates every semantic check downstream."""

    _graph: "SDKStore"
    _target: ResolvedEvaluationQueryTargetV1
    _bindings: tuple[EvaluationQueryBinding, ...] = ()
    _selections: tuple[EvaluationQuerySelectionItem, ...] = ()
    _expectations: tuple[ContainsRowExpectationV0, ...] = ()
    _provider: RelationProviderV1 | None = None
    _authored_policy_owner: object | None = None

    def bind(
        self,
        address: SemanticPortAddress | PolicyPortHandle,
        value: Any,
    ) -> "EvaluationQueryBuilderV1":
        """Add one direct-port binding from a structured address or SDK handle."""

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
    ) -> "EvaluationQueryBuilderV1":
        """Add one ordered direct-port or structured field projection."""

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
    ) -> "EvaluationQueryBuilderV1":
        """Observe whether a completed result contains a matching selected row.

        This does not modify the Policy or the Query projection.  Exact aliases
        and typed values are resolved only at compile time against ``select``.
        """

        try:
            expectation = ContainsRowExpectationV0(
                expectation_id,
                tuple(selected_values.items()),
            )
        except (TypeError, ValueError) as exc:
            raise SDKStoreError(f"query expectation rejected: {exc}") from exc
        return replace(self, _expectations=(*self._expectations, expectation))

    def using(self, provider: RelationProviderV1) -> "EvaluationQueryBuilderV1":
        """Attach one restricted pre-engine provider to a V1 GoalPlan.

        This is intentionally unavailable to the legacy terminal methods:
        providers materialize a sealed finite relation before Scenario and are
        recorded in a V1 Run/Replay payload, rather than being silently
        executed from the old live evaluator.
        """

        if not isinstance(provider, RelationProviderV1):
            raise SDKStoreError("query provider must be RelationProviderV1")
        return replace(self, _provider=provider)

    def plan(
        self,
        *,
        result_mode: GoalResultModeV1 = "rows",
        expectations: tuple[GoalExpectationV1, ...] = (),
        scenario: ScenarioSpecV1 | None = None,
        evidence_scope: EvidenceScopeV1 | None = None,
        profile: EvaluationExecutionProfileV1 | None = None,
        candidate: (
            ResolvedRuleBundle
            | Policy
            | ResolvedEvaluationQueryTargetV1
            | AuthoredPolicyTargetV1
            | None
        ) = None,
        candidate_address_space: SemanticAddressSpace | None = None,
    ) -> "GoalPlanInvocationV1":
        """Compile one immutable V1 GoalPlan without evaluating it.

        Rule and Policy targets use exactly the same typed Query compiler as
        the compatibility path.  ``scenario`` is declarative input only; its
        resolver runs later against one captured relation.  An optional
        candidate is compiled independently with the identical bind/select
        declaration for immutable policy comparison.
        """

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

    def compile(self) -> TargetedCompiledEvaluationQueryV0:
        """Return the existing compiled Query inside a source-target envelope."""

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

    def evaluate(self, **kwargs: Any) -> Any:
        """Compile then use the sole native evaluator; no default kwargs are injected."""

        return self._graph.eval.evaluate(self.compile(), **kwargs)

    def capture(self) -> Any:
        """Capture this exact native Query and its optional observations.

        This is terminal.  It does not widen ordinary ``evaluate(...,
        capture=...)``: the returned outer artifact retains the compiled
        expectation inventory separately from F4's bundle contract.
        """

        return self._graph.eval.capture_query(self.compile())

    def what_if(
        self,
        scenario: ScenarioFieldSubstitutionV0 | ScenarioFieldSubstitutionSetV0 | ScenarioSpecV1,
    ) -> "ScenarioQueryBuilderV0 | ScenarioGoalPlanBuilderV1":
        """Freeze Query intent and enter the bounded ScenarioRun lifecycle.

        This is terminal by design: binding, projection and expectation intent
        must already be present, so there is still only one Query compiler and
        one immutable Query contract.
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
        """Compile once and enter the captured ScenarioRun API."""

        return self._query._graph.eval.run_scenario(self._query.compile(), self._scenario)


@dataclass(frozen=True)
class ScenarioGoalPlanBuilderV1:
    """V1 Scenario convenience wrapper over the same GoalPlan compiler."""

    _query: EvaluationQueryBuilderV1
    _scenario: ScenarioSpecV1

    def plan(self, **kwargs: Any) -> "GoalPlanInvocationV1":
        if "scenario" in kwargs:
            raise SDKStoreError("Scenario is already fixed by query.what_if(ScenarioSpecV1)")
        return self._query.plan(scenario=self._scenario, **kwargs)

    def run(self, **kwargs: Any) -> Any:
        return self.plan(**kwargs).run()


def build_evaluation_query_builder(
    graph: "SDKStore",
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
    if isinstance(target, ProviderQueryTargetV1):
        provider = target.provider
        target = target.target
    if isinstance(target, AuthoredPolicyTargetV1):
        if address_space is not None:
            raise SDKStoreError(
                "AuthoredPolicyTargetV1 already carries its exact SemanticAddressSpace; "
                "do not pass address_space=",
                code="AUTHORED_POLICY_ADDRESS_SPACE_OVERRIDE",
            )
        authored_target = target
        target = authored_target.policy
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
    )


__all__ = [
    "EvaluationQueryBuilderV1",
    "ProviderQueryTargetV1",
    "ScenarioQueryBuilderV0",
    "ScenarioGoalPlanBuilderV1",
    "build_evaluation_query_builder",
]
