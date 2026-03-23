from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from factpy_kernel.adapters.souffle.package import ExportOptions, export_package
from factpy_kernel.audit import (
    AuditQuery,
    ECSS_COMPLIANCE_STATUS_PRED_ID,
    ECSS_REQUIREMENT_PRED_ID,
    ECSS_REQUIREMENT_RID_PRED_ID,
    ECSS_REVIEW_MILESTONE_PRED_ID,
    ECSS_VERIFICATION_METHOD_PRED_ID,
    build_candidate_evidence_tree_narrative_dto,
    build_candidate_evidence_tree_summary_dto,
    build_candidate_evidence_tree_dto,
    build_rule_trace_narrative_dto,
    build_rule_trace_detail_dto,
    build_rule_trace_summary_dto,
    build_rule_trace_summary_list_dto,
    build_compliance_matrix_dto,
    extend_schema_ir_with_ecss_vcd_predicates,
    load_audit_package,
    render_audit_static_site,
)
from factpy_kernel.audit.assertions import load_assertion_index
from factpy_kernel.audit.static_ui import _slug_id
from factpy_kernel.authoring import (
    AuthoringDerivationCompileError,
    FileAuthoringRegistry,
    build_derivation_preview_dto,
    compile_authoring_schema_v1,
    compile_authoring_derivation_v1,
    parse_authoring_schema_dsl_v1,
    parse_authoring_derivation_dsl_v1,
)
from factpy_kernel.authoring.where_schema_lowering import (
    WhereSchemaLoweringError,
    lower_blueprint_where_sugar_with_schema_v1,
)
from factpy_kernel.domains.ecss import (
    ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
    ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
    ECSS_INTERVAL_END_PRED_ID,
    ECSS_INTERVAL_START_PRED_ID,
    ECSS_OBLIGATION_TIMESTAMP_PRED_ID,
    ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
    ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
    ECSS_WINDOW_END_PRED_ID,
    ECSS_WINDOW_START_PRED_ID,
    EcssTemporalError,
    EcssUncertaintyError,
    EcssVcdError,
    extend_schema_ir_with_ecss_uncertainty_predicates,
    extend_schema_ir_with_ecss_temporal_predicates,
)
from factpy_kernel.core.rules.rule_ir import (
    RuleCompileError,
    RuleRegistry,
    RuleSpec,
    run_rule_with_trace,
)
from factpy_kernel.core.rules._trace import (
    RuleTraceArtifact,
    RuleTraceInvocation,
    RuleTraceRuleRefLink,
    rule_trace_artifact_from_dict,
    rule_trace_artifact_to_dict,
    summarize_rule_trace_artifact_dict,
)
from factpy_kernel.core.rules._trace_nl import render_rule_run_nl_explain
from factpy_kernel.core.rules._trace_narrative import render_rule_run_narrative
from factpy_kernel.core.rules.ruleref_types import NativeRuleRefResolution, NativeRuleRefRowSupport
from factpy_kernel.core.rules.where_eval import WhereValidationError, _plan_body_atoms
from factpy_kernel.core.store import Store, register_engine_evaluator
import factpy_kernel.core.store._builders as store_builders
from factpy_kernel.core.store._artifact_sidecar import FileArtifactSidecar, GCResult
from factpy_kernel.core.store._candidate_evidence_tree_narrative import render_candidate_evidence_tree_narrative
from factpy_kernel.core.store._candidate_evidence_tree_nl import render_candidate_evidence_tree_nl_explain
from factpy_kernel.core.store._candidate_evidence_tree_summary import summarize_candidate_evidence_tree_dict
from factpy_kernel.core.store._support_capture import (
    build_support_artifact_for_binding,
    derive_rule_ref_edges_for_binding,
    find_winning_branch_index,
)
from factpy_kernel.core.store._support import (
    ENGINE_NO_WITNESS_KIND,
    ProjectedFact,
    compute_support_digest,
    support_artifact_from_dict,
    support_artifact_to_dict,
)
from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.core.view.projector import project_view_facts
from factpy_kernel.sdk import (
    Body,
    Derivation,
    Entity,
    Field,
    Identity,
    Not,
    Pred,
    Query,
    Rule,
    RuleRef,
    SDKDSLError,
    SDKStore,
    SDKStoreError,
    compile_schema_from_classes,
    vars as sdk_vars,
)
from factpy_kernel.sdk.ecss import (
    apply_ecss_vcd_schema,
    make_ecss_requirement_ref,
    write_ecss_requirement_bundle,
)
from factpy_kernel.sdk.ingest import CONVENTION_META_KEYS, SENSITIVE_SEMANTIC_META_KEYS
from factpy_kernel.service.app_v1 import app
from factpy_kernel.service.runtime_v1 import (
    _require_session,
    accept_runtime_derivation,
    close_runtime_session,
    evaluate_runtime_derivation,
    explain_runtime_nl,
    explain_runtime_narrative,
    explain_runtime_ref,
    explain_runtime_rule_trace,
    explain_runtime_summary,
    explain_runtime_support,
    explain_runtime_tree,
    export_runtime_package,
    open_runtime_session,
    project_runtime_view_facts,
    retract_runtime_fact,
    reset_runtime_sessions_for_tests,
    run_runtime_rule,
    write_runtime_fact,
)
from factpy_kernel.tests._test_helpers import User, _schema_ir, _seed_users_for_syntax_matrix


