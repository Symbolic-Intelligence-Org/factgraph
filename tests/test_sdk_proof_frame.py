"""sdk_proof_frame_recheck contract tests.

Phase 2 of G2 (per archived blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g2-fact-overlay-proofframe-recheck.md`` §8)
ships full §5.2 / §5.4 / §5.6 / §5.8 contract coverage for
``sdk_proof_frame_recheck(...)``. Mirrors the G1 / G4 / Fact Overlay
per-method contract test structure with ProofFrame-specific narrowing
(no derivation lowering, no registry resolution, no engine arg).
"""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from factgraph.application.capability_helpers import build_fact_value_override
from factgraph.application.protocol import (
    EvaluationOverlay,
    ProofFrameRecheckResult,
    ProtocolShapeError,
)
from factgraph.application.protocol.schema_runtime import FieldPath
from factgraph.core.store._support import SupportArtifact
from factgraph.sdk.shells.check import sdk_check
from factgraph.sdk.shells.proof_frame import sdk_proof_frame_recheck
from factgraph.sdk import (
    Inference,
    Entity,
    Field,
    Identity,
    SDKStore,
    SDKStoreError,
    vars,
)


class Person(Entity):
    name: str = Identity()
    age: int = Field()
    region: str = Field()


def _build_sdk() -> SDKStore:
    return SDKStore([Person])


def _seed_person(sdk: SDKStore, *, name: str, age: int, region: str) -> str:
    ref = sdk.entities.ref(Person, name=name)
    sdk.fields.set(Person.age, ref, age)
    sdk.fields.set(Person.region, ref, region)
    return ref


def _age_derivation() -> Inference:
    with vars("p", "age") as (p, age):
        return Inference(
            id="sdk.recheck_proof_frame.age",
            version="v1",
            when=[Person(p), p.age == age],
            head=Person.age(value=age),
        )


def _capture_support(sdk: SDKStore, alice: str, age: int) -> SupportArtifact:
    """Run sdk_check(sdk, ...) and extract the captured SupportArtifact."""
    result = sdk_check(sdk, _age_derivation(), {"$p": alice, "$age": age})
    payload = result.evidence_envelope.engine_payload
    assert isinstance(payload, SupportArtifact), (
        f"native engine should produce SupportArtifact, got {type(payload).__name__}"
    )
    return payload


def _build_overlay(sdk: SDKStore, e_ref: str, new_age: int) -> EvaluationOverlay:
    override = build_fact_value_override(
        sdk._store,
        sdk._application_schema_index,
        e_ref=e_ref,
        field=FieldPath(entity_type="Person", field_name="age"),
        new_value=new_age,
    )
    return EvaluationOverlay(fact_actions=(override,))


