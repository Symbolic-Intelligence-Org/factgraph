"""Rule Add Condition protocol shape tests."""

from __future__ import annotations

import dataclasses
import typing
import unittest
from dataclasses import FrozenInstanceError

from factgraph.application import protocol as protocol_pkg
from factgraph.application.protocol import (
    ErrorDTO,
    FactOverlay,
    ProofFrameConditionVerdict,
    ProofFrameRecheckResult,
    ProtocolShapeError,
    RuleAddConditionAction,
    RuleAddConditionRequest,
    RuleAddConditionResult,
    RuleAddConditionStatus,
    AddedCondition,
)
from factgraph.application.protocol import rule_add_condition as add_protocol
from factgraph.core.rules.rule_ir import RuleSpec
from factgraph.core.store._support import PredWitness, ProofReceipt


def _rule_spec() -> RuleSpec:
    return RuleSpec(
        rule_id="person.eligible",
        version="1.0",
        select_vars=["$p"],
        where=[("pred", "Person:exists", ["$p"]), ("lt", "$age", 65)],
    )


def _artifact(**kwargs: object) -> ProofReceipt:
    fields = {
        "kind": "native_binding_v1",
        "root_result_kind": "row",
        "binding_items": (("$p", "person:alice"),),
        "pred_witnesses": (
            PredWitness(pred_condition_key="c0.c0:Person:exists", asrt_ids=("a1",)),
        ),
    }
    fields.update(kwargs)
    return ProofReceipt(**fields)  # type: ignore[arg-type]


def _action() -> RuleAddConditionAction:
    return RuleAddConditionAction(
        rule_id="person.eligible",
        version="1.0",
        case_index=0,
        added_atom=AddedCondition(("lt", "$age", 65)),
    )


def _overlay() -> FactOverlay:
    return FactOverlay(rule_actions=(_action(),))


def _proof_frame() -> ProofFrameRecheckResult:
    verdict = ProofFrameConditionVerdict(
        condition_key="c0.add0:lt",
        verdict="invalidated",
        affected_action_indices=(0,),
    )
    return ProofFrameRecheckResult(
        status="invalidated",
        binding_items=(("$p", "person:alice"),),
        atom_verdicts=(verdict,),
    )


def _error(code: str = "RULE_ADD_CONDITION_ACTION_COUNT") -> ErrorDTO:
    return ErrorDTO(code=code, message="rule add condition unavailable")


