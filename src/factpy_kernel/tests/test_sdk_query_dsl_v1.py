from __future__ import annotations

import unittest

from factpy_kernel.sdk import Entity, Field, Identity, Query, SDKDSLError, vars
from factpy_kernel.sdk.error_codes import QUERY_ALIAS_CONFLICT, QUERY_UNBOUND_VAR


class Company(Entity):
    source_id: str = Identity()
    name: str = Field(cardinality="functional")


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional")
    name: str = Field(cardinality="functional")
    works_at: Company = Field(cardinality="functional")


class SDKQueryDSLV1Tests(unittest.TestCase):
    def test_query_entity_head_builds_return_contract(self) -> None:
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[p.country == "DE"],
            )
        contract = query.return_contract
        self.assertEqual(len(contract), 1)
        self.assertEqual(contract[0].var, "$p")
        self.assertEqual(contract[0].alias, "p")
        self.assertEqual(contract[0].entity_type, "Person")
        self.assertIsNone(contract[0].field_path)

    def test_query_multi_entity_head_builds_return_contract(self) -> None:
        with vars("p", "c") as (p, c):
            query = Query(
                head=[Person(p), Company(c)],
                where=[p.works_at == c],
            )
        contract = query.return_contract
        self.assertEqual(len(contract), 2)
        self.assertEqual([entry.alias for entry in contract], ["p", "c"])
        self.assertEqual([entry.entity_type for entry in contract], ["Person", "Company"])

    def test_query_field_head_builds_projection_return_contract(self) -> None:
        with vars("p", "name") as (p, name):
            query = Query(
                head=Person.name(person=p, value=name),
                where=[p.country == "DE"],
            )
        contract = query.return_contract
        self.assertEqual(len(contract), 1)
        self.assertEqual(contract[0].var, "$name")
        self.assertEqual(contract[0].alias, "name")
        self.assertIsNone(contract[0].entity_type)
        self.assertEqual(contract[0].field_path, "Person.name")

    def test_query_head_alias_conflict_raises_code(self) -> None:
        with vars("p") as (p,):
            with self.assertRaises(SDKDSLError) as ctx:
                Query(
                    head=[Person(p), Company(p)],
                    where=[p == p],
                )
        self.assertEqual(ctx.exception.code, QUERY_ALIAS_CONFLICT)

    def test_query_where_unbound_var_raises_code(self) -> None:
        with vars("p", "q") as (p, q):
            with self.assertRaises(SDKDSLError) as ctx:
                Query(
                    head=Person(p),
                    where=[q >= 1],
                )
        self.assertEqual(ctx.exception.code, QUERY_UNBOUND_VAR)

    def test_query_invalid_head_shape_raises_sdk_dsl_error(self) -> None:
        with vars("p") as (p,):
            with self.assertRaises(SDKDSLError):
                Query(
                    head=p,
                    where=[p == p],
                )


if __name__ == "__main__":
    unittest.main()
