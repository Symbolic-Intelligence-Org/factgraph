"""Runtime tests for Fact Overlay native execution."""

from __future__ import annotations

from dataclasses import dataclass
import unittest
from typing import Any
from unittest.mock import patch

from factpy.application import (
    build_schema_index,
    check_fact_overlay_binding,
    entity_info,
    field_predicate,
    resolve_selector,
)
from factpy.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    EntitySelector,
    EvaluationOverlay,
    FactOverlayCheckRequest,
    FactRemoveAction,
    FactValueOverride,
    OverlayCheckPhase,
    RuleDisableAction,
)
from factpy.core.evidence.write_protocol import set_field
from factpy.core.rules.rule_ir import RuleRegistry
from factpy.core.store._support import ProjectedFact
from factpy.core.store import Store
from factpy.sdk import Entity, Field, Identity, compile_schema_from_classes

from factpy.application.fact_overlay_runtime import (
    _apply_fact_overlay_projection,
    _build_overlay_diff,
    _validate_fact_overlay_actions,
)


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")
    region: str = Field(cardinality="single")


@dataclass(frozen=True)
class SeededPerson:
    e_ref: str
    exists_asrt_id: str
    name_asrt_id: str
    age_asrt_id: str
    region_asrt_id: str
    age_pred_id: str
    region_pred_id: str


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
) -> SeededPerson:
    ref = resolve_selector(
        EntitySelector(entity_type="Person", identity={"name": name}),
        index=index,
    )
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    exists_asrt_id = set_field(store.ledger, info.exists_predicate_id, encoded, [])
    name_asrt_id = set_field(
        store.ledger,
        info.identity_predicates["name"].pred_id,
        encoded,
        [("string", name)],
    )
    age_pred_id = field_predicate(index, "Person", "age").pred_id
    age_asrt_id = set_field(
        store.ledger,
        age_pred_id,
        encoded,
        [("int", age)],
    )
    region_pred_id = field_predicate(index, "Person", "region").pred_id
    region_asrt_id = set_field(
        store.ledger,
        region_pred_id,
        encoded,
        [("string", region)],
    )
    return SeededPerson(
        e_ref=encoded,
        exists_asrt_id=exists_asrt_id,
        name_asrt_id=name_asrt_id,
        age_asrt_id=age_asrt_id,
        region_asrt_id=region_asrt_id,
        age_pred_id=age_pred_id,
        region_pred_id=region_pred_id,
    )


def _build_plan(
    body_ir: list[Any],
    target_pred_id: str,
    head_var_names: tuple[str, ...] = ("$p",),
) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="overlay-test",
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


def _exists_plus_age_region_body(index: Any) -> tuple[list[Any], str]:
    info = entity_info(index, "Person")
    age_pred = field_predicate(index, "Person", "age").pred_id
    region_pred = field_predicate(index, "Person", "region").pred_id
    body: list[Any] = [
        ("pred", info.exists_predicate_id, ["$p"]),
        ("pred", age_pred, ["$p", "$age"]),
        ("pred", region_pred, ["$p", "$region"]),
    ]
    return body, info.exists_predicate_id


def _override(
    seeded: SeededPerson | None = None,
    *,
    new_age: int = 26,
) -> FactValueOverride:
    if seeded is None:
        return FactValueOverride(
            asrt_id="asrt-placeholder",
            pred_id="Person.age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
            new_fact_tuple=("person:alice", new_age),
        )
    return FactValueOverride(
        asrt_id=seeded.age_asrt_id,
        pred_id=seeded.age_pred_id,
        e_ref=seeded.e_ref,
        old_fact_tuple=(seeded.e_ref, 25),
        new_fact_tuple=(seeded.e_ref, new_age),
    )


def _region_override(seeded: SeededPerson, *, new_region: str) -> FactValueOverride:
    return FactValueOverride(
        asrt_id=seeded.region_asrt_id,
        pred_id=seeded.region_pred_id,
        e_ref=seeded.e_ref,
        old_fact_tuple=(seeded.e_ref, "us"),
        new_fact_tuple=(seeded.e_ref, new_region),
    )


def _remove_age(seeded: SeededPerson) -> FactRemoveAction:
    return FactRemoveAction(
        asrt_id=seeded.age_asrt_id,
        pred_id=seeded.age_pred_id,
        e_ref=seeded.e_ref,
        old_fact_tuple=(seeded.e_ref, 25),
    )


