"""§7-WhyNot-8 / 9 / 13 / 14 anti-regression gates.

Why-not is Sibling-with-Diagnose: runtime composition may call Diagnose and
construct Diagnose requests internally, but it must not call Check, leak
Diagnose result DTOs into the public protocol, depend on evaluator trace hooks,
or write durable ledger state.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from kernel.application import why_not_runtime as _why_not_runtime_module
from kernel.application.protocol import derivation_why_not as _why_not_protocol_module

_BANNED_CHECK_MODULES = frozenset(
    {
        "kernel.application.derivation_check_runtime",
        "kernel.application.protocol.derivation_check",
        "derivation_check_runtime",
        "derivation_check",
    }
)

_BANNED_CHECK_SYMBOLS = frozenset(
    {
        "check_derivation_binding",
        "CheckRuntimeError",
        "_native_check",
        "_non_native_check",
        "_souffle_check",
        "_problog_pyreason_check",
        "_request_representability_precheck",
        "_ruleref_preflight",
        "_binding_matches",
        "_invalid_request",
        "CheckRequest",
        "CheckResult",
        "CheckStatus",
        "CheckEngine",
    }
)

_BANNED_PROTOCOL_SYMBOLS = frozenset(
    {
        "DiagnoseResult",
        "DiagnoseAtomLocator",
        "CheckRequest",
        "CheckResult",
        "EvidenceEnvelope",
        "SupportArtifact",
        "ProvenanceEnvelope",
    }
)

_BANNED_DIAGNOSE_RESULT_IMPORTS_IN_RUNTIME = frozenset(
    {
        "DiagnoseResult",
        "DiagnoseAtomLocator",
    }
)

_ALLOWED_DIAGNOSE_RUNTIME_IMPORTS = frozenset(
    {
        "diagnose_derivation_binding",
        "DiagnoseRequest",
    }
)

_BANNED_EVALUATOR_TRACE_NAMES = frozenset(
    {
        "trace",
        "traces",
        "callback",
        "callbacks",
        "near_miss",
        "near_misses",
        "failed_frontier",
        "exclusion_reason",
        "exclusion_reasons",
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
    }
)


def _parse_module(module: object) -> ast.Module:
    filename = getattr(module, "__file__")
    source = Path(filename).read_text(encoding="utf-8")
    return ast.parse(source)


def _imports(tree: ast.AST) -> list[ast.Import | ast.ImportFrom]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]


def _imported_symbols(tree: ast.AST) -> set[str]:
    symbols: set[str] = set()
    for node in _imports(tree):
        for alias in node.names:
            symbols.add(alias.name.rsplit(".", maxsplit=1)[-1])
            if alias.asname:
                symbols.add(alias.asname)
    return symbols


def _annotation_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        annotations: list[ast.AST] = []
        annotation = getattr(node, "annotation", None)
        if annotation is not None:
            annotations.append(annotation)
        if isinstance(node, ast.FunctionDef) and node.returns is not None:
            annotations.append(node.returns)

        for annotation_node in annotations:
            for child in ast.walk(annotation_node):
                if isinstance(child, ast.Name):
                    names.add(child.id)
                elif isinstance(child, ast.Attribute):
                    names.add(child.attr)
                elif isinstance(child, ast.Constant) and isinstance(child.value, str):
                    names.update(
                        banned
                        for banned in _BANNED_PROTOCOL_SYMBOLS
                        | _BANNED_DIAGNOSE_RESULT_IMPORTS_IN_RUNTIME
                        if banned in child.value
                    )
    return names


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class WhyNotSiblingImportInvariantTests(unittest.TestCase):
    """§7-WhyNot-8 / 9: protocol owns DTOs; runtime composes Diagnose only."""

    def test_protocol_has_no_sibling_or_payload_imports_or_annotations(self) -> None:
        tree = _parse_module(_why_not_protocol_module)
        imported = _imported_symbols(tree)
        annotated = _annotation_names(tree)

        self.assertEqual(imported & _BANNED_PROTOCOL_SYMBOLS, set())
        self.assertEqual(annotated & _BANNED_PROTOCOL_SYMBOLS, set())

    def test_runtime_imports_allowed_diagnose_entry_only(self) -> None:
        tree = _parse_module(_why_not_runtime_module)
        imported = _imported_symbols(tree)

        self.assertIn("diagnose_derivation_binding", imported)
        self.assertIn("DiagnoseRequest", imported)
        self.assertEqual(
            imported & _BANNED_DIAGNOSE_RESULT_IMPORTS_IN_RUNTIME,
            set(),
        )
        self.assertLessEqual(
            imported
            & (
                _ALLOWED_DIAGNOSE_RUNTIME_IMPORTS
                | _BANNED_DIAGNOSE_RESULT_IMPORTS_IN_RUNTIME
            ),
            _ALLOWED_DIAGNOSE_RUNTIME_IMPORTS,
        )

    def test_runtime_does_not_import_check_modules_or_symbols(self) -> None:
        tree = _parse_module(_why_not_runtime_module)
        offenders: list[tuple[str, str]] = []
        for node in _imports(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in _BANNED_CHECK_MODULES:
                    for alias in node.names:
                        offenders.append((module, alias.name))
                for alias in node.names:
                    if alias.name in _BANNED_CHECK_SYMBOLS:
                        offenders.append((module or "<relative>", alias.name))
            else:
                for alias in node.names:
                    if alias.name in _BANNED_CHECK_MODULES:
                        offenders.append((alias.name, alias.name))

        self.assertEqual(offenders, [])

    def test_banned_lists_cover_minimum_boundary_surface(self) -> None:
        self.assertEqual(
            {
                "check_derivation_binding",
                "CheckRequest",
                "CheckResult",
                "DiagnoseResult",
                "DiagnoseAtomLocator",
            }
            - (_BANNED_CHECK_SYMBOLS | _BANNED_DIAGNOSE_RESULT_IMPORTS_IN_RUNTIME),
            set(),
        )


class WhyNotEvaluatorAndWriteInvariantTests(unittest.TestCase):
    """§7-WhyNot-13 / 14: no evaluator trace hook and no write substrate."""

    def test_runtime_evaluate_native_where_calls_do_not_request_trace_hooks(self) -> None:
        tree = _parse_module(_why_not_runtime_module)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "evaluate_native_where"
        ]
        self.assertGreaterEqual(len(calls), 1)
        for call in calls:
            keyword_names = {keyword.arg for keyword in call.keywords if keyword.arg}
            self.assertEqual(keyword_names & _BANNED_EVALUATOR_TRACE_NAMES, set())

    def test_runtime_source_does_not_reference_near_miss_trace_concepts(self) -> None:
        tree = _parse_module(_why_not_runtime_module)
        seen_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                seen_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                seen_names.add(node.attr)
        self.assertEqual(seen_names & _BANNED_EVALUATOR_TRACE_NAMES, set())

    def test_runtime_does_not_import_or_call_write_substrates(self) -> None:
        tree = _parse_module(_why_not_runtime_module)
        imported = _imported_symbols(tree)
        called = {
            name
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for name in [_call_name(node)]
            if name is not None
        }

        self.assertEqual(imported & _BANNED_WRITE_CALLS, set())
        self.assertEqual(called & _BANNED_WRITE_CALLS, set())


if __name__ == "__main__":
    unittest.main()
