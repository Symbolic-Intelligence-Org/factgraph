"""Tests for Check capability helper builders."""

from __future__ import annotations

import unittest

from factgraph.application import (
    CapabilityHelperError,
    OriginPackageError,
    build_check_request,
)
from factgraph.application.protocol import (
    CheckRequest,
    CompiledDerivationPlan,
    CompiledHeadCall,
    ProtocolShapeError,
)
from factgraph.core.store._support import normalize_binding_items
from factgraph.sdk import Pred, Rule, vars as sdk_vars


def _plan(*, heads: tuple[CompiledHeadCall, ...] | None = None) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="helper.check",
        version="1.0",
        body_ir=[("pred", "person:age", ["$p", "$age"])],
        heads=heads
        if heads is not None
        else (CompiledHeadCall(target_pred_id="person:eligible", head_var_names=("$p",)),),
    )


def _sdk_rule() -> Rule:
    with sdk_vars("p", "age") as (p, age):
        return Rule(
            id="helper.sdk_rule",
            version="1.0",
            select=[Pred("person:eligible", p)],
            where=[Pred("person:age", p, age)],
        )


def _plan_with_sdk_rule_in_body_ir() -> CompiledDerivationPlan:
    plan = _plan()
    return CompiledDerivationPlan(
        derivation_id=plan.derivation_id,
        version=plan.version,
        body_ir=[*plan.body_ir, _sdk_rule()],
        heads=plan.heads,
    )


class BuildCheckRequestTests(unittest.TestCase):
    def test_builds_check_request_from_mapping_binding(self) -> None:
        plan = _plan()

        request = build_check_request(plan, {"$age": 30, "$p": "person-1"})

        self.assertIsInstance(request, CheckRequest)
        self.assertIs(request.plan, plan)
        self.assertEqual(request.binding, (("$age", 30), ("$p", "person-1")))
        self.assertEqual(request.engine, "native")

    def test_builds_check_request_from_binding_items(self) -> None:
        binding = normalize_binding_items((("$p", "person-1"), ("$age", 30)))

        request = build_check_request(_plan(), binding, engine="souffle")

        self.assertEqual(request.binding, binding)
        self.assertEqual(request.engine, "souffle")

    def test_empty_binding_and_none_values_are_allowed(self) -> None:
        empty_request = build_check_request(_plan(), {})
        none_request = build_check_request(_plan(), {"$p": None})

        self.assertEqual(empty_request.binding, ())
        self.assertEqual(none_request.binding, (("$p", None),))

    def test_mapping_keys_must_be_non_empty_strings(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "binding keys"):
            build_check_request(_plan(), {"": "person-1"})
        with self.assertRaisesRegex(CapabilityHelperError, "binding keys"):
            build_check_request(_plan(), {1: "person-1"})  # type: ignore[dict-item]

    def test_binding_items_must_be_sorted(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "sorted"):
            build_check_request(_plan(), (("$p", "person-1"), ("$age", 30)))

    def test_binding_items_reject_duplicate_keys(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "duplicate"):
            build_check_request(_plan(), (("$p", "person-1"), ("$p", "person-2")))

    def test_binding_items_reject_malformed_rows(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "tuple"):
            build_check_request(_plan(), (("$p", "person-1", "extra"),))  # type: ignore[arg-type]

    def test_non_binding_container_rejected_by_helper(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "Mapping"):
            build_check_request(_plan(), [("$p", "person-1")])  # type: ignore[arg-type]

    def test_invalid_engine_delegates_to_protocol_validation(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            build_check_request(_plan(), {"$p": "person-1"}, engine="lambda")

    def test_multi_head_plan_delegates_to_protocol_validation(self) -> None:
        plan = _plan(
            heads=(
                CompiledHeadCall(target_pred_id="person:a", head_var_names=("$p",)),
                CompiledHeadCall(target_pred_id="person:b", head_var_names=("$p",)),
            )
        )
        with self.assertRaises(ProtocolShapeError):
            build_check_request(plan, {"$p": "person-1"})

    def test_non_plan_rejected_by_helper(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "CompiledDerivationPlan"):
            build_check_request(object(), {})  # type: ignore[arg-type]

    def test_sdk_rule_as_plan_raises_origin_package_error(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_check_request(_sdk_rule(), {})  # type: ignore[arg-type]

    def test_sdk_object_nested_in_plan_body_ir_raises_origin_package_error(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_check_request(_plan_with_sdk_rule_in_body_ir(), {"$p": "person-1"})

    def test_sdk_object_in_binding_value_raises_origin_package_error(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_check_request(_plan(), {"$rule": _sdk_rule()})

    def test_sdk_object_in_binding_key_raises_origin_package_error(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_check_request(_plan(), ((_sdk_rule(), "value"),))  # type: ignore[arg-type]

    def test_recursive_binding_value_raises_helper_error(self) -> None:
        recursive: dict[str, object] = {}
        recursive["self"] = recursive

        with self.assertRaisesRegex(CapabilityHelperError, "binding value is recursive"):
            build_check_request(_plan(), {"$payload": recursive})

    def test_phase_1_exports_from_application_and_helper_package(self) -> None:
        from factgraph import application
        from factgraph.application import capability_helpers

        self.assertIs(application.build_check_request, build_check_request)
        self.assertIs(capability_helpers.build_check_request, build_check_request)


if __name__ == "__main__":
    unittest.main()
