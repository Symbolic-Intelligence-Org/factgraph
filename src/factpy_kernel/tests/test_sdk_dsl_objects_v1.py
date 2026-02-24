from __future__ import annotations

import unittest

from factpy_kernel.sdk import Derivation, Entity, Field, Identity, Rule, RuleRef, SDKDSLError, vars


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")


class LivesIn(Entity):
    uid: str = Identity(default_factory="uuid4")
    person: Person = Field(cardinality="functional")
    country: str = Field(cardinality="functional")

    class Meta:
        is_record = True


class SDKDSLObjectsV1Tests(unittest.TestCase):
    def test_rule_to_authoring_payload_supports_pythonic_where_and_ruleref(self) -> None:
        with vars("li", "p", "c") as (li, p, c):
            rule = Rule(
                id="q_country_rows",
                version="1.0.0",
                select=[p, c],
                where=[
                    LivesIn(li),
                    li.person == p,
                    li.country == c,
                    RuleRef("q_other", version="1.0.0")(p, c),
                    c != "xx",
                ],
                expose=True,
            )
        payload = rule.to_authoring_payload()
        self.assertEqual(payload["select"], ["$p", "$c"])
        self.assertEqual(payload["where"][0], ("pred", "LivesIn:exists", ["$li"]))
        self.assertEqual(payload["where"][1], ("pred", "livesin:person", ["$li", "$p"]))
        self.assertEqual(payload["where"][2], ("pred", "livesin:country", ["$li", "$c"]))
        self.assertEqual(payload["where"][3], ("ruleref", "q_other", "1.0.0", ["$p", "$c"]))
        self.assertEqual(payload["where"][4], ("not", [("eq", "$c", "xx")]))
        self.assertTrue(payload["expose"])

    def test_derivation_to_authoring_payload_supports_head_call(self) -> None:
        with vars("p", "c") as (p, c):
            drv = Derivation(
                id="drv.country_copy",
                version="1.0.0",
                head=Person.country(person=p, value=c),
                where=[("pred", "person:country", ["$p", "$c"])],
                materialize_as="fact",
            )
        payload = drv.to_authoring_payload()
        self.assertEqual(payload["head"]["kind"], "head_call")
        self.assertEqual(payload["head"]["callee_kind"], "pred_ref")
        self.assertEqual(payload["head"]["entity_type"], "Person")
        self.assertEqual(payload["head"]["field"], "country")
        self.assertEqual(payload["head"]["kwargs"]["person"], "$p")
        self.assertEqual(payload["head"]["kwargs"]["value"], "$c")

    def test_rule_to_authoring_payload_lowers_linear_arithmetic_to_builtin_atoms(self) -> None:
        with vars("p", "by", "age") as (p, by, age):
            rule = Rule(
                id="q_adults",
                version="1.0.0",
                select=[p, age],
                where=[
                    ("pred", "person:birth_year", ["$p", "$by"]),
                    age == (2026 - by),
                    age >= 18,
                ],
            )
        payload = rule.to_authoring_payload()
        self.assertEqual(payload["where"][0], ("pred", "person:birth_year", ["$p", "$by"]))
        self.assertEqual(payload["where"][1], ("sub", "$_arith1", 2026, "$by"))
        self.assertEqual(payload["where"][2], ("eq", "$age", "$_arith1"))
        self.assertEqual(payload["where"][3], ("ge", "$age", 18))

    def test_noarg_vars_exposes_factory_mode_error_for_unpack(self) -> None:
        with self.assertRaises(SDKDSLError):
            with vars() as pair:
                _ = list(pair)  # explicit iterate to trigger clear error

    def test_attr_to_attr_compare_is_rejected_with_actionable_error(self) -> None:
        with vars("a", "b") as (a, b):
            rule = Rule(
                id="q.bad",
                version="1.0.0",
                select=[a],
                where=[LivesIn(a), LivesIn(b), a.country == b.country],
            )
        with self.assertRaises(SDKDSLError):
            rule.to_authoring_payload()


if __name__ == "__main__":
    unittest.main()
