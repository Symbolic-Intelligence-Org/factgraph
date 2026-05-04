"""Non-native Diagnose runtime tests (§8 Step 4 representability gate + Step 5 souffle dispatch)."""
from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from kernel.application import (
    build_schema_index,
    diagnose_derivation_binding,
    entity_info,
    field_predicate,
)
from kernel.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DiagnoseRequest,
)
from kernel.core.store import Store
from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")


def _build_store() -> tuple[Store, Any]:
    schema_ir = compile_schema_from_classes([Person])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


def _build_plan(
    body_ir: list[Any],
    target_pred_id: str,
    head_var_names: tuple[str, ...] = ("$p",),
    *,
    head_spec: dict[str, Any] | None = None,
) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="diagnose-non-native-test",
        version="1.0",
        body_ir=body_ir,
        heads=(
            CompiledHeadCall(
                target_pred_id=target_pred_id,
                head_var_names=head_var_names,
            ),
        ),
        head_spec=head_spec,
    )


def _exists_age_body(index: Any) -> tuple[list[Any], str]:
    info = entity_info(index, "Person")
    age_pred = field_predicate(index, "Person", "age").pred_id
    body: list[Any] = [
        ("pred", info.exists_predicate_id, ["$p"]),
        ("pred", age_pred, ["$p", "$age"]),
    ]
    return body, info.exists_predicate_id


