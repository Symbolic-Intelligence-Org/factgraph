from __future__ import annotations

import unittest

import factgraph.sdk as sdk
from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.protocol import EntitySelector, Rule
from factgraph.application.explain.evidence_tree import Holds, NotReached
from factgraph.application.explain.prober import ProbeEnv, _probe_atom
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.view.projector import project_view_facts
from factgraph.core.rules.where_ast import AggregateAtom, CmpAtom, Const, PredAtom, Var
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.sdk import Entity, Field, Identity


class NativeExplainUser(Entity):
    class Meta:
        repr = "NativeUser %user_id"

    user_id: str = Identity()
    region: str = Field(repr="%ENT region %FLD")
    age: int = Field(repr="%ENT age %FLD")
    tag: str = Field(repr="%ENT tag %FLD")


class NativeAggregateOrder(Entity):
    order_id: str = Identity()
    amount: int = Field()
    buyer: str = Field()


def _store() -> sdk.SDKStore:
    return sdk.SDKStore([NativeExplainUser])


def _aggregate_store() -> sdk.SDKStore:
    return sdk.SDKStore([NativeAggregateOrder])


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


def _seed_order(graph: sdk.SDKStore, order_id: str, *, amount: int, buyer: str = "all") -> str:
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(EntitySelector(entity_type="NativeAggregateOrder", identity={"order_id": order_id}), index=index)
    info = entity_info(index, "NativeAggregateOrder")
    encoded = ref.encoded_ref or ""
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(graph.ledger, info.identity_predicates["order_id"].pred_id, encoded, [("string", order_id)])
    set_field(graph.ledger, field_predicate(index, "NativeAggregateOrder", "amount").pred_id, encoded, [("int", amount)])
    set_field(graph.ledger, field_predicate(index, "NativeAggregateOrder", "buyer").pred_id, encoded, [("string", buyer)])
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


def _aggregate_rule(graph: sdk.SDKStore, kind: str) -> Rule:
    index = build_schema_index(graph.schema_ir)
    amount_pred = field_predicate(index, "NativeAggregateOrder", "amount").pred_id
    order = Var("$order")
    amount = Var("$amount")
    total = Var("$total")
    if kind == "count":
        aggregate = AggregateAtom("count", None, [PredAtom(amount_pred, [order, amount])])
    else:
        aggregate = AggregateAtom(kind, amount, [PredAtom(amount_pred, [order, amount])])
    return Rule(id=f"order_{kind}", when=(CmpAtom("eq", total, aggregate),), ports={"total": total})


def _correlated_aggregate_rule(graph: sdk.SDKStore) -> Rule:
    index = build_schema_index(graph.schema_ir)
    amount_pred = field_predicate(index, "NativeAggregateOrder", "amount").pred_id
    buyer_pred = field_predicate(index, "NativeAggregateOrder", "buyer").pred_id
    outer_order = Var("$outer_order")
    order = Var("$order")
    amount = Var("$amount")
    buyer = Var("$buyer")
    total = Var("$total")
    aggregate = AggregateAtom(
        "sum",
        amount,
        [
            PredAtom(buyer_pred, [order, buyer]),
            PredAtom(amount_pred, [order, amount]),
        ],
    )
    return Rule(
        id="buyer_order_sum",
        when=(PredAtom(buyer_pred, [outer_order, buyer]), CmpAtom("eq", total, aggregate)),
        ports={"buyer": buyer, "total": total},
    )


def _row_public_value(row: object, port_name: str) -> object:
    value = row.bindings[port_name]  # type: ignore[attr-defined,index]
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _evidence_atoms(row: object) -> tuple[object, ...]:
    explanation = row.explain()  # type: ignore[attr-defined]
    evidence = explanation.evidence
    assert evidence is not None
    return tuple(
        atom
        for path in evidence.paths
        for rule in path.rules
        for atom in rule.atoms
    )


