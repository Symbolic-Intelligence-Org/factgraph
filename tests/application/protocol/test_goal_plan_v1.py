from __future__ import annotations

from dataclasses import replace

import pytest

from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.goal_plan_v1 import (
    ContainsRowExpectationV1,
    CountEqExpectationV1,
    ExactLocalAbsenceExpectationV1,
    ExistsExpectationV1,
    GoalExpectationOutcomeV1,
    GoalPlanV1,
    GoalResultRowV1,
    GoalResultV1,
    GoalRowExpectationV1,
    GoalSelectionV1,
    GoalTargetRefV1,
    GoalTechnicalAssessmentV1,
    GoalValueV1,
    SetEqualsExpectationV1,
)
from factgraph.application.protocol.scenario_v1 import (
    ExactLocalClosureTargetV1,
    ScenarioValueV1,
)


def _token(character: str) -> str:
    return f"sha256:{character * 64}"


def _target() -> GoalTargetRefV1:
    return GoalTargetRefV1("policy", "hr.older_coworker", "3", _token("a"))


def _value(value: int) -> GoalValueV1:
    return GoalValueV1("int", value)


def _row(*, age: int = 22, alias: str = "age") -> GoalResultRowV1:
    return GoalResultRowV1(((alias, _value(age)),))


def _plan(*, expectations: tuple[object, ...] = ()) -> GoalPlanV1:
    return GoalPlanV1(
        _target(),
        _token("b"),
        "rows",
        (GoalSelectionV1("age", "int"),),
        expectations=expectations,  # type: ignore[arg-type]
    )


def test_plan_is_deterministic_and_validates_typed_expectation_surface() -> None:
    expected = GoalRowExpectationV1((("age", _value(22)),))
    contains = ContainsRowExpectationV1("has_22", expected)
    plan_a = _plan(expectations=(contains, CountEqExpectationV1("count", 1)))
    plan_b = _plan(expectations=(contains, CountEqExpectationV1("count", 1)))

    assert plan_a.plan_digest == plan_b.plan_digest
    assert plan_a.expectations[0].expectation_digest.startswith("sha256:")

    with pytest.raises(ProtocolShapeError, match="unknown selected alias"):
        _plan(
            expectations=(
                ContainsRowExpectationV1(
                    "wrong",
                    GoalRowExpectationV1((("other", _value(22)),)),
                ),
            )
        )

    with pytest.raises(ProtocolShapeError, match="value tag"):
        _plan(
            expectations=(
                ContainsRowExpectationV1(
                    "wrong_tag",
                    GoalRowExpectationV1((("age", GoalValueV1("string", "22")),)),
                ),
            )
        )

    with pytest.raises(ProtocolShapeError, match="must differ"):
        GoalPlanV1(
            _target(),
            _token("b"),
            "rows",
            (GoalSelectionV1("age", "int"),),
            candidate_target=_target(),
        )


def test_result_uses_unique_canonical_semantic_rows_not_bag_semantics() -> None:
    plan = _plan()
    first = _row(age=22)
    second = _row(age=35)
    result = GoalResultV1(plan.plan_digest, "rows", "complete", (second, first))

    assert tuple(row.values[0][1].value for row in result.rows) == (22, 35)
    assert all(row.anchor is not None for row in result.rows)
    assert result.summary_anchor is not None
    assert result.summary_anchor.semantic_row_digests == tuple(
        row.semantic_row_digest for row in result.rows
    )

    with pytest.raises(ProtocolShapeError, match="duplicate semantic rows"):
        GoalResultV1(plan.plan_digest, "rows", "complete", (first, first))


def test_result_rejects_cross_plan_row_anchor_and_summary_splice() -> None:
    plan = _plan()
    other_plan = GoalPlanV1(
        _target(),
        _token("c"),
        "rows",
        (GoalSelectionV1("age", "int"),),
    )
    row = _row().anchored(plan.plan_digest)

    with pytest.raises(ProtocolShapeError, match="belongs to another plan"):
        GoalResultV1(other_plan.plan_digest, "rows", "complete", (row,))

    result = GoalResultV1(plan.plan_digest, "rows", "complete", (_row(),))
    assert result.summary_anchor is not None
    with pytest.raises(ProtocolShapeError, match="summary anchor"):
        GoalResultV1(
            plan.plan_digest,
            "rows",
            "complete",
            (_row(),),
            summary_anchor=replace(
                result.summary_anchor,
                completeness="incomplete",
            ),
        )


