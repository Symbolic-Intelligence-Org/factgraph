"""Fault-injection characterization for the broad boundary in goal_plan_v1_runtime.

``execute_goal_plan_invocation_v1`` fails closed: an unexpected engine,
provider or resolver fault must become a typed ``GoalPlanFailureV1`` with
``execution="failed"``, never a successful-looking zero-row ``GoalPlanRunV1``.
The opaque detail digest must also stay stable and must not serialize the
exception text.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from factgraph.application import goal_plan_v1_runtime
from factgraph.application.goal_plan_v1_runtime import (
    GoalPlanFailureV1,
    GoalPlanInvocationV1,
    GoalPlanRuntimeError,
    execute_goal_plan_invocation_v1,
)


class _BoundaryFault(Exception):
    """Custom, non-domain failure injected into the goal execution boundary."""


def _invocation(scenario: object | None = None) -> GoalPlanInvocationV1:
    """Minimal structural invocation: only the fields the failure path reads."""
    plan = SimpleNamespace(
        plan_digest="sha256:" + ("0" * 64),
        expectations=(),
    )
    profile = SimpleNamespace(kind="native_deterministic_v1")
    return GoalPlanInvocationV1(
        _graph=None,  # type: ignore[arg-type]
        plan=plan,  # type: ignore[arg-type]
        primary=SimpleNamespace(),  # type: ignore[arg-type]
        profile=profile,  # type: ignore[arg-type]
        scenario=scenario,  # type: ignore[arg-type]
        evidence_scope=SimpleNamespace(),  # type: ignore[arg-type]
    )


class GoalPlanExecutionBoundaryTests(unittest.TestCase):
    """src/factgraph/application/goal_plan_v1_runtime.py: fail-closed execution boundary."""

    def test_unexpected_fault_becomes_a_typed_failure_not_an_empty_run(self) -> None:
        invocation = _invocation()

        with patch.object(
            goal_plan_v1_runtime,
            "_assert_invocation_matches_plan",
            side_effect=_BoundaryFault("injected engine failure"),
        ):
            outcome = execute_goal_plan_invocation_v1(invocation)

        # Not reported as success: a failure DTO, never a zero-row run.
        self.assertIsInstance(outcome, GoalPlanFailureV1)
        assert isinstance(outcome, GoalPlanFailureV1)
        self.assertEqual(outcome.code, "GOAL_EXECUTION_FAILED")
        self.assertEqual(outcome.assessment.execution, "failed")
        self.assertEqual(outcome.assessment.explain, "unavailable")
        self.assertEqual(outcome.assessment.replay, "unavailable")
        self.assertIsNone(outcome.assessment.result_digest)
        self.assertEqual(outcome.assessment.completeness, "unknown")
        self.assertEqual(outcome.assessment.capability, "unresolved")
        # Preserved detail: an opaque digest is carried, not raw exception text.
        self.assertTrue(outcome.detail_digest.startswith("sha256:"))
        self.assertNotIn("injected engine failure", outcome.detail_digest)
        self.assertIs(outcome.plan, invocation.plan)

    def test_detail_digest_distinguishes_the_exception_type(self) -> None:
        invocation = _invocation()

        def _run(side_effect: BaseException) -> GoalPlanFailureV1:
            with patch.object(
                goal_plan_v1_runtime, "_assert_invocation_matches_plan", side_effect=side_effect
            ):
                outcome = execute_goal_plan_invocation_v1(invocation)
            assert isinstance(outcome, GoalPlanFailureV1)
            return outcome

        first = _run(_BoundaryFault("a"))
        second = _run(LookupError("b"))
        self.assertNotEqual(first.detail_digest, second.detail_digest)
        self.assertEqual(second.code, "GOAL_EXECUTION_FAILED")

    def test_domain_error_still_uses_its_own_typed_code(self) -> None:
        invocation = _invocation()

        with patch.object(
            goal_plan_v1_runtime,
            "_assert_invocation_matches_plan",
            side_effect=GoalPlanRuntimeError("splice", code="GOAL_INVOCATION_PLAN_SPLICE"),
        ):
            outcome = execute_goal_plan_invocation_v1(invocation)

        assert isinstance(outcome, GoalPlanFailureV1)
        self.assertEqual(outcome.code, "GOAL_INVOCATION_PLAN_SPLICE")
        self.assertEqual(outcome.assessment.contract_validity, "invalid")

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        invocation = _invocation()

        with patch.object(
            goal_plan_v1_runtime, "_assert_invocation_matches_plan", side_effect=KeyboardInterrupt
        ):
            with self.assertRaises(KeyboardInterrupt):
                execute_goal_plan_invocation_v1(invocation)

    def test_non_invocation_input_still_raises_the_contract_error(self) -> None:
        with self.assertRaises(GoalPlanRuntimeError):
            execute_goal_plan_invocation_v1(object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
