"""Scalar evidence tokens and actual relationships keep distinct batch semantics."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factgraph.sdk import (
    Database,
    Entity,
    FactGraph,
    Field,
    Identity,
    SDKStoreError,
    compile_schema_from_classes,
)
from factgraph.sdk.batch import WireBatchPlan


class BatchReferenceTarget(Entity):
    key: str = Identity()
    label: str = Field()


class BatchEvidenceRecord(Entity):
    key: str = Identity()
    token: str = Field()
    tokens: list[str] = Field()
    target: BatchReferenceTarget = Field()


_SCHEMA = [BatchReferenceTarget, BatchEvidenceRecord]


class BatchScalarReferenceContractTests(unittest.TestCase):
    def test_opaque_tokens_preserve_scalar_tags_set_add_and_deduplication(self):
        for value in ("ordinary-text", "idref_v1:Foreign:example", "idref_v1:"):
            with self.subTest(value=value), FactGraph.create(schema_classes=_SCHEMA) as fg:
                tx = fg.batch(meta={"source": "evidence"})
                row = tx.entity(BatchEvidenceRecord, key="record")
                row.token.set(value)
                row.tokens.add(value)
                row.tokens.add(value)
                tx.commit()
                snapshot = fg.entities.get(BatchEvidenceRecord, key="record")
                self.assertEqual(snapshot.token, value)
                self.assertEqual(snapshot.tokens, (value,))
                for member in ("token", "tokens"):
                    assertion = snapshot.assertions.field(member).active.one()
                    self.assertEqual(assertion.value_tag, "string")
                    self.assertEqual(assertion.meta.source, "evidence")

    def test_same_known_reference_is_scalar_or_relation_according_to_field(self):
        with FactGraph.create(schema_classes=_SCHEMA) as fg:
            reference = fg.entities.create(BatchReferenceTarget, key="known")
            tx = fg.batch()
            row = tx.entity(BatchEvidenceRecord, key="record")
            row.token.set(reference)
            row.tokens.add(reference)
            row.target.set(reference)
            tx.commit()
            snapshot = fg.entities.get(BatchEvidenceRecord, key="record")
            self.assertEqual(snapshot.token, reference)
            self.assertEqual(snapshot.tokens, (reference,))
            self.assertEqual(snapshot.target, reference)
            self.assertEqual(snapshot.assertions.field("token").active.one().value_tag, "string")
            self.assertEqual(snapshot.assertions.field("target").active.one().value_tag, "entity_ref")

    def test_wire_roundtrip_keeps_scalar_tokens_and_staged_relationship(self):
        value = "idref_v1:Foreign:example"
        with FactGraph.create(schema_classes=_SCHEMA) as source:
            tx = source.batch()
            target = tx.entity(BatchReferenceTarget, key="target")
            target.label.set("Target")
            row = tx.entity(BatchEvidenceRecord, key="record")
            row.token.set(value)
            row.tokens.add(value)
            row.target.set(target)
            payload = tx.preview().export(source).to_json()
            self.assertFalse(source.entities.exists(BatchEvidenceRecord, key="record"))
            self.assertFalse(source.entities.exists(BatchReferenceTarget, key="target"))
        with FactGraph.create(schema_classes=_SCHEMA) as destination:
            WireBatchPlan.from_json(payload).apply(destination)
            snapshot = destination.entities.get(BatchEvidenceRecord, key="record")
            self.assertEqual(snapshot.token, value)
            self.assertEqual(snapshot.tokens, (value,))
            self.assertEqual(
                snapshot.target, destination.entities.ref(BatchReferenceTarget, key="target")
            )

    def test_unmanaged_relationship_still_rejects_entire_batch(self):
        with (
            Database.create(schema_ir=compile_schema_from_classes(_SCHEMA)) as database,
            FactGraph.attach(database, schema_classes=_SCHEMA) as fg,
        ):
            before = database.head()
            tx = fg.batch()
            row = tx.entity(BatchEvidenceRecord, key="record")
            row.token.set("ordinary-text")
            row.target.set("idref_v1:BatchReferenceTarget:unmanaged")
            with self.assertRaisesRegex(SDKStoreError, "not managed by this runtime"):
                tx.commit()
            self.assertEqual(database.head(), before)
            self.assertFalse(fg.entities.exists(BatchEvidenceRecord, key="record"))

    def test_invalid_relationship_does_not_become_scalar(self):
        with FactGraph.create(schema_classes=_SCHEMA) as fg:
            tx = fg.batch()
            row = tx.entity(BatchEvidenceRecord, key="record")
            with self.assertRaises(SDKStoreError):
                row.target.set(17)
            self.assertFalse(fg.entities.exists(BatchEvidenceRecord, key="record"))

    def test_durable_scalar_and_relation_batch_survives_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace"
            with FactGraph.create(path=path, schema_classes=_SCHEMA) as fg:
                tx = fg.batch()
                target = tx.entity(BatchReferenceTarget, key="target")
                target.label.set("Target")
                row = tx.entity(BatchEvidenceRecord, key="record")
                row.token.set("idref_v1:Foreign:example")
                row.tokens.add("idref_v1:Foreign:example")
                row.target.set(target)
                tx.commit()
            with FactGraph.load_workspace(path, schema_classes=_SCHEMA) as reopened:
                snapshot = reopened.entities.get(BatchEvidenceRecord, key="record")
                self.assertEqual(snapshot.token, "idref_v1:Foreign:example")
                self.assertEqual(snapshot.tokens, ("idref_v1:Foreign:example",))
                self.assertEqual(
                    snapshot.target, reopened.entities.ref(BatchReferenceTarget, key="target")
                )


if __name__ == "__main__":
    unittest.main()
