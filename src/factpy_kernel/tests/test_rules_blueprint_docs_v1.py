from __future__ import annotations

import unittest
from pathlib import Path


class RulesBlueprintDocsV1Tests(unittest.TestCase):
    def test_derivation_doc_has_v2_redirect_notice(self) -> None:
        text = _rules_doc().read_text(encoding="utf-8")
        self.assertIn("Derivation 的当前可执行语法以 v2 为准", text)
        self.assertIn("用户侧不再使用 `materialize_as/id_policy`", text)
        self.assertIn("candidate_protocol_v2.md", text)

    def test_derivation_doc_mentions_head_inference_rule(self) -> None:
        text = _rules_doc().read_text(encoding="utf-8")
        self.assertIn("head", text)
        self.assertIn("candidate kind", text)


def _rules_doc() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "blueprint" / "规则.md"


if __name__ == "__main__":
    unittest.main()
