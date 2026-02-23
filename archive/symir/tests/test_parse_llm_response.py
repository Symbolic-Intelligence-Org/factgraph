import json
import unittest

from symir.examples.parse_llm_response import resp_to_rule
from symir.ir.expr_ir import Ref, Var
from symir.ir.fact_schema import Entity, Value, Fact, FactSchema, PredicateSchema, Rel


class _MockResp:
    def __init__(self, payload: dict) -> None:
        self.output_text = json.dumps(payload)


class TestParseLLMResponse(unittest.TestCase):
    def test_compact_args_are_bound_by_name(self) -> None:
        person = Fact("person", [Entity("Name", "string")])
        company = Fact(
            "company",
            [Entity("Company", "string"), Entity("Country", "string")],
        )
        works_at = Rel(
            "works_at",
            sub=person,
            obj=company,
            props=[Value("since", "int"), Value("title", "string")],
        )
        schema = FactSchema([person, company, works_at])
        view = schema.view([works_at])
        head = PredicateSchema(
            name="candidate",
            arity=1,
            signature=[Value("Name", "string")],
        )

        payload = {
            "conditions": [
                {
                    "literals": [
                        {
                            "kind": "ref",
                            "schema": works_at.schema_id,
                            "args": [
                                {"name": "obj_Country", "value": {"kind": "var", "name": "Country"}},
                                {"name": "since", "value": {"kind": "var", "name": "Since"}},
                                {"name": "sub_Name", "value": {"kind": "var", "name": "X"}},
                                {"name": "title", "value": {"kind": "var", "name": "Title"}},
                                {"name": "obj_Company", "value": {"kind": "var", "name": "C"}},
                            ],
                            "negated": False,
                        }
                    ],
                    "prob": 0.7,
                }
            ]
        }

        rule = resp_to_rule(_MockResp(payload), head=head, view=view, mode="compact")
        self.assertEqual(len(rule.conditions), 1)
        literal = rule.conditions[0].literals[0]
        self.assertIsInstance(literal, Ref)
        self.assertEqual([term.name for term in literal.terms if isinstance(term, Var)], ["X", "C", "Country", "Since", "Title"])


if __name__ == "__main__":
    unittest.main()
