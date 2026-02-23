import json
import unittest

from symir.ir.fact_schema import Entity, Value, PredicateSchema, FactSchema, Fact, Rel
from symir.rules.library import Library, LibrarySpec
from symir.rules.constraint_schemas import (
    build_pydantic_rule_model,
    build_responses_schema,
    build_predicate_catalog,
)

class TestRuleSchemaGen(unittest.TestCase):
    def test_pydantic_and_json_schema(self) -> None:
        parent = PredicateSchema(
            name="Parent",
            arity=2,
            signature=[Value("Param", "string"), Value("Param2", "string")],
        )
        schema = FactSchema([parent])
        view = schema.view([parent])
        model = build_pydantic_rule_model(view, mode="compact")
        instance = model.model_validate(
            {
                "conditions": [
                    {
                        "literals": [
                            {
                                "kind": "ref",
                                "schema": parent.schema_id,
                                "args": [
                                    {"name": "Param", "value": {"kind": "var", "name": "X"}},
                                    {"name": "Param2", "value": {"kind": "var", "name": "Y"}},
                                ],
                            }
                        ],
                        "prob": 0.6,
                    }
                ],
            }
        )
        self.assertEqual(len(instance.conditions), 1)

        json_schema = build_responses_schema(view, mode="compact")
        json_blob = json.dumps(json_schema)
        self.assertIn(parent.schema_id, json_blob)

        catalog = build_predicate_catalog(view)
        self.assertIn(parent.schema_id, catalog)
        self.assertEqual(catalog[parent.schema_id]["kind"], "fact")

    def test_prompt_block_catalog(self) -> None:
        person = Fact(
            "person",
            [Entity("Name", "string"), Value("Address", "string")],
        )
        company = Fact(
            "company",
            [Entity("Company", "string"), Entity("Country", "string")],
        )
        employment = Rel(
            "employment",
            sub=person,
            obj=company,
            props=[Value("since", "int"), Value("title", "string")],
        )
        schema = FactSchema([person, company, employment])
        view = schema.view([person, company, employment])

        library = Library()
        library.register(
            LibrarySpec(
                name="member",
                arity=2,
                kind="predicate",
                description="list membership",
                signature=["term", "list"],
            )
        )

        catalog = build_predicate_catalog(
            view,
            library=library,
            style="prompt_blocks",
            payload_mode="compact",
        )
        self.assertIn("head", catalog)
        self.assertIn(person.schema_id, catalog)
        self.assertIn(employment.schema_id, catalog)
        self.assertIn("The subject entity (Sub) is", catalog[employment.schema_id])
        self.assertIn("Sub key args (structured, required)", catalog[employment.schema_id])
        self.assertIn("Selected relation view (rel_mode=flattened)", catalog[employment.schema_id])
        self.assertIn("Ref literal syntax (compact mode)", catalog["head"])

    def test_compact_arity_error_includes_predicate_context(self) -> None:
        person = Fact("person", [Entity("Name", "string")])
        company = Fact(
            "company",
            [Entity("Company", "string"), Entity("Country", "string")],
        )
        employment = Rel(
            "employment",
            sub=person,
            obj=company,
            props=[Value("since", "int"), Value("title", "string")],
        )
        schema = FactSchema([person, company, employment])
        view = schema.view([employment])
        model = build_pydantic_rule_model(view, mode="compact")

        payload = {
            "conditions": [
                {
                    "literals": [
                        {
                            "kind": "ref",
                            "schema": employment.schema_id,
                            "args": [
                                {"name": "Sub", "value": {"kind": "var", "name": "Sub"}},
                                {"name": "Obj", "value": {"kind": "var", "name": "Obj"}},
                                {"name": "since", "value": {"kind": "const", "value": 2020}},
                            ],
                            "negated": False,
                        }
                    ],
                    "prob": 0.7,
                }
            ]
        }
        with self.assertRaises(Exception) as ctx:
            model.model_validate(payload)
        text = str(ctx.exception)
        self.assertIn("predicate 'employment'", text)
        self.assertIn("Expected args: sub_Name (string), obj_Company (string), obj_Country (string), since (int), title (string)", text)
        self.assertIn("Compact mode requires all args", text)

    def test_compact_allows_freeform_arg_names(self) -> None:
        person = Fact("person", [Entity("Name", "string")])
        city = Fact("city", [Entity("City", "string")])
        lives = Rel("lives_in", sub=person, obj=city)
        schema = FactSchema([person, city, lives])
        view = schema.view([lives])
        model = build_pydantic_rule_model(view, mode="compact")

        payload = {
            "conditions": [
                {
                    "literals": [
                        {
                            "kind": "ref",
                            "schema": lives.schema_id,
                            "args": [
                                {"name": "City", "value": {"kind": "var", "name": "Y"}},
                                {"name": "sub_Name", "value": {"kind": "var", "name": "X"}},
                            ],
                            "negated": False,
                        }
                    ],
                    "prob": 0.6,
                }
            ]
        }
        validated = model.model_validate(payload)
        self.assertEqual(len(validated.conditions), 1)

    def test_prompt_block_rel_mode_selection(self) -> None:
        person = Fact("person", [Entity("Name", "string")], description="person node")
        city = Fact("city", [Entity("City", "string")], description="city node")
        lives = Rel("lives_in", sub=person, obj=city)
        schema = FactSchema([person, city, lives])
        view = schema.view([lives])

        composed_catalog = build_predicate_catalog(
            view,
            style="prompt_blocks",
            payload_mode="compact",
            rel_mode="composed",
        )
        block = composed_catalog[lives.schema_id]
        self.assertIn("Selected relation view (rel_mode=composed): Sub, Obj", block)
        self.assertNotIn("rel_mode=flattened", block)

    def test_compact_response_schema_enforces_ref_arity(self) -> None:
        person = Fact("person", [Entity("Name", "string")])
        company = Fact(
            "company",
            [Entity("Company", "string"), Entity("Country", "string")],
        )
        works = Rel(
            "works_at",
            sub=person,
            obj=company,
            props=[Value("since", "int"), Value("title", "string")],
        )
        schema = FactSchema([person, company, works])
        view = schema.view([works])

        json_schema = build_responses_schema(view, mode="compact")
        ref_anyof = json_schema["properties"]["conditions"]["items"]["properties"]["literals"]["items"]["anyOf"][0]["anyOf"]
        works_ref = next(
            item for item in ref_anyof
            if item["properties"]["schema"]["const"] == works.schema_id
        )
        args_spec = works_ref["properties"]["args"]
        self.assertEqual(args_spec["minItems"], works.arity)
        self.assertEqual(args_spec["maxItems"], works.arity)


if __name__ == "__main__":
    unittest.main()
