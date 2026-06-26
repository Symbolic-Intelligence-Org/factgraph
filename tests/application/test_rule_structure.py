from __future__ import annotations

from pathlib import Path
import shutil
import unittest

import factgraph.sdk as sdk
from factgraph.adapters.souffle.runner import find_souffle_binary
from factgraph.application import build_schema_index, entity_info, field_predicate, resolve_selector
from factgraph.application.explain import probe_native
from factgraph.application.protocol import EntitySelector, FreeVar, Rule, RuleStructure
from factgraph.application.protocol.rule_expr_lowering import _lower_rule_expr
from factgraph.application.rule_structure import assemble_static_structure
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.where_ast import Const, CmpAtom, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity


class RSUser(Entity):
    user_id: str = Identity()
    region: str = Field()


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


class RuleStructureBoundaryTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
