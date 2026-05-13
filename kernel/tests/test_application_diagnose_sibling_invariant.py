"""§7-Diagnose-3 anti-regression: Q1 Sibling no-Check-call invariant (static check).

Verifies that the Diagnose runtime module never imports Check runtime helpers,
public Check entry points, or Check protocol DTOs at the import-graph level.
The banned-symbol list is maintained alongside this test; extend when new
Check internals appear (per audit C7 §7-Diagnose-3).

Mechanism: AST walk over ``diagnose_runtime.py`` source. The audit deliberately
left the mechanism unspecified at altitude; this implementation parses the
runtime file via ``ast.parse`` and inspects ``Import`` / ``ImportFrom`` nodes
without executing the module. Same-named local helpers (e.g.,
``_lookup_support_artifact``, ``_derive_branch_index_from_artifact``,
``_parse_branch_index``, ``_extract_head_var_binding``) are permitted because
Diagnose owns its own copies per D11 — the scan only flags IMPORT statements,
not local definitions.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from kernel.application import diagnose_runtime as _diagnose_runtime_module

# Modules that the Diagnose runtime must never import from.
# Importing any of these would bring Check runtime symbols or Check-protocol
# DTOs into Diagnose's substrate — forbidden per Q1 Sibling supersede.
_BANNED_MODULES = frozenset(
    {
        "kernel.application.derivation_check_runtime",
        "kernel.application.protocol.derivation_check",
    }
)

# Symbols that indicate a Sibling invariant violation if imported by name.
# Covers Check's public + private runtime surface and Check protocol DTO
# names. Diagnose uses locally-defined helpers with some identical names
# (e.g., ``_lookup_support_artifact``); same-named LOCAL DEFINITIONS are fine
# because this scan inspects only import statements.
_BANNED_SYMBOLS = frozenset(
    {
        # Public Check runtime
        "check_derivation_binding",
        "CheckRuntimeError",
        # Check runtime private helpers
        "_native_check",
        "_souffle_check",
        "_problog_pyreason_check",
        "_request_representability_precheck",
        "_ruleref_preflight",
        "_binding_matches",
        "_invalid_request",
        "_extract_head_var_binding",
        "_extract_term_value",
        "_derive_branch_index_from_artifact",
        "_parse_branch_index",
        "_lookup_support_artifact",
        "_lookup_provenance_envelope",
        # Check protocol DTOs (Diagnose redeclares its Status / Engine
        # Literals locally per D5)
        "CheckRequest",
        "CheckResult",
        "CheckStatus",
        "CheckEngine",
        "EvidenceEnvelope",
    }
)


def _diagnose_runtime_imports() -> list[ast.AST]:
    source = Path(_diagnose_runtime_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]


class DiagnoseSiblingBannedSymbolTests(unittest.TestCase):
    """§7-Diagnose-3: Diagnose runtime must not reach into Check runtime."""

    def test_no_imports_from_banned_modules(self) -> None:
        offenders: list[tuple[str, str]] = []
        for node in _diagnose_runtime_imports():
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
            f"Diagnose runtime imports banned Check modules: {offenders}",
        )

    def test_no_imports_of_banned_symbols(self) -> None:
        offenders: list[tuple[str, str]] = []
        for node in _diagnose_runtime_imports():
            if not isinstance(node, ast.ImportFrom):
                continue
            for alias in node.names:
                if alias.name in _BANNED_SYMBOLS:
                    offenders.append((node.module or "<top>", alias.name))
        self.assertEqual(
            offenders,
            [],
            f"Diagnose runtime imports banned Check symbols: {offenders}",
        )

    def test_banned_list_covers_check_runtime_minimum_surface(self) -> None:
        # Maintenance floor: when Check adds new public exports or private
        # helpers, the banned list must be extended to track them. This
        # assertion does not enumerate every Check symbol (that would tie the
        # test to Check internals); it pins the minimum coverage.
        required_minimum = {
            "check_derivation_binding",
            "CheckRuntimeError",
            "_request_representability_precheck",
            "_ruleref_preflight",
            "_binding_matches",
        }
        missing = required_minimum - _BANNED_SYMBOLS
        self.assertEqual(
            missing,
            set(),
            f"banned-symbol list missing required entries: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