class NativeAggregateExplainConformanceTests(unittest.TestCase):
    def test_aggregate_count_evaluate_and_explain(self) -> None:
        self._assert_aggregate_result("count", 3)

    def test_aggregate_sum_evaluate_and_explain(self) -> None:
        self._assert_aggregate_result("sum", 60)

    def test_aggregate_min_evaluate_and_explain(self) -> None:
        self._assert_aggregate_result("min", 10)

    def test_aggregate_max_evaluate_and_explain(self) -> None:
        self._assert_aggregate_result("max", 30)

    def test_aggregate_mean_evaluate_and_explain(self) -> None:
        self._assert_aggregate_result("mean", 20.0)

    def test_mean_aggregate_still_rejects_int_comparison(self) -> None:
        graph = _aggregate_store()
        _seed_order(graph, "o-1", amount=10)
        _seed_order(graph, "o-2", amount=20)
        _seed_order(graph, "o-3", amount=30)
        index = build_schema_index(graph.schema_ir)
        amount_pred = field_predicate(index, "NativeAggregateOrder", "amount").pred_id
        order = Var("$order")
        amount = Var("$amount")
        aggregate = AggregateAtom("mean", amount, [PredAtom(amount_pred, [order, amount])])
        rule = Rule(
            id="order_mean_cmp",
            when=(PredAtom(amount_pred, [order, amount]), CmpAtom("ge", aggregate, Const(20))),
            ports={"order": order},
        )

        with self.assertRaisesRegex(WhereValidationError, "ge supports only int/time values"):
            graph.eval.evaluate(rule, head=rule, engine="native")

    def _assert_aggregate_result(self, kind: str, expected: object) -> None:
        graph = _aggregate_store()
        _seed_order(graph, "o-1", amount=10)
        _seed_order(graph, "o-2", amount=20)
        _seed_order(graph, "o-3", amount=30)

        result = graph.eval.evaluate(_aggregate_rule(graph, kind), head=_aggregate_rule(graph, kind), engine="native")

        self.assertEqual(result.count(), 1)
        self.assertEqual(_row_public_value(result[0], "total"), expected)
        explanation = result[0].explain()
        self.assertEqual(explanation.status, "passed")
        self.assertIsNotNone(explanation.evidence)
        assert explanation.evidence is not None
        self.assertTrue(explanation.evidence.paths)
        atom_text = "\n".join(atom.repr_text or "" for atom in _evidence_atoms(result[0]))
        self.assertNotIn("$", atom_text)
        self.assertNotIn("('", atom_text)
        self.assertNotIn("[(", atom_text)
        self.assertIn("count" if kind == "count" else f"{kind} of amount", atom_text)
        aggregate_atoms = [
            atom
            for atom in _evidence_atoms(result[0])
            if atom.repr_text and ("count" in atom.repr_text or f"{kind} of amount" in atom.repr_text)
        ]
        self.assertTrue(aggregate_atoms)
        self.assertTrue(any(isinstance(atom.verdict, Holds) for atom in aggregate_atoms))

    def test_correlated_aggregate_explain_holds_when_outer_var_is_bound(self) -> None:
        graph = _aggregate_store()
        _seed_order(graph, "o-1", amount=10, buyer="u-1")
        _seed_order(graph, "o-2", amount=20, buyer="u-1")
        _seed_order(graph, "o-3", amount=5, buyer="u-2")

        result = graph.eval.evaluate(_correlated_aggregate_rule(graph), head=_correlated_aggregate_rule(graph), engine="native")

        rows_by_buyer = {str(_row_public_value(row, "buyer")): row for row in result}
        self.assertEqual(_row_public_value(rows_by_buyer["u-1"], "total"), 30)
        self.assertEqual(_row_public_value(rows_by_buyer["u-2"], "total"), 5)
        first_text = "\n".join(atom.repr_text or "" for atom in _evidence_atoms(rows_by_buyer["u-1"]))
        second_text = "\n".join(atom.repr_text or "" for atom in _evidence_atoms(rows_by_buyer["u-2"]))
        self.assertIn("30 equals sum of amount", first_text)
        self.assertIn("5 equals sum of amount", second_text)
        first_aggregate_atoms = [atom for atom in _evidence_atoms(rows_by_buyer["u-1"]) if atom.repr_text == "30 equals sum of amount"]
        second_aggregate_atoms = [atom for atom in _evidence_atoms(rows_by_buyer["u-2"]) if atom.repr_text == "5 equals sum of amount"]
        self.assertTrue(first_aggregate_atoms)
        self.assertTrue(second_aggregate_atoms)
        self.assertTrue(all(isinstance(atom.verdict, Holds) for atom in first_aggregate_atoms + second_aggregate_atoms))

    def test_correlated_aggregate_missing_outer_var_is_not_reached_without_leaking(self) -> None:
        graph = _aggregate_store()
        _seed_order(graph, "o-1", amount=10, buyer="u-1")
        _seed_order(graph, "o-2", amount=20, buyer="u-2")
        index = build_schema_index(graph.schema_ir)
        amount_pred = field_predicate(index, "NativeAggregateOrder", "amount").pred_id
        buyer_pred = field_predicate(index, "NativeAggregateOrder", "buyer").pred_id
        atom = (
            "eq",
            "$total",
            (
                "sum",
                "$_agg_amount",
                [
                    ("pred", buyer_pred, ["$_agg_order", "$buyer"]),
                    ("pred", amount_pred, ["$_agg_order", "$_agg_amount"]),
                ],
            ),
        )

        evidence_atom, candidate_envs, verdict_envs = _probe_atom(
            atom,
            (ProbeEnv.from_bindings({"$total": 30}),),
            verdict_envs=(ProbeEnv.from_bindings({"$total": 30}),),
            view_facts={key: list(value) for key, value in project_view_facts(graph.ledger, graph.schema_ir).items()},
            atom_id="aggregate:correlated:missing",
            failed_upstream=False,
            schema_index=index,
        )

        self.assertIsInstance(evidence_atom.verdict, NotReached)
        self.assertIn("$buyer", evidence_atom.verdict.blocked_by)
        self.assertEqual(evidence_atom.repr_text, "30 equals sum of amount")
        self.assertNotIn("u-1", evidence_atom.repr_text or "")
        self.assertNotIn("u-2", evidence_atom.repr_text or "")
        self.assertEqual(candidate_envs, ())
        self.assertEqual(verdict_envs, (ProbeEnv.from_bindings({"$total": 30}),))


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
