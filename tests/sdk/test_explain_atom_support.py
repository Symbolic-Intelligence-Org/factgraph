"""`Holds.support` is populated for holding Fact atoms in the modern explains.

The reach-chain (souffle/problog via diagnostic_assemble) and native (prober)
explain paths attach a provenance `Source` to each holding PRED (Fact) atom — the
matched EDB fact behind the verdict. Compare / builtin atoms have no backing fact,
so their support stays empty. (The legacy provenance adapters already populated
support; this locks the modern paths.)
"""
from __future__ import annotations

import shutil
import unittest

from factgraph.sdk import Entity, FactGraph, Field, Identity, build_application_rule, vars
from factgraph.core.evidence.write_protocol import set_field
from factgraph.application.explain.evidence_tree import Fact, Fails, Holds, Source

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

    class Meta:
        repr = "User %user_id"


class Assignment(Entity):
    assignment_id: str = Identity(repr="%ENT id %FLD")
    user: User = Field(repr="%ENT by %FLD")
    project: Project = Field(repr="%ENT on %FLD")
    workload: int = Field(repr="%ENT workload %FLD h")

    class Meta:
        repr = "Assignment %assignment_id"


def _fg(*, active: bool = True):
    fg = FactGraph.create(schema_classes=[Company, Project, User, Assignment])

    def ex(e, t):
        set_field(fg.ledger, f"{t}:exists", e, [], None)

    alice = fg.entities.create(User, user_id="Alice"); ex(alice, "User")
    p1 = fg.entities.create(Project, project_id="P1"); fg.fields.set(Project.active, p1, active); ex(p1, "Project")
    ap1 = fg.entities.create(Assignment, assignment_id="AP1")
    fg.fields.set(Assignment.user, ap1, alice)
    fg.fields.set(Assignment.project, ap1, p1)
    fg.fields.set(Assignment.workload, ap1, 30)
    ex(ap1, "Assignment")
    return fg


def _works_rule():
    with vars("x", "p", "g", "wl") as (x, p, g, wl):
        return build_application_rule(
            id="works_on_project",
            when=[
                User(x), Project(p), Assignment(g),
                Assignment(g).user == x, Assignment(g).project == p,
                Project(p).active == True, Assignment(g).workload == wl, wl > 20,
            ],
            ports={"X": x, "P": p},
            repr="%X works on project %P",
        )


class HoldsSupportTests(unittest.TestCase):
    def _check(self, **engine_kwargs) -> None:
        fg = _fg()
        rule = _works_rule()
        row = fg.eval.evaluate(rule, head=rule, **engine_kwargs).first()
        self.assertIsNotNone(row)
        assert row is not None
        graph = row.explain().evidence
        self.assertIsNotNone(graph)
        assert graph is not None
        fact_atoms = 0
        for tree in graph.paths:
            for r in tree.rules:
                for atom in r.atoms:
                    if isinstance(atom.verdict, Holds) and isinstance(atom.form, Fact):
                        fact_atoms += 1
                        self.assertEqual(
                            len(atom.verdict.support), 1,
                            f"holding Fact atom {atom.repr_text!r} must carry one Source",
                        )
                        src = atom.verdict.support[0]
                        self.assertIsInstance(src, Source)
                        self.assertEqual(src.meta.get("predicate"), atom.form.predicate)
                    else:
                        # compare / builtin (or any non-holding verdict): no backing fact
                        self.assertEqual(getattr(atom.verdict, "support", ()), ())
        self.assertGreaterEqual(fact_atoms, 5, "expected several holding Fact atoms")

    def test_native_holds_support(self) -> None:
        self._check(engine="native")

    @unittest.skipIf(not _PROBLOG, "problog not installed")
    def test_problog_holds_support(self) -> None:
        from factgraph.sdk import ProbLogConfig

        self._check(config=ProbLogConfig(
            name="support-test",
            uncertainty_projection={
                "probabilistic": {"policy": "identity_probability"},
                "possibilistic": {"policy": "reject"},
                "fallback": "use_default",
            },
        ))


def _works_check(user_id: str):
    """A CLOSED works_on_project head pinned to one user + project P1."""
    with vars("x", "p", "g", "wl") as (x, p, g, wl):
        return build_application_rule(
            id=f"works_check_{user_id}",
            when=[
                User(x), User(x).user_id == user_id,
                Project(p), Project(p).project_id == "P1",
                Assignment(g), Assignment(g).user == x, Assignment(g).project == p,
                Project(p).active == True, Assignment(g).workload == wl, wl > 20,
            ],
            ports={"X": x, "P": p},
            repr="%X works on project %P",
        )


class FailsSupportTests(unittest.TestCase):
    """A failing Fact atom carries the refuting EDB fact (same owner, other value)."""

    def _check(self, **engine_kwargs) -> None:
        fg = _fg(active=False)  # P1 inactive -> works(Alice) fails at project:active
        head = _works_check("Alice")
        exp = fg.eval.explain(head, head=head, **engine_kwargs)
        self.assertEqual(exp.status, "failed")
        assert exp.evidence is not None
        refuting_atoms = 0
        for tree in exp.evidence.paths:
            for r in tree.rules:
                for atom in r.atoms:
                    if isinstance(atom.verdict, Fails) and "active" in (atom.repr_text or ""):
                        refuting_atoms += 1
                        self.assertTrue(
                            atom.verdict.support,
                            f"failing {atom.repr_text!r} must carry the refuting fact",
                        )
                        src = atom.verdict.support[0]
                        self.assertIsInstance(src, Source)
                        self.assertEqual(src.meta.get("role"), "refuting")
                        self.assertEqual(src.meta.get("predicate"), atom.form.predicate)
        self.assertGreaterEqual(refuting_atoms, 1, "expected the failing project:active atom")

    def test_native_fails_refuting(self) -> None:
        self._check(engine="native")

    @unittest.skipIf(not _PROBLOG, "problog not installed")
    def test_problog_fails_refuting(self) -> None:
        from factgraph.sdk import ProbLogConfig

        self._check(config=ProbLogConfig(
            name="support-fail-test",
            uncertainty_projection={
                "probabilistic": {"policy": "identity_probability"},
                "possibilistic": {"policy": "reject"},
                "fallback": "use_default",
            },
        ))


if __name__ == "__main__":
    unittest.main()
