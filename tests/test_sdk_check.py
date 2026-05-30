"""SDKStore.check contract tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from factgraph.application.capability_helpers import CapabilityHelperError, OriginPackageError
from factgraph.application.protocol import CheckResult
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
            id="sdk.check.age",
            version="v1",
            where=[Person(p), p.age == age],
            head=Person.age(value=age),
        )


def _region_filtered_age_derivation() -> Inference:
    with vars("p", "age", "region") as (p, age, region):
        return Inference(
            id="sdk.check.age_by_region",
            version="v1",
            where=[Person(p), p.age == age, p.region == region],
            head=Person.age(value=age),
        )


def _multi_head_derivation() -> Inference:
    with vars("p", "age", "region") as (p, age, region):
        return Inference(
            id="sdk.check.multi_head",
            version="v1",
            where=[Person(p), p.age == age, p.region == region],
            head=[Person.age(value=age), Person.region(value=region)],
        )


class SDKCheckContractTests(unittest.TestCase):
    def test_complete_binding_passes_and_returns_raw_check_result(self) -> None:
        sdk = _build_sdk()
        person_ref = _seed_person(sdk, name="alice", age=30, region="us")

        result = sdk.check(_age_derivation(), {"$p": person_ref, "$age": 30})

        self.assertIsInstance(result, CheckResult)
        self.assertEqual(result.status, "passed")
        self.assertIsNotNone(result.evidence_envelope)
        self.assertNotIsInstance(result, tuple)

    def test_complete_binding_fails_without_evidence(self) -> None:
        sdk = _build_sdk()
        person_ref = _seed_person(sdk, name="alice", age=30, region="us")

        result = sdk.check(_age_derivation(), {"$p": person_ref, "$age": 99})

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.matched_count, 0)
        self.assertIsNone(result.evidence_envelope)

    def test_unknown_variable_binding_returns_invalid_request(self) -> None:
        sdk = _build_sdk()
        _seed_person(sdk, name="alice", age=30, region="us")

        result = sdk.check(_age_derivation(), {"$unknown": "x"})

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "UNKNOWN_VARIABLE_IN_BINDING")

    def test_non_native_body_only_binding_returns_unsupported(self) -> None:
        sdk = _build_sdk()
        _seed_person(sdk, name="alice", age=30, region="us")

        result = sdk.check(
            _region_filtered_age_derivation(),
            {"$region": "us"},
            engine="problog",
        )

        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE")

    def test_rule_is_rejected_at_sdk_surface(self) -> None:
        with vars("p") as (p,):
            rule = Rule(
                id="sdk.check.not_derivation",
                version="v1",
                select=[Pred("Person:exists", p)],
                where=[Person(p)],
            )

        with self.assertRaises(SDKStoreError) as ctx:
            _build_sdk().check(rule, {})  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.check.inference")
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
            sdk.check(app_plan, {})  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.check.inference")

    def test_binding_items_are_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check(_age_derivation(), (("$age", 30),))  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.check.binding")

    def test_binding_keys_must_be_dollar_prefixed_strings(self) -> None:
        sdk = _build_sdk()

        for binding in ({"age": 30}, {"": 30}, {1: 30}):
            with self.subTest(binding=binding):
                with self.assertRaises(SDKStoreError) as ctx:
                    sdk.check(_age_derivation(), binding)  # type: ignore[arg-type]
                self.assertEqual(ctx.exception.path, "$.check.binding")

    def test_multi_head_derivation_is_rejected_before_request_construction(self) -> None:
        with self.assertRaises(SDKDSLError) as ctx:
            _multi_head_derivation()

        self.assertEqual(ctx.exception.path, "$.head")
        self.assertIn("multi-head", str(ctx.exception))

    def test_capability_helper_error_remaps_to_sdk_store_error_with_cause(self) -> None:
        sdk = _build_sdk()

        with patch("factgraph.sdk.shells.check.build_check_request") as mock_builder:
            mock_builder.side_effect = CapabilityHelperError("bad helper input")
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check(_age_derivation(), {"$age": 30})

        self.assertEqual(ctx.exception.path, "$.check")
        self.assertIsInstance(ctx.exception.__cause__, CapabilityHelperError)

    def test_origin_package_error_remaps_to_sdk_store_error_with_cause(self) -> None:
        sdk = _build_sdk()

        with patch("factgraph.sdk.shells.check.build_check_request") as mock_builder:
            mock_builder.side_effect = OriginPackageError("sdk object leaked")
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check(_age_derivation(), {"$age": 30})

        self.assertEqual(ctx.exception.path, "$.check")
        self.assertIsInstance(ctx.exception.__cause__, OriginPackageError)

    def test_engine_is_passed_to_builder(self) -> None:
        sdk = _build_sdk()

        with patch("factgraph.sdk.shells.check.build_check_request") as mock_builder, patch(
            "factgraph.sdk.shells.check.check_derivation_binding"
        ) as mock_runtime:
            mock_builder.side_effect = RuntimeError("stop after observing engine")
            with self.assertRaises(RuntimeError):
                sdk.check(_age_derivation(), {"$age": 30}, engine="souffle")

        self.assertEqual(mock_builder.call_args.kwargs["engine"], "souffle")
        mock_runtime.assert_not_called()

    def test_registry_is_resolved_and_passed_to_runtime(self) -> None:
        sdk = _build_sdk()
        derivation = _age_derivation()
        registry = RuleRegistry()
        expected = object()

        with patch.object(sdk, "_resolve_runtime_registry", return_value=expected) as mock_resolve, patch(
            "factgraph.sdk.shells.check.check_derivation_binding"
        ) as mock_runtime:
            mock_runtime.return_value = CheckResult(
                status="failed",
                requested_binding=(("$age", 30),),
                matched_count=0,
                matched_binding=None,
                evidence_envelope=None,
            )
            result = sdk.check(derivation, {"$age": 30}, registry=registry)

        self.assertEqual(result.status, "failed")
        mock_resolve.assert_called_once_with(derivation, explicit_registry=registry)
        self.assertIs(mock_runtime.call_args.kwargs["registry"], expected)

    def test_engine_ext_conflict_raises_sdk_store_error(self) -> None:
        """B.2 audit-fix regression: ValueError from `_compiled_derivation_plan_to_application`
        (e.g., engine_ext conflict between explicit Inference and compiled plan)
        must remap to ``SDKStoreError`` per §5.3 lock, not leak as ``ValueError``.
        """
        sdk = _build_sdk()

        with patch(
            "factgraph.sdk.shells.check._compiled_derivation_plan_to_application",
            side_effect=ValueError(
                "Conflicting engine_ext between explicit derivation and compiled plan"
            ),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check(_age_derivation(), {"$age": 30})

        self.assertEqual(ctx.exception.path, "$.check.inference")
        self.assertIsInstance(ctx.exception.__cause__, ValueError)
        self.assertIn("engine_ext", str(ctx.exception))

    def test_dependency_rule_compile_error_raises_sdk_store_error(self) -> None:
        """B.1 audit-fix regression: registry dependency failures must not leak."""
        sdk = _build_sdk()

        with patch.object(
            sdk,
            "_resolve_runtime_registry",
            side_effect=RuleCompileError("duplicate rule registration"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check(_age_derivation(), {"$age": 30})

        self.assertEqual(ctx.exception.path, "$.check.dependencies")
        self.assertIsInstance(ctx.exception.__cause__, RuleCompileError)
        self.assertIn("duplicate rule registration", str(ctx.exception))

    def test_pathless_sdk_store_error_from_dep_compile_remaps_to_dependencies_path(
        self,
    ) -> None:
        """G3 verification-round Blocker regression (cross-cuts back to G1):
        ``_compile_rule_input(dep_rule)`` raises a pathless ``SDKStoreError``
        when a dependency rule has malformed authoring payload. The shared
        ``resolve_runtime_registry`` helper now catches this in addition to
        ``RuleCompileError`` so the pathless error doesn't leak past the
        SDK boundary.
        """
        sdk = _build_sdk()

        with patch.object(
            sdk,
            "_resolve_runtime_registry",
            side_effect=SDKStoreError("invalid rule input: malformed dep payload"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check(_age_derivation(), {"$age": 30})

        self.assertEqual(ctx.exception.path, "$.check.dependencies")
        self.assertIsInstance(ctx.exception.__cause__, SDKStoreError)
        self.assertIn("malformed dep payload", str(ctx.exception))

    def test_check_result_not_exported_from_factgraph_sdk_all(self) -> None:
        import factgraph.sdk as sdk_pkg

        self.assertNotIn("CheckResult", sdk_pkg.__all__)
        self.assertFalse(hasattr(sdk_pkg, "CheckResult"))


if __name__ == "__main__":
    unittest.main()
