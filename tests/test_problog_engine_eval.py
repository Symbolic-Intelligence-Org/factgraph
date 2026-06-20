"""Tests for the ProbLog engine evaluator."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from unittest.mock import patch

import factgraph.adapters.problog  # noqa: F401
from factgraph.adapters.problog.engine_eval import evaluate_problog
from factgraph.adapters.problog.rule_ext import ProbLogRuleExt
from factgraph.core.store.runtime import get_engine_evaluator
from factgraph.core.store.types import EngineExtBase
from factgraph.core.evidence.write_protocol import set_field
from factgraph.sdk.dsl import vars as sdk_vars
from factgraph.sdk.dsl import EmitSpec, Inference, Pred
from factgraph.sdk.errors import SDKStoreError
from factgraph.sdk.schema import Entity, Field, Identity
from factgraph.sdk.store import SDKStore


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag_seed: str = Field()
    tag: str = Field()


@dataclass(frozen=True)
class DummyProbLogExt(EngineExtBase):
    flag: int = 1


class ProbLogEngineEvalTests(unittest.TestCase):
    def _make_sdk(self) -> SDKStore:
        sdk = SDKStore([User])
        alice_ref = sdk.entities.ref(User, user_id="Alice")
        set_field(
            sdk.ledger,
            pred_id="user:name",
            e_ref=alice_ref,
            rest_terms=[("string", "Alice")],
            meta={"source": "test"},
        )
        set_field(
            sdk.ledger,
            pred_id="user:tag_seed",
            e_ref=alice_ref,
            rest_terms=[("string", "vip")],
            meta={"source": "test"},
        )
        return sdk

    def _make_derivation(self) -> Inference:
        with sdk_vars("u", "tag") as (u, tag):
            return Inference(
                id="drv.problog_tag",
                version="v1",
                when=[Pred("user:tag_seed", u, tag)],
                emits=EmitSpec("user:tag", [u, tag]),
            )

    def _mock_output(self, sdk: SDKStore) -> str:
        alice_ref = sdk.entities.ref(User, user_id="Alice")
        return "\n".join(
            [
                " call query(X1,X2) {0.00000} []",
                f'  result query(X1,X2) ("{alice_ref}","vip") {{{{}}}} {{0.00012}} []',
                " complete query(X1,X2) {0.00013} {0.00013} []",
                f' call answer("{alice_ref}","vip") {{0.00019}} [at 4:7]',
                f'  result answer("{alice_ref}","vip") ("{alice_ref}","vip") {{{{}}}} {{0.00060}} []',
                f' complete answer("{alice_ref}","vip") {{0.00061}} {{0.00042}} []',
                "",
                f'answer("{alice_ref}","vip"):\t0.42',
            ]
        )

    def test_registration_on_import(self) -> None:
        evaluator = get_engine_evaluator("problog")
        self.assertIs(evaluator, evaluate_problog)

    @patch("factgraph.adapters.problog.engine_eval.run_problog")
    def test_default_timeout_used_when_engine_options_missing(self, mock_run) -> None:
        sdk = self._make_sdk()
        mock_run.return_value = self._mock_output(sdk)

        candidates = sdk.eval.evaluate(self._make_derivation(), engine="problog")

        self.assertEqual(len(candidates), 1)
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 30)
        self.assertTrue(mock_run.call_args.kwargs["trace"])
        explanation = candidates[0].explain()
        assert explanation.evidence is not None
        self.assertEqual(explanation.status, "passed")
        self.assertTrue(explanation.evidence.paths)
        self.assertIn("candidate_id", explanation.evidence.paths[0].metadata)
        self.assertNotEqual(candidates[0].closed_head_digest, f"sha256:{'0' * 64}")

    @patch("factgraph.adapters.problog.engine_eval.run_problog")
    def test_free_form_target_pred_id_uses_query_style_candidates(self, mock_run) -> None:
        sdk = self._make_sdk()
        mock_run.return_value = self._mock_output(sdk)
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        compiled["target_pred_id"] = "find_user_tags"

        candidates = sdk.eval.evaluate(compiled, engine="problog")

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates.head.id, "find_user_tags")
        self.assertIn("u", candidates[0].bindings)
        self.assertIn("tag", candidates[0].bindings)

    def test_sdk_evaluate_rejects_engine_options_timeout(self) -> None:
        sdk = self._make_sdk()

        compiled = sdk._compile_derivation_input(self._make_derivation())
        self.assertNotIn("engine_options", compiled[0])

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(
                self._make_derivation(),
                engine="problog",
                engine_options={"timeout": 7},
            )
        self.assertIn("engine_options", str(ctx.exception))

    def test_unknown_engine_option_raises(self) -> None:
        sdk = self._make_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(self._make_derivation(), engine="problog", engine_options={"timesteps": 5})

        self.assertIn("engine_options", str(ctx.exception))

    def test_bad_timeout_type_raises(self) -> None:
        sdk = self._make_sdk()

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(self._make_derivation(), engine="problog", engine_options={"timeout": "slow"})

        self.assertIn("engine_options", str(ctx.exception))

    def test_non_problog_engine_ext_is_rejected(self) -> None:
        sdk = self._make_sdk()
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        compiled["engine_ext"] = DummyProbLogExt()

        with self.assertRaises(ValueError) as ctx:
            sdk.eval.evaluate(compiled, engine="problog")

        self.assertIn("ProbLog engine_ext must be ProbLogRuleExt", str(ctx.exception))

    @patch("factgraph.adapters.problog.engine_eval.run_problog")
    def test_problog_rule_ext_is_accepted_and_drives_export(self, mock_run) -> None:
        sdk = self._make_sdk()
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return self._mock_output(sdk)

        mock_run.side_effect = _fake_run

        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        compiled["engine_ext"] = ProbLogRuleExt(case_probabilities=(0.5,))

        candidates = sdk.eval.evaluate(compiled, engine="problog")

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.5::rule_body_0", seen["program"])

    @patch("factgraph.adapters.problog.engine_eval.run_problog")
    def test_legacy_body_confidences_are_bridged_to_engine_ext(self, mock_run) -> None:
        sdk = self._make_sdk()
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        compiled["body_confidences"] = [0.25]
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return self._mock_output(sdk)

        mock_run.side_effect = _fake_run

        candidates = sdk.eval.evaluate(compiled, engine="problog")

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.25::rule_body_0", seen["program"])

    def test_conflicting_body_confidences_and_engine_ext_raise(self) -> None:
        sdk = self._make_sdk()
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        compiled["body_confidences"] = [0.25]
        compiled["engine_ext"] = ProbLogRuleExt(case_probabilities=(0.5,))

        with self.assertRaises(ValueError) as ctx:
            sdk.eval.evaluate(compiled, engine="problog")

        self.assertIn("Conflicting ProbLog branch probabilities", str(ctx.exception))

    @patch("factgraph.adapters.problog.engine_eval.run_problog")
    def test_matching_body_confidences_and_engine_ext_are_allowed(self, mock_run) -> None:
        sdk = self._make_sdk()
        compiled = sdk._compile_derivation_input(self._make_derivation())[0]
        compiled["body_confidences"] = [0.25]
        compiled["engine_ext"] = ProbLogRuleExt(case_probabilities=(0.25,))
        seen: dict[str, str] = {}

        def _fake_run(pl_path, *, timeout, trace):
            seen["program"] = pl_path.read_text(encoding="utf-8")
            return self._mock_output(sdk)

        mock_run.side_effect = _fake_run

        candidates = sdk.eval.evaluate(compiled, engine="problog")

        self.assertEqual(len(candidates), 1)
        self.assertIn("0.25::rule_body_0", seen["program"])


if __name__ == "__main__":
    unittest.main()
