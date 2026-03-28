"""Tests for PyReason engine-specific write session.

Validates schema enforcement, bound handling, confidence auto-derivation,
node/edge fact separation, entity-level batch API, and annotation template
generation. No real PyReason dependency.
"""
from __future__ import annotations

import unittest

from factpy_kernel.adapters.pyreason.session import (
    PyReasonBatchTx,
    PyReasonEntityHandle,
    PyReasonSession,
    _owner_prefix,
)
from factpy_kernel.sdk.schema import Entity, Field, Identity, Relationship


class User(Entity):
    user_id: str = Identity()
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")
    popular: str = Field(cardinality="single")


class Pet(Entity):
    pet_id: str = Identity()
    species: str = Field(cardinality="single")


class Friends(Relationship):
    from_entity = User
    to_entity = User
    strength: str = Field(cardinality="single")


def _test_schema_ir() -> dict[str, object]:
    """Raw schema_ir matching Entity/Relationship classes above."""
    return {
        "predicates": [
            {"pred_id": "user:name", "arity": 2},
            {"pred_id": "user:tag", "arity": 2},
            {"pred_id": "user:popular", "arity": 2},
            {"pred_id": "pet:species", "arity": 2},
            {
                "pred_id": "friends:strength",
                "arity": 3,
                "relationship_type": "Friends",
                "from_entity_type": "User",
                "to_entity_type": "User",
            },
        ],
    }


class PyReasonSessionInternalTests(unittest.TestCase):
    """Tests for direct fact writing on the session."""

    def _session(self) -> PyReasonSession:
        return PyReasonSession(_test_schema_ir())

    def test_write_node_fact_validates_pred_id(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError) as ctx:
            s._write_node_fact_internal("nonexistent:pred", "ref", "val")
        self.assertIn("not found in schema_ir", str(ctx.exception))

    def test_write_node_fact_rejects_relationship_pred(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError) as ctx:
            s._write_node_fact_internal("friends:strength", "ref", "val")
        self.assertIn("relationship predicate", str(ctx.exception))

    def test_write_edge_fact_validates_pred_id(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError) as ctx:
            s._write_edge_fact_internal("nonexistent:pred", "a", "b")
        self.assertIn("not found in schema_ir", str(ctx.exception))

    def test_write_edge_fact_rejects_non_relationship_pred(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError) as ctx:
            s._write_edge_fact_internal("user:name", "a", "b")
        self.assertIn("not a relationship predicate", str(ctx.exception))

    def test_default_bound_is_definitely_true(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "ref", "Alice")
        self.assertEqual(s.node_facts[0]["bound"], (1.0, 1.0))

    def test_public_write_node_fact_wrapper_still_works(self) -> None:
        s = self._session()
        s.write_node_fact("user:name", "ref", "Alice")
        self.assertEqual(s.node_facts[0]["value"], "Alice")

    def test_public_write_edge_fact_wrapper_still_works(self) -> None:
        s = self._session()
        s.write_edge_fact("friends:strength", "a", "b", "0.9")
        self.assertEqual(s.edge_facts[0]["value"], "0.9")

    def test_custom_bound_stored(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "ref", "Alice", bound=[0.6, 0.9])
        self.assertEqual(s.node_facts[0]["bound"], (0.6, 0.9))

    def test_bound_validation_rejects_out_of_range(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError):
            s._write_node_fact_internal("user:name", "ref", "val", bound=[1.5, 2.0])

    def test_bound_validation_rejects_inverted(self) -> None:
        s = self._session()
        with self.assertRaises(ValueError):
            s._write_node_fact_internal("user:name", "ref", "val", bound=[0.9, 0.3])

    def test_bound_accepts_zero_lower(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "ref", "val", bound=[0.0, 0.5])
        self.assertEqual(s.node_facts[0]["bound"], (0.0, 0.5))

    def test_confidence_auto_derived_from_bound_lower(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "ref", "Alice", bound=[0.7, 0.9])
        self.assertAlmostEqual(s.node_facts[0]["meta"]["confidence"], 0.7)
        self.assertEqual(s.node_facts[0]["meta"]["confidence_source"], "pyreason:lower_bound")

    def test_explicit_confidence_preserved(self) -> None:
        s = self._session()
        s._write_node_fact_internal(
            "user:name",
            "ref",
            "Alice",
            bound=[0.7, 0.9],
            meta={"confidence": 0.85},
        )
        self.assertAlmostEqual(s.node_facts[0]["meta"]["confidence"], 0.85)
        self.assertEqual(s.node_facts[0]["meta"]["confidence_source"], "meta:confidence")

    def test_edge_fact_confidence_auto_derived(self) -> None:
        s = self._session()
        s._write_edge_fact_internal("friends:strength", "a", "b", "0.9", bound=[0.5, 0.8])
        self.assertAlmostEqual(s.edge_facts[0]["meta"]["confidence"], 0.5)

    def test_node_and_edge_facts_separate(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "ref1", "Alice")
        s._write_node_fact_internal("user:tag", "ref1", "vip")
        s._write_edge_fact_internal("friends:strength", "ref1", "ref2", "0.9")
        self.assertEqual(len(s.node_facts), 2)
        self.assertEqual(len(s.edge_facts), 1)

    def test_edge_fact_stores_from_to_refs(self) -> None:
        s = self._session()
        s._write_edge_fact_internal("friends:strength", "ref_a", "ref_b", "0.9")
        ef = s.edge_facts[0]
        self.assertEqual(ef["from_ref"], "ref_a")
        self.assertEqual(ef["to_ref"], "ref_b")

    def test_active_from_to_stored(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "ref", "Alice", active_from=2, active_to=7)
        self.assertEqual(s.node_facts[0]["active_from"], 2)
        self.assertEqual(s.node_facts[0]["active_to"], 7)

    def test_default_active_from_is_zero(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "ref", "Alice")
        self.assertEqual(s.node_facts[0]["active_from"], 0)
        self.assertIsNone(s.node_facts[0]["active_to"])

    def test_meta_fields_preserved(self) -> None:
        s = self._session()
        s._write_node_fact_internal(
            "user:name",
            "ref",
            "Alice",
            meta={"source": "ESA Report", "analyst": "Dr. Weber"},
        )
        m = s.node_facts[0]["meta"]
        self.assertEqual(m["source"], "ESA Report")
        self.assertEqual(m["analyst"], "Dr. Weber")
        self.assertIn("confidence", m)

    def test_all_facts_meta_includes_all(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "r1", "Alice", meta={"source": "a"})
        s._write_edge_fact_internal("friends:strength", "r1", "r2", "0.9", meta={"source": "b"})
        all_meta = s.all_facts_meta
        self.assertEqual(len(all_meta), 2)
        self.assertEqual(all_meta[0]["meta"]["source"], "a")
        self.assertEqual(all_meta[1]["meta"]["source"], "b")

    def test_empty_session_has_no_facts(self) -> None:
        s = self._session()
        self.assertEqual(len(s.node_facts), 0)
        self.assertEqual(len(s.edge_facts), 0)
        self.assertEqual(len(s.all_facts_meta), 0)


