import unittest

from symir.fact_store.neo4j_component import Neo4jCfg, Neo4jComponent
from symir.ir.fact_schema import Entity, Value, Fact, Rel, FactSchema
from symir.ir.instance import Instance


class TestNeo4jComponent(unittest.TestCase):
    def test_import_graph_example_style(self) -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        def runner(query: str, params: dict[str, object]) -> None:
            calls.append((query, params))

        component = Neo4jComponent(
            Neo4jCfg(uri="bolt://localhost:7687", user="neo4j", password="test"),
            runner=runner,
        )
        schema = {"nodes": {"Person": ["name"], "Company": ["name"]}}
        nodes = {"Person": ["alice"], "Company": ["openai"]}
        rels = {("Person", "works_at", "Company"): [("alice", "openai")]}

        component.import_graph(schema=schema, nodes=nodes, rels=rels, batch=1000)
        cypher = "\n".join(item[0] for item in calls)
        self.assertIn("CREATE CONSTRAINT", cypher)
        self.assertIn("MERGE (n:Person", cypher)
        self.assertIn("MERGE (s)-[:WORKS_AT]->(o)", cypher)

    def test_import_instances(self) -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        def runner(query: str, params: dict[str, object]) -> None:
            calls.append((query, params))

        person = Fact("person", [Entity("Name", "string"), Value("Age", "int")])
        company = Fact("company", [Entity("Company", "string")])
        works = Rel("works_at", sub=person, obj=company, props=[Value("Since", "int")])
        schema = FactSchema([person, company, works])
        instances = [
            Instance(schema=person, terms={"Name": "alice", "Age": 30}),
            Instance(schema=company, terms={"Company": "openai"}),
            Instance(schema=works, terms=[{"Name": "alice"}, {"Company": "openai"}, 2020]),
        ]

        component = Neo4jComponent(
            Neo4jCfg(uri="bolt://localhost:7687", user="neo4j", password="test"),
            runner=runner,
        )
        component.import_instances(schema=schema, instances=instances, batch=1000)

        cypher = "\n".join(item[0] for item in calls)
        self.assertIn("MERGE (n:`person`", cypher)
        self.assertIn("MERGE (n:`company`", cypher)
        self.assertIn("MERGE (s)-[r:`WORKS_AT`]->(o)", cypher)

    def test_render_then_execute_cypher_interfaces(self) -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        def runner(query: str, params: dict[str, object]) -> None:
            calls.append((query, params))

        person = Fact("person", [Entity("Name", "string"), Value("Age", "int")])
        schema = FactSchema([person])
        instances = [Instance(schema=person, terms={"Name": "alice", "Age": 30})]

        component = Neo4jComponent(
            Neo4jCfg(uri="bolt://localhost:7687", user="neo4j", password="test"),
            runner=runner,
        )
        script = component.render_cypher_for_instances(schema=schema, instances=instances)
        self.assertIn("MERGE (n:`person`", script)

        component.execute_cypher(script)
        self.assertTrue(any("MERGE (n:`person`" in query for query, _ in calls))


if __name__ == "__main__":
    unittest.main()
