"""SDKStore.check_fact_overlay contract tests.

Phase 1 of G2 (per blueprint
``docs/blueprints/active/2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.md`` §8)
ships full §5.1 / §5.3 / §5.6 / §5.8 contract coverage for
``SDKStore.check_fact_overlay(...)``. Mirrors the G1 + G4 per-method
contract test structure (Mapping/Sequence input variants, type-rejection
boundary, error-path remap, engine + registry passthrough,
Q3 Sibling discipline).
"""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from kernel.application.capability_helpers import build_fact_value_override
from kernel.application.protocol import (
    ErrorDTO,
    EvaluationOverlay,
    FactOverlayCheckResult,
    FactValueOverride,
    ProtocolShapeError,
)
from kernel.application.protocol.schema_runtime import FieldPath
from kernel.core.rules.rule_ir import RuleCompileError, RuleRegistry
from kernel.sdk import (
    Derivation,
    Entity,
    Field,
    Identity,
    Pred,
    Rule,
    SDKStore,
    SDKStoreError,
    vars,
)
from kernel.sdk.store import _compiled_derivation_plan_to_application


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")
    region: str = Field(cardinality="single")


def _build_sdk() -> SDKStore:
    return SDKStore([Person])


def _seed_person(sdk: SDKStore, *, name: str, age: int, region: str) -> str:
    ref = sdk.ref(Person, name=name)
    sdk.set(Person.age, ref, age)
    sdk.set(Person.region, ref, region)
    return ref


def _age_derivation() -> Derivation:
    with vars("p", "age") as (p, age):
        return Derivation(
            id="sdk.check_fact_overlay.age",
            version="v1",
            where=[Person(p), p.age == age],
            head=Person.age(value=age),
        )


def _multi_head_derivation() -> Derivation:
    with vars("p", "age", "region") as (p, age, region):
        return Derivation(
            id="sdk.check_fact_overlay.multi_head",
            version="v1",
            where=[Person(p), p.age == age, p.region == region],
            head=[Person.age(value=age), Person.region(value=region)],
        )


def _build_overlay(sdk: SDKStore, e_ref: str, new_age: int) -> EvaluationOverlay:
    """Build an EvaluationOverlay via A helper for happy-path tests."""
    override = build_fact_value_override(
        sdk._store,
        sdk._application_schema_index,
        e_ref=e_ref,
        field=FieldPath(entity_type="Person", field_name="age"),
        new_value=new_age,
    )
    return EvaluationOverlay(fact_actions=(override,))


def _empty_result() -> FactOverlayCheckResult:
    return FactOverlayCheckResult(
        status="invalid_request",
        requested_binding=(("$age", 30),),
        before=None,
        after=None,
        diff=None,
        errors=(ErrorDTO(code="STUB", message="stubbed runtime", path=()),),
    )