def _request(
    *,
    plan: CompiledDerivationPlan,
    binding: tuple[tuple[str, object], ...],
    overlay: tuple[FactValueOverride, ...] | EvaluationOverlay,
    engine: str = "native",
) -> FactOverlayCheckRequest:
    return FactOverlayCheckRequest(
        plan=plan,
        binding=binding,
        overlay=overlay,
        engine=engine,  # type: ignore[arg-type]
    )


def _ledger_dump(store: Store) -> bytes:
    return "\n".join(store.ledger._get_connection().iterdump()).encode("utf-8")


class FactOverlayRuntimePreflightTests(unittest.TestCase):
    """§7-Overlay-5 / §7-Overlay-6: preflight result gates."""

    def test_empty_overlay_returns_invalid_request(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(),
            overlay=(),
        )

        result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "invalid_request")
        self.assertIsNone(result.before)
        self.assertIsNone(result.after)
        self.assertIsNone(result.diff)
        self.assertEqual(result.errors[0].code, "EMPTY_OVERLAY_NOT_PERMITTED")

    def test_rule_actions_are_rejected_before_empty_fact_overlay(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(),
            overlay=EvaluationOverlay(
                rule_actions=(
                    RuleDisableAction(
                        rule_id="person.eligible",
                        version="1.0",
                        branch_index=0,
                        atom_index=0,
                    ),
                )
            ),
        )

        result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_ACTIONS_NOT_SUPPORTED")

    def test_ruleref_without_registry_returns_invalid_request(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(
            body + [("ruleref", "person.exists", "1.0", ["$p"])],
            exists_pred,
        )
        request = _request(plan=plan, binding=(), overlay=(_override(),))

        result = check_fact_overlay_binding(request, store=store, registry=None)

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "REGISTRY_REQUIRED")

    def test_ruleref_unresolvable_returns_invalid_request(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(
            body + [("ruleref", "missing.rule", "1.0", ["$p"])],
            exists_pred,
        )
        request = _request(plan=plan, binding=(), overlay=(_override(),))

        result = check_fact_overlay_binding(request, store=store, registry=RuleRegistry())

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_REF_UNRESOLVABLE")

    def test_malformed_ruleref_returns_invalid_request(self) -> None:
        malformed_atoms = (
            ("ruleref",),
            ("ruleref", "person.exists", "1.0"),
            ("ruleref", "person.exists", "1.0", "not-a-list"),
            ("ruleref", 123, "1.0", []),
            ("ruleref", "person.exists", 1.0, []),
        )
        for atom in malformed_atoms:
            with self.subTest(atom=atom):
                store, index = _build_store()
                body, exists_pred = _exists_body(index)
                plan = _build_plan(body + [atom], exists_pred)
                request = _request(plan=plan, binding=(), overlay=(_override(),))

                result = check_fact_overlay_binding(request, store=store, registry=RuleRegistry())

                self.assertEqual(result.status, "invalid_request")
                self.assertEqual(result.errors[0].code, "RULE_REF_MALFORMED")

    def test_malformed_ruleref_precedes_missing_registry(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body + [("ruleref", "person.exists", "1.0")], exists_pred)
        request = _request(plan=plan, binding=(), overlay=(_override(),))

        result = check_fact_overlay_binding(request, store=store, registry=None)

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_REF_MALFORMED")

    def test_non_native_engines_short_circuit_unsupported(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(body, exists_pred)
        for engine in ("souffle", "problog", "pyreason"):
            with self.subTest(engine=engine):
                result = check_fact_overlay_binding(
                    _request(
                        plan=plan,
                        binding=(),
                        overlay=(_override(),),
                        engine=engine,
                    ),
                    store=store,
                )
                self.assertEqual(result.status, "unsupported")
                self.assertIsNone(result.before)
                self.assertIsNone(result.after)
                self.assertIsNone(result.diff)
                self.assertEqual(result.errors[0].code, "ENGINE_OVERLAY_NOT_SUPPORTED")

    def test_non_native_ruleref_short_circuits_before_registry_preflight(self) -> None:
        store, index = _build_store()
        body, exists_pred = _exists_body(index)
        plan = _build_plan(
            body + [("ruleref", "person.exists", "1.0", ["$p"])],
            exists_pred,
        )

        result = check_fact_overlay_binding(
            _request(
                plan=plan,
                binding=(),
                overlay=(_override(),),
                engine="souffle",
            ),
            store=store,
            registry=None,
        )

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "ENGINE_OVERLAY_NOT_SUPPORTED")


class FactOverlayProjectionHelperTests(unittest.TestCase):
    """§7-Overlay-7 / §7-Overlay-8: projection-copy overlay behavior."""

    def test_apply_fact_overlay_projection_replaces_matching_row(self) -> None:
        witness = {
            "age": [
                ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25)),
                ProjectedFact(asrt_id="a2", fact_tuple=("person:bob", 40)),
            ]
        }
        override = FactValueOverride(
            asrt_id="a1",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
            new_fact_tuple=("person:alice", 26),
        )

        result = _apply_fact_overlay_projection((override,), witness)

        self.assertEqual(result["age"][0].fact_tuple, ("person:alice", 26))
        self.assertEqual(result["age"][1], witness["age"][1])
        self.assertEqual(witness["age"][0].fact_tuple, ("person:alice", 25))
        self.assertIsNot(result["age"], witness["age"])

    def test_apply_fact_overlay_projection_applies_multiple_overrides(self) -> None:
        witness = {
            "age": [ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25))],
            "region": [ProjectedFact(asrt_id="r1", fact_tuple=("person:alice", "us"))],
        }
        age_override = FactValueOverride(
            asrt_id="a1",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
            new_fact_tuple=("person:alice", 99),
        )
        region_override = FactValueOverride(
            asrt_id="r1",
            pred_id="region",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", "us"),
            new_fact_tuple=("person:alice", "ca"),
        )

        result = _apply_fact_overlay_projection((age_override, region_override), witness)

        self.assertEqual(result["age"][0].fact_tuple, ("person:alice", 99))
        self.assertEqual(result["region"][0].fact_tuple, ("person:alice", "ca"))

    def test_apply_fact_overlay_projection_removes_matching_row(self) -> None:
        witness = {
            "age": [
                ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25)),
                ProjectedFact(asrt_id="a2", fact_tuple=("person:bob", 40)),
            ]
        }
        action = FactRemoveAction(
            asrt_id="a1",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
        )

        result = _apply_fact_overlay_projection((action,), witness)

        self.assertEqual(result["age"], [witness["age"][1]])
        self.assertEqual(witness["age"][0].fact_tuple, ("person:alice", 25))
        self.assertIsNot(result["age"], witness["age"])

    def test_apply_fact_overlay_projection_ignores_unmatched_override(self) -> None:
        witness = {"age": [ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25))]}
        override = FactValueOverride(
            asrt_id="missing",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
            new_fact_tuple=("person:alice", 99),
        )

        result = _apply_fact_overlay_projection((override,), witness)

        self.assertEqual(result, witness)
        self.assertIsNot(result["age"], witness["age"])


