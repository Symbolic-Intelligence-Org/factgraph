from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from factgraph.authoring.registry_fs import FileAuthoringRegistry
from factgraph.adapters.souffle.package import ExportOptions, export_package
from factgraph.adapters.souffle.pred_norm import normalize_pred_id
from factgraph.adapters.souffle.where_compile import (
    build_query_witness_layout,
    compile_where_to_query_dl,
)
from factgraph.core.rules.ruleref_common import internal_rule_pred_id
from factgraph.core.rules.rule_ir import RuleRegistry, RuleSpec
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.core.store.runtime import Store
from factgraph.sdk import Pred, Rule, RuleRef, SDKStore, vars as sdk_vars
from tests._test_helpers import User, _schema_ir as _runtime_schema_ir


class SouffleWitnessWhereCompileV1Tests(unittest.TestCase):
    def test_build_query_witness_layout_collects_pred_atoms_in_branch_order(self) -> None:
        where = [
            [("pred", "user:name", ["$e", "$value"])],
            [("pred", "user:status", ["$e", "$value"])],
        ]

        layout = build_query_witness_layout(where)

        self.assertEqual(layout.query_variables, ("$e", "$value"))
        self.assertEqual(
            [row.pred_atom_key for row in layout.pred_witness_columns],
            ["b0.a0:user:name", "b1.a0:user:status"],
        )

    def test_compile_where_to_query_dl_with_witness_columns_uses_w_relations(self) -> None:
        where = [
            [("pred", "user:name", ["$e", "$value"])],
            [("pred", "user:status", ["$e", "$value"])],
        ]

        dl = compile_where_to_query_dl(
            schema_ir=_schema_ir(),
            where=where,
            query_rel="query__test",
            include_pred_witness_columns=True,
        )

        self.assertIn(".decl query__test(C0:symbol, C1:symbol, W0:symbol, W1:symbol)", dl)
        self.assertIn(".output query__test", dl)
        self.assertIn('query__test(C0, C1, W0, W1) :- p_user_name_w(C0, C1, W0), W1 = "".', dl)
        self.assertIn('query__test(C0, C1, W0, W1) :- p_user_status_w(C0, C1, W1), W0 = "".', dl)

    def test_compile_where_to_query_dl_keeps_legacy_shape_by_default(self) -> None:
        where = [
            ("pred", "user:name", ["$e", "$name"]),
            ("pred", "user:status", ["$e", "$status"]),
        ]

        dl = compile_where_to_query_dl(
            schema_ir=_schema_ir(),
            where=where,
            query_rel="query__legacy",
        )

        self.assertIn(".decl query__legacy(C0:symbol, C1:symbol, C2:symbol)", dl)
        self.assertNotIn("W0:symbol", dl)
        self.assertIn("p_user_name(C0, C1)", dl)
        self.assertIn("p_user_status(C0, C2)", dl)
        self.assertNotIn("p_user_name_w(", dl)

    def test_compile_where_to_query_dl_rewrites_ruleref_with_registry(self) -> None:
        internal_rel = normalize_pred_id(internal_rule_pred_id("q.user_name_rows", "1.0.0"))
        dl = compile_where_to_query_dl(
            schema_ir=_schema_ir(),
            where=[
                ("ruleref", "q.user_name_rows", "1.0.0", ["$e", "$name"]),
                ("pred", "user:status", ["$e", "$status"]),
            ],
            query_rel="query__ruleref",
            registry=_rule_registry(),
        )

        self.assertIn(f".decl {internal_rel}(C0:symbol, C1:symbol)", dl)
        self.assertIn(f"{internal_rel}(C0, C1) :- p_user_name(C0, C1).", dl)
        self.assertIn(
            f"query__ruleref(C0, C1, C2) :- {internal_rel}(C0, C1), p_user_status(C0, C2).",
            dl,
        )

    def test_compile_where_to_query_dl_ruleref_requires_registry(self) -> None:
        with self.assertRaises(WhereValidationError) as ctx:
            compile_where_to_query_dl(
                schema_ir=_schema_ir(),
                where=[("ruleref", "q.user_name_rows", "1.0.0", ["$e", "$name"])],
                query_rel="query__ruleref",
            )
        self.assertIn("requires registry_root", str(ctx.exception))

    def test_export_package_threads_query_registry_root_for_ruleref(self) -> None:
        internal_rel = normalize_pred_id(internal_rule_pred_id("q.user_name_rows", "1.0.0"))
        store = Store(_runtime_schema_ir())
        with TemporaryDirectory() as package_dir:
            with patch(
                "factgraph.adapters.souffle.package._load_query_rule_registry",
                return_value=_rule_registry(),
            ) as mock_load_registry:
                export_package(
                    store,
                    Path(package_dir),
                    ExportOptions(package_kind="inference"),
                    query={
                        "where": [("ruleref", "q.user_name_rows", "1.0.0", ["$e", "$name"])],
                        "query_rel": "query__export",
                        "registry_root": "/tmp/fake-registry",
                    },
                )

            mock_load_registry.assert_called_once_with("/tmp/fake-registry")
            idb_text = (Path(package_dir) / "rules" / "idb.dl").read_text(encoding="utf-8")
            self.assertIn(f".decl {internal_rel}(C0:symbol, C1:symbol)", idb_text)
            self.assertIn(
                f"query__export(C0, C1) :- {internal_rel}(C0, C1).",
                idb_text,
            )

    def test_export_package_loads_nested_ruleref_rules_from_registry_files(self) -> None:
        sdk = SDKStore([User], schema_ir=_runtime_schema_ir())
        with TemporaryDirectory() as package_dir, TemporaryDirectory() as registry_dir:
            registry = FileAuthoringRegistry(Path(registry_dir))
            registry.upsert_schema_ir(sdk.schema_ir)
            with sdk_vars("u", "tag") as (u, tag):
                child_rule = Rule(
                    id="q.child_rule",
                    version="1.0.0",
                    select=[u, tag],
                    where=[Pred("user:tag", u, tag)],
                    expose=True,
                )
                parent_rule = Rule(
                    id="q.parent_rule",
                    version="1.0.0",
                    select=[u, tag],
                    where=[RuleRef(child_rule)(u, tag)],
                    expose=True,
                )
            registry.register_rule_spec(sdk._compile_rule_input(child_rule))
            registry.register_rule_spec(sdk._compile_rule_input(parent_rule))

            export_package(
                sdk.store,
                Path(package_dir),
                ExportOptions(package_kind="inference"),
                query={
                    "where": [("ruleref", "q.parent_rule", "1.0.0", ["$u", "$tag"])],
                    "query_rel": "query__nested",
                    "registry_root": registry_dir,
                },
            )

            idb_text = (Path(package_dir) / "rules" / "idb.dl").read_text(encoding="utf-8")
            child_rel = normalize_pred_id(internal_rule_pred_id("q.child_rule", "1.0.0"))
            parent_rel = normalize_pred_id(internal_rule_pred_id("q.parent_rule", "1.0.0"))
            self.assertIn(f".decl {child_rel}(C0:symbol, C1:symbol)", idb_text)
            self.assertIn(f".decl {parent_rel}(C0:symbol, C1:symbol)", idb_text)
            self.assertIn(f"{parent_rel}(C0, C1) :- {child_rel}(C0, C1).", idb_text)
            self.assertIn(f"query__nested(C0, C1) :- {parent_rel}(C1, C0).", idb_text)


def _schema_ir() -> dict[str, object]:
    return {
        "predicates": [
            {
                "pred_id": "user:name",
                "cardinality": "multi",
                "arg_specs": [
                    {"name": "e_ref", "type_domain": "entity_ref"},
                    {"name": "name", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            },
            {
                "pred_id": "user:status",
                "cardinality": "single",
                "arg_specs": [
                    {"name": "e_ref", "type_domain": "entity_ref"},
                    {"name": "status", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            },
        ]
    }


def _rule_registry() -> RuleRegistry:
    registry = RuleRegistry()
    registry.register(
        RuleSpec(
            rule_id="q.user_name_rows",
            version="1.0.0",
            select_vars=["$e", "$name"],
            where=[("pred", "user:name", ["$e", "$name"])],
            expose=True,
        )
    )
    return registry


if __name__ == "__main__":
    unittest.main()
