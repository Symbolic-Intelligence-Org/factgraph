"""§7-EvaluatorFrontier anti-regression gates.

The frontier trace is native-only evaluator architecture. It must keep normal
native evaluation unchanged, expose bounded aggregate rows only, avoid upper
layer imports, and stay invisible to shipped application capabilities until a
later scoped blueprint opts them in.
"""
from __future__ import annotations

import ast
from dataclasses import fields
import inspect
from pathlib import Path
import unittest

from factpy.core.rules import frontier as _frontier_module
from factpy.core.rules.frontier import (
    NativeWhereFrontierEvaluation,
    NativeWhereFrontierRow,
    evaluate_native_where_frontier,
)
from factpy.core.rules.rule_ir import RuleRegistry, RuleSpec
from factpy.core.rules.ruleref_substrate import NativeWhereEvaluation, evaluate_native_where

_BANNED_KWARGS = frozenset(
    {
        "trace",
        "callback",
        "near_miss",
        "failed_frontier",
        "exclusion_reason",
        "mode",
        "options",
        "search_budget",
        "sample_limit",
    }
)

_BANNED_IMPORT_PREFIXES = frozenset(
    {
        "factpy.application",
        "factpy.sdk",
        "factpy.adapters",
        "factpy.core.derivation.candidates",
        "factpy.core.store._support",
        "factpy.core.store.runtime",
    }
)

_BANNED_ROW_FIELDS = frozenset(
    {
        "sample_binding",
        "details",
        "env",
        "envs",
        "payload",
        "candidate",
        "support_artifact",
        "provenance_envelope",
        "raw",
        "raw_env",
    }
)

_BANNED_PAYLOAD_SYMBOLS = frozenset(
    {
        "CandidateSet",
        "SupportArtifact",
        "ProvenanceEnvelope",
        "EvidenceEnvelope",
        "ErrorDTO",
        "WarningDTO",
    }
)

_BANNED_WRITE_CALLS = frozenset(
    {
        "append_assertion",
        "append_revocation",
        "accept_derivation_candidate_set",
        "accept_derivation_candidate_sets",
        "accept_derivation_candidate",
        "accept",
        "set_field",
        "add_field",
        "retract_by_asrt",
        "apply_write_plan",
        "plan_write_command",
        "apply_ingest_request",
        "_remember_candidate_support",
        "_remember_provenance_envelope",
        "_remember_rule_trace_artifact",
    }
)

_ADAPTER_NAMES = frozenset({"souffle", "problog", "pyreason"})
_FRONTIER_MODULES = frozenset(
    {
        "factpy.core.rules.frontier",
        "frontier",
    }
)
_FRONTIER_PUBLIC_SYMBOLS = frozenset(
    {
        "evaluate_native_where_frontier",
        "NativeWhereFrontierEvaluation",
        "NativeWhereFrontierFailureKind",
        "NativeWhereFrontierRow",
    }
)


def _frontier_tree() -> ast.Module:
    return _parse_path(Path(_frontier_module.__file__))


def _parse_path(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(tree: ast.AST) -> list[ast.Import | ast.ImportFrom]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]


