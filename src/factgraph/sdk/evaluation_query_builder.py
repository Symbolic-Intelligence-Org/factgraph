"""Thin SDK facade for the native resolved Rule-or-Policy Query target."""

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
from factgraph.application.protocol.policy import Policy
from factgraph.application.protocol.semantic_address import SemanticPortAddress
from factgraph.application.semantic_address_runtime import SemanticAddressSpace
from factgraph.application.semantic_port_runtime import ResolvedRuleBundle

from .errors import SDKStoreError

if TYPE_CHECKING:
    from .store import SDKStore


@dataclass(frozen=True)
class EvaluationQueryBuilderV1:
    """Immutable native builder that delegates every semantic check downstream."""

    _graph: "SDKStore"
    _target: ResolvedEvaluationQueryTargetV1
    _bindings: tuple[EvaluationQueryBinding, ...] = ()
    _selections: tuple[EvaluationQuerySelectionItem, ...] = ()
    _expectations: tuple[ContainsRowExpectationV0, ...] = ()

    def bind(self, address: SemanticPortAddress, value: Any) -> "EvaluationQueryBuilderV1":
        """Add one structured direct-port binding; dotted paths are not accepted."""

        try:
            binding = EvaluationQueryBinding(address, value)
        except EvaluationQueryError as exc:
            raise SDKStoreError(f"query bind rejected: {exc}", code=exc.code) from exc
        return replace(self, _bindings=(*self._bindings, binding))

    def select(
        self,
        alias: str,
        source: SemanticPortAddress | EvaluationQueryFieldNavigationV0,
    ) -> "EvaluationQueryBuilderV1":
        """Add one ordered direct-port or structured field projection."""

        try:
            selection: EvaluationQuerySelectionItem
            if isinstance(source, SemanticPortAddress):
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

    def compile(self) -> TargetedCompiledEvaluationQueryV0:
        """Return the existing compiled Query inside a source-target envelope."""

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

    def what_if(
        self,
        scenario: ScenarioFieldSubstitutionV0 | ScenarioFieldSubstitutionSetV0,
    ) -> "ScenarioQueryBuilderV0":
        """Freeze Query intent and enter the bounded ScenarioRun lifecycle.

        This is terminal by design: binding, projection and expectation intent
        must already be present, so there is still only one Query compiler and
        one immutable Query contract.
        """

        if not isinstance(
            scenario,
            (ScenarioFieldSubstitutionV0, ScenarioFieldSubstitutionSetV0),
        ):
            raise SDKStoreError(
                "query.what_if(...) requires ScenarioFieldSubstitutionV0 "
                "or ScenarioFieldSubstitutionSetV0"
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


def build_evaluation_query_builder(
    graph: "SDKStore",
    target: ResolvedRuleBundle | Policy | ResolvedEvaluationQueryTargetV1,
    *,
    address_space: SemanticAddressSpace | None = None,
) -> EvaluationQueryBuilderV1:
    """Resolve an in-process target before any bind/select intent is accepted."""

    try:
        resolved = resolve_evaluation_query_target(
            target,
            address_space=address_space,
            schema_index=graph._application_schema_index,
        )
    except EvaluationQueryTargetError as exc:
        raise SDKStoreError(f"query target rejected: {exc}", code=exc.code) from exc
    return EvaluationQueryBuilderV1(graph, resolved)


__all__ = [
    "EvaluationQueryBuilderV1",
    "ScenarioQueryBuilderV0",
    "build_evaluation_query_builder",
]
