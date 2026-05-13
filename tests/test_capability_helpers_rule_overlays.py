"""Tests for rule overlay capability helper builders."""

from __future__ import annotations

import unittest

from factpy.application import (
    CapabilityHelperError,
    OriginPackageError,
    build_rule_add_condition_request,
    build_rule_disable_request,
    build_rule_literal_replace_request,
)
from factpy.application.protocol import (
    EvaluationOverlay,
    FactValueOverride,
    RuleAddConditionAction,
    RuleAddConditionRequest,
    RuleAddedAtom,
    RuleDisableAction,
    RuleDisableRequest,
    RuleLiteralPath,
    RuleLiteralReplaceAction,
    RuleLiteralReplaceRequest,
)
from factpy.core.rules.rule_ir import RuleSpec
from factpy.core.store._support import PredWitness, SupportArtifact
from factpy.sdk import Pred, Rule, vars as sdk_vars


def _rule_spec(*, where: list[object] | None = None) -> RuleSpec:
    return RuleSpec(
        rule_id="person.eligible",
        version="1.0",
        select_vars=["$p"],
        where=where
        if where is not None
        else [("pred", "Person:exists", ["$p"]), ("eq", "$region", "us")],
    )


def _support(*, binding_items: tuple[tuple[str, object], ...] | None = None) -> SupportArtifact:
    return SupportArtifact(
        kind="native_binding_v1",
        root_result_kind="row",
        binding_items=binding_items if binding_items is not None else (("$p", "person:alice"),),
        pred_witnesses=(
            PredWitness(pred_atom_key="b0.a0:Person:exists", asrt_ids=("a1",)),
        ),
    )


def _sdk_rule() -> Rule:
    with sdk_vars("p", "age") as (p, age):
        return Rule(
            id="helper.sdk_rule",
            version="1.0",
            select=[Pred("person:eligible", p)],
            where=[Pred("person:age", p, age)],
        )


def _fact_overlay() -> EvaluationOverlay:
    return EvaluationOverlay(
        fact_actions=(
            FactValueOverride(
                asrt_id="a1",
                pred_id="Person.age",
                e_ref="person:alice",
                old_fact_tuple=("person:alice", 25),
                new_fact_tuple=("person:alice", 26),
            ),
        )
    )


def _sdk_fact_overlay() -> EvaluationOverlay:
    return EvaluationOverlay(
        fact_actions=(
            FactValueOverride(
                asrt_id="a1",
                pred_id="Person.age",
                e_ref="person:alice",
                old_fact_tuple=("person:alice", 25),
                new_fact_tuple=("person:alice", _sdk_rule()),
            ),
        )
    )


