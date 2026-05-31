from __future__ import annotations

import unittest

from factgraph.application.protocol import (
    CheckRequest,
    CheckResult,
    CompiledDerivationPlan,
    CompiledHeadCall,
    ErrorDTO,
    EvidenceEnvelope,
    ProtocolShapeError,
)
from factgraph.core.store._support import (
    ProvenanceEnvelope,
    ProofReceipt,
    provenance_envelope_from_dict,
    provenance_envelope_to_dict,
    support_artifact_from_dict,
    support_artifact_to_dict,
)


def _head(target: str = "doc:eligible", vars_: tuple[str, ...] = ("$doc",)) -> CompiledHeadCall:
    return CompiledHeadCall(target_pred_id=target, head_var_names=vars_)


def _plan(*, heads: tuple[CompiledHeadCall, ...] | None = None) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="drv.check",
        version="1.0",
        body_ir=[("pred", "doc:risk", ["$doc", "$risk"]), ("eq", "$risk", "high")],
        heads=heads if heads is not None else (_head(),),
    )


def _binding() -> tuple[tuple[str, object], ...]:
    return (("$doc", "d-1"), ("$risk", "high"))


def _partial_binding() -> tuple[tuple[str, object], ...]:
    return (("$doc", "d-1"),)


def _error(code: str = "BINDING_NOT_REPRESENTABLE_FOR_ENGINE") -> ErrorDTO:
    return ErrorDTO(code=code, message="not representable")


def _support_artifact() -> ProofReceipt:
    return ProofReceipt(
        kind="native_binding_v1",
        root_result_kind="fact",
        binding_items=_binding(),
        pred_witnesses=(),
    )


def _provenance_envelope() -> ProvenanceEnvelope:
    return ProvenanceEnvelope(
        candidate_id="cand_v2:test",
        engine="problog",
        payload_type="proof_graph",
        payload={"nodes": [{"id": "n1", "probability": 0.75}]},
    )


def _evidence_envelope(
    *,
    engine: str = "native",
    payload: ProofReceipt | ProvenanceEnvelope | None = None,
) -> EvidenceEnvelope:
    return EvidenceEnvelope(
        engine=engine,  # type: ignore[arg-type]
        support_kind="native_binding_v1" if payload is None or isinstance(payload, ProofReceipt) else "problog_provenance_v1",
        support_digest="sha256:" + ("1" * 64),
        case_index=0 if engine in {"native", "souffle"} else None,
        proof=payload or _support_artifact(),
    )


