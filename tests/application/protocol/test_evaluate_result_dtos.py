from __future__ import annotations

import unittest

from factgraph.application.protocol import (
    Claim,
    DetachedRowError,
    ErrorDTO,
    EvaluateResult,
    EvaluateRow,
    EvidenceRef,
    Explanation,
    Rule,
)
from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluate_result import (
    _candidate_set_to_evaluate_row,
    _explain_live_row,
    _row_digest_for,
    claim_digest_for,
    closed_head_digest_for,
    evidence_ref_id_for,
    result_digest_for,
    result_id_for,
    row_id_for,
)
from factgraph.audit.evidence_graph import EvidenceGraph, EvidenceNode, NODE_CONCLUSION
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var


def _head_rule() -> Rule:
    person = Var("$person")
    return Rule(id="person_head", where=(PredAtom("Person:exists", [person]),), ports={"person": person})


def _token(label: str) -> str:
    return sha256_token(label.encode("utf-8"))


def _result_parts() -> tuple[str, str, str, str, str, str, str, str, str, Rule]:
    head = _head_rule()
    run_id = "run_v1:" + "1" * 64
    expr_digest = _token("expr")
    rule_set_digest = _token("rules")
    view_snapshot_digest = _token("view")
    semantics_digest = _token("semantics")
    result_id = result_id_for(
        run_id=run_id,
        expr_digest=expr_digest,
        rule_set_digest=rule_set_digest,
        view_snapshot_digest=view_snapshot_digest,
        semantics_digest=semantics_digest,
        engine="native",
        head_id=head.id,
        head_content_digest=head.content_digest,
    )
    closed_head_digest = closed_head_digest_for(head)
    return (
        run_id,
        result_id,
        expr_digest,
        rule_set_digest,
        view_snapshot_digest,
        semantics_digest,
        closed_head_digest,
        head.content_digest,
        "native",
        head,
    )


def _row(result_id: str, run_id: str, closed_head_digest: str, bindings: dict[str, object]) -> EvaluateRow:
    digest = claim_digest_for("fact_triple", "Person:exists", bindings)
    row_id = row_id_for(run_id, bindings)
    claim = Claim(
        kind="fact_triple",
        name="Person:exists",
        arguments=bindings,
        repr="Person:exists(person)",
        digest=digest,
    )
    evidence_ref = EvidenceRef(
        ref_id=evidence_ref_id_for(result_id, row_id, digest, closed_head_digest),
        result_id=result_id,
        row_id=row_id,
        fact_digest=digest,
        closed_head_digest=closed_head_digest,
    )
    return EvaluateRow(
        row_id=row_id,
        bindings=bindings,
        claim=claim,
        raw_kind=None,
        bound=None,
        evidence_ref=evidence_ref,
    )


