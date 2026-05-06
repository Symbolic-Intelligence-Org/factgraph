from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


class RoundStoryFullDemoTests(unittest.TestCase):
    def test_round_story_full_demo_returns_exact_phase_summary(self) -> None:
        module = _load_demo_module()

        self.assertEqual(
            module.run_demo(verbose=False),
            module.EXPECTED_PHASE_SUMMARY,
        )
        self.assertEqual(
            module.run_sdk_check_diagnose_demo(verbose=False),
            {"check": "passed", "diagnose": "atom_localized"},
        )
        self.assertEqual(
            module.run_overlay_why_not_frontier_demo(verbose=False),
            {
                "fact_overlay": "passed",
                "why_not": "completed",
                "frontier": "atom_filter_empty",
            },
        )
        self.assertEqual(
            module.run_proofframe_rule_overlay_demo(verbose=False),
            {
                "proofframe": "invalidated",
                "rule_disable": "completed",
                "rule_literal_replace": "completed",
                "rule_add_condition": "completed",
            },
        )
        self.assertEqual(
            module.run_round_persistence_diff_demo(verbose=False),
            {"round_diff": "frame_status_changed"},
        )


def _load_demo_module():
    repo_root = Path(__file__).resolve().parents[3]
    demo_path = repo_root / "examples" / "round_story_full_demo.py"
    spec = importlib.util.spec_from_file_location("round_story_full_demo", demo_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"failed to load demo module from {demo_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
