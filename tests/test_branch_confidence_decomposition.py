"""Red-baseline tests for Track 3 / A2 branch confidence decomposition."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path

from factpy.authoring.derivation_compile import (
    AuthoringDerivationCompileError,
    compile_authoring_derivation_v1,
)
from factpy.core.store.types import DerivationSpec, RuleSpec
from factpy.sdk import Pred
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


def _authoring_derivation_payload() -> dict[str, object]:
    return {
        "derivation_id": "drv.a2.user_tag",
        "version": "v1",
        "target": "user:tag",
        "head_vars": ["$u", "$tag"],
        "where": [("pred", "user:tag_seed", ["$u", "$tag"])],
    }


def _runtime_derivation_payload() -> dict[str, object]:
    return {
        "derivation_id": "drv.a2.runtime_user_tag",
        "version": "v1",
        "target": "user:tag",
        "head_vars": ["$u", "$tag"],
        "where": [["pred", "user:tag_seed", ["$u", "$tag"]]],
    }


class SDKBranchSurfaceTests(unittest.TestCase):
    def test_factpy_sdk_exports_branch_not_body(self) -> None:
        sdk = importlib.import_module("factpy.sdk")

        self.assertIn("Branch", sdk.__all__)
        self.assertNotIn("Body", sdk.__all__)
        self.assertTrue(hasattr(sdk, "Branch"))
        self.assertFalse(hasattr(sdk, "Body"))
        with self.assertRaises(ImportError):
            exec("from factpy.sdk import Body", {})

    def test_sdk_dsl_file_is_renamed_to_branch(self) -> None:
        sdk_dsl_dir = Path(__file__).resolve().parents[1] / "sdk" / "dsl"

        self.assertTrue((sdk_dsl_dir / "branch.py").exists())
        self.assertFalse((sdk_dsl_dir / "body.py").exists())

    def test_branch_lowers_to_branch_where_structure(self) -> None:
        sdk = importlib.import_module("factpy.sdk")
        branch_cls = getattr(sdk, "Branch", None)
        self.assertIsNotNone(branch_cls)

        from factpy.sdk.dsl.expr import lower_where

        lowered = lower_where(
            [
                branch_cls([Pred("user:tag_seed", "$u", "$tag")]),
                branch_cls([Pred("user:tag_hint", "$u", "$tag")]),
            ]
        )

        self.assertEqual(
            lowered,
            [
                [("pred", "user:tag_seed", ["$u", "$tag"])],
                [("pred", "user:tag_hint", ["$u", "$tag"])],
            ],
        )

    def test_branch_rejects_confidence_keyword(self) -> None:
        sdk = importlib.import_module("factpy.sdk")
        branch_cls = getattr(sdk, "Branch", None)
        self.assertIsNotNone(branch_cls)

        with self.assertRaises(TypeError):
            branch_cls([Pred("user:tag_seed", "$u", "$tag")], confidence=0.9)

    def test_branch_rejects_engine_specific_keywords(self) -> None:
        sdk = importlib.import_module("factpy.sdk")
        branch_cls = getattr(sdk, "Branch", None)
        self.assertIsNotNone(branch_cls)

        with self.assertRaises(TypeError):
            branch_cls([Pred("user:tag_seed", "$u", "$tag")], engine_ext=object())
        with self.assertRaises(TypeError):
            branch_cls([Pred("user:tag_seed", "$u", "$tag")], probability=0.9)


class AuthoringBranchConfidenceTests(unittest.TestCase):
    def test_authoring_body_confidences_key_is_rejected(self) -> None:
        payload = dict(_authoring_derivation_payload())
        payload["body_confidences"] = [0.9]

        with self.assertRaises(AuthoringDerivationCompileError) as ctx:
            compile_authoring_derivation_v1(payload)

        self.assertEqual(ctx.exception.path, "$.body_confidences")
        self.assertIn("ProbLogRuleExt.branch_probabilities", str(ctx.exception))

    def test_internal_ir_keeps_body_confidences_bridge(self) -> None:
        self.assertIn("body_confidences", RuleSpec.__annotations__)
        self.assertIn("body_confidences", DerivationSpec.__annotations__)


class ServiceBranchConfidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_sessions_for_tests()

    def tearDown(self) -> None:
        reset_runtime_sessions_for_tests()

    def _open_session(self) -> str:
        sdk = SDKStore([User])
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"], open_resp)
        return str(open_resp["session"]["session_id"])

    def test_service_rejects_top_level_body_confidences(self) -> None:
        session_id = self._open_session()
        try:
            resp = evaluate_runtime_derivation(
                session_id,
                {
                    "engine": "native",
                    "body_confidences": [0.9],
                    "inference": _runtime_derivation_payload(),
                },
            )

            self.assertFalse(resp["ok"], resp)
            self.assertEqual(resp["errors"][0]["path"], "$.body_confidences")
            self.assertIn("ProbLogRuleExt.branch_probabilities", resp["errors"][0]["details"]["message"])
        finally:
            close_runtime_session(session_id)

    def test_service_rejects_derivation_body_confidences(self) -> None:
        session_id = self._open_session()
        derivation = dict(_runtime_derivation_payload())
        derivation["body_confidences"] = [0.9]
        try:
            resp = evaluate_runtime_derivation(
                session_id,
                {
                    "engine": "native",
                    "inference": derivation,
                },
            )

            self.assertFalse(resp["ok"], resp)
            self.assertEqual(resp["errors"][0]["path"], "$.inference.body_confidences")
            self.assertIn("ProbLogRuleExt.branch_probabilities", resp["errors"][0]["details"]["message"])
        finally:
            close_runtime_session(session_id)


class ProbLogFallbackTests(unittest.TestCase):
    def test_problog_branch_probabilities_remain_public_fallback(self) -> None:
        from factpy.adapters.problog.rule_ext import ProbLogRuleExt

        ext = ProbLogRuleExt(branch_probabilities=(0.9, 0.6))

        self.assertEqual(ext.branch_probabilities, (0.9, 0.6))


if __name__ == "__main__":
    unittest.main()
