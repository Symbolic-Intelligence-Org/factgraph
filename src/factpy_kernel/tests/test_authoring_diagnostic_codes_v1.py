from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from factpy_kernel.authoring import (
    AUTHORING_DIAGNOSTIC_CODES_V1 as AUTHORING_DIAGNOSTIC_CODES_V1_EXPORTED,
    AUTHORING_DIAGNOSTIC_PHASES_V1 as AUTHORING_DIAGNOSTIC_PHASES_V1_EXPORTED,
    build_diagnostics_contract_meta_v1,
)
from factpy_kernel.authoring.diagnostic_codes import (
    AUTHORING_DIAGNOSTIC_CODES_V1,
    AUTHORING_DIAGNOSTIC_CODES_V1_SET,
    AUTHORING_DIAGNOSTIC_PHASES_V1,
    AUTHORING_DIAGNOSTIC_PHASES_V1_SET,
    AUTHORING_ERROR_CODES_V1,
    AUTHORING_WARNING_CODES_V1,
    CODE_APPLY_BLOCKED_ACTION,
    CODE_APPLY_BLOCKED_ACTIONS_PRESENT,
    CODE_APPLY_PREVALIDATE_BLOCKED_ACTION,
    CODE_APPLY_PREVALIDATE_BLOCKED_ACTIONS_PRESENT,
    CODE_APPLY_SKIPPED_ACTION,
    CODE_APPLY_SKIPPED_ACTIONS_PRESENT,
    CODE_AUTHORING_DERIVATION_DSL_PARSE_ERROR,
    CODE_AUTHORING_DERIVATION_COMPILE_ERROR,
    CODE_AUTHORING_RULE_DSL_PARSE_ERROR,
    CODE_AUTHORING_RULE_COMPILE_ERROR,
    CODE_AUTHORING_SCHEMA_DSL_PARSE_ERROR,
    CODE_AUTHORING_SCHEMA_COMPILE_ERROR,
    CODE_DERIVATION_PREVIEW_ERROR,
    CODE_EMPTY_PREDICATES,
    CODE_PREVIEW_TRUNCATED,
    CODE_PUBLISH_BLOCKED_MISSING_OR_INVALID_SECTION,
    CODE_PUBLISH_BLOCKED_SECTION_ERROR,
    CODE_PUBLISH_SKIPPED_UNSUPPORTED_SECTION,
    CODE_REGISTRY_RULE_ERROR,
    CODE_RULE_COMPILE_ERROR,
    CODE_RULE_SPEC_ERROR,
    CODE_SCHEMA_VALIDATION_ERROR,
    CODE_SOUFFLE_BINARY_MISSING,
    CODE_TEMPORAL_CURRENT_NO_PRED_REFS,
    CODE_TEMPORAL_CURRENT_NO_TEMPORAL_SCHEMA_PREDICATES,
    CODE_TEMPORAL_CURRENT_NO_TEMPORAL_WHERE_PREDICATES,
    PHASE_DERIVATION_AUTHORING_COMPILE,
    PHASE_DERIVATION_DSL_PARSE,
    PHASE_DERIVATION_PREVIEW,
    PHASE_DERIVATION_PREVIEW_ENV,
    PHASE_PUBLISH_APPLY,
    PHASE_PUBLISH_PLAN,
    PHASE_RULE_DSL_PARSE,
    PHASE_RULE_AUTHORING_COMPILE,
    PHASE_RULE_COMPILE,
    PHASE_RULE_PARSE,
    PHASE_RULE_PREFLIGHT,
    PHASE_RULE_REGISTRY,
    PHASE_SCHEMA_AUTHORING_COMPILE,
    PHASE_SCHEMA_DSL_PARSE,
    PHASE_SCHEMA_PREFLIGHT,
    PHASE_SCHEMA_VALIDATE,
)


