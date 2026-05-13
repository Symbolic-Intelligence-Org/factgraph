from __future__ import annotations

import unittest

from kernel.application import field_predicate
from kernel.core.evidence.write_protocol import set_field
from kernel.sdk import Entity, Field, Identity, Pred, Query, SDKStore, SDKStoreError, vars
from kernel.sdk.error_codes import QUERY_MISSING_REF, QUERY_TYPE_MISMATCH
from kernel.sdk.facade import EntitySnapshot


class User(Entity):
    name: str = Identity(primary_key=True)
    nickname: str = Field(cardinality="single")


class Country(Entity):
    code: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


def _build_sdk() -> SDKStore:
    return SDKStore([User, Country])


def _seed_person(sdk: SDKStore, *, name: str, nickname: str) -> str:
    ref = sdk.ref(User, name=name)
    sdk.set(User.nickname, ref, nickname)
    return ref


def _seed_country(sdk: SDKStore, *, code: str, name: str) -> str:
    ref = sdk.ref(Country, code=code)
    sdk.set(Country.name, ref, name)
    return ref


def _seed_orphan_person_field_row(sdk: SDKStore, *, nickname: str) -> str:
    """Runtime policy fixture: field row exists but identity/exists rows do not."""

    ref = f"idref_v1:User:orphan-{nickname}"
    pred = field_predicate(sdk._application_schema_index, "User", "nickname")
    set_field(sdk.ledger, pred.pred_id, ref, [("string", nickname)])
    return ref


def _person_entity_query(*, on_missing: str = "error", on_type_mismatch: str = "error") -> Query:
    with vars("p") as (p,):
        return Query(
            head=User(p),
            where=[p.nickname == "ally"],
            on_missing=on_missing,
            on_type_mismatch=on_type_mismatch,
        )


def _person_field_projection_query(*, on_missing: str = "error") -> Query:
    with vars("p", "n") as (p, n):
        return Query(
            head=[User(p), User.nickname(value=n)],
            where=[p.nickname == n],
            on_missing=on_missing,
        )


def _type_mismatch_query(*, on_type_mismatch: str) -> Query:
    with vars("p") as (p,):
        return Query(
            head=User(p),
            where=[Pred("country:name", p, "Germany")],
            on_type_mismatch=on_type_mismatch,
        )


class OnMissingPolicyTests(unittest.TestCase):
    def test_on_missing_error_raises_sdk_store_error(self) -> None:
        sdk = _build_sdk()
        _seed_person(sdk, name="alice", nickname="ally")
        _seed_orphan_person_field_row(sdk, nickname="ghost")

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.run(_person_field_projection_query(on_missing="error"))

        self.assertEqual(ctx.exception.code, QUERY_MISSING_REF)

    def test_on_missing_skip_drops_missing_rows(self) -> None:
        sdk = _build_sdk()
        _seed_person(sdk, name="alice", nickname="ally")
        _seed_orphan_person_field_row(sdk, nickname="ghost")

        rows = sdk.run(_person_field_projection_query(on_missing="skip"))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["n"], "ally")
        self.assertIsInstance(rows[0]["p"], EntitySnapshot)

    def test_on_missing_null_keeps_row_with_none_alias(self) -> None:
        sdk = _build_sdk()
        _seed_person(sdk, name="alice", nickname="ally")
        _seed_orphan_person_field_row(sdk, nickname="ghost")

        rows = sdk.run(_person_field_projection_query(on_missing="null"))

        self.assertTrue(any(row["p"] is None and row["n"] == "ghost" for row in rows))
        self.assertTrue(any(isinstance(row["p"], EntitySnapshot) and row["n"] == "ally" for row in rows))


class OnTypeMismatchPolicyTests(unittest.TestCase):
    def test_on_type_mismatch_error_raises_sdk_store_error(self) -> None:
        sdk = _build_sdk()
        _seed_country(sdk, code="DE", name="Germany")

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.run(_type_mismatch_query(on_type_mismatch="error"))

        self.assertEqual(ctx.exception.code, QUERY_TYPE_MISMATCH)

    def test_on_type_mismatch_skip_drops_rows(self) -> None:
        sdk = _build_sdk()
        _seed_country(sdk, code="DE", name="Germany")

        rows = sdk.run(_type_mismatch_query(on_type_mismatch="skip"))

        self.assertEqual(rows, [])

    def test_on_type_mismatch_null_keeps_row_with_none_alias(self) -> None:
        sdk = _build_sdk()
        _seed_country(sdk, code="DE", name="Germany")

        rows = sdk.run(_type_mismatch_query(on_type_mismatch="null"))

        self.assertEqual(rows, [{"p": None}])


class ReturnModeTests(unittest.TestCase):
    def test_dict_mode_returns_mapping_rows(self) -> None:
        sdk = _build_sdk()
        _seed_person(sdk, name="alice", nickname="ally")

        rows = sdk.run(_person_entity_query())

        self.assertIsInstance(rows, list)
        self.assertIsInstance(rows[0], dict)
        self.assertIsInstance(rows[0]["p"], EntitySnapshot)

    def test_instance_mode_returns_entity_snapshots(self) -> None:
        sdk = _build_sdk()
        _seed_person(sdk, name="alice", nickname="ally")

        rows = sdk.run(_person_entity_query(), row_format="instance")

        self.assertIsInstance(rows[0], EntitySnapshot)
        self.assertEqual(rows[0].nickname, "ally")


class ScalarProjectionTests(unittest.TestCase):
    def test_scalar_field_projection_returns_raw_value(self) -> None:
        sdk = _build_sdk()
        _seed_person(sdk, name="alice", nickname="ally")

        rows = sdk.run(_person_field_projection_query())

        self.assertEqual(rows[0]["n"], "ally")


class DedupTests(unittest.TestCase):
    def test_duplicate_query_rows_are_deduped_by_sdk_adapter(self) -> None:
        sdk = _build_sdk()
        _seed_person(sdk, name="alice", nickname="ally")
        with vars("p") as (p,):
            query = Query(
                head=User(p),
                where=[[p.nickname == "ally"], [p.nickname == "ally"]],
            )

        rows = sdk.run(query)

        self.assertEqual(len(rows), 1)


class QuerySnapshotCompatibilityTests(unittest.TestCase):
    def test_query_entity_snapshot_exposes_empty_field_assertions(self) -> None:
        sdk = _build_sdk()
        _seed_person(sdk, name="alice", nickname="ally")

        snapshot = sdk.run(_person_entity_query(), row_format="instance")[0]

        self.assertEqual(snapshot.field("nickname").active(), ())
        self.assertEqual(snapshot.field("nickname").all(), ())


if __name__ == "__main__":
    unittest.main()
