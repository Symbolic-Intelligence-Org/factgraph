from __future__ import annotations

import unittest

from kernel.sdk import Entity, Field, Identity, Query, SDKStore, SDKStoreError, vars
from kernel.sdk.facade import AssertionRecordSet, EntitySnapshot


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


class Collision(Entity):
    collision_id: str = Identity(primary_key=True)
    active: str = Field(cardinality="single")
    all: str = Field(cardinality="single")
    where: str = Field(cardinality="single")


def _seed_user_store() -> tuple[SDKStore, str, dict[str, str]]:
    sdk = SDKStore([User, Collision])
    ref = sdk.ref(User, user_id="u-1")
    ids = {
        "name_seed": sdk.set(
            User.name,
            ref,
            "Alice",
            meta={"source": "seed", "trace_id": "import-001", "version": "name-v1"},
        ),
        "name_corrected": sdk.set(
            User.name,
            ref,
            "Alicia",
            meta={"source": "correction", "trace_id": "import-002", "version": "name-v2"},
        ),
        "tag_vip": sdk.add(
            User.tag,
            ref,
            "vip",
            meta={"source": "seed", "trace_id": "import-003", "version": "tag-v1"},
        ),
    }
    return sdk, ref, ids


def _get_user_snapshot(sdk: SDKStore) -> EntitySnapshot:
    snap = sdk.get(User, user_id="u-1")
    if snap is None:
        raise AssertionError("expected seeded User snapshot")
    return snap


def _user_entity_query() -> Query:
    with vars("u") as (u,):
        return Query(head=User(u), where=[u.name == "Alicia"])


class TestAssertionCollectionSnapScope(unittest.TestCase):
    def test_snapshot_scope_active_and_all_are_record_sets(self) -> None:
        sdk, _, ids = _seed_user_store()
        snap = _get_user_snapshot(sdk)

        active = snap.assertions.active()
        all_records = snap.assertions.all()

        self.assertIsInstance(active, AssertionRecordSet)
        self.assertIsInstance(all_records, AssertionRecordSet)
        self.assertEqual(active.where(source="correction").one().asrt_id, ids["name_corrected"])
        self.assertEqual(all_records.where(source="seed", value="Alice").one().asrt_id, ids["name_seed"])

    def test_snapshot_scope_by_id_and_by_ids(self) -> None:
        sdk, _, ids = _seed_user_store()
        snap = _get_user_snapshot(sdk)

        record = snap.assertions.by_id(ids["name_corrected"])
        records = snap.assertions.by_ids([ids["name_corrected"], ids["tag_vip"], "missing-asrt"])

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.asrt_id, ids["name_corrected"])
        self.assertIsInstance(records, AssertionRecordSet)
        self.assertEqual({item.asrt_id for item in records}, {ids["name_corrected"], ids["tag_vip"]})

    def test_snapshot_field_string_and_descriptor_return_same_records(self) -> None:
        sdk, _, ids = _seed_user_store()
        snap = _get_user_snapshot(sdk)

        by_name = snap.assertions.field("name").active()
        by_descriptor = snap.assertions.field(User.name).active()

        self.assertEqual(by_name.where(source="correction").one().asrt_id, ids["name_corrected"])
        self.assertEqual(by_descriptor.where(source="correction").one().asrt_id, ids["name_corrected"])

    def test_field_scope_records_include_context_fields(self) -> None:
        sdk, ref, ids = _seed_user_store()
        snap = _get_user_snapshot(sdk)

        record = snap.assertions.field("name").active().where(source="correction").one()

        self.assertEqual(record.asrt_id, ids["name_corrected"])
        self.assertEqual(record.entity_type, "User")
        self.assertEqual(record.field_name, "name")
        self.assertEqual(record.pred_id, "user:name")
        self.assertEqual(record.e_ref, ref)


