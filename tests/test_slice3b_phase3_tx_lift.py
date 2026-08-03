from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from factgraph.core.schema.meta_policy import MetaKeyPolicy
from factgraph.core.store.database import (
    DBTX_V2_META_DEFAULTS_SUFFIX,
    AssertionInput,
    Database,
    DatabaseError,
    MetaEntry,
    RevocationInput,
    _MetaUnsetInput,
    canonical_bytes_dbtx_v2,
    resolve_database_workspace_paths,
)
from factgraph.core.store.premise_filter import (
    MetaExclusion,
    PredicatePremiseAllowance,
    is_predicate_premise_excluded,
    is_premise_excluded,
)
from factgraph.sdk import Entity, Identity, compile_schema_from_classes


class _TxLiftEntity(Entity):
    entity_id: str = Identity()


def _schema_ir() -> dict:
    return compile_schema_from_classes(
        [_TxLiftEntity],
        meta_keys={
            "source": MetaKeyPolicy(
                premise_eligible=True,
                storage_scope="tx_liftable",
            ),
            "trace_id": MetaKeyPolicy(
                reader_class="audit",
                load_policy="lazy",
                storage_scope="tx_liftable",
            ),
        },
    )


class TxMetaDefaultsProtocolTests(unittest.TestCase):
    def test_empty_defaults_preserve_bytes_and_nonempty_use_separate_suffix(self) -> None:
        args = {
            "parent_tx_id": None,
            "schema_digest": "sha256:" + "1" * 64,
            "digest_scheme": "lthash16-v2",
            "tx_seq": 0,
            "operations": (),
        }
        baseline = canonical_bytes_dbtx_v2(**args)
        self.assertEqual(canonical_bytes_dbtx_v2(**args, meta_defaults=()), baseline)
        self.assertNotIn(DBTX_V2_META_DEFAULTS_SUFFIX, baseline)

        unsorted = (
            MetaEntry("trace_id", "str", "trace-7"),
            MetaEntry("source", "str", "bulk-import"),
        )
        sorted_rows = tuple(sorted(unsorted, key=lambda row: row.key))
        with_defaults = canonical_bytes_dbtx_v2(**args, meta_defaults=unsorted)
        self.assertEqual(
            with_defaults,
            canonical_bytes_dbtx_v2(**args, meta_defaults=sorted_rows),
        )
        self.assertEqual(with_defaults.count(DBTX_V2_META_DEFAULTS_SUFFIX), 1)

    def test_tx_default_writer_rejects_duplicates_unset_and_reserved_keys(self) -> None:
        args = {
            "parent_tx_id": None,
            "schema_digest": "sha256:" + "1" * 64,
            "digest_scheme": "lthash16-v2",
            "tx_seq": 0,
            "operations": (),
        }
        invalid = (
            (MetaEntry("source", "str", "a"), MetaEntry("source", "str", "b")),
            ({"key": "source", "kind": None, "value": None},),
            (MetaEntry("__system__.tx", "str", "x"),),
            (MetaEntry("__factgraph_annotation_v1__:forged", "str", "x"),),
            (MetaEntry("assertion_digest", "str", "x"),),
            (MetaEntry("schema_digest", "str", "x"),),
            (MetaEntry("tx_id", "str", "x"),),
            (MetaEntry("ingested_at", "time", 1),),
            (MetaEntry("ingest_key", "str", "x"),),
            (MetaEntry("revoked_asrt_id", "str", "x"),),
        )
        for rows in invalid:
            with self.subTest(rows=rows):
                with self.assertRaises(DatabaseError):
                    canonical_bytes_dbtx_v2(**args, meta_defaults=rows)

    def test_tx_object_reader_rejects_unsorted_duplicate_empty_and_unknown_fields(self) -> None:
        mutations = (
            [
                {"key": "trace_id", "kind": "str", "value": "t"},
                {"key": "source", "kind": "str", "value": "s"},
            ],
            [
                {"key": "source", "kind": "str", "value": "s"},
                {"key": "source", "kind": "str", "value": "t"},
            ],
            [],
        )
        for meta_defaults in mutations:
            with self.subTest(meta_defaults=meta_defaults), tempfile.TemporaryDirectory() as raw:
                workspace = Path(raw) / "workspace"
                database = Database.create(workspace, schema_ir=_schema_ir())
                head = database.head()
                database.close()
                tx_path = (
                    resolve_database_workspace_paths(workspace).tx_objects
                    / f"{head.tx_id.removeprefix('tx:')}.json"
                )
                payload = json.loads(tx_path.read_text(encoding="utf-8"))
                payload["meta_defaults"] = meta_defaults
                tx_path.write_text(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8",
                )
                with self.assertRaises(DatabaseError):
                    Database.open(workspace, schema_ir=_schema_ir())

        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw) / "workspace"
            database = Database.create(workspace, schema_ir=_schema_ir())
            head = database.head()
            database.close()
            tx_path = (
                resolve_database_workspace_paths(workspace).tx_objects
                / f"{head.tx_id.removeprefix('tx:')}.json"
            )
            payload = json.loads(tx_path.read_text(encoding="utf-8"))
            payload["unknown"] = True
            tx_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(DatabaseError):
                Database.open(workspace, schema_ir=_schema_ir())