class FactOverlayValidationHelperTests(unittest.TestCase):
    """§7-Overlay-7 / §7-Overlay-8: override validation guards."""

    def test_validate_fact_overlay_actions_accepts_visible_matching_override(self) -> None:
        witness = {"age": [ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25))]}
        schema_ir = {"predicates": [{"pred_id": "age", "group_key_indexes": [0]}]}
        override = FactValueOverride(
            asrt_id="a1",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
            new_fact_tuple=("person:alice", 99),
        )

        errors = _validate_fact_overlay_actions((override,), witness, schema_ir)

        self.assertEqual(errors, [])

    def test_validate_fact_overlay_actions_accepts_visible_matching_remove(self) -> None:
        witness = {"age": [ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25))]}
        schema_ir = {"predicates": [{"pred_id": "age", "group_key_indexes": [0]}]}
        action = FactRemoveAction(
            asrt_id="a1",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
        )

        errors = _validate_fact_overlay_actions((action,), witness, schema_ir)

        self.assertEqual(errors, [])

    def test_validate_fact_overlay_actions_collects_duplicate_asrt_ids(self) -> None:
        witness = {"age": [ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25))]}
        schema_ir = {"predicates": [{"pred_id": "age", "group_key_indexes": [0]}]}
        first = FactValueOverride(
            asrt_id="a1",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
            new_fact_tuple=("person:alice", 99),
        )
        second = FactValueOverride(
            asrt_id="a1",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
            new_fact_tuple=("person:alice", 100),
        )

        errors = _validate_fact_overlay_actions((first, second), witness, schema_ir)

        self.assertIn("OVERLAY_DUPLICATE_ASRT_ID", {error.code for error in errors})

    def test_validate_fact_overlay_actions_rejects_non_visible_asrt_id(self) -> None:
        override = FactValueOverride(
            asrt_id="missing",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
            new_fact_tuple=("person:alice", 99),
        )

        errors = _validate_fact_overlay_actions(
            (override,),
            {"age": [ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25))]},
            {"predicates": [{"pred_id": "age", "group_key_indexes": [0]}]},
        )

        self.assertEqual([error.code for error in errors], ["OVERLAY_ASRT_ID_NOT_VISIBLE"])

    def test_validate_fact_overlay_actions_rejects_stale_old_fact_tuple(self) -> None:
        override = FactValueOverride(
            asrt_id="a1",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 24),
            new_fact_tuple=("person:alice", 99),
        )

        errors = _validate_fact_overlay_actions(
            (override,),
            {"age": [ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25))]},
            {"predicates": [{"pred_id": "age", "group_key_indexes": [0]}]},
        )

        self.assertIn("OVERLAY_STALE_OLD_FACT_TUPLE", {error.code for error in errors})

    def test_validate_fact_overlay_actions_rejects_tuple_arity_mismatch(self) -> None:
        override = FactValueOverride(
            asrt_id="a1",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
            new_fact_tuple=("person:alice", 99, "extra"),
        )

        errors = _validate_fact_overlay_actions(
            (override,),
            {"age": [ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25))]},
            {"predicates": [{"pred_id": "age", "group_key_indexes": [0]}]},
        )

        self.assertIn("OVERLAY_TUPLE_ARITY_MISMATCH", {error.code for error in errors})

    def test_validate_fact_overlay_actions_rejects_e_ref_position_mismatch(self) -> None:
        override = FactValueOverride(
            asrt_id="a1",
            pred_id="age",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", 25),
            new_fact_tuple=("person:bob", 99),
        )

        errors = _validate_fact_overlay_actions(
            (override,),
            {"age": [ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25))]},
            {"predicates": [{"pred_id": "age", "group_key_indexes": [0]}]},
        )

        self.assertIn("OVERLAY_E_REF_POSITION_MISMATCH", {error.code for error in errors})

    def test_validate_fact_overlay_actions_rejects_group_key_change(self) -> None:
        override = FactValueOverride(
            asrt_id="rel1",
            pred_id="friend_strength",
            e_ref="person:alice",
            old_fact_tuple=("person:alice", "person:bob", "0.8"),
            new_fact_tuple=("person:alice", "person:cara", "0.8"),
        )

        errors = _validate_fact_overlay_actions(
            (override,),
            {
                "friend_strength": [
                    ProjectedFact(
                        asrt_id="rel1",
                        fact_tuple=("person:alice", "person:bob", "0.8"),
                    )
                ]
            },
            {"predicates": [{"pred_id": "friend_strength", "group_key_indexes": [0, 1]}]},
        )

        self.assertIn("OVERLAY_GROUP_KEY_CHANGED", {error.code for error in errors})

    def test_validate_fact_overlay_actions_collects_multiple_errors(self) -> None:
        override = FactValueOverride(
            asrt_id="a1",
            pred_id="age",
            e_ref="person:bob",
            old_fact_tuple=("person:bob", 24),
            new_fact_tuple=("person:cara", 99, "extra"),
        )

        errors = _validate_fact_overlay_actions(
            (override,),
            {"age": [ProjectedFact(asrt_id="a1", fact_tuple=("person:alice", 25))]},
            {"predicates": [{"pred_id": "age", "group_key_indexes": [0]}]},
        )

        self.assertGreaterEqual(len(errors), 3)
        self.assertIn("OVERLAY_STALE_OLD_FACT_TUPLE", {error.code for error in errors})
        self.assertIn("OVERLAY_TUPLE_ARITY_MISMATCH", {error.code for error in errors})
        self.assertIn("OVERLAY_E_REF_POSITION_MISMATCH", {error.code for error in errors})