class AuthoringDiagnosticCodesV1Tests(unittest.TestCase):
    def test_codes_are_unique_and_partitioned(self) -> None:
        self.assertEqual(len(AUTHORING_DIAGNOSTIC_CODES_V1), len(AUTHORING_DIAGNOSTIC_CODES_V1_SET))
        self.assertEqual(
            AUTHORING_DIAGNOSTIC_CODES_V1_SET,
            set(AUTHORING_ERROR_CODES_V1).union(AUTHORING_WARNING_CODES_V1),
        )
        self.assertTrue(set(AUTHORING_ERROR_CODES_V1).isdisjoint(set(AUTHORING_WARNING_CODES_V1)))

    def test_registry_contains_current_preflight_codes(self) -> None:
        expected = {
            CODE_AUTHORING_SCHEMA_COMPILE_ERROR,
            CODE_AUTHORING_SCHEMA_DSL_PARSE_ERROR,
            CODE_SCHEMA_VALIDATION_ERROR,
            CODE_EMPTY_PREDICATES,
            CODE_REGISTRY_RULE_ERROR,
            CODE_RULE_SPEC_ERROR,
            CODE_RULE_COMPILE_ERROR,
            CODE_AUTHORING_RULE_COMPILE_ERROR,
            CODE_AUTHORING_RULE_DSL_PARSE_ERROR,
            CODE_DERIVATION_PREVIEW_ERROR,
            CODE_AUTHORING_DERIVATION_COMPILE_ERROR,
            CODE_AUTHORING_DERIVATION_DSL_PARSE_ERROR,
            CODE_PUBLISH_BLOCKED_SECTION_ERROR,
            CODE_PUBLISH_BLOCKED_MISSING_OR_INVALID_SECTION,
            CODE_APPLY_BLOCKED_ACTION,
            CODE_APPLY_BLOCKED_ACTIONS_PRESENT,
            CODE_APPLY_PREVALIDATE_BLOCKED_ACTION,
            CODE_APPLY_PREVALIDATE_BLOCKED_ACTIONS_PRESENT,
            CODE_PREVIEW_TRUNCATED,
            CODE_SOUFFLE_BINARY_MISSING,
            CODE_TEMPORAL_CURRENT_NO_PRED_REFS,
            CODE_TEMPORAL_CURRENT_NO_TEMPORAL_SCHEMA_PREDICATES,
            CODE_TEMPORAL_CURRENT_NO_TEMPORAL_WHERE_PREDICATES,
            CODE_PUBLISH_SKIPPED_UNSUPPORTED_SECTION,
            CODE_APPLY_SKIPPED_ACTION,
            CODE_APPLY_SKIPPED_ACTIONS_PRESENT,
        }
        self.assertEqual(AUTHORING_DIAGNOSTIC_CODES_V1_SET, expected)

    def test_preflight_uses_registry_constants_for_code_fields(self) -> None:
        preflight_py = Path(__file__).resolve().parents[1] / "authoring" / "preflight.py"
        text = preflight_py.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r'code\\s*=\\s*["\\\']', text))

    def test_phase_registry_contains_current_preflight_phases(self) -> None:
        expected = {
            PHASE_SCHEMA_AUTHORING_COMPILE,
            PHASE_SCHEMA_DSL_PARSE,
            PHASE_SCHEMA_VALIDATE,
            PHASE_SCHEMA_PREFLIGHT,
            PHASE_RULE_DSL_PARSE,
            PHASE_RULE_REGISTRY,
            PHASE_RULE_PARSE,
            PHASE_RULE_PREFLIGHT,
            PHASE_RULE_COMPILE,
            PHASE_RULE_AUTHORING_COMPILE,
            PHASE_DERIVATION_PREVIEW_ENV,
            PHASE_DERIVATION_PREVIEW,
            PHASE_DERIVATION_AUTHORING_COMPILE,
            PHASE_DERIVATION_DSL_PARSE,
            PHASE_PUBLISH_PLAN,
            PHASE_PUBLISH_APPLY,
        }
        self.assertEqual(AUTHORING_DIAGNOSTIC_PHASES_V1_SET, expected)
        self.assertEqual(len(AUTHORING_DIAGNOSTIC_PHASES_V1), len(AUTHORING_DIAGNOSTIC_PHASES_V1_SET))

    def test_preflight_uses_registry_constants_for_phase_fields(self) -> None:
        preflight_py = Path(__file__).resolve().parents[1] / "authoring" / "preflight.py"
        text = preflight_py.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r'phase\\s*=\\s*["\\\']', text))

    def test_docs_examples_and_fixtures_codes_align_with_registry(self) -> None:
        contract_doc = (_docs_root() / "Authoring 层契约.md").read_text(encoding="utf-8")
        fixtures_doc = (_docs_root() / "Authoring 层契约 fixtures.md").read_text(encoding="utf-8")

        contract_codes = self._extract_backtick_items_after_header(
            contract_doc, "现有 warning/code 示例（已实装）："
        )
        fixture_codes = set(re.findall(r'"([a-z0-9_]+)"', fixtures_doc))
        fixture_codes.update(re.findall(r"`([a-z0-9_]+)`", fixtures_doc))
        fixture_codes = {code for code in fixture_codes if code in AUTHORING_DIAGNOSTIC_CODES_V1_SET}

        self.assertTrue(contract_codes)
        self.assertTrue(contract_codes.issubset(set(AUTHORING_WARNING_CODES_V1)))
        self.assertTrue(fixture_codes.issubset(AUTHORING_DIAGNOSTIC_CODES_V1_SET))
        self.assertIn(CODE_EMPTY_PREDICATES, contract_codes)
        self.assertIn(CODE_PREVIEW_TRUNCATED, fixture_codes)
        self.assertIn("authoring_diagnostics_contract_v1", fixtures_doc)
        self.assertIn("diagnostics_contract", fixtures_doc)

    def test_docs_canonical_code_list_matches_registry(self) -> None:
        contract_doc = (_docs_root() / "Authoring 层契约.md").read_text(encoding="utf-8")
        doc_codes = self._extract_backtick_items_after_header(
            contract_doc, "Canonical diagnostics `code` 列表（v1，已实装）："
        )
        self.assertEqual(doc_codes, AUTHORING_DIAGNOSTIC_CODES_V1_SET)

    def test_docs_canonical_phase_list_matches_registry(self) -> None:
        contract_doc = (_docs_root() / "Authoring 层契约.md").read_text(encoding="utf-8")
        doc_phases = self._extract_backtick_items_after_header(
            contract_doc, "Canonical diagnostics `phase` 列表（v1，已实装）："
        )
        self.assertEqual(doc_phases, AUTHORING_DIAGNOSTIC_PHASES_V1_SET)

    def test_authoring_package_exports_diagnostics_registry(self) -> None:
        self.assertEqual(tuple(AUTHORING_DIAGNOSTIC_CODES_V1_EXPORTED), AUTHORING_DIAGNOSTIC_CODES_V1)
        self.assertEqual(tuple(AUTHORING_DIAGNOSTIC_PHASES_V1_EXPORTED), AUTHORING_DIAGNOSTIC_PHASES_V1)
        meta = build_diagnostics_contract_meta_v1()
        self.assertEqual(meta["diagnostics_contract_version"], "authoring_diagnostics_contract_v1")
        self.assertEqual(meta["codes"], list(AUTHORING_DIAGNOSTIC_CODES_V1))
        self.assertEqual(meta["phases"], list(AUTHORING_DIAGNOSTIC_PHASES_V1))

    def test_docs_canonical_diagnostics_contract_snippet_matches_helper(self) -> None:
        contract_doc = (_docs_root() / "Authoring 层契约.md").read_text(encoding="utf-8")
        snippet = self._extract_json_code_block_after_header(
            contract_doc,
            "Canonical `diagnostics_contract` 片段（嵌入 `authoring_ui_dto_v1` / `authoring_session_dto_v1` 顶层，v1，已实装）：",
        )
        self.assertEqual(snippet, {"diagnostics_contract": build_diagnostics_contract_meta_v1()})

    def test_docs_reserved_v2_codes_are_not_in_canonical_registry(self) -> None:
        contract_doc = (_docs_root() / "Authoring 层契约.md").read_text(encoding="utf-8")
        fixtures_doc = (_docs_root() / "Authoring 层契约 fixtures.md").read_text(encoding="utf-8")
        reserved_codes = {
            "apply_v2_prevalidate_blocked_actions_present",
            "apply_v2_partial_apply_forbidden",
            "apply_v2_transaction_policy_unsupported",
        }
        for code in reserved_codes:
            self.assertIn(code, contract_doc)
            self.assertIn(code, fixtures_doc)
            self.assertNotIn(code, AUTHORING_DIAGNOSTIC_CODES_V1_SET)
        self.assertIn("spec-only", fixtures_doc)
        self.assertIn("不得把上述预留 codes 加入 canonical `code` 列表", contract_doc)
        self.assertIn('phase="publish.apply"', contract_doc)

    def _extract_backtick_items_after_header(self, text: str, header: str) -> set[str]:
        idx = text.find(header)
        self.assertNotEqual(idx, -1, f"missing header: {header}")
        out: set[str] = set()
        for line in text[idx:].splitlines()[1:50]:
            stripped = line.strip()
            if not stripped:
                if out:
                    break
                continue
            if not stripped.startswith("- "):
                if out:
                    break
                continue
            match = re.search(r"`([^`]+)`", stripped)
            if match:
                out.add(match.group(1))
        return out

    def _extract_json_code_block_after_header(self, text: str, header: str) -> dict:
        idx = text.find(header)
        self.assertNotEqual(idx, -1, f"missing header: {header}")
        tail = text[idx:]
        match = re.search(r"```json\s*\n(.*?)\n```", tail, flags=re.S)
        self.assertIsNotNone(match, f"missing json code block after: {header}")
        return json.loads(match.group(1))


def _docs_root() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "blueprint"


if __name__ == "__main__":
    unittest.main()
