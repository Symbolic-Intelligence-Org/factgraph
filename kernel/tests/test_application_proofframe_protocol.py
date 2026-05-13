"""ProofFrame Rechecker protocol shape tests."""

from __future__ import annotations

import dataclasses
import unittest
from dataclasses import FrozenInstanceError

from kernel.application import protocol as protocol_pkg
from kernel.application.protocol import (
    EvaluationOverlay,
    FactValueOverride,
    ProofFrameAtomVerdict,
    ProofFrameRecheckRequest,
    ProofFrameRecheckResult,
    ProtocolShapeError,
    aggregate_proof_frame_status,
)
from kernel.application.protocol import proofframe as proofframe_protocol
from kernel.core.store._support import PredWitness, SupportArtifact


def _artifact(**kwargs: object) -> SupportArtifact:
    fields = {
        "kind": "native_binding_v1",
        "root_result_kind": "row",
        "binding_items": (("$p", "person:alice"),),
        "pred_witnesses": (
            PredWitness(pred_atom_key="b0.a0:Person.age", asrt_ids=("a1",)),
        ),
    }
    fields.update(kwargs)
    return SupportArtifact(**fields)  # type: ignore[arg-type]


def _overlay() -> EvaluationOverlay:
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


def _verdict(
    *,
    atom_key: str = "b0.a0:Person.age",
    verdict: str = "still_valid",
    affected_action_indices: tuple[int, ...] = (),
) -> ProofFrameAtomVerdict:
    return ProofFrameAtomVerdict(
        atom_key=atom_key,
        verdict=verdict,  # type: ignore[arg-type]
        affected_action_indices=affected_action_indices,
    )


