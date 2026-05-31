"""Diagnose protocol shape tests (blueprint §7.2 + §8 Step 1).

Each test class enforces a Step 0.B D-decision or §7-Diagnose-N anti-regression
gate. Tests target the DTOs only — no runtime behavior.
"""
from __future__ import annotations

import typing
import unittest

from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DiagnoseConditionLocator,
    DiagnoseFailureKind,
    DiagnoseRequest,
    DiagnoseResult,
    DiagnoseStatus,
    ErrorDTO,
    EvidenceEnvelope,
    ProtocolShapeError,
)
from factgraph.core.store._support import ProvenanceEnvelope, ProofReceipt


def _head(target: str = "doc:eligible", vars_: tuple[str, ...] = ("$doc",)) -> CompiledHeadCall:
    return CompiledHeadCall(target_pred_id=target, head_var_names=vars_)


def _plan(*, heads: tuple[CompiledHeadCall, ...] | None = None) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="drv.diagnose",
        version="1.0",
        body_ir=[("pred", "doc:risk", ["$doc", "$risk"]), ("eq", "$risk", "high")],
        heads=heads if heads is not None else (_head(),),
    )


def _binding() -> tuple[tuple[str, object], ...]:
    return (("$doc", "d-1"), ("$risk", "high"))


def _partial_binding() -> tuple[tuple[str, object], ...]:
    return (("$doc", "d-1"),)


def _error(code: str = "EVIDENCE_LOOKUP_MISS") -> ErrorDTO:
    return ErrorDTO(code=code, message="evidence lookup miss")


def _atom_locator() -> DiagnoseConditionLocator:
    return DiagnoseConditionLocator(
        branch_index=0,
        failed_atom_index=1,
        attempted_binding=_partial_binding(),
    )


