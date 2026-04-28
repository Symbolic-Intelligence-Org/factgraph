from __future__ import annotations

import unittest

from kernel.application import (
    DerivationRuntimeError,
    accept_derivation_candidate_sets,
    build_schema_index,
    evaluate_derivation_plans,
)
from kernel.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DerivationAcceptRequest,
    DerivationEvaluateRequest,
    ProtocolShapeError,
)
from kernel.core.store import Store
from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity(primary_key=True)
    nickname: str = Field(cardinality="single")


def _build_store() -> tuple[Store, object]:
    schema_ir = compile_schema_from_classes([Person])
    return Store(schema_ir), build_schema_index(schema_ir)


class DerivationDTOValidationTests(unittest.TestCase):
    def test_compiled_head_call_requires_target_pred_id(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            CompiledHeadCall(target_pred_id="", head_var_names=("x",))

    def test_compiled_head_call_head_var_names_must_be_tuple(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            CompiledHeadCall(target_pred_id="t:exists", head_var_names=["x"])  # type: ignore[arg-type]

    def test_compiled_plan_requires_non_empty_heads(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            CompiledDerivationPlan(
                derivation_id="d1",
                version="1.0",
                body_ir=[("pred", "t:exists", ["$x"])],
                heads=(),
            )

    def test_compiled_plan_body_confidence_range(self) -> None:
        head = CompiledHeadCall(target_pred_id="t:exists", head_var_names=("x",))
        with self.assertRaises(ProtocolShapeError):
            CompiledDerivationPlan(
                derivation_id="d1",
                version="1.0",
                body_ir=[("pred", "t:exists", ["$x"])],
                heads=(head,),
                body_confidence=1.5,
            )

    def test_evaluate_request_rejects_empty_plans(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DerivationEvaluateRequest(plans=())

    def test_evaluate_request_engine_literal(self) -> None:
        head = CompiledHeadCall(target_pred_id="t:exists", head_var_names=("x",))
        plan = CompiledDerivationPlan(
            derivation_id="d1",
            version="1.0",
            body_ir=[("pred", "t:exists", ["$x"])],
            heads=(head,),
        )
        with self.assertRaises(ProtocolShapeError):
            DerivationEvaluateRequest(plans=(plan,), engine="lambda")  # type: ignore[arg-type]

    def test_accept_request_idempotent_flag_is_bool(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DerivationAcceptRequest(idempotent_duplicate_ok="yes")  # type: ignore[arg-type]


class AcceptDerivationSmokeTests(unittest.TestCase):
    def test_accept_many_with_empty_list_returns_empty(self) -> None:
        store, _ = _build_store()
        accept_request = DerivationAcceptRequest()
        result = accept_derivation_candidate_sets([], accept_request, store=store)
        self.assertEqual(result, [])


class EvaluateDerivationSmokeTests(unittest.TestCase):
    def test_evaluator_returns_list_for_unmatched_body(self) -> None:
        # body_ir matches no facts -> evaluator should return empty CandidateSet list
        # (or list containing an empty CandidateSet, depending on engine_evaluate behavior)
        store, _ = _build_store()
        head = CompiledHeadCall(target_pred_id="Person:exists", head_var_names=("x",))
        plan = CompiledDerivationPlan(
            derivation_id="derived:Person:exists",
            version="0.1",
            body_ir=[("pred", "Person:exists", ["$x"])],
            heads=(head,),
        )
        request = DerivationEvaluateRequest(plans=(plan,))
        result = evaluate_derivation_plans(request, store=store)
        self.assertIsInstance(result, list)
        for cs in result:
            self.assertTrue(hasattr(cs, "candidates"))


class DerivationRuntimeErrorTests(unittest.TestCase):
    def test_to_error_dto_round_trip(self) -> None:
        err = DerivationRuntimeError(
            "boom",
            code="DERIVATION_PLAN_FAILED",
            path=("plan", "0"),
            details={"hint": "x"},
        )
        dto = err.to_error_dto()
        self.assertEqual(dto.code, "DERIVATION_PLAN_FAILED")
        self.assertEqual(dto.path, ("plan", "0"))


if __name__ == "__main__":
    unittest.main()
