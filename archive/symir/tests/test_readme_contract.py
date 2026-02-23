import tempfile
from pathlib import Path
import unittest

from symir.errors import ProviderError, SchemaError, ValidationError
from symir.fact_store.provider import CSVProvider, CSVSource
from symir.fact_store.rel_builder import RelBuilder, ROW_PROB_KEY
from symir.ir.expr_ir import Const, Ref, Var, expr_from_dict
from symir.ir.fact_schema import Entity, Value, field_from_dict, Fact, FactLayer, Rel
from symir.ir.instance import Instance
from symir.ir.rule_schema import Cond, Rule
from symir.rules.constraint_schemas import build_pydantic_rule_model, build_responses_schema
from symir.rules.validator import RuleValidator


class TestReadmeContract(unittest.TestCase):
    def _basic_schema(self) -> tuple[FactLayer, Fact, Fact, Rel]:
        person = Fact(
            "person",
            [
                Entity("Name", "string"),
                Value("Address", "string"),
                Value("Age", "int"),
            ],
        )
        company = Fact(
            "company",
            [
                Entity("Company", "string"),
                Value("Worth", "float"),
            ],
        )
        employment = Rel(
            "employment",
            sub=person,
            obj=company,
            props=[Value("Since", "int"), Value("Title", "string")],
        )
        return FactLayer([person, company, employment]), person, company, employment

    def test_argument_and_schema_payload_contract(self) -> None:
        city = Entity("City", "string")
        self.assertEqual(city.name, "City")
        self.assertEqual(city.datatype, "string")

        with self.assertRaises(SchemaError):
            Value("Name", "string", role="key")

        from_arg_name = field_from_dict({"datatype": "string", "arg_name": "Name", "role": "key"})
        self.assertEqual(from_arg_name.name, "Name")
        self.assertEqual(from_arg_name.role, "key")
        from_name = field_from_dict({"datatype": "string", "name": "Name"})
        self.assertEqual(from_name.name, "Name")
        with self.assertRaises(SchemaError):
            field_from_dict({"spec": "Country:string"})  # type: ignore[arg-type]
        with self.assertRaises(SchemaError):
            Entity("Country", "json")  # type: ignore[arg-type]

        _, person, company, employment = self._basic_schema()
        self.assertEqual(employment.arity, len(employment.endpoints["sub_key_fields"]) + len(employment.endpoints["obj_key_fields"]) + len(employment.props))

        rel_payload = employment.to_dict()
        self.assertNotIn("signature", rel_payload)
        self.assertIn("derived_signature", rel_payload)
        derived = rel_payload["derived_signature"]
        self.assertEqual(derived["sub_args"][0]["arg_name"], "Sub")
        self.assertEqual(derived["obj_args"][0]["arg_name"], "Obj")
        self.assertIn("prop_args", derived)

        fact_payload = person.to_dict()
        self.assertIn("signature", fact_payload)
        self.assertIn("key_fields", fact_payload)
        self.assertEqual(fact_payload["kind"], "fact")
        self.assertEqual(rel_payload["kind"], "rel")

    def test_fact_and_rel_require_keys(self) -> None:
        with self.assertRaisesRegex(SchemaError, "Fact requires at least one key field"):
            Fact("person_no_key", [Value("Name", "string")])

        person = Fact("person", [Entity("Name", "string")])
        company = Fact("company", [Entity("Company", "string")])
        with self.assertRaisesRegex(
            SchemaError,
            "Rel subject and object each require at least one key field",
        ):
            Rel(
                "works_at_invalid",
                sub=person,
                obj=company,
                endpoints={"sub_key_fields": [], "obj_key_fields": ["Company"]},
            )

    def test_registry_and_view_contract(self) -> None:
        registry, person, company, employment = self._basic_schema()

        self.assertEqual(registry.fact("person").schema_id, person.schema_id)
        self.assertEqual(registry.rel("employment").schema_id, employment.schema_id)
        self.assertEqual(registry.rel_of_ids("employment", person.schema_id, company.schema_id).schema_id, employment.schema_id)

        payload = registry.to_dict()
        self.assertEqual(payload["version"], 1)
        loaded = FactLayer.from_dict(payload)
        self.assertEqual(loaded.names(), registry.names())

        view = registry.view([person, employment])
        self.assertTrue(view.allows(person))
        self.assertTrue(view.allows(employment))
        self.assertEqual(view.fact("person").schema_id, person.schema_id)
        self.assertEqual(view.rel("employment").schema_id, employment.schema_id)

    def test_instance_rel_forms_and_meta_rules(self) -> None:
        registry, person, company, employment = self._basic_schema()

        alice = Instance(schema=person, terms=["alice", "addr1", 28])
        openai = Instance(schema=company, terms=["openai", 10.5])

        rel_from_refs = Instance(
            schema=employment,
            terms={
                "sub_ref": alice,
                "obj_ref": openai,
                "props": {"Since": 2020, "Title": "researcher"},
            },
        )
        self.assertEqual(rel_from_refs.props["Since"], 2020)

        rel_inline = Instance(
            schema=employment,
            terms={
                "sub_key": {"Name": "alice"},
                "obj_key": {"Company": "openai"},
                "Since": 2021,
                "Title": "engineer",
            },
        )
        self.assertEqual(rel_inline.props["Title"], "engineer")

        with self.assertRaisesRegex(SchemaError, "Unknown rel props"):
            Instance(
                schema=employment,
                terms={
                    "sub_ref": alice,
                    "obj_ref": openai,
                    "props": {"BadProp": 1},
                },
            )

        with self.assertRaisesRegex(SchemaError, "Rel endpoint missing key fields"):
            Instance(
                schema=employment,
                terms={
                    "sub_key": {"Name": "alice"},
                    "obj_key": {},
                    "props": {"Since": 2020, "Title": "x"},
                },
            )

        with self.assertRaisesRegex(SchemaError, "Unknown meta keys"):
            Instance(schema=person, terms=["alice", "addr1", 28], meta={"bad_key": "x"})

        with self.assertRaisesRegex(SchemaError, "meta.status must be one of"):
            Instance(schema=person, terms=["alice", "addr1", 28], meta={"status": "draft"})

        keep_person = Fact(
            "person_keep",
            [Entity("Name", "string"), Value("Address", "string")],
            merge_policy="keep_all",
        )
        keep_company = Fact(
            "company_keep",
            [Entity("Company", "string")],
            merge_policy="keep_all",
        )
        keep_rel = Rel(
            "employment_keep",
            sub=keep_person,
            obj=keep_company,
            props=[Value("Since", "int")],
            merge_policy="keep_all",
        )

        p = Instance(schema=keep_person, terms=["alice", "addr1"])
        c = Instance(schema=keep_company, terms=["openai"])
        self.assertIsNotNone(p.record_id)
        self.assertIsNotNone(c.record_id)

        r1 = Instance(schema=keep_rel, terms=[{"Name": "alice"}, {"Company": "openai"}, 2020])
        r2 = Instance(schema=keep_rel, terms=[{"Name": "alice"}, {"Company": "openai"}, 2021])
        self.assertIsNotNone(r1.record_id)
        self.assertEqual(r1.sub_entity_id, r2.sub_entity_id)
        self.assertEqual(r1.obj_entity_id, r2.obj_entity_id)

        readable = rel_from_refs.to_dict(include_keys=True)
        self.assertIn("sub_key", readable)
        self.assertIn("obj_key", readable)
        loaded_rel = Instance.from_dict(rel_from_refs.to_dict(), registry=registry)
        with self.assertRaisesRegex(SchemaError, "missing endpoint key props"):
            loaded_rel.to_dict(include_keys=True)

    def test_csv_provider_mapping_contract(self) -> None:
        registry, person, company, employment = self._basic_schema()

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "people.csv").write_text("p_name,p_addr,p_age\nalice,addr1,28\n", encoding="utf-8")
            (base / "companies.csv").write_text("c_name,c_worth\nopenai,10.5\n", encoding="utf-8")
            (base / "employment.csv").write_text(
                "person_col,company_col,since_col,title_col\nalice,openai,2020,researcher\n",
                encoding="utf-8",
            )

            provider = CSVProvider(
                schema=registry,
                base_path=base,
                sources=[
                    CSVSource(schema=person, file="people.csv", columns=["p_name", "p_addr", "p_age"]),
                    CSVSource(schema=company, file="companies.csv", columns=["c_name", "c_worth"]),
                    CSVSource(
                        schema=employment,
                        file="employment.csv",
                        columns=["person_col", "company_col", "since_col", "title_col"],
                    ),
                ],
                datatype_cast="coerce",
            )

            instances = provider.query(registry.view([person, company, employment]))
            rels = [i for i in instances if i.kind == "rel"]
            self.assertEqual(len(rels), 1)
            self.assertIsInstance(rels[0].props["Since"], int)

            bad_provider = CSVProvider(
                schema=registry,
                base_path=base,
                sources=[CSVSource(schema=person, file="people.csv", columns=["p_name", "p_addr", "p_age"])],
            )
            with self.assertRaisesRegex(ProviderError, "Missing CSV source mapping.*name=company"):
                bad_provider.query(registry.view([person, company]))

    def test_rel_builder_contract_and_errors(self) -> None:
        person = Fact(
            "person",
            [Entity("Name", "string"), Entity("Address", "string")],
        )
        company = Fact(
            "company",
            [Entity("Company", "string"), Entity("Country", "string")],
        )
        works = Rel("works_at", sub=person, obj=company, props=[Value("Since", "int")])
        registry = FactLayer([person, company, works])

        facts = [
            Instance(schema=person, terms=["alice", "addr1"]),
            Instance(schema=person, terms=["alice", "addr2"]),
            Instance(schema=company, terms=["openai", "US"]),
            Instance(schema=company, terms=["openai", "UK"]),
        ]

        bad_list_builder = RelBuilder(rel=works, match_keys=["person", "company"])
        with self.assertRaisesRegex(SchemaError, "single key per endpoint"):
            bad_list_builder.build(facts=facts, rows=[], registry=registry)

        strict_builder = RelBuilder(
            rel=works,
            match_keys={"sub": {"Name": "person"}, "obj": {"Company": "company"}},
            key_mode="strict",
            multi="error",
        )
        with self.assertRaisesRegex(SchemaError, "Missing obj key fields in row"):
            strict_builder.build(
                facts=facts,
                rows=[{"person": "alice", "company": "openai", "Since": 2020, ROW_PROB_KEY: 0.9}],
                registry=registry,
                datatype_cast="coerce",
            )

        partial_builder = RelBuilder(
            rel=works,
            match_keys={"sub": {"Name": "person"}, "obj": {"Company": "company"}},
            key_mode="partial",
            multi="cartesian",
        )
        rels = partial_builder.build(
            facts=facts,
            rows=[{"person": "alice", "company": "openai", "Since": 2020, ROW_PROB_KEY: 0.8}],
            registry=registry,
            datatype_cast="coerce",
        )
        self.assertEqual(len(rels), 4)
        self.assertTrue(all(rel.props["Since"] == 2020 for rel in rels))

    def test_rule_ref_and_constraint_schema_contract(self) -> None:
        person = Fact("person", [Entity("Name", "string"), Value("Age", "int")])
        head = Fact("resident", [Entity("Name", "string"), Value("Age", "int")])
        schema = FactLayer([person])
        view = schema.view([person])

        good_ref = Ref(schema=person, terms=[Var("X"), Const(30)])
        self.assertEqual(good_ref.schema, person.schema_id)
        with self.assertRaises(SchemaError):
            Ref(schema=person, terms=[Var("X"), Const("thirty")])
        with self.assertRaisesRegex(SchemaError, "PredicateSchema or Instance"):
            Ref(schema=person.schema_id, terms=[Var("X"), Const(30)])  # type: ignore[arg-type]

        alice = Instance(schema=person, terms=["alice", 30])
        ref_from_instance = Ref(schema=alice)
        self.assertTrue(all(isinstance(t, Const) for t in ref_from_instance.terms))

        cond = Cond(literals=[Ref(schema=person, terms=[Var("Name"), Var("Age")])], prob=0.7)
        rule = Rule(predicate=head, conditions=[cond])
        loaded = Rule.from_dict(rule.to_dict())
        self.assertEqual(loaded.predicate.schema_id, rule.predicate.schema_id)

        validator = RuleValidator(view)
        validator.validate(rule)
        recursive_rule = Rule(
            predicate=person,
            conditions=[Cond(literals=[Ref(schema=person, terms=[Var("Name"), Var("Age")])], prob=0.7)],
        )
        with self.assertRaises(ValidationError):
            validator.validate(recursive_rule)

        model = build_pydantic_rule_model(view, mode="compact")
        validated = model.model_validate(
            {
                "conditions": [
                    {
                        "literals": [
                            {
                                "kind": "ref",
                                "schema": person.schema_id,
                                "args": [
                                    {"name": "Name", "value": {"kind": "var", "name": "X"}},
                                    {"name": "Age", "value": {"kind": "const", "value": 30}},
                                ],
                                "negated": False,
                            }
                        ],
                        "prob": 0.6,
                    }
                ]
            }
        )
        self.assertEqual(len(validated.conditions), 1)

        with self.assertRaises(Exception):
            model.model_validate(
                {
                    "conditions": [
                        {
                            "literals": [
                                {
                                    "kind": "ref",
                                    "schema_id": person.schema_id,
                                    "args": [
                                        {"name": "Name", "value": {"kind": "var", "name": "X"}},
                                        {"name": "Age", "value": {"kind": "const", "value": 30}},
                                    ],
                                    "negated": False,
                                }
                            ],
                            "prob": 0.6,
                        }
                    ]
                }
            )

        schema_json = build_responses_schema(view, mode="compact")
        cond_required = schema_json["properties"]["conditions"]["items"]["required"]
        self.assertIn("prob", cond_required)
        self.assertEqual(
            schema_json["properties"]["conditions"]["items"]["properties"]["prob"]["type"],
            "number",
        )

        # Legacy payload compatibility for deserialization only.
        legacy_ref = expr_from_dict(
            {
                "kind": "ref",
                "schema_id": person.schema_id,
                "terms": [{"kind": "var", "name": "X"}, {"kind": "const", "value": 30}],
                "negated": False,
            }
        )
        self.assertIsInstance(legacy_ref, Ref)


if __name__ == "__main__":
    unittest.main()
