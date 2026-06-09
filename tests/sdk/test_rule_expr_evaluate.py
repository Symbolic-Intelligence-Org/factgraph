from __future__ import annotations

import unittest
import warnings
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
from factgraph.application.protocol.rule_expr_lowering import _lower_rule_expr
from factgraph.adapters.problog.provenance import parse_problog_trace, problog_trace_to_dict
from factgraph.adapters.pyreason.provenance import (
    PyReasonTraceEventV0,
    PyReasonTraceV0,
    pyreason_trace_to_dict,
)
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import AggregateAtom, CmpAtom, Const, PredAtom, Var
from factgraph.core.rules.where_eval import WhereValidationError
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


def _store() -> sdk.SDKStore:
    return sdk.SDKStore([Person])


def _anchor_store() -> sdk.SDKStore:
    return sdk.SDKStore([ExplainAnchorUser])


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

    def test_souffle_row_explain_uses_support_artifact_paths(self) -> None:
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

        explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        tree = explanation.evidence.paths[0]
        self.assertEqual(tree.metadata["support_kind"], SOUFFLE_WITNESS_KIND)
        self.assertEqual({rule.role for rule in tree.rules}, {"head", "body"})
        body = next(rule for rule in tree.rules if rule.role == "body")
        self.assertTrue(body.atoms)
        self.assertIn("asrt-souffle-person", body.atoms[0].repr_text or "")

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

        with patch("factgraph.sdk.store._souffle_support_artifact_to_evidence_graph", side_effect=ValueError("bad")):
            explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        tree = explanation.evidence.paths[0]
        self.assertEqual(tree.metadata["fallback"], "minimal_row_evidence")
        self.assertEqual([rule.role for rule in tree.rules], ["head"])

    def test_problog_row_explain_uses_provenance_envelope_paths(self) -> None:
        graph = _store()
        encoded = _seed_person(graph, "problog")
        rule = _person_exists_rule()
        trace = parse_problog_trace(
            f"""
 call Person:exists({encoded}) {{0.00010}} []
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
        self.assertEqual({rule.role for rule in tree.rules}, {"head"})
        self.assertTrue(tree.rules[0].atoms)
        self.assertEqual(tree.rules[0].atoms[0].repr_text, f"Person:exists({encoded})")

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

        explanation = result[0].explain()

        self.assertEqual(explanation.status, "passed")
        assert explanation.evidence is not None
        self.assertEqual(explanation.evidence.paths[0].metadata["fallback"], "minimal_row_evidence")

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
