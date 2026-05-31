"""Narrative renderer tests for ProofFrame Rechecker."""

from __future__ import annotations

import unittest

from factgraph.application import render_proof_frame_narrative
from factgraph.application.protocol import (
    FactOverlay,
    RemoveFact,
    ReplaceFact,
    ProofFrameConditionVerdict,
    ProofFrameRecheckResult,
)


def _overlay() -> FactOverlay:
    return FactOverlay(
        fact_actions=(
            ReplaceFact(
                asrt_id="opaque-age-asrt",
                pred_id="Person.age",
                e_ref="person:alice",
                old_fact_tuple=("person:alice", 25),
                new_fact_tuple=("person:alice", 26),
            ),
            RemoveFact(
                asrt_id="opaque-region-asrt",
                pred_id="Person.region",
                e_ref="person:alice",
                old_fact_tuple=("person:alice", "us"),
            ),
        )
    )


class ProofFrameNarrativeTests(unittest.TestCase):
    def test_renderer_is_deterministic_and_uses_action_indices(self) -> None:
        result = ProofFrameRecheckResult(
            status="invalidated",
            binding_items=(("$p", "person:alice"),),
            atom_verdicts=(
                ProofFrameConditionVerdict(
                    atom_key="b0.a0:Person.age",
                    verdict="invalidated",
                    affected_action_indices=(0,),
                ),
                ProofFrameConditionVerdict(
                    atom_key="b0.a1:eq",
                    verdict="still_valid",
                    affected_action_indices=(),
                ),
            ),
        )

        first = render_proof_frame_narrative(result, overlay=_overlay())
        second = render_proof_frame_narrative(result, overlay=_overlay())

        self.assertEqual(first, second)
        self.assertEqual(
            first,
            "\n".join(
                [
                    "Proof frame status: invalidated.",
                    "- b0.a0:Person.age: invalidated by action #0(replace Person.age).",
                ]
            ),
        )
        self.assertNotIn("opaque-age-asrt", first)
        self.assertNotIn("opaque-region-asrt", first)
        self.assertNotIn("b0.a1:eq", first)

    def test_renderer_omits_still_valid_atom_lines(self) -> None:
        result = ProofFrameRecheckResult(
            status="still_valid",
            binding_items=(("$p", "person:alice"),),
            atom_verdicts=(
                ProofFrameConditionVerdict(
                    atom_key="b0.a0:Person.age",
                    verdict="still_valid",
                    affected_action_indices=(),
                ),
            ),
        )

        self.assertEqual(
            render_proof_frame_narrative(result, overlay=FactOverlay(fact_actions=())),
            "Proof frame status: still_valid.",
        )

    def test_renderer_handles_frame_level_unknown(self) -> None:
        result = ProofFrameRecheckResult(
            status="unknown",
            binding_items=(("$p", "person:alice"),),
            atom_verdicts=(),
        )

        self.assertEqual(
            render_proof_frame_narrative(result, overlay=FactOverlay(fact_actions=())),
            "Proof frame status: unknown.\nNo recheckable proof atoms were evaluated.",
        )

    def test_application_package_exports_renderer(self) -> None:
        from factgraph import application

        self.assertIs(application.render_proof_frame_narrative, render_proof_frame_narrative)
