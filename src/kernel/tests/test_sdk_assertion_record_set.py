from __future__ import annotations

from datetime import datetime, timezone
import unittest

import kernel.sdk as sdk_module
from kernel.sdk import Entity, Field, Identity, SDKStore, SDKStoreError


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")
    risk: str = Field(cardinality="multi")


def _seed_store() -> tuple[SDKStore, str, dict[str, str]]:
    sdk = SDKStore([User])
    ref = sdk.ref(User, user_id="u-1")

    ids = {
        "name_seed": sdk.set(
            User.name,
            ref,
            "Alice",
            meta={
                "source": "seed",
                "trace_id": "trace-name-1",
                "version": "name-v1",
                "batch": "initial",
            },
        ),
        "name_corrected": sdk.set(
            User.name,
            ref,
            "Alicia",
            meta={
                "source": "correction",
                "trace_id": "trace-name-2",
                "version": "name-v2",
                "batch": "cleanup",
            },
        ),
        "tag_vip": sdk.add(
            User.tag,
            ref,
            "vip",
            meta={
                "source": "seed",
                "trace_id": "trace-tag-1",
                "version": "tag-v1",
                "batch": "initial",
            },
        ),
        "tag_unlabeled": sdk.add(
            User.tag,
            ref,
            "unlabeled",
            meta={
                "trace_id": "trace-tag-2",
                "version": "tag-v2",
                "batch": "unlabeled",
            },
        ),
    }
    return sdk, ref, ids


class AssertionRecordSetShapeTests(unittest.TestCase):
    def test_all_assertion_access_paths_return_tuple_compatible_helper(self) -> None:
        sdk, _, _ = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        at_now = datetime.now(timezone.utc).isoformat()
        collections = (
            snap.field("tag").active(),
            snap.field("tag").all(),
            snap.field("tag").at(at_now),
            snap.field("tag").version("tag-v1"),
            snap.assertions.field("tag").active(),
            snap.assertions.field("tag").all(),
        )

        for records in collections:
            with self.subTest(records=records):
                self.assertIsInstance(records, tuple)
                self.assertTrue(hasattr(records, "where"))
                self.assertTrue(hasattr(records, "one"))
                self.assertTrue(hasattr(records, "all"))
                self.assertTrue(hasattr(records, "first"))

    def test_existing_tuple_behavior_remains_compatible(self) -> None:
        sdk, _, _ = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        records = snap.field("tag").active()

        self.assertIsInstance(records, tuple)
        self.assertEqual(len(records), 2)
        self.assertEqual([record.value for record in records], ["vip", "unlabeled"])
        self.assertEqual(records[0].value, "vip")
        self.assertEqual(records[:0], ())

    def test_slicing_concat_multiply_and_chained_where_preserve_helper_type(self) -> None:
        sdk, _, _ = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        records = snap.field("tag").active()
        sliced = records[:1]
        concatenated = records[:1] + records[1:]
        multiplied = records[:1] * 2

        for subset in (sliced, concatenated, multiplied):
            with self.subTest(subset=subset):
                self.assertIs(type(subset), type(records))
                self.assertTrue(hasattr(subset, "where"))

        match = records.where(source="seed").where(value="vip").one()
        self.assertEqual(match.value, "vip")


class AssertionRecordSetFilterTests(unittest.TestCase):
    def test_where_filters_by_value_and_metadata_with_and_semantics(self) -> None:
        sdk, _, ids = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        record = (
            snap.field("tag")
            .active()
            .where(
                value="vip",
                source="seed",
                trace_id="trace-tag-1",
                version="tag-v1",
                meta={"batch": "initial"},
            )
            .one()
        )

        self.assertEqual(record.asrt_id, ids["tag_vip"])
        self.assertEqual(record.value, "vip")

    def test_where_distinguishes_explicit_none_from_omitted_filter(self) -> None:
        sdk, _, ids = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        all_records = snap.field("tag").active().where()
        source_none = snap.field("tag").active().where(source=None)
        meta_filter = snap.field("tag").active().where(meta={"batch": "unlabeled"})

        self.assertEqual(len(all_records), 2)
        self.assertEqual(source_none.one().asrt_id, ids["tag_unlabeled"])
        self.assertEqual(meta_filter.one().asrt_id, ids["tag_unlabeled"])

    def test_one_all_and_first_semantics(self) -> None:
        sdk, _, ids = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        records = snap.field("tag").active()

        self.assertEqual(records.where(value="vip").one().asrt_id, ids["tag_vip"])
        self.assertIsNone(records.where(value="missing").first())
        self.assertEqual(records.where(value="missing").all(), ())
        self.assertIs(type(records.all()), tuple)
        self.assertIsNot(type(records.all()), type(records))

        with self.assertRaises(SDKStoreError):
            records.where(value="missing").one()
        with self.assertRaises(SDKStoreError):
            records.one()


class AssertionRecordSetRawUncertaintyFilterTests(unittest.TestCase):
    def test_where_filters_exact_raw_kind_and_bound_meta(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="u-risk")
        low = sdk.add(
            User.risk,
            ref,
            "low",
            meta={"raw_kind": "probabilistic", "bound": [0.1, 0.2], "source": "model-a"},
        )
        high = sdk.add(
            User.risk,
            ref,
            "high",
            meta={"raw_kind": "possibilistic", "bound": [0.4, 0.9], "source": "expert-a"},
        )

        snap = sdk.get(User, user_id="u-risk")
        self.assertIsNotNone(snap)
        assert snap is not None

        probabilistic = snap.field("risk").active().where(meta={"raw_kind": "probabilistic"}).one()
        exact_bound = snap.field("risk").active().where(meta={"bound": [0.4, 0.9]}).one()
        no_interval_semantics = snap.field("risk").active().where(meta={"bound": [0.4, 0.9000001]})

        self.assertEqual(probabilistic.asrt_id, low)
        self.assertEqual(exact_bound.asrt_id, high)
        self.assertEqual(no_interval_semantics.all(), ())

    def test_sdk_rejects_removed_probability_meta(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="u-risk")

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.add(User.risk, ref, "removed", meta={"probability": 0.4})

        self.assertIn("probability", str(ctx.exception))


class AssertionRecordSetBoundaryTests(unittest.TestCase):
    def test_write_retract_remains_asrt_id_based(self) -> None:
        sdk, _, ids = _seed_store()
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None

        target = snap.field("tag").active()[0]

        with self.assertRaises(SDKStoreError):
            sdk.retract(target)

        revoker = sdk.retract(ids["tag_vip"])
        self.assertIsInstance(revoker, str)

    def test_no_new_public_sdk_export_or_read_namespace_method(self) -> None:
        sdk, _, _ = _seed_store()

        self.assertEqual(len(sdk_module.__all__), 40)
        self.assertNotIn("ReadPolicy", sdk_module.__all__)
        self.assertIn("SemanticsProfile", sdk_module.__all__)
        self.assertIn("ProbLogSemantics", sdk_module.__all__)
        self.assertIn("PyReasonSemantics", sdk_module.__all__)
        self.assertNotIn("AssertionRecordSet", sdk_module.__all__)
        self.assertFalse(hasattr(sdk.read, "assertions"))


if __name__ == "__main__":
    unittest.main()