class BuildRuleDisableRequestTests(unittest.TestCase):
    def test_builds_disable_request_with_generated_overlay(self) -> None:
        rule_spec = _rule_spec()
        support = _support()

        request = build_rule_disable_request(
            rule_spec,
            support,
            branch_index=0,
            atom_index=1,
            note="phase4",
        )

        self.assertIsInstance(request, RuleDisableRequest)
        self.assertIs(request.rule_spec, rule_spec)
        self.assertIs(request.support_artifact, support)
        self.assertEqual(request.overlay.fact_actions, ())
        self.assertEqual(len(request.overlay.rule_actions), 1)
        action = request.overlay.rule_actions[0]
        self.assertIsInstance(action, RuleDisableAction)
        self.assertEqual(action.rule_id, "person.eligible")
        self.assertEqual(action.version, "1.0")
        self.assertEqual(action.branch_index, 0)
        self.assertEqual(action.atom_index, 1)
        self.assertEqual(action.note, "phase4")

    def test_accepts_explicit_empty_overlay_as_base(self) -> None:
        request = build_rule_disable_request(
            _rule_spec(),
            _support(),
            branch_index=0,
            atom_index=1,
            overlay=EvaluationOverlay(),
        )

        self.assertIsInstance(request.overlay.rule_actions[0], RuleDisableAction)

    def test_rejects_non_empty_overlay(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "non-empty overlay"):
            build_rule_disable_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                atom_index=1,
                overlay=_fact_overlay(),
            )

    def test_rejects_wrong_common_input_types(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "rule_spec"):
            build_rule_disable_request(
                object(),  # type: ignore[arg-type]
                _support(),
                branch_index=0,
                atom_index=1,
            )
        with self.assertRaisesRegex(CapabilityHelperError, "support"):
            build_rule_disable_request(
                _rule_spec(),
                object(),  # type: ignore[arg-type]
                branch_index=0,
                atom_index=1,
            )
        with self.assertRaisesRegex(CapabilityHelperError, "overlay"):
            build_rule_disable_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                atom_index=1,
                overlay=object(),  # type: ignore[arg-type]
            )

    def test_rejects_sdk_origin_in_rule_spec_and_support(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_rule_disable_request(
                _rule_spec(where=[_sdk_rule()]),
                _support(),
                branch_index=0,
                atom_index=1,
            )

    def test_rejects_top_level_sdk_origin_before_type_or_overlay_errors(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_rule_disable_request(
                _sdk_rule(),  # type: ignore[arg-type]
                _support(),
                branch_index=0,
                atom_index=1,
            )
        with self.assertRaises(OriginPackageError):
            build_rule_disable_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                atom_index=1,
                overlay=_sdk_rule(),  # type: ignore[arg-type]
            )
        with self.assertRaises(OriginPackageError):
            build_rule_disable_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                atom_index=1,
                overlay=_sdk_fact_overlay(),
            )
        with self.assertRaises(OriginPackageError):
            build_rule_disable_request(
                _rule_spec(),
                _support(),
                branch_index=_sdk_rule(),  # type: ignore[arg-type]
                atom_index=1,
            )
        with self.assertRaises(OriginPackageError):
            build_rule_disable_request(
                _rule_spec(),
                _support(binding_items=(("$rule", _sdk_rule()),)),
                branch_index=0,
                atom_index=1,
            )


