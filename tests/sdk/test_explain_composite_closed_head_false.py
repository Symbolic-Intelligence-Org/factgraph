"""Faithful, full-coverage explanation of a NON-holding multi-occurrence composite.

Regression for the closed_head_false fix (blueprint 2026-06-22): when
``fg.eval.explain(composite, head=closed_head)`` finds no matching row, the
failure branch lowers the FULL expr body (not just the head), seeds it with the
closed head's pins, and routes through the per-engine evidence builders — so the
explanation verdicts every body atom / join, not only the head pins.

Engines: native + problog are exercised end-to-end. souffle is intentionally NOT
exercised on this composite — its witness-building evaluate trips a pre-existing
arity limit (witness arity > 22) for a body this large, independent of this fix
(it constrains HOLDING souffle explain of large composites too); the souffle reach
routing itself is covered by the cross-engine conformance suite on smaller bodies.
"""
from __future__ import annotations

import shutil
import unittest

from factgraph.sdk import Entity, FactGraph, Field, Identity, build_application_rule, vars
from factgraph.core.evidence.write_protocol import set_field
from factgraph.application import build_schema_index, entity_info
from factgraph.application.protocol import Rule
from factgraph.application.explain.evidence_tree import Fails
from factgraph.core.rules.where_ast import Const, PredAtom, Var

_PROBLOG = shutil.which("problog") is not None


class Company(Entity):
    company_id: str = Identity(repr="%ENT id %FLD")

    class Meta:
        repr = "Company %company_id"


class Project(Entity):
    project_id: str = Identity(repr="%ENT id %FLD")
    active: bool = Field(repr="%ENT active %FLD")

    class Meta:
        repr = "Project %project_id"


class User(Entity):
    user_id: str = Identity(repr="%ENT id %FLD")
    company: Company = Field(repr="%ENT works at %FLD")

    class Meta:
        repr = "User %user_id"


class Assignment(Entity):
    assignment_id: str = Identity(repr="%ENT id %FLD")
    user: User = Field(repr="%ENT by %FLD")
    project: Project = Field(repr="%ENT on %FLD")
    workload: int = Field(repr="%ENT workload %FLD h")

    class Meta:
        repr = "Assignment %assignment_id"


def _build_fg(*, carol_project_id: str | None):
    """Alice (30h on P1) and Carol are ACME colleagues.

    ``carol_project_id is None`` -> Carol has NO qualifying assignment
    (in-occurrence failure: works_b fails at its own assignment:user atom).
    ``carol_project_id == "P2"`` -> Carol works a DIFFERENT active project at 30h
    (same-project join failure: every occurrence holds, the cross-occurrence join
    ``works_a.Pa == works_b.Pb`` is the sole culprit).
    """
    fg = FactGraph.create(schema_classes=[Company, Project, User, Assignment])

    def ex(e, t):
        set_field(fg.ledger, f"{t}:exists", e, [], None)

    acme = fg.entities.create(Company, company_id="ACME"); ex(acme, "Company")
    alice = fg.entities.create(User, user_id="Alice"); fg.fields.set(User.company, alice, acme); ex(alice, "User")
    carol = fg.entities.create(User, user_id="Carol"); fg.fields.set(User.company, carol, acme); ex(carol, "User")
    p1 = fg.entities.create(Project, project_id="P1"); fg.fields.set(Project.active, p1, True); ex(p1, "Project")

    rows = [("AP1", alice, p1, 30)]
    if carol_project_id is not None:
        pc = fg.entities.create(Project, project_id=carol_project_id)
        fg.fields.set(Project.active, pc, True); ex(pc, "Project")
        rows.append(("CP", carol, pc, 30))
    for nm, u, prj, wl in rows:
        g = fg.entities.create(Assignment, assignment_id=nm)
        fg.fields.set(Assignment.user, g, u)
        fg.fields.set(Assignment.project, g, prj)
        fg.fields.set(Assignment.workload, g, wl)
        ex(g, "Assignment")
    return fg