class DiagnoseAtomLocatorProtocolTests(unittest.TestCase):
    def test_atom_locator_construction(self) -> None:
        loc = _atom_locator()
        self.assertEqual(loc.branch_index, 0)
        self.assertEqual(loc.failed_atom_index, 1)
        self.assertEqual(loc.attempted_binding, _partial_binding())

    def test_atom_locator_negative_branch_rejected(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseConditionLocator(
                branch_index=-1,
                failed_atom_index=0,
                attempted_binding=_partial_binding(),
            )

    def test_atom_locator_negative_atom_index_rejected(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseConditionLocator(
                branch_index=0,
                failed_atom_index=-1,
                attempted_binding=_partial_binding(),
            )

    def test_atom_locator_invalid_binding_rejected(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseConditionLocator(
                branch_index=0,
                failed_atom_index=0,
                attempted_binding=(("doc", "d-1"),),  # missing $-prefix
            )

    def test_atom_locator_is_capability_output_not_in_evidence_envelope(self) -> None:
        # §7-Diagnose-2: DiagnoseConditionLocator must NOT be accepted by
        # EvidenceEnvelope.engine_payload (which is ProofReceipt | ProvenanceEnvelope only).
        with self.assertRaises(ProtocolShapeError):
            EvidenceEnvelope(
                engine="native",
                support_kind="native_binding_v1",
                support_digest="sha256:" + ("1" * 64),
                branch_index=0,
                engine_payload=_atom_locator(),  # type: ignore[arg-type]
            )


class DiagnoseRequestProtocolTests(unittest.TestCase):
    def test_request_complete_binding_construction(self) -> None:
        req = DiagnoseRequest(plan=_plan(), binding=_binding(), engine="native")
        self.assertEqual(req.binding, _binding())
        self.assertEqual(req.engine, "native")

    def test_request_partial_binding_construction(self) -> None:
        req = DiagnoseRequest(plan=_plan(), binding=_partial_binding(), engine="native")
        self.assertEqual(req.binding, _partial_binding())

    def test_binding_dollar_prefix_violation(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseRequest(plan=_plan(), binding=(("doc", "d-1"),), engine="native")

    def test_binding_duplicate_key_rejection(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseRequest(
                plan=_plan(),
                binding=(("$doc", "d-1"), ("$doc", "d-2")),
                engine="native",
            )

    def test_binding_wrong_container_type(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseRequest(plan=_plan(), binding={"$doc": "d-1"}, engine="native")  # type: ignore[arg-type]

    def test_engine_literal_validation(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseRequest(plan=_plan(), binding=_binding(), engine="lambda")  # type: ignore[arg-type]

    def test_engine_required_no_default(self) -> None:
        with self.assertRaises(TypeError):
            DiagnoseRequest(plan=_plan(), binding=_binding())  # type: ignore[call-arg]

    def test_request_rejects_store_field(self) -> None:
        with self.assertRaises(TypeError):
            DiagnoseRequest(
                plan=_plan(),
                binding=_binding(),
                engine="native",
                store=object(),  # type: ignore[call-arg]
            )

    def test_request_rejects_registry_field(self) -> None:
        with self.assertRaises(TypeError):
            DiagnoseRequest(
                plan=_plan(),
                binding=_binding(),
                engine="native",
                registry=object(),  # type: ignore[call-arg]
            )

    def test_request_rejects_diagnostic_mode_field(self) -> None:
        # D4: no diagnostic_mode field in MVP request DTO
        with self.assertRaises(TypeError):
            DiagnoseRequest(
                plan=_plan(),
                binding=_binding(),
                engine="native",
                diagnostic_mode="atom_localized",  # type: ignore[call-arg]
            )

    def test_request_rejects_engine_options_field(self) -> None:
        # §6.4: no request-level engine_options
        with self.assertRaises(TypeError):
            DiagnoseRequest(
                plan=_plan(),
                binding=_binding(),
                engine="native",
                engine_options={"solver_mode": "fast"},  # type: ignore[call-arg]
            )

    def test_multi_head_plan_rejection(self) -> None:
        plan = _plan(heads=(_head("doc:a"), _head("doc:b")))
        with self.assertRaises(ProtocolShapeError):
            DiagnoseRequest(plan=plan, binding=_binding(), engine="native")


class DiagnoseResultPassedTests(unittest.TestCase):
    def test_passed_nullable_matrix(self) -> None:
        result = DiagnoseResult(
            status="passed",
            requested_binding=_partial_binding(),
            matched_count=1,
            matched_binding=_binding(),
            failure_kind=None,
            diagnostic_payload=None,
        )
        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.matched_binding, _binding())
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)

    def test_passed_requires_matched_count_at_least_one(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="passed",
                requested_binding=_partial_binding(),
                matched_count=0,
                matched_binding=_binding(),
                failure_kind=None,
                diagnostic_payload=None,
            )

    def test_passed_requires_matched_binding(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="passed",
                requested_binding=_partial_binding(),
                matched_count=1,
                matched_binding=None,
                failure_kind=None,
                diagnostic_payload=None,
            )

    def test_passed_rejects_failure_kind(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="passed",
                requested_binding=_partial_binding(),
                matched_count=1,
                matched_binding=_binding(),
                failure_kind="no_candidate",
                diagnostic_payload=None,
            )

    def test_passed_rejects_diagnostic_payload(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="passed",
                requested_binding=_partial_binding(),
                matched_count=1,
                matched_binding=_binding(),
                failure_kind=None,
                diagnostic_payload=_atom_locator(),
            )


class DiagnoseResultFailedTests(unittest.TestCase):
    def test_failed_no_candidate_nullable_matrix(self) -> None:
        result = DiagnoseResult(
            status="failed",
            requested_binding=_partial_binding(),
            matched_count=0,
            matched_binding=None,
            failure_kind="no_candidate",
            diagnostic_payload=None,
        )
        self.assertEqual(result.matched_count, 0)
        self.assertIsNone(result.matched_binding)
        self.assertEqual(result.failure_kind, "no_candidate")
        self.assertIsNone(result.diagnostic_payload)

    def test_failed_atom_localized_nullable_matrix(self) -> None:
        result = DiagnoseResult(
            status="failed",
            requested_binding=_partial_binding(),
            matched_count=0,
            matched_binding=None,
            failure_kind="atom_localized",
            diagnostic_payload=_atom_locator(),
        )
        self.assertEqual(result.failure_kind, "atom_localized")
        self.assertIsInstance(result.diagnostic_payload, DiagnoseConditionLocator)

    def test_failed_requires_failure_kind(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="failed",
                requested_binding=_partial_binding(),
                matched_count=0,
                matched_binding=None,
                failure_kind=None,
                diagnostic_payload=None,
            )

    def test_failed_no_candidate_rejects_diagnostic_payload(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="failed",
                requested_binding=_partial_binding(),
                matched_count=0,
                matched_binding=None,
                failure_kind="no_candidate",
                diagnostic_payload=_atom_locator(),
            )

    def test_failed_atom_localized_requires_diagnostic_payload(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="failed",
                requested_binding=_partial_binding(),
                matched_count=0,
                matched_binding=None,
                failure_kind="atom_localized",
                diagnostic_payload=None,
            )

    def test_failed_requires_matched_count_zero(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="failed",
                requested_binding=_partial_binding(),
                matched_count=None,
                matched_binding=None,
                failure_kind="no_candidate",
                diagnostic_payload=None,
            )

    def test_failed_rejects_matched_binding(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="failed",
                requested_binding=_partial_binding(),
                matched_count=0,
                matched_binding=_binding(),
                failure_kind="no_candidate",
                diagnostic_payload=None,
            )


class DiagnoseResultUnsupportedTests(unittest.TestCase):
    def test_unsupported_evidence_unavailable_nullable_matrix(self) -> None:
        # §7-Diagnose-1: evidence-unavailable maps to status="unsupported"
        # with EVIDENCE_LOOKUP_MISS (NOT failed with hypothetical
        # failure_kind="evidence_unavailable").
        result = DiagnoseResult(
            status="unsupported",
            requested_binding=_partial_binding(),
            matched_count=None,
            matched_binding=None,
            failure_kind=None,
            diagnostic_payload=None,
            errors=(_error("EVIDENCE_LOOKUP_MISS"),),
        )
        self.assertEqual(result.status, "unsupported")
        self.assertIsNone(result.failure_kind)
        self.assertEqual(result.errors[0].code, "EVIDENCE_LOOKUP_MISS")

    def test_unsupported_representability_nullable_matrix(self) -> None:
        result = DiagnoseResult(
            status="unsupported",
            requested_binding=_partial_binding(),
            matched_count=None,
            matched_binding=None,
            failure_kind=None,
            diagnostic_payload=None,
            errors=(_error("BINDING_NOT_REPRESENTABLE"),),
        )
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE")

    def test_unsupported_requires_errors(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="unsupported",
                requested_binding=_partial_binding(),
                matched_count=None,
                matched_binding=None,
                failure_kind=None,
                diagnostic_payload=None,
            )

    def test_unsupported_rejects_failure_kind(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="unsupported",
                requested_binding=_partial_binding(),
                matched_count=None,
                matched_binding=None,
                failure_kind="no_candidate",
                diagnostic_payload=None,
                errors=(_error(),),
            )

    def test_unsupported_rejects_matched_count(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="unsupported",
                requested_binding=_partial_binding(),
                matched_count=0,
                matched_binding=None,
                failure_kind=None,
                diagnostic_payload=None,
                errors=(_error(),),
            )


class DiagnoseResultInvalidRequestTests(unittest.TestCase):
    def test_invalid_request_nullable_matrix(self) -> None:
        result = DiagnoseResult(
            status="invalid_request",
            requested_binding=_partial_binding(),
            matched_count=None,
            matched_binding=None,
            failure_kind=None,
            diagnostic_payload=None,
            errors=(_error("UNKNOWN_VARIABLE_IN_BINDING"),),
        )
        self.assertEqual(result.errors[0].code, "UNKNOWN_VARIABLE_IN_BINDING")

    def test_invalid_request_requires_errors(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="invalid_request",
                requested_binding=_partial_binding(),
                matched_count=None,
                matched_binding=None,
                failure_kind=None,
                diagnostic_payload=None,
            )


class DiagnoseStatusEnumInvarianceTests(unittest.TestCase):
    """§7-Diagnose-7: status Literal contains exactly Check's 4 values, no 5th."""

    def test_status_literal_exact_members(self) -> None:
        members = set(typing.get_args(DiagnoseStatus))
        self.assertEqual(
            members,
            {"passed", "failed", "unsupported", "invalid_request"},
        )

    def test_failure_kind_literal_exact_members(self) -> None:
        # §7-Diagnose-1 corollary: no `evidence_unavailable` enum value;
        # failure_kind Literal is exactly {no_candidate, atom_localized}.
        members = set(typing.get_args(DiagnoseFailureKind))
        self.assertEqual(members, {"no_candidate", "atom_localized"})

    def test_status_rejects_fifth_value(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            DiagnoseResult(
                status="evidence_unavailable",  # type: ignore[arg-type]
                requested_binding=_partial_binding(),
                matched_count=None,
                matched_binding=None,
                failure_kind=None,
                diagnostic_payload=None,
                errors=(_error(),),
            )


class DiagnoseAtomLocatorEvidenceEnvelopeIsolationTests(unittest.TestCase):
    """§7-Diagnose-2: Check's EvidenceEnvelope.engine_payload Union is unchanged.

    Verifies that adding DiagnoseConditionLocator did not widen the Union; the
    Union members remain exactly {ProofReceipt, ProvenanceEnvelope}.
    """

    def test_engine_payload_accepts_support_artifact(self) -> None:
        artifact = ProofReceipt(
            kind="native_binding_v1",
            root_result_kind="fact",
            binding_items=_binding(),
            pred_witnesses=(),
        )
        env = EvidenceEnvelope(
            engine="native",
            support_kind="native_binding_v1",
            support_digest="sha256:" + ("1" * 64),
            branch_index=0,
            engine_payload=artifact,
        )
        self.assertIsInstance(env.engine_payload, ProofReceipt)

    def test_engine_payload_accepts_provenance_envelope(self) -> None:
        envelope = ProvenanceEnvelope(
            candidate_id="cand_v2:diagnose-test",
            engine="problog",
            payload_type="proof_graph",
            payload={"nodes": []},
        )
        env = EvidenceEnvelope(
            engine="problog",
            support_kind="problog_provenance_v1",
            support_digest="sha256:" + ("2" * 64),
            branch_index=None,
            engine_payload=envelope,
        )
        self.assertIsInstance(env.engine_payload, ProvenanceEnvelope)

    def test_engine_payload_rejects_atom_locator(self) -> None:
        # Already covered by DiagnoseAtomLocatorProtocolTests but kept here
        # as the §7-Diagnose-2 anti-regression anchor for clarity.
        with self.assertRaises(ProtocolShapeError):
            EvidenceEnvelope(
                engine="native",
                support_kind="native_binding_v1",
                support_digest="sha256:" + ("1" * 64),
                branch_index=0,
                engine_payload=_atom_locator(),  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
