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
from factpy_kernel.ecss import (
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
from factpy_kernel.core.evidence.write_protocol import WriteProtocolError, set_field
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


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


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
        from factpy_kernel.adapters.souffle.runner import find_souffle_binary

        if find_souffle_binary() is None:
            self.skipTest("souffle binary is unavailable; skipping engine parity test")

        import factpy_kernel.adapters.souffle  # noqa: F401

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

    def test_query_rejects_body_confidence(self) -> None:
        sdk = SDKStore([User])
        _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u") as (u,):
            with self.assertRaises(SDKDSLError) as ctx:
                Query(
                    head=[User(u)],
                    where=[Body([User(u)], confidence=0.9)],
                )
        self.assertIn("does not support Body.confidence", str(ctx.exception))

    def test_run_view_return_display_meta_contract(self) -> None:
        sdk = SDKStore([User])
        refs = _seed_users_for_syntax_matrix(sdk)

        with sdk_vars("u", "nm") as (u, nm):
            rule = Rule(
                id="q.names",
                version="1.0.0",
                select=[u, nm],
                where=[Body([Pred("user:name", u, nm)], confidence=0.9)],
            )

        rows = sdk.run(rule, row_format="dict", view="default")
        self.assertTrue(rows)
        self.assertNotIn("confidence", rows[0])
        self.assertEqual({row["u"] for row in rows}, {refs["u1"], refs["u2"], refs["u3"]})

        rows2, display_meta = sdk.run(
            rule,
            row_format="dict",
            view="default",
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
        self.assertIn("requires view", str(ctx_no_view.exception))

    def test_confidence_meta_requires_float_in_range(self) -> None:
        sdk = SDKStore([User])
        ref = sdk.ref(User, user_id="u-conf", locale="zh")

        with self.assertRaises(WriteProtocolError) as ctx_int:
            sdk.set(User.name, ref, "Alice", meta={"confidence": 1})
        self.assertIn("meta[confidence] must be float", str(ctx_int.exception))

        with self.assertRaises(WriteProtocolError) as ctx_range:
            sdk.set(User.name, ref, "Alice", meta={"confidence": 1.5})
        self.assertIn("within (0,1]", str(ctx_range.exception))

    def test_write_protocol_kind_map_covers_sensitive_and_convention_meta(self) -> None:
        from factpy_kernel.core.evidence import write_protocol

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
                        "derivation": {
                            "derivation_id": "drv.runtime.user_tag_copy",
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
                    / f"{quote(candidate_id, safe='')}.html"
                ).read_text(encoding="utf-8")
                self.assertIn("Referenced support", html)
                self.assertIn("rule_ref_edges=1", html)
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
                    f"candidate_evidence/{quote(candidate_id, safe='')}.html",
                    site_manifest["candidate_evidence"],
                )
                page_path = Path(site_dir) / "candidate_evidence" / f"{quote(candidate_id, safe='')}.html"
                self.assertTrue(page_path.exists())
                html = page_path.read_text(encoding="utf-8")
                self.assertIn(candidate_id, html)
                self.assertIn(f"assertions/{quote(asrt_id, safe='')}.html", html)
                self.assertIn("Support", html)
                self.assertIn("Narrative", html)
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
            pred_atom_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_atom_keys,
                {
                    "b0.a0:aml:transaction_event",
                    "b0.a1:aml:transaction_event",
                    "b0.a2:aml:transaction_event",
                    "b0.a5:aml:shared_device_signal",
                    "b0.a6:aml:bo_mismatch_signal",
                    "b0.a7:aml:beneficiary_risk",
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
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{quote(rule_run_id, safe='')}.html"
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
            pred_atom_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_atom_keys,
                {
                    "b0.a0:aml:trigger_evaluation_time",
                    "b0.a1:aml:windowed_structuring_signal",
                    "b0.a4:aml:high_risk_outflow_signal",
                    "b0.a5:aml:shared_device_signal",
                    "b0.a6:aml:bo_mismatch_signal",
                    "b0.a7:aml:trigger_score_ppm",
                    "b0.a8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertEqual(len(invocation["non_fact_steps"]), 3)
            self.assertEqual({step["kind"] for step in invocation["non_fact_steps"]}, {"le", "ge"})

            non_fact_by_key = {step["step_key"]: step for step in invocation["non_fact_steps"]}
            self.assertEqual(sorted(non_fact_by_key.keys()), ["b0.a2:le", "b0.a3:le", "b0.a9:ge"])
            lower_binding = dict(dict(non_fact_by_key["b0.a2:le"]["details"])["binding"])
            upper_binding = dict(dict(non_fact_by_key["b0.a3:le"]["details"])["binding"])
            threshold_binding = dict(dict(non_fact_by_key["b0.a9:ge"]["details"])["binding"])
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
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{quote(rule_run_id, safe='')}.html"
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
            pred_atom_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_atom_keys,
                {
                    "b0.a0:aml:trigger_evaluation_time",
                    "b0.a1:aml:windowed_structuring_signal",
                    "b0.a4:aml:high_risk_outflow_signal",
                    "b0.a5:aml:shared_device_signal",
                    "b0.a6:aml:bo_mismatch_signal",
                    "b0.a7:aml:trigger_score_ppm",
                    "b0.a8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertFalse(any(key.endswith(":aml:transaction_event") for key in pred_atom_keys))
            self.assertFalse(any(key.endswith(":aml:transaction_timestamp") for key in pred_atom_keys))
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
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{quote(rule_run_id, safe='')}.html"
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
                        assertion_page = Path(out_dir) / "assertions" / f"{quote(assertion_ids[key], safe='')}.html"
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
            pred_atom_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_atom_keys,
                {
                    "b0.a0:aml:trigger_evaluation_time",
                    "b0.a1:aml:windowed_structuring_signal",
                    "b0.a4:aml:high_risk_outflow_signal",
                    "b0.a5:aml:shared_device_signal",
                    "b0.a6:aml:bo_mismatch_signal",
                    "b0.a7:aml:trigger_score_ppm",
                    "b0.a8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertFalse(any(key.endswith(":aml:transaction_event") for key in pred_atom_keys))
            self.assertFalse(any(key.endswith(":aml:transaction_timestamp") for key in pred_atom_keys))
            self.assertFalse(any(key.endswith(":aml:beneficiary_risk") for key in pred_atom_keys))
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
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{quote(rule_run_id, safe='')}.html"
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
                        assertion_page = Path(out_dir) / "assertions" / f"{quote(assertion_ids[key], safe='')}.html"
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
            pred_atom_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_atom_keys,
                {
                    "b0.a0:aml:trigger_evaluation_time",
                    "b0.a1:aml:windowed_structuring_signal",
                    "b0.a4:aml:high_risk_outflow_signal",
                    "b0.a5:aml:shared_device_signal",
                    "b0.a6:aml:bo_mismatch_signal",
                    "b0.a7:aml:trigger_score_ppm",
                    "b0.a8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertFalse(any(":form:" in key for key in pred_atom_keys))
            self.assertFalse(any(key.endswith(":aml:beneficiary_risk") for key in pred_atom_keys))
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
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{quote(rule_run_id, safe='')}.html"
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
                        assertion_page = Path(out_dir) / "assertions" / f"{quote(assertion_ids[key], safe='')}.html"
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
            pred_atom_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_atom_keys,
                {
                    "b0.a0:aml:trigger_evaluation_time",
                    "b0.a1:aml:windowed_structuring_signal",
                    "b0.a4:aml:high_risk_outflow_signal",
                    "b0.a5:aml:shared_device_signal",
                    "b0.a6:aml:bo_mismatch_signal",
                    "b0.a7:aml:trigger_score_ppm",
                    "b0.a8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertFalse(any(":note:" in key for key in pred_atom_keys))
            self.assertFalse(any(key.endswith(":aml:beneficiary_risk") for key in pred_atom_keys))
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
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{quote(rule_run_id, safe='')}.html"
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
                    self.assertNotIn("confirmed", html.lower())
                    self.assertNotIn("certain", html.lower())
                    self.assertNotIn("verified", html.lower())
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
                        assertion_page = Path(out_dir) / "assertions" / f"{quote(assertion_ids[key], safe='')}.html"
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
            pred_atom_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_atom_keys,
                {
                    "b0.a0:aml:trigger_evaluation_time",
                    "b0.a1:aml:windowed_structuring_signal",
                    "b0.a4:aml:high_risk_outflow_signal",
                    "b0.a5:aml:shared_device_signal",
                    "b0.a6:aml:bo_mismatch_signal",
                    "b0.a7:aml:trigger_score_ppm",
                    "b0.a8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertFalse(any(":notes:" in key for key in pred_atom_keys))
            self.assertFalse(any(key.endswith(":aml:beneficiary_risk") for key in pred_atom_keys))
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
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{quote(rule_run_id, safe='')}.html"
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
                    lowered_html = html.lower()
                    self.assertNotIn("confirmed", lowered_html)
                    self.assertNotIn("certain", lowered_html)
                    self.assertNotIn("verified", lowered_html)
                    self.assertNotIn("synthesis", lowered_html)
                    self.assertNotIn("comprehensive analysis", lowered_html)
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
                        assertion_page = Path(out_dir) / "assertions" / f"{quote(assertion_ids[key], safe='')}.html"
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
            pred_atom_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_atom_keys,
                {
                    "b0.a0:aml:trigger_evaluation_time",
                    "b0.a1:aml:windowed_structuring_signal",
                    "b0.a4:aml:high_risk_outflow_signal",
                    "b0.a5:aml:shared_device_signal",
                    "b0.a6:aml:bo_mismatch_signal",
                    "b0.a7:aml:trigger_score_ppm",
                    "b0.a8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertEqual(len(invocation["pred_witnesses"]), 7)
            self.assertEqual(len(invocation["non_fact_steps"]), 3)
            self.assertFalse(any(":notes:" in key for key in pred_atom_keys))

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
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{quote(rule_run_id, safe='')}.html"
                    self.assertTrue(rule_trace_page.exists())
                    html = rule_trace_page.read_text(encoding="utf-8")
                    self.assertIn("q.conflicting_multi_note_evidence_walkthrough", html)
                    self.assertIn(
                        "Predicate aml:high_risk_outflow_signal was witnessed by 1 assertion(s) across 1 invocation(s).",
                        html,
                    )
                    self.assertNotIn("Predicate notes:beneficiary_risk_extracted was witnessed", html)
                    lowered_html = html.lower()
                    self.assertNotIn("confirmed", lowered_html)
                    self.assertNotIn("certain", lowered_html)
                    self.assertNotIn("verified", lowered_html)
                    self.assertNotIn("resolved", lowered_html)
                    self.assertNotIn("resolution", lowered_html)
                    self.assertNotIn("judgment", lowered_html)
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
                        assertion_page = Path(out_dir) / "assertions" / f"{quote(assertion_ids[key], safe='')}.html"
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
            pred_atom_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_atom_keys,
                {
                    "b0.a0:aml:trigger_evaluation_time",
                    "b0.a1:aml:windowed_structuring_signal",
                    "b0.a4:aml:high_risk_outflow_signal",
                    "b0.a5:aml:shared_device_signal",
                    "b0.a6:aml:bo_mismatch_signal",
                    "b0.a7:aml:trigger_score_ppm",
                    "b0.a8:aml:trigger_score_threshold_ppm",
                },
            )
            self.assertEqual(len(invocation["pred_witnesses"]), 7)
            self.assertEqual(len(invocation["non_fact_steps"]), 3)
            self.assertFalse(any(key.endswith(":aml:transaction_event") for key in pred_atom_keys))
            self.assertFalse(any(":form:" in key for key in pred_atom_keys))
            self.assertFalse(any(":note:" in key for key in pred_atom_keys))

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
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{quote(rule_run_id, safe='')}.html"
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
                        assertion_page = Path(out_dir) / "assertions" / f"{quote(assertion_ids[key], safe='')}.html"
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

            pred_atom_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_atom_keys,
                {
                    "b0.a0:process:high_high_temperature",
                    "b0.a1:process:temperature_shutdown_threshold",
                    "b0.a3:process:high_high_pressure",
                    "b0.a4:process:pressure_shutdown_threshold",
                    "b0.a6:process:shutdown_alarm_active",
                    "b0.a7:process:shutdown_interlock_armed",
                    "b0.a8:process:manual_override_cleared",
                },
            )

            non_fact_by_key = {step["step_key"]: step for step in invocation["non_fact_steps"]}
            self.assertEqual(sorted(non_fact_by_key.keys()), ["b0.a2:ge", "b0.a5:ge"])
            temp_binding = dict(dict(non_fact_by_key["b0.a2:ge"]["details"])["binding"])
            pressure_binding = dict(dict(non_fact_by_key["b0.a5:ge"]["details"])["binding"])
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
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{quote(rule_run_id, safe='')}.html"
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
                        assertion_page = Path(out_dir) / "assertions" / f"{quote(assertion_ids[key], safe='')}.html"
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
            pred_atom_keys = {witness["pred_atom_key"] for witness in invocation["pred_witnesses"]}
            self.assertEqual(
                pred_atom_keys,
                {
                    "b0.a0:clinical:mild_fever_signal",
                    "b0.a1:clinical:mild_tachycardia_signal",
                    "b0.a2:clinical:mild_tachypnea_signal",
                    "b0.a3:clinical:mild_hypotension_signal",
                    "b0.a4:clinical:abnormal_indicator_count",
                    "b0.a5:clinical:deterioration_count_threshold",
                },
            )
            self.assertFalse(any(key.endswith(":clinical:normal_oxygen_saturation") for key in pred_atom_keys))
            self.assertFalse(any(key.endswith(":clinical:normal_lactate") for key in pred_atom_keys))
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
                    rule_trace_page = Path(out_dir) / "rule_traces" / f"{quote(rule_run_id, safe='')}.html"
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
                        assertion_page = Path(out_dir) / "assertions" / f"{quote(assertion_ids[key], safe='')}.html"
                        self.assertTrue(assertion_page.exists())
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

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
            register_engine_evaluator(None, "souffle")

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
                    / f"{quote(engine_candidate['candidate_id'], safe='')}.html"
                ).read_text(encoding="utf-8")
                self.assertIn("degraded_support", engine_page)
                self.assertIn(ENGINE_NO_WITNESS_KIND, engine_page)
                self.assertIn("witness_status=degraded", engine_page)
                self.assertIn(runtime_narrative["headline"], engine_page)
                self.assertNotIn("child_support_digest", engine_page)
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()
            register_engine_evaluator(None, "souffle")

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
                self.assertIn("Narrative", candidate_html_http.text)
                self.assertIn("predicate_witness_group", candidate_html_http.text)

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
        candidates = sdk.evaluate(drv, mode="native")
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

        candidates = sdk.evaluate(drv, mode="native")
        self.assertTrue(candidates)
        for candidate in candidates:
            digest = sdk.store.get_candidate_support_digest(candidate.candidate_id)
            support_kind = sdk.store.get_candidate_support_kind(candidate.candidate_id)
            self.assertEqual(digest, candidate.support_digest)
            self.assertEqual(support_kind, "native_binding_v1")
            self.assertIsNotNone(sdk.store.explain_support(digest))

        self.assertIsNone(sdk.store.get_candidate_support_digest("missing-candidate-id"))
        self.assertIsNone(sdk.store.get_candidate_support_kind("missing-candidate-id"))

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
            trace_page_rel = f"rule_traces/{quote(trace_result.rule_run_id, safe='')}.html"
            self.assertEqual(site_manifest["rule_traces"], [trace_page_rel])
            witness_asrt_ids = sorted(
                {
                    asrt_id
                    for witness in live_invocation["pred_witnesses"]
                    for asrt_id in witness["asrt_ids"]
                }
            )
            for asrt_id in witness_asrt_ids:
                assertion_page = Path(site_dir) / "assertions" / f"{quote(asrt_id, safe='')}.html"
                self.assertTrue(assertion_page.exists())

            sample_assertion_html = (
                Path(site_dir) / "assertions" / f"{quote(collision_threshold_asrt_id, safe='')}.html"
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
            self.assertIn(f"../assertions/{quote(collision_threshold_asrt_id, safe='')}.html", trace_page_html)

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

    def test_support_artifact_from_dict_round_trip_ignores_envelope_and_restores_bytes(self) -> None:
        row = {
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
            "non_fact_steps": [
                {
                    "step_key": "b0.a1:eq",
                    "kind": "eq",
                    "status": "ok",
                    "details": [["payload", {"__bytes_hex__": "6162"}]],
                }
            ],
            "rule_refs": ["r.1"],
            "unexpected": "ignored",
        }

        artifact = support_artifact_from_dict(row)

        self.assertEqual(artifact.kind, "native_binding_v1")
        self.assertEqual(artifact.root_result_kind, "fact")
        self.assertEqual(artifact.binding_items, (("$blob", b"\x00\xff"), ("$pair", [1, 2])))
        self.assertEqual(artifact.pred_witnesses[0].pred_atom_key, "b0.a0:user:tag")
        self.assertEqual(artifact.non_fact_steps[0].details, (("payload", b"ab"),))
        self.assertEqual(
            support_artifact_to_dict(artifact),
            {
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
                "non_fact_steps": [
                    {
                        "step_key": "b0.a1:eq",
                        "kind": "eq",
                        "status": "ok",
                        "details": [["payload", {"__bytes_hex__": "6162"}]],
                    }
                ],
                "rule_refs": ["r.1"],
                "rule_ref_edges": [],
            },
        )

    def test_runtime_tree_renders_unresolved_rule_ref_edge_terminal_node(self) -> None:
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
            support_digest = "sha256:" + ("cd" * 32)
            artifact = support_artifact_from_dict(
                {
                    "support_digest": support_digest,
                    "kind": "native_binding_v1",
                    "root_result_kind": "fact",
                    "binding": [["$tag", "vip"], ["$u", refs["u1"]]],
                    "pred_witnesses": [
                        {
                            "pred_atom_key": "b0.a0:user:tag",
                            "asrt_ids": [asrt_id],
                        }
                    ],
                    "non_fact_steps": [
                        {
                            "step_key": "b0.a1:ruleref",
                            "kind": "ruleref",
                            "status": "satisfied",
                            "details": [],
                        }
                    ],
                    "rule_refs": ["q.child_rule"],
                    "rule_ref_edges": [
                        {
                            "ruleref_atom_key": "b0.a1:ruleref",
                            "rule_ref_id": "q.child_rule",
                            "rule_ref_version": "1.0.0",
                            "child_support_digest": None,
                            "unresolved_reason": "child_support_unavailable",
                        }
                    ],
                }
            )
            session.store._remember_support_artifact(support_digest, artifact)
            session.store._remember_candidate_support("cand-unresolved-rule-ref", support_digest, "native_binding_v1")

            tree_resp = explain_runtime_tree(session_id, {"kind": "candidate", "id": "cand-unresolved-rule-ref"})
            self.assertTrue(tree_resp["ok"])
            rule_ref_section = tree_resp["tree"]["root"]["children"][1]
            self.assertEqual(rule_ref_section["node_kind"], "rule_ref_section")
            rule_ref_node = rule_ref_section["children"][0]
            self.assertEqual(rule_ref_node["ruleref_atom_key"], "b0.a1:ruleref")
            self.assertIsNone(rule_ref_node["child_support_digest"])
            self.assertEqual(rule_ref_node["unresolved_reason"], "child_support_unavailable")
            unresolved = rule_ref_node["children"][0]
            self.assertEqual(unresolved["node_kind"], "unresolved_support")
            self.assertEqual(unresolved["reason"], "child_support_unavailable")
        finally:
            close_runtime_session(session_id)
            reset_runtime_sessions_for_tests()

    def test_winning_branch_single_branch_rule_is_no_op(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [("pred", "user:tag", ["$u", "vip"])]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        self.assertEqual(selected_branch_index, 0)

        artifact = build_support_artifact_for_binding(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            root_result_kind="fact",
            selected_branch_index=selected_branch_index,
            rule_ref_edges=(),
        )
        self.assertEqual(
            [row.pred_atom_key for row in artifact.pred_witnesses],
            ["b0.a0:user:tag"],
        )

    def test_winning_branch_prefers_lowest_index_when_multiple_branches_satisfy(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [
            [("pred", "user:tag", ["$u", "vip"])],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        self.assertEqual(selected_branch_index, 0)

        artifact = build_support_artifact_for_binding(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            root_result_kind="fact",
            selected_branch_index=selected_branch_index,
            rule_ref_edges=(),
        )
        self.assertEqual(
            [row.pred_atom_key for row in artifact.pred_witnesses],
            ["b0.a0:user:tag"],
        )

    def test_winning_branch_excludes_non_satisfying_pred_branch(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [
            [("pred", "user:tag", ["$u", "blocked"])],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        self.assertEqual(selected_branch_index, 1)

    def test_winning_branch_not_atom_recheck_excludes_branch_with_negated_match(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
                ProjectedFact(asrt_id="A2", fact_tuple=("user-1", "blocked")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [
            [("not", [("pred", "user:tag", ["$u", "blocked"])]), ("pred", "user:tag", ["$u", "vip"])],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        self.assertEqual(selected_branch_index, 1)

    def test_winning_branch_ruleref_that_cannot_ground_does_not_satisfy(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [
            [("ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"])],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(
                NativeRuleRefResolution(
                    ruleref_atom_key="b0.a0:ruleref",
                    rule_ref_id="q.child_rule",
                    rule_ref_version="1.0.0",
                    row_supports=(
                        NativeRuleRefRowSupport(
                            row_terms=("user-1", "vip"),
                            child_support_digest="sha256:" + ("12" * 32),
                        ),
                    ),
                ),
            ),
        )
        self.assertEqual(selected_branch_index, 1)

    def test_winning_branch_arith_mismatch_excludes_branch(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1", "$x": 3, "$sum": 99}
        where = [
            [("addc", "$sum", "$x", 2)],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        selected_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        self.assertEqual(selected_branch_index, 1)

    def test_winning_branch_digest_is_stable_for_same_input(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }
        binding = {"$u": "user-1"}
        where = [
            [("pred", "user:tag", ["$u", "vip"])],
            [("pred", "user:tag", ["$u", "vip"])],
        ]

        first_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        first_artifact = build_support_artifact_for_binding(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            root_result_kind="fact",
            selected_branch_index=first_branch_index,
            rule_ref_edges=(),
        )
        second_branch_index = find_winning_branch_index(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            rule_ref_resolutions=(),
        )
        second_artifact = build_support_artifact_for_binding(
            where=where,
            binding=binding,
            witness_facts=witness_facts,
            root_result_kind="fact",
            selected_branch_index=second_branch_index,
            rule_ref_edges=(),
        )

        self.assertEqual(first_branch_index, 0)
        self.assertEqual(second_branch_index, 0)
        self.assertEqual(compute_support_digest(first_artifact), compute_support_digest(second_artifact))

    def test_winning_branch_fails_fast_when_no_branch_satisfies_final_binding(self) -> None:
        witness_facts = {
            "user:tag": [
                ProjectedFact(asrt_id="A1", fact_tuple=("user-1", "vip")),
            ]
        }

        with self.assertRaises(WhereValidationError) as ctx:
            find_winning_branch_index(
                where=[("pred", "user:tag", ["$u", "blocked"])],
                binding={"$u": "user-1"},
                witness_facts=witness_facts,
                rule_ref_resolutions=(),
            )
        self.assertIn("no satisfying branch", str(ctx.exception))

    def test_rule_ref_edge_derivation_fails_fast_on_duplicate_row_support_match(self) -> None:
        with self.assertRaises(WhereValidationError) as ctx:
            derive_rule_ref_edges_for_binding(
                where=[("ruleref", "q.child_rule", "1.0.0", ["$u", "$tag"])],
                binding={"$u": "user-1", "$tag": "vip"},
                rule_ref_resolutions=(
                    NativeRuleRefResolution(
                        ruleref_atom_key="b0.a0:ruleref",
                        rule_ref_id="q.child_rule",
                        rule_ref_version="1.0.0",
                        row_supports=(
                            NativeRuleRefRowSupport(
                                row_terms=("user-1", "vip"),
                                child_support_digest="sha256:" + ("12" * 32),
                            ),
                            NativeRuleRefRowSupport(
                                row_terms=("user-1", "vip"),
                                child_support_digest="sha256:" + ("34" * 32),
                            ),
                        ),
                    ),
                ),
                selected_branch_index=0,
            )

        self.assertIn("multiple row_support matches", str(ctx.exception))

    def test_rule_trace_rule_ref_link_and_invocation_sorting_validation(self) -> None:
        with self.assertRaises(ValueError) as ctx_empty_key:
            RuleTraceRuleRefLink(ruleref_atom_key="", child_invocation_id="rr_1:i1")
        self.assertEqual(str(ctx_empty_key.exception), "ruleref_atom_key must be non-empty string")

        with self.assertRaises(ValueError) as ctx_empty_invocation:
            RuleTraceRuleRefLink(ruleref_atom_key="b0.a0:ruleref", child_invocation_id="")
        self.assertEqual(str(ctx_empty_invocation.exception), "child_invocation_id must be non-empty string")

        link_a = RuleTraceRuleRefLink(ruleref_atom_key="b0.a0:ruleref", child_invocation_id="rr_1:i1")
        link_b = RuleTraceRuleRefLink(ruleref_atom_key="b0.a1:ruleref", child_invocation_id="rr_1:i2")
        with self.assertRaises(ValueError) as ctx_unsorted:
            RuleTraceInvocation(
                invocation_id="rr_1:i0",
                parent_invocation_id=None,
                rule_id="q.user",
                version="1.0.0",
                memo_hit=False,
                memo_source_invocation_id=None,
                original_where=[],
                rewritten_where=[],
                bindings=(),
                output_rows=(),
                ruleref_links=(link_b, link_a),
            )
        self.assertEqual(str(ctx_unsorted.exception), "ruleref_links must be sorted by ruleref_atom_key")

    def test_rule_trace_artifact_from_dict_round_trip_keeps_where_payload_opaque(self) -> None:
        row = {
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
                    "non_fact_steps": [
                        {
                            "binding_index": 0,
                            "step_key": "b0.a1:eq",
                            "kind": "eq",
                            "status": "satisfied",
                            "details": [["payload", {"__bytes_hex__": "ff"}]],
                        },
                        {
                            "binding_index": 0,
                            "step_key": "b0.a2:not",
                            "kind": "not",
                            "status": "no_match",
                            "details": [["payload", {"__bytes_hex__": "0f"}]],
                        }
                    ],
                }
            ],
            "root_rows": [[{"__bytes_hex__": "c0ff"}]],
            "extra": "ignored",
        }

        artifact = rule_trace_artifact_from_dict(row)
        invocation = artifact.invocations[0]

        self.assertEqual(artifact.root_rule_id, "q.user")
        self.assertEqual(artifact.root_version, "1.0.0")
        self.assertEqual(invocation.original_where, [["pred", "user:tag", [{"__bytes_hex__": "00ff"}]]])
        self.assertEqual(invocation.rewritten_where, {"opaque": {"__bytes_hex__": "0a0b"}})
        self.assertEqual(invocation.bindings, ((("$blob", b"ab"), ("$pair", [1, 2])),))
        self.assertEqual(invocation.output_rows, ((b"\x01\x02", [3, 4]),))
        self.assertEqual(invocation.ruleref_links, ())
        self.assertEqual(invocation.non_fact_steps[0].status, "evaluated")
        self.assertEqual(invocation.non_fact_steps[1].status, "negated")
        self.assertEqual(invocation.non_fact_steps[0].details, (("payload", b"\xff"),))
        self.assertEqual(artifact.root_rows, ((b"\xc0\xff",),))
        self.assertEqual(
            rule_trace_artifact_to_dict(artifact),
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
                        "non_fact_steps": [
                            {
                                "binding_index": 0,
                                "step_key": "b0.a1:eq",
                                "kind": "eq",
                                "status": "evaluated",
                                "details": [["payload", {"__bytes_hex__": "ff"}]],
                            },
                            {
                                "binding_index": 0,
                                "step_key": "b0.a2:not",
                                "kind": "not",
                                "status": "negated",
                                "details": [["payload", {"__bytes_hex__": "0f"}]],
                            }
                        ],
                        "ruleref_links": [],
                    }
                ],
                "root_rows": [[{"__bytes_hex__": "c0ff"}]],
            },
        )

    def test_rule_trace_artifact_round_trip_preserves_ruleref_links(self) -> None:
        artifact = RuleTraceArtifact(
            rule_run_id="rr_linked",
            root_rule_id="q.user",
            root_version="1.0.0",
            select_vars=("$u",),
            invocations=(
                RuleTraceInvocation(
                    invocation_id="rr_linked:i1",
                    parent_invocation_id=None,
                    rule_id="q.user",
                    version="1.0.0",
                    memo_hit=False,
                    memo_source_invocation_id=None,
                    original_where=[["ruleref", "q.dep", "1.0.0", ["$u"]]],
                    rewritten_where=[["pred", "__rule_ref__q_dep__1_0_0", ["$u"]]],
                    bindings=((("$u", "idref_v1:User:user_id=u1"),),),
                    output_rows=(("idref_v1:User:user_id=u1",),),
                    ruleref_links=(
                        RuleTraceRuleRefLink(
                            ruleref_atom_key="b0.a0:ruleref",
                            child_invocation_id="rr_linked:i2",
                        ),
                    ),
                ),
                RuleTraceInvocation(
                    invocation_id="rr_linked:i2",
                    parent_invocation_id="rr_linked:i1",
                    rule_id="q.dep",
                    version="1.0.0",
                    memo_hit=False,
                    memo_source_invocation_id=None,
                    original_where=[["pred", "user:tag", ["$u", "vip"]]],
                    rewritten_where=[["pred", "user:tag", ["$u", "vip"]]],
                    bindings=((("$u", "idref_v1:User:user_id=u1"),),),
                    output_rows=(("idref_v1:User:user_id=u1",),),
                ),
            ),
            root_rows=(("idref_v1:User:user_id=u1",),),
        )

        round_tripped = rule_trace_artifact_from_dict(rule_trace_artifact_to_dict(artifact))
        self.assertEqual(round_tripped, artifact)

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
                f"support_digest collision for different SupportArtifact on disk: {digest}",
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

            with self.assertLogs("factpy_kernel.core.store._artifact_sidecar", level="WARNING") as warnings_ctx:
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

            candidates = writer.evaluate(drv, mode="native")
            self.assertTrue(candidates)
            support_digest = candidates[0].support_digest

            reader = SDKStore([User], artifact_store_root=tmp_dir)
            self.assertIsNotNone(reader.store.explain_support(support_digest))

            via_factory = SDKStore.from_schema_classes([User], artifact_store_root=tmp_dir)
            self.assertIsNotNone(via_factory.store.explain_support(support_digest))


def _schema_ir() -> dict[str, object]:
    return compile_schema_from_classes([User])


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


def _seed_users_for_syntax_matrix(sdk: SDKStore) -> dict[str, str]:
    with sdk.batch() as tx:
        u1 = tx.entity(User, user_id="u-syntax-1", locale="zh")
        u1.name.set("Alice")
        u1.tag.add("vip")

        u2 = tx.entity(User, user_id="u-syntax-2", locale="en")
        u2.name.set("Bob")
        u2.tag.add("staff")

        u3 = tx.entity(User, user_id="u-syntax-3", locale="zh")
        u3.name.set("Carol")

        tx.commit(objects=[u1, u2, u3])

    return {
        "u1": u1.e_ref,
        "u2": u2.e_ref,
        "u3": u3.e_ref,
    }


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


if __name__ == "__main__":
    unittest.main()
