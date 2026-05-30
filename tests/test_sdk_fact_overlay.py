"""SDKStore.check_fact_overlay contract tests.

Phase 1 of G2 (per archived blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.md`` §8)
ships full §5.1 / §5.3 / §5.6 / §5.8 contract coverage for
``SDKStore.check_fact_overlay(...)``. Mirrors the G1 + G4 per-method
contract test structure (Mapping/Sequence input variants, type-rejection
boundary, error-path remap, engine + registry passthrough,
Q3 Sibling discipline). Tuple-form overlay rejection and runtime
exception remap (`$.check_fact_overlay`) coverage landed during the
post-publish verification round 2026-05-08.
"""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from factgraph.application.capability_helpers import build_fact_value_override
from factgraph.application.protocol import (
    ErrorDTO,
    EvaluationOverlay,
    FactOverlayCheckResult,
    FactValueOverride,
)
from factgraph.application.protocol.schema_runtime import FieldPath
from factgraph.core.rules.rule_ir import RuleCompileError, RuleRegistry
from factgraph.sdk import (
    Inference,
    Entity,
    Field,
    Identity,
    Pred,
    Rule,
    SDKDSLError,
    SDKStore,
    SDKStoreError,
    vars,
)
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
            id="sdk.check_fact_overlay.age",
            version="v1",
            where=[Person(p), p.age == age],
            head=Person.age(value=age),
        )