class RuleAddConditionActionProtocolTests(unittest.TestCase):
    def test_action_construction(self) -> None:
        action = _action()

        self.assertEqual(action.rule_id, "person.eligible")
        self.assertEqual(action.version, "1.0")
        self.assertEqual(action.case_index, 0)
        self.assertEqual(action.added_atom.atom, ("lt", "$age", 65))

    def test_action_is_frozen(self) -> None:
        action = _action()
        with self.assertRaises(FrozenInstanceError):
            action.case_index = 1  # type: ignore[misc]

    def test_action_rejects_bad_shape(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            AddedCondition(())  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            AddedCondition((1, "$age", 65))  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            RuleAddConditionAction(
                rule_id="person.eligible",
                version="1.0",
                case_index=-1,
                added_atom=AddedCondition(("lt", "$age", 65)),
            )
        with self.assertRaises(ProtocolShapeError):
            RuleAddConditionAction(
                rule_id="person.eligible",
                version="1.0",
                case_index=0,
                added_atom=object(),  # type: ignore[arg-type]
            )

    def test_evaluation_overlay_accepts_rule_add_condition_action(self) -> None:
        overlay = FactOverlay(rule_actions=(_action(),))

        self.assertEqual(overlay.rule_actions, (_action(),))


class RuleAddConditionRequestProtocolTests(unittest.TestCase):
    def test_request_construction(self) -> None:
        request = RuleAddConditionRequest(
            rule_spec=_rule_spec(),
            support_artifact=_artifact(),
            overlay=_overlay(),
        )

        self.assertEqual(request.rule_spec, _rule_spec())
        self.assertEqual(request.support_artifact, _artifact())
        self.assertEqual(request.overlay, _overlay())

    def test_request_is_frozen(self) -> None:
        request = RuleAddConditionRequest(_rule_spec(), _artifact(), _overlay())
        with self.assertRaises(FrozenInstanceError):
            request.overlay = FactOverlay()  # type: ignore[misc]

    def test_request_rejects_wrong_types(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            RuleAddConditionRequest(object(), _artifact(), _overlay())  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            RuleAddConditionRequest(_rule_spec(), object(), _overlay())  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            RuleAddConditionRequest(_rule_spec(), _artifact(), object())  # type: ignore[arg-type]


class RuleAddConditionResultProtocolTests(unittest.TestCase):
    def test_completed_result_construction(self) -> None:
        result = RuleAddConditionResult(
            status="completed",
            variant_rows=((("$p", "person:alice"),),),
            proof_frame=_proof_frame(),
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.variant_rows, ((("$p", "person:alice"),),))
        self.assertEqual(result.errors, ())
        self.assertEqual(result.warnings, ())

    def test_completed_result_normalizes_variant_rows(self) -> None:
        result = RuleAddConditionResult(
            status="completed",
            variant_rows=((("$z", 1), ("$a", 2)),),
            proof_frame=_proof_frame(),
        )

        self.assertEqual(result.variant_rows, ((("$a", 2), ("$z", 1)),))

    def test_completed_requires_proof_frame_and_no_errors(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            RuleAddConditionResult(
                status="completed",
                variant_rows=(),
                proof_frame=None,
            )
        with self.assertRaises(ProtocolShapeError):
            RuleAddConditionResult(
                status="completed",
                variant_rows=(),
                proof_frame=_proof_frame(),
                errors=(_error(),),
            )

    def test_unsupported_and_invalid_request_require_errors_only(self) -> None:
        for status in ("unsupported", "invalid_request"):
            with self.subTest(status=status):
                result = RuleAddConditionResult(
                    status=status,  # type: ignore[arg-type]
                    variant_rows=(),
                    proof_frame=None,
                    errors=(_error(),),
                )
                self.assertEqual(result.status, status)

                with self.assertRaises(ProtocolShapeError):
                    RuleAddConditionResult(
                        status=status,  # type: ignore[arg-type]
                        variant_rows=(),
                        proof_frame=None,
                    )
                with self.assertRaises(ProtocolShapeError):
                    RuleAddConditionResult(
                        status=status,  # type: ignore[arg-type]
                        variant_rows=((("$p", "person:alice"),),),
                        proof_frame=None,
                        errors=(_error(),),
                    )
                with self.assertRaises(ProtocolShapeError):
                    RuleAddConditionResult(
                        status=status,  # type: ignore[arg-type]
                        variant_rows=(),
                        proof_frame=_proof_frame(),
                        errors=(_error(),),
                    )

    def test_result_rejects_bad_shape(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            RuleAddConditionResult(
                status="maybe",  # type: ignore[arg-type]
                variant_rows=(),
                proof_frame=None,
                errors=(_error(),),
            )
        for bad_row in (
            (("$p", "person:alice"), ("$p", "person:bob")),
            (("p", "person:alice"),),
            (("$", "person:alice"),),
        ):
            with self.subTest(bad_row=bad_row):
                with self.assertRaises(ProtocolShapeError):
                    RuleAddConditionResult(
                        status="completed",
                        variant_rows=(bad_row,),
                        proof_frame=_proof_frame(),
                    )


class RuleAddConditionProtocolStaticInvariantTests(unittest.TestCase):
    def test_status_literal_exact_members(self) -> None:
        self.assertEqual(
            set(typing.get_args(RuleAddConditionStatus)),
            {"completed", "unsupported", "invalid_request"},
        )

    def test_dataclass_surfaces_are_exact(self) -> None:
        self.assertEqual(
            [field.name for field in dataclasses.fields(RuleAddConditionRequest)],
            ["rule_spec", "support_artifact", "overlay"],
        )
        self.assertEqual(
            [field.name for field in dataclasses.fields(RuleAddConditionResult)],
            ["status", "variant_rows", "proof_frame", "errors", "warnings"],
        )

    def test_protocol_package_exports_rule_add_condition_types(self) -> None:
        self.assertIs(protocol_pkg.AddedCondition, AddedCondition)
        self.assertIs(protocol_pkg.RuleAddConditionAction, RuleAddConditionAction)
        self.assertIs(protocol_pkg.RuleAddConditionRequest, RuleAddConditionRequest)
        self.assertIs(protocol_pkg.RuleAddConditionResult, RuleAddConditionResult)

    def test_module_exports_expected_symbols(self) -> None:
        self.assertEqual(
            set(add_protocol.__all__),
            {
                "RuleAddConditionRequest",
                "RuleAddConditionResult",
                "RuleAddConditionStatus",
            },
        )


if __name__ == "__main__":
    unittest.main()
