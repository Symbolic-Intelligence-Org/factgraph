from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factgraph.audit.meta_history import (
    effective_meta_at,
    export_meta_history,
    import_meta_history,
    read_meta_history,
)
from factgraph.core.store.database import (
    AssertionInput,
    Database,
    DatabaseError,
    MetaAppendInput,
    MetaEntry,
    RevocationInput,
    _MetaUnsetInput,
    resolve_database_workspace_paths,
)
from factgraph.core.store.ledger import MetaRow
from factgraph.core.store.premise_filter import (
    MetaExclusion,
    PredicatePremiseAllowance,
    is_predicate_premise_excluded,
    is_premise_excluded,
)


_ASSERTION_ID = "asrt:11111111111111111111111111111111"
_REVOKER_ID = "asrt:22222222222222222222222222222222"


class Slice3bMetaEventSemanticsTests(unittest.TestCase):
    def test_repeated_key_unset_as_of_and_cold_export_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp, patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID],
        ):
            workspace = Path(raw_tmp) / "workspace"
            db = Database.create(workspace, schema_ir=_schema_ir())
            record = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                        (MetaEntry("provenance_class", "str", "observed"),),
                    ),
                )
            ).assertions[0]
            first = db.commit_changes(
                assertions=(),
                revocations=(),
                meta_appends=(
                    MetaAppendInput(record.asrt_id, "provenance_class", "str", "agent"),
                ),
            )
            second = db.commit_changes(
                assertions=(),
                revocations=(),
                meta_appends=(
                    MetaAppendInput(record.asrt_id, "provenance_class", "str", "human"),
                ),
            )
            unset = db._commit_meta_unsets(
                (_MetaUnsetInput(record.asrt_id, "provenance_class"),)
            )

            ledger = db._ledger_for_attach()
            history = read_meta_history(
                ledger,
                asrt_id=record.asrt_id,
                key="provenance_class",
            )
            self.assertEqual(
                [(event.tx_seq, event.op_ordinal, event.kind, event.value) for event in history],
                [
                    (1, 0, "str", "observed"),
                    (first.value.tx_seq, 0, "str", "agent"),
                    (second.value.tx_seq, 0, "str", "human"),
                    (unset.value.tx_seq, 0, None, None),
                ],
            )
            self.assertEqual(
                ledger._effective_meta_rows(
                    asrt_id=record.asrt_id,
                    key="provenance_class",
                ),
                (),
            )
            self.assertEqual(
                effective_meta_at(
                    ledger,
                    asrt_id=record.asrt_id,
                    as_of=(second.value.tx_seq, 0),
                )["provenance_class"],
                "human",
            )
            before = export_meta_history(ledger, asrt_id=record.asrt_id)
            self.assertEqual(import_meta_history(before), read_meta_history(ledger, asrt_id=record.asrt_id))
            db.close()

            reopened = Database.open(workspace, schema_ir=_schema_ir())
            try:
                cold = export_meta_history(
                    reopened._ledger_for_attach(),
                    asrt_id=record.asrt_id,
                )
                self.assertEqual(cold, before)
                self.assertEqual(import_meta_history(cold), import_meta_history(before))
            finally:
                reopened.close()

            tx_path = (
                resolve_database_workspace_paths(workspace).tx_objects
                / f"{unset.value.tx_id.removeprefix('tx:')}.json"
            )
            operation = json.loads(tx_path.read_text(encoding="utf-8"))["operations"][0]
            self.assertEqual(
                operation["meta"],
                {"key": "provenance_class", "kind": None, "value": None},
            )

    def test_unset_is_missing_for_exclusion_allowance_and_revoker(self) -> None:
        with patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID, _REVOKER_ID],
        ):
            db = Database.create(schema_ir=_schema_ir())
            assertion = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                        (MetaEntry("provenance_class", "str", "blocked"),),
                    ),
                )
            ).assertions[0]
            revoker = db.commit_changes(
                assertions=(),
                revocations=(
                    RevocationInput(
                        assertion.asrt_id,
                        (MetaEntry("provenance_class", "str", "blocked"),),
                    ),
                ),
            ).revocations[0]
            ledger = db._ledger_for_attach()
            exclusion = (MetaExclusion("provenance_class", frozenset({"blocked"})),)
            self.assertTrue(is_premise_excluded(ledger, revoker.revoker_asrt_id, exclusion))

            db._commit_meta_unsets(
                (
                    _MetaUnsetInput(assertion.asrt_id, "provenance_class"),
                    _MetaUnsetInput(revoker.revoker_asrt_id, "provenance_class"),
                )
            )
            self.assertFalse(is_premise_excluded(ledger, assertion.asrt_id, exclusion))
            self.assertFalse(is_premise_excluded(ledger, revoker.revoker_asrt_id, exclusion))
            self.assertTrue(
                is_predicate_premise_excluded(
                    ledger,
                    assertion.asrt_id,
                    {
                        "person:name": PredicatePremiseAllowance(
                            "person:name",
                            "provenance_class",
                            frozenset({"observed"}),
                            absent_ok=False,
                        )
                    },
                )
            )
            self.assertFalse(
                is_predicate_premise_excluded(
                    ledger,
                    assertion.asrt_id,
                    {
                        "person:name": PredicatePremiseAllowance(
                            "person:name",
                            "provenance_class",
                            frozenset({"observed"}),
                            absent_ok=True,
                        )
                    },
                )
            )
            db.close()

    def test_generic_meta_inputs_cannot_forge_dual_null_event(self) -> None:
        with patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID],
        ):
            db = Database.create(schema_ir=_schema_ir())
            assertion = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                    ),
                )
            ).assertions[0]
            head = db.head()
            with self.assertRaisesRegex(DatabaseError, "unsupported meta kind"):
                db.commit_changes(
                    assertions=(),
                    revocations=(),
                    meta_appends=(MetaAppendInput(assertion.asrt_id, "source", None, None),),  # type: ignore[arg-type]
                )
            self.assertEqual(db.head(), head)

            ledger = db._ledger_for_attach()
            with self.assertRaisesRegex(ValueError, "unsupported meta kind"):
                ledger.append_meta(
                    [MetaRow(assertion.asrt_id, "source", None, None)]  # type: ignore[arg-type]
                )
            self.assertEqual(db.head(), head)
            db.close()


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
        "generated_at": "2026-08-02T00:00:00Z",
    }


if __name__ == "__main__":
    unittest.main()
