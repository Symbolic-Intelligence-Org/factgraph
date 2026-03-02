from __future__ import annotations

import unittest

from factpy_kernel.sdk import (
    Entity,
    Field,
    Identity,
    QUERY_INVALID_ROW_FORMAT,
    QUERY_MISSING_REF,
    QUERY_TYPE_MISMATCH,
    Query,
    SDKStore,
    SDKStoreError,
    vars,
)


class Company(Entity):
    source_id: str = Identity()
    name: str = Field(cardinality="functional")


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional")
    works_at: Company = Field(cardinality="functional")
    nickname: str = Field(cardinality="temporal")


class SDKQueryRuntimeV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.sdk = SDKStore.from_schema_classes([Person, Company])
        self.c1_ref = self.sdk.ref(Company, source_id="c1")
        self.p1_ref = self.sdk.ref(Person, source_id="u1")
        self.p2_ref = self.sdk.ref(Person, source_id="u2")

        self.sdk.set(Company.name, self.c1_ref, "Acme")
        self.sdk.set(Person.country, self.p1_ref, "DE")
        self.sdk.set(Person.country, self.p2_ref, "FR")
        self.sdk.set(Person.works_at, self.p1_ref, self.c1_ref)
        self.sdk.set(Person.nickname, self.p1_ref, "alice-v1")
        self.sdk.set(Person.nickname, self.p1_ref, "alice-v2")

    def test_query_single_entity_head_happy_path(self) -> None:
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[p.country == "DE"],
            )
        rows = self.sdk.run(query)
        self.assertEqual(len(rows), 1)
        person = rows[0]["p"]
        self.assertEqual(person.ref, self.p1_ref)
        self.assertEqual(person.country, "DE")

    def test_query_multi_head_join_happy_path(self) -> None:
        with vars("p", "c") as (p, c):
            query = Query(
                head=[Person(p), Company(c)],
                where=[p.works_at == c],
            )
        rows = self.sdk.run(query)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["p"].ref, self.p1_ref)
        self.assertEqual(rows[0]["c"].ref, self.c1_ref)
        self.assertEqual(rows[0]["c"].name, "Acme")

    def test_query_field_projection_happy_path(self) -> None:
        with vars("p", "country") as (p, country):
            query = Query(
                head=Person.country(person=p, value=country),
                where=[p.country == country],
            )
        rows = self.sdk.run(query)
        self.assertEqual(rows, [{"country": "DE"}, {"country": "FR"}])

    def test_on_missing_error_raises_query_missing_ref(self) -> None:
        ghost_ref = self.sdk.ref(Person, source_id="ghost")
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[p == ghost_ref],
                on_missing="error",
            )
        with self.assertRaises(SDKStoreError) as ctx:
            self.sdk.run(query)
        self.assertEqual(ctx.exception.code, QUERY_MISSING_REF)
        self.assertEqual(ctx.exception.path, "$.run.result[0].p")

    def test_on_missing_skip_drops_missing_rows(self) -> None:
        ghost_ref = self.sdk.ref(Person, source_id="ghost")
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[
                    [p.country == "DE"],
                    [p == ghost_ref],
                ],
                on_missing="skip",
            )
        rows = self.sdk.run(query)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["p"].ref, self.p1_ref)

    def test_on_missing_null_keeps_row_with_null_cell(self) -> None:
        ghost_ref = self.sdk.ref(Person, source_id="ghost")
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[
                    [p.country == "DE"],
                    [p == ghost_ref],
                ],
                on_missing="null",
            )
        rows = self.sdk.run(query)
        self.assertEqual(len(rows), 2)
        values = [row["p"] for row in rows]
        self.assertIn(None, values)
        self.assertIn(self.p1_ref, [value.ref for value in values if value is not None])

    def test_on_type_mismatch_error_raises_query_type_mismatch(self) -> None:
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[p == "not_an_idref"],
                on_type_mismatch="error",
            )
        with self.assertRaises(SDKStoreError) as ctx:
            self.sdk.run(query)
        self.assertEqual(ctx.exception.code, QUERY_TYPE_MISMATCH)
        self.assertEqual(ctx.exception.path, "$.run.result[0].p")

    def test_on_type_mismatch_null_sets_null(self) -> None:
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[p == self.c1_ref],
                on_type_mismatch="null",
            )
        rows = self.sdk.run(query)
        self.assertEqual(rows, [{"p": None}])

    def test_multiple_missing_columns_are_handled_independently(self) -> None:
        ghost_p = self.sdk.ref(Person, source_id="ghost-p")
        ghost_c = self.sdk.ref(Company, source_id="ghost-c")
        with vars("p", "c") as (p, c):
            query = Query(
                head=[Person(p), Company(c)],
                where=[p == ghost_p, c == ghost_c],
                on_missing="null",
            )
        rows = self.sdk.run(query)
        self.assertEqual(rows, [{"p": None, "c": None}])

    def test_on_missing_null_rows_participate_in_dedup(self) -> None:
        ghost_p1 = self.sdk.ref(Person, source_id="ghost-p1")
        ghost_p2 = self.sdk.ref(Person, source_id="ghost-p2")
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[
                    [p == ghost_p1],
                    [p == ghost_p2],
                ],
                on_missing="null",
            )
        rows = self.sdk.run(query)
        self.assertEqual(rows, [{"p": None}])

    def test_query_supports_temporal_view_current(self) -> None:
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[p.country == "DE"],
            )
        rows_active = self.sdk.run(query, temporal_view="active")
        rows_current = self.sdk.run(query, temporal_view="current")
        self.assertEqual(rows_active[0]["p"].ref, self.p1_ref)
        self.assertEqual(rows_current[0]["p"].ref, self.p1_ref)
        self.assertGreaterEqual(len(rows_active[0]["p"].nickname), len(rows_current[0]["p"].nickname))
        self.assertEqual(len(rows_current[0]["p"].nickname), 1)

    def test_query_row_format_is_rejected(self) -> None:
        with vars("p") as (p,):
            query = Query(
                head=Person(p),
                where=[Person(p)],
            )
        with self.assertRaises(SDKStoreError) as ctx:
            self.sdk.run(query, row_format="dict")
        self.assertEqual(ctx.exception.code, QUERY_INVALID_ROW_FORMAT)


if __name__ == "__main__":
    unittest.main()
