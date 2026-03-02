from __future__ import annotations

import tempfile
import unittest

from factpy_kernel.core.rules.where_ast import lower_ast_to_where_ir
from factpy_kernel.core.schema.schema_ir import schema_digest
from factpy_kernel.sdk import (
    Entity,
    Field,
    Identity,
    Query,
    SDKRegistry,
    SDKRegistryError,
    SDKStore,
    SDKStoreError,
    vars,
)
from factpy_kernel.sdk.query_lower import QueryPlan, lower_query


class Company(Entity):
    source_id: str = Identity()
    sector: str = Field(cardinality="functional")


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional")
    name: str = Field(cardinality="functional")
    works_at: Company = Field(cardinality="functional")
    tag: str = Field(cardinality="multi")
    name_by_lang: str = Field(
        cardinality="functional",
        dims=[("lang", "string")],
        fact_key=["lang"],
    )


class SDKQueryLoweringV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.sdk = SDKStore.from_schema_classes([Person, Company])
        self.schema_digest = schema_digest(self.sdk.schema_ir)

    def test_lower_query_returns_query_plan_with_runtime_query_rule_ast(self) -> None:
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[p.country == "DE"],
            )
        plan = lower_query(
            query,
            temporal_view="active",
            schema_ir=self.sdk.schema_ir,
            schema_digest=self.schema_digest,
        )

        self.assertIsInstance(plan, QueryPlan)
        self.assertTrue(plan.query_id.startswith("__query__:"))
        self.assertEqual(len(plan.query_id.split(":", 1)[1]), 16)
        self.assertEqual(plan.rule_ast.rule_id, plan.query_id)
        self.assertEqual(plan.rule_ast.version, "runtime")
        self.assertEqual(plan.rule_ast.select_vars, ["$p"])
        self.assertEqual(lower_ast_to_where_ir(plan.rule_ast.where), query.where_ir)
        self.assertEqual([entry.alias for entry in plan.return_contract], ["p"])
        self.assertEqual(plan.temporal_view, "active")

    def test_lower_query_is_deterministic_for_same_semantics(self) -> None:
        with vars("p") as (p,):
            q1 = Query(
                head=Person(p),
                where=[p.country == "DE"],
            )
        with vars("p") as (p,):
            q2 = Query(
                head=Person(p),
                where=[p.country == "DE"],
            )
        p1 = lower_query(
            q1,
            temporal_view="active",
            schema_ir=self.sdk.schema_ir,
            schema_digest=self.schema_digest,
        )
        p2 = lower_query(
            q2,
            temporal_view="active",
            schema_ir=self.sdk.schema_ir,
            schema_digest=self.schema_digest,
        )
        self.assertEqual(p1.query_id, p2.query_id)

    def test_lower_query_head_order_changes_query_id(self) -> None:
        with vars("p", "c") as (p, c):
            q1 = Query(
                head=[Person(p), Company(c)],
                where=[Person(p), Company(c), p.works_at == c],
            )
            q2 = Query(
                head=[Company(c), Person(p)],
                where=[Person(p), Company(c), p.works_at == c],
            )
        p1 = lower_query(
            q1,
            temporal_view="active",
            schema_ir=self.sdk.schema_ir,
            schema_digest=self.schema_digest,
        )
        p2 = lower_query(
            q2,
            temporal_view="active",
            schema_ir=self.sdk.schema_ir,
            schema_digest=self.schema_digest,
        )
        self.assertNotEqual(p1.query_id, p2.query_id)

    def test_lower_query_rejects_multi_field_projection(self) -> None:
        with vars("p", "tag") as (p, tag):
            query = Query(
                head=Person.tag(person=p, value=tag),
                where=[Person(p)],
            )
        with self.assertRaises(SDKStoreError) as ctx:
            lower_query(
                query,
                temporal_view="active",
                schema_ir=self.sdk.schema_ir,
                schema_digest=self.schema_digest,
            )
        self.assertIn("only supports functional fields", str(ctx.exception))

    def test_lower_query_rejects_dims_field_projection(self) -> None:
        with vars("p", "name") as (p, name):
            query = Query(
                head=Person.name_by_lang(person=p, lang="en", value=name),
                where=[Person(p)],
            )
        with self.assertRaises(SDKStoreError) as ctx:
            lower_query(
                query,
                temporal_view="active",
                schema_ir=self.sdk.schema_ir,
                schema_digest=self.schema_digest,
            )
        self.assertIn("does not support fields with dims", str(ctx.exception))

    def test_run_query_executes_after_lowering(self) -> None:
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[p.country == "DE"],
            )
        p_ref = self.sdk.ref(Person, source_id="u1")
        self.sdk.set(Person.country, p_ref, "DE")
        rows = self.sdk.run(query)
        self.assertEqual(len(rows), 1)
        self.assertIn("p", rows[0])
        self.assertEqual(rows[0]["p"].ref, p_ref)

    def test_query_cannot_be_registered_as_rule_asset(self) -> None:
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[p.country == "DE"],
            )
        with tempfile.TemporaryDirectory() as tmp:
            registry = SDKRegistry(root_dir=tmp)
            with self.assertRaises(SDKRegistryError):
                registry.register_rule(query)


if __name__ == "__main__":
    unittest.main()
