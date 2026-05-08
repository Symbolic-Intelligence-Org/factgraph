"""Unit tests for the shared SDK shell input validators.

Exercises the shared validators in
``kernel.sdk.shells._validation`` directly: behavior parity vs the
inlined G1 validators they replaced (Q1 follow-up to Round 4 audit) for
``validate_derivation`` / ``validate_binding``; G2 polish-round
``validate_evaluation_overlay``; and G3 Phase 0 hygiene additions
``validate_rule`` / ``validate_support_artifact`` /
``validate_optional_evaluation_overlay``. Locks the path-parameter
contract that lets multiple SDK shell methods (Check, Diagnose, Why-not,
G2 Fact Overlay + ProofFrame Recheck, G3 rule-overlay shells) share
validators without duplicating logic, and the post-G2 Phase 0 hygiene
location under ``kernel/sdk/shells/``.
"""

from __future__ import annotations

import unittest

from kernel.application.protocol import (
    EvaluationOverlay,
    FactRemoveAction,
    FactValueOverride,
    RuleDisableAction,
)
from kernel.sdk import (
    Derivation,
    Entity,
    Field,
    Identity,
    Pred,
    Rule,
    SDKStoreError,
    vars,
)
from kernel.sdk.shells._validation import (
    validate_binding,
    validate_derivation,
    validate_evaluation_overlay,
    validate_optional_evaluation_overlay,
    validate_rule,
    validate_support_artifact,
)


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")


def _age_derivation() -> Derivation:
    with vars("p", "age") as (p, age):
        return Derivation(
            id="sdk.validation.age",
            version="v1",
            where=[Person(p), p.age == age],
            head=Person.age(value=age),
        )


