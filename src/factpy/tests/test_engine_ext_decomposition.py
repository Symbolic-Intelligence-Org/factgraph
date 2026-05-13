"""Red-baseline tests for Track 3 / A3 engine_ext decomposition."""

from __future__ import annotations

import unittest
from dataclasses import dataclass, fields
from pathlib import Path

from factpy.authoring.derivation_compile import (
    AuthoringDerivationCompileError,
    compile_authoring_derivation_v1,
)
from factpy.core.store.types import EngineExtBase
from factpy.sdk import Branch, Inference, Pred, Rule
from factpy.sdk.schema import Entity, Field, Identity
from factpy.sdk.store import SDKStore
from factpy.service.runtime_v1 import (
    close_runtime_session,
    evaluate_runtime_derivation,
    open_runtime_session,
    reset_runtime_sessions_for_tests,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")


@dataclass(frozen=True)
class _TestEngineExt(EngineExtBase):
    label: str = "test"


def _authoring_derivation_payload() -> dict[str, object]:
    return {
        "derivation_id": "drv.a3.user_tag",
        "version": "v1",
        "target": "user:tag",
        "head_vars": ["$u", "$tag"],
        "where": [("pred", "user:tag_seed", ["$u", "$tag"])],
    }


def _runtime_derivation_payload() -> dict[str, object]:
    return {
        "derivation_id": "drv.a3.runtime_user_tag",
        "version": "v1",
        "target": "user:tag",
        "head_vars": ["$u", "$tag"],
        "where": [["pred", "user:tag_seed", ["$u", "$tag"]]],
    }


class SDKEngineExtSurfaceTests(unittest.TestCase):
    def test_rule_dataclass_has_no_public_engine_ext_field(self) -> None:
        self.assertNotIn("engine_ext", {field.name for field in fields(Rule)})

    def test_derivation_dataclass_has_no_public_engine_ext_field(self) -> None:
        self.assertNotIn("engine_ext", {field.name for field in fields(Inference)})

    def test_rule_constructor_rejects_engine_ext_keyword(self) -> None:
        with self.assertRaises(TypeError):
            Rule(
                id="rule.a3.user_tag",
                version="v1",
                select=[Pred("user:tag", "$u", "$tag")],
                where=[Pred("user:tag_seed", "$u", "$tag")],
                engine_ext=_TestEngineExt(),
            )

    def test_derivation_constructor_rejects_engine_ext_keyword(self) -> None:
        with self.assertRaises(TypeError):
            Inference(
                id="drv.a3.user_tag",
                version="v1",
                where=[Pred("user:tag_seed", "$u", "$tag")],
                target="user:tag",
                head_vars=["$u", "$tag"],
                engine_ext=_TestEngineExt(),
            )

    def test_authoring_payload_emits_no_engine_ext(self) -> None:
        derivation = Inference(
            id="drv.a3.user_tag",
            version="v1",
            where=[Branch([Pred("user:tag_seed", "$u", "$tag")])],
            target="user:tag",
            head_vars=["$u", "$tag"],
        )

        self.assertNotIn("engine_ext", derivation.to_authoring_payload())

    def test_sdk_evaluate_and_shells_do_not_read_object_engine_ext(self) -> None:
        root = Path(__file__).resolve().parents[1]
        files = [
            root / "sdk" / "store.py",
            root / "sdk" / "shells" / "check.py",
            root / "sdk" / "shells" / "diagnose.py",
            root / "sdk" / "shells" / "fact_overlay.py",
            root / "sdk" / "shells" / "why_not.py",
        ]

        needle = 'getattr(derivation, "engine_ext"'
        violations = [str(path.relative_to(root)) for path in files if needle in path.read_text()]
        self.assertEqual([], violations)


class AuthoringEngineExtTests(unittest.TestCase):
    def test_authoring_engine_ext_key_is_rejected(self) -> None:
        payload = dict(_authoring_derivation_payload())
        payload["engine_ext"] = {"kind": "problog", "branch_probabilities": [0.9]}

        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(payload)

        self.assertEqual(ctx.exception.path, "$.engine_ext")
        self.assertIn("SemanticsProfile", str(ctx.exception))


class ServiceEngineExtTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def _open_session(self) -> str:
        sdk = SDKStore([User])
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"], open_resp)
        return str(open_resp["session"]["session_id"])

    def test_service_rejects_top_level_engine_ext(self) -> None:
        session_id = self._open_session()
        try:
            resp = evaluate_runtime_derivation(
                session_id,
                {
                    "engine": "native",
                    "engine_ext": {"kind": "problog"},
                    "inference": _runtime_derivation_payload(),
                },
            )

            self.assertFalse(resp["ok"], resp)
            self.assertEqual(resp["errors"][0]["path"], "$.engine_ext")
            self.assertIn("SemanticsProfile", resp["errors"][0]["details"]["message"])
        finally:
            close_runtime_session(session_id)

    def test_service_rejects_derivation_engine_ext(self) -> None:
        session_id = self._open_session()
        derivation = dict(_runtime_derivation_payload())
        derivation["engine_ext"] = {"kind": "problog"}
        try:
            resp = evaluate_runtime_derivation(
                session_id,
                {
                    "engine": "native",
                    "inference": derivation,
                },
            )

            self.assertFalse(resp["ok"], resp)
            self.assertEqual(resp["errors"][0]["path"], "$.inference.engine_ext")
            self.assertIn("SemanticsProfile", resp["errors"][0]["details"]["message"])
        finally:
            close_runtime_session(session_id)


class InternalEngineExtBridgeTests(unittest.TestCase):
    def test_internal_protocol_keeps_engine_ext_bridge(self) -> None:
        from factpy.application.protocol.derivation import CompiledDerivationPlan, CompiledHeadCall

        plan = CompiledDerivationPlan(
            derivation_id="drv.a3.internal",
            version="v1",
            body_ir=[("pred", "user:tag_seed", ["$u", "$tag"])],
            heads=(CompiledHeadCall(target_pred_id="user:tag", head_var_names=("$u", "$tag")),),
            engine_ext=_TestEngineExt(),
        )

        self.assertIsInstance(plan.engine_ext, _TestEngineExt)

    def test_adapter_ext_types_remain_internal_targets(self) -> None:
        from factpy.adapters.problog.rule_ext import ProbLogRuleExt
        from factpy.adapters.pyreason.rule_ext import PyReasonRuleExt

        problog_ext = ProbLogRuleExt(branch_probabilities=(0.9,))
        pyreason_ext = PyReasonRuleExt(
            timestep_delay=1,
            body_predicate_bounds={"user:tag_seed": (0.5, 1.0)},
            head_bound=(0.8, 0.9),
        )

        self.assertEqual(problog_ext.branch_probabilities, (0.9,))
        self.assertEqual(pyreason_ext.timestep_delay, 1)
        self.assertEqual(pyreason_ext.body_predicate_bounds["user:tag_seed"], (0.5, 1.0))
        self.assertEqual(tuple(pyreason_ext.head_bound or ()), (0.8, 0.9))

    def test_a2_body_confidences_bridge_still_resolves_to_problog_ext(self) -> None:
        from factpy.adapters.problog.rule_ext import ProbLogRuleExt, resolve_problog_engine_ext

        resolved = resolve_problog_engine_ext(
            where=[[("pred", "user:tag_seed", ["$u", "$tag"])]],
            engine_ext=None,
            legacy_body_confidences=[0.7],
        )

        self.assertIsInstance(resolved, ProbLogRuleExt)
        self.assertEqual(resolved.branch_probabilities, (0.7,))


if __name__ == "__main__":
    unittest.main()
