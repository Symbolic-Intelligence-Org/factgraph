from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from factgraph.core.store.database import (
    DBTX_V2_PREFIX,
    AssertionInput,
    Database,
    MetaAppendInput,
    MetaEntry,
    RevocationInput,
    SchemaTransitionInput,
    canonical_bytes_dbtx_v2,
    resolve_database_workspace_paths,
)
from factgraph.core.store.ledger import AnnotationRow


_GOLDEN_ROOT = Path(__file__).with_name("golden") / "dbtx_v2"
_FIXTURES = (
    ("assertion_revocation_only.json", frozenset({"assertion", "revocation"})),
    ("append_meta_schema_change.json", frozenset({"append_meta", "schema_change"})),
    ("repair_ops.json", frozenset({"repair_add", "repair_remove", "repair"})),
)
_ALLOWED_KINDS = {
    "assertion_revocation_only.json": frozenset({"assertion", "revocation"}),
    "append_meta_schema_change.json": frozenset(
        {"assertion", "append_meta", "schema_change"}
    ),
    "repair_ops.json": frozenset({"repair_add", "repair_remove", "repair"}),
}
_COMMIT_PATH_IDS = (
    "asrt:11111111111111111111111111111111",
    "asrt:22222222222222222222222222222222",
    "asrt:33333333333333333333333333333333",
)