def _teammates_composite():
    """teammates = colleagues & works_a & works_b, joined on the colleague ports
    and on a SHARED project (works_a.Pa == works_b.Pb)."""
    with vars("a", "b", "c") as (a, b, c):
        colleagues = build_application_rule(
            id="colleagues",
            when=[User(a), User(b), Company(c), User(a).company == c, User(b).company == c, a != b],
            ports={"A": a, "B": b},
            repr="%A and %B are colleagues",
        )

    def works_for(sf):
        with vars(f"x{sf}", f"p{sf}", f"g{sf}", f"wl{sf}") as (x, p, g, wl):
            return build_application_rule(
                id=f"works_{sf}",
                when=[
                    User(x), Project(p), Assignment(g),
                    Assignment(g).user == x, Assignment(g).project == p,
                    Project(p).active == True, Assignment(g).workload == wl, wl > 20,
                ],
                ports={f"U{sf}": x, f"P{sf}": p},
                repr=f"%U{sf} works on project %P{sf}",
            )

    col = colleagues.as_("col")
    wa = works_for("a").as_("wa")
    wb = works_for("b").as_("wb")
    teammates = (
        (col & wa & wb)
        .join(col.port("A").eq(wa.port("Ua")))
        .join(col.port("B").eq(wb.port("Ub")))
        .join(wa.port("Pa").eq(wb.port("Pb")))
    )
    return teammates


def _build_fg_colleagues_only():
    """Alice and Carol are ACME colleagues; P1 exists active; NEITHER is assigned."""
    fg = FactGraph.create(schema_classes=[Company, Project, User, Assignment])

    def ex(e, t):
        set_field(fg.ledger, f"{t}:exists", e, [], None)

    acme = fg.entities.create(Company, company_id="ACME"); ex(acme, "Company")
    alice = fg.entities.create(User, user_id="Alice"); fg.fields.set(User.company, alice, acme); ex(alice, "User")
    carol = fg.entities.create(User, user_id="Carol"); fg.fields.set(User.company, carol, acme); ex(carol, "User")
    p1 = fg.entities.create(Project, project_id="P1"); fg.fields.set(Project.active, p1, True); ex(p1, "Project")
    return fg


def _or_composite():
    """colleagues & (works_a | works_b), distributed as a 2-branch OR (each branch
    pairs an independent colleagues occurrence with one works occurrence joined on
    its colleague port). For a pair where NEITHER subject has a qualifying
    assignment, BOTH branches fail -> a multi-branch closed_head_false."""

    def works_for(sf):
        with vars(f"x{sf}", f"p{sf}", f"g{sf}", f"wl{sf}") as (x, p, g, wl):
            return build_application_rule(
                id=f"works_{sf}",
                when=[
                    User(x), Project(p), Assignment(g),
                    Assignment(g).user == x, Assignment(g).project == p,
                    Project(p).active == True, Assignment(g).workload == wl, wl > 20,
                ],
                ports={f"U{sf}": x, f"P{sf}": p},
                repr=f"%U{sf} works on project %P{sf}",
            )

    def colleagues_occ(alias):
        with vars(f"a_{alias}", f"b_{alias}", f"c_{alias}") as (a, b, c):
            rule = build_application_rule(
                id="colleagues",
                when=[User(a), User(b), Company(c), User(a).company == c, User(b).company == c, a != b],
                ports={"A": a, "B": b},
                repr="%A and %B are colleagues",
            )
        return rule.as_(alias)

    col1 = colleagues_occ("col1")
    col2 = colleagues_occ("col2")
    wa = works_for("a").as_("wa")
    wb = works_for("b").as_("wb")
    return (
        ((col1 & wa).join(col1.port("A").eq(wa.port("Ua"))))
        | ((col2 & wb).join(col2.port("B").eq(wb.port("Ub"))))
    )


def _closed_head(fg, a_name: str, b_name: str) -> Rule:
    index = build_schema_index(fg.schema_ir)
    uid = entity_info(index, "User").identity_predicates["user_id"].pred_id
    ha, hb = Var("$ha"), Var("$hb")
    return Rule(
        id=f"teammates_{a_name}_{b_name}",
        when=(
            PredAtom("User:exists", [ha]),
            PredAtom("User:exists", [hb]),
            PredAtom(uid, [ha, Const(a_name)]),
            PredAtom(uid, [hb, Const(b_name)]),
        ),
        ports={"A": ha, "B": hb},
    )


def _rule(tree, alias):
    for r in tree.rules:
        if r.occurrence_alias == alias:
            return r
    raise AssertionError(f"no occurrence {alias!r} in tree (have {[r.occurrence_alias for r in tree.rules]})")


