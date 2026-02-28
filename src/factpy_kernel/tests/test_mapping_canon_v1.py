from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.mapping.canon import MappingConflictError
from factpy_kernel.core.store.api import Store
from factpy_kernel.core.store.ledger import MetaRow


class MappingCanonV1Tests(unittest.TestCase):
    def test_mapping_conflict_error_default(self) -> None:
        store = Store(schema_ir=_schema_with_mapping(tie_break=None))
        mention = "idref_v1:Person:m1"
        canon_a = "idref_v1:Person:c_a"
        canon_b = "idref_v1:Person:c_b"

        set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", canon_a)],
            meta={"source": "hr", "source_loc": "row-1"},
        )
        set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", canon_b)],
            meta={"source": "crm", "source_loc": "row-2"},
        )

        with self.assertRaises(MappingConflictError):
            store.resolve_mapping("er:canon_of", policy_mode="edb")

    def test_mapping_latest_tie_break(self) -> None:
        store = Store(
            schema_ir=_schema_with_mapping(
                tie_break="latest_by_ingested_at_then_min_assertion_id"
            )
        )
        mention = "idref_v1:Person:m2"
        canon_old = "idref_v1:Person:c_old"
        canon_new = "idref_v1:Person:c_new"

        asrt_old = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", canon_old)],
            meta={"source": "hr", "source_loc": "row-1"},
        )
        asrt_new = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", canon_new)],
            meta={"source": "crm", "source_loc": "row-2"},
        )
        _set_ingested_at(store, asrt_old, 100)
        _set_ingested_at(store, asrt_new, 200)

        resolution = store.resolve_mapping("er:canon_of", policy_mode="edb")
        self.assertEqual(resolution.chosen_map[(mention,)], (canon_new,))

    def test_mapping_prefer_source_tie_break(self) -> None:
        store = Store(
            schema_ir=_schema_with_mapping(
                tie_break={"mode": "prefer_source", "source_rank": ["crm", "hr"]}
            )
        )
        mention = "idref_v1:Person:m3"
        canon_hr = "idref_v1:Person:c_hr"
        canon_crm = "idref_v1:Person:c_crm"

        asrt_hr = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", canon_hr)],
            meta={"source": "hr", "source_loc": "row-1"},
        )
        asrt_crm = set_field(
            store.ledger,
            pred_id="er:canon_of",
            e_ref=mention,
            rest_terms=[("entity_ref", canon_crm)],
            meta={"source": "crm", "source_loc": "row-2"},
        )
        _set_ingested_at(store, asrt_hr, 300)
        _set_ingested_at(store, asrt_crm, 100)

        resolution = store.resolve_mapping("er:canon_of", policy_mode="edb")
        self.assertEqual(resolution.chosen_map[(mention,)], (canon_crm,))

    def test_mapping_idb_rejects_non_error_tie_break(self) -> None:
        store = Store(
            schema_ir=_schema_with_mapping(
                tie_break="latest_by_ingested_at_then_min_assertion_id"
            )
        )
        with self.assertRaises(NotImplementedError):
            store.resolve_mapping("er:canon_of", policy_mode="idb")


def _schema_with_mapping(tie_break: object) -> dict:
    predicate: dict[str, object] = {
        "pred_id": "er:canon_of",
        "arg_specs": [
            {"name": "mention", "type_domain": "entity_ref"},
            {"name": "canonical", "type_domain": "entity_ref"},
        ],
        "group_key_indexes": [0],
        "cardinality": "functional",
        "is_mapping": True,
        "mapping_kind": "single_valued",
        "mapping_key_positions": [0],
        "mapping_value_positions": [1],
    }
    if tie_break is not None:
        predicate["tie_break"] = tie_break

    return {
        "schema_ir_version": "v1",
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [
                    {"name": "source_id", "type_domain": "string"},
                ],
            }
        ],
        "predicates": [predicate],
        "projection": {
            "entities": [],
            "predicates": ["er:canon_of"],
        },
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": "2026-01-01T00:00:00Z",
    }


def _set_ingested_at(store: Store, asrt_id: str, epoch_nanos: int) -> None:
    replaced = False
    updated: list[MetaRow] = []
    for row in store.ledger.meta_rows:
        if row.asrt_id == asrt_id and row.key == "ingested_at":
            updated.append(
                MetaRow(
                    asrt_id=row.asrt_id,
                    key=row.key,
                    kind="time",
                    value=epoch_nanos,
                )
            )
            replaced = True
        else:
            updated.append(row)
    if not replaced:
        raise AssertionError(f"missing ingested_at for asrt_id={asrt_id}")
    store.ledger._force_replace_meta_rows(updated)
if __name__ == "__main__":
    unittest.main()
