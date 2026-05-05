from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


def _load_demo_module() -> types.ModuleType:
    repo_root = Path(__file__).resolve().parents[3]
    demo_path = repo_root / "examples" / "11_capabilities_e2e_demo.py"
    spec = importlib.util.spec_from_file_location("capabilities_e2e_demo", demo_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load demo script: {demo_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CapabilitiesE2EDemoSmokeTests(unittest.TestCase):
    def test_capabilities_e2e_demo_runs_assertion_bearing_flow(self) -> None:
        demo = _load_demo_module()

        outcomes = demo.run_demo(verbose=False)

        self.assertEqual(
            outcomes,
            {
                "check": "passed",
                "diagnose": "atom_localized",
                "fact_overlay": "passed",
                "why_not": "completed",
                "frontier": "atom_filter_empty",
            },
        )


if __name__ == "__main__":
    unittest.main()
