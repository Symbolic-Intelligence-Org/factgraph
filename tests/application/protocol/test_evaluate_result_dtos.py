from __future__ import annotations

from dataclasses import fields, replace
import unittest

from factgraph.application.protocol import (
    BOOLEAN_CERTAINTY,
    Certainty,
    DetachedRowError,
    ErrorDTO,
    EvaluateResult,
    EvaluateRow,
    Explanation,
    ResultFingerprint,
    Rule,
    ScenarioResolutionV0,
)
from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluate_result import (
    _derivation_output_to_evaluate_row,
    _explain_live_row,
    _row_digest_for,
    _scenario_semantic_rows_digest,
    canonical_bytes_for_evaluate,
    claim_digest_for,
    closed_head_digest_for,
    evidence_ref_id_for,
    result_digest_for,
    result_id_for,
    row_id_for,
)
from factgraph.application.explain.evidence_tree import (
    EvidenceGraph,
    EvidenceRule,
    EvidenceTree,
    LAYOUT_TREE,
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
    return EvaluateRow(
        row_id=row_id,
        bindings=bindings,
        kind="fact_triple",
        digest=digest,
        closed_head_digest=closed_head_digest,
        certainty=BOOLEAN_CERTAINTY,
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
    return evidence_ref_id_for(result_id, row.row_id, row.digest, row.closed_head_digest)


class CertaintyTests(unittest.TestCase):
    def test_certainty_validates_probability_bounds(self) -> None:
        self.assertEqual(Certainty(1, 1, "boolean"), BOOLEAN_CERTAINTY)
        with self.assertRaisesRegex(ProtocolShapeError, "Certainty.lo"):
            Certainty(-0.1, 1.0, "boolean")
        with self.assertRaisesRegex(ProtocolShapeError, "Certainty.lo must be <= Certainty.hi"):
            Certainty(0.8, 0.7, "probabilistic")
        with self.assertRaisesRegex(ProtocolShapeError, "Certainty.kind"):
            Certainty(0.0, 1.0, "unknown")  # type: ignore[arg-type]

    def test_row_and_result_digests_preserve_legacy_uncertainty_payload(self) -> None:
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
        bindings = {"person": "p1"}
        row = EvaluateRow(
            row_id=row_id_for(run_id, bindings),
            bindings=bindings,
            kind="fact_triple",
            digest=claim_digest_for("fact_triple", head.id, bindings),
            closed_head_digest=closed_head_digest,
            certainty=Certainty(0.75, 0.75, "probabilistic"),
        )
        expected_row_digest = sha256_token(
            canonical_bytes_for_evaluate(
                "evaluate_row_digest_v2",
                {
                    "bindings": row.bindings,
                    "bound": (0.75, 0.75),
                    "claim": {
                        "arguments": row.bindings,
                        "digest": row.digest,
                        "kind": row.kind,
                        "name": head.id,
                        "repr": f"{head.id}{dict(row.bindings)!r}",
                    },
                    "evidence_ref": {
                        "closed_head_digest": row.closed_head_digest,
                        "fact_digest": row.digest,
                        "result_id": result_id,
                        "row_id": row.row_id,
                    },
                    "raw_kind": "probabilistic",
                    "row_id": row.row_id,
                },
            )
        )

        self.assertEqual(_row_digest_for(row, result_id=result_id, claim_name=head.id), expected_row_digest)
        self.assertEqual(
            result_digest_for(
                result_id=result_id,
                run_id=run_id,
                row_digests=(expected_row_digest,),
                head_id=head.id,
                head_content_digest=head_content_digest,
                engine=engine,
                engine_version=None,
                adapter_version=None,
                expr_digest=expr_digest,
                rule_set_digest=rule_set_digest,
                view_snapshot_digest=view_snapshot_digest,
                config_digest=config_digest,
            ),
            result_digest_for(
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
            ),
        )


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
        layout_hint=LAYOUT_TREE,
        subject_binding=row.bindings,
        paths=(
            EvidenceTree(
                tree_id=row.row_id,
                status="holds",
                rules=(
                    EvidenceRule(
                        occurrence_alias=result.head.id,
                        rule_id=result.head.id,
                        role="head",
                        status="holds",
                        ports=row.bindings,
                        atoms=(),
                    ),
                ),
                joins=(),
            ),
        ),
        certainty=row.certainty,
        metadata=metadata,
    )


def _evidence_metadata_for_test(row: EvaluateRow, result: EvaluateResult) -> dict[str, object]:
    fingerprint = result.fingerprint
    return {
        "result_id": result.result_id,
        "row_id": row.row_id,
        "evidence_ref_id": _evidence_ref_id(result.result_id, row),
        "claim_digest": row.digest,
        "closed_head_digest": row.closed_head_digest,
        "expr_digest": fingerprint.expr_digest,
        "rule_set_digest": fingerprint.rule_set_digest,
        "view_snapshot_digest": fingerprint.view_snapshot_digest,
        "config_digest": fingerprint.config_digest,
        "result_digest": fingerprint.result_digest,
        "engine": result.engine,
        "engine_version": result.engine_meta["engine_version"],
        "adapter_version": result.engine_meta["adapter_version"],
        "evaluated_at": result.evaluated_at,
    }


class EvaluateResultDTOTests(unittest.TestCase):
    def test_evaluate_row_holds_claim_and_evidence_fields_directly(self) -> None:
        result = _single_row_result()
        row = result[0]

        self.assertEqual(
            {field.name for field in fields(EvaluateRow)},
            {"row_id", "bindings", "kind", "digest", "closed_head_digest", "certainty", "_result_resolver"},
        )
        self.assertEqual(row.kind, "fact_triple")
        self.assertEqual(row.digest, claim_digest_for("fact_triple", result.head.id, row.bindings))
        self.assertEqual(row.closed_head_digest, closed_head_digest_for(result.head))
        self.assertFalse(hasattr(row, "claim"))
        self.assertFalse(hasattr(row, "evidence_ref"))

    def test_evidence_ref_id_formula_uses_direct_row_fields(self) -> None:
        result = _single_row_result()
        row = result[0]

        self.assertEqual(
            evidence_ref_id_for(result.result_id, row.row_id, row.digest, row.closed_head_digest),
            _evidence_ref_id(result.result_id, row),
        )

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
        self.assertIsNone(result.run_anchor)
        self.assertIs(result.first(), result[0])
        self.assertIs(result[0]._require_live_result(), result)

    def test_scenario_result_cannot_carry_run_anchor_or_bundle(self) -> None:
        from factgraph.application.protocol import FieldPath, ScenarioResultDiffV0, ScenarioScalarValueV0

        result = _single_row_result()
        effective_digest = result.fingerprint.view_snapshot_digest
        diff = ScenarioResultDiffV0(
            1,
            1,
            _token("baseline"),
            _scenario_semantic_rows_digest(result.rows),
            True,
        )
        scenario = ScenarioResolutionV0(
            premise_id="hypothesis",
            entity_ref="idref_v1:Person:test",
            field=FieldPath("Person", "age"),
            baseline_value=ScenarioScalarValueV0("int", 22),
            effective_value=ScenarioScalarValueV0("int", 35),
            base_view_digest=_token("base"),
            baseline_relation_digest=_token("before"),
            effective_relation_digest=effective_digest,
            semantic_value_changed=True,
            effective_source_changed=True,
            result_diff=diff,
        )
        scenario_result = _evaluate_result(
            result_id=result.result_id,
            rows=result.rows,
            head=result.head,
            engine=result.engine,
            expr_digest=result.fingerprint.expr_digest,
            rule_set_digest=result.fingerprint.rule_set_digest,
            view_snapshot_digest=result.fingerprint.view_snapshot_digest,
            config_digest=result.fingerprint.config_digest,
            result_digest=result.fingerprint.result_digest,
            run_id=result.fingerprint.run_id,
            scenario=scenario,
        )
        self.assertIs(scenario_result.scenario, scenario)

        with self.assertRaisesRegex(ProtocolShapeError, "effective relation digest"):
            replace(
                scenario_result,
                scenario=replace(scenario, effective_relation_digest=_token("wrong")),
            )
        with self.assertRaisesRegex(ProtocolShapeError, "requires a result diff"):
            replace(scenario_result, scenario=replace(scenario, result_diff=None))
        with self.assertRaisesRegex(ProtocolShapeError, "effective rows"):
            replace(
                scenario_result,
                scenario=replace(
                    scenario,
                    result_diff=ScenarioResultDiffV0(
                        1,
                        1,
                        _token("baseline"),
                        _token("wrong-rows"),
                        True,
                    ),
                ),
            )

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

        with self.assertRaisesRegex(ProtocolShapeError, "adapter provenance envelopes"):
            _single_row_result(provenance_envelope=bad_envelope)

    def test_detached_row_live_helper_raises(self) -> None:
        run_id, result_id, _expr, _rules, _view, _semantics, closed_head_digest, *_rest, head = _result_parts()
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
        self.assertIs(explanation.row, result[0])
        self.assertEqual(explanation.result_id, result.result_id)
        self.assertEqual(explanation.failure_class, None)
        self.assertEqual(explanation.checked_scope["config_digest"], config_digest)
        self.assertEqual(explanation.checked_scope["semantics_source"], "row_result")
        self.assertEqual(explanation.checked_scope["evaluate_config_digest"], config_digest)
        self.assertEqual(explanation.checked_scope["explain_config_digest"], config_digest)
        self.assertEqual(explanation.checked_scope["semantics_match"], True)
        self.assertTrue(explanation.evidence.paths)
        self.assertEqual(explanation.evidence.paths[0].tree_id, result[0].row_id)
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
        self.assertEqual(explanation.evidence.metadata["claim_digest"], result[0].digest)
        self.assertEqual(explanation.evidence.metadata["closed_head_digest"], result[0].closed_head_digest)
        self.assertEqual(explanation.evidence.metadata["expr_digest"], expr_digest)
        self.assertEqual(explanation.evidence.metadata["rule_set_digest"], rule_set_digest)
        self.assertEqual(explanation.evidence.metadata["view_snapshot_digest"], view_snapshot_digest)
        self.assertEqual(explanation.evidence.metadata["config_digest"], config_digest)
        self.assertEqual(explanation.evidence.metadata["result_digest"], result_digest)
        self.assertEqual(explanation.evidence.metadata["engine"], engine)
        self.assertEqual(explanation.evidence.metadata["engine_version"], None)
        self.assertEqual(explanation.evidence.metadata["adapter_version"], None)
        self.assertEqual(explanation.evidence.metadata["evaluated_at"], "2026-05-25T00:00:00Z")
        self.assertEqual(explanation.evidence.paths[0].rules[0].role, "head")
        self.assertEqual(explanation.evidence.paths[0].rules[0].rule_id, result.head.id)

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
        self.assertTrue(graph.paths)
        self.assertEqual(graph.layout_hint, LAYOUT_TREE)
        self.assertEqual(graph.paths[0].tree_id, result[0].row_id)
        self.assertEqual(graph.paths[0].rules[0].role, "head")

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
        self.assertTrue(explanation.evidence.paths)
        self.assertFalse(hasattr(explanation.evidence, "nodes"))

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
        self.assertTrue(graph.paths)
        self.assertEqual(graph.layout_hint, LAYOUT_TREE)
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
        self.assertEqual(graph.paths[0].rules[0].role, "head")

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
        self.assertTrue(explanation.evidence.paths)
        self.assertFalse(hasattr(explanation.evidence, "edges"))

    def test_explanation_status_matrix_is_enforced(self) -> None:
        run_id, result_id, _expr, _rules, _view, _semantics, closed_head_digest, *_rest, head = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})

        with self.assertRaisesRegex(ProtocolShapeError, "iff"):
            Explanation(
                status="passed",
                evidence=None,
                row=row,
                result_id=result_id,
            )
        with self.assertRaisesRegex(ProtocolShapeError, "iff"):
            Explanation(
                status="failed",
                evidence=None,
                row=row,
                result_id=result_id,
            )
        with self.assertRaisesRegex(ProtocolShapeError, "failure_class"):
            Explanation(
                status="failed",
                evidence=_graph_with_metadata(row, _single_row_result(), {}),
                row=row,
                result_id=result_id,
            )
        with self.assertRaisesRegex(ProtocolShapeError, "errors"):
            Explanation(
                status="unsupported",
                evidence=None,
                row=row,
                result_id=result_id,
            )

    def test_manual_explanation_uses_row_reference(self) -> None:
        run_id, result_id, _expr, _rules, _view, _semantics, closed_head_digest, *_rest = _result_parts()
        row = _row(result_id, run_id, closed_head_digest, {"person": "p1"})

        explanation = Explanation(
            status="passed",
            evidence=EvidenceGraph(
                graph_id="manual",
                engine="native",
                layout_hint=LAYOUT_TREE,
                subject_binding=row.bindings,
                paths=(
                    EvidenceTree(
                        tree_id="root",
                        status="holds",
                        rules=(
                            EvidenceRule(
                                occurrence_alias="manual",
                                rule_id="manual",
                                role="head",
                                status="holds",
                                ports=row.bindings,
                                atoms=(),
                            ),
                        ),
                        joins=(),
                    ),
                ),
                metadata={},
            ),
            row=row,
            result_id=result_id,
        )

        self.assertEqual(explanation.status, "passed")
        self.assertIs(explanation.row, row)

        failed = Explanation(
            status="failed",
            evidence=explanation.evidence,
            row=row,
            result_id=result_id,
            failure_class="no_matching_row",
            suggested_next_steps=("Retry with a closed head.",),
        )
        self.assertEqual(failed.failure_class, "no_matching_row")

        invalid = Explanation(
            status="invalid_request",
            evidence=None,
            row=None,
            result_id=None,
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
            kind=outside_row.kind,
            digest=outside_row.digest,
            closed_head_digest=outside_row.closed_head_digest,
            certainty=outside_row.certainty,
            _result_resolver=lambda: result,
        )

        explanation = live_outside_row.explain()

        self.assertEqual(explanation.status, "unsupported")
        self.assertIsNone(explanation.failure_class)
        self.assertEqual(explanation.errors[0].code, "ROW_NOT_IN_RESULT")
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
        run_id, result_id, _expr, _rules, _view, _semantics, closed_head_digest, *_rest, head = _result_parts()
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

        row = _derivation_output_to_evaluate_row(
            candidate,
            head=head,
            result_id=result_id,
            run_id=run_id,
            closed_head_digest=closed_head_digest,
        )

        self.assertEqual(dict(row.bindings), {"person": {"kind": "const", "value": "p1"}})
        self.assertEqual(row.certainty, Certainty(0.75, 0.75, "probabilistic"))
        self.assertFalse(hasattr(row, "candidate_id"))
        self.assertEqual(row.digest, claim_digest_for(row.kind, "Person:exists", row.bindings))

        native_row = _derivation_output_to_evaluate_row(
            CandidateSet(
                derivation_id="native",
                derivation_version="v1",
                run_id="legacy-run",
                target="Person:exists",
                key_tuple_digest=_token("native-key"),
                tup_digest=None,
                payload={"terms": [{"kind": "const", "value": "p1"}]},
                support_digest=_token("native-support"),
                support_kind="native",
                generated_at=1,
                state="candidate",
            ),
            head=head,
            result_id=result_id,
            run_id=run_id,
            closed_head_digest=closed_head_digest,
        )
        pyreason_row = _derivation_output_to_evaluate_row(
            CandidateSet(
                derivation_id="pyreason",
                derivation_version="v1",
                run_id="legacy-run",
                target="Person:exists",
                key_tuple_digest=_token("pyreason-key"),
                tup_digest=None,
                payload={"terms": [{"kind": "const", "value": "p1"}]},
                support_digest=_token("pyreason-support"),
                support_kind="native",
                generated_at=1,
                state="candidate",
                confidence=0.4,
                confidence_kind="certainty",
            ),
            head=head,
            result_id=result_id,
            run_id=run_id,
            closed_head_digest=closed_head_digest,
        )

        self.assertEqual(native_row.certainty, BOOLEAN_CERTAINTY)
        self.assertEqual(pyreason_row.certainty, Certainty(0.4, 0.4, "possibilistic"))