class ValidateDerivationTests(unittest.TestCase):
    def test_accepts_sdk_derivation(self) -> None:
        validate_derivation(_age_derivation(), path="$.check.derivation")

    def test_rejects_non_derivation_with_provided_path(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_derivation({"not": "derivation"}, path="$.diagnose.derivation")
        self.assertEqual(ctx.exception.path, "$.diagnose.derivation")
        self.assertIn("derivation must be SDK Derivation", str(ctx.exception))

    def test_rejects_none(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_derivation(None, path="$.check.derivation")
        self.assertEqual(ctx.exception.path, "$.check.derivation")

    def test_path_is_forwarded_verbatim(self) -> None:
        custom_path = "$.future_g4.why_not.derivation"
        with self.assertRaises(SDKStoreError) as ctx:
            validate_derivation("not-a-derivation", path=custom_path)
        self.assertEqual(ctx.exception.path, custom_path)


class ValidateBindingTests(unittest.TestCase):
    def test_accepts_dollar_prefixed_string_keys_and_returns_dict_copy(self) -> None:
        binding = {"$p": "alice", "$age": 30}
        out = validate_binding(binding, path="$.check.binding")
        self.assertEqual(out, {"$p": "alice", "$age": 30})
        self.assertIsInstance(out, dict)
        self.assertIsNot(out, binding)

    def test_rejects_non_mapping(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_binding([("$p", "alice")], path="$.check.binding")
        self.assertEqual(ctx.exception.path, "$.check.binding")
        self.assertIn("Mapping", str(ctx.exception))

    def test_rejects_non_string_key(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_binding({1: "x"}, path="$.diagnose.binding")
        self.assertEqual(ctx.exception.path, "$.diagnose.binding")

    def test_rejects_unprefixed_key(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_binding({"p": "alice"}, path="$.check.binding")
        self.assertEqual(ctx.exception.path, "$.check.binding")

    def test_rejects_lone_dollar_key(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_binding({"$": "alice"}, path="$.check.binding")
        self.assertIn("$-prefixed", str(ctx.exception))

    def test_accepts_empty_mapping(self) -> None:
        out = validate_binding({}, path="$.check.binding")
        self.assertEqual(out, {})

    def test_path_is_forwarded_verbatim(self) -> None:
        custom_path = "$.future_g4.why_not.binding"
        with self.assertRaises(SDKStoreError) as ctx:
            validate_binding("not-a-mapping", path=custom_path)
        self.assertEqual(ctx.exception.path, custom_path)


def _adult_rule() -> Rule:
    with vars("p") as (p,):
        return Rule(
            id="sdk.validation.adult",
            version="v1",
            select=[Pred("Person:exists", p)],
            where=[Person(p)],
        )


class ValidateRuleTests(unittest.TestCase):
    def test_accepts_sdk_rule(self) -> None:
        validate_rule(_adult_rule(), path="$.check_rule_disable.rule")

    def test_rejects_non_rule_with_provided_path(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_rule({"not": "rule"}, path="$.check_rule_literal_replace.rule")
        self.assertEqual(ctx.exception.path, "$.check_rule_literal_replace.rule")
        self.assertIn("rule must be SDK Rule", str(ctx.exception))

    def test_rejects_none(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_rule(None, path="$.check_rule_add_condition.rule")
        self.assertEqual(ctx.exception.path, "$.check_rule_add_condition.rule")

    def test_rejects_derivation(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_rule(_age_derivation(), path="$.check_rule_disable.rule")
        self.assertEqual(ctx.exception.path, "$.check_rule_disable.rule")

    def test_path_is_forwarded_verbatim(self) -> None:
        custom_path = "$.future_g3.future_method.rule"
        with self.assertRaises(SDKStoreError) as ctx:
            validate_rule("not-a-rule", path=custom_path)
        self.assertEqual(ctx.exception.path, custom_path)


class ValidateSupportArtifactTests(unittest.TestCase):
    def test_rejects_non_support_artifact_with_provided_path(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_support_artifact(
                {"not": "support"}, path="$.check_rule_disable.support"
            )
        self.assertEqual(ctx.exception.path, "$.check_rule_disable.support")
        self.assertIn("support must be SupportArtifact", str(ctx.exception))

    def test_rejects_none(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_support_artifact(None, path="$.recheck_proof_frame.support_artifact")
        self.assertEqual(
            ctx.exception.path, "$.recheck_proof_frame.support_artifact"
        )

    def test_path_is_forwarded_verbatim(self) -> None:
        custom_path = "$.future_g5.future_method.support"
        with self.assertRaises(SDKStoreError) as ctx:
            validate_support_artifact("not-a-support", path=custom_path)
        self.assertEqual(ctx.exception.path, custom_path)


class ValidateOptionalEvaluationOverlayTests(unittest.TestCase):
    def test_accepts_none(self) -> None:
        validate_optional_evaluation_overlay(None, path="$.check_rule_disable.overlay")

    def test_accepts_empty_evaluation_overlay(self) -> None:
        validate_optional_evaluation_overlay(
            EvaluationOverlay(), path="$.check_rule_disable.overlay"
        )

    def test_rejects_non_evaluation_overlay_non_none_with_provided_path(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_optional_evaluation_overlay(
                {"not": "overlay"}, path="$.check_rule_literal_replace.overlay"
            )
        self.assertEqual(
            ctx.exception.path, "$.check_rule_literal_replace.overlay"
        )
        self.assertIn(
            "overlay must be EvaluationOverlay or None", str(ctx.exception)
        )

    def test_rejects_tuple_form_overlay(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_optional_evaluation_overlay(
                (FactValueOverride(asrt_id="A1", pred_id="Person:age", e_ref="alice", old_fact_tuple=(20,), new_fact_tuple=(30,)),),
                path="$.check_rule_disable.overlay",
            )
        self.assertEqual(ctx.exception.path, "$.check_rule_disable.overlay")
        self.assertIn(
            "overlay must be EvaluationOverlay or None", str(ctx.exception)
        )

    def test_rejects_overlay_with_fact_actions(self) -> None:
        overlay = EvaluationOverlay(
            fact_actions=(
                FactValueOverride(asrt_id="A1", pred_id="Person:age", e_ref="alice", old_fact_tuple=(20,), new_fact_tuple=(30,)),
            )
        )
        with self.assertRaises(SDKStoreError) as ctx:
            validate_optional_evaluation_overlay(
                overlay, path="$.check_rule_disable.overlay"
            )
        self.assertEqual(ctx.exception.path, "$.check_rule_disable.overlay")
        self.assertIn("must be empty EvaluationOverlay", str(ctx.exception))
        self.assertIn(
            "rule-action overlay is constructed internally", str(ctx.exception)
        )

    def test_rejects_overlay_with_fact_remove_actions(self) -> None:
        overlay = EvaluationOverlay(
            fact_actions=(
                FactRemoveAction(
                    asrt_id="A1",
                    pred_id="Person:age",
                    e_ref="alice",
                    old_fact_tuple=(30,),
                ),
            )
        )
        with self.assertRaises(SDKStoreError) as ctx:
            validate_optional_evaluation_overlay(
                overlay, path="$.check_rule_literal_replace.overlay"
            )
        self.assertEqual(
            ctx.exception.path, "$.check_rule_literal_replace.overlay"
        )

    def test_rejects_overlay_with_rule_actions(self) -> None:
        overlay = EvaluationOverlay(
            rule_actions=(
                RuleDisableAction(
                    rule_id="sdk.validation.adult",
                    version="v1",
                    branch_index=0,
                    atom_index=0,
                ),
            )
        )
        with self.assertRaises(SDKStoreError) as ctx:
            validate_optional_evaluation_overlay(
                overlay, path="$.check_rule_disable.overlay"
            )
        self.assertEqual(ctx.exception.path, "$.check_rule_disable.overlay")
        self.assertIn("must be empty EvaluationOverlay", str(ctx.exception))

    def test_path_is_forwarded_verbatim(self) -> None:
        custom_path = "$.future_g3.future_method.overlay"
        with self.assertRaises(SDKStoreError) as ctx:
            validate_optional_evaluation_overlay("not-overlay", path=custom_path)
        self.assertEqual(ctx.exception.path, custom_path)


class ValidateEvaluationOverlayTests(unittest.TestCase):
    """Smoke parity test for the existing G2 polish-round validator.

    The Fact Overlay + ProofFrame Recheck shells use this directly; G3
    rule-overlay shells use ``validate_optional_evaluation_overlay``
    instead, which differs in (a) accepting ``None`` and (b) rejecting
    non-empty overlays.
    """

    def test_accepts_evaluation_overlay(self) -> None:
        validate_evaluation_overlay(EvaluationOverlay(), path="$.check_fact_overlay.overlay")

    def test_rejects_none(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_evaluation_overlay(None, path="$.check_fact_overlay.overlay")
        self.assertEqual(ctx.exception.path, "$.check_fact_overlay.overlay")
        self.assertIn("overlay must be EvaluationOverlay", str(ctx.exception))

    def test_rejects_non_evaluation_overlay(self) -> None:
        with self.assertRaises(SDKStoreError) as ctx:
            validate_evaluation_overlay(
                (FactValueOverride(asrt_id="A1", pred_id="Person:age", e_ref="alice", old_fact_tuple=(20,), new_fact_tuple=(30,)),),
                path="$.recheck_proof_frame.overlay",
            )
        self.assertEqual(ctx.exception.path, "$.recheck_proof_frame.overlay")


if __name__ == "__main__":
    unittest.main()
