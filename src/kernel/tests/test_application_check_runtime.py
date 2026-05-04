"""Runtime tests for `kernel.application.derivation_check_runtime`.

Covers (per blueprint Step 2 plan + Step 0.B/0.C contract):

- Native happy path: complete + partial + empty binding, single + multi match.
- Semantic invalid_request: unknown variable, missing/unresolvable registry.
- EvidenceEnvelope shape: engine field, support_kind, typed engine_payload,
  branch_atom_projection always None on passed.
- Deterministic primary: stable across runs, OR-of-AND lowest branch_index.
- Anti-regression (per topic doc §7):
  * support build receives FULL binding (not user partial)
  * passed + branch_atom_projection=None + engine_payload non-None is
    fully evidence-bearing (None != degraded)
  * unexpected runtime exception propagates loudly (does not collapse
    into status)
- Non-native staging: souffle/problog/pyreason raise NotImplementedError.
"""
from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from kernel.application import (
    CheckRuntimeError,
    build_schema_index,
    check_derivation_binding,
    entity_info,
    field_predicate,
    resolve_selector,
)
from kernel.application.protocol import (
    CheckRequest,
    CheckResult,
    CompiledDerivationPlan,
    CompiledHeadCall,
    EntitySelector,
)
from kernel.core.evidence.write_protocol import set_field
from kernel.core.rules.rule_ir import RuleRegistry, RuleSpec
from kernel.core.store import Store
from kernel.core.store._support import SupportArtifact, normalize_binding_items
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
    target_pred_id: str,
    head_var_names: tuple[str, ...] = ("p",),
) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="check-test",
        version="1.0",
        body_ir=body_ir,
        heads=(
            CompiledHeadCall(
                target_pred_id=target_pred_id,
                head_var_names=head_var_names,
            ),
        ),
    )


def _exists_body(index: Any) -> tuple[list[Any], str]:
    info = entity_info(index, "Person")
    body: list[Any] = [("pred", info.exists_predicate_id, ["$p"])]
    return body, info.exists_predicate_id


def _exists_plus_age_body(index: Any) -> tuple[list[Any], str]:
    info = entity_info(index, "Person")
    age_pred = field_predicate(index, "Person", "age").pred_id
    body: list[Any] = [
        ("pred", info.exists_predicate_id, ["$p"]),
        ("pred", age_pred, ["$p", "$age"]),
    ]
    return body, info.exists_predicate_id


class _CountingRuleRegistry(RuleRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.resolve_calls: list[tuple[str, str]] = []

    def resolve(self, rule_id: str, version: str) -> RuleSpec:
        self.resolve_calls.append((rule_id, version))
        return super().resolve(rule_id, version)


class NativeHappyPathTests(unittest.TestCase):
    def test_complete_binding_passes(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(
            plan=plan,
            binding=(("$age", 25), ("$p", encoded)),
            engine="native",
        )

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 1)
        self.assertIsNotNone(result.matched_binding)
        self.assertIsNotNone(result.evidence_envelope)

    def test_complete_binding_fails(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(
            plan=plan,
            binding=(("$age", 99), ("$p", encoded)),
            engine="native",
        )

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.matched_count, 0)
        self.assertIsNone(result.matched_binding)
        self.assertIsNone(result.evidence_envelope)

    def test_partial_binding_single_match_passes(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(
            plan=plan,
            binding=(("$p", encoded),),
            engine="native",
        )

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 1)
        # Primary matched_binding should include both $p and $age (full binding).
        keys = {key for key, _ in result.matched_binding or ()}
        self.assertIn("$p", keys)
        self.assertIn("$age", keys)

    def test_partial_binding_multi_match(self) -> None:
        store, index = _build_store()
        _seed_person(store, index, "alice", 25, "us")
        _seed_person(store, index, "bob", 25, "eu")
        body, exists_pred = _exists_plus_age_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(
            plan=plan,
            binding=(("$age", 25),),
            engine="native",
        )

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertGreaterEqual(result.matched_count or 0, 2)
        self.assertIsNotNone(result.matched_binding)

    def test_partial_binding_no_match_fails(self) -> None:
        store, index = _build_store()
        _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(
            plan=plan,
            binding=(("$age", 99),),
            engine="native",
        )

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.matched_count, 0)

    def test_empty_binding_with_results_passes(self) -> None:
        store, index = _build_store()
        _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(plan=plan, binding=(), engine="native")

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertGreaterEqual(result.matched_count or 0, 1)

    def test_empty_binding_no_results_fails(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(plan=plan, binding=(), engine="native")

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.matched_count, 0)


