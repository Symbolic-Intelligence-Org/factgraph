from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields
import inspect
from pathlib import Path
import unittest

from factgraph.core.rules import frontier as _frontier_module
from factgraph.core.rules.frontier import (
    NativeWhereFrontierEvaluation,
    NativeWhereFrontierRow,
    evaluate_native_where_frontier,
)
from factgraph.core.rules.rule_ir import RuleRegistry, RuleSpec
from factgraph.core.rules.ruleref_substrate import evaluate_native_where

_BANNED_IMPORT_PREFIXES = (
    "factgraph.application",
    "factgraph.sdk",
    "factgraph.adapters",
    "factgraph.core.derivation.candidates",
    "factgraph.core.store._support",
    "factgraph.core.store.runtime",
)

_BANNED_SYMBOLS = frozenset(
    {
        "CandidateSet",
        "ProofReceipt",
        "ProvenanceEnvelope",
        "EvidenceEnvelope",
        "ErrorDTO",
        "WarningDTO",
    }
)

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


def _frontier_tree() -> ast.Module:
    source = Path(_frontier_module.__file__).read_text(encoding="utf-8")
    return ast.parse(source)


def _imported_modules(tree: ast.AST) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    return modules


def _imported_symbols(tree: ast.AST) -> set[str]:
    symbols: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for alias in node.names:
            symbols.add(alias.name.rsplit(".", maxsplit=1)[-1])
            if alias.asname:
                symbols.add(alias.asname)
    return symbols


class NativeWhereFrontierDTOTests(unittest.TestCase):
    def test_row_fields_are_exact_stable_contract(self) -> None:
        self.assertEqual(
            [field.name for field in fields(NativeWhereFrontierRow)],
            [
                "branch_index",
                "failed_atom_index",
                "atoms_satisfied",
                "frontier_count",
                "failure_kind",
            ],
        )

    def test_row_accepts_atom_filter_empty(self) -> None:
        row = NativeWhereFrontierRow(
            branch_index=0,
            failed_atom_index=2,
            atoms_satisfied=2,
            frontier_count=3,
            failure_kind="atom_filter_empty",
        )

        self.assertEqual(row.branch_index, 0)
        self.assertEqual(row.frontier_count, 3)

    def test_row_accepts_defensive_empty_input(self) -> None:
        row = NativeWhereFrontierRow(
            branch_index=0,
            failed_atom_index=0,
            atoms_satisfied=0,
            frontier_count=0,
            failure_kind="empty_input",
        )

        self.assertEqual(row.failure_kind, "empty_input")

    def test_row_rejects_unknown_failure_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "failure_kind"):
            NativeWhereFrontierRow(
                branch_index=0,
                failed_atom_index=0,
                atoms_satisfied=0,
                frontier_count=1,
                failure_kind="wrong_arity",  # type: ignore[arg-type]
            )

    def test_row_rejects_atoms_satisfied_drift(self) -> None:
        with self.assertRaisesRegex(ValueError, "atoms_satisfied"):
            NativeWhereFrontierRow(
                branch_index=0,
                failed_atom_index=2,
                atoms_satisfied=1,
                frontier_count=1,
                failure_kind="atom_filter_empty",
            )

    def test_row_rejects_failure_kind_count_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "frontier_count=0"):
            NativeWhereFrontierRow(
                branch_index=0,
                failed_atom_index=0,
                atoms_satisfied=0,
                frontier_count=1,
                failure_kind="empty_input",
            )
        with self.assertRaisesRegex(ValueError, "frontier_count>0"):
            NativeWhereFrontierRow(
                branch_index=0,
                failed_atom_index=0,
                atoms_satisfied=0,
                frontier_count=0,
                failure_kind="atom_filter_empty",
            )

    def test_row_rejects_bool_and_negative_ints(self) -> None:
        with self.assertRaisesRegex(ValueError, "branch_index"):
            NativeWhereFrontierRow(
                branch_index=True,  # type: ignore[arg-type]
                failed_atom_index=0,
                atoms_satisfied=0,
                frontier_count=0,
                failure_kind="empty_input",
            )
        with self.assertRaisesRegex(ValueError, "failed_atom_index"):
            NativeWhereFrontierRow(
                branch_index=0,
                failed_atom_index=-1,
                atoms_satisfied=0,
                frontier_count=0,
                failure_kind="empty_input",
            )

    def test_row_is_frozen(self) -> None:
        row = NativeWhereFrontierRow(
            branch_index=0,
            failed_atom_index=0,
            atoms_satisfied=0,
            frontier_count=0,
            failure_kind="empty_input",
        )

        with self.assertRaises(FrozenInstanceError):
            row.frontier_count = 1  # type: ignore[misc]

    def test_evaluation_fields_and_defaults_are_exact(self) -> None:
        evaluation = NativeWhereFrontierEvaluation(bindings=[])

        self.assertEqual(
            [field.name for field in fields(NativeWhereFrontierEvaluation)],
            ["bindings", "rule_refs", "rule_ref_resolutions", "frontier_rows"],
        )
        self.assertEqual(evaluation.rule_refs, ())
        self.assertEqual(evaluation.rule_ref_resolutions, ())
        self.assertEqual(evaluation.frontier_rows, ())

    def test_evaluation_rejects_wrong_shapes(self) -> None:
        with self.assertRaisesRegex(ValueError, "bindings"):
            NativeWhereFrontierEvaluation(bindings=())  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "frontier_rows"):
            NativeWhereFrontierEvaluation(
                bindings=[],
                frontier_rows=(object(),),  # type: ignore[arg-type]
            )


