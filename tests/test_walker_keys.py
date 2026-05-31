"""Condition key parsing tests for B Phase 3."""

from __future__ import annotations

import unittest

from factgraph.application.walker import ConditionKeyView, WalkerFrozenError, WalkerParseError, parse_condition_key


class ConditionKeyViewParseTests(unittest.TestCase):
    def test_parse_pred_key_with_colons_in_payload(self) -> None:
        key = parse_condition_key("c12.c3:Person:age")

        self.assertIsInstance(key, ConditionKeyView)
        self.assertEqual(key.key, "c12.c3:Person:age")
        self.assertEqual(key.case_index, 12)
        self.assertEqual(key.condition_index, 3)
        self.assertEqual(key.payload, "Person:age")
        self.assertEqual(key.kind, "unknown")
        self.assertEqual(key.pred_id, None)
        self.assertEqual(key.step_kind, None)
        self.assertEqual(key.underlying, "c12.c3:Person:age")

    def test_contextualized_pred_and_step_views(self) -> None:
        parsed = parse_condition_key("c0.c1:Person:exists")

        pred = parsed.as_pred()
        step = parse_condition_key("c0.c2:eq").as_step()

        self.assertEqual(pred.key, parsed.key)
        self.assertEqual(pred.case_index, parsed.case_index)
        self.assertEqual(pred.condition_index, parsed.condition_index)
        self.assertEqual(pred.payload, parsed.payload)
        self.assertEqual(pred.underlying, parsed.underlying)
        self.assertEqual(pred.kind, "pred")
        self.assertEqual(pred.pred_id, "Person:exists")
        self.assertEqual(pred.step_kind, None)
        self.assertEqual(step.key, "c0.c2:eq")
        self.assertEqual(step.case_index, 0)
        self.assertEqual(step.condition_index, 2)
        self.assertEqual(step.payload, "eq")
        self.assertEqual(step.underlying, "c0.c2:eq")
        self.assertEqual(step.kind, "step")
        self.assertEqual(step.pred_id, None)
        self.assertEqual(step.step_kind, "eq")
        self.assertIsNot(pred, parsed)

    def test_constructor_rejects_invalid_public_shape(self) -> None:
        invalid_kwargs = [
            dict(case_index=-1, condition_index=0, payload="P", kind="unknown"),
            dict(case_index=True, condition_index=0, payload="P", kind="unknown"),
            dict(case_index=0, condition_index=-1, payload="P", kind="unknown"),
            dict(case_index=0, condition_index=False, payload="P", kind="unknown"),
            dict(case_index=0, condition_index=0, payload="", kind="unknown"),
            dict(case_index=0, condition_index=0, payload="P", kind="invalid"),
            dict(case_index=0, condition_index=0, payload="P", kind="pred", pred_id=None),
            dict(case_index=0, condition_index=0, payload="P", kind="step", step_kind=None),
        ]

        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(WalkerParseError):
                    ConditionKeyView(key="c0.c0:P", **kwargs)  # type: ignore[arg-type]

    def test_parse_rejects_invalid_shapes(self) -> None:
        for key in (
            "",
            "b.c1:pred",
            "b0.a:pred",
            "c0.c1:",
            "x0.c1:pred",
            "b0.a-1:pred",
            "c0.c1",
            "c0.c1 pred",
            object(),
        ):
            with self.subTest(key=key):
                with self.assertRaises(WalkerParseError):
                    parse_condition_key(key)  # type: ignore[arg-type]


class ConditionKeyViewContractTests(unittest.TestCase):
    def test_view_is_frozen_and_has_no_forbidden_aliases(self) -> None:
        key = parse_condition_key("c0.c0:Person:exists")

        with self.assertRaises(WalkerFrozenError):
            key.kind = "pred"  # type: ignore[misc]

        self.assertFalse(hasattr(key, "source"))
        self.assertFalse(hasattr(key, "carrier"))
        self.assertFalse(hasattr(key, "raw"))

    def test_equality_and_hash_exclude_underlying(self) -> None:
        a = ConditionKeyView(
            key="c0.c0:Person:exists",
            case_index=0,
            condition_index=0,
            payload="Person:exists",
            kind="pred",
            pred_id="Person:exists",
            step_kind=None,
            underlying="c0.c0:Person:exists",
        )
        b = ConditionKeyView(
            key="c0.c0:Person:exists",
            case_index=0,
            condition_index=0,
            payload="Person:exists",
            kind="pred",
            pred_id="Person:exists",
            step_kind=None,
            underlying="different raw key",
        )

        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_phase_3_key_types_reexport_from_application_package(self) -> None:
        from factgraph.application import ConditionKeyView as AppConditionKeyView
        from factgraph.application import parse_condition_key as app_parse_condition_key

        self.assertIs(AppConditionKeyView, ConditionKeyView)
        self.assertIs(app_parse_condition_key, parse_condition_key)


if __name__ == "__main__":
    unittest.main()
