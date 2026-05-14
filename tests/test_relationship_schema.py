"""Tests for Relationship SDK type and schema_ir compilation."""
from __future__ import annotations

import unittest

from factgraph.sdk import Entity, Identity, Field, Relationship
from factgraph.sdk.compile import compile_schema_from_classes, build_authoring_schema_from_classes
from factgraph.sdk.schema import SDKSchemaError


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")


class Friends(Relationship):
    from_entity = User
    to_entity = User
    strength: str = Field(cardinality="single")


class Owns(Relationship):
    from_entity = User
    to_entity: str = "Pet"  # string reference (entity not defined)
    affection: str = Field(cardinality="single")


class RelationshipSchemaTests(unittest.TestCase):

    def test_relationship_spec_has_required_fields(self) -> None:
        """Relationship.sdk_relationship_spec() returns correct structure."""
        spec = Friends.sdk_relationship_spec()
        self.assertEqual(spec["relationship_type"], "Friends")
        self.assertEqual(spec["from_entity_type"], "User")
        self.assertEqual(spec["to_entity_type"], "User")
        self.assertIsInstance(spec["fields"], list)
        self.assertEqual(len(spec["fields"]), 1)
        self.assertEqual(spec["fields"][0]["py_name"], "strength")

    def test_relationship_with_string_entity_ref(self) -> None:
        """Relationship can reference entity by string name."""
        spec = Owns.sdk_relationship_spec()
        self.assertEqual(spec["from_entity_type"], "User")
        self.assertEqual(spec["to_entity_type"], "Pet")

    def test_compile_schema_with_entities_and_relationships(self) -> None:
        """compile_schema_from_classes accepts both Entity and Relationship."""
        schema_ir = compile_schema_from_classes([User, Friends])
        pred_ids = [p["pred_id"] for p in schema_ir["predicates"]]
        # Entity predicates
        self.assertIn("User:exists", pred_ids)
        self.assertIn("user:name", pred_ids)
        # Relationship predicate
        self.assertIn("friends:strength", pred_ids)

    def test_relationship_predicate_shape(self) -> None:
        """Relationship predicate has (from_ref, to_ref, ...field_args) shape."""
        schema_ir = compile_schema_from_classes([User, Friends])
        friends_pred = next(
            p for p in schema_ir["predicates"] if p["pred_id"] == "friends:strength"
        )
        self.assertEqual(friends_pred["arity"], 3)
        arg_names = [a["name"] for a in friends_pred["arg_specs"]]
        self.assertEqual(arg_names[0], "from_ref")
        self.assertEqual(arg_names[1], "to_ref")
        self.assertEqual(arg_names[2], "strength")

    def test_relationship_predicate_carries_type_metadata(self) -> None:
        """Relationship predicate has relationship_type and entity type refs."""
        schema_ir = compile_schema_from_classes([User, Friends])
        friends_pred = next(
            p for p in schema_ir["predicates"] if p["pred_id"] == "friends:strength"
        )
        self.assertEqual(friends_pred.get("owner_type"), "Friends")
        self.assertEqual(friends_pred.get("relationship_type"), "Friends")
        self.assertEqual(friends_pred.get("from_entity_type"), "User")
        self.assertEqual(friends_pred.get("to_entity_type"), "User")

    def test_relationship_predicate_has_group_key_indexes(self) -> None:
        """Relationship predicate indexes from_ref and to_ref as group keys."""
        schema_ir = compile_schema_from_classes([User, Friends])
        friends_pred = next(
            p for p in schema_ir["predicates"] if p["pred_id"] == "friends:strength"
        )
        self.assertEqual(friends_pred.get("group_key_indexes"), [0, 1])

    def test_entity_only_compilation_unchanged(self) -> None:
        """Entity-only compilation still works (backward compat)."""
        schema_ir = compile_schema_from_classes([User])
        pred_ids = [p["pred_id"] for p in schema_ir["predicates"]]
        self.assertIn("User:exists", pred_ids)
        self.assertIn("user:name", pred_ids)
        # No relationship predicates
        for p in schema_ir["predicates"]:
            self.assertNotIn("relationship_type", p)

    def test_build_authoring_schema_includes_relationships(self) -> None:
        """build_authoring_schema_from_classes returns relationships key."""
        payload = build_authoring_schema_from_classes([User, Friends])
        self.assertIn("entities", payload)
        self.assertIn("relationships", payload)
        self.assertEqual(len(payload["relationships"]), 1)
        self.assertEqual(payload["relationships"][0]["relationship_type"], "Friends")

    def test_relationship_without_fields_produces_no_predicates(self) -> None:
        """Relationship with no Field members produces no predicates."""
        class EmptyRel(Relationship):
            from_entity = User
            to_entity = User

        schema_ir = compile_schema_from_classes([User, EmptyRel])
        rel_preds = [p for p in schema_ir["predicates"] if p.get("relationship_type")]
        self.assertEqual(len(rel_preds), 0)

    def test_relationship_missing_from_entity_raises(self) -> None:
        """Relationship without from_entity raises SDKSchemaError."""
        with self.assertRaises(SDKSchemaError):
            class BadRel(Relationship):
                to_entity = User
                value: str = Field(cardinality="single")

    def test_relationship_missing_to_entity_raises(self) -> None:
        """Relationship without to_entity raises SDKSchemaError."""
        with self.assertRaises(SDKSchemaError):
            class BadRel(Relationship):
                from_entity = User
                value: str = Field(cardinality="single")

    def test_multiple_relationships_compiled(self) -> None:
        """Multiple Relationship types compile correctly."""
        schema_ir = compile_schema_from_classes([User, Friends, Owns])
        rel_preds = [p for p in schema_ir["predicates"] if p.get("relationship_type")]
        rel_types = {p["relationship_type"] for p in rel_preds}
        self.assertEqual(rel_types, {"Friends", "Owns"})


if __name__ == "__main__":
    unittest.main()