class EcssComplianceContractsTests(unittest.TestCase):
    def test_ecss_vcd_schema_helper_extends_schema_ir_idempotently(self) -> None:
        base = _schema_ir()
        extended = extend_schema_ir_with_ecss_vcd_predicates(base)
        extended_again = extend_schema_ir_with_ecss_vcd_predicates(extended)

        pred_ids = [pred["pred_id"] for pred in extended["predicates"]]
        self.assertIn(ECSS_REQUIREMENT_PRED_ID, pred_ids)
        self.assertIn(ECSS_VERIFICATION_METHOD_PRED_ID, pred_ids)
        self.assertIn(ECSS_COMPLIANCE_STATUS_PRED_ID, pred_ids)
        self.assertIn(ECSS_REQUIREMENT_RID_PRED_ID, pred_ids)
        self.assertIn(ECSS_REVIEW_MILESTONE_PRED_ID, pred_ids)

        self.assertEqual(pred_ids.count(ECSS_REQUIREMENT_PRED_ID), 1)
        self.assertEqual(extended_again["predicates"], extended["predicates"])
        self.assertEqual(
            extended_again["projection"]["predicates"],
            extended["projection"]["predicates"],
        )

    def test_shared_ecss_vcd_schema_helper_rejects_invalid_shape(self) -> None:
        with self.assertRaises(EcssVcdError):
            apply_ecss_vcd_schema(["not-a-schema"])  # type: ignore[arg-type]

    def test_ecss_temporal_schema_helper_extends_schema_ir_idempotently(self) -> None:
        base = _schema_ir()
        extended = extend_schema_ir_with_ecss_temporal_predicates(base)
        extended_again = extend_schema_ir_with_ecss_temporal_predicates(extended)

        pred_ids = [pred["pred_id"] for pred in extended["predicates"]]
        self.assertIn(ECSS_OBLIGATION_TIMESTAMP_PRED_ID, pred_ids)
        self.assertIn(ECSS_WINDOW_START_PRED_ID, pred_ids)
        self.assertIn(ECSS_WINDOW_END_PRED_ID, pred_ids)
        self.assertIn(ECSS_INTERVAL_START_PRED_ID, pred_ids)
        self.assertIn(ECSS_INTERVAL_END_PRED_ID, pred_ids)

        self.assertEqual(pred_ids.count(ECSS_OBLIGATION_TIMESTAMP_PRED_ID), 1)
        self.assertEqual(extended_again["predicates"], extended["predicates"])
        self.assertEqual(
            extended_again["projection"]["predicates"],
            extended["projection"]["predicates"],
        )

    def test_shared_ecss_temporal_schema_helper_rejects_invalid_shape(self) -> None:
        with self.assertRaises(EcssTemporalError):
            extend_schema_ir_with_ecss_temporal_predicates(["not-a-schema"])  # type: ignore[arg-type]

    def test_ecss_uncertainty_schema_helper_extends_schema_ir_idempotently(self) -> None:
        base = _schema_ir()
        extended = extend_schema_ir_with_ecss_uncertainty_predicates(base)
        extended_again = extend_schema_ir_with_ecss_uncertainty_predicates(extended)

        pred_ids = [pred["pred_id"] for pred in extended["predicates"]]
        self.assertIn(ECSS_COLLISION_PROBABILITY_PPM_PRED_ID, pred_ids)
        self.assertIn(ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID, pred_ids)
        self.assertIn(ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID, pred_ids)
        self.assertIn(ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID, pred_ids)

        self.assertEqual(pred_ids.count(ECSS_COLLISION_PROBABILITY_PPM_PRED_ID), 1)
        self.assertEqual(extended_again["predicates"], extended["predicates"])
        self.assertEqual(
            extended_again["projection"]["predicates"],
            extended["projection"]["predicates"],
        )

    def test_shared_ecss_uncertainty_schema_helper_rejects_invalid_shape(self) -> None:
        with self.assertRaises(EcssUncertaintyError):
            extend_schema_ir_with_ecss_uncertainty_predicates(["not-a-schema"])  # type: ignore[arg-type]

    def test_temporal_deadline_and_window_checks_reuse_cmp_trace_contract(self) -> None:
        schema_ir = extend_schema_ir_with_ecss_temporal_predicates(_schema_ir())
        sdk = SDKStore([User], schema_ir=schema_ir)

        obligation_ref = encode_idref_v1("ECSSObligation", [("obligation_id", "string", "OB-001")])
        with patch(
            "factpy_kernel.core.evidence.write_protocol.now_epoch_nanos",
            side_effect=[100, 110, 120],
        ):
            obligation_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_OBLIGATION_TIMESTAMP_PRED_ID,
                obligation_ref,
                [("time", 100)],
            )
            window_start_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_WINDOW_START_PRED_ID,
                obligation_ref,
                [("time", 80)],
            )
            window_end_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_WINDOW_END_PRED_ID,
                obligation_ref,
                [("time", 120)],
            )

        with sdk_vars("o", "event_ts", "start_ts", "cutoff_ts") as (o, event_ts, start_ts, cutoff_ts):
            deadline_window_rule = Rule(
                id="q.temporal_deadline_window_ok",
                version="1.0.0",
                select=[o],
                where=[
                    Pred(ECSS_OBLIGATION_TIMESTAMP_PRED_ID, o, event_ts),
                    Pred(ECSS_WINDOW_START_PRED_ID, o, start_ts),
                    Pred(ECSS_WINDOW_END_PRED_ID, o, cutoff_ts),
                    start_ts <= event_ts,
                    event_ts <= cutoff_ts,
                ],
            )

        compiled = sdk._compile_rule_input(deadline_window_rule)
        rule_spec = RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )

        trace_result = run_rule_with_trace(sdk.store, rule_spec, RuleRegistry())
        self.assertEqual(trace_result.rows, [(obligation_ref,)])

        trace = sdk.store.explain_rule_trace(trace_result.rule_run_id)
        self.assertIsNotNone(trace)
        assert trace is not None
        invocation = next(inv for inv in trace["invocations"] if inv["rule"]["rule_id"] == "q.temporal_deadline_window_ok")

        witness_map = {
            witness["pred_atom_key"]: tuple(witness["asrt_ids"])
            for witness in invocation["pred_witnesses"]
        }
        self.assertEqual(witness_map["b0.a0:ecss:obligation_timestamp"], (obligation_asrt_id,))
        self.assertEqual(witness_map["b0.a1:ecss:window_start"], (window_start_asrt_id,))
        self.assertEqual(witness_map["b0.a2:ecss:window_end"], (window_end_asrt_id,))

        non_fact_by_key = {step["step_key"]: step for step in invocation["non_fact_steps"]}
        self.assertEqual(non_fact_by_key["b0.a3:le"]["kind"], "le")
        self.assertEqual(non_fact_by_key["b0.a4:le"]["kind"], "le")

        step_details = dict(non_fact_by_key["b0.a4:le"]["details"])
        binding_rows = dict(step_details["binding"])
        self.assertEqual(binding_rows["$event_ts"], 100)
        self.assertEqual(binding_rows["$cutoff_ts"], 120)

    def test_temporal_interval_relation_can_be_expressed_via_helper_rule(self) -> None:
        schema_ir = extend_schema_ir_with_ecss_temporal_predicates(_schema_ir())
        sdk = SDKStore([User], schema_ir=schema_ir)

        interval_outer = encode_idref_v1("ECSSInterval", [("interval_id", "string", "I-OUTER")])
        interval_inner = encode_idref_v1("ECSSInterval", [("interval_id", "string", "I-INNER")])
        interval_overlap = encode_idref_v1("ECSSInterval", [("interval_id", "string", "I-OVERLAP")])

        with patch(
            "factpy_kernel.core.evidence.write_protocol.now_epoch_nanos",
            side_effect=[100, 110, 120, 130, 140, 150],
        ):
            set_field(sdk.store.ledger, ECSS_INTERVAL_START_PRED_ID, interval_outer, [("time", 0)])
            set_field(sdk.store.ledger, ECSS_INTERVAL_END_PRED_ID, interval_outer, [("time", 20)])
            set_field(sdk.store.ledger, ECSS_INTERVAL_START_PRED_ID, interval_inner, [("time", 5)])
            set_field(sdk.store.ledger, ECSS_INTERVAL_END_PRED_ID, interval_inner, [("time", 10)])
            set_field(sdk.store.ledger, ECSS_INTERVAL_START_PRED_ID, interval_overlap, [("time", 15)])
            set_field(sdk.store.ledger, ECSS_INTERVAL_END_PRED_ID, interval_overlap, [("time", 25)])

        with sdk_vars("outer", "inner", "outer_start", "outer_end", "inner_start", "inner_end") as (
            outer,
            inner,
            outer_start,
            outer_end,
            inner_start,
            inner_end,
        ):
            interval_contains = Rule(
                id="q.interval_contains",
                version="1.0.0",
                select=[outer, inner],
                where=[
                    Pred(ECSS_INTERVAL_START_PRED_ID, outer, outer_start),
                    Pred(ECSS_INTERVAL_END_PRED_ID, outer, outer_end),
                    Pred(ECSS_INTERVAL_START_PRED_ID, inner, inner_start),
                    Pred(ECSS_INTERVAL_END_PRED_ID, inner, inner_end),
                    outer != inner,
                    outer_start <= inner_start,
                    inner_end <= outer_end,
                ],
                expose=True,
            )
            interval_contains_pairs = Rule(
                id="q.interval_contains_pairs",
                version="1.0.0",
                select=[outer, inner],
                where=[RuleRef(interval_contains)(outer, inner)],
            )

        registry = RuleRegistry()
        sdk._register_rule_dependencies(registry, interval_contains_pairs)
        compiled = sdk._compile_rule_input(interval_contains_pairs)
        rule_spec = RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )

        trace_result = run_rule_with_trace(sdk.store, rule_spec, registry)
        self.assertEqual(trace_result.rows, [(interval_outer, interval_inner)])

        trace = sdk.store.explain_rule_trace(trace_result.rule_run_id)
        self.assertIsNotNone(trace)
        assert trace is not None
        root_invocation = next(inv for inv in trace["invocations"] if inv["rule"]["rule_id"] == "q.interval_contains_pairs")
        helper_invocation = next(inv for inv in trace["invocations"] if inv["rule"]["rule_id"] == "q.interval_contains")

        self.assertEqual(len(root_invocation["ruleref_links"]), 1)
        self.assertEqual(root_invocation["ruleref_links"][0]["child_invocation_id"], helper_invocation["invocation_id"])
        helper_step_kinds = {step["kind"] for step in helper_invocation["non_fact_steps"]}
        self.assertIn("not", helper_step_kinds)
        self.assertIn("le", helper_step_kinds)
        self.assertTrue(any(witness["asrt_ids"] for witness in helper_invocation["pred_witnesses"]))

    def test_uncertainty_threshold_checks_reuse_cmp_trace_contract(self) -> None:
        schema_ir = extend_schema_ir_with_ecss_uncertainty_predicates(_schema_ir())
        sdk = SDKStore([User], schema_ir=schema_ir)

        assessment_ref = encode_idref_v1("ECSSRiskAssessment", [("assessment_id", "string", "RA-001")])
        with patch(
            "factpy_kernel.core.evidence.write_protocol.now_epoch_nanos",
            side_effect=[100, 110, 120, 130],
        ):
            collision_prob_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
                assessment_ref,
                [("int", 80)],
            )
            collision_threshold_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
                assessment_ref,
                [("int", 100)],
            )
            success_prob_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
                assessment_ref,
                [("int", 920000)],
            )
            success_threshold_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
                assessment_ref,
                [("int", 900000)],
            )

        with sdk_vars(
            "assessment",
            "pc_ppm",
            "pc_threshold_ppm",
            "success_ppm",
            "success_threshold_ppm",
        ) as (assessment, pc_ppm, pc_threshold_ppm, success_ppm, success_threshold_ppm):
            uncertainty_rule = Rule(
                id="q.uncertainty_threshold_ok",
                version="1.0.0",
                select=[assessment],
                where=[
                    Pred(ECSS_COLLISION_PROBABILITY_PPM_PRED_ID, assessment, pc_ppm),
                    Pred(ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID, assessment, pc_threshold_ppm),
                    Pred(ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID, assessment, success_ppm),
                    Pred(ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID, assessment, success_threshold_ppm),
                    pc_ppm <= pc_threshold_ppm,
                    success_ppm >= success_threshold_ppm,
                ],
            )

        compiled = sdk._compile_rule_input(uncertainty_rule)
        rule_spec = RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )

        trace_result = run_rule_with_trace(sdk.store, rule_spec, RuleRegistry())
        self.assertEqual(trace_result.rows, [(assessment_ref,)])

        trace = sdk.store.explain_rule_trace(trace_result.rule_run_id)
        self.assertIsNotNone(trace)
        assert trace is not None
        invocation = next(inv for inv in trace["invocations"] if inv["rule"]["rule_id"] == "q.uncertainty_threshold_ok")

        witness_map = {
            witness["pred_atom_key"]: tuple(witness["asrt_ids"])
            for witness in invocation["pred_witnesses"]
        }
        self.assertEqual(witness_map["b0.a0:ecss:collision_probability_ppm"], (collision_prob_asrt_id,))
        self.assertEqual(
            witness_map["b0.a1:ecss:collision_probability_threshold_ppm"],
            (collision_threshold_asrt_id,),
        )
        self.assertEqual(
            witness_map["b0.a2:ecss:disposal_success_probability_ppm"],
            (success_prob_asrt_id,),
        )
        self.assertEqual(
            witness_map["b0.a3:ecss:disposal_success_threshold_ppm"],
            (success_threshold_asrt_id,),
        )

        non_fact_by_key = {step["step_key"]: step for step in invocation["non_fact_steps"]}
        self.assertEqual(non_fact_by_key["b0.a4:le"]["kind"], "le")
        self.assertEqual(non_fact_by_key["b0.a5:ge"]["kind"], "ge")

        le_details = dict(non_fact_by_key["b0.a4:le"]["details"])
        le_binding = dict(le_details["binding"])
        self.assertEqual(le_binding["$pc_ppm"], 80)
        self.assertEqual(le_binding["$pc_threshold_ppm"], 100)

        ge_details = dict(non_fact_by_key["b0.a5:ge"]["details"])
        ge_binding = dict(ge_details["binding"])
        self.assertEqual(ge_binding["$success_ppm"], 920000)
        self.assertEqual(ge_binding["$success_threshold_ppm"], 900000)

    def test_scenario_a_composite_reference_check_has_live_and_audit_parity(self) -> None:
        schema_ir = extend_schema_ir_with_ecss_temporal_predicates(_schema_ir())
        schema_ir = extend_schema_ir_with_ecss_uncertainty_predicates(schema_ir)
        sdk = SDKStore([User], schema_ir=schema_ir)

        assessment_ref = encode_idref_v1("ECSSAssessment", [("assessment_id", "string", "A-COMPOSITE-001")])
        with patch(
            "factpy_kernel.core.evidence.write_protocol.now_epoch_nanos",
            side_effect=[100, 110, 120, 130, 140, 150, 160],
        ):
            event_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_OBLIGATION_TIMESTAMP_PRED_ID,
                assessment_ref,
                [("time", 100)],
            )
            window_start_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_WINDOW_START_PRED_ID,
                assessment_ref,
                [("time", 80)],
            )
            window_end_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_WINDOW_END_PRED_ID,
                assessment_ref,
                [("time", 120)],
            )
            collision_prob_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_COLLISION_PROBABILITY_PPM_PRED_ID,
                assessment_ref,
                [("int", 80)],
            )
            collision_threshold_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID,
                assessment_ref,
                [("int", 100)],
            )
            success_prob_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID,
                assessment_ref,
                [("int", 920000)],
            )
            success_threshold_asrt_id = set_field(
                sdk.store.ledger,
                ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID,
                assessment_ref,
                [("int", 900000)],
            )

        with sdk_vars(
            "assessment",
            "event_ts",
            "window_start_ts",
            "window_end_ts",
            "pc_ppm",
            "pc_threshold_ppm",
            "success_ppm",
            "success_threshold_ppm",
        ) as (
            assessment,
            event_ts,
            window_start_ts,
            window_end_ts,
            pc_ppm,
            pc_threshold_ppm,
            success_ppm,
            success_threshold_ppm,
        ):
            composite_rule = Rule(
                id="q.scenario_a_composite_reference_check",
                version="1.0.0",
                select=[assessment],
                where=[
                    Pred(ECSS_OBLIGATION_TIMESTAMP_PRED_ID, assessment, event_ts),
                    Pred(ECSS_WINDOW_START_PRED_ID, assessment, window_start_ts),
                    Pred(ECSS_WINDOW_END_PRED_ID, assessment, window_end_ts),
                    Pred(ECSS_COLLISION_PROBABILITY_PPM_PRED_ID, assessment, pc_ppm),
                    Pred(ECSS_COLLISION_PROBABILITY_THRESHOLD_PPM_PRED_ID, assessment, pc_threshold_ppm),
                    Pred(ECSS_DISPOSAL_SUCCESS_PROBABILITY_PPM_PRED_ID, assessment, success_ppm),
                    Pred(ECSS_DISPOSAL_SUCCESS_THRESHOLD_PPM_PRED_ID, assessment, success_threshold_ppm),
                    window_start_ts <= event_ts,
                    event_ts <= window_end_ts,
                    pc_ppm <= pc_threshold_ppm,
                    success_ppm >= success_threshold_ppm,
                ],
            )

        compiled = sdk._compile_rule_input(composite_rule)
        rule_spec = RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )

        trace_result = run_rule_with_trace(sdk.store, rule_spec, RuleRegistry())
        self.assertEqual(trace_result.rows, [(assessment_ref,)])

        live_trace = sdk.store.explain_rule_trace(trace_result.rule_run_id)
        self.assertIsNotNone(live_trace)
        assert live_trace is not None
        live_invocation = next(
            inv
            for inv in live_trace["invocations"]
            if inv["rule"]["rule_id"] == "q.scenario_a_composite_reference_check"
        )

        self.assertEqual(live_trace["root_rule"], {"rule_id": "q.scenario_a_composite_reference_check", "version": "1.0.0"})
        self.assertEqual(len(live_invocation["pred_witnesses"]), 7)
        self.assertEqual(len(live_invocation["non_fact_steps"]), 4)

        live_witness_map = {
            witness["pred_atom_key"]: tuple(witness["asrt_ids"])
            for witness in live_invocation["pred_witnesses"]
        }
        self.assertEqual(live_witness_map["b0.a0:ecss:obligation_timestamp"], (event_asrt_id,))
        self.assertEqual(live_witness_map["b0.a1:ecss:window_start"], (window_start_asrt_id,))
        self.assertEqual(live_witness_map["b0.a2:ecss:window_end"], (window_end_asrt_id,))
        self.assertEqual(live_witness_map["b0.a3:ecss:collision_probability_ppm"], (collision_prob_asrt_id,))
        self.assertEqual(
            live_witness_map["b0.a4:ecss:collision_probability_threshold_ppm"],
            (collision_threshold_asrt_id,),
        )
        self.assertEqual(
            live_witness_map["b0.a5:ecss:disposal_success_probability_ppm"],
            (success_prob_asrt_id,),
        )
        self.assertEqual(
            live_witness_map["b0.a6:ecss:disposal_success_threshold_ppm"],
            (success_threshold_asrt_id,),
        )

        live_non_fact_by_key = {step["step_key"]: step for step in live_invocation["non_fact_steps"]}
        self.assertEqual(sorted(live_non_fact_by_key.keys()), ["b0.a10:ge", "b0.a7:le", "b0.a8:le", "b0.a9:le"])

        ge_binding = dict(dict(live_non_fact_by_key["b0.a10:ge"]["details"])["binding"])
        self.assertEqual(ge_binding["$window_start_ts"], 80)
        self.assertEqual(ge_binding["$event_ts"], 100)
        self.assertEqual(ge_binding["$window_end_ts"], 120)
        self.assertEqual(ge_binding["$pc_ppm"], 80)
        self.assertEqual(ge_binding["$pc_threshold_ppm"], 100)
        self.assertEqual(ge_binding["$success_ppm"], 920000)
        self.assertEqual(ge_binding["$success_threshold_ppm"], 900000)

        with TemporaryDirectory() as package_dir, TemporaryDirectory() as site_dir:
            manifest_path = export_package(
                sdk.store,
                Path(package_dir),
                ExportOptions(package_kind="audit"),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            audit_files = manifest["paths"]["audit_files"]

            trace_rows = [
                json.loads(line)
                for line in (Path(package_dir) / audit_files["rule_trace_artifacts"]).read_text(encoding="utf-8").splitlines()
                if line
            ]
            offline_trace_row = next(row for row in trace_rows if row["rule_run_id"] == trace_result.rule_run_id)
            self.assertEqual(offline_trace_row["root_rule"], live_trace["root_rule"])

            offline_artifact = rule_trace_artifact_from_dict(offline_trace_row)
            self.assertEqual(
                rule_trace_artifact_to_dict(offline_artifact),
                offline_trace_row,
            )

            offline_invocation = next(
                inv
                for inv in offline_trace_row["invocations"]
                if inv["rule"]["rule_id"] == "q.scenario_a_composite_reference_check"
            )
            self.assertEqual(offline_invocation["pred_witnesses"], live_invocation["pred_witnesses"])
            self.assertEqual(offline_invocation["non_fact_steps"], live_invocation["non_fact_steps"])

            package = load_audit_package(package_dir)
            self.assertEqual(package.manifest["package_kind"], "audit")
            self.assertTrue(package.rule_trace_artifacts)
            query = AuditQuery(package)
            loaded_trace = query.get_rule_trace(trace_result.rule_run_id)
            self.assertIsNotNone(loaded_trace)
            assert loaded_trace is not None
            self.assertEqual(loaded_trace["root_rule"], live_trace["root_rule"])
            self.assertEqual(
                [row["rule_run_id"] for row in query.list_rule_traces(root_rule_id="q.scenario_a_composite_reference_check")],
                [trace_result.rule_run_id],
            )

            site_manifest = render_audit_static_site(package_dir, site_dir)
            self.assertEqual(site_manifest["rule_trace_index"], "rule_traces.html")
            self.assertEqual(site_manifest["rule_trace_count"], 1)
            trace_page_rel = f"rule_traces/{_slug_id(trace_result.rule_run_id)}.html"
            self.assertEqual(site_manifest["rule_traces"], [trace_page_rel])
            witness_asrt_ids = sorted(
                {
                    asrt_id
                    for witness in live_invocation["pred_witnesses"]
                    for asrt_id in witness["asrt_ids"]
                }
            )
            for asrt_id in witness_asrt_ids:
                assertion_page = Path(site_dir) / "assertions" / f"{_slug_id(asrt_id)}.html"
                self.assertTrue(assertion_page.exists())

            sample_assertion_html = (
                Path(site_dir) / "assertions" / f"{_slug_id(collision_threshold_asrt_id)}.html"
            ).read_text(encoding="utf-8")
            self.assertIn(collision_threshold_asrt_id, sample_assertion_html)

            trace_index_html = (Path(site_dir) / "rule_traces.html").read_text(encoding="utf-8")
            self.assertIn(trace_result.rule_run_id, trace_index_html)
            self.assertIn("q.scenario_a_composite_reference_check", trace_index_html)

            trace_page_html = (Path(site_dir) / trace_page_rel).read_text(encoding="utf-8")
            self.assertIn(trace_result.rule_run_id, trace_page_html)
            self.assertIn("q.scenario_a_composite_reference_check", trace_page_html)
            self.assertIn("Narrative", trace_page_html)
            self.assertIn(
                "Rule q.scenario_a_composite_reference_check@1.0.0 produced 1 root row(s) across 1 invocation(s).",
                trace_page_html,
            )
            self.assertIn(
                "Predicate ecss:collision_probability_ppm was witnessed by 1 assertion(s) across 1 invocation(s).",
                trace_page_html,
            )
            self.assertIn(
                "Check kind le was evaluated 3 time(s) across 1 invocation(s).",
                trace_page_html,
            )
            self.assertIn(collision_threshold_asrt_id, trace_page_html)
            self.assertIn(f"../assertions/{_slug_id(collision_threshold_asrt_id)}.html", trace_page_html)

            index_html = (Path(site_dir) / "index.html").read_text(encoding="utf-8")
            self.assertIn("rule_traces.html", index_html)

            ui_index = json.loads((Path(site_dir) / "ui_index.json").read_text(encoding="utf-8"))
            self.assertEqual(ui_index["counts"]["rule_traces"], 1)
            self.assertEqual(ui_index["links"]["rule_traces"], "rule_traces.html")
            self.assertEqual(
                ui_index["lookup"]["rule_trace_pages"][trace_result.rule_run_id],
                trace_page_rel,
            )
            self.assertEqual(ui_index["rule_trace_index"]["count"], 1)

    def test_audit_query_builds_ecss_compliance_matrix_from_package_facts(self) -> None:
        schema_ir = extend_schema_ir_with_ecss_vcd_predicates(_schema_ir())
        store = Store(schema_ir)
        seeded = _seed_ecss_compliance_facts(store)
        req1_ref = seeded["req1_ref"]
        req2_ref = seeded["req2_ref"]
        open_asrt_id = seeded["open_asrt_id"]
        closed_asrt_id = seeded["closed_asrt_id"]

        with TemporaryDirectory() as tmp_dir:
            manifest_path = export_package(
                store,
                Path(tmp_dir),
                ExportOptions(package_kind="audit"),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertNotIn("compliance_matrix", manifest["paths"]["audit_files"])

            package = load_audit_package(tmp_dir)
            query = AuditQuery(package)

            rows = query.list_compliance_matrix()
            self.assertEqual([row["req_id"] for row in rows], ["REQ-001", "REQ-002"])

            req1 = next(row for row in rows if row["req_id"] == "REQ-001")
            self.assertEqual(req1["requirement_ref"], req1_ref)
            self.assertEqual(req1["title"], "Battery test evidence")
            self.assertEqual(req1["standard_ref"], "ECSS-M-ST-10/5.1")
            self.assertEqual(req1["status"], "closed")
            self.assertEqual(req1["status_asrt_id"], closed_asrt_id)
            self.assertNotEqual(req1["status_asrt_id"], open_asrt_id)
            self.assertEqual(req1["review_milestone"], "CDR")
            self.assertEqual(
                [item["method"] for item in req1["verification_methods"]],
                ["Analysis", "Test"],
            )
            self.assertTrue(all(len(item["asrt_ids"]) == 1 for item in req1["verification_methods"]))
            self.assertEqual([item["rid_id"] for item in req1["rid_links"]], ["RID-007"])
            self.assertEqual(len(req1["rid_links"][0]["asrt_ids"]), 1)

            req2 = next(row for row in rows if row["req_id"] == "REQ-002")
            self.assertEqual(req2["requirement_ref"], req2_ref)
            self.assertEqual(req2["title"], "Inspection note")
            self.assertIsNone(req2["standard_ref"])
            self.assertEqual(req2["status"], "waived")

            self.assertEqual(
                [row["req_id"] for row in query.list_compliance_matrix(status="closed")],
                ["REQ-001"],
            )
            self.assertEqual(
                [row["req_id"] for row in query.list_compliance_matrix(milestone="CDR")],
                ["REQ-001"],
            )

            dto = build_compliance_matrix_dto(query, status="closed")
            self.assertEqual(dto["audit_ui_dto_version"], "audit_ui_dto_v1")
            self.assertEqual(dto["kind"], "compliance_matrix")
            self.assertEqual(dto["count"], 1)
            self.assertEqual(dto["rows"][0]["req_id"], "REQ-001")

    def test_render_audit_static_site_includes_compliance_matrix_page(self) -> None:
        schema_ir = extend_schema_ir_with_ecss_vcd_predicates(_schema_ir())
        store = Store(schema_ir)
        seeded = _seed_ecss_compliance_facts(store)

        with TemporaryDirectory() as package_dir, TemporaryDirectory() as site_dir:
            export_package(
                store,
                Path(package_dir),
                ExportOptions(package_kind="audit"),
            )
            site_manifest = render_audit_static_site(package_dir, site_dir)

            self.assertEqual(site_manifest["compliance_matrix"], "compliance_matrix.html")
            self.assertEqual(site_manifest["compliance_matrix_row_count"], 2)

            compliance_path = Path(site_dir) / "compliance_matrix.html"
            self.assertTrue(compliance_path.exists())
            compliance_html = compliance_path.read_text(encoding="utf-8")
            self.assertIn("Compliance Matrix", compliance_html)
            self.assertIn("REQ-001", compliance_html)
            self.assertIn("Battery test evidence", compliance_html)
            self.assertIn("RID-007", compliance_html)
            self.assertIn(f"assertions/{seeded['closed_asrt_id']}.html", compliance_html)

            index_html = (Path(site_dir) / "index.html").read_text(encoding="utf-8")
            self.assertIn("compliance_matrix.html", index_html)

            ui_index = json.loads((Path(site_dir) / "ui_index.json").read_text(encoding="utf-8"))
            self.assertEqual(ui_index["links"]["compliance_matrix"], "compliance_matrix.html")
            self.assertEqual(ui_index["counts"]["compliance_matrix_rows"], 2)
            self.assertEqual(ui_index["compliance_matrix"]["count"], 2)

    def test_load_audit_package_keeps_legacy_packages_without_rule_trace_artifacts(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "audit").mkdir(parents=True, exist_ok=True)
            (root / "outputs").mkdir(parents=True, exist_ok=True)
            manifest = {
                "package_kind": "audit",
                "paths": {
                    "audit_files": {
                        "run_ledger": "audit/run_ledger.jsonl",
                        "candidate_ledger": "audit/candidate_ledger.jsonl",
                        "accept_write_ledger": "audit/accept_write_ledger.jsonl",
                        "accept_failed": "audit/accept_failed.jsonl",
                        "mapping_resolution": "audit/mapping_resolution.json",
                        "decision_log": "audit/decision_log.jsonl",
                    }
                },
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            for rel in (
                "audit/run_ledger.jsonl",
                "audit/candidate_ledger.jsonl",
                "audit/accept_write_ledger.jsonl",
                "audit/accept_failed.jsonl",
                "audit/decision_log.jsonl",
            ):
                (root / rel).write_text("", encoding="utf-8")
            (root / "audit/mapping_resolution.json").write_text("{}", encoding="utf-8")

            package = load_audit_package(root)
            self.assertEqual(package.support_artifacts, [])
            self.assertEqual(package.rule_trace_artifacts, [])
            self.assertEqual(AuditQuery(package).list_rule_traces(), [])

    def test_sdk_ecss_requirement_bundle_round_trips_into_compliance_matrix(self) -> None:
        schema_ir = apply_ecss_vcd_schema(_schema_ir())
        sdk = SDKStore([User], schema_ir=schema_ir)

        expected_ref = make_ecss_requirement_ref("REQ-100")
        written = write_ecss_requirement_bundle(
            sdk,
            req_id="REQ-100",
            title="Power budget closure",
            standard_ref="ECSS-M-ST-10/7.2",
            status="closed",
            verification_methods=["Analysis", "Review"],
            rid_links=["RID-100"],
            review_milestone="PDR",
            meta={"source": "seed", "trace_id": "ecss-req-100"},
        )

        self.assertEqual(written["requirement_ref"], expected_ref)
        self.assertEqual(len(written["verification_method_asrt_ids"]), 2)
        self.assertEqual(len(written["rid_asrt_ids"]), 1)

        with TemporaryDirectory() as tmp_dir:
            export_package(
                sdk.store,
                Path(tmp_dir),
                ExportOptions(package_kind="audit"),
            )
            package = load_audit_package(tmp_dir)
            rows = AuditQuery(package).list_compliance_matrix()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["req_id"], "REQ-100")
        self.assertEqual(rows[0]["requirement_ref"], expected_ref)
        self.assertEqual(rows[0]["status"], "closed")
        self.assertEqual(
            [item["method"] for item in rows[0]["verification_methods"]],
            ["Analysis", "Review"],
        )
        self.assertEqual([item["rid_id"] for item in rows[0]["rid_links"]], ["RID-100"])


def _seed_ecss_compliance_facts(store: Store) -> dict[str, str]:
    req1_ref = encode_idref_v1("ECSSRequirement", [("req_id", "string", "REQ-001")])
    req2_ref = encode_idref_v1("ECSSRequirement", [("req_id", "string", "REQ-002")])

    with patch(
        "factpy_kernel.core.evidence.write_protocol.now_epoch_nanos",
        side_effect=[100, 110, 120, 130, 140, 150, 160, 170, 180],
    ):
        requirement_asrt_id = set_field(
            store.ledger,
            ECSS_REQUIREMENT_PRED_ID,
            req1_ref,
            [
                ("string", "REQ-001"),
                ("string", "Battery test evidence"),
                ("string", "ECSS-M-ST-10/5.1"),
            ],
        )
        analysis_asrt_id = set_field(
            store.ledger,
            ECSS_VERIFICATION_METHOD_PRED_ID,
            req1_ref,
            [("string", "Analysis")],
        )
        test_asrt_id = set_field(
            store.ledger,
            ECSS_VERIFICATION_METHOD_PRED_ID,
            req1_ref,
            [("string", "Test")],
        )
        open_asrt_id = set_field(
            store.ledger,
            ECSS_COMPLIANCE_STATUS_PRED_ID,
            req1_ref,
            [("string", "open")],
        )
        closed_asrt_id = set_field(
            store.ledger,
            ECSS_COMPLIANCE_STATUS_PRED_ID,
            req1_ref,
            [("string", "closed")],
        )
        rid_asrt_id = set_field(
            store.ledger,
            ECSS_REQUIREMENT_RID_PRED_ID,
            req1_ref,
            [("string", "RID-007")],
        )
        milestone_asrt_id = set_field(
            store.ledger,
            ECSS_REVIEW_MILESTONE_PRED_ID,
            req1_ref,
            [("string", "CDR")],
        )
        requirement2_asrt_id = set_field(
            store.ledger,
            ECSS_REQUIREMENT_PRED_ID,
            req2_ref,
            [("string", "REQ-002"), ("string", "Inspection note"), ("string", "")],
        )
        waived_asrt_id = set_field(
            store.ledger,
            ECSS_COMPLIANCE_STATUS_PRED_ID,
            req2_ref,
            [("string", "waived")],
        )

    return {
        "req1_ref": req1_ref,
        "req2_ref": req2_ref,
        "requirement_asrt_id": requirement_asrt_id,
        "analysis_asrt_id": analysis_asrt_id,
        "test_asrt_id": test_asrt_id,
        "open_asrt_id": open_asrt_id,
        "closed_asrt_id": closed_asrt_id,
        "rid_asrt_id": rid_asrt_id,
        "milestone_asrt_id": milestone_asrt_id,
        "requirement2_asrt_id": requirement2_asrt_id,
        "waived_asrt_id": waived_asrt_id,
    }
