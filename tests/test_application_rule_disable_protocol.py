"""Rule Disable protocol shape tests."""

from __future__ import annotations

import dataclasses
import typing
import unittest
from dataclasses import FrozenInstanceError

from factpy.application import protocol as protocol_pkg
from factpy.application.protocol import (
    ErrorDTO,
    EvaluationOverlay,
    ProofFrameAtomVerdict,
    ProofFrameRecheckResult,
    ProtocolShapeError,
    RuleDisableAction,
    RuleDisableRequest,
    RuleDisableResult,
    RuleDisableStatus,
)
from factpy.application.protocol import rule_disable as rule_disable_protocol
from factpy.core.rules.rule_ir import RuleSpec
from factpy.core.store._support import PredWitness, SupportArtifact


def _rule_spec() -> RuleSpec:
    return RuleSpec(
        rule_id="person.eligible",
        version="1.0",
        select_vars=["$p"],
        where=[("pred", "Person:exists", ["$p"])],
    )


def _artifact(**kwargs: object) -> SupportArtifact:
    fields = {
        "kind": "native_binding_v1",
        "root_result_kind": "row",
        "binding_items": (("$p", "person:alice"),),
        "pred_witnesses": (
            PredWitness(pred_atom_key="b0.a0:Person:exists", asrt_ids=("a1",)),
        ),
    }
    fields.update(kwargs)
    return SupportArtifact(**fields)  # type: ignore[arg-type]


def _action() -> RuleDisableAction:
    return RuleDisableAction(
        rule_id="person.eligible",
        version="1.0",
        branch_index=0,
        atom_index=0,
    )


def _overlay() -> EvaluationOverlay:
    return EvaluationOverlay(rule_actions=(_action(),))


def _proof_frame() -> ProofFrameRecheckResult:
    verdict = ProofFrameAtomVerdict(
        atom_key="b0.a0:Person:exists",
        verdict="invalidated",
        affected_action_indices=(0,),
    )
    return ProofFrameRecheckResult(
        status="invalidated",
        binding_items=(("$p", "person:alice"),),
        atom_verdicts=(verdict,),
    )


def _error(code: str = "RULE_DISABLE_ACTION_COUNT") -> ErrorDTO:
    return ErrorDTO(code=code, message="rule disable unavailable")


