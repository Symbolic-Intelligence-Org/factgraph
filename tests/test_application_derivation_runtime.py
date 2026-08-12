from __future__ import annotations

import unittest
from dataclasses import dataclass
from unittest.mock import Mock, patch

from factgraph.application import (
    DerivationRuntimeError,
    accept_derivation_candidate_set,
    accept_derivation_candidate_sets,
    build_schema_index,
    evaluate_derivation_plans,
)
from factgraph.application.derivation_runtime import _attach_run_id
from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DerivationAcceptRequest,
    DerivationEvaluateRequest,
    ProtocolShapeError,
)
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.store import Store
from factgraph.core.store.types import EngineExtBase
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


@dataclass(frozen=True)
class _TestEngineExt(EngineExtBase):
    label: str = "test"


def _make_candidate(*, run_id: str, target: str = "t:p") -> CandidateSet:
    digest = "sha256:" + ("0" * 64)
    return CandidateSet(
        derivation_id="d1",
        derivation_version="1.0",
        run_id=run_id,
        target=target,
        key_tuple_digest=digest,
        tup_digest=None,
        payload={"terms": []},
        support_digest=digest,
        support_kind="native",
        generated_at=0,
        state="proposed",
    )


class Person(Entity):
    name: str = Identity()
    nickname: str = Field()


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


