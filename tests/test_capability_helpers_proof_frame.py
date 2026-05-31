"""Tests for ProofFrame capability helper builders."""

from __future__ import annotations

import unittest

from factgraph.application import (
    CapabilityHelperError,
    OriginPackageError,
    build_proof_frame_recheck_request,
)
from factgraph.application.protocol import (
    FactOverlay,
    ReplaceFact,
    ProofFrameRecheckRequest,
)
from factgraph.core.store._support import PredWitness, ProofReceipt
from factgraph.sdk import Pred, vars as sdk_vars
from factgraph.sdk.dsl import Rule


def _support(*, binding_items: tuple[tuple[str, object], ...] | None = None) -> ProofReceipt:
    return ProofReceipt(
        kind="native_binding_v1",
        root_result_kind="row",
        binding_items=binding_items if binding_items is not None else (("$p", "person:alice"),),
        pred_witnesses=(
            PredWitness(pred_atom_key="b0.a0:Person.age", asrt_ids=("a1",)),
        ),
    )


def _overlay(*, old_value: object = 25, new_value: object = 26) -> FactOverlay:
    return FactOverlay(
        fact_actions=(
            ReplaceFact(
                asrt_id="a1",
                pred_id="Person.age",
                e_ref="person:alice",
                old_fact_tuple=("person:alice", old_value),
                new_fact_tuple=("person:alice", new_value),
            ),
        )
    )


def _sdk_rule() -> Rule:
    with sdk_vars("p", "age") as (p, age):
        return Rule(
            id="helper.sdk_rule",
            version="1.0",
            select=[Pred("person:eligible", p)],
            where=[Pred("person:age", p, age)],
        )


class BuildProofFrameRecheckRequestTests(unittest.TestCase):
    def test_builds_request_with_default_empty_overlay(self) -> None:
        support = _support()

        request = build_proof_frame_recheck_request(support)

        self.assertIsInstance(request, ProofFrameRecheckRequest)
        self.assertIs(request.support_artifact, support)
        self.assertEqual(request.overlay, FactOverlay())

    def test_builds_request_with_explicit_overlay(self) -> None:
        support = _support()
        overlay = _overlay()

        request = build_proof_frame_recheck_request(support, overlay=overlay)

        self.assertIs(request.support_artifact, support)
        self.assertIs(request.overlay, overlay)

    def test_non_support_rejected_by_helper(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "ProofReceipt"):
            build_proof_frame_recheck_request(object())  # type: ignore[arg-type]

    def test_non_overlay_rejected_by_helper(self) -> None:
        with self.assertRaisesRegex(CapabilityHelperError, "FactOverlay"):
            build_proof_frame_recheck_request(_support(), overlay=object())  # type: ignore[arg-type]

    def test_sdk_object_as_support_raises_origin_package_error(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_proof_frame_recheck_request(_sdk_rule())  # type: ignore[arg-type]

    def test_sdk_object_nested_in_support_raises_origin_package_error(self) -> None:
        support = _support(binding_items=(("$rule", _sdk_rule()),))

        with self.assertRaises(OriginPackageError):
            build_proof_frame_recheck_request(support)

    def test_sdk_object_nested_in_overlay_raises_origin_package_error(self) -> None:
        with self.assertRaises(OriginPackageError):
            build_proof_frame_recheck_request(_support(), overlay=_overlay(new_value=_sdk_rule()))

    def test_phase_3_exports_from_application_and_helper_package(self) -> None:
        from factgraph import application
        from factgraph.application import capability_helpers

        self.assertIs(
            application.build_proof_frame_recheck_request,
            build_proof_frame_recheck_request,
        )
        self.assertIs(
            capability_helpers.build_proof_frame_recheck_request,
            build_proof_frame_recheck_request,
        )


if __name__ == "__main__":
    unittest.main()
