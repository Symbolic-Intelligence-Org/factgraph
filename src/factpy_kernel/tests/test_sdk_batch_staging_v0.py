from __future__ import annotations

import copy
import json
import unittest
from typing import Any

import factpy_kernel.tests._warnings as test_warnings
from factpy_kernel.sdk import Entity, Field, Identity, SDKStore, SDKStoreError
from factpy_kernel.sdk.batch import AddOp, RefOp, RetractOp, SetOp, WireBatchPlan


def setUpModule() -> None:
    test_warnings.install_test_warning_filters()


class Company(Entity):
    source_id: str = Identity()
    sector: str = Field(cardinality="functional", pred_id="company:sector")


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")
    name_by_lang: str = Field(
        cardinality="functional",
        pred_id="person:name_by_lang",
        dims=[("lang", "string")],
        fact_key=["lang"],
    )
    works_at: Company = Field(cardinality="multi", pred_id="person:works_at")


class SDKBatchStagingV0Tests(unittest.TestCase):
    def test_preview_commit_equivalence_and_core_semantics(self) -> None:
        sdk_commit = SDKStore.from_schema_classes([Person, Company])
        sdk_replay = SDKStore.from_schema_classes([Person, Company])

        with sdk_commit.batch(meta={"trace_id": "t-1", "source": "etl"}) as tx:
            alice = tx.entity(Person, source_id="u1")
            google = tx.entity(Company, source_id="c1")
            alice.country.set("de")
            alice.country.set("fr")  # functional last-write-wins
            google.sector.set("Tech", meta={"field_source": "hr"})
            alice.works_at.add(google)
            alice.works_at.add(google)  # multi duplicate should dedup
            alice.name_by_lang.set("Alice", dims={"lang": "en"})

            plan = tx.preview(commit_meta={"commit_scope": "demo"})

            self.assertEqual(len([op for op in plan.ops if isinstance(op, RefOp)]), 2)
            self.assertEqual(
                len([op for op in plan.ops if isinstance(op, SetOp) and op.field_name == "country"]),
                1,
            )
            self.assertEqual(
                len([op for op in plan.ops if isinstance(op, AddOp) and op.field_name == "works_at"]),
                1,
            )
            country_op = next(op for op in plan.ops if isinstance(op, SetOp) and op.field_name == "country")
            self.assertEqual(country_op.value, "fr")
            self.assertEqual(country_op.meta["trace_id"], "t-1")
            self.assertEqual(country_op.meta["source"], "etl")
            self.assertEqual(country_op.meta["commit_scope"], "demo")

            replay_res = plan.apply(sdk_replay)
            commit_res = tx.commit(commit_meta={"commit_scope": "demo"})

        self.assertEqual(
            _claim_signatures(sdk_commit.ledger),
            _claim_signatures(sdk_replay.ledger),
        )
        self.assertEqual(
            _user_meta_by_claim_signature(sdk_commit.ledger),
            _user_meta_by_claim_signature(sdk_replay.ledger),
        )
        self.assertEqual(len(commit_res.apply_result.assertion_ids), len(replay_res.assertion_ids))

    def test_wire_export_is_stable_and_roundtrip_apply_is_equivalent(self) -> None:
        sdk_a = SDKStore.from_schema_classes([Person, Company])
        sdk_b = SDKStore.from_schema_classes([Person, Company])
        sdk_c = SDKStore.from_schema_classes([Person, Company])

        wire_json_1 = self._build_demo_wire_json(sdk_a)
        wire_json_2 = self._build_demo_wire_json(sdk_b)
        self.assertEqual(wire_json_1.encode("utf-8"), wire_json_2.encode("utf-8"))

        wire = WireBatchPlan.from_json(wire_json_1)
        replay_res = wire.apply(sdk_c)

        with sdk_a.batch(meta={"trace_id": "t-2", "source": "etl"}) as tx:
            alice = tx.entity(Person, source_id="u2")
            google = tx.entity(Company, source_id="c2")
            alice.country.set("de")
            alice.works_at.add(google)
            alice.name_by_lang.set("Alice", dims={"lang": "en"})
            commit_res = tx.commit(commit_meta={"commit_scope": "wire"})

        self.assertEqual(_claim_signatures(sdk_a.ledger), _claim_signatures(sdk_c.ledger))
        self.assertEqual(_user_meta_by_claim_signature(sdk_a.ledger), _user_meta_by_claim_signature(sdk_c.ledger))
        self.assertEqual(len(commit_res.apply_result.assertion_ids), len(replay_res.assertion_ids))

    def test_wire_apply_rejects_pred_field_mismatch(self) -> None:
        sdk = SDKStore.from_schema_classes([Person, Company])
        wire_json = self._build_demo_wire_json(sdk)
        payload = json.loads(wire_json)
        target = next(op for op in payload["ops"] if op.get("kind") in {"set", "add"} and op.get("field_name") == "country")
        target["field_name"] = "works_at"  # mismatches pred_id=person:country
        wire = WireBatchPlan.from_dict(payload)
        with self.assertRaises(SDKStoreError) as ctx:
            wire.apply(SDKStore.from_schema_classes([Person, Company]))
        self.assertIn("pred_id/field_name mismatch", str(ctx.exception))
        self.assertIn("Person#1.country", str(ctx.exception))

    def test_preview_include_deps_false_rejects_missing_dependency(self) -> None:
        sdk = SDKStore.from_schema_classes([Person, Company])
        with sdk.batch() as tx:
            alice = tx.entity(Person, source_id="u1")
            google = tx.entity(Company, source_id="c1")
            alice.works_at.add(google)
            with self.assertRaises(SDKStoreError) as ctx:
                tx.preview(objects=[alice], include_deps=False)
        self.assertIn("missing dependency", str(ctx.exception))
        self.assertIn("Person#1", str(ctx.exception))

    def test_cardinality_rules_are_strict_in_staging(self) -> None:
        sdk = SDKStore.from_schema_classes([Person, Company])
        with sdk.batch() as tx:
            alice = tx.entity(Person, source_id="u1")
            google = tx.entity(Company, source_id="c1")
            with self.assertRaises(SDKStoreError):
                alice.country.add("de")
            with self.assertRaises(SDKStoreError):
                alice.works_at.set(google)

    def test_tx_entity_rejects_mixed_source_and_uid_identity(self) -> None:
        sdk = SDKStore.from_schema_classes([Person, Company])
        with sdk.batch() as tx:
            with self.assertRaises(SDKStoreError) as ctx:
                tx.entity(Person, source_id="u1", uid="x")
        self.assertIn("source_* identity and uid are mutually exclusive", str(ctx.exception))

    def test_retract_basic_roundtrip_equivalence(self) -> None:
        seed_sdk = SDKStore.from_schema_classes([Person, Company])
        p_ref = seed_sdk.ref(Person, source_id="u3")
        c_ref = seed_sdk.ref(Company, source_id="c3")
        asrt_works = seed_sdk.add(Person.works_at, p_ref, c_ref, meta={"source": "seed", "trace_id": "r1"})

        sdk_commit = SDKStore.from_schema_classes([Person, Company], ledger=copy.deepcopy(seed_sdk.ledger))
        sdk_wire = SDKStore.from_schema_classes([Person, Company], ledger=copy.deepcopy(seed_sdk.ledger))

        with sdk_commit.batch(meta={"trace_id": "r-tx", "source": "etl"}) as tx:
            alice = tx.entity(Person, source_id="u3")
            alice.works_at.retract(asrt_works, meta={"reason": "cleanup"})
            plan = tx.preview(commit_meta={"commit_scope": "retract"})
            wire = WireBatchPlan.from_json(plan.to_json(sdk_commit))
            wire_res = wire.apply(sdk_wire)
            commit_res = tx.commit(commit_meta={"commit_scope": "retract"})

        self.assertEqual(_claim_signatures(sdk_commit.ledger), _claim_signatures(sdk_wire.ledger))
        self.assertEqual(_revoke_signatures(sdk_commit.ledger), _revoke_signatures(sdk_wire.ledger))
        self.assertEqual(_revoke_user_meta(sdk_commit.ledger), _revoke_user_meta(sdk_wire.ledger))
        self.assertEqual(len(commit_res.apply_result.assertion_ids), len(wire_res.assertion_ids))

    def test_retract_wire_export_is_stable(self) -> None:
        seed_sdk = SDKStore.from_schema_classes([Person, Company])
        p_ref = seed_sdk.ref(Person, source_id="u4")
        c_ref = seed_sdk.ref(Company, source_id="c4")
        asrt_works = seed_sdk.add(Person.works_at, p_ref, c_ref)

        sdk_a = SDKStore.from_schema_classes([Person, Company], ledger=copy.deepcopy(seed_sdk.ledger))
        sdk_b = SDKStore.from_schema_classes([Person, Company], ledger=copy.deepcopy(seed_sdk.ledger))
        wire_a = self._build_retract_wire_json(sdk_a, assertion_id=asrt_works, person_source_id="u4")
        wire_b = self._build_retract_wire_json(sdk_b, assertion_id=asrt_works, person_source_id="u4")
        self.assertEqual(wire_a.encode("utf-8"), wire_b.encode("utf-8"))

    def test_retract_dedup_last_meta_wins(self) -> None:
        seed_sdk = SDKStore.from_schema_classes([Person, Company])
        p_ref = seed_sdk.ref(Person, source_id="u5")
        c_ref = seed_sdk.ref(Company, source_id="c5")
        asrt_works = seed_sdk.add(Person.works_at, p_ref, c_ref)

        sdk = SDKStore.from_schema_classes([Person, Company], ledger=copy.deepcopy(seed_sdk.ledger))
        with sdk.batch(meta={"trace_id": "rtx"}) as tx:
            alice = tx.entity(Person, source_id="u5")
            alice.works_at.retract(asrt_works, meta={"reason": "first"})
            alice.works_at.retract(asrt_works, meta={"reason": "second"})
            plan = tx.preview(commit_meta={"scope": "demo"})

        retract_ops = [op for op in plan.ops if isinstance(op, RetractOp)]
        self.assertEqual(len(retract_ops), 1)
        self.assertEqual(retract_ops[0].assertion_id, asrt_works)
        self.assertEqual(retract_ops[0].meta["reason"], "second")
        self.assertEqual(retract_ops[0].meta["trace_id"], "rtx")
        self.assertEqual(retract_ops[0].meta["scope"], "demo")

    def test_retract_path_on_immediate_and_commit_error(self) -> None:
        sdk = SDKStore.from_schema_classes([Person, Company])
        with sdk.batch() as tx:
            alice = tx.entity(Person, source_id="u6")
            with self.assertRaises(SDKStoreError) as ctx1:
                alice.works_at.retract("")
            self.assertIn("Person#1.works_at.retract", str(ctx1.exception))

            alice.works_at.retract("deadbeef")
            with self.assertRaises(SDKStoreError) as ctx2:
                tx.commit()
            self.assertIn("Person#1.works_at.retract", str(ctx2.exception))

    def test_wire_retract_schema_digest_strict(self) -> None:
        seed_sdk = SDKStore.from_schema_classes([Person, Company])
        p_ref = seed_sdk.ref(Person, source_id="u7")
        c_ref = seed_sdk.ref(Company, source_id="c7")
        asrt_works = seed_sdk.add(Person.works_at, p_ref, c_ref)

        sdk = SDKStore.from_schema_classes([Person, Company], ledger=copy.deepcopy(seed_sdk.ledger))
        payload = json.loads(self._build_retract_wire_json(sdk, assertion_id=asrt_works, person_source_id="u7"))
        payload["schema_digest"] = "sha256:deadbeef"
        wire = WireBatchPlan.from_dict(payload)
        with self.assertRaises(SDKStoreError) as ctx:
            wire.apply(SDKStore.from_schema_classes([Person, Company], ledger=copy.deepcopy(seed_sdk.ledger)))
        self.assertIn("schema_digest mismatch", str(ctx.exception))

    def _build_demo_wire_json(self, sdk: SDKStore) -> str:
        with sdk.batch(meta={"trace_id": "t-2", "source": "etl"}) as tx:
            alice = tx.entity(Person, source_id="u2")
            google = tx.entity(Company, source_id="c2")
            alice.country.set("de")
            alice.works_at.add(google)
            alice.name_by_lang.set("Alice", dims={"lang": "en"})
            plan = tx.preview(commit_meta={"commit_scope": "wire"})
        return plan.to_json(sdk)

    def _build_retract_wire_json(self, sdk: SDKStore, *, assertion_id: str, person_source_id: str) -> str:
        with sdk.batch(meta={"trace_id": "rtx", "source": "etl"}) as tx:
            alice = tx.entity(Person, source_id=person_source_id)
            alice.works_at.retract(assertion_id, meta={"reason": "cleanup"})
            plan = tx.preview(commit_meta={"commit_scope": "wire"})
        return plan.to_json(sdk)


