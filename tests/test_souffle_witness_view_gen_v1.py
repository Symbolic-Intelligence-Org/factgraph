from __future__ import annotations

import unittest

from factpy.adapters.souffle.pred_norm import normalize_pred_id
from factpy.adapters.souffle.souffle_view_gen import generate_view_dl, witness_rel_name


class SouffleWitnessViewGenV1Tests(unittest.TestCase):
    def test_generate_view_dl_without_witness_views_keeps_legacy_shape(self) -> None:
        dl = generate_view_dl(_schema_ir(), include_witness_views=False)

        self.assertIn(".decl p_user_name(E:symbol, V0:symbol)", dl)
        self.assertIn(".output p_user_name", dl)
        self.assertNotIn(".decl p_user_name_w(", dl)
        self.assertNotIn("p_user_name_w(E, V0, A)", dl)

    def test_generate_view_dl_with_witness_views_emits_multi_and_single_variants(self) -> None:
        dl = generate_view_dl(_schema_ir(), include_witness_views=True)

        self.assertIn(".decl p_user_name(E:symbol, V0:symbol)", dl)
        self.assertIn(".decl p_user_name_w(E:symbol, V0:symbol, WA:symbol)", dl)
        self.assertIn(
            'p_user_name_w(E, V0, A) :- claim(A,"user:name",E,_), active(A), claim_arg(A,"0",V0,TagOut0).',
            dl,
        )

        self.assertIn(".decl p_user_status(E:symbol, V0:symbol)", dl)
        self.assertIn(".decl p_user_status_w(E:symbol, V0:symbol, WA:symbol)", dl)
        self.assertIn(".decl chosen_asrt__p_user_status(E:symbol, A:symbol)", dl)
        self.assertIn(
            'p_user_status_w(E, V0, A) :- chosen_asrt__p_user_status(E, A), claim_arg(A,"0",V0,TagOut0).',
            dl,
        )

    def test_witness_rel_name_uses_w_suffix(self) -> None:
        self.assertEqual(witness_rel_name(normalize_pred_id("user:name")), "p_user_name_w")


def _schema_ir() -> dict[str, object]:
    return {
        "predicates": [
            {
                "pred_id": "user:name",
                "cardinality": "multi",
                "arg_specs": [
                    {"name": "e_ref", "type_domain": "entity_ref"},
                    {"name": "name", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            },
            {
                "pred_id": "user:status",
                "cardinality": "single",
                "arg_specs": [
                    {"name": "e_ref", "type_domain": "entity_ref"},
                    {"name": "status", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            },
        ]
    }


if __name__ == "__main__":
    unittest.main()
