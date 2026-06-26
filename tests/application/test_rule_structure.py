from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
import shutil
import subprocess
import unittest

import factgraph.sdk as sdk
from factgraph.adapters.souffle.runner import find_souffle_binary
from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.explain import probe_native
from factgraph.application.protocol import Const as StructureConst
from factgraph.application.protocol import EntitySelector, FreeVar, HeadClosure, Rule, RuleStructure
from factgraph.application.protocol.rule_structure import Aggregate
from factgraph.application.protocol.rule_expr_lowering import _lower_rule_expr
from factgraph.application.rule_structure import assemble_static_structure
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import AggregateAtom, Const, CmpAtom, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity


class RSUser(Entity):
    user_id: str = Identity()
    region: str = Field()


class RSOrder(Entity):
    order_id: str = Identity()
    amount: int = Field()


_SINGLE_JOIN_NARRATE = (
    "Structure ── eligible_region",
    "  Derivation:  eligible_region <= ( left_region AND right_region )",
    "               join:  left_region.region = right_region.region",
    "               join:  left_region.user = right_region.user",
    '  eligible_region [head] ── "eligible_region"',
    "       %region equals us  [c0:atom:2]",
    '  left_region ── "left_region"',
    "       RSUser %user has region %region  [c0:atom:0]",
    '  right_region ── "right_region"',
    "       RSUser %user has region %region  [c0:atom:1]",
)

_OR_JOIN_NARRATE = (
    "Structure ── eligible_region",
    "  Derivation:  eligible_region <= ( left_region AND right_region ) OR ( vip_region )",
    "▸ Path c0",
    "               join:  left_region.region = right_region.region",
    "               join:  left_region.user = right_region.user",
    '  eligible_region [head] ── "eligible_region"',
    "       %region equals us  [c0:atom:2]",
    '  left_region ── "left_region"',
    "       RSUser %user has region %region  [c0:atom:0]",
    '  right_region ── "right_region"',
    "       RSUser %user has region %region  [c0:atom:1]",
    "▸ Path c1",
    '  eligible_region [head] ── "eligible_region"',
    "       %region equals us  [c1:atom:2]",
    '  vip_region ── "vip_region"',
    "       RSUser %user has region %region  [c1:atom:0]",
    "       %region equals eu  [c1:atom:1]",
)

_AGGREGATE_NARRATE = (
    "Structure ── order_count",
    '  order_count ── "order_count"',
    "       %total equals count(...)  [c0:atom:0]",
)


def _ids_from_structure(structure: RuleStructure) -> dict[str, set[str]]:
    return {
        "branch_id": {branch.branch_id for branch in structure.branches},
        "occurrence_alias": {
            occurrence.occurrence_alias
            for branch in structure.branches
            for occurrence in branch.occurrences
        },
        "atom_id": {
            atom.atom_id
            for branch in structure.branches
            for occurrence in branch.occurrences
            for atom in occurrence.atoms
        },
        "join_id": {join.join_id for branch in structure.branches for join in branch.joins},
    }


def _ids_from_evidence(evidence: object) -> dict[str, set[str]]:
    paths = getattr(evidence, "paths")
    return {
        "branch_id": {path.tree_id for path in paths},
        "occurrence_alias": {
            rule.occurrence_alias
            for path in paths
            for rule in path.rules
        },
        "atom_id": {
            atom.atom_id
            for path in paths
            for rule in path.rules
            for atom in rule.atoms
        },
        "join_id": {join.join_id for path in paths for join in path.joins},
    }


