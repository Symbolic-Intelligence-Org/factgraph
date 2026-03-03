from __future__ import annotations

import unittest

from factpy_kernel.authoring import (
    AuthoringDerivationCompileError,
    compile_authoring_derivation_v1,
    parse_authoring_derivation_dsl_v1,
)
from factpy_kernel.authoring.where_schema_lowering import (
    WhereSchemaLoweringError,
    lower_blueprint_where_sugar_with_schema_v1,
)
from factpy_kernel.core.rules.where_eval import _plan_body_atoms
from factpy_kernel.core.view.projector import project_view_facts
from factpy_kernel.sdk import Entity, Field, Identity, SDKStore, SDKStoreError, compile_schema_from_classes


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


class Phase3ContractsV1Tests(unittest.TestCase):
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
        python_candidates = sdk.evaluate(compiled, mode="python")
        engine_candidates = sdk.evaluate(compiled, mode="engine")

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
        self.assertIn(("version", "num", 3), meta_rows)

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


def _schema_ir() -> dict[str, object]:
    return compile_schema_from_classes([User])


if __name__ == "__main__":
    unittest.main()
