from __future__ import annotations

import unittest

import factgraph.sdk as sdk
from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.protocol import EntitySelector, Rule
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity


class NativeExplainUser(Entity):
    class Meta:
        repr = "NativeUser %user_id"

    user_id: str = Identity()
    region: str = Field(repr="%ENT region %FLD")
    age: int = Field(repr="%ENT age %FLD")
    tag: str = Field(repr="%ENT tag %FLD")


def _store() -> sdk.SDKStore:
    return sdk.SDKStore([NativeExplainUser])


def _seed_user(graph: sdk.SDKStore, user_id: str, *, region: str, age: int, tag: str) -> str:
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(EntitySelector(entity_type="NativeExplainUser", identity={"user_id": user_id}), index=index)
    info = entity_info(index, "NativeExplainUser")
    encoded = ref.encoded_ref or ""
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(graph.ledger, info.identity_predicates["user_id"].pred_id, encoded, [("string", user_id)])
    set_field(graph.ledger, field_predicate(index, "NativeExplainUser", "region").pred_id, encoded, [("string", region)])
    set_field(graph.ledger, field_predicate(index, "NativeExplainUser", "age").pred_id, encoded, [("int", age)])
    set_field(graph.ledger, field_predicate(index, "NativeExplainUser", "tag").pred_id, encoded, [("string", tag)])
    return encoded


def _predicates(graph: sdk.SDKStore) -> tuple[str, str, str]:
    index = build_schema_index(graph.schema_ir)
    return (
        field_predicate(index, "NativeExplainUser", "region").pred_id,
        field_predicate(index, "NativeExplainUser", "age").pred_id,
        field_predicate(index, "NativeExplainUser", "tag").pred_id,
    )


def _body_rule(graph: sdk.SDKStore, rule_id: str = "body_user") -> Rule:
    region_pred, age_pred, _tag_pred = _predicates(graph)
    user = Var("$user")
    region = Var("$region")
    age = Var("$age")
    return Rule(
        id=rule_id,
        when=(
            PredAtom(region_pred, [user, region]),
            PredAtom(age_pred, [user, age]),
            CmpAtom("ge", age, Const(18)),
        ),
        ports={"user": user, "region": region, "age": age},
    )


def _tag_rule(graph: sdk.SDKStore, rule_id: str = "tag_user") -> Rule:
    _region_pred, _age_pred, tag_pred = _predicates(graph)
    user = Var("$user")
    tag = Var("$tag")
    return Rule(id=rule_id, when=(PredAtom(tag_pred, [user, tag]),), ports={"user": user, "tag": tag})


def _row_value(row: object, port_name: str) -> object:
    value = row.bindings[port_name]  # type: ignore[attr-defined,index]
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _atom_text(row: object) -> str:
    explanation = row.explain()  # type: ignore[attr-defined]
    evidence = explanation.evidence
    assert evidence is not None
    return "\n".join(
        atom.repr_text or ""
        for path in evidence.paths
        for rule in path.rules
        for atom in rule.atoms
    )


