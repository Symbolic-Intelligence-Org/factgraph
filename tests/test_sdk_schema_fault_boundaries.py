"""Fault-injection characterization for the broad boundaries in factgraph.sdk.schema.

Each test injects a custom exception type at the guarded import boundary and pins
the exact typed outcome, so a later narrowing of the `except Exception` clauses
cannot silently change the contract. KeyboardInterrupt must never be swallowed.
"""

from __future__ import annotations

import builtins
import unittest
from typing import Any

from factgraph.sdk import schema as schema_mod
from factgraph.sdk.dsl.expr import LogicVar


class _BoundaryFault(Exception):
    """Custom, non-builtin failure raised at the injected import boundary."""


def _import_hook_raising(target: str, exc: BaseException):
    real_import = builtins.__import__

    def _hook(name: str, globals_: Any = None, locals_: Any = None, fromlist: Any = (), level: int = 0):
        if name == target:
            raise exc
        return real_import(name, globals_, locals_, fromlist, level)

    return _hook


class IsSdkDslValueFaultBoundaryTests(unittest.TestCase):
    def test_dsl_import_failure_yields_typed_false_not_a_dsl_claim(self) -> None:
        dsl_value = LogicVar(label="x")
        # Precondition: without the injected fault this value IS recognised as DSL.
        self.assertIs(schema_mod._is_sdk_dsl_value(dsl_value), True)
        self.assertTrue(schema_mod._looks_like_sdk_dsl_entity_call((), {"k": dsl_value}))

        real_import = builtins.__import__
        builtins.__import__ = _import_hook_raising("dsl.expr", _BoundaryFault("dsl.expr unavailable"))
        try:
            observed = schema_mod._is_sdk_dsl_value(dsl_value)
            call_shape = schema_mod._looks_like_sdk_dsl_entity_call((), {"k": dsl_value})
        finally:
            builtins.__import__ = real_import

        # Typed outcome: a plain bool False, never a truthy "is a DSL value" claim,
        # and never the raw _BoundaryFault leaking out of the detector.
        self.assertIs(observed, False)
        self.assertIsInstance(observed, bool)
        # The boundary must not report the injected failure as a successful detection.
        self.assertIs(call_shape, False)

    def test_dsl_import_keyboard_interrupt_is_not_swallowed(self) -> None:
        real_import = builtins.__import__
        builtins.__import__ = _import_hook_raising("dsl.expr", KeyboardInterrupt())
        try:
            with self.assertRaises(KeyboardInterrupt):
                schema_mod._is_sdk_dsl_value(LogicVar(label="x"))
        finally:
            builtins.__import__ = real_import

    def test_happy_path_still_resolves_dsl_values(self) -> None:
        # Unpatched: the import boundary succeeds; DSL values are True, others False.
        self.assertIs(schema_mod._is_sdk_dsl_value(LogicVar(label="x")), True)
        self.assertIs(schema_mod._is_sdk_dsl_value(object()), False)


class TypingUnionOriginFaultBoundaryTests(unittest.TestCase):
    def test_typing_import_failure_yields_none_origin(self) -> None:
        real_import = builtins.__import__
        builtins.__import__ = _import_hook_raising("typing", _BoundaryFault("typing unavailable"))
        try:
            observed = schema_mod._typing_union_origin()
        finally:
            builtins.__import__ = real_import

        # Typed outcome: None (no union origin), never a bogus sentinel object.
        self.assertIsNone(observed)

    def test_typing_import_keyboard_interrupt_is_not_swallowed(self) -> None:
        real_import = builtins.__import__
        builtins.__import__ = _import_hook_raising("typing", KeyboardInterrupt())
        try:
            with self.assertRaises(KeyboardInterrupt):
                schema_mod._typing_union_origin()
        finally:
            builtins.__import__ = real_import

    def test_happy_path_returns_typing_union(self) -> None:
        from typing import Union

        self.assertIs(schema_mod._typing_union_origin(), Union)


if __name__ == "__main__":
    unittest.main()
