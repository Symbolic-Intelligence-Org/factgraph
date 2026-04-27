"""Round-trip tests for PyReason accept helper."""
from __future__ import annotations

import unittest

from kernel.adapters.pyreason.accept import (
    AcceptResult,
    accept_pyreason_session,
)
from kernel.adapters.pyreason.session import PyReasonSession
from kernel.core.store.ledger import Ledger
from kernel.sdk.schema import Entity, Field, Identity, Relationship


class User(Entity):
    user_id: str = Identity()
    name: str = Field(cardinality="single")
    popular: str = Field(cardinality="single")


class Friends(Relationship):
    from_entity = User
    to_entity = User
    strength: str = Field(cardinality="single")


def _test_schema_ir() -> dict[str, object]:
    return {
        "predicates": [
            {
                "pred_id": "user:name",
                "arity": 2,
                "owner_type": "User",
                "arg_specs": [
                    {"name": "user", "type_domain": "entity_ref"},
                    {"name": "name", "type_domain": "string"},
                ],
            },
            {
                "pred_id": "user:popular",
                "arity": 2,
                "owner_type": "User",
                "arg_specs": [
                    {"name": "user", "type_domain": "entity_ref"},
                    {"name": "popular", "type_domain": "string"},
                ],
            },
            {
                "pred_id": "friends:strength",
                "arity": 3,
                "arg_specs": [
                    {"name": "from_ref", "type_domain": "entity_ref"},
                    {"name": "to_ref", "type_domain": "entity_ref"},
                    {"name": "strength", "type_domain": "string"},
                ],
                "relationship_type": "Friends",
                "from_entity_type": "User",
                "to_entity_type": "User",
            },
        ],
    }


