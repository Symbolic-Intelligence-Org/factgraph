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

from factpy.adapters.souffle.package import ExportOptions, export_package
from factpy.audit import (
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
from factpy.domains.ecss.compliance import (
    ECSS_COMPLIANCE_STATUS_PRED_ID,
    ECSS_REQUIREMENT_PRED_ID,
    ECSS_REQUIREMENT_RID_PRED_ID,
    ECSS_REVIEW_MILESTONE_PRED_ID,
    ECSS_VERIFICATION_METHOD_PRED_ID,
    extend_schema_ir_with_ecss_vcd_predicates,
)
from factpy.service.static_ui import render_audit_static_site
from factpy.audit.assertions import load_assertion_index
from factpy.authoring import (
    AuthoringDerivationCompileError,
    FileAuthoringRegistry,
    build_derivation_preview_dto,
    compile_authoring_schema_v1,
    compile_authoring_derivation_v1,
    parse_authoring_schema_dsl_v1,
    parse_authoring_derivation_dsl_v1,
)
from factpy.authoring.where_schema_lowering import (
    WhereSchemaLoweringError,
    lower_blueprint_where_sugar_with_schema_v1,
)
from factpy.domains.ecss import (
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
from factpy.core.rules.rule_ir import (
    RuleCompileError,
    RuleRegistry,
    RuleSpec,
    run_rule_with_trace,
)
from factpy.core.rules._trace import (
    RuleTraceArtifact,
    RuleTraceInvocation,
    RuleTraceRuleRefLink,
    rule_trace_artifact_from_dict,
    rule_trace_artifact_to_dict,
    summarize_rule_trace_artifact_dict,
)
from factpy.core.rules._trace_nl import render_rule_run_nl_explain
from factpy.core.rules._trace_narrative import render_rule_run_narrative
from factpy.core.rules.ruleref_types import NativeRuleRefResolution, NativeRuleRefRowSupport
from factpy.core.rules.where_eval import WhereValidationError, _plan_body_atoms
from factpy.core.store import Store, register_engine_evaluator
import factpy.core.store._builders as store_builders
from factpy.core.store._artifact_sidecar import FileArtifactSidecar, GCResult
from factpy.core.store._candidate_evidence_tree_narrative import render_candidate_evidence_tree_narrative
from factpy.core.store._candidate_evidence_tree_nl import render_candidate_evidence_tree_nl_explain
from factpy.core.store._candidate_evidence_tree_summary import summarize_candidate_evidence_tree_dict
from factpy.core.store._support_capture import (
    build_support_artifact_for_binding,
    derive_rule_ref_edges_for_binding,
    find_winning_branch_index,
)
from factpy.core.store._support import (
    ENGINE_NO_WITNESS_KIND,
    ProjectedFact,
    compute_support_digest,
    support_artifact_from_dict,
    support_artifact_to_dict,
)
from factpy.core.evidence.write_protocol import set_field
from factpy.core.protocol.idref_v1 import encode_idref_v1
from factpy.core.view.projector import project_view_facts
from factpy.sdk import (
    Branch,
    Derivation,
    Entity,
    Field,
    Identity,
    Not,
    Pred,
    Query,
    ReadPolicy,
    Rule,
    RuleRef,
    SDKDSLError,
    SDKStore,
    SDKStoreError,
    compile_schema_from_classes,
    vars as sdk_vars,
)
from factpy.domains.ecss.sdk_helpers import (
    apply_ecss_vcd_schema,
    make_ecss_requirement_ref,
    write_ecss_requirement_bundle,
)
from factpy.sdk.ingest import CONVENTION_META_KEYS, SENSITIVE_SEMANTIC_META_KEYS
from factpy.service.app_v1 import app
from factpy.service.runtime_v1 import (
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
from tests._test_helpers import User, _schema_ir, _seed_users_for_syntax_matrix


class Phase3ContractsV1Tests(unittest.TestCase):
    def test_entity_docstring_is_emitted_as_entity_description(self) -> None:
        class Account(Entity):
            """Account record used by docs/LLM description."""

            account_id: str = Identity(primary_key=True)

        schema_ir = compile_schema_from_classes([Account])
        entity = schema_ir["entities"][0]
        self.assertEqual(entity.get("description"), "Account record used by docs/LLM description.")

    def test_schema_dsl_entity_docstring_is_mapped_to_description(self) -> None:
        parsed = parse_authoring_schema_dsl_v1(
            """
class Account(Entity):
    \"\"\"Account record description from DSL.\"\"\"
    account_id: str = Identity(primary_key=True)
""".strip()
        )
        self.assertEqual(parsed["entities"][0].get("description"), "Account record description from DSL.")

        schema_ir = compile_authoring_schema_v1(parsed)
        self.assertEqual(schema_ir["entities"][0].get("description"), "Account record description from DSL.")

    def test_head_primary_key_implicit_and_strict_compile_errors(self) -> None:
        schema_ir = _schema_ir()
        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.user_name",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "pred_ref",
                    "entity_type": "User",
                    "field": "name",
                    "kwargs": {
                        "locale": "$locale",
                        "name": "$name",
                    },
                },
                "where": [
                    ("pred", "user:name", ["$u", "$name"]),
                    ("pred", "user:tag", ["$u", "$tag"]),
                ],
            },
            schema_ir=schema_ir,
        )
        self.assertEqual(payload["head_vars"], ["$u", "$name"])

        with self.assertRaises(AuthoringDerivationCompileError) as ctx_primary_in_head:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.bad_primary_in_head",
                    "head": {
                        "kind": "head_call",
                        "callee_kind": "pred_ref",
                        "entity_type": "User",
                        "field": "name",
                        "kwargs": {
                            "user_id": "$uid",
                            "locale": "$locale",
                            "name": "$name",
                        },
                    },
                    "where": [("pred", "user:name", ["$u", "$name"])],
                },
                schema_ir=schema_ir,
            )
        self.assertEqual(ctx_primary_in_head.exception.path, "$.head.kwargs")
        self.assertIn("must not include primary_key", str(ctx_primary_in_head.exception))

        with self.assertRaises(AuthoringDerivationCompileError) as ctx_no_binding:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.no_binding",
                    "head": {
                        "kind": "head_call",
                        "callee_kind": "pred_ref",
                        "entity_type": "User",
                        "field": "name",
                        "kwargs": {
                            "locale": "$locale",
                            "name": "$name",
                        },
                    },
                    "where": [("eq", "$x", "$y")],
                },
                schema_ir=schema_ir,
            )
        self.assertEqual(ctx_no_binding.exception.path, "$.where")
        self.assertIn("where must bind one User entity variable", str(ctx_no_binding.exception))

        with self.assertRaises(AuthoringDerivationCompileError) as ctx_ambiguous_binding:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.ambiguous_binding",
                    "head": {
                        "kind": "head_call",
                        "callee_kind": "pred_ref",
                        "entity_type": "User",
                        "field": "name",
                        "kwargs": {
                            "locale": "$locale",
                            "name": "$name",
                        },
                    },
                    "where": [
                        ("pred", "user:name", ["$u1", "$name1"]),
                        ("pred", "user:tag", ["$u2", "$tag"]),
                    ],
                },
                schema_ir=schema_ir,
            )
        self.assertEqual(ctx_ambiguous_binding.exception.path, "$.where")
        self.assertIn("multiple User entity variables", str(ctx_ambiguous_binding.exception))

    def test_cross_coordinate_requires_explicit_non_primary_identity(self) -> None:
        schema_ir = _schema_ir()
        with self.assertRaises(AuthoringDerivationCompileError) as ctx_missing_locale:
            compile_authoring_derivation_v1(
                {
                    "derivation_id": "drv.missing_locale",
                    "head": {
                        "kind": "head_call",
                        "callee_kind": "pred_ref",
                        "entity_type": "User",
                        "field": "name",
                        "kwargs": {
                            "name": "$name",
                        },
                    },
                    "where": [("pred", "user:name", ["$u", "$name"])],
                },
                schema_ir=schema_ir,
            )
        self.assertEqual(ctx_missing_locale.exception.path, "$.head.kwargs")
        self.assertIn("missing non-primary identity fields: locale", str(ctx_missing_locale.exception))

        payload = compile_authoring_derivation_v1(
            {
                "derivation_id": "drv.with_locale",
                "head": {
                    "kind": "head_call",
                    "callee_kind": "pred_ref",
                    "entity_type": "User",
                    "field": "name",
                    "kwargs": {
                        "locale": "$target_locale",
                        "name": "$name",
                    },
                },
                "where": [("pred", "user:name", ["$u", "$name"])],
            },
            schema_ir=schema_ir,
        )
        self.assertEqual(payload["head_vars"], ["$u", "$name"])

        parsed_pk_join = parse_authoring_derivation_dsl_v1(
            """
Derivation(
  derivation_id="drv.pk_join",
  head=User.name(locale=loc, name=name),
  where=[
    User(u1),
    User(u2),
    u1.user_id == u2.user_id,
    u1.name == name,
    u1.locale == loc,
  ],
)
""".strip()
        )
        lowered_where = lower_blueprint_where_sugar_with_schema_v1(
            parsed_pk_join["where"],
            schema_ir=schema_ir,
            path="$.where",
        )
        expected_where = [
            ("pred", "User:exists", ["$u1"]),
            ("pred", "User:exists", ["$u2"]),
            ("pred", "user:user_id", ["$u1", "$__pk_0"]),
            ("pred", "user:user_id", ["$u2", "$__pk_0"]),
            ("pred", "user:name", ["$u1", "$name"]),
            ("pred", "user:locale", ["$u1", "$loc"]),
        ]
        self.assertEqual(lowered_where, expected_where)
        compiled_pk_join = compile_authoring_derivation_v1(parsed_pk_join, schema_ir=schema_ir)
        self.assertEqual(compiled_pk_join["head_vars"], ["$u1", "$name"])

        parsed_non_primary_join = parse_authoring_derivation_dsl_v1(
            """
Derivation(
  derivation_id="drv.non_pk_join",
  head=User.name(locale=loc, name=name),
  where=[
    User(u1),
    User(u2),
    u1.locale == u2.locale,
    u1.name == name,
    u1.locale == loc,
  ],
)
""".strip()
        )
        with self.assertRaises(WhereSchemaLoweringError) as ctx_non_primary_join:
            lower_blueprint_where_sugar_with_schema_v1(
                parsed_non_primary_join["where"],
                schema_ir=schema_ir,
                path="$.where",
            )
        self.assertIn("'locale' is not a primary_key field of User", str(ctx_non_primary_join.exception))
        self.assertIn("requires primary_key field 'user_id'", str(ctx_non_primary_join.exception))

    def test_identity_field_write_raises_in_batch_and_editor(self) -> None:
        sdk = SDKStore([User])
        with sdk.batch() as tx:
            user = tx.entity(User, user_id="u-1", locale="zh")
            user.name.set("Alice")
            with self.assertRaises(SDKStoreError) as ctx_set:
                user.user_id.set("u-2")
            self.assertIn("immutable", str(ctx_set.exception))
            with self.assertRaises(SDKStoreError) as ctx_add:
                user.locale.add("en")
            self.assertIn("immutable", str(ctx_add.exception))
            with self.assertRaises(SDKStoreError) as ctx_retract:
                user.user_id.retract("asrt-1")
            self.assertIn("immutable", str(ctx_retract.exception))
            tx.commit(objects=[user])

        ref = sdk.ref(User, user_id="u-1", locale="zh")
        facts = project_view_facts(sdk.ledger, sdk.schema_ir)
        self.assertIn((ref, "u-1"), facts.get("user:user_id", []))
        self.assertIn((ref, "zh"), facts.get("user:locale", []))

        with sdk.edit(User, user_id="u-1", locale="zh") as editor:
            with self.assertRaises(SDKStoreError) as ctx_editor_set:
                editor.user_id.set("u-3")
            self.assertIn("immutable", str(ctx_editor_set.exception))
            with self.assertRaises(SDKStoreError) as ctx_editor_add:
                editor.locale.add("en")
            self.assertIn("immutable", str(ctx_editor_add.exception))
            with self.assertRaises(SDKStoreError) as ctx_editor_retract:
                editor.user_id.retract("asrt-1")
            self.assertIn("immutable", str(ctx_editor_retract.exception))

    def test_python_where_planner_prioritizes_primary_key_shared_variable(self) -> None:
        body = [
            ("pred", "User:exists", ["$u1"]),
            ("pred", "User:exists", ["$u2"]),
            ("pred", "user:user_id", ["$u1", "$__pk_0"]),
            ("pred", "user:user_id", ["$u2", "$__pk_0"]),
        ]
        planned = _plan_body_atoms(body, ast_gate_on=True)
        self.assertEqual(
            planned,
            [
                ("pred", "User:exists", ["$u1"]),
                ("pred", "user:user_id", ["$u1", "$__pk_0"]),
                ("pred", "user:user_id", ["$u2", "$__pk_0"]),
                ("pred", "User:exists", ["$u2"]),
            ],
        )

    def test_python_where_planner_keeps_original_order_without_system_pk_vars(self) -> None:
        body = [
            ("pred", "User:exists", ["$u1"]),
            ("pred", "User:exists", ["$u2"]),
            ("pred", "user:locale", ["$u1", "$loc"]),
            ("pred", "user:name", ["$u2", "$name"]),
        ]
        planned = _plan_body_atoms(body, ast_gate_on=True)
        self.assertEqual(planned, body)

    def test_cross_coordinate_join_engine_matches_python(self) -> None:
        from factpy.adapters.souffle.runner import find_souffle_binary

        if find_souffle_binary() is None:
            self.skipTest("souffle binary is unavailable; skipping engine parity test")

        import factpy.adapters.souffle  # noqa: F401

        sdk = SDKStore([User])
        with sdk.batch() as tx:
            u1_zh = tx.entity(User, user_id="u-1", locale="zh")
            u1_zh.name.set("AliceZH")
            u1_en = tx.entity(User, user_id="u-1", locale="en")
            u1_en.name.set("AliceEN")
            u2_zh = tx.entity(User, user_id="u-2", locale="zh")
            u2_zh.name.set("BobZH")
            tx.commit(objects=[u1_zh, u1_en, u2_zh])

        parsed = parse_authoring_derivation_dsl_v1(
            """
Derivation(
  derivation_id="drv.pk_join_engine",
  head=User.name(locale=loc_zh, name=name_zh),
  where=[
    User(u_zh),
    User(u_en),
    u_zh.user_id == u_en.user_id,
    u_zh.locale == "zh",
    u_en.locale == "en",
    u_zh.locale == loc_zh,
    u_zh.name == name_zh,
    u_en.name == en_name,
  ],
)
""".strip()
        )
        compiled = compile_authoring_derivation_v1(parsed, schema_ir=sdk.schema_ir)
        python_candidates = sdk.evaluate(compiled, mode="native")
        engine_candidates = sdk.evaluate(compiled, mode="souffle")

        python_rows = sorted(
            [(cand.target, cand.payload["terms"]) for cand in python_candidates],
            key=lambda row: (row[0], str(row[1])),
        )
        engine_rows = sorted(
            [(cand.target, cand.payload["terms"]) for cand in engine_candidates],
            key=lambda row: (row[0], str(row[1])),
        )
        self.assertEqual(engine_rows, python_rows)
        self.assertEqual(len(engine_candidates), 1)
        self.assertEqual(engine_candidates[0].payload["terms"][1]["value"], "AliceZH")

    def test_temporal_meta_fields_are_persisted_on_write(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="u-meta", locale="zh")
        asrt_id = sdk.set(
            User.name,
            ref,
            "MetaAlice",
            meta={
                "valid_from": "2024-01-01",
                "valid_to": "2024-12-31",
                "version": 3,
                "source": "demo",
            },
        )
        meta_rows = {(row.key, row.kind, row.value) for row in sdk.ledger.find_meta(asrt_id=asrt_id)}
        self.assertIn(("valid_from", "str", "2024-01-01"), meta_rows)
        self.assertIn(("valid_to", "str", "2024-12-31"), meta_rows)
        self.assertIn(("version", "int", 3), meta_rows)

    def test_idempotency_key_distinguishes_temporal_material(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="u-idemp", locale="zh")
        base_meta = {
            "source": "hr",
            "source_loc": "file://batch.csv#1",
            "trace_id": "t-001",
        }
        asrt_v1 = sdk.set(
            User.name,
            ref,
            "Alice",
            meta={**base_meta, "valid_from": "2024-01-01", "valid_to": "2024-12-31", "version": 1},
        )
        asrt_v2 = sdk.set(
            User.name,
            ref,
            "Alice",
            meta={**base_meta, "valid_from": "2025-01-01", "valid_to": "2025-12-31", "version": 1},
        )
        self.assertNotEqual(asrt_v1, asrt_v2)

        asrt_v2_retry = sdk.set(
            User.name,
            ref,
            "Alice",
            meta={**base_meta, "valid_from": "2025-01-01", "valid_to": "2025-12-31", "version": 1},
        )
        self.assertEqual(asrt_v2_retry, asrt_v2)

        asrt_v3 = sdk.set(
            User.name,
            ref,
            "Alice",
            meta={**base_meta, "valid_from": "2025-01-01", "valid_to": "2025-12-31", "version": 2},
        )
        self.assertNotEqual(asrt_v3, asrt_v2)

    def test_field_assertions_temporal_views_filter_active_records(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="u-view", locale="zh")

        sdk.add(User.tag, ref, "legacy-no-temporal")
        asrt_open = sdk.add(
            User.tag,
            ref,
            "open-window",
            meta={"valid_from": "2024-01-01", "version": 1},
        )
        asrt_closes_at_t = sdk.add(
            User.tag,
            ref,
            "closes-at-t",
            meta={"valid_from": "2024-01-01", "valid_to": "2024-03-01", "version": 1},
        )
        asrt_revoked = sdk.add(
            User.tag,
            ref,
            "revoked-window",
            meta={"valid_from": "2024-01-01", "valid_to": "2024-12-31", "version": 2},
        )
        sdk.retract(asrt_revoked)
        asrt_future = sdk.add(
            User.tag,
            ref,
            "future-window",
            meta={"valid_from": "2025-01-01", "version": "v3"},
        )

        snap = sdk.get(User, user_id="u-view", locale="zh")
        self.assertIsNotNone(snap)
        assert snap is not None  # for type checker

        at_feb = {row.asrt_id for row in snap.assertions.tag.at("2024-02-01")}
        self.assertEqual(at_feb, {asrt_open, asrt_closes_at_t})

        at_mar = {row.asrt_id for row in snap.assertions.tag.at("2024-03-01")}
        self.assertEqual(at_mar, {asrt_open})

        self.assertNotIn(asrt_revoked, at_feb)
        self.assertNotIn(asrt_future, at_feb)

        version_int = {row.asrt_id for row in snap.assertions.tag.version(1)}
        self.assertEqual(version_int, {asrt_open, asrt_closes_at_t})

        version_str = {row.asrt_id for row in snap.assertions.tag.version("v3")}
        self.assertEqual(version_str, {asrt_future})

        version_revoked = {row.asrt_id for row in snap.assertions.tag.version(2)}
        self.assertEqual(version_revoked, set())

    def test_field_assertions_temporal_views_validate_inputs(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="u-view-validate", locale="zh")
        sdk.add(
            User.tag,
            ref,
            "broken-format",
            meta={"valid_from": "03/01/2024", "version": 1},
        )
        snap = sdk.get(User, user_id="u-view-validate", locale="zh")
        self.assertIsNotNone(snap)
        assert snap is not None

        with self.assertRaises(SDKStoreError) as ctx_bad_t:
            snap.assertions.tag.at("03/01/2024")
        self.assertIn("expects ISO 8601 string", str(ctx_bad_t.exception))

        with self.assertRaises(SDKStoreError) as ctx_bad_meta:
            snap.assertions.tag.at("2024-03-01")
        self.assertIn("invalid meta.valid_from", str(ctx_bad_meta.exception))

        with self.assertRaises(SDKStoreError) as ctx_bad_version:
            snap.assertions.tag.version(True)
        self.assertIn("expects string|int version selector", str(ctx_bad_version.exception))

    def test_rule_dsl_syntax_matrix_ruleref_not_or(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u") as (u,):
            vip_rule = Rule(
                id="q.vip",
                version="1.0.0",
                select=[u],
                where=[Pred("user:tag", u, "vip")],
                expose=True,
            )
            hidden_rule = Rule(
                id="q.hidden",
                version="1.0.0",
                select=[u],
                where=[Pred("user:tag", u, "vip")],
                expose=False,
            )
            non_vip_rule = Rule(
                id="q.non_vip",
                version="1.0.0",
                select=[u],
                where=[
                    User(u),
                    Not([Pred("user:tag", u, "vip")]),
                ],
            )
            vip_or_staff_rule = Rule(
                id="q.vip_or_staff",
                version="1.0.0",
                select=[u],
                where=[
                    [Pred("user:tag", u, "vip")],
                    [Pred("user:tag", u, "staff")],
                ],
            )
            bad_ref_rule = Rule(
                id="q.bad_ref",
                version="1.0.0",
                select=[u],
                where=[RuleRef(hidden_rule)(u)],
            )
            bad_not_ruleref_rule = Rule(
                id="q.bad_not_ruleref",
                version="1.0.0",
                select=[u],
                where=[User(u), Not([RuleRef(vip_rule)(u)])],
            )

        vip_rows = sdk.run(vip_rule, row_format="dict")
        self.assertEqual({row["u"] for row in vip_rows}, {refs["u1"]})

        non_vip_rows = sdk.run(non_vip_rule, row_format="dict")
        self.assertEqual({row["u"] for row in non_vip_rows}, {refs["u2"], refs["u3"]})

        vip_or_staff_rows = sdk.run(vip_or_staff_rule, row_format="dict")
        self.assertEqual({row["u"] for row in vip_or_staff_rows}, {refs["u1"], refs["u2"]})

        with self.assertRaises(RuleCompileError) as ctx_bad_ref:
            sdk.run(bad_ref_rule, row_format="dict")
        self.assertIn("expose=True", str(ctx_bad_ref.exception))

        with self.assertRaises(SDKStoreError) as ctx_bad_not_ruleref:
            sdk.run(bad_not_ruleref_rule, row_format="dict")
        self.assertIn("RuleRefAtom is not allowed in not body", str(ctx_bad_not_ruleref.exception))

    def test_run_rule_with_trace_captures_readback_and_memo_hits(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "t1", "t2") as (u, t1, t2):
            tagged_rule = Rule(
                id="q.tagged",
                version="1.0.0",
                select=[u, t1],
                where=[Pred("user:tag", u, t1)],
                expose=True,
            )
            tagged_pair_rule = Rule(
                id="q.tagged_pair",
                version="1.0.0",
                select=[u, t1, t2],
                where=[RuleRef(tagged_rule)(u, t1), RuleRef(tagged_rule)(u, t2)],
            )

        compiled = sdk._compile_rule_input(tagged_pair_rule)
        rule_spec = RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )
        registry = RuleRegistry()
        sdk._register_rule_dependencies(registry, tagged_pair_rule)

        result = run_rule_with_trace(sdk.store, rule_spec, registry)
        self.assertTrue(result.rule_run_id)
        self.assertEqual(
            set(result.rows),
            {
                (refs["u1"], "vip", "vip"),
                (refs["u2"], "staff", "staff"),
            },
        )

        trace = sdk.store.explain_rule_trace(result.rule_run_id)
        self.assertIsNotNone(trace)
        assert trace is not None
        self.assertEqual(trace["root_rule"], {"rule_id": "q.tagged_pair", "version": "1.0.0"})
        self.assertEqual(trace["select_vars"], ["$u", "$t1", "$t2"])
        self.assertEqual(sdk.store.explain_rule_trace("missing-rule-run"), None)

        root_invocation = next(inv for inv in trace["invocations"] if inv["rule"]["rule_id"] == "q.tagged_pair")
        self.assertEqual(root_invocation["parent_invocation_id"], None)
        self.assertFalse(root_invocation["memo_hit"])
        self.assertEqual(root_invocation["original_where"][0][0], "ruleref")
        self.assertEqual(root_invocation["rewritten_where"][0][0], "pred")
        self.assertTrue(root_invocation["rewritten_where"][0][1].startswith("__rule_ref__q_tagged__1_0_0"))

        tagged_invocations = [inv for inv in trace["invocations"] if inv["rule"]["rule_id"] == "q.tagged"]
        self.assertEqual(len(tagged_invocations), 2)
        self.assertEqual(sorted(inv["memo_hit"] for inv in tagged_invocations), [False, True])

        primary_invocation = next(inv for inv in tagged_invocations if inv["memo_hit"] is False)
        memo_invocation = next(inv for inv in tagged_invocations if inv["memo_hit"] is True)
        self.assertEqual(memo_invocation["memo_source_invocation_id"], primary_invocation["invocation_id"])
        self.assertTrue(any(witness["asrt_ids"] for witness in primary_invocation["pred_witnesses"]))
        self.assertEqual(
            root_invocation["ruleref_links"],
            [
                {
                    "ruleref_atom_key": "b0.a0:ruleref",
                    "child_invocation_id": primary_invocation["invocation_id"],
                },
                {
                    "ruleref_atom_key": "b0.a1:ruleref",
                    "child_invocation_id": memo_invocation["invocation_id"],
                },
            ],
        )

    def test_run_rule_with_trace_writes_negated_and_evaluated_statuses(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "nm") as (u, nm):
            filtered_rule = Rule(
                id="q.filtered_non_fact_status",
                version="1.0.0",
                select=[u],
                where=[
                    User(u),
                    u.name == nm,
                    nm == "Alice",
                    Not([Pred("user:tag", u, "staff")]),
                ],
            )

        compiled = sdk._compile_rule_input(filtered_rule)
        rule_spec = RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )
        registry = RuleRegistry()
        sdk._register_rule_dependencies(registry, filtered_rule)

        result = run_rule_with_trace(sdk.store, rule_spec, registry)
        self.assertEqual(result.rows, [(refs["u1"],)])

        trace = sdk.store.explain_rule_trace(result.rule_run_id)
        self.assertIsNotNone(trace)
        assert trace is not None

        root_invocation = next(inv for inv in trace["invocations"] if inv["rule"]["rule_id"] == "q.filtered_non_fact_status")
        statuses = {(step["kind"], step["status"]) for step in root_invocation["non_fact_steps"]}
        self.assertIn(("eq", "evaluated"), statuses)
        self.assertIn(("not", "negated"), statuses)
        self.assertNotIn(("eq", "satisfied"), statuses)
        self.assertNotIn(("not", "no_match"), statuses)

    def test_query_dsl_syntax_matrix_entity_and_field_head(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "loc", "nm") as (u, loc, nm):
            query = Query(
                head=[
                    User(u),
                    User.name(locale=loc, name=nm),
                ],
                where=[
                    User(u),
                    u.locale == loc,
                    u.name == nm,
                    loc == "zh",
                ],
            )

        rows = sdk.run(query)
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["nm"] for row in rows}, {"Alice", "Carol"})
        self.assertEqual({row["u"].ref for row in rows}, {refs["u1"], refs["u3"]})
        self.assertTrue(all(row["u"].entity_type == "User" for row in rows))

    def test_query_row_format_instance_returns_snapshots(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "loc") as (u, loc):
            query = Query(
                head=User(u),
                where=[
                    User(u),
                    u.locale == loc,
                    loc == "zh",
                ],
            )

        rows = sdk.run(query, row_format="instance")
        self.assertEqual({row.ref for row in rows}, {refs["u1"], refs["u3"]})
        self.assertTrue(all(row.entity_type == "User" for row in rows))

    def test_query_row_format_instance_requires_single_entity_head(self) -> None:
        sdk = SDKStore([User])
        _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "loc", "nm") as (u, loc, nm):
            query = Query(
                head=[User(u), User.name(locale=loc, name=nm)],
                where=[
                    User(u),
                    u.locale == loc,
                    u.name == nm,
                ],
            )

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.run(query, row_format="instance")
        self.assertEqual(ctx.exception.code, "QUERY_INVALID_ROW_FORMAT")
        self.assertIn("requires exactly one Entity(var)", str(ctx.exception))

    def test_query_ruleref_object_dependency_auto_registers(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "tag") as (u, tag):
            tag_rows = Rule(
                id="q.user_tag_rows",
                version="1.0.0",
                select=[u, tag],
                where=[Pred("user:tag", u, tag)],
                expose=True,
            )
            query = Query(
                head=User(u),
                where=[
                    RuleRef(tag_rows)(u, tag),
                    tag == "vip",
                ],
            )

        rows = sdk.run(query, row_format="instance")
        self.assertEqual([row.ref for row in rows], [refs["u1"]])

    def test_query_ruleref_string_requires_explicit_registry(self) -> None:
        sdk = SDKStore([User])
        _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "tag") as (u, tag):
            query = Query(
                head=User(u),
                where=[
                    RuleRef("q.user_tag_rows", version="1.0.0")(u, tag),
                    tag == "vip",
                ],
            )

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.run(query)
        self.assertIn("RuleRef execution requires explicit RuleRegistry", str(ctx.exception))

    def test_derivation_ruleref_object_dependency_auto_registers_and_captures_rule_refs(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "tag") as (u, tag):
            tag_rows = Rule(
                id="q.user_tag_rows",
                version="1.0.0",
                select=[u, tag],
                where=[Pred("user:tag", u, tag)],
                expose=True,
            )
            drv = Derivation(
                id="drv.user_tag_copy",
                version="1.0.0",
                where=[
                    RuleRef(tag_rows)(u, tag),
                    tag == "vip",
                ],
                target="user:tag",
                head_vars=[u, tag],
            )

        candidates = sdk.evaluate(drv, mode="native")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].payload["terms"][0]["value"], refs["u1"])
        support = sdk.store.explain_support(candidates[0].support_digest)
        self.assertIsNotNone(support)
        assert support is not None
        self.assertEqual(support["rule_refs"], ["q.user_tag_rows"])
        self.assertEqual(
            support["rule_ref_edges"],
            [
                {
                    "ruleref_atom_key": "b0.a0:ruleref",
                    "rule_ref_id": "q.user_tag_rows",
                    "rule_ref_version": "1.0.0",
                    "child_support_digest": support["rule_ref_edges"][0]["child_support_digest"],
                    "unresolved_reason": None,
                }
            ],
        )
        self.assertTrue(str(support["rule_ref_edges"][0]["child_support_digest"]).startswith("sha256:"))

    def test_derivation_preview_dto_default_mode_is_native(self) -> None:
        sdk = SDKStore([User])
        _seed_users_for_syntax_matrix(sdk)
        dto = build_derivation_preview_dto(
            store=sdk.store,
            derivation_id="drv.preview.default_mode",
            version="1.0.0",
            target_pred_id="user:name",
            head_vars=["$u", "$name"],
            where=[("pred", "user:name", ["$u", "$name"])],
        )
        self.assertEqual(dto["kind"], "derivation_preview")
        self.assertTrue(dto["ok"])

    def test_query_accepts_branch_wrapper(self) -> None:
        sdk = SDKStore([User])
        _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u") as (u,):
            query = Query(
                head=[User(u)],
                where=[Branch([User(u)])],
            )
        self.assertEqual(query.where_ir, [[("pred", "User:exists", ["$u"])]])

    def test_run_view_return_display_meta_contract(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "nm") as (u, nm):
            rule = Rule(
                id="q.names",
                version="1.0.0",
                select=[u, nm],
                where=[Branch([Pred("user:name", u, nm)])],
            )

        rows = sdk.run(rule, row_format="dict")
        self.assertTrue(rows)
        self.assertNotIn("confidence", rows[0])
        self.assertEqual({row["u"] for row in rows}, {refs["u1"], refs["u2"], refs["u3"]})

        policy = ReadPolicy(confidence_strategy="max")
        rows2, display_meta = sdk.run(
            rule,
            row_format="dict",
            policy=policy,
            return_display_meta=True,
        )
        self.assertEqual(rows2, rows)
        self.assertEqual(len(rows2), len(display_meta))
        self.assertIn("confidence", display_meta[0])
        self.assertIn("confidence_strategy", display_meta[0])
        self.assertIn("source_breakdown", display_meta[0])
        self.assertEqual(display_meta[0]["confidence_strategy"], "max")

        with self.assertRaises(SDKStoreError) as ctx_no_view:
            sdk.run(rule, row_format="dict", return_display_meta=True)
        self.assertIn("requires policy", str(ctx_no_view.exception))

    def test_write_protocol_kind_map_covers_sensitive_and_convention_meta(self) -> None:
        from factpy.core.evidence import write_protocol

        required = set(CONVENTION_META_KEYS) | set(SENSITIVE_SEMANTIC_META_KEYS)
        self.assertTrue(required.issubset(set(write_protocol._KEY_KIND_MAP.keys())))

    def test_derivation_multi_head_syntax_matrix_shared_run_id(self) -> None:
        sdk = SDKStore([User])
        _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "loc", "nm", "tg") as (u, loc, nm, tg):
            drv = Derivation(
                id="drv.multi_head",
                version="1.0.0",
                where=[
                    User(u),
                    u.locale == loc,
                    u.name == nm,
                    u.tag == tg,
                ],
                head=[
                    User.name(locale=loc, name=nm),
                    User.tag(locale=loc, tag=tg),
                ],
            )

        cands = sdk.evaluate(drv, mode="native")
        self.assertGreaterEqual(len(cands), 2)
        self.assertEqual({cand.candidate_kind for cand in cands}, {"fact"})
        self.assertEqual(len({cand.run_id for cand in cands}), 1)
        self.assertEqual({cand.target for cand in cands}, {"user:name", "user:tag"})

    def test_temporal_view_rejection_matrix_sdk_and_runtime(self) -> None:
        sdk = SDKStore([User])
        _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "nm") as (u, nm):
            drv = Derivation(
                id="drv.temporal.reject",
                version="1.0.0",
                where=[("pred", "user:name", [u.token, nm.token])],
                head=User.name(locale="zh", name=nm),
            )

        with self.assertRaises(SDKStoreError) as ctx_sdk:
            sdk.evaluate(drv, temporal_view="active")
        self.assertIn("temporal_view is removed", str(ctx_sdk.exception))

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            view_resp = project_runtime_view_facts(session_id, {"temporal_view": "active"})
            self.assertFalse(view_resp["ok"])
            self.assertEqual(view_resp["errors"][0]["path"], "$.temporal_view")

            rule_resp = run_runtime_rule(
                session_id,
                {
                    "rule": {
                        "rule_id": "r.temporal.reject",
                        "version": "1.0.0",
                        "select": ["$u"],
                        "where": [["pred", "User:exists", ["$u"]]],
                    },
                    "temporal_view": "active",
                },
            )
            self.assertFalse(rule_resp["ok"])
            self.assertEqual(rule_resp["errors"][0]["path"], "$.temporal_view")

            drv_resp = evaluate_runtime_derivation(session_id, {"temporal_view": "active"})
            self.assertFalse(drv_resp["ok"])
            self.assertEqual(drv_resp["errors"][0]["path"], "$.temporal_view")
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_runtime_derivation_ruleref_uses_session_registry_root(self) -> None:
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
                        "inference": {
                            "derivation_id": "drv.runtime.user_tag_copy",
                            "version": "1.0.0",
                            "target": "user:tag",
                            "head_vars": ["$u", "$tag"],
                            "where": [
                                ["ruleref", "q.user_tag_rows", "1.0.0", ["$u", "$tag"]],
                                ["eq", "$tag", "vip"],
                            ],
                        }
                    },
                )
                self.assertTrue(eval_resp["ok"])
                candidate = eval_resp["evaluation"]["candidates"][0]
                self.assertEqual(candidate["payload"]["terms"][0]["value"], refs["u1"])

                explain_support_resp = explain_runtime_support(
                    session_id,
                    {"support_digest": candidate["support_digest"]},
                )
                self.assertTrue(explain_support_resp["ok"])
                self.assertEqual(explain_support_resp["explain"]["rule_refs"], ["q.user_tag_rows"])
                self.assertEqual(
                    explain_support_resp["explain"]["rule_ref_edges"][0]["ruleref_atom_key"],
                    "b0.a0:ruleref",
                )
                self.assertEqual(
                    explain_support_resp["explain"]["rule_ref_edges"][0]["rule_ref_version"],
                    "1.0.0",
                )
                child_support_digest = explain_support_resp["explain"]["rule_ref_edges"][0]["child_support_digest"]
                self.assertTrue(str(child_support_digest).startswith("sha256:"))

                explain_tree_resp = explain_runtime_tree(session_id, {"kind": "candidate", "id": candidate["candidate_id"]})
                self.assertTrue(explain_tree_resp["ok"])
                rule_ref_section = explain_tree_resp["tree"]["root"]["children"][1]
                self.assertEqual(rule_ref_section["node_kind"], "rule_ref_section")
                rule_ref_node = rule_ref_section["children"][0]
                self.assertEqual(rule_ref_node["ruleref_atom_key"], "b0.a0:ruleref")
                self.assertEqual(rule_ref_node["child_support_digest"], child_support_digest)
                referenced_support = rule_ref_node["children"][0]
                self.assertEqual(referenced_support["node_kind"], "referenced_support")
                self.assertEqual(referenced_support["root_result_kind"], "row")
                self.assertEqual(referenced_support["support_digest"], child_support_digest)
            finally:
                close_runtime_session(session_id)
                reset_runtime_sessions_for_tests()

    def test_runtime_derivation_caches_recipe_by_run_id(self) -> None:
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
                    "inference": {
                        "derivation_id": "drv.runtime.user_tag_recipe",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [
                            ["pred", "user:tag", ["$u", "$tag"]],
                            ["eq", "$tag", "vip"],
                        ],
                    }
                },
            )
            self.assertTrue(eval_resp["ok"])
            candidate = eval_resp["evaluation"]["candidates"][0]

            session = _require_session(session_id)
            recipe = session.derivation_recipes[candidate["run_id"]]
            self.assertEqual(recipe.derivation_id, "drv.runtime.user_tag_recipe")
            self.assertEqual(recipe.derivation_version, "1.0.0")
            self.assertEqual(recipe.target_pred_id, "user:tag")
            self.assertEqual(recipe.head_vars, ["$u", "$tag"])
            self.assertEqual(recipe.where, [("pred", "user:tag", ["$u", "$tag"]), ("eq", "$tag", "vip")])
            self.assertIsNone(recipe.registry_root)
            self.assertEqual(candidate["payload"]["terms"][0]["value"], refs["u1"])
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_runtime_derivation_recipe_cache_keeps_distinct_run_ids_for_same_derivation_id(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        reset_runtime_sessions_for_tests()
        open_resp = open_runtime_session({"schema_ir": sdk.schema_ir})
        self.assertTrue(open_resp["ok"])
        session_id = open_resp["session"]["session_id"]
        try:
            first_write = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag",
                    "e_ref": refs["u1"],
                    "rest_terms": [["string", "vip"]],
                },
                kind="add",
            )
            second_write = write_runtime_fact(
                session_id,
                {
                    "pred_id": "user:tag",
                    "e_ref": refs["u2"],
                    "rest_terms": [["string", "staff"]],
                },
                kind="add",
            )
            self.assertTrue(first_write["ok"])
            self.assertTrue(second_write["ok"])
            first_eval = evaluate_runtime_derivation(
                session_id,
                {
                    "inference": {
                        "derivation_id": "drv.runtime.user_tag_reused",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [
                            ["pred", "user:tag", ["$u", "$tag"]],
                            ["eq", "$tag", "staff"],
                        ],
                    }
                },
            )
            self.assertTrue(first_eval["ok"])
            first_run_id = first_eval["evaluation"]["candidates"][0]["run_id"]

            second_eval = evaluate_runtime_derivation(
                session_id,
                {
                    "inference": {
                        "derivation_id": "drv.runtime.user_tag_reused",
                        "version": "1.0.0",
                        "target": "user:tag",
                        "head_vars": ["$u", "$tag"],
                        "where": [
                            ["pred", "user:tag", ["$u", "$tag"]],
                            ["eq", "$tag", "vip"],
                        ],
                    }
                },
            )
            self.assertTrue(second_eval["ok"])
            second_run_id = second_eval["evaluation"]["candidates"][0]["run_id"]

            self.assertNotEqual(first_run_id, second_run_id)
            session = _require_session(session_id)
            self.assertEqual(
                set(session.derivation_recipes.keys()),
                {first_run_id, second_run_id},
            )
            self.assertEqual(
                session.derivation_recipes[first_run_id].where,
                [("pred", "user:tag", ["$u", "$tag"]), ("eq", "$tag", "staff")],
            )
            self.assertEqual(
                session.derivation_recipes[second_run_id].where,
                [("pred", "user:tag", ["$u", "$tag"]), ("eq", "$tag", "vip")],
            )
            self.assertEqual(session.derivation_recipes[first_run_id].derivation_id, "drv.runtime.user_tag_reused")
            self.assertEqual(session.derivation_recipes[second_run_id].derivation_id, "drv.runtime.user_tag_reused")
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

if __name__ == "__main__":
    unittest.main()