class SDKProofFrameRecheckContractTests(unittest.TestCase):
    def test_happy_path_returns_raw_proof_frame_recheck_result(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)
        overlay = _build_overlay(sdk, alice, new_age=30)

        result = sdk_proof_frame_recheck(sdk, support, overlay)

        self.assertIsInstance(result, ProofFrameRecheckResult)

    def test_non_support_artifact_input_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk_proof_frame_recheck(sdk, "not-a-support-artifact", EvaluationOverlay())  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.recheck_proof_frame.support_artifact")
        self.assertIn("SupportArtifact", str(ctx.exception))

    def test_none_support_artifact_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk_proof_frame_recheck(sdk, None, EvaluationOverlay())  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.recheck_proof_frame.support_artifact")

    def test_non_evaluation_overlay_input_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with self.assertRaises(SDKStoreError) as ctx:
            sdk_proof_frame_recheck(sdk, support, "not-an-overlay")  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.recheck_proof_frame.overlay")
        self.assertIn("EvaluationOverlay", str(ctx.exception))

    def test_tuple_form_overlay_rejected_at_sdk_surface(self) -> None:
        """SDK accepts only EvaluationOverlay; tuple-form
        ``tuple[FactValueOverride, ...]`` (which the application request
        DTO permits) is rejected at the SDK boundary per §5.2."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)
        override = build_fact_value_override(
            sdk._store,
            sdk._application_schema_index,
            e_ref=alice,
            field=FieldPath(entity_type="Person", field_name="age"),
            new_value=30,
        )

        with self.assertRaises(SDKStoreError) as ctx:
            sdk_proof_frame_recheck(sdk, support, (override,))  # type: ignore[arg-type]

        self.assertEqual(ctx.exception.path, "$.recheck_proof_frame.overlay")

    def test_protocol_shape_error_remaps_to_sdk_store_error_with_cause(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with patch(
            "factgraph.sdk.shells.proof_frame.ProofFrameRecheckRequest",
            side_effect=ProtocolShapeError("bad request shape"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk_proof_frame_recheck(sdk, support, EvaluationOverlay())

        self.assertEqual(ctx.exception.path, "$.recheck_proof_frame.request")
        self.assertIsInstance(ctx.exception.__cause__, ProtocolShapeError)

    def test_unexpected_runtime_exception_remaps_to_sdk_store_error_with_cause(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with patch(
            "factgraph.sdk.shells.proof_frame.recheck_proof_frame",
            side_effect=RuntimeError("simulated runtime failure"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk_proof_frame_recheck(sdk, support, EvaluationOverlay())

        self.assertEqual(ctx.exception.path, "$.recheck_proof_frame")
        self.assertIsInstance(ctx.exception.__cause__, RuntimeError)

    def test_proof_frame_recheck_result_not_exported_from_factgraph_sdk_all(self) -> None:
        import factgraph.sdk as sdk_pkg

        self.assertNotIn("ProofFrameRecheckResult", sdk_pkg.__all__)
        self.assertFalse(hasattr(sdk_pkg, "ProofFrameRecheckResult"))

    def test_runtime_dispatched_with_store_only_no_registry_no_engine(self) -> None:
        """§5.8 ProofFrame Recheck has no derivation lowering / registry
        resolution / engine argument paths. Verify runtime is called with
        only ``store=`` kwarg."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        captured = {}

        def fake_runtime(request, *, store):
            captured["request"] = request
            captured["store"] = store
            return ProofFrameRecheckResult(
                status="unknown",
                binding_items=request.support_artifact.binding_items,
                atom_verdicts=(),
            )

        with patch(
            "factgraph.sdk.shells.proof_frame.recheck_proof_frame",
            side_effect=fake_runtime,
        ):
            sdk_proof_frame_recheck(sdk, support, EvaluationOverlay())

        self.assertIs(captured["store"], sdk._store)
        self.assertIs(captured["request"].support_artifact, support)

    def test_q3_q4_sibling_proof_frame_does_not_call_other_sdk_shells_at_runtime(self) -> None:
        """§5.8 Sibling: ``sdk_proof_frame_recheck`` MUST NOT call
        ``sdk_check`` / ``sdk_diagnose`` / ``sdk_why_not`` /
        ``sdk_fact_overlay_check`` internally."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with patch("factgraph.sdk.shells.check.sdk_check") as mock_check, patch(
            "factgraph.sdk.shells.diagnose.sdk_diagnose"
        ) as mock_diagnose, patch(
            "factgraph.sdk.shells.why_not.sdk_why_not"
        ) as mock_why_not, patch(
            "factgraph.sdk.shells.fact_overlay.sdk_fact_overlay_check"
        ) as mock_fact_overlay:
            sdk_proof_frame_recheck(sdk, support, EvaluationOverlay())

        mock_check.assert_not_called()
        mock_diagnose.assert_not_called()
        mock_why_not.assert_not_called()
        mock_fact_overlay.assert_not_called()

    def test_q3_q4_sibling_proof_frame_module_does_not_import_sibling_sdk_shells(self) -> None:
        """§5.8 Sibling static check: factgraph.sdk.shells.proof_frame source
        has no sibling SDK shell references."""
        import factgraph.sdk.shells.proof_frame as proof_frame_module

        source = inspect.getsource(proof_frame_module)
        for forbidden in (
            "from .check",
            "from .diagnose",
            "from .why_not",
            "from .fact_overlay",
            "from factgraph.sdk.shells.check",
            "from factgraph.sdk.shells.diagnose",
            "from factgraph.sdk.shells.why_not",
            "from factgraph.sdk.shells.fact_overlay",
            "sdk_check(",
            "sdk_diagnose(",
            "sdk_why_not(",
            "sdk_fact_overlay_check(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
