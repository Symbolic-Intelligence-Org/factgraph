"""Atom key parsing tests for B Phase 3."""

from __future__ import annotations

import unittest

from factpy.application.walker import AtomKeyView, WalkerFrozenError, WalkerParseError, parse_atom_key


class AtomKeyViewParseTests(unittest.TestCase):
    def test_parse_pred_key_with_colons_in_payload(self) -> None:
        key = parse_atom_key("b12.a3:Person:age")

        self.assertIsInstance(key, AtomKeyView)
        self.assertEqual(key.key, "b12.a3:Person:age")
        self.assertEqual(key.branch_index, 12)
        self.assertEqual(key.atom_index, 3)
        self.assertEqual(key.payload, "Person:age")
        self.assertEqual(key.kind, "unknown")
        self.assertEqual(key.pred_id, None)
        self.assertEqual(key.step_kind, None)
        self.assertEqual(key.underlying, "b12.a3:Person:age")

    def test_contextualized_pred_and_step_views(self) -> None:
        parsed = parse_atom_key("b0.a1:Person:exists")

        pred = parsed.as_pred()
        step = parse_atom_key("b0.a2:eq").as_step()

        self.assertEqual(pred.key, parsed.key)
        self.assertEqual(pred.branch_index, parsed.branch_index)
        self.assertEqual(pred.atom_index, parsed.atom_index)
        self.assertEqual(pred.payload, parsed.payload)
        self.assertEqual(pred.underlying, parsed.underlying)
        self.assertEqual(pred.kind, "pred")
        self.assertEqual(pred.pred_id, "Person:exists")
        self.assertEqual(pred.step_kind, None)
        self.assertEqual(step.key, "b0.a2:eq")
        self.assertEqual(step.branch_index, 0)
        self.assertEqual(step.atom_index, 2)
        self.assertEqual(step.payload, "eq")
        self.assertEqual(step.underlying, "b0.a2:eq")
        self.assertEqual(step.kind, "step")
        self.assertEqual(step.pred_id, None)
        self.assertEqual(step.step_kind, "eq")
        self.assertIsNot(pred, parsed)

    def test_constructor_rejects_invalid_public_shape(self) -> None:
        invalid_kwargs = [
            dict(branch_index=-1, atom_index=0, payload="P", kind="unknown"),
            dict(branch_index=True, atom_index=0, payload="P", kind="unknown"),
            dict(branch_index=0, atom_index=-1, payload="P", kind="unknown"),
            dict(branch_index=0, atom_index=False, payload="P", kind="unknown"),
            dict(branch_index=0, atom_index=0, payload="", kind="unknown"),
            dict(branch_index=0, atom_index=0, payload="P", kind="invalid"),
            dict(branch_index=0, atom_index=0, payload="P", kind="pred", pred_id=None),
            dict(branch_index=0, atom_index=0, payload="P", kind="step", step_kind=None),
        ]

        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(WalkerParseError):
                    AtomKeyView(key="b0.a0:P", **kwargs)  # type: ignore[arg-type]

    def test_parse_rejects_invalid_shapes(self) -> None:
        for key in (
            "",
            "b.a1:pred",
            "b0.a:pred",
            "b0.a1:",
            "x0.a1:pred",
            "b0.a-1:pred",
            "b0.a1",
            "b0.a1 pred",
            object(),
        ):
            with self.subTest(key=key):
                with self.assertRaises(WalkerParseError):
                    parse_atom_key(key)  # type: ignore[arg-type]


class AtomKeyViewContractTests(unittest.TestCase):
    def test_view_is_frozen_and_has_no_forbidden_aliases(self) -> None:
        key = parse_atom_key("b0.a0:Person:exists")

        with self.assertRaises(WalkerFrozenError):
            key.kind = "pred"  # type: ignore[misc]

        self.assertFalse(hasattr(key, "source"))
        self.assertFalse(hasattr(key, "carrier"))
        self.assertFalse(hasattr(key, "raw"))

    def test_equality_and_hash_exclude_underlying(self) -> None:
        a = AtomKeyView(
            key="b0.a0:Person:exists",
            branch_index=0,
            atom_index=0,
            payload="Person:exists",
            kind="pred",
            pred_id="Person:exists",
            step_kind=None,
            underlying="b0.a0:Person:exists",
        )
        b = AtomKeyView(
            key="b0.a0:Person:exists",
            branch_index=0,
            atom_index=0,
            payload="Person:exists",
            kind="pred",
            pred_id="Person:exists",
            step_kind=None,
            underlying="different raw key",
        )

        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_phase_3_key_types_reexport_from_application_package(self) -> None:
        from factpy.application import AtomKeyView as AppAtomKeyView
        from factpy.application import parse_atom_key as app_parse_atom_key

        self.assertIs(AppAtomKeyView, AtomKeyView)
        self.assertIs(app_parse_atom_key, parse_atom_key)


if __name__ == "__main__":
    unittest.main()