class FactOverlayDiffHelperTests(unittest.TestCase):
    """§7-Overlay-12: diff is derived only from phase summaries."""

    def test_build_overlay_diff_no_change(self) -> None:
        phase = OverlayCheckPhase(
            status="passed",
            matched_count=1,
            matched_binding=(("$p", "person:alice"),),
        )

        diff = _build_overlay_diff(phase, phase)

        self.assertFalse(diff.status_changed)
        self.assertEqual(diff.matched_count_delta, 0)
        self.assertEqual(diff.bindings_added, ())
        self.assertEqual(diff.bindings_removed, ())

    def test_build_overlay_diff_pass_to_fail_removes_binding(self) -> None:
        before = OverlayCheckPhase(
            status="passed",
            matched_count=1,
            matched_binding=(("$p", "person:alice"),),
        )
        after = OverlayCheckPhase(status="failed", matched_count=0, matched_binding=None)

        diff = _build_overlay_diff(before, after)

        self.assertTrue(diff.status_changed)
        self.assertEqual(diff.matched_count_delta, -1)
        self.assertEqual(diff.bindings_added, ())
        self.assertEqual(diff.bindings_removed, ((("$p", "person:alice"),),))

    def test_build_overlay_diff_fail_to_pass_adds_binding(self) -> None:
        before = OverlayCheckPhase(status="failed", matched_count=0, matched_binding=None)
        after = OverlayCheckPhase(
            status="passed",
            matched_count=1,
            matched_binding=(("$p", "person:alice"),),
        )

        diff = _build_overlay_diff(before, after)

        self.assertTrue(diff.status_changed)
        self.assertEqual(diff.matched_count_delta, 1)
        self.assertEqual(diff.bindings_added, ((("$p", "person:alice"),),))
        self.assertEqual(diff.bindings_removed, ())


