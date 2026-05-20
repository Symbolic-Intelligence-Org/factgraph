from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.schema.schema_ir import canonicalize_schema_ir_jcs
from factgraph.core.store.database import (
    ASSERTION_V1_PREFIX,
    DBDATA_V1_PREFIX,
    DBTX_V1_PREFIX,
    VIEW_V1_PREFIX,
    AssertionInput,
    Database,
    DatabaseError,
    DuplicateAssertionError,
    FrozenAssertionView,
    MetaEntry,
    asrt_id_for,
    assertion_digest_for,
    canonical_bytes_assertion_v1,
    canonical_bytes_dbdata_v1,
    canonical_bytes_dbtx_v1,
    canonical_bytes_view_v1,
    resolve_database_workspace_paths,
    view_digest_for,
)
from factgraph.core.store.ledger import Ledger, MetaRow, Revokes


def _schema_ir() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [{"name": "person_id", "type_domain": "string"}],
            }
        ],
        "predicates": [
            {
                "pred_id": "person:name",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "name", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            }
        ],
        "projection": {"entities": ["Person"], "predicates": ["person:name"]},
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": "2026-05-20T00:00:00Z",
    }


def _person_ref(value: str = "p1") -> str:
    return f"idref_v1:Person:{value}"


def _assertion(name: str, *, meta: tuple[MetaEntry, ...] = ()) -> AssertionInput:
    return AssertionInput(
        pred_id="person:name",
        fact_tuple=(("entity_ref", _person_ref()), ("string", name)),
        meta=meta,
    )