class ProofFrameRecheckRequestProtocolTests(unittest.TestCase):
    def test_request_construction(self) -> None:
        request = ProofFrameRecheckRequest(
            support_artifact=_artifact(),
            overlay=_overlay(),
        )

        self.assertEqual(request.support_artifact, _artifact())
        self.assertEqual(request.overlay, _overlay())

    def test_request_is_frozen(self) -> None:
        request = ProofFrameRecheckRequest(_artifact(), _overlay())
        with self.assertRaises(FrozenInstanceError):
            request.overlay = EvaluationOverlay(fact_actions=())  # type: ignore[misc]

    def test_request_rejects_wrong_types(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            ProofFrameRecheckRequest(object(), _overlay())  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            ProofFrameRecheckRequest(_artifact(), object())  # type: ignore[arg-type]


class ProofFrameAtomVerdictProtocolTests(unittest.TestCase):
    def test_atom_verdict_construction(self) -> None:
        verdict = _verdict(verdict="invalidated", affected_action_indices=(0, 2))

        self.assertEqual(verdict.atom_key, "b0.a0:Person.age")
        self.assertEqual(verdict.verdict, "invalidated")
        self.assertEqual(verdict.affected_action_indices, (0, 2))

    def test_atom_verdict_is_frozen(self) -> None:
        verdict = _verdict()
        with self.assertRaises(FrozenInstanceError):
            verdict.atom_key = "other"  # type: ignore[misc]

    def test_atom_verdict_rejects_bad_shape(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _verdict(atom_key="")
        with self.assertRaises(ProtocolShapeError):
            _verdict(verdict="unsupported")
        with self.assertRaises(ProtocolShapeError):
            _verdict(affected_action_indices=[0])  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            _verdict(affected_action_indices=(1, 0))
        with self.assertRaises(ProtocolShapeError):
            _verdict(affected_action_indices=(0, 0))


class ProofFrameRecheckResultProtocolTests(unittest.TestCase):
    def test_result_construction(self) -> None:
        atom_verdicts = (_verdict(verdict="unknown"),)
        result = ProofFrameRecheckResult(
            status="unknown",
            binding_items=(("$p", "person:alice"),),
            atom_verdicts=atom_verdicts,
        )

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.binding_items, (("$p", "person:alice"),))
        self.assertEqual(result.atom_verdicts, atom_verdicts)

    def test_result_normalizes_binding_items(self) -> None:
        result = ProofFrameRecheckResult(
            status="still_valid",
            binding_items=(("$z", 1), ("$a", 2)),
            atom_verdicts=(_verdict(),),
        )

        self.assertEqual(result.binding_items, (("$a", 2), ("$z", 1)))

    def test_result_enforces_aggregation_invariant(self) -> None:
        atom_verdicts = (
            _verdict(atom_key="b0.a0:Person.age", verdict="still_valid"),
            _verdict(atom_key="b0.a1:not", verdict="unknown"),
        )

        with self.assertRaises(ProtocolShapeError):
            ProofFrameRecheckResult(
                status="still_valid",
                binding_items=(("$p", "person:alice"),),
                atom_verdicts=atom_verdicts,
            )

    def test_result_empty_atom_verdicts_aggregate_to_unknown(self) -> None:
        result = ProofFrameRecheckResult(
            status="unknown",
            binding_items=(("$p", "person:alice"),),
            atom_verdicts=(),
        )

        self.assertEqual(result.status, "unknown")

    def test_aggregate_priority(self) -> None:
        self.assertEqual(aggregate_proof_frame_status((_verdict(),)), "still_valid")
        self.assertEqual(
            aggregate_proof_frame_status(
                (
                    _verdict(atom_key="b0.a0:Person.age"),
                    _verdict(atom_key="b0.a1:not", verdict="unknown"),
                )
            ),
            "unknown",
        )
        self.assertEqual(
            aggregate_proof_frame_status(
                (
                    _verdict(atom_key="b0.a0:Person.age", verdict="invalidated"),
                    _verdict(atom_key="b0.a1:not", verdict="unknown"),
                )
            ),
            "invalidated",
        )

    def test_result_rejects_bad_shape(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            ProofFrameRecheckResult(
                status="unsupported",
                binding_items=(("$p", "person:alice"),),
                atom_verdicts=(_verdict(),),
            )
        with self.assertRaises(ProtocolShapeError):
            ProofFrameRecheckResult(
                status="still_valid",
                binding_items={"$p": "person:alice"},  # type: ignore[arg-type]
                atom_verdicts=(_verdict(),),
            )
        with self.assertRaises(ProtocolShapeError):
            ProofFrameRecheckResult(
                status="still_valid",
                binding_items=(("$p", "person:alice"),),
                atom_verdicts=[_verdict()],  # type: ignore[arg-type]
            )


class ProofFrameProtocolExportTests(unittest.TestCase):
    def test_protocol_package_exports_proofframe_types(self) -> None:
        self.assertIs(protocol_pkg.ProofFrameRecheckRequest, ProofFrameRecheckRequest)
        self.assertIs(protocol_pkg.ProofFrameRecheckResult, ProofFrameRecheckResult)
        self.assertIs(protocol_pkg.ProofFrameAtomVerdict, ProofFrameAtomVerdict)

    def test_dataclass_surface_is_exact(self) -> None:
        self.assertEqual(
            [field.name for field in dataclasses.fields(ProofFrameRecheckRequest)],
            ["support_artifact", "overlay"],
        )
        self.assertEqual(
            [field.name for field in dataclasses.fields(ProofFrameAtomVerdict)],
            ["atom_key", "verdict", "affected_action_indices"],
        )
        self.assertEqual(
            [field.name for field in dataclasses.fields(ProofFrameRecheckResult)],
            ["status", "binding_items", "atom_verdicts"],
        )

    def test_module_exports_expected_symbols(self) -> None:
        self.assertEqual(
            set(proofframe_protocol.__all__),
            {
                "ProofFrameAtomVerdict",
                "ProofFrameRecheckRequest",
                "ProofFrameRecheckResult",
                "ProofFrameStatus",
                "aggregate_proof_frame_status",
            },
        )