def _imported_modules(tree: ast.AST) -> list[str]:
    modules: list[str] = []
    for node in _imports(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    return modules


def _imported_symbols(tree: ast.AST) -> set[str]:
    symbols: set[str] = set()
    for node in _imports(tree):
        for alias in node.names:
            symbols.add(alias.name.rsplit(".", maxsplit=1)[-1])
            if alias.asname:
                symbols.add(alias.asname)
    return symbols


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _frontier_application_opt_in_offenders(tree: ast.AST, path: Path) -> list[tuple[str, str]]:
    offenders: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _FRONTIER_MODULES:
                    offenders.append((str(path), alias.name))
            continue
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "factpy.core.rules":
                for alias in node.names:
                    if alias.name == "frontier" or alias.name in _FRONTIER_PUBLIC_SYMBOLS:
                        offenders.append((str(path), f"{module}.{alias.name}"))
            elif module in _FRONTIER_MODULES:
                for alias in node.names:
                    if alias.name in _FRONTIER_PUBLIC_SYMBOLS:
                        offenders.append((str(path), f"{module}.{alias.name}"))
            continue
        if isinstance(node, ast.Name) and (
            node.id in _FRONTIER_PUBLIC_SYMBOLS or node.id.startswith("NativeWhereFrontier")
        ):
            offenders.append((str(path), node.id))
            continue
        if isinstance(node, ast.Attribute) and (
            node.attr in _FRONTIER_PUBLIC_SYMBOLS or node.attr.startswith("NativeWhereFrontier")
        ):
            offenders.append((str(path), node.attr))
    return offenders


def _eligible_registry() -> RuleRegistry:
    registry = RuleRegistry()
    registry.register(
        RuleSpec(
            rule_id="person.eligible",
            version="1.0",
            select_vars=["$name"],
            where=[
                ("pred", "person", ["$name"]),
                ("pred", "eligible", ["$name"]),
            ],
            expose=True,
        )
    )
    return registry


class EvaluatorFrontierSurfaceGateTests(unittest.TestCase):
    """§7-EvaluatorFrontier-1 / 2 / 3 / 5 / 8: public surface gates."""

    def test_1_separate_entrypoint_keeps_normal_native_surface_unchanged(self) -> None:
        self.assertEqual(
            list(inspect.signature(evaluate_native_where_frontier).parameters),
            list(inspect.signature(evaluate_native_where).parameters),
        )
        self.assertEqual(
            [field.name for field in fields(NativeWhereEvaluation)],
            ["bindings", "rule_refs", "rule_ref_resolutions"],
        )
        self.assertEqual(
            [field.name for field in fields(NativeWhereFrontierEvaluation)],
            ["bindings", "rule_refs", "rule_ref_resolutions", "frontier_rows"],
        )

    def test_2_no_trace_kwargs_on_normal_or_frontier_entrypoints(self) -> None:
        normal_params = set(inspect.signature(evaluate_native_where).parameters)
        frontier_params = set(inspect.signature(evaluate_native_where_frontier).parameters)

        self.assertEqual(normal_params & _BANNED_KWARGS, set())
        self.assertEqual(frontier_params & _BANNED_KWARGS, set())

    def test_3_frontier_module_imports_no_upper_layers_or_payload_dtos(self) -> None:
        tree = _frontier_tree()
        imported_modules = _imported_modules(tree)
        imported_symbols = _imported_symbols(tree)

        offenders = [
            module
            for module in imported_modules
            if any(
                module == banned or module.startswith(f"{banned}.")
                for banned in _BANNED_IMPORT_PREFIXES
            )
        ]
        self.assertEqual(offenders, [])
        self.assertEqual(imported_symbols & _BANNED_PAYLOAD_SYMBOLS, set())

    def test_5_frontier_rows_expose_no_env_dump_or_opaque_payload(self) -> None:
        row_fields = {field.name for field in fields(NativeWhereFrontierRow)}
        result_fields = {field.name for field in fields(NativeWhereFrontierEvaluation)}
        tree = _frontier_tree()
        class_fields: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    class_fields.add(item.target.id)

        self.assertEqual(row_fields & _BANNED_ROW_FIELDS, set())
        self.assertEqual(result_fields & (_BANNED_ROW_FIELDS - {"envs"}), set())
        self.assertEqual(class_fields & _BANNED_ROW_FIELDS, set())

    def test_8_frontier_scope_stays_native_only(self) -> None:
        source = Path(_frontier_module.__file__).read_text(encoding="utf-8")
        tree = _frontier_tree()
        imported_modules = _imported_modules(tree)

        adapter_imports = [
            module
            for module in imported_modules
            if module == "factpy.adapters" or module.startswith("factpy.adapters.")
        ]
        self.assertEqual(adapter_imports, [])
        self.assertEqual({name for name in _ADAPTER_NAMES if name in source}, set())


class EvaluatorFrontierRuntimeGateTests(unittest.TestCase):
    """§7-EvaluatorFrontier-4 / 6 / 7 / 9: runtime invariants."""

    def assert_success_parity(
        self,
        view_facts: dict[str, list[tuple[object, ...]]],
        where: list[object],
        *,
        registry: RuleRegistry | None = None,
    ) -> NativeWhereFrontierEvaluation:
        native = evaluate_native_where(view_facts, where, registry=registry)
        frontier = evaluate_native_where_frontier(view_facts, where, registry=registry)

        self.assertEqual(frontier.bindings, native.bindings)
        self.assertEqual(frontier.rule_refs, native.rule_refs)
        self.assertEqual(frontier.rule_ref_resolutions, native.rule_ref_resolutions)
        return frontier

    def test_4_bounded_rows_emit_at_most_one_row_per_normalized_branch(self) -> None:
        view_facts = {"person": [("alice",)]}
        where = [
            [("pred", "person", ["$name"]), ("eq", "$name", "bob"), ("eq", "$name", "carol")],
            [("pred", "person", ["$name"]), ("eq", "$name", "dora"), ("eq", "$name", "erin")],
            [("pred", "person", ["$name"]), ("eq", "$name", "alice")],
        ]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertLessEqual(len(frontier.frontier_rows), 3)
        self.assertEqual([row.branch_index for row in frontier.frontier_rows], [0, 1])

    def test_6_deterministic_counts_are_pre_atom_input_counts(self) -> None:
        view_facts = {"person": [("alice",), ("bob",)]}
        where = [
            ("pred", "person", ["$name"]),
            ("eq", "$name", "carol"),
        ]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertEqual(
            frontier.frontier_rows,
            (
                NativeWhereFrontierRow(
                    branch_index=0,
                    failed_atom_index=1,
                    atoms_satisfied=1,
                    frontier_count=2,
                    failure_kind="atom_filter_empty",
                ),
            ),
        )

    def test_7_success_parity_covers_native_path_shapes(self) -> None:
        cases: list[tuple[dict[str, list[tuple[object, ...]]], list[object], RuleRegistry | None]] = [
            (
                {"person": [("alice",), ("bob",)], "eligible": [("alice",)]},
                [("pred", "person", ["$name"]), ("pred", "eligible", ["$name"])],
                None,
            ),
            (
                {"person": [("alice",), ("bob",)], "vip": [("bob",)]},
                [
                    [("pred", "person", ["$name"]), ("eq", "$name", "alice")],
                    [("pred", "vip", ["$name"])],
                ],
                None,
            ),
            (
                {"person": [("alice",), ("bob",)]},
                [("pred", "person", ["$name"]), ("in", "$name", ["alice"])],
                None,
            ),
            (
                {"score": [("alice", 2), ("bob", 3)]},
                [
                    ("pred", "score", ["$name", "$score"]),
                    ("addc", "$next_score", "$score", 1),
                    ("eq", "$next_score", 3),
                ],
                None,
            ),
            (
                {"person": [("alice",), ("bob",)], "blocked": [("alice",)]},
                [("pred", "person", ["$name"]), ("not", [("pred", "blocked", ["$name"])])],
                None,
            ),
            (
                {"person": [("alice",), ("bob",)], "eligible": [("alice",)]},
                [("ruleref", "person.eligible", "1.0", ["$name"])],
                _eligible_registry(),
            ),
        ]

        for view_facts, where, registry in cases:
            with self.subTest(where=where):
                self.assert_success_parity(view_facts, where, registry=registry)

    def test_9_frontier_evaluation_adds_no_new_persistence_callback(self) -> None:
        calls: list[tuple[str, object]] = []
        view_facts = {
            "person": [("alice",), ("bob",)],
            "eligible": [("alice",)],
        }
        where: list[object] = [
            ("ruleref", "person.eligible", "1.0", ["$name"]),
            ("eq", "$name", "bob"),
        ]

        frontier = evaluate_native_where_frontier(
            view_facts,
            where,
            registry=_eligible_registry(),
            remember_support_artifact=lambda key, artifact: calls.append((key, artifact)),
        )

        self.assertEqual(frontier.bindings, [])
        self.assertEqual(calls, [])


class EvaluatorFrontierBoundaryGateTests(unittest.TestCase):
    """§7-EvaluatorFrontier-9 / 10: no writes and no application opt-in."""

    def test_9_frontier_module_does_not_import_or_call_write_substrates(self) -> None:
        tree = _frontier_tree()
        imported = _imported_symbols(tree)
        called = {
            call_name
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for call_name in [_call_name(node)]
            if call_name is not None
        }

        self.assertEqual(imported & _BANNED_WRITE_CALLS, set())
        self.assertEqual(called & _BANNED_WRITE_CALLS, set())

    def test_10_application_layer_does_not_opt_into_frontier_trace(self) -> None:
        app_dir = Path(__file__).parents[1] / "application"
        offenders: list[tuple[str, str]] = []
        for path in sorted(app_dir.glob("**/*.py")):
            tree = _parse_path(path)
            offenders.extend(_frontier_application_opt_in_offenders(tree, path))

        self.assertEqual(offenders, [])

    def test_10_application_opt_in_gate_catches_module_qualified_access(self) -> None:
        samples = [
            "import factpy.core.rules.frontier as f\nf.evaluate_native_where_frontier({}, [])\n",
            "from factpy.core.rules import frontier\nfrontier.evaluate_native_where_frontier({}, [])\n",
            "from factpy.core.rules import frontier\nx: frontier.NativeWhereFrontierRow | None = None\n",
            (
                "from factpy.core.rules.frontier import NativeWhereFrontierRow\n"
                "row: NativeWhereFrontierRow | None = None\n"
            ),
        ]

        for source in samples:
            with self.subTest(source=source):
                offenders = _frontier_application_opt_in_offenders(
                    ast.parse(source),
                    Path("sample.py"),
                )
                self.assertGreaterEqual(len(offenders), 1)


if __name__ == "__main__":
    unittest.main()
