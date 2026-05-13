"""Tests for application-layer capability ergonomics helpers."""

from __future__ import annotations

from dataclasses import dataclass
import unittest
from typing import Any

from kernel.application import (
    CapabilityHelperError,
    build_evaluation_overlay,
    build_fact_remove_action,
    build_fact_value_override,
    build_frontier_view_facts,
    build_schema_index,
    build_why_not_candidate_universe,
    entity_info,
    field_predicate,
    resolve_selector,
)
from kernel.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    EntitySelector,
    EvaluationOverlay,
    FactRemoveAction,
    FieldPath,
    WhyNotUniverseRequest,
)
from kernel.core.evidence.write_protocol import add_field, set_field
from kernel.core.rules.frontier import evaluate_native_where_frontier
from kernel.core.store import Store
from kernel.core.store._support import normalize_binding_items
from kernel.core.view.projector import project_view_facts
from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")
    region: str = Field(cardinality="single")


class Team(Entity):
    name: str = Identity(primary_key=True)
    score: int = Field(cardinality="single")


class Reading(Entity):
    name: str = Identity(primary_key=True)
    value: float = Field(cardinality="single")


class Profile(Entity):
    name: str = Identity(primary_key=True)
    tag: str = Field(cardinality="multi")


@dataclass(frozen=True)
class SeededPerson:
    e_ref: str
    age_asrt_id: str | None
    age_pred_id: str


def _build_store() -> tuple[Store, Any]:
    schema_ir = compile_schema_from_classes([Person, Team, Reading, Profile])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


def _seed_person(
    store: Store,
    index: Any,
    *,
    name: str = "alice",
    age: int | None = 25,
    region: str = "us",
) -> SeededPerson:
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
    age_pred_id = field_predicate(index, "Person", "age").pred_id
    age_asrt_id = None
    if age is not None:
        age_asrt_id = set_field(store.ledger, age_pred_id, encoded, [("int", age)])
    region_pred_id = field_predicate(index, "Person", "region").pred_id
    set_field(store.ledger, region_pred_id, encoded, [("string", region)])
    return SeededPerson(
        e_ref=encoded,
        age_asrt_id=age_asrt_id,
        age_pred_id=age_pred_id,
    )


def _seed_reading(
    store: Store,
    index: Any,
    *,
    name: str = "temperature",
    value: float | str = "0x3ff8000000000000",
) -> tuple[str, str]:
    ref = resolve_selector(
        EntitySelector(entity_type="Reading", identity={"name": name}),
        index=index,
    )
    info = entity_info(index, "Reading")
    encoded = ref.encoded_ref or ""
    set_field(store.ledger, info.exists_predicate_id, encoded, [])
    set_field(
        store.ledger,
        info.identity_predicates["name"].pred_id,
        encoded,
        [("string", name)],
    )
    value_pred_id = field_predicate(index, "Reading", "value").pred_id
    set_field(store.ledger, value_pred_id, encoded, [("float64", value)])
    return encoded, value_pred_id


def _seed_profile_tags(
    store: Store,
    index: Any,
    *,
    name: str = "alice",
    tags: tuple[str, ...] = ("red",),
) -> tuple[str, str, tuple[str, ...]]:
    ref = resolve_selector(
        EntitySelector(entity_type="Profile", identity={"name": name}),
        index=index,
    )
    info = entity_info(index, "Profile")
    encoded = ref.encoded_ref or ""
    set_field(store.ledger, info.exists_predicate_id, encoded, [])
    set_field(
        store.ledger,
        info.identity_predicates["name"].pred_id,
        encoded,
        [("string", name)],
    )
    tag_pred_id = field_predicate(index, "Profile", "tag").pred_id
    asrt_ids = tuple(
        add_field(store.ledger, tag_pred_id, encoded, [("string", tag)]) for tag in tags
    )
    return encoded, tag_pred_id, asrt_ids


def _build_plan(index: Any) -> CompiledDerivationPlan:
    info = entity_info(index, "Person")
    age_pred = field_predicate(index, "Person", "age").pred_id
    region_pred = field_predicate(index, "Person", "region").pred_id
    return CompiledDerivationPlan(
        derivation_id="capability-helper-test",
        version="1.0",
        body_ir=[
            ("pred", info.exists_predicate_id, ["$p"]),
            ("pred", age_pred, ["$p", "$age"]),
            ("pred", region_pred, ["$p", "$region"]),
        ],
        heads=(
            CompiledHeadCall(
                target_pred_id=info.exists_predicate_id,
                head_var_names=("$p", "$age", "$region"),
            ),
        ),
    )