class CompositeClosedHeadFalseTests(unittest.TestCase):
    def _explain_tree(self, engine: str, *, carol_project_id: str | None):
        fg = _build_fg(carol_project_id=carol_project_id)
        teammates = _teammates_composite()
        closed = _closed_head(fg, "Alice", "Carol")
        exp = fg.eval.explain(teammates, head=closed, engine=engine)
        self.assertEqual(exp.status, "failed")
        self.assertEqual(exp.failure_class, "closed_head_false")
        self.assertIsNotNone(exp.evidence)
        assert exp.evidence is not None
        self.assertEqual(len(exp.evidence.paths), 1)
        return exp.evidence.paths[0]

    # --- in-occurrence failure: Carol has no qualifying assignment ----------
    def _check_in_occurrence(self, engine: str) -> None:
        tree = self._explain_tree(engine, carol_project_id=None)
        self.assertEqual(tree.status, "fails")
        self.assertEqual(_rule(tree, "col").status, "holds")
        self.assertEqual(_rule(tree, "wa").status, "holds")
        wb = _rule(tree, "wb")
        self.assertEqual(wb.status, "fails")
        culprits = [a for a in wb.atoms if isinstance(a.verdict, Fails)]
        self.assertTrue(culprits, "works_b must carry a failing culprit atom")
        # the culprit is the by-Carol assignment match, not a head-link / wrong entity
        self.assertTrue(
            any("Carol" in (a.repr_text or "") for a in culprits),
            f"culprit should name Carol; got {[a.repr_text for a in culprits]}",
        )

    def test_in_occurrence_failure_native(self) -> None:
        self._check_in_occurrence("native")

    @unittest.skipIf(not _PROBLOG, "problog not installed")
    def test_in_occurrence_failure_problog(self) -> None:
        self._check_in_occurrence("problog")

    # --- same-project join failure: every occurrence holds individually -----
    def _check_same_project(self, engine: str) -> None:
        tree = self._explain_tree(engine, carol_project_id="P2")
        self.assertEqual(tree.status, "fails")
        self.assertEqual(_rule(tree, "col").status, "holds")
        self.assertEqual(_rule(tree, "wa").status, "holds")
        self.assertEqual(_rule(tree, "wb").status, "holds")
        self.assertTrue(
            any(j.status == "fails" for j in tree.joins),
            f"a cross-occurrence join must fail; got {[(j.join_id, j.status) for j in tree.joins]}",
        )

    def test_same_project_join_failure_native(self) -> None:
        self._check_same_project("native")

    @unittest.skipIf(not _PROBLOG, "problog not installed")
    def test_same_project_join_failure_problog(self) -> None:
        self._check_same_project("problog")

    # --- OR composite: every branch is verdicted, all fail ------------------
    def _check_or_multibranch(self, engine: str) -> None:
        fg = _build_fg_colleagues_only()
        or_expr = _or_composite()
        closed = _closed_head(fg, "Alice", "Carol")
        exp = fg.eval.explain(or_expr, head=closed, engine=engine)
        self.assertEqual(exp.status, "failed")
        self.assertEqual(exp.failure_class, "closed_head_false")
        self.assertIsNotNone(exp.evidence)
        assert exp.evidence is not None
        paths = exp.evidence.paths
        self.assertEqual(len(paths), 2, "the 2-branch OR must produce two evidence trees")
        self.assertTrue(all(p.status == "fails" for p in paths), "both OR branches must fail")
        failing = {r.occurrence_alias for p in paths for r in p.rules if r.status == "fails"}
        self.assertEqual(failing, {"wa", "wb"}, "each branch's works occurrence is its culprit")

    def test_or_composite_multibranch_native(self) -> None:
        self._check_or_multibranch("native")

    @unittest.skipIf(not _PROBLOG, "problog not installed")
    def test_or_composite_multibranch_problog(self) -> None:
        self._check_or_multibranch("problog")

    # --- seed-parity: the pin idref equals the EDB idref --------------------
    def test_pin_seed_idref_matches_edb(self) -> None:
        fg = _build_fg(carol_project_id=None)
        closed = _closed_head(fg, "Alice", "Carol")
        pins = fg._pin_bindings_for_closed_head(closed)
        self.assertEqual(str(pins["A"]), str(fg.entities.ref(User, user_id="Alice")))
        self.assertEqual(str(pins["B"]), str(fg.entities.ref(User, user_id="Carol")))


if __name__ == "__main__":
    unittest.main()
