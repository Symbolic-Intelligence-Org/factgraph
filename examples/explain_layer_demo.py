"""Explain-layer demo — exhaustive per-condition evidence + natural-language repr.

Run:
    PYTHONPATH=src python examples/explain_layer_demo.py

What it shows (v2 explain layer):
- Schema-authored ``repr`` templates render atoms in natural language.
- ``row.explain()`` returns a paths-model ``EvidenceGraph`` (not a flat node/edge DAG).
- The native prober produces a head rule + a body rule with per-atom verdicts
  (Holds / Fails / NotReached) — exhaustively, not just the winning witness.
- ``Explanation.repr`` walks the evidence into an indented "X because ..." tree.

``%ENT`` resolves bound entity refs through visible identity facts, so atoms
render friendly labels such as "User u-1" rather than raw ``idref_v1:...``
tokens. Scalar fields (``%FLD``) and comparisons render fully as well.
"""

from __future__ import annotations

from factgraph.application import build_schema_index, field_predicate
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, Rule, SDKStore


# ---------------------------------------------------------------------------
# 1. Schema with repr templates
# ---------------------------------------------------------------------------
class User(Entity):
    user_id: str = Identity(repr="%ENT has id %FLD")
    region: str = Field(repr="%ENT is in region %FLD")
    age: int = Field(repr="%ENT is %FLD years old")

    class Meta:
        repr = "%CLS %user_id"  # entity label, e.g. "User u-1"


def seed_user(fg: SDKStore, user_id: str, *, region: str, age: int) -> None:
    """Create a User and set its fields via the public SDK API."""
    ref = fg.entities.create(User, user_id=user_id)
    fg.fields.set(User.region, ref, region)
    fg.fields.set(User.age, ref, age)


def adult_in_region_rule(index) -> Rule:
    """Body has three conditions: bound region, bound age, and age >= 18."""
    region_pred = field_predicate(index, "User", "region").pred_id
    age_pred = field_predicate(index, "User", "age").pred_id
    user, region, age = Var("$user"), Var("$region"), Var("$age")
    return Rule(
        id="adult_user",
        when=(
            PredAtom(region_pred, [user, region]),
            PredAtom(age_pred, [user, age]),
            CmpAtom("ge", age, Const(18)),
        ),
        ports={"user": user, "region": region, "age": age},
        repr="%user is an adult user",
    )


def render(explanation) -> None:
    print(f"  status   : {explanation.status}")
    if explanation.evidence is None:
        print("  evidence : None")
        return
    print(f"  paths    : {len(explanation.evidence.paths)} tree(s)")
    print("  rendered :")
    for line in explanation.repr or ():
        print(f"      {line}")


def main() -> None:
    fg = SDKStore([User])
    index = build_schema_index(fg.schema_ir)

    seed_user(fg, "u-1", region="us", age=30)   # adult -> matches
    seed_user(fg, "u-2", region="eu", age=17)   # minor -> filtered out

    rule = adult_in_region_rule(index)
    result = fg.eval.evaluate(rule, head=rule, engine="native")

    print("=" * 66)
    print(f"evaluate(adult_user, engine=native) -> {result.count()} row(s)")
    print("(u-2 is 17, filtered by age >= 18)")
    print("=" * 66)

    for row in result:
        print(f"\nrow {dict(row.bindings)}")
        render(row.explain())

    if result.count():
        ev = result[0].explain().evidence
        assert ev is not None
        tree = ev.paths[0]
        print("\n" + "-" * 66)
        print("raw EvidenceTree (paths-model, first row):")
        print(f"  tree.status = {tree.status!r}")
        for r in tree.rules:
            print(f"  EvidenceRule role={r.role!r} alias={r.occurrence_alias!r} status={r.status!r}")
            for atom in r.atoms:
                v = type(atom.verdict).__name__
                print(f"    EvidenceAtom verdict={v:11s} repr_text={atom.repr_text!r}")


if __name__ == "__main__":
    main()
