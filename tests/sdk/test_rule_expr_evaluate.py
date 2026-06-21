from __future__ import annotations

import json
from pathlib import Path
import unittest
import warnings
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import factgraph.sdk as sdk
import factgraph.sdk.dsl as dsl
from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.protocol import (
    DetachedRowError,
    EntitySelector,
    EvaluateResult,
    Explanation,
    Rule,
    RuleExprError,
    RuleExprInspect,
)
from factgraph.application.protocol.rule_expr_inspect import _inspect_closed_head
from factgraph.application.protocol.evaluate_result import closed_head_digest_for
from factgraph.application.protocol.rule_expr_lowering import _lower_application_rule, _lower_rule_expr
from factgraph.adapters.problog.provenance import parse_problog_trace, problog_trace_to_dict
from factgraph.adapters.souffle.runner import find_souffle_binary
from factgraph.adapters.pyreason.provenance import (
    PyReasonTraceEventV0,
    PyReasonTraceV0,
    pyreason_trace_to_dict,
)
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import AggregateAtom, AndExpr, CmpAtom, Const, NotAtom, PredAtom, Var
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.core.store.ledger import AnnotationRow
from factgraph.core.store._support import (
    PROBLOG_PROVENANCE_KIND,
    PYREASON_PROVENANCE_KIND,
    PredWitness,
    ProofReceipt,
    ProvenanceEnvelope,
    SOUFFLE_WITNESS_KIND,
)
from factgraph.sdk import Entity, Field, Identity
from factgraph.sdk.store import SDKStoreError, _initial_probe_bindings_for_row


class Person(Entity):
    name: str = Identity()
    region: str = Field()


class ExplainAnchorUser(Entity):
    class Meta:
        repr = "AnchorUser %user_id"

    user_id: str = Identity()
    region: str = Field(repr="%ENT region %FLD")
    age: int = Field(repr="%ENT age %FLD")
    tag: str = Field()


class ExplainTxn(Entity):
    class Meta:
        repr = "Txn %txn_id"

    txn_id: str = Identity()
    customer: str = Field(repr="%ENT is by %FLD")
    direction: str = Field(repr="%ENT direction %FLD")
    amount: int = Field(repr="%ENT amount %FLD")


def _store() -> sdk.SDKStore:
    return sdk.SDKStore([Person])


def _anchor_store() -> sdk.SDKStore:
    return sdk.SDKStore([ExplainAnchorUser])


def _txn_store() -> sdk.SDKStore:
    return sdk.SDKStore([ExplainTxn])


def _seed_person(graph: sdk.SDKStore, name: str, region: str = "us") -> str:
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(EntitySelector(entity_type="Person", identity={"name": name}), index=index)
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(graph.ledger, info.identity_predicates["name"].pred_id, encoded, [("string", name)])
    set_field(graph.ledger, field_predicate(index, "Person", "region").pred_id, encoded, [("string", region)])
    return encoded


def _seed_anchor_user(graph: sdk.SDKStore, user_id: str, *, region: str, age: int, tag: str) -> str:
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(EntitySelector(entity_type="ExplainAnchorUser", identity={"user_id": user_id}), index=index)
    info = entity_info(index, "ExplainAnchorUser")
    encoded = ref.encoded_ref or ""
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(graph.ledger, info.identity_predicates["user_id"].pred_id, encoded, [("string", user_id)])
    set_field(graph.ledger, field_predicate(index, "ExplainAnchorUser", "region").pred_id, encoded, [("string", region)])
    set_field(graph.ledger, field_predicate(index, "ExplainAnchorUser", "age").pred_id, encoded, [("int", age)])
    set_field(graph.ledger, field_predicate(index, "ExplainAnchorUser", "tag").pred_id, encoded, [("string", tag)])
    return encoded


def _seed_txn(graph: sdk.SDKStore, txn_id: str, *, customer: str, direction: str, amount: int) -> str:
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(EntitySelector(entity_type="ExplainTxn", identity={"txn_id": txn_id}), index=index)
    info = entity_info(index, "ExplainTxn")
    encoded = ref.encoded_ref or ""
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(graph.ledger, info.identity_predicates["txn_id"].pred_id, encoded, [("string", txn_id)])
    set_field(graph.ledger, field_predicate(index, "ExplainTxn", "customer").pred_id, encoded, [("string", customer)])
    set_field(graph.ledger, field_predicate(index, "ExplainTxn", "direction").pred_id, encoded, [("string", direction)])
    set_field(graph.ledger, field_predicate(index, "ExplainTxn", "amount").pred_id, encoded, [("int", amount)])
    return encoded


def _person_exists_rule(rule_id: str = "Person:exists") -> Rule:
    person = Var("$person")
    return Rule(id=rule_id, when=(PredAtom("Person:exists", [person]),), ports={"person": person})


def _person_region_rule(rule_id: str = "person_region") -> Rule:
    person = Var("$person")
    region = Var("$region")
    return Rule(
        id=rule_id,
        when=(PredAtom("Person:exists", [person]), PredAtom("person:region", [person, region])),
        ports={"person": person, "region": region},
    )


def _aggregate_rule() -> Rule:
    total = Var("$total")
    amount = Var("$amount")
    order = Var("$order")
    aggregate = AggregateAtom("sum", amount, [PredAtom("OrderAmount", [order, amount])])
    return Rule(id="amount_sum", when=(CmpAtom("eq", total, aggregate),), ports={"total": total})


def _atom_repr_text(row: object) -> str:
    explanation = row.explain()  # type: ignore[attr-defined]
    self_evidence = explanation.evidence
    assert self_evidence is not None
    return "\n".join(
        atom.repr_text or ""
        for path in self_evidence.paths
        for rule in path.rules
        for atom in rule.atoms
    )


def _row_binding_value(row: object, port_name: str) -> object:
    value = row.bindings[port_name]  # type: ignore[attr-defined,index]
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _narrate_atom_lines(row: object) -> tuple[str, ...]:
    explanation = row.explain()  # type: ignore[attr-defined]
    lines = explanation.narrate()
    assert lines is not None
    return tuple(line for line in lines if line.strip().startswith("✓"))