class RuleStructureTests(unittest.TestCase):
    def test_static_structure_keys_match_native_explain_for_or_join_rule(self) -> None:
        left_person = Var("$left_person")
        left_region = Var("$left_region")
        right_person = Var("$right_person")
        right_region = Var("$right_region")
        vip_person = Var("$vip_person")
        vip_region = Var("$vip_region")
        head_region = Var("$head_region")

        left = Rule(
            id="left_region",
            when=(PredAtom("Person:region", [left_person, left_region]),),
            ports={"person": left_person, "region": left_region},
        )
        right = Rule(
            id="right_region",
            when=(PredAtom("Person:region", [right_person, right_region]),),
            ports={"person": right_person, "region": right_region},
        )
        vip = Rule(
            id="vip_region",
            when=(
                PredAtom("Person:region", [vip_person, vip_region]),
                CmpAtom("eq", vip_region, Const("EU")),
            ),
            ports={"person": vip_person, "region": vip_region},
        )
        head = Rule(
            id="eligible_pair",
            when=(CmpAtom("eq", head_region, Const("US")),),
            ports={"region": head_region},
        )
        left_occurrence = left.as_("left")
        right_occurrence = right.as_("right")
        joined = (left_occurrence & right_occurrence).join(
            left_occurrence.region.eq(right_occurrence.region),
            left_occurrence.person.eq(right_occurrence.person),
        )
        expr = joined | vip.as_("vip")
        plan = _lower_rule_expr(expr, head=head)

        structure = assemble_static_structure(plan, rule_expr=expr)
        evidence = probe_native(
            plan,
            {},
            {"Person:region": [("alice", "US"), ("bob", "US"), ("carol", "EU")]},
            rules_by_id={rule.id: rule for rule in (left, right, vip, head)},
        )

        self.assertIsNone(structure.head_closure)
        self.assertEqual(_ids_from_structure(structure), _ids_from_evidence(evidence))
        first_free_var = next(
            term
            for branch in structure.branches
            for occurrence in branch.occurrences
            for atom in occurrence.atoms
            for term in getattr(atom.form, "terms", getattr(atom.form, "operands", ()))
            if isinstance(term, FreeVar)
        )
        self.assertTrue(first_free_var.name.startswith("$"))
        self.assertIsNotNone(first_free_var.port_name)

    def test_sdk_structure_matches_authored_inspect_floor_for_application_rule(self) -> None:
        fg = sdk.SDKStore([RSUser])
        index = build_schema_index(fg.schema_ir)
        user = Var("$user")
        region = Var("$region")
        rule = Rule(
            id="active_user",
            when=(
                PredAtom(entity_info(index, "RSUser").exists_predicate_id, [user]),
                PredAtom(field_predicate(index, "RSUser", "region").pred_id, [user, region]),
                CmpAtom("eq", region, Const("us")),
            ),
            ports={"user": user, "region": region},
            repr="User %user in %region",
        )

        structure = fg.rules.structure(rule)
        inspected = fg.rules.inspect(rule)
        bindings = {"user": "alice", "region": "us"}

        self.assertEqual(structure.ast, inspected.ast)
        self.assertEqual(structure.render(bindings), inspected.render(bindings))
        self.assertEqual(structure.render_compact(), inspected.render_compact())
        self.assertEqual(
            [(occ.rule_id, occ.occurrence_alias, occ.repr_text, occ.port_names) for occ in structure.occurrences],
            [(occ.template_id, occ.alias, occ.repr_template, occ.ports) for occ in inspected.occurrences],
        )
        self.assertEqual(structure.joins, inspected.joins)
        self.assertEqual(
            [(port.name, port.kind, port.entity_type) for port in structure.ports],
            [(port.name, port.kind, port.entity_type) for port in inspected.ports],
        )
        self.assertEqual(structure.templates, inspected.templates)
        self.assertEqual(dict(structure.port_visibility), dict(inspected.port_visibility))
        self.assertEqual(structure.is_closed, inspected.is_closed)
        self.assertEqual(structure.unbound_ports, inspected.unbound_ports)

    def test_sdk_structure_matches_authored_inspect_ast_and_render_for_ruleexpr(self) -> None:
        fg = sdk.SDKStore([RSUser])
        index = build_schema_index(fg.schema_ir)
        region_pred = field_predicate(index, "RSUser", "region").pred_id
        left_user = Var("$left_user")
        left_region = Var("$left_region")
        right_user = Var("$right_user")
        right_region = Var("$right_region")
        left = Rule(
            id="left_region",
            when=(PredAtom(region_pred, [left_user, left_region]),),
            ports={"user": left_user, "region": left_region},
            repr="Left %user in %region",
        )
        right = Rule(
            id="right_region",
            when=(PredAtom(region_pred, [right_user, right_region]),),
            ports={"user": right_user, "region": right_region},
            repr="Right %user in %region",
        )
        left_occurrence = left.as_("left")
        right_occurrence = right.as_("right")
        expr = (left_occurrence & right_occurrence).join(
            left_occurrence.region.eq(right_occurrence.region),
            left_occurrence.user.eq(right_occurrence.user),
        )
        head_region = Var("$head_region")
        head = Rule(
            id="matching_region",
            when=(CmpAtom("eq", head_region, Const("us")),),
            ports={"region": head_region},
        )

        structure = fg.rules.structure(expr, head=head)
        inspected = fg.rules.inspect(expr)
        bindings = {
            "left.user": "alice",
            "left.region": "us",
            "right.user": "bob",
            "right.region": "us",
        }

        self.assertEqual(structure.ast, inspected.ast)
        self.assertEqual(structure.render(bindings), inspected.render(bindings))
        self.assertEqual(structure.render_compact(), inspected.render_compact())
        self.assertEqual([occ.repr_text for occ in structure.occurrences], ["Left %user in %region", "Right %user in %region"])
        body_repr = {
            occurrence.occurrence_alias: occurrence.repr_text
            for branch in structure.branches
            for occurrence in branch.occurrences
            if occurrence.role == "body"
        }
        self.assertEqual(body_repr, {"left": "Left %user in %region", "right": "Right %user in %region"})

    @unittest.skipIf(shutil.which("problog") is None, "problog CLI is not available")
    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_static_structure_keys_match_explain_evidence_across_tree_engines(self) -> None:
        fg, expr, head = _sdk_or_join_fixture()
        structure = fg.rules.structure(expr, head=head)
        structure_ids = _ids_from_structure(structure)

        for engine in ("native", "problog", "souffle"):
            with self.subTest(engine=engine):
                explanation = fg.eval.explain(expr, head=head, engine=engine)
                self.assertIsNotNone(explanation.evidence)
                self.assertEqual(structure_ids, _ids_from_evidence(explanation.evidence))

    def test_structure_narrate_matches_normalized_explain_for_single_join_rule(self) -> None:
        fg, expr, head = _sdk_single_join_fixture()
        structure = fg.rules.structure(expr, head=head)
        explanation = fg.eval.explain(expr, head=head, engine="native")

        structure_lines = structure.narrate()

        self.assertEqual(structure_lines, _SINGLE_JOIN_NARRATE)
        self.assertEqual(_non_atom_lines(structure_lines), _normalized_explain_non_atom_narrate(explanation.narrate()))
        _assert_structure_narrate_is_runtime_free(self, structure_lines, explanation)

    def test_structure_narrate_matches_normalized_explain_for_or_rule(self) -> None:
        fg, expr, head = _sdk_or_join_fixture()
        structure = fg.rules.structure(expr, head=head)
        explanation = fg.eval.explain(expr, head=head, engine="native")

        structure_lines = structure.narrate()

        self.assertEqual(structure_lines, _OR_JOIN_NARRATE)
        self.assertEqual(_non_atom_lines(structure_lines), _normalized_explain_non_atom_narrate(explanation.narrate()))
        _assert_structure_narrate_is_runtime_free(self, structure_lines, explanation)

    def test_structure_narrate_golden_rejects_injected_runtime_atom_text(self) -> None:
        fg, expr, head = _sdk_single_join_fixture()
        structure = fg.rules.structure(expr, head=head)

        mutated = _replace_atom_repr_text(structure, "c0:atom:0", "RSUser dave has region jp")

        self.assertNotEqual(mutated.narrate(), _SINGLE_JOIN_NARRATE)
        self.assertIn("RSUser dave has region jp", "\n".join(mutated.narrate()))

    def test_structure_narrate_body_repr_label_mirrors_explain_rule_id(self) -> None:
        fg, expr, head = _sdk_body_repr_join_fixture()
        structure = fg.rules.structure(expr, head=head)
        explanation = fg.eval.explain(expr, head=head, engine="native")

        structure_lines = structure.narrate()

        self.assertEqual(structure_lines, _SINGLE_JOIN_NARRATE)
        self.assertEqual(_non_atom_lines(structure_lines), _normalized_explain_non_atom_narrate(explanation.narrate()))
        self.assertNotIn('Member %user in %region', "\n".join(structure_lines))
        self.assertNotIn('Peer %user in %region', "\n".join(structure_lines))

    def test_structure_narrate_aggregate_atom_uses_bare_aggregate_form(self) -> None:
        fg, rule = _sdk_aggregate_count_fixture()
        structure = fg.rules.structure(rule)
        result = fg.eval.evaluate(rule, head=rule, engine="native")
        explanation = result.rows[0].explain()

        structure_lines = structure.narrate()
        aggregate_atom = next(
            atom
            for branch in structure.branches
            for occurrence in branch.occurrences
            for atom in occurrence.atoms
            if atom.atom_id == "c0:atom:0"
        )

        self.assertEqual(structure_lines, _AGGREGATE_NARRATE)
        self.assertIsInstance(aggregate_atom.form.right, Aggregate)
        self.assertNotIn("('count'", "\n".join(structure_lines))
        self.assertEqual(_non_atom_lines(structure_lines), _normalized_explain_non_atom_narrate(explanation.narrate()))
        _assert_structure_narrate_is_runtime_free(self, structure_lines, explanation)

    def test_structure_render_returns_empty_string_without_authored_ast(self) -> None:
        fg, expr, head = _sdk_single_join_fixture()
        plan = _lower_rule_expr(expr, head=head)
        structure = assemble_static_structure(plan, schema_index=build_schema_index(fg.schema_ir))

        self.assertEqual(structure.ast, ())
        self.assertEqual(structure.render(), "")
        self.assertEqual(structure.render_compact(), "")

    def test_sdk_exports_structure_leaf_types(self) -> None:
        self.assertIs(sdk.FreeVar, FreeVar)
        self.assertIs(sdk.HeadClosure, HeadClosure)
        self.assertIs(sdk.Const, StructureConst)