def test_exists_and_count_have_no_false_empty_result_semantics() -> None:
    plan = _plan()

    exists = GoalResultV1(plan.plan_digest, "exists", "incomplete", (_row(),), exists_value="true")
    assert exists.exists_value == "true"
    with pytest.raises(ProtocolShapeError, match="false exists"):
        GoalResultV1(plan.plan_digest, "exists", "incomplete", (), exists_value="false")
    with pytest.raises(ProtocolShapeError, match="undetermined exists"):
        GoalResultV1(
            plan.plan_digest, "exists", "incomplete", (_row(),), exists_value="undetermined"
        )

    counted = GoalResultV1(plan.plan_digest, "count", "complete", (_row(),), count_value=1)
    assert counted.count_value == 1
    with pytest.raises(ProtocolShapeError, match="count value requires complete"):
        GoalResultV1(plan.plan_digest, "count", "incomplete", (_row(),), count_value=1)
    with pytest.raises(ProtocolShapeError, match="complete count"):
        GoalResultV1(plan.plan_digest, "count", "complete", (), count_value=None)

    # A complete no-row result can satisfy an explicit `exists=False`
    # expectation; it must not be rejected merely because there is no positive
    # row witness.  The runner checks the expected boolean against the plan.
    absent = ExistsExpectationV1("absent", False)
    absent_plan = _plan(expectations=(absent,))
    absent_outcome = GoalExpectationOutcomeV1(
        "absent", absent.expectation_digest, "exists", "satisfied"
    )
    GoalResultV1(
        absent_plan.plan_digest,
        "exists",
        "complete",
        (),
        exists_value="false",
        expectation_outcomes=(absent_outcome,),
    )


def test_exact_local_absence_is_resolver_targeted_not_query_row_derived() -> None:
    exact = ExactLocalAbsenceExpectationV1(
        "no_22",
        ExactLocalClosureTargetV1(
            "member",
            "idref_v1:Person:alice",
            "person:skills",
            ScenarioValueV1("string", "sql"),
        ),
    )
    plan = GoalPlanV1(
        _target(),
        _token("b"),
        "rows",
        (GoalSelectionV1("age", "int"),),
        scenario_request_digest=_token("f"),
        expectations=(exact,),
    )

    satisfied = GoalExpectationOutcomeV1(
        "no_22", exact.expectation_digest, "exact_local_absence", "satisfied"
    )
    result = GoalResultV1(
        plan.plan_digest,
        "rows",
        "complete",
        (_row(age=35),),
        expectation_outcomes=(satisfied,),
    )
    assert result.expectation_outcomes == (satisfied,)

    # The Scenario closure, not selected-row enumeration, supplies the
    # absence basis.  A resource-limited projection can therefore still carry
    # a satisfied exact-local-absence outcome when its closure is sealed.
    GoalResultV1(
        plan.plan_digest,
        "rows",
        "resource_limited",
        (_row(age=35),),
        expectation_outcomes=(satisfied,),
    )

    rejected = GoalExpectationOutcomeV1(
        "no_22",
        exact.expectation_digest,
        "exact_local_absence",
        "not_satisfied",
    )
    assert not rejected.matched_semantic_row_digests

    # A complete selected-row result does not magically make an unavailable
    # closure decidable; this is a separate assessment axis.
    underdetermined = GoalExpectationOutcomeV1(
        "no_22", exact.expectation_digest, "exact_local_absence", "underdetermined"
    )
    GoalResultV1(
        plan.plan_digest,
        "rows",
        "complete",
        (_row(age=35),),
        expectation_outcomes=(underdetermined,),
    )

    with pytest.raises(ProtocolShapeError, match="requires a Scenario request digest"):
        _plan(expectations=(exact,))