class CheckRequestProtocolTests(unittest.TestCase):
    def test_check_request_complete_binding_construction(self) -> None:
        req = CheckRequest(plan=_plan(), binding=_binding(), engine="native")
        self.assertEqual(req.binding, _binding())
        self.assertEqual(req.engine, "native")

    def test_check_request_partial_binding_construction(self) -> None:
        req = CheckRequest(plan=_plan(), binding=_partial_binding(), engine="native")
        self.assertEqual(req.binding, _partial_binding())

    def test_binding_dollar_prefix_violation(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            CheckRequest(plan=_plan(), binding=(("doc", "d-1"),), engine="native")

    def test_binding_duplicate_key_rejection(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            CheckRequest(
                plan=_plan(),
                binding=(("$doc", "d-1"), ("$doc", "d-2")),
                engine="native",
            )

    def test_binding_wrong_container_type(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            CheckRequest(plan=_plan(), binding={"$doc": "d-1"}, engine="native")  # type: ignore[arg-type]

    def test_engine_literal_validation(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            CheckRequest(plan=_plan(), binding=_binding(), engine="lambda")  # type: ignore[arg-type]

    def test_engine_required_no_default(self) -> None:
        with self.assertRaises(TypeError):
            CheckRequest(plan=_plan(), binding=_binding())  # type: ignore[call-arg]

    def test_check_request_rejects_store_field(self) -> None:
        with self.assertRaises(TypeError):
            CheckRequest(
                plan=_plan(),
                binding=_binding(),
                engine="native",
                store=object(),  # type: ignore[call-arg]
            )

    def test_check_request_rejects_registry_field(self) -> None:
        with self.assertRaises(TypeError):
            CheckRequest(
                plan=_plan(),
                binding=_binding(),
                engine="native",
                registry=object(),  # type: ignore[call-arg]
            )

    def test_check_request_rejects_resolutions_field(self) -> None:
        with self.assertRaises(TypeError):
            CheckRequest(
                plan=_plan(),
                binding=_binding(),
                engine="native",
                rule_ref_resolutions=(),  # type: ignore[call-arg]
            )

    def test_multi_head_plan_rejection(self) -> None:
        plan = _plan(heads=(_head("doc:a"), _head("doc:b")))
        with self.assertRaises(ProtocolShapeError):
            CheckRequest(plan=plan, binding=_binding(), engine="native")


class EvidenceEnvelopeProtocolTests(unittest.TestCase):
    def test_evidence_envelope_construction(self) -> None:
        env = _evidence_envelope(engine="problog", payload=_provenance_envelope())
        self.assertEqual(env.engine, "problog")
        self.assertIsNone(env.case_index)

    def test_evidence_envelope_accepts_support_artifact_payload(self) -> None:
        env = _evidence_envelope(payload=_support_artifact())
        self.assertIsInstance(env.proof, ProofReceipt)

    def test_evidence_envelope_accepts_provenance_payload(self) -> None:
        env = _evidence_envelope(engine="problog", payload=_provenance_envelope())
        self.assertIsInstance(env.proof, ProvenanceEnvelope)

    def test_evidence_envelope_branch_atom_projection_must_be_none(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            EvidenceEnvelope(
                engine="native",
                support_kind="native_binding_v1",
                support_digest="sha256:" + ("1" * 64),
                case_index=0,
                proof=_support_artifact(),
                branch_atom_projection=object(),  # type: ignore[arg-type]
            )

    def test_evidence_envelope_engine_payload_round_trip(self) -> None:
        artifact = _support_artifact()
        self.assertEqual(support_artifact_from_dict(support_artifact_to_dict(artifact)), artifact)
        envelope = _provenance_envelope()
        self.assertEqual(
            provenance_envelope_from_dict(provenance_envelope_to_dict(envelope)),
            envelope,
        )


class CheckResultProtocolTests(unittest.TestCase):
    def test_check_result_passed_nullable_matrix(self) -> None:
        result = CheckResult(
            status="passed",
            requested_binding=_partial_binding(),
            matched_count=1,
            matched_binding=_binding(),
            evidence_envelope=_evidence_envelope(),
        )
        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.matched_binding, _binding())
        self.assertIsNotNone(result.evidence_envelope)

    def test_check_result_failed_nullable_matrix(self) -> None:
        result = CheckResult(
            status="failed",
            requested_binding=_partial_binding(),
            matched_count=0,
            matched_binding=None,
            evidence_envelope=None,
        )
        self.assertEqual(result.matched_count, 0)
        self.assertIsNone(result.matched_binding)
        self.assertIsNone(result.evidence_envelope)

    def test_check_result_unsupported_nullable_matrix(self) -> None:
        result = CheckResult(
            status="unsupported",
            requested_binding=_partial_binding(),
            matched_count=None,
            matched_binding=None,
            evidence_envelope=None,
            errors=(_error(),),
        )
        self.assertIsNone(result.matched_count)
        self.assertEqual(result.errors[0].code, "BINDING_NOT_REPRESENTABLE_FOR_ENGINE")

    def test_check_result_invalid_request_nullable_matrix(self) -> None:
        result = CheckResult(
            status="invalid_request",
            requested_binding=_partial_binding(),
            matched_count=None,
            matched_binding=None,
            evidence_envelope=None,
            errors=(_error("UNKNOWN_BINDING_VARIABLE"),),
        )
        self.assertIsNone(result.matched_count)
        self.assertEqual(result.errors[0].code, "UNKNOWN_BINDING_VARIABLE")

    def test_unsupported_requires_errors(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            CheckResult(
                status="unsupported",
                requested_binding=_partial_binding(),
                matched_count=None,
                matched_binding=None,
                evidence_envelope=None,
            )

    def test_error_codes_screaming_snake_case(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            ErrorDTO(code="not_screaming", message="bad")


if __name__ == "__main__":
    unittest.main()
