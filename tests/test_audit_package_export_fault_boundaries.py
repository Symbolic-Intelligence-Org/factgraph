"""Fault-injection characterization for the broad boundary in factgraph.audit.package_export.

``_build_mapping_audit_payload`` resolves each mapping predicate through the
store/policy adapters.  A resolution fault must be recorded as an explicit
``status="error"`` row carrying the original message - never dropped, and never
mistaken for a resolved mapping with zero decisions.
"""

from __future__ import annotations

import unittest
from typing import Any

from factgraph.audit.package_export import _build_mapping_audit_payload
from factgraph.core.mapping.canon import MappingConflictError


class _BoundaryFault(Exception):
    """Custom, non-MappingConflictError failure raised by the injected resolver."""


class _Resolution:
    candidates: tuple[Any, ...] = ()
    chosen_map: dict[Any, Any] = {}
    decisions: tuple[Any, ...] = ()


class _FakeStore:
    """Duck-typed stand-in exposing only what the audit payload builder reads."""

    def __init__(self, error: BaseException | None) -> None:
        self._error = error
        self.schema_ir: dict[str, Any] = {
            "predicates": [
                {"pred_id": "p.mapping", "is_mapping": True},
                {"pred_id": "p.plain", "is_mapping": False},
            ]
        }

    def resolve_mapping(self, pred_id: str, *, policy_mode: str) -> Any:
        if self._error is not None:
            raise self._error
        return _Resolution()


class MappingAuditBoundaryTests(unittest.TestCase):
    """src/factgraph/audit/package_export.py: ``store.resolve_mapping`` boundary."""

    def test_resolver_fault_becomes_an_explicit_error_row(self) -> None:
        payload = _build_mapping_audit_payload(
            _FakeStore(_BoundaryFault("injected mapping resolution failure")),  # type: ignore[arg-type]
            "edb",
        )
        rows = payload["predicates"]
        self.assertEqual(len(rows), 1)
        row = rows[0]

        # Not reported as success: the row is an error row, not a resolved one.
        self.assertEqual(row["status"], "error")
        self.assertNotIn("chosen", row)
        self.assertNotIn("decisions", row)
        self.assertNotIn("candidate_count", row)
        # Preserved detail: the original exception message survives into the audit row.
        self.assertEqual(row["error"], "injected mapping resolution failure")
        self.assertEqual(row["pred_id"], "p.mapping")
        self.assertEqual(row["policy_mode"], "edb")

    def test_conflict_still_takes_the_dedicated_conflict_branch(self) -> None:
        conflict = MappingConflictError("mapping conflict detail", [{"key_tuple": ["k"]}])
        payload = _build_mapping_audit_payload(_FakeStore(conflict), "edb")  # type: ignore[arg-type]
        row = payload["predicates"][0]
        self.assertEqual(row["status"], "conflict")
        self.assertIn("mapping conflict detail", row["error"])
        self.assertEqual(row["conflicts"], [{"key_tuple": ["k"]}])

    def test_keyboard_interrupt_is_not_swallowed(self) -> None:
        with self.assertRaises(KeyboardInterrupt):
            _build_mapping_audit_payload(_FakeStore(KeyboardInterrupt()), "edb")  # type: ignore[arg-type]

    def test_resolved_row_shape_is_unchanged_on_the_happy_path(self) -> None:
        payload = _build_mapping_audit_payload(_FakeStore(None), "edb")  # type: ignore[arg-type]
        row = payload["predicates"][0]
        self.assertEqual(row["status"], "resolved")
        self.assertEqual(row["candidate_count"], 0)
        self.assertEqual(row["chosen"], [])
        self.assertEqual(row["decisions"], [])


if __name__ == "__main__":
    unittest.main()