class SemanticInvalidRequestTests(unittest.TestCase):
    def test_unknown_variable_in_binding_invalid_request(self) -> None:
        store, index = _build_store()
        _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred)
        # body only has $p; ask about $nonexistent
        request = CheckRequest(
            plan=plan,
            binding=(("$nonexistent", "x"),),
            engine="native",
        )

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "invalid_request")
        self.assertIsNone(result.matched_count)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].code, "UNKNOWN_VARIABLE_IN_BINDING")
        self.assertIn("$nonexistent", result.errors[0].details["unknown_variables"])

    def test_ruleref_without_registry_invalid_request(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        body_with_ruleref = body + [("ruleref", "rule_x", "1.0", ["$p"])]
        plan = _build_plan(body_with_ruleref, exists_pred)
        request = CheckRequest(
            plan=plan,
            binding=(),
            engine="native",
        )

        result = check_derivation_binding(request, store=store, registry=None)

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "REGISTRY_REQUIRED")

    def test_ruleref_unresolvable_via_preflight_invalid_request(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        body_with_ruleref = body + [("ruleref", "missing_rule", "1.0", ["$p"])]
        plan = _build_plan(body_with_ruleref, exists_pred)
        registry = RuleRegistry()  # empty -- resolve will fail
        request = CheckRequest(plan=plan, binding=(), engine="native")

        result = check_derivation_binding(request, store=store, registry=registry)

        self.assertEqual(result.status, "invalid_request")
        codes = {err.code for err in result.errors}
        self.assertIn("RULE_REF_UNRESOLVABLE", codes)
        # Reason preserved in details (no brittle text parsing required of caller).
        unresolvable = next(
            err for err in result.errors if err.code == "RULE_REF_UNRESOLVABLE"
        )
        self.assertEqual(unresolvable.details["rule_id"], "missing_rule")
        self.assertEqual(unresolvable.details["version"], "1.0")
        self.assertIn("reason", unresolvable.details)

    def test_ruleref_preflight_dedupes_repeated_keys(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        body_with_duplicate_refs = body + [
            ("ruleref", "missing_rule", "1.0", ["$p"]),
            ("ruleref", "missing_rule", "1.0", ["$p"]),
        ]
        plan = _build_plan(body_with_duplicate_refs, exists_pred)
        registry = _CountingRuleRegistry()
        request = CheckRequest(plan=plan, binding=(), engine="native")

        result = check_derivation_binding(request, store=store, registry=registry)

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(registry.resolve_calls, [("missing_rule", "1.0")])
        self.assertEqual(
            [err.code for err in result.errors],
            ["RULE_REF_UNRESOLVABLE"],
        )

    def test_ruleref_inside_or_branch_preflight_requires_registry(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        body_with_or_ref: list[Any] = [
            body,
            [("ruleref", "child_rule", "1.0", ["$p"])],
        ]
        plan = _build_plan(body_with_or_ref, exists_pred)
        request = CheckRequest(plan=plan, binding=(), engine="native")

        result = check_derivation_binding(request, store=store, registry=None)

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "REGISTRY_REQUIRED")

    def test_ruleref_with_valid_registry_passes(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        child_body, exists_pred = _exists_body(index)
        registry = RuleRegistry()
        registry.register(
            RuleSpec(
                rule_id="person.exists",
                version="1.0",
                select_vars=["$p"],
                where=child_body,
                expose=True,
            )
        )
        parent_body: list[Any] = [("ruleref", "person.exists", "1.0", ["$p"])]
        plan = _build_plan(parent_body, exists_pred)
        request = CheckRequest(plan=plan, binding=(("$p", encoded),), engine="native")

        result = check_derivation_binding(request, store=store, registry=registry)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 1)
        envelope = result.evidence_envelope
        assert envelope is not None
        artifact = envelope.engine_payload
        self.assertIsInstance(artifact, SupportArtifact)
        assert isinstance(artifact, SupportArtifact)
        self.assertEqual(artifact.rule_refs, ("person.exists",))
        self.assertEqual(len(artifact.rule_ref_edges), 1)


class EvidenceEnvelopeShapeTests(unittest.TestCase):
    def _passed_result(self) -> CheckResult:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(
            plan=plan,
            binding=(("$p", encoded),),
            engine="native",
        )
        return check_derivation_binding(request, store=store)

    def test_evidence_engine_is_native(self) -> None:
        envelope = self._passed_result().evidence_envelope
        self.assertIsNotNone(envelope)
        assert envelope is not None
        self.assertEqual(envelope.engine, "native")

    def test_evidence_support_kind_is_native_binding_v1(self) -> None:
        envelope = self._passed_result().evidence_envelope
        assert envelope is not None
        self.assertEqual(envelope.support_kind, "native_binding_v1")

    def test_evidence_engine_payload_is_support_artifact_typed(self) -> None:
        envelope = self._passed_result().evidence_envelope
        assert envelope is not None
        self.assertIsInstance(envelope.engine_payload, SupportArtifact)

    def test_evidence_branch_atom_projection_always_none_on_passed(self) -> None:
        envelope = self._passed_result().evidence_envelope
        assert envelope is not None
        self.assertIsNone(envelope.branch_atom_projection)

    def test_support_digest_can_be_explained_from_store(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(
            plan=plan,
            binding=(("$p", encoded),),
            engine="native",
        )

        result = check_derivation_binding(request, store=store)

        envelope = result.evidence_envelope
        assert envelope is not None
        rendered = store.explain_support(envelope.support_digest)
        self.assertIsNotNone(rendered)
        assert rendered is not None
        self.assertEqual(rendered["kind"], "native_binding_v1")


class DeterministicPrimaryTests(unittest.TestCase):
    def test_multi_binding_match_primary_stable_across_runs(self) -> None:
        store, index = _build_store()
        _seed_person(store, index, "alice", 25, "us")
        _seed_person(store, index, "bob", 25, "eu")
        _seed_person(store, index, "carol", 25, "ap")
        body, exists_pred = _exists_plus_age_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(
            plan=plan,
            binding=(("$age", 25),),
            engine="native",
        )

        primaries = {
            check_derivation_binding(request, store=store).matched_binding
            for _ in range(3)
        }

        self.assertEqual(len(primaries), 1)

    def test_partial_multi_match_primary_is_lowest_binding_items(self) -> None:
        store, index = _build_store()
        encoded_alice = _seed_person(store, index, "alice", 25, "us")
        encoded_bob = _seed_person(store, index, "bob", 25, "eu")
        encoded_carol = _seed_person(store, index, "carol", 25, "ap")
        body, exists_pred = _exists_plus_age_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(
            plan=plan,
            binding=(("$age", 25),),
            engine="native",
        )

        result = check_derivation_binding(request, store=store)

        expected_primary = min(
            normalize_binding_items({"$age": 25, "$p": encoded})
            for encoded in (encoded_alice, encoded_bob, encoded_carol)
        )
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 3)
        self.assertEqual(result.matched_binding, expected_primary)

    def test_or_of_and_multi_branch_primary_lowest_branch_index(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        info = entity_info(index, "Person")
        age_pred = field_predicate(index, "Person", "age").pred_id
        region_pred = field_predicate(index, "Person", "region").pred_id
        # OR-of-AND: branch 0 = age==25; branch 1 = region=="us".
        # alice satisfies BOTH. Primary must be branch_index=0.
        body: list[Any] = [
            [
                ("pred", info.exists_predicate_id, ["$p"]),
                ("pred", age_pred, ["$p", "$age"]),
                ("eq", "$age", 25),
            ],
            [
                ("pred", info.exists_predicate_id, ["$p"]),
                ("pred", region_pred, ["$p", "$region"]),
                ("eq", "$region", "us"),
            ],
        ]
        plan = _build_plan(body, info.exists_predicate_id)
        request = CheckRequest(
            plan=plan,
            binding=(("$p", encoded),),
            engine="native",
        )

        result = check_derivation_binding(request, store=store)
        self.assertEqual(result.status, "passed")
        envelope = result.evidence_envelope
        assert envelope is not None
        self.assertEqual(envelope.branch_index, 0)


class AntiRegressionTests(unittest.TestCase):
    def test_support_build_uses_full_binding_not_partial(self) -> None:
        """§7.1 trap: support build must receive primary FULL binding, not user partial."""
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        plan = _build_plan(body, exists_pred)
        # User partial binding only has $p; runtime must enumerate full bindings
        # (which include $age) and pass the FULL primary binding to support build.
        request = CheckRequest(
            plan=plan,
            binding=(("$p", encoded),),
            engine="native",
        )

        with patch(
            "kernel.application.derivation_check_runtime.build_support_artifact_for_binding",
            wraps=__import__(
                "kernel.core.store._support_capture",
                fromlist=["build_support_artifact_for_binding"],
            ).build_support_artifact_for_binding,
        ) as spy:
            check_derivation_binding(request, store=store)

        self.assertEqual(spy.call_count, 1)
        binding_kwarg = spy.call_args.kwargs["binding"]
        self.assertIn("$p", binding_kwarg)
        # Primary FULL binding must include body-only var $age, not just user partial.
        self.assertIn("$age", binding_kwarg)
        self.assertEqual(binding_kwarg["$age"], 25)

    def test_passed_with_none_projection_and_envelope_is_fully_evidence_bearing(
        self,
    ) -> None:
        """§7.3 trap: branch_atom_projection=None must NOT be read as degraded."""
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(
            plan=plan,
            binding=(("$p", encoded),),
            engine="native",
        )

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        envelope = result.evidence_envelope
        assert envelope is not None
        # Both conditions hold: projection slot is None AND engine_payload is rich.
        self.assertIsNone(envelope.branch_atom_projection)
        self.assertIsNotNone(envelope.engine_payload)
        self.assertTrue(envelope.support_digest.startswith("sha256:"))

    def test_runtime_exception_propagates_loudly(self) -> None:
        """§7 outcome purity: unexpected runtime errors must not collapse into status."""
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(plan=plan, binding=(), engine="native")

        boom = RuntimeError("evaluator exploded")
        with patch(
            "kernel.application.derivation_check_runtime.evaluate_native_where",
            side_effect=boom,
        ):
            with self.assertRaises(RuntimeError) as ctx:
                check_derivation_binding(request, store=store)
        self.assertIs(ctx.exception, boom)


class NonNativeStagingTests(unittest.TestCase):
    def _request(self, engine: str) -> CheckRequest:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred)
        return CheckRequest(plan=plan, binding=(), engine=engine)  # type: ignore[arg-type]

    def test_non_native_engines_raise_not_implemented(self) -> None:
        store, _ = _build_store()
        for engine in ("souffle", "problog", "pyreason"):
            with self.subTest(engine=engine):
                request = self._request(engine)
                with self.assertRaises(NotImplementedError):
                    check_derivation_binding(request, store=store)


class CheckRuntimeErrorTests(unittest.TestCase):
    def test_to_error_dto_round_trip(self) -> None:
        err = CheckRuntimeError(
            "internal invariant violation",
            code="CHECK_INTERNAL_ERROR",
            path=("primary",),
            details={"key": "value"},
        )
        dto = err.to_error_dto()
        self.assertEqual(dto.code, "CHECK_INTERNAL_ERROR")
        self.assertEqual(dto.path, ("primary",))
        self.assertEqual(dto.details, {"key": "value"})


if __name__ == "__main__":
    unittest.main()