def _multi_head_derivation() -> Inference:
    with vars("p", "age", "region") as (p, age, region):
        return Inference(
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

    def test_empty_overlay_returns_invalid_request_passthrough(self) -> None:
        """Empty `EvaluationOverlay` is a runtime ``invalid_request`` condition;
        the SDK passes the result through unchanged per §5.8 lock."""
        empty_overlay = EvaluationOverlay(fact_actions=(), rule_actions=())
        result = _build_sdk().check_fact_overlay(
            _age_derivation(), {"$age": 30}, empty_overlay
        )

        self.assertEqual(result.status, "invalid_request")

    def test_tuple_form_overlay_rejected_at_sdk_surface(self) -> None:
        """Per §5.1 lock, the SDK accepts only `EvaluationOverlay`; the
        application `FactOverlayCheckRequest.overlay` would otherwise tolerate
        ``tuple[FactValueOverride, ...]``, but the SDK boundary rejects it."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        override = build_fact_value_override(
            sdk._store,
            sdk._application_schema_index,
            e_ref=alice,
            field=FieldPath(entity_type="Person", field_name="age"),
            new_value=30,
        )

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, (override,))  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.overlay")
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

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.inference")
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
            sdk.check_fact_overlay(app_plan, {"$age": 30}, EvaluationOverlay())  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.inference")

    def test_multi_head_derivation_is_rejected_before_request_construction(self) -> None:
        with self.assertRaises(SDKDSLError) as ctx:
            _multi_head_derivation()

        self.assertEqual(ctx.exception.path, "$.head")
        self.assertIn("multi-head", str(ctx.exception))

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

    def test_string_overlay_rejected_at_sdk_surface_overlay_path(self) -> None:
        """Non-`EvaluationOverlay` input (string) is caught by the shared
        ``validate_evaluation_overlay`` SDK-side validator and remapped to
        ``$.check_fact_overlay.overlay``. This is a direct `SDKStoreError`
        raise (no `ProtocolShapeError` chain), distinct from the §5.8
        request-construction path."""
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, "not-an-overlay")  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.overlay")
        self.assertIn("EvaluationOverlay", str(ctx.exception))

    def test_engine_ext_conflict_raises_sdk_store_error(self) -> None:
        sdk = _build_sdk()

        with patch(
            "factgraph.sdk.shells.fact_overlay._compiled_derivation_plan_to_application",
            side_effect=ValueError(
                "Conflicting engine_ext between explicit derivation and compiled plan"
            ),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, EvaluationOverlay())

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.inference")
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
                sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, EvaluationOverlay())

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.dependencies")
        self.assertIsInstance(ctx.exception.__cause__, SDKStoreError)
        self.assertIn("malformed dep payload", str(ctx.exception))

    def test_engine_is_passed_to_request(self) -> None:
        sdk = _build_sdk()

        with patch(
            "factgraph.sdk.shells.fact_overlay.check_fact_overlay_binding",
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
            "factgraph.sdk.shells.fact_overlay.check_fact_overlay_binding",
            return_value=_empty_result(),
        ) as mock_runtime:
            sdk.check_fact_overlay(
                derivation, {"$age": 30}, EvaluationOverlay(), registry=registry
            )

        mock_resolve.assert_called_once_with(derivation, explicit_registry=registry)
        self.assertIs(mock_runtime.call_args.kwargs["registry"], expected)

    def test_fact_overlay_check_result_not_exported_from_factgraph_sdk_all(self) -> None:
        import factgraph.sdk as sdk_pkg

        self.assertNotIn("FactOverlayCheckResult", sdk_pkg.__all__)
        self.assertFalse(hasattr(sdk_pkg, "FactOverlayCheckResult"))

    def test_unexpected_runtime_exception_remaps_to_sdk_store_error_with_cause(self) -> None:
        """§5.8 base path: unexpected `check_fact_overlay_binding(...)` exceptions
        remap to `SDKStoreError(path="$.check_fact_overlay") from exc`. The runtime
        ordinarily returns `FactOverlayCheckResult` (no raise), so this is
        defensive coverage for forward-compat."""
        sdk = _build_sdk()

        with patch(
            "factgraph.sdk.shells.fact_overlay.check_fact_overlay_binding",
            side_effect=RuntimeError("simulated runtime failure"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, EvaluationOverlay())

        self.assertEqual(ctx.exception.path, "$.check_fact_overlay")
        self.assertIsInstance(ctx.exception.__cause__, RuntimeError)

    def test_q3_sibling_fact_overlay_does_not_call_other_sdk_shells_at_runtime(self) -> None:
        """§5.8 Q3 Sibling: ``sdk_fact_overlay_check`` MUST NOT call ``sdk_check`` /
        ``sdk_diagnose`` / ``sdk_why_not`` / ``sdk_proof_frame_recheck`` internally."""
        sdk = _build_sdk()

        with patch("factgraph.sdk.shells.check.sdk_check") as mock_check, patch(
            "factgraph.sdk.shells.diagnose.sdk_diagnose"
        ) as mock_diagnose, patch(
            "factgraph.sdk.shells.why_not.sdk_why_not"
        ) as mock_why_not, patch(
            "factgraph.sdk.shells.proof_frame.sdk_proof_frame_recheck"
        ) as mock_proof_frame, patch(
            "factgraph.sdk.shells.fact_overlay.check_fact_overlay_binding",
            return_value=_empty_result(),
        ):
            sdk.check_fact_overlay(_age_derivation(), {"$age": 30}, EvaluationOverlay())

        mock_check.assert_not_called()
        mock_diagnose.assert_not_called()
        mock_why_not.assert_not_called()
        mock_proof_frame.assert_not_called()

    def test_q3_sibling_fact_overlay_module_does_not_import_sibling_sdk_shells(self) -> None:
        """§5.8 Q3 Sibling static check: factgraph.sdk.shells.fact_overlay source has no sibling references."""
        import factgraph.sdk.shells.fact_overlay as fact_overlay_module

        source = inspect.getsource(fact_overlay_module)
        for forbidden in (
            "from .check",
            "from .diagnose",
            "from .why_not",
            "from .proof_frame",
            "from factgraph.sdk.shells.check",
            "from factgraph.sdk.shells.diagnose",
            "from factgraph.sdk.shells.why_not",
            "from factgraph.sdk.shells.proof_frame",
            "sdk_check(",
            "sdk_diagnose(",
            "sdk_why_not(",
            "sdk_proof_frame_recheck(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
