"""§7-Overlay-1 anti-regression: Sibling no-Check-call invariant.

Verifies that the Fact Overlay runtime module never imports Check runtime
helpers, public Check entry points, Check protocol DTOs, or engine-native
artifact payload types at the import-graph level.

Mechanism: AST walk over ``fact_overlay_runtime.py`` source. The scan inspects
``Import`` / ``ImportFrom`` nodes without executing the module. Local helper
definitions are allowed; imported Check symbols are not.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from factgraph.application import fact_overlay_runtime as _fact_overlay_runtime_module

_BANNED_MODULES = frozenset(
    {
        "factgraph.application.derivation_check_runtime",
        "factgraph.application.protocol.derivation_check",
    }
)

_BANNED_SYMBOLS = frozenset(
    {
        # Public Check runtime
        "check_derivation_binding",
        "CheckRuntimeError",
        # Check runtime private helpers
        "_native_check",
        "_non_native_check",
        "_souffle_check",
        "_problog_pyreason_check",
        "_request_representability_precheck",
        "_ruleref_preflight",
        "_invalid_request",
        "_find_ruleref_atoms",
        "_extract_head_var_binding",
        "_extract_term_value",
        "_determine_root_result_kind",
        "_derive_case_index_from_artifact",
        "_parse_case_index",
        "_lookup_support_artifact",
        "_lookup_provenance_envelope",
        # Check protocol DTOs and engine-native payload channel
        "CheckRequest",
        "CheckResult",
        "CheckStatus",
        "CheckEngine",
        "EvidenceEnvelope",
        "ProofReceipt",
        "ProvenanceEnvelope",
    }
)


def _fact_overlay_runtime_imports() -> list[ast.AST]:
    source = Path(_fact_overlay_runtime_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]


class FactOverlaySiblingBannedSymbolTests(unittest.TestCase):
    """§7-Overlay-1: Overlay runtime must not reach into Check runtime."""

    def test_no_imports_from_banned_modules(self) -> None:
        offenders: list[tuple[str, str]] = []
        for node in _fact_overlay_runtime_imports():
            if isinstance(node, ast.ImportFrom):
                module = node.module
                if module and module in _BANNED_MODULES:
                    for alias in node.names:
                        offenders.append((module, alias.name))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in _BANNED_MODULES:
                        offenders.append((alias.name, alias.name))
        self.assertEqual(
            offenders,
            [],
            f"Fact Overlay runtime imports banned Check modules: {offenders}",
        )

    def test_no_imports_of_banned_symbols(self) -> None:
        offenders: list[tuple[str, str]] = []
        for node in _fact_overlay_runtime_imports():
            if not isinstance(node, ast.ImportFrom):
                continue
            for alias in node.names:
                if alias.name in _BANNED_SYMBOLS:
                    offenders.append((node.module or "<top>", alias.name))
        self.assertEqual(
            offenders,
            [],
            f"Fact Overlay runtime imports banned Check symbols: {offenders}",
        )

    def test_banned_list_covers_check_runtime_minimum_surface(self) -> None:
        required_minimum = {
            "check_derivation_binding",
            "CheckRuntimeError",
            "_native_check",
            "_souffle_check",
            "_problog_pyreason_check",
            "_request_representability_precheck",
            "_ruleref_preflight",
            "CheckRequest",
            "CheckResult",
            "EvidenceEnvelope",
        }
        missing = required_minimum - _BANNED_SYMBOLS
        self.assertEqual(
            missing,
            set(),
            f"banned-symbol list missing required entries: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