class RuleDisableRequestProtocolTests(unittest.TestCase):
    def test_request_construction(self) -> None:
        request = RuleDisableRequest(
            rule_spec=_rule_spec(),
            support_artifact=_artifact(),
            overlay=_overlay(),
        )

        self.assertEqual(request.rule_spec, _rule_spec())
        self.assertEqual(request.support_artifact, _artifact())
        self.assertEqual(request.overlay, _overlay())

    def test_request_is_frozen(self) -> None:
        request = RuleDisableRequest(_rule_spec(), _artifact(), _overlay())
        with self.assertRaises(FrozenInstanceError):
            request.overlay = EvaluationOverlay()  # type: ignore[misc]

    def test_request_rejects_wrong_types(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            RuleDisableRequest(object(), _artifact(), _overlay())  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            RuleDisableRequest(_rule_spec(), object(), _overlay())  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            RuleDisableRequest(_rule_spec(), _artifact(), object())  # type: ignore[arg-type]


class RuleDisableResultProtocolTests(unittest.TestCase):
    def test_completed_result_construction(self) -> None:
        result = RuleDisableResult(
            status="completed",
            variant_rows=((("$p", "person:alice"),),),
            proof_frame=_proof_frame(),
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.variant_rows, ((("$p", "person:alice"),),))
        self.assertEqual(result.errors, ())
        self.assertEqual(result.warnings, ())

    def test_completed_result_normalizes_variant_rows(self) -> None:
        result = RuleDisableResult(
            status="completed",
            variant_rows=((("$z", 1), ("$a", 2)),),
            proof_frame=_proof_frame(),
        )

        self.assertEqual(result.variant_rows, ((("$a", 2), ("$z", 1)),))

    def test_completed_requires_proof_frame_and_no_errors(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            RuleDisableResult(
                status="completed",
                variant_rows=(),
                proof_frame=None,
            )
        with self.assertRaises(ProtocolShapeError):
            RuleDisableResult(
                status="completed",
                variant_rows=(),
                proof_frame=_proof_frame(),
                errors=(_error(),),
            )

    def test_unsupported_and_invalid_request_require_errors_only(self) -> None:
        for status in ("unsupported", "invalid_request"):
            with self.subTest(status=status):
                result = RuleDisableResult(
                    status=status,  # type: ignore[arg-type]
                    variant_rows=(),
                    proof_frame=None,
                    errors=(_error(),),
                )
                self.assertEqual(result.status, status)

                with self.assertRaises(ProtocolShapeError):
                    RuleDisableResult(
                        status=status,  # type: ignore[arg-type]
                        variant_rows=(),
                        proof_frame=None,
                    )
                with self.assertRaises(ProtocolShapeError):
                    RuleDisableResult(
                        status=status,  # type: ignore[arg-type]
                        variant_rows=((("$p", "person:alice"),),),
                        proof_frame=None,
                        errors=(_error(),),
                    )
                with self.assertRaises(ProtocolShapeError):
                    RuleDisableResult(
                        status=status,  # type: ignore[arg-type]
                        variant_rows=(),
                        proof_frame=_proof_frame(),
                        errors=(_error(),),
                    )

    def test_result_rejects_bad_shape(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            RuleDisableResult(
                status="maybe",  # type: ignore[arg-type]
                variant_rows=(),
                proof_frame=None,
                errors=(_error(),),
            )
        with self.assertRaises(ProtocolShapeError):
            RuleDisableResult(
                status="completed",
                variant_rows=[(("$p", "person:alice"),)],  # type: ignore[arg-type]
                proof_frame=_proof_frame(),
            )
        for bad_row in (
            (("$p", "person:alice"), ("$p", "person:bob")),
            (("p", "person:alice"),),
            (("$", "person:alice"),),
        ):
            with self.subTest(bad_row=bad_row):
                with self.assertRaises(ProtocolShapeError):
                    RuleDisableResult(
                        status="completed",
                        variant_rows=(bad_row,),
                        proof_frame=_proof_frame(),
                    )
        with self.assertRaises(ProtocolShapeError):
            RuleDisableResult(
                status="completed",
                variant_rows=(),
                proof_frame=_proof_frame(),
                errors=(object(),),  # type: ignore[arg-type]
            )


class RuleDisableProtocolStaticInvariantTests(unittest.TestCase):
    def test_status_literal_exact_members(self) -> None:
        self.assertEqual(
            set(typing.get_args(RuleDisableStatus)),
            {"completed", "unsupported", "invalid_request"},
        )

    def test_dataclass_surfaces_are_exact(self) -> None:
        self.assertEqual(
            [field.name for field in dataclasses.fields(RuleDisableRequest)],
            ["rule_spec", "support_artifact", "overlay"],
        )
        self.assertEqual(
            [field.name for field in dataclasses.fields(RuleDisableResult)],
            ["status", "variant_rows", "proof_frame", "errors", "warnings"],
        )

    def test_protocol_package_exports_rule_disable_types(self) -> None:
        self.assertIs(protocol_pkg.RuleDisableAction, RuleDisableAction)
        self.assertIs(protocol_pkg.RuleDisableRequest, RuleDisableRequest)
        self.assertIs(protocol_pkg.RuleDisableResult, RuleDisableResult)

    def test_module_exports_expected_symbols(self) -> None:
        self.assertEqual(
            set(rule_disable_protocol.__all__),
            {"RuleDisableRequest", "RuleDisableResult", "RuleDisableStatus"},
        )


if __name__ == "__main__":
    unittest.main()
