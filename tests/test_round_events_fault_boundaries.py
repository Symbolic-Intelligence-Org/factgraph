"""Fault-injection characterization for the broad boundaries in factgraph.audit.round_events.

Both guarded sites (``_replace_jsonl`` / ``_replace_json``) only clean up the
temporary file of an atomic replace: they must never turn a serialization or
filesystem failure into a silent success, and the original exception has to
reach the caller unchanged, with its temp file removed.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factgraph.audit import round_events
from factgraph.audit.round_events import _replace_json, _replace_jsonl


class _BoundaryFault(Exception):
    """Custom, non-OSError failure injected into the atomic replace boundary."""


def _tmp_siblings(directory: Path, name: str) -> list[Path]:
    return sorted(directory.glob(f".{name}.*.tmp"))


class ReplaceJsonlBoundaryTests(unittest.TestCase):
    """src/factgraph/audit/round_events.py: ``_replace_jsonl`` temp-file cleanup."""

    def test_serialization_fault_propagates_and_removes_the_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "round_events.jsonl"

            with (
                patch.object(round_events.json, "dumps", side_effect=_BoundaryFault("boom-jsonl")),
                self.assertRaises(_BoundaryFault) as ctx,
            ):
                _replace_jsonl(target, [{"a": 1}])

            # Preserved cause/detail: the original exception, not a wrapper.
            self.assertEqual(str(ctx.exception), "boom-jsonl")
            self.assertIsNone(ctx.exception.__cause__)
            # Not reported as success: no target file, no leaked temp file.
            self.assertFalse(target.exists())
            self.assertEqual(_tmp_siblings(directory, target.name), [])

    def test_os_replace_fault_propagates_and_removes_the_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "round_events.jsonl"

            with (
                patch.object(round_events.os, "replace", side_effect=OSError("replace failed")),
                self.assertRaises(OSError),
            ):
                _replace_jsonl(target, [{"a": 1}])

            self.assertFalse(target.exists())
            self.assertEqual(_tmp_siblings(directory, target.name), [])

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "round_events.jsonl"

            with (
                patch.object(round_events.json, "dumps", side_effect=KeyboardInterrupt),
                self.assertRaises(KeyboardInterrupt),
            ):
                _replace_jsonl(target, [{"a": 1}])

    def test_happy_path_still_writes_the_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "round_events.jsonl"
            _replace_jsonl(target, [{"a": 1}, {"b": 2}])
            rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows, [{"a": 1}, {"b": 2}])
            self.assertEqual(_tmp_siblings(directory, target.name), [])


class ReplaceJsonBoundaryTests(unittest.TestCase):
    """src/factgraph/audit/round_events.py: ``_replace_json`` temp-file cleanup."""

    def test_serialization_fault_propagates_and_leaves_manifest_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "manifest.json"
            target.write_text('{"package_kind": "audit"}', encoding="utf-8")

            with (
                patch.object(round_events.json, "dumps", side_effect=_BoundaryFault("boom-json")),
                self.assertRaises(_BoundaryFault) as ctx,
            ):
                _replace_json(target, {"package_kind": "audit", "paths": {}})

            self.assertEqual(str(ctx.exception), "boom-json")
            # Not reported as success: the previous manifest content is unchanged.
            self.assertEqual(target.read_text(encoding="utf-8"), '{"package_kind": "audit"}')
            self.assertEqual(_tmp_siblings(directory, target.name), [])

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "manifest.json"
            target.write_text("{}", encoding="utf-8")

            with (
                patch.object(round_events.json, "dumps", side_effect=KeyboardInterrupt),
                self.assertRaises(KeyboardInterrupt),
            ):
                _replace_json(target, {"a": 1})

    def test_happy_path_still_replaces_the_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "manifest.json"
            target.write_text("{}", encoding="utf-8")
            _replace_json(target, {"package_kind": "audit"})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"package_kind": "audit"})
            self.assertEqual(_tmp_siblings(directory, target.name), [])


if __name__ == "__main__":
    unittest.main()
