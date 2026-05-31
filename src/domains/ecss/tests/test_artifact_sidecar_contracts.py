from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import unittest
from unittest.mock import patch
from urllib.parse import quote

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
    find_winning_branch_index,
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
    RuleRef,
    SDKDSLError,
    SDKStore,
    SDKStoreError,
    compile_schema_from_classes,
    vars as sdk_vars,
)
from factgraph.sdk.dsl import Rule
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


class ArtifactSidecarContractsTests(unittest.TestCase):
    def test_runtime_session_artifact_store_root_enables_cross_session_explain_readback(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with TemporaryDirectory() as tmp_dir:
            reset_runtime_sessions_for_tests()
            first_open = open_runtime_session({"schema_ir": sdk.schema_ir, "artifact_store_root": tmp_dir})
            self.assertTrue(first_open["ok"])
            first_session_id = first_open["session"]["session_id"]
            self.assertNotIn("artifact_store_root", first_open["session"])
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

                eval_resp = evaluate_runtime_derivation(
                    first_session_id,
                    {
                        "inference": {
                            "derivation_id": "drv.tag_copy",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [["pred", "user:tag", ["$u", "$tag"]]],
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                support_digest = eval_resp["evaluation"]["candidates"][0]["support_digest"]

                rule_resp = run_runtime_rule(
                    first_session_id,
                    {
                        "rule": {
                            "rule_id": "q.runtime_sidecar_rows",
                            "version": "1.0.0",
                            "select": ["$u", "$tag"],
                            "where": [["pred", "user:tag", ["$u", "$tag"]]],
                        },
                        "capture_trace": True,
                    },
                )
                self.assertTrue(rule_resp["ok"])
                rule_run_id = rule_resp["result"]["trace"]["rule_run_id"]
            finally:
                close_runtime_session(first_session_id)

            second_open = open_runtime_session({"schema_ir": sdk.schema_ir, "artifact_store_root": tmp_dir})
            self.assertTrue(second_open["ok"])
            second_session_id = second_open["session"]["session_id"]
            self.assertNotIn("artifact_store_root", second_open["session"])
            try:
                explain_support_resp = explain_runtime_support(
                    second_session_id,
                    {"support_digest": support_digest},
                )
                self.assertTrue(explain_support_resp["ok"])
                self.assertEqual(explain_support_resp["meta"]["support_digest"], support_digest)

                explain_rule_resp = explain_runtime_rule_trace(
                    second_session_id,
                    {"rule_run_id": rule_run_id},
                )
                self.assertTrue(explain_rule_resp["ok"])
                self.assertEqual(explain_rule_resp["meta"]["rule_run_id"], rule_run_id)
            finally:
                close_runtime_session(second_session_id)
                reset_runtime_sessions_for_tests()

    def test_audit_package_exports_support_and_rule_trace_artifacts(self) -> None:
        sdk = SDKStore([User])
        _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "loc", "tag") as (u, loc, tag):
            drv = Derivation(
                id="drv.tag_copy",
                version="1.0.0",
                where=[
                    User(u),
                    u.locale == loc,
                    u.tag == tag,
                ],
                head=User.tag(locale=loc, tag=tag),
            )
        candidates = sdk.eval.evaluate(drv, mode="native")
        self.assertTrue(candidates)
        self.assertEqual(candidates[0].support_kind, "native_binding_v1")
        support_digest = candidates[0].support_digest
        self.assertIsNotNone(sdk.store.explain_support(support_digest))

        with sdk_vars("u", "tag") as (u, tag):
            rule = Rule(
                id="q.audit_tag_rows",
                version="1.0.0",
                select=[u, tag],
                where=[Pred("user:tag", u, tag)],
                expose=True,
            )

        compiled = sdk._compile_rule_input(rule)
        rule_spec = RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )
        registry = RuleRegistry()
        sdk._register_rule_dependencies(registry, rule)
        trace_result = run_rule_with_trace(sdk.store, rule_spec, registry)
        self.assertIsNotNone(sdk.store.explain_rule_trace(trace_result.rule_run_id))

        with TemporaryDirectory() as tmp_dir:
            manifest_path = export_package(
                sdk.store,
                Path(tmp_dir),
                ExportOptions(package_kind="audit"),
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            audit_files = manifest["paths"]["audit_files"]
            self.assertEqual(audit_files["support_artifacts"], "audit/support_artifacts.jsonl")
            self.assertEqual(audit_files["rule_trace_artifacts"], "audit/rule_trace_artifacts.jsonl")

            support_rows = [
                json.loads(line)
                for line in (Path(tmp_dir) / audit_files["support_artifacts"]).read_text(encoding="utf-8").splitlines()
                if line
            ]
            trace_rows = [
                json.loads(line)
                for line in (Path(tmp_dir) / audit_files["rule_trace_artifacts"]).read_text(encoding="utf-8").splitlines()
                if line
            ]

            self.assertTrue(any(row["support_digest"] == support_digest for row in support_rows))
            support_row = next(row for row in support_rows if row["support_digest"] == support_digest)
            self.assertEqual(support_row["kind"], "native_binding_v1")
            self.assertIn("binding", support_row)
            self.assertIn("pred_witnesses", support_row)
            self.assertNotIn("artifact", support_row)

            self.assertTrue(any(row["rule_run_id"] == trace_result.rule_run_id for row in trace_rows))
            trace_row = next(row for row in trace_rows if row["rule_run_id"] == trace_result.rule_run_id)
            self.assertEqual(trace_row["root_rule"]["rule_id"], "q.audit_tag_rows")
            self.assertIn("invocations", trace_row)
            self.assertNotIn("artifact", trace_row)

    def test_candidate_support_backrefs_track_native_kind_and_missing_ids(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "loc", "tag") as (u, loc, tag):
            drv = Derivation(
                id="drv.tag_copy.backref",
                version="1.0.0",
                where=[
                    User(u),
                    u.locale == loc,
                    u.tag == tag,
                ],
                head=User.tag(locale=loc, tag=tag),
            )

        candidates = sdk.eval.evaluate(drv, mode="native")
        self.assertTrue(candidates)
        for candidate in candidates:
            digest = sdk.store.get_candidate_support_digest(candidate.candidate_id)
            support_kind = sdk.store.get_candidate_support_kind(candidate.candidate_id)
            confidence_kind = sdk.store.get_candidate_confidence_kind(candidate.candidate_id)
            self.assertEqual(digest, candidate.support_digest)
            self.assertEqual(support_kind, "native_binding_v1")
            self.assertEqual(confidence_kind, "none")
            self.assertIsNotNone(sdk.store.explain_support(digest))

        self.assertIsNone(sdk.store.get_candidate_support_digest("missing-candidate-id"))
        self.assertIsNone(sdk.store.get_candidate_support_kind("missing-candidate-id"))
        self.assertIsNone(sdk.store.get_candidate_confidence_kind("missing-candidate-id"))

        compat_candidate = sdk.store.evaluate_dummy(
            derivation_id="drv.compat",
            version="1.0.0",
            target="user:tag",
            e_ref=refs["u1"],
            rest_terms=[("string", "legacy")],
            dims_terms=[],
        )
        self.assertEqual(compat_candidate.support_kind, ENGINE_NO_WITNESS_KIND)
        self.assertIsNone(sdk.store.get_candidate_support_digest(compat_candidate.candidate_id))
        self.assertIsNone(sdk.store.get_candidate_support_kind(compat_candidate.candidate_id))
        self.assertIsNone(sdk.store.get_candidate_confidence_kind(compat_candidate.candidate_id))

    def test_file_artifact_sidecar_support_read_write_and_collision(self) -> None:
        artifact = support_artifact_from_dict(
            {
                "support_digest": "sha256:" + ("ab" * 32),
                "kind": "native_binding_v1",
                "root_result_kind": "fact",
                "binding": [
                    ["$blob", {"__bytes_hex__": "00ff"}],
                    ["$pair", [1, 2]],
                ],
                "pred_witnesses": [
                    {
                        "pred_atom_key": "b0.a0:user:tag",
                        "asrt_ids": ["A1"],
                    }
                ],
                "non_fact_steps": [],
                "rule_refs": [],
            }
        )
        digest = "sha256:" + ("ab" * 32)

        with TemporaryDirectory() as tmp_dir:
            clock_values = iter([123, 999])
            sidecar = FileArtifactSidecar(tmp_dir, clock=lambda: next(clock_values))
            meta_path = Path(tmp_dir) / "support" / "sha256" / f"{'ab' * 32}.meta.json"

            self.assertIsNone(sidecar.read_support(digest))

            sidecar.write_support(digest, artifact)
            self.assertEqual(sidecar.read_support(digest), artifact)
            self.assertEqual(json.loads(meta_path.read_text(encoding="utf-8")), {"captured_at_ns": 123})

            sidecar.write_support(digest, artifact)
            self.assertEqual(json.loads(meta_path.read_text(encoding="utf-8")), {"captured_at_ns": 123})

            with self.assertRaises(ValueError) as ctx:
                sidecar.write_support(
                    digest,
                    support_artifact_from_dict(
                        {
                            "support_digest": digest,
                            "kind": "native_binding_v1",
                            "root_result_kind": "fact",
                            "binding": [["$blob", {"__bytes_hex__": "ff"}]],
                            "pred_witnesses": [
                                {
                                    "pred_atom_key": "b0.a0:user:tag",
                                    "asrt_ids": ["A1"],
                                }
                            ],
                            "non_fact_steps": [],
                            "rule_refs": [],
                        }
                    ),
                )
            self.assertEqual(
                str(ctx.exception),
                f"support_digest collision for different ProofReceipt on disk: {digest}",
            )

    def test_file_artifact_sidecar_rule_trace_read_write_collision_and_path_guard(self) -> None:
        artifact = rule_trace_artifact_from_dict(
            {
                "rule_run_id": "rr_1",
                "root_rule": {"rule_id": "q.user", "version": "1.0.0"},
                "select_vars": ["$u"],
                "invocations": [
                    {
                        "invocation_id": "rr_1:i1",
                        "parent_invocation_id": None,
                        "rule": {"rule_id": "q.user", "version": "1.0.0"},
                        "memo_hit": False,
                        "memo_source_invocation_id": None,
                        "original_where": [["pred", "user:tag", [{"__bytes_hex__": "00ff"}]]],
                        "rewritten_where": {"opaque": {"__bytes_hex__": "0a0b"}},
                        "bindings": [
                            [
                                ["$blob", {"__bytes_hex__": "6162"}],
                                ["$pair", [1, 2]],
                            ]
                        ],
                        "output_rows": [[{"__bytes_hex__": "0102"}, [3, 4]]],
                        "pred_witnesses": [
                            {
                                "binding_index": 0,
                                "pred_atom_key": "b0.a0:user:tag",
                                "asrt_ids": ["A1"],
                            }
                        ],
                        "non_fact_steps": [],
                    }
                ],
                "root_rows": [[{"__bytes_hex__": "c0ff"}]],
            }
        )

        with TemporaryDirectory() as tmp_dir:
            sidecar = FileArtifactSidecar(tmp_dir)

            self.assertIsNone(sidecar.read_rule_trace("missing"))

            sidecar.write_rule_trace("rr_1", artifact)
            self.assertEqual(sidecar.read_rule_trace("rr_1"), artifact)

            sidecar.write_rule_trace("rr_1", artifact)

            with self.assertRaises(ValueError) as ctx_collision:
                sidecar.write_rule_trace(
                    "rr_1",
                    rule_trace_artifact_from_dict(
                        {
                            "rule_run_id": "rr_1",
                            "root_rule": {"rule_id": "q.user.changed", "version": "1.0.0"},
                            "select_vars": ["$u"],
                            "invocations": [],
                            "root_rows": [],
                        }
                    ),
                )
            self.assertEqual(
                str(ctx_collision.exception),
                "rule_run_id collision for different RuleTraceArtifact on disk: rr_1",
            )

            with self.assertRaises(ValueError) as ctx_path:
                sidecar.read_rule_trace("bad/name")
            self.assertEqual(str(ctx_path.exception), "rule_run_id must be filesystem-safe")

            with self.assertRaises(ValueError) as ctx_backslash:
                sidecar.read_rule_trace("bad\\name")
            self.assertEqual(str(ctx_backslash.exception), "rule_run_id must be filesystem-safe")

            with self.assertRaises(ValueError) as ctx_null:
                sidecar.read_rule_trace("bad\x00name")
            self.assertEqual(str(ctx_null.exception), "rule_run_id must be filesystem-safe")

    def test_file_artifact_sidecar_gc_rule_trace_dry_run_keeps_files(self) -> None:
        artifact = rule_trace_artifact_from_dict(
            {
                "rule_run_id": "rr_old",
                "root_rule": {"rule_id": "q.user", "version": "1.0.0"},
                "select_vars": ["$u"],
                "invocations": [],
                "root_rows": [],
            }
        )

        with TemporaryDirectory() as tmp_dir:
            clock_values = iter([100, 250])
            sidecar = FileArtifactSidecar(tmp_dir, clock=lambda: next(clock_values))
            payload_path = sidecar._rule_trace_path("rr_old")
            meta_path = sidecar._meta_path(payload_path)

            sidecar.write_rule_trace("rr_old", artifact)

            dry_run = sidecar.gc_rule_trace(100, dry_run=True)
            self.assertIsInstance(dry_run, GCResult)
            self.assertEqual(dry_run.total_scanned, 1)
            self.assertEqual(dry_run.deleted_keys, ("rr_old",))
            self.assertEqual(dry_run.deleted_orphan_meta_paths, ())
            self.assertEqual(dry_run.skipped_orphan_payload_paths, ())
            self.assertEqual(dry_run.failed_keys, ())
            self.assertTrue(payload_path.exists())
            self.assertTrue(meta_path.exists())

    def test_file_artifact_sidecar_gc_rule_trace_uses_single_now_snapshot(self) -> None:
        artifact_old = rule_trace_artifact_from_dict(
            {
                "rule_run_id": "rr_old",
                "root_rule": {"rule_id": "q.user", "version": "1.0.0"},
                "select_vars": ["$u"],
                "invocations": [],
                "root_rows": [],
            }
        )
        artifact_new = rule_trace_artifact_from_dict(
            {
                "rule_run_id": "rr_new",
                "root_rule": {"rule_id": "q.user", "version": "1.0.0"},
                "select_vars": ["$u"],
                "invocations": [],
                "root_rows": [],
            }
        )

        with TemporaryDirectory() as tmp_dir:
            clock_values = iter([100, 200, 250, 900])
            sidecar = FileArtifactSidecar(tmp_dir, clock=lambda: next(clock_values))
            old_payload_path = sidecar._rule_trace_path("rr_old")
            old_meta_path = sidecar._meta_path(old_payload_path)
            new_payload_path = sidecar._rule_trace_path("rr_new")
            new_meta_path = sidecar._meta_path(new_payload_path)

            sidecar.write_rule_trace("rr_old", artifact_old)
            sidecar.write_rule_trace("rr_new", artifact_new)

            applied = sidecar.gc_rule_trace(100)
            self.assertIsInstance(applied, GCResult)
            self.assertEqual(applied.total_scanned, 2)
            self.assertEqual(applied.deleted_keys, ("rr_old",))
            self.assertEqual(applied.failed_keys, ())
            self.assertFalse(old_payload_path.exists())
            self.assertFalse(old_meta_path.exists())
            self.assertTrue(new_payload_path.exists())
            self.assertTrue(new_meta_path.exists())

    def test_file_artifact_sidecar_gc_rule_trace_handles_orphans_failures_and_ttl_validation(self) -> None:
        payload_orphan_artifact = rule_trace_artifact_from_dict(
            {
                "rule_run_id": "rr_payload_orphan",
                "root_rule": {"rule_id": "q.user", "version": "1.0.0"},
                "select_vars": ["$u"],
                "invocations": [],
                "root_rows": [],
            }
        )
        corrupt_meta_artifact = rule_trace_artifact_from_dict(
            {
                "rule_run_id": "rr_bad_meta",
                "root_rule": {"rule_id": "q.user", "version": "1.0.0"},
                "select_vars": ["$u"],
                "invocations": [],
                "root_rows": [],
            }
        )

        with TemporaryDirectory() as tmp_dir:
            clock_values = iter([100, 200, 1_000])
            sidecar = FileArtifactSidecar(tmp_dir, clock=lambda: next(clock_values))

            sidecar.write_rule_trace("rr_payload_orphan", payload_orphan_artifact)
            payload_orphan_path = sidecar._rule_trace_path("rr_payload_orphan")
            payload_orphan_meta_path = sidecar._meta_path(payload_orphan_path)
            payload_orphan_meta_path.unlink()

            sidecar.write_rule_trace("rr_bad_meta", corrupt_meta_artifact)
            bad_meta_payload_path = sidecar._rule_trace_path("rr_bad_meta")
            bad_meta_path = sidecar._meta_path(bad_meta_payload_path)
            bad_meta_path.write_text('{"captured_at_ns":"oops"}', encoding="utf-8")

            orphan_meta_path = sidecar._meta_path(sidecar._rule_trace_path("rr_meta_orphan"))
            orphan_meta_path.parent.mkdir(parents=True, exist_ok=True)
            orphan_meta_path.write_text('{"captured_at_ns":1}', encoding="utf-8")

            with self.assertRaises(ValueError) as ctx_ttl:
                sidecar.gc_rule_trace(0)
            self.assertEqual(str(ctx_ttl.exception), "ttl_ns must be positive int")

            with self.assertLogs("factgraph.core.store._artifact_sidecar", level="WARNING") as warnings_ctx:
                result = sidecar.gc_rule_trace(100)

            self.assertEqual(result.total_scanned, 3)
            self.assertEqual(result.deleted_keys, ())
            self.assertEqual(result.deleted_orphan_meta_paths, (str(orphan_meta_path),))
            self.assertEqual(result.skipped_orphan_payload_paths, (str(payload_orphan_path),))
            self.assertEqual(
                result.failed_keys,
                (("rr_bad_meta", str(bad_meta_path), f"captured_at_ns must be int: {bad_meta_path}"),),
            )
            self.assertFalse(orphan_meta_path.exists())
            self.assertTrue(payload_orphan_path.exists())
            self.assertFalse(payload_orphan_meta_path.exists())
            self.assertTrue(bad_meta_payload_path.exists())
            self.assertTrue(bad_meta_path.exists())
            self.assertEqual(len(warnings_ctx.output), 2)

    def test_store_sidecar_cross_store_readback_and_rehydrate(self) -> None:
        support_digest = "sha256:" + ("ab" * 32)
        support_artifact = support_artifact_from_dict(
            {
                "support_digest": support_digest,
                "kind": "native_binding_v1",
                "root_result_kind": "fact",
                "binding": [["$blob", {"__bytes_hex__": "00ff"}]],
                "pred_witnesses": [
                    {
                        "pred_atom_key": "b0.a0:user:tag",
                        "asrt_ids": ["A1"],
                    }
                ],
                "non_fact_steps": [],
                "rule_refs": [],
            }
        )
        rule_trace_artifact = rule_trace_artifact_from_dict(
            {
                "rule_run_id": "rr_cross_store",
                "root_rule": {"rule_id": "q.user", "version": "1.0.0"},
                "select_vars": ["$u"],
                "invocations": [],
                "root_rows": [],
            }
        )

        with TemporaryDirectory() as tmp_dir:
            sidecar = FileArtifactSidecar(tmp_dir)
            writer = Store(_schema_ir(), artifact_sidecar=sidecar)
            reader = Store(_schema_ir(), artifact_sidecar=FileArtifactSidecar(tmp_dir))

            writer._remember_support_artifact(support_digest, support_artifact)
            writer._remember_rule_trace_artifact("rr_cross_store", rule_trace_artifact)

            self.assertNotIn(support_digest, reader._support_artifacts)
            self.assertNotIn("rr_cross_store", reader._rule_trace_artifacts)

            self.assertEqual(reader._lookup_support_artifact(support_digest), support_artifact)
            self.assertEqual(reader._lookup_rule_trace_artifact("rr_cross_store"), rule_trace_artifact)

            self.assertEqual(reader._support_artifacts[support_digest], support_artifact)
            self.assertEqual(reader._rule_trace_artifacts["rr_cross_store"], rule_trace_artifact)

    def test_store_sidecar_rehydrate_does_not_rewrite_sidecar(self) -> None:
        support_digest = "sha256:" + ("cd" * 32)
        support_artifact = support_artifact_from_dict(
            {
                "support_digest": support_digest,
                "kind": "native_binding_v1",
                "root_result_kind": "fact",
                "binding": [["$blob", {"__bytes_hex__": "00ff"}]],
                "pred_witnesses": [
                    {
                        "pred_atom_key": "b0.a0:user:tag",
                        "asrt_ids": ["A1"],
                    }
                ],
                "non_fact_steps": [],
                "rule_refs": [],
            }
        )

        class SpySidecar:
            def __init__(self, artifact: object) -> None:
                self._artifact = artifact
                self.write_support_calls = 0
                self.read_support_calls = 0

            def write_support(self, support_digest: str, artifact: object) -> None:
                self.write_support_calls += 1

            def write_rule_trace(self, rule_run_id: str, artifact: object) -> None:
                raise AssertionError("unexpected write_rule_trace call")

            def read_support(self, support_digest: str) -> object | None:
                self.read_support_calls += 1
                return self._artifact

            def read_rule_trace(self, rule_run_id: str) -> object | None:
                raise AssertionError("unexpected read_rule_trace call")

        sidecar = SpySidecar(support_artifact)
        store = Store(_schema_ir(), artifact_sidecar=sidecar)

        self.assertEqual(store._lookup_support_artifact(support_digest), support_artifact)
        self.assertEqual(sidecar.read_support_calls, 1)
        self.assertEqual(sidecar.write_support_calls, 0)
        self.assertEqual(store._support_artifacts[support_digest], support_artifact)

    def test_store_sidecar_read_errors_propagate(self) -> None:
        class BrokenSidecar:
            def write_support(self, support_digest: str, artifact: object) -> None:
                raise AssertionError("unexpected write_support call")

            def write_rule_trace(self, rule_run_id: str, artifact: object) -> None:
                raise AssertionError("unexpected write_rule_trace call")

            def read_support(self, support_digest: str) -> object | None:
                raise ValueError("corrupt support sidecar row")

            def read_rule_trace(self, rule_run_id: str) -> object | None:
                raise ValueError("corrupt rule trace sidecar row")

        store = Store(_schema_ir(), artifact_sidecar=BrokenSidecar())

        with self.assertRaises(ValueError) as ctx_support:
            store._lookup_support_artifact("sha256:" + ("ef" * 32))
        self.assertEqual(str(ctx_support.exception), "corrupt support sidecar row")

        with self.assertRaises(ValueError) as ctx_trace:
            store._lookup_rule_trace_artifact("rr_broken")
        self.assertEqual(str(ctx_trace.exception), "corrupt rule trace sidecar row")

    def test_sdk_artifact_store_root_enables_cross_instance_readback(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            writer = SDKStore([User], artifact_store_root=tmp_dir)
            refs = _seed_users_for_syntax_matrix(writer)

            with sdk_vars("u", "tag") as (u, tag):
                drv = Derivation(
                    id="drv.tag_copy.sdk_sidecar",
                    version="1.0.0",
                    where=[
                        User(u),
                        u.tag == tag,
                    ],
                    head=User.tag(locale="zh", tag=tag),
                )

            candidates = writer.eval.evaluate(drv, mode="native")
            self.assertTrue(candidates)
            support_digest = candidates[0].support_digest

            reader = SDKStore([User], artifact_store_root=tmp_dir)
            self.assertIsNotNone(reader.store.explain_support(support_digest))

            via_factory = SDKStore.from_schema_classes([User], artifact_store_root=tmp_dir)
            self.assertIsNotNone(via_factory.store.explain_support(support_digest))
