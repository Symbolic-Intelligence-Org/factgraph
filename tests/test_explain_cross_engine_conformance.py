from __future__ import annotations

import re
import shutil
import unittest

import factgraph.sdk as sdk
from factgraph.adapters.souffle.runner import find_souffle_binary
from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.explain.evidence_tree import EvidenceGraph, EvidenceRule, EvidenceTree, LAYOUT_TREE
from factgraph.application.protocol import EntitySelector, Rule
from factgraph.application.protocol.certainty import Certainty
from factgraph.application.protocol.explanation_render import narrate_evidence
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import CmpAtom, Const as WhereConst, PredAtom, Var
from factgraph.core.store.ledger import AnnotationRow
from factgraph.sdk import Entity, Field, Identity


_RUN_RE = re.compile(r"run_v1:[0-9a-f]{8}…")


class CEPerson(Entity):
    class Meta:
        repr = "Person %name"

    name: str = Identity()
    region: str = Field(repr="%ENT has region %FLD")


class CEUser(Entity):
    class Meta:
        repr = "User %user_id"

    user_id: str = Identity()
    country: str = Field(repr="%ENT country %FLD")


class CECountry(Entity):
    class Meta:
        repr = "Country %country_id"

    country_id: str = Identity()
    language: str = Field(repr="%ENT language %FLD")


class CELanguage(Entity):
    class Meta:
        repr = "Language %language_id"

    language_id: str = Identity()
    name: str = Field(repr="%ENT name %FLD")


class CEAnchorUser(Entity):
    class Meta:
        repr = "Citizen %user_id"

    user_id: str = Identity()
    region: str = Field(repr="%ENT region %FLD")
    age: int = Field(repr="%ENT age %FLD")


class CEProbRoute(Entity):
    class Meta:
        repr = "Route %route_id"

    route_id: str = Identity()
    via_a: str = Field(repr="%ENT via A %FLD")
    via_b: str = Field(repr="%ENT via B %FLD")
    via_c: str = Field(repr="%ENT via C %FLD")


def _normalize_narrative(lines: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_RUN_RE.sub("run_v1:<run>…", line) for line in lines)


def _narrative(row: object) -> tuple[str, ...]:
    explanation = row.explain()  # type: ignore[attr-defined]
    lines = explanation.narrate()
    assert lines is not None
    return _normalize_narrative(lines)


def _narratives(rows: object) -> tuple[tuple[str, ...], ...]:
    return tuple(sorted((_narrative(row) for row in rows), key=lambda item: "\n".join(item)))


def _verdict_matrix(row: object) -> tuple[tuple[str, str, str], ...]:
    explanation = row.explain()  # type: ignore[attr-defined]
    evidence = explanation.evidence
    assert evidence is not None
    out: list[tuple[str, str, str]] = []
    for path in evidence.paths:
        for rule in path.rules:
            for atom in rule.atoms:
                verdict = getattr(atom.verdict, "kind", type(atom.verdict).__name__)
                out.append((rule.rule_id, atom.repr_text or "", str(verdict)))
    return tuple(out)


def _verdict_kinds(rows: object) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(item[2] for item in _verdict_matrix(row)) for row in rows)


def _seed_entity(graph: sdk.SDKStore, entity_type: str, identity: dict[str, str]) -> str:
    index = build_schema_index(graph.schema_ir)
    ref = resolve_selector(EntitySelector(entity_type=entity_type, identity=identity), index=index)
    encoded = ref.encoded_ref or ""
    info = entity_info(index, entity_type)
    key, value = next(iter(identity.items()))
    set_field(graph.ledger, info.exists_predicate_id, encoded, [])
    set_field(graph.ledger, info.identity_predicates[key].pred_id, encoded, [("string", value)])
    return encoded


def _set_field(
    graph: sdk.SDKStore,
    entity_type: str,
    field_name: str,
    encoded: str,
    value_tag: str,
    value: object,
    *,
    probability: float | None = None,
) -> str:
    index = build_schema_index(graph.schema_ir)
    pred_id = field_predicate(index, entity_type, field_name).pred_id
    meta = None
    if probability is not None:
        meta = {"raw_kind": "probabilistic", "bound": [probability, probability]}
    asrt_id = set_field(graph.ledger, pred_id, encoded, [(value_tag, value)], meta=meta)
    if probability is not None:
        graph.ledger.append_annotations(
            [
                AnnotationRow(
                    asrt_id=asrt_id,
                    namespace="problog",
                    category="semantic",
                    key="probability",
                    kind="float",
                    value=probability,
                    origin="observed",
                )
            ]
        )
    return asrt_id