class TestAssertionCollectionGraphScope(unittest.TestCase):
    def test_graph_scope_active_and_all_are_record_sets(self) -> None:
        sdk, _, ids = _seed_user_store()

        active = sdk.assertions.active()
        all_records = sdk.assertions.all()

        self.assertIsInstance(active, AssertionRecordSet)
        self.assertIsInstance(all_records, AssertionRecordSet)
        self.assertEqual(active.where(source="correction").one().asrt_id, ids["name_corrected"])
        self.assertEqual(all_records.where(source="seed", value="Alice").one().asrt_id, ids["name_seed"])

    def test_graph_field_descriptor_scope(self) -> None:
        sdk, _, ids = _seed_user_store()

        records = sdk.assertions.field(User.name).active()

        self.assertIsInstance(records, AssertionRecordSet)
        self.assertEqual(records.where(source="correction").one().asrt_id, ids["name_corrected"])

    def test_graph_scope_all_is_ledger_level_and_retains_revoked_assertions(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="u-revoked")
        asrt_id = sdk.set(User.name, ref, "Alice", meta={"source": "seed"})

        sdk.retract(asrt_id)

        revoked = sdk.assertions.all().by_id(asrt_id).one()
        self.assertEqual(revoked.asrt_id, asrt_id)
        self.assertFalse(revoked.is_active)


class TestAssertionCollectionHardCuts(unittest.TestCase):
    def test_snapshot_field_attribute_access_is_removed(self) -> None:
        sdk, _, _ = _seed_user_store()
        snap = _get_user_snapshot(sdk)

        with self.assertRaises(AttributeError):
            _ = snap.assertions.name

    def test_field_active_and_history_properties_are_removed(self) -> None:
        sdk, _, ids = _seed_user_store()
        snap = _get_user_snapshot(sdk)
        field_records = snap.assertions.field("name")

        self.assertTrue(callable(field_records.active))
        self.assertTrue(callable(field_records.all))
        self.assertEqual(field_records.active().where(source="correction").one().asrt_id, ids["name_corrected"])
        self.assertNotIsInstance(field_records.active, AssertionRecordSet)
        self.assertFalse(hasattr(field_records, "history"))

    def test_assertion_record_is_revoked_is_removed(self) -> None:
        sdk, _, ids = _seed_user_store()

        record = sdk.assertions.by_ids([ids["name_corrected"]]).first()

        self.assertIsNotNone(record)
        assert record is not None
        self.assertFalse(hasattr(record, "is_revoked"))
        self.assertIsInstance(record.is_active, bool)


class TestAssertionCollectionFieldInputAsymmetry(unittest.TestCase):
    def test_snapshot_field_name_collisions_are_reachable_through_field_method(self) -> None:
        sdk = SDKStore([User, Collision])
        ref = sdk.ref(Collision, collision_id="c-1")
        active_id = sdk.set(Collision.active, ref, "yes", meta={"source": "seed"})
        all_id = sdk.set(Collision.all, ref, "everything", meta={"source": "seed"})
        where_id = sdk.set(Collision.where, ref, "filter", meta={"source": "seed"})
        snap = sdk.get(Collision, collision_id="c-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        self.assertEqual(snap.assertions.field("active").active().one().asrt_id, active_id)
        self.assertEqual(snap.assertions.field(Collision.active).active().one().asrt_id, active_id)
        self.assertEqual(snap.assertions.field("all").active().one().asrt_id, all_id)
        self.assertEqual(snap.assertions.field("where").active().one().asrt_id, where_id)

    def test_graph_field_rejects_string_names_as_ambiguous(self) -> None:
        sdk, _, _ = _seed_user_store()

        with self.assertRaises(SDKStoreError):
            sdk.assertions.field("name")

    def test_snapshot_field_descriptor_must_match_snapshot_entity_type(self) -> None:
        sdk, _, _ = _seed_user_store()
        snap = _get_user_snapshot(sdk)

        with self.assertRaises(SDKStoreError):
            snap.assertions.field(Collision.active)


class TestAssertionCollectionDeferredQueryWitness(unittest.TestCase):
    def test_query_entity_snapshots_do_not_carry_assertion_witness_records(self) -> None:
        sdk, _, _ = _seed_user_store()

        snapshot = sdk.run(_user_entity_query(), row_format="instance")[0]

        self.assertIsInstance(snapshot, EntitySnapshot)
        self.assertEqual(snapshot.assertions.field("name").all(), ())

    def test_assertion_record_set_match_query_is_not_available(self) -> None:
        sdk, _, ids = _seed_user_store()
        records = sdk.assertions.by_ids([ids["name_corrected"]])

        self.assertFalse(hasattr(records, "match"))
        with self.assertRaises(AttributeError):
            records.match(_user_entity_query())  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
