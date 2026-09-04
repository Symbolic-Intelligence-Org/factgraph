"""Fault-injection characterization for the ``Database.__del__`` broad boundary.

``__del__`` may run during interpreter teardown, where raising would only
produce an unraisable-exception warning and could mask the real error.  The
finalizer therefore absorbs faults - but an *explicit* ``close()`` (or context
manager exit) must still propagate them, so a failed close is never silently
reported as a clean shutdown.
"""

from __future__ import annotations

import unittest

from factgraph.core.store.database import Database
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity()
    age: int = Field()


class _BoundaryFault(Exception):
    """Custom failure injected into the close path."""


def _schema_ir() -> dict:
    return compile_schema_from_classes([Person])


class DatabaseFinalizerBoundaryTests(unittest.TestCase):
    """src/factgraph/core/store/database.py: ``Database.__del__`` boundary."""

    def test_finalizer_absorbs_a_close_fault(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        calls: list[str] = []

        def _boom() -> None:
            calls.append("close")
            raise _BoundaryFault("injected close failure")

        db.close = _boom  # type: ignore[method-assign]
        try:
            # Typed outcome: the finalizer returns, it never raises out of __del__.
            self.assertIsNone(db.__del__())
            self.assertEqual(calls, ["close"])
        finally:
            del db.close  # type: ignore[attr-defined]
            db.close()

    def test_explicit_close_still_propagates_the_same_fault(self) -> None:
        db = Database.create(schema_ir=_schema_ir())

        def _boom() -> None:
            raise _BoundaryFault("injected close failure")

        db.close = _boom  # type: ignore[method-assign]
        try:
            with self.assertRaises(_BoundaryFault) as ctx:
                db.close()
            # Preserved detail: the original message reaches the explicit caller.
            self.assertEqual(str(ctx.exception), "injected close failure")
        finally:
            del db.close  # type: ignore[attr-defined]
            db.close()

    def test_finalizer_does_not_swallow_keyboard_interrupt(self) -> None:
        db = Database.create(schema_ir=_schema_ir())

        def _boom() -> None:
            raise KeyboardInterrupt

        db.close = _boom  # type: ignore[method-assign]
        try:
            with self.assertRaises(KeyboardInterrupt):
                db.__del__()
        finally:
            del db.close  # type: ignore[attr-defined]
            db.close()

    def test_finalizer_on_a_healthy_database_closes_it(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        db.__del__()
        self.assertTrue(db._closed)


if __name__ == "__main__":
    unittest.main()