class DbtxV2GoldenTests(unittest.TestCase):
    def test_production_adapter_annotation_commit_is_frozen(self) -> None:
        fixture = _load_fixture("adapter_annotation_commit.json")
        expected = fixture["adapter_step"]
        with tempfile.TemporaryDirectory() as raw_tmp, patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=(_COMMIT_PATH_IDS[0],),
        ):
            workspace = Path(raw_tmp) / "workspace"
            database = Database.create(workspace, schema_ir=_adapter_schema_ir())
            actual_heads = [database.head().tx_id]
            assertion = database.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                    ),
                )
            ).assertions[0]
            actual_heads.append(database.head().tx_id)
            database._ledger_for_attach().append_annotations(
                [
                    AnnotationRow(
                        assertion.asrt_id,
                        "problog",
                        "semantic",
                        "probability",
                        "float",
                        0.75,
                        "derived",
                        "run-1",
                    )
                ]
            )
            head = database.head()
            actual_heads.append(head.tx_id)
            self.assertEqual(actual_heads, fixture["head_progression"])
            self.assertEqual(head.tx_seq, expected["tx_seq"])
            self.assertEqual(head.tx_id, expected["tx_id"])

            object_path = (
                resolve_database_workspace_paths(workspace).tx_objects
                / f"{head.tx_id.removeprefix('tx:')}.json"
            )
            object_bytes = object_path.read_bytes()
            self.assertEqual(object_bytes, bytes.fromhex(expected["tx_object_hex"]))
            payload = json.loads(object_bytes.decode("utf-8"))
            canonical = canonical_bytes_dbtx_v2(
                parent_tx_id=payload["parent_tx_id"],
                schema_digest=payload["schema_digest"],
                digest_scheme=payload["digest_scheme"],
                tx_seq=payload["tx_seq"],
                operations=payload["operations"],
            )
            self.assertEqual(canonical, bytes.fromhex(expected["canonical_hex"]))
            database.close()

    def test_canonical_bytes_tx_ids_and_head_progression_are_frozen(self) -> None:
        for fixture_name, required_kinds in _FIXTURES:
            with self.subTest(fixture=fixture_name):
                fixture = _load_fixture(fixture_name)
                self.assertEqual(fixture["fixture_version"], 1)

                parent_tx_id: str | None = None
                actual_heads: list[str] = []
                observed_kinds: set[str] = set()

                for transaction in fixture["transactions"]:
                    self.assertEqual(transaction["parent_tx_id"], parent_tx_id)
                    canonical = canonical_bytes_dbtx_v2(
                        parent_tx_id=transaction["parent_tx_id"],
                        schema_digest=transaction["schema_digest"],
                        digest_scheme=transaction["digest_scheme"],
                        tx_seq=transaction["tx_seq"],
                        operations=transaction["operations"],
                    )
                    self.assertTrue(canonical.startswith(DBTX_V2_PREFIX))
                    canonical_hex = transaction.get("canonical_hex")
                    if canonical_hex is None:
                        canonical_hex = "".join(transaction["canonical_hex_chunks"])
                    self.assertEqual(canonical, bytes.fromhex(canonical_hex))

                    tx_id = "tx:" + hashlib.sha256(canonical).hexdigest()
                    self.assertEqual(tx_id, transaction["tx_id"])
                    actual_heads.append(tx_id)
                    parent_tx_id = tx_id
                    observed_kinds.update(op["kind"] for op in transaction["operations"])

                self.assertEqual(actual_heads, fixture["head_progression"])
                self.assertTrue(required_kinds.issubset(observed_kinds))
                self.assertTrue(observed_kinds <= _ALLOWED_KINDS[fixture_name])

    def test_production_commit_path_tx_objects_and_heads_are_frozen(self) -> None:
        fixture = _load_fixture("commit_path_all_ops.json")
        self.assertEqual(fixture["fixture_version"], 1)
        self.assertEqual(
            fixture["head_progression"],
            [step["tx_id"] for step in fixture["transactions"]],
        )
        self.assertEqual(
            {
                operation["kind"]
                for step in fixture["transactions"]
                for operation in json.loads(
                    bytes.fromhex("".join(step["tx_object_hex_chunks"])).decode("utf-8")
                )["operations"]
            },
            {"assertion", "revocation", "append_meta", "schema_change"},
        )
        expected_steps = iter(fixture["transactions"])
        state_digests = fixture["head_state_digests"]

        with tempfile.TemporaryDirectory() as raw_tmp, patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=_COMMIT_PATH_IDS,
        ):
            workspace = Path(raw_tmp) / "workspace"
            database = Database.create(workspace, schema_ir=_commit_path_schema_ir(version=1))
            try:
                self._assert_persisted_step(
                    database, workspace, next(expected_steps), state_digests
                )

                first = database.commit_changes(
                    assertions=(
                        AssertionInput(
                            pred_id="person:name",
                            fact_tuple=(
                                ("entity_ref", "idref_v1:Person:alice"),
                                ("string", "Alice"),
                            ),
                            meta=(
                                MetaEntry("source", "str", "phase0-golden"),
                                MetaEntry("ingested_at", "time", 1_788_220_800_000_000_001),
                            ),
                        ),
                    ),
                    revocations=(),
                )
                self.assertEqual(first.assertions[0].asrt_id, _COMMIT_PATH_IDS[0])
                self._assert_persisted_step(
                    database, workspace, next(expected_steps), state_digests
                )

                mixed = database.commit_changes(
                    assertions=(
                        AssertionInput(
                            pred_id="person:name",
                            fact_tuple=(
                                ("entity_ref", "idref_v1:Person:bob"),
                                ("string", "Bob"),
                            ),
                            meta=(MetaEntry("payload", "json", {"encoding": "00ff"}),),
                        ),
                    ),
                    revocations=(
                        RevocationInput(
                            revoked_asrt_id=_COMMIT_PATH_IDS[0],
                            meta=(
                                MetaEntry("actor", "str", "phase0-golden"),
                                MetaEntry("retry", "bool", False),
                                MetaEntry("attempt", "int", 7),
                                MetaEntry("ratio", "float", 0.25),
                            ),
                        ),
                    ),
                    meta_appends=(
                        MetaAppendInput(
                            _COMMIT_PATH_IDS[0], "reviewed", "bool", True
                        ),
                    ),
                )
                self.assertEqual(mixed.assertions[0].asrt_id, _COMMIT_PATH_IDS[1])
                self.assertEqual(mixed.revocations[0].revoker_asrt_id, _COMMIT_PATH_IDS[2])
                self._assert_persisted_step(
                    database, workspace, next(expected_steps), state_digests
                )

                database.commit_changes(
                    assertions=(),
                    revocations=(),
                    meta_appends=(
                        MetaAppendInput(_COMMIT_PATH_IDS[1], "confidence", "float", 0.5),
                        MetaAppendInput(
                            _COMMIT_PATH_IDS[1],
                            "details",
                            "json",
                            {"flags": ["a", "b"], "score": 7},
                        ),
                    ),
                )
                self._assert_persisted_step(
                    database, workspace, next(expected_steps), state_digests
                )

                database.commit_changes(
                    assertions=(),
                    revocations=(),
                    schema_transition=SchemaTransitionInput(
                        old_schema_digest=database.head().schema_digest,
                        new_schema_ir=_commit_path_schema_ir(version=2),
                    ),
                )
                self._assert_persisted_step(
                    database, workspace, next(expected_steps), state_digests
                )
                with self.assertRaises(StopIteration):
                    next(expected_steps)
            finally:
                database.close()

    def _assert_persisted_step(
        self,
        database: Database,
        workspace: Path,
        expected: dict[str, Any],
        state_digests: dict[str, list[str]],
    ) -> None:
        head = database.head()
        expected_metadata = dict(expected["head_metadata"])
        expected_metadata["head_state_digest"] = "".join(
            state_digests[expected["head_state_digest"]]
        )
        self.assertEqual(head.tx_id, expected["tx_id"])
        self.assertEqual(head.tx_seq, expected["tx_seq"])
        self.assertEqual(head.state_digest, expected_metadata["head_state_digest"])

        ledger = database._ledger_for_attach()
        actual_meta = ledger.get_ledger_meta_snapshot(
            ("head_tx_id", "head_tx_seq", "head_state_digest")
        )
        self.assertEqual(actual_meta, expected_metadata)

        paths = resolve_database_workspace_paths(workspace)
        object_path = paths.tx_objects / f"{head.tx_id.removeprefix('tx:')}.json"
        object_bytes = object_path.read_bytes()
        self.assertEqual(
            object_bytes,
            bytes.fromhex("".join(expected["tx_object_hex_chunks"])),
        )

        payload = json.loads(object_bytes.decode("utf-8"))
        canonical = canonical_bytes_dbtx_v2(
            parent_tx_id=payload["parent_tx_id"],
            schema_digest=payload["schema_digest"],
            digest_scheme=payload["digest_scheme"],
            tx_seq=payload["tx_seq"],
            operations=payload["operations"],
        )
        self.assertEqual("tx:" + hashlib.sha256(canonical).hexdigest(), expected["tx_id"])


def _load_fixture(name: str) -> dict[str, Any]:
    payload = json.loads((_GOLDEN_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"dbtx_v2 fixture must be an object: {name}")
    return payload


def _commit_path_schema_ir(*, version: int) -> dict[str, Any]:
    predicates = [
        {
            "pred_id": "person:name",
            "arg_specs": [
                {"name": "person", "type_domain": "entity_ref"},
                {"name": "name", "type_domain": "string"},
            ],
            "group_key_indexes": [0],
        }
    ]
    if version == 2:
        predicates.append(
            {
                "pred_id": "person:alias",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "alias", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            }
        )
    return {
        "schema_ir_version": "v1",
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [{"name": "person_id", "type_domain": "string"}],
            }
        ],
        "predicates": predicates,
        "projection": {
            "entities": ["Person"],
            "predicates": [item["pred_id"] for item in predicates],
        },
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": f"2026-08-01T00:00:0{version}Z",
    }


def _adapter_schema_ir() -> dict[str, Any]:
    value = _commit_path_schema_ir(version=1)
    value["generated_at"] = "2026-08-02T00:00:00Z"
    return value


if __name__ == "__main__":
    unittest.main()
