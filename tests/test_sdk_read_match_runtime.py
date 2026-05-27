from __future__ import annotations

import unittest

import factgraph.sdk as sdk
from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.protocol import EntitySelector, Rule
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.sdk import Entity, Field, Identity
from factgraph.sdk.dsl.rule import Query
from factgraph.sdk.store import SDKStoreError


class Person(Entity):
    name: str = Identity(primary_key=True)
    region: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


class Account(Entity):
    account_id: str = Identity(primary_key=True)
    label: str = Field(cardinality="single")


def _store() -> sdk.SDKStore:
    return sdk.SDKStore([Person, Account])


def _seed_person(graph: sdk.SDKStore, name: str, region: str = "us", *, tags: tuple[str, ...] = ()) -> str:
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(EntitySelector(entity_type="Person", identity={"name": name}), index=index)
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(graph.ledger, info.identity_predicates["name"].pred_id, encoded, [("string", name)])
    set_field(graph.ledger, field_predicate(index, "Person", "region").pred_id, encoded, [("string", region)])
    for tag in tags:
        set_field(graph.ledger, field_predicate(index, "Person", "tag").pred_id, encoded, [("string", tag)])
    return encoded


def _person_region_rule(rule_id: str = "person_region") -> Rule:
    person = Var("$person")
    region = Var("$region")
    return Rule(
        id=rule_id,
        where=(PredAtom("Person:exists", [person]), PredAtom("person:region", [person, region])),
        ports={"person": person, "region": region},
    )


def _person_exists_rule(rule_id: str = "person_exists") -> Rule:
    person = Var("$person")
    return Rule(id=rule_id, where=(PredAtom("Person:exists", [person]),), ports={"person": person})


def _person_tag_rule() -> Rule:
    person = Var("$person")
    tag = Var("$tag")
    return Rule(
        id="person_tag",
        where=(PredAtom("Person:exists", [person]), PredAtom("person:tag", [person, tag])),
        ports={"person": person, "tag": tag},
    )


class SDKReadMatchRuntimeTests(unittest.TestCase):
    def test_rule_literal_constraints_return_distinct_snapshots_and_apply_limit_after_dedup(self) -> None:
        graph = _store()
        _seed_person(graph, "alice", "us", tags=("vip", "admin"))
        _seed_person(graph, "bob", "eu")

        matches = graph.read.match(Person, _person_tag_rule(), tag="vip")
        limited = graph.read.match(Person, _person_tag_rule(), limit=1)

        self.assertEqual([row.region for row in matches], ["us"])
        self.assertEqual(len(limited), 1)
        self.assertEqual(len({row.ref for row in graph.read.match(Person, _person_tag_rule())}), 1)

    def test_rule_accepts_idref_and_snapshot_entity_ref_constraints(self) -> None:
        graph = _store()
        alice_ref = _seed_person(graph, "alice", "us")
        _seed_person(graph, "bob", "eu")
        rule = _person_region_rule()
        alice_snapshot = graph.read.get(Person, name="alice")

        self.assertEqual([row.ref for row in graph.read.match(Person, rule, person=alice_ref)], [alice_ref])
        self.assertEqual([row.ref for row in graph.read.match(Person, rule, person=alice_snapshot)], [alice_ref])

    def test_own_class_field_constraints_are_allowed_and_cross_entity_fields_reject(self) -> None:
        graph = _store()
        _seed_person(graph, "alice", "us")
        _seed_person(graph, "bob", "eu")

        self.assertEqual(
            sorted(row.region for row in graph.read.match(Person, _person_region_rule(), region=Person.region)),
            ["eu", "us"],
        )
        with self.assertRaisesRegex(SDKStoreError, "cross-entity Field constraints"):
            graph.read.match(Person, _person_region_rule(), region=Account.label)

    def test_ruleexpr_and_match_works_and_or_rejects(self) -> None:
        graph = _store()
        _seed_person(graph, "alice", "us")
        exists = _person_exists_rule()
        region = _person_region_rule()
        expr = (exists.as_("exists") & region.as_("region")).join_by_ports("person")

        self.assertEqual([row.region for row in graph.read.match(Person, expr, region="us")], ["us"])
        with self.assertRaisesRegex(SDKStoreError, "Rule and AND RuleExpr only"):
            graph.read.match(Person, exists | region)

    def test_projection_missing_ambiguous_unknown_and_legacy_template_errors(self) -> None:
        graph = _store()
        person = Var("$person")
        other = Var("$other")
        region = Var("$region")
        value_only = Rule(
            id="value_only",
            where=(PredAtom("Person:exists", [person]), PredAtom("person:region", [person, region])),
            ports={"region": region},
        )
        ambiguous = Rule(
            id="ambiguous",
            where=(PredAtom("Person:exists", [person]), PredAtom("Person:exists", [other])),
            ports={"person": person, "other": other},
        )

        with self.assertRaisesRegex(SDKStoreError, "requires exactly one entity_ref port"):
            graph.read.match(Person, value_only)
        with self.assertRaisesRegex(SDKStoreError, "ambiguous"):
            graph.read.match(Person, ambiguous)
        with self.assertRaisesRegex(SDKStoreError, "unknown match port 'missing'"):
            graph.read.match(Person, _person_region_rule(), missing="x")
        with self.assertRaisesRegex(SDKStoreError, "template must be application Rule or AND RuleExpr"):
            graph.read.match(Person, ["not", "a", "rule"])
        with sdk.vars("p") as (p,):
            query = Query(head=Person(p), where=[Person(p)])
        with self.assertRaisesRegex(SDKStoreError, "template must be application Rule or AND RuleExpr"):
            graph.read.match(Person, query)

    def test_disconnected_constrained_port_rejects_before_matching(self) -> None:
        graph = _store()
        alice = _seed_person(graph, "alice")
        person = Var("$person")
        other = Var("$other")
        region = Var("$region")
        rule = Rule(
            id="disconnected",
            where=(PredAtom("Person:exists", [person]), PredAtom("person:region", [other, region])),
            ports={"person": person, "other": other, "region": region},
        )

        with self.assertRaisesRegex(SDKStoreError, "silent cross product"):
            graph.read.match(Person, rule, other=alice)


if __name__ == "__main__":
    unittest.main()