class EvaluateResultDTOTests(unittest.TestCase):
    def test_evidence_ref_fact_digest_must_equal_claim_digest(self) -> None:
        run_id, result_id, _expr, _rules, _view, _semantics, closed_head_digest, *_rest = _result_parts()
        digest = claim_digest_for("fact_triple", "Person:exists", {"person": "p1"})
        row_id = row_id_for(run_id, {"person": "p1"})
        claim = Claim(
            kind="fact_triple",
            name="Person:exists",
            arguments={"person": "p1"},
            repr="Person:exists(person)",
            digest=digest,
        )
        evidence_ref = EvidenceRef(
            ref_id=evidence_ref_id_for(result_id, row_id, _token("other"), closed_head_digest),
            result_id=result_id,
            row_id=row_id,
            fact_digest=_token("other"),
            closed_head_digest=closed_head_digest,
        )

        with self.assertRaisesRegex(ProtocolShapeError, "fact_digest"):
            EvaluateRow(
                row_id=row_id,
                bindings={"person": "p1"},
                claim=claim,
                raw_kind=None,
                bound=None,
                evidence_ref=evidence_ref,
            )

    def test_evaluate_result_container_binds_live_rows(self) -> None:
        (
            run_id,
            result_id,
            expr_digest,
            rule_set_digest,
            view_snapshot_digest,
            semantics_digest,
            closed_head_digest,
            head_content_digest,
            engine,
            head,
        ) = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})
        result_digest = result_digest_for(
            result_id=result_id,
            run_id=run_id,
            row_digests=(_row_digest_for(row),),
            head_id=head.id,
            head_content_digest=head_content_digest,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
        )

        result = EvaluateResult(
            result_id=result_id,
            run_id=run_id,
            rows=(row,),
            head=head,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
            evaluated_at="2026-05-25T00:00:00Z",
            result_digest=result_digest,
        )

        self.assertEqual(len(result), 1)
        self.assertTrue(result.exists())
        self.assertEqual(result.count(), 1)
        self.assertIs(result.first(), result[0])
        self.assertIs(result[0]._require_live_result(), result)

    def test_detached_row_live_helper_raises(self) -> None:
        run_id, result_id, _expr, _rules, _view, _semantics, closed_head_digest, *_rest = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})

        with self.assertRaises(DetachedRowError):
            row._require_live_result()
        with self.assertRaises(DetachedRowError):
            row.explain()
        with self.assertRaises(DetachedRowError):
            row.close()

    def test_live_value_row_close_strips_projection_placeholders(self) -> None:
        head = Rule.projection("region")
        run_id = "run_v1:" + "1" * 64
        expr_digest = _token("expr")
        rule_set_digest = _token("rules")
        view_snapshot_digest = _token("view")
        semantics_digest = _token("semantics")
        result_id = result_id_for(
            run_id=run_id,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
            engine="native",
            head_id=head.id,
            head_content_digest=head.content_digest,
        )
        closed_head_digest = closed_head_digest_for(head)
        row = _row(result_id, run_id, closed_head_digest, {"region": "eu"})
        result_digest = result_digest_for(
            result_id=result_id,
            run_id=run_id,
            row_digests=(_row_digest_for(row),),
            head_id=head.id,
            head_content_digest=head.content_digest,
            engine="native",
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
        )
        result = EvaluateResult(
            result_id=result_id,
            run_id=run_id,
            rows=(row,),
            head=head,
            engine="native",
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
            evaluated_at="2026-05-25T00:00:00Z",
            result_digest=result_digest,
        )

        closed = result[0].close()

        self.assertIsInstance(closed, Rule)
        self.assertIn("_closed_", closed.id)
        self.assertNotIn("__factgraph_projection_placeholder", repr(closed.where))
        self.assertTrue(any(isinstance(atom, CmpAtom) and atom.rhs == Const("eu") for atom in closed.where))

    def test_live_row_explain_returns_passed_explanation(self) -> None:
        (
            run_id,
            result_id,
            expr_digest,
            rule_set_digest,
            view_snapshot_digest,
            semantics_digest,
            closed_head_digest,
            head_content_digest,
            engine,
            head,
        ) = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})
        result_digest = result_digest_for(
            result_id=result_id,
            run_id=run_id,
            row_digests=(_row_digest_for(row),),
            head_id=head.id,
            head_content_digest=head_content_digest,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
        )
        result = EvaluateResult(
            result_id=result_id,
            run_id=run_id,
            rows=(row,),
            head=head,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
            evaluated_at="2026-05-25T00:00:00Z",
            result_digest=result_digest,
        )

        explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        self.assertIsInstance(explanation.evidence, EvidenceGraph)
        self.assertIs(explanation.claim, result[0].claim)
        self.assertEqual(explanation.result_id, result.result_id)
        self.assertEqual(explanation.row_id, result[0].row_id)
        self.assertEqual(explanation.evidence_ref_id, result[0].evidence_ref.ref_id)
        self.assertEqual(explanation.raw_kind, result[0].raw_kind)
        self.assertEqual(explanation.bound, result[0].bound)
        self.assertEqual(explanation.failure_class, None)
        self.assertEqual(explanation.checked_scope["semantics_digest"], semantics_digest)
        self.assertEqual(explanation.checked_scope["semantics_source"], "row_result")
        self.assertEqual(explanation.checked_scope["evaluate_semantics_digest"], semantics_digest)
        self.assertEqual(explanation.checked_scope["explain_semantics_digest"], semantics_digest)
        self.assertEqual(explanation.checked_scope["semantics_match"], True)
        self.assertEqual(explanation.evidence.root_node_id, result[0].row_id)
        self.assertEqual(explanation.evidence.metadata["result_id"], result.result_id)
        self.assertEqual(explanation.evidence.metadata["evidence_ref_id"], result[0].evidence_ref.ref_id)
        self.assertEqual(explanation.evidence.metadata["view_snapshot_digest"], view_snapshot_digest)

    def test_explanation_status_matrix_is_enforced(self) -> None:
        run_id, result_id, _expr, _rules, _view, _semantics, closed_head_digest, *_rest = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})

        with self.assertRaisesRegex(ProtocolShapeError, "iff"):
            Explanation(
                status="passed",
                evidence=None,
                claim=row.claim,
                result_id=result_id,
                row_id=row.row_id,
                evidence_ref_id=row.evidence_ref.ref_id,
            )
        with self.assertRaisesRegex(ProtocolShapeError, "failure_class"):
            Explanation(
                status="failed",
                evidence=None,
                claim=row.claim,
                result_id=result_id,
                row_id=row.row_id,
                evidence_ref_id=row.evidence_ref.ref_id,
            )
        with self.assertRaisesRegex(ProtocolShapeError, "errors"):
            Explanation(
                status="unsupported",
                evidence=None,
                claim=row.claim,
                result_id=result_id,
                row_id=row.row_id,
                evidence_ref_id=row.evidence_ref.ref_id,
            )

    def test_manual_passed_explanation_allows_no_row_back_reference(self) -> None:
        run_id, result_id, _expr, _rules, _view, _semantics, closed_head_digest, *_rest = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})

        explanation = Explanation(
            status="passed",
            evidence=EvidenceGraph(
                graph_id="manual",
                engine="native",
                root_node_id="root",
                nodes=(
                    EvidenceNode(
                        node_id="root",
                        node_kind=NODE_CONCLUSION,
                        component="evaluate.row",
                        label="manual",
                        value_summary="manual",
                    ),
                ),
                edges=(),
                support_kind="evaluate_row",
                metadata={},
            ),
            claim=row.claim,
            result_id=result_id,
            row_id=None,
            evidence_ref_id=None,
        )

        self.assertEqual(explanation.status, "passed")
        self.assertIsNone(explanation.row_id)
        self.assertIsNone(explanation.evidence_ref_id)

        failed = Explanation(
            status="failed",
            evidence=None,
            claim=row.claim,
            result_id=result_id,
            row_id=row.row_id,
            evidence_ref_id=row.evidence_ref.ref_id,
            failure_class="no_matching_row",
            suggested_next_steps=("Retry with a closed head.",),
        )
        self.assertEqual(failed.failure_class, "no_matching_row")

        invalid = Explanation(
            status="invalid_request",
            evidence=None,
            claim=None,
            result_id=None,
            row_id=None,
            evidence_ref_id=None,
            errors=(ErrorDTO(code="INVALID_REQUEST", message="bad request"),),
        )
        self.assertEqual(invalid.errors[0].code, "INVALID_REQUEST")

    def test_live_row_explain_reports_row_not_in_result(self) -> None:
        (
            run_id,
            result_id,
            expr_digest,
            rule_set_digest,
            view_snapshot_digest,
            semantics_digest,
            closed_head_digest,
            head_content_digest,
            engine,
            head,
        ) = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})
        outside_row = _row(result_id, run_id, closed_head_digest, {"person": "p2"})
        result_digest = result_digest_for(
            result_id=result_id,
            run_id=run_id,
            row_digests=(_row_digest_for(row),),
            head_id=head.id,
            head_content_digest=head_content_digest,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
        )
        result = EvaluateResult(
            result_id=result_id,
            run_id=run_id,
            rows=(row,),
            head=head,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
            evaluated_at="2026-05-25T00:00:00Z",
            result_digest=result_digest,
        )
        live_outside_row = EvaluateRow(
            row_id=outside_row.row_id,
            bindings=outside_row.bindings,
            claim=outside_row.claim,
            raw_kind=outside_row.raw_kind,
            bound=outside_row.bound,
            evidence_ref=outside_row.evidence_ref,
            _result_resolver=lambda: result,
        )

        explanation = live_outside_row.explain()

        self.assertEqual(explanation.status, "failed")
        self.assertEqual(explanation.failure_class, "row_not_in_result")
        self.assertIsNone(explanation.evidence)

    def test_graph_validation_failure_returns_unsupported(self) -> None:
        (
            run_id,
            result_id,
            expr_digest,
            rule_set_digest,
            view_snapshot_digest,
            semantics_digest,
            closed_head_digest,
            head_content_digest,
            engine,
            head,
        ) = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})
        result_digest = result_digest_for(
            result_id=result_id,
            run_id=run_id,
            row_digests=(_row_digest_for(row),),
            head_id=head.id,
            head_content_digest=head_content_digest,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
        )
        result = EvaluateResult(
            result_id=result_id,
            run_id=run_id,
            rows=(row,),
            head=head,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
            evaluated_at="2026-05-25T00:00:00Z",
            result_digest=result_digest,
        )

        explanation = _explain_live_row(result[0], result, graph_builder=lambda _row, _result, _metadata: (_ for _ in ()).throw(ValueError("bad graph")))

        self.assertEqual(explanation.status, "unsupported")
        self.assertEqual(explanation.errors[0].code, "GRAPH_VALIDATION_FAILED")
        self.assertIsNone(explanation.evidence)

    def test_evaluate_result_rejects_duplicate_row_id(self) -> None:
        (
            run_id,
            result_id,
            expr_digest,
            rule_set_digest,
            view_snapshot_digest,
            semantics_digest,
            closed_head_digest,
            head_content_digest,
            engine,
            head,
        ) = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})
        result_digest = result_digest_for(
            result_id=result_id,
            run_id=run_id,
            row_digests=(_row_digest_for(row), _row_digest_for(row)),
            head_id=head.id,
            head_content_digest=head_content_digest,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            semantics_digest=semantics_digest,
        )

        with self.assertRaisesRegex(ProtocolShapeError, "duplicate row_id"):
            EvaluateResult(
                result_id=result_id,
                run_id=run_id,
                rows=(row, row),
                head=head,
                engine=engine,
                engine_version=None,
                adapter_version=None,
                expr_digest=expr_digest,
                rule_set_digest=rule_set_digest,
                view_snapshot_digest=view_snapshot_digest,
                semantics_digest=semantics_digest,
                evaluated_at="2026-05-25T00:00:00Z",
                result_digest=result_digest,
            )

    def test_candidate_set_conversion_harness_keeps_candidate_internal(self) -> None:
        run_id, result_id, _expr, _rules, _view, _semantics, closed_head_digest, *_rest = _result_parts()
        candidate = CandidateSet(
            derivation_id="deriv",
            derivation_version="v1",
            run_id="legacy-run",
            target="Person:exists",
            key_tuple_digest=_token("key"),
            tup_digest=None,
            payload={"terms": [{"kind": "const", "value": "p1"}], "bindings": {"person": "p1"}},
            support_digest=_token("support"),
            support_kind="native",
            generated_at=1,
            state="candidate",
            confidence=0.75,
            confidence_kind="probability",
        )

        row = _candidate_set_to_evaluate_row(
            candidate,
            result_id=result_id,
            run_id=run_id,
            closed_head_digest=closed_head_digest,
        )

        self.assertEqual(dict(row.bindings), {"person": "p1"})
        self.assertEqual(row.raw_kind, "probabilistic")
        self.assertEqual(row.bound, (0.75, 0.75))
        self.assertFalse(hasattr(row, "candidate_id"))
        self.assertEqual(row.evidence_ref.fact_digest, row.claim.digest)


if __name__ == "__main__":
    unittest.main()
