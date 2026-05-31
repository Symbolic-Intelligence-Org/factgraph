"""Rule Literal Replace protocol shape tests."""

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
    ConditionPath,
    RuleLiteralReplaceAction,
    RuleLiteralReplaceRequest,
    RuleLiteralReplaceResult,
    RuleLiteralReplaceStatus,
)
from factgraph.application.protocol import rule_literal_replace as replace_protocol
from factgraph.core.rules.rule_ir import RuleSpec
from factgraph.core.store._support import PredWitness, ProofReceipt


def _rule_spec() -> RuleSpec:
    return RuleSpec(
        rule_id="person.eligible",
        version="1.0",
        select_vars=["$p"],
        where=[("pred", "Person:exists", ["$p"]), ("eq", "$region", "us")],
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


def _action() -> RuleLiteralReplaceAction:
    return RuleLiteralReplaceAction(
        rule_id="person.eligible",
        version="1.0",
        case_index=0,
        condition_index=1,
        literal_path=ConditionPath(kind="rhs"),
        old_literal="us",
        new_literal="eu",
    )


def _overlay() -> FactOverlay:
    return FactOverlay(rule_actions=(_action(),))


def _proof_frame() -> ProofFrameRecheckResult:
    verdict = ProofFrameConditionVerdict(
        condition_key="c0.c1:eq",
        verdict="invalidated",
        affected_action_indices=(0,),
    )
    return ProofFrameRecheckResult(
        status="invalidated",
        binding_items=(("$p", "person:alice"),),
        atom_verdicts=(verdict,),
    )


def _error(code: str = "RULE_LITERAL_REPLACE_ACTION_COUNT") -> ErrorDTO:
    return ErrorDTO(code=code, message="rule literal replace unavailable")


class RuleLiteralReplaceRequestProtocolTests(unittest.TestCase):
    def test_request_construction(self) -> None:
        request = RuleLiteralReplaceRequest(
            rule_spec=_rule_spec(),
            support_artifact=_artifact(),
            overlay=_overlay(),
        )

        self.assertEqual(request.rule_spec, _rule_spec())
        self.assertEqual(request.support_artifact, _artifact())
        self.assertEqual(request.overlay, _overlay())

    def test_request_is_frozen(self) -> None:
        request = RuleLiteralReplaceRequest(_rule_spec(), _artifact(), _overlay())
        with self.assertRaises(FrozenInstanceError):
            request.overlay = FactOverlay()  # type: ignore[misc]

    def test_request_rejects_wrong_types(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            RuleLiteralReplaceRequest(object(), _artifact(), _overlay())  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            RuleLiteralReplaceRequest(_rule_spec(), object(), _overlay())  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            RuleLiteralReplaceRequest(_rule_spec(), _artifact(), object())  # type: ignore[arg-type]


class RuleLiteralReplaceResultProtocolTests(unittest.TestCase):
    def test_completed_result_construction(self) -> None:
        result = RuleLiteralReplaceResult(
            status="completed",
            variant_rows=((("$p", "person:alice"),),),
            proof_frame=_proof_frame(),
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.variant_rows, ((("$p", "person:alice"),),))
        self.assertEqual(result.errors, ())
        self.assertEqual(result.warnings, ())

    def test_completed_result_normalizes_variant_rows(self) -> None:
        result = RuleLiteralReplaceResult(
            status="completed",
            variant_rows=((("$z", 1), ("$a", 2)),),
            proof_frame=_proof_frame(),
        )

        self.assertEqual(result.variant_rows, ((("$a", 2), ("$z", 1)),))

    def test_completed_requires_proof_frame_and_no_errors(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            RuleLiteralReplaceResult(
                status="completed",
                variant_rows=(),
                proof_frame=None,
            )
        with self.assertRaises(ProtocolShapeError):
            RuleLiteralReplaceResult(
                status="completed",
                variant_rows=(),
                proof_frame=_proof_frame(),
                errors=(_error(),),
            )

    def test_unsupported_and_invalid_request_require_errors_only(self) -> None:
        for status in ("unsupported", "invalid_request"):
            with self.subTest(status=status):
                result = RuleLiteralReplaceResult(
                    status=status,  # type: ignore[arg-type]
                    variant_rows=(),
                    proof_frame=None,
                    errors=(_error(),),
                )
                self.assertEqual(result.status, status)

                with self.assertRaises(ProtocolShapeError):
                    RuleLiteralReplaceResult(
                        status=status,  # type: ignore[arg-type]
                        variant_rows=(),
                        proof_frame=None,
                    )
                with self.assertRaises(ProtocolShapeError):
                    RuleLiteralReplaceResult(
                        status=status,  # type: ignore[arg-type]
                        variant_rows=((("$p", "person:alice"),),),
                        proof_frame=None,
                        errors=(_error(),),
                    )
                with self.assertRaises(ProtocolShapeError):
                    RuleLiteralReplaceResult(
                        status=status,  # type: ignore[arg-type]
                        variant_rows=(),
                        proof_frame=_proof_frame(),
                        errors=(_error(),),
                    )

    def test_result_rejects_bad_shape(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            RuleLiteralReplaceResult(
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
                    RuleLiteralReplaceResult(
                        status="completed",
                        variant_rows=(bad_row,),
                        proof_frame=_proof_frame(),
                    )


class RuleLiteralReplaceProtocolStaticInvariantTests(unittest.TestCase):
    def test_status_literal_exact_members(self) -> None:
        self.assertEqual(
            set(typing.get_args(RuleLiteralReplaceStatus)),
            {"completed", "unsupported", "invalid_request"},
        )

    def test_dataclass_surfaces_are_exact(self) -> None:
        self.assertEqual(
            [field.name for field in dataclasses.fields(RuleLiteralReplaceRequest)],
            ["rule_spec", "support_artifact", "overlay"],
        )
        self.assertEqual(
            [field.name for field in dataclasses.fields(RuleLiteralReplaceResult)],
            ["status", "variant_rows", "proof_frame", "errors", "warnings"],
        )

    def test_protocol_package_exports_rule_literal_replace_types(self) -> None:
        self.assertIs(protocol_pkg.ConditionPath, ConditionPath)
        self.assertIs(protocol_pkg.RuleLiteralReplaceAction, RuleLiteralReplaceAction)
        self.assertIs(protocol_pkg.RuleLiteralReplaceRequest, RuleLiteralReplaceRequest)
        self.assertIs(protocol_pkg.RuleLiteralReplaceResult, RuleLiteralReplaceResult)

    def test_module_exports_expected_symbols(self) -> None:
        self.assertEqual(
            set(replace_protocol.__all__),
            {
                "RuleLiteralReplaceRequest",
                "RuleLiteralReplaceResult",
                "RuleLiteralReplaceStatus",
            },
        )


if __name__ == "__main__":
    unittest.main()
