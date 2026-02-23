import unittest

from symir.errors import RenderError, SchemaError, ValidationError
from symir.ir.fact_schema import Value, PredicateSchema, FactSchema, Rel
from symir.ir.expr_ir import Var, Const, Call, Unify, If, expr_from_dict, Ref
from symir.ir.rule_schema import Expr, Cond, Rule, Query
from symir.rules.validator import RuleValidator
from symir.mappers.renderers import ProbLogRenderer, RenderContext
from symir.probability import ProbabilityConfig


class TestLLMRules(unittest.TestCase):
    def _schema(self) -> FactSchema:
        person = PredicateSchema(
            name="Person",
            arity=1,
            signature=[Value(None, "string")],
        )
        lives = PredicateSchema(
            name="LivesIn",
            arity=2,
            signature=[Value(None, "string"), Value(None, "string")],
        )
        return FactSchema([person, lives])

    def test_rule_roundtrip(self) -> None:
        head_pred = PredicateSchema(
            name="Resident",
            arity=1,
            signature=[Value("X", "string")],
        )
        body_pred = PredicateSchema(
            name="Person",
            arity=1,
            signature=[Value("X", "string")],
        )
        body = Cond(literals=[Ref(schema=body_pred, terms=[Var("X")])], prob=0.5)
        rule = Rule(
            predicate=head_pred,
            conditions=[body],
            render_configs={"var_mode": "sanitize"},
        )
        loaded = Rule.from_dict(rule.to_dict())
        self.assertEqual(rule.predicate.schema_id, loaded.predicate.schema_id)
        self.assertEqual(len(loaded.conditions), 1)
        self.assertEqual(loaded.render_configs, {"var_mode": "sanitize"})

    def test_rule_from_dict_accepts_direct_exprir_literal(self) -> None:
        head_pred = PredicateSchema(
            name="Resident",
            arity=1,
            signature=[Value("X", "string")],
        )
        payload = head_pred.to_dict()
        payload["conditions"] = [
            {
                "literals": [
                    {
                        "kind": "unify",
                        "lhs": {"kind": "var", "name": "X"},
                        "rhs": {"kind": "const", "value": "alice"},
                    }
                ],
                "prob": 0.5,
            }
        ]
        loaded = Rule.from_dict(payload)
        self.assertEqual(len(loaded.conditions), 1)
        self.assertIsInstance(loaded.conditions[0].literals[0], Expr)

    def test_rule_to_dict_emits_direct_exprir_kind(self) -> None:
        head_pred = PredicateSchema(
            name="Resident",
            arity=1,
            signature=[Value("X", "string")],
        )
        rule = Rule(
            predicate=head_pred,
            conditions=[
                Cond(
                    literals=[Unify(Var("X"), Const("alice"))],
                    prob=0.5,
                )
            ],
        )
        payload = rule.to_dict()
        literal = payload["conditions"][0]["literals"][0]
        self.assertEqual(literal["kind"], "unify")

    def test_cond_rejects_non_literal_types(self) -> None:
        with self.assertRaises(SchemaError):
            Cond(literals=[Var("X")])  # type: ignore[list-item]

    def test_cond_accepts_direct_exprir_node(self) -> None:
        cond = Cond(
            literals=[
                Unify(Var("Y"), Call("add", [Var("X"), Const(1)])),
            ],
            prob=0.6,
        )
        self.assertEqual(len(cond.literals), 1)
        self.assertIsInstance(cond.literals[0], Expr)

    def test_multiple_conditions_render(self) -> None:
        schema = self._schema()
        view = schema.view(schema.predicates())
        person = schema.predicates()[0]
        body1 = Cond(literals=[Ref(schema=person, terms=[Var("X")])], prob=0.5)
        body2 = Cond(literals=[Ref(schema=person, terms=[Var("X")], negated=True)], prob=0.5)
        head_pred = PredicateSchema(
            name="Resident",
            arity=1,
            signature=[Value("X", "string")],
        )
        rule = Rule(predicate=head_pred, conditions=[body1, body2])

        RuleValidator(view).validate(rule)
        renderer = ProbLogRenderer()
        text = renderer.render_rule(rule, RenderContext(schema=schema))
        self.assertEqual(len(text.splitlines()), 2)

    def test_ref_not_in_view(self) -> None:
        schema = self._schema()
        view = schema.view([])
        person = schema.predicates()[0]
        body = Cond(literals=[Ref(schema=person, terms=[Var("X")])], prob=0.5)
        head_pred = PredicateSchema(
            name="Resident",
            arity=1,
            signature=[Value("X", "string")],
        )
        rule = Rule(predicate=head_pred, conditions=[body])
        with self.assertRaises(ValidationError):
            RuleValidator(view).validate(rule)

    def test_negated_ref_render(self) -> None:
        schema = self._schema()
        view = schema.view(schema.predicates())
        person = schema.predicates()[0]
        body = Cond(literals=[Ref(schema=person, terms=[Var("X")], negated=True)], prob=0.5)
        head_pred = PredicateSchema(
            name="Resident",
            arity=1,
            signature=[Value(None, "string")],
        )
        rule = Rule(predicate=head_pred, conditions=[body])
        RuleValidator(view).validate(rule)
        text = ProbLogRenderer().render_rule(rule, RenderContext(schema=schema))
        self.assertIn("\\+ Person(X)", text)

    def test_expr_serialization_and_render(self) -> None:
        expr = If(
            cond=Call("gt", [Var("X"), Const(0)]),
            then=Unify(Var("Y"), Call("add", [Var("X"), Const(1)])) ,
            else_=Unify(Var("Y"), Const(0)),
        )
        expr_dict = expr.to_dict()
        expr2 = expr_from_dict(expr_dict)
        self.assertEqual(expr, expr2)

        schema = self._schema()
        view = schema.view(schema.predicates())
        head_pred = PredicateSchema(
            name="Calc",
            arity=2,
            signature=[Value("X", "int"), Value("Y", "int")],
        )
        body = Cond(literals=[Expr(expr=expr2)], prob=0.8)
        rule = Rule(predicate=head_pred, conditions=[body])
        RuleValidator(view).validate(rule)
        text = ProbLogRenderer().render_rule(rule, RenderContext(schema=schema))
        self.assertIn("((X > 0, Y = X + 1) ; (\\+ (X > 0), Y = 0))", text)

    def test_missing_probability_default(self) -> None:
        schema = self._schema()
        view = schema.view(schema.predicates())
        person = schema.predicates()[0]
        body = Cond(literals=[Ref(schema=person, terms=[Var("X")])], prob=None)
        head_pred = PredicateSchema(
            name="Resident",
            arity=1,
            signature=[Value("X", "string")],
        )
        rule = Rule(predicate=head_pred, conditions=[body])
        RuleValidator(view).validate(rule)
        config = ProbabilityConfig(default_rule_prob=0.7, missing_prob_policy="inject_default")
        text = ProbLogRenderer(prob_config=config).render_rule(rule, RenderContext(schema=schema))
        self.assertIn("0.7::Resident(X)", text)

    def test_query_render(self) -> None:
        schema = self._schema()
        head_pred = PredicateSchema(
            name="Resident",
            arity=1,
            signature=[Value(None, "string")],
        )
        query = Query(predicate=head_pred, terms=[Var("X")])
        text = ProbLogRenderer().render_query(query, RenderContext(schema=schema))
        self.assertEqual("query(Resident(X)).", text)

        person_id = schema.predicates()[0].schema_id
        query_fact = Query(predicate_id=person_id, terms=[Const("alice")])
        text2 = ProbLogRenderer().render_query(query_fact, RenderContext(schema=schema))
        self.assertEqual("query(Person(alice)).", text2)

    def test_var_default_sanitize(self) -> None:
        person = PredicateSchema(
            name="person",
            arity=1,
            signature=[Value("x", "string")],
        )
        schema = FactSchema([person])
        head = PredicateSchema(
            name="resident",
            arity=1,
            signature=[Value("x", "string")],
        )
        rule = Rule(
            predicate=head,
            conditions=[Cond(literals=[Ref(schema=person, terms=[Var("x")])], prob=0.5)],
        )
        text = ProbLogRenderer().render_rule(rule, RenderContext(schema=schema))
        self.assertEqual("0.5::resident(X) :- person(X).", text)

    def test_var_mode_error(self) -> None:
        person = PredicateSchema(
            name="person",
            arity=1,
            signature=[Value("x", "string")],
        )
        schema = FactSchema([person])
        head = PredicateSchema(
            name="resident",
            arity=1,
            signature=[Value("x", "string")],
        )
        rule = Rule(
            predicate=head,
            conditions=[Cond(literals=[Ref(schema=person, terms=[Var("x")])], prob=0.5)],
            render_configs={"var_mode": "error"},
        )
        with self.assertRaises(RenderError):
            ProbLogRenderer().render_rule(rule, RenderContext(schema=schema))

    def test_var_mode_prefix(self) -> None:
        person = PredicateSchema(
            name="person",
            arity=1,
            signature=[Value("x", "string")],
        )
        schema = FactSchema([person])
        head = PredicateSchema(
            name="resident",
            arity=1,
            signature=[Value("x", "string")],
        )
        rule = Rule(
            predicate=head,
            conditions=[Cond(literals=[Ref(schema=person, terms=[Var("x")])], prob=0.5)],
            render_configs={"var_mode": "prefix", "var_prefix": "VAR_"},
        )
        text = ProbLogRenderer().render_rule(rule, RenderContext(schema=schema))
        self.assertEqual("0.5::resident(VAR_x) :- person(VAR_x).", text)

    def test_rel_head_uses_sub_obj_then_props(self) -> None:
        person = PredicateSchema(
            name="person",
            arity=2,
            signature=[Value("Name", "string"), Value("Addr", "string")],
            key_fields=["Name"],
        )
        company = PredicateSchema(
            name="company",
            arity=1,
            signature=[Value("Company", "string")],
            key_fields=["Company"],
        )
        employment = Rel(
            "employment",
            sub=person,
            obj=company,
            props=[Value("Since", "int"), Value("Title", "string")],
        )
        schema = FactSchema([person, company, employment])
        cond = Cond(
            literals=[
                Ref(schema=person, terms=[Var("Sub_Name"), Var("Sub_Addr")]),
                Ref(schema=company, terms=[Var("Obj_Company")]),
                Expr(expr=Unify(Var("Since"), Const(2020))),
                Expr(expr=Unify(Var("Title"), Const("researcher"))),
                Expr(expr=Unify(Var("Sub"), Call("person", [Var("Sub_Name"), Var("Sub_Addr")]))),
                Expr(expr=Unify(Var("Obj"), Call("company", [Var("Obj_Company")]))),
            ],
            prob=0.7,
        )
        rule = Rule(predicate=employment, conditions=[cond])
        text = ProbLogRenderer().render_rule(rule, RenderContext(schema=schema))
        self.assertEqual(
            "0.7::employment(Sub, Obj, Since, Title) :- "
            "person(Sub_Name, Sub_Addr), company(Obj_Company), Since = 2020, "
            "Title = researcher, Sub = person(Sub_Name, Sub_Addr), Obj = company(Obj_Company).",
            text,
        )

    def test_rel_binding_auto_injected_from_renderer_mode(self) -> None:
        person = PredicateSchema(
            name="person",
            arity=2,
            signature=[Value("Name", "string"), Value("Addr", "string")],
            key_fields=["Name"],
        )
        company = PredicateSchema(
            name="company",
            arity=1,
            signature=[Value("Company", "string")],
            key_fields=["Company"],
        )
        employment = Rel(
            "employment",
            sub=person,
            obj=company,
            props=[Value("Since", "int"), Value("Title", "string")],
        )
        schema = FactSchema([person, company, employment])
        cond = Cond(
            literals=[
                Expr(expr=Unify(Var("Since"), Const(2020))),
                Expr(expr=Unify(Var("Title"), Const("researcher"))),
            ],
            prob=0.7,
        )
        rule = Rule(predicate=employment, conditions=[cond])
        text = ProbLogRenderer(rel_mode="composed").render_rule(
            rule,
            RenderContext(schema=schema),
        )
        self.assertEqual(
            "0.7::employment(Sub, Obj, Since, Title) :- "
            "Sub = person(Sub_Name, Sub_Addr), Obj = company(Obj_Company), "
            "person(Sub_Name, Sub_Addr), company(Obj_Company), "
            "Since = 2020, Title = researcher.",
            text,
        )

    def test_rel_binding_rule_override_turns_off_context_default(self) -> None:
        person = PredicateSchema(
            name="person",
            arity=1,
            signature=[Value("Name", "string")],
            key_fields=["Name"],
        )
        company = PredicateSchema(
            name="company",
            arity=1,
            signature=[Value("Company", "string")],
            key_fields=["Company"],
        )
        employment = Rel("employment", sub=person, obj=company, props=[Value("Since", "int")])
        schema = FactSchema([person, company, employment])
        cond = Cond(
            literals=[Expr(expr=Unify(Var("Since"), Const(2020)))],
            prob=0.7,
        )
        rule = Rule(
            predicate=employment,
            conditions=[cond],
            render_configs={"rel_mode": "none"},
        )
        text = ProbLogRenderer(rel_mode="composed").render_rule(
            rule,
            RenderContext(schema=schema),
        )
        self.assertEqual("0.7::employment(Sub, Obj, Since) :- Since = 2020.", text)

    def test_rel_mode_flattened_renders_flat_head(self) -> None:
        person = PredicateSchema(
            name="person",
            arity=2,
            signature=[Value("Name", "string"), Value("Addr", "string")],
            key_fields=["Name"],
        )
        company = PredicateSchema(
            name="company",
            arity=1,
            signature=[Value("Company", "string")],
            key_fields=["Company"],
        )
        employment = Rel("employment", sub=person, obj=company, props=[Value("Since", "int")])
        schema = FactSchema([person, company, employment])
        cond = Cond(
            literals=[
                Ref(schema=person, terms=[Var("sub_Name"), Var("sub_Addr")]),
                Ref(schema=company, terms=[Var("obj_Company")]),
                Expr(expr=Unify(Var("Since"), Const(2020))),
            ],
            prob=0.7,
        )
        rule = Rule(
            predicate=employment,
            conditions=[cond],
            render_configs={"rel_mode": "flattened"},
        )
        text = ProbLogRenderer().render_rule(rule, RenderContext(schema=schema))
        self.assertEqual(
            "0.7::employment(Sub_Name, Obj_Company, Since) :- "
            "person(Sub_Name, Sub_Addr), company(Obj_Company), Since = 2020.",
            text,
        )

    def test_unknown_render_config_key_rejected(self) -> None:
        person = PredicateSchema(
            name="person",
            arity=1,
            signature=[Value("Name", "string")],
            key_fields=["Name"],
        )
        company = PredicateSchema(
            name="company",
            arity=1,
            signature=[Value("Company", "string")],
            key_fields=["Company"],
        )
        employment = Rel("employment", sub=person, obj=company, props=[Value("Since", "int")])
        schema = FactSchema([person, company, employment])
        cond = Cond(
            literals=[Expr(expr=Unify(Var("Since"), Const(2020)))],
            prob=0.7,
        )
        rule = Rule(
            predicate=employment,
            conditions=[cond],
            render_configs={"legacy_bind": True},
        )
        with self.assertRaises(RenderError):
            ProbLogRenderer().render_rule(rule, RenderContext(schema=schema))


if __name__ == "__main__":
    unittest.main()
