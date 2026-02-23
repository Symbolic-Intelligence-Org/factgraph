from __future__ import annotations

import unittest
from pathlib import Path


class RulesBlueprintDocsV1Tests(unittest.TestCase):
    def test_derivation_head_materialize_status_section_exists(self) -> None:
        text = _rules_doc().read_text(encoding="utf-8")
        self.assertIn("#### 5.2.4 当前实现对齐状态（v1）", text)
        for phrase in [
            'head=Person.field(...), materialize_as="fact"',
            'head=RecordType(...), materialize_as="record"',
            'head=RecordType(...), materialize_as="fact"',
            "lowering 为 position-based `head_vars`",
        ]:
            self.assertIn(phrase, text)

    def test_derivation_record_id_policy_v1_subset_is_documented(self) -> None:
        text = _rules_doc().read_text(encoding="utf-8")
        self.assertIn('id_policy={"kind":"key_tuple_digest_v1"}', text)
        self.assertIn('"kind": "identity_fields_v1"', text)
        self.assertIn("role-sourced", text)
        self.assertIn("projection_pred_id", text)
        self.assertIn("projection_arg_order", text)


def _rules_doc() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "规则.md"


if __name__ == "__main__":
    unittest.main()