class RuleExprEvaluatePublicDispatchTests(unittest.TestCase):
    def test_ruleexpr_native_evaluate_returns_evaluate_result(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "alice")
        rule = _person_exists_rule()
        region = _person_region_rule()
        expr = (rule.as_("exists") & region.as_("region")).join_by_ports("person")

        result = graph.eval.evaluate(expr, head=rule, engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertTrue(result)
        self.assertIn(encoded, str(result[0].bindings))
        self.assertNotIn("occurrence_map", result[0].bindings)
        self.assertNotIn("join_materializations", result[0].bindings)
        self.assertRegex(result.result_id, r"^evalr_v1:[0-9a-f]{64}$")
        self.assertRegex(result.fingerprint.view_snapshot_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(result.fingerprint.result_digest, r"^sha256:[0-9a-f]{64}$")
        self.assertIsNone(result.fingerprint.config_digest)
        self.assertFalse(hasattr(result[0], "candidate_id"))
        self.assertFalse(hasattr(result[0], "support_digest"))
        explanation = result[0].explain()
        self.assertIsInstance(explanation, Explanation)
        self.assertIsNotNone(explanation.evidence)
        assert explanation.evidence is not None
        self.assertTrue(explanation.evidence.paths)
        rules = explanation.evidence.paths[0].rules
        self.assertTrue(any(rule.role == "head" for rule in rules))
        self.assertTrue(any(rule.role == "body" for rule in rules))
        self.assertTrue(any(atom.repr_text for rule in rules for atom in rule.atoms))
        self.assertIsInstance(result[0].close(), Rule)

    def test_nested_ruleexpr_evaluates_like_manual_dnf(self) -> None:
        graph = _store()
        _seed_person(graph, "alice", region="us")
        _seed_person(graph, "bob", region="eu")
        exists = _person_exists_rule("exists_rule")
        region = _person_region_rule("region_rule")
        copy = _person_exists_rule("copy_rule")
        marker = _person_exists_rule("marker_rule")
        nested = (
            ((exists.as_("exists") & region.as_("region")).join_by_ports("person") | copy.as_("copy"))
            & marker.as_("marker")
        ).join_by_ports("person")
        manual = (
            (exists.as_("exists") & region.as_("region") & marker.as_("marker__c0")).join_by_ports("person")
            | (copy.as_("copy") & marker.as_("marker__c1")).join_by_ports("person")
        )
        head = Rule.projection("person")

        nested_result = graph.eval.evaluate(nested, head=head, engine="native")
        manual_result = graph.eval.evaluate(manual, head=head, engine="native")

        self.assertEqual(nested_result.fingerprint.expr_digest, manual_result.fingerprint.expr_digest)
        self.assertEqual(sorted(row.digest for row in nested_result), sorted(row.digest for row in manual_result))
        nested_lines = sorted(_narrate_atom_lines(row) for row in nested_result)
        manual_lines = sorted(_narrate_atom_lines(row) for row in manual_result)
        self.assertEqual(nested_lines, manual_lines)

    def test_native_explain_narrate_uses_head_and_body_rule_repr(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "alice")
        person = Var("$person")
        region = Var("$region")
        rule = Rule(
            id="narrate_region",
            when=(PredAtom("Person:exists", [person]), PredAtom("person:region", [person, region])),
            ports={"person": person, "region": region},
            repr="region %person is %region",
        )

        row = graph.eval.evaluate(rule, head=rule, engine="native")[0]
        narrative = row.explain().narrate()

        assert narrative is not None
        text = "\n".join(narrative)
        self.assertIn("region Person alice is us", text)
        self.assertNotIn(encoded, text)

    def test_row_explain_anchors_each_passed_row_to_its_own_bindings(self) -> None:
        graph = _anchor_store()
        u1 = _seed_anchor_user(graph, "u-1", region="us", age=30, tag="alpha")
        u2 = _seed_anchor_user(graph, "u-2", region="eu", age=40, tag="beta")
        index = build_schema_index(graph.schema_ir)
        region_pred = field_predicate(index, "ExplainAnchorUser", "region").pred_id
        age_pred = field_predicate(index, "ExplainAnchorUser", "age").pred_id
        user = Var("$user")
        region = Var("$region")
        age = Var("$age")
        rule = Rule(
            id="adult_anchor",
            when=(
                PredAtom(region_pred, [user, region]),
                PredAtom(age_pred, [user, age]),
                CmpAtom("ge", age, Const(18)),
            ),
            ports={"user": user, "region": region, "age": age},
        )

        result = graph.eval.evaluate(rule, head=rule, engine="native")

        self.assertEqual(result.count(), 2)
        rows_by_user = {str(_row_binding_value(row, "user")): row for row in result}
        first_text = _atom_repr_text(rows_by_user[u1])
        second_text = _atom_repr_text(rows_by_user[u2])
        self.assertIn("AnchorUser u-1 region us", first_text)
        self.assertIn("AnchorUser u-1 age 30", first_text)
        self.assertIn("30 >= 18", first_text)
        self.assertNotIn(u1, first_text)
        self.assertNotIn("AnchorUser u-2", first_text)
        self.assertNotIn("AnchorUser u-2 region eu", first_text)
        self.assertNotIn("AnchorUser u-2 age 40", first_text)
        self.assertNotIn("40 >= 18", first_text)
        self.assertIn("AnchorUser u-2 region eu", second_text)
        self.assertIn("AnchorUser u-2 age 40", second_text)
        self.assertIn("40 >= 18", second_text)
        self.assertNotIn(u2, second_text)
        self.assertNotIn("AnchorUser u-1", second_text)
        self.assertNotIn("AnchorUser u-1 region us", second_text)
        self.assertNotIn("AnchorUser u-1 age 30", second_text)
        self.assertNotIn("30 >= 18", second_text)

    def test_initial_probe_seed_uses_lowered_occurrence_vars_and_unwraps_values(self) -> None:
        x = Var("$x")
        region = Var("$region")
        age = Var("$age")
        left = Rule(id="left", when=(PredAtom("left_p", [x, region]),), ports={"x": x, "region": region})
        right = Rule(id="right", when=(PredAtom("right_p", [x, age]),), ports={"x": x, "age": age})
        head = Rule(
            id="left_head",
            when=(PredAtom("left_p", [x, region]), PredAtom("right_p", [x, age])),
            ports={"x": x, "region": region, "age": age},
        )
        join_plan = _lower_rule_expr(
            (left.as_("left") & right.as_("right")).join(left.as_("left").x.eq(right.as_("right").x)),
            head=head,
        )
        row = SimpleNamespace(
            bindings={
                "x": {"kind": "entity_ref", "value": "idref_v1:User:u-1"},
                "region": {"kind": "literal", "tag": "string", "value": "us"},
                "age": {"kind": "literal", "tag": "int", "value": 30},
            }
        )

        join_seed = _initial_probe_bindings_for_row(row, join_plan)

        x_exec_vars = tuple(
            binding.alias_local_execution_var.name
            for occurrence in join_plan.occurrence_map
            for binding in occurrence.port_bindings
            if binding.source_var.name == "$x"
        )
        self.assertGreaterEqual(len(x_exec_vars), 2)
        self.assertTrue(all(join_seed[name] == "idref_v1:User:u-1" for name in x_exec_vars))
        self.assertTrue(any(value == "us" for value in join_seed.values()))
        self.assertTrue(any(value == 30 for value in join_seed.values()))
        self.assertTrue(all(not isinstance(value, dict) for value in join_seed.values()))

        or_plan = _lower_rule_expr(left.as_("left") | right.as_("right"), head=head)
        or_seed = _initial_probe_bindings_for_row(row, or_plan)
        or_x_exec_vars = tuple(
            binding.alias_local_execution_var.name
            for occurrence in or_plan.occurrence_map
            for binding in occurrence.port_bindings
            if binding.source_var.name == "$x"
        )
        self.assertGreaterEqual(len(or_x_exec_vars), 2)
        self.assertTrue(all(or_seed[name] == "idref_v1:User:u-1" for name in or_x_exec_vars))

    def test_closed_head_false_still_produces_failed_evidence(self) -> None:
        graph = _store()
        _seed_person(graph, "closed-false", region="us")
        index = build_schema_index(graph.schema_ir)
        identity_pred_id = entity_info(index, "Person").identity_predicates["name"].pred_id
        person = Var("$person")
        body = _person_exists_rule()
        closed = Rule(
            id="Person:exists_closed_missing",
            when=(PredAtom("Person:exists", [person]), PredAtom(identity_pred_id, [person, Const("missing")])),
            ports={"person": person},
        )

        explanation = graph.eval.explain(body, head=closed, engine="native")

        self.assertEqual(explanation.status, "failed")
        self.assertEqual(explanation.failure_class, "closed_head_false")
        self.assertIsNotNone(explanation.evidence)
        assert explanation.evidence is not None
        self.assertTrue(explanation.evidence.paths)

    def test_application_rule_input_uses_c35_single_rule_coercion(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "bob")
        rule = _person_exists_rule()

        result = graph.eval.evaluate(rule, head=rule, engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertTrue(result)
        self.assertIn(encoded, str(result[0].bindings))
        self.assertEqual(
            result.fingerprint.view_snapshot_digest,
            graph.eval.evaluate(rule, head=rule, engine="native").fingerprint.view_snapshot_digest,
        )

    def test_free_form_head_id_evaluates_query_style_rows(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "query", region="us")
        rule = _person_region_rule("find_us_users")

        result = graph.eval.evaluate(rule, head=rule, engine="native")

        self.assertEqual(result.head.id, "find_us_users")
        self.assertEqual(result.count(), 1)
        self.assertEqual(result[0].bindings["person"]["value"], encoded)
        self.assertEqual(result[0].bindings["region"]["value"], "us")
        self.assertEqual(result[0].kind, "fact_triple")

    def test_schema_backed_head_id_still_rejects_arity_mismatch(self) -> None:
        graph = _store()
        _seed_person(graph, "arity")
        person = Var("$person")
        rule = Rule(
            id="Person:exists",
            when=(PredAtom("Person:exists", [person]),),
            ports={"person": person, "extra": person},
        )

        with self.assertRaisesRegex(WhereValidationError, "head_vars length must match target arg_specs"):
            graph.eval.evaluate(rule, head=rule, engine="native")

    def test_missing_head_uses_sdk_store_error(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with self.assertRaisesRegex(SDKStoreError, "requires head="):
            graph.eval.evaluate(rule)

    def test_invalid_head_types_use_sdk_store_error(self) -> None:
        graph = _store()
        rule = _person_exists_rule()
        with sdk.vars("p") as (p,):
            legacy_rule = dsl.Rule(id="legacy", version="v1", select=[p], where=[sdk.Pred("Person:exists", p)])
            inference = sdk.Inference(
                id="legacy_inference",
                version="v1",
                when=[sdk.Pred("Person:exists", p)],
                emits=sdk.EmitSpec("Person:exists", [p]),
            )
        inspected = RuleExprInspect(ast=(), occurrences=(), joins=(), unjoined_same_name_ports=())

        for invalid in (legacy_rule, inference, {"head": "dict"}, "Person:exists", inspected):
            with self.subTest(invalid=type(invalid).__name__):
                with self.assertRaisesRegex(SDKStoreError, "head= must be Rule"):
                    graph.eval.evaluate(rule, head=invalid)

    def test_external_head_filters_rows_and_evaluates(self) -> None:
        graph = _store()
        alice = _seed_person(graph, "alice", region="eu")
        _seed_person(graph, "bob", region="us")
        body = _person_region_rule("body_region")
        person = Var("$person")
        region = Var("$region")
        external_head = Rule(
            id="person:region",
            when=(
                PredAtom("Person:exists", [person]),
                PredAtom("person:region", [person, region]),
                CmpAtom("eq", region, Const("eu")),
            ),
            ports={"person": person, "region": region},
        )

        result = graph.eval.evaluate(body, head=external_head, engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertTrue(result)
        self.assertIn(alice, str(result[0].bindings))
        self.assertNotIn("bob", str(result[0].bindings))

    def test_projection_head_evaluates_and_preserves_argument_order(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "erin", region="apac")
        rule = _person_region_rule()

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            result = graph.eval.evaluate(rule, head=Rule.projection("region", "person"), engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertEqual(result.count(), 0)
        request = evaluate.call_args.args[0]
        self.assertEqual(request.plans[0].heads[0].head_var_names, ("$__projection_0", "$__projection_1"))
        self.assertIn("$__projection_0", repr(request.plans[0].body_ir))
        self.assertNotIn("__factgraph_projection_placeholder", repr(request.plans[0].body_ir))

        self.assertTrue(encoded)

    def test_row_close_adds_value_and_entity_identity_literals(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "alice", region="eu")
        rule = _person_region_rule("body_region")
        person = Var("$person")
        region = Var("$region")
        head = Rule(
            id="person:region",
            when=(PredAtom("Person:exists", [person]), PredAtom("person:region", [person, region])),
            ports={"person": person, "region": region},
        )

        result = graph.eval.evaluate(rule, head=head, engine="native")
        closed = result[0].close()

        self.assertIsInstance(closed, Rule)
        self.assertIn("_closed_", closed.id)
        self.assertNotIn("__factgraph_projection_placeholder", repr(closed.when))
        self.assertIn(encoded, str(result[0].bindings))
        self.assertTrue(any(isinstance(atom, CmpAtom) and atom.rhs == Const("eu") for atom in closed.when))
        index = build_schema_index(graph.schema_ir)
        identity_pred_id = entity_info(index, "Person").identity_predicates["name"].pred_id
        self.assertTrue(
            any(
                isinstance(atom, PredAtom)
                and atom.pred_id == identity_pred_id
                and tuple(atom.terms)[1] == Const("alice")
                for atom in closed.when
            )
        )
        self.assertTrue(_inspect_closed_head(closed, schema_index=build_schema_index(graph.schema_ir)).is_closed)

    def test_row_close_detached_row_raises_detached_error(self) -> None:
        graph = _store()
        _seed_person(graph, "detached")
        rule = _person_exists_rule()
        row = graph.eval.evaluate(rule, head=rule, engine="native")[0]

        detached = row.__class__(
            row_id=row.row_id,
            bindings=row.bindings,
            kind=row.kind,
            digest=row.digest,
            closed_head_digest=row.closed_head_digest,
            certainty=row.certainty,
        )

        with self.assertRaisesRegex(DetachedRowError, "detached"):
            detached.close()

    def test_manual_explain_rejects_non_closed_head(self) -> None:
        graph = _store()
        _seed_person(graph, "open")
        rule = _person_exists_rule()

        with self.assertRaisesRegex(RuleExprError, "must be closed"):
            graph.eval.explain(rule, head=rule, engine="native")

    def test_manual_explain_uses_closed_head_and_manual_checked_scope(self) -> None:
        graph = _store()
        _seed_person(graph, "manual")
        rule = _person_exists_rule()
        result = graph.eval.evaluate(rule, head=rule, engine="native")
        closed = result[0].close()

        explanation = graph.eval.explain(rule, head=closed, engine="native")

        self.assertIsInstance(explanation, Explanation)
        self.assertEqual(explanation.status, "passed")
        self.assertEqual(explanation.checked_scope["semantics_source"], "manual_standalone")
        self.assertIsNone(explanation.checked_scope["evaluate_config_digest"])
        self.assertIsNone(explanation.checked_scope["semantics_match"])
        self.assertIsNotNone(explanation.row)
        assert explanation.row is not None
        self.assertEqual(dict(explanation.row.bindings), dict(result[0].bindings))
        self.assertEqual(explanation.checked_scope["closed_head_digest"], closed_head_digest_for(closed))

    def test_projection_undeclared_port_uses_ruleexpr_error(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with self.assertRaisesRegex(RuleExprError, "is not declared by the RuleExpr"):
            graph.eval.evaluate(rule, head=Rule.projection("unknown"), engine="native")

    def test_same_id_version_mismatch_warns_and_evaluates(self) -> None:
        graph = _store()
        _seed_person(graph, "dana")
        person = Var("$person")
        rule = Rule(
            id="Person:exists",
            version="v1",
            when=(PredAtom("Person:exists", [person]),),
            ports={"person": person},
        )
        head = Rule(id=rule.id, version="v2", when=rule.when, ports=rule.ports)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = graph.eval.evaluate(rule, head=head, engine="native")

        self.assertTrue(result)
        self.assertEqual(len(caught), 1)
        self.assertIn("different version", str(caught[0].message))

    def test_same_id_different_digest_uses_ruleexpr_error(self) -> None:
        graph = _store()
        body = _person_exists_rule("same_id")
        head = _person_region_rule("same_id")

        with self.assertRaisesRegex(RuleExprError, "different content digest"):
            graph.eval.evaluate(body, head=head, engine="native")

    def test_same_name_ambiguity_uses_ruleexpr_error_before_evaluation(self) -> None:
        graph = _store()
        left = _person_exists_rule("left")
        right = _person_exists_rule("right")
        expr = left.as_("left") & right.as_("right")

        with self.assertRaisesRegex(RuleExprError, "ambiguous across occurrences"):
            graph.eval.evaluate(expr, head=left, engine="native")

    def test_souffle_and_problog_paths_use_existing_request_shape(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        for engine in ("souffle", "problog"):
            with self.subTest(engine=engine):
                with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
                    result = graph.eval.evaluate(rule, head=rule, engine=engine)

                self.assertIsInstance(result, EvaluateResult)
                self.assertEqual(result.count(), 0)
                request = evaluate.call_args.args[0]
                self.assertEqual(request.engine, engine)
                self.assertEqual(request.plans[0].engine_options, {})

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_souffle_row_explain_uses_reach_chain_before_support_artifact(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "souffle")
        rule = _person_exists_rule()
        support_digest = "sha256:" + ("d" * 64)
        candidate = CandidateSet(
            derivation_id="Person:exists",
            derivation_version="1.0",
            run_id="souffle-run",
            target="Person:exists",
            key_tuple_digest="sha256:" + ("1" * 64),
            tup_digest=None,
            payload={"terms": [encoded]},
            support_digest=support_digest,
            support_kind=SOUFFLE_WITNESS_KIND,
            generated_at=0,
            state="generated",
        )
        artifact = ProofReceipt(
            kind=SOUFFLE_WITNESS_KIND,
            root_result_kind="fact",
            binding_items=(("$person", encoded),),
            pred_witnesses=(
                PredWitness(
                    pred_condition_key="c0.c0:Person:exists",
                    asrt_ids=("asrt-souffle-person",),
                ),
            ),
        )

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[candidate]):
            with patch.object(graph._store, "_lookup_support_artifact", return_value=artifact):
                result = graph.eval.evaluate(rule, head=rule, engine="souffle")

        with patch("factgraph.sdk.store.run_diagnostic_souffle", side_effect=AssertionError("old companion should not run")):
            explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        tree = explanation.evidence.paths[0]
        self.assertEqual(tree.metadata["branch_id"], "c0")
        self.assertEqual(tree.certainty.kind, "boolean")
        self.assertEqual({rule.role for rule in tree.rules}, {"head", "body"})
        body = next(rule for rule in tree.rules if rule.role == "body")
        self.assertTrue(body.atoms)
        self.assertEqual(body.atoms[0].verdict.certainty.kind, "boolean")
        self.assertIn("Person souffle", body.atoms[0].repr_text or "")
        self.assertNotIn("asrt-souffle-person", body.atoms[0].repr_text or "")

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_souffle_reach_chain_explain_preserves_row_bindings_and_failure_value(self) -> None:
        graph = _anchor_store()
        eve = _seed_anchor_user(graph, "eve", region="us", age=2000, tag="risk")
        _seed_anchor_user(graph, "mallory", region="eu", age=30, tag="risk")
        user = Var("$user")
        age = Var("$age")
        region_us = Rule(
            id="region_us",
            when=(PredAtom("explain_anchor_user:region", [user, Const("us")]),),
            ports={"user": user},
            repr="region us %user",
        )
        tag_risk = Rule(
            id="tag_risk",
            when=(PredAtom("explain_anchor_user:tag", [user, Const("risk")]),),
            ports={"user": user},
            repr="risk tag %user",
        )
        young = Rule(
            id="young_u",
            when=(PredAtom("explain_anchor_user:age", [user, age]), CmpAtom("lt", age, Const(90))),
            ports={"user": user, "age": age},
            repr="young %user age %age",
        )
        expr = ((region_us.as_("r") & tag_risk.as_("t")).join_by_ports("user") | young.as_("y"))

        result = graph.eval.evaluate(expr, head=Rule.projection("user"), engine="souffle")
        row = next(row for row in result if _row_binding_value(row, "user") == eve)

        with patch("factgraph.sdk.store.run_diagnostic_souffle", side_effect=AssertionError("old companion should not run")):
            explanation = row.explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        self.assertEqual(explanation.evidence.certainty, row.certainty)
        text = "\n".join(explanation.narrate() or ())
        self.assertIn("AnchorUser eve region us", text)
        self.assertIn("AnchorUser eve has tag risk", text)
        self.assertIn("young AnchorUser eve age 2000", text)
        self.assertIn("2000 < 90", text)
        self.assertNotIn("AnchorUser mallory age 30", text)
        self.assertIn("[c0:atom:0]", text)
        self.assertIn("[c1:atom:1]", text)
        self.assertNotIn("souffle_proof_receipt", text)
        paths_by_id = {path.tree_id: path for path in explanation.evidence.paths}
        self.assertEqual(paths_by_id["c0"].metadata["branch_probability"], 1.0)
        self.assertIsNone(paths_by_id["c1"].metadata["branch_probability"])

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_souffle_reach_chain_explain_rebakes_holding_branch_witnesses_from_terminal_row(self) -> None:
        graph = _txn_store()
        _seed_txn(graph, "M2a", customer="C-MALLORY", direction="out", amount=27000)
        _seed_txn(graph, "E1", customer="C-EVE", direction="in", amount=12000)
        eo = _seed_txn(graph, "Eo", customer="C-EVE", direction="out", amount=28000)
        txn = Var("$txn")
        amount = Var("$amount")
        rule = Rule(
            id="txn_forwards_out",
            when=(
                PredAtom("ExplainTxn:exists", [txn]),
                PredAtom("explain_txn:customer", [txn, Const("C-EVE")]),
                PredAtom("explain_txn:direction", [txn, Const("out")]),
                PredAtom("explain_txn:amount", [txn, amount]),
                CmpAtom("gt", amount, Const(20000)),
            ),
            ports={"txn": txn},
            repr="%txn forwards out",
        )

        result = graph.eval.evaluate(rule, head=rule, engine="souffle")
        row = next(row for row in result if _row_binding_value(row, "txn") == eo)

        with patch("factgraph.sdk.store.run_diagnostic_souffle", side_effect=AssertionError("old companion should not run")):
            explanation = row.explain()

        self.assertEqual(explanation.status, "passed")
        text = "\n".join(explanation.narrate() or ())
        self.assertIn("Txn Eo exists", text)
        self.assertIn("Txn Eo is by C-EVE", text)
        self.assertIn("Txn Eo direction out", text)
        self.assertIn("Txn Eo amount 28000", text)
        self.assertNotIn("Txn M2a exists", text)
        self.assertNotIn("Txn E1 is by C-EVE", text)
        self.assertNotIn("Txn M2a is by C-EVE", text)

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_souffle_reach_chain_explain_keeps_wide_failed_branch_rich_without_unbound(self) -> None:
        graph = _anchor_store()
        eve = _seed_anchor_user(graph, "eve", region="us", age=2000, tag="risk")
        _seed_anchor_user(graph, "mallory", region="eu", age=30, tag="risk")
        user = Var("$user")
        age = Var("$age")
        holding = Rule(
            id="wide_holding",
            when=(
                PredAtom("explain_anchor_user:region", [user, Const("us")]),
                PredAtom("explain_anchor_user:tag", [user, Const("risk")]),
            ),
            ports={"user": user},
            repr="holding %user",
        )
        wide_tail = tuple(
            PredAtom("explain_anchor_user:tag", [Var(f"$other{index}"), Var(f"$tag{index}")])
            for index in range(10)
        )
        failed_wide = Rule(
            id="wide_failed",
            when=(
                PredAtom("explain_anchor_user:age", [user, age]),
                CmpAtom("lt", age, Const(90)),
                *wide_tail,
            ),
            ports={"user": user},
            repr="failed wide %user",
        )
        expr = holding.as_("hold") | failed_wide.as_("wide")

        result = graph.eval.evaluate(expr, head=Rule.projection("user"), engine="souffle")
        row = next(row for row in result if _row_binding_value(row, "user") == eve)

        with patch("factgraph.sdk.store.run_diagnostic_souffle", side_effect=AssertionError("old companion should not run")):
            explanation = row.explain()

        self.assertEqual(explanation.status, "passed")
        text = "\n".join(explanation.narrate() or ())
        self.assertIn("AnchorUser eve region us", text)
        self.assertIn("AnchorUser eve has tag risk", text)
        self.assertIn("AnchorUser eve age 2000", text)
        self.assertIn("2000 < 90", text)
        self.assertIn("[c0:atom:0]", text)
        self.assertIn("[c1:atom:1]", text)
        self.assertNotIn("<unbound>", text)
        self.assertNotIn("souffle:", text)

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_souffle_reach_chain_explain_keeps_wide_holding_branch_rich_after_dropping_dead_witness_columns(self) -> None:
        graph = _anchor_store()
        eve = _seed_anchor_user(graph, "eve", region="us", age=42, tag="risk")
        _seed_anchor_user(graph, "mallory", region="eu", age=30, tag="risk")
        user = Var("$user")
        repeated_tag_atoms = tuple(
            PredAtom("explain_anchor_user:tag", [user, Var(f"$tag{index}")])
            for index in range(13)
        )
        rule = Rule(
            id="wide_holding_without_witness_columns",
            when=(
                PredAtom("explain_anchor_user:region", [user, Const("us")]),
                *repeated_tag_atoms,
            ),
            ports={"user": user},
            repr="wide holding %user",
        )

        result = graph.eval.evaluate(rule, head=rule, engine="souffle")
        row = next(row for row in result if _row_binding_value(row, "user") == eve)

        with patch("factgraph.sdk.store.run_diagnostic_souffle", side_effect=AssertionError("old companion should not run")):
            explanation = row.explain()

        self.assertEqual(explanation.status, "passed")
        text = "\n".join(explanation.narrate() or ())
        self.assertIn("AnchorUser eve region us", text)
        self.assertIn("AnchorUser eve has tag risk", text)
        self.assertIn("[c0:atom:13]", text)
        self.assertNotIn("<unbound>", text)
        self.assertNotIn("souffle:", text)

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_souffle_reach_chain_reports_unknown_overwide_branch_before_runner_crash(self) -> None:
        from factgraph.adapters.souffle.reach_explain import (
            SouffleReachExplainUnsupported,
            _build_reach_program,
            _run_reach_program,
        )

        graph = _anchor_store()
        eve = _seed_anchor_user(graph, "eve", region="us", age=2000, tag="risk")
        user = Var("$user")
        rule = Rule(
            id="overwide_reach_holding",
            when=tuple(PredAtom("explain_anchor_user:tag", [user, Var(f"$tag{index}")]) for index in range(24)),
            ports={"user": user},
        )
        plan = _lower_application_rule(rule, head=rule)
        program = _build_reach_program(plan, {"user": eve})

        with self.assertRaisesRegex(
            SouffleReachExplainUnsupported,
            "souffle reach relation arity exceeds supported limit before branch outcome was known",
        ) as ctx:
            _run_reach_program(graph._store, program)

        message = str(ctx.exception)
        self.assertIn("arity=", message)
        self.assertIn("limit=22", message)

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_souffle_eval_builds_proof_receipt_from_per_branch_witness_rows(self) -> None:
        graph = _anchor_store()
        eve = _seed_anchor_user(graph, "eve", region="us", age=42, tag="risk")
        _seed_anchor_user(graph, "mallory", region="eu", age=30, tag="risk")
        user = Var("$user")
        region_eu = Rule(
            id="branch_region_eu",
            when=(PredAtom("explain_anchor_user:region", [user, Const("eu")]),),
            ports={"user": user},
        )
        region_us = Rule(
            id="branch_region_us",
            when=(PredAtom("explain_anchor_user:region", [user, Const("us")]),),
            ports={"user": user},
        )
        tag_risk = Rule(
            id="branch_tag_risk",
            when=(PredAtom("explain_anchor_user:tag", [user, Const("risk")]),),
            ports={"user": user},
        )
        expr = region_eu.as_("eu") | (region_us.as_("us") & tag_risk.as_("tag")).join_by_ports("user")

        result = graph.eval.evaluate(expr, head=Rule.projection("user"), engine="souffle")
        row = next(row for row in result if _row_binding_value(row, "user") == eve)

        artifact = result._row_support_artifacts[row.row_id]  # type: ignore[index]
        self.assertEqual(artifact.kind, SOUFFLE_WITNESS_KIND)
        witness_keys = {witness.pred_condition_key for witness in artifact.pred_witnesses}
        self.assertEqual(witness_keys, {"c0.c0:explain_anchor_user:region", "c0.c1:explain_anchor_user:tag"})
        witness_ids = {asrt_id for witness in artifact.pred_witnesses for asrt_id in witness.asrt_ids}
        self.assertEqual(len(witness_ids), 2)
        self.assertTrue(all("mallory" not in asrt_id for asrt_id in witness_ids))

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_souffle_eval_rejects_overwide_branch_witness_relation_before_runner(self) -> None:
        graph = _anchor_store()
        _seed_anchor_user(graph, "eve", region="us", age=42, tag="risk")
        user = Var("$user")
        when = tuple(PredAtom("explain_anchor_user:region", [user, Var(f"$region{index}")]) for index in range(22))
        rule = Rule(id="overwide_witness_branch", when=when, ports={"user": user})

        with self.assertRaisesRegex(
            WhereValidationError,
            "souffle witness relation arity exceeds supported limit",
        ) as ctx:
            graph.eval.evaluate(rule, head=rule, engine="souffle")

        message = str(ctx.exception)
        self.assertIn("arity=23", message)
        self.assertIn("limit=22", message)
        self.assertIn("witness_predicates=22", message)

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_souffle_reach_chain_explain_falls_back_when_runner_fails(self) -> None:
        graph = _anchor_store()
        _seed_anchor_user(graph, "eve", region="us", age=42, tag="risk")
        user = Var("$user")
        rule = Rule(
            id="runner_failure_fallback",
            when=(PredAtom("explain_anchor_user:region", [user, Const("us")]),),
            ports={"user": user},
        )
        result = graph.eval.evaluate(rule, head=rule, engine="souffle")

        def fake_run_package(package_dir: object, entrypoints: object, *, engine: str) -> Path:
            path = Path(package_dir) / "fake_run_manifest.json"
            path.write_text(json.dumps({"engine_mode": "souffle", "exit_code": 1}), encoding="utf-8")
            return path

        with patch("factgraph.adapters.souffle.reach_explain.run_package", side_effect=fake_run_package):
            with patch("factgraph.sdk.store.run_diagnostic_souffle", side_effect=AssertionError("old companion should not run")):
                explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        text = "\n".join(explanation.narrate() or ())
        self.assertIn("souffle:", text)
        self.assertNotIn("<unbound>", text)

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_souffle_reach_chain_explain_keeps_ne_rich(self) -> None:
        graph = _anchor_store()
        _seed_anchor_user(graph, "eve", region="us", age=2000, tag="risk")
        mallory = _seed_anchor_user(graph, "mallory", region="eu", age=30, tag="risk")
        user = Var("$user")
        rule = Rule(
            id="ne_rule",
            when=(
                PredAtom("explain_anchor_user:region", [user, Const("us")]),
                CmpAtom("ne", user, Const(mallory)),
            ),
            ports={"user": user},
            repr="ne %user",
        )

        result = graph.eval.evaluate(rule, head=rule, engine="souffle")

        with patch("factgraph.sdk.store.run_diagnostic_souffle", side_effect=AssertionError("old companion should not run")):
            narrative = result[0].explain().narrate()

        assert narrative is not None
        text = "\n".join(narrative)
        self.assertIn("AnchorUser eve does not equal AnchorUser mallory", text)
        self.assertIn("[c0:atom:1]", text)
        self.assertNotIn("edb_fact", text)
        self.assertNotIn("c0:head:0", text)

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_souffle_reach_chain_explain_keeps_not_pred_and_compare_rich(self) -> None:
        graph = _anchor_store()
        _seed_anchor_user(graph, "eve", region="us", age=2000, tag="risk")
        user = Var("$user")
        age = Var("$age")
        rule = Rule(
            id="not_and_compare_rule",
            when=(
                PredAtom("explain_anchor_user:age", [user, age]),
                CmpAtom("ge", age, Const(100)),
                NotAtom(AndExpr([PredAtom("explain_anchor_user:tag", [user, Const("blocked")])])),
            ),
            ports={"user": user},
            repr="not compare %user",
        )

        result = graph.eval.evaluate(rule, head=rule, engine="souffle")

        with patch("factgraph.sdk.store.run_diagnostic_souffle", side_effect=AssertionError("old companion should not run")):
            narrative = result[0].explain().narrate()

        assert narrative is not None
        text = "\n".join(narrative)
        self.assertIn("2000 >= 100", text)
        self.assertIn("!AnchorUser eve has tag blocked", text)
        self.assertIn("[c0:atom:2]", text)
        self.assertNotIn("souffle_proof_receipt", text)

    def test_souffle_row_explain_falls_back_to_minimal_paths_on_converter_error(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "souffle-fallback")
        rule = _person_exists_rule()
        support_digest = "sha256:" + ("e" * 64)
        candidate = CandidateSet(
            derivation_id="Person:exists",
            derivation_version="1.0",
            run_id="souffle-run",
            target="Person:exists",
            key_tuple_digest="sha256:" + ("2" * 64),
            tup_digest=None,
            payload={"terms": [encoded]},
            support_digest=support_digest,
            support_kind=SOUFFLE_WITNESS_KIND,
            generated_at=0,
            state="generated",
        )
        artifact = ProofReceipt(
            kind=SOUFFLE_WITNESS_KIND,
            root_result_kind="fact",
            binding_items=(("$person", encoded),),
            pred_witnesses=(
                PredWitness(
                    pred_condition_key="c0.c0:Person:exists",
                    asrt_ids=("asrt-souffle-person",),
                ),
            ),
        )

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[candidate]):
            with patch.object(graph._store, "_lookup_support_artifact", return_value=artifact):
                result = graph.eval.evaluate(rule, head=rule, engine="souffle")

        with patch("factgraph.sdk.store.souffle_reach_explain_to_evidence_graph", side_effect=ValueError("reach bad")):
            with patch("factgraph.sdk.store.run_diagnostic_souffle", side_effect=AssertionError("old companion should not run")):
                with patch("factgraph.sdk.store._souffle_support_artifact_to_evidence_graph", side_effect=ValueError("bad")):
                    explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        tree = explanation.evidence.paths[0]
        self.assertEqual(tree.metadata["fallback"], "minimal_row_evidence")
        self.assertEqual([rule.role for rule in tree.rules], ["head"])

    @unittest.skipIf(shutil.which("problog") is None, "problog CLI is not available")
    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_native_problog_and_souffle_projection_atom_lines_match(self) -> None:
        graph = _store()
        _seed_person(graph, "tri-engine", "us")
        rule = _person_region_rule("tri_engine_region")

        native = graph.eval.evaluate(rule, head=rule, engine="native")
        problog = graph.eval.evaluate(rule, head=rule, engine="problog")
        souffle = graph.eval.evaluate(rule, head=rule, engine="souffle")

        self.assertEqual(_narrate_atom_lines(problog[0]), _narrate_atom_lines(native[0]))
        self.assertEqual(_narrate_atom_lines(souffle[0]), _narrate_atom_lines(native[0]))

    def test_problog_row_explain_uses_provenance_envelope_paths(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "problog")
        index = build_schema_index(graph.schema_ir)
        set_field(
            graph.ledger,
            field_predicate(index, "Person", "region").pred_id,
            encoded,
            [("string", "us")],
            meta={"source": "problog-test", "raw_kind": "probabilistic", "bound": [0.4, 0.4]},
        )
        rule = Rule(
            id="Person:exists",
            when=(PredAtom("person:region", [Var("$person"), Const("us")]),),
            ports={"person": Var("$person")},
            repr="person %person exists",
        )
        trace = parse_problog_trace(
            f"""
 call Person:exists({encoded}) {{0.00010}} []
  call edb_fact(X1,'person:region','{encoded}','us') {{0.00011}} []
   result edb_fact(X1,'person:region','{encoded}','us') ({encoded},us) {{{{}}}} {{0.000115}} []
  complete edb_fact(X1,'person:region','{encoded}','us') {{0.000116}} {{0.000006}} []
  result Person:exists({encoded}) ({encoded},) {{{{}}}} {{0.00012}} []
 complete Person:exists({encoded}) {{0.00013}} {{0.00003}} []

Person:exists({encoded}):\t0.73
""".strip()
        )
        support_digest = "sha256:" + ("f" * 64)
        candidate = CandidateSet(
            derivation_id="Person:exists",
            derivation_version="1.0",
            run_id="problog-run",
            target="Person:exists",
            key_tuple_digest="sha256:" + ("3" * 64),
            tup_digest=None,
            payload={"terms": [encoded]},
            support_digest=support_digest,
            support_kind=PROBLOG_PROVENANCE_KIND,
            generated_at=0,
            state="generated",
            confidence=0.73,
            confidence_kind="probability",
        )
        envelope = ProvenanceEnvelope(
            candidate_id="cand_v2:problog",
            engine="problog",
            payload_type="proof_trace",
            payload=problog_trace_to_dict(trace),
        )

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[candidate]):
            with patch.object(graph._store, "_lookup_provenance_envelope", return_value=envelope):
                result = graph.eval.evaluate(rule, head=rule, engine="problog")

        explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        self.assertEqual(explanation.evidence.engine, "problog")
        self.assertEqual(explanation.evidence.certainty.kind, "probabilistic")
        self.assertEqual(explanation.evidence.certainty.lo, 0.73)
        tree = explanation.evidence.paths[0]
        self.assertEqual(tree.certainty.kind, "probabilistic")
        self.assertEqual(tree.certainty.lo, 0.73)
        self.assertEqual(tree.tree_id, "c0")
        self.assertEqual(tree.metadata["candidate_id"], "cand_v2:problog")
        self.assertEqual(explanation.evidence.subject_binding["person"], "Person problog")
        self.assertEqual({rule.role for rule in tree.rules}, {"head", "body"})
        self.assertTrue(tree.rules[0].atoms)
        head = next(rule for rule in tree.rules if rule.role == "head")
        body = next(rule for rule in tree.rules if rule.role == "body")
        self.assertEqual(head.rule_id, "Person:exists")
        self.assertEqual(head.repr_text, "person Person problog exists")
        self.assertEqual(head.ports["person"], "Person problog")
        narrative = explanation.narrate()
        assert narrative is not None
        self.assertIn("person Person problog exists", "\n".join(narrative))
        self.assertNotIn(f"person {encoded} exists", "\n".join(narrative))
        self.assertEqual(head.atoms[0].atom_id, "c0:head:0")
        self.assertEqual(head.atoms[0].verdict.certainty.kind, "boolean")
        status_atom = body.atoms[0]
        self.assertEqual(status_atom.atom_id, "c0:body:1")
        self.assertEqual(status_atom.form.predicate, "edb_fact")
        self.assertEqual(status_atom.verdict.certainty.kind, "probabilistic")
        self.assertEqual(status_atom.verdict.certainty.lo, 0.4)
        self.assertEqual(status_atom.verdict.certainty.hi, 0.4)

    def test_problog_row_explain_falls_back_to_minimal_paths_on_converter_error(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "problog-fallback")
        rule = _person_exists_rule()
        support_digest = "sha256:" + ("9" * 64)
        candidate = CandidateSet(
            derivation_id="Person:exists",
            derivation_version="1.0",
            run_id="problog-run",
            target="Person:exists",
            key_tuple_digest="sha256:" + ("4" * 64),
            tup_digest=None,
            payload={"terms": [encoded]},
            support_digest=support_digest,
            support_kind=PROBLOG_PROVENANCE_KIND,
            generated_at=0,
            state="generated",
        )
        envelope = ProvenanceEnvelope(
            candidate_id="cand_v2:problog-bad",
            engine="problog",
            payload_type="proof_trace",
            payload={"engine": "problog", "trace_type": "proof_trace", "events": [], "answers": []},
        )

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[candidate]):
            with patch.object(graph._store, "_lookup_provenance_envelope", return_value=envelope):
                result = graph.eval.evaluate(rule, head=rule, engine="problog")

        with patch("factgraph.sdk.store.run_diagnostic_problog", side_effect=ValueError("projection bad")):
            explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        self.assertEqual(explanation.evidence.paths[0].metadata["fallback"], "minimal_row_evidence")

    @unittest.skipIf(shutil.which("problog") is None, "problog CLI is not available")
    def test_problog_row_explain_uses_diagnostic_projection_before_trace_converter(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "problog-projection")
        index = build_schema_index(graph.schema_ir)
        region_pred = field_predicate(index, "Person", "region").pred_id
        claim = next(claim for claim in graph.ledger.find_claims(pred_id=region_pred, e_ref=encoded))
        graph.ledger.append_annotations(
            [
                AnnotationRow(
                    asrt_id=claim.asrt_id,
                    namespace="problog",
                    category="semantic",
                    key="probability",
                    kind="float",
                    value=0.4,
                    origin="derived",
                    derivation="problog-projection",
                )
            ]
        )
        rule = Rule(
            id="Person:exists",
            when=(PredAtom("Person:exists", [Var("$person")]),),
            ports={"person": Var("$person")},
            repr="person %person exists",
        )
        support_digest = "sha256:" + ("b" * 64)
        candidate = CandidateSet(
            derivation_id="Person:exists",
            derivation_version="1.0",
            run_id="problog-run",
            target="Person:exists",
            key_tuple_digest="sha256:" + ("6" * 64),
            tup_digest=None,
            payload={"terms": [encoded]},
            support_digest=support_digest,
            support_kind=PROBLOG_PROVENANCE_KIND,
            generated_at=0,
            state="generated",
            confidence=0.4,
            confidence_kind="probability",
        )
        envelope = ProvenanceEnvelope(
            candidate_id="cand_v2:problog-projection",
            engine="problog",
            payload_type="proof_trace",
            payload={"engine": "problog", "trace_type": "proof_trace", "events": [], "answers": []},
        )

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[candidate]):
            with patch.object(graph._store, "_lookup_provenance_envelope", return_value=envelope):
                result = graph.eval.evaluate(rule, head=rule, engine="problog")

        with patch("factgraph.sdk.store.problog_trace_to_evidence_graph", side_effect=AssertionError("trace should not run")):
            explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        tree = explanation.evidence.paths[0]
        self.assertEqual(tree.tree_id, "c0")
        self.assertIn("branch_probability", tree.metadata)
        self.assertTrue(any(rule.role == "body" and rule.atoms for rule in tree.rules))
        narrative = explanation.narrate()
        assert narrative is not None
        self.assertFalse(any(line.startswith("      probability:") for line in narrative))
        self.assertFalse(any(line.startswith("  Derivation:") for line in narrative))
        self.assertFalse(any(" [head] ── " in line for line in narrative))
        self.assertIn("  Person:exists  [holds]", narrative)
        self.assertFalse(any('Person:exists ── "person Person problog-projection exists"' in line for line in narrative))
        self.assertTrue(any("Person problog-projection exists" in line for line in narrative))

    def test_pyreason_row_explain_uses_provenance_envelope_timeline(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "pyreason")
        rule = _person_exists_rule()
        trace = PyReasonTraceV0(
            timesteps=2,
            node_events=(
                PyReasonTraceEventV0(
                    time=1,
                    fixpoint_op=1,
                    component=encoded,
                    component_type="node",
                    label="exists",
                    old_bound=(0.0, 1.0),
                    new_bound=(0.84, 0.84),
                    occurred_due_to="pyreason_rule",
                    clause_groundings=("[pyreason]",),
                ),
            ),
            edge_events=(),
        )
        support_digest = "sha256:" + ("a" * 64)
        candidate = CandidateSet(
            derivation_id="Person:exists",
            derivation_version="1.0",
            run_id="pyreason-run",
            target="Person:exists",
            key_tuple_digest="sha256:" + ("5" * 64),
            tup_digest=None,
            payload={"terms": [encoded]},
            support_digest=support_digest,
            support_kind=PYREASON_PROVENANCE_KIND,
            generated_at=0,
            state="generated",
            confidence=0.84,
            confidence_kind="certainty",
        )
        envelope = ProvenanceEnvelope(
            candidate_id="cand_v2:pyreason",
            engine="pyreason",
            payload_type="event_log",
            payload=pyreason_trace_to_dict(trace),
        )

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[candidate]):
            with patch.object(graph._store, "_lookup_provenance_envelope", return_value=envelope):
                result = graph.eval.evaluate(rule, head=rule, engine="pyreason")

        explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        self.assertEqual(explanation.evidence.engine, "pyreason")
        self.assertEqual(explanation.evidence.layout_hint, "timeline")
        self.assertEqual(explanation.evidence.certainty.kind, "possibilistic")
        self.assertEqual(explanation.evidence.certainty.lo, 0.84)
        timeline = explanation.evidence.paths[0]
        self.assertEqual(timeline.certainty.kind, "possibilistic")
        self.assertEqual(timeline.events[0].timestep, 1)
        self.assertEqual(timeline.events[0].form.predicate, "exists")
        self.assertEqual(timeline.events[0].verdict.support[0].meta["clause_groundings"], ("[pyreason]",))

    def test_pyreason_row_explain_falls_back_to_minimal_paths_on_converter_error(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "pyreason-fallback")
        rule = _person_exists_rule()
        support_digest = "sha256:" + ("b" * 64)
        candidate = CandidateSet(
            derivation_id="Person:exists",
            derivation_version="1.0",
            run_id="pyreason-run",
            target="Person:exists",
            key_tuple_digest="sha256:" + ("6" * 64),
            tup_digest=None,
            payload={"terms": [encoded]},
            support_digest=support_digest,
            support_kind=PYREASON_PROVENANCE_KIND,
            generated_at=0,
            state="generated",
        )
        envelope = ProvenanceEnvelope(
            candidate_id="cand_v2:pyreason-bad",
            engine="pyreason",
            payload_type="event_log",
            payload={"engine": "pyreason", "trace_type": "event_log", "timesteps": 0, "node_events": [], "edge_events": []},
        )

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[candidate]):
            with patch.object(graph._store, "_lookup_provenance_envelope", return_value=envelope):
                result = graph.eval.evaluate(rule, head=rule, engine="pyreason")

        explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        self.assertEqual(explanation.evidence.paths[0].metadata["fallback"], "minimal_row_evidence")

    def test_evaluate_rejects_public_engine_options_and_registry(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with self.assertRaisesRegex(SDKStoreError, "engine_options"):
            graph.eval.evaluate(rule, head=rule, engine="native", engine_options={"timeout": 1})
        with self.assertRaisesRegex(SDKStoreError, "registry"):
            graph.eval.evaluate(rule, head=rule, engine="native", registry=object())

    def test_application_rule_accepts_problog_semantics_wrapper(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            result = graph.eval.evaluate(rule, head=rule, config=sdk.ProbLogConfig())

        self.assertIsInstance(result, EvaluateResult)
        request = evaluate.call_args.args[0]
        self.assertEqual(request.engine, "problog")
        self.assertEqual(request.semantics_profile.engine, "problog")
        self.assertEqual(request.semantics_profile.rule_projection, {})
        self.assertIsNotNone(result.fingerprint.config_digest)

    def test_application_rule_accepts_pyreason_semantics_wrapper(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            result = graph.eval.evaluate(rule, head=rule, config=sdk.PyReasonConfig())

        self.assertIsInstance(result, EvaluateResult)
        request = evaluate.call_args.args[0]
        self.assertEqual(request.engine, "pyreason")
        self.assertEqual(request.semantics_profile.engine, "pyreason")
        self.assertEqual(request.semantics_profile.rule_projection, {})

    def test_ruleexpr_accepts_problog_semantics_wrapper_branch_ids(self) -> None:
        graph = _store()
        left = _person_exists_rule("left")
        right = _person_region_rule("right")
        expr = left.as_("left") | right.as_("right")

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            result = graph.eval.evaluate(
                expr,
                head=left,
                config=sdk.ProbLogConfig(case_probabilities={"c0": 0.7}),
            )

        self.assertIsInstance(result, EvaluateResult)
        profile = evaluate.call_args.args[0].semantics_profile
        self.assertEqual(profile.engine, "problog")
        self.assertIn({"target": "branch:0", "kind": "branch_probability", "value": 0.7}, profile.rule_projection["problog"])

    def test_legacy_inference_still_accepts_problog_semantics_wrapper(self) -> None:
        graph = _store()
        with sdk.vars("p") as (p,):
            inference = sdk.Inference(
                id="legacy_wrapper_inference",
                version="v1",
                when=[sdk.Case([sdk.Pred("Person:exists", p)], id="seed_path")],
                emits=sdk.EmitSpec("Person:exists", [p]),
            )

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            result = graph.eval.evaluate(
                inference,
                config=sdk.ProbLogConfig(case_probabilities={"seed_path": 0.8}),
            )

        self.assertIsInstance(result, EvaluateResult)
        profile = evaluate.call_args.args[0].semantics_profile
        self.assertEqual(profile.rule_projection["problog"], [{"target": "branch:0", "kind": "branch_probability", "value": 0.8}])

    def test_application_rule_still_accepts_direct_semantics_profile(self) -> None:
        graph = _store()
        rule = _person_exists_rule()
        profile = sdk.SemanticsProfile(name="profile.t5_8.problog", engine="problog")

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            result = graph.eval.evaluate(rule, head=rule, config=profile)

        self.assertIsInstance(result, EvaluateResult)
        self.assertIs(evaluate.call_args.args[0].semantics_profile, profile)

    def test_application_rule_still_accepts_explicit_problog_engine(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            result = graph.eval.evaluate(rule, head=rule, engine="problog")

        self.assertIsInstance(result, EvaluateResult)
        self.assertEqual(evaluate.call_args.args[0].engine, "problog")
        self.assertIsNone(evaluate.call_args.args[0].semantics_profile)

    def test_single_application_rule_rejects_branch_specific_wrapper_config(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with self.assertRaisesRegex(SDKStoreError, "single application Rule"):
            graph.eval.evaluate(rule, head=rule, config=sdk.ProbLogConfig(case_probabilities={"c0": 0.7}))

    def test_ruleexpr_wrapper_rejects_unknown_branch_ids(self) -> None:
        graph = _store()
        left = _person_exists_rule("left")
        right = _person_region_rule("right")
        expr = left.as_("left") | right.as_("right")

        with self.assertRaisesRegex(SDKStoreError, "unknown branch id 'missing'"):
            graph.eval.evaluate(expr, head=left, config=sdk.ProbLogConfig(case_probabilities={"missing": 0.7}))

    def test_wrapper_rule_params_lower_and_reject_unknown_rule_id(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            first = graph.eval.evaluate(
                rule,
                head=rule,
                config=sdk.ProbLogConfig(rule_params={rule.id: {"label": "primary"}}),
            )
            second = graph.eval.evaluate(rule, head=rule, config=sdk.ProbLogConfig())

        profile = evaluate.call_args_list[0].args[0].semantics_profile
        self.assertEqual(
            profile.rule_projection["sdk_rule_params"],
            [{"target": f"rule:{rule.id}", "kind": "rule_params", "value": {"label": "primary"}}],
        )
        self.assertNotEqual(first.fingerprint.config_digest, second.fingerprint.config_digest)

        with self.assertRaisesRegex(SDKStoreError, "unknown Rule.id 'missing'"):
            graph.eval.evaluate(rule, head=rule, config=sdk.ProbLogConfig(rule_params={"missing": {"label": "bad"}}))

    def test_pyreason_pred_only_path_preflights_and_evaluates_when_supported(self) -> None:
        graph = _store()
        rule = _person_exists_rule()

        with patch("factgraph.sdk.store.evaluate_derivation_plans", return_value=[]) as evaluate:
            result = graph.eval.evaluate(rule, head=rule, engine="pyreason")

        self.assertIsInstance(result, EvaluateResult)
        self.assertEqual(result.count(), 0)
        request = evaluate.call_args.args[0]
        self.assertEqual(request.engine, "pyreason")

    def test_pyreason_ruleexpr_join_rejection_uses_d9_message_fields(self) -> None:
        graph = _store()
        left = _person_region_rule("left_region")
        right = _person_region_rule("right_region")
        expr = (left.as_("left") & right.as_("right")).join_by_ports("person", "region")

        with self.assertRaises(SDKStoreError) as ctx:
            graph.eval.evaluate(expr, head=left, engine="pyreason")

        message = str(ctx.exception)
        self.assertIn("engine='pyreason'", message)
        self.assertIn("unsupported feature 'eq'", message)
        self.assertIn("ruleexpr-join", message)
        self.assertIn("native, souffle, problog", message)

    def test_pyreason_aggregate_rejection_uses_sdk_store_error(self) -> None:
        graph = _store()
        rule = _aggregate_rule()

        with self.assertRaisesRegex(SDKStoreError, "unsupported feature 'aggregate'"):
            graph.eval.evaluate(rule, head=rule, engine="pyreason")

    def test_legacy_inference_evaluation_returns_evaluate_result(self) -> None:
        graph = _store()
        _seed_person(graph, "carol")
        with sdk.vars("p") as (p,):
            inference = sdk.Inference(
                id="legacy_inference",
                version="v1",
                when=[sdk.Pred("Person:exists", p)],
                emits=sdk.EmitSpec("Person:exists", [p]),
            )

        result = graph.eval.evaluate(inference, engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertTrue(result)
        self.assertTrue(all(not isinstance(row, CandidateSet) for row in result))

    def test_structured_derivation_dict_returns_evaluate_result(self) -> None:
        graph = _store()
        _seed_person(graph, "frank")
        with sdk.vars("p") as (p,):
            derivation = sdk.Inference(
                id="dict_inference",
                version="v1",
                when=[sdk.Pred("Person:exists", p)],
                emits=sdk.EmitSpec("Person:exists", [p]),
            ).to_authoring_payload()

        result = graph.eval.evaluate(derivation, engine="native")

        self.assertIsInstance(result, EvaluateResult)
        self.assertTrue(result)
        self.assertEqual(result.head.id, "Person:exists")

    def test_direct_store_style_evaluate_fallback_is_rejected(self) -> None:
        graph = _store()

        with self.assertRaisesRegex(SDKStoreError, "direct Store.evaluate-style calls"):
            graph.eval.evaluate(
                derivation_id="legacy",
                version="v1",
                target_pred_id="Person:exists",
                head_vars=["$person"],
                where=[],
            )


if __name__ == "__main__":
    unittest.main()
