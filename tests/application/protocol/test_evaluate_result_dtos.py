from __future__ import annotations

from dataclasses import fields
import unittest

from factgraph.application.protocol import (
    Claim,
    DetachedClaimError,
    DetachedEvidenceRefError,
    DetachedRowError,
    ErrorDTO,
    EvaluateResult,
    EvaluateRow,
    EvidenceRef,
    Explanation,
    ResultFingerprint,
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
from factgraph.audit.evidence_graph import (
    EDGE_SUPPORTS,
    EvidenceGraph,
    EvidenceNode,
    NODE_CONCLUSION,
    NODE_PREMISE,
    NODE_SEED,
)
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var
from factgraph.core.store._support import (
    SOUFFLE_WITNESS_KIND,
    NonFactStep,
    PredWitness,
    ProvenanceEnvelope,
    ProofReceipt,
)


def _head_rule() -> Rule:
    person = Var("$person")
    return Rule(id="person_head", when=(PredAtom("Person:exists", [person]),), ports={"person": person})


def _token(label: str) -> str:
    return sha256_token(label.encode("utf-8"))


def _result_parts() -> tuple[str, str, str, str, str, str, str, str, str, Rule]:
    head = _head_rule()
    engine = "native"
    run_id = "run_v1:" + "1" * 64
    expr_digest = _token("expr")
    rule_set_digest = _token("rules")
    view_snapshot_digest = _token("view")
    config_digest = _token("semantics")
    result_id = result_id_for(
        run_id=run_id,
        expr_digest=expr_digest,
        rule_set_digest=rule_set_digest,
        view_snapshot_digest=view_snapshot_digest,
        config_digest=config_digest,
        engine=engine,
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
        config_digest,
        closed_head_digest,
        head.content_digest,
        engine,
        head,
    )


def _row(result_id: str, run_id: str, closed_head_digest: str, bindings: dict[str, object]) -> EvaluateRow:
    digest = claim_digest_for("fact_triple", "person_head", bindings)
    row_id = row_id_for(run_id, bindings)
    claim = Claim(
        kind="fact_triple",
        repr="Person:exists(person)",
        digest=digest,
    )
    evidence_ref = EvidenceRef(
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


def _fingerprint(
    *,
    run_id: str,
    expr_digest: str,
    rule_set_digest: str,
    view_snapshot_digest: str,
    config_digest: str | None,
    result_digest: str,
) -> ResultFingerprint:
    return ResultFingerprint(
        expr_digest=expr_digest,
        rule_set_digest=rule_set_digest,
        view_snapshot_digest=view_snapshot_digest,
        config_digest=config_digest,
        result_digest=result_digest,
        run_id=run_id,
    )


def _evaluate_result(
    *,
    result_id: str,
    run_id: str,
    rows: tuple[EvaluateRow, ...],
    head: Rule,
    engine: str,
    expr_digest: str,
    rule_set_digest: str,
    view_snapshot_digest: str,
    config_digest: str | None,
    result_digest: str,
    evaluated_at: object = "2026-05-25T00:00:00Z",
    engine_version: str | None = None,
    adapter_version: str | None = None,
    **kwargs: object,
) -> EvaluateResult:
    return EvaluateResult(
        result_id=result_id,
        rows=rows,
        head=head,
        engine=engine,
        evaluated_at=evaluated_at,
        fingerprint=_fingerprint(
            run_id=run_id,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
            result_digest=result_digest,
        ),
        engine_meta={"engine_version": engine_version, "adapter_version": adapter_version},
        **kwargs,
    )


def _evidence_ref_id(result_id: str, row: EvaluateRow) -> str:
    return evidence_ref_id_for(result_id, row.row_id, row.claim.digest, row.evidence_ref.closed_head_digest)


def _single_row_result(
    bindings: dict[str, object] | None = None,
    *,
    support_artifact: ProofReceipt | None = None,
    provenance_envelope: ProvenanceEnvelope | None = None,
) -> EvaluateResult:
    (
        run_id,
        result_id,
        expr_digest,
        rule_set_digest,
        view_snapshot_digest,
        config_digest,
        closed_head_digest,
        head_content_digest,
        engine,
        head,
    ) = _result_parts()
    row = _row(result_id, run_id, closed_head_digest, {"person": "p1"} if bindings is None else bindings)
    result_digest = result_digest_for(
        result_id=result_id,
        run_id=run_id,
        row_digests=(_row_digest_for(row, result_id=result_id, claim_name=head.id),),
        head_id=head.id,
        head_content_digest=head_content_digest,
        engine=engine,
        engine_version=None,
        adapter_version=None,
        expr_digest=expr_digest,
        rule_set_digest=rule_set_digest,
        view_snapshot_digest=view_snapshot_digest,
        config_digest=config_digest,
    )
    row_support_artifacts = {row.row_id: support_artifact} if support_artifact is not None else None
    row_provenance_envelopes = {row.row_id: provenance_envelope} if provenance_envelope is not None else None
    return _evaluate_result(
        result_id=result_id,
        rows=(row,),
        head=head,
        engine=engine,
        expr_digest=expr_digest,
        rule_set_digest=rule_set_digest,
        view_snapshot_digest=view_snapshot_digest,
        config_digest=config_digest,
        result_digest=result_digest,
        run_id=run_id,
        _row_support_artifacts=row_support_artifacts,
        _row_provenance_envelopes=row_provenance_envelopes,
    )


def _native_support_artifact(
    pred_witnesses: tuple[PredWitness, ...],
    *,
    kind: str = "native_binding_v1",
    non_fact_steps: tuple[NonFactStep, ...] = (),
) -> ProofReceipt:
    return ProofReceipt(
        kind=kind,
        root_result_kind="row",
        binding_items=(("$person", "p1"),),
        pred_witnesses=pred_witnesses,
        non_fact_steps=non_fact_steps,
    )


def _problog_provenance_envelope() -> ProvenanceEnvelope:
    return ProvenanceEnvelope(
        candidate_id="cand_v2:problog",
        engine="problog",
        payload_type="proof_trace",
        payload={
            "engine": "problog",
            "trace_type": "proof_trace",
            "events": [],
            "answers": [],
        },
    )


def _graph_with_metadata(
    row: EvaluateRow,
    result: EvaluateResult,
    metadata: dict[str, object],
) -> EvidenceGraph:
    return EvidenceGraph(
        graph_id=f"{result.result_id}:{row.row_id}",
        engine=result.engine,
        root_node_id=row.row_id,
        nodes=(
            EvidenceNode(
                node_id=row.row_id,
                node_kind=NODE_CONCLUSION,
                component="evaluate.row",
                label=result.head.id,
                value_summary=row.claim.repr,
            ),
        ),
        edges=(),
        support_kind="evaluate_row",
        metadata=metadata,
    )


class EvaluateResultDTOTests(unittest.TestCase):
    def test_claim_and_evidence_ref_redundant_names_are_not_dataclass_fields(self) -> None:
        self.assertEqual({field.name for field in fields(Claim)}, {"kind", "repr", "digest", "_row_resolver"})
        self.assertEqual({field.name for field in fields(EvidenceRef)}, {"closed_head_digest", "_row_resolver"})

    def test_standalone_claim_without_resolver_raises_detached_error(self) -> None:
        claim = Claim(
            kind="fact_triple",
            repr="Person:exists(person)",
            digest=claim_digest_for("fact_triple", "person_head", {"person": "p1"}),
        )

        with self.assertWarns(DeprecationWarning), self.assertRaises(DetachedClaimError):
            _ = claim.name
        with self.assertWarns(DeprecationWarning), self.assertRaises(DetachedClaimError):
            _ = claim.arguments

    def test_standalone_evidence_ref_without_resolver_raises_detached_error(self) -> None:
        _run_id, _result_id, _expr, _rules, _view, _semantics, closed_head_digest, *_rest = _result_parts()
        evidence_ref = EvidenceRef(closed_head_digest=closed_head_digest)

        with self.assertWarns(DeprecationWarning), self.assertRaises(DetachedEvidenceRefError):
            _ = evidence_ref.row_id
        with self.assertWarns(DeprecationWarning), self.assertRaises(DetachedEvidenceRefError):
            _ = evidence_ref.result_id
        with self.assertWarns(DeprecationWarning), self.assertRaises(DetachedEvidenceRefError):
            _ = evidence_ref.ref_id
        with self.assertWarns(DeprecationWarning), self.assertRaises(DetachedEvidenceRefError):
            _ = evidence_ref.fact_digest

    def test_claim_deprecated_name_emits_warning(self) -> None:
        result = _single_row_result()
        row = result[0]

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(row.claim.name, result.head.id)

    def test_claim_deprecated_arguments_emits_warning(self) -> None:
        result = _single_row_result()
        row = result[0]

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(dict(row.claim.arguments), dict(row.bindings))

    def test_evidence_ref_deprecated_row_id_emits_warning(self) -> None:
        result = _single_row_result()
        row = result[0]

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(row.evidence_ref.row_id, row.row_id)

    def test_evidence_ref_deprecated_result_id_emits_warning(self) -> None:
        result = _single_row_result()
        row = result[0]

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(row.evidence_ref.result_id, result.result_id)

    def test_evidence_ref_deprecated_ref_id_byte_equal_to_pre_alpha(self) -> None:
        result = _single_row_result()
        row = result[0]

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(row.evidence_ref.ref_id, _evidence_ref_id(result.result_id, row))

    def test_evidence_ref_deprecated_fact_digest_emits_warning(self) -> None:
        result = _single_row_result()
        row = result[0]

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(row.evidence_ref.fact_digest, row.claim.digest)

    def test_result_fingerprint_holds_folded_result_metadata(self) -> None:
        result = _single_row_result()

        self.assertEqual(
            {field.name for field in fields(ResultFingerprint)},
            {"expr_digest", "rule_set_digest", "view_snapshot_digest", "config_digest", "result_digest", "run_id"},
        )
        self.assertEqual(result.fingerprint.run_id, _result_parts()[0])
        self.assertEqual(result.engine_meta["engine_version"], None)
        self.assertEqual(result.engine_meta["adapter_version"], None)

    def test_evaluate_result_deprecated_flat_fields_emit_warnings(self) -> None:
        result = _single_row_result()

        with self.assertWarns(DeprecationWarning):
            self.assertEqual(result.run_id, result.fingerprint.run_id)
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(result.expr_digest, result.fingerprint.expr_digest)
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(result.rule_set_digest, result.fingerprint.rule_set_digest)
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(result.view_snapshot_digest, result.fingerprint.view_snapshot_digest)
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(result.config_digest, result.fingerprint.config_digest)
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(result.result_digest, result.fingerprint.result_digest)
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(result.engine_version, result.engine_meta["engine_version"])
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(result.adapter_version, result.engine_meta["adapter_version"])

    def test_evaluate_result_engine_meta_requires_version_keys(self) -> None:
        result = _single_row_result()

        with self.assertRaisesRegex(ProtocolShapeError, "engine_version"):
            EvaluateResult(
                result_id=result.result_id,
                rows=result.rows,
                head=result.head,
                engine=result.engine,
                evaluated_at=result.evaluated_at,
                fingerprint=result.fingerprint,
                engine_meta={"adapter_version": None},
            )

    def test_evaluate_result_container_binds_live_rows(self) -> None:
        (
            run_id,
            result_id,
            expr_digest,
            rule_set_digest,
            view_snapshot_digest,
            config_digest,
            closed_head_digest,
            head_content_digest,
            engine,
            head,
        ) = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})
        result_digest = result_digest_for(
            result_id=result_id,
            run_id=run_id,
            row_digests=(_row_digest_for(row, result_id=result_id, claim_name=head.id),),
            head_id=head.id,
            head_content_digest=head_content_digest,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
        )

        result = _evaluate_result(
            result_id=result_id,
            rows=(row,),
            head=head,
            engine=engine,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
            result_digest=result_digest,
            run_id=run_id,
        )

        self.assertEqual(len(result), 1)
        self.assertTrue(result.exists())
        self.assertEqual(result.count(), 1)
        self.assertIs(result.first(), result[0])
        self.assertIs(result[0]._require_live_result(), result)

    def test_row_provenance_envelopes_reject_unknown_row_id(self) -> None:
        result = _single_row_result()
        row = result.rows[0]

        with self.assertRaisesRegex(ProtocolShapeError, "unknown row_id"):
            _evaluate_result(
                result_id=result.result_id,
                rows=(row,),
                head=result.head,
                engine=result.engine,
                expr_digest=result.fingerprint.expr_digest,
                rule_set_digest=result.fingerprint.rule_set_digest,
                view_snapshot_digest=result.fingerprint.view_snapshot_digest,
                config_digest=result.fingerprint.config_digest,
                evaluated_at=result.evaluated_at,
                result_digest=result.fingerprint.result_digest,
                run_id=result.fingerprint.run_id,
                engine_version=result.engine_meta["engine_version"],  # type: ignore[arg-type]
                adapter_version=result.engine_meta["adapter_version"],  # type: ignore[arg-type]
                _row_provenance_envelopes={"missing-row": _problog_provenance_envelope()},
            )

    def test_row_provenance_envelopes_reject_non_problog_payload(self) -> None:
        bad_envelope = ProvenanceEnvelope(
            candidate_id="cand_v2:pyreason",
            engine="pyreason",
            payload_type="trace",
            payload={},
        )

        with self.assertRaisesRegex(ProtocolShapeError, "ProbLog proof traces"):
            _single_row_result(provenance_envelope=bad_envelope)

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
        config_digest = _token("semantics")
        result_id = result_id_for(
            run_id=run_id,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
            engine="native",
            head_id=head.id,
            head_content_digest=head.content_digest,
        )
        closed_head_digest = closed_head_digest_for(head)
        row = _row(result_id, run_id, closed_head_digest, {"region": "eu"})
        result_digest = result_digest_for(
            result_id=result_id,
            run_id=run_id,
            row_digests=(_row_digest_for(row, result_id=result_id, claim_name=head.id),),
            head_id=head.id,
            head_content_digest=head.content_digest,
            engine="native",
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
        )
        result = _evaluate_result(
            result_id=result_id,
            rows=(row,),
            head=head,
            engine="native",
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
            result_digest=result_digest,
            run_id=run_id,
        )

        closed = result[0].close()

        self.assertIsInstance(closed, Rule)
        self.assertIn("_closed_", closed.id)
        self.assertNotIn("__factgraph_projection_placeholder", repr(closed.when))
        self.assertTrue(any(isinstance(atom, CmpAtom) and atom.rhs == Const("eu") for atom in closed.when))

    def test_live_row_explain_returns_passed_explanation(self) -> None:
        (
            run_id,
            result_id,
            expr_digest,
            rule_set_digest,
            view_snapshot_digest,
            config_digest,
            closed_head_digest,
            head_content_digest,
            engine,
            head,
        ) = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})
        result_digest = result_digest_for(
            result_id=result_id,
            run_id=run_id,
            row_digests=(_row_digest_for(row, result_id=result_id, claim_name=head.id),),
            head_id=head.id,
            head_content_digest=head_content_digest,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
        )
        result = _evaluate_result(
            result_id=result_id,
            rows=(row,),
            head=head,
            engine=engine,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
            result_digest=result_digest,
            run_id=run_id,
        )

        explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        self.assertIsInstance(explanation.evidence, EvidenceGraph)
        self.assertIs(explanation.claim, result[0].claim)
        self.assertEqual(explanation.result_id, result.result_id)
        self.assertEqual(explanation.row_id, result[0].row_id)
        self.assertEqual(explanation.evidence_ref_id, _evidence_ref_id(result_id, result[0]))
        self.assertEqual(explanation.raw_kind, result[0].raw_kind)
        self.assertEqual(explanation.bound, result[0].bound)
        self.assertEqual(explanation.failure_class, None)
        self.assertEqual(explanation.checked_scope["config_digest"], config_digest)
        self.assertEqual(explanation.checked_scope["semantics_source"], "row_result")
        self.assertEqual(explanation.checked_scope["evaluate_config_digest"], config_digest)
        self.assertEqual(explanation.checked_scope["explain_config_digest"], config_digest)
        self.assertEqual(explanation.checked_scope["semantics_match"], True)
        self.assertEqual(explanation.evidence.root_node_id, result[0].row_id)
        expected_metadata_keys = {
            "result_id",
            "row_id",
            "evidence_ref_id",
            "claim_digest",
            "closed_head_digest",
            "expr_digest",
            "rule_set_digest",
            "view_snapshot_digest",
            "config_digest",
            "result_digest",
            "engine",
            "engine_version",
            "adapter_version",
            "evaluated_at",
        }
        self.assertEqual(set(explanation.evidence.metadata), expected_metadata_keys)
        self.assertNotIn("run_id", explanation.evidence.metadata)
        self.assertEqual(explanation.evidence.metadata["result_id"], result.result_id)
        self.assertEqual(explanation.evidence.metadata["row_id"], result[0].row_id)
        self.assertEqual(explanation.evidence.metadata["evidence_ref_id"], _evidence_ref_id(result_id, result[0]))
        self.assertEqual(explanation.evidence.metadata["claim_digest"], result[0].claim.digest)
        self.assertEqual(explanation.evidence.metadata["closed_head_digest"], result[0].evidence_ref.closed_head_digest)
        self.assertEqual(explanation.evidence.metadata["expr_digest"], expr_digest)
        self.assertEqual(explanation.evidence.metadata["rule_set_digest"], rule_set_digest)
        self.assertEqual(explanation.evidence.metadata["view_snapshot_digest"], view_snapshot_digest)
        self.assertEqual(explanation.evidence.metadata["config_digest"], config_digest)
        self.assertEqual(explanation.evidence.metadata["result_digest"], result_digest)
        self.assertEqual(explanation.evidence.metadata["engine"], engine)
        self.assertEqual(explanation.evidence.metadata["engine_version"], None)
        self.assertEqual(explanation.evidence.metadata["adapter_version"], None)
        self.assertEqual(explanation.evidence.metadata["evaluated_at"], "2026-05-25T00:00:00Z")
        self.assertEqual(len(explanation.evidence.nodes), 1)
        self.assertEqual(explanation.evidence.edges, ())
        self.assertEqual(explanation.evidence.support_kind, "evaluate_row")

    def test_live_row_explain_uses_native_form1_support_topology(self) -> None:
        support = _native_support_artifact(
            (
                PredWitness(pred_condition_key="c0.c0:Person:exists", asrt_ids=("asrt-1",)),
            ),
            non_fact_steps=(
                NonFactStep(step_key="c0.c1:eq", kind="eq", status="satisfied", details=(("atom_repr", "eq"),)),
            ),
        )
        result = _single_row_result(support_artifact=support)

        explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        graph = explanation.evidence
        self.assertEqual(graph.support_kind, "native_binding_v1")
        self.assertEqual(graph.root_node_id, result[0].row_id)
        root = next(node for node in graph.nodes if node.node_id == graph.root_node_id)
        self.assertEqual(root.node_kind, NODE_CONCLUSION)
        self.assertEqual(root.component, result.head.id)
        self.assertEqual(root.engine_meta["alternative_paths"], {"mode": "winning_path_only", "omitted_count": None})
        self.assertEqual(root.engine_meta["explained_claim_ref"]["row_id"], result[0].row_id)
        self.assertEqual(root.engine_meta["quantitative_explanation"]["mode"], "not_applicable")

        premise_nodes = [node for node in graph.nodes if node.node_kind == NODE_PREMISE]
        seed_nodes = [node for node in graph.nodes if node.node_kind == NODE_SEED]
        self.assertEqual({node.node_id for node in premise_nodes}, {"premise:c0.c0:Person:exists", "premise:c0.c1:eq"})
        self.assertEqual({node.node_id for node in seed_nodes}, {"seed:assertion:asrt-1"})
        self.assertTrue(all(edge.edge_kind == EDGE_SUPPORTS for edge in graph.edges))
        self.assertIn(("premise:c0.c0:Person:exists", result[0].row_id), {(e.from_node_id, e.to_node_id) for e in graph.edges})
        self.assertIn(
            ("seed:assertion:asrt-1", "premise:c0.c0:Person:exists"),
            {(e.from_node_id, e.to_node_id) for e in graph.edges},
        )

    def test_native_form1_support_reuses_seed_node_with_multiple_edges(self) -> None:
        support = _native_support_artifact(
            (
                PredWitness(pred_condition_key="c0.c0:Person:exists", asrt_ids=("asrt-1",)),
                PredWitness(pred_condition_key="c0.c1:Person:active", asrt_ids=("asrt-1",)),
            )
        )
        result = _single_row_result(support_artifact=support)

        explanation = result[0].explain()

        assert explanation.evidence is not None
        seed_nodes = [node for node in explanation.evidence.nodes if node.node_kind == NODE_SEED]
        self.assertEqual([node.node_id for node in seed_nodes], ["seed:assertion:asrt-1"])
        seed_edges = [edge for edge in explanation.evidence.edges if edge.from_node_id == "seed:assertion:asrt-1"]
        self.assertEqual(
            {edge.to_node_id for edge in seed_edges},
            {"premise:c0.c0:Person:exists", "premise:c0.c1:Person:active"},
        )

    def test_live_row_explain_uses_souffle_form1_support_topology(self) -> None:
        support = _native_support_artifact(
            (
                PredWitness(pred_condition_key="c0.c0:Person:exists", asrt_ids=("souffle-asrt-1",)),
            ),
            kind=SOUFFLE_WITNESS_KIND,
            non_fact_steps=(
                NonFactStep(step_key="c0.c1:eq", kind="eq", status="satisfied", details=(("source", "souffle"),)),
            ),
        )
        result = _single_row_result(support_artifact=support)

        explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        graph = explanation.evidence
        self.assertEqual(graph.support_kind, SOUFFLE_WITNESS_KIND)
        self.assertEqual(graph.root_node_id, result[0].row_id)
        self.assertEqual(
            set(graph.metadata),
            {
                "result_id",
                "row_id",
                "evidence_ref_id",
                "claim_digest",
                "closed_head_digest",
                "expr_digest",
                "rule_set_digest",
                "view_snapshot_digest",
                "config_digest",
                "result_digest",
                "engine",
                "engine_version",
                "adapter_version",
                "evaluated_at",
            },
        )
        self.assertEqual(graph.metadata["result_id"], result.result_id)
        self.assertEqual(graph.metadata["row_id"], result[0].row_id)
        self.assertNotIn("run_id", graph.metadata)
        root = next(node for node in graph.nodes if node.node_id == graph.root_node_id)
        self.assertEqual(root.node_kind, NODE_CONCLUSION)
        self.assertEqual(root.engine_meta["alternative_paths"], {"mode": "winning_path_only", "omitted_count": None})

        premise_nodes = [node for node in graph.nodes if node.node_kind == NODE_PREMISE]
        seed_nodes = [node for node in graph.nodes if node.node_kind == NODE_SEED]
        self.assertEqual({node.node_id for node in premise_nodes}, {"premise:c0.c0:Person:exists", "premise:c0.c1:eq"})
        self.assertEqual({node.node_id for node in seed_nodes}, {"seed:assertion:souffle-asrt-1"})
        self.assertIn(
            ("premise:c0.c0:Person:exists", result[0].row_id),
            {(edge.from_node_id, edge.to_node_id) for edge in graph.edges},
        )
        self.assertIn(
            ("seed:assertion:souffle-asrt-1", "premise:c0.c0:Person:exists"),
            {(edge.from_node_id, edge.to_node_id) for edge in graph.edges},
        )

    def test_souffle_form1_support_reuses_seed_node_with_multiple_edges(self) -> None:
        support = _native_support_artifact(
            (
                PredWitness(pred_condition_key="c0.c0:Person:exists", asrt_ids=("souffle-asrt-1",)),
                PredWitness(pred_condition_key="c0.c1:Person:active", asrt_ids=("souffle-asrt-1",)),
            ),
            kind=SOUFFLE_WITNESS_KIND,
        )
        result = _single_row_result(support_artifact=support)

        explanation = result[0].explain()

        assert explanation.evidence is not None
        seed_nodes = [node for node in explanation.evidence.nodes if node.node_kind == NODE_SEED]
        self.assertEqual([node.node_id for node in seed_nodes], ["seed:assertion:souffle-asrt-1"])
        seed_edges = [edge for edge in explanation.evidence.edges if edge.from_node_id == "seed:assertion:souffle-asrt-1"]
        self.assertEqual(
            {edge.to_node_id for edge in seed_edges},
            {"premise:c0.c0:Person:exists", "premise:c0.c1:Person:active"},
        )

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
                evidence_ref_id=_evidence_ref_id(result_id, row),
            )
        with self.assertRaisesRegex(ProtocolShapeError, "failure_class"):
            Explanation(
                status="failed",
                evidence=None,
                claim=row.claim,
                result_id=result_id,
                row_id=row.row_id,
                evidence_ref_id=_evidence_ref_id(result_id, row),
            )
        with self.assertRaisesRegex(ProtocolShapeError, "errors"):
            Explanation(
                status="unsupported",
                evidence=None,
                claim=row.claim,
                result_id=result_id,
                row_id=row.row_id,
                evidence_ref_id=_evidence_ref_id(result_id, row),
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
            evidence_ref_id=_evidence_ref_id(result_id, row),
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
            config_digest,
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
            row_digests=(_row_digest_for(row, result_id=result_id, claim_name=head.id),),
            head_id=head.id,
            head_content_digest=head_content_digest,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
        )
        result = _evaluate_result(
            result_id=result_id,
            rows=(row,),
            head=head,
            engine=engine,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
            result_digest=result_digest,
            run_id=run_id,
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
            config_digest,
            closed_head_digest,
            head_content_digest,
            engine,
            head,
        ) = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})
        result_digest = result_digest_for(
            result_id=result_id,
            run_id=run_id,
            row_digests=(_row_digest_for(row, result_id=result_id, claim_name=head.id),),
            head_id=head.id,
            head_content_digest=head_content_digest,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
        )
        result = _evaluate_result(
            result_id=result_id,
            rows=(row,),
            head=head,
            engine=engine,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
            result_digest=result_digest,
            run_id=run_id,
        )

        explanation = _explain_live_row(result[0], result, graph_builder=lambda _row, _result, _metadata: (_ for _ in ()).throw(ValueError("bad graph")))

        self.assertEqual(explanation.status, "unsupported")
        self.assertEqual(explanation.errors[0].code, "GRAPH_VALIDATION_FAILED")
        self.assertIsNone(explanation.evidence)

    def test_graph_metadata_checker_rejects_missing_key(self) -> None:
        result = _single_row_result()
        explanation = _explain_live_row(
            result[0],
            result,
            graph_builder=lambda row, build_result, metadata: _graph_with_metadata(
                row,
                build_result,
                {key: value for key, value in metadata.items() if key != "result_id"},
            ),
        )

        self.assertEqual(explanation.status, "unsupported")
        self.assertEqual(explanation.errors[0].code, "GRAPH_VALIDATION_FAILED")
        self.assertIn("missing", explanation.errors[0].message)
        self.assertIsNone(explanation.evidence)

    def test_graph_metadata_checker_rejects_extra_key(self) -> None:
        result = _single_row_result()

        def _builder(row: EvaluateRow, build_result: EvaluateResult, metadata: object) -> EvidenceGraph:
            mutated = dict(metadata)  # type: ignore[arg-type]
            mutated["run_id"] = build_result.fingerprint.run_id
            return _graph_with_metadata(row, build_result, mutated)

        explanation = _explain_live_row(result[0], result, graph_builder=_builder)

        self.assertEqual(explanation.status, "unsupported")
        self.assertEqual(explanation.errors[0].code, "GRAPH_VALIDATION_FAILED")
        self.assertIn("extra", explanation.errors[0].message)
        self.assertIsNone(explanation.evidence)

    def test_graph_metadata_checker_rejects_wrong_value(self) -> None:
        result = _single_row_result()

        def _builder(row: EvaluateRow, build_result: EvaluateResult, metadata: object) -> EvidenceGraph:
            mutated = dict(metadata)  # type: ignore[arg-type]
            mutated["row_id"] = "row:wrong"
            return _graph_with_metadata(row, build_result, mutated)

        explanation = _explain_live_row(result[0], result, graph_builder=_builder)

        self.assertEqual(explanation.status, "unsupported")
        self.assertEqual(explanation.errors[0].code, "GRAPH_VALIDATION_FAILED")
        self.assertIn("row_id", explanation.errors[0].message)
        self.assertIsNone(explanation.evidence)

    def test_evaluate_result_rejects_duplicate_row_id(self) -> None:
        (
            run_id,
            result_id,
            expr_digest,
            rule_set_digest,
            view_snapshot_digest,
            config_digest,
            closed_head_digest,
            head_content_digest,
            engine,
            head,
        ) = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})
        result_digest = result_digest_for(
            result_id=result_id,
            run_id=run_id,
            row_digests=(_row_digest_for(row, result_id=result_id, claim_name=head.id), _row_digest_for(row, result_id=result_id, claim_name=head.id)),
            head_id=head.id,
            head_content_digest=head_content_digest,
            engine=engine,
            engine_version=None,
            adapter_version=None,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
        )

        with self.assertRaisesRegex(ProtocolShapeError, "duplicate row_id"):
            _evaluate_result(
                result_id=result_id,
                rows=(row, row),
                head=head,
                engine=engine,
                expr_digest=expr_digest,
                rule_set_digest=rule_set_digest,
                view_snapshot_digest=view_snapshot_digest,
                config_digest=config_digest,
                result_digest=result_digest,
                run_id=run_id,
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
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(row.evidence_ref.fact_digest, row.claim.digest)


if __name__ == "__main__":
    unittest.main()
