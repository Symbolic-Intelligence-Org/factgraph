"""SDKStore.check_rule_disable contract tests.

Phase 1 of G3 (per archived blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g3-rule-overlays.md`` §8)
ships full §5.1 / §5.2 / §5.4 / §5.7 / §5.8 contract coverage for
``SDKStore.check_rule_disable(...)``. Mirrors the G1 / G4 / G2
per-method contract test structure with rule-overlay specifics
(SDK ``Rule`` lowering through ``_compile_rule_input``, raw
``SupportArtifact`` from a prior Check, ``branch_index`` /
``atom_index`` action arguments mirroring the A helper).
"""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from factpy.application.capability_helpers.errors import CapabilityHelperError
from factpy.application.protocol import (
    EvaluationOverlay,
    FactValueOverride,
    ProtocolShapeError,
    RuleDisableAction,
    RuleDisableResult,
)
from factpy.core.rules.rule_ir import RuleCompileError
from factpy.core.store._support import SupportArtifact
from factpy.sdk import (
    Inference,
    Entity,
    Field,
    Identity,
    Rule,
    SDKStore,
    SDKStoreError,
    vars,
)


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


def _age_derivation() -> Inference:
    with vars("p", "age") as (p, age):
        return Inference(
            id="sdk.check_rule_disable.age",
            version="v1",
            where=[Person(p), p.age == age],
            head=Person.age(value=age),
        )


def _adult_rule() -> Rule:
    with vars("p", "age") as (p, age):
        return Rule(
            id="sdk.check_rule_disable.adult",
            version="v1",
            select=[p, age],
            where=[Person(p), p.age == age],
        )


def _capture_support(sdk: SDKStore, e_ref: str, age: int) -> SupportArtifact:
    """Run sdk.check(...) and extract the captured SupportArtifact."""
    result = sdk.check(_age_derivation(), {"$p": e_ref, "$age": age})
    payload = result.evidence_envelope.engine_payload
    assert isinstance(payload, SupportArtifact), (
        f"native engine should produce SupportArtifact, got {type(payload).__name__}"
    )
    return payload


