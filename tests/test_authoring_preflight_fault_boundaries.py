"""Fault-injection characterization for the broad boundaries in factgraph.authoring.preflight.

``_find_souffle_binary_safe`` guards an optional adapter import and an
environment probe.  A failing probe must degrade to "binary not found", which
the caller turns into an explicit preflight warning diagnostic - never into a
silent claim that a Soufflé preview will work.
"""

from __future__ import annotations

import builtins
import unittest
from unittest.mock import patch

from factgraph.authoring import preflight
from factgraph.authoring.diagnostic_codes import CODE_SOUFFLE_BINARY_MISSING
from factgraph.authoring.preflight import _find_souffle_binary_safe


class _BoundaryFault(Exception):
    """Custom, non-ImportError failure injected into the Soufflé probe boundary."""


class SouffleProbeBoundaryTests(unittest.TestCase):
    """src/factgraph/authoring/preflight.py: adapter import + binary probe boundaries."""

    def test_import_fault_degrades_to_binary_not_found(self) -> None:
        real_import = builtins.__import__

        def _boom(name, *args, **kwargs):
            if name == "factgraph.adapters.souffle.runner":
                raise _BoundaryFault("injected adapter import failure")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", _boom):
            self.assertIsNone(_find_souffle_binary_safe())

    def test_probe_fault_degrades_to_binary_not_found(self) -> None:
        from factgraph.adapters.souffle import runner

        with patch.object(runner, "find_souffle_binary", side_effect=_BoundaryFault("probe boom")):
            self.assertIsNone(_find_souffle_binary_safe())

    def test_import_keyboard_interrupt_is_not_swallowed(self) -> None:
        real_import = builtins.__import__

        def _boom(name, *args, **kwargs):
            if name == "factgraph.adapters.souffle.runner":
                raise KeyboardInterrupt
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", _boom):
            with self.assertRaises(KeyboardInterrupt):
                _find_souffle_binary_safe()

    def test_probe_keyboard_interrupt_is_not_swallowed(self) -> None:
        from factgraph.adapters.souffle import runner

        with patch.object(runner, "find_souffle_binary", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                _find_souffle_binary_safe()

    def test_probe_fault_is_reported_as_an_explicit_preflight_warning(self) -> None:
        """A degraded probe surfaces a warning; it is never a silent 'engine is fine'."""
        from factgraph.core.store import Store
        from factgraph.sdk import Entity, Identity, compile_schema_from_classes

        class Person(Entity):
            name: str = Identity()

        store = Store(compile_schema_from_classes([Person]))

        with patch.object(preflight, "_find_souffle_binary_safe", return_value=None), patch.object(
            Store, "evaluate", return_value=[]
        ):
            payload = preflight.derivation_dry_run_preview(
                store=store,
                derivation_id="d1",
                version="1.0",
                target_pred_id="Person.name",
                head_vars=["$p"],
                where=[],
                mode="souffle",
            )

        codes = {item.get("code") for item in payload["warnings"]}
        self.assertIn(CODE_SOUFFLE_BINARY_MISSING, codes)
        warning = next(
            item for item in payload["warnings"] if item.get("code") == CODE_SOUFFLE_BINARY_MISSING
        )
        self.assertEqual(warning.get("severity"), "warning")


if __name__ == "__main__":
    unittest.main()