class FactOverlayRuntimeNativeDoubleRunTests(unittest.TestCase):
    """§7-Overlay-3 / §7-Overlay-4 / §7-Overlay-12: native double-run gates."""

    def test_native_overlay_pass_to_fail_reports_real_diff(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", seeded.e_ref), ("$age", 25)),
            overlay=(_override(seeded, new_age=99),),
        )

        result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.before.status, "passed")
        self.assertEqual(result.after.status, "failed")
        self.assertTrue(result.diff.status_changed)
        self.assertEqual(result.diff.matched_count_delta, -1)
        self.assertEqual(result.diff.bindings_added, ())
        self.assertEqual(
            result.diff.bindings_removed,
            (((("$age", 25), ("$p", seeded.e_ref))),),
        )

    def test_native_overlay_fail_to_pass_reports_real_diff(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", seeded.e_ref), ("$age", 99)),
            overlay=(_override(seeded, new_age=99),),
        )

        result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.before.status, "failed")
        self.assertEqual(result.after.status, "passed")
        self.assertTrue(result.diff.status_changed)
        self.assertEqual(result.diff.matched_count_delta, 1)
        self.assertEqual(
            result.diff.bindings_added,
            (((("$age", 99), ("$p", seeded.e_ref))),),
        )
        self.assertEqual(result.diff.bindings_removed, ())

    def test_native_overlay_multiple_overrides_are_applied(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_region_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", seeded.e_ref), ("$age", 99), ("$region", "ca")),
            overlay=(
                _override(seeded, new_age=99),
                _region_override(seeded, new_region="ca"),
            ),
        )

        result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.before.status, "failed")
        self.assertEqual(result.after.status, "passed")

    def test_native_overlay_remove_action_pass_to_fail(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", seeded.e_ref), ("$age", 25)),
            overlay=EvaluationOverlay(fact_actions=(_remove_age(seeded),)),
        )

        result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.before.status, "passed")
        self.assertEqual(result.after.status, "failed")
        self.assertTrue(result.diff.status_changed)
        self.assertEqual(result.diff.matched_count_delta, -1)
        self.assertEqual(
            result.diff.bindings_removed,
            (((("$age", 25), ("$p", seeded.e_ref))),),
        )

    def test_native_top_level_status_matches_after_status(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", seeded.e_ref),),
            overlay=(_override(seeded),),
        )

        result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, result.after.status)

    def test_native_phase_passes_remember_support_artifact_none(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", seeded.e_ref),),
            overlay=(_override(seeded),),
        )

        from factpy.application import fact_overlay_runtime

        calls: list[dict[str, object]] = []
        original = fact_overlay_runtime.evaluate_native_where

        def spy_evaluate_native_where(*args: object, **kwargs: object) -> object:
            calls.append(dict(kwargs))
            return original(*args, **kwargs)  # type: ignore[misc]

        with patch.object(
            fact_overlay_runtime,
            "evaluate_native_where",
            side_effect=spy_evaluate_native_where,
        ):
            result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertIn("remember_support_artifact", call)
            self.assertIsNone(call["remember_support_artifact"])

    def test_native_overlay_leaves_ledger_byte_identical_and_does_not_write(self) -> None:
        """§7-Overlay-3: overlay execution does not write ledger state."""
        store, index = _build_store()
        seeded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", seeded.e_ref), ("$age", 99)),
            overlay=(_override(seeded, new_age=99),),
        )
        before = _ledger_dump(store)

        with (
            patch.object(
                store.ledger,
                "append_assertion",
                side_effect=AssertionError("overlay must not append assertions"),
            ) as append_assertion,
            patch.object(
                store.ledger,
                "append_revocation",
                side_effect=AssertionError("overlay must not append revocations"),
            ) as append_revocation,
        ):
            result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(_ledger_dump(store), before)
        self.assertFalse(append_assertion.called)
        self.assertFalse(append_revocation.called)

    def test_native_remove_action_leaves_ledger_byte_identical_and_does_not_write(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_plus_age_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", seeded.e_ref), ("$age", 25)),
            overlay=EvaluationOverlay(fact_actions=(_remove_age(seeded),)),
        )
        before = _ledger_dump(store)

        with (
            patch.object(
                store.ledger,
                "append_assertion",
                side_effect=AssertionError("overlay must not append assertions"),
            ) as append_assertion,
            patch.object(
                store.ledger,
                "append_revocation",
                side_effect=AssertionError("overlay must not append revocations"),
            ) as append_revocation,
        ):
            result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(_ledger_dump(store), before)
        self.assertFalse(append_assertion.called)
        self.assertFalse(append_revocation.called)

    def test_native_overlay_does_not_write_live_store_caches(self) -> None:
        """§7-Overlay-4: overlay execution does not remember live cache artifacts."""
        store, index = _build_store()
        seeded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", seeded.e_ref),),
            overlay=(_override(seeded),),
        )

        with (
            patch.object(
                store,
                "_remember_support_artifact",
                side_effect=AssertionError("overlay must not remember support artifacts"),
            ) as remember_support,
            patch.object(
                store,
                "_remember_provenance_envelope",
                side_effect=AssertionError("overlay must not remember provenance"),
            ) as remember_provenance,
            patch.object(
                store,
                "_remember_candidate_support",
                side_effect=AssertionError("overlay must not remember candidate support"),
            ) as remember_candidate,
            patch.object(
                store,
                "_remember_rule_trace_artifact",
                side_effect=AssertionError("overlay must not remember rule traces"),
            ) as remember_rule_trace,
        ):
            result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertFalse(remember_support.called)
        self.assertFalse(remember_provenance.called)
        self.assertFalse(remember_candidate.called)
        self.assertFalse(remember_rule_trace.called)

    def test_native_validation_errors_return_invalid_request_before_phase_execution(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_body(index)
        invalid_override = FactValueOverride(
            asrt_id=seeded.age_asrt_id,
            pred_id=seeded.age_pred_id,
            e_ref=seeded.e_ref,
            old_fact_tuple=(seeded.e_ref, 24),
            new_fact_tuple=(seeded.e_ref, 99, "extra"),
        )
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", seeded.e_ref),),
            overlay=(invalid_override,),
        )

        from factpy.application import fact_overlay_runtime

        with patch.object(fact_overlay_runtime, "evaluate_native_where") as spy:
            result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "invalid_request")
        self.assertIsNone(result.before)
        self.assertIsNone(result.after)
        self.assertIsNone(result.diff)
        self.assertFalse(spy.called)
        self.assertIn("OVERLAY_STALE_OLD_FACT_TUPLE", {error.code for error in result.errors})
        self.assertIn("OVERLAY_TUPLE_ARITY_MISMATCH", {error.code for error in result.errors})

    def test_native_phase_runtime_error_returns_no_partial_phases(self) -> None:
        store, index = _build_store()
        seeded = _seed_person(store, index, "alice", 25, "us")
        body, exists_pred = _exists_body(index)
        request = _request(
            plan=_build_plan(body, exists_pred),
            binding=(("$p", seeded.e_ref),),
            overlay=(_override(seeded),),
        )

        from factpy.application import fact_overlay_runtime

        with patch.object(
            fact_overlay_runtime,
            "_run_native_overlay_phase",
            side_effect=RuntimeError("boom"),
        ):
            result = check_fact_overlay_binding(request, store=store)

        self.assertEqual(result.status, "invalid_request")
        self.assertIsNone(result.before)
        self.assertIsNone(result.after)
        self.assertIsNone(result.diff)
        self.assertEqual(result.errors[0].code, "OVERLAY_PHASE_RUNTIME_ERROR")


if __name__ == "__main__":
    unittest.main()
