"""Runtime tests for Why-not Universe Diagnose runtime assembly and diagnostics."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from typing import Any
from unittest.mock import patch

import factgraph.application.why_not_runtime as why_not_runtime
from factgraph.application import (
    WhyNotRuntimeError,
    build_schema_index,
    check_why_not_universe,
    entity_info,
    field_predicate,
    resolve_selector,
)
from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DiagnoseConditionLocator,
    DiagnoseResult,
    EntitySelector,
    ErrorDTO,
    WarningDTO,
    WhyNotUniverseRequest,
)
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.rule_ir import RuleRegistry, RuleSpec
from factgraph.core.store import Store
from factgraph.core.store._support import (
    ProofReceipt,
    compute_support_digest,
    normalize_binding_items,
)
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity()
    age: int = Field()
    region: str = Field()


def _build_store() -> tuple[Store, Any]:
    schema_ir = compile_schema_from_classes([Person])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


def _ledger_dump(store: Store) -> bytes:
    return "\n".join(store.ledger._get_connection().iterdump()).encode("utf-8")


def _seed_person(
    store: Store,
    index: Any,
    name: str,
    age: int,
    region: str,
) -> str:
    ref = resolve_selector(
        EntitySelector(entity_type="Person", identity={"name": name}),
        index=index,
    )
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    set_field(store.ledger, info.exists_predicate_id, encoded, [])
    set_field(
        store.ledger,
        info.identity_predicates["name"].pred_id,
        encoded,
        [("string", name)],
    )
    set_field(
        store.ledger,
        field_predicate(index, "Person", "age").pred_id,
        encoded,
        [("int", age)],
    )
    set_field(
        store.ledger,
        field_predicate(index, "Person", "region").pred_id,
        encoded,
        [("string", region)],
    )
    return encoded


def _build_plan(
    body_ir: list[Any],
    target_pred_id: str = "Person:exists",
    head_var_names: tuple[str, ...] = ("$p",),
    *,
    head_spec: dict[str, Any] | None = None,
) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="why-not-test",
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


def _exists_age_region_body(index: Any) -> tuple[list[Any], str]:
    info = entity_info(index, "Person")
    age_pred = field_predicate(index, "Person", "age").pred_id
    region_pred = field_predicate(index, "Person", "region").pred_id
    body: list[Any] = [
        ("pred", info.exists_predicate_id, ["$p"]),
        ("pred", age_pred, ["$p", "$age"]),
        ("pred", region_pred, ["$p", "$region"]),
    ]
    return body, info.exists_predicate_id


def _binding(*items: tuple[str, object]) -> tuple[tuple[str, object], ...]:
    return normalize_binding_items(tuple(items))


def _candidate(
    *,
    candidate_key: str = "candk_v2:why-not-test",
    support_digest: str = "sha256:" + ("a" * 64),
    support_kind: str = "problog_provenance_v1",
    target: str = "Person:exists",
    terms: list[Any] | None = None,
) -> CandidateSet:
    payload_terms = [{"kind": "entity_ref", "value": "person-1"}] if terms is None else terms
    return CandidateSet(
        derivation_id="why-not-test",
        derivation_version="1.0",
        run_id="why-not-run",
        target=target,
        key_tuple_digest="sha256:" + ("0" * 64),
        tup_digest=None,
        payload={"terms": payload_terms},
        support_digest=support_digest,
        support_kind=support_kind,
        generated_at=0,
        state="generated",
        candidate_key=candidate_key,
    )


def _diagnose_no_candidate(
    binding: tuple[tuple[str, object], ...],
    *,
    warnings: tuple[WarningDTO, ...] = (),
) -> DiagnoseResult:
    return DiagnoseResult(
        status="failed",
        requested_binding=binding,
        matched_count=0,
        matched_binding=None,
        failure_kind="no_candidate",
        diagnostic_payload=None,
        errors=(),
        warnings=warnings,
    )


def _diagnose_unsupported(
    binding: tuple[tuple[str, object], ...],
    *,
    errors: tuple[ErrorDTO, ...] | None = None,
) -> DiagnoseResult:
    return DiagnoseResult(
        status="unsupported",
        requested_binding=binding,
        matched_count=None,
        matched_binding=None,
        failure_kind=None,
        diagnostic_payload=None,
        errors=errors
        or (
            ErrorDTO(
                code="ROW_DIAGNOSTIC_UNAVAILABLE",
                message="row diagnostic unavailable",
            ),
        ),
        warnings=(),
    )


class _CountingRuleRegistry(RuleRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.resolve_calls: list[tuple[str, str]] = []

    def resolve(self, rule_id: str, version: str) -> RuleSpec:
        self.resolve_calls.append((rule_id, version))
        return super().resolve(rule_id, version)


class WhyNotRuntimeNativeBoardTests(unittest.TestCase):
    """§7-WhyNot-5 / 7 / 12 / 14: native board and side-effect gates."""

    def test_empty_universe_returns_completed_without_evaluation(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p", "$age")),
            candidate_universe=(),
            engine="native",
        )

        with patch("factgraph.application.why_not_runtime.evaluate_native_where") as mocked:
            result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.passed, ())
        self.assertEqual(result.failed, ())
        mocked.assert_not_called()

    def test_empty_universe_with_ruleref_returns_completed_without_preflight(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        request = WhyNotUniverseRequest(
            plan=_build_plan(
                body + [("ruleref", "person.exists", "1.0", ["$p"])],
                target,
                ("$p", "$age"),
            ),
            candidate_universe=(),
            engine="native",
        )

        with patch("factgraph.application.why_not_runtime.evaluate_native_where") as mocked:
            result = check_why_not_universe(request, store=store, registry=None)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.passed, ())
        self.assertEqual(result.failed, ())
        self.assertEqual(result.errors, ())
        mocked.assert_not_called()

    def test_native_partitions_green_and_red_in_universe_order(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, "alice", 25, "us")
        bob = _seed_person(store, index, "bob", 30, "eu")
        body, target = _exists_age_body(index)
        alice_binding = _binding(("$p", alice), ("$age", 25))
        bob_binding = _binding(("$p", bob), ("$age", 30))
        missing_binding = _binding(("$p", "idref_v1:Person:name:missing"), ("$age", 25))
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p", "$age")),
            candidate_universe=(missing_binding, alice_binding, bob_binding),
            engine="native",
        )

        result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.requested_universe, request.candidate_universe)
        self.assertEqual(result.passed, (alice_binding, bob_binding))
        self.assertEqual(tuple(row.binding for row in result.failed), (missing_binding,))
        self.assertEqual(result.failed[0].diagnostic.status, "failed")
        self.assertEqual(result.failed[0].diagnostic.failure_kind, "atom_localized")
        self.assertEqual(
            result.failed[0].diagnostic.diagnostic_granularity,
            "atom_localized",
        )
        locator = result.failed[0].diagnostic.atom_locator
        assert locator is not None
        self.assertEqual(locator.failed_atom_index, 0)

    def test_native_all_green_partition(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, "alice", 25, "us")
        bob = _seed_person(store, index, "bob", 30, "eu")
        body, target = _exists_age_body(index)
        alice_binding = _binding(("$p", alice), ("$age", 25))
        bob_binding = _binding(("$p", bob), ("$age", 30))
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p", "$age")),
            candidate_universe=(alice_binding, bob_binding),
            engine="native",
        )

        result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.passed, (alice_binding, bob_binding))
        self.assertEqual(result.failed, ())

    def test_native_all_red_partition(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        missing_a = _binding(("$p", "idref_v1:Person:name:missing-a"), ("$age", 25))
        missing_b = _binding(("$p", "idref_v1:Person:name:missing-b"), ("$age", 30))
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p", "$age")),
            candidate_universe=(missing_a, missing_b),
            engine="native",
        )

        result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.passed, ())
        self.assertEqual(tuple(row.binding for row in result.failed), (missing_a, missing_b))

    def test_native_preserves_interleaved_partition_order(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, "alice", 25, "us")
        bob = _seed_person(store, index, "bob", 30, "eu")
        body, target = _exists_age_body(index)
        alice_binding = _binding(("$p", alice), ("$age", 25))
        bob_binding = _binding(("$p", bob), ("$age", 30))
        missing_a = _binding(("$p", "idref_v1:Person:name:missing-a"), ("$age", 25))
        missing_b = _binding(("$p", "idref_v1:Person:name:missing-b"), ("$age", 30))
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p", "$age")),
            candidate_universe=(missing_a, alice_binding, missing_b, bob_binding),
            engine="native",
        )

        result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.passed, (alice_binding, bob_binding))
        self.assertEqual(tuple(row.binding for row in result.failed), (missing_a, missing_b))

    def test_ruleref_without_registry_returns_invalid_request(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        request = WhyNotUniverseRequest(
            plan=_build_plan(
                body + [("ruleref", "person.exists", "1.0", ["$p"])],
                target,
                ("$p", "$age"),
            ),
            candidate_universe=(_binding(("$p", "person-1"), ("$age", 25)),),
            engine="native",
        )

        result = check_why_not_universe(request, store=store, registry=None)

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.passed, ())
        self.assertEqual(result.failed, ())
        self.assertEqual(result.errors[0].code, "REGISTRY_REQUIRED")

    def test_ruleref_unresolvable_returns_invalid_request(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        request = WhyNotUniverseRequest(
            plan=_build_plan(
                body + [("ruleref", "missing.rule", "1.0", ["$p"])],
                target,
                ("$p", "$age"),
            ),
            candidate_universe=(_binding(("$p", "person-1"), ("$age", 25)),),
            engine="native",
        )

        result = check_why_not_universe(
            request,
            store=store,
            registry=_CountingRuleRegistry(),
        )

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_REF_UNRESOLVABLE")

    def test_native_unrepresentable_head_binding_returns_unsupported(self) -> None:
        store, _index = _build_store()
        request = WhyNotUniverseRequest(
            plan=_build_plan([("eq", "$age", 25)], "Person:exists", ("$p",)),
            candidate_universe=(_binding(("$p", "person-1")),),
            engine="native",
        )

        result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.passed, ())
        self.assertEqual(result.failed, ())
        self.assertEqual(result.errors[0].code, "CANDIDATE_BINDING_NOT_REPRESENTABLE")

    def test_native_why_not_leaves_ledger_byte_identical_and_does_not_write(self) -> None:
        """§7-WhyNot-14: Why-not execution does not write durable ledger state."""
        store, index = _build_store()
        alice = _seed_person(store, index, "alice", 25, "us")
        body, target = _exists_age_region_body(index)
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p", "$region")),
            candidate_universe=(_binding(("$p", alice), ("$region", "eu")),),
            engine="native",
        )
        before = _ledger_dump(store)

        with (
            patch.object(
                store.ledger,
                "append_assertion",
                side_effect=AssertionError("Why-not must not append assertions"),
            ) as append_assertion,
            patch.object(
                store.ledger,
                "append_revocation",
                side_effect=AssertionError("Why-not must not append revocations"),
            ) as append_revocation,
        ):
            result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        self.assertEqual(_ledger_dump(store), before)
        self.assertFalse(append_assertion.called)
        self.assertFalse(append_revocation.called)


class WhyNotRuntimeRowDiagnosticTests(unittest.TestCase):
    """§7-WhyNot-9 / 10 / 11: Diagnose mapping and invariant gates."""

    def test_native_red_row_maps_actual_atom_localized_diagnose(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, "alice", 25, "us")
        body, target = _exists_age_region_body(index)
        red_binding = _binding(("$p", alice), ("$region", "eu"))
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p", "$region")),
            candidate_universe=(red_binding,),
            engine="native",
        )

        result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.passed, ())
        self.assertEqual(tuple(row.binding for row in result.failed), (red_binding,))
        diagnostic = result.failed[0].diagnostic
        self.assertEqual(diagnostic.status, "failed")
        self.assertEqual(diagnostic.failure_kind, "atom_localized")
        self.assertEqual(diagnostic.diagnostic_granularity, "atom_localized")
        locator = diagnostic.atom_locator
        assert locator is not None
        self.assertEqual(locator.case_index, 0)
        self.assertEqual(locator.failed_atom_index, 2)
        self.assertIn(("$age", 25), locator.attempted_binding)

    def test_red_rows_call_diagnose_with_same_plan_binding_engine_store_registry(self) -> None:
        store, _index = _build_store()
        registry = RuleRegistry()
        first = _binding(("$p", "person-1"))
        second = _binding(("$p", "person-2"))
        plan = _build_plan([("eq", "$p", "person-0")], "Person:exists", ("$p",))
        request = WhyNotUniverseRequest(
            plan=plan,
            candidate_universe=(first, second),
            engine="native",
        )
        seen: list[tuple[Any, Store, RuleRegistry | None]] = []

        def _fake_diagnose(diagnose_request: Any, *, store: Store, registry: Any) -> DiagnoseResult:
            seen.append((diagnose_request, store, registry))
            return _diagnose_no_candidate(diagnose_request.binding)

        with (
            patch(
                "factgraph.application.why_not_runtime.evaluate_native_where",
                return_value=SimpleNamespace(bindings=()),
            ),
            patch(
                "factgraph.application.why_not_runtime.diagnose_derivation_binding",
                side_effect=_fake_diagnose,
            ),
        ):
            result = check_why_not_universe(request, store=store, registry=registry)

        self.assertEqual(tuple(row.binding for row in result.failed), (first, second))
        self.assertEqual([entry[0].binding for entry in seen], [first, second])
        self.assertTrue(all(entry[0].plan is plan for entry in seen))
        self.assertEqual([entry[0].engine for entry in seen], ["native", "native"])
        self.assertTrue(all(entry[1] is store for entry in seen))
        self.assertTrue(all(entry[2] is registry for entry in seen))

    def test_failed_no_candidate_diagnose_maps_to_coarse_row(self) -> None:
        store, _index = _build_store()
        binding = _binding(("$p", "person-1"))
        warning = WarningDTO(code="ROW_DIAGNOSTIC_WARNING", message="row warning")
        request = WhyNotUniverseRequest(
            plan=_build_plan([("eq", "$p", "person-0")], "Person:exists", ("$p",)),
            candidate_universe=(binding,),
            engine="native",
        )

        with (
            patch(
                "factgraph.application.why_not_runtime.evaluate_native_where",
                return_value=SimpleNamespace(bindings=()),
            ),
            patch(
                "factgraph.application.why_not_runtime.diagnose_derivation_binding",
                return_value=_diagnose_no_candidate(binding, warnings=(warning,)),
            ),
        ):
            result = check_why_not_universe(request, store=store)

        diagnostic = result.failed[0].diagnostic
        self.assertEqual(diagnostic.status, "failed")
        self.assertEqual(diagnostic.failure_kind, "no_candidate")
        self.assertEqual(diagnostic.diagnostic_granularity, "coarse")
        self.assertIsNone(diagnostic.atom_locator)
        self.assertEqual(diagnostic.warnings, (warning,))

    def test_unsupported_diagnose_maps_to_unavailable_row(self) -> None:
        store, _index = _build_store()
        binding = _binding(("$p", "person-1"))
        error = ErrorDTO(code="ROW_ENGINE_UNSUPPORTED", message="row unsupported")
        request = WhyNotUniverseRequest(
            plan=_build_plan([("eq", "$p", "person-0")], "Person:exists", ("$p",)),
            candidate_universe=(binding,),
            engine="native",
        )

        with (
            patch(
                "factgraph.application.why_not_runtime.evaluate_native_where",
                return_value=SimpleNamespace(bindings=()),
            ),
            patch(
                "factgraph.application.why_not_runtime.diagnose_derivation_binding",
                return_value=_diagnose_unsupported(binding, errors=(error,)),
            ),
        ):
            result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        diagnostic = result.failed[0].diagnostic
        self.assertEqual(diagnostic.status, "unsupported")
        self.assertIsNone(diagnostic.failure_kind)
        self.assertEqual(diagnostic.diagnostic_granularity, "unavailable")
        self.assertIsNone(diagnostic.atom_locator)
        self.assertEqual(diagnostic.errors, (error,))

    def test_passed_diagnose_result_raises_invariant_error(self) -> None:
        store, _index = _build_store()
        binding = _binding(("$p", "person-1"))
        request = WhyNotUniverseRequest(
            plan=_build_plan([("eq", "$p", "person-0")], "Person:exists", ("$p",)),
            candidate_universe=(binding,),
            engine="native",
        )
        passed = DiagnoseResult(
            status="passed",
            requested_binding=binding,
            matched_count=1,
            matched_binding=binding,
            failure_kind=None,
            diagnostic_payload=None,
            errors=(),
            warnings=(),
        )

        with (
            patch(
                "factgraph.application.why_not_runtime.evaluate_native_where",
                return_value=SimpleNamespace(bindings=()),
            ),
            patch(
                "factgraph.application.why_not_runtime.diagnose_derivation_binding",
                return_value=passed,
            ),
            self.assertRaises(WhyNotRuntimeError) as raised,
        ):
            check_why_not_universe(request, store=store)

        self.assertEqual(raised.exception.code, "WHY_NOT_DIAGNOSE_PASSED_FAILED_BINDING")

    def test_invalid_request_diagnose_result_raises_invariant_error(self) -> None:
        store, _index = _build_store()
        binding = _binding(("$p", "person-1"))
        request = WhyNotUniverseRequest(
            plan=_build_plan([("eq", "$p", "person-0")], "Person:exists", ("$p",)),
            candidate_universe=(binding,),
            engine="native",
        )
        invalid = DiagnoseResult(
            status="invalid_request",
            requested_binding=binding,
            matched_count=None,
            matched_binding=None,
            failure_kind=None,
            diagnostic_payload=None,
            errors=(ErrorDTO(code="ROW_INVALID_REQUEST", message="row invalid"),),
            warnings=(),
        )

        with (
            patch(
                "factgraph.application.why_not_runtime.evaluate_native_where",
                return_value=SimpleNamespace(bindings=()),
            ),
            patch(
                "factgraph.application.why_not_runtime.diagnose_derivation_binding",
                return_value=invalid,
            ),
            self.assertRaises(WhyNotRuntimeError) as raised,
        ):
            check_why_not_universe(request, store=store)

        self.assertEqual(raised.exception.code, "WHY_NOT_DIAGNOSE_INVALID_REQUEST")

    def test_atom_localized_diagnose_result_copies_locator_into_why_not_dto(self) -> None:
        store, _index = _build_store()
        binding = _binding(("$p", "person-1"))
        attempted = _binding(("$p", "person-1"), ("$age", 25))
        request = WhyNotUniverseRequest(
            plan=_build_plan([("eq", "$p", "person-0")], "Person:exists", ("$p",)),
            candidate_universe=(binding,),
            engine="native",
        )
        diagnose_result = DiagnoseResult(
            status="failed",
            requested_binding=binding,
            matched_count=0,
            matched_binding=None,
            failure_kind="atom_localized",
            diagnostic_payload=DiagnoseConditionLocator(
                case_index=3,
                failed_atom_index=4,
                attempted_binding=attempted,
            ),
            errors=(),
            warnings=(),
        )

        with (
            patch(
                "factgraph.application.why_not_runtime.evaluate_native_where",
                return_value=SimpleNamespace(bindings=()),
            ),
            patch(
                "factgraph.application.why_not_runtime.diagnose_derivation_binding",
                return_value=diagnose_result,
            ),
        ):
            result = check_why_not_universe(request, store=store)

        locator = result.failed[0].diagnostic.atom_locator
        assert locator is not None
        self.assertEqual(locator.case_index, 3)
        self.assertEqual(locator.failed_atom_index, 4)
        self.assertEqual(locator.attempted_binding, attempted)
        self.assertIsNot(locator, diagnose_result.diagnostic_payload)


class WhyNotRuntimeNonNativeBoardTests(unittest.TestCase):
    """§7-WhyNot-12: non-native board support and unsupported boundaries."""

    def test_problog_and_pyreason_partition_representable_candidate_payloads(self) -> None:
        for engine in ("problog", "pyreason"):
            with self.subTest(engine=engine):
                store, index = _build_store()
                body, target = _exists_age_body(index)
                plan = _build_plan(body, target, ("$p",))
                request = WhyNotUniverseRequest(
                    plan=plan,
                    candidate_universe=(
                        _binding(("$p", "person-2")),
                        _binding(("$p", "person-1")),
                    ),
                    engine=engine,  # type: ignore[arg-type]
                )

                with patch(
                    "factgraph.application.why_not_runtime.evaluate_derivation_plans",
                    return_value=(_candidate(),),
                ), patch(
                    "factgraph.application.why_not_runtime.diagnose_derivation_binding",
                    side_effect=lambda diagnose_request, **_kwargs: _diagnose_no_candidate(
                        diagnose_request.binding
                    ),
                ):
                    result = check_why_not_universe(request, store=store)

                self.assertEqual(result.status, "completed")
                self.assertEqual(result.passed, (_binding(("$p", "person-1")),))
                self.assertEqual(
                    tuple(row.binding for row in result.failed),
                    (_binding(("$p", "person-2")),),
                )
                self.assertEqual(result.failed[0].diagnostic.status, "failed")
                self.assertEqual(result.failed[0].diagnostic.failure_kind, "no_candidate")
                self.assertEqual(
                    result.failed[0].diagnostic.diagnostic_granularity,
                    "coarse",
                )

    def test_problog_entity_target_returns_unsupported_before_dispatch(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        request = WhyNotUniverseRequest(
            plan=_build_plan(
                body,
                target,
                ("$p",),
                head_spec={"callee_kind": "entity_type", "entity_type": "Person"},
            ),
            candidate_universe=(_binding(("$p", "person-1")),),
            engine="problog",
        )

        with patch("factgraph.application.why_not_runtime.evaluate_derivation_plans") as mocked:
            result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "ENTITY_TARGET_NOT_REPRESENTABLE")
        mocked.assert_not_called()

    def test_candidate_ref_payload_returns_top_level_unsupported(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p",)),
            candidate_universe=(_binding(("$p", "person-1")),),
            engine="pyreason",
        )

        with patch(
            "factgraph.application.why_not_runtime.evaluate_derivation_plans",
            return_value=(
                _candidate(
                    support_kind="pyreason_provenance_v1",
                    terms=[{"kind": "candidate_ref", "candidate_key": "candk_v2:x"}],
                ),
            ),
        ):
            result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "CANDIDATE_BINDING_NOT_REPRESENTABLE")

    def test_unrecognized_candidate_payload_term_returns_top_level_unsupported(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p",)),
            candidate_universe=(_binding(("$p", "person-1")),),
            engine="problog",
        )

        with patch(
            "factgraph.application.why_not_runtime.evaluate_derivation_plans",
            return_value=(_candidate(terms=[{"kind": "literal_without_value"}]),),
        ), patch(
            "factgraph.application.why_not_runtime.diagnose_derivation_binding",
        ) as diagnose:
            result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "CANDIDATE_BINDING_NOT_REPRESENTABLE")
        diagnose.assert_not_called()

    def test_non_native_row_level_unsupported_keeps_completed_board(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        red_binding = _binding(("$p", "person-2"))
        error = ErrorDTO(code="ROW_DIAGNOSTIC_UNAVAILABLE", message="row unavailable")
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p",)),
            candidate_universe=(red_binding,),
            engine="problog",
        )

        with patch(
            "factgraph.application.why_not_runtime.evaluate_derivation_plans",
            return_value=(),
        ), patch(
            "factgraph.application.why_not_runtime.diagnose_derivation_binding",
            return_value=_diagnose_unsupported(red_binding, errors=(error,)),
        ):
            result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.errors, ())
        self.assertEqual(result.passed, ())
        self.assertEqual(tuple(row.binding for row in result.failed), (red_binding,))
        self.assertEqual(result.failed[0].diagnostic.status, "unsupported")
        self.assertIsNone(result.failed[0].diagnostic.failure_kind)
        self.assertEqual(
            result.failed[0].diagnostic.diagnostic_granularity,
            "unavailable",
        )
        self.assertEqual(result.failed[0].diagnostic.errors, (error,))

    def test_souffle_uses_support_artifact_binding_items(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        binding = normalize_binding_items((("$p", "person-1"),))
        artifact = ProofReceipt(
            kind="souffle_witness_v1",
            root_result_kind="fact",
            binding_items=binding,
            pred_witnesses=(),
        )
        support_digest = compute_support_digest(artifact)
        store._remember_support_artifact(support_digest, artifact)
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p",)),
            candidate_universe=(
                _binding(("$p", "person-1")),
                _binding(("$p", "person-2")),
            ),
            engine="souffle",
        )

        with patch(
            "factgraph.application.why_not_runtime.evaluate_derivation_plans",
            return_value=(
                _candidate(
                    support_digest=support_digest,
                    support_kind="souffle_witness_v1",
                    terms=[],
                ),
            ),
        ), patch(
            "factgraph.application.why_not_runtime.diagnose_derivation_binding",
            side_effect=lambda diagnose_request, **_kwargs: _diagnose_no_candidate(
                diagnose_request.binding
            ),
        ):
            result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.passed, (_binding(("$p", "person-1")),))
        self.assertEqual(
            tuple(row.binding for row in result.failed),
            (_binding(("$p", "person-2")),),
        )
        self.assertEqual(result.failed[0].diagnostic.status, "failed")
        self.assertEqual(result.failed[0].diagnostic.failure_kind, "no_candidate")

    def test_souffle_support_lookup_miss_returns_unsupported(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p",)),
            candidate_universe=(_binding(("$p", "person-1")),),
            engine="souffle",
        )

        with patch(
            "factgraph.application.why_not_runtime.evaluate_derivation_plans",
            return_value=(
                _candidate(
                    support_digest="sha256:" + ("f" * 64),
                    support_kind="souffle_witness_v1",
                    terms=[],
                ),
            ),
        ):
            result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "EVIDENCE_LOOKUP_MISS")


class WhyNotRuntimeBoundaryTests(unittest.TestCase):
    """§7-WhyNot-9: runtime composition boundary smoke coverage."""

    def test_runtime_composes_diagnose_without_check_or_protocol_result_imports(self) -> None:
        source = Path(why_not_runtime.__file__).read_text()
        tree = ast.parse(source)
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imported_names.add(alias.name.rsplit(".", maxsplit=1)[-1])
                    if alias.asname:
                        imported_names.add(alias.asname)

        self.assertIn("DiagnoseRequest", imported_names)
        self.assertIn("diagnose_derivation_binding", imported_names)
        self.assertNotIn("check_derivation_binding", imported_names)
        self.assertNotIn("derivation_check_runtime", imported_names)
        self.assertNotIn("DiagnoseResult", imported_names)
        self.assertNotIn("DiagnoseConditionLocator", imported_names)


if __name__ == "__main__":
    unittest.main()
