import unittest

from symir.ir.fact_schema import Entity, Value, Fact, Rel, FactSchema
from symir.ir.expr_ir import Var, Const, Call, Ref
from symir.ir.rule_schema import Cond, Rule, Expr, Query
from symir.ir.instance import Instance
from symir.mappers.renderers import CypherRenderer, RenderContext


class TestCypherRenderer(unittest.TestCase):
    def _schema(self) -> tuple[FactSchema, Fact, Fact, Rel]:
        person = Fact("person", [Entity("Name", "string"), Value("Age", "int")])
        company = Fact("company", [Entity("Company", "string")])
        works_at = Rel("works_at", sub=person, obj=company, props=[Value("Since", "int")])
        schema = FactSchema([person, company, works_at])
        return schema, person, company, works_at

    def test_render_rule_generates_match_where_return(self) -> None:
        schema, person, _company, _works = self._schema()
        head = Fact("resident", [Entity("Name", "string")])
        cond = Cond(
            literals=[
                Ref(schema=person, terms=[Var("Name"), Var("Age")]),
                Expr(expr=Call("gt", [Var("Age"), Const(18)])),
            ],
            prob=0.8,
        )
        rule = Rule(predicate=head, conditions=[cond])

        text = CypherRenderer().render_rule(rule, RenderContext(schema=schema))
        self.assertIn("MATCH (n0:`person`)", text)
        self.assertIn("n0.`Age` > 18", text)
        self.assertIn("RETURN DISTINCT", text)
        self.assertIn("AS `Name`", text)
        self.assertIn("AS `prob`", text)

    def test_render_facts_generates_merge_statements(self) -> None:
        schema, person, company, works = self._schema()
        facts = [
            Instance(schema=person, terms={"Name": "alice", "Age": 30}),
            Instance(schema=company, terms={"Company": "openai"}),
            Instance(schema=works, terms=[{"Name": "alice"}, {"Company": "openai"}, 2020]),
        ]
        text = CypherRenderer().render_facts(facts, RenderContext(schema=schema))
        self.assertIn("MERGE (n:`person`", text)
        self.assertIn("MERGE (n:`company`", text)
        self.assertIn("MERGE (s)-[r:`WORKS_AT`]->(o)", text)

    def test_render_query(self) -> None:
        schema, person, _company, _works = self._schema()
        query = Query(predicate=person, terms=[Var("X"), Const(30)])
        text = CypherRenderer().render_query(query, RenderContext(schema=schema))
        self.assertIn("MATCH (n0:`person`)", text)
        self.assertIn("= 30", text)
        self.assertIn("RETURN DISTINCT", text)
        self.assertIn("AS `X`", text)


if __name__ == "__main__":
    unittest.main()