class CompiledPlanParityTests(unittest.TestCase):
    """Commit 2a: head_spec / engine_ext / accept-options parity."""

    def _head(self) -> CompiledHeadCall:
        return CompiledHeadCall(target_pred_id="t:exists", head_var_names=("x",))

    def test_head_spec_with_single_head_is_accepted(self) -> None:
        plan = CompiledDerivationPlan(
            derivation_id="d1",
            version="1.0",
            body_ir=[("pred", "t:exists", ["$x"])],
            heads=(self._head(),),
            head_spec={"kind": "single", "vars": ["x"]},
        )
        self.assertEqual(plan.head_spec, {"kind": "single", "vars": ["x"]})

    def test_head_spec_rejects_multi_head_plans(self) -> None:
        head_a = CompiledHeadCall(target_pred_id="t:a", head_var_names=("x",))
        head_b = CompiledHeadCall(target_pred_id="t:b", head_var_names=("x",))
        with self.assertRaises(ProtocolShapeError):
            CompiledDerivationPlan(
                derivation_id="d1",
                version="1.0",
                body_ir=[("pred", "t:exists", ["$x"])],
                heads=(head_a, head_b),
                head_spec={"kind": "multi"},
            )

    def test_head_spec_must_be_dict(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            CompiledDerivationPlan(
                derivation_id="d1",
                version="1.0",
                body_ir=[("pred", "t:exists", ["$x"])],
                heads=(self._head(),),
                head_spec=["not", "a", "dict"],  # type: ignore[arg-type]
            )

    def test_engine_ext_must_be_engine_ext_base(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            CompiledDerivationPlan(
                derivation_id="d1",
                version="1.0",
                body_ir=[("pred", "t:exists", ["$x"])],
                heads=(self._head(),),
                engine_ext="not-an-engine-ext",  # type: ignore[arg-type]
            )

    def test_engine_ext_accepts_engine_ext_base_instance(self) -> None:
        plan = CompiledDerivationPlan(
            derivation_id="d1",
            version="1.0",
            body_ir=[("pred", "t:exists", ["$x"])],
            heads=(self._head(),),
            engine_ext=_TestEngineExt(label="hello"),
        )
        assert plan.engine_ext is not None
        self.assertEqual(plan.engine_ext.label, "hello")  # type: ignore[attr-defined]


class DerivationAcceptRequestParityTests(unittest.TestCase):
    def test_accept_options_fields_round_trip(self) -> None:
        req = DerivationAcceptRequest(
            approved_by="alice",
            note="test run",
            dry_run=True,
            identity_override={"by": "alice"},
        )
        self.assertEqual(req.approved_by, "alice")
        self.assertEqual(req.note, "test run")
        self.assertTrue(req.dry_run)
        self.assertEqual(req.identity_override, {"by": "alice"})

    def test_dry_run_must_be_bool(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DerivationAcceptRequest(dry_run="yes")  # type: ignore[arg-type]

    def test_identity_override_must_be_dict(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DerivationAcceptRequest(identity_override=("not", "a", "dict"))  # type: ignore[arg-type]

    def test_approved_by_rejects_empty_string(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DerivationAcceptRequest(approved_by="")


class RunIdPropagationTests(unittest.TestCase):
    """Commit 2a D4: shared run_id propagation via dataclasses.replace."""

    def test_attach_run_id_rewrites_each_candidate(self) -> None:
        before = [_make_candidate(run_id="orig-1"), _make_candidate(run_id="orig-2")]
        after = _attach_run_id(before, run_id="shared-rid")
        self.assertEqual([c.run_id for c in after], ["shared-rid", "shared-rid"])
        self.assertNotEqual(before[0].candidate_id, after[0].candidate_id)
        self.assertTrue(after[0].candidate_id.startswith("cand_v2:"))
        # Other fields preserved
        self.assertEqual(before[0].target, after[0].target)
        self.assertEqual(before[0].key_tuple_digest, after[0].key_tuple_digest)
        # Originals untouched (frozen dataclass + replace returns new objects)
        self.assertEqual([c.run_id for c in before], ["orig-1", "orig-2"])


class AcceptDerivationSmokeTests(unittest.TestCase):
    def test_accept_many_with_empty_list_returns_empty(self) -> None:
        store, _ = _build_store()
        accept_request = DerivationAcceptRequest()
        result = accept_derivation_candidate_sets([], accept_request, store=store)
        self.assertEqual(result, [])

    def test_single_accept_delegates_to_store_owned_seam(self) -> None:
        store = Mock()
        expected = object()
        candidate = _make_candidate(run_id="single")
        request = DerivationAcceptRequest(
            approved_by="alice",
            note="reviewed",
            dry_run=True,
            identity_override={"name": "alice"},
            meta={"request_id": "req-1"},
        )

        with patch(
            "factgraph.application.derivation_runtime."
            "_store_accept._accept_store_candidate_as_derived_rule",
            return_value=expected,
        ) as accept_with_provenance:
            result = accept_derivation_candidate_set(
                candidate,
                request,
                store=store,
                derived_rule_id="business.rule",
                derived_rule_version="v1",
            )

        self.assertIs(result, expected)
        kwargs = accept_with_provenance.call_args.kwargs
        self.assertIs(accept_with_provenance.call_args.args[0], store)
        self.assertEqual(kwargs["derivation_id"], "business.rule")
        self.assertEqual(kwargs["version"], "v1")
        self.assertIs(kwargs["candidate_set"], candidate)
        self.assertEqual(kwargs["options"].approved_by, "alice")
        self.assertEqual(kwargs["options"].note, "reviewed")
        self.assertTrue(kwargs["options"].dry_run)
        self.assertEqual(kwargs["options"].identity_override, {"name": "alice"})
        self.assertEqual(kwargs["options"].actor_meta, {"request_id": "req-1"})

    def test_batch_accept_propagates_per_item_intent_to_store(self) -> None:
        store = Mock()
        store.accept_many.return_value = [{"ok": True}]
        candidates = [_make_candidate(run_id="batch")]
        request = DerivationAcceptRequest(
            accept_mode="atomic",
            idempotent_duplicate_ok=False,
            approved_by="alice",
            note="reviewed",
            identity_override={"name": "alice"},
            meta={"request_id": "req-2"},
        )

        result = accept_derivation_candidate_sets(candidates, request, store=store)

        self.assertEqual(result, [{"ok": True}])
        batch = store.accept_many.call_args.args[0]
        self.assertEqual(len(batch), 1)
        self.assertIs(batch[0].candidate_set, candidates[0])
        self.assertEqual(batch[0].approved_by, "alice")
        self.assertEqual(batch[0].note, "reviewed")
        self.assertEqual(batch[0].identity_override, {"name": "alice"})
        self.assertEqual(batch[0].actor_meta, {"request_id": "req-2"})
        self.assertEqual(store.accept_many.call_args.kwargs["mode"], "atomic")
        self.assertFalse(store.accept_many.call_args.kwargs["idempotent_duplicate_ok"])

    def test_batch_accept_rejects_dry_run(self) -> None:
        store = Mock()
        with self.assertRaisesRegex(DerivationRuntimeError, "dry_run"):
            accept_derivation_candidate_sets(
                [_make_candidate(run_id="batch")],
                DerivationAcceptRequest(dry_run=True),
                store=store,
            )
        store.accept_many.assert_not_called()

    def test_batch_accept_rejects_multi_output_identity_override(self) -> None:
        store = Mock()
        with self.assertRaisesRegex(DerivationRuntimeError, "ambiguous"):
            accept_derivation_candidate_sets(
                [_make_candidate(run_id="one"), _make_candidate(run_id="two")],
                DerivationAcceptRequest(identity_override={"name": "alice"}),
                store=store,
            )
        store.accept_many.assert_not_called()


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