class OwnerPrefixTests(unittest.TestCase):
    def test_simple_camel(self) -> None:
        self.assertEqual(_owner_prefix("User"), "user")

    def test_multi_word(self) -> None:
        self.assertEqual(_owner_prefix("FriendRequest"), "friend_request")

    def test_already_lower(self) -> None:
        self.assertEqual(_owner_prefix("user"), "user")

    def test_empty(self) -> None:
        self.assertEqual(_owner_prefix(""), "")

    def test_acronym_boundary(self) -> None:
        self.assertEqual(_owner_prefix("HTTPClient"), "http_client")


class PyReasonBatchApiTests(unittest.TestCase):
    """Tests for entity-level batch API."""

    def _session(self) -> PyReasonSession:
        return PyReasonSession(_test_schema_ir())

    def test_entity_returns_handle(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            self.assertIsInstance(alice, PyReasonEntityHandle)
            self.assertEqual(alice._node_ref, "Alice")

    def test_entity_dedup_same_identity(self) -> None:
        s = self._session()
        with s.batch() as tx:
            h1 = tx.entity(User, user_id="Alice")
            h2 = tx.entity(User, user_id="Alice")
            self.assertIs(h1, h2)

    def test_entity_same_node_ref_different_type_stays_distinct(self) -> None:
        s = self._session()
        with s.batch() as tx:
            user = tx.entity(User, user_id="shared-id")
            pet = tx.entity(Pet, pet_id="shared-id")
            self.assertIsNot(user, pet)

    def test_entity_rejects_non_entity_class(self) -> None:
        s = self._session()
        with s.batch() as tx:
            with self.assertRaises(ValueError) as ctx:
                tx.entity(str, name="test")
            self.assertIn("not an Entity class", str(ctx.exception))

    def test_entity_rejects_no_identity(self) -> None:
        s = self._session()
        with s.batch() as tx:
            with self.assertRaises(ValueError):
                tx.entity(User)

    def test_field_set_stages_node_fact(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            alice.name.set("Alice", bound=[1.0, 1.0])
            tx.commit()
        self.assertEqual(len(s.node_facts), 1)
        fact = s.node_facts[0]
        self.assertEqual(fact["pred_id"], "user:name")
        self.assertEqual(fact["node_ref"], "Alice")
        self.assertEqual(fact["value"], "Alice")
        self.assertEqual(fact["bound"], (1.0, 1.0))

    def test_field_set_with_custom_bound(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            alice.popular.set("true", bound=[0.6, 0.9])
            tx.commit()
        self.assertEqual(s.node_facts[0]["bound"], (0.6, 0.9))

    def test_field_set_with_temporal(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            alice.name.set("Alice", active_from=2, active_to=5)
            tx.commit()
        self.assertEqual(s.node_facts[0]["active_from"], 2)
        self.assertEqual(s.node_facts[0]["active_to"], 5)

    def test_field_set_with_meta(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            alice.name.set("Alice", meta={"source": "profile"})
            tx.commit()
        self.assertEqual(s.node_facts[0]["meta"]["source"], "profile")

    def test_field_set_returns_entity_handle_for_chaining(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            result = alice.name.set("Alice")
            self.assertIs(result, alice)

    def test_field_handle_caching(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            h1 = alice.name
            h2 = alice.name
            self.assertIs(h1, h2)

    def test_unknown_field_raises_attribute_error(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            with self.assertRaises(AttributeError) as ctx:
                alice.nonexistent_field
            self.assertIn("no field", str(ctx.exception))

    def test_multiple_fields_on_same_entity(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            alice.name.set("Alice")
            alice.tag.set("vip")
            alice.popular.set("true", bound=[0.8, 0.9])
            tx.commit()
        self.assertEqual(len(s.node_facts), 3)
        pred_ids = {f["pred_id"] for f in s.node_facts}
        self.assertEqual(pred_ids, {"user:name", "user:tag", "user:popular"})

    def test_multiple_entities(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            alice.name.set("Alice")
            bob = tx.entity(User, user_id="Bob")
            bob.name.set("Bob")
            tx.commit()
        self.assertEqual(len(s.node_facts), 2)
        refs = {f["node_ref"] for f in s.node_facts}
        self.assertEqual(refs, {"Alice", "Bob"})

    def test_relationship_stages_edge_fact(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            bob = tx.entity(User, user_id="Bob")
            tx.relationship(Friends, from_entity=alice, to_entity=bob, strength="0.9", bound=[0.9, 0.9])
            tx.commit()
        self.assertEqual(len(s.edge_facts), 1)
        ef = s.edge_facts[0]
        self.assertEqual(ef["pred_id"], "friends:strength")
        self.assertEqual(ef["from_ref"], "Alice")
        self.assertEqual(ef["to_ref"], "Bob")
        self.assertEqual(ef["value"], "0.9")
        self.assertEqual(ef["bound"], (0.9, 0.9))

    def test_relationship_rejects_non_relationship_class(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            bob = tx.entity(User, user_id="Bob")
            with self.assertRaises(ValueError) as ctx:
                tx.relationship(User, from_entity=alice, to_entity=bob, name="test")
            self.assertIn("not a Relationship class", str(ctx.exception))

    def test_relationship_rejects_unknown_fields(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            bob = tx.entity(User, user_id="Bob")
            with self.assertRaises(ValueError) as ctx:
                tx.relationship(Friends, from_entity=alice, to_entity=bob, strength="0.9", unknown_field="x")
            self.assertIn("Unknown fields", str(ctx.exception))

    def test_batch_context_manager(self) -> None:
        s = self._session()
        with s.batch() as tx:
            self.assertIsInstance(tx, PyReasonBatchTx)

    def test_full_scenario_from_handoff(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            alice.name.set("Alice", bound=[1.0, 1.0])
            alice.popular.set("true", bound=[1.0, 1.0])

            bob = tx.entity(User, user_id="Bob")
            bob.name.set("Bob", bound=[1.0, 1.0])

            tx.relationship(Friends, from_entity=alice, to_entity=bob, strength="0.9", bound=[0.9, 0.9])
            tx.commit()

        self.assertEqual(len(s.node_facts), 3)
        self.assertEqual(len(s.edge_facts), 1)
        self.assertEqual(len(s.all_facts_meta), 4)


class AnnotationTemplateTests(unittest.TestCase):
    """Tests for annotation template generation."""

    def _session(self) -> PyReasonSession:
        return PyReasonSession(_test_schema_ir())

    def test_node_fact_generates_annotation_templates(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "Alice", "Alice", bound=[0.6, 0.9])
        templates = s.annotation_templates
        self.assertGreaterEqual(len(templates), 4)

        keys = {t["key"] for t in templates}
        self.assertIn("bound_lower", keys)
        self.assertIn("bound_upper", keys)
        self.assertIn("confidence", keys)
        self.assertIn("confidence_source", keys)

    def test_bound_values_correct(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "Alice", "Alice", bound=[0.6, 0.9])
        by_key = {t["key"]: t for t in s.annotation_templates}
        self.assertEqual(by_key["bound_lower"]["value"], 0.6)
        self.assertEqual(by_key["bound_upper"]["value"], 0.9)
        self.assertEqual(by_key["bound_lower"]["namespace"], "pyreason")
        self.assertEqual(by_key["bound_lower"]["category"], "semantic")

    def test_confidence_derived_from_lower_bound(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "Alice", "Alice", bound=[0.6, 0.9])
        by_key = {t["key"]: t for t in s.annotation_templates}
        conf = by_key["confidence"]
        self.assertEqual(conf["value"], 0.6)
        self.assertEqual(conf["namespace"], "shared")
        self.assertEqual(conf["category"], "derived")
        self.assertEqual(conf["origin"], "derived")
        self.assertEqual(conf["derivation"], "pyreason:lower_bound")

    def test_active_from_omitted_when_default(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "Alice", "Alice")
        keys = {t["key"] for t in s.annotation_templates}
        self.assertNotIn("active_from", keys)
        self.assertNotIn("active_to", keys)

    def test_active_from_included_when_nonzero(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "Alice", "Alice", active_from=3, active_to=7)
        by_key = {t["key"]: t for t in s.annotation_templates}
        self.assertEqual(by_key["active_from"]["value"], 3)
        self.assertEqual(by_key["active_to"]["value"], 7)
        self.assertEqual(by_key["active_from"]["namespace"], "pyreason")
        self.assertEqual(by_key["active_from"]["category"], "semantic")

    def test_source_meta_forwarded_as_annotation(self) -> None:
        s = self._session()
        s._write_node_fact_internal(
            "user:name",
            "Alice",
            "Alice",
            meta={"source": "ESA handbook", "analyst": "Dr. Weber"},
        )
        by_key = {t["key"]: t for t in s.annotation_templates}
        self.assertEqual(by_key["source"]["value"], "ESA handbook")
        self.assertEqual(by_key["source"]["namespace"], "shared")
        self.assertEqual(by_key["source"]["category"], "source")
        self.assertEqual(by_key["analyst"]["value"], "Dr. Weber")

    def test_edge_fact_generates_templates(self) -> None:
        s = self._session()
        s._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9", bound=[0.9, 0.9])
        templates = s.annotation_templates
        self.assertGreaterEqual(len(templates), 4)
        self.assertTrue(all(t["fact_kind"] == "edge" for t in templates))

    def test_templates_have_placeholder_asrt_id(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "Alice", "Alice")
        for template in s.annotation_templates:
            self.assertEqual(template["asrt_id"], "")

    def test_templates_property_returns_copy(self) -> None:
        s = self._session()
        s._write_node_fact_internal("user:name", "Alice", "Alice")
        snapshot = s.annotation_templates
        snapshot.append({"fake": True})
        self.assertNotEqual(len(s.annotation_templates), len(snapshot))

    def test_empty_session_has_no_templates(self) -> None:
        s = self._session()
        self.assertEqual(len(s.annotation_templates), 0)

    def test_batch_api_generates_templates(self) -> None:
        s = self._session()
        with s.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            alice.name.set("Alice", bound=[0.7, 0.8])
            tx.relationship(
                Friends,
                from_entity=alice,
                to_entity=tx.entity(User, user_id="Bob"),
                strength="0.9",
                bound=[0.9, 0.9],
            )
            tx.commit()
        templates = s.annotation_templates
        self.assertGreaterEqual(len(templates), 8)
        node_templates = [t for t in templates if t["fact_kind"] == "node"]
        edge_templates = [t for t in templates if t["fact_kind"] == "edge"]
        self.assertGreaterEqual(len(node_templates), 4)
        self.assertGreaterEqual(len(edge_templates), 4)


if __name__ == "__main__":
    unittest.main()