class NativeWhereFrontierEntrypointTests(unittest.TestCase):
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

    def test_entrypoint_signature_mirrors_native_without_trace_kwargs(self) -> None:
        frontier_signature = inspect.signature(evaluate_native_where_frontier)
        native_signature = inspect.signature(evaluate_native_where)

        self.assertEqual(
            list(frontier_signature.parameters),
            list(native_signature.parameters),
        )
        for name, native_param in native_signature.parameters.items():
            frontier_param = frontier_signature.parameters[name]
            self.assertEqual(frontier_param.kind, native_param.kind)
            self.assertEqual(frontier_param.default, native_param.default)

        self.assertEqual(set(frontier_signature.parameters) & _BANNED_KWARGS, set())

    def test_entrypoint_scaffold_preserves_success_bindings(self) -> None:
        view_facts = {
            "person": [("alice",), ("bob",)],
            "eligible": [("alice",)],
        }
        where = [
            ("pred", "person", ["$name"]),
            ("pred", "eligible", ["$name"]),
        ]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertIsInstance(frontier, NativeWhereFrontierEvaluation)
        self.assertEqual(frontier.frontier_rows, ())

    def test_entrypoint_scaffold_preserves_success_bindings_for_or_body(self) -> None:
        view_facts = {
            "person": [("alice",), ("bob",)],
            "vip": [("bob",)],
        }
        where = [
            [("pred", "person", ["$name"]), ("eq", "$name", "alice")],
            [("pred", "vip", ["$name"])],
        ]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertEqual(frontier.frontier_rows, ())

    def test_entrypoint_preserves_success_bindings_for_filter_path(self) -> None:
        view_facts = {"person": [("alice",), ("bob",)]}
        where = [
            ("pred", "person", ["$name"]),
            ("in", "$name", ["alice"]),
        ]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertEqual(frontier.bindings, [{"$name": "alice"}])
        self.assertEqual(frontier.frontier_rows, ())

    def test_entrypoint_preserves_success_bindings_for_arithmetic_path(self) -> None:
        view_facts = {"score": [("alice", 2), ("bob", 3)]}
        where = [
            ("pred", "score", ["$name", "$score"]),
            ("addc", "$next_score", "$score", 1),
            ("eq", "$next_score", 3),
        ]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertEqual(
            frontier.bindings,
            [{"$name": "alice", "$next_score": 3, "$score": 2}],
        )
        self.assertEqual(frontier.frontier_rows, ())

    def test_entrypoint_preserves_success_bindings_for_not_path(self) -> None:
        view_facts = {
            "person": [("alice",), ("bob",)],
            "blocked": [("alice",)],
        }
        where = [
            ("pred", "person", ["$name"]),
            ("not", [("pred", "blocked", ["$name"])]),
        ]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertEqual(frontier.bindings, [{"$name": "bob"}])
        self.assertEqual(frontier.frontier_rows, ())

    def test_entrypoint_preserves_success_bindings_for_ruleref_path(self) -> None:
        view_facts = {
            "person": [("alice",), ("bob",)],
            "eligible": [("alice",)],
        }
        registry = _eligible_registry()
        where: list[object] = [("ruleref", "person.eligible", "1.0", ["$name"])]

        frontier = self.assert_success_parity(view_facts, where, registry=registry)

        self.assertEqual(frontier.bindings, [{"$name": "alice"}])
        self.assertEqual(frontier.rule_refs, ("person.eligible",))
        self.assertEqual(frontier.frontier_rows, ())

    def test_predicate_failure_emits_branch_frontier(self) -> None:
        view_facts = {"person": []}
        where = [("pred", "person", ["$name"])]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertEqual(frontier.bindings, [])
        self.assertEqual(
            frontier.frontier_rows,
            (
                NativeWhereFrontierRow(
                    branch_index=0,
                    failed_atom_index=0,
                    atoms_satisfied=0,
                    frontier_count=1,
                    failure_kind="atom_filter_empty",
                ),
            ),
        )

    def test_filter_failure_records_pre_atom_env_count(self) -> None:
        view_facts = {"person": [("alice",), ("bob",)]}
        where = [
            ("pred", "person", ["$name"]),
            ("eq", "$name", "carol"),
        ]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertEqual(frontier.bindings, [])
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

    def test_not_failure_records_outer_not_atom_frontier(self) -> None:
        view_facts = {
            "person": [("alice",)],
            "blocked": [("alice",)],
        }
        where = [
            ("pred", "person", ["$name"]),
            ("not", [("pred", "blocked", ["$name"])]),
        ]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertEqual(frontier.bindings, [])
        self.assertEqual(
            frontier.frontier_rows,
            (
                NativeWhereFrontierRow(
                    branch_index=0,
                    failed_atom_index=1,
                    atoms_satisfied=1,
                    frontier_count=1,
                    failure_kind="atom_filter_empty",
                ),
            ),
        )

    def test_or_body_emits_sparse_failed_branch_rows_with_success_bindings(self) -> None:
        view_facts = {"person": [("alice",)]}
        where = [
            [("pred", "person", ["$name"]), ("eq", "$name", "alice")],
            [("pred", "person", ["$name"]), ("eq", "$name", "bob")],
        ]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertEqual(frontier.bindings, [{"$name": "alice"}])
        self.assertEqual(
            frontier.frontier_rows,
            (
                NativeWhereFrontierRow(
                    branch_index=1,
                    failed_atom_index=1,
                    atoms_satisfied=1,
                    frontier_count=1,
                    failure_kind="atom_filter_empty",
                ),
            ),
        )

    def test_or_body_emits_at_most_one_frontier_row_per_failed_branch(self) -> None:
        view_facts = {"person": [("alice",)]}
        where = [
            [
                ("pred", "person", ["$name"]),
                ("eq", "$name", "bob"),
                ("eq", "$name", "carol"),
            ],
            [
                ("pred", "person", ["$name"]),
                ("eq", "$name", "dora"),
                ("eq", "$name", "erin"),
            ],
        ]

        frontier = self.assert_success_parity(view_facts, where)

        self.assertEqual(frontier.bindings, [])
        self.assertEqual(
            frontier.frontier_rows,
            (
                NativeWhereFrontierRow(
                    branch_index=0,
                    failed_atom_index=1,
                    atoms_satisfied=1,
                    frontier_count=1,
                    failure_kind="atom_filter_empty",
                ),
                NativeWhereFrontierRow(
                    branch_index=1,
                    failed_atom_index=1,
                    atoms_satisfied=1,
                    frontier_count=1,
                    failure_kind="atom_filter_empty",
                ),
            ),
        )

    def test_ruleref_frontier_is_computed_after_parent_rewrite(self) -> None:
        view_facts = {
            "person": [("alice",), ("bob",)],
            "eligible": [("alice",)],
        }
        registry = _eligible_registry()
        where: list[object] = [
            ("ruleref", "person.eligible", "1.0", ["$name"]),
            ("eq", "$name", "bob"),
        ]

        frontier = self.assert_success_parity(view_facts, where, registry=registry)

        self.assertEqual(frontier.bindings, [])
        self.assertEqual(frontier.rule_refs, ("person.eligible",))
        self.assertEqual(
            frontier.frontier_rows,
            (
                NativeWhereFrontierRow(
                    branch_index=0,
                    failed_atom_index=1,
                    atoms_satisfied=1,
                    frontier_count=1,
                    failure_kind="atom_filter_empty",
                ),
            ),
        )


class NativeWhereFrontierLayerBoundaryTests(unittest.TestCase):
    def test_frontier_module_imports_no_upper_layers_or_payload_dtos(self) -> None:
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
        self.assertEqual(imported_symbols & _BANNED_SYMBOLS, set())

    def test_frontier_module_has_no_banned_parameter_names_or_dump_fields(self) -> None:
        tree = _frontier_tree()
        parameter_names: set[str] = set()
        class_field_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.arg):
                parameter_names.add(node.arg)
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        class_field_names.add(item.target.id)

        self.assertEqual(parameter_names & _BANNED_KWARGS, set())
        self.assertEqual(
            class_field_names & {"sample_binding", "details", "env", "envs", "payload"},
            set(),
        )


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


if __name__ == "__main__":
    unittest.main()
