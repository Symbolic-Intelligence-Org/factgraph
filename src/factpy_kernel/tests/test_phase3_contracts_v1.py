from __future__ import annotations

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
    build_rule_trace_narrative_dto,
    build_rule_trace_summary_dto,
    build_rule_trace_summary_list_dto,
    build_compliance_matrix_dto,
    extend_schema_ir_with_ecss_vcd_predicates,
    load_audit_package,
    render_audit_static_site,
)
from factpy_kernel.authoring import (
    AuthoringDerivationCompileError,
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
from factpy_kernel.core.rules.where_eval import _plan_body_atoms
from factpy_kernel.core.store import Store, register_engine_evaluator
import factpy_kernel.core.store._builders as store_builders
from factpy_kernel.core.store._artifact_sidecar import FileArtifactSidecar, GCResult
from factpy_kernel.core.store._support import (
    ENGINE_NO_WITNESS_KIND,
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
    close_runtime_session,
    evaluate_runtime_derivation,
    explain_runtime_nl,
    explain_runtime_narrative,
    explain_runtime_ref,
    explain_runtime_rule_trace,
    explain_runtime_summary,
    explain_runtime_support,
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

            with TestClient(app) as client:
                candidate_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain",
                    json={"kind": "candidate", "id": candidate_id},
                )
                self.assertEqual(candidate_http.status_code, 200)
                self.assertTrue(candidate_http.json()["ok"])
                self.assertEqual(candidate_http.json()["kind"], "candidate")

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

                narrative_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-narrative",
                    json={"kind": "rule_run", "id": rule_run_id},
                )
                self.assertEqual(narrative_http.status_code, 200)
                self.assertTrue(narrative_http.json()["ok"])
                self.assertEqual(narrative_http.json()["kind"], "rule_run_narrative")
                self.assertIn("narrative", narrative_http.json())

                nl_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-nl",
                    json={"kind": "rule_run", "id": rule_run_id},
                )
                self.assertEqual(nl_http.status_code, 200)
                self.assertTrue(nl_http.json()["ok"])
                self.assertEqual(nl_http.json()["kind"], "rule_run_nl_explain")
                self.assertIn("explain_nl", nl_http.json())

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

                unsupported_summary_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-summary",
                    json={"kind": "candidate", "id": candidate_id},
                )
                self.assertEqual(unsupported_summary_kind_http.status_code, 200)
                self.assertFalse(unsupported_summary_kind_http.json()["ok"])
                self.assertEqual(unsupported_summary_kind_http.json()["errors"][0]["kind"], "shape")

                missing_summary_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-summary",
                    json={"id": rule_run_id},
                )
                self.assertEqual(missing_summary_kind_http.status_code, 200)
                self.assertFalse(missing_summary_kind_http.json()["ok"])
                self.assertEqual(missing_summary_kind_http.json()["errors"][0]["kind"], "shape")

                unsupported_narrative_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-narrative",
                    json={"kind": "candidate", "id": candidate_id},
                )
                self.assertEqual(unsupported_narrative_kind_http.status_code, 200)
                self.assertFalse(unsupported_narrative_kind_http.json()["ok"])
                self.assertEqual(unsupported_narrative_kind_http.json()["errors"][0]["kind"], "shape")

                missing_narrative_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-narrative",
                    json={"id": rule_run_id},
                )
                self.assertEqual(missing_narrative_kind_http.status_code, 200)
                self.assertFalse(missing_narrative_kind_http.json()["ok"])
                self.assertEqual(missing_narrative_kind_http.json()["errors"][0]["kind"], "shape")

                unsupported_nl_kind_http = client.post(
                    f"/v1/runtime/sessions/{session_id}/queries/explain-nl",
                    json={"kind": "candidate", "id": candidate_id},
                )
                self.assertEqual(unsupported_nl_kind_http.status_code, 200)
                self.assertFalse(unsupported_nl_kind_http.json()["ok"])
                self.assertEqual(unsupported_nl_kind_http.json()["errors"][0]["kind"], "shape")

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
            },
        )

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