class RowConclusionNodeReprTests(unittest.TestCase):
    """Conclusion node's value_summary must use Rule.render_repr when head has repr."""

    def _build_result_with_head(self, head: Rule, row_bindings: dict[str, object]) -> tuple[EvaluateRow, EvaluateResult]:
        run_id = "run_v1:" + "1" * 64
        engine = "native"
        expr_digest = _token("expr")
        rule_set_digest = _token("rules")
        view_snapshot_digest = _token("view")
        config_digest = _token("config")
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
        row = EvaluateRow(
            row_id=row_id_for(run_id, row_bindings),
            bindings=row_bindings,
            kind="fact_triple",
            digest=claim_digest_for("fact_triple", head.id, row_bindings),
            closed_head_digest=closed_head_digest,
            certainty=BOOLEAN_CERTAINTY,
        )
        result = EvaluateResult(
            result_id=result_id,
            rows=(row,),
            head=head,
            engine=engine,
            evaluated_at="2026-06-04T00:00:00Z",
            fingerprint=ResultFingerprint(
                expr_digest=expr_digest,
                rule_set_digest=rule_set_digest,
                view_snapshot_digest=view_snapshot_digest,
                config_digest=config_digest,
                result_digest=_token("result"),
                run_id=run_id,
            ),
            engine_meta={"engine_version": "test", "adapter_version": "test"},
        )
        return row, result

    def test_value_summary_uses_rendered_repr_when_head_has_repr(self) -> None:
        from factgraph.application.protocol.evaluate_result import _build_minimal_row_evidence_graph

        user_var = Var("$user")
        head = Rule(
            id="adults_in_us",
            when=(PredAtom("user:region", [user_var, Const("US")]),),
            ports={"user": user_var},
            repr="Adult user %user lives in the US",
        )
        bindings = {"user": {"kind": "entity_ref", "value": "idref_v1:User:alice"}}
        row, result = self._build_result_with_head(head, bindings)

        graph = _build_minimal_row_evidence_graph(row, result, _evidence_metadata_for_test(row, result))

        self.assertEqual(graph.paths[0].rules[0].rule_id, "adults_in_us")
        self.assertEqual(graph.paths[0].rules[0].role, "head")

    def test_value_summary_falls_back_to_claim_repr_when_head_has_no_repr(self) -> None:
        from factgraph.application.protocol.evaluate_result import _build_minimal_row_evidence_graph

        head = _head_rule()
        bindings = {"person": {"kind": "entity_ref", "value": "idref_v1:Person:alice"}}
        row, result = self._build_result_with_head(head, bindings)

        graph = _build_minimal_row_evidence_graph(row, result, _evidence_metadata_for_test(row, result))

        self.assertEqual(graph.paths[0].rules[0].rule_id, "person_head")
        self.assertFalse(graph.paths[0].rules[0].atoms)


if __name__ == "__main__":
    unittest.main()
