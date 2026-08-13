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
    EvaluationQuerySelection,
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
    _selections: tuple[EvaluationQuerySelection, ...] = ()

    def bind(self, address: SemanticPortAddress, value: Any) -> "EvaluationQueryBuilderV1":
        """Add one structured direct-port binding; dotted paths are not accepted."""

        try:
            binding = EvaluationQueryBinding(address, value)
        except EvaluationQueryError as exc:
            raise SDKStoreError(f"query bind rejected: {exc}", code=exc.code) from exc
        return replace(self, _bindings=(*self._bindings, binding))

    def select(self, alias: str, address: SemanticPortAddress) -> "EvaluationQueryBuilderV1":
        """Add one ordered projection; at least one selection is required."""

        try:
            selection = EvaluationQuerySelection(alias, address)
        except EvaluationQueryError as exc:
            raise SDKStoreError(f"query select rejected: {exc}", code=exc.code) from exc
        return replace(self, _selections=(*self._selections, selection))

    def compile(self) -> TargetedCompiledEvaluationQueryV0:
        """Return the existing compiled Query inside a source-target envelope."""

        try:
            return compile_targeted_evaluation_query(
                self._target,
                bindings=self._bindings,
                selections=self._selections,
                schema_index=self._graph._application_schema_index,
            )
        except (EvaluationQueryError, EvaluationQueryTargetError, ValueError) as exc:
            code = getattr(exc, "code", None)
            raise SDKStoreError(f"query compilation rejected: {exc}", code=code) from exc

    def evaluate(self, **kwargs: Any) -> Any:
        """Compile then use the sole native evaluator; no default kwargs are injected."""

        return self._graph.eval.evaluate(self.compile(), **kwargs)


def build_evaluation_query_builder(
    graph: "SDKStore",
    target: ResolvedRuleBundle | Policy | ResolvedEvaluationQueryTargetV1,
    *,
    address_space: SemanticAddressSpace | None = None,
) -> EvaluationQueryBuilderV1:
    """Resolve an in-process target before any bind/select intent is accepted."""

    try:
        resolved = resolve_evaluation_query_target(target, address_space=address_space)
    except EvaluationQueryTargetError as exc:
        raise SDKStoreError(f"query target rejected: {exc}", code=exc.code) from exc
    return EvaluationQueryBuilderV1(graph, resolved)


__all__ = ["EvaluationQueryBuilderV1", "build_evaluation_query_builder"]