def _claim_signatures(ledger) -> list[tuple[str, str, tuple[tuple[str, Any], ...]]]:
    rows: list[tuple[str, str, tuple[tuple[str, Any], ...]]] = []
    for claim in ledger.claims:
        rows.append((claim.pred_id, claim.e_ref, tuple(claim.rest_terms)))
    return sorted(rows)


def _user_meta_by_claim_signature(ledger) -> dict[tuple[str, str, tuple[tuple[str, Any], ...]], list[tuple[str, str, Any]]]:
    out: dict[tuple[str, str, tuple[tuple[str, Any], ...]], list[tuple[str, str, Any]]] = {}
    for claim in ledger.claims:
        sig = (claim.pred_id, claim.e_ref, tuple(claim.rest_terms))
        rows = []
        for meta in ledger.find_meta(asrt_id=claim.asrt_id):
            if meta.key in {"ingested_at", "ingest_key"}:
                continue
            rows.append((meta.key, meta.kind, meta.value))
        out[sig] = sorted(rows)
    return out


def _revoke_signatures(ledger) -> list[str]:
    return sorted([row.revoked_asrt_id for row in ledger.revokes])


def _revoke_user_meta(ledger) -> dict[str, list[tuple[str, str, Any]]]:
    out: dict[str, list[tuple[str, str, Any]]] = {}
    for row in ledger.revokes:
        rows = []
        for meta in ledger.find_meta(asrt_id=row.revoker_asrt_id):
            if meta.key in {"ingested_at", "revoked_asrt_id"}:
                continue
            rows.append((meta.key, meta.kind, meta.value))
        out[row.revoked_asrt_id] = sorted(rows)
    return out


if __name__ == "__main__":
    unittest.main()
