"""Thin public read facade over one sealed V2 product evaluation run.

``EvaluationRunV2`` remains the durable execution/replay carrier.  This
module adds no evaluator, profile, query, Scenario, registry, or truth
semantics: it merely opens the already sealed run through the product result
and Explain adapters.  In particular, it deliberately has no implicit first
row, Boolean success, or ``close()`` convenience.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from factgraph.application.product_explanation_data_v2 import (
    EvaluationRunV2ExplanationDataV2,
    evaluation_explanation_data_v2_from_evaluation_run_v2,
)
from factgraph.application.product_result_views_v2 import (
    EvaluationRunV2ExplainTarget,
    EvaluationRunV2ResultView,
    EvaluationRunV2RowView,
    ProductViewErrorV2,
    result_view_v2_from_evaluation_run_v2,
)
from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_run_v2 import (
    EvaluationRunV2,
    assert_evaluation_run_v2_current,
)

from .errors import SDKStoreError

if TYPE_CHECKING:  # pragma: no cover - imported lazily by replay()
    from factgraph.application.goal_plan_v2_runtime import EvaluationRunReplayV2


class ProductEvaluationOutcomeErrorV2(SDKStoreError):
    """Typed public rejection while opening a sealed V2 outcome facade."""


@dataclass(frozen=True, repr=False)
class ProductEvaluationOutcomeV2:
    """Ergonomic read facade for exactly one sealed ``EvaluationRunV2``.

    ``run`` remains public and is the original durable carrier.  Result views
    are lazily opened per named side, so the facade never chooses a row or
    turns point probability into an ordinary Boolean result.
    """

    run: EvaluationRunV2

    def __post_init__(self) -> None:
        if not isinstance(self.run, EvaluationRunV2):
            raise ProductEvaluationOutcomeErrorV2(
                "ProductEvaluationOutcomeV2.run must be EvaluationRunV2",
                code="PRODUCT_OUTCOME_V2_RUN_INVALID",
            )
        try:
            assert_evaluation_run_v2_current(self.run)
        except ProtocolShapeError as exc:
            raise ProductEvaluationOutcomeErrorV2(
                "ProductEvaluationOutcomeV2 requires an integrity-valid sealed run",
                code="PRODUCT_OUTCOME_V2_RUN_INVALID",
            ) from exc

    @classmethod
    def from_run(cls, run: EvaluationRunV2) -> "ProductEvaluationOutcomeV2":
        """Open an already sealed raw run without changing its representation."""

        return cls(run=run)

    @property
    def baseline(self) -> EvaluationRunV2ResultView:
        """The explicitly named baseline-world product result view."""

        return self._side("baseline")

    @property
    def effective(self) -> EvaluationRunV2ResultView:
        """The explicitly named effective-world product result view."""

        return self._side("effective")

    @property
    def candidate_effective(self) -> EvaluationRunV2ResultView | None:
        """The candidate effective view, only when the sealed run has one."""

        if self.run.candidate_effective is None:
            return None
        return self._side("candidate_effective")

    def explain(
        self,
        target: EvaluationRunV2RowView | EvaluationRunV2ExplainTarget,
    ) -> EvaluationRunV2ExplanationDataV2:
        """Return data-first Explain material for one caller-selected row.

        Passing a row view is merely shorthand for its own explicit V2 target;
        the target's run/side/engine/observation links are revalidated by the
        product Explain adapter.  A string, row ordinal, empty result, or a
        Boolean request is intentionally not accepted.
        """

        if isinstance(target, EvaluationRunV2RowView):
            explicit_target = target.to_explain_target()
        elif isinstance(target, EvaluationRunV2ExplainTarget):
            explicit_target = target
        else:
            raise ProductEvaluationOutcomeErrorV2(
                "outcome.explain(...) requires an explicit V2 row view or Explain target",
                code="PRODUCT_OUTCOME_V2_EXPLAIN_TARGET_INVALID",
            )
        try:
            return evaluation_explanation_data_v2_from_evaluation_run_v2(
                self.run,
                target=explicit_target,
            )
        except ProductViewErrorV2 as exc:
            raise ProductEvaluationOutcomeErrorV2(
                f"outcome Explain target is invalid: {exc}",
                code="PRODUCT_OUTCOME_V2_EXPLAIN_TARGET_INVALID",
            ) from exc

    def replay(self) -> "EvaluationRunReplayV2":
        """Replay the sealed raw run; no graph or live evaluator is reopened."""

        from factgraph.application.goal_plan_v2_runtime import replay_evaluation_run_v2

        return replay_evaluation_run_v2(self.run)

    def __bool__(self) -> bool:
        raise ProductEvaluationOutcomeErrorV2(
            "a V2 product outcome has no implicit Boolean truth value; inspect a named result view",
            code="PRODUCT_OUTCOME_V2_BOOLEAN_UNSUPPORTED",
        )

    def __repr__(self) -> str:
        return (
            "ProductEvaluationOutcomeV2("
            f"run_digest={self.run.run_digest!r}, "
            f"candidate_effective={'present' if self.run.candidate_effective else 'none'})"
        )

    def _side(self, side: str) -> EvaluationRunV2ResultView:
        try:
            return result_view_v2_from_evaluation_run_v2(
                self.run,
                side=side,  # type: ignore[arg-type]  # closed literals above.
            )
        except ProductViewErrorV2 as exc:
            raise ProductEvaluationOutcomeErrorV2(
                f"outcome result view is invalid: {exc}",
                code="PRODUCT_OUTCOME_V2_RESULT_INVALID",
            ) from exc


def outcome_from_run_v2(run: EvaluationRunV2) -> ProductEvaluationOutcomeV2:
    """Public functional spelling of :meth:`ProductEvaluationOutcomeV2.from_run`."""

    return ProductEvaluationOutcomeV2.from_run(run)


__all__ = [
    "ProductEvaluationOutcomeErrorV2",
    "ProductEvaluationOutcomeV2",
    "outcome_from_run_v2",
]
