"""Layer 4C1 clarity heuristic tests."""

from __future__ import annotations

import unittest

from factpy.agent import compute_structural_clarity, detect_section_label


class AgentLayer4C1ClarityTests(unittest.TestCase):
    def test_if_then_scores_high(self) -> None:
        score, pattern = compute_structural_clarity("If customer is VIP then escalate review.")
        self.assertGreaterEqual(score, 0.7)
        self.assertEqual(pattern, "if_then")

    def test_definition_scores_definition_band(self) -> None:
        score, pattern = compute_structural_clarity("Account means an identified customer ledger.")
        self.assertGreaterEqual(score, 0.7)
        self.assertEqual(pattern, "definition")

    def test_narrative_scores_low(self) -> None:
        score, pattern = compute_structural_clarity("This paragraph tells a story without explicit structure.")
        self.assertLessEqual(score, 0.3)
        self.assertEqual(pattern, "narrative")

    def test_detect_section_label_supports_markdown_article_and_chinese(self) -> None:
        self.assertEqual(detect_section_label("# Intro"), "Intro")
        self.assertEqual(detect_section_label("Article 3.2 Requirements"), "Article 3.2")
        self.assertEqual(detect_section_label("第五条 审批要求"), "第五条")


if __name__ == "__main__":
    unittest.main()
