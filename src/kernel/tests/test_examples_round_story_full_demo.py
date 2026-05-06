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