class RuleStructureBoundaryTests(unittest.TestCase):
    def test_evidence_and_explanation_render_sources_have_no_worktree_diff(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [
                "git",
                "diff",
                "--",
                "src/factgraph/application/explain/evidence_tree.py",
                "src/factgraph/application/protocol/explanation_render.py",
            ],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout, "")

    def test_core_and_derivation_chain_do_not_accept_rule_structure_or_evidence_graph(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        paths = [
            repo / "src/factgraph/core",
            repo / "src/factgraph/application/derivation_runtime.py",
            repo / "src/factgraph/application/derivation_check_runtime.py",
            repo / "src/factgraph/application/protocol/derivation.py",
        ]
        hits: list[str] = []
        for path in paths:
            files = path.rglob("*.py") if path.is_dir() else (path,)
            for file_path in files:
                text = file_path.read_text(encoding="utf-8")
                for line_no, line in enumerate(text.splitlines(), start=1):
                    if "RuleStructure" in line or "EvidenceGraph" in line:
                        hits.append(f"{file_path.relative_to(repo)}:{line_no}:{line.strip()}")
        self.assertEqual(hits, [])


def _sdk_single_join_fixture() -> tuple[sdk.SDKStore, object, Rule]:
    fg = sdk.SDKStore([RSUser])
    index = build_schema_index(fg.schema_ir)
    info = entity_info(index, "RSUser")
    region_pred = field_predicate(index, "RSUser", "region").pred_id

    def seed(user_id: str, region: str) -> None:
        ref = resolve_selector(EntitySelector(entity_type="RSUser", identity={"user_id": user_id}), index=index)
        encoded = ref.encoded_ref or ""
        set_field(fg.ledger, info.exists_predicate_id, encoded, [])
        set_field(fg.ledger, info.identity_predicates["user_id"].pred_id, encoded, [("string", user_id)])
        set_field(fg.ledger, region_pred, encoded, [("string", region)])

    seed("alice", "us")
    seed("bob", "eu")

    left_user = Var("$left_user")
    left_region = Var("$left_region")
    right_user = Var("$right_user")
    right_region = Var("$right_region")
    head_region = Var("$head_region")
    left = Rule(
        id="left_region",
        when=(PredAtom(region_pred, [left_user, left_region]),),
        ports={"user": left_user, "region": left_region},
    )
    right = Rule(
        id="right_region",
        when=(PredAtom(region_pred, [right_user, right_region]),),
        ports={"user": right_user, "region": right_region},
    )
    head = Rule(
        id="eligible_region",
        when=(CmpAtom("eq", head_region, Const("us")),),
        ports={"region": head_region},
    )
    left_occurrence = left.as_("left")
    right_occurrence = right.as_("right")
    expr = (left_occurrence & right_occurrence).join(
        left_occurrence.region.eq(right_occurrence.region),
        left_occurrence.user.eq(right_occurrence.user),
    )
    return fg, expr, head


def _sdk_or_join_fixture() -> tuple[sdk.SDKStore, object, Rule]:
    fg = sdk.SDKStore([RSUser])
    index = build_schema_index(fg.schema_ir)
    info = entity_info(index, "RSUser")
    region_pred = field_predicate(index, "RSUser", "region").pred_id

    def seed(user_id: str, region: str) -> None:
        ref = resolve_selector(EntitySelector(entity_type="RSUser", identity={"user_id": user_id}), index=index)
        encoded = ref.encoded_ref or ""
        set_field(fg.ledger, info.exists_predicate_id, encoded, [])
        set_field(fg.ledger, info.identity_predicates["user_id"].pred_id, encoded, [("string", user_id)])
        set_field(fg.ledger, region_pred, encoded, [("string", region)])

    seed("alice", "us")
    seed("bob", "us")
    seed("carol", "eu")

    left_user = Var("$left_user")
    left_region = Var("$left_region")
    right_user = Var("$right_user")
    right_region = Var("$right_region")
    vip_user = Var("$vip_user")
    vip_region = Var("$vip_region")
    head_region = Var("$head_region")
    left = Rule(
        id="left_region",
        when=(PredAtom(region_pred, [left_user, left_region]),),
        ports={"user": left_user, "region": left_region},
    )
    right = Rule(
        id="right_region",
        when=(PredAtom(region_pred, [right_user, right_region]),),
        ports={"user": right_user, "region": right_region},
    )
    vip = Rule(
        id="vip_region",
        when=(PredAtom(region_pred, [vip_user, vip_region]), CmpAtom("eq", vip_region, Const("eu"))),
        ports={"user": vip_user, "region": vip_region},
    )
    head = Rule(
        id="eligible_region",
        when=(CmpAtom("eq", head_region, Const("us")),),
        ports={"region": head_region},
    )
    left_occurrence = left.as_("left")
    right_occurrence = right.as_("right")
    joined = (left_occurrence & right_occurrence).join(
        left_occurrence.region.eq(right_occurrence.region),
        left_occurrence.user.eq(right_occurrence.user),
    )
    return fg, joined | vip.as_("vip"), head


def _sdk_body_repr_join_fixture() -> tuple[sdk.SDKStore, object, Rule]:
    fg, _expr, _head = _sdk_single_join_fixture()
    index = build_schema_index(fg.schema_ir)
    region_pred = field_predicate(index, "RSUser", "region").pred_id
    left_user = Var("$left_user")
    left_region = Var("$left_region")
    right_user = Var("$right_user")
    right_region = Var("$right_region")
    head_region = Var("$head_region")
    left = Rule(
        id="left_region",
        when=(PredAtom(region_pred, [left_user, left_region]),),
        ports={"user": left_user, "region": left_region},
        repr="Member %user in %region",
    )
    right = Rule(
        id="right_region",
        when=(PredAtom(region_pred, [right_user, right_region]),),
        ports={"user": right_user, "region": right_region},
        repr="Peer %user in %region",
    )
    head = Rule(
        id="eligible_region",
        when=(CmpAtom("eq", head_region, Const("us")),),
        ports={"region": head_region},
    )
    left_occurrence = left.as_("left")
    right_occurrence = right.as_("right")
    expr = (left_occurrence & right_occurrence).join(
        left_occurrence.region.eq(right_occurrence.region),
        left_occurrence.user.eq(right_occurrence.user),
    )
    return fg, expr, head


def _sdk_aggregate_count_fixture() -> tuple[sdk.SDKStore, Rule]:
    fg = sdk.SDKStore([RSOrder])
    index = build_schema_index(fg.schema_ir)
    info = entity_info(index, "RSOrder")
    amount_pred = field_predicate(index, "RSOrder", "amount").pred_id

    def seed(order_id: str, amount: int) -> None:
        ref = resolve_selector(EntitySelector(entity_type="RSOrder", identity={"order_id": order_id}), index=index)
        encoded = ref.encoded_ref or ""
        set_field(fg.ledger, info.exists_predicate_id, encoded, [])
        set_field(fg.ledger, info.identity_predicates["order_id"].pred_id, encoded, [("string", order_id)])
        set_field(fg.ledger, amount_pred, encoded, [("int", amount)])

    seed("o1", 10)
    seed("o2", 20)

    order = Var("$order")
    amount = Var("$amount")
    total = Var("$total")
    aggregate = AggregateAtom("count", None, [PredAtom(amount_pred, [order, amount])])
    rule = Rule(id="order_count", when=(CmpAtom("eq", total, aggregate),), ports={"total": total})
    return fg, rule


def _normalized_explain_non_atom_narrate(lines: tuple[str, ...]) -> tuple[str, ...]:
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") or stripped.startswith("produces:") or stripped.startswith("probability:"):
            continue
        if _is_narrate_atom_line(line):
            continue
        if line.startswith(("Conclusion", "NOT concluded")):
            line = re.sub(r"^(Conclusion|NOT concluded)", "Structure", line)
            line = re.sub(r" \([^)]*\)$", "", line)
        line = re.sub(r"^(▸ Path \S+).*$", r"\1", line)
        line = re.sub(r"\s+\[p=[^\]]+\]", "", line)
        line = re.sub(r"  \[(holds|fails|not_reached)\](?:\s+\(p = [^)]+\))?$", "", line)
        out.append(line)
    return tuple(out)


def _non_atom_lines(lines: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(line for line in lines if not _is_structure_atom_line(line))


def _is_narrate_atom_line(line: str) -> bool:
    return re.match(r"^\s*[✓○✗]\s+.*?  \[[^\]]+\]\s+(holds|fails|not_reached).*$", line) is not None


def _is_structure_atom_line(line: str) -> bool:
    return re.match(r"^\s{7}.+  \[[^\]]+\]$", line) is not None


def _replace_atom_repr_text(structure: RuleStructure, atom_id: str, repr_text: str) -> RuleStructure:
    branches = []
    for branch in structure.branches:
        occurrences = []
        for occurrence in branch.occurrences:
            atoms = tuple(
                replace(atom, repr_text=repr_text) if atom.atom_id == atom_id else atom
                for atom in occurrence.atoms
            )
            occurrences.append(replace(occurrence, atoms=atoms))
        branches.append(replace(branch, occurrences=tuple(occurrences)))
    return replace(structure, branches=tuple(branches))


def _assert_structure_narrate_is_runtime_free(
    testcase: unittest.TestCase,
    lines: tuple[str, ...],
    explanation: object | None = None,
) -> None:
    text = "\n".join(lines)
    for token in ("[holds]", "[fails]", "[not_reached]", "[p=", "produces:", "Conclusion", "NOT concluded"):
        testcase.assertNotIn(token, text)
    testcase.assertNotRegex(text, r"(^|\s)[✓○✗]\s")
    for executed_value in _runtime_tokens_from_explanation(explanation, structure_text=text):
        testcase.assertNotIn(executed_value, text)


def _runtime_tokens_from_explanation(explanation: object | None, *, structure_text: str) -> tuple[str, ...]:
    evidence = getattr(explanation, "evidence", None)
    if evidence is None:
        return ()
    structure_tokens = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]*", structure_text))
    out: list[str] = []
    for path in getattr(evidence, "paths", ()):
        for rule in getattr(path, "rules", ()):
            for atom in getattr(rule, "atoms", ()):
                repr_text = getattr(atom, "repr_text", None)
                if not isinstance(repr_text, str):
                    continue
                for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", repr_text):
                    if token in structure_tokens or token in out:
                        continue
                    out.append(token)
    return tuple(out)


if __name__ == "__main__":
    unittest.main()
