"""Red + guard baseline tests for Track 3 / B SemanticsProfile scaffolding."""

from __future__ import annotations

import importlib
import unittest
from dataclasses import FrozenInstanceError, fields, is_dataclass
from pathlib import Path

from kernel.sdk import Derivation, Pred
from kernel.sdk.schema import Entity, Field, Identity
from kernel.sdk.store import SDKStore, SDKStoreError
from service.runtime_v1 import (
    close_runtime_session,
    evaluate_runtime_derivation,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")


def _semantics_module():
    return importlib.import_module("kernel.core.semantics.profile")


def _profile_class():
    return getattr(_semantics_module(), "SemanticsProfile")


def _inspect_func():
    return getattr(_semantics_module(), "inspect_semantics_profile")


def _runtime_derivation_payload() -> dict[str, object]:
    return {
        "derivation_id": "drv.b.runtime_user_tag",
        "version": "v1",
        "target": "user:tag",
        "head_vars": ["$u", "$tag"],
        "where": [["pred", "user:tag_seed", ["$u", "$tag"]]],
    }


def _minimal_profile(**overrides: object):
    SemanticsProfile = _profile_class()
    kwargs: dict[str, object] = {
        "name": "profile.b.problog",
        "engine": "problog",
        "version": "1.0",
    }
    kwargs.update(overrides)
    return SemanticsProfile(**kwargs)


class SemanticsProfileShapeTests(unittest.TestCase):
    def test_semantics_profile_importable_from_core_semantics(self) -> None:
        SemanticsProfile = _profile_class()

        self.assertEqual(SemanticsProfile.__module__, "kernel.core.semantics.profile")

    def test_core_semantics_package_exports_profile_and_inspector(self) -> None:
        package = importlib.import_module("kernel.core.semantics")

        self.assertIs(getattr(package, "SemanticsProfile"), _profile_class())
        self.assertIs(getattr(package, "inspect_semantics_profile"), _inspect_func())

    def test_semantics_profile_is_frozen_dataclass(self) -> None:
        profile = _minimal_profile()

        self.assertTrue(is_dataclass(profile))
        self.assertIn("rule_projection", {field.name for field in fields(profile)})
        with self.assertRaises(FrozenInstanceError):
            profile.name = "changed"  # type: ignore[misc]

    def test_semantics_profile_defaults_are_empty_and_noop(self) -> None:
        profile = _minimal_profile()

        self.assertEqual(profile.engine_options, {})
        self.assertEqual(profile.uncertainty_projection, {})
        self.assertEqual(profile.temporal_projection, {"mode": "none"})
        self.assertEqual(profile.rule_projection, {})
        self.assertEqual(profile.certainty_projection, {})
        self.assertEqual(profile.output_readback, {})
        self.assertEqual(profile.fallback, "reject_unconfigured")


class SemanticsProfileValidationTests(unittest.TestCase):
    def test_rejects_unknown_version(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _minimal_profile(version="2.0")

        self.assertIn("version", str(ctx.exception))

    def test_rejects_unknown_engine(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _minimal_profile(engine="unknown")

        self.assertIn("engine", str(ctx.exception))

    def test_rejects_unknown_fallback(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _minimal_profile(fallback="silently_guess")

        self.assertIn("fallback", str(ctx.exception))

    def test_rejects_rule_projection_bucket_that_is_not_list(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _minimal_profile(rule_projection={"problog": {"target": "branch:0"}})

        self.assertIn("rule_projection.problog", str(ctx.exception))

    def test_rejects_rule_projection_missing_target(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _minimal_profile(rule_projection={"problog": [{"kind": "branch_probability", "value": 0.9}]})

        self.assertIn("target", str(ctx.exception))

    def test_rejects_rule_projection_missing_kind(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _minimal_profile(rule_projection={"problog": [{"target": "branch:0", "value": 0.9}]})

        self.assertIn("kind", str(ctx.exception))

    def test_accepts_engine_specific_rule_projection_kind_without_interpreting(self) -> None:
        profile = _minimal_profile(
            rule_projection={
                "custom_engine": [
                    {"target": "custom:anything", "kind": "future_adapter_kind", "value": {"x": 1}}
                ]
            }
        )

        self.assertEqual(profile.rule_projection["custom_engine"][0]["kind"], "future_adapter_kind")

    def test_rejects_unknown_uncertainty_projection_policy(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _minimal_profile(uncertainty_projection={"probabilistic": {"policy": "typo_policy"}})

        self.assertIn("uncertainty_projection", str(ctx.exception))

    def test_rejects_temporal_projection_mode_other_than_none(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _minimal_profile(temporal_projection={"mode": "valid_time_boundaries"})

        self.assertIn("Track 3 / D", str(ctx.exception))


class SemanticsProfileInspectionTests(unittest.TestCase):
    def test_inspect_profile_returns_json_like_summary(self) -> None:
        profile = _minimal_profile(
            engine_options={"timesteps": 3},
            rule_projection={"problog": [{"target": "branch:0", "kind": "branch_probability", "value": 0.9}]},
            uncertainty_projection={"probabilistic": {"policy": "identity_probability"}},
        )

        inspected = _inspect_func()(profile)

        self.assertEqual(inspected["engine"], "problog")
        self.assertEqual(inspected["profile"], "profile.b.problog")
        self.assertEqual(inspected["version"], "1.0")
        self.assertEqual(inspected["fallback"], "reject_unconfigured")
        self.assertEqual(
            inspected["uses"],
            {
                "engine_options": True,
                "uncertainty_projection": True,
                "temporal_projection": False,
                "rule_projection": True,
                "certainty_projection": False,
                "output_readback": False,
            },
        )
        self.assertEqual(inspected["warnings"], [])

    def test_inspect_profile_is_pure(self) -> None:
        profile = _minimal_profile(rule_projection={"problog": [{"target": "branch:0", "kind": "x"}]})
        before = profile.rule_projection

        _inspect_func()(profile)

        self.assertIs(profile.rule_projection, before)
        self.assertEqual(profile.rule_projection, before)


class PublicIntegrationRejectionTests(unittest.TestCase):
    def test_kernel_sdk_does_not_export_semantics_profile(self) -> None:
        sdk = importlib.import_module("kernel.sdk")

        self.assertNotIn("SemanticsProfile", sdk.__all__)
        self.assertFalse(hasattr(sdk, "SemanticsProfile"))

    def test_sdk_evaluate_rejects_semantics_keyword(self) -> None:
        sdk = SDKStore([User])
        derivation = Derivation(
            id="drv.b.user_tag",
            version="v1",
            where=[Pred("user:tag_seed", "$u", "$tag")],
            target="user:tag",
            head_vars=["$u", "$tag"],
        )

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.evaluate(derivation, semantics={"name": "profile.b"})

        self.assertIn("semantics", str(ctx.exception))

    def test_sdk_evaluate_rejects_semantics_profile_keyword(self) -> None:
        sdk = SDKStore([User])
        derivation = Derivation(
            id="drv.b.user_tag",
            version="v1",
            where=[Pred("user:tag_seed", "$u", "$tag")],
            target="user:tag",
            head_vars=["$u", "$tag"],
        )

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.evaluate(derivation, semantics_profile={"name": "profile.b"})

        self.assertIn("semantics_profile", str(ctx.exception))

    def test_service_rejects_top_level_semantics_keys(self) -> None:
        reset_runtime_sessions_for_tests()
        sdk = SDKStore([User])
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"], open_resp)
        session_id = str(open_resp["session"]["session_id"])
        try:
            for key in ("semantics", "semantics_profile"):
                resp = evaluate_runtime_derivation(
                    session_id,
                    {"engine": "native", key: {"name": "x"}, "derivation": _runtime_derivation_payload()},
                )

                self.assertFalse(resp["ok"], resp)
                self.assertEqual(resp["errors"][0]["path"], f"$.{key}")
                self.assertIn("Track 3 / E", resp["errors"][0]["details"]["message"])
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_service_rejects_derivation_level_semantics_keys(self) -> None:
        reset_runtime_sessions_for_tests()
        sdk = SDKStore([User])
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"], open_resp)
        session_id = str(open_resp["session"]["session_id"])
        try:
            for key in ("semantics", "semantics_profile"):
                derivation = dict(_runtime_derivation_payload())
                derivation[key] = {"name": "x"}
                resp = evaluate_runtime_derivation(
                    session_id,
                    {"engine": "native", "derivation": derivation},
                )

                self.assertFalse(resp["ok"], resp)
                self.assertEqual(resp["errors"][0]["path"], f"$.derivation.{key}")
                self.assertIn("Track 3 / E", resp["errors"][0]["details"]["message"])
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_application_protocol_has_no_semantics_profile_field(self) -> None:
        from kernel.application.protocol.derivation import DerivationEvaluateRequest

        field_names = {field.name for field in fields(DerivationEvaluateRequest)}
        self.assertNotIn("semantics", field_names)
        self.assertNotIn("semantics_profile", field_names)


class BridgeGuardTests(unittest.TestCase):
    def test_adapters_do_not_import_semantics_profile_in_b(self) -> None:
        root = Path(__file__).resolve().parents[1] / "adapters"
        violations = [
            str(path.relative_to(root))
            for path in root.rglob("*.py")
            if "SemanticsProfile" in path.read_text()
        ]

        self.assertEqual([], violations)

    def test_internal_problog_legacy_body_confidences_bridge_survives(self) -> None:
        from kernel.adapters.problog.rule_ext import ProbLogRuleExt, resolve_problog_engine_ext

        resolved = resolve_problog_engine_ext(
            where=[[("pred", "user:tag_seed", ["$u", "$tag"])]],
            engine_ext=None,
            legacy_body_confidences=[0.7],
        )

        self.assertIsInstance(resolved, ProbLogRuleExt)
        self.assertEqual(resolved.branch_probabilities, (0.7,))

    def test_pyreason_rule_ext_internal_bridge_survives(self) -> None:
        from kernel.adapters.pyreason.rule_ext import PyReasonRuleExt

        ext = PyReasonRuleExt(
            timestep_delay=1,
            body_predicate_bounds={"user:tag_seed": (0.5, 1.0)},
            head_bound=(0.8, 0.9),
        )

        self.assertEqual(ext.timestep_delay, 1)
        self.assertEqual(ext.body_predicate_bounds["user:tag_seed"], (0.5, 1.0))
        self.assertEqual(tuple(ext.head_bound or ()), (0.8, 0.9))


if __name__ == "__main__":
    unittest.main()
