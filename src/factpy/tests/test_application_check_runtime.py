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
- Non-native staging: request-level representability gate; representable
  requests raise NotImplementedError until evaluate-then-match lands.
"""
from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from factpy.application import (
    CheckRuntimeError,
    build_schema_index,
    check_derivation_binding,
    entity_info,
    field_predicate,
    resolve_selector,
)
from factpy.application.protocol import (
    CheckRequest,
    CheckResult,
    CompiledDerivationPlan,
    CompiledHeadCall,
    EntitySelector,
)
from factpy.core.evidence.write_protocol import set_field
from factpy.core.rules.rule_ir import RuleRegistry, RuleSpec
from factpy.core.store import Store
from factpy.core.store._support import SupportArtifact, normalize_binding_items
from factpy.sdk import Entity, Field, Identity, compile_schema_from_classes


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
    head_var_names: tuple[str, ...] = ("$p",),
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
    def _request(
        self,
        engine: str,
        *,
        binding: tuple[tuple[str, object], ...] = (),
        plan: CompiledDerivationPlan | None = None,
    ) -> CheckRequest:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        selected_plan = plan or _build_plan(body, exists_pred)
        return CheckRequest(plan=selected_plan, binding=binding, engine=engine)  # type: ignore[arg-type]

    def test_problog_body_only_binding_returns_unsupported_before_evaluate(self) -> None:
        store, _ = _build_store()
        request = self._request("problog", binding=(("$age", 25),))

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.matched_count)
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE")
        self.assertEqual(result.errors[0].details["body_only_variables"], ["$age"])

    def test_pyreason_body_only_binding_returns_unsupported_before_evaluate(self) -> None:
        store, _ = _build_store()
        request = self._request("pyreason", binding=(("$age", 25),))

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE")

    def test_problog_entity_target_plan_returns_unsupported_before_evaluate(self) -> None:
        store, index = _build_store()
        body, _ = _exists_body(index)
        plan = _build_plan(body, "Person")
        object.__setattr__(
            plan,
            "head_spec",
            {"callee_kind": "entity_type", "entity_type": "Person"},
        )
        request = self._request("problog", plan=plan)

        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "ENTITY_TARGET_NOT_REPRESENTABLE")


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


def _make_souffle_candidate(
    *,
    candidate_key: str = "candk_v2:souffle-test",
    support_digest: str = "sha256:" + ("a" * 64),
    target: str = "Person:exists",
) -> Any:
    """Step 4.2 fixture: minimal CandidateSet shaped like a Souffle output."""
    from factpy.core.derivation.candidates import CandidateSet

    key_digest = "sha256:" + ("0" * 64)
    return CandidateSet(
        derivation_id="check-test",
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
    """Step 4.2 fixture: minimal SupportArtifact for souffle path mocking."""
    from factpy.core.store._support import PredWitness, SupportArtifact

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


class SouffleCheckTests(unittest.TestCase):
    """Step 4.2: Souffle Check via evaluate-then-match against SupportArtifact.

    These tests mock ``evaluate_derivation_plans`` and ``_lookup_support_artifact``
    (the typed internal API used by the runtime) so they exercise the Check
    runtime contract without requiring the souffle binary to be installed.
    """

    def _build_request(self, binding: tuple[tuple[str, Any], ...]) -> tuple[
        CheckRequest, Store, Any
    ]:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred)
        request = CheckRequest(plan=plan, binding=binding, engine="souffle")
        return request, store, index

    def test_souffle_passes_with_matched_candidate(self) -> None:
        request, store, _ = self._build_request(binding=(("$p", "person-1"),))
        candidate = _make_souffle_candidate()
        artifact = _make_support_artifact(
            binding_items=(("$p", "person-1"),),
            pred_witness_keys=("b0.a0:Person:exists",),
        )
        with patch(
            "kernel.application.derivation_check_runtime.evaluate_derivation_plans",
            return_value=[candidate],
        ), patch(
            "kernel.application.derivation_check_runtime._lookup_support_artifact",
            return_value=artifact,
        ):
            result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 1)
        self.assertIsNotNone(result.evidence_envelope)
        envelope = result.evidence_envelope
        assert envelope is not None
        self.assertEqual(envelope.engine, "souffle")
        self.assertEqual(envelope.support_kind, "souffle_witness_v1")
        self.assertEqual(envelope.branch_index, 0)
        self.assertIs(envelope.engine_payload, artifact)
        self.assertIsNone(envelope.branch_atom_projection)

    def test_souffle_fails_with_no_matching_candidate(self) -> None:
        request, store, _ = self._build_request(binding=(("$p", "person-99"),))
        candidate = _make_souffle_candidate()
        artifact = _make_support_artifact(binding_items=(("$p", "person-1"),))
        with patch(
            "kernel.application.derivation_check_runtime.evaluate_derivation_plans",
            return_value=[candidate],
        ), patch(
            "kernel.application.derivation_check_runtime._lookup_support_artifact",
            return_value=artifact,
        ):
            result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.matched_count, 0)
        self.assertIsNone(result.matched_binding)
        self.assertIsNone(result.evidence_envelope)

    def test_souffle_fails_with_zero_candidates(self) -> None:
        """Per audit log Step 0.C C6: zero candidates is failed (representable but no result),
        NOT unsupported."""
        request, store, _ = self._build_request(binding=(("$p", "person-1"),))
        with patch(
            "kernel.application.derivation_check_runtime.evaluate_derivation_plans",
            return_value=[],
        ):
            result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.matched_count, 0)

    def test_souffle_skips_candidate_without_retrievable_artifact(self) -> None:
        """Candidate whose SupportArtifact lookup returns None is silently skipped."""
        request, store, _ = self._build_request(binding=(("$p", "person-1"),))
        good_candidate = _make_souffle_candidate(
            candidate_key="candk_v2:good",
            support_digest="sha256:" + ("a" * 64),
        )
        bad_candidate = _make_souffle_candidate(
            candidate_key="candk_v2:bad",
            support_digest="sha256:" + ("b" * 64),
        )
        good_artifact = _make_support_artifact(binding_items=(("$p", "person-1"),))

        def _lookup(_store: Store, digest: str) -> Any:
            if digest == good_candidate.support_digest:
                return good_artifact
            return None

        with patch(
            "kernel.application.derivation_check_runtime.evaluate_derivation_plans",
            return_value=[bad_candidate, good_candidate],
        ), patch(
            "kernel.application.derivation_check_runtime._lookup_support_artifact",
            side_effect=_lookup,
        ):
            result = check_derivation_binding(request, store=store)

        # bad_candidate skipped; good_candidate matches.
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 1)

    def test_souffle_multi_match_primary_by_lowest_branch_index(self) -> None:
        """Per Step 0.C C4: souffle primary key = (branch_index, binding_items, candidate_key)."""
        request, store, _ = self._build_request(binding=(("$p", "person-1"),))
        higher_branch_cand = _make_souffle_candidate(
            candidate_key="candk_v2:higher",
            support_digest="sha256:" + ("1" * 64),
        )
        lower_branch_cand = _make_souffle_candidate(
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
            if digest == higher_branch_cand.support_digest:
                return higher_artifact
            return lower_artifact

        with patch(
            "kernel.application.derivation_check_runtime.evaluate_derivation_plans",
            return_value=[higher_branch_cand, lower_branch_cand],
        ), patch(
            "kernel.application.derivation_check_runtime._lookup_support_artifact",
            side_effect=_lookup,
        ):
            result = check_derivation_binding(request, store=store)

        self.assertEqual(result.matched_count, 2)
        envelope = result.evidence_envelope
        assert envelope is not None
        # Lower branch_index wins primary.
        self.assertEqual(envelope.branch_index, 1)


class SouffleHelperUnitTests(unittest.TestCase):
    """Unit-level tests for Step 4.2 souffle helpers."""

    def test_parse_branch_index_basic(self) -> None:
        from factpy.application.derivation_check_runtime import _parse_branch_index

        self.assertEqual(_parse_branch_index("b0.a1:Person:exists"), 0)
        self.assertEqual(_parse_branch_index("b12.a3:eq"), 12)

    def test_parse_branch_index_returns_none_on_garbage(self) -> None:
        from factpy.application.derivation_check_runtime import _parse_branch_index

        self.assertIsNone(_parse_branch_index(""))
        self.assertIsNone(_parse_branch_index("not-a-key"))
        self.assertIsNone(_parse_branch_index("a0.b1:..."))  # leading 'a' not 'b'
        self.assertIsNone(_parse_branch_index("bX.a1:..."))  # non-int branch
        self.assertIsNone(_parse_branch_index("b0"))  # no dot
        self.assertIsNone(_parse_branch_index("b0.x1:..."))  # no atom marker
        self.assertIsNone(_parse_branch_index("b0.aX:..."))  # non-int atom
        self.assertIsNone(_parse_branch_index("b0.a1"))  # no suffix separator

    def test_derive_branch_index_returns_none_when_inconsistent(self) -> None:
        """Defensive fallback: if pred_witnesses span multiple branches, return None."""
        from factpy.application.derivation_check_runtime import (
            _derive_branch_index_from_artifact,
        )

        artifact = _make_support_artifact(
            binding_items=(("$p", "x"),),
            pred_witness_keys=("b0.a0:p", "b1.a0:q"),  # two branches
        )
        self.assertIsNone(_derive_branch_index_from_artifact(artifact))

    def test_derive_branch_index_from_pred_atom_keys(self) -> None:
        from factpy.application.derivation_check_runtime import (
            _derive_branch_index_from_artifact,
        )

        artifact = _make_support_artifact(
            binding_items=(("$p", "x"),),
            pred_witness_keys=("b2.a0:p", "b2.a1:q"),  # both branch 2
        )
        self.assertEqual(_derive_branch_index_from_artifact(artifact), 2)


class PrecheckHeadVarNormalizationTests(unittest.TestCase):
    """Step 4.2 fix: head_var_names without $-prefix are literals (per resolve_head_ref),
    not variable references; precheck must filter them out so non-native engines don't
    over-flag body_only_variables."""

    def test_problog_with_dollar_prefixed_head_var_does_not_overflag(self) -> None:
        """head_var_names=('$p',) + binding $p → not flagged as body_only.

        Should reach evaluate (Step 4.3 path); with mocked-empty candidates,
        result is `failed` (representable, evaluated, no match), NOT `unsupported`.
        """
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred, head_var_names=("$p",))
        request = CheckRequest(
            plan=plan,
            binding=(("$p", "person-1"),),
            engine="problog",
        )
        with patch(
            "kernel.application.derivation_check_runtime.evaluate_derivation_plans",
            return_value=[],
        ):
            result = check_derivation_binding(request, store=store)
        # Critical: representable + no match = failed (per Step 0.C C6),
        # NOT unsupported (the request was answerable).
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.matched_count, 0)

    def test_problog_with_bare_head_var_treats_as_literal_so_var_is_body_only(self) -> None:
        """head_var_names=('p',) literal + binding $p → flagged body_only (correct).

        Per `resolve_head_ref` convention in core/store/_builders.py: bare names are
        literal head args. They cannot match a requested binding variable.
        """
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred, head_var_names=("p",))  # bare literal
        request = CheckRequest(
            plan=plan,
            binding=(("$p", "person-1"),),
            engine="problog",
        )
        result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE")
        self.assertIn("$p", result.errors[0].details["body_only_variables"])


def _make_provenance_candidate(
    *,
    engine: str,
    candidate_key: str = "candk_v2:prov-test",
    support_digest: str | None = None,
    target: str = "Person:exists",
    terms: list[Any] | None = None,
) -> Any:
    """Step 4.3 fixture: minimal CandidateSet for ProbLog/PyReason path."""
    from factpy.core.derivation.candidates import CandidateSet

    support_kind = f"{engine}_provenance_v1"
    digest = support_digest or "sha256:" + ("c" * 64)
    return CandidateSet(
        derivation_id="check-test",
        derivation_version="1.0",
        run_id=f"{engine}-run",
        target=target,
        key_tuple_digest="sha256:" + ("0" * 64),
        tup_digest=None,
        payload={"terms": terms or []},
        support_digest=digest,
        support_kind=support_kind,
        generated_at=0,
        state="generated",
        candidate_key=candidate_key,
    )


def _make_provenance_envelope(
    *,
    candidate_id: str = "cand_v2:prov-test",
    engine: str = "problog",
    payload_type: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    """Step 4.3 fixture: minimal ProvenanceEnvelope."""
    from factpy.core.store._support import ProvenanceEnvelope

    return ProvenanceEnvelope(
        candidate_id=candidate_id,
        engine=engine,
        payload_type=payload_type or f"{engine}_provenance_v1",
        payload=payload or {"trace": "stub"},
    )


class ProblogPyreasonCheckTests(unittest.TestCase):
    """Step 4.3: ProbLog / PyReason Check via evaluate-then-match against ProvenanceEnvelope.

    Mocks ``evaluate_derivation_plans`` and ``_lookup_provenance_envelope`` so tests
    exercise the Check runtime contract without requiring problog/pyreason adapter
    binaries. Per Step 0.C C3: representability is gated to head vars (body-only
    requests are already filtered by precheck and never reach this path).
    """

    def _build_request(
        self,
        *,
        engine: str,
        binding: tuple[tuple[str, Any], ...],
    ) -> tuple[CheckRequest, Store]:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred, head_var_names=("$p",))
        request = CheckRequest(
            plan=plan,
            binding=binding,
            engine=engine,  # type: ignore[arg-type]
        )
        return request, store

    def test_problog_passes_with_matched_candidate(self) -> None:
        for engine in ("problog", "pyreason"):
            with self.subTest(engine=engine):
                request, store = self._build_request(
                    engine=engine, binding=(("$p", "person-1"),)
                )
                candidate = _make_provenance_candidate(
                    engine=engine,
                    terms=[{"kind": "entity_ref", "value": "person-1"}],
                )
                envelope_payload = _make_provenance_envelope(engine=engine)
                with patch(
                    "kernel.application.derivation_check_runtime.evaluate_derivation_plans",
                    return_value=[candidate],
                ), patch(
                    "kernel.application.derivation_check_runtime._lookup_provenance_envelope",
                    return_value=envelope_payload,
                ):
                    result = check_derivation_binding(request, store=store)

                self.assertEqual(result.status, "passed")
                self.assertEqual(result.matched_count, 1)
                env = result.evidence_envelope
                assert env is not None
                self.assertEqual(env.engine, engine)
                self.assertEqual(env.support_kind, f"{engine}_provenance_v1")
                # Per C4: ProbLog/PyReason carry no per-branch concept.
                self.assertIsNone(env.branch_index)
                self.assertIs(env.engine_payload, envelope_payload)
                self.assertIsNone(env.branch_atom_projection)

    def test_problog_fails_with_no_matching_candidate(self) -> None:
        request, store = self._build_request(
            engine="problog", binding=(("$p", "person-99"),)
        )
        candidate = _make_provenance_candidate(
            engine="problog",
            terms=[{"kind": "entity_ref", "value": "person-1"}],
        )
        envelope_payload = _make_provenance_envelope(engine="problog")
        with patch(
            "kernel.application.derivation_check_runtime.evaluate_derivation_plans",
            return_value=[candidate],
        ), patch(
            "kernel.application.derivation_check_runtime._lookup_provenance_envelope",
            return_value=envelope_payload,
        ):
            result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.matched_count, 0)
        self.assertIsNone(result.evidence_envelope)

    def test_problog_fails_with_zero_candidates(self) -> None:
        """Per Step 0.C C6: representable + zero candidates = failed (not unsupported)."""
        request, store = self._build_request(
            engine="problog", binding=(("$p", "person-1"),)
        )
        with patch(
            "kernel.application.derivation_check_runtime.evaluate_derivation_plans",
            return_value=[],
        ):
            result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.matched_count, 0)

    def test_problog_skips_candidate_without_provenance(self) -> None:
        request, store = self._build_request(
            engine="problog", binding=(("$p", "person-1"),)
        )
        good_candidate = _make_provenance_candidate(
            engine="problog",
            candidate_key="candk_v2:good",
            support_digest="sha256:" + ("a" * 64),
            terms=[{"kind": "entity_ref", "value": "person-1"}],
        )
        bad_candidate = _make_provenance_candidate(
            engine="problog",
            candidate_key="candk_v2:bad",
            support_digest="sha256:" + ("b" * 64),
            terms=[{"kind": "entity_ref", "value": "person-1"}],
        )
        good_envelope = _make_provenance_envelope(engine="problog")

        def _lookup(_store: Store, digest: str) -> Any:
            if digest == good_candidate.support_digest:
                return good_envelope
            return None

        with patch(
            "kernel.application.derivation_check_runtime.evaluate_derivation_plans",
            return_value=[bad_candidate, good_candidate],
        ), patch(
            "kernel.application.derivation_check_runtime._lookup_provenance_envelope",
            side_effect=_lookup,
        ):
            result = check_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 1)

    def test_problog_multi_match_primary_by_candidate_key(self) -> None:
        """Per Step 0.C C4: ProbLog/PyReason primary key = (candidate_key, binding_items)."""
        request, store = self._build_request(
            engine="problog", binding=(("$p", "person-1"),)
        )
        candidate_b = _make_provenance_candidate(
            engine="problog",
            candidate_key="candk_v2:beta",  # lex > alpha
            support_digest="sha256:" + ("1" * 64),
            terms=[{"kind": "entity_ref", "value": "person-1"}],
        )
        candidate_a = _make_provenance_candidate(
            engine="problog",
            candidate_key="candk_v2:alpha",  # lex first
            support_digest="sha256:" + ("2" * 64),
            terms=[{"kind": "entity_ref", "value": "person-1"}],
        )
        envelope_payload = _make_provenance_envelope(engine="problog")
        with patch(
            "kernel.application.derivation_check_runtime.evaluate_derivation_plans",
            return_value=[candidate_b, candidate_a],
        ), patch(
            "kernel.application.derivation_check_runtime._lookup_provenance_envelope",
            return_value=envelope_payload,
        ):
            result = check_derivation_binding(request, store=store)

        self.assertEqual(result.matched_count, 2)
        env = result.evidence_envelope
        assert env is not None
        # alpha sorts before beta lexically; primary support_digest must be alpha's.
        self.assertEqual(env.support_digest, candidate_a.support_digest)


class ProvenanceExtractionUnitTests(unittest.TestCase):
    """Step 4.3 helper unit tests: term-value extraction + head_var alignment."""

    def test_extract_term_value_from_dict_entity_ref(self) -> None:
        from factpy.application.derivation_check_runtime import _extract_term_value

        self.assertEqual(
            _extract_term_value({"kind": "entity_ref", "value": "person-1"}),
            "person-1",
        )

    def test_extract_term_value_from_dict_literal(self) -> None:
        from factpy.application.derivation_check_runtime import _extract_term_value

        self.assertEqual(
            _extract_term_value({"kind": "literal", "tag": "string", "value": "hello"}),
            "hello",
        )
        self.assertEqual(
            _extract_term_value({"kind": "literal", "tag": "int", "value": 42}),
            42,
        )

    def test_extract_term_value_from_tuple(self) -> None:
        from factpy.application.derivation_check_runtime import _extract_term_value

        self.assertEqual(_extract_term_value(("string", "hello")), "hello")
        self.assertEqual(_extract_term_value(("int", 42)), 42)

    def test_extract_term_value_marks_candidate_ref_unrepresentable(self) -> None:
        from factpy.application.derivation_check_runtime import (
            _extract_term_value,
            _UNREPRESENTABLE_TERM,
        )

        self.assertIs(
            _extract_term_value({"kind": "candidate_ref", "candidate_key": "candk_v2:x"}),
            _UNREPRESENTABLE_TERM,
        )

    def test_extract_head_var_binding_aligns_by_position(self) -> None:
        from factpy.application.derivation_check_runtime import _extract_head_var_binding

        candidate = _make_provenance_candidate(
            engine="problog",
            terms=[
                {"kind": "entity_ref", "value": "person-1"},
                {"kind": "literal", "tag": "int", "value": 25},
            ],
        )
        # plan with two head_vars: $p (var) + literal "age_role" (bare literal)
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred, head_var_names=("$p", "age_role"))
        binding = _extract_head_var_binding(candidate=candidate, plan=plan)

        self.assertEqual(binding, {"$p": "person-1"})  # bare "age_role" filtered
        self.assertNotIn("age_role", binding)

    def test_extract_head_var_binding_skips_candidate_ref_term(self) -> None:
        from factpy.application.derivation_check_runtime import _extract_head_var_binding

        candidate = _make_provenance_candidate(
            engine="problog",
            terms=[
                {"kind": "candidate_ref", "candidate_key": "candk_v2:x"},
                {"kind": "literal", "tag": "int", "value": 25},
            ],
        )
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred, head_var_names=("$p", "$age"))
        binding = _extract_head_var_binding(candidate=candidate, plan=plan)

        self.assertEqual(binding, {"$age": 25})
        self.assertNotIn("$p", binding)

    def test_extract_head_var_binding_returns_empty_on_shape_mismatch(self) -> None:
        from factpy.application.derivation_check_runtime import _extract_head_var_binding

        # 2 head_vars, only 1 term → mismatch
        candidate = _make_provenance_candidate(
            engine="problog",
            terms=[{"kind": "entity_ref", "value": "person-1"}],
        )
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred, head_var_names=("$p", "$q"))
        binding = _extract_head_var_binding(candidate=candidate, plan=plan)

        self.assertEqual(binding, {})


if __name__ == "__main__":
    unittest.main()