class AcceptPyReasonSessionTests(unittest.TestCase):
    """Round-trip: session -> accept -> ledger -> verify."""

    def _setup(self) -> tuple[Ledger, PyReasonSession]:
        return Ledger(), PyReasonSession(_test_schema_ir())

    def test_accept_empty_session(self) -> None:
        ledger, session = self._setup()
        result = accept_pyreason_session(ledger, session)
        self.assertIsInstance(result, AcceptResult)
        self.assertEqual(result.node_asrt_ids, [])
        self.assertEqual(result.edge_asrt_ids, [])
        self.assertEqual(result.annotation_count, 0)

    def test_accept_single_node_fact(self) -> None:
        ledger, session = self._setup()
        session._write_node_fact_internal("user:name", "Alice", "Alice", bound=[0.8, 0.9])
        result = accept_pyreason_session(ledger, session)
        self.assertEqual(len(result.node_asrt_ids), 1)
        self.assertEqual(result.edge_asrt_ids, [])
        self.assertTrue(len(result.node_asrt_ids[0]) > 0)

    def test_accept_node_fact_creates_assertion(self) -> None:
        ledger, session = self._setup()
        session._write_node_fact_internal("user:name", "Alice", "Alice")
        result = accept_pyreason_session(ledger, session)
        claim = ledger.get_claim(result.node_asrt_ids[0])
        self.assertIsNotNone(claim)
        self.assertEqual(claim.pred_id, "user:name")
        self.assertEqual(claim.e_ref, "idref_v1:User:Alice")
        self.assertEqual(claim.rest_terms, [("string", "Alice")])

    def test_accept_edge_fact(self) -> None:
        ledger, session = self._setup()
        session._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9", bound=[0.9, 0.9])
        result = accept_pyreason_session(ledger, session)
        self.assertEqual(len(result.edge_asrt_ids), 1)
        claim = ledger.get_claim(result.edge_asrt_ids[0])
        self.assertIsNotNone(claim)
        self.assertEqual(claim.pred_id, "friends:strength")
        self.assertEqual(claim.e_ref, "idref_v1:User:Alice")
        self.assertEqual(claim.rest_terms, [("entity_ref", "idref_v1:User:Bob"), ("string", "0.9")])

    def test_accept_multiple_facts(self) -> None:
        ledger, session = self._setup()
        session._write_node_fact_internal("user:name", "Alice", "Alice")
        session._write_node_fact_internal("user:popular", "Alice", "true", bound=[0.6, 0.9])
        session._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9")
        result = accept_pyreason_session(ledger, session)
        self.assertEqual(len(result.node_asrt_ids), 2)
        self.assertEqual(len(result.edge_asrt_ids), 1)
        all_ids = result.node_asrt_ids + result.edge_asrt_ids
        self.assertEqual(len(set(all_ids)), 3)

    def test_pyreason_annotations_persisted(self) -> None:
        ledger, session = self._setup()
        session._write_node_fact_internal("user:name", "Alice", "Alice", bound=[0.6, 0.9])
        result = accept_pyreason_session(ledger, session)
        self.assertGreater(result.annotation_count, 0)
        asrt_id = result.node_asrt_ids[0]
        annotations = ledger.find_annotations(asrt_id=asrt_id, namespace="pyreason")
        keys = {a.key for a in annotations}
        self.assertIn("bound_lower", keys)
        self.assertIn("bound_upper", keys)

    def test_bound_values_correct_in_ledger(self) -> None:
        ledger, session = self._setup()
        session._write_node_fact_internal("user:name", "Alice", "Alice", bound=[0.6, 0.9])
        result = accept_pyreason_session(ledger, session)
        asrt_id = result.node_asrt_ids[0]
        annotations = ledger.find_annotations(asrt_id=asrt_id, namespace="pyreason")
        by_key = {a.key: a for a in annotations}
        self.assertAlmostEqual(float(by_key["bound_lower"].value), 0.6)
        self.assertAlmostEqual(float(by_key["bound_upper"].value), 0.9)
        self.assertEqual(by_key["bound_lower"].category, "semantic")
        self.assertEqual(by_key["bound_lower"].origin, "observed")

    def test_active_from_to_persisted_when_set(self) -> None:
        ledger, session = self._setup()
        session._write_node_fact_internal("user:name", "Alice", "Alice", active_from=3, active_to=7)
        result = accept_pyreason_session(ledger, session)
        asrt_id = result.node_asrt_ids[0]
        annotations = ledger.find_annotations(asrt_id=asrt_id, namespace="pyreason")
        by_key = {a.key: a for a in annotations}
        self.assertEqual(int(by_key["active_from"].value), 3)
        self.assertEqual(int(by_key["active_to"].value), 7)

    def test_active_from_not_persisted_when_default(self) -> None:
        ledger, session = self._setup()
        session._write_node_fact_internal("user:name", "Alice", "Alice")
        result = accept_pyreason_session(ledger, session)
        asrt_id = result.node_asrt_ids[0]
        annotations = ledger.find_annotations(asrt_id=asrt_id, namespace="pyreason")
        keys = {a.key for a in annotations}
        self.assertNotIn("active_from", keys)
        self.assertNotIn("active_to", keys)

    def test_shared_annotations_not_duplicated(self) -> None:
        ledger, session = self._setup()
        session._write_node_fact_internal(
            "user:name",
            "Alice",
            "Alice",
            bound=[0.6, 0.9],
            meta={"source": "ESA handbook"},
        )
        result = accept_pyreason_session(ledger, session)
        asrt_id = result.node_asrt_ids[0]
        shared = ledger.find_annotations(asrt_id=asrt_id, namespace="shared")
        shared_keys = {a.key for a in shared}
        self.assertIn("confidence", shared_keys)
        self.assertIn("source", shared_keys)
        all_confidence = [a for a in shared if a.key == "confidence"]
        self.assertEqual(len(all_confidence), 1)
        self.assertEqual(all_confidence[0].origin, "derived")
        self.assertEqual(all_confidence[0].derivation, "pyreason:lower_bound")

    def test_rejects_invalid_template_origin(self) -> None:
        ledger, session = self._setup()
        session._write_node_fact_internal("user:name", "Alice", "Alice")
        session._annotation_templates.append(
            {
                "asrt_id": "",
                "fact_index": 0,
                "fact_kind": "node",
                "namespace": "pyreason",
                "category": "semantic",
                "key": "bad_origin",
                "kind": "str",
                "value": "x",
                "origin": "guessed",
                "derivation": None,
            }
        )

        with self.assertRaises(ValueError):
            accept_pyreason_session(ledger, session)

    def test_edge_fact_annotations_persisted(self) -> None:
        ledger, session = self._setup()
        session._write_edge_fact_internal("friends:strength", "Alice", "Bob", "0.9", bound=[0.9, 0.9])
        result = accept_pyreason_session(ledger, session)
        asrt_id = result.edge_asrt_ids[0]
        annotations = ledger.find_annotations(asrt_id=asrt_id, namespace="pyreason")
        by_key = {a.key: a for a in annotations}
        self.assertAlmostEqual(float(by_key["bound_lower"].value), 0.9)
        self.assertAlmostEqual(float(by_key["bound_upper"].value), 0.9)

    def test_annotation_binds_to_correct_fact(self) -> None:
        ledger, session = self._setup()
        session._write_node_fact_internal("user:name", "Alice", "Alice", bound=[0.6, 0.9])
        session._write_node_fact_internal("user:popular", "Alice", "true", bound=[0.3, 0.5])
        result = accept_pyreason_session(ledger, session)
        ann_1 = ledger.find_annotations(asrt_id=result.node_asrt_ids[0], namespace="pyreason")
        by_key_1 = {a.key: a for a in ann_1}
        self.assertAlmostEqual(float(by_key_1["bound_lower"].value), 0.6)
        ann_2 = ledger.find_annotations(asrt_id=result.node_asrt_ids[1], namespace="pyreason")
        by_key_2 = {a.key: a for a in ann_2}
        self.assertAlmostEqual(float(by_key_2["bound_lower"].value), 0.3)

    def test_rejects_non_ledger(self) -> None:
        _, session = self._setup()
        with self.assertRaises(ValueError):
            accept_pyreason_session("not_a_ledger", session)

    def test_rejects_non_session(self) -> None:
        ledger, _ = self._setup()
        with self.assertRaises(ValueError):
            accept_pyreason_session(ledger, "not_a_session")

    def test_full_round_trip(self) -> None:
        ledger = Ledger()
        session = PyReasonSession(_test_schema_ir())
        with session.batch() as tx:
            alice = tx.entity(User, user_id="Alice")
            alice.name.set("Alice", bound=[1.0, 1.0])
            alice.popular.set("true", bound=[0.7, 0.8])

            bob = tx.entity(User, user_id="Bob")
            bob.name.set("Bob", bound=[1.0, 1.0])

            tx.relationship(Friends, from_entity=alice, to_entity=bob, strength="0.9", bound=[0.9, 0.9])
            tx.commit()

        result = accept_pyreason_session(ledger, session)
        self.assertEqual(len(result.node_asrt_ids), 3)
        self.assertEqual(len(result.edge_asrt_ids), 1)
        self.assertGreater(result.annotation_count, 0)

        for asrt_id in result.node_asrt_ids + result.edge_asrt_ids:
            self.assertIsNotNone(ledger.get_claim(asrt_id))

        popular_asrt = result.node_asrt_ids[1]
        ann = ledger.find_annotations(asrt_id=popular_asrt, namespace="pyreason")
        by_key = {a.key: a for a in ann}
        self.assertAlmostEqual(float(by_key["bound_lower"].value), 0.7)
        self.assertAlmostEqual(float(by_key["bound_upper"].value), 0.8)


if __name__ == "__main__":
    unittest.main()