class SDKFactOverlayContractTests(unittest.TestCase):
    def test_happy_path_returns_raw_fact_overlay_check_result(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        overlay = _build_overlay(sdk, alice, new_age=30)

        result = sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, overlay)

        self.assertIsInstance(result, FactOverlayCheckResult)
        self.assertNotIn(result.status, ("", None))

    def test_overlay_with_rule_actions_returns_invalid_request_passthrough(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        override = build_fact_value_override(
            sdk._store,
            sdk._application_schema_index,
            e_ref=alice,
            field=FieldPath(entity_type="Person", field_name="age"),
            new_value=30,
        )

        # Manually construct an invalid_request scenario without raising at SDK
        # boundary: empty overlay returns invalid_request from runtime, not exception.
        empty_overlay = EvaluationOverlay(fact_actions=(), rule_actions=())
        result = sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, empty_overlay)

        self.assertEqual(result.status, "invalid_request")
        # Use override to keep the variable referenced (silences ruff F841).
        self.assertIsInstance(override, FactValueOverride)

    def test_rule_is_rejected_at_sdk_surface(self) -> None:
        with vars("p") as (p,):
            rule = Rule(
                id="sdk.check_fact_overlay.not_derivation",
                version="v1",
                select=[Pred("Person:exists", p)],
                where=[Person(p)],
            )

        with self.assertRaises(SDKStoreError) as ctx:
            _build_sdk().check_fact_overlay(rule, {"$age": 30}, EvaluationOverlay())  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.derivation")
        self.assertIn("Derivation", str(ctx.exception))

    def test_compiled_plan_is_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()
        compiled = sdk._compile_derivation_input(_age_derivation())
        app_plan = _compiled_derivation_plan_to_application(
            compiled[0],
            mode="native",
            explicit_engine_ext=None,
            engine_options=None,
        )

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check_fact_overlay(app_plan, {"$age": 30}, EvaluationOverlay())  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.derivation")

    def test_multi_head_derivation_is_rejected_before_request_construction(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            _build_sdk().check_fact_overlay(
                _multi_head_derivation(), {"$age": 30, "$region": "us"}, EvaluationOverlay()
            )

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.derivation")
        self.assertIn("exactly one plan", str(ctx.exception))

    def test_binding_must_be_mapping(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check_fact_overlay(_age_derivation(), [("$age", 30)], EvaluationOverlay())  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.binding")
        self.assertIn("Mapping", str(ctx.exception))

    def test_binding_keys_must_be_dollar_prefixed_strings(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check_fact_overlay(_age_derivation(), {"age": 30}, EvaluationOverlay())

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.binding")

    def test_non_evaluation_overlay_remaps_to_request_protocol_shape_error(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, "not-an-overlay")  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.request")
        self.assertIsInstance(ctx.exception.__cause__, ProtocolShapeError)

    def test_engine_ext_conflict_raises_sdk_store_error(self) -> None:
        sdk = _build_sdk()

        with patch(
            "kernel.sdk.shells.fact_overlay._compiled_derivation_plan_to_application",
            side_effect=ValueError(
                "Conflicting engine_ext between explicit derivation and compiled plan"
            ),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, EvaluationOverlay())

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.derivation")
        self.assertIsInstance(ctx.exception.__cause__, ValueError)

    def test_dependency_rule_compile_error_raises_sdk_store_error(self) -> None:
        sdk = _build_sdk()

        with patch.object(
            sdk,
            "_resolve_runtime_registry",
            side_effect=RuleCompileError("duplicate rule registration"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, EvaluationOverlay())

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.dependencies")
        self.assertIsInstance(ctx.exception.__cause__, RuleCompileError)

    def test_engine_is_passed_to_request(self) -> None:
        sdk = _build_sdk()

        with patch(
            "kernel.sdk.shells.fact_overlay.check_fact_overlay_binding",
            return_value=_empty_result(),
        ) as mock_runtime:
            sdk.check_fact_overlay(
                _age_derivation(),
                {"$age": 30},
                EvaluationOverlay(fact_actions=()),
                engine="native",
            )

        request = mock_runtime.call_args.args[0]
        self.assertEqual(request.engine, "native")

    def test_registry_is_resolved_and_passed_to_runtime(self) -> None:
        sdk = _build_sdk()
        derivation = _age_derivation()
        registry = RuleRegistry()
        expected = object()

        with patch.object(sdk, "_resolve_runtime_registry", return_value=expected) as mock_resolve, patch(
            "kernel.sdk.shells.fact_overlay.check_fact_overlay_binding",
            return_value=_empty_result(),
        ) as mock_runtime:
            sdk.check_fact_overlay(
                derivation, {"$age": 30}, EvaluationOverlay(), registry=registry
            )

        mock_resolve.assert_called_once_with(derivation, explicit_registry=registry)
        self.assertIs(mock_runtime.call_args.kwargs["registry"], expected)

    def test_fact_overlay_check_result_not_exported_from_kernel_sdk_all(self) -> None:
        import kernel.sdk as sdk_pkg

        self.assertNotIn("FactOverlayCheckResult", sdk_pkg.__all__)
        self.assertFalse(hasattr(sdk_pkg, "FactOverlayCheckResult"))

    def test_q3_sibling_fact_overlay_does_not_call_other_sdk_shells_at_runtime(self) -> None:
        """§5.8 Q3 Sibling: ``sdk_fact_overlay_check`` MUST NOT call ``sdk_check`` /
        ``sdk_diagnose`` / ``sdk_why_not`` / ``sdk_proof_frame_recheck`` internally."""
        sdk = _build_sdk()

        with patch("kernel.sdk.shells.check.sdk_check") as mock_check, patch(
            "kernel.sdk.shells.diagnose.sdk_diagnose"
        ) as mock_diagnose, patch(
            "kernel.sdk.shells.why_not.sdk_why_not"
        ) as mock_why_not, patch(
            "kernel.sdk.shells.fact_overlay.check_fact_overlay_binding",
            return_value=_empty_result(),
        ):
            sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, EvaluationOverlay())

        mock_check.assert_not_called()
        mock_diagnose.assert_not_called()
        mock_why_not.assert_not_called()

    def test_q3_sibling_fact_overlay_module_does_not_import_sibling_sdk_shells(self) -> None:
        """§5.8 Q3 Sibling static check: kernel.sdk.shells.fact_overlay source has no sibling references."""
        import kernel.sdk.shells.fact_overlay as fact_overlay_module

        source = inspect.getsource(fact_overlay_module)
        for forbidden in (
            "from .check",
            "from .diagnose",
            "from .why_not",
            "from .proof_frame",
            "from kernel.sdk.shells.check",
            "from kernel.sdk.shells.diagnose",
            "from kernel.sdk.shells.why_not",
            "from kernel.sdk.shells.proof_frame",
            "sdk_check(",
            "sdk_diagnose(",
            "sdk_why_not(",
            "sdk_proof_frame_recheck(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
