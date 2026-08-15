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
    """Open one sealed Product V2 run as user-facing result views.

    ``run`` remains public and is the original durable carrier.  Result views
    are lazily opened per named side, so the facade never chooses a row or
    turns point probability into an ordinary Boolean result.

    Attributes:
        run: Original integrity-validated ``EvaluationRunV2`` carrier.

    Notes:
        The facade is read-only. It does not reevaluate the Query, read the
        live ledger, or reinterpret probabilities as Boolean truth.
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
        """Open an already sealed raw run.

        Args:
            run: Integrity-valid Product V2 run.

        Returns:
            A read-only ``ProductEvaluationOutcomeV2`` facade.

        Raises:
            ProductEvaluationOutcomeErrorV2: If the run type or any nested
                seal is invalid.

        Notes:
            Opening does not change, reseal, replay, or authenticate the run.
        """

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
        """Return structured Explain data for one explicit row.

        Passing a row view is merely shorthand for its own explicit V2 target;
        the target's run/side/engine/observation links are revalidated by the
        product Explain adapter.  A string, row ordinal, empty result, or a
        Boolean request is intentionally not accepted.

        Args:
            target: Row view from this run or its explicit Explain target.

        Returns:
            Machine-readable ``EvaluationRunV2ExplanationDataV2`` including
            available Scenario, asset, probability, Function, choice, and
            evidence sections.

        Raises:
            ProductEvaluationOutcomeErrorV2: If the target is invalid,
                cross-run, cross-side, stale, or unsupported.

        Notes:
            ``render_text()`` / ``narrate()`` are presentation helpers; product
            code should parse the structured fields. No EvidenceGraph is
            fabricated when the run did not capture one.
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
        """Replay the sealed run without live dependencies.

        Returns:
            An ``EvaluationRunReplayV2`` report, normally with status
            ``"matched"`` when the capture reproduces its recorded frames.

        Notes:
            Replay does not read the live ledger, invoke a Provider, or call a
            Product Function. A match is deterministic agreement with the
            capture, not source authority or artifact authentication.
        """

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
    """Open a sealed Product V2 run through the user-facing outcome facade.

    Args:
        run: Integrity-valid ``EvaluationRunV2`` returned by a Product Query.

    Returns:
        A ``ProductEvaluationOutcomeV2`` with named baseline/effective and
        optional candidate views.

    Raises:
        ProductEvaluationOutcomeErrorV2: If the run or a nested seal is stale
            or malformed.

    Examples:
        >>> outcome = outcome_from_run_v2(query.plan(profile=profile).run())
        >>> row = outcome.effective.rows[0]
        >>> data = outcome.explain(row)
        >>> outcome.replay().status
        'matched'

    Notes:
        This is the functional spelling of
        ``ProductEvaluationOutcomeV2.from_run(run)``.
    """

    return ProductEvaluationOutcomeV2.from_run(run)


__all__ = [
    "ProductEvaluationOutcomeErrorV2",
    "ProductEvaluationOutcomeV2",
    "outcome_from_run_v2",
]