def _flat_store() -> sdk.SDKStore:
    graph = sdk.SDKStore([CEPerson])
    encoded = _seed_entity(graph, "CEPerson", {"name": "tri-engine"})
    _set_field(graph, "CEPerson", "region", encoded, "string", "us")
    return graph


def _anchor_store_for_or() -> sdk.SDKStore:
    graph = sdk.SDKStore([CEAnchorUser])
    u1 = _seed_entity(graph, "CEAnchorUser", {"user_id": "u1"})
    _set_field(graph, "CEAnchorUser", "region", u1, "string", "us")
    _set_field(graph, "CEAnchorUser", "age", u1, "int", 30)
    u2 = _seed_entity(graph, "CEAnchorUser", {"user_id": "u2"})
    _set_field(graph, "CEAnchorUser", "region", u2, "string", "eu")
    _set_field(graph, "CEAnchorUser", "age", u2, "int", 70)
    u3 = _seed_entity(graph, "CEAnchorUser", {"user_id": "u3"})
    _set_field(graph, "CEAnchorUser", "region", u3, "string", "eu")
    _set_field(graph, "CEAnchorUser", "age", u3, "int", 20)
    return graph


def _resident_and_senior_rules() -> tuple[Rule, Rule, Rule]:
    user = Var("$user")
    region = Var("$region")
    age = Var("$age")
    resident = Rule(
        id="resident",
        when=(PredAtom("ce_anchor_user:region", [user, region]), CmpAtom("eq", region, WhereConst("us"))),
        ports={"user": user},
        repr="%user is resident",
    )
    senior = Rule(
        id="senior",
        when=(PredAtom("ce_anchor_user:age", [user, age]), CmpAtom("ge", age, WhereConst(65))),
        ports={"user": user},
        repr="%user is senior",
    )
    known = Rule(
        id="known_user",
        when=(PredAtom("ce_anchor_user:age", [user, age]),),
        ports={"user": user},
        repr="%user is known",
    )
    return resident, senior, known


def _flat_rule() -> Rule:
    person = Var("$person")
    region = Var("$region")
    return Rule(
        id="person_region",
        when=(PredAtom("ce_person:region", [person, region]),),
        ports={"person": person, "region": region},
        repr="%person is in %region",
    )


def _chain_store(*, probabilistic: bool = False) -> sdk.SDKStore:
    graph = sdk.SDKStore([CEUser, CECountry, CELanguage])
    user_ref = _seed_entity(graph, "CEUser", {"user_id": "u1"})
    country_ref = _seed_entity(graph, "CECountry", {"country_id": "us"})
    language_ref = _seed_entity(graph, "CELanguage", {"language_id": "en"})
    _set_field(
        graph,
        "CEUser",
        "country",
        user_ref,
        "entity_ref",
        country_ref,
        probability=0.9 if probabilistic else None,
    )
    _set_field(
        graph,
        "CECountry",
        "language",
        country_ref,
        "entity_ref",
        language_ref,
        probability=0.85 if probabilistic else None,
    )
    _set_field(graph, "CELanguage", "name", language_ref, "string", "English")
    return graph


def _chain_rule(rule_id: str = "user_language") -> Rule:
    user = Var("$user")
    country = Var("$country")
    language = Var("$language")
    name = Var("$name")
    return Rule(
        id=rule_id,
        when=(
            PredAtom("ce_user:country", [user, country]),
            PredAtom("ce_country:language", [country, language]),
            PredAtom("ce_language:name", [language, name]),
        ),
        ports={"user": user, "name": name},
        repr="%user speaks %name",
    )


def _probabilistic_or_store(*, via_a: float, via_b: float, include_missing_branch: bool = False) -> sdk.SDKStore:
    graph = sdk.SDKStore([CEProbRoute])
    route_ref = _seed_entity(graph, "CEProbRoute", {"route_id": "r1"})
    _set_field(graph, "CEProbRoute", "via_a", route_ref, "string", "yes", probability=via_a)
    _set_field(graph, "CEProbRoute", "via_b", route_ref, "string", "yes", probability=via_b)
    if not include_missing_branch:
        _set_field(graph, "CEProbRoute", "via_c", route_ref, "string", "yes")
    return graph


def _probabilistic_or_rules() -> tuple[Rule, Rule, Rule]:
    route = Var("$route")
    via_a = Rule(
        id="via_a",
        when=(PredAtom("ce_prob_route:via_a", [route, WhereConst("yes")]),),
        ports={"route": route},
        repr="%route qualifies via A",
    )
    via_b = Rule(
        id="via_b",
        when=(PredAtom("ce_prob_route:via_b", [route, WhereConst("yes")]),),
        ports={"route": route},
        repr="%route qualifies via B",
    )
    via_c = Rule(
        id="via_c",
        when=(PredAtom("ce_prob_route:via_c", [route, WhereConst("yes")]),),
        ports={"route": route},
        repr="%route qualifies via C",
    )
    return via_a, via_b, via_c


