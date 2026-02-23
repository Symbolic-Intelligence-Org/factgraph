from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from factpy_kernel.authoring import (
    AuthoringRuleDSLParseError,
    compile_authoring_rule_v1,
    parse_authoring_rule_dsl_v1,
)


class AuthoringRuleDSLParseV1Tests(unittest.TestCase):
    def test_parse_rule_dsl_basic_and_compile(self) -> None:
        payload = parse_authoring_rule_dsl_v1(
            """
country_rows = Rule(
    version="v1",
    select=["E", "$C"],
    body=[("pred", "person:country", ["$E", "$C"])],
    public=True
)
"""
        )
        self.assertEqual(payload["name"], "country_rows")
        compiled = compile_authoring_rule_v1(payload)
        self.assertEqual(compiled["rule_id"], "country_rows")
        self.assertEqual(compiled["select_vars"], ["$E", "$C"])
        self.assertTrue(compiled["expose"])

    def test_parse_rule_dsl_keeps_where_literals(self) -> None:
        payload = parse_authoring_rule_dsl_v1(
            """
Rule(
    rule_id="rules.rank_filter",
    select_vars=["$E","$R"],
    where=[
      ("pred","person:rank",["$E","$R"]),
      ("ge","$R",3),
      ("in","$R",[3,5])
    ]
)
"""
        )
        self.assertEqual(payload["rule_id"], "rules.rank_filter")
        self.assertEqual(payload["where"][1], ("ge", "$R", 3))
        self.assertEqual(payload["where"][2], ("in", "$R", [3, 5]))

    def test_parse_rule_dsl_helper_atom_sugar(self) -> None:
        payload = parse_authoring_rule_dsl_v1(
            """
rank_filter = Rule(
    select=["E", "R"],
    where=Or(
        [Pred("person:rank", "$E", "$R"), In("$R", [3, 5]), Ge("$R", 4)],
        [Pred("person:rank", "$E", "$R"), Eq("$R", 9)]
    )
)
"""
        )
        self.assertEqual(payload["name"], "rank_filter")
        self.assertIsInstance(payload["where"], list)
        self.assertIsInstance(payload["where"][0], list)
        self.assertEqual(payload["where"][0][0], ("pred", "person:rank", ["$E", "$R"]))
        self.assertEqual(payload["where"][0][1], ("in", "$R", [3, 5]))
        self.assertEqual(payload["where"][0][2], ("ge", "$R", 4))
        self.assertEqual(payload["where"][1][1], ("eq", "$R", 9))

    def test_parse_rule_dsl_not_sugar(self) -> None:
        payload = parse_authoring_rule_dsl_v1(
            """
Rule(
    select_vars=["$E"],
    where=[
        Pred("person:country", "$E", "de"),
        Not([Pred("person:blacklist", "$E", "x")]),
    ]
)
"""
        )
        self.assertEqual(payload["where"][0], ("pred", "person:country", ["$E", "de"]))
        self.assertEqual(payload["where"][1], ("not", [("pred", "person:blacklist", ["$E", "x"])]))

    def test_parse_rule_dsl_blueprint_where_sugar_with_vars_and_paths(self) -> None:
        payload = parse_authoring_rule_dsl_v1(
            """
with vars() as (li, p, c):
    r = Rule(
        select=["li", "p", "c"],
        where=[
            LivesIn(li),
            li.person == p,
            li.country == c,
        ],
    )
"""
        )
        self.assertEqual(payload["name"], "r")
        self.assertEqual(payload["where"][0], ("pred", "LivesIn:exists", ["$li"]))
        self.assertEqual(payload["where"][1], ("pred", "livesin:person", ["$li", "$p"]))
        self.assertEqual(payload["where"][2], ("pred", "livesin:country", ["$li", "$c"]))

    def test_reject_rule_dsl_positional_args(self) -> None:
        with self.assertRaises(AuthoringRuleDSLParseError):
            parse_authoring_rule_dsl_v1('Rule("x")')

    def test_reject_rule_dsl_unsupported_top_level(self) -> None:
        with self.assertRaises(AuthoringRuleDSLParseError):
            parse_authoring_rule_dsl_v1("def make():\n    return Rule()\n")

    def test_rule_dsl_parse_error_exposes_syntax_kind_and_path(self) -> None:
        with self.assertRaises(AuthoringRuleDSLParseError) as ctx:
            parse_authoring_rule_dsl_v1("Rule(\n")
        self.assertEqual(ctx.exception.kind, "syntax")
        self.assertTrue((ctx.exception.path or "").startswith("$.dsl:line:"))
        self.assertIsNone(getattr(ctx.exception, "details", None))

    def test_rule_dsl_parse_error_exposes_helper_details(self) -> None:
        with self.assertRaises(AuthoringRuleDSLParseError) as ctx:
            parse_authoring_rule_dsl_v1(
                """
Rule(
    where=[In("$R", "bad")]
)
"""
            )
        self.assertEqual(ctx.exception.kind, "structure")
        self.assertEqual(ctx.exception.path, "$.dsl.body[0].where[].args[1]")
        self.assertEqual(ctx.exception.details["dsl_error_detail_code"], "helper_arg_type")
        self.assertEqual(ctx.exception.details["helper"], "In")
        self.assertEqual(ctx.exception.details["arg_index"], 1)

    def test_rule_dsl_parse_error_exposes_unsupported_helper_details(self) -> None:
        with self.assertRaises(AuthoringRuleDSLParseError) as ctx:
            parse_authoring_rule_dsl_v1(
                """
Rule(
    where=[Foo("x")]
)
"""
            )
        self.assertEqual(ctx.exception.kind, "structure")
        self.assertEqual(ctx.exception.path, "$.dsl.body[0].where[]")
        self.assertEqual(ctx.exception.details["dsl_error_detail_code"], "unsupported_helper")
        self.assertEqual(ctx.exception.details["helper"], "Foo")

    def test_fixtures_doc_rule_dsl_examples_shape(self) -> None:
        text = (_docs_root() / "Authoring 层契约 fixtures.md").read_text(encoding="utf-8")
        source = self._extract_code_block_after_header(
            text,
            "### F5-H rule DSL parser（语法层 → Authoring rule payload，最小切片）",
            "python",
            which=1,
        )
        payload = parse_authoring_rule_dsl_v1(source)
        self.assertIn("select", payload)
        json_shape = json.loads(
            self._extract_code_block_after_header(
                text,
                "### F5-H rule DSL parser（语法层 → Authoring rule payload，最小切片）",
                "json",
                which=1,
            )
        )
        self.assertEqual(json_shape["select"][0], "E")
        self.assertEqual(json_shape["body"][0][0], "pred")
        sugar_source = self._extract_code_block_after_header(
            text,
            "### F5-H rule DSL parser（语法层 → Authoring rule payload，最小切片）",
            "python",
            which=2,
        )
        sugar_payload = parse_authoring_rule_dsl_v1(sugar_source)
        self.assertEqual(sugar_payload["where"][0][0][0], "pred")
        self.assertEqual(sugar_payload["where"][0][1][0], "in")
        sugar_shape = json.loads(
            self._extract_code_block_after_header(
                text,
                "### F5-H rule DSL parser（语法层 → Authoring rule payload，最小切片）",
                "json",
                which=2,
            )
        )
        self.assertEqual(sugar_shape["where"][1][1][0], "eq")

    def _extract_code_block_after_header(self, text: str, header: str, lang: str, *, which: int) -> str:
        idx = text.find(header)
        self.assertNotEqual(idx, -1, f"missing header: {header}")
        tail = text[idx:]
        matches = list(re.finditer(rf"```{lang}\s*\n(.*?)\n```", tail, flags=re.S))
        self.assertGreaterEqual(len(matches), which, f"missing code block #{which} lang={lang} after {header}")
        return matches[which - 1].group(1)


def _docs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "docs"


if __name__ == "__main__":
    unittest.main()