class DatabaseIdentitySubstrateTests(unittest.TestCase):
    def test_canonical_protocol_prefixes_and_token_forms(self) -> None:
        data_bytes = canonical_bytes_dbdata_v1(("asrt:" + "0" * 64,))
        self.assertTrue(data_bytes.startswith(DBDATA_V1_PREFIX))

        tx_bytes = canonical_bytes_dbtx_v1(
            parent_tx_id=None,
            schema_digest="sha256:" + "1" * 64,
            added_assertion_digests=("sha256:" + "2" * 64,),
            data_digest="sha256:" + "3" * 64,
        )
        self.assertTrue(tx_bytes.startswith(DBTX_V1_PREFIX))

        assertion_bytes = canonical_bytes_assertion_v1(
            pred_id="person:name",
            fact_tuple=(("entity_ref", _person_ref()), ("string", "Ada")),
            schema_digest="sha256:" + "4" * 64,
            meta=(MetaEntry("source", "str", "unit-test"),),
        )
        self.assertTrue(assertion_bytes.startswith(ASSERTION_V1_PREFIX))
        self.assertTrue(
            assertion_digest_for(
                pred_id="person:name",
                fact_tuple=(("entity_ref", _person_ref()), ("string", "Ada")),
                schema_digest="sha256:" + "4" * 64,
                meta=(MetaEntry("source", "str", "unit-test"),),
            ).startswith("sha256:")
        )
        self.assertTrue(
            asrt_id_for(
                pred_id="person:name",
                fact_tuple=(("entity_ref", _person_ref()), ("string", "Ada")),
                schema_digest="sha256:" + "4" * 64,
                meta=(MetaEntry("source", "str", "unit-test"),),
            ).startswith("asrt:")
        )

    def test_meta_identity_uses_normalized_metarow_semantics_not_raw_order(self) -> None:
        fact_tuple = (("entity_ref", _person_ref()), ("string", "Ada"))
        schema_digest = "sha256:" + "4" * 64
        first = asrt_id_for(
            pred_id="person:name",
            fact_tuple=fact_tuple,
            schema_digest=schema_digest,
            meta=(
                MetaEntry("note", "str", "same"),
                MetaEntry("score", "int", 7),
            ),
        )
        second = asrt_id_for(
            pred_id="person:name",
            fact_tuple=fact_tuple,
            schema_digest=schema_digest,
            meta=(
                MetaRow("legacy-id-is-ignored", "score", "int", 7),
                MetaRow("another-ignored-id", "note", "str", "same"),
            ),
        )
        self.assertEqual(first, second)

    def test_database_create_commit_and_open_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            created = db.head()
            self.assertTrue(created.db_id.startswith("db:"))
            self.assertTrue(created.tx_id.startswith("tx:"))
            self.assertTrue(created.data_digest.startswith("sha256:"))

            result = db.commit_assertions(
                [_assertion("Ada", meta=(MetaEntry("source", "str", "unit-test"),))]
            )
            self.assertEqual(result.parent_tx_id, created.tx_id)
            self.assertEqual(result.value, db.head())
            record = result.assertions[0]
            self.assertEqual(record.tx_id, result.value.tx_id)
            self.assertEqual(record.fact_tuple, (("entity_ref", _person_ref()), ("string", "Ada")))
            self.assertEqual(db._ledger.get_claim(record.asrt_id).pred_id, "person:name")
            tx_meta = db._ledger.find_meta(asrt_id=record.asrt_id, key="tx_id", kind="str")
            self.assertEqual([row.value for row in tx_meta], [record.tx_id])

            reopened = Database.open(path, schema_ir=_schema_ir())
            self.assertEqual(reopened.db_id, db.db_id)
            self.assertEqual(reopened.head(), result.value)

    def test_database_workspace_layout_created_with_content_addressed_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            head = db.head()
            paths = resolve_database_workspace_paths(path)

            self.assertTrue(paths.assertions.exists())
            self.assertEqual(paths.head.read_text(encoding="ascii").strip(), head.tx_id)
            self.assertTrue((paths.tx_objects / f"{head.tx_id.removeprefix('tx:')}.json").exists())

            schema_path = paths.schema_objects / f"{head.schema_digest.removeprefix('sha256:')}.json"
            self.assertEqual(schema_path.read_bytes(), canonicalize_schema_ir_jcs(_schema_ir()))

            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["components"], {"db": "db/", "views": "views/"})
            self.assertNotIn("registry", manifest["components"])
            self.assertNotIn("schema_digest", manifest)

    def test_database_head_resolves_from_head_tx_object_not_ledger_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            result = db.commit_assertions([_assertion("Ada")])

            db._ledger.replace_ledger_meta("head_data_digest", "sha256:" + "0" * 64)

            self.assertEqual(db.head(), result.value)
            reopened = Database.open(path, schema_ir=_schema_ir())
            self.assertEqual(reopened.head(), result.value)

    def test_tx_object_filename_content_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            result = db.commit_assertions([_assertion("Ada")])
            paths = resolve_database_workspace_paths(path)
            tx_path = paths.tx_objects / f"{result.value.tx_id.removeprefix('tx:')}.json"
            payload = json.loads(tx_path.read_text(encoding="utf-8"))
            payload["tx_id"] = "tx:" + "0" * 64
            tx_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

            with self.assertRaisesRegex(DatabaseError, "filename/content|recompute"):
                db.head()

    def test_database_create_preserves_existing_registry_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            marker = path / "registry" / "rules" / "keep.json"
            marker.parent.mkdir(parents=True)
            marker.write_text("legacy registry data", encoding="utf-8")

            Database.create(path, schema_ir=_schema_ir())

            self.assertEqual(marker.read_text(encoding="utf-8"), "legacy registry data")
            paths = resolve_database_workspace_paths(path)
            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["components"]["registry"], "registry/")

    def test_data_digest_is_path_independent_for_same_active_universe(self) -> None:
        db_ab = Database.create(schema_ir=_schema_ir())
        first = db_ab.commit_assertions([_assertion("Ada")])
        second = db_ab.commit_assertions(
            [
                AssertionInput(
                    pred_id="person:name",
                    fact_tuple=(("entity_ref", _person_ref("p2")), ("string", "Grace")),
                )
            ]
        )

        db_ba = Database.create(schema_ir=_schema_ir())
        db_ba.commit_assertions(
            [
                AssertionInput(
                    pred_id="person:name",
                    fact_tuple=(("entity_ref", _person_ref("p2")), ("string", "Grace")),
                )
            ]
        )
        reversed_second = db_ba.commit_assertions([_assertion("Ada")])

        self.assertEqual(second.value.data_digest, reversed_second.value.data_digest)
        self.assertNotEqual(second.value.tx_id, reversed_second.value.tx_id)
        self.assertEqual(first.assertions[0].asrt_id, reversed_second.assertions[0].asrt_id)

    def test_data_digest_uses_active_only_no_view_universe(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        ada = db.commit_assertions([_assertion("Ada")]).assertions[0]
        grace = AssertionInput(
            pred_id="person:name",
            fact_tuple=(("entity_ref", _person_ref("p2")), ("string", "Grace")),
        )

        db._ledger.append_revocation(
            revokes=Revokes(revoker_asrt_id="asrt:" + "f" * 64, revoked_asrt_id=ada.asrt_id),
            meta_rows=[],
            revoker_asrt_id="asrt:" + "f" * 64,
        )
        after_revoke = db.commit_assertions([grace])
        expected = "sha256:" + sha256_hex(canonical_bytes_dbdata_v1((after_revoke.assertions[0].asrt_id,)))
        self.assertEqual(after_revoke.value.data_digest, expected)

    def test_duplicate_content_addressed_assertion_rejected(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        db.commit_assertions([_assertion("Ada")])
        with self.assertRaises(DuplicateAssertionError):
            db.commit_assertions([_assertion("Ada")])

    def test_fact_tuple_must_be_tagged_identity_tuple(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        with self.assertRaisesRegex(Exception, "fact_tuple"):
            db.commit_assertions(
                [
                    AssertionInput(
                        pred_id="person:name",
                        fact_tuple=(("string", _person_ref()), ("string", "Ada")),
                    )
                ]
            )

    def test_view_digest_uses_subset_view_prefix_and_normalized_membership(self) -> None:
        ids = ("asrt:" + "2" * 64, "asrt:" + "1" * 64, "asrt:" + "1" * 64)
        view_bytes = canonical_bytes_view_v1(
            db_id="db:test",
            base_tx_id="tx:" + "3" * 64,
            schema_digest="sha256:" + "4" * 64,
            asrt_ids=ids,
        )

        self.assertTrue(view_bytes.startswith(VIEW_V1_PREFIX))
        self.assertEqual(
            view_digest_for(
                db_id="db:test",
                base_tx_id="tx:" + "3" * 64,
                schema_digest="sha256:" + "4" * 64,
                asrt_ids=ids,
            ),
            view_digest_for(
                db_id="db:test",
                base_tx_id="tx:" + "3" * 64,
                schema_digest="sha256:" + "4" * 64,
                asrt_ids=reversed(ids),
            ),
        )

    def test_database_create_view_persists_content_addressed_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            result = db.commit_assertions(
                [
                    _assertion("Ada"),
                    AssertionInput(
                        pred_id="person:name",
                        fact_tuple=(("entity_ref", _person_ref("p2")), ("string", "Grace")),
                    ),
                ]
            )
            ids = tuple(record.asrt_id for record in result.assertions)

            view = db.create_view(" review ", reversed(ids))

            self.assertIsInstance(view, FrozenAssertionView)
            self.assertEqual(view.name, "review")
            self.assertEqual(view.asrt_ids, tuple(sorted(ids)))
            self.assertEqual(view.db_id, db.db_id)
            self.assertEqual(view.base_tx_id, result.value.tx_id)
            self.assertEqual(view.schema_digest, result.value.schema_digest)
            self.assertEqual(
                view.view_digest,
                view_digest_for(
                    db_id=view.db_id,
                    base_tx_id=view.base_tx_id,
                    schema_digest=view.schema_digest,
                    asrt_ids=ids,
                ),
            )

            paths = resolve_database_workspace_paths(path)
            view_path = paths.views / "objects" / f"{view.view_digest.removeprefix('sha256:')}.json"
            payload = json.loads(view_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["name"], "review")
            self.assertEqual(payload["view_digest"], view.view_digest)
            self.assertEqual(payload["asrt_ids"], list(view.asrt_ids))

            self.assertEqual(db.create_view("review", ids), view)

    def test_database_create_view_rejects_memory_and_legacy_modes(self) -> None:
        memory_db = Database.create(schema_ir=_schema_ir())
        with self.assertRaisesRegex(DatabaseError, "new-layout Database workspace"):
            memory_db.create_view("review", [])

        legacy_db = Database(
            ledger=Ledger(path=":memory:"),
            db_id="db:legacy",
            schema_digest="sha256:" + "4" * 64,
        )
        with self.assertRaisesRegex(DatabaseError, "new-layout Database workspace"):
            legacy_db.create_view("review", [])

    def test_database_create_view_validates_current_head_and_claim_existence_not_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            initial = db.head()
            ada = db.commit_assertions([_assertion("Ada")]).assertions[0]
            db._ledger.append_revocation(
                revokes=Revokes(revoker_asrt_id="asrt:" + "f" * 64, revoked_asrt_id=ada.asrt_id),
                meta_rows=[],
                revoker_asrt_id="asrt:" + "f" * 64,
            )

            view = db.create_view("includes-revoked", [ada.asrt_id])
            self.assertEqual(view.asrt_ids, (ada.asrt_id,))

            with self.assertRaisesRegex(DatabaseError, "current Database head"):
                db.create_view("historical", [ada.asrt_id], base=initial)
            with self.assertRaisesRegex(DatabaseError, "does not exist"):
                db.create_view("missing", ["asrt:" + "0" * 64])

    def test_view_object_conflicting_content_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace"
            db = Database.create(path, schema_ir=_schema_ir())
            record = db.commit_assertions([_assertion("Ada")]).assertions[0]
            view = db.create_view("review", [record.asrt_id])
            paths = resolve_database_workspace_paths(path)
            view_path = paths.views / "objects" / f"{view.view_digest.removeprefix('sha256:')}.json"
            payload = json.loads(view_path.read_text(encoding="utf-8"))
            payload["view_digest"] = "sha256:" + "0" * 64
            view_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

            with self.assertRaisesRegex(DatabaseError, "different bytes"):
                db.create_view("review", [record.asrt_id])


if __name__ == "__main__":
    unittest.main()