def test_set_equals_is_an_exact_set_and_never_a_bag() -> None:
    expected_22 = GoalRowExpectationV1((("age", _value(22)),))
    expected_35 = GoalRowExpectationV1((("age", _value(35)),))
    equality = SetEqualsExpectationV1("only", (expected_35, expected_22))
    plan = _plan(expectations=(equality,))

    assert tuple(row.row_digest for row in equality.rows) == tuple(
        sorted(row.row_digest for row in equality.rows)
    )
    with pytest.raises(ProtocolShapeError, match="duplicate semantic rows"):
        SetEqualsExpectationV1("bag", (expected_22, expected_22))

    outcome = GoalExpectationOutcomeV1(
        "only", equality.expectation_digest, "set_equals", "satisfied"
    )
    GoalResultV1(
        plan.plan_digest,
        "set",
        "complete",
        (_row(age=35), _row(age=22)),
        expectation_outcomes=(outcome,),
    )


def test_value_storage_is_canonical_and_technical_assessment_is_not_product_verdict() -> None:
    assert GoalValueV1("bytes", "YWJj").value == "YWJj"
    with pytest.raises(ProtocolShapeError, match="canonical bytes"):
        GoalValueV1("bytes", "YWJj=")
    with pytest.raises(ProtocolShapeError, match="canonical float64"):
        GoalValueV1("float64", "0xABCDEFABCDEFABCD")

    plan = _plan()
    result = GoalResultV1(plan.plan_digest, "rows", "complete", (_row(),))
    assessment = GoalTechnicalAssessmentV1(
        plan.plan_digest,
        result.result_digest,
        "not_requested",
        "succeeded",
        "not_requested",
        "complete",
        "not_requested",
        "available",
        "unavailable",
        contract_validity="valid",
        exact_local_closure="not_requested",
        capability="supported",
    )
    assert assessment.assessment_digest.startswith("sha256:")

    with pytest.raises(ProtocolShapeError, match="successful technical assessment"):
        GoalTechnicalAssessmentV1(
            plan.plan_digest,
            None,
            "not_requested",
            "succeeded",
            "not_requested",
            "complete",
            "not_requested",
            "available",
            "unavailable",
        )
    with pytest.raises(ProtocolShapeError, match="only successful technical assessment"):
        GoalTechnicalAssessmentV1(
            plan.plan_digest,
            result.result_digest,
            "unresolved",
            "failed",
            "unresolved",
            "unknown",
            "not_requested",
            "unavailable",
            "unavailable",
        )


def test_completeness_and_assessment_axes_do_not_overload_one_another() -> None:
    plan = _plan()
    result = GoalResultV1(plan.plan_digest, "rows", "resource_limited", (_row(),))
    assert result.completeness == "resource_limited"
    with pytest.raises(ProtocolShapeError, match="outside this protocol"):
        GoalResultV1(plan.plan_digest, "rows", "partial", (_row(),))  # type: ignore[arg-type]

    assessment = GoalTechnicalAssessmentV1(
        plan.plan_digest,
        result.result_digest,
        "resolved",
        "succeeded",
        "not_requested",
        "resource_limited",
        "underdetermined",
        "unavailable",
        "available",
        contract_validity="valid",
        exact_local_closure="required",
        capability="supported",
    )
    assert assessment.exact_local_closure == "required"

    with pytest.raises(ProtocolShapeError, match="resolved exact-local closure"):
        GoalTechnicalAssessmentV1(
            plan.plan_digest,
            result.result_digest,
            "not_requested",
            "succeeded",
            "not_requested",
            "resource_limited",
            "not_requested",
            "unavailable",
            "available",
            exact_local_closure="resolved",
        )
    with pytest.raises(ProtocolShapeError, match="rejected capability"):
        GoalTechnicalAssessmentV1(
            plan.plan_digest,
            result.result_digest,
            "resolved",
            "succeeded",
            "not_requested",
            "resource_limited",
            "not_requested",
            "unavailable",
            "available",
            capability="rejected",
        )
