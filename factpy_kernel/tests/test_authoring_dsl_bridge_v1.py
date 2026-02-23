from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from factpy_kernel.authoring import (
    AuthoringDSLBridgeError,
    build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_dto,
    build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_safe_dto,
    build_authoring_session_from_dsl_inputs_dto,
    build_authoring_session_from_dsl_inputs_safe_dto,
)
from factpy_kernel.authoring.diagnostic_codes import (
    CODE_AUTHORING_DERIVATION_DSL_PARSE_ERROR,
    CODE_AUTHORING_RULE_DSL_PARSE_ERROR,
    CODE_AUTHORING_SCHEMA_DSL_PARSE_ERROR,
    PHASE_DERIVATION_DSL_PARSE,
    PHASE_RULE_DSL_PARSE,
    PHASE_SCHEMA_DSL_PARSE,
)


_SCHEMA_DSL = """
class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional")
"""

_RULE_DSL = """
country_rows = Rule(
    version="v1",
    select=["E", "$C"],
    body=[("pred", "person:country", ["$E", "$C"])],
    public=True
)
"""

_DERIVATION_DSL = """
country_derivation = Derivation(
    target="person:country",
    select=["E", "country"],
    body=[("pred", "person:country", ["$E", "$country"])],
    mode="python",
    temporal_view="record"
)
"""