class FactValueOverrideHelperTests(unittest.TestCase):
    def test_builds_override_from_active_single_scalar_fact(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index)

        override = build_fact_value_override(
            store,
            index,
            e_ref=alice.e_ref,
            field=FieldPath(entity_type="Person", field_name="age"),
            new_value=30,
            note="helper test",
        )

        self.assertEqual(override.asrt_id, alice.age_asrt_id)
        self.assertEqual(override.pred_id, alice.age_pred_id)
        self.assertEqual(override.e_ref, alice.e_ref)
        self.assertEqual(override.old_fact_tuple, (alice.e_ref, 25))
        self.assertEqual(override.new_fact_tuple, (alice.e_ref, 30))
        self.assertEqual(override.note, "helper test")

    def test_missing_active_field_fact_raises_helper_error(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index, age=None)

        with self.assertRaisesRegex(CapabilityHelperError, "no active projected fact"):
            build_fact_value_override(
                store,
                index,
                e_ref=alice.e_ref,
                field=FieldPath(entity_type="Person", field_name="age"),
                new_value=30,
            )

    def test_entity_field_mismatch_raises_helper_error(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index)

        with self.assertRaisesRegex(CapabilityHelperError, "does not match"):
            build_fact_value_override(
                store,
                index,
                e_ref=alice.e_ref,
                field=FieldPath(entity_type="Team", field_name="score"),
                new_value=10,
            )

    def test_float64_hex_string_value_matches_write_protocol_convention(self) -> None:
        store, index = _build_store()
        e_ref, value_pred_id = _seed_reading(store, index)

        override = build_fact_value_override(
            store,
            index,
            e_ref=e_ref,
            field=FieldPath(entity_type="Reading", field_name="value"),
            new_value="0x40091eb851eb851f",
        )

        self.assertEqual(override.pred_id, value_pred_id)
        self.assertEqual(override.old_fact_tuple, (e_ref, "0x3ff8000000000000"))
        self.assertEqual(override.new_fact_tuple, (e_ref, "0x40091eb851eb851f"))

    def test_float64_decimal_string_raises_helper_error(self) -> None:
        store, index = _build_store()
        e_ref, _value_pred_id = _seed_reading(store, index)

        with self.assertRaisesRegex(CapabilityHelperError, "canonical float64 hex"):
            build_fact_value_override(
                store,
                index,
                e_ref=e_ref,
                field=FieldPath(entity_type="Reading", field_name="value"),
                new_value="3.14",
            )


class FactRemoveActionHelperTests(unittest.TestCase):
    def test_builds_remove_action_from_active_single_scalar_fact(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index)

        action = build_fact_remove_action(
            store,
            index,
            e_ref=alice.e_ref,
            field=FieldPath(entity_type="Person", field_name="age"),
            note="remove age",
        )

        self.assertEqual(action.asrt_id, alice.age_asrt_id)
        self.assertEqual(action.pred_id, alice.age_pred_id)
        self.assertEqual(action.e_ref, alice.e_ref)
        self.assertEqual(action.old_fact_tuple, (alice.e_ref, 25))
        self.assertEqual(action.note, "remove age")

    def test_builds_remove_action_matching_current_value(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index)

        action = build_fact_remove_action(
            store,
            index,
            e_ref=alice.e_ref,
            field=FieldPath(entity_type="Person", field_name="age"),
            current_value=25,
        )

        self.assertEqual(action.old_fact_tuple, (alice.e_ref, 25))

    def test_remove_action_current_value_miss_raises_helper_error(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index)

        with self.assertRaisesRegex(CapabilityHelperError, "no matching projected fact"):
            build_fact_remove_action(
                store,
                index,
                e_ref=alice.e_ref,
                field=FieldPath(entity_type="Person", field_name="age"),
                current_value=30,
            )

    def test_remove_action_multi_cardinality_requires_current_value_for_single_row(
        self,
    ) -> None:
        store, index = _build_store()
        e_ref, _tag_pred_id, _asrt_ids = _seed_profile_tags(store, index, tags=("red",))

        with self.assertRaisesRegex(CapabilityHelperError, "requires current_value"):
            build_fact_remove_action(
                store,
                index,
                e_ref=e_ref,
                field=FieldPath(entity_type="Profile", field_name="tag"),
            )

    def test_remove_action_multi_cardinality_requires_current_value_before_ambiguity(
        self,
    ) -> None:
        store, index = _build_store()
        e_ref, _tag_pred_id, _asrt_ids = _seed_profile_tags(
            store,
            index,
            tags=("red", "blue"),
        )

        with self.assertRaisesRegex(CapabilityHelperError, "requires current_value"):
            build_fact_remove_action(
                store,
                index,
                e_ref=e_ref,
                field=FieldPath(entity_type="Profile", field_name="tag"),
            )

    def test_builds_remove_action_for_multi_cardinality_matching_current_value(
        self,
    ) -> None:
        store, index = _build_store()
        e_ref, tag_pred_id, asrt_ids = _seed_profile_tags(store, index, tags=("red", "blue"))

        action = build_fact_remove_action(
            store,
            index,
            e_ref=e_ref,
            field=FieldPath(entity_type="Profile", field_name="tag"),
            current_value="blue",
        )

        self.assertEqual(action.asrt_id, asrt_ids[1])
        self.assertEqual(action.pred_id, tag_pred_id)
        self.assertEqual(action.old_fact_tuple, (e_ref, "blue"))

    def test_remove_action_multi_cardinality_current_value_miss_raises_helper_error(
        self,
    ) -> None:
        store, index = _build_store()
        e_ref, _tag_pred_id, _asrt_ids = _seed_profile_tags(store, index, tags=("red",))

        with self.assertRaisesRegex(CapabilityHelperError, "no matching projected fact"):
            build_fact_remove_action(
                store,
                index,
                e_ref=e_ref,
                field=FieldPath(entity_type="Profile", field_name="tag"),
                current_value="blue",
            )


