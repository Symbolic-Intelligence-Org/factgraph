from __future__ import annotations

import unittest

from kernel.application import entity_info, field_predicate
from kernel.sdk import Entity, Field, Identity, SDKStore


class Country(Entity):
    code: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    age: int = Field(cardinality="single")
    tag: str = Field(cardinality="multi")
    lives_in: Country = Field(cardinality="single")


def _build_sdk() -> SDKStore:
    return SDKStore([Country, User])


def _claim_pred_id(sdk: SDKStore, asrt_id: str) -> str:
    claim = sdk.ledger.get_claim(asrt_id)
    assert claim is not None
    return claim.pred_id


def _active_claim_count(sdk: SDKStore, *, pred_id: str, e_ref: str) -> int:
    return len(list(sdk.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)))


class IngestCacheHitPathTests(unittest.TestCase):
    def test_set_cache_hit_delegates_to_application_and_returns_field_assertion_id(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.ref(User, user_id="u-1")

        result = sdk.ingest(
            [
                {
                    "kind": "set",
                    "field": User.name,
                    "e_ref": user_ref,
                    "value": "Alice",
                }
            ]
        )

        self.assertEqual(len(result.written_assertion_ids), 1)
        expected_pred = field_predicate(sdk._application_schema_index, "User", "name").pred_id
        self.assertEqual(_claim_pred_id(sdk, result.written_assertion_ids[0]), expected_pred)
        user_exists = entity_info(sdk._application_schema_index, "User").exists_predicate_id
        self.assertEqual(_active_claim_count(sdk, pred_id=user_exists, e_ref=user_ref), 1)

    def test_add_cache_hit_delegates_to_application(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.ref(User, user_id="u-1")

        result = sdk.ingest(
            [
                {
                    "kind": "add",
                    "field": User.tag,
                    "e_ref": user_ref,
                    "value": "vip",
                }
            ]
        )

        expected_pred = field_predicate(sdk._application_schema_index, "User", "tag").pred_id
        self.assertEqual(len(result.written_assertion_ids), 1)
        self.assertEqual(_claim_pred_id(sdk, result.written_assertion_ids[0]), expected_pred)
        snap = sdk.get(User, user_id="u-1")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.tag, ("vip",))

    def test_entity_ref_value_cache_hit_delegates_to_application_dependencies(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.ref(User, user_id="u-1")
        country_ref = sdk.ref(Country, code="DE")

        result = sdk.ingest(
            [
                {
                    "kind": "set",
                    "field": User.lives_in,
                    "e_ref": user_ref,
                    "value": country_ref,
                }
            ]
        )

        expected_pred = field_predicate(sdk._application_schema_index, "User", "lives_in").pred_id
        self.assertEqual(len(result.written_assertion_ids), 1)
        self.assertEqual(_claim_pred_id(sdk, result.written_assertion_ids[0]), expected_pred)
        country_exists = entity_info(sdk._application_schema_index, "Country").exists_predicate_id
        self.assertEqual(_active_claim_count(sdk, pred_id=country_exists, e_ref=country_ref), 1)


class IngestCacheMissFallbackTests(unittest.TestCase):
    def test_target_cache_miss_uses_legacy_path(self) -> None:
        sdk = _build_sdk()
        raw_user_ref = "idref_v1:User:raw-user"

        result = sdk.ingest(
            [
                {
                    "kind": "set",
                    "field": User.name,
                    "e_ref": raw_user_ref,
                    "value": "Raw",
                }
            ]
        )

        self.assertEqual(len(result.written_assertion_ids), 1)
        claim = sdk.ledger.get_claim(result.written_assertion_ids[0])
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual(claim.e_ref, raw_user_ref)
        user_exists = entity_info(sdk._application_schema_index, "User").exists_predicate_id
        self.assertEqual(_active_claim_count(sdk, pred_id=user_exists, e_ref=raw_user_ref), 0)

    def test_entity_ref_value_cache_miss_uses_legacy_path(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.ref(User, user_id="u-1")
        raw_country_ref = "idref_v1:Country:raw-country"

        result = sdk.ingest(
            [
                {
                    "kind": "set",
                    "field": User.lives_in,
                    "e_ref": user_ref,
                    "value": raw_country_ref,
                }
            ]
        )

        self.assertEqual(len(result.written_assertion_ids), 1)
        user_exists = entity_info(sdk._application_schema_index, "User").exists_predicate_id
        self.assertEqual(_active_claim_count(sdk, pred_id=user_exists, e_ref=user_ref), 0)
        claim = sdk.ledger.get_claim(result.written_assertion_ids[0])
        self.assertIsNotNone(claim)
        assert claim is not None
        self.assertEqual(claim.rest_terms, [("entity_ref", raw_country_ref)])


class IngestRetractDelegateTests(unittest.TestCase):
    def test_retract_delegates_to_application_ingest(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.ref(User, user_id="u-1")
        asrt_id = sdk.set(User.name, user_ref, "Alice")

        result = sdk.ingest([{"kind": "retract", "asrt_id": asrt_id}])

        self.assertEqual(len(result.written_assertion_ids), 1)
        self.assertEqual(sdk.ledger.find_revoker(asrt_id), result.written_assertion_ids[0])


class IngestCompatibilityTests(unittest.TestCase):
    def test_duplicate_detection_remains_sdk_level_for_application_path(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.ref(User, user_id="u-1")

        result = sdk.ingest(
            [
                {"kind": "set", "field": User.name, "e_ref": user_ref, "value": "Alice"},
                {"kind": "set", "field": User.name, "e_ref": user_ref, "value": "Alice"},
            ]
        )

        self.assertEqual(len(result.written_assertion_ids), 1)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(result.skipped_count, 1)

    def test_precheck_diagnostics_still_collect_and_stop_before_application_runtime(self) -> None:
        sdk = _build_sdk()
        user_ref = sdk.ref(User, user_id="u-1")

        result = sdk.ingest(
            [
                {
                    "kind": "set",
                    "field": User.age,
                    "e_ref": user_ref,
                    "value": "not-an-int",
                }
            ]
        )

        self.assertEqual(result.written_assertion_ids, [])
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(result.duplicate_count, 0)
        self.assertTrue(any(row["code"] == "ingest_item_field_value_invalid" for row in result.diagnostics))


if __name__ == "__main__":
    unittest.main()
