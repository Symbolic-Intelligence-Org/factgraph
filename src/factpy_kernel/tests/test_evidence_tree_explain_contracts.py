from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import factpy_kernel.adapters.souffle as souffle_adapter
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


class EvidenceTreeExplainContractsTests(unittest.TestCase):
    def test_recursive_candidate_evidence_tree_round_trips_through_audit_and_static(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "tag") as (u, tag):
            helper_rule = Rule(
                id="q.user_tag_rows",
                version="1.0.0",
                select=[u, tag],
                where=[Pred("user:tag", u, tag)],
                expose=True,
            )

        compiled_rule = sdk._compile_rule_input(helper_rule)

        with TemporaryDirectory() as tmp_dir:
            registry = FileAuthoringRegistry(Path(tmp_dir))
            registry.upsert_schema_ir(sdk.schema_ir)
            registry.register_rule_spec(compiled_rule)

            reset_runtime_sessions_for_tests()
            open_resp = open_runtime_session({"registry_root": tmp_dir})
            self.assertTrue(open_resp["ok"])
            session_id = open_resp["session"]["session_id"]
            try:
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": "user:tag",
                        "e_ref": refs["u1"],
                        "rest_terms": [["string", "vip"]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

                eval_resp = evaluate_runtime_derivation(
                    session_id,
                    {
                        "derivation": {
                            "derivation_id": "drv.runtime.user_tag_tree",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [
                                ["ruleref", "q.user_tag_rows", "1.0.0", ["$u", "$tag"]],
                                ["eq", "$tag", "vip"],
                            ],
                            "mode": "native",
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                candidate_id = eval_resp["evaluation"]["candidates"][0]["candidate_id"]

                runtime_tree_resp = explain_runtime_tree(session_id, {"kind": "candidate", "id": candidate_id})
                self.assertTrue(runtime_tree_resp["ok"])
                runtime_rule_ref_node = runtime_tree_resp["tree"]["root"]["children"][1]["children"][0]
                self.assertEqual(runtime_rule_ref_node["children"][0]["node_kind"], "referenced_support")

                package_dir = str(Path(tmp_dir) / "audit_package")
                accept_resp = accept_runtime_derivation(
                    session_id,
                    {
                        "candidate": eval_resp["evaluation"]["candidates"][0],
                        "options": {"approved_by": "alice"},
                    },
                )
                self.assertTrue(accept_resp["ok"])
                export_resp = export_runtime_package(
                    session_id,
                    {"out_dir": package_dir, "package_kind": "audit"},
                )
                self.assertTrue(export_resp["ok"])
                package = load_audit_package(package_dir)
                audit_query = AuditQuery(package)

                audit_tree = audit_query.get_candidate_evidence_tree(candidate_id)
                assert audit_tree is not None
                audit_rule_ref_node = audit_tree["root"]["children"][1]["children"][0]
                self.assertEqual(audit_rule_ref_node["node_kind"], "rule_ref")
                self.assertEqual(audit_rule_ref_node["children"][0]["node_kind"], "referenced_support")

                site_dir = str(Path(tmp_dir) / "site")
                render_audit_static_site(package_dir, site_dir)
                html = (
                    Path(site_dir)
                    / "candidate_evidence"
                    / f"{_slug_id(candidate_id)}.html"
                ).read_text(encoding="utf-8")
                self.assertIn("Child Proof", html)
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_runtime_service_explain_support_and_rule_trace(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)
        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            write_resp = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag",
                    "e_ref": refs["u1"],
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])

            eval_resp = evaluate_runtime_derivation(
                session_id,
                {
                    "derivation": {
                        "derivation_id": "drv.tag_copy",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [["pred", "user:tag", ["$u", "$tag"]]],
                        "mode": "native",
                    }
                },
            )
            self.assertTrue(eval_resp["ok"])
            candidate = eval_resp["evaluation"]["candidates"][0]
            self.assertEqual(candidate["support_kind"], "native_binding_v1")
            self.assertEqual(candidate["confidence_kind"], "none")

            legacy_candidate = dict(candidate)
            legacy_candidate.pop("confidence_kind")
            accept_resp = accept_runtime_derivation(
                session_id,
                {
                    "candidate": legacy_candidate,
                    "options": {"approved_by": "alice"},
                },
            )
            self.assertTrue(accept_resp["ok"])
            written_asrt_id = accept_resp["accept"]["written_assertions"][0]["asrt_id"]
            meta_rows = {
                (row.key, row.kind, row.value)
                for row in _require_session(session_id).store.ledger.find_meta(asrt_id=written_asrt_id)
            }
            self.assertIn(("confidence_kind", "str", "none"), meta_rows)

            explain_support_resp = explain_runtime_support(
                session_id,
                {"support_digest": candidate["support_digest"]},
            )
            self.assertTrue(explain_support_resp["ok"])
            self.assertNotIn("kind", explain_support_resp)
            self.assertEqual(explain_support_resp["meta"]["support_digest"], candidate["support_digest"])
            self.assertEqual(explain_support_resp["explain"]["kind"], "native_binding_v1")

            missing_support_resp = explain_runtime_support(session_id, {"support_digest": "sha256:missing"})
            self.assertFalse(missing_support_resp["ok"])
            self.assertEqual(missing_support_resp["errors"][0]["kind"], "runtime_explain_not_found")
            self.assertEqual(missing_support_resp["errors"][0]["path"], "$.support_digest")

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.runtime_tag_rows",
                        "version": "1.0.0",
                        "select": ["$u", "$tag"],
                        "where": [["pred", "user:tag", ["$u", "$tag"]]],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            self.assertIn("trace", rule_resp["result"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]
            self.assertTrue(rule_run_id)

            explain_rule_resp = explain_runtime_rule_trace(session_id, {"rule_run_id": rule_run_id})
            self.assertTrue(explain_rule_resp["ok"])
            self.assertNotIn("kind", explain_rule_resp)
            self.assertEqual(explain_rule_resp["meta"]["rule_run_id"], rule_run_id)
            self.assertEqual(explain_rule_resp["explain"]["root_rule"]["rule_id"], "q.runtime_tag_rows")

            missing_rule_trace_resp = explain_runtime_rule_trace(session_id, {"rule_run_id": "missing-rule-run"})
            self.assertFalse(missing_rule_trace_resp["ok"])
            self.assertEqual(missing_rule_trace_resp["errors"][0]["kind"], "runtime_explain_not_found")
            self.assertEqual(missing_rule_trace_resp["errors"][0]["path"], "$.rule_run_id")
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_runtime_explain_ref_candidate_assertion_and_rule_run(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        first_open = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(first_open["ok"])
        first_session_id = first_open["session"]["session_id"]
        candidate_id = ""
        try:
            write_resp = write_runtime_fact(
                first_session_id,
                {
                    "pred_id": "user:tag",
                    "e_ref": refs["u1"],
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])
            active_asrt_id = write_resp["write"]["assertion_id"]

            eval_resp = evaluate_runtime_derivation(
                first_session_id,
                {
                    "derivation": {
                        "derivation_id": "drv.tag_copy.unified",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [["pred", "user:tag", ["$u", "$tag"]]],
                        "mode": "native",
                    }
                },
            )
            self.assertTrue(eval_resp["ok"])
            candidate = eval_resp["evaluation"]["candidates"][0]
            candidate_id = candidate["candidate_id"]

            explain_candidate_resp = explain_runtime_ref(
                first_session_id,
                {"kind": "candidate", "id": candidate_id},
            )
            self.assertTrue(explain_candidate_resp["ok"])
            self.assertEqual(explain_candidate_resp["kind"], "candidate")
            self.assertEqual(explain_candidate_resp["meta"]["candidate_id"], candidate_id)
            self.assertEqual(explain_candidate_resp["explain"]["candidate_id"], candidate_id)
            self.assertEqual(explain_candidate_resp["explain"]["support_digest"], candidate["support_digest"])
            self.assertEqual(explain_candidate_resp["explain"]["support"]["kind"], "native_binding_v1")
            self.assertNotIn("witness_status", explain_candidate_resp["explain"])

            explain_assertion_active = explain_runtime_ref(
                first_session_id,
                {"kind": "assertion", "id": active_asrt_id},
            )
            self.assertTrue(explain_assertion_active["ok"])
            self.assertEqual(explain_assertion_active["kind"], "assertion")
            self.assertEqual(explain_assertion_active["meta"]["asrt_id"], active_asrt_id)
            self.assertEqual(explain_assertion_active["explain"]["asrt_id"], active_asrt_id)
            self.assertEqual(explain_assertion_active["explain"]["pred_id"], "user:tag")
            self.assertEqual(explain_assertion_active["explain"]["e_ref"], refs["u1"])
            self.assertTrue(explain_assertion_active["explain"]["is_active"])
            self.assertNotIn("revoker_asrt_id", explain_assertion_active["explain"])

            retract_resp = retract_runtime_fact(first_session_id, {"asrt_id": active_asrt_id})
            self.assertTrue(retract_resp["ok"])
            revoker_asrt_id = retract_resp["write"]["assertion_id"]

            explain_assertion_revoked = explain_runtime_ref(
                first_session_id,
                {"kind": "assertion", "id": active_asrt_id},
            )
            self.assertTrue(explain_assertion_revoked["ok"])
            self.assertFalse(explain_assertion_revoked["explain"]["is_active"])
            self.assertEqual(explain_assertion_revoked["explain"]["revoker_asrt_id"], revoker_asrt_id)

            missing_assertion_resp = explain_runtime_ref(
                first_session_id,
                {"kind": "assertion", "id": "missing-assertion"},
            )
            self.assertFalse(missing_assertion_resp["ok"])
            self.assertEqual(missing_assertion_resp["errors"][0]["kind"], "runtime_explain_not_found")
            self.assertEqual(missing_assertion_resp["errors"][0]["path"], "$.id")

            rule_resp = run_runtime_rule(
                first_session_id,
                {
                    "rule": {
                        "rule_id": "q.runtime_unified_rows",
                        "version": "1.0.0",
                        "select": ["$u", "$tag"],
                        "where": [["pred", "user:tag", ["$u", "$tag"]]],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            explain_rule_resp = explain_runtime_ref(
                first_session_id,
                {"kind": "rule_run", "id": rule_run_id},
            )
            self.assertTrue(explain_rule_resp["ok"])
            self.assertEqual(explain_rule_resp["kind"], "rule_run")
            self.assertEqual(explain_rule_resp["meta"]["rule_run_id"], rule_run_id)
            self.assertEqual(explain_rule_resp["explain"]["root_rule"]["rule_id"], "q.runtime_unified_rows")

            missing_rule_resp = explain_runtime_ref(
                first_session_id,
                {"kind": "rule_run", "id": "missing-rule-run"},
            )
            self.assertFalse(missing_rule_resp["ok"])
            self.assertEqual(missing_rule_resp["errors"][0]["kind"], "runtime_explain_not_found")
            self.assertEqual(missing_rule_resp["errors"][0]["path"], "$.id")
        finally:
            close_runtime_session(first_session_id)

        second_open = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(second_open["ok"])
        second_session_id = second_open["session"]["session_id"]
        try:
            missing_candidate_resp = explain_runtime_ref(
                second_session_id,
                {"kind": "candidate", "id": candidate_id},
            )
            self.assertFalse(missing_candidate_resp["ok"])
            self.assertEqual(missing_candidate_resp["errors"][0]["kind"], "runtime_explain_not_found")
            self.assertEqual(missing_candidate_resp["errors"][0]["path"], "$.id")
        finally:
            close_runtime_session(second_session_id)
            reset_runtime_sessions_for_tests()

    def test_native_candidate_evidence_tree_runtime_audit_and_static(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            write_resp = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag",
                    "e_ref": refs["u1"],
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])
            asrt_id = write_resp["write"]["assertion_id"]

            eval_resp = evaluate_runtime_derivation(
                session_id,
                {
                    "derivation": {
                        "derivation_id": "drv.tag_copy.evidence_tree",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [["pred", "user:tag", ["$u", "$tag"]]],
                        "mode": "native",
                    }
                },
            )
            self.assertTrue(eval_resp["ok"])
            candidate = eval_resp["evaluation"]["candidates"][0]
            candidate_id = candidate["candidate_id"]

            explain_candidate_resp = explain_runtime_ref(session_id, {"kind": "candidate", "id": candidate_id})
            self.assertTrue(explain_candidate_resp["ok"])
            self.assertNotIn("tree", explain_candidate_resp)

            tree_resp = explain_runtime_tree(session_id, {"kind": "candidate", "id": candidate_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "candidate", "id": candidate_id})
            narrative_resp = explain_runtime_narrative(session_id, {"kind": "candidate", "id": candidate_id})
            nl_resp = explain_runtime_nl(session_id, {"kind": "candidate", "id": candidate_id})
            self.assertTrue(tree_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertTrue(narrative_resp["ok"])
            self.assertTrue(nl_resp["ok"])
            self.assertEqual(tree_resp["kind"], "candidate_evidence_tree")
            self.assertEqual(tree_resp["meta"]["candidate_id"], candidate_id)
            tree = tree_resp["tree"]
            self.assertEqual(tree["candidate_id"], candidate_id)
            self.assertEqual(tree["support_digest"], candidate["support_digest"])
            self.assertEqual(tree["support_kind"], "native_binding_v1")
            runtime_summary = summary_resp["summary"]
            runtime_narrative = narrative_resp["narrative"]
            runtime_nl = nl_resp["explain_nl"]
            self.assertEqual(summary_resp["kind"], "candidate_evidence_tree_summary")
            self.assertEqual(narrative_resp["kind"], "candidate_evidence_tree_narrative")
            self.assertEqual(nl_resp["kind"], "candidate_evidence_tree_nl_explain")
            self.assertEqual(runtime_summary, summarize_candidate_evidence_tree_dict(tree))
            self.assertEqual(runtime_narrative, render_candidate_evidence_tree_narrative(runtime_summary, locale="en"))
            self.assertEqual(
                runtime_nl,
                render_candidate_evidence_tree_nl_explain(runtime_summary, runtime_narrative, locale="en"),
            )
            self.assertEqual(tree["root"]["node_kind"], "candidate_result")
            self.assertEqual(
                [row.get("node_kind") for row in tree["root"]["children"]],
                ["support_section"],
            )
            support_section = tree["root"]["children"][0]
            pred_nodes = [
                row for row in support_section["children"] if row.get("node_kind") == "predicate_witness_group"
            ]
            self.assertEqual(len(pred_nodes), 1)
            self.assertEqual(pred_nodes[0]["pred_id"], "user:tag")
            self.assertEqual(pred_nodes[0]["assertion_count"], 1)
            leaf = pred_nodes[0]["children"][0]
            self.assertEqual(
                set(leaf.keys()),
                {"node_id", "node_kind", "title", "asrt_id", "pred_id", "e_ref", "claim_args", "children"},
            )
            self.assertEqual(leaf["asrt_id"], asrt_id)
            self.assertEqual(leaf["pred_id"], "user:tag")
            self.assertEqual(leaf["e_ref"], refs["u1"])
            self.assertNotIn("meta", leaf)
            self.assertNotIn("revoked_by", leaf)
            self.assertNotIn("revokes", leaf)
            self.assertNotIn("is_revoked", leaf)

            accept_resp = accept_runtime_derivation(
                session_id,
                {
                    "candidate": candidate,
                    "options": {
                        "approved_by": "alice",
                    },
                },
            )
            self.assertTrue(accept_resp["ok"])
            self.assertEqual(accept_resp["accept"]["candidate_id"], candidate_id)

            with TemporaryDirectory() as tmp_dir:
                package_dir = str(Path(tmp_dir) / "pkg")
                export_resp = export_runtime_package(
                    session_id,
                    {
                        "out_dir": package_dir,
                        "package_kind": "audit",
                    },
                )
                self.assertTrue(export_resp["ok"])

                package = load_audit_package(package_dir)
                self.assertTrue(package.support_artifacts)
                query = AuditQuery(package)
                audit_tree = query.get_candidate_evidence_tree(candidate_id)
                self.assertEqual(audit_tree, tree)
                dto_tree = build_candidate_evidence_tree_dto(query, candidate_id)
                self.assertEqual(dto_tree, tree)
                audit_summary = query.get_candidate_evidence_tree_summary(candidate_id)
                audit_narrative = query.get_candidate_evidence_tree_narrative(candidate_id)
                self.assertEqual(audit_summary, runtime_summary)
                self.assertEqual(audit_narrative, runtime_narrative)
                summary_dto = build_candidate_evidence_tree_summary_dto(query, candidate_id)
                narrative_dto = build_candidate_evidence_tree_narrative_dto(query, candidate_id)
                self.assertEqual(summary_dto["kind"], "candidate_evidence_tree_summary")
                self.assertEqual(summary_dto["candidate_id"], candidate_id)
                self.assertEqual(summary_dto["summary"], runtime_summary)
                self.assertEqual(narrative_dto["kind"], "candidate_evidence_tree_narrative")
                self.assertEqual(narrative_dto["candidate_id"], candidate_id)
                self.assertEqual(narrative_dto["narrative"], runtime_narrative)

                site_dir = str(Path(tmp_dir) / "site")
                site_manifest = render_audit_static_site(package_dir, site_dir)
                self.assertIn("candidate_evidence_index", site_manifest)
                self.assertIn(
                    f"candidate_evidence/{_slug_id(candidate_id)}.html",
                    site_manifest["candidate_evidence"],
                )
                page_path = Path(site_dir) / "candidate_evidence" / f"{_slug_id(candidate_id)}.html"
                self.assertTrue(page_path.exists())
                html = page_path.read_text(encoding="utf-8")
                self.assertIn(candidate_id, html)
                self.assertIn(f"assertions/{_slug_id(asrt_id)}.html", html)
                self.assertIn("Evidence Tree", html)
                self.assertIn("Analysis Summary", html)
                self.assertIn(runtime_narrative["headline"], html)
                self.assertNotIn("revoked_by", html)
                self.assertNotIn("is_revoked", html)
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_native_candidate_evidence_tree_v2_emits_rule_ref_section_only_when_present(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            write_resp = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag",
                    "e_ref": refs["u1"],
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])
            asrt_id = write_resp["write"]["assertion_id"]

            session = _require_session(session_id)
            support_digest = "sha256:" + ("ab" * 32)
            artifact = support_artifact_from_dict(
                {
                    "support_digest": support_digest,
                    "kind": "native_binding_v1",
                    "root_result_kind": "entity",
                    "binding": [["$u", refs["u1"]]],
                    "pred_witnesses": [
                        {
                            "pred_atom_key": "b0.a0:user:tag",
                            "asrt_ids": [asrt_id],
                        }
                    ],
                    "non_fact_steps": [],
                    "rule_refs": ["q.child_rule_a", "q.child_rule_b"],
                }
            )
            session.store._remember_support_artifact(support_digest, artifact)
            session.store._remember_candidate_support("cand-with-rule-refs", support_digest, "native_binding_v1")

            tree_resp = explain_runtime_tree(session_id, {"kind": "candidate", "id": "cand-with-rule-refs"})
            self.assertTrue(tree_resp["ok"])
            tree = tree_resp["tree"]
            self.assertEqual(
                [row.get("node_kind") for row in tree["root"]["children"]],
                ["support_section", "rule_ref_section"],
            )
            support_section, rule_ref_section = tree["root"]["children"]
            self.assertEqual(support_section["title"], "Support")
            self.assertEqual(rule_ref_section["title"], "Rule References")
            self.assertEqual(
                [row.get("node_kind") for row in rule_ref_section["children"]],
                ["rule_ref", "rule_ref"],
            )
            self.assertEqual(
                [row.get("rule_ref_id") for row in rule_ref_section["children"]],
                ["q.child_rule_a", "q.child_rule_b"],
            )
            self.assertEqual(rule_ref_section["children"][0]["children"], [])
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_runtime_rule_run_explain_ref_is_canonical_and_locks_stable_shape(self) -> None:
        schema_ir = extend_schema_ir_with_ecss_temporal_predicates(_schema_ir())
        sdk = SDKStore([User], schema_ir=schema_ir)
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            for pred_id, time_value in (
                (ECSS_OBLIGATION_TIMESTAMP_PRED_ID, 100),
                (ECSS_WINDOW_START_PRED_ID, 80),
            ):
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": pred_id,
                        "e_ref": refs["u1"],
                        "rest_terms": [["time", time_value]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.runtime_rule_run_contract",
                        "version": "1.0.0",
                        "select": ["$a", "$window_start_ts", "$event_ts"],
                        "where": [
                            ["pred", ECSS_OBLIGATION_TIMESTAMP_PRED_ID, ["$a", "$event_ts"]],
                            ["pred", ECSS_WINDOW_START_PRED_ID, ["$a", "$window_start_ts"]],
                            ["le", "$window_start_ts", "$event_ts"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            legacy_resp = explain_runtime_rule_trace(session_id, {"rule_run_id": rule_run_id})
            canonical_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})

            self.assertTrue(legacy_resp["ok"])
            self.assertTrue(canonical_resp["ok"])
            self.assertNotIn("kind", legacy_resp)
            self.assertEqual(canonical_resp["kind"], "rule_run")
            self.assertEqual(legacy_resp["meta"]["rule_run_id"], rule_run_id)
            self.assertEqual(canonical_resp["meta"]["rule_run_id"], rule_run_id)
            self.assertEqual(canonical_resp["explain"], legacy_resp["explain"])

            explain = canonical_resp["explain"]
            self.assertEqual(explain["rule_run_id"], rule_run_id)
            self.assertEqual(
                explain["root_rule"],
                {"rule_id": "q.runtime_rule_run_contract", "version": "1.0.0"},
            )
            self.assertEqual(explain["select_vars"], ["$a", "$window_start_ts", "$event_ts"])
            self.assertEqual(explain["root_rows"], [[refs["u1"], 80, 100]])
            self.assertIsInstance(explain["invocations"], list)
            self.assertNotIn("kind", explain)

            invocation = next(
                inv
                for inv in explain["invocations"]
                if inv["rule"]["rule_id"] == "q.runtime_rule_run_contract"
            )
            self.assertTrue(
                {
                    "invocation_id",
                    "parent_invocation_id",
                    "rule",
                    "memo_hit",
                    "memo_source_invocation_id",
                    "original_where",
                    "rewritten_where",
                    "bindings",
                    "output_rows",
                    "pred_witnesses",
                    "non_fact_steps",
                    "ruleref_links",
                }.issubset(invocation.keys())
            )
            self.assertNotIn("child_invocations", invocation)
            self.assertIsInstance(invocation["original_where"], list)
            self.assertIsInstance(invocation["rewritten_where"], list)
            self.assertIsNone(invocation["parent_invocation_id"])
            self.assertIsInstance(invocation["ruleref_links"], list)
            self.assertEqual(invocation["ruleref_links"], [])

            self.assertEqual(len(invocation["pred_witnesses"]), 2)
            witness_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                witness_keys,
                {"b0.a0:ecss:obligation_timestamp", "b0.a1:ecss:window_start"},
            )

            self.assertEqual(len(invocation["non_fact_steps"]), 1)
            step = invocation["non_fact_steps"][0]
            self.assertTrue(
                {"binding_index", "step_key", "kind", "status", "details"}.issubset(step.keys())
            )
            self.assertEqual(step["kind"], "le")
            details = dict(step["details"])
            self.assertIn("binding", details)
            self.assertIn("atom", details)
            self.assertIsInstance(details["atom"], list)
            binding = dict(details["binding"])
            self.assertEqual(binding["$window_start_ts"], 80)
            self.assertEqual(binding["$event_ts"], 100)
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_runtime_rule_run_explain_summary_is_pure_derivation_from_raw_payload(self) -> None:
        schema_ir = extend_schema_ir_with_ecss_temporal_predicates(_schema_ir())
        sdk = SDKStore([User], schema_ir=schema_ir)
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            for pred_id, time_value in (
                (ECSS_OBLIGATION_TIMESTAMP_PRED_ID, 100),
                (ECSS_WINDOW_START_PRED_ID, 80),
            ):
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": pred_id,
                        "e_ref": refs["u1"],
                        "rest_terms": [["time", time_value]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.runtime_rule_run_summary",
                        "version": "1.0.0",
                        "select": ["$a", "$window_start_ts", "$event_ts"],
                        "where": [
                            ["pred", ECSS_OBLIGATION_TIMESTAMP_PRED_ID, ["$a", "$event_ts"]],
                            ["pred", ECSS_WINDOW_START_PRED_ID, ["$a", "$window_start_ts"]],
                            ["le", "$window_start_ts", "$event_ts"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})

            self.assertTrue(raw_resp["ok"])
            self.assertTrue(summary_resp["ok"])
            self.assertEqual(summary_resp["kind"], "rule_run_summary")
            self.assertEqual(summary_resp["meta"]["rule_run_id"], rule_run_id)

            raw = raw_resp["explain"]
            summary = summary_resp["summary"]
            self.assertEqual(
                sorted(summary.keys()),
                [
                    "invocation_count",
                    "non_fact_step_groups",
                    "predicate_witness_groups",
                    "root_row_count",
                    "root_rule",
                    "rule_run_id",
                    "witness_assertion_ids",
                ],
            )
            self.assertEqual(summary["rule_run_id"], raw["rule_run_id"])
            self.assertEqual(summary["root_rule"], raw["root_rule"])
            self.assertEqual(summary["root_row_count"], len(raw["root_rows"]))
            self.assertEqual(summary["invocation_count"], len(raw["invocations"]))
            self.assertNotIn("raw_ref", summary)
            self.assertNotIn("assertion_refs", summary)

            expected_witness_assertion_ids = sorted(
                {
                    asrt_id
                    for invocation in raw["invocations"]
                    for witness in invocation["pred_witnesses"]
                    for asrt_id in witness["asrt_ids"]
                }
            )
            self.assertEqual(summary["witness_assertion_ids"], expected_witness_assertion_ids)

            expected_predicate_group_map: dict[str, dict[str, set[str]]] = {}
            for invocation in raw["invocations"]:
                invocation_id = invocation["invocation_id"]
                for witness in invocation["pred_witnesses"]:
                    pred_id = witness["pred_atom_key"].split(":", 1)[1]
                    group = expected_predicate_group_map.setdefault(
                        pred_id,
                        {"asrt_ids": set(), "invocation_ids": set()},
                    )
                    group["invocation_ids"].add(invocation_id)
                    group["asrt_ids"].update(witness["asrt_ids"])
            expected_predicate_groups = [
                {
                    "pred_id": pred_id,
                    "asrt_ids": sorted(group["asrt_ids"]),
                    "invocation_ids": sorted(group["invocation_ids"]),
                }
                for pred_id, group in sorted(expected_predicate_group_map.items())
            ]
            self.assertEqual(
                summary["predicate_witness_groups"],
                expected_predicate_groups,
            )
            self.assertEqual(
                summary["non_fact_step_groups"],
                [
                    {
                        "kind": "le",
                        "count": 1,
                        "invocation_ids": [raw["invocations"][0]["invocation_id"]],
                    }
                ],
            )
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_audit_rule_trace_summary_matches_runtime_summary_contract(self) -> None:
        schema_ir = extend_schema_ir_with_ecss_temporal_predicates(_schema_ir())
        sdk = SDKStore([User], schema_ir=schema_ir)
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            for pred_id, time_value in (
                (ECSS_OBLIGATION_TIMESTAMP_PRED_ID, 100),
                (ECSS_WINDOW_START_PRED_ID, 80),
            ):
                write_resp = write_runtime_fact(
                    session_id,
                    {
                        "pred_id": pred_id,
                        "e_ref": refs["u1"],
                        "rest_terms": [["time", time_value]],
                    },
                    kind="add",
                )
                self.assertTrue(write_resp["ok"])

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.audit_rule_run_summary_export",
                        "version": "1.0.0",
                        "select": ["$a", "$window_start_ts", "$event_ts"],
                        "where": [
                            ["pred", ECSS_OBLIGATION_TIMESTAMP_PRED_ID, ["$a", "$event_ts"]],
                            ["pred", ECSS_WINDOW_START_PRED_ID, ["$a", "$window_start_ts"]],
                            ["le", "$window_start_ts", "$event_ts"],
                        ],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            raw_resp = explain_runtime_ref(session_id, {"kind": "rule_run", "id": rule_run_id})
            runtime_summary_resp = explain_runtime_summary(session_id, {"kind": "rule_run", "id": rule_run_id})
            runtime_narrative_resp = explain_runtime_narrative(session_id, {"kind": "rule_run", "id": rule_run_id})
            runtime_nl_resp = explain_runtime_nl(session_id, {"kind": "rule_run", "id": rule_run_id})
            self.assertTrue(raw_resp["ok"])
            self.assertTrue(runtime_summary_resp["ok"])
            self.assertTrue(runtime_narrative_resp["ok"])
            self.assertTrue(runtime_nl_resp["ok"])

            raw_explain = raw_resp["explain"]
            runtime_summary = runtime_summary_resp["summary"]
            runtime_narrative = runtime_narrative_resp["narrative"]
            runtime_nl = runtime_nl_resp["explain_nl"]
            self.assertEqual(runtime_summary, summarize_rule_trace_artifact_dict(raw_explain))
            self.assertEqual(runtime_narrative, render_rule_run_narrative(runtime_summary, locale="en"))
            self.assertEqual(runtime_nl, render_rule_run_nl_explain(runtime_summary, runtime_narrative, locale="en"))

            with TemporaryDirectory() as package_dir:
                session = _require_session(session_id)
                export_package(session.store, Path(package_dir), ExportOptions(package_kind="audit"))

                package = load_audit_package(package_dir)
                query = AuditQuery(package)

                audit_summary = query.get_rule_trace_summary(rule_run_id)
                self.assertIsNotNone(audit_summary)
                assert audit_summary is not None
                self.assertEqual(audit_summary, runtime_summary)
                self.assertEqual(
                    query.list_rule_trace_summaries(root_rule_id="q.audit_rule_run_summary_export"),
                    [runtime_summary],
                )

                audit_narrative = query.get_rule_trace_narrative(rule_run_id)
                self.assertIsNotNone(audit_narrative)
                assert audit_narrative is not None
                self.assertEqual(audit_narrative, runtime_narrative)

                summary_dto = build_rule_trace_summary_dto(query, rule_run_id)
                self.assertEqual(summary_dto["kind"], "rule_run_summary")
                self.assertEqual(summary_dto["summary"], runtime_summary)

                narrative_dto = build_rule_trace_narrative_dto(query, rule_run_id)
                self.assertEqual(narrative_dto["kind"], "rule_run_narrative")
                self.assertEqual(narrative_dto["rule_run_id"], rule_run_id)
                self.assertEqual(narrative_dto["narrative"], runtime_narrative)

                summary_list_dto = build_rule_trace_summary_list_dto(
                    query,
                    root_rule_id="q.audit_rule_run_summary_export",
                )
                self.assertEqual(summary_list_dto["kind"], "rule_run_summary_list")
                self.assertEqual(summary_list_dto["count"], 1)
                self.assertEqual(summary_list_dto["rule_run_summaries"], [runtime_summary])
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_rule_run_narrative_is_deterministic_from_summary(self) -> None:
        summary = {
            "rule_run_id": "rt_123",
            "root_rule": {"rule_id": "q.foo", "version": "1.0.0"},
            "root_row_count": 1,
            "invocation_count": 3,
            "witness_assertion_ids": ["A1", "A2"],
            "predicate_witness_groups": [
                {"pred_id": "ecss:window_start", "asrt_ids": ["A1"], "invocation_ids": ["rt_123:i1"]},
                {"pred_id": "ecss:obligation_timestamp", "asrt_ids": ["A2"], "invocation_ids": ["rt_123:i1", "rt_123:i2"]},
            ],
            "non_fact_step_groups": [
                {"kind": "ge", "count": 1, "invocation_ids": ["rt_123:i1"]},
                {"kind": "le", "count": 2, "invocation_ids": ["rt_123:i1", "rt_123:i2"]},
            ],
        }

        narrative = render_rule_run_narrative(summary, locale="en")
        self.assertEqual(
            narrative,
            {
                "headline": "Rule q.foo@1.0.0 produced 1 root row(s) across 3 invocation(s).",
                "overview_lines": [
                    "Witness assertions: 2 unique assertion(s).",
                    "Predicate witness groups: 2.",
                    "Non-fact check groups: 2.",
                ],
                "predicate_lines": [
                    "Predicate ecss:obligation_timestamp was witnessed by 1 assertion(s) across 2 invocation(s).",
                    "Predicate ecss:window_start was witnessed by 1 assertion(s) across 1 invocation(s).",
                ],
                "non_fact_check_lines": [
                    "Check kind ge was evaluated 1 time(s) across 1 invocation(s).",
                    "Check kind le was evaluated 2 time(s) across 2 invocation(s).",
                ],
                "drilldown_lines": [
                    "Open the linked assertion detail page(s) for 2 witness assertion(s) to inspect supporting facts.",
                    "Continue below for invocation-level detail and the full raw trace payload.",
                ],
            },
        )

    def test_rule_run_nl_explain_is_deterministic_from_summary_and_narrative(self) -> None:
        summary = {
            "rule_run_id": "rt_123",
            "root_rule": {"rule_id": "q.foo", "version": "1.0.0"},
            "root_row_count": 1,
            "invocation_count": 3,
            "witness_assertion_ids": ["A1", "A2"],
            "predicate_witness_groups": [
                {"pred_id": "ecss:window_start", "asrt_ids": ["A1"], "invocation_ids": ["rt_123:i1"]},
                {"pred_id": "ecss:obligation_timestamp", "asrt_ids": ["A2"], "invocation_ids": ["rt_123:i1", "rt_123:i2"]},
            ],
            "non_fact_step_groups": [
                {"kind": "ge", "count": 1, "invocation_ids": ["rt_123:i1"]},
                {"kind": "le", "count": 2, "invocation_ids": ["rt_123:i1", "rt_123:i2"]},
            ],
        }
        narrative = render_rule_run_narrative(summary, locale="en")

        explain_nl = render_rule_run_nl_explain(summary, narrative, locale="en")
        self.assertEqual(
            explain_nl,
            {
                "headline": "Rule q.foo@1.0.0 matched 1 root row(s) across 3 invocation(s).",
                "paragraphs": [
                    "Rule q.foo@1.0.0 produced 1 root row(s) across 3 invocation(s). This run identified 2 unique witness assertion(s), 2 predicate witness group(s), and 2 non-fact check group(s). Witness assertions: 2 unique assertion(s). Predicate witness groups: 2. Non-fact check groups: 2.",
                    "Evidence summary: Predicate ecss:obligation_timestamp was witnessed by 1 assertion(s) across 2 invocation(s). Predicate ecss:window_start was witnessed by 1 assertion(s) across 1 invocation(s).",
                    "Check summary: Check kind ge was evaluated 1 time(s) across 1 invocation(s). Check kind le was evaluated 2 time(s) across 2 invocation(s).",
                    "Drill-down guidance: Open the linked assertion detail page(s) for 2 witness assertion(s) to inspect supporting facts. Continue below for invocation-level detail and the full raw trace payload.",
                ],
            },
        )

    def test_candidate_evidence_tree_summary_narrative_and_nl_are_deterministic_for_native_tree(self) -> None:
        tree = {
            "kind": "candidate_evidence_tree",
            "candidate_id": "cand-native",
            "support_digest": "sha256:native",
            "support_kind": "native_binding_v1",
            "root": {
                "node_id": "cand:cand-native",
                "node_kind": "candidate_result",
                "title": "Candidate cand-native",
                "root_result_kind": "fact",
                "binding": {"$u": "user:1"},
                "rule_refs": ["q.child.unresolved", "q.child.recursive", "q.child.boundary"],
                "rule_ref_edges": [],
                "children": [
                    {
                        "node_id": "support:cand-native",
                        "node_kind": "support_section",
                        "title": "Support",
                        "children": [
                            {
                                "node_id": "atom:b0.a0:user:tag",
                                "node_kind": "predicate_witness_group",
                                "title": "Predicate witness user:tag",
                                "pred_atom_key": "b0.a0:user:tag",
                                "pred_id": "user:tag",
                                "assertion_count": 1,
                                "children": [
                                    {
                                        "node_id": "asrt:A1",
                                        "node_kind": "assertion_fact",
                                        "title": "Assertion A1",
                                        "asrt_id": "A1",
                                        "pred_id": "user:tag",
                                        "e_ref": "user:1",
                                        "claim_args": [],
                                        "children": [],
                                    }
                                ],
                            },
                            {
                                "node_id": "step:b0.a1:eq",
                                "node_kind": "non_fact_check",
                                "title": "Non-fact check b0.a1:eq",
                                "step_key": "b0.a1:eq",
                                "check_kind": "eq",
                                "status": "satisfied",
                                "details": {"lhs": "$tag", "rhs": "vip"},
                                "children": [],
                            },
                        ],
                    },
                    {
                        "node_id": "rule_refs:cand-native",
                        "node_kind": "rule_ref_section",
                        "title": "Rule References",
                        "children": [
                            {
                                "node_id": "ruleref:b0.a2:ruleref",
                                "node_kind": "rule_ref",
                                "title": "Rule reference q.child.recursive",
                                "ruleref_atom_key": "b0.a2:ruleref",
                                "rule_ref_id": "q.child.recursive",
                                "rule_ref_version": "1.0.0",
                                "child_support_digest": "sha256:child1",
                                "unresolved_reason": None,
                                "children": [
                                    {
                                        "node_id": "referenced_support:sha256:child1",
                                        "node_kind": "referenced_support",
                                        "title": "Referenced support sha256:child1",
                                        "support_digest": "sha256:child1",
                                        "root_result_kind": "row",
                                        "binding": {"$u": "user:1"},
                                        "rule_refs": [],
                                        "rule_ref_edges": [],
                                        "children": [
                                            {
                                                "node_id": "support:sha256:child1",
                                                "node_kind": "support_section",
                                                "title": "Support",
                                                "children": [
                                                    {
                                                        "node_id": "atom:b0.a0:user:status",
                                                        "node_kind": "predicate_witness_group",
                                                        "title": "Predicate witness user:status",
                                                        "pred_atom_key": "b0.a0:user:status",
                                                        "pred_id": "user:status",
                                                        "assertion_count": 1,
                                                        "children": [
                                                            {
                                                                "node_id": "asrt:A2",
                                                                "node_kind": "assertion_fact",
                                                                "title": "Assertion A2",
                                                                "asrt_id": "A2",
                                                                "pred_id": "user:status",
                                                                "e_ref": "user:1",
                                                                "claim_args": [],
                                                                "children": [],
                                                            }
                                                        ],
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            },
                            {
                                "node_id": "ruleref:b0.a3:ruleref",
                                "node_kind": "rule_ref",
                                "title": "Rule reference q.child.unresolved",
                                "ruleref_atom_key": "b0.a3:ruleref",
                                "rule_ref_id": "q.child.unresolved",
                                "rule_ref_version": "1.0.0",
                                "child_support_digest": None,
                                "unresolved_reason": "child_support_unavailable",
                                "children": [
                                    {
                                        "node_id": "unresolved:b0.a3:ruleref",
                                        "node_kind": "unresolved_support",
                                        "title": "Unresolved support",
                                        "reason": "child_support_unavailable",
                                        "child_support_digest": None,
                                        "children": [],
                                    }
                                ],
                            },
                            {
                                "node_id": "ruleref:b0.a4:ruleref",
                                "node_kind": "rule_ref",
                                "title": "Rule reference q.child.boundary",
                                "ruleref_atom_key": "b0.a4:ruleref",
                                "rule_ref_id": "q.child.boundary",
                                "rule_ref_version": "1.0.0",
                                "child_support_digest": "sha256:cycle1",
                                "unresolved_reason": None,
                                "children": [
                                    {
                                        "node_id": "boundary:b0.a4:ruleref",
                                        "node_kind": "recursion_boundary",
                                        "title": "Recursion boundary",
                                        "boundary_reason": "depth_limit",
                                        "children": [],
                                    }
                                ],
                            },
                        ],
                    },
                ],
            },
        }

        summary = summarize_candidate_evidence_tree_dict(tree)
        self.assertEqual(
            summary,
            {
                "candidate_id": "cand-native",
                "support_kind": "native_binding_v1",
                "is_degraded": False,
                "root_result_kind": "fact",
                "node_count_by_role": {
                    "structural": 4,
                    "witness": 4,
                    "constraint": 1,
                    "rule_chain": 4,
                    "terminal": 2,
                    "degraded": 0,
                },
                "witness_assertion_count": 2,
                "rule_ref_count": 3,
                "recursive_depth": 1,
                "has_unresolved": True,
                "has_boundary": True,
                "unresolved_reasons": ["child_support_unavailable"],
                "boundary_reasons": ["depth_limit"],
            },
        )

        narrative = render_candidate_evidence_tree_narrative(summary, locale="en")
        self.assertEqual(
            narrative,
            {
                "headline": "Candidate cand-native uses support kind native_binding_v1 across 15 tree node(s).",
                "overview_lines": [
                    "Root result kind: fact.",
                    "Role counts: structural=4, witness=4, constraint=1, rule_chain=4, terminal=2, degraded=0.",
                    "Recursive depth: 1.",
                ],
                "evidence_lines": [
                    "Witness assertions: 2.",
                    "Witness nodes: 4; constraint nodes: 1.",
                ],
                "rule_chain_lines": [
                    "Rule reference nodes: 3.",
                    "Recursive proof depth: 1.",
                ],
                "terminal_lines": [
                    "Unresolved support reasons: child_support_unavailable.",
                    "Recursion boundary reasons: depth_limit.",
                ],
                "drilldown_lines": [
                    "Open referenced support branches to inspect recursive child proof.",
                    "Open linked assertion nodes to inspect witness facts.",
                ],
            },
        )

        explain_nl = render_candidate_evidence_tree_nl_explain(summary, narrative, locale="en")
        self.assertEqual(
            explain_nl,
            {
                "headline": "Candidate cand-native is explained by support kind native_binding_v1 with root result kind fact.",
                "paragraphs": [
                    "Candidate cand-native uses support kind native_binding_v1 across 15 tree node(s). Root result kind: fact. Role counts: structural=4, witness=4, constraint=1, rule_chain=4, terminal=2, degraded=0. Recursive depth: 1.",
                    "Evidence summary: Witness assertions: 2. Witness nodes: 4; constraint nodes: 1.",
                    "Rule-chain summary: Rule reference nodes: 3. Recursive proof depth: 1.",
                    "Terminal and drill-down summary: Unresolved support reasons: child_support_unavailable. Recursion boundary reasons: depth_limit. Open referenced support branches to inspect recursive child proof. Open linked assertion nodes to inspect witness facts.",
                ],
            },
        )

    def test_candidate_evidence_tree_summary_narrative_and_nl_are_deterministic_for_degraded_tree(self) -> None:
        tree = {
            "kind": "candidate_evidence_tree",
            "candidate_id": "cand-degraded",
            "support_digest": "sha256:0000",
            "support_kind": ENGINE_NO_WITNESS_KIND,
            "root": {
                "node_id": "cand:cand-degraded",
                "node_kind": "candidate_result",
                "title": "Candidate cand-degraded",
                "binding": {},
                "rule_refs": [],
                "rule_ref_edges": [],
                "children": [
                    {
                        "node_id": "support:cand-degraded",
                        "node_kind": "support_section",
                        "title": "Support",
                        "children": [
                            {
                                "node_id": "degraded:cand-degraded",
                                "node_kind": "degraded_support",
                                "title": "Degraded support",
                                "support_kind": ENGINE_NO_WITNESS_KIND,
                                "witness_status": "degraded",
                                "children": [],
                            }
                        ],
                    }
                ],
            },
        }

        summary = summarize_candidate_evidence_tree_dict(tree)
        self.assertEqual(
            summary,
            {
                "candidate_id": "cand-degraded",
                "support_kind": ENGINE_NO_WITNESS_KIND,
                "is_degraded": True,
                "root_result_kind": None,
                "node_count_by_role": {
                    "structural": 2,
                    "witness": 0,
                    "constraint": 0,
                    "rule_chain": 0,
                    "terminal": 0,
                    "degraded": 1,
                },
                "witness_assertion_count": 0,
                "rule_ref_count": 0,
                "recursive_depth": 0,
                "has_unresolved": False,
                "has_boundary": False,
                "unresolved_reasons": [],
                "boundary_reasons": [],
            },
        )

        narrative = render_candidate_evidence_tree_narrative(summary, locale="en")
        self.assertEqual(
            narrative,
            {
                "headline": f"Candidate cand-degraded uses degraded support kind {ENGINE_NO_WITNESS_KIND} without witness artifacts.",
                "overview_lines": [
                    "Root result kind: -.",
                    "Role counts: structural=2, witness=0, constraint=0, rule_chain=0, terminal=0, degraded=1.",
                    "Recursive depth: 0.",
                ],
                "evidence_lines": [
                    "No witness assertions or constraint checks are available because this candidate uses degraded support."
                ],
                "rule_chain_lines": ["No recursive rule-chain proof is available for degraded support."],
                "terminal_lines": ["No unresolved support or recursion boundaries were encountered."],
                "drilldown_lines": [
                    "Open the raw tree below to inspect the degraded support envelope.",
                    "This candidate does not expose native witness assertions or recursive child proof.",
                ],
            },
        )

        explain_nl = render_candidate_evidence_tree_nl_explain(summary, narrative, locale="en")
        self.assertEqual(
            explain_nl,
            {
                "headline": f"Candidate cand-degraded has degraded support kind {ENGINE_NO_WITNESS_KIND}.",
                "paragraphs": [
                    f"Candidate cand-degraded uses degraded support kind {ENGINE_NO_WITNESS_KIND} without witness artifacts. Root result kind: -. Role counts: structural=2, witness=0, constraint=0, rule_chain=0, terminal=0, degraded=1. Recursive depth: 0.",
                    "Evidence summary: No witness assertions or constraint checks are available because this candidate uses degraded support.",
                    "Rule-chain summary: No recursive rule-chain proof is available for degraded support.",
                    "Terminal and drill-down summary: No unresolved support or recursion boundaries were encountered. Open the raw tree below to inspect the degraded support envelope. This candidate does not expose native witness assertions or recursive child proof.",
                ],
            },
        )

    def test_runtime_explain_ref_candidate_degraded_for_engine_and_legacy_none(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)
        zero_digest = f"sha256:{'0' * 64}"

        def fake_souffle_evaluator(
            store: Any,
            *,
            derivation_id: str,
            version: str,
            target_pred_id: str,
            head_vars: list[Any],
            where: list[Any],
            head: dict[str, Any] | None = None,
        ) -> list[Any]:
            schema_pred = store_builders.find_schema_pred(store, target_pred_id)
            self.assertIsNotNone(schema_pred)
            self.assertEqual(len(where), 1)
            self.assertEqual(where[0][0], "pred")
            self.assertEqual(where[0][1], "user:tag")
            return store_builders.candidates_from_bindings(
                store,
                derivation_id=derivation_id,
                version=version,
                target_pred_id=target_pred_id,
                arg_specs=schema_pred["arg_specs"],
                head_vars=head_vars,
                schema_pred=schema_pred,
                bindings=[{"$u": refs["u1"], "$tag": "vip"}],
            )

        register_engine_evaluator(fake_souffle_evaluator, "souffle")
        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            eval_resp = evaluate_runtime_derivation(
                session_id,
                {
                    "derivation": {
                        "derivation_id": "drv.engine_degraded_explain",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [["pred", "user:tag", ["$u", "$tag"]]],
                        "mode": "souffle",
                    }
                },
            )
            self.assertTrue(eval_resp["ok"])
            candidate = eval_resp["evaluation"]["candidates"][0]
            self.assertEqual(candidate["support_kind"], ENGINE_NO_WITNESS_KIND)
            self.assertEqual(candidate["support_digest"], zero_digest)

            session = _require_session(session_id)
            self.assertEqual(
                session.store.get_candidate_support_digest(candidate["candidate_id"]),
                zero_digest,
            )
            self.assertEqual(
                session.store.get_candidate_support_kind(candidate["candidate_id"]),
                ENGINE_NO_WITNESS_KIND,
            )

            explain_engine_candidate = explain_runtime_ref(
                session_id,
                {"kind": "candidate", "id": candidate["candidate_id"]},
            )
            self.assertTrue(explain_engine_candidate["ok"])
            self.assertEqual(explain_engine_candidate["kind"], "candidate")
            self.assertEqual(explain_engine_candidate["explain"]["support_kind"], ENGINE_NO_WITNESS_KIND)
            self.assertEqual(explain_engine_candidate["explain"]["support_digest"], zero_digest)
            self.assertEqual(explain_engine_candidate["explain"]["witness_status"], "degraded")
            self.assertNotIn("support", explain_engine_candidate["explain"])

            explain_engine_tree = explain_runtime_tree(
                session_id,
                {"kind": "candidate", "id": candidate["candidate_id"]},
            )
            self.assertTrue(explain_engine_tree["ok"])
            self.assertEqual(explain_engine_tree["kind"], "candidate_evidence_tree")
            engine_tree = explain_engine_tree["tree"]
            self.assertEqual(engine_tree["support_kind"], ENGINE_NO_WITNESS_KIND)
            root = engine_tree["root"]
            self.assertEqual(root["node_kind"], "candidate_result")
            support_section = root["children"][0]
            self.assertEqual(support_section["node_kind"], "support_section")
            degraded_node = support_section["children"][0]
            self.assertEqual(degraded_node["node_kind"], "degraded_support")
            self.assertEqual(degraded_node["support_kind"], ENGINE_NO_WITNESS_KIND)
            self.assertEqual(degraded_node["witness_status"], "degraded")
            self.assertNotIn("support_digest", degraded_node)
            self.assertEqual(degraded_node["children"], [])

            session.store._remember_candidate_support("cand-legacy-none", zero_digest, "none")
            explain_legacy_none = explain_runtime_ref(
                session_id,
                {"kind": "candidate", "id": "cand-legacy-none"},
            )
            self.assertTrue(explain_legacy_none["ok"])
            self.assertEqual(explain_legacy_none["explain"]["support_kind"], "none")
            self.assertEqual(explain_legacy_none["explain"]["witness_status"], "degraded")
            self.assertEqual(explain_legacy_none["explain"]["support_digest"], zero_digest)
            self.assertNotIn("support", explain_legacy_none["explain"])

            explain_legacy_tree = explain_runtime_tree(
                session_id,
                {"kind": "candidate", "id": "cand-legacy-none"},
            )
            self.assertTrue(explain_legacy_tree["ok"])
            legacy_tree = explain_legacy_tree["tree"]
            self.assertEqual(legacy_tree["support_kind"], "none")
            legacy_degraded_node = legacy_tree["root"]["children"][0]["children"][0]
            self.assertEqual(legacy_degraded_node["node_kind"], "degraded_support")
            self.assertEqual(legacy_degraded_node["support_kind"], "none")
            self.assertEqual(legacy_degraded_node["witness_status"], "degraded")
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()
            register_engine_evaluator(souffle_adapter.evaluate_store_engine, "souffle")

    def test_engine_candidate_evidence_tree_round_trips_through_audit_and_static(self) -> None:
        zero_digest = f"sha256:{'0' * 64}"
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        def fake_souffle_evaluator(
            store: Any,
            *,
            derivation_id: str,
            version: str,
            target_pred_id: str,
            head_vars: list[Any],
            where: list[Any],
            head: dict[str, Any] | None = None,
        ) -> list[Any]:
            schema_pred = store_builders.find_schema_pred(store, target_pred_id)
            self.assertIsNotNone(schema_pred)
            return store_builders.candidates_from_bindings(
                store,
                derivation_id=derivation_id,
                version=version,
                target_pred_id=target_pred_id,
                arg_specs=schema_pred["arg_specs"],
                head_vars=head_vars,
                schema_pred=schema_pred,
                bindings=[{"$u": refs["u1"], "$tag": "vip"}],
            )

        register_engine_evaluator(fake_souffle_evaluator, "souffle")
        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            eval_resp = evaluate_runtime_derivation(
                session_id,
                {
                    "derivation": {
                        "derivation_id": "drv.engine_degraded_tree.audit",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [["pred", "user:tag", ["$u", "$tag"]]],
                        "mode": "souffle",
                    }
                },
            )
            self.assertTrue(eval_resp["ok"])
            engine_candidate = eval_resp["evaluation"]["candidates"][0]
            self.assertEqual(engine_candidate["support_kind"], ENGINE_NO_WITNESS_KIND)
            self.assertEqual(engine_candidate["support_digest"], zero_digest)

            with TemporaryDirectory() as tmpdir:
                package_dir = str(Path(tmpdir) / "pkg")
                accept_resp = accept_runtime_derivation(
                    session_id,
                    {
                        "candidate": engine_candidate,
                        "options": {"approved_by": "alice"},
                    },
                )
                self.assertTrue(accept_resp["ok"])
                export_resp = export_runtime_package(
                    session_id,
                    {"out_dir": package_dir, "package_kind": "audit"},
                )
                self.assertTrue(export_resp["ok"])

                package = load_audit_package(package_dir)
                query = AuditQuery(package)

                engine_tree = query.get_candidate_evidence_tree(engine_candidate["candidate_id"])
                self.assertIsNotNone(engine_tree)
                self.assertEqual(engine_tree["support_kind"], ENGINE_NO_WITNESS_KIND)
                degraded_node = engine_tree["root"]["children"][0]["children"][0]
                self.assertEqual(degraded_node["node_kind"], "degraded_support")
                self.assertEqual(degraded_node["support_kind"], ENGINE_NO_WITNESS_KIND)
                self.assertEqual(degraded_node["witness_status"], "degraded")
                self.assertNotIn("support_digest", degraded_node)
                runtime_summary_resp = explain_runtime_summary(
                    session_id, {"kind": "candidate", "id": engine_candidate["candidate_id"]}
                )
                runtime_narrative_resp = explain_runtime_narrative(
                    session_id, {"kind": "candidate", "id": engine_candidate["candidate_id"]}
                )
                runtime_nl_resp = explain_runtime_nl(
                    session_id, {"kind": "candidate", "id": engine_candidate["candidate_id"]}
                )
                self.assertTrue(runtime_summary_resp["ok"])
                self.assertTrue(runtime_narrative_resp["ok"])
                self.assertTrue(runtime_nl_resp["ok"])
                runtime_summary = runtime_summary_resp["summary"]
                runtime_narrative = runtime_narrative_resp["narrative"]
                runtime_nl = runtime_nl_resp["explain_nl"]
                self.assertEqual(runtime_summary, summarize_candidate_evidence_tree_dict(engine_tree))
                self.assertEqual(runtime_narrative, render_candidate_evidence_tree_narrative(runtime_summary, locale="en"))
                self.assertEqual(
                    runtime_nl,
                    render_candidate_evidence_tree_nl_explain(runtime_summary, runtime_narrative, locale="en"),
                )

                dto_tree = build_candidate_evidence_tree_dto(query, engine_candidate["candidate_id"])
                self.assertEqual(dto_tree["support_kind"], ENGINE_NO_WITNESS_KIND)
                self.assertEqual(dto_tree["root"]["children"][0]["children"][0]["node_kind"], "degraded_support")
                audit_summary = query.get_candidate_evidence_tree_summary(engine_candidate["candidate_id"])
                audit_narrative = query.get_candidate_evidence_tree_narrative(engine_candidate["candidate_id"])
                self.assertEqual(audit_summary, runtime_summary)
                self.assertEqual(audit_narrative, runtime_narrative)
                summary_dto = build_candidate_evidence_tree_summary_dto(query, engine_candidate["candidate_id"])
                narrative_dto = build_candidate_evidence_tree_narrative_dto(query, engine_candidate["candidate_id"])
                self.assertEqual(summary_dto["summary"], runtime_summary)
                self.assertEqual(narrative_dto["narrative"], runtime_narrative)

                query.package.candidate_ledger.append(
                    {
                        "candidate_id": "cand-legacy-none",
                        "support_digest": zero_digest,
                        "support_kind": "none",
                    }
                )
                legacy_tree = query.get_candidate_evidence_tree("cand-legacy-none")
                self.assertIsNotNone(legacy_tree)
                legacy_degraded_node = legacy_tree["root"]["children"][0]["children"][0]
                self.assertEqual(legacy_degraded_node["node_kind"], "degraded_support")
                self.assertEqual(legacy_degraded_node["support_kind"], "none")
                self.assertEqual(legacy_degraded_node["witness_status"], "degraded")

                static_out = Path(tmpdir) / "site"
                render_audit_static_site(package_dir, static_out)
                engine_page = (
                    Path(static_out)
                    / "candidate_evidence"
                    / f"{_slug_id(engine_candidate['candidate_id'])}.html"
                ).read_text(encoding="utf-8")
                self.assertIn("Degraded", engine_page)
                self.assertIn(ENGINE_NO_WITNESS_KIND, engine_page)
                self.assertIn("degraded", engine_page.lower())
                self.assertIn(runtime_narrative["headline"], engine_page)
                self.assertNotIn("child_support_digest", engine_page)
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()
            register_engine_evaluator(souffle_adapter.evaluate_store_engine, "souffle")

    def test_runtime_explain_ref_route_http_200_and_shape_errors(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            write_resp = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag",
                    "e_ref": refs["u1"],
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            self.assertTrue(write_resp["ok"])
            asrt_id = write_resp["write"]["assertion_id"]

            eval_resp = evaluate_runtime_derivation(
                session_id,
                {
                    "derivation": {
                        "derivation_id": "drv.tag_copy.unified.route",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [["pred", "user:tag", ["$u", "$tag"]]],
                        "mode": "native",
                    }
                },
            )
            self.assertTrue(eval_resp["ok"])
            candidate_id = eval_resp["evaluation"]["candidates"][0]["candidate_id"]

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "q.runtime_unified_route_rows",
                        "version": "1.0.0",
                        "select": ["$u", "$tag"],
                        "where": [["pred", "user:tag", ["$u", "$tag"]]],
                    },
                    "capture_trace": True,
                },
            )
            self.assertTrue(rule_resp["ok"])
            rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]

            self.assertIn(
                "/v1/runtime/sessions/{session_id}/queries/explain",
                {route.path for route in app.routes},
            )
            self.assertIn(
                "/v1/runtime/sessions/{session_id}/queries/explain-tree",
                {route.path for route in app.routes},
            )
            self.assertIn(
                "/v1/runtime/sessions/{session_id}/queries/explain-summary",
                {route.path for route in app.routes},
            )
            self.assertIn(
                "/v1/runtime/sessions/{session_id}/queries/explain-narrative",
                {route.path for route in app.routes},
            )
            self.assertIn(
                "/v1/runtime/sessions/{session_id}/queries/explain-nl",
                {route.path for route in app.routes},
            )
            self.assertIn(
                "/v1/runtime/sessions/{session_id}/evidence/candidate/{candidate_id}",
                {route.path for route in app.routes},
            )
            self.assertIn(
                "/v1/runtime/sessions/{session_id}/evidence/rule-trace/{rule_run_id}",
                {route.path for route in app.routes},
            )

            with TestClient(app) as client:
                candidate_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain",
                    json={"kind": "candidate", "id": candidate_id},
                )
                self.assertEqual(candidate_http.status_code, 200)
                self.assertTrue(candidate_http.json()["ok"])
                self.assertEqual(candidate_http.json()["kind"], "candidate")

                candidate_tree_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-tree",
                    json={"kind": "candidate", "id": candidate_id},
                )
                self.assertEqual(candidate_tree_http.status_code, 200)
                self.assertTrue(candidate_tree_http.json()["ok"])
                self.assertEqual(candidate_tree_http.json()["kind"], "candidate_evidence_tree")
                self.assertIn("tree", candidate_tree_http.json())

                assertion_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain",
                    json={"kind": "assertion", "id": asrt_id},
                )
                self.assertEqual(assertion_http.status_code, 200)
                self.assertTrue(assertion_http.json()["ok"])
                self.assertEqual(assertion_http.json()["kind"], "assertion")

                rule_run_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain",
                    json={"kind": "rule_run", "id": rule_run_id},
                )
                self.assertEqual(rule_run_http.status_code, 200)
                self.assertTrue(rule_run_http.json()["ok"])
                self.assertEqual(rule_run_http.json()["kind"], "rule_run")

                summary_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-summary",
                    json={"kind": "rule_run", "id": rule_run_id},
                )
                self.assertEqual(summary_http.status_code, 200)
                self.assertTrue(summary_http.json()["ok"])
                self.assertEqual(summary_http.json()["kind"], "rule_run_summary")
                self.assertIn("summary", summary_http.json())

                candidate_summary_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-summary",
                    json={"kind": "candidate", "id": candidate_id},
                )
                self.assertEqual(candidate_summary_http.status_code, 200)
                self.assertTrue(candidate_summary_http.json()["ok"])
                self.assertEqual(candidate_summary_http.json()["kind"], "candidate_evidence_tree_summary")
                self.assertIn("summary", candidate_summary_http.json())

                narrative_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-narrative",
                    json={"kind": "rule_run", "id": rule_run_id},
                )
                self.assertEqual(narrative_http.status_code, 200)
                self.assertTrue(narrative_http.json()["ok"])
                self.assertEqual(narrative_http.json()["kind"], "rule_run_narrative")
                self.assertIn("narrative", narrative_http.json())

                candidate_narrative_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-narrative",
                    json={"kind": "candidate", "id": candidate_id},
                )
                self.assertEqual(candidate_narrative_http.status_code, 200)
                self.assertTrue(candidate_narrative_http.json()["ok"])
                self.assertEqual(candidate_narrative_http.json()["kind"], "candidate_evidence_tree_narrative")
                self.assertIn("narrative", candidate_narrative_http.json())

                nl_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-nl",
                    json={"kind": "rule_run", "id": rule_run_id},
                )
                self.assertEqual(nl_http.status_code, 200)
                self.assertTrue(nl_http.json()["ok"])
                self.assertEqual(nl_http.json()["kind"], "rule_run_nl_explain")
                self.assertIn("explain_nl", nl_http.json())

                candidate_nl_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-nl",
                    json={"kind": "candidate", "id": candidate_id},
                )
                self.assertEqual(candidate_nl_http.status_code, 200)
                self.assertTrue(candidate_nl_http.json()["ok"])
                self.assertEqual(candidate_nl_http.json()["kind"], "candidate_evidence_tree_nl_explain")
                self.assertIn("explain_nl", candidate_nl_http.json())

                candidate_html_http = client.get(
                    f"/v1/runtime/sessions/{session_id}/evidence/candidate/{candidate_id}",
                )
                self.assertEqual(candidate_html_http.status_code, 200)
                self.assertTrue(candidate_html_http.headers["content-type"].startswith("text/html"))
                self.assertIn(f"Candidate Evidence {candidate_id}", candidate_html_http.text)
                self.assertIn("Analysis Summary", candidate_html_http.text)
                self.assertIn("Fact Match", candidate_html_http.text)

                rule_trace_html_http = client.get(
                    f"/v1/runtime/sessions/{session_id}/evidence/rule-trace/{rule_run_id}",
                )
                self.assertEqual(rule_trace_html_http.status_code, 200)
                self.assertTrue(rule_trace_html_http.headers["content-type"].startswith("text/html"))
                self.assertIn(f"Rule Trace {rule_run_id}", rule_trace_html_http.text)
                self.assertIn("Narrative", rule_trace_html_http.text)
                self.assertIn("Predicate Witnesses", rule_trace_html_http.text)

                unsupported_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain",
                    json={"kind": "fact", "id": "ignored"},
                )
                self.assertEqual(unsupported_kind_http.status_code, 200)
                self.assertFalse(unsupported_kind_http.json()["ok"])
                self.assertEqual(unsupported_kind_http.json()["errors"][0]["kind"], "shape")

                missing_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain",
                    json={"id": candidate_id},
                )
                self.assertEqual(missing_kind_http.status_code, 200)
                self.assertFalse(missing_kind_http.json()["ok"])
                self.assertEqual(missing_kind_http.json()["errors"][0]["kind"], "shape")

                unsupported_tree_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-tree",
                    json={"kind": "rule_run", "id": rule_run_id},
                )
                self.assertEqual(unsupported_tree_kind_http.status_code, 200)
                self.assertFalse(unsupported_tree_kind_http.json()["ok"])
                self.assertEqual(unsupported_tree_kind_http.json()["errors"][0]["kind"], "shape")

                missing_tree_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-tree",
                    json={"id": candidate_id},
                )
                self.assertEqual(missing_tree_kind_http.status_code, 200)
                self.assertFalse(missing_tree_kind_http.json()["ok"])
                self.assertEqual(missing_tree_kind_http.json()["errors"][0]["kind"], "shape")

                missing_summary_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-summary",
                    json={"id": rule_run_id},
                )
                self.assertEqual(missing_summary_kind_http.status_code, 200)
                self.assertFalse(missing_summary_kind_http.json()["ok"])
                self.assertEqual(missing_summary_kind_http.json()["errors"][0]["kind"], "shape")

                missing_narrative_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-narrative",
                    json={"id": rule_run_id},
                )
                self.assertEqual(missing_narrative_kind_http.status_code, 200)
                self.assertFalse(missing_narrative_kind_http.json()["ok"])
                self.assertEqual(missing_narrative_kind_http.json()["errors"][0]["kind"], "shape")

                missing_nl_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-nl",
                    json={"id": rule_run_id},
                )
                self.assertEqual(missing_nl_kind_http.status_code, 200)
                self.assertFalse(missing_nl_kind_http.json()["ok"])
                self.assertEqual(missing_nl_kind_http.json()["errors"][0]["kind"], "shape")
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    # ── F-CORE-2: _remember_candidate_support digest collision ────────

    def test_remember_candidate_support_first_registration(self) -> None:
        """Fresh candidate_id registers normally in all three indices."""
        open_resp = open_runtime_session({"schema_ir": _schema_ir()})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            session = _require_session(session_id)
            digest = "sha256:" + "a" * 64
            session.store._remember_candidate_support(
                "cand-fresh", digest, "native_binding_v1",
                confidence_kind="certainty",
            )
            self.assertEqual(
                session.store.get_candidate_support_digest("cand-fresh"),
                digest,
            )
            self.assertEqual(
                session.store.get_candidate_support_kind("cand-fresh"),
                "native_binding_v1",
            )
            self.assertEqual(
                session.store.get_candidate_confidence_kind("cand-fresh"),
                "certainty",
            )
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_remember_candidate_support_idempotent_same_digest(self) -> None:
        """Same candidate_id + same digest re-registers without error."""
        open_resp = open_runtime_session({"schema_ir": _schema_ir()})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            session = _require_session(session_id)
            digest = "sha256:" + "b" * 64
            session.store._remember_candidate_support(
                "cand-idem", digest, "native_binding_v1",
                confidence_kind="certainty",
            )
            # Second call — same digest — must not raise
            session.store._remember_candidate_support(
                "cand-idem", digest, "native_binding_v1",
                confidence_kind="certainty",
            )
            self.assertEqual(
                session.store.get_candidate_support_digest("cand-idem"),
                digest,
            )
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_remember_candidate_support_raises_on_different_digest(self) -> None:
        """Same candidate_id + different digest raises ValueError."""
        open_resp = open_runtime_session({"schema_ir": _schema_ir()})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            session = _require_session(session_id)
            digest_a = "sha256:" + "c" * 64
            digest_b = "sha256:" + "d" * 64
            session.store._remember_candidate_support(
                "cand-collision", digest_a, "native_binding_v1",
            )
            with self.assertRaises(ValueError) as ctx:
                session.store._remember_candidate_support(
                    "cand-collision", digest_b, "native_binding_v1",
                )
            self.assertIn("already registered with different support_digest", str(ctx.exception))
            # Original digest preserved
            self.assertEqual(
                session.store.get_candidate_support_digest("cand-collision"),
                digest_a,
            )
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()
