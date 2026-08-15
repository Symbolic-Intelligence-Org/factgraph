"""Regression gate for the disposable Q17 D09 native observation probe."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType


def _probe_module() -> ModuleType:
    root = Path(__file__).resolve().parents[2]
    path = root / "tools" / "spikes" / "d09_native_absence_closure" / "probe.py"
    spec = importlib.util.spec_from_file_location("d09_native_absence_closure_probe", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load D09 native observation probe")
    module = importlib.util.module_from_spec(spec)
    # ``probe.py`` uses frozen dataclasses with postponed annotations; the
    # module must be visible during class decoration exactly as normal import
    # machinery makes it visible.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_q17_native_observation_matrix_is_stable() -> None:
    probe = _probe_module()

    observations = probe.verify_matrix()

    assert [
        (
            item.cell,
            item.mechanism,
            item.before_matches,
            item.after_matches,
            item.observation,
        )
        for item in observations
    ] == list(probe._EXPECTED_MATRIX)


def test_q17_output_keeps_the_observed_only_interpretation_boundary() -> None:
    probe = _probe_module()

    output = probe.observations_as_json()

    assert probe._INTERPRETATION_BOUNDARY in output
    assert "MISSING" in output
    assert "MASKED" in output
    assert "NEGATED" in output
    assert "closed-world" in output