class AuthoringDSLBridgeV1Tests(unittest.TestCase):
    def test_build_session_from_dsl_inputs(self) -> None:
        session = build_authoring_session_from_dsl_inputs_dto(
            schema_dsl=_SCHEMA_DSL,
            rule_dsl=_RULE_DSL,
            derivation_dsl=_DERIVATION_DSL,
        )
        self.assertEqual(session["authoring_session_dto_version"], "authoring_session_dto_v1")
        self.assertEqual(session["kind"], "authoring_session")
        self.assertEqual(session["order"], ["schema_preflight", "rule_preflight", "derivation_preview"])
        self.assertIn(session["status"], {"ok", "warning"})
        self.assertEqual(session["sections"]["rule_preflight"]["kind"], "rule_preflight")
        self.assertEqual(session["sections"]["derivation_preview"]["kind"], "derivation_preview")

    def test_build_workflow_bundle_from_dsl_inputs(self) -> None:
        bundle = build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_dto(
            schema_dsl=_SCHEMA_DSL,
            rule_dsl=_RULE_DSL,
            derivation_dsl=_DERIVATION_DSL,
        )
        self.assertEqual(
            bundle["authoring_publish_workflow_bundle_dto_version"],
            "authoring_publish_workflow_bundle_dto_v1",
        )
        self.assertEqual(bundle["kind"], "authoring_publish_workflow_bundle")
        self.assertEqual(bundle["publish_plan"]["kind"], "authoring_publish_plan")
        self.assertEqual(bundle["apply_result"]["kind"], "authoring_apply_result")

    def test_bridge_wraps_schema_dsl_parse_error(self) -> None:
        with self.assertRaises(AuthoringDSLBridgeError):
            build_authoring_session_from_dsl_inputs_dto(schema_dsl="class Person(Entity)\n    x: str = Identity()\n")

    def test_bridge_requires_schema_or_store_for_rule(self) -> None:
        with self.assertRaises(AuthoringDSLBridgeError):
            build_authoring_session_from_dsl_inputs_dto(rule_dsl=_RULE_DSL)

    def test_safe_bridge_returns_session_diagnostics_for_schema_parse_error(self) -> None:
        session = build_authoring_session_from_dsl_inputs_safe_dto(
            schema_dsl="class Person(Entity)\n    source_id: str = Identity()\n"
        )
        self.assertFalse(session["ok"])
        self.assertEqual(session["status"], "error")
        section = session["sections"]["schema_preflight"]
        self.assertEqual(section["source_kind"], "dsl_parse")
        self.assertEqual(section["diagnostics"][0]["code"], CODE_AUTHORING_SCHEMA_DSL_PARSE_ERROR)
        self.assertEqual(section["diagnostics"][0]["phase"], PHASE_SCHEMA_DSL_PARSE)
        self.assertTrue(section["diagnostics"][0]["path"].startswith("$.schema_dsl"))
        self.assertEqual(section["diagnostics"][0]["dsl_error_kind"], "syntax")

    def test_safe_bridge_schema_parse_error_includes_top_level_statement_details(self) -> None:
        session = build_authoring_session_from_dsl_inputs_safe_dto(
            schema_dsl="def f():\n    return 1\n"
        )
        diagnostic = session["sections"]["schema_preflight"]["diagnostics"][0]
        self.assertEqual(diagnostic["code"], CODE_AUTHORING_SCHEMA_DSL_PARSE_ERROR)
        self.assertEqual(diagnostic["phase"], PHASE_SCHEMA_DSL_PARSE)
        self.assertEqual(diagnostic["path"], "$.schema_dsl.body[0]")
        self.assertEqual(diagnostic["dsl_error_kind"], "structure")
        self.assertEqual(diagnostic["details"]["dsl_error_detail_code"], "unsupported_top_level_statement")
        self.assertEqual(diagnostic["details"]["statement_type"], "FunctionDef")

    def test_safe_bridge_schema_parse_error_includes_unsupported_keywords_details(self) -> None:
        session = build_authoring_session_from_dsl_inputs_safe_dto(
            schema_dsl="""
class Person(Entity):
    source_id: str = Identity()
    age: int = Field(cardinality="functional", bad_kw=True)
"""
        )
        diagnostic = session["sections"]["schema_preflight"]["diagnostics"][0]
        self.assertEqual(diagnostic["code"], CODE_AUTHORING_SCHEMA_DSL_PARSE_ERROR)
        self.assertEqual(diagnostic["phase"], PHASE_SCHEMA_DSL_PARSE)
        self.assertEqual(diagnostic["path"], "$.schema_dsl.entities[0].body[1].Field")
        self.assertEqual(diagnostic["dsl_error_kind"], "structure")
        self.assertEqual(diagnostic["details"]["dsl_error_detail_code"], "unsupported_keywords")
        self.assertEqual(diagnostic["details"]["call_name"], "Field")
        self.assertEqual(diagnostic["details"]["unsupported_keywords"], "bad_kw")

    def test_safe_bridge_returns_mixed_sections_with_rule_parse_error(self) -> None:
        session = build_authoring_session_from_dsl_inputs_safe_dto(
            schema_dsl=_SCHEMA_DSL,
            rule_dsl='Rule("bad")',
        )
        self.assertFalse(session["ok"])
        self.assertEqual(session["status"], "error")
        self.assertEqual(session["order"], ["schema_preflight", "rule_preflight"])
        self.assertTrue(session["sections"]["schema_preflight"]["kind"] == "schema_preflight")
        rule_section = session["sections"]["rule_preflight"]
        self.assertEqual(rule_section["source_kind"], "dsl_parse")
        self.assertEqual(rule_section["diagnostics"][0]["code"], CODE_AUTHORING_RULE_DSL_PARSE_ERROR)
        self.assertEqual(rule_section["diagnostics"][0]["phase"], PHASE_RULE_DSL_PARSE)
        self.assertEqual(rule_section["diagnostics"][0]["path"], "$.rule_dsl.body[0].args")
        self.assertEqual(rule_section["diagnostics"][0]["dsl_error_kind"], "structure")

    def test_safe_bridge_rule_parse_error_retains_granular_helper_path(self) -> None:
        session = build_authoring_session_from_dsl_inputs_safe_dto(
            schema_dsl=_SCHEMA_DSL,
            rule_dsl="""
Rule(
    where=[Pred()]
)
""",
        )
        rule_section = session["sections"]["rule_preflight"]
        diagnostic = rule_section["diagnostics"][0]
        self.assertEqual(diagnostic["code"], CODE_AUTHORING_RULE_DSL_PARSE_ERROR)
        self.assertEqual(diagnostic["phase"], PHASE_RULE_DSL_PARSE)
        self.assertEqual(diagnostic["path"], "$.rule_dsl.body[0].where[]")
        self.assertEqual(diagnostic["dsl_error_kind"], "structure")
        self.assertEqual(diagnostic["details"]["dsl_error_detail_code"], "helper_arity")
        self.assertEqual(diagnostic["details"]["helper"], "Pred")

    def test_safe_bridge_rule_parse_error_includes_unsupported_helper_details(self) -> None:
        session = build_authoring_session_from_dsl_inputs_safe_dto(
            schema_dsl=_SCHEMA_DSL,
            rule_dsl="""
Rule(
    where=[Foo("x")]
)
""",
        )
        diagnostic = session["sections"]["rule_preflight"]["diagnostics"][0]
        self.assertEqual(diagnostic["code"], CODE_AUTHORING_RULE_DSL_PARSE_ERROR)
        self.assertEqual(diagnostic["phase"], PHASE_RULE_DSL_PARSE)
        self.assertEqual(diagnostic["path"], "$.rule_dsl.body[0].where[]")
        self.assertEqual(diagnostic["dsl_error_kind"], "structure")
        self.assertEqual(diagnostic["details"]["dsl_error_detail_code"], "unsupported_helper")
        self.assertEqual(diagnostic["details"]["helper"], "Foo")

    def test_safe_bridge_rule_parse_error_includes_helper_kwargs_details(self) -> None:
        session = build_authoring_session_from_dsl_inputs_safe_dto(
            schema_dsl=_SCHEMA_DSL,
            rule_dsl="""
Rule(
    where=[Pred("person:country", e="$E")]
)
""",
        )
        diagnostic = session["sections"]["rule_preflight"]["diagnostics"][0]
        self.assertEqual(diagnostic["code"], CODE_AUTHORING_RULE_DSL_PARSE_ERROR)
        self.assertEqual(diagnostic["phase"], PHASE_RULE_DSL_PARSE)
        self.assertEqual(diagnostic["path"], "$.rule_dsl.body[0].where[].keywords")
        self.assertEqual(diagnostic["dsl_error_kind"], "structure")
        self.assertEqual(diagnostic["details"]["dsl_error_detail_code"], "helper_kwargs_not_supported")
        self.assertEqual(diagnostic["details"]["helper"], "Pred")

    def test_safe_bridge_rule_parse_error_includes_helper_arg_type_details(self) -> None:
        session = build_authoring_session_from_dsl_inputs_safe_dto(
            schema_dsl=_SCHEMA_DSL,
            rule_dsl="""
Rule(
    where=[In("$R", "bad")]
)
""",
        )
        diagnostic = session["sections"]["rule_preflight"]["diagnostics"][0]
        self.assertEqual(diagnostic["code"], CODE_AUTHORING_RULE_DSL_PARSE_ERROR)
        self.assertEqual(diagnostic["phase"], PHASE_RULE_DSL_PARSE)
        self.assertEqual(diagnostic["path"], "$.rule_dsl.body[0].where[].args[1]")
        self.assertEqual(diagnostic["dsl_error_kind"], "structure")
        self.assertEqual(diagnostic["details"]["dsl_error_detail_code"], "helper_arg_type")
        self.assertEqual(diagnostic["details"]["helper"], "In")
        self.assertEqual(diagnostic["details"]["arg_index"], 1)

    def test_safe_bridge_workflow_bundle_from_parse_error_session(self) -> None:
        bundle = build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_safe_dto(
            schema_dsl=_SCHEMA_DSL,
            rule_dsl='Rule("bad")',
        )
        self.assertFalse(bundle["ok"])
        self.assertEqual(bundle["status"], "error")
        self.assertEqual(bundle["session"]["status"], "error")
        self.assertEqual(bundle["publish_plan"]["status"], "error")
        self.assertEqual(bundle["apply_result"]["status"], "error")

    def test_safe_bridge_derivation_parse_error_includes_helper_kwargs_details(self) -> None:
        session = build_authoring_session_from_dsl_inputs_safe_dto(
            schema_dsl=_SCHEMA_DSL,
            derivation_dsl="""
Derivation(
    target="person:country",
    select=["E", "C"],
    body=[Pred("person:country", e="$E")]
)
""",
        )
        diagnostic = session["sections"]["derivation_preview"]["diagnostics"][0]
        self.assertEqual(diagnostic["code"], CODE_AUTHORING_DERIVATION_DSL_PARSE_ERROR)
        self.assertEqual(diagnostic["phase"], PHASE_DERIVATION_DSL_PARSE)
        self.assertEqual(diagnostic["path"], "$.derivation_dsl.body[0].body[].keywords")
        self.assertEqual(diagnostic["dsl_error_kind"], "structure")
        self.assertEqual(diagnostic["details"]["dsl_error_detail_code"], "helper_kwargs_not_supported")
        self.assertEqual(diagnostic["details"]["helper"], "Pred")

    def test_safe_bridge_derivation_parse_error_includes_helper_arg_type_details(self) -> None:
        session = build_authoring_session_from_dsl_inputs_safe_dto(
            schema_dsl=_SCHEMA_DSL,
            derivation_dsl="""
Derivation(
    target_pred_id="person:rank",
    head_vars=["$E", "$R"],
    where=[In("$R", "bad")]
)
""",
        )
        diagnostic = session["sections"]["derivation_preview"]["diagnostics"][0]
        self.assertEqual(diagnostic["code"], CODE_AUTHORING_DERIVATION_DSL_PARSE_ERROR)
        self.assertEqual(diagnostic["phase"], PHASE_DERIVATION_DSL_PARSE)
        self.assertEqual(diagnostic["path"], "$.derivation_dsl.body[0].where[].args[1]")
        self.assertEqual(diagnostic["dsl_error_kind"], "structure")
        self.assertEqual(diagnostic["details"]["dsl_error_detail_code"], "helper_arg_type")
        self.assertEqual(diagnostic["details"]["helper"], "In")
        self.assertEqual(diagnostic["details"]["arg_index"], 1)

    def test_fixtures_doc_dsl_bridge_example_shape(self) -> None:
        text = (_docs_root() / "Authoring 层契约 fixtures.md").read_text(encoding="utf-8")
        snippet = self._extract_json_code_block_after_header(
            text,
            "### F5-J DSL bridge（DSL source → session/workflow dry-run DTO，最小切片）",
        )
        self.assertEqual(
            snippet["authoring_publish_workflow_bundle_dto_version"],
            "authoring_publish_workflow_bundle_dto_v1",
        )
        self.assertEqual(snippet["kind"], "authoring_publish_workflow_bundle")
        self.assertEqual(snippet["mode"], "dry_run_only")
        self.assertIn("publish_plan_status", snippet["summary"])
        diag_snippet = self._extract_json_code_block_after_header(
            text,
            "### F5-J DSL bridge（DSL source → session/workflow dry-run DTO，最小切片）",
            which=2,
        )
        self.assertEqual(diag_snippet["code"], CODE_AUTHORING_RULE_DSL_PARSE_ERROR)
        self.assertEqual(diag_snippet["phase"], PHASE_RULE_DSL_PARSE)
        self.assertEqual(diag_snippet["dsl_error_kind"], "structure")
        self.assertEqual(diag_snippet["details"]["dsl_error_detail_code"], "helper_arg_type")
        self.assertEqual(diag_snippet["details"]["helper"], "In")
        self.assertEqual(diag_snippet["details"]["arg_index"], 1)

    def _extract_json_code_block_after_header(self, text: str, header: str, *, which: int = 1) -> dict:
        idx = text.find(header)
        self.assertNotEqual(idx, -1, f"missing header: {header}")
        tail = text[idx:]
        matches = list(re.finditer(r"```json\s*\n(.*?)\n```", tail, flags=re.S))
        self.assertGreaterEqual(len(matches), which, f"missing json code block #{which} after: {header}")
        return json.loads(matches[which - 1].group(1))


def _docs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "docs"


if __name__ == "__main__":
    unittest.main()