class NativeExplainConformanceTests(unittest.TestCase):
    def test_projection_head_explain_anchors_each_projected_row(self) -> None:
        graph = _store()
        u1 = _seed_user(graph, "u-1", region="us", age=30, tag="alpha")
        u2 = _seed_user(graph, "u-2", region="eu", age=40, tag="beta")
        result = graph.eval.evaluate(_body_rule(graph), head=Rule.projection("user", "region", "age"), engine="native")

        rows_by_user = {str(_row_value(row, "user")): row for row in result}
        first_text = _atom_text(rows_by_user[u1])
        second_text = _atom_text(rows_by_user[u2])

        self.assertIn("NativeUser u-1 region us", first_text)
        self.assertIn("NativeUser u-1 age 30", first_text)
        self.assertNotIn("NativeUser u-2", first_text)
        self.assertIn("NativeUser u-2 region eu", second_text)
        self.assertIn("NativeUser u-2 age 40", second_text)
        self.assertNotIn("NativeUser u-1", second_text)

    def test_external_head_explain_anchors_head_and_body_atoms(self) -> None:
        graph = _store()
        u1 = _seed_user(graph, "u-1", region="us", age=30, tag="alpha")
        u2 = _seed_user(graph, "u-2", region="eu", age=40, tag="beta")
        region_pred, age_pred, _tag_pred = _predicates(graph)
        head_user = Var("$head_user")
        head_region = Var("$head_region")
        head_age = Var("$head_age")
        external_head = Rule(
            id="external_adult_user",
            when=(
                PredAtom(region_pred, [head_user, head_region]),
                PredAtom(age_pred, [head_user, head_age]),
                CmpAtom("ge", head_age, Const(18)),
            ),
            ports={"user": head_user, "region": head_region, "age": head_age},
        )

        result = graph.eval.evaluate(_body_rule(graph), head=external_head, engine="native")

        rows_by_user = {str(_row_value(row, "user")): row for row in result}
        first_text = _atom_text(rows_by_user[u1])
        second_text = _atom_text(rows_by_user[u2])
        self.assertIn("NativeUser u-1 region us", first_text)
        self.assertIn("NativeUser u-1 age 30", first_text)
        self.assertNotIn("NativeUser u-2", first_text)
        self.assertIn("NativeUser u-2 region eu", second_text)
        self.assertIn("NativeUser u-2 age 40", second_text)
        self.assertNotIn("NativeUser u-1", second_text)

    def test_projection_join_explain_seeds_all_joined_occurrences(self) -> None:
        graph = _store()
        u1 = _seed_user(graph, "u-1", region="us", age=30, tag="alpha")
        u2 = _seed_user(graph, "u-2", region="eu", age=40, tag="beta")
        expr = (_body_rule(graph, "adult").as_("adult") & _tag_rule(graph, "tag").as_("tag")).join_by_ports("user")

        result = graph.eval.evaluate(expr, head=Rule.projection("user", "region", "age", "tag"), engine="native")

        rows_by_user = {str(_row_value(row, "user")): row for row in result}
        first_text = _atom_text(rows_by_user[u1])
        second_text = _atom_text(rows_by_user[u2])
        self.assertIn("NativeUser u-1 region us", first_text)
        self.assertIn("NativeUser u-1 age 30", first_text)
        self.assertIn("NativeUser u-1 tag alpha", first_text)
        self.assertNotIn("NativeUser u-2", first_text)
        self.assertIn("NativeUser u-2 region eu", second_text)
        self.assertIn("NativeUser u-2 age 40", second_text)
        self.assertIn("NativeUser u-2 tag beta", second_text)
        self.assertNotIn("NativeUser u-1", second_text)

    def test_projection_or_explain_seeds_branch_specific_sources(self) -> None:
        graph = _store()
        u1 = _seed_user(graph, "u-1", region="us", age=30, tag="alpha")
        u2 = _seed_user(graph, "u-2", region="eu", age=40, tag="beta")
        region_user = Var("$user")
        region_value = Var("$value")
        tag_user = Var("$user")
        tag_value = Var("$value")
        region_rule = Rule(
            id="region_value",
            when=(PredAtom(_predicates(graph)[0], [region_user, region_value]),),
            ports={"user": region_user, "value": region_value},
        )
        tag_rule = Rule(
            id="tag_value",
            when=(PredAtom(_predicates(graph)[2], [tag_user, tag_value]),),
            ports={"user": tag_user, "value": tag_value},
        )

        result = graph.eval.evaluate(region_rule.as_("region") | tag_rule.as_("tag"), head=Rule.projection("user", "value"), engine="native")

        rows = {(str(_row_value(row, "user")), str(_row_value(row, "value"))): row for row in result}
        self.assertIn("NativeUser u-1 region us", _atom_text(rows[(u1, "us")]))
        self.assertIn("NativeUser u-1 tag alpha", _atom_text(rows[(u1, "alpha")]))
        self.assertIn("NativeUser u-2 region eu", _atom_text(rows[(u2, "eu")]))
        self.assertIn("NativeUser u-2 tag beta", _atom_text(rows[(u2, "beta")]))


if __name__ == "__main__":
    unittest.main()