class BuildRuleLiteralReplaceRequestTests(unittest.TestCase):
    def test_builds_literal_replace_request_with_generated_overlay(self) -> None:
        rule_spec = _rule_spec()
        support = _support()
        literal_path = RuleLiteralPath(kind="rhs")

        request = build_rule_literal_replace_request(
            rule_spec,
            support,
            branch_index=0,
            atom_index=1,
            literal_path=literal_path,
            old_literal="us",
            new_literal="eu",
            note="replace",
        )

        self.assertIsInstance(request, RuleLiteralReplaceRequest)
        self.assertIs(request.rule_spec, rule_spec)
        self.assertIs(request.support_artifact, support)
        action = request.overlay.rule_actions[0]
        self.assertIsInstance(action, RuleLiteralReplaceAction)
        self.assertEqual(action.rule_id, "person.eligible")
        self.assertEqual(action.version, "1.0")
        self.assertEqual(action.branch_index, 0)
        self.assertEqual(action.atom_index, 1)
        self.assertEqual(action.literal_path, literal_path)
        self.assertEqual(action.old_literal, "us")
        self.assertEqual(action.new_literal, "eu")
        self.assertEqual(action.note, "replace")

    def test_accepts_explicit_empty_overlay_as_base(self) -> None:
        request = build_rule_literal_replace_request(
            _rule_spec(),
            _support(),
            branch_index=0,
            atom_index=1,
            literal_path=RuleLiteralPath(kind="rhs"),
            old_literal="us",
            new_literal="eu",
            overlay=EvaluationOverlay(),
        )

        self.assertIsInstance(request.overlay.rule_actions[0], RuleLiteralReplaceAction)

    def test_rejects_non_empty_overlay(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "non-empty overlay"):
            build_rule_literal_replace_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                atom_index=1,
                literal_path=RuleLiteralPath(kind="rhs"),
                old_literal="us",
                new_literal="eu",
                overlay=_fact_overlay(),
            )

    def test_rejects_wrong_common_input_types(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "rule_spec"):
            build_rule_literal_replace_request(
                object(),  # type: ignore[arg-type]
                _support(),
                branch_index=0,
                atom_index=1,
                literal_path=RuleLiteralPath(kind="rhs"),
                old_literal="us",
                new_literal="eu",
            )
        with self.assertRaisesRegex(CapabilityHelperError, "support"):
            build_rule_literal_replace_request(
                _rule_spec(),
                object(),  # type: ignore[arg-type]
                branch_index=0,
                atom_index=1,
                literal_path=RuleLiteralPath(kind="rhs"),
                old_literal="us",
                new_literal="eu",
            )

    def test_rejects_sdk_origin_in_rule_spec_support_and_literals(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_rule_literal_replace_request(
                _rule_spec(where=[_sdk_rule()]),
                _support(),
                branch_index=0,
                atom_index=1,
                literal_path=RuleLiteralPath(kind="rhs"),
                old_literal="us",
                new_literal="eu",
            )
        with self.assertRaises(OriginPackageError):
            build_rule_literal_replace_request(
                _rule_spec(),
                _support(binding_items=(("$rule", _sdk_rule()),)),
                branch_index=0,
                atom_index=1,
                literal_path=RuleLiteralPath(kind="rhs"),
                old_literal="us",
                new_literal="eu",
            )
        with self.assertRaises(OriginPackageError):
            build_rule_literal_replace_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                atom_index=1,
                literal_path=RuleLiteralPath(kind="rhs"),
                old_literal="us",
                new_literal=_sdk_rule(),
            )

    def test_rejects_top_level_sdk_origin_before_type_or_overlay_errors(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_rule_literal_replace_request(
                _sdk_rule(),  # type: ignore[arg-type]
                _support(),
                branch_index=0,
                atom_index=1,
                literal_path=RuleLiteralPath(kind="rhs"),
                old_literal="us",
                new_literal="eu",
            )
        with self.assertRaises(OriginPackageError):
            build_rule_literal_replace_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                atom_index=1,
                literal_path=RuleLiteralPath(kind="rhs"),
                old_literal="us",
                new_literal="eu",
                overlay=_sdk_rule(),  # type: ignore[arg-type]
            )
        with self.assertRaises(OriginPackageError):
            build_rule_literal_replace_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                atom_index=1,
                literal_path=RuleLiteralPath(kind="rhs"),
                old_literal="us",
                new_literal="eu",
                overlay=_sdk_fact_overlay(),
            )
        with self.assertRaises(OriginPackageError):
            build_rule_literal_replace_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                atom_index=1,
                literal_path=_sdk_rule(),  # type: ignore[arg-type]
                old_literal="us",
                new_literal="eu",
            )
        with self.assertRaises(OriginPackageError):
            build_rule_literal_replace_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                atom_index=1,
                literal_path=RuleLiteralPath(kind="rhs"),
                old_literal=_sdk_rule(),
                new_literal="eu",
            )