class NonNativeRepresentabilityGateTests(unittest.TestCase):
    def _request(
        self,
        engine: str,
        *,
        binding: tuple[tuple[str, object], ...] = (),
        head_var_names: tuple[str, ...] = ("$p",),
        head_spec: dict[str, Any] | None = None,
    ) -> tuple[Store, DiagnoseRequest]:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        plan = _build_plan(
            body,
            target,
            head_var_names=head_var_names,
            head_spec=head_spec,
        )
        request = DiagnoseRequest(plan=plan, binding=binding, engine=engine)  # type: ignore[arg-type]
        return store, request

    def test_problog_body_only_binding_returns_unsupported_before_dispatch(self) -> None:
        store, request = self._request("problog", binding=(("$age", 25),))

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE")
        self.assertEqual(result.errors[0].details["body_only_variables"], ["$age"])

    def test_pyreason_body_only_binding_returns_unsupported_before_dispatch(self) -> None:
        store, request = self._request("pyreason", binding=(("$age", 25),))

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE")

    def test_problog_entity_target_plan_returns_unsupported_before_dispatch(self) -> None:
        store, request = self._request(
            "problog",
            head_spec={"callee_kind": "entity_type", "entity_type": "Person"},
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)
        self.assertEqual(result.errors[0].code, "ENTITY_TARGET_NOT_REPRESENTABLE")

    def test_pyreason_entity_target_plan_returns_unsupported_before_dispatch(self) -> None:
        store, request = self._request(
            "pyreason",
            head_spec={"callee_kind": "entity_type", "entity_type": "Person"},
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)
        self.assertEqual(result.errors[0].code, "ENTITY_TARGET_NOT_REPRESENTABLE")

    def test_pyreason_accumulates_entity_and_body_only_errors(self) -> None:
        store, request = self._request(
            "pyreason",
            binding=(("$age", 25),),
            head_spec={"callee_kind": "entity_type", "entity_type": "Person"},
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(
            [error.code for error in result.errors],
            ["ENTITY_TARGET_NOT_REPRESENTABLE", "BINDING_NOT_REPRESENTABLE"],
        )
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)

    def test_problog_head_only_binding_is_representable_for_later_dispatch(self) -> None:
        store, request = self._request("problog", binding=(("$p", "person-1"),))

        with self.assertRaises(NotImplementedError):
            diagnose_derivation_binding(request, store=store)

    def test_pyreason_bare_head_var_treats_requested_var_as_body_only(self) -> None:
        store, request = self._request(
            "pyreason",
            binding=(("$p", "person-1"),),
            head_var_names=("p",),
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE")
        self.assertEqual(result.errors[0].details["body_only_variables"], ["$p"])


def _make_souffle_candidate(
    *,
    candidate_key: str = "candk_v2:diagnose-souffle-test",
    support_digest: str = "sha256:" + ("a" * 64),
    target: str = "Person:exists",
) -> Any:
    """Step 5 fixture: minimal CandidateSet shaped like a Souffle output."""
    from kernel.core.derivation.candidates import CandidateSet

    key_digest = "sha256:" + ("0" * 64)
    return CandidateSet(
        derivation_id="diagnose-souffle-test",
        derivation_version="1.0",
        run_id="souffle-run",
        target=target,
        key_tuple_digest=key_digest,
        tup_digest=None,
        payload={"terms": []},
        support_digest=support_digest,
        support_kind="souffle_witness_v1",
        generated_at=0,
        state="generated",
        candidate_key=candidate_key,
    )


def _make_support_artifact(
    *,
    binding_items: tuple[tuple[str, Any], ...] = (),
    pred_witness_keys: tuple[str, ...] = ("b0.a0:Person:exists",),
    kind: str = "souffle_witness_v1",
) -> Any:
    """Step 5 fixture: minimal SupportArtifact for souffle path mocking."""
    from kernel.core.store._support import PredWitness, SupportArtifact

    return SupportArtifact(
        kind=kind,
        root_result_kind="fact",
        binding_items=binding_items,
        pred_witnesses=tuple(
            sorted(
                (PredWitness(pred_atom_key=key, asrt_ids=()) for key in pred_witness_keys),
                key=lambda row: row.pred_atom_key,
            )
        ),
    )


class SouffleDiagnoseDispatchTests(unittest.TestCase):
    """§8 Step 5: Souffle dispatch via three-bucket classification (audit C4).

    Tests mock ``evaluate_derivation_plans`` and ``_lookup_support_artifact`` at
    the diagnose runtime module level so they exercise the dispatch contract
    without requiring the souffle binary to be installed.
    """

    def _build_request(
        self,
        binding: tuple[tuple[str, Any], ...] = (("$p", "person-1"),),
    ) -> tuple[Store, DiagnoseRequest]:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        plan = _build_plan(body, target)
        request = DiagnoseRequest(plan=plan, binding=binding, engine="souffle")
        return store, request

    def test_souffle_passed_with_matched_candidate(self) -> None:
        store, request = self._build_request(binding=(("$p", "person-1"),))
        candidate = _make_souffle_candidate()
        artifact = _make_support_artifact(
            binding_items=(("$p", "person-1"),),
            pred_witness_keys=("b0.a0:Person:exists",),
        )
        with patch(
            "kernel.application.diagnose_runtime.evaluate_derivation_plans",
            return_value=[candidate],
        ), patch(
            "kernel.application.diagnose_runtime._lookup_support_artifact",
            return_value=artifact,
        ):
            result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.matched_binding, (("$p", "person-1"),))
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)

    def test_souffle_failed_no_candidate_when_artifact_does_not_match(self) -> None:
        store, request = self._build_request(binding=(("$p", "person-99"),))
        candidate = _make_souffle_candidate()
        artifact = _make_support_artifact(binding_items=(("$p", "person-1"),))
        with patch(
            "kernel.application.diagnose_runtime.evaluate_derivation_plans",
            return_value=[candidate],
        ), patch(
            "kernel.application.diagnose_runtime._lookup_support_artifact",
            return_value=artifact,
        ):
            result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_kind, "no_candidate")
        self.assertEqual(result.matched_count, 0)
        self.assertIsNone(result.matched_binding)
        self.assertIsNone(result.diagnostic_payload)
        self.assertEqual(result.errors, ())

    def test_souffle_failed_no_candidate_when_evaluator_returns_zero(self) -> None:
        store, request = self._build_request(binding=(("$p", "person-1"),))
        with patch(
            "kernel.application.diagnose_runtime.evaluate_derivation_plans",
            return_value=[],
        ):
            result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_kind, "no_candidate")
        self.assertEqual(result.matched_count, 0)

    def test_souffle_unsupported_when_lookup_miss_only(self) -> None:
        # §7-Diagnose-6: lookup-miss surfaces EVIDENCE_LOOKUP_MISS as observable
        # contract problem, never silent-skipped.
        store, request = self._build_request(binding=(("$p", "person-1"),))
        candidate = _make_souffle_candidate()
        with patch(
            "kernel.application.diagnose_runtime.evaluate_derivation_plans",
            return_value=[candidate],
        ), patch(
            "kernel.application.diagnose_runtime._lookup_support_artifact",
            return_value=None,
        ):
            result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.matched_binding)
        self.assertIsNone(result.diagnostic_payload)
        self.assertEqual(len(result.errors), 1)
        error = result.errors[0]
        self.assertEqual(error.code, "EVIDENCE_LOOKUP_MISS")
        self.assertEqual(error.details["engine"], "souffle")
        self.assertEqual(error.details["support_kind"], "souffle_witness_v1")
        self.assertEqual(error.details["support_digest"], candidate.support_digest)
        self.assertEqual(error.details["candidate_key"], candidate.candidate_key)

    def test_souffle_lookup_miss_outranks_no_candidate(self) -> None:
        # Audit C4 precedence: when match bucket is empty AND lookup-miss bucket
        # is non-empty (even alongside no-match candidates), result is
        # `unsupported` with EVIDENCE_LOOKUP_MISS — NOT silently degraded to
        # `failed_no_candidate`.
        store, request = self._build_request(binding=(("$p", "person-99"),))
        no_match_cand = _make_souffle_candidate(
            candidate_key="candk_v2:no-match",
            support_digest="sha256:" + ("1" * 64),
        )
        miss_cand = _make_souffle_candidate(
            candidate_key="candk_v2:miss",
            support_digest="sha256:" + ("2" * 64),
        )
        no_match_artifact = _make_support_artifact(
            binding_items=(("$p", "person-1"),),
        )

        def _lookup(_store: Store, digest: str) -> Any:
            if digest == no_match_cand.support_digest:
                return no_match_artifact
            return None  # miss_cand is the lookup-miss path

        with patch(
            "kernel.application.diagnose_runtime.evaluate_derivation_plans",
            return_value=[no_match_cand, miss_cand],
        ), patch(
            "kernel.application.diagnose_runtime._lookup_support_artifact",
            side_effect=_lookup,
        ):
            result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.failure_kind)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].code, "EVIDENCE_LOOKUP_MISS")
        self.assertEqual(
            result.errors[0].details["candidate_key"], miss_cand.candidate_key
        )

    def test_souffle_match_wins_over_lookup_miss(self) -> None:
        # Audit C4 precedence: match bucket non-empty → passed, regardless of
        # whether lookup-miss bucket also has entries. Lookup-miss is not
        # surfaced as primary outcome in the passed case.
        store, request = self._build_request(binding=(("$p", "person-1"),))
        match_cand = _make_souffle_candidate(
            candidate_key="candk_v2:match",
            support_digest="sha256:" + ("1" * 64),
        )
        miss_cand = _make_souffle_candidate(
            candidate_key="candk_v2:miss",
            support_digest="sha256:" + ("2" * 64),
        )
        match_artifact = _make_support_artifact(
            binding_items=(("$p", "person-1"),),
        )

        def _lookup(_store: Store, digest: str) -> Any:
            if digest == match_cand.support_digest:
                return match_artifact
            return None

        with patch(
            "kernel.application.diagnose_runtime.evaluate_derivation_plans",
            return_value=[match_cand, miss_cand],
        ), patch(
            "kernel.application.diagnose_runtime._lookup_support_artifact",
            side_effect=_lookup,
        ):
            result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.errors, ())

    def test_souffle_multi_match_primary_by_lowest_branch_index(self) -> None:
        # Per audit C4 + Check 0.C C4: souffle primary key =
        # (branch_index, binding_items, candidate_key). Lower branch_index wins.
        store, request = self._build_request(binding=(("$p", "person-1"),))
        higher_cand = _make_souffle_candidate(
            candidate_key="candk_v2:higher",
            support_digest="sha256:" + ("1" * 64),
        )
        lower_cand = _make_souffle_candidate(
            candidate_key="candk_v2:lower",
            support_digest="sha256:" + ("2" * 64),
        )
        higher_artifact = _make_support_artifact(
            binding_items=(("$p", "person-1"),),
            pred_witness_keys=("b3.a0:Person:exists",),
        )
        lower_artifact = _make_support_artifact(
            binding_items=(("$p", "person-1"),),
            pred_witness_keys=("b1.a0:Person:exists",),
        )

        def _lookup(_store: Store, digest: str) -> Any:
            if digest == higher_cand.support_digest:
                return higher_artifact
            return lower_artifact

        with patch(
            "kernel.application.diagnose_runtime.evaluate_derivation_plans",
            return_value=[higher_cand, lower_cand],
        ), patch(
            "kernel.application.diagnose_runtime._lookup_support_artifact",
            side_effect=_lookup,
        ):
            result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 2)
        # Lower branch wins primary; matched_binding is the same in both
        # since both artifacts have the same binding_items, but the chosen
        # candidate is the lower-branch one.
        self.assertEqual(result.matched_binding, (("$p", "person-1"),))

    def test_souffle_never_returns_failure_kind_atom_localized(self) -> None:
        # §7-Diagnose-5: non-native engines never set failure_kind="atom_localized".
        # Verify across multiple souffle outcomes.
        store, request = self._build_request(binding=(("$p", "person-99"),))
        candidate = _make_souffle_candidate()
        artifact = _make_support_artifact(binding_items=(("$p", "person-1"),))
        with patch(
            "kernel.application.diagnose_runtime.evaluate_derivation_plans",
            return_value=[candidate],
        ), patch(
            "kernel.application.diagnose_runtime._lookup_support_artifact",
            return_value=artifact,
        ):
            result = diagnose_derivation_binding(request, store=store)

        # No-match → failed + no_candidate (NOT atom_localized).
        self.assertEqual(result.status, "failed")
        self.assertNotEqual(result.failure_kind, "atom_localized")
        self.assertEqual(result.failure_kind, "no_candidate")


if __name__ == "__main__":
    unittest.main()
