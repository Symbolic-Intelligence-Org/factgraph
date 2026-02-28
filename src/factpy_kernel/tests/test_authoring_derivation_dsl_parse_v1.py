from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from factpy_kernel.authoring import (
    AuthoringDerivationDSLParseError,
    compile_authoring_derivation_v1,
    parse_authoring_derivation_dsl_v1,
)


class AuthoringDerivationDSLParseV1Tests(unittest.TestCase):
    def test_parse_derivation_dsl_basic_and_compile(self) -> None:
        payload = parse_authoring_derivation_dsl_v1(
            """
country_derivation = Derivation(
    target="person:country",
    select=["E", "country"],
    body=[("pred","person:country",["$E","$country"])],
    mode="python",
    temporal_view="record"
)
"""
        )
        self.assertEqual(payload["name"], "country_derivation")
        compiled = compile_authoring_derivation_v1(payload)
        self.assertEqual(compiled["derivation_id"], "country_derivation")
        self.assertEqual(compiled["target_pred_id"], "person:country")
        self.assertEqual(compiled["head_vars"], ["$E", "$country"])

    def test_parse_derivation_dsl_with_literals(self) -> None:
        payload = parse_authoring_derivation_dsl_v1(
            """
Derivation(
  derivation_id="drv.rank_ge_3",
  target_pred_id="person:rank",
  head_vars=["$E", "$R"],
  where=[("pred","person:rank",["$E","$R"]), ("ge","$R",3)],
  mode="engine",
  temporal_view="current"
)
"""
        )
        self.assertEqual(payload["mode"], "engine")
        self.assertEqual(payload["temporal_view"], "current")
        self.assertEqual(payload["where"][1], ("ge", "$R", 3))

    def test_parse_derivation_dsl_helper_atom_sugar(self) -> None:
        payload = parse_authoring_derivation_dsl_v1(
            """
Derivation(
  target="person:rank",
  select=["E","R"],
  body=Or(
    [Pred("person:rank", "$E", "$R"), In("$R", [3,5]), Gt("$R", 3)],
    [Pred("person:rank", "$E", "$R"), Eq("$R", 9)]
  ),
  mode="engine"
)
"""
        )
        self.assertEqual(payload["target"], "person:rank")
        self.assertEqual(payload["body"][0][0], ("pred", "person:rank", ["$E", "$R"]))
        self.assertEqual(payload["body"][0][1], ("in", "$R", [3, 5]))
        self.assertEqual(payload["body"][0][2], ("gt", "$R", 3))
        self.assertEqual(payload["body"][1][1], ("eq", "$R", 9))

    def test_parse_derivation_dsl_head_materialize_as_shape(self) -> None:
        payload = parse_authoring_derivation_dsl_v1(
            """
Derivation(
  derivation_id="drv.speaks",
  target="person:speaks",
  head_vars=["$E", "$L"],
  head=Person.speaks(person=p, language=l),
  body=[Pred("person:speaks", "$E", "$L")],
  materialize_as="fact"
)
"""
        )
        self.assertEqual(payload["materialize_as"], "fact")
        self.assertEqual(payload["head"]["kind"], "head_call")
        self.assertEqual(payload["head"]["callee_kind"], "pred_ref")
        self.assertEqual(payload["head"]["entity_type"], "Person")
        self.assertEqual(payload["head"]["field"], "speaks")
        self.assertEqual(payload["head"]["kwargs"]["person"], "$p")
        self.assertEqual(payload["head"]["kwargs"]["language"], "$l")

    def test_parse_derivation_dsl_blueprint_where_sugar_with_vars_and_paths(self) -> None:
        payload = parse_authoring_derivation_dsl_v1(
            """
with vars() as (p, c, l, li, hl):
    SpeaksDerive = Derivation(
        head=Speaks(person=p, language=l),
        materialize_as="record",
        id_policy={"kind": "key_tuple_digest_v1"},
        where=[
            LivesIn(li),
            HasLanguage(hl),
            li.person == p,
            li.country == c,
            hl.country == c,
            hl.language == l,
        ],
    )
"""
        )
        self.assertEqual(payload["name"], "SpeaksDerive")
        self.assertEqual(payload["head"]["callee_kind"], "entity_type")
        self.assertEqual(payload["head"]["entity_type"], "Speaks")
        self.assertEqual(payload["where"][0], ("pred", "LivesIn:exists", ["$li"]))
        self.assertEqual(payload["where"][1], ("pred", "HasLanguage:exists", ["$hl"]))
        self.assertEqual(payload["where"][2], ("pred", "livesin:person", ["$li", "$p"]))
        self.assertEqual(payload["where"][3], ("pred", "livesin:country", ["$li", "$c"]))
        self.assertEqual(payload["where"][4], ("pred", "haslanguage:country", ["$hl", "$c"]))
        self.assertEqual(payload["where"][5], ("pred", "haslanguage:language", ["$hl", "$l"]))

    def test_parse_derivation_dsl_not_sugar(self) -> None:
        payload = parse_authoring_derivation_dsl_v1(
            """
Derivation(
  target_pred_id="person:country",
  head_vars=["$E", "$C"],
  where=[
    Pred("person:country", "$E", "$C"),
    Not([Pred("person:blacklist", "$E", "x")])
  ]
)
"""
        )
        self.assertEqual(payload["where"][1], ("not", [("pred", "person:blacklist", ["$E", "x"])]))

    def test_parse_derivation_dsl_supports_infix_comparators_and_ruleref_nested_call(self) -> None:
        payload = parse_authoring_derivation_dsl_v1(
            """
with vars() as (e, c):
    Derivation(
      derivation_id="drv.country_copy",
      target="person:country_copy",
      select=["e", "c"],
      where=[
        RuleRef("q_country", version="1.0.0")(e, c),
        c != "xx",
        c >= "aa"
      ]
    )
"""
        )
        self.assertEqual(payload["where"][0], ("ruleref", "q_country", "1.0.0", ["$e", "$c"]))
        self.assertEqual(payload["where"][1], ("not", [("eq", "$c", "xx")]))
        self.assertEqual(payload["where"][2], ("ge", "$c", "aa"))

    def test_reject_derivation_dsl_positional_args(self) -> None:
        with self.assertRaises(AuthoringDerivationDSLParseError):
            parse_authoring_derivation_dsl_v1('Derivation("x")')

    def test_reject_derivation_dsl_unsupported_top_level(self) -> None:
        with self.assertRaises(AuthoringDerivationDSLParseError):
            parse_authoring_derivation_dsl_v1("class X: pass\n")

    def test_derivation_dsl_parse_error_exposes_syntax_kind_and_path(self) -> None:
        with self.assertRaises(AuthoringDerivationDSLParseError) as ctx:
            parse_authoring_derivation_dsl_v1("Derivation(\n")
        self.assertEqual(ctx.exception.kind, "syntax")
        self.assertTrue((ctx.exception.path or "").startswith("$.dsl:line:"))
        self.assertIsNone(getattr(ctx.exception, "details", None))

    def test_derivation_dsl_parse_error_exposes_helper_kwargs_details(self) -> None:
        with self.assertRaises(AuthoringDerivationDSLParseError) as ctx:
            parse_authoring_derivation_dsl_v1(
                """
Derivation(
    target="person:country",
    select=["E", "C"],
    body=[Pred("person:country", e="$E")]
)
"""
            )
        self.assertEqual(ctx.exception.kind, "structure")
        self.assertEqual(ctx.exception.path, "$.dsl.body[0].body[].keywords")
        self.assertEqual(ctx.exception.details["dsl_error_detail_code"], "helper_kwargs_not_supported")
        self.assertEqual(ctx.exception.details["helper"], "Pred")

    def test_derivation_dsl_parse_error_exposes_helper_arg_type_details(self) -> None:
        with self.assertRaises(AuthoringDerivationDSLParseError) as ctx:
            parse_authoring_derivation_dsl_v1(
                """
Derivation(
    target_pred_id="person:rank",
    head_vars=["$E", "$R"],
    where=[In("$R", "bad")]
)
"""
            )
        self.assertEqual(ctx.exception.kind, "structure")
        self.assertEqual(ctx.exception.path, "$.dsl.body[0].where[].args[1]")
        self.assertEqual(ctx.exception.details["dsl_error_detail_code"], "helper_arg_type")
        self.assertEqual(ctx.exception.details["helper"], "In")
        self.assertEqual(ctx.exception.details["arg_index"], 1)

    def test_derivation_dsl_parse_error_rejects_invalid_head_shape(self) -> None:
        with self.assertRaises(AuthoringDerivationDSLParseError) as ctx:
            parse_authoring_derivation_dsl_v1(
                """
Derivation(
    target="person:country",
    head_vars=["$E", "$C"],
    head=Fn(Person.speaks(person=p, language=l))
)
"""
            )
        self.assertEqual(ctx.exception.kind, "structure")
        self.assertIn("$.dsl.body[0].head", ctx.exception.path or "")

    def test_fixtures_doc_derivation_dsl_examples_shape(self) -> None:
        text = (_docs_root() / "Authoring 层契约 fixtures.md").read_text(encoding="utf-8")
        source = self._extract_code_block_after_header(
            text,
            "### F5-I derivation DSL parser（语法层 → Authoring derivation payload，最小切片）",
            "python",
            which=1,
        )
        payload = parse_authoring_derivation_dsl_v1(source)
        self.assertIn("head", payload)
        self.assertEqual(payload["head"]["callee_kind"], "pred_ref")
        self.assertEqual(payload["head"]["entity_type"], "Person")
        self.assertEqual(payload["head"]["field"], "country")
        json_shape = json.loads(
            self._extract_code_block_after_header(
                text,
                "### F5-I derivation DSL parser（语法层 → Authoring derivation payload，最小切片）",
                "json",
                which=1,
            )
        )
        self.assertEqual(json_shape["head"]["entity_type"], "Person")
        self.assertEqual(json_shape["head"]["field"], "country")
        self.assertEqual(json_shape["materialize_as"], "fact")
        sugar_source = self._extract_code_block_after_header(
            text,
            "### F5-I derivation DSL parser（语法层 → Authoring derivation payload，最小切片）",
            "python",
            which=2,
        )
        sugar_payload = parse_authoring_derivation_dsl_v1(sugar_source)
        self.assertEqual(sugar_payload["body"][0][1][0], "gt")
        self.assertEqual(sugar_payload["body"][1][1][0], "not")
        sugar_shape = json.loads(
            self._extract_code_block_after_header(
                text,
                "### F5-I derivation DSL parser（语法层 → Authoring derivation payload，最小切片）",
                "json",
                which=2,
            )
        )
        self.assertEqual(sugar_shape["body"][1][1][0], "not")

        record_source = self._extract_code_block_after_header(
            text,
            "### F5-I derivation DSL parser（语法层 → Authoring derivation payload，最小切片）",
            "python",
            which=3,
        )
        record_payload = parse_authoring_derivation_dsl_v1(record_source)
        self.assertEqual(record_payload["materialize_as"], "record")
        self.assertEqual(record_payload["head"]["callee_kind"], "entity_type")
        self.assertNotIn("id_policy", record_payload)
        record_shape = json.loads(
            self._extract_code_block_after_header(
                text,
                "### F5-I derivation DSL parser（语法层 → Authoring derivation payload，最小切片）",
                "json",
                which=3,
            )
        )
        self.assertEqual(record_shape["materialize_as"], "record")
        self.assertNotIn("id_policy", record_shape)

    def _extract_code_block_after_header(self, text: str, header: str, lang: str, *, which: int) -> str:
        idx = text.find(header)
        self.assertNotEqual(idx, -1, f"missing header: {header}")
        tail = text[idx:]
        matches = list(re.finditer(rf"```{lang}\s*\n(.*?)\n```", tail, flags=re.S))
        self.assertGreaterEqual(len(matches), which, f"missing code block #{which} lang={lang} after {header}")
        return matches[which - 1].group(1)


def _docs_root() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "blueprint"


if __name__ == "__main__":
    unittest.main()
