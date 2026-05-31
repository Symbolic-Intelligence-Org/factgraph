from __future__ import annotations

import copy
import json
import re as _re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import unittest
from unittest.mock import patch


def _strip_style(html: str) -> str:
    """Strip <style> blocks so CSS class names don't trigger content assertions."""
    return _re.sub(r"<style[^>]*>.*?</style>", "", html, flags=_re.DOTALL)

from fastapi.testclient import TestClient

from factgraph.adapters.souffle.package import ExportOptions, export_package
from factgraph.audit import (
    AuditQuery,
    build_candidate_evidence_tree_narrative_dto,
    build_candidate_evidence_tree_summary_dto,
    build_candidate_evidence_tree_dto,
    build_rule_trace_narrative_dto,
    build_rule_trace_detail_dto,
    build_rule_trace_summary_dto,
    build_rule_trace_summary_list_dto,
    build_compliance_matrix_dto,
    load_audit_package,
)
from domains.ecss.compliance import (
    ECSS_COMPLIANCE_STATUS_PRED_ID,
    ECSS_REQUIREMENT_PRED_ID,
    ECSS_REQUIREMENT_RID_PRED_ID,
    ECSS_REVIEW_MILESTONE_PRED_ID,
    ECSS_VERIFICATION_METHOD_PRED_ID,
    extend_schema_ir_with_ecss_vcd_predicates,
)
from service.static_ui import render_audit_static_site
from factgraph.audit.assertions import load_assertion_index
from service.static_ui import _slug_id
from factgraph.authoring import (
    AuthoringDerivationCompileError,
    build_derivation_preview_dto,
    compile_authoring_schema_v1,
    compile_authoring_derivation_v1,
    parse_authoring_schema_dsl_v1,
    parse_authoring_derivation_dsl_v1,
)
from factgraph.authoring.where_schema_lowering import (
    WhereSchemaLoweringError,
    lower_blueprint_where_sugar_with_schema_v1,
)
from domains.ecss import (
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
from factgraph.core.rules.rule_ir import (
    RuleCompileError,
    RuleRegistry,
    RuleSpec,
    run_rule_with_trace,
)
from factgraph.core.rules._trace import (
    RuleTraceArtifact,
    RuleTraceInvocation,
    RuleTraceRuleRefLink,
    rule_trace_artifact_from_dict,
    rule_trace_artifact_to_dict,
    summarize_rule_trace_artifact_dict,
)
from factgraph.core.rules._trace_nl import render_rule_run_nl_explain
from factgraph.core.rules._trace_narrative import render_rule_run_narrative
from factgraph.core.rules.ruleref_types import NativeRuleRefResolution, NativeRuleRefRowSupport
from factgraph.core.rules.where_eval import WhereValidationError, _plan_body_atoms
from factgraph.core.store import Store, register_engine_evaluator
import factgraph.core.store._builders as store_builders
from factgraph.core.store._artifact_sidecar import FileArtifactSidecar, GCResult
from factgraph.core.store._candidate_evidence_tree_narrative import render_candidate_evidence_tree_narrative
from factgraph.core.store._candidate_evidence_tree_nl import render_candidate_evidence_tree_nl_explain
from factgraph.core.store._candidate_evidence_tree_summary import summarize_candidate_evidence_tree_dict
from factgraph.core.store._support_capture import (
    build_support_artifact_for_binding,
    derive_rule_ref_edges_for_binding,
    find_winning_case_index,
)
from factgraph.core.store._support import (
    ENGINE_NO_WITNESS_KIND,
    ProjectedFact,
    compute_support_digest,
    support_artifact_from_dict,
    support_artifact_to_dict,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.view.projector import project_view_facts
from factgraph.sdk import (
    Case,
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
from domains.ecss.sdk_helpers import (
    apply_ecss_vcd_schema,
    make_ecss_requirement_ref,
    write_ecss_requirement_bundle,
)
from factgraph.sdk.ingest import CONVENTION_META_KEYS, SENSITIVE_SEMANTIC_META_KEYS
from service.app_v1 import app
from service.runtime_v1 import (
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
from factgraph.tests._test_helpers import User, _schema_ir, _seed_users_for_syntax_matrix


AML_TRANSACTION_EVENT_PRED_ID = "aml:transaction_event"
AML_SHARED_DEVICE_SIGNAL_PRED_ID = "aml:shared_device_signal"
AML_BO_MISMATCH_SIGNAL_PRED_ID = "aml:bo_mismatch_signal"
AML_BENEFICIARY_RISK_PRED_ID = "aml:beneficiary_risk"
AML_TRANSACTION_TIMESTAMP_PRED_ID = "aml:transaction_timestamp"
AML_TRIGGER_EVALUATION_TIME_PRED_ID = "aml:trigger_evaluation_time"
AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID = "aml:windowed_structuring_signal"
AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID = "aml:high_risk_outflow_signal"
AML_TRIGGER_SCORE_PPM_PRED_ID = "aml:trigger_score_ppm"
AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID = "aml:trigger_score_threshold_ppm"
PROCESS_HIGH_HIGH_TEMPERATURE_PRED_ID = "process:high_high_temperature"
PROCESS_TEMPERATURE_SHUTDOWN_THRESHOLD_PRED_ID = "process:temperature_shutdown_threshold"
PROCESS_HIGH_HIGH_PRESSURE_PRED_ID = "process:high_high_pressure"
PROCESS_PRESSURE_SHUTDOWN_THRESHOLD_PRED_ID = "process:pressure_shutdown_threshold"
PROCESS_SHUTDOWN_ALARM_ACTIVE_PRED_ID = "process:shutdown_alarm_active"
PROCESS_SHUTDOWN_INTERLOCK_ARMED_PRED_ID = "process:shutdown_interlock_armed"
PROCESS_MANUAL_OVERRIDE_CLEARED_PRED_ID = "process:manual_override_cleared"
CLINICAL_MILD_FEVER_SIGNAL_PRED_ID = "clinical:mild_fever_signal"
CLINICAL_MILD_TACHYCARDIA_SIGNAL_PRED_ID = "clinical:mild_tachycardia_signal"
CLINICAL_MILD_TACHYPNEA_SIGNAL_PRED_ID = "clinical:mild_tachypnea_signal"
CLINICAL_MILD_HYPOTENSION_SIGNAL_PRED_ID = "clinical:mild_hypotension_signal"
CLINICAL_NORMAL_OXYGEN_SATURATION_PRED_ID = "clinical:normal_oxygen_saturation"
CLINICAL_NORMAL_LACTATE_PRED_ID = "clinical:normal_lactate"
CLINICAL_ABNORMAL_INDICATOR_COUNT_PRED_ID = "clinical:abnormal_indicator_count"
CLINICAL_DETERIORATION_COUNT_THRESHOLD_PRED_ID = "clinical:deterioration_count_threshold"
FORM_EXTRACTED_BENEFICIARY_RISK_PRED_ID = "form:beneficiary_risk_extracted"
FORM_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID = "form:shared_device_signal_extracted"
FORM_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID = "form:bo_mismatch_signal_extracted"
FORM_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID = "form:trigger_score_ppm_extracted"
FORM_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID = "form:trigger_score_threshold_ppm_extracted"
NOTE_EXTRACTED_REVIEW_WINDOW_SUMMARY_PRED_ID = "note:review_window_summary_extracted"
NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID = "note:beneficiary_risk_extracted"
NOTE_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID = "note:shared_device_signal_extracted"
NOTE_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID = "note:bo_mismatch_signal_extracted"
NOTE_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID = "note:trigger_score_ppm_extracted"
NOTE_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID = "note:trigger_score_threshold_ppm_extracted"
MULTI_NOTE_EXTRACTED_REVIEW_WINDOW_SUMMARY_PRED_ID = "notes:review_window_summary_extracted"
MULTI_NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID = "notes:beneficiary_risk_extracted"
MULTI_NOTE_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID = "notes:shared_device_signal_extracted"
MULTI_NOTE_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID = "notes:bo_mismatch_signal_extracted"
MULTI_NOTE_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID = "notes:trigger_score_ppm_extracted"
MULTI_NOTE_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID = "notes:trigger_score_threshold_ppm_extracted"


class DomainWalkthroughContractsTests(unittest.TestCase):
    def test_aml_case_review_walkthrough_reuses_five_layer_explain_delivery(self) -> None:
        schema_ir = _aml_case_review_schema_ir()

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            refs = {
                "account": encode_idref_v1("AMLAccount", [("account_id", "string", "ACCT-001")]),
                "beneficiary": encode_idref_v1("AMLBeneficiary", [("beneficiary_id", "string", "BEN-001")]),
                "device": encode_idref_v1("AMLDevice", [("device_id", "string", "DEV-001")]),
                "tx1": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-001")]),
                "tx2": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-002")]),
                "tx3": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-003")]),
            }

            assertion_ids: dict[str, str] = {}
            for pred_id, rest_terms in (
                (
                    AML_TRANSACTION_EVENT_PRED_ID,
                    [("entity_ref", refs["tx1"]), ("entity_ref", refs["beneficiary"]), ("int", 4700)],
                ),
                (
                    AML_TRANSACTION_EVENT_PRED_ID,
                    [("entity_ref", refs["tx2"]), ("entity_ref", refs["beneficiary"]), ("int", 4800)],
                ),
                (
                    AML_TRANSACTION_EVENT_PRED_ID,
                    [("entity_ref", refs["tx3"]), ("entity_ref", refs["beneficiary"]), ("int", 4900)],
                ),
                (
                    AML_SHARED_DEVICE_SIGNAL_PRED_ID,
                    [("entity_ref", refs["device"])],
                ),
                (
                    AML_BO_MISMATCH_SIGNAL_PRED_ID,
                    [("string", "beneficial_owner_mismatch")],
                ),
                (
                    AML_BENEFICIARY_RISK_PRED_ID,
                    [("entity_ref", refs["beneficiary"]), ("string", "high-risk-jurisdiction")],
                ),
            ):
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": pred_id,
                        "e_ref": refs["account"],
                        "rest_terms": [[tag, value] for tag, value in rest_terms],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                assertion_ids.setdefault(f"{pred_id}:{len(assertion_ids)}", write_resp["write"]["assertion_id"])

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.aml_case_review_walkthrough",
                        "version": "1.0.0",
                        "select": [
                            "$account",
                            "$tx1",
                            "$tx2",
                            "$tx3",
                            "$beneficiary",
                            "$device",
                            "$jurisdiction",
                        ],
                        "where": [
                            ["pred", AML_TRANSACTION_EVENT_PRED_ID, ["$account", "$tx1", "$beneficiary", "$amount1"]],
                            ["pred", AML_TRANSACTION_EVENT_PRED_ID, ["$account", "$tx2", "$beneficiary", "$amount2"]],
                            ["pred", AML_TRANSACTION_EVENT_PRED_ID, ["$account", "$tx3", "$beneficiary", "$amount3"]],
                            ["lt", "$amount1", "$amount2"],
                            ["lt", "$amount2", "$amount3"],
                            ["pred", AML_SHARED_DEVICE_SIGNAL_PRED_ID, ["$account", "$device"]],
                            ["pred", AML_BO_MISMATCH_SIGNAL_PRED_ID, ["$account", "$mismatch_kind"]],
                            ["pred", AML_BENEFICIARY_RISK_PRED_ID, ["$account", "$beneficiary", "$jurisdiction"]],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            summary = summary_resp["summary"]
            narrative = narrative_resp["narrative"]
            explain_nl = nl_resp["explain_nl"]

            self.assertEqual(raw_explain["root_rule"]["rule_id"], "q.aml_case_review_walkthrough")
            self.assertEqual(len(raw_explain["root_rows"]), 1)
            self.assertEqual(
                raw_explain["root_rows"][0],
                [
                    refs["account"],
                    refs["tx1"],
                    refs["tx2"],
                    refs["tx3"],
                    refs["beneficiary"],
                    refs["device"],
                    "high-risk-jurisdiction",
                ],
            )

            invocation = next(
                inv
                for inv in raw_explain["invocations"]
                if inv["rule"]["rule_id"] == "q.aml_case_review_walkthrough"
            )
            self.assertEqual(len(invocation["pred_witnesses"]), 6)
            pred_condition_keys = {witness["pred_condition_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_condition_keys,
                {
                    "c0.c0:aml:transaction_event",
                    "c0.c1:aml:transaction_event",
                    "c0.c2:aml:transaction_event",
                    "c0.c5:aml:shared_device_signal",
                    "c0.c6:aml:bo_mismatch_signal",
                    "c0.c7:aml:beneficiary_risk",
                },
            )
            self.assertEqual(len(invocation["non_fact_steps"]), 2)
            self.assertEqual({step["kind"] for step in invocation["non_fact_steps"]}, {"lt"})

            witness_groups = {row["pred_id"]: row for row in summary["predicate_witness_groups"]}
            self.assertEqual(summary["root_row_count"], 1)
            self.assertEqual(summary["invocation_count"], 1)
            self.assertEqual(len(summary["witness_assertion_ids"]), 6)
            self.assertEqual(len(witness_groups[AML_TRANSACTION_EVENT_PRED_ID]["asrt_ids"]), 3)
            self.assertEqual(witness_groups[AML_SHARED_DEVICE_SIGNAL_PRED_ID]["asrt_ids"], [assertion_ids["aml:shared_device_signal:3"]])
            self.assertEqual(witness_groups[AML_BO_MISMATCH_SIGNAL_PRED_ID]["asrt_ids"], [assertion_ids["aml:bo_mismatch_signal:4"]])
            self.assertEqual(witness_groups[AML_BENEFICIARY_RISK_PRED_ID]["asrt_ids"], [assertion_ids["aml:beneficiary_risk:5"]])

            self.assertIn(
                "Predicate aml:transaction_event was witnessed by 3 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate aml:beneficiary_risk was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertEqual(explain_nl["headline"], "Rule q.aml_case_review_walkthrough@1.0.0 matched 1 root row(s) across 1 invocation(s).")
            self.assertTrue(any("aml:transaction_event" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("aml:beneficiary_risk" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("Drill-down guidance:" in paragraph for paragraph in explain_nl["paragraphs"]))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))
                package = load_audit_package(package_dir)
                query = AuditQuery(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertEqual(audit_summary, summary)
                self.assertEqual(audit_narrative, narrative)

                detail_dto = build_rule_trace_detail_dto(query, rule_run_id)
                self.assertEqual(detail_dto["stats"]["witness_assertion_count"], 6)
                self.assertEqual(detail_dto["stats"]["pred_witness_count"], 6)
                self.assertEqual(len(detail_dto["witness_assertion_ids"]), 6)

                with TemporaryDirectory() as out_dir:
                    site_manifest = render_audit_static_site(package_dir, out_dir)
                    self.assertEqual(site_manifest["rule_trace_count"], 1)
                    self.assertIn("rule_traces.html", site_manifest["rule_trace_index"])
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{_slug_id(rule_run_id)}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("Rule Trace", html)
                    self.assertIn("q.aml_case_review_walkthrough", html)
                    self.assertIn("Predicate aml:transaction_event was witnessed by 3 assertion(s) across 1 invocation(s).", html)
                    self.assertIn("high-risk-jurisdiction", html)
                    self.assertIn(assertion_ids["aml:transaction_event:0"], html)
                    self.assertIn(assertion_ids["aml:beneficiary_risk:5"], html)
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_aml_trigger_walkthrough_reuses_five_layer_explain_delivery_with_temporal_and_threshold_placeholders(
        self,
    ) -> None:
        schema_ir = _aml_trigger_walkthrough_schema_ir()

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            refs = {
                "account": encode_idref_v1("AMLAccount", [("account_id", "string", "ACCT-TRIGGER-001")]),
                "beneficiary": encode_idref_v1("AMLBeneficiary", [("beneficiary_id", "string", "BEN-TRIGGER-001")]),
                "device": encode_idref_v1("AMLDevice", [("device_id", "string", "DEV-TRIGGER-001")]),
            }

            assertion_ids: dict[str, str] = {}
            for pred_id, rest_terms in (
                (
                    AML_TRIGGER_EVALUATION_TIME_PRED_ID,
                    [("time", 200)],
                ),
                (
                    AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                    [("time", 100), ("time", 300), ("int", 3)],
                ),
                (
                    AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                    [("entity_ref", refs["beneficiary"]), ("string", "high-risk-jurisdiction")],
                ),
                (
                    AML_SHARED_DEVICE_SIGNAL_PRED_ID,
                    [("entity_ref", refs["device"])],
                ),
                (
                    AML_BO_MISMATCH_SIGNAL_PRED_ID,
                    [("string", "beneficial_owner_mismatch")],
                ),
                (
                    AML_TRIGGER_SCORE_PPM_PRED_ID,
                    [("int", 910000)],
                ),
                (
                    AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                    [("int", 900000)],
                ),
            ):
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": pred_id,
                        "e_ref": refs["account"],
                        "rest_terms": [[tag, value] for tag, value in rest_terms],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                assertion_ids.setdefault(f"{pred_id}:{len(assertion_ids)}", write_resp["write"]["assertion_id"])

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.aml_review_required_trigger_walkthrough",
                        "version": "1.0.0",
                        "select": [
                            "$account",
                            "$beneficiary",
                            "$jurisdiction",
                            "$window_start_ts",
                            "$window_end_ts",
                            "$eval_ts",
                            "$score_ppm",
                        ],
                        "where": [
                            ["pred", AML_TRIGGER_EVALUATION_TIME_PRED_ID, ["$account", "$eval_ts"]],
                            [
                                "pred",
                                AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                                ["$account", "$window_start_ts", "$window_end_ts", "$structuring_tx_count"],
                            ],
                            ["le", "$window_start_ts", "$eval_ts"],
                            ["le", "$eval_ts", "$window_end_ts"],
                            [
                                "pred",
                                AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                                ["$account", "$beneficiary", "$jurisdiction"],
                            ],
                            ["pred", AML_SHARED_DEVICE_SIGNAL_PRED_ID, ["$account", "$device"]],
                            ["pred", AML_BO_MISMATCH_SIGNAL_PRED_ID, ["$account", "$mismatch_kind"]],
                            ["pred", AML_TRIGGER_SCORE_PPM_PRED_ID, ["$account", "$score_ppm"]],
                            [
                                "pred",
                                AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                                ["$account", "$score_threshold_ppm"],
                            ],
                            ["ge", "$score_ppm", "$score_threshold_ppm"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            summary = summary_resp["summary"]
            narrative = narrative_resp["narrative"]
            explain_nl = nl_resp["explain_nl"]

            self.assertEqual(raw_explain["root_rule"]["rule_id"], "q.aml_review_required_trigger_walkthrough")
            self.assertEqual(len(raw_explain["root_rows"]), 1)
            self.assertEqual(
                raw_explain["root_rows"][0],
                [
                    refs["account"],
                    refs["beneficiary"],
                    "high-risk-jurisdiction",
                    100,
                    300,
                    200,
                    910000,
                ],
            )

            invocation = next(
                inv
                for inv in raw_explain["invocations"]
                if inv["rule"]["rule_id"] == "q.aml_review_required_trigger_walkthrough"
            )
            self.assertEqual(len(invocation["pred_witnesses"]), 7)
            pred_condition_keys = {witness["pred_condition_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_condition_keys,
                {
                    "c0.c0:aml:trigger_evaluation_time",
                    "c0.c1:aml:windowed_structuring_signal",
                    "c0.c4:aml:high_risk_outflow_signal",
                    "c0.c5:aml:shared_device_signal",
                    "c0.c6:aml:bo_mismatch_signal",
                    "c0.c7:aml:trigger_score_ppm",
                    "c0.c8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertEqual(len(invocation["non_fact_steps"]), 3)
            self.assertEqual({step["kind"] for step in invocation["non_fact_steps"]}, {"le", "ge"})

            non_fact_by_key = {step["step_key"]: step for step in invocation["non_fact_steps"]}
            self.assertEqual(sorted(non_fact_by_key.keys()), ["c0.c2:le", "c0.c3:le", "c0.c9:ge"])
            lower_binding = dict(dict(non_fact_by_key["c0.c2:le"]["details"])["binding"])
            upper_binding = dict(dict(non_fact_by_key["c0.c3:le"]["details"])["binding"])
            threshold_binding = dict(dict(non_fact_by_key["c0.c9:ge"]["details"])["binding"])
            self.assertEqual(lower_binding["$window_start_ts"], 100)
            self.assertEqual(lower_binding["$eval_ts"], 200)
            self.assertEqual(upper_binding["$eval_ts"], 200)
            self.assertEqual(upper_binding["$window_end_ts"], 300)
            self.assertEqual(threshold_binding["$score_ppm"], 910000)
            self.assertEqual(threshold_binding["$score_threshold_ppm"], 900000)

            witness_groups = {row["pred_id"]: row for row in summary["predicate_witness_groups"]}
            self.assertEqual(summary["root_row_count"], 1)
            self.assertEqual(summary["invocation_count"], 1)
            self.assertEqual(len(summary["witness_assertion_ids"]), 7)
            self.assertEqual(
                witness_groups[AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID]["asrt_ids"],
                [assertion_ids["aml:windowed_structuring_signal:1"]],
            )
            self.assertEqual(
                witness_groups[AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID]["asrt_ids"],
                [assertion_ids["aml:high_risk_outflow_signal:2"]],
            )
            self.assertEqual(
                witness_groups[AML_TRIGGER_SCORE_PPM_PRED_ID]["asrt_ids"],
                [assertion_ids["aml:trigger_score_ppm:5"]],
            )
            self.assertEqual(
                witness_groups[AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID]["asrt_ids"],
                [assertion_ids["aml:trigger_score_threshold_ppm:6"]],
            )

            self.assertIn(
                "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate aml:trigger_score_ppm was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Check kind le was evaluated 2 time(s) across 1 invocation(s).",
                narrative["non_fact_check_lines"],
            )
            self.assertIn(
                "Check kind ge was evaluated 1 time(s) across 1 invocation(s).",
                narrative["non_fact_check_lines"],
            )

            self.assertEqual(
                explain_nl["headline"],
                "Rule q.aml_review_required_trigger_walkthrough@1.0.0 matched 1 root row(s) across 1 invocation(s).",
            )
            self.assertTrue(
                any("aml:windowed_structuring_signal" in paragraph for paragraph in explain_nl["paragraphs"])
            )
            self.assertTrue(any("aml:trigger_score_ppm" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("Check kind ge was evaluated 1 time(s)" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("formal obligation" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("certainty combination" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))
                package = load_audit_package(package_dir)
                query = AuditQuery(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertEqual(audit_summary, summary)
                self.assertEqual(audit_narrative, narrative)

                detail_dto = build_rule_trace_detail_dto(query, rule_run_id)
                self.assertEqual(detail_dto["stats"]["witness_assertion_count"], 7)
                self.assertEqual(detail_dto["stats"]["pred_witness_count"], 7)
                self.assertEqual(len(detail_dto["witness_assertion_ids"]), 7)

                with TemporaryDirectory() as out_dir:
                    site_manifest = render_audit_static_site(package_dir, out_dir)
                    self.assertEqual(site_manifest["rule_trace_count"], 1)
                    self.assertIn("rule_traces.html", site_manifest["rule_trace_index"])
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{_slug_id(rule_run_id)}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("Rule Trace", html)
                    self.assertIn("q.aml_review_required_trigger_walkthrough", html)
                    self.assertIn(
                        "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertIn(
                        "Predicate aml:trigger_score_ppm was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertIn("high-risk-jurisdiction", html)
                    self.assertIn(assertion_ids["aml:trigger_score_threshold_ppm:6"], html)
                    self.assertIn(assertion_ids["aml:windowed_structuring_signal:1"], html)
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_aml_aggregation_materialization_walkthrough_preserves_helper_vs_rule_boundary(self) -> None:
        schema_ir = _aml_aggregation_materialization_schema_ir()

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            refs = {
                "account": encode_idref_v1("AMLAccount", [("account_id", "string", "ACCT-MATL-001")]),
                "beneficiary": encode_idref_v1("AMLBeneficiary", [("beneficiary_id", "string", "BEN-MATL-001")]),
                "device": encode_idref_v1("AMLDevice", [("device_id", "string", "DEV-MATL-001")]),
                "tx1": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-MATL-001")]),
                "tx2": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-MATL-002")]),
                "tx3": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-MATL-003")]),
            }

            assertion_ids: dict[str, str] = {}
            for pred_id, e_ref, rest_terms in (
                (
                    AML_TRANSACTION_EVENT_PRED_ID,
                    refs["account"],
                    [("entity_ref", refs["tx1"]), ("entity_ref", refs["beneficiary"]), ("int", 9700)],
                ),
                (
                    AML_TRANSACTION_EVENT_PRED_ID,
                    refs["account"],
                    [("entity_ref", refs["tx2"]), ("entity_ref", refs["beneficiary"]), ("int", 9800)],
                ),
                (
                    AML_TRANSACTION_EVENT_PRED_ID,
                    refs["account"],
                    [("entity_ref", refs["tx3"]), ("entity_ref", refs["beneficiary"]), ("int", 9900)],
                ),
                (
                    AML_TRANSACTION_TIMESTAMP_PRED_ID,
                    refs["tx1"],
                    [("time", 110)],
                ),
                (
                    AML_TRANSACTION_TIMESTAMP_PRED_ID,
                    refs["tx2"],
                    [("time", 150)],
                ),
                (
                    AML_TRANSACTION_TIMESTAMP_PRED_ID,
                    refs["tx3"],
                    [("time", 190)],
                ),
                (
                    AML_BENEFICIARY_RISK_PRED_ID,
                    refs["account"],
                    [("entity_ref", refs["beneficiary"]), ("string", "high-risk-jurisdiction")],
                ),
                (
                    AML_TRIGGER_EVALUATION_TIME_PRED_ID,
                    refs["account"],
                    [("time", 200)],
                ),
                (
                    AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                    refs["account"],
                    [("time", 100), ("time", 300), ("int", 3)],
                ),
                (
                    AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                    refs["account"],
                    [("entity_ref", refs["beneficiary"]), ("string", "high-risk-jurisdiction")],
                ),
                (
                    AML_SHARED_DEVICE_SIGNAL_PRED_ID,
                    refs["account"],
                    [("entity_ref", refs["device"])],
                ),
                (
                    AML_BO_MISMATCH_SIGNAL_PRED_ID,
                    refs["account"],
                    [("string", "beneficial_owner_mismatch")],
                ),
                (
                    AML_TRIGGER_SCORE_PPM_PRED_ID,
                    refs["account"],
                    [("int", 910000)],
                ),
                (
                    AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                    refs["account"],
                    [("int", 900000)],
                ),
            ):
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": pred_id,
                        "e_ref": e_ref,
                        "rest_terms": [[tag, value] for tag, value in rest_terms],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                assertion_ids.setdefault(f"{pred_id}:{len(assertion_ids)}", write_resp["write"]["assertion_id"])

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.aml_aggregation_materialization_walkthrough",
                        "version": "1.0.0",
                        "select": [
                            "$account",
                            "$beneficiary",
                            "$jurisdiction",
                            "$window_start_ts",
                            "$window_end_ts",
                            "$eval_ts",
                            "$score_ppm",
                        ],
                        "where": [
                            ["pred", AML_TRIGGER_EVALUATION_TIME_PRED_ID, ["$account", "$eval_ts"]],
                            [
                                "pred",
                                AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                                ["$account", "$window_start_ts", "$window_end_ts", "$structuring_tx_count"],
                            ],
                            ["le", "$window_start_ts", "$eval_ts"],
                            ["le", "$eval_ts", "$window_end_ts"],
                            [
                                "pred",
                                AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                                ["$account", "$beneficiary", "$jurisdiction"],
                            ],
                            ["pred", AML_SHARED_DEVICE_SIGNAL_PRED_ID, ["$account", "$device"]],
                            ["pred", AML_BO_MISMATCH_SIGNAL_PRED_ID, ["$account", "$mismatch_kind"]],
                            ["pred", AML_TRIGGER_SCORE_PPM_PRED_ID, ["$account", "$score_ppm"]],
                            [
                                "pred",
                                AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                                ["$account", "$score_threshold_ppm"],
                            ],
                            ["ge", "$score_ppm", "$score_threshold_ppm"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            summary = summary_resp["summary"]
            narrative = narrative_resp["narrative"]
            explain_nl = nl_resp["explain_nl"]

            self.assertEqual(raw_explain["root_rule"]["rule_id"], "q.aml_aggregation_materialization_walkthrough")
            self.assertEqual(len(raw_explain["root_rows"]), 1)
            self.assertEqual(
                raw_explain["root_rows"][0],
                [
                    refs["account"],
                    refs["beneficiary"],
                    "high-risk-jurisdiction",
                    100,
                    300,
                    200,
                    910000,
                ],
            )

            invocation = next(
                inv
                for inv in raw_explain["invocations"]
                if inv["rule"]["rule_id"] == "q.aml_aggregation_materialization_walkthrough"
            )
            pred_condition_keys = {witness["pred_condition_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_condition_keys,
                {
                    "c0.c0:aml:trigger_evaluation_time",
                    "c0.c1:aml:windowed_structuring_signal",
                    "c0.c4:aml:high_risk_outflow_signal",
                    "c0.c5:aml:shared_device_signal",
                    "c0.c6:aml:bo_mismatch_signal",
                    "c0.c7:aml:trigger_score_ppm",
                    "c0.c8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertFalse(any(key.endswith(":aml:transaction_event") for key in pred_condition_keys))
            self.assertFalse(any(key.endswith(":aml:transaction_timestamp") for key in pred_condition_keys))
            self.assertEqual(len(invocation["pred_witnesses"]), 7)
            self.assertEqual(len(invocation["non_fact_steps"]), 3)

            witness_groups = {row["pred_id"]: row for row in summary["predicate_witness_groups"]}
            self.assertNotIn(AML_TRANSACTION_EVENT_PRED_ID, witness_groups)
            self.assertNotIn(AML_TRANSACTION_TIMESTAMP_PRED_ID, witness_groups)
            self.assertIn(AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID, witness_groups)
            self.assertIn(AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID, witness_groups)

            self.assertIn(
                "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertNotIn(
                "Predicate aml:transaction_event was witnessed by 3 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )

            self.assertEqual(
                explain_nl["headline"],
                "Rule q.aml_aggregation_materialization_walkthrough@1.0.0 matched 1 root row(s) across 1 invocation(s).",
            )
            self.assertTrue(any("aml:windowed_structuring_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("aml:high_risk_outflow_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("aml:transaction_event" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("aggregated transactions during rule execution" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))
                package = load_audit_package(package_dir)
                query = AuditQuery(package)
                assertion_index = load_assertion_index(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertEqual(audit_summary, summary)
                self.assertEqual(audit_narrative, narrative)

                raw_tx_detail = assertion_index.get_assertion_detail(assertion_ids["aml:transaction_event:0"])
                raw_ts_detail = assertion_index.get_assertion_detail(assertion_ids["aml:transaction_timestamp:3"])
                raw_risk_detail = assertion_index.get_assertion_detail(assertion_ids["aml:beneficiary_risk:6"])
                self.assertIsNotNone(raw_tx_detail)
                self.assertIsNotNone(raw_ts_detail)
                self.assertIsNotNone(raw_risk_detail)
                assert raw_tx_detail is not None
                assert raw_ts_detail is not None
                assert raw_risk_detail is not None
                self.assertEqual(raw_tx_detail["claim"]["pred_id"], AML_TRANSACTION_EVENT_PRED_ID)
                self.assertEqual(raw_ts_detail["claim"]["pred_id"], AML_TRANSACTION_TIMESTAMP_PRED_ID)
                self.assertEqual(raw_risk_detail["claim"]["pred_id"], AML_BENEFICIARY_RISK_PRED_ID)

                with TemporaryDirectory() as out_dir:
                    site_manifest = render_audit_static_site(package_dir, out_dir)
                    self.assertEqual(site_manifest["rule_trace_count"], 1)
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{_slug_id(rule_run_id)}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("q.aml_aggregation_materialization_walkthrough", html)
                    self.assertIn(
                        "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertIn(
                        "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertNotIn("Predicate aml:transaction_event was witnessed", html)
                    self.assertIn(assertion_ids["aml:windowed_structuring_signal:8"], html)

                    for key in (
                        "aml:transaction_event:0",
                        "aml:transaction_event:1",
                        "aml:transaction_event:2",
                        "aml:transaction_timestamp:3",
                        "aml:transaction_timestamp:4",
                        "aml:transaction_timestamp:5",
                        "aml:beneficiary_risk:6",
                    ):
                        assertion_page = Path(out_dir) / "assertions" / f"{_slug_id(assertion_ids[key])}.html"
                        self.assertTrue(assertion_page.exists())
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_aml_transaction_feed_materialization_walkthrough_preserves_source_to_rule_boundary(self) -> None:
        schema_ir = _aml_aggregation_materialization_schema_ir()

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            refs = {
                "account": encode_idref_v1("AMLAccount", [("account_id", "string", "ACCT-FEED-001")]),
                "beneficiary": encode_idref_v1("AMLBeneficiary", [("beneficiary_id", "string", "BEN-FEED-001")]),
                "device": encode_idref_v1("AMLDevice", [("device_id", "string", "DEV-FEED-001")]),
                "tx1": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-FEED-001")]),
                "tx2": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-FEED-002")]),
                "tx3": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-FEED-003")]),
            }
            tx_refs = {
                "TX-FEED-001": refs["tx1"],
                "TX-FEED-002": refs["tx2"],
                "TX-FEED-003": refs["tx3"],
            }
            raw_feed_records = [
                {
                    "tx_id": "TX-FEED-001",
                    "timestamp_ns": 110,
                    "amount_minor": 9700,
                    "beneficiary_id": "BEN-FEED-001",
                    "device_id": "DEV-FEED-001",
                    "jurisdiction": "high-risk-jurisdiction",
                    "bo_mismatch_kind": "beneficial_owner_mismatch",
                },
                {
                    "tx_id": "TX-FEED-002",
                    "timestamp_ns": 150,
                    "amount_minor": 9800,
                    "beneficiary_id": "BEN-FEED-001",
                    "device_id": "DEV-FEED-001",
                    "jurisdiction": "high-risk-jurisdiction",
                    "bo_mismatch_kind": "beneficial_owner_mismatch",
                },
                {
                    "tx_id": "TX-FEED-003",
                    "timestamp_ns": 190,
                    "amount_minor": 9900,
                    "beneficiary_id": "BEN-FEED-001",
                    "device_id": "DEV-FEED-001",
                    "jurisdiction": "high-risk-jurisdiction",
                    "bo_mismatch_kind": "beneficial_owner_mismatch",
                },
            ]

            def normalize_transaction_feed(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
                normalized: list[dict[str, Any]] = []
                for record in records:
                    tx_ref = tx_refs[record["tx_id"]]
                    normalized.append(
                        {
                            "key": f"tx_event:{record['tx_id']}",
                            "pred_id": AML_TRANSACTION_EVENT_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                ("entity_ref", tx_ref),
                                ("entity_ref", refs["beneficiary"]),
                                ("int", record["amount_minor"]),
                            ],
                        }
                    )
                    normalized.append(
                        {
                            "key": f"tx_timestamp:{record['tx_id']}",
                            "pred_id": AML_TRANSACTION_TIMESTAMP_PRED_ID,
                            "e_ref": tx_ref,
                            "rest_terms": [("time", record["timestamp_ns"])],
                        }
                    )
                normalized.append(
                    {
                        "key": "beneficiary_risk",
                        "pred_id": AML_BENEFICIARY_RISK_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            ("entity_ref", refs["beneficiary"]),
                            ("string", records[0]["jurisdiction"]),
                        ],
                    }
                )
                normalized.append(
                    {
                        "key": "shared_device_signal",
                        "pred_id": AML_SHARED_DEVICE_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [("entity_ref", refs["device"])],
                    }
                )
                normalized.append(
                    {
                        "key": "bo_mismatch_signal",
                        "pred_id": AML_BO_MISMATCH_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [("string", records[0]["bo_mismatch_kind"])],
                    }
                )
                return normalized

            def materialize_trigger_support(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
                timestamps = [int(record["timestamp_ns"]) for record in records]
                count = len(records)
                return [
                    {
                        "key": "trigger_evaluation_time",
                        "pred_id": AML_TRIGGER_EVALUATION_TIME_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [("time", 200)],
                    },
                    {
                        "key": "windowed_structuring_signal",
                        "pred_id": AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [("time", min(timestamps) - 10), ("time", max(timestamps) + 110), ("int", count)],
                    },
                    {
                        "key": "high_risk_outflow_signal",
                        "pred_id": AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            ("entity_ref", refs["beneficiary"]),
                            ("string", records[0]["jurisdiction"]),
                        ],
                    },
                    {
                        "key": "trigger_score_ppm",
                        "pred_id": AML_TRIGGER_SCORE_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [("int", 910000)],
                    },
                    {
                        "key": "trigger_score_threshold_ppm",
                        "pred_id": AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [("int", 900000)],
                    },
                ]

            normalized_facts = normalize_transaction_feed(raw_feed_records)
            materialized_facts = materialize_trigger_support(raw_feed_records)
            normalized_by_key = {row["key"]: row for row in normalized_facts}
            materialized_by_key = {row["key"]: row for row in materialized_facts}

            self.assertEqual(
                normalized_by_key["tx_event:TX-FEED-001"]["rest_terms"][2],
                ("int", raw_feed_records[0]["amount_minor"]),
            )
            self.assertEqual(
                normalized_by_key["tx_timestamp:TX-FEED-002"]["rest_terms"][0],
                ("time", raw_feed_records[1]["timestamp_ns"]),
            )
            self.assertEqual(
                normalized_by_key["beneficiary_risk"]["rest_terms"][1],
                ("string", raw_feed_records[0]["jurisdiction"]),
            )
            self.assertEqual(
                materialized_by_key["windowed_structuring_signal"]["rest_terms"],
                [("time", 100), ("time", 300), ("int", 3)],
            )

            assertion_ids: dict[str, str] = {}
            for row in normalized_facts + materialized_facts:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": row["pred_id"],
                        "e_ref": row["e_ref"],
                        "rest_terms": [[tag, value] for tag, value in row["rest_terms"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                assertion_ids[row["key"]] = write_resp["write"]["assertion_id"]

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.aml_transaction_feed_materialization_walkthrough",
                        "version": "1.0.0",
                        "select": [
                            "$account",
                            "$beneficiary",
                            "$jurisdiction",
                            "$window_start_ts",
                            "$window_end_ts",
                            "$eval_ts",
                            "$score_ppm",
                        ],
                        "where": [
                            ["pred", AML_TRIGGER_EVALUATION_TIME_PRED_ID, ["$account", "$eval_ts"]],
                            [
                                "pred",
                                AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                                ["$account", "$window_start_ts", "$window_end_ts", "$structuring_tx_count"],
                            ],
                            ["le", "$window_start_ts", "$eval_ts"],
                            ["le", "$eval_ts", "$window_end_ts"],
                            [
                                "pred",
                                AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                                ["$account", "$beneficiary", "$jurisdiction"],
                            ],
                            ["pred", AML_SHARED_DEVICE_SIGNAL_PRED_ID, ["$account", "$device"]],
                            ["pred", AML_BO_MISMATCH_SIGNAL_PRED_ID, ["$account", "$mismatch_kind"]],
                            ["pred", AML_TRIGGER_SCORE_PPM_PRED_ID, ["$account", "$score_ppm"]],
                            [
                                "pred",
                                AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                                ["$account", "$score_threshold_ppm"],
                            ],
                            ["ge", "$score_ppm", "$score_threshold_ppm"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            summary = summary_resp["summary"]
            narrative = narrative_resp["narrative"]
            explain_nl = nl_resp["explain_nl"]

            self.assertEqual(raw_explain["root_rule"]["rule_id"], "q.aml_transaction_feed_materialization_walkthrough")
            self.assertEqual(
                raw_explain["root_rows"],
                [[refs["account"], refs["beneficiary"], "high-risk-jurisdiction", 100, 300, 200, 910000]],
            )

            invocation = next(
                inv
                for inv in raw_explain["invocations"]
                if inv["rule"]["rule_id"] == "q.aml_transaction_feed_materialization_walkthrough"
            )
            pred_condition_keys = {witness["pred_condition_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_condition_keys,
                {
                    "c0.c0:aml:trigger_evaluation_time",
                    "c0.c1:aml:windowed_structuring_signal",
                    "c0.c4:aml:high_risk_outflow_signal",
                    "c0.c5:aml:shared_device_signal",
                    "c0.c6:aml:bo_mismatch_signal",
                    "c0.c7:aml:trigger_score_ppm",
                    "c0.c8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertFalse(any(key.endswith(":aml:transaction_event") for key in pred_condition_keys))
            self.assertFalse(any(key.endswith(":aml:transaction_timestamp") for key in pred_condition_keys))
            self.assertFalse(any(key.endswith(":aml:beneficiary_risk") for key in pred_condition_keys))
            self.assertEqual(len(invocation["pred_witnesses"]), 7)
            self.assertEqual(len(invocation["non_fact_steps"]), 3)

            witness_groups = {row["pred_id"]: row for row in summary["predicate_witness_groups"]}
            self.assertNotIn(AML_TRANSACTION_EVENT_PRED_ID, witness_groups)
            self.assertNotIn(AML_TRANSACTION_TIMESTAMP_PRED_ID, witness_groups)
            self.assertNotIn(AML_BENEFICIARY_RISK_PRED_ID, witness_groups)
            self.assertIn(AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID, witness_groups)
            self.assertIn(AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID, witness_groups)
            self.assertEqual(summary["root_row_count"], 1)
            self.assertEqual(summary["invocation_count"], 1)
            self.assertEqual(len(summary["witness_assertion_ids"]), 7)

            self.assertIn(
                "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertNotIn(
                "Predicate aml:transaction_event was witnessed by 3 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )

            self.assertEqual(
                explain_nl["headline"],
                "Rule q.aml_transaction_feed_materialization_walkthrough@1.0.0 matched 1 root row(s) across 1 invocation(s).",
            )
            self.assertTrue(any("aml:windowed_structuring_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("aml:high_risk_outflow_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("aml:transaction_event" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("raw source record" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("normalized the feed" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))
                package = load_audit_package(package_dir)
                query = AuditQuery(package)
                assertion_index = load_assertion_index(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertEqual(audit_summary, summary)
                self.assertEqual(audit_narrative, narrative)

                raw_tx_detail = assertion_index.get_assertion_detail(assertion_ids["tx_event:TX-FEED-001"])
                raw_ts_detail = assertion_index.get_assertion_detail(assertion_ids["tx_timestamp:TX-FEED-001"])
                raw_risk_detail = assertion_index.get_assertion_detail(assertion_ids["beneficiary_risk"])
                helper_detail = assertion_index.get_assertion_detail(assertion_ids["windowed_structuring_signal"])
                self.assertIsNotNone(raw_tx_detail)
                self.assertIsNotNone(raw_ts_detail)
                self.assertIsNotNone(raw_risk_detail)
                self.assertIsNotNone(helper_detail)
                assert raw_tx_detail is not None
                assert raw_ts_detail is not None
                assert raw_risk_detail is not None
                assert helper_detail is not None
                self.assertEqual(raw_tx_detail["claim"]["pred_id"], AML_TRANSACTION_EVENT_PRED_ID)
                self.assertEqual(raw_tx_detail["claim_args"][2]["tag"], "int")
                self.assertEqual(raw_tx_detail["claim_args"][2]["val"], "9700")
                self.assertEqual(raw_ts_detail["claim"]["pred_id"], AML_TRANSACTION_TIMESTAMP_PRED_ID)
                self.assertEqual(raw_ts_detail["claim_args"][0]["tag"], "time")
                self.assertEqual(raw_ts_detail["claim_args"][0]["val"], "110")
                self.assertEqual(raw_risk_detail["claim"]["pred_id"], AML_BENEFICIARY_RISK_PRED_ID)
                self.assertEqual(helper_detail["claim"]["pred_id"], AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID)

                with TemporaryDirectory() as out_dir:
                    site_manifest = render_audit_static_site(package_dir, out_dir)
                    self.assertEqual(site_manifest["rule_trace_count"], 1)
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{_slug_id(rule_run_id)}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("q.aml_transaction_feed_materialization_walkthrough", html)
                    self.assertIn(
                        "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertIn(
                        "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertNotIn("Predicate aml:transaction_event was witnessed", html)
                    self.assertIn(assertion_ids["windowed_structuring_signal"], html)

                    for key in (
                        "tx_event:TX-FEED-001",
                        "tx_event:TX-FEED-002",
                        "tx_event:TX-FEED-003",
                        "tx_timestamp:TX-FEED-001",
                        "tx_timestamp:TX-FEED-002",
                        "tx_timestamp:TX-FEED-003",
                        "beneficiary_risk",
                        "shared_device_signal",
                        "bo_mismatch_signal",
                        "windowed_structuring_signal",
                    ):
                        assertion_page = Path(out_dir) / "assertions" / f"{_slug_id(assertion_ids[key])}.html"
                        self.assertTrue(assertion_page.exists())
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_form_document_extraction_walkthrough_preserves_document_to_rule_boundary(self) -> None:
        schema_ir = _form_document_extraction_schema_ir()

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            refs = {
                "account": encode_idref_v1("AMLAccount", [("account_id", "string", "ACCT-FORM-001")]),
                "beneficiary": encode_idref_v1("AMLBeneficiary", [("beneficiary_id", "string", "BEN-FORM-001")]),
                "device": encode_idref_v1("AMLDevice", [("device_id", "string", "DEV-FORM-001")]),
                "document": encode_idref_v1("AMLReviewForm", [("form_id", "string", "FORM-001")]),
            }
            form_fixture = {
                "form_id": "FORM-001",
                "account_id": "ACCT-FORM-001",
                "beneficiary_id": "BEN-FORM-001",
                "device_id": "DEV-FORM-001",
                "jurisdiction_field": "High Risk Jurisdiction",
                "score_ppm_field": "910000",
                "score_threshold_ppm_field": "900000",
                "window_start_ns": 100,
                "window_end_ns": 300,
                "evaluation_time_ns": 200,
                "transaction_count_field": "3",
                "bo_mismatch_field": "beneficial owner mismatch",
            }

            def extract_form_document(form: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
                extracted: list[dict[str, Any]] = [
                    {
                        "key": "beneficiary_risk",
                        "pred_id": FORM_EXTRACTED_BENEFICIARY_RISK_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            ("entity_ref", refs["beneficiary"]),
                            ("string", "high-risk-jurisdiction"),
                            ("entity_ref", refs["document"]),
                        ],
                    },
                    {
                        "key": "shared_device_signal",
                        "pred_id": FORM_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            ("entity_ref", refs["device"]),
                            ("entity_ref", refs["document"]),
                        ],
                    },
                    {
                        "key": "bo_mismatch_signal",
                        "pred_id": FORM_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            ("string", "beneficial_owner_mismatch"),
                            ("entity_ref", refs["document"]),
                        ],
                    },
                    {
                        "key": "trigger_score_ppm",
                        "pred_id": FORM_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            ("int", int(form["score_ppm_field"])),
                            ("entity_ref", refs["document"]),
                        ],
                    },
                    {
                        "key": "trigger_score_threshold_ppm",
                        "pred_id": FORM_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            ("int", int(form["score_threshold_ppm_field"])),
                            ("entity_ref", refs["document"]),
                        ],
                    },
                ]
                extraction_meta = {
                    "ambiguous_fields": {
                        "jurisdiction_field": {
                            "raw": form["jurisdiction_field"],
                            "mapped_to": "high-risk-jurisdiction",
                            "status": "deterministic_alias_map",
                        }
                    }
                }
                return extracted, extraction_meta

            def materialize_form_trigger_support(
                form: dict[str, Any],
                extracted_rows: list[dict[str, Any]],
            ) -> list[dict[str, Any]]:
                extracted_by_key = {row["key"]: row for row in extracted_rows}
                return [
                    {
                        "key": "trigger_evaluation_time",
                        "pred_id": AML_TRIGGER_EVALUATION_TIME_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [("time", form["evaluation_time_ns"])],
                    },
                    {
                        "key": "windowed_structuring_signal",
                        "pred_id": AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            ("time", form["window_start_ns"]),
                            ("time", form["window_end_ns"]),
                            ("int", int(form["transaction_count_field"])),
                        ],
                    },
                    {
                        "key": "high_risk_outflow_signal",
                        "pred_id": AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["beneficiary_risk"]["rest_terms"][:2],
                    },
                    {
                        "key": "shared_device_signal_materialized",
                        "pred_id": AML_SHARED_DEVICE_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["shared_device_signal"]["rest_terms"][:1],
                    },
                    {
                        "key": "bo_mismatch_signal_materialized",
                        "pred_id": AML_BO_MISMATCH_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["bo_mismatch_signal"]["rest_terms"][:1],
                    },
                    {
                        "key": "trigger_score_ppm_materialized",
                        "pred_id": AML_TRIGGER_SCORE_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["trigger_score_ppm"]["rest_terms"][:1],
                    },
                    {
                        "key": "trigger_score_threshold_ppm_materialized",
                        "pred_id": AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["trigger_score_threshold_ppm"]["rest_terms"][:1],
                    },
                ]

            extracted_facts, extraction_meta = extract_form_document(form_fixture)
            materialized_facts = materialize_form_trigger_support(form_fixture, extracted_facts)
            extracted_by_key = {row["key"]: row for row in extracted_facts}
            materialized_by_key = {row["key"]: row for row in materialized_facts}

            self.assertEqual(
                extracted_by_key["trigger_score_ppm"]["rest_terms"][0],
                ("int", int(form_fixture["score_ppm_field"])),
            )
            self.assertEqual(
                extracted_by_key["beneficiary_risk"]["rest_terms"][1],
                ("string", "high-risk-jurisdiction"),
            )
            self.assertEqual(
                extracted_by_key["beneficiary_risk"]["rest_terms"][2],
                ("entity_ref", refs["document"]),
            )
            self.assertEqual(
                extracted_by_key["shared_device_signal"]["rest_terms"][1],
                ("entity_ref", refs["document"]),
            )
            self.assertEqual(
                extracted_by_key["beneficiary_risk"]["rest_terms"][2],
                extracted_by_key["shared_device_signal"]["rest_terms"][1],
            )
            self.assertEqual(
                materialized_by_key["windowed_structuring_signal"]["rest_terms"],
                [("time", 100), ("time", 300), ("int", 3)],
            )
            self.assertEqual(
                extraction_meta["ambiguous_fields"]["jurisdiction_field"],
                {
                    "raw": "High Risk Jurisdiction",
                    "mapped_to": "high-risk-jurisdiction",
                    "status": "deterministic_alias_map",
                },
            )

            assertion_ids: dict[str, str] = {}
            for row in extracted_facts + materialized_facts:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": row["pred_id"],
                        "e_ref": row["e_ref"],
                        "rest_terms": [[tag, value] for tag, value in row["rest_terms"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                assertion_ids[row["key"]] = write_resp["write"]["assertion_id"]

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.form_document_extraction_walkthrough",
                        "version": "1.0.0",
                        "select": [
                            "$account",
                            "$beneficiary",
                            "$jurisdiction",
                            "$window_start_ts",
                            "$window_end_ts",
                            "$eval_ts",
                            "$score_ppm",
                        ],
                        "where": [
                            ["pred", AML_TRIGGER_EVALUATION_TIME_PRED_ID, ["$account", "$eval_ts"]],
                            [
                                "pred",
                                AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                                ["$account", "$window_start_ts", "$window_end_ts", "$structuring_tx_count"],
                            ],
                            ["le", "$window_start_ts", "$eval_ts"],
                            ["le", "$eval_ts", "$window_end_ts"],
                            [
                                "pred",
                                AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                                ["$account", "$beneficiary", "$jurisdiction"],
                            ],
                            ["pred", AML_SHARED_DEVICE_SIGNAL_PRED_ID, ["$account", "$device"]],
                            ["pred", AML_BO_MISMATCH_SIGNAL_PRED_ID, ["$account", "$mismatch_kind"]],
                            ["pred", AML_TRIGGER_SCORE_PPM_PRED_ID, ["$account", "$score_ppm"]],
                            [
                                "pred",
                                AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                                ["$account", "$score_threshold_ppm"],
                            ],
                            ["ge", "$score_ppm", "$score_threshold_ppm"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            summary = summary_resp["summary"]
            narrative = narrative_resp["narrative"]
            explain_nl = nl_resp["explain_nl"]

            self.assertEqual(raw_explain["root_rule"]["rule_id"], "q.form_document_extraction_walkthrough")
            self.assertEqual(
                raw_explain["root_rows"],
                [[refs["account"], refs["beneficiary"], "high-risk-jurisdiction", 100, 300, 200, 910000]],
            )

            invocation = next(
                inv
                for inv in raw_explain["invocations"]
                if inv["rule"]["rule_id"] == "q.form_document_extraction_walkthrough"
            )
            pred_condition_keys = {witness["pred_condition_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_condition_keys,
                {
                    "c0.c0:aml:trigger_evaluation_time",
                    "c0.c1:aml:windowed_structuring_signal",
                    "c0.c4:aml:high_risk_outflow_signal",
                    "c0.c5:aml:shared_device_signal",
                    "c0.c6:aml:bo_mismatch_signal",
                    "c0.c7:aml:trigger_score_ppm",
                    "c0.c8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertFalse(any(":form:" in key for key in pred_condition_keys))
            self.assertFalse(any(key.endswith(":aml:beneficiary_risk") for key in pred_condition_keys))
            self.assertEqual(len(invocation["pred_witnesses"]), 7)
            self.assertEqual(len(invocation["non_fact_steps"]), 3)

            witness_groups = {row["pred_id"]: row for row in summary["predicate_witness_groups"]}
            self.assertNotIn(AML_BENEFICIARY_RISK_PRED_ID, witness_groups)
            self.assertIn(AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID, witness_groups)
            self.assertIn(AML_SHARED_DEVICE_SIGNAL_PRED_ID, witness_groups)
            self.assertEqual(summary["root_row_count"], 1)
            self.assertEqual(summary["invocation_count"], 1)
            self.assertEqual(len(summary["witness_assertion_ids"]), 7)

            self.assertIn(
                "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate aml:shared_device_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertNotIn(
                "Predicate aml:beneficiary_risk was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )

            self.assertEqual(
                explain_nl["headline"],
                "Rule q.form_document_extraction_walkthrough@1.0.0 matched 1 root row(s) across 1 invocation(s).",
            )
            self.assertTrue(any("aml:windowed_structuring_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("aml:shared_device_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("form document" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("extracted from form" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))
                package = load_audit_package(package_dir)
                query = AuditQuery(package)
                assertion_index = load_assertion_index(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertEqual(audit_summary, summary)
                self.assertEqual(audit_narrative, narrative)

                extracted_risk_detail = assertion_index.get_assertion_detail(assertion_ids["beneficiary_risk"])
                extracted_device_detail = assertion_index.get_assertion_detail(assertion_ids["shared_device_signal"])
                extracted_score_detail = assertion_index.get_assertion_detail(assertion_ids["trigger_score_ppm"])
                helper_detail = assertion_index.get_assertion_detail(assertion_ids["windowed_structuring_signal"])
                materialized_device_detail = assertion_index.get_assertion_detail(assertion_ids["shared_device_signal_materialized"])
                self.assertIsNotNone(extracted_risk_detail)
                self.assertIsNotNone(extracted_device_detail)
                self.assertIsNotNone(extracted_score_detail)
                self.assertIsNotNone(helper_detail)
                self.assertIsNotNone(materialized_device_detail)
                assert extracted_risk_detail is not None
                assert extracted_device_detail is not None
                assert extracted_score_detail is not None
                assert helper_detail is not None
                assert materialized_device_detail is not None
                self.assertEqual(extracted_risk_detail["claim"]["pred_id"], FORM_EXTRACTED_BENEFICIARY_RISK_PRED_ID)
                self.assertEqual(extracted_device_detail["claim"]["pred_id"], FORM_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID)
                self.assertEqual(extracted_score_detail["claim"]["pred_id"], FORM_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID)
                self.assertEqual(helper_detail["claim"]["pred_id"], AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID)
                self.assertEqual(extracted_risk_detail["claim_args"][2]["tag"], "entity_ref")
                self.assertEqual(extracted_risk_detail["claim_args"][2]["val"], refs["document"])
                self.assertEqual(extracted_device_detail["claim_args"][1]["tag"], "entity_ref")
                self.assertEqual(extracted_device_detail["claim_args"][1]["val"], refs["document"])
                self.assertEqual(extracted_score_detail["claim_args"][1]["tag"], "entity_ref")
                self.assertEqual(extracted_score_detail["claim_args"][1]["val"], refs["document"])
                self.assertEqual(extracted_score_detail["claim_args"][0]["tag"], "int")
                self.assertEqual(extracted_score_detail["claim_args"][0]["val"], "910000")
                self.assertEqual(materialized_device_detail["claim"]["pred_id"], AML_SHARED_DEVICE_SIGNAL_PRED_ID)

                with TemporaryDirectory() as out_dir:
                    site_manifest = render_audit_static_site(package_dir, out_dir)
                    self.assertEqual(site_manifest["rule_trace_count"], 1)
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{_slug_id(rule_run_id)}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("q.form_document_extraction_walkthrough", html)
                    self.assertIn(
                        "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertIn(
                        "Predicate aml:shared_device_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertNotIn("Predicate aml:beneficiary_risk was witnessed", html)
                    self.assertIn(assertion_ids["windowed_structuring_signal"], html)

                    for key in (
                        "beneficiary_risk",
                        "shared_device_signal",
                        "bo_mismatch_signal",
                        "trigger_score_ppm",
                        "trigger_score_threshold_ppm",
                        "trigger_evaluation_time",
                        "windowed_structuring_signal",
                        "high_risk_outflow_signal",
                        "shared_device_signal_materialized",
                        "bo_mismatch_signal_materialized",
                        "trigger_score_ppm_materialized",
                        "trigger_score_threshold_ppm_materialized",
                    ):
                        assertion_page = Path(out_dir) / "assertions" / f"{_slug_id(assertion_ids[key])}.html"
                        self.assertTrue(assertion_page.exists())
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_single_note_narrative_extraction_walkthrough_preserves_best_effort_boundary(self) -> None:
        schema_ir = _single_note_narrative_extraction_schema_ir()

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            refs = {
                "account": encode_idref_v1("AMLAccount", [("account_id", "string", "ACCT-NOTE-001")]),
                "beneficiary": encode_idref_v1("AMLBeneficiary", [("beneficiary_id", "string", "BEN-NOTE-001")]),
                "device": encode_idref_v1("AMLDevice", [("device_id", "string", "DEV-NOTE-001")]),
                "note": encode_idref_v1("AMLInvestigatorNote", [("note_id", "string", "NOTE-001")]),
            }
            note_fixture = {
                "note_id": "NOTE-001",
                "account_id": "ACCT-NOTE-001",
                "beneficiary_id": "BEN-NOTE-001",
                "device_id": "DEV-NOTE-001",
                "text": (
                    "Investigator note NOTE-001 for account ACCT-NOTE-001: between 100 and 300 "
                    "the account sent three rapid outbound payments to beneficiary BEN-NOTE-001 "
                    "from device DEV-NOTE-001; evaluate at 200. The destination was described as an "
                    "\"elevated-risk corridor\" and the profile appears off from the recorded beneficial owner. "
                    "Current trigger score 910000 against review floor 900000. Background note: "
                    "customer answered follow-up questions calmly."
                ),
            }

            def extract_single_note(note: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
                text = note["text"]
                extracted: list[dict[str, Any]] = []
                extraction_meta = {
                    "best_effort_phrases": {},
                    "skipped_phrases": {},
                    "excerpt_map": {},
                }

                if (
                    "between 100 and 300" in text
                    and "three rapid outbound payments" in text
                    and "evaluate at 200" in text
                ):
                    extracted.append(
                        {
                            "key": "review_window_summary",
                            "pred_id": NOTE_EXTRACTED_REVIEW_WINDOW_SUMMARY_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                ("time", 100),
                                ("time", 300),
                                ("time", 200),
                                ("int", 3),
                                ("entity_ref", refs["note"]),
                            ],
                        }
                    )
                    extraction_meta["excerpt_map"]["review_window_phrase"] = (
                        "between 100 and 300 the account sent three rapid outbound payments"
                    )
                if "elevated-risk corridor" in text:
                    extracted.append(
                        {
                            "key": "beneficiary_risk",
                            "pred_id": NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                ("entity_ref", refs["beneficiary"]),
                                ("string", "high-risk-jurisdiction"),
                                ("entity_ref", refs["note"]),
                            ],
                        }
                    )
                    extraction_meta["best_effort_phrases"]["jurisdiction_phrase"] = {
                        "raw": "elevated-risk corridor",
                        "mapped_to": "high-risk-jurisdiction",
                        "status": "deterministic_best_effort",
                    }
                if "device DEV-NOTE-001" in text:
                    extracted.append(
                        {
                            "key": "shared_device_signal",
                            "pred_id": NOTE_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                ("entity_ref", refs["device"]),
                                ("entity_ref", refs["note"]),
                            ],
                        }
                    )
                if "profile appears off from the recorded beneficial owner" in text:
                    extracted.append(
                        {
                            "key": "bo_mismatch_signal",
                            "pred_id": NOTE_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                ("string", "beneficial_owner_mismatch"),
                                ("entity_ref", refs["note"]),
                            ],
                        }
                    )
                if "trigger score 910000" in text:
                    extracted.append(
                        {
                            "key": "trigger_score_ppm",
                            "pred_id": NOTE_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                ("int", 910000),
                                ("entity_ref", refs["note"]),
                            ],
                        }
                    )
                    extraction_meta["excerpt_map"]["trigger_score_phrase"] = "trigger score 910000"
                if "review floor 900000" in text:
                    extracted.append(
                        {
                            "key": "trigger_score_threshold_ppm",
                            "pred_id": NOTE_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                ("int", 900000),
                                ("entity_ref", refs["note"]),
                            ],
                        }
                    )
                    extraction_meta["excerpt_map"]["trigger_floor_phrase"] = "review floor 900000"
                if "customer answered follow-up questions calmly" in text:
                    extraction_meta["skipped_phrases"]["calm_background"] = {
                        "raw": "customer answered follow-up questions calmly",
                        "status": "explicit_skip_background",
                    }

                return extracted, extraction_meta

            def materialize_note_trigger_support(
                extracted_rows: list[dict[str, Any]],
            ) -> list[dict[str, Any]]:
                extracted_by_key = {row["key"]: row for row in extracted_rows}
                review_window_terms = extracted_by_key["review_window_summary"]["rest_terms"]
                return [
                    {
                        "key": "trigger_evaluation_time",
                        "pred_id": AML_TRIGGER_EVALUATION_TIME_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [review_window_terms[2]],
                    },
                    {
                        "key": "windowed_structuring_signal",
                        "pred_id": AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            review_window_terms[0],
                            review_window_terms[1],
                            review_window_terms[3],
                        ],
                    },
                    {
                        "key": "high_risk_outflow_signal",
                        "pred_id": AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["beneficiary_risk"]["rest_terms"][:2],
                    },
                    {
                        "key": "shared_device_signal_materialized",
                        "pred_id": AML_SHARED_DEVICE_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["shared_device_signal"]["rest_terms"][:1],
                    },
                    {
                        "key": "bo_mismatch_signal_materialized",
                        "pred_id": AML_BO_MISMATCH_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["bo_mismatch_signal"]["rest_terms"][:1],
                    },
                    {
                        "key": "trigger_score_ppm_materialized",
                        "pred_id": AML_TRIGGER_SCORE_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["trigger_score_ppm"]["rest_terms"][:1],
                    },
                    {
                        "key": "trigger_score_threshold_ppm_materialized",
                        "pred_id": AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["trigger_score_threshold_ppm"]["rest_terms"][:1],
                    },
                ]

            extracted_facts, extraction_meta = extract_single_note(note_fixture)
            materialized_facts = materialize_note_trigger_support(extracted_facts)
            extracted_by_key = {row["key"]: row for row in extracted_facts}
            materialized_by_key = {row["key"]: row for row in materialized_facts}

            self.assertIn(extraction_meta["excerpt_map"]["trigger_score_phrase"], note_fixture["text"])
            self.assertEqual(
                extracted_by_key["trigger_score_ppm"]["rest_terms"][0],
                ("int", 910000),
            )
            self.assertEqual(
                extracted_by_key["beneficiary_risk"]["rest_terms"][1],
                ("string", "high-risk-jurisdiction"),
            )
            self.assertEqual(
                extracted_by_key["beneficiary_risk"]["rest_terms"][2],
                ("entity_ref", refs["note"]),
            )
            self.assertEqual(
                extracted_by_key["trigger_score_ppm"]["rest_terms"][1],
                ("entity_ref", refs["note"]),
            )
            self.assertEqual(
                extracted_by_key["beneficiary_risk"]["rest_terms"][2],
                extracted_by_key["trigger_score_ppm"]["rest_terms"][1],
            )
            self.assertEqual(
                extracted_by_key["review_window_summary"]["rest_terms"],
                [("time", 100), ("time", 300), ("time", 200), ("int", 3), ("entity_ref", refs["note"])],
            )
            self.assertEqual(
                extraction_meta["best_effort_phrases"]["jurisdiction_phrase"],
                {
                    "raw": "elevated-risk corridor",
                    "mapped_to": "high-risk-jurisdiction",
                    "status": "deterministic_best_effort",
                },
            )
            self.assertEqual(
                extraction_meta["skipped_phrases"]["calm_background"],
                {
                    "raw": "customer answered follow-up questions calmly",
                    "status": "explicit_skip_background",
                },
            )
            self.assertEqual(
                materialized_by_key["windowed_structuring_signal"]["rest_terms"],
                [("time", 100), ("time", 300), ("int", 3)],
            )

            assertion_ids: dict[str, str] = {}
            for row in extracted_facts + materialized_facts:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": row["pred_id"],
                        "e_ref": row["e_ref"],
                        "rest_terms": [[tag, value] for tag, value in row["rest_terms"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                assertion_ids[row["key"]] = write_resp["write"]["assertion_id"]

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.single_note_narrative_extraction_walkthrough",
                        "version": "1.0.0",
                        "select": [
                            "$account",
                            "$beneficiary",
                            "$jurisdiction",
                            "$window_start_ts",
                            "$window_end_ts",
                            "$eval_ts",
                            "$score_ppm",
                        ],
                        "where": [
                            ["pred", AML_TRIGGER_EVALUATION_TIME_PRED_ID, ["$account", "$eval_ts"]],
                            [
                                "pred",
                                AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                                ["$account", "$window_start_ts", "$window_end_ts", "$structuring_tx_count"],
                            ],
                            ["le", "$window_start_ts", "$eval_ts"],
                            ["le", "$eval_ts", "$window_end_ts"],
                            [
                                "pred",
                                AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                                ["$account", "$beneficiary", "$jurisdiction"],
                            ],
                            ["pred", AML_SHARED_DEVICE_SIGNAL_PRED_ID, ["$account", "$device"]],
                            ["pred", AML_BO_MISMATCH_SIGNAL_PRED_ID, ["$account", "$mismatch_kind"]],
                            ["pred", AML_TRIGGER_SCORE_PPM_PRED_ID, ["$account", "$score_ppm"]],
                            [
                                "pred",
                                AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                                ["$account", "$score_threshold_ppm"],
                            ],
                            ["ge", "$score_ppm", "$score_threshold_ppm"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            summary = summary_resp["summary"]
            narrative = narrative_resp["narrative"]
            explain_nl = nl_resp["explain_nl"]

            self.assertEqual(
                raw_explain["root_rule"]["rule_id"],
                "q.single_note_narrative_extraction_walkthrough",
            )
            self.assertEqual(
                raw_explain["root_rows"],
                [[refs["account"], refs["beneficiary"], "high-risk-jurisdiction", 100, 300, 200, 910000]],
            )

            invocation = next(
                inv
                for inv in raw_explain["invocations"]
                if inv["rule"]["rule_id"] == "q.single_note_narrative_extraction_walkthrough"
            )
            pred_condition_keys = {witness["pred_condition_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_condition_keys,
                {
                    "c0.c0:aml:trigger_evaluation_time",
                    "c0.c1:aml:windowed_structuring_signal",
                    "c0.c4:aml:high_risk_outflow_signal",
                    "c0.c5:aml:shared_device_signal",
                    "c0.c6:aml:bo_mismatch_signal",
                    "c0.c7:aml:trigger_score_ppm",
                    "c0.c8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertFalse(any(":note:" in key for key in pred_condition_keys))
            self.assertFalse(any(key.endswith(":aml:beneficiary_risk") for key in pred_condition_keys))
            self.assertEqual(len(invocation["pred_witnesses"]), 7)
            self.assertEqual(len(invocation["non_fact_steps"]), 3)

            witness_groups = {row["pred_id"]: row for row in summary["predicate_witness_groups"]}
            self.assertNotIn(NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID, witness_groups)
            self.assertNotIn(NOTE_EXTRACTED_REVIEW_WINDOW_SUMMARY_PRED_ID, witness_groups)
            self.assertIn(AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID, witness_groups)
            self.assertIn(AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID, witness_groups)
            self.assertEqual(summary["root_row_count"], 1)
            self.assertEqual(summary["invocation_count"], 1)
            self.assertEqual(len(summary["witness_assertion_ids"]), 7)

            self.assertIn(
                "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertNotIn(
                "Predicate note:beneficiary_risk_extracted was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )

            self.assertEqual(
                explain_nl["headline"],
                "Rule q.single_note_narrative_extraction_walkthrough@1.0.0 matched 1 root row(s) across 1 invocation(s).",
            )
            self.assertTrue(any("aml:windowed_structuring_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("aml:high_risk_outflow_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("note:" in paragraph for paragraph in explain_nl["paragraphs"]))
            lowered_nl_paragraphs = [paragraph.lower() for paragraph in explain_nl["paragraphs"]]
            self.assertFalse(any("confirmed" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("certain" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("verified" in paragraph for paragraph in lowered_nl_paragraphs))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))
                package = load_audit_package(package_dir)
                query = AuditQuery(package)
                assertion_index = load_assertion_index(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertEqual(audit_summary, summary)
                self.assertEqual(audit_narrative, narrative)

                extracted_risk_detail = assertion_index.get_assertion_detail(assertion_ids["beneficiary_risk"])
                extracted_window_detail = assertion_index.get_assertion_detail(assertion_ids["review_window_summary"])
                extracted_score_detail = assertion_index.get_assertion_detail(assertion_ids["trigger_score_ppm"])
                helper_detail = assertion_index.get_assertion_detail(assertion_ids["windowed_structuring_signal"])
                materialized_device_detail = assertion_index.get_assertion_detail(assertion_ids["shared_device_signal_materialized"])
                self.assertIsNotNone(extracted_risk_detail)
                self.assertIsNotNone(extracted_window_detail)
                self.assertIsNotNone(extracted_score_detail)
                self.assertIsNotNone(helper_detail)
                self.assertIsNotNone(materialized_device_detail)
                assert extracted_risk_detail is not None
                assert extracted_window_detail is not None
                assert extracted_score_detail is not None
                assert helper_detail is not None
                assert materialized_device_detail is not None
                self.assertEqual(extracted_risk_detail["claim"]["pred_id"], NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID)
                self.assertEqual(extracted_window_detail["claim"]["pred_id"], NOTE_EXTRACTED_REVIEW_WINDOW_SUMMARY_PRED_ID)
                self.assertEqual(extracted_score_detail["claim"]["pred_id"], NOTE_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID)
                self.assertEqual(helper_detail["claim"]["pred_id"], AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID)
                self.assertEqual(extracted_risk_detail["claim_args"][2]["tag"], "entity_ref")
                self.assertEqual(extracted_risk_detail["claim_args"][2]["val"], refs["note"])
                self.assertEqual(extracted_window_detail["claim_args"][4]["tag"], "entity_ref")
                self.assertEqual(extracted_window_detail["claim_args"][4]["val"], refs["note"])
                self.assertEqual(extracted_score_detail["claim_args"][1]["tag"], "entity_ref")
                self.assertEqual(extracted_score_detail["claim_args"][1]["val"], refs["note"])
                self.assertEqual(extracted_score_detail["claim_args"][0]["tag"], "int")
                self.assertEqual(extracted_score_detail["claim_args"][0]["val"], "910000")
                self.assertEqual(materialized_device_detail["claim"]["pred_id"], AML_SHARED_DEVICE_SIGNAL_PRED_ID)

                with TemporaryDirectory() as out_dir:
                    site_manifest = render_audit_static_site(package_dir, out_dir)
                    self.assertEqual(site_manifest["rule_trace_count"], 1)
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{_slug_id(rule_run_id)}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("q.single_note_narrative_extraction_walkthrough", html)
                    self.assertIn(
                        "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertIn(
                        "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertNotIn("Predicate note:beneficiary_risk_extracted was witnessed", html)
                    self.assertNotIn("confirmed", _strip_style(html).lower())
                    self.assertNotIn("certain", _strip_style(html).lower())
                    self.assertNotIn("verified", _strip_style(html).lower())
                    self.assertIn(assertion_ids["windowed_structuring_signal"], html)

                    for key in (
                        "review_window_summary",
                        "beneficiary_risk",
                        "shared_device_signal",
                        "bo_mismatch_signal",
                        "trigger_score_ppm",
                        "trigger_score_threshold_ppm",
                        "trigger_evaluation_time",
                        "windowed_structuring_signal",
                        "high_risk_outflow_signal",
                        "shared_device_signal_materialized",
                        "bo_mismatch_signal_materialized",
                        "trigger_score_ppm_materialized",
                        "trigger_score_threshold_ppm_materialized",
                    ):
                        assertion_page = Path(out_dir) / "assertions" / f"{_slug_id(assertion_ids[key])}.html"
                        self.assertTrue(assertion_page.exists())
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_correlated_multi_note_review_walkthrough_preserves_cross_note_boundary(self) -> None:
        schema_ir = _correlated_multi_note_review_schema_ir()

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            refs = {
                "account": encode_idref_v1("AMLAccount", [("account_id", "string", "ACCT-NOTES-001")]),
                "beneficiary": encode_idref_v1("AMLBeneficiary", [("beneficiary_id", "string", "BEN-NOTES-001")]),
                "device": encode_idref_v1("AMLDevice", [("device_id", "string", "DEV-NOTES-001")]),
                "note_a": encode_idref_v1("AMLInvestigatorNote", [("note_id", "string", "NOTE-A")]),
                "note_b": encode_idref_v1("AMLInvestigatorNote", [("note_id", "string", "NOTE-B")]),
            }
            note_fixtures = [
                {
                    "note_id": "NOTE-A",
                    "text": (
                        "Investigator note NOTE-A for account ACCT-NOTES-001: between 100 and 300 "
                        "the account sent three rapid outbound payments to beneficiary BEN-NOTES-001. "
                        "The destination was described as an \"elevated-risk corridor\". "
                        "Background note: caller remained cooperative."
                    ),
                    "note_ref": refs["note_a"],
                },
                {
                    "note_id": "NOTE-B",
                    "text": (
                        "Investigator note NOTE-B for account ACCT-NOTES-001: activity was observed "
                        "from device DEV-NOTES-001 and the profile appears off from the recorded beneficial owner. "
                        "Evaluate at 200. Current trigger score 910000 against review floor 900000."
                    ),
                    "note_ref": refs["note_b"],
                },
            ]

            def extract_multi_notes(
                notes: list[dict[str, Any]],
            ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
                extracted: list[dict[str, Any]] = []
                extraction_meta = {
                    "best_effort_phrases": {},
                    "skipped_phrases": {},
                    "excerpt_map": {},
                }

                for note in notes:
                    text = note["text"]
                    note_key = note["note_id"]
                    note_ref = note["note_ref"]
                    if (
                        "between 100 and 300" in text
                        and "three rapid outbound payments" in text
                    ):
                        extracted.append(
                            {
                                "key": f"review_window_summary:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_REVIEW_WINDOW_SUMMARY_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("time", 100),
                                    ("time", 300),
                                    ("time", 200),
                                    ("int", 3),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                        extraction_meta["excerpt_map"][f"review_window_phrase:{note_key}"] = (
                            "between 100 and 300 the account sent three rapid outbound payments"
                        )
                    if "elevated-risk corridor" in text:
                        extracted.append(
                            {
                                "key": f"beneficiary_risk:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("entity_ref", refs["beneficiary"]),
                                    ("string", "high-risk-jurisdiction"),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                        extraction_meta["best_effort_phrases"][f"jurisdiction_phrase:{note_key}"] = {
                            "raw": "elevated-risk corridor",
                            "mapped_to": "high-risk-jurisdiction",
                            "status": "deterministic_best_effort",
                        }
                    if "device DEV-NOTES-001" in text:
                        extracted.append(
                            {
                                "key": f"shared_device_signal:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("entity_ref", refs["device"]),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                        extraction_meta["excerpt_map"][f"device_phrase:{note_key}"] = "device DEV-NOTES-001"
                    if "profile appears off from the recorded beneficial owner" in text:
                        extracted.append(
                            {
                                "key": f"bo_mismatch_signal:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("string", "beneficial_owner_mismatch"),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                    if "trigger score 910000" in text:
                        extracted.append(
                            {
                                "key": f"trigger_score_ppm:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("int", 910000),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                        extraction_meta["excerpt_map"][f"trigger_score_phrase:{note_key}"] = "trigger score 910000"
                    if "review floor 900000" in text:
                        extracted.append(
                            {
                                "key": f"trigger_score_threshold_ppm:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("int", 900000),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                    if "caller remained cooperative" in text:
                        extraction_meta["skipped_phrases"][f"background:{note_key}"] = {
                            "raw": "caller remained cooperative",
                            "status": "explicit_skip_background",
                        }

                return extracted, extraction_meta

            def materialize_multi_note_trigger_support(
                extracted_rows: list[dict[str, Any]],
            ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
                by_prefix: dict[str, list[dict[str, Any]]] = {}
                for row in extracted_rows:
                    prefix = row["key"].split(":", 1)[0]
                    by_prefix.setdefault(prefix, []).append(row)

                review_window_row = by_prefix["review_window_summary"][0]
                risk_row = by_prefix["beneficiary_risk"][0]
                shared_device_row = by_prefix["shared_device_signal"][0]
                mismatch_row = by_prefix["bo_mismatch_signal"][0]
                score_row = by_prefix["trigger_score_ppm"][0]
                threshold_row = by_prefix["trigger_score_threshold_ppm"][0]

                aggregation_meta = {
                    "multi_note_support": {
                        "windowed_structuring_signal": [
                            review_window_row["key"],
                            shared_device_row["key"],
                        ],
                        "high_risk_outflow_signal": [
                            risk_row["key"],
                            mismatch_row["key"],
                        ],
                    }
                }
                return (
                    [
                        {
                            "key": "trigger_evaluation_time",
                            "pred_id": AML_TRIGGER_EVALUATION_TIME_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [review_window_row["rest_terms"][2]],
                        },
                        {
                            "key": "windowed_structuring_signal",
                            "pred_id": AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                review_window_row["rest_terms"][0],
                                review_window_row["rest_terms"][1],
                                review_window_row["rest_terms"][3],
                            ],
                        },
                        {
                            "key": "high_risk_outflow_signal",
                            "pred_id": AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": risk_row["rest_terms"][:2],
                        },
                        {
                            "key": "shared_device_signal_materialized",
                            "pred_id": AML_SHARED_DEVICE_SIGNAL_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": shared_device_row["rest_terms"][:1],
                        },
                        {
                            "key": "bo_mismatch_signal_materialized",
                            "pred_id": AML_BO_MISMATCH_SIGNAL_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": mismatch_row["rest_terms"][:1],
                        },
                        {
                            "key": "trigger_score_ppm_materialized",
                            "pred_id": AML_TRIGGER_SCORE_PPM_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": score_row["rest_terms"][:1],
                        },
                        {
                            "key": "trigger_score_threshold_ppm_materialized",
                            "pred_id": AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": threshold_row["rest_terms"][:1],
                        },
                    ],
                    aggregation_meta,
                )

            extracted_facts, extraction_meta = extract_multi_notes(note_fixtures)
            materialized_facts, aggregation_meta = materialize_multi_note_trigger_support(extracted_facts)
            extracted_by_key = {row["key"]: row for row in extracted_facts}
            materialized_by_key = {row["key"]: row for row in materialized_facts}

            self.assertIn(
                extraction_meta["excerpt_map"]["review_window_phrase:NOTE-A"],
                note_fixtures[0]["text"],
            )
            self.assertIn(
                extraction_meta["excerpt_map"]["trigger_score_phrase:NOTE-B"],
                note_fixtures[1]["text"],
            )
            self.assertEqual(
                extracted_by_key["beneficiary_risk:NOTE-A"]["rest_terms"][2],
                ("entity_ref", refs["note_a"]),
            )
            self.assertEqual(
                extracted_by_key["trigger_score_ppm:NOTE-B"]["rest_terms"][1],
                ("entity_ref", refs["note_b"]),
            )
            self.assertNotEqual(
                extracted_by_key["beneficiary_risk:NOTE-A"]["rest_terms"][2],
                extracted_by_key["trigger_score_ppm:NOTE-B"]["rest_terms"][1],
            )
            self.assertEqual(
                extraction_meta["best_effort_phrases"]["jurisdiction_phrase:NOTE-A"],
                {
                    "raw": "elevated-risk corridor",
                    "mapped_to": "high-risk-jurisdiction",
                    "status": "deterministic_best_effort",
                },
            )
            self.assertEqual(
                extraction_meta["skipped_phrases"]["background:NOTE-A"],
                {
                    "raw": "caller remained cooperative",
                    "status": "explicit_skip_background",
                },
            )
            self.assertEqual(
                materialized_by_key["windowed_structuring_signal"]["rest_terms"],
                [("time", 100), ("time", 300), ("int", 3)],
            )
            self.assertEqual(
                aggregation_meta["multi_note_support"]["windowed_structuring_signal"],
                ["review_window_summary:NOTE-A", "shared_device_signal:NOTE-B"],
            )
            self.assertEqual(
                aggregation_meta["multi_note_support"]["high_risk_outflow_signal"],
                ["beneficiary_risk:NOTE-A", "bo_mismatch_signal:NOTE-B"],
            )

            assertion_ids: dict[str, str] = {}
            for row in extracted_facts + materialized_facts:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": row["pred_id"],
                        "e_ref": row["e_ref"],
                        "rest_terms": [[tag, value] for tag, value in row["rest_terms"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                assertion_ids[row["key"]] = write_resp["write"]["assertion_id"]

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.correlated_multi_note_review_walkthrough",
                        "version": "1.0.0",
                        "select": [
                            "$account",
                            "$beneficiary",
                            "$jurisdiction",
                            "$window_start_ts",
                            "$window_end_ts",
                            "$eval_ts",
                            "$score_ppm",
                        ],
                        "where": [
                            ["pred", AML_TRIGGER_EVALUATION_TIME_PRED_ID, ["$account", "$eval_ts"]],
                            [
                                "pred",
                                AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                                ["$account", "$window_start_ts", "$window_end_ts", "$structuring_tx_count"],
                            ],
                            ["le", "$window_start_ts", "$eval_ts"],
                            ["le", "$eval_ts", "$window_end_ts"],
                            [
                                "pred",
                                AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                                ["$account", "$beneficiary", "$jurisdiction"],
                            ],
                            ["pred", AML_SHARED_DEVICE_SIGNAL_PRED_ID, ["$account", "$device"]],
                            ["pred", AML_BO_MISMATCH_SIGNAL_PRED_ID, ["$account", "$mismatch_kind"]],
                            ["pred", AML_TRIGGER_SCORE_PPM_PRED_ID, ["$account", "$score_ppm"]],
                            [
                                "pred",
                                AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                                ["$account", "$score_threshold_ppm"],
                            ],
                            ["ge", "$score_ppm", "$score_threshold_ppm"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            summary = summary_resp["summary"]
            narrative = narrative_resp["narrative"]
            explain_nl = nl_resp["explain_nl"]

            self.assertEqual(
                raw_explain["root_rule"]["rule_id"],
                "q.correlated_multi_note_review_walkthrough",
            )
            self.assertEqual(
                raw_explain["root_rows"],
                [[refs["account"], refs["beneficiary"], "high-risk-jurisdiction", 100, 300, 200, 910000]],
            )

            invocation = next(
                inv
                for inv in raw_explain["invocations"]
                if inv["rule"]["rule_id"] == "q.correlated_multi_note_review_walkthrough"
            )
            pred_condition_keys = {witness["pred_condition_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_condition_keys,
                {
                    "c0.c0:aml:trigger_evaluation_time",
                    "c0.c1:aml:windowed_structuring_signal",
                    "c0.c4:aml:high_risk_outflow_signal",
                    "c0.c5:aml:shared_device_signal",
                    "c0.c6:aml:bo_mismatch_signal",
                    "c0.c7:aml:trigger_score_ppm",
                    "c0.c8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertFalse(any(":notes:" in key for key in pred_condition_keys))
            self.assertFalse(any(key.endswith(":aml:beneficiary_risk") for key in pred_condition_keys))
            self.assertEqual(len(invocation["pred_witnesses"]), 7)
            self.assertEqual(len(invocation["non_fact_steps"]), 3)

            witness_groups = {row["pred_id"]: row for row in summary["predicate_witness_groups"]}
            self.assertNotIn(MULTI_NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID, witness_groups)
            self.assertNotIn(MULTI_NOTE_EXTRACTED_REVIEW_WINDOW_SUMMARY_PRED_ID, witness_groups)
            self.assertIn(AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID, witness_groups)
            self.assertIn(AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID, witness_groups)
            self.assertEqual(summary["root_row_count"], 1)
            self.assertEqual(summary["invocation_count"], 1)
            self.assertEqual(len(summary["witness_assertion_ids"]), 7)

            self.assertIn(
                "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertNotIn(
                "Predicate notes:beneficiary_risk_extracted was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )

            self.assertEqual(
                explain_nl["headline"],
                "Rule q.correlated_multi_note_review_walkthrough@1.0.0 matched 1 root row(s) across 1 invocation(s).",
            )
            self.assertTrue(any("aml:windowed_structuring_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("aml:high_risk_outflow_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            lowered_nl_paragraphs = [paragraph.lower() for paragraph in explain_nl["paragraphs"]]
            self.assertFalse(any("notes:" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("confirmed" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("certain" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("verified" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("synthesis" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("comprehensive analysis" in paragraph for paragraph in lowered_nl_paragraphs))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))
                package = load_audit_package(package_dir)
                query = AuditQuery(package)
                assertion_index = load_assertion_index(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertEqual(audit_summary, summary)
                self.assertEqual(audit_narrative, narrative)

                extracted_risk_detail = assertion_index.get_assertion_detail(assertion_ids["beneficiary_risk:NOTE-A"])
                extracted_window_detail = assertion_index.get_assertion_detail(assertion_ids["review_window_summary:NOTE-A"])
                extracted_score_detail = assertion_index.get_assertion_detail(assertion_ids["trigger_score_ppm:NOTE-B"])
                extracted_device_detail = assertion_index.get_assertion_detail(assertion_ids["shared_device_signal:NOTE-B"])
                helper_detail = assertion_index.get_assertion_detail(assertion_ids["windowed_structuring_signal"])
                materialized_device_detail = assertion_index.get_assertion_detail(assertion_ids["shared_device_signal_materialized"])
                self.assertIsNotNone(extracted_risk_detail)
                self.assertIsNotNone(extracted_window_detail)
                self.assertIsNotNone(extracted_score_detail)
                self.assertIsNotNone(extracted_device_detail)
                self.assertIsNotNone(helper_detail)
                self.assertIsNotNone(materialized_device_detail)
                assert extracted_risk_detail is not None
                assert extracted_window_detail is not None
                assert extracted_score_detail is not None
                assert extracted_device_detail is not None
                assert helper_detail is not None
                assert materialized_device_detail is not None
                self.assertEqual(extracted_risk_detail["claim"]["pred_id"], MULTI_NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID)
                self.assertEqual(extracted_window_detail["claim"]["pred_id"], MULTI_NOTE_EXTRACTED_REVIEW_WINDOW_SUMMARY_PRED_ID)
                self.assertEqual(extracted_score_detail["claim"]["pred_id"], MULTI_NOTE_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID)
                self.assertEqual(extracted_device_detail["claim"]["pred_id"], MULTI_NOTE_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID)
                self.assertEqual(helper_detail["claim"]["pred_id"], AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID)
                self.assertEqual(extracted_risk_detail["claim_args"][2]["tag"], "entity_ref")
                self.assertEqual(extracted_risk_detail["claim_args"][2]["val"], refs["note_a"])
                self.assertEqual(extracted_window_detail["claim_args"][4]["tag"], "entity_ref")
                self.assertEqual(extracted_window_detail["claim_args"][4]["val"], refs["note_a"])
                self.assertEqual(extracted_score_detail["claim_args"][1]["tag"], "entity_ref")
                self.assertEqual(extracted_score_detail["claim_args"][1]["val"], refs["note_b"])
                self.assertEqual(extracted_device_detail["claim_args"][1]["tag"], "entity_ref")
                self.assertEqual(extracted_device_detail["claim_args"][1]["val"], refs["note_b"])
                self.assertEqual(extracted_score_detail["claim_args"][0]["tag"], "int")
                self.assertEqual(extracted_score_detail["claim_args"][0]["val"], "910000")
                self.assertEqual(materialized_device_detail["claim"]["pred_id"], AML_SHARED_DEVICE_SIGNAL_PRED_ID)

                with TemporaryDirectory() as out_dir:
                    site_manifest = render_audit_static_site(package_dir, out_dir)
                    self.assertEqual(site_manifest["rule_trace_count"], 1)
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{_slug_id(rule_run_id)}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("q.correlated_multi_note_review_walkthrough", html)
                    self.assertIn(
                        "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertIn(
                        "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertNotIn("Predicate notes:beneficiary_risk_extracted was witnessed", html)
                    lowered_body = _strip_style(html).lower()
                    self.assertNotIn("confirmed", lowered_body)
                    self.assertNotIn("certain", lowered_body)
                    self.assertNotIn("verified", lowered_body)
                    self.assertNotIn("synthesis", lowered_body)
                    self.assertNotIn("comprehensive analysis", lowered_body)
                    self.assertIn(assertion_ids["windowed_structuring_signal"], html)

                    for key in (
                        "review_window_summary:NOTE-A",
                        "beneficiary_risk:NOTE-A",
                        "shared_device_signal:NOTE-B",
                        "bo_mismatch_signal:NOTE-B",
                        "trigger_score_ppm:NOTE-B",
                        "trigger_score_threshold_ppm:NOTE-B",
                        "trigger_evaluation_time",
                        "windowed_structuring_signal",
                        "high_risk_outflow_signal",
                        "shared_device_signal_materialized",
                        "bo_mismatch_signal_materialized",
                        "trigger_score_ppm_materialized",
                        "trigger_score_threshold_ppm_materialized",
                    ):
                        assertion_page = Path(out_dir) / "assertions" / f"{_slug_id(assertion_ids[key])}.html"
                        self.assertTrue(assertion_page.exists())
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_conflicting_multi_note_evidence_walkthrough_retains_non_witnessed_side(self) -> None:
        schema_ir = _conflicting_multi_note_evidence_schema_ir()

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            refs = {
                "account": encode_idref_v1("AMLAccount", [("account_id", "string", "ACCT-CONFLICT-001")]),
                "beneficiary": encode_idref_v1("AMLBeneficiary", [("beneficiary_id", "string", "BEN-CONFLICT-001")]),
                "device": encode_idref_v1("AMLDevice", [("device_id", "string", "DEV-CONFLICT-001")]),
                "note_a": encode_idref_v1("AMLInvestigatorNote", [("note_id", "string", "NOTE-A")]),
                "note_b": encode_idref_v1("AMLInvestigatorNote", [("note_id", "string", "NOTE-B")]),
            }
            note_fixtures = [
                {
                    "note_id": "NOTE-A",
                    "text": (
                        "Investigator note NOTE-A for account ACCT-CONFLICT-001: between 100 and 300 "
                        "the account sent three rapid outbound payments to beneficiary BEN-CONFLICT-001. "
                        "The destination was described as a \"low-risk corridor\". "
                        "Background note: caller remained cooperative."
                    ),
                    "note_ref": refs["note_a"],
                },
                {
                    "note_id": "NOTE-B",
                    "text": (
                        "Investigator note NOTE-B for account ACCT-CONFLICT-001: the same beneficiary "
                        "BEN-CONFLICT-001 was described as an \"elevated-risk corridor\". Activity was "
                        "observed from device DEV-CONFLICT-001 and the profile appears off from the "
                        "recorded beneficial owner. Evaluate at 200. Current trigger score 910000 "
                        "against review floor 900000."
                    ),
                    "note_ref": refs["note_b"],
                },
            ]

            def extract_conflicting_multi_notes(
                notes: list[dict[str, Any]],
            ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
                extracted: list[dict[str, Any]] = []
                extraction_meta = {
                    "conflict_detected": {},
                    "excerpt_map": {},
                    "skipped_phrases": {},
                }

                for note in notes:
                    text = note["text"]
                    note_key = note["note_id"]
                    note_ref = note["note_ref"]
                    if (
                        "between 100 and 300" in text
                        and "three rapid outbound payments" in text
                    ):
                        extracted.append(
                            {
                                "key": f"review_window_summary:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_REVIEW_WINDOW_SUMMARY_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("time", 100),
                                    ("time", 300),
                                    ("time", 200),
                                    ("int", 3),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                        extraction_meta["excerpt_map"][f"review_window_phrase:{note_key}"] = (
                            "between 100 and 300 the account sent three rapid outbound payments"
                        )
                    if "low-risk corridor" in text:
                        extracted.append(
                            {
                                "key": f"beneficiary_risk_low:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("entity_ref", refs["beneficiary"]),
                                    ("string", "low-risk-jurisdiction"),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                        extraction_meta["excerpt_map"][f"low_risk_phrase:{note_key}"] = "low-risk corridor"
                    if "elevated-risk corridor" in text:
                        extracted.append(
                            {
                                "key": f"beneficiary_risk_high:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("entity_ref", refs["beneficiary"]),
                                    ("string", "high-risk-jurisdiction"),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                        extraction_meta["excerpt_map"][f"high_risk_phrase:{note_key}"] = "elevated-risk corridor"
                    if "device DEV-CONFLICT-001" in text:
                        extracted.append(
                            {
                                "key": f"shared_device_signal:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("entity_ref", refs["device"]),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                    if "profile appears off from the recorded beneficial owner" in text:
                        extracted.append(
                            {
                                "key": f"bo_mismatch_signal:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("string", "beneficial_owner_mismatch"),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                    if "trigger score 910000" in text:
                        extracted.append(
                            {
                                "key": f"trigger_score_ppm:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("int", 910000),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                        extraction_meta["excerpt_map"][f"trigger_score_phrase:{note_key}"] = "trigger score 910000"
                    if "review floor 900000" in text:
                        extracted.append(
                            {
                                "key": f"trigger_score_threshold_ppm:{note_key}",
                                "pred_id": MULTI_NOTE_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                                "e_ref": refs["account"],
                                "rest_terms": [
                                    ("int", 900000),
                                    ("entity_ref", note_ref),
                                ],
                            }
                        )
                    if "caller remained cooperative" in text:
                        extraction_meta["skipped_phrases"][f"background:{note_key}"] = {
                            "raw": "caller remained cooperative",
                            "status": "explicit_skip_background",
                        }

                extraction_meta["conflict_detected"]["jurisdiction_conflict"] = {
                    "keys": ["beneficiary_risk_low:NOTE-A", "beneficiary_risk_high:NOTE-B"],
                    "status": "retained_conflict",
                }
                return extracted, extraction_meta

            def materialize_conflict_trigger_support(
                extracted_rows: list[dict[str, Any]],
            ) -> list[dict[str, Any]]:
                extracted_by_key = {row["key"]: row for row in extracted_rows}
                review_window_terms = extracted_by_key["review_window_summary:NOTE-A"]["rest_terms"]
                high_risk_terms = extracted_by_key["beneficiary_risk_high:NOTE-B"]["rest_terms"]
                return [
                    {
                        "key": "trigger_evaluation_time",
                        "pred_id": AML_TRIGGER_EVALUATION_TIME_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [review_window_terms[2]],
                    },
                    {
                        "key": "windowed_structuring_signal",
                        "pred_id": AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            review_window_terms[0],
                            review_window_terms[1],
                            review_window_terms[3],
                        ],
                    },
                    {
                        "key": "high_risk_outflow_signal",
                        "pred_id": AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": high_risk_terms[:2],
                    },
                    {
                        "key": "shared_device_signal_materialized",
                        "pred_id": AML_SHARED_DEVICE_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["shared_device_signal:NOTE-B"]["rest_terms"][:1],
                    },
                    {
                        "key": "bo_mismatch_signal_materialized",
                        "pred_id": AML_BO_MISMATCH_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["bo_mismatch_signal:NOTE-B"]["rest_terms"][:1],
                    },
                    {
                        "key": "trigger_score_ppm_materialized",
                        "pred_id": AML_TRIGGER_SCORE_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["trigger_score_ppm:NOTE-B"]["rest_terms"][:1],
                    },
                    {
                        "key": "trigger_score_threshold_ppm_materialized",
                        "pred_id": AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": extracted_by_key["trigger_score_threshold_ppm:NOTE-B"]["rest_terms"][:1],
                    },
                ]

            extracted_facts, extraction_meta = extract_conflicting_multi_notes(note_fixtures)
            materialized_facts = materialize_conflict_trigger_support(extracted_facts)
            extracted_by_key = {row["key"]: row for row in extracted_facts}

            self.assertIn(extraction_meta["excerpt_map"]["low_risk_phrase:NOTE-A"], note_fixtures[0]["text"])
            self.assertIn(extraction_meta["excerpt_map"]["high_risk_phrase:NOTE-B"], note_fixtures[1]["text"])
            self.assertEqual(
                extracted_by_key["beneficiary_risk_low:NOTE-A"]["rest_terms"][1],
                ("string", "low-risk-jurisdiction"),
            )
            self.assertEqual(
                extracted_by_key["beneficiary_risk_high:NOTE-B"]["rest_terms"][1],
                ("string", "high-risk-jurisdiction"),
            )
            self.assertEqual(
                extracted_by_key["beneficiary_risk_low:NOTE-A"]["rest_terms"][2],
                ("entity_ref", refs["note_a"]),
            )
            self.assertEqual(
                extracted_by_key["beneficiary_risk_high:NOTE-B"]["rest_terms"][2],
                ("entity_ref", refs["note_b"]),
            )
            self.assertNotEqual(
                extracted_by_key["beneficiary_risk_low:NOTE-A"]["rest_terms"][2],
                extracted_by_key["beneficiary_risk_high:NOTE-B"]["rest_terms"][2],
            )
            self.assertEqual(
                extraction_meta["conflict_detected"]["jurisdiction_conflict"],
                {
                    "keys": ["beneficiary_risk_low:NOTE-A", "beneficiary_risk_high:NOTE-B"],
                    "status": "retained_conflict",
                },
            )
            self.assertEqual(
                extraction_meta["skipped_phrases"]["background:NOTE-A"],
                {
                    "raw": "caller remained cooperative",
                    "status": "explicit_skip_background",
                },
            )

            assertion_ids: dict[str, str] = {}
            for row in extracted_facts + materialized_facts:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": row["pred_id"],
                        "e_ref": row["e_ref"],
                        "rest_terms": [[tag, value] for tag, value in row["rest_terms"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                assertion_ids[row["key"]] = write_resp["write"]["assertion_id"]

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.conflicting_multi_note_evidence_walkthrough",
                        "version": "1.0.0",
                        "select": [
                            "$account",
                            "$beneficiary",
                            "$jurisdiction",
                            "$window_start_ts",
                            "$window_end_ts",
                            "$eval_ts",
                            "$score_ppm",
                        ],
                        "where": [
                            ["pred", AML_TRIGGER_EVALUATION_TIME_PRED_ID, ["$account", "$eval_ts"]],
                            [
                                "pred",
                                AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                                ["$account", "$window_start_ts", "$window_end_ts", "$structuring_tx_count"],
                            ],
                            ["le", "$window_start_ts", "$eval_ts"],
                            ["le", "$eval_ts", "$window_end_ts"],
                            [
                                "pred",
                                AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                                ["$account", "$beneficiary", "$jurisdiction"],
                            ],
                            ["pred", AML_SHARED_DEVICE_SIGNAL_PRED_ID, ["$account", "$device"]],
                            ["pred", AML_BO_MISMATCH_SIGNAL_PRED_ID, ["$account", "$mismatch_kind"]],
                            ["pred", AML_TRIGGER_SCORE_PPM_PRED_ID, ["$account", "$score_ppm"]],
                            [
                                "pred",
                                AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                                ["$account", "$score_threshold_ppm"],
                            ],
                            ["ge", "$score_ppm", "$score_threshold_ppm"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            summary = summary_resp["summary"]
            narrative = narrative_resp["narrative"]
            explain_nl = nl_resp["explain_nl"]

            self.assertEqual(
                raw_explain["root_rule"]["rule_id"],
                "q.conflicting_multi_note_evidence_walkthrough",
            )
            self.assertEqual(
                raw_explain["root_rows"],
                [[refs["account"], refs["beneficiary"], "high-risk-jurisdiction", 100, 300, 200, 910000]],
            )

            invocation = next(
                inv
                for inv in raw_explain["invocations"]
                if inv["rule"]["rule_id"] == "q.conflicting_multi_note_evidence_walkthrough"
            )
            pred_condition_keys = {witness["pred_condition_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_condition_keys,
                {
                    "c0.c0:aml:trigger_evaluation_time",
                    "c0.c1:aml:windowed_structuring_signal",
                    "c0.c4:aml:high_risk_outflow_signal",
                    "c0.c5:aml:shared_device_signal",
                    "c0.c6:aml:bo_mismatch_signal",
                    "c0.c7:aml:trigger_score_ppm",
                    "c0.c8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertEqual(len(invocation["pred_witnesses"]), 7)
            self.assertEqual(len(invocation["non_fact_steps"]), 3)
            self.assertFalse(any(":notes:" in key for key in pred_condition_keys))

            witness_groups = {row["pred_id"]: row for row in summary["predicate_witness_groups"]}
            self.assertNotIn(MULTI_NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID, witness_groups)
            self.assertIn(AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID, witness_groups)
            self.assertEqual(summary["root_row_count"], 1)
            self.assertEqual(summary["invocation_count"], 1)
            self.assertEqual(len(summary["witness_assertion_ids"]), 7)

            self.assertIn(
                "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertNotIn(
                "Predicate notes:beneficiary_risk_extracted was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )

            self.assertEqual(
                explain_nl["headline"],
                "Rule q.conflicting_multi_note_evidence_walkthrough@1.0.0 matched 1 root row(s) across 1 invocation(s).",
            )
            self.assertTrue(any("aml:high_risk_outflow_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("notes:" in paragraph for paragraph in explain_nl["paragraphs"]))
            lowered_nl_paragraphs = [paragraph.lower() for paragraph in explain_nl["paragraphs"]]
            self.assertFalse(any("confirmed" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("certain" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("verified" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("resolved" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("resolution" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("judgment" in paragraph for paragraph in lowered_nl_paragraphs))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))
                package = load_audit_package(package_dir)
                query = AuditQuery(package)
                assertion_index = load_assertion_index(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertEqual(audit_summary, summary)
                self.assertEqual(audit_narrative, narrative)

                extracted_low_detail = assertion_index.get_assertion_detail(assertion_ids["beneficiary_risk_low:NOTE-A"])
                extracted_high_detail = assertion_index.get_assertion_detail(assertion_ids["beneficiary_risk_high:NOTE-B"])
                extracted_window_detail = assertion_index.get_assertion_detail(assertion_ids["review_window_summary:NOTE-A"])
                materialized_risk_detail = assertion_index.get_assertion_detail(assertion_ids["high_risk_outflow_signal"])
                self.assertIsNotNone(extracted_low_detail)
                self.assertIsNotNone(extracted_high_detail)
                self.assertIsNotNone(extracted_window_detail)
                self.assertIsNotNone(materialized_risk_detail)
                assert extracted_low_detail is not None
                assert extracted_high_detail is not None
                assert extracted_window_detail is not None
                assert materialized_risk_detail is not None
                self.assertEqual(extracted_low_detail["claim"]["pred_id"], MULTI_NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID)
                self.assertEqual(extracted_high_detail["claim"]["pred_id"], MULTI_NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID)
                self.assertEqual(extracted_low_detail["claim_args"][1]["tag"], "string")
                self.assertEqual(extracted_low_detail["claim_args"][1]["val"], "low-risk-jurisdiction")
                self.assertEqual(extracted_low_detail["claim_args"][2]["tag"], "entity_ref")
                self.assertEqual(extracted_low_detail["claim_args"][2]["val"], refs["note_a"])
                self.assertEqual(extracted_high_detail["claim_args"][1]["tag"], "string")
                self.assertEqual(extracted_high_detail["claim_args"][1]["val"], "high-risk-jurisdiction")
                self.assertEqual(extracted_high_detail["claim_args"][2]["tag"], "entity_ref")
                self.assertEqual(extracted_high_detail["claim_args"][2]["val"], refs["note_b"])
                self.assertEqual(extracted_window_detail["claim_args"][4]["val"], refs["note_a"])
                self.assertEqual(materialized_risk_detail["claim"]["pred_id"], AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID)
                self.assertEqual(materialized_risk_detail["claim_args"][1]["tag"], "string")
                self.assertEqual(materialized_risk_detail["claim_args"][1]["val"], "high-risk-jurisdiction")

                with TemporaryDirectory() as out_dir:
                    site_manifest = render_audit_static_site(package_dir, out_dir)
                    self.assertEqual(site_manifest["rule_trace_count"], 1)
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{_slug_id(rule_run_id)}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("q.conflicting_multi_note_evidence_walkthrough", html)
                    self.assertIn(
                        "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertNotIn("Predicate notes:beneficiary_risk_extracted was witnessed", html)
                    lowered_body = _strip_style(html).lower()
                    self.assertNotIn("confirmed", lowered_body)
                    self.assertNotIn("certain", lowered_body)
                    self.assertNotIn("verified", lowered_body)
                    self.assertNotIn("resolved", lowered_body)
                    self.assertNotIn("resolution", lowered_body)
                    self.assertNotIn("judgment", lowered_body)
                    self.assertIn(assertion_ids["high_risk_outflow_signal"], html)

                    for key in (
                        "review_window_summary:NOTE-A",
                        "beneficiary_risk_low:NOTE-A",
                        "beneficiary_risk_high:NOTE-B",
                        "shared_device_signal:NOTE-B",
                        "bo_mismatch_signal:NOTE-B",
                        "trigger_score_ppm:NOTE-B",
                        "trigger_score_threshold_ppm:NOTE-B",
                        "trigger_evaluation_time",
                        "windowed_structuring_signal",
                        "high_risk_outflow_signal",
                        "shared_device_signal_materialized",
                        "bo_mismatch_signal_materialized",
                        "trigger_score_ppm_materialized",
                        "trigger_score_threshold_ppm_materialized",
                    ):
                        assertion_page = Path(out_dir) / "assertions" / f"{_slug_id(assertion_ids[key])}.html"
                        self.assertTrue(assertion_page.exists())
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_mixed_source_case_pack_walkthrough_preserves_cross_source_distinguishability(self) -> None:
        schema_ir = _mixed_source_case_pack_schema_ir()

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            refs = {
                "account": encode_idref_v1("AMLAccount", [("account_id", "string", "ACCT-MIX-001")]),
                "beneficiary": encode_idref_v1("AMLBeneficiary", [("beneficiary_id", "string", "BEN-MIX-001")]),
                "device": encode_idref_v1("AMLDevice", [("device_id", "string", "DEV-MIX-001")]),
                "document": encode_idref_v1("AMLReviewForm", [("form_id", "string", "FORM-MIX-001")]),
                "note": encode_idref_v1("AMLInvestigatorNote", [("note_id", "string", "NOTE-MIX-001")]),
                "tx1": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-MIX-001")]),
                "tx2": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-MIX-002")]),
                "tx3": encode_idref_v1("AMLTransaction", [("tx_id", "string", "TX-MIX-003")]),
            }
            tx_refs = {
                "TX-MIX-001": refs["tx1"],
                "TX-MIX-002": refs["tx2"],
                "TX-MIX-003": refs["tx3"],
            }

            raw_feed_records = [
                {
                    "tx_id": "TX-MIX-001",
                    "timestamp_ns": 110,
                    "amount_minor": 9700,
                },
                {
                    "tx_id": "TX-MIX-002",
                    "timestamp_ns": 150,
                    "amount_minor": 9800,
                },
                {
                    "tx_id": "TX-MIX-003",
                    "timestamp_ns": 190,
                    "amount_minor": 9900,
                },
            ]
            form_fixture = {
                "form_id": "FORM-MIX-001",
                "device_id": "DEV-MIX-001",
                "score_threshold_ppm_field": "900000",
            }
            note_fixture = {
                "note_id": "NOTE-MIX-001",
                "text": (
                    "Investigator note NOTE-MIX-001 for account ACCT-MIX-001: the beneficiary "
                    "BEN-MIX-001 was described as an \"elevated-risk corridor\". Activity was "
                    "observed from device DEV-MIX-001 and the profile appears off from the recorded "
                    "beneficial owner. Current trigger score 910000. Background note: customer "
                    "answered follow-up questions calmly."
                ),
            }

            def normalize_transaction_feed(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
                normalized: list[dict[str, Any]] = []
                for record in records:
                    tx_ref = tx_refs[record["tx_id"]]
                    normalized.append(
                        {
                            "key": f"tx_event:{record['tx_id']}",
                            "pred_id": AML_TRANSACTION_EVENT_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                ("entity_ref", tx_ref),
                                ("entity_ref", refs["beneficiary"]),
                                ("int", record["amount_minor"]),
                            ],
                        }
                    )
                    normalized.append(
                        {
                            "key": f"tx_timestamp:{record['tx_id']}",
                            "pred_id": AML_TRANSACTION_TIMESTAMP_PRED_ID,
                            "e_ref": tx_ref,
                            "rest_terms": [("time", record["timestamp_ns"])],
                        }
                    )
                return normalized

            def extract_form_document(form: dict[str, Any]) -> list[dict[str, Any]]:
                return [
                    {
                        "key": "form_shared_device_signal",
                        "pred_id": FORM_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            ("entity_ref", refs["device"]),
                            ("entity_ref", refs["document"]),
                        ],
                    },
                    {
                        "key": "form_trigger_score_threshold_ppm",
                        "pred_id": FORM_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [
                            ("int", int(form["score_threshold_ppm_field"])),
                            ("entity_ref", refs["document"]),
                        ],
                    },
                ]

            def extract_single_note(note: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
                text = note["text"]
                extracted: list[dict[str, Any]] = []
                extraction_meta = {
                    "best_effort_phrases": {},
                    "skipped_phrases": {},
                    "excerpt_map": {},
                }
                if "elevated-risk corridor" in text:
                    extracted.append(
                        {
                            "key": "note_beneficiary_risk",
                            "pred_id": NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                ("entity_ref", refs["beneficiary"]),
                                ("string", "high-risk-jurisdiction"),
                                ("entity_ref", refs["note"]),
                            ],
                        }
                    )
                    extraction_meta["best_effort_phrases"]["jurisdiction_phrase"] = {
                        "raw": "elevated-risk corridor",
                        "mapped_to": "high-risk-jurisdiction",
                        "status": "deterministic_best_effort",
                    }
                if "profile appears off from the recorded beneficial owner" in text:
                    extracted.append(
                        {
                            "key": "note_bo_mismatch_signal",
                            "pred_id": NOTE_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                ("string", "beneficial_owner_mismatch"),
                                ("entity_ref", refs["note"]),
                            ],
                        }
                    )
                if "trigger score 910000" in text:
                    extracted.append(
                        {
                            "key": "note_trigger_score_ppm",
                            "pred_id": NOTE_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID,
                            "e_ref": refs["account"],
                            "rest_terms": [
                                ("int", 910000),
                                ("entity_ref", refs["note"]),
                            ],
                        }
                    )
                    extraction_meta["excerpt_map"]["trigger_score_phrase"] = "trigger score 910000"
                if "customer answered follow-up questions calmly" in text:
                    extraction_meta["skipped_phrases"]["calm_background"] = {
                        "raw": "customer answered follow-up questions calmly",
                        "status": "explicit_skip_background",
                    }
                return extracted, extraction_meta

            def materialize_mixed_source_support(
                normalized_feed_rows: list[dict[str, Any]],
                extracted_form_rows: list[dict[str, Any]],
                extracted_note_rows: list[dict[str, Any]],
            ) -> list[dict[str, Any]]:
                tx_timestamps = [
                    int(row["rest_terms"][0][1])
                    for row in normalized_feed_rows
                    if row["pred_id"] == AML_TRANSACTION_TIMESTAMP_PRED_ID
                ]
                form_by_key = {row["key"]: row for row in extracted_form_rows}
                note_by_key = {row["key"]: row for row in extracted_note_rows}
                return [
                    {
                        "key": "trigger_evaluation_time",
                        "pred_id": AML_TRIGGER_EVALUATION_TIME_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [("time", 200)],
                    },
                    {
                        "key": "windowed_structuring_signal",
                        "pred_id": AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": [("time", min(tx_timestamps) - 10), ("time", max(tx_timestamps) + 110), ("int", 3)],
                    },
                    {
                        "key": "high_risk_outflow_signal",
                        "pred_id": AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": note_by_key["note_beneficiary_risk"]["rest_terms"][:2],
                    },
                    {
                        "key": "shared_device_signal_materialized",
                        "pred_id": AML_SHARED_DEVICE_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": form_by_key["form_shared_device_signal"]["rest_terms"][:1],
                    },
                    {
                        "key": "bo_mismatch_signal_materialized",
                        "pred_id": AML_BO_MISMATCH_SIGNAL_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": note_by_key["note_bo_mismatch_signal"]["rest_terms"][:1],
                    },
                    {
                        "key": "trigger_score_ppm_materialized",
                        "pred_id": AML_TRIGGER_SCORE_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": note_by_key["note_trigger_score_ppm"]["rest_terms"][:1],
                    },
                    {
                        "key": "trigger_score_threshold_ppm_materialized",
                        "pred_id": AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                        "e_ref": refs["account"],
                        "rest_terms": form_by_key["form_trigger_score_threshold_ppm"]["rest_terms"][:1],
                    },
                ]

            normalized_feed_facts = normalize_transaction_feed(raw_feed_records)
            extracted_form_facts = extract_form_document(form_fixture)
            extracted_note_facts, note_extraction_meta = extract_single_note(note_fixture)
            materialized_facts = materialize_mixed_source_support(
                normalized_feed_facts,
                extracted_form_facts,
                extracted_note_facts,
            )

            normalized_feed_by_key = {row["key"]: row for row in normalized_feed_facts}
            extracted_form_by_key = {row["key"]: row for row in extracted_form_facts}
            extracted_note_by_key = {row["key"]: row for row in extracted_note_facts}

            self.assertEqual(
                normalized_feed_by_key["tx_event:TX-MIX-001"]["rest_terms"][2],
                ("int", raw_feed_records[0]["amount_minor"]),
            )
            self.assertEqual(
                extracted_form_by_key["form_trigger_score_threshold_ppm"]["rest_terms"][0],
                ("int", int(form_fixture["score_threshold_ppm_field"])),
            )
            self.assertEqual(
                extracted_form_by_key["form_shared_device_signal"]["rest_terms"][1],
                ("entity_ref", refs["document"]),
            )
            self.assertIn(
                note_extraction_meta["excerpt_map"]["trigger_score_phrase"],
                note_fixture["text"],
            )
            self.assertEqual(
                extracted_note_by_key["note_beneficiary_risk"]["rest_terms"][1],
                ("string", "high-risk-jurisdiction"),
            )
            self.assertEqual(
                note_extraction_meta["best_effort_phrases"]["jurisdiction_phrase"],
                {
                    "raw": "elevated-risk corridor",
                    "mapped_to": "high-risk-jurisdiction",
                    "status": "deterministic_best_effort",
                },
            )

            assertion_ids: dict[str, str] = {}
            for row in normalized_feed_facts + extracted_form_facts + extracted_note_facts + materialized_facts:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": row["pred_id"],
                        "e_ref": row["e_ref"],
                        "rest_terms": [[tag, value] for tag, value in row["rest_terms"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                assertion_ids[row["key"]] = write_resp["write"]["assertion_id"]

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.mixed_source_case_pack_walkthrough",
                        "version": "1.0.0",
                        "select": [
                            "$account",
                            "$beneficiary",
                            "$jurisdiction",
                            "$window_start_ts",
                            "$window_end_ts",
                            "$eval_ts",
                            "$score_ppm",
                        ],
                        "where": [
                            ["pred", AML_TRIGGER_EVALUATION_TIME_PRED_ID, ["$account", "$eval_ts"]],
                            [
                                "pred",
                                AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
                                ["$account", "$window_start_ts", "$window_end_ts", "$structuring_tx_count"],
                            ],
                            ["le", "$window_start_ts", "$eval_ts"],
                            ["le", "$eval_ts", "$window_end_ts"],
                            [
                                "pred",
                                AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
                                ["$account", "$beneficiary", "$jurisdiction"],
                            ],
                            ["pred", AML_SHARED_DEVICE_SIGNAL_PRED_ID, ["$account", "$device"]],
                            ["pred", AML_BO_MISMATCH_SIGNAL_PRED_ID, ["$account", "$mismatch_kind"]],
                            ["pred", AML_TRIGGER_SCORE_PPM_PRED_ID, ["$account", "$score_ppm"]],
                            [
                                "pred",
                                AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
                                ["$account", "$score_threshold_ppm"],
                            ],
                            ["ge", "$score_ppm", "$score_threshold_ppm"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            summary = summary_resp["summary"]
            narrative = narrative_resp["narrative"]
            explain_nl = nl_resp["explain_nl"]

            self.assertEqual(
                raw_explain["root_rule"]["rule_id"],
                "q.mixed_source_case_pack_walkthrough",
            )
            self.assertEqual(
                raw_explain["root_rows"],
                [[refs["account"], refs["beneficiary"], "high-risk-jurisdiction", 100, 300, 200, 910000]],
            )

            invocation = next(
                inv
                for inv in raw_explain["invocations"]
                if inv["rule"]["rule_id"] == "q.mixed_source_case_pack_walkthrough"
            )
            pred_condition_keys = {witness["pred_condition_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_condition_keys,
                {
                    "c0.c0:aml:trigger_evaluation_time",
                    "c0.c1:aml:windowed_structuring_signal",
                    "c0.c4:aml:high_risk_outflow_signal",
                    "c0.c5:aml:shared_device_signal",
                    "c0.c6:aml:bo_mismatch_signal",
                    "c0.c7:aml:trigger_score_ppm",
                    "c0.c8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertEqual(len(invocation["pred_witnesses"]), 7)
            self.assertEqual(len(invocation["non_fact_steps"]), 3)
            self.assertFalse(any(key.endswith(":aml:transaction_event") for key in pred_condition_keys))
            self.assertFalse(any(":form:" in key for key in pred_condition_keys))
            self.assertFalse(any(":note:" in key for key in pred_condition_keys))

            witness_groups = {row["pred_id"]: row for row in summary["predicate_witness_groups"]}
            self.assertNotIn(AML_TRANSACTION_EVENT_PRED_ID, witness_groups)
            self.assertNotIn(FORM_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID, witness_groups)
            self.assertNotIn(NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID, witness_groups)
            self.assertIn(AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID, witness_groups)
            self.assertIn(AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID, witness_groups)
            self.assertEqual(summary["root_row_count"], 1)
            self.assertEqual(summary["invocation_count"], 1)
            self.assertEqual(len(summary["witness_assertion_ids"]), 7)

            self.assertIn(
                "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertNotIn(
                "Predicate aml:transaction_event was witnessed by 3 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertNotIn(
                "Predicate form:shared_device_signal_extracted was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertNotIn(
                "Predicate note:beneficiary_risk_extracted was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )

            self.assertEqual(
                explain_nl["headline"],
                "Rule q.mixed_source_case_pack_walkthrough@1.0.0 matched 1 root row(s) across 1 invocation(s).",
            )
            self.assertTrue(any("aml:windowed_structuring_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("aml:high_risk_outflow_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            lowered_nl_paragraphs = [paragraph.lower() for paragraph in explain_nl["paragraphs"]]
            self.assertFalse(any("aml:transaction_event" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("form:" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("note:" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("case package" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("source-linkage" in paragraph for paragraph in lowered_nl_paragraphs))
            self.assertFalse(any("first-class case" in paragraph for paragraph in lowered_nl_paragraphs))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))
                package = load_audit_package(package_dir)
                query = AuditQuery(package)
                assertion_index = load_assertion_index(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertEqual(audit_summary, summary)
                self.assertEqual(audit_narrative, narrative)

                feed_detail = assertion_index.get_assertion_detail(assertion_ids["tx_event:TX-MIX-001"])
                form_detail = assertion_index.get_assertion_detail(assertion_ids["form_shared_device_signal"])
                note_detail = assertion_index.get_assertion_detail(assertion_ids["note_beneficiary_risk"])
                self.assertIsNotNone(feed_detail)
                self.assertIsNotNone(form_detail)
                self.assertIsNotNone(note_detail)
                assert feed_detail is not None
                assert form_detail is not None
                assert note_detail is not None
                self.assertEqual(feed_detail["claim"]["pred_id"], AML_TRANSACTION_EVENT_PRED_ID)
                self.assertEqual(form_detail["claim"]["pred_id"], FORM_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID)
                self.assertEqual(note_detail["claim"]["pred_id"], NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID)
                self.assertEqual(feed_detail["claim_args"][0]["tag"], "entity_ref")
                self.assertEqual(form_detail["claim_args"][1]["tag"], "entity_ref")
                self.assertEqual(note_detail["claim_args"][2]["tag"], "entity_ref")
                self.assertTrue(feed_detail["claim_args"][0]["val"].startswith("idref_v1:AMLTransaction:"))
                self.assertTrue(form_detail["claim_args"][1]["val"].startswith("idref_v1:AMLReviewForm:"))
                self.assertTrue(note_detail["claim_args"][2]["val"].startswith("idref_v1:AMLInvestigatorNote:"))
                self.assertNotEqual(feed_detail["claim_args"][0]["val"], form_detail["claim_args"][1]["val"])
                self.assertNotEqual(feed_detail["claim_args"][0]["val"], note_detail["claim_args"][2]["val"])
                self.assertNotEqual(form_detail["claim_args"][1]["val"], note_detail["claim_args"][2]["val"])

                with TemporaryDirectory() as out_dir:
                    site_manifest = render_audit_static_site(package_dir, out_dir)
                    self.assertEqual(site_manifest["rule_trace_count"], 1)
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{_slug_id(rule_run_id)}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("q.mixed_source_case_pack_walkthrough", html)
                    self.assertIn(
                        "Predicate aml:windowed_structuring_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertIn(
                        "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertNotIn("Predicate aml:transaction_event was witnessed", html)
                    lowered_html = html.lower()
                    self.assertNotIn("case package", lowered_html)
                    self.assertNotIn("source-linkage", lowered_html)
                    self.assertNotIn("first-class case", lowered_html)
                    self.assertIn(assertion_ids["windowed_structuring_signal"], html)

                    for key in (
                        "tx_event:TX-MIX-001",
                        "tx_event:TX-MIX-002",
                        "tx_event:TX-MIX-003",
                        "tx_timestamp:TX-MIX-001",
                        "tx_timestamp:TX-MIX-002",
                        "tx_timestamp:TX-MIX-003",
                        "form_shared_device_signal",
                        "form_trigger_score_threshold_ppm",
                        "note_beneficiary_risk",
                        "note_bo_mismatch_signal",
                        "note_trigger_score_ppm",
                        "trigger_evaluation_time",
                        "windowed_structuring_signal",
                        "high_risk_outflow_signal",
                        "shared_device_signal_materialized",
                        "bo_mismatch_signal_materialized",
                        "trigger_score_ppm_materialized",
                        "trigger_score_threshold_ppm_materialized",
                    ):
                        assertion_page = Path(out_dir) / "assertions" / f"{_slug_id(assertion_ids[key])}.html"
                        self.assertTrue(assertion_page.exists())
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_process_safety_shutdown_walkthrough_reuses_five_layer_explain_delivery(self) -> None:
        schema_ir = _process_safety_shutdown_schema_ir()

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            unit_ref = encode_idref_v1("ProcessUnit", [("unit_id", "string", "UNIT-001")])

            assertion_ids: dict[str, str] = {}
            for pred_id, rest_terms in (
                (
                    PROCESS_HIGH_HIGH_TEMPERATURE_PRED_ID,
                    [("int", 510)],
                ),
                (
                    PROCESS_TEMPERATURE_SHUTDOWN_THRESHOLD_PRED_ID,
                    [("int", 500)],
                ),
                (
                    PROCESS_HIGH_HIGH_PRESSURE_PRED_ID,
                    [("int", 245)],
                ),
                (
                    PROCESS_PRESSURE_SHUTDOWN_THRESHOLD_PRED_ID,
                    [("int", 240)],
                ),
                (
                    PROCESS_SHUTDOWN_ALARM_ACTIVE_PRED_ID,
                    [],
                ),
                (
                    PROCESS_SHUTDOWN_INTERLOCK_ARMED_PRED_ID,
                    [],
                ),
                (
                    PROCESS_MANUAL_OVERRIDE_CLEARED_PRED_ID,
                    [],
                ),
            ):
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": pred_id,
                        "e_ref": unit_ref,
                        "rest_terms": [[tag, value] for tag, value in rest_terms],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                assertion_ids.setdefault(f"{pred_id}:{len(assertion_ids)}", write_resp["write"]["assertion_id"])

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.process_shutdown_required_walkthrough",
                        "version": "1.0.0",
                        "select": [
                            "$unit",
                            "$temperature_c",
                            "$temperature_threshold_c",
                            "$pressure_kpa",
                            "$pressure_threshold_kpa",
                        ],
                        "where": [
                            ["pred", PROCESS_HIGH_HIGH_TEMPERATURE_PRED_ID, ["$unit", "$temperature_c"]],
                            ["pred", PROCESS_TEMPERATURE_SHUTDOWN_THRESHOLD_PRED_ID, ["$unit", "$temperature_threshold_c"]],
                            ["ge", "$temperature_c", "$temperature_threshold_c"],
                            ["pred", PROCESS_HIGH_HIGH_PRESSURE_PRED_ID, ["$unit", "$pressure_kpa"]],
                            ["pred", PROCESS_PRESSURE_SHUTDOWN_THRESHOLD_PRED_ID, ["$unit", "$pressure_threshold_kpa"]],
                            ["ge", "$pressure_kpa", "$pressure_threshold_kpa"],
                            ["pred", PROCESS_SHUTDOWN_ALARM_ACTIVE_PRED_ID, ["$unit"]],
                            ["pred", PROCESS_SHUTDOWN_INTERLOCK_ARMED_PRED_ID, ["$unit"]],
                            ["pred", PROCESS_MANUAL_OVERRIDE_CLEARED_PRED_ID, ["$unit"]],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            summary = summary_resp["summary"]
            narrative = narrative_resp["narrative"]
            explain_nl = nl_resp["explain_nl"]

            self.assertEqual(raw_explain["root_rule"]["rule_id"], "q.process_shutdown_required_walkthrough")
            self.assertEqual(
                raw_explain["root_rows"],
                [[unit_ref, 510, 500, 245, 240]],
            )

            invocation = next(
                inv
                for inv in raw_explain["invocations"]
                if inv["rule"]["rule_id"] == "q.process_shutdown_required_walkthrough"
            )
            self.assertEqual(len(invocation["pred_witnesses"]), 7)
            self.assertEqual(len(invocation["non_fact_steps"]), 2)
            self.assertEqual({step["kind"] for step in invocation["non_fact_steps"]}, {"ge"})

            pred_condition_keys = {witness["pred_condition_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_condition_keys,
                {
                    "c0.c0:process:high_high_temperature",
                    "c0.c1:process:temperature_shutdown_threshold",
                    "c0.c3:process:high_high_pressure",
                    "c0.c4:process:pressure_shutdown_threshold",
                    "c0.c6:process:shutdown_alarm_active",
                    "c0.c7:process:shutdown_interlock_armed",
                    "c0.c8:process:manual_override_cleared",
                },
            )

            non_fact_by_key = {step["step_key"]: step for step in invocation["non_fact_steps"]}
            self.assertEqual(sorted(non_fact_by_key.keys()), ["c0.c2:ge", "c0.c5:ge"])
            temp_binding = dict(dict(non_fact_by_key["c0.c2:ge"]["details"])["binding"])
            pressure_binding = dict(dict(non_fact_by_key["c0.c5:ge"]["details"])["binding"])
            self.assertEqual(temp_binding["$temperature_c"], 510)
            self.assertEqual(temp_binding["$temperature_threshold_c"], 500)
            self.assertEqual(pressure_binding["$pressure_kpa"], 245)
            self.assertEqual(pressure_binding["$pressure_threshold_kpa"], 240)

            witness_groups = {row["pred_id"]: row for row in summary["predicate_witness_groups"]}
            self.assertEqual(summary["root_row_count"], 1)
            self.assertEqual(summary["invocation_count"], 1)
            self.assertEqual(len(summary["witness_assertion_ids"]), 7)
            self.assertEqual(
                witness_groups[PROCESS_HIGH_HIGH_TEMPERATURE_PRED_ID]["asrt_ids"],
                [assertion_ids["process:high_high_temperature:0"]],
            )
            self.assertEqual(
                witness_groups[PROCESS_SHUTDOWN_INTERLOCK_ARMED_PRED_ID]["asrt_ids"],
                [assertion_ids["process:shutdown_interlock_armed:5"]],
            )
            self.assertEqual(
                witness_groups[PROCESS_MANUAL_OVERRIDE_CLEARED_PRED_ID]["asrt_ids"],
                [assertion_ids["process:manual_override_cleared:6"]],
            )

            self.assertIn(
                "Predicate process:high_high_temperature was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate process:shutdown_interlock_armed was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate process:manual_override_cleared was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Check kind ge was evaluated 2 time(s) across 1 invocation(s).",
                narrative["non_fact_check_lines"],
            )

            self.assertEqual(
                explain_nl["headline"],
                "Rule q.process_shutdown_required_walkthrough@1.0.0 matched 1 root row(s) across 1 invocation(s).",
            )
            self.assertTrue(any("process:high_high_temperature" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("process:shutdown_interlock_armed" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("process:manual_override_cleared" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("review" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("flagged" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))
                package = load_audit_package(package_dir)
                query = AuditQuery(package)
                assertion_index = load_assertion_index(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertEqual(audit_summary, summary)
                self.assertEqual(audit_narrative, narrative)

                for key, pred_id in (
                    ("process:high_high_temperature:0", PROCESS_HIGH_HIGH_TEMPERATURE_PRED_ID),
                    ("process:shutdown_alarm_active:4", PROCESS_SHUTDOWN_ALARM_ACTIVE_PRED_ID),
                    ("process:shutdown_interlock_armed:5", PROCESS_SHUTDOWN_INTERLOCK_ARMED_PRED_ID),
                    ("process:manual_override_cleared:6", PROCESS_MANUAL_OVERRIDE_CLEARED_PRED_ID),
                ):
                    detail = assertion_index.get_assertion_detail(assertion_ids[key])
                    self.assertIsNotNone(detail)
                    assert detail is not None
                    self.assertEqual(detail["claim"]["pred_id"], pred_id)

                with TemporaryDirectory() as out_dir:
                    site_manifest = render_audit_static_site(package_dir, out_dir)
                    self.assertEqual(site_manifest["rule_trace_count"], 1)
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{_slug_id(rule_run_id)}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("q.process_shutdown_required_walkthrough", html)
                    self.assertIn(
                        "Predicate process:shutdown_interlock_armed was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertIn(
                        "Predicate process:manual_override_cleared was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertIn(assertion_ids["process:shutdown_interlock_armed:5"], html)
                    self.assertIn(assertion_ids["process:manual_override_cleared:6"], html)

                    for key in (
                        "process:high_high_temperature:0",
                        "process:temperature_shutdown_threshold:1",
                        "process:high_high_pressure:2",
                        "process:pressure_shutdown_threshold:3",
                        "process:shutdown_alarm_active:4",
                        "process:shutdown_interlock_armed:5",
                        "process:manual_override_cleared:6",
                    ):
                        assertion_page = Path(out_dir) / "assertions" / f"{_slug_id(assertion_ids[key])}.html"
                        self.assertTrue(assertion_page.exists())
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_clinical_weak_signal_walkthrough_preserves_collective_significance_honesty(self) -> None:
        schema_ir = _clinical_weak_signal_schema_ir()

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            patient_ref = encode_idref_v1("ClinicalPatient", [("patient_id", "string", "PT-001")])

            assertion_ids: dict[str, str] = {}
            for pred_id, rest_terms in (
                (
                    CLINICAL_MILD_FEVER_SIGNAL_PRED_ID,
                    [("int", 381)],
                ),
                (
                    CLINICAL_MILD_TACHYCARDIA_SIGNAL_PRED_ID,
                    [("int", 108)],
                ),
                (
                    CLINICAL_MILD_TACHYPNEA_SIGNAL_PRED_ID,
                    [("int", 23)],
                ),
                (
                    CLINICAL_MILD_HYPOTENSION_SIGNAL_PRED_ID,
                    [("int", 67)],
                ),
                (
                    CLINICAL_NORMAL_OXYGEN_SATURATION_PRED_ID,
                    [("int", 97)],
                ),
                (
                    CLINICAL_NORMAL_LACTATE_PRED_ID,
                    [("int", 15)],
                ),
                (
                    CLINICAL_ABNORMAL_INDICATOR_COUNT_PRED_ID,
                    [("int", 4)],
                ),
                (
                    CLINICAL_DETERIORATION_COUNT_THRESHOLD_PRED_ID,
                    [("int", 4)],
                ),
            ):
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": pred_id,
                        "e_ref": patient_ref,
                        "rest_terms": [[tag, value] for tag, value in rest_terms],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])
                assertion_ids.setdefault(f"{pred_id}:{len(assertion_ids)}", write_resp["write"]["assertion_id"])

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.clinical_weak_signal_walkthrough",
                        "version": "1.0.0",
                        "select": [
                            "$patient",
                            "$abnormal_indicator_count",
                            "$deterioration_threshold",
                        ],
                        "where": [
                            ["pred", CLINICAL_MILD_FEVER_SIGNAL_PRED_ID, ["$patient", "$temp_tenths_c"]],
                            ["pred", CLINICAL_MILD_TACHYCARDIA_SIGNAL_PRED_ID, ["$patient", "$heart_rate_bpm"]],
                            ["pred", CLINICAL_MILD_TACHYPNEA_SIGNAL_PRED_ID, ["$patient", "$resp_rate_bpm"]],
                            ["pred", CLINICAL_MILD_HYPOTENSION_SIGNAL_PRED_ID, ["$patient", "$map_mmhg"]],
                            [
                                "pred",
                                CLINICAL_ABNORMAL_INDICATOR_COUNT_PRED_ID,
                                ["$patient", "$abnormal_indicator_count"],
                            ],
                            [
                                "pred",
                                CLINICAL_DETERIORATION_COUNT_THRESHOLD_PRED_ID,
                                ["$patient", "$deterioration_threshold"],
                            ],
                            ["ge", "$abnormal_indicator_count", "$deterioration_threshold"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            summary = summary_resp["summary"]
            narrative = narrative_resp["narrative"]
            explain_nl = nl_resp["explain_nl"]

            self.assertEqual(raw_explain["root_rule"]["rule_id"], "q.clinical_weak_signal_walkthrough")
            self.assertEqual(raw_explain["root_rows"], [[patient_ref, 4, 4]])

            invocation = next(
                inv
                for inv in raw_explain["invocations"]
                if inv["rule"]["rule_id"] == "q.clinical_weak_signal_walkthrough"
            )
            pred_condition_keys = {witness["pred_condition_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_condition_keys,
                {
                    "c0.c0:clinical:mild_fever_signal",
                    "c0.c1:clinical:mild_tachycardia_signal",
                    "c0.c2:clinical:mild_tachypnea_signal",
                    "c0.c3:clinical:mild_hypotension_signal",
                    "c0.c4:clinical:abnormal_indicator_count",
                    "c0.c5:clinical:deterioration_count_threshold",
                },
            )
            self.assertFalse(any(key.endswith(":clinical:normal_oxygen_saturation") for key in pred_condition_keys))
            self.assertFalse(any(key.endswith(":clinical:normal_lactate") for key in pred_condition_keys))
            self.assertEqual(len(invocation["pred_witnesses"]), 6)
            self.assertEqual(len(invocation["non_fact_steps"]), 1)
            self.assertEqual(invocation["non_fact_steps"][0]["kind"], "ge")

            threshold_binding = dict(dict(invocation["non_fact_steps"][0]["details"])["binding"])
            self.assertEqual(threshold_binding["$abnormal_indicator_count"], 4)
            self.assertEqual(threshold_binding["$deterioration_threshold"], 4)

            witness_groups = {row["pred_id"]: row for row in summary["predicate_witness_groups"]}
            self.assertEqual(summary["root_row_count"], 1)
            self.assertEqual(summary["invocation_count"], 1)
            self.assertEqual(len(summary["witness_assertion_ids"]), 6)
            self.assertEqual(
                witness_groups[CLINICAL_MILD_FEVER_SIGNAL_PRED_ID]["asrt_ids"],
                [assertion_ids["clinical:mild_fever_signal:0"]],
            )
            self.assertEqual(
                witness_groups[CLINICAL_MILD_TACHYCARDIA_SIGNAL_PRED_ID]["asrt_ids"],
                [assertion_ids["clinical:mild_tachycardia_signal:1"]],
            )
            self.assertEqual(
                witness_groups[CLINICAL_ABNORMAL_INDICATOR_COUNT_PRED_ID]["asrt_ids"],
                [assertion_ids["clinical:abnormal_indicator_count:6"]],
            )
            self.assertNotIn(CLINICAL_NORMAL_OXYGEN_SATURATION_PRED_ID, witness_groups)
            self.assertNotIn(CLINICAL_NORMAL_LACTATE_PRED_ID, witness_groups)

            self.assertIn(
                "Predicate clinical:mild_fever_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate clinical:mild_tachypnea_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Predicate clinical:abnormal_indicator_count was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertNotIn(
                "Predicate clinical:normal_oxygen_saturation was witnessed by 1 assertion(s) across 1 invocation(s).",
                narrative["predicate_lines"],
            )
            self.assertIn(
                "Check kind ge was evaluated 1 time(s) across 1 invocation(s).",
                narrative["non_fact_check_lines"],
            )

            self.assertEqual(
                explain_nl["headline"],
                "Rule q.clinical_weak_signal_walkthrough@1.0.0 matched 1 root row(s) across 1 invocation(s).",
            )
            self.assertTrue(any("clinical:mild_fever_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("clinical:mild_tachycardia_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("clinical:mild_tachypnea_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("clinical:mild_hypotension_signal" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(any("clinical:abnormal_indicator_count" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertTrue(
                any("Check kind ge was evaluated 1 time(s) across 1 invocation(s)." in paragraph for paragraph in explain_nl["paragraphs"])
            )
            self.assertFalse(any("clinical:normal_oxygen_saturation" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("clinical:normal_lactate" in paragraph for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("probability" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("confidence" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("weight" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))
            self.assertFalse(any("severe" in paragraph.lower() for paragraph in explain_nl["paragraphs"]))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))
                package = load_audit_package(package_dir)
                query = AuditQuery(package)
                assertion_index = load_assertion_index(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertEqual(audit_summary, summary)
                self.assertEqual(audit_narrative, narrative)

                mild_detail = assertion_index.get_assertion_detail(assertion_ids["clinical:mild_fever_signal:0"])
                normal_o2_detail = assertion_index.get_assertion_detail(assertion_ids["clinical:normal_oxygen_saturation:4"])
                normal_lactate_detail = assertion_index.get_assertion_detail(assertion_ids["clinical:normal_lactate:5"])
                self.assertIsNotNone(mild_detail)
                self.assertIsNotNone(normal_o2_detail)
                self.assertIsNotNone(normal_lactate_detail)
                assert mild_detail is not None
                assert normal_o2_detail is not None
                assert normal_lactate_detail is not None
                self.assertEqual(mild_detail["claim"]["pred_id"], CLINICAL_MILD_FEVER_SIGNAL_PRED_ID)
                self.assertEqual(normal_o2_detail["claim"]["pred_id"], CLINICAL_NORMAL_OXYGEN_SATURATION_PRED_ID)
                self.assertEqual(normal_lactate_detail["claim"]["pred_id"], CLINICAL_NORMAL_LACTATE_PRED_ID)

                with TemporaryDirectory() as out_dir:
                    site_manifest = render_audit_static_site(package_dir, out_dir)
                    self.assertEqual(site_manifest["rule_trace_count"], 1)
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{_slug_id(rule_run_id)}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("q.clinical_weak_signal_walkthrough", html)
                    self.assertIn(
                        "Predicate clinical:mild_fever_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertIn(
                        "Predicate clinical:abnormal_indicator_count was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertNotIn("Predicate clinical:normal_oxygen_saturation was witnessed", html)
                    self.assertIn(assertion_ids["clinical:mild_fever_signal:0"], html)
                    self.assertIn(assertion_ids["clinical:deterioration_count_threshold:7"], html)

                    for key in (
                        "clinical:mild_fever_signal:0",
                        "clinical:mild_tachycardia_signal:1",
                        "clinical:mild_tachypnea_signal:2",
                        "clinical:mild_hypotension_signal:3",
                        "clinical:normal_oxygen_saturation:4",
                        "clinical:normal_lactate:5",
                        "clinical:abnormal_indicator_count:6",
                        "clinical:deterioration_count_threshold:7",
                    ):
                        assertion_page = Path(out_dir) / "assertions" / f"{_slug_id(assertion_ids[key])}.html"
                        self.assertTrue(assertion_page.exists())
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()


def _aml_case_review_schema_ir() -> dict[str, Any]:
    schema_ir = copy.deepcopy(_schema_ir())
    predicates = schema_ir["predicates"]
    projection_predicates = schema_ir["projection"]["predicates"]
    aml_predicates = [
        {
            "pred_id": AML_TRANSACTION_EVENT_PRED_ID,
            "owner_type": "aml_account",
            "arity": 4,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "transaction_ref", "type_domain": "entity_ref"},
                {"name": "beneficiary_ref", "type_domain": "entity_ref"},
                {"name": "amount_minor", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": AML_SHARED_DEVICE_SIGNAL_PRED_ID,
            "owner_type": "aml_account",
            "arity": 2,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "device_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": AML_BO_MISMATCH_SIGNAL_PRED_ID,
            "owner_type": "aml_account",
            "arity": 2,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "mismatch_kind", "type_domain": "string"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": AML_BENEFICIARY_RISK_PRED_ID,
            "owner_type": "aml_account",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "beneficiary_ref", "type_domain": "entity_ref"},
                {"name": "jurisdiction", "type_domain": "string"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
    ]
    existing = {pred.get("pred_id") for pred in predicates if isinstance(pred, dict)}
    for predicate in aml_predicates:
        pred_id = predicate["pred_id"]
        if pred_id not in existing:
            predicates.append(predicate)
            existing.add(pred_id)
        if pred_id not in projection_predicates:
            projection_predicates.append(pred_id)
    return schema_ir


def _aml_trigger_walkthrough_schema_ir() -> dict[str, Any]:
    schema_ir = _aml_case_review_schema_ir()
    predicates = schema_ir["predicates"]
    projection_predicates = schema_ir["projection"]["predicates"]
    aml_predicates = [
        {
            "pred_id": AML_TRIGGER_EVALUATION_TIME_PRED_ID,
            "owner_type": "aml_account",
            "arity": 2,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "evaluation_ts", "type_domain": "time"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": AML_WINDOWED_STRUCTURING_SIGNAL_PRED_ID,
            "owner_type": "aml_account",
            "arity": 4,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "window_start_ns", "type_domain": "time"},
                {"name": "window_end_ns", "type_domain": "time"},
                {"name": "transaction_count", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": AML_HIGH_RISK_OUTFLOW_SIGNAL_PRED_ID,
            "owner_type": "aml_account",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "beneficiary_ref", "type_domain": "entity_ref"},
                {"name": "jurisdiction", "type_domain": "string"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": AML_TRIGGER_SCORE_PPM_PRED_ID,
            "owner_type": "aml_account",
            "arity": 2,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "trigger_score_ppm", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": AML_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
            "owner_type": "aml_account",
            "arity": 2,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "trigger_score_threshold_ppm", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
    ]
    existing = {pred.get("pred_id") for pred in predicates if isinstance(pred, dict)}
    for predicate in aml_predicates:
        pred_id = predicate["pred_id"]
        if pred_id not in existing:
            predicates.append(predicate)
            existing.add(pred_id)
        if pred_id not in projection_predicates:
            projection_predicates.append(pred_id)
    return schema_ir


def _aml_aggregation_materialization_schema_ir() -> dict[str, Any]:
    schema_ir = _aml_trigger_walkthrough_schema_ir()
    predicates = schema_ir["predicates"]
    projection_predicates = schema_ir["projection"]["predicates"]
    aml_predicates = [
        {
            "pred_id": AML_TRANSACTION_TIMESTAMP_PRED_ID,
            "owner_type": "aml_transaction",
            "arity": 2,
            "arg_specs": [
                {"name": "transaction_ref", "type_domain": "entity_ref"},
                {"name": "transaction_ts", "type_domain": "time"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
    ]
    existing = {pred.get("pred_id") for pred in predicates if isinstance(pred, dict)}
    for predicate in aml_predicates:
        pred_id = predicate["pred_id"]
        if pred_id not in existing:
            predicates.append(predicate)
            existing.add(pred_id)
        if pred_id not in projection_predicates:
            projection_predicates.append(pred_id)
    return schema_ir


def _process_safety_shutdown_schema_ir() -> dict[str, Any]:
    schema_ir = copy.deepcopy(_schema_ir())
    predicates = schema_ir["predicates"]
    projection_predicates = schema_ir["projection"]["predicates"]
    process_predicates = [
        {
            "pred_id": PROCESS_HIGH_HIGH_TEMPERATURE_PRED_ID,
            "owner_type": "process_unit",
            "arity": 2,
            "arg_specs": [
                {"name": "unit_ref", "type_domain": "entity_ref"},
                {"name": "temperature_c", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": PROCESS_TEMPERATURE_SHUTDOWN_THRESHOLD_PRED_ID,
            "owner_type": "process_unit",
            "arity": 2,
            "arg_specs": [
                {"name": "unit_ref", "type_domain": "entity_ref"},
                {"name": "threshold_c", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": PROCESS_HIGH_HIGH_PRESSURE_PRED_ID,
            "owner_type": "process_unit",
            "arity": 2,
            "arg_specs": [
                {"name": "unit_ref", "type_domain": "entity_ref"},
                {"name": "pressure_kpa", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": PROCESS_PRESSURE_SHUTDOWN_THRESHOLD_PRED_ID,
            "owner_type": "process_unit",
            "arity": 2,
            "arg_specs": [
                {"name": "unit_ref", "type_domain": "entity_ref"},
                {"name": "threshold_kpa", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": PROCESS_SHUTDOWN_ALARM_ACTIVE_PRED_ID,
            "owner_type": "process_unit",
            "arity": 1,
            "arg_specs": [
                {"name": "unit_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0],
        },
        {
            "pred_id": PROCESS_SHUTDOWN_INTERLOCK_ARMED_PRED_ID,
            "owner_type": "process_unit",
            "arity": 1,
            "arg_specs": [
                {"name": "unit_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0],
        },
        {
            "pred_id": PROCESS_MANUAL_OVERRIDE_CLEARED_PRED_ID,
            "owner_type": "process_unit",
            "arity": 1,
            "arg_specs": [
                {"name": "unit_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0],
        },
    ]
    existing = {pred.get("pred_id") for pred in predicates if isinstance(pred, dict)}
    for predicate in process_predicates:
        pred_id = predicate["pred_id"]
        if pred_id not in existing:
            predicates.append(predicate)
            existing.add(pred_id)
        if pred_id not in projection_predicates:
            projection_predicates.append(pred_id)
    return schema_ir


def _clinical_weak_signal_schema_ir() -> dict[str, Any]:
    schema_ir = copy.deepcopy(_schema_ir())
    predicates = schema_ir["predicates"]
    projection_predicates = schema_ir["projection"]["predicates"]
    clinical_predicates = [
        {
            "pred_id": CLINICAL_MILD_FEVER_SIGNAL_PRED_ID,
            "owner_type": "clinical_patient",
            "arity": 2,
            "arg_specs": [
                {"name": "patient_ref", "type_domain": "entity_ref"},
                {"name": "temp_tenths_c", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": CLINICAL_MILD_TACHYCARDIA_SIGNAL_PRED_ID,
            "owner_type": "clinical_patient",
            "arity": 2,
            "arg_specs": [
                {"name": "patient_ref", "type_domain": "entity_ref"},
                {"name": "heart_rate_bpm", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": CLINICAL_MILD_TACHYPNEA_SIGNAL_PRED_ID,
            "owner_type": "clinical_patient",
            "arity": 2,
            "arg_specs": [
                {"name": "patient_ref", "type_domain": "entity_ref"},
                {"name": "resp_rate_bpm", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": CLINICAL_MILD_HYPOTENSION_SIGNAL_PRED_ID,
            "owner_type": "clinical_patient",
            "arity": 2,
            "arg_specs": [
                {"name": "patient_ref", "type_domain": "entity_ref"},
                {"name": "map_mmhg", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": CLINICAL_NORMAL_OXYGEN_SATURATION_PRED_ID,
            "owner_type": "clinical_patient",
            "arity": 2,
            "arg_specs": [
                {"name": "patient_ref", "type_domain": "entity_ref"},
                {"name": "spo2_percent", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": CLINICAL_NORMAL_LACTATE_PRED_ID,
            "owner_type": "clinical_patient",
            "arity": 2,
            "arg_specs": [
                {"name": "patient_ref", "type_domain": "entity_ref"},
                {"name": "lactate_tenths_mmol_l", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": CLINICAL_ABNORMAL_INDICATOR_COUNT_PRED_ID,
            "owner_type": "clinical_patient",
            "arity": 2,
            "arg_specs": [
                {"name": "patient_ref", "type_domain": "entity_ref"},
                {"name": "abnormal_indicator_count", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
        {
            "pred_id": CLINICAL_DETERIORATION_COUNT_THRESHOLD_PRED_ID,
            "owner_type": "clinical_patient",
            "arity": 2,
            "arg_specs": [
                {"name": "patient_ref", "type_domain": "entity_ref"},
                {"name": "deterioration_threshold", "type_domain": "int"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1],
        },
    ]
    existing = {pred.get("pred_id") for pred in predicates if isinstance(pred, dict)}
    for predicate in clinical_predicates:
        pred_id = predicate["pred_id"]
        if pred_id not in existing:
            predicates.append(predicate)
            existing.add(pred_id)
        if pred_id not in projection_predicates:
            projection_predicates.append(pred_id)
    return schema_ir


def _form_document_extraction_schema_ir() -> dict[str, Any]:
    schema_ir = _aml_aggregation_materialization_schema_ir()
    predicates = schema_ir["predicates"]
    projection_predicates = schema_ir["projection"]["predicates"]
    form_predicates = [
        {
            "pred_id": FORM_EXTRACTED_BENEFICIARY_RISK_PRED_ID,
            "owner_type": "aml_review_form",
            "arity": 4,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "beneficiary_ref", "type_domain": "entity_ref"},
                {"name": "jurisdiction", "type_domain": "string"},
                {"name": "document_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 3],
        },
        {
            "pred_id": FORM_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID,
            "owner_type": "aml_review_form",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "device_ref", "type_domain": "entity_ref"},
                {"name": "document_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": FORM_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID,
            "owner_type": "aml_review_form",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "mismatch_kind", "type_domain": "string"},
                {"name": "document_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": FORM_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID,
            "owner_type": "aml_review_form",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "score_ppm", "type_domain": "int"},
                {"name": "document_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": FORM_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
            "owner_type": "aml_review_form",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "score_threshold_ppm", "type_domain": "int"},
                {"name": "document_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
    ]
    existing = {pred.get("pred_id") for pred in predicates if isinstance(pred, dict)}
    for predicate in form_predicates:
        pred_id = predicate["pred_id"]
        if pred_id not in existing:
            predicates.append(predicate)
            existing.add(pred_id)
        if pred_id not in projection_predicates:
            projection_predicates.append(pred_id)
    return schema_ir


def _single_note_narrative_extraction_schema_ir() -> dict[str, Any]:
    schema_ir = _aml_aggregation_materialization_schema_ir()
    predicates = schema_ir["predicates"]
    projection_predicates = schema_ir["projection"]["predicates"]
    note_predicates = [
        {
            "pred_id": NOTE_EXTRACTED_REVIEW_WINDOW_SUMMARY_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 6,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "window_start_ns", "type_domain": "time"},
                {"name": "window_end_ns", "type_domain": "time"},
                {"name": "evaluation_time_ns", "type_domain": "time"},
                {"name": "transaction_count", "type_domain": "int"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2, 3, 4, 5],
        },
        {
            "pred_id": NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 4,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "beneficiary_ref", "type_domain": "entity_ref"},
                {"name": "jurisdiction", "type_domain": "string"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 3],
        },
        {
            "pred_id": NOTE_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "device_ref", "type_domain": "entity_ref"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": NOTE_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "mismatch_kind", "type_domain": "string"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": NOTE_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "score_ppm", "type_domain": "int"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": NOTE_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "score_threshold_ppm", "type_domain": "int"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
    ]
    existing = {pred.get("pred_id") for pred in predicates if isinstance(pred, dict)}
    for predicate in note_predicates:
        pred_id = predicate["pred_id"]
        if pred_id not in existing:
            predicates.append(predicate)
            existing.add(pred_id)
        if pred_id not in projection_predicates:
            projection_predicates.append(pred_id)
    return schema_ir


def _correlated_multi_note_review_schema_ir() -> dict[str, Any]:
    schema_ir = _aml_aggregation_materialization_schema_ir()
    predicates = schema_ir["predicates"]
    projection_predicates = schema_ir["projection"]["predicates"]
    multi_note_predicates = [
        {
            "pred_id": MULTI_NOTE_EXTRACTED_REVIEW_WINDOW_SUMMARY_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 6,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "window_start_ns", "type_domain": "time"},
                {"name": "window_end_ns", "type_domain": "time"},
                {"name": "evaluation_time_ns", "type_domain": "time"},
                {"name": "transaction_count", "type_domain": "int"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2, 3, 4, 5],
        },
        {
            "pred_id": MULTI_NOTE_EXTRACTED_BENEFICIARY_RISK_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 4,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "beneficiary_ref", "type_domain": "entity_ref"},
                {"name": "jurisdiction", "type_domain": "string"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 3],
        },
        {
            "pred_id": MULTI_NOTE_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "device_ref", "type_domain": "entity_ref"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": MULTI_NOTE_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "mismatch_kind", "type_domain": "string"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": MULTI_NOTE_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "score_ppm", "type_domain": "int"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": MULTI_NOTE_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
            "owner_type": "aml_investigator_note",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "score_threshold_ppm", "type_domain": "int"},
                {"name": "note_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
    ]
    existing = {pred.get("pred_id") for pred in predicates if isinstance(pred, dict)}
    for predicate in multi_note_predicates:
        pred_id = predicate["pred_id"]
        if pred_id not in existing:
            predicates.append(predicate)
            existing.add(pred_id)
        if pred_id not in projection_predicates:
            projection_predicates.append(pred_id)
    return schema_ir


def _conflicting_multi_note_evidence_schema_ir() -> dict[str, Any]:
    return _correlated_multi_note_review_schema_ir()


def _mixed_source_case_pack_schema_ir() -> dict[str, Any]:
    schema_ir = _single_note_narrative_extraction_schema_ir()
    predicates = schema_ir["predicates"]
    projection_predicates = schema_ir["projection"]["predicates"]
    form_predicates = [
        {
            "pred_id": FORM_EXTRACTED_BENEFICIARY_RISK_PRED_ID,
            "owner_type": "aml_review_form",
            "arity": 4,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "beneficiary_ref", "type_domain": "entity_ref"},
                {"name": "jurisdiction", "type_domain": "string"},
                {"name": "document_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 3],
        },
        {
            "pred_id": FORM_EXTRACTED_SHARED_DEVICE_SIGNAL_PRED_ID,
            "owner_type": "aml_review_form",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "device_ref", "type_domain": "entity_ref"},
                {"name": "document_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": FORM_EXTRACTED_BO_MISMATCH_SIGNAL_PRED_ID,
            "owner_type": "aml_review_form",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "mismatch_kind", "type_domain": "string"},
                {"name": "document_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": FORM_EXTRACTED_TRIGGER_SCORE_PPM_PRED_ID,
            "owner_type": "aml_review_form",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "score_ppm", "type_domain": "int"},
                {"name": "document_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
        {
            "pred_id": FORM_EXTRACTED_TRIGGER_SCORE_THRESHOLD_PPM_PRED_ID,
            "owner_type": "aml_review_form",
            "arity": 3,
            "arg_specs": [
                {"name": "account_ref", "type_domain": "entity_ref"},
                {"name": "score_threshold_ppm", "type_domain": "int"},
                {"name": "document_ref", "type_domain": "entity_ref"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0, 1, 2],
        },
    ]
    existing = {pred.get("pred_id") for pred in predicates if isinstance(pred, dict)}
    for predicate in form_predicates:
        pred_id = predicate["pred_id"]
        if pred_id not in existing:
            predicates.append(predicate)
            existing.add(pred_id)
        if pred_id not in projection_predicates:
            projection_predicates.append(pred_id)
    return schema_ir