class BuildRuleAddConditionRequestTests(unittest.TestCase):
    def test_builds_add_condition_request_with_generated_overlay(self) -> None:
        rule_spec = _rule_spec()
        support = _support()
        added_atom = RuleAddedAtom(("lt", "$age", 65))

        request = build_rule_add_condition_request(
            rule_spec,
            support,
            branch_index=0,
            added_atom=added_atom,
            note="add",
        )

        self.assertIsInstance(request, RuleAddConditionRequest)
        self.assertIs(request.rule_spec, rule_spec)
        self.assertIs(request.support_artifact, support)
        action = request.overlay.rule_actions[0]
        self.assertIsInstance(action, RuleAddConditionAction)
        self.assertEqual(action.rule_id, "person.eligible")
        self.assertEqual(action.version, "1.0")
        self.assertEqual(action.branch_index, 0)
        self.assertEqual(action.added_atom, added_atom)
        self.assertEqual(action.note, "add")

    def test_accepts_explicit_empty_overlay_as_base(self) -> None:
        request = build_rule_add_condition_request(
            _rule_spec(),
            _support(),
            branch_index=0,
            added_atom=RuleAddedAtom(("lt", "$age", 65)),
            overlay=EvaluationOverlay(),
        )

        self.assertIsInstance(request.overlay.rule_actions[0], RuleAddConditionAction)

    def test_rejects_non_empty_overlay(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "non-empty overlay"):
            build_rule_add_condition_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                added_atom=RuleAddedAtom(("lt", "$age", 65)),
                overlay=_fact_overlay(),
            )

    def test_rejects_wrong_common_input_types(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "rule_spec"):
            build_rule_add_condition_request(
                object(),  # type: ignore[arg-type]
                _support(),
                branch_index=0,
                added_atom=RuleAddedAtom(("lt", "$age", 65)),
            )
        with self.assertRaisesRegex(CapabilityHelperError, "support"):
            build_rule_add_condition_request(
                _rule_spec(),
                object(),  # type: ignore[arg-type]
                branch_index=0,
                added_atom=RuleAddedAtom(("lt", "$age", 65)),
            )

    def test_rejects_sdk_origin_in_rule_spec_support_and_added_atom(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_rule_add_condition_request(
                _rule_spec(where=[_sdk_rule()]),
                _support(),
                branch_index=0,
                added_atom=RuleAddedAtom(("lt", "$age", 65)),
            )
        with self.assertRaises(OriginPackageError):
            build_rule_add_condition_request(
                _rule_spec(),
                _support(binding_items=(("$rule", _sdk_rule()),)),
                branch_index=0,
                added_atom=RuleAddedAtom(("lt", "$age", 65)),
            )
        with self.assertRaises(OriginPackageError):
            build_rule_add_condition_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                added_atom=RuleAddedAtom(("lt", "$age", _sdk_rule())),
            )

    def test_rejects_top_level_sdk_origin_before_type_or_overlay_errors(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_rule_add_condition_request(
                _sdk_rule(),  # type: ignore[arg-type]
                _support(),
                branch_index=0,
                added_atom=RuleAddedAtom(("lt", "$age", 65)),
            )
        with self.assertRaises(OriginPackageError):
            build_rule_add_condition_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                added_atom=RuleAddedAtom(("lt", "$age", 65)),
                overlay=_sdk_rule(),  # type: ignore[arg-type]
            )
        with self.assertRaises(OriginPackageError):
            build_rule_add_condition_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                added_atom=RuleAddedAtom(("lt", "$age", 65)),
                overlay=_sdk_fact_overlay(),
            )
        with self.assertRaises(OriginPackageError):
            build_rule_add_condition_request(
                _rule_spec(),
                _support(),
                branch_index=_sdk_rule(),  # type: ignore[arg-type]
                added_atom=RuleAddedAtom(("lt", "$age", 65)),
            )
        with self.assertRaises(OriginPackageError):
            build_rule_add_condition_request(
                _rule_spec(),
                _support(),
                branch_index=0,
                added_atom=_sdk_rule(),  # type: ignore[arg-type]
            )


class RuleOverlayHelperExportTests(unittest.TestCase):
    def test_phase_4_exports_from_application_and_helper_package(self) -> None:
        from . import application
        from factpy.application import capability_helpers

        self.assertIs(
            application.build_rule_disable_request,
            build_rule_disable_request,
        )
        self.assertIs(
            application.build_rule_literal_replace_request,
            build_rule_literal_replace_request,
        )
        self.assertIs(
            application.build_rule_add_condition_request,
            build_rule_add_condition_request,
        )
        self.assertIs(
            capability_helpers.build_rule_disable_request,
            build_rule_disable_request,
        )
        self.assertIs(
            capability_helpers.build_rule_literal_replace_request,
            build_rule_literal_replace_request,
        )
        self.assertIs(
            capability_helpers.build_rule_add_condition_request,
            build_rule_add_condition_request,
        )


if __name__ == "__main__":
    unittest.main()
