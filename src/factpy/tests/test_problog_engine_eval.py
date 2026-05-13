"""Tests for the ProbLog engine evaluator."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from unittest.mock import patch

import factpy.adapters.problog  # noqa: F401
from factpy.adapters.problog.engine_eval import evaluate_problog
from factpy.adapters.problog.rule_ext import ProbLogRuleExt
from factpy.core.store._support import PROBLOG_PROVENANCE_KIND
from factpy.core.store.runtime import get_engine_evaluator
from factpy.core.store.types import EngineExtBase
from factpy.core.evidence.write_protocol import set_field
from kernel.sdk.dsl import vars as sdk_vars
from factpy.sdk.dsl import Inference, Pred
from factpy.sdk.schema import Entity, Field, Identity
from factpy.sdk.store import SDKStore


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")


@dataclass(frozen=True)
class DummyProbLogExt(EngineExtBase):
    flag: int = 1


class ProbLogEngineEvalTests(unittest.TestCase):
    def _make_sdk(self) -> SDKStore:
        sdk = SDKStore([User])
        alice_ref = sdk.ref(User, user_id="Alice")
        set_field(
            sdk.ledger,
            pred_id="user:name",
            e_ref=alice_ref,
            rest_terms=[("string", "Alice")],
            meta={"source": "test", "confidence": 1.0},
        )
        set_field(
            sdk.ledger,
            pred_id="user:tag_seed",
            e_ref=alice_ref,
            rest_terms=[("string", "vip")],
            meta={"source": "test", "confidence": 1.0},
        )
        return sdk

    def _make_derivation(self) -> Inference:
        with sdk_vars("u", "tag") as (u, tag):
            return Inference(
                id="drv.problog_tag",
                version="v1",
                where=[Pred("user:tag_seed", u, tag)],
                target="user:tag",
                head_vars=[u, tag],
            )

    def _mock_output(self, sdk: SDKStore) -> str:
        alice_ref = sdk.ref(User, user_id="Alice")
        return "\n".join(
            [
                " call query(X1,X2) {0.00000} []",
                f'  result query(X1,X2) ("vip","{alice_ref}") {{{{}}}} {{0.00012}} []',
                " complete query(X1,X2) {0.00013} {0.00013} []",
                f' call answer("vip","{alice_ref}") {{0.00019}} [at 4:7]',
                f'  result answer("vip","{alice_ref}") ("vip","{alice_ref}") {{{{}}}} {{0.00060}} []',
                f' complete answer("vip","{alice_ref}") {{0.00061}} {{0.00042}} []',
                "",
                f'answer("vip","{alice_ref}"):\t0.42',
            ]
        )

    def test_registration_on_import(self) -> None:
        evaluator = get_engine_evaluator("problog")
        self.assertIs(evaluator, evaluate_problog)

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_default_timeout_used_when_engine_options_missing(self, mock_run) -> None:
        sdk = self._make_sdk()
        mock_run.return_value = self._mock_output(sdk)

        candidates = sdk.evaluate(self._make_derivation(), engine="problog")

        self.assertEqual(len(candidates), 1)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 30)
        self.assertTrue(mock_run.call_args.kwargs["trace"])
        self.assertEqual(candidates[0].support_kind, PROBLOG_PROVENANCE_KIND)
        self.assertNotEqual(candidates[0].support_digest, f"sha256:{'0' * 64}")

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_engine_options_timeout_override_default(self, mock_run) -> None:
        sdk = self._make_sdk()
        mock_run.return_value = self._mock_output(sdk)

        compiled = sdk._compile_derivation_input(self._make_derivation())
        self.assertNotIn("engine_options", compiled[0])

        candidates = sdk.evaluate(
            self._make_derivation(),
            engine="problog",
            engine_options={"timeout": 7},
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 7)
        self.assertTrue(mock_run.call_args.kwargs["trace"])

    def test_unknown_engine_option_raises(self) -> None:
        sdk = self._make_sdk()

        with self.assertRaises(ValueError) as ctx:
            sdk.evaluate(self._make_derivation(), engine="problog", engine_options={"timesteps": 5})

        self.assertIn("Supported keys: timeout", str(ctx.exception))

    def test_bad_timeout_type_raises(self) -> None:
        sdk = self._make_sdk()

        with self.assertRaises(ValueError) as ctx:
            sdk.evaluate(self._make_derivation(), engine="problog", engine_options={"timeout": "slow"})

        self.assertIn("positive int", str(ctx.exception))

    def test_non_problog_engine_ext_is_rejected(self) -> None:
        sdk = self._make_sdk()
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        compiled["engine_ext"] = DummyProbLogExt()

        with self.assertRaises(ValueError) as ctx:
            sdk.evaluate(compiled, engine="problog")

        self.assertIn("ProbLog engine_ext must be ProbLogRuleExt", str(ctx.exception))

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_problog_rule_ext_is_accepted_and_drives_export(self, mock_run) -> None:
        sdk = self._make_sdk()
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return self._mock_output(sdk)

        mock_run.side_effect = _fake_run

        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        compiled["engine_ext"] = ProbLogRuleExt(branch_probabilities=(0.5,))

        candidates = sdk.evaluate(compiled, engine="problog")

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.5::rule_body_0", seen["program"])

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_legacy_body_confidences_are_bridged_to_engine_ext(self, mock_run) -> None:
        sdk = self._make_sdk()
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        compiled["body_confidences"] = [0.25]
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return self._mock_output(sdk)

        mock_run.side_effect = _fake_run

        candidates = sdk.evaluate(compiled, engine="problog")

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.25::rule_body_0", seen["program"])

    def test_conflicting_body_confidences_and_engine_ext_raise(self) -> None:
        sdk = self._make_sdk()
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        compiled["body_confidences"] = [0.25]
        compiled["engine_ext"] = ProbLogRuleExt(branch_probabilities=(0.5,))

        with self.assertRaises(ValueError) as ctx:
            sdk.evaluate(compiled, engine="problog")

        self.assertIn("Conflicting ProbLog branch probabilities", str(ctx.exception))

    @patch("kernel.adapters.problog.engine_eval.run_problog")
    def test_matching_body_confidences_and_engine_ext_are_allowed(self, mock_run) -> None:
        sdk = self._make_sdk()
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        compiled["body_confidences"] = [0.25]
        compiled["engine_ext"] = ProbLogRuleExt(branch_probabilities=(0.25,))
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return self._mock_output(sdk)

        mock_run.side_effect = _fake_run

        candidates = sdk.evaluate(compiled, engine="problog")

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.25::rule_body_0", seen["program"])


if __name__ == "__main__":
    unittest.main()