class TxLiftResolverTests(unittest.TestCase):
    def test_empty_default_world_is_byte_for_byte_single_layer_equivalent(self) -> None:
        database = Database.create(schema_ir=_schema_ir())
        record = database.commit_assertions(
            (
                AssertionInput(
                    "_tx_lift_entity:entity_id",
                    (("entity_ref", "idref_v1:_TxLiftEntity:one"), ("string", "one")),
                    meta=(MetaEntry("source", "str", "claim"),),
                ),
            )
        ).assertions[0]
        ledger = database._ledger_for_attach()
        before = ledger.effective_meta_events(asrt_id=record.asrt_id)
        ledger.replace_tx_meta_defaults(())
        self.assertEqual(ledger.effective_meta_events(asrt_id=record.asrt_id), before)
        database.close()

    def test_inherit_override_unset_and_revoker_symmetry(self) -> None:
        database = Database.create(schema_ir=_schema_ir())
        committed = database.commit_changes(
            assertions=(
                AssertionInput(
                    "_tx_lift_entity:entity_id",
                    (("entity_ref", "idref_v1:_TxLiftEntity:one"), ("string", "one")),
                ),
                AssertionInput(
                    "_tx_lift_entity:entity_id",
                    (("entity_ref", "idref_v1:_TxLiftEntity:two"), ("string", "two")),
                    meta=(MetaEntry("source", "str", "claim-override"),),
                ),
            ),
            revocations=(),
            meta_defaults=(MetaEntry("source", "str", "batch-default"),),
        )
        first, second = committed.assertions
        revoked = database.commit_changes(
            assertions=(),
            revocations=(RevocationInput(first.asrt_id),),
            meta_defaults=(MetaEntry("source", "str", "batch-default"),),
        )
        revoker_id = revoked.revocations[0].revoker_asrt_id
        ledger = database._ledger_for_attach()

        self.assertEqual(
            ledger.effective_meta_rows(asrt_id=first.asrt_id, key="source")[0].value,
            "batch-default",
        )
        self.assertEqual(
            ledger.effective_meta_rows(asrt_id=second.asrt_id, key="source")[0].value,
            "claim-override",
        )
        self.assertEqual(
            ledger.effective_meta_rows(asrt_id=revoker_id, key="source")[0].value,
            "batch-default",
        )
        exclusion = (MetaExclusion("source", frozenset({"batch-default"})),)
        self.assertTrue(is_premise_excluded(ledger, first.asrt_id, exclusion))
        self.assertFalse(is_premise_excluded(ledger, second.asrt_id, exclusion))
        self.assertTrue(is_premise_excluded(ledger, revoker_id, exclusion))

        database._commit_meta_unsets((_MetaUnsetInput(first.asrt_id, "source"),))
        self.assertEqual(
            ledger.effective_meta_rows(asrt_id=first.asrt_id, key="source"), ()
        )
        allowance = {
            "_tx_lift_entity:entity_id": PredicatePremiseAllowance(
                "_tx_lift_entity:entity_id",
                "source",
                frozenset({"batch-default"}),
                absent_ok=False,
            )
        }
        self.assertTrue(
            is_predicate_premise_excluded(ledger, first.asrt_id, allowance)
        )
        database.close()

    def test_commit_defaults_require_consumers_and_tx_liftable_schema_keys(self) -> None:
        database = Database.create(schema_ir=_schema_ir())
        before = database.head()
        invalid_calls = (
            {
                "assertions": (),
                "revocations": (),
                "meta_defaults": (MetaEntry("source", "str", "batch"),),
            },
            {
                "assertions": (
                    AssertionInput(
                        "_tx_lift_entity:entity_id",
                        (("entity_ref", "idref_v1:_TxLiftEntity:one"), ("string", "one")),
                    ),
                ),
                "revocations": (),
                "meta_defaults": (MetaEntry("ordinary", "str", "not-liftable"),),
            },
        )
        for kwargs in invalid_calls:
            with self.subTest(kwargs=kwargs), self.assertRaises(DatabaseError):
                database.commit_changes(**kwargs)
            self.assertEqual(database.head(), before)
        database.close()

    def test_commit_defaults_reject_every_reserved_key_before_writing(self) -> None:
        database = Database.create(schema_ir=_schema_ir())
        before = database.head()
        assertion = AssertionInput(
            "_tx_lift_entity:entity_id",
            (("entity_ref", "idref_v1:_TxLiftEntity:one"), ("string", "one")),
        )
        for key in (
            "__system__.batch",
            "__factgraph_annotation_v1__:forged",
            "assertion_digest",
            "schema_digest",
            "tx_id",
            "ingested_at",
            "ingest_key",
            "revoked_asrt_id",
        ):
            with self.subTest(key=key), self.assertRaises(DatabaseError):
                database.commit_changes(
                    assertions=(assertion,),
                    revocations=(),
                    meta_defaults=(MetaEntry(key, "str", "forged"),),
                )
            self.assertEqual(database.head(), before)
        database.close()


if __name__ == "__main__":
    unittest.main()