class ExplainCrossEngineConformanceTests(unittest.TestCase):
    @unittest.skipIf(shutil.which("problog") is None, "problog CLI is not available")
    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_flat_boolean_narrate_and_verdict_matrix_match_across_engines(self) -> None:
        graph = _flat_store()
        rule = _flat_rule()

        rows = {engine: graph.eval.evaluate(rule, head=rule, engine=engine)[0] for engine in ("native", "problog", "souffle")}

        self.assertEqual(_narrative(rows["problog"]), _narrative(rows["native"]))
        self.assertEqual(_narrative(rows["souffle"]), _narrative(rows["native"]))
        self.assertEqual(_verdict_matrix(rows["problog"]), _verdict_matrix(rows["native"]))
        self.assertEqual(_verdict_matrix(rows["souffle"]), _verdict_matrix(rows["native"]))

    @unittest.skipIf(shutil.which("problog") is None, "problog CLI is not available")
    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_entity_chain_boolean_narrate_and_verdict_matrix_match_across_engines(self) -> None:
        graph = _chain_store()
        rule = _chain_rule()

        rows = {engine: graph.eval.evaluate(rule, head=rule, engine=engine)[0] for engine in ("native", "problog", "souffle")}

        self.assertEqual(_narrative(rows["problog"]), _narrative(rows["native"]))
        self.assertEqual(_narrative(rows["souffle"]), _narrative(rows["native"]))
        self.assertEqual(_verdict_matrix(rows["problog"]), _verdict_matrix(rows["native"]))
        self.assertEqual(_verdict_matrix(rows["souffle"]), _verdict_matrix(rows["native"]))

    def test_native_manual_or_keeps_three_states_and_global_dnf(self) -> None:
        graph = sdk.SDKStore([CEAnchorUser])
        user_ref = _seed_entity(graph, "CEAnchorUser", {"user_id": "u1"})
        _set_field(graph, "CEAnchorUser", "region", user_ref, "string", "us")
        _set_field(graph, "CEAnchorUser", "age", user_ref, "int", 30)
        user = Var("$user")
        region = Var("$region")
        age = Var("$age")
        missing = Var("$missing")
        resident = Rule(
            id="resident",
            when=(PredAtom("ce_anchor_user:region", [user, region]), CmpAtom("eq", region, WhereConst("us"))),
            ports={"user": user},
            repr="%user is resident",
        )
        senior = Rule(
            id="senior",
            when=(
                PredAtom("ce_anchor_user:age", [user, age]),
                CmpAtom("ge", age, WhereConst(65)),
                CmpAtom("eq", missing, WhereConst("ok")),
            ),
            ports={"user": user},
            repr="%user is senior",
        )
        expr = resident.as_("resident") | senior.as_("senior")
        row = graph.eval.evaluate(expr, head=Rule.projection("user"), engine="native")[0]
        lines = _narrative(row)
        text = "\n".join(lines)

        self.assertIn("  Derivation:  projection(user) <= ( resident ) OR ( senior )", lines)
        self.assertIn("✓ Citizen u1 region us", text)
        self.assertIn("✗ 30 >= 65", text)
        self.assertIn("○ <unbound> equals ok", text)

    @unittest.skipIf(shutil.which("problog") is None, "problog CLI is not available")
    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_manual_or_narrate_matches_across_adapters(self) -> None:
        graph = _anchor_store_for_or()
        resident, senior, _known = _resident_and_senior_rules()
        expr = resident.as_("resident") | senior.as_("senior")
        head = Rule.projection("user")

        rows = {engine: graph.eval.evaluate(expr, head=head, engine=engine) for engine in ("native", "problog", "souffle")}

        self.assertEqual([len(value) for value in rows.values()], [2, 2, 2])
        self.assertEqual(_narratives(rows["problog"]), _narratives(rows["souffle"]))
        self.assertEqual(_verdict_kinds(rows["problog"]), _verdict_kinds(rows["native"]))
        self.assertEqual(_verdict_kinds(rows["souffle"]), _verdict_kinds(rows["native"]))

    @unittest.skipIf(shutil.which("problog") is None, "problog CLI is not available")
    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_nested_auto_dnf_or_narrate_matches_across_adapters(self) -> None:
        graph = _anchor_store_for_or()
        resident, senior, known = _resident_and_senior_rules()
        expr = ((resident.as_("resident") | senior.as_("senior")) & known.as_("known")).join_by_ports("user")
        head = Rule.projection("user")

        rows = {engine: graph.eval.evaluate(expr, head=head, engine=engine) for engine in ("native", "problog", "souffle")}

        self.assertEqual([len(value) for value in rows.values()], [2, 2, 2])
        self.assertEqual(_narratives(rows["problog"]), _narratives(rows["souffle"]))
        self.assertEqual(_verdict_kinds(rows["problog"]), _verdict_kinds(rows["native"]))
        self.assertEqual(_verdict_kinds(rows["souffle"]), _verdict_kinds(rows["native"]))

    @unittest.skipIf(shutil.which("problog") is None, "problog CLI is not available")
    def test_problog_entity_chain_probability_formula_and_tail(self) -> None:
        graph = _chain_store(probabilistic=True)
        rule = _chain_rule("prob_user_language")
        row = graph.eval.evaluate(rule, head=rule, engine="problog")[0]
        lines = _narrative(row)
        text = "\n".join(lines)

        self.assertIn("holds with probability 0.765", text)
        self.assertIn("  prob_user_language  [holds]  (p = 0.9 × 0.85 × 1 = 0.765)", lines)
        self.assertIn("✓ User u1 country Country us", text)
        self.assertIn("(p = 0.9)", text)
        self.assertIn("(p = 0.85)", text)

    @unittest.skipIf(shutil.which("problog") is None, "problog CLI is not available")
    def test_problog_probabilistic_or_renders_noisy_or_formula(self) -> None:
        graph = _probabilistic_or_store(via_a=0.7, via_b=0.4)
        via_a, via_b, _via_c = _probabilistic_or_rules()
        row = graph.eval.evaluate(via_a.as_("via_a") | via_b.as_("via_b"), head=Rule.projection("route"), engine="problog")[0]
        lines = _narrative(row)
        text = "\n".join(lines)

        self.assertIn("holds with probability 0.82", text)
        self.assertIn("      probability:  1 − (1−0.7) × (1−0.4) = 0.82", lines)
        self.assertIn("▸ Path c0  [holds] (p = 0.7)", lines)
        self.assertIn("▸ Path c1  [holds] (p = 0.4)", lines)

    @unittest.skipIf(shutil.which("problog") is None, "problog CLI is not available")
    def test_problog_probabilistic_or_skips_failing_branch_in_noisy_or_formula(self) -> None:
        graph = _probabilistic_or_store(via_a=0.8, via_b=0.63, include_missing_branch=True)
        via_a, via_b, via_c = _probabilistic_or_rules()
        row = graph.eval.evaluate(
            (via_a.as_("via_a") | via_b.as_("via_b")) | via_c.as_("via_c"),
            head=Rule.projection("route"),
            engine="problog",
        )[0]
        lines = _narrative(row)
        text = "\n".join(lines)

        self.assertIn("holds with probability 0.926", text)
        self.assertIn("      probability:  1 − (1−0.8) × (1−0.63) = 0.926", lines)
        self.assertIn("▸ Path c0  [holds] (p = 0.8)", lines)
        self.assertIn("▸ Path c1  [holds] (p = 0.63)", lines)
        self.assertIn("▸ Path c2  [fails]", lines)

    def test_synthetic_noisy_or_and_shape_cases(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph",
            engine="problog",
            layout_hint=LAYOUT_TREE,
            subject_binding={},
            paths=(
                EvidenceTree("c0", "holds", (), certainty=Certainty(0.7, 0.7, "probabilistic"), metadata={"branch_probability": 0.7}),
                EvidenceTree("c1", "holds", (), certainty=Certainty(0.4, 0.4, "probabilistic"), metadata={"branch_probability": 0.4}),
            ),
            certainty=Certainty(0.82, 0.82, "probabilistic"),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertIn("      probability:  1 − (1−0.7) × (1−0.4) = 0.82", lines)
        self.assertIn("▸ Path c0  [holds] (p = 0.7)", lines)

    def test_projection_head_label_shape(self) -> None:
        graph = EvidenceGraph(
            graph_id="graph",
            engine="native",
            layout_hint=LAYOUT_TREE,
            subject_binding={"user": "Citizen u1"},
            paths=(
                EvidenceTree(
                    "c0",
                    "holds",
                    (
                        EvidenceRule(
                            "head",
                            "__factgraph_projection__user",
                            "head",
                            "holds",
                            repr_text="projection(user)",
                            ports={"user": "Citizen u1"},
                        ),
                    ),
                ),
            ),
            metadata={"run_id": "run_v1:abcdef123456"},
        )

        lines = narrate_evidence(graph, status="passed")

        self.assertIn("Conclusion ── projection(user)", lines)
        self.assertIn("              [projection(user) · run_v1:<run>… · c0]  holds", _normalize_narrative(lines))


if __name__ == "__main__":
    unittest.main()
