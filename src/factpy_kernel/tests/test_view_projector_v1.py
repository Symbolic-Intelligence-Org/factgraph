from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import retract_by_asrt, set_field
from factpy_kernel.core.policy.chosen import PolicyNonDeterminismError, compute_chosen_for_predicate
from factpy_kernel.core.store.ledger import Ledger, MetaRow
from factpy_kernel.core.view.projector import project_view_facts


class ViewProjectorV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = Ledger()
        self.pred_id = "person:country"
        self.e_ref = (
            "idref_v1:Person:irk4tcjz3wzyl4ja6245k5duzqd3vn5dypm4rr5s7glkdulef4ha"
        )
        self.schema_pred = {
            "pred_id": self.pred_id,
            "arg_specs": [
                {"name": "E", "type_domain": "entity_ref"},
                {"name": "country", "type_domain": "string"},
            ],
            "group_key_indexes": [0],
            "cardinality": "functional",
        }
        self.schema_ir = {"predicates": [self.schema_pred]}

    def test_functional_chosen_and_tie_break(self) -> None:
        asrt_1 = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "de")],
            {"source": "test", "source_loc": "row-1"},
        )
        asrt_2 = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "fr")],
            {"source": "test", "source_loc": "row-2"},
        )

        self._set_ingested_at(asrt_1, 100)
        self._set_ingested_at(asrt_2, 200)

        view_facts = project_view_facts(self.ledger, self.schema_ir)
        self.assertEqual(view_facts[self.pred_id], [(self.e_ref, "fr")])

        chosen_map = compute_chosen_for_predicate(self.ledger, self.schema_pred)
        group_key = (self.pred_id, self.e_ref)
        self.assertEqual(chosen_map[group_key], asrt_2)

        self._set_ingested_at(asrt_1, 300)
        self._set_ingested_at(asrt_2, 300)
        tie_chosen_map = compute_chosen_for_predicate(self.ledger, self.schema_pred)
        expected_asrt = min(asrt_1, asrt_2)
        self.assertEqual(tie_chosen_map[group_key], expected_asrt)

    def test_revoke_latest_rolls_back_view(self) -> None:
        asrt_1 = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "de")],
            {"source": "test", "source_loc": "row-1"},
        )
        asrt_2 = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "fr")],
            {"source": "test", "source_loc": "row-2"},
        )

        self._set_ingested_at(asrt_1, 100)
        self._set_ingested_at(asrt_2, 200)

        retract_by_asrt(self.ledger, asrt_2, {"source": "review"})

        view_facts = project_view_facts(self.ledger, self.schema_ir)
        self.assertEqual(view_facts[self.pred_id], [(self.e_ref, "de")])

    def test_missing_ingested_at_raises_policy_error(self) -> None:
        asrt_id = set_field(
            self.ledger,
            self.pred_id,
            self.e_ref,
            [("string", "de")],
            {"source": "test", "source_loc": "row-1"},
        )
        self.ledger._force_replace_meta_rows([
            row
            for row in self.ledger.meta_rows
            if not (row.asrt_id == asrt_id and row.key == "ingested_at")
        ])

        with self.assertRaises(PolicyNonDeterminismError):
            compute_chosen_for_predicate(self.ledger, self.schema_pred)

    def _set_ingested_at(self, asrt_id: str, epoch_nanos: int) -> None:
        replaced = False
        updated: list[MetaRow] = []
        for row in self.ledger.meta_rows:
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
            raise AssertionError(f"missing ingested_at row for asrt_id={asrt_id}")
        self.ledger._force_replace_meta_rows(updated)
if __name__ == "__main__":
    unittest.main()
