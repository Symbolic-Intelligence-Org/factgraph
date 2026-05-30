"""SDKStore.why_not contract tests."""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from factgraph.application.capability_helpers import CapabilityHelperError
from factgraph.application.protocol import ProtocolShapeError, WhyNotUniverseResult
from factgraph.application.why_not_runtime import WhyNotRuntimeError
from factgraph.core.rules.rule_ir import RuleCompileError, RuleRegistry
from factgraph.sdk import Inference, Entity, Field, Identity, Pred, SDKDSLError, SDKStore, SDKStoreError, vars
from factgraph.sdk.dsl import Rule
from factgraph.sdk.store import _compiled_derivation_plan_to_application


class Person(Entity):
    name: str = Identity()
    age: int = Field()
    region: str = Field()


def _build_sdk() -> SDKStore:
    return SDKStore([Person])


def _seed_person(sdk: SDKStore, *, name: str, age: int, region: str) -> str:
    ref = sdk.ref(Person, name=name)
    sdk.set(Person.age, ref, age)
    sdk.set(Person.region, ref, region)
    return ref


def _age_derivation() -> Inference:
    with vars("p", "age") as (p, age):
        return Inference(
            id="sdk.why_not.age",
            version="v1",
            where=[Person(p), p.age == age],
            head=Person.age(value=age),
        )


def _region_filtered_age_derivation() -> Inference:
    with vars("p", "age", "region") as (p, age, region):
        return Inference(
            id="sdk.why_not.age_by_region",
            version="v1",
            where=[Person(p), p.age == age, p.region == region],
            head=Person.age(value=age),
        )


def _multi_head_derivation() -> Inference:
    with vars("p", "age", "region") as (p, age, region):
        return Inference(
            id="sdk.why_not.multi_head",
            version="v1",
            where=[Person(p), p.age == age, p.region == region],
            head=[Person.age(value=age), Person.region(value=region)],
        )


def _empty_result() -> WhyNotUniverseResult:
    return WhyNotUniverseResult(
        status="completed",
        requested_universe=(),
        green=(),
        red=(),
    )