class EvaluationOverlayHelperTests(unittest.TestCase):
    def test_builds_evaluation_overlay_from_fact_actions(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index)
        override = build_fact_value_override(
            store,
            index,
            e_ref=alice.e_ref,
            field=FieldPath(entity_type="Person", field_name="age"),
            new_value=30,
        )
        remove = build_fact_remove_action(
            store,
            index,
            e_ref=alice.e_ref,
            field=FieldPath(entity_type="Person", field_name="region"),
        )

        overlay = build_evaluation_overlay(override, remove)

        self.assertIsInstance(overlay, EvaluationOverlay)
        self.assertEqual(overlay.fact_actions, (override, remove))
        self.assertIsInstance(overlay.fact_actions[1], FactRemoveAction)

    def test_build_evaluation_overlay_requires_action(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "requires at least one action"):
            build_evaluation_overlay()


class WhyNotUniverseHelperTests(unittest.TestCase):
    def test_builds_universe_from_mapping_rows(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index)
        plan = _build_plan(index)

        universe = build_why_not_candidate_universe(
            plan,
            ({"$region": "us", "$p": alice.e_ref, "$age": 30},),
        )

        self.assertEqual(
            universe,
            (normalize_binding_items((("$p", alice.e_ref), ("$age", 30), ("$region", "us"))),),
        )
        request = WhyNotUniverseRequest(plan=plan, candidate_universe=universe, engine="native")
        self.assertEqual(request.candidate_universe, universe)

    def test_builds_universe_from_sequence_rows(self) -> None:
        store, index = _build_store()
        alice = _seed_person(store, index)
        plan = _build_plan(index)

        universe = build_why_not_candidate_universe(plan, ((alice.e_ref, 30, "us"),))

        self.assertEqual(
            universe,
            (normalize_binding_items((("$p", alice.e_ref), ("$age", 30), ("$region", "us"))),),
        )

    def test_incomplete_mapping_row_raises_helper_error(self) -> None:
        _store, index = _build_store()
        plan = _build_plan(index)

        with self.assertRaisesRegex(CapabilityHelperError, "missing head variables"):
            build_why_not_candidate_universe(plan, ({"$p": "person-1", "$age": 30},))


class FrontierStoreProjectionHelperTests(unittest.TestCase):
    def test_frontier_view_facts_matches_manual_projection(self) -> None:
        store, index = _build_store()
        _seed_person(store, index, name="alice", age=25, region="us")
        _seed_person(store, index, name="bob", age=30, region="eu")
        info = entity_info(index, "Person")
        age_pred = field_predicate(index, "Person", "age").pred_id
        region_pred = field_predicate(index, "Person", "region").pred_id
        where = [
            ("pred", info.exists_predicate_id, ["$p"]),
            ("pred", age_pred, ["$p", 99]),
            ("pred", region_pred, ["$p", "us"]),
        ]

        helper_view_facts = build_frontier_view_facts(store)
        manual_view_facts = project_view_facts(store.ledger, store.schema_ir)

        self.assertEqual(helper_view_facts, manual_view_facts)
        result = evaluate_native_where_frontier(helper_view_facts, where)
        self.assertEqual(len(result.frontier_rows), 1)
        self.assertEqual(result.frontier_rows[0].failed_atom_index, 1)


if __name__ == "__main__":
    unittest.main()