class SDKRuleDisableContractTests(unittest.TestCase):
    def test_happy_path_returns_raw_rule_disable_result(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        result = sdk.check_rule_disable(
            _adult_rule(),
            support,
            branch_index=0,
            atom_index=0,
        )

        self.assertIsInstance(result, RuleDisableResult)

    def test_non_rule_input_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check_rule_disable(
                {"not": "rule"},  # type: ignore[arg-type]
                support,
                branch_index=0,
                atom_index=0,
            )

        self.assertEqual(ctx.exception.path, "$.check_rule_disable.rule")
        self.assertIn("Rule", str(ctx.exception))

    def test_derivation_input_rejected_at_sdk_surface(self) -> None:
        """Per §5.2 lock, only SDK ``Rule`` is accepted; ``Inference`` is
        a sibling DSL object but not a rule."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check_rule_disable(
                _age_derivation(),  # type: ignore[arg-type]
                support,
                branch_index=0,
                atom_index=0,
            )

        self.assertEqual(ctx.exception.path, "$.check_rule_disable.rule")

    def test_non_support_artifact_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check_rule_disable(
                _adult_rule(),
                "not-a-support-artifact",  # type: ignore[arg-type]
                branch_index=0,
                atom_index=0,
            )

        self.assertEqual(ctx.exception.path, "$.check_rule_disable.support")
        self.assertIn("SupportArtifact", str(ctx.exception))

    def test_non_evaluation_overlay_input_rejected_at_sdk_surface(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check_rule_disable(
                _adult_rule(),
                support,
                branch_index=0,
                atom_index=0,
                overlay="not-an-overlay",  # type: ignore[arg-type]
            )

        self.assertEqual(ctx.exception.path, "$.check_rule_disable.overlay")
        self.assertIn("EvaluationOverlay", str(ctx.exception))

    def test_non_empty_overlay_rejected_at_sdk_surface(self) -> None:
        """§5.4 lock: SDK rejects non-empty ``EvaluationOverlay`` because
        the rule-action overlay is constructed internally by the A
        helper; SDK callers pass ``None`` or empty ``EvaluationOverlay()``.
        """
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)
        non_empty_overlay = EvaluationOverlay(
            fact_actions=(
                FactValueOverride(
                    asrt_id="a1",
                    pred_id="Person:age",
                    e_ref=alice,
                    old_fact_tuple=(25,),
                    new_fact_tuple=(30,),
                ),
            )
        )

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.check_rule_disable(
                _adult_rule(),
                support,
                branch_index=0,
                atom_index=0,
                overlay=non_empty_overlay,
            )

        self.assertEqual(ctx.exception.path, "$.check_rule_disable.overlay")
        self.assertIn("rule-action overlay is constructed internally", str(ctx.exception))

    def test_empty_evaluation_overlay_accepted(self) -> None:
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        result = sdk.check_rule_disable(
            _adult_rule(),
            support,
            branch_index=0,
            atom_index=0,
            overlay=EvaluationOverlay(),
        )

        self.assertIsInstance(result, RuleDisableResult)

    def test_rule_compile_error_on_lowering_remaps_to_rule_path(self) -> None:
        """B.1 + B.2 fix pattern: ``RuleCompileError`` from rule lowering
        chain remaps to ``$.check_rule_disable.rule``."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with patch.object(
            SDKStore,
            "_compile_rule_input",
            side_effect=RuleCompileError("simulated compile failure"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check_rule_disable(
                    _adult_rule(),
                    support,
                    branch_index=0,
                    atom_index=0,
                )

        self.assertEqual(ctx.exception.path, "$.check_rule_disable.rule")
        self.assertIsInstance(ctx.exception.__cause__, RuleCompileError)

    def test_dependency_rule_compile_error_remaps_to_dependencies_path(self) -> None:
        """B.1 fix pattern: ``RuleCompileError`` from
        ``_resolve_runtime_registry`` (e.g., duplicate dependency
        registration) remaps to ``$.check_rule_disable.dependencies``."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with patch.object(
            SDKStore,
            "_resolve_runtime_registry",
            side_effect=RuleCompileError("simulated dependency cycle"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check_rule_disable(
                    _adult_rule(),
                    support,
                    branch_index=0,
                    atom_index=0,
                )

        self.assertEqual(ctx.exception.path, "$.check_rule_disable.dependencies")
        self.assertIsInstance(ctx.exception.__cause__, RuleCompileError)

    def test_pathless_sdk_store_error_from_dep_compile_remaps_to_dependencies_path(
        self,
    ) -> None:
        """Verification-round Blocker regression: a malformed dependency
        rule causes ``_compile_rule_input(dep_rule)`` (called via
        ``_register_rule_dependencies`` inside ``_resolve_runtime_registry``)
        to raise a pathless ``SDKStoreError("invalid rule input: ...")``.
        The G3 shell must catch this in addition to ``RuleCompileError``
        and remap to ``$.check_rule_disable.dependencies`` — otherwise
        the pathless error leaks past the SDK boundary.
        """
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with patch.object(
            SDKStore,
            "_resolve_runtime_registry",
            side_effect=SDKStoreError("invalid rule input: malformed dep payload"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check_rule_disable(
                    _adult_rule(),
                    support,
                    branch_index=0,
                    atom_index=0,
                )

        self.assertEqual(ctx.exception.path, "$.check_rule_disable.dependencies")
        self.assertIsInstance(ctx.exception.__cause__, SDKStoreError)
        self.assertIn("malformed dep payload", str(ctx.exception))

    def test_capability_helper_error_remaps_to_request_path(self) -> None:
        """A helper ``CapabilityHelperError`` (e.g., ``_reject_sdk_origin``
        rejecting an SDK DSL object slipped into action args) remaps to
        ``$.check_rule_disable.request``."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with patch(
            "factpy.sdk.shells.rule_disable.build_rule_disable_request",
            side_effect=CapabilityHelperError("simulated helper rejection"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check_rule_disable(
                    _adult_rule(),
                    support,
                    branch_index=0,
                    atom_index=0,
                )

        self.assertEqual(ctx.exception.path, "$.check_rule_disable.request")
        self.assertIsInstance(ctx.exception.__cause__, CapabilityHelperError)

    def test_protocol_shape_error_remaps_to_request_path(self) -> None:
        """``ProtocolShapeError`` from action / request DTO ``__post_init__``
        remaps to ``$.check_rule_disable.request``."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with patch(
            "factpy.sdk.shells.rule_disable.build_rule_disable_request",
            side_effect=ProtocolShapeError("bad request shape"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check_rule_disable(
                    _adult_rule(),
                    support,
                    branch_index=0,
                    atom_index=0,
                )

        self.assertEqual(ctx.exception.path, "$.check_rule_disable.request")
        self.assertIsInstance(ctx.exception.__cause__, ProtocolShapeError)

    def test_unexpected_runtime_exception_remaps_to_base_path(self) -> None:
        """§5.8 base-path remap: ``check_rule_disable_action(...)``
        normally returns result DTOs; the defensive base path covers
        any forward-compat unexpected raise."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with patch(
            "factpy.sdk.shells.rule_disable.check_rule_disable_action",
            side_effect=RuntimeError("simulated runtime failure"),
        ):
            with self.assertRaises(SDKStoreError) as ctx:
                sdk.check_rule_disable(
                    _adult_rule(),
                    support,
                    branch_index=0,
                    atom_index=0,
                )

        self.assertEqual(ctx.exception.path, "$.check_rule_disable")
        self.assertIsInstance(ctx.exception.__cause__, RuntimeError)

    def test_rule_disable_result_not_exported_from_factpy_sdk_all(self) -> None:
        import factpy.sdk as sdk_pkg

        self.assertNotIn("RuleDisableResult", sdk_pkg.__all__)
        self.assertFalse(hasattr(sdk_pkg, "RuleDisableResult"))
        self.assertNotIn("RuleDisableAction", sdk_pkg.__all__)
        self.assertNotIn("RuleDisableRequest", sdk_pkg.__all__)

    def test_runtime_dispatched_with_store_and_resolved_registry(self) -> None:
        """§5.8: runtime is called with positional request +
        ``store=`` + ``registry=`` kwargs from the SDK shell."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        captured = {}

        def fake_runtime(request, *, store, registry):
            captured["request"] = request
            captured["store"] = store
            captured["registry"] = registry
            return RuleDisableResult(
                status="unsupported",
                variant_rows=(),
                proof_frame=None,
                errors=(__import__("factpy.application.protocol", fromlist=["ErrorDTO"]).ErrorDTO(
                    code="STUB", message="stub", path=("stub",)
                ),),
                warnings=(),
            )

        with patch(
            "factpy.sdk.shells.rule_disable.check_rule_disable_action",
            side_effect=fake_runtime,
        ):
            sdk.check_rule_disable(
                _adult_rule(),
                support,
                branch_index=0,
                atom_index=0,
            )

        self.assertIs(captured["store"], sdk._store)
        self.assertIs(captured["request"].support_artifact, support)
        self.assertEqual(len(captured["request"].overlay.rule_actions), 1)
        action = captured["request"].overlay.rule_actions[0]
        self.assertIsInstance(action, RuleDisableAction)
        self.assertEqual(action.branch_index, 0)
        self.assertEqual(action.atom_index, 0)

    def test_sibling_rule_disable_does_not_call_other_sdk_shells_at_runtime(self) -> None:
        """§5.8 Sibling: ``sdk_rule_disable`` MUST NOT call any of the
        other 7 SDK shells at runtime."""
        sdk = _build_sdk()
        alice = _seed_person(sdk, name="alice", age=25, region="us")
        support = _capture_support(sdk, alice, 25)

        with patch("factpy.sdk.shells.check.sdk_check") as mock_check, patch(
            "factpy.sdk.shells.diagnose.sdk_diagnose"
        ) as mock_diagnose, patch(
            "factpy.sdk.shells.why_not.sdk_why_not"
        ) as mock_why_not, patch(
            "factpy.sdk.shells.fact_overlay.sdk_fact_overlay_check"
        ) as mock_fact_overlay, patch(
            "factpy.sdk.shells.proof_frame.sdk_proof_frame_recheck"
        ) as mock_proof_frame, patch(
            "factpy.sdk.shells.rule_literal_replace.sdk_rule_literal_replace"
        ) as mock_rule_literal_replace, patch(
            "factpy.sdk.shells.rule_add_condition.sdk_rule_add_condition"
        ) as mock_rule_add_condition:
            sdk.check_rule_disable(
                _adult_rule(),
                support,
                branch_index=0,
                atom_index=0,
            )

        mock_check.assert_not_called()
        mock_diagnose.assert_not_called()
        mock_why_not.assert_not_called()
        mock_fact_overlay.assert_not_called()
        mock_proof_frame.assert_not_called()
        mock_rule_literal_replace.assert_not_called()
        mock_rule_add_condition.assert_not_called()

    def test_sibling_rule_disable_module_does_not_import_sibling_sdk_shells(self) -> None:
        """§5.8 Sibling static check: factpy.sdk.shells.rule_disable
        source has no sibling SDK shell references (G1 + G4 + G2 +
        future G3 sister modules)."""
        import factpy.sdk.shells.rule_disable as rule_disable_module

        source = inspect.getsource(rule_disable_module)
        for forbidden in (
            "from .check",
            "from .diagnose",
            "from .why_not",
            "from .fact_overlay",
            "from .proof_frame",
            "from .rule_literal_replace",
            "from .rule_add_condition",
            "from factpy.sdk.shells.check",
            "from factpy.sdk.shells.diagnose",
            "from factpy.sdk.shells.why_not",
            "from factpy.sdk.shells.fact_overlay",
            "from factpy.sdk.shells.proof_frame",
            "from factpy.sdk.shells.rule_literal_replace",
            "from factpy.sdk.shells.rule_add_condition",
            "sdk_check(",
            "sdk_diagnose(",
            "sdk_why_not(",
            "sdk_fact_overlay_check(",
            "sdk_proof_frame_recheck(",
            "sdk_rule_literal_replace(",
            "sdk_rule_add_condition(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