class SDKWhyNotContractTests(unittest.TestCase):
    def test_mapping_candidate_rows_return_raw_why_not_result(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=30, region="us")
        bob = _seed_person(sdk, name="bob", age=40, region="eu")
        missing = "idref_v1:Person:name:missing"

        result = sdk.why_not(
            _age_derivation(),
            [
                {"$p": missing, "$age": 30},
                {"$p": alice, "$age": 30},
                {"$p": bob, "$age": 40},
            ],
        )

        self.assertIsInstance(result, WhyNotUniverseResult)
        self.assertEqual(result.status, "completed")
        self.assertNotIsInstance(result, tuple)
        self.assertEqual(tuple(dict(row)["$p"] for row in result.green), (alice, bob))
        self.assertEqual(tuple(dict(row.binding)["$p"] for row in result.red), (missing,))

    def test_sequence_candidate_rows_are_accepted_in_head_var_order(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=30, region="us")

        result = sdk.why_not(_age_derivation(), [(alice, 30)])

        self.assertEqual(result.status, "completed")
        self.assertEqual(tuple(dict(row) for row in result.green), ({"$p": alice, "$age": 30},))
        self.assertEqual(result.red, ())

    def test_empty_candidate_universe_returns_completed_without_runtime_errors(self) -> None:
        result = _build_sdk().why_not(_age_derivation(), [])

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.requested_universe, ())
        self.assertEqual(result.green, ())
        self.assertEqual(result.red, ())

    def test_rule_is_rejected_at_sdk_surface(self) -> None:
        with vars("p") as (p,):
            rule = Rule(
                id="sdk.why_not.not_derivation",
                version="v1",
                select=[Pred("Person:exists", p)],
                where=[Person(p)],
            )

        with self.assertRaises(SDKStoreError) as ctx:
            _build_sdk().why_not(rule, [])  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.why_not.inference")
        self.assertIn("Inference", str(ctx.exception))

    def test_compiled_plan_is_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()
        compiled = sdk._compile_derivation_input(_age_derivation())
        app_plan = _compiled_derivation_plan_to_application(
            compiled[0],
            mode="native",
            engine_options=None,
        )

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.why_not(app_plan, [])  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.why_not.inference")

    def test_multi_head_derivation_is_rejected_before_request_construction(self) -> None:
        with self.assertRaises(SDKDSLError) as ctx:
            _multi_head_derivation()

        self.assertEqual(ctx.exception.path, "$.head")
        self.assertIn("multi-head", str(ctx.exception))

    def test_malformed_candidate_row_remaps_to_sdk_store_error_with_cause(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.why_not(_age_derivation(), [{"$p": "person:alice"}])

        self.assertEqual(ctx.exception.path, "$.why_not.candidates")
        self.assertIsInstance(ctx.exception.__cause__, CapabilityHelperError)

    def test_wrong_length_sequence_candidate_row_remaps_to_sdk_store_error_with_cause(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=30, region="us")

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.why_not(_age_derivation(), [(alice,)])

        self.assertEqual(ctx.exception.path, "$.why_not.candidates")
        self.assertIsInstance(ctx.exception.__cause__, CapabilityHelperError)

    def test_capability_helper_error_remaps_to_sdk_store_error_with_cause(self) -> None:
        sdk = _build_sdk()

        with patch("factgraph.sdk.shells.why_not.build_why_not_candidate_universe") as mock_builder:
            mock_builder.side_effect = CapabilityHelperError("bad candidate input")
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.why_not(_age_derivation(), [])

        self.assertEqual(ctx.exception.path, "$.why_not.candidates")
        self.assertIsInstance(ctx.exception.__cause__, CapabilityHelperError)

    def test_engine_is_passed_to_request(self) -> None:
        sdk = _build_sdk()

        with patch("factgraph.sdk.shells.why_not.check_why_not_universe", return_value=_empty_result()) as mock_runtime:
            result = sdk.why_not(_age_derivation(), [], engine="souffle")

        self.assertEqual(result.status, "completed")
        request = mock_runtime.call_args.args[0]
        self.assertEqual(request.engine, "souffle")

    def test_registry_is_resolved_and_passed_to_runtime(self) -> None:
        sdk = _build_sdk()
        derivation = _age_derivation()
        registry = RuleRegistry()
        expected = object()

        with patch.object(sdk, "_resolve_runtime_registry", return_value=expected) as mock_resolve, patch(
            "factgraph.sdk.shells.why_not.check_why_not_universe",
            return_value=_empty_result(),
        ) as mock_runtime:
            result = sdk.why_not(derivation, [], registry=registry)

        self.assertEqual(result.status, "completed")
        mock_resolve.assert_called_once_with(derivation, explicit_registry=registry)
        self.assertIs(mock_runtime.call_args.kwargs["registry"], expected)

    def test_engine_ext_conflict_raises_sdk_store_error(self) -> None:
        sdk = _build_sdk()

        with patch(
            "factgraph.sdk.shells.why_not._compiled_derivation_plan_to_application",
            side_effect=ValueError(
                "Conflicting engine_ext between explicit derivation and compiled plan"
            ),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.why_not(_age_derivation(), [])

        self.assertEqual(ctx.exception.path, "$.why_not.inference")
        self.assertIsInstance(ctx.exception.__cause__, ValueError)
        self.assertIn("engine_ext", str(ctx.exception))

    def test_dependency_rule_compile_error_raises_sdk_store_error(self) -> None:
        sdk = _build_sdk()

        with patch.object(
            sdk,
            "_resolve_runtime_registry",
            side_effect=RuleCompileError("duplicate rule registration"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.why_not(_age_derivation(), [])

        self.assertEqual(ctx.exception.path, "$.why_not.dependencies")
        self.assertIsInstance(ctx.exception.__cause__, RuleCompileError)
        self.assertIn("duplicate rule registration", str(ctx.exception))

    def test_pathless_sdk_store_error_from_dep_compile_remaps_to_dependencies_path(
        self,
    ) -> None:
        """G3 verification-round Blocker regression: see test_sdk_check.py
        sister test for full rationale."""
        sdk = _build_sdk()

        with patch.object(
            sdk,
            "_resolve_runtime_registry",
            side_effect=SDKStoreError("invalid rule input: malformed dep payload"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.why_not(_age_derivation(), [])

        self.assertEqual(ctx.exception.path, "$.why_not.dependencies")
        self.assertIsInstance(ctx.exception.__cause__, SDKStoreError)
        self.assertIn("malformed dep payload", str(ctx.exception))

    def test_request_protocol_shape_error_raises_sdk_store_error(self) -> None:
        sdk = _build_sdk()

        with patch(
            "factgraph.sdk.shells.why_not.WhyNotUniverseRequest",
            side_effect=ProtocolShapeError("engine must be one of"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.why_not(_age_derivation(), [])

        self.assertEqual(ctx.exception.path, "$.why_not.request")
        self.assertIsInstance(ctx.exception.__cause__, ProtocolShapeError)

    def test_runtime_why_not_error_raises_sdk_store_error(self) -> None:
        sdk = _build_sdk()

        with patch(
            "factgraph.sdk.shells.why_not.check_why_not_universe",
            side_effect=WhyNotRuntimeError(
                "runtime invariant failed",
                code="WHY_NOT_TEST_FAILURE",
            ),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.why_not(_age_derivation(), [])

        self.assertEqual(ctx.exception.path, "$.why_not")
        self.assertIsInstance(ctx.exception.__cause__, WhyNotRuntimeError)

    def test_why_not_result_not_exported_from_factgraph_sdk_all(self) -> None:
        import factgraph.sdk as sdk_pkg

        self.assertNotIn("WhyNotUniverseResult", sdk_pkg.__all__)
        self.assertFalse(hasattr(sdk_pkg, "WhyNotUniverseResult"))

    def test_q1_sibling_why_not_does_not_call_sdk_check_or_diagnose_at_runtime(self) -> None:
        sdk = _build_sdk()

        with patch("factgraph.sdk.shells.check.sdk_check") as mock_check, patch(
            "factgraph.sdk.shells.diagnose.sdk_diagnose"
        ) as mock_diagnose, patch(
            "factgraph.sdk.shells.why_not.check_why_not_universe",
            return_value=_empty_result(),
        ):
            sdk.why_not(_age_derivation(), [])

        mock_check.assert_not_called()
        mock_diagnose.assert_not_called()

    def test_q1_sibling_why_not_module_does_not_import_sdk_check_or_diagnose(self) -> None:
        import factgraph.sdk.shells.why_not as why_not_module

        source = inspect.getsource(why_not_module)
        self.assertNotIn("from .check", source)
        self.assertNotIn("from .diagnose", source)
        self.assertNotIn("from factgraph.sdk.check", source)
        self.assertNotIn("from factgraph.sdk.diagnose", source)
        self.assertNotIn("from factgraph.sdk.shells.check", source)
        self.assertNotIn("from factgraph.sdk.shells.diagnose", source)
        self.assertNotIn("sdk_check(", source)
        self.assertNotIn("sdk_diagnose(", source)


if __name__ == "__main__":
    unittest.main()
