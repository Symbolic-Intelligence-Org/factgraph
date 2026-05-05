"""Runtime tests for Why-not Universe Diagnose Step 2 board assembly."""
from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from kernel.application import (
    build_schema_index,
    check_why_not_universe,
    entity_info,
    field_predicate,
    resolve_selector,
)
from kernel.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    EntitySelector,
    WhyNotUniverseRequest,
)
from kernel.core.derivation.candidates import CandidateSet
from kernel.core.evidence.write_protocol import set_field
from kernel.core.rules.rule_ir import RuleRegistry, RuleSpec
from kernel.core.store import Store
from kernel.core.store._support import (
    SupportArtifact,
    compute_support_digest,
    normalize_binding_items,
)
from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")
    region: str = Field(cardinality="single")


def _build_store() -> tuple[Store, Any]:
    schema_ir = compile_schema_from_classes([Person])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


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


class _CountingRuleRegistry(RuleRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.resolve_calls: list[tuple[str, str]] = []

    def resolve(self, rule_id: str, version: str) -> RuleSpec:
        self.resolve_calls.append((rule_id, version))
        return super().resolve(rule_id, version)


class WhyNotRuntimeNativeBoardTests(unittest.TestCase):
    def test_empty_universe_returns_completed_without_evaluation(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p", "$age")),
            candidate_universe=(),
            engine="native",
        )

        with patch("kernel.application.why_not_runtime.evaluate_native_where") as mocked:
            result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.green, ())
        self.assertEqual(result.red, ())
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

        with patch("kernel.application.why_not_runtime.evaluate_native_where") as mocked:
            result = check_why_not_universe(request, store=store, registry=None)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.green, ())
        self.assertEqual(result.red, ())
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
        self.assertEqual(result.green, (alice_binding, bob_binding))
        self.assertEqual(tuple(row.binding for row in result.red), (missing_binding,))
        self.assertEqual(result.red[0].diagnostic.status, "failed")
        self.assertEqual(result.red[0].diagnostic.failure_kind, "no_candidate")
        self.assertEqual(result.red[0].diagnostic.diagnostic_granularity, "coarse")

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
        self.assertEqual(result.green, (alice_binding, bob_binding))
        self.assertEqual(result.red, ())

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
        self.assertEqual(result.green, ())
        self.assertEqual(tuple(row.binding for row in result.red), (missing_a, missing_b))

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
        self.assertEqual(result.green, (alice_binding, bob_binding))
        self.assertEqual(tuple(row.binding for row in result.red), (missing_a, missing_b))

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
        self.assertEqual(result.green, ())
        self.assertEqual(result.red, ())
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
        self.assertEqual(result.green, ())
        self.assertEqual(result.red, ())
        self.assertEqual(result.errors[0].code, "CANDIDATE_BINDING_NOT_REPRESENTABLE")


class WhyNotRuntimeNonNativeBoardTests(unittest.TestCase):
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
                    "kernel.application.why_not_runtime.evaluate_derivation_plans",
                    return_value=(_candidate(),),
                ):
                    result = check_why_not_universe(request, store=store)

                self.assertEqual(result.status, "completed")
                self.assertEqual(result.green, (_binding(("$p", "person-1")),))
                self.assertEqual(
                    tuple(row.binding for row in result.red),
                    (_binding(("$p", "person-2")),),
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

        with patch("kernel.application.why_not_runtime.evaluate_derivation_plans") as mocked:
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
            "kernel.application.why_not_runtime.evaluate_derivation_plans",
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

    def test_souffle_uses_support_artifact_binding_items(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        binding = normalize_binding_items((("$p", "person-1"),))
        artifact = SupportArtifact(
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
            "kernel.application.why_not_runtime.evaluate_derivation_plans",
            return_value=(
                _candidate(
                    support_digest=support_digest,
                    support_kind="souffle_witness_v1",
                    terms=[],
                ),
            ),
        ):
            result = check_why_not_universe(request, store=store)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.green, (_binding(("$p", "person-1")),))
        self.assertEqual(
            tuple(row.binding for row in result.red),
            (_binding(("$p", "person-2")),),
        )

    def test_souffle_support_lookup_miss_returns_unsupported(self) -> None:
        store, index = _build_store()
        body, target = _exists_age_body(index)
        request = WhyNotUniverseRequest(
            plan=_build_plan(body, target, ("$p",)),
            candidate_universe=(_binding(("$p", "person-1")),),
            engine="souffle",
        )

        with patch(
            "kernel.application.why_not_runtime.evaluate_derivation_plans",
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


if __name__ == "__main__":
    unittest.main()
