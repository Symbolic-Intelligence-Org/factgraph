"""Explain-layer demo — paths-model evidence with per-row anchoring + verdicts.

Run:
    PYTHONPATH=src python examples/explain_layer_demo.py

What it shows (v2 explain layer, post conformance rework):

1. **Per-row anchoring** — in a multi-row result, every row's ``explain()``
   describes *only that row's* entity. No cross-row/entity leakage.
2. **Paths-model evidence** — ``row.explain()`` returns an ``EvidenceGraph`` of
   ``EvidenceTree`` paths (head rule + body rule(s) + per-atom verdicts), not a
   flat node/edge DAG.
3. **Per-atom verdicts** — each condition carries ``Holds`` / ``Fails`` /
   ``NotReached``. After a condition fails inside a branch, later conditions
   are still probed when their inputs are row-anchored; the branch stays failed
   without resurrecting.
4. **Schema-authored repr** — ``%CLS`` / ``%ENT`` / ``%FLD`` render atoms in
   natural language. ``%ENT`` resolves bound entity refs to friendly labels
   ("User u-1") instead of raw ``idref_v1:...`` tokens. Unbound values render as
   ``<unbound>`` rather than internal variable names.
"""

from __future__ import annotations

from factgraph.application import build_schema_index, field_predicate
from factgraph.core.rules.where_ast import CmpAtom, Const, PredAtom, Var
from factgraph.sdk import Entity, Field, Identity, Rule, SDKStore


# ---------------------------------------------------------------------------
# Schema with repr templates
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


def _atom_lines(explanation) -> list[str]:
    """Flatten an explanation into ``<verdict> <repr_text>`` lines per path."""
    lines: list[str] = []
    if explanation.evidence is None:
        return ["  (no evidence)"]
    for path_index, tree in enumerate(explanation.evidence.paths):
        lines.append(f"  path {path_index} [{tree.status}]:")
        for rule in tree.rules:
            for atom in rule.atoms:
                verdict = type(atom.verdict).__name__
                lines.append(f"      {verdict:<10} {atom.repr_text}")
    return lines


def _row_user(row) -> str:
    binding = dict(row.bindings).get("user", {})
    return binding.get("value", "?") if isinstance(binding, dict) else str(binding)


# ---------------------------------------------------------------------------
# Section 1 — per-row anchoring across a multi-row result
# ---------------------------------------------------------------------------
def section_per_row_anchoring() -> None:
    fg = SDKStore([User])
    index = build_schema_index(fg.schema_ir)
    seed_user(fg, "u-1", region="us", age=30)   # adult -> matches
    seed_user(fg, "u-2", region="jp", age=45)   # adult -> matches
    seed_user(fg, "u-3", region="eu", age=16)   # minor -> filtered out

    region_pred = field_predicate(index, "User", "region").pred_id
    age_pred = field_predicate(index, "User", "age").pred_id
    user, region, age = Var("$user"), Var("$region"), Var("$age")
    adult = Rule(
        id="adult_user",
        when=(
            PredAtom(region_pred, [user, region]),
            PredAtom(age_pred, [user, age]),
            CmpAtom("ge", age, Const(18)),
        ),
        ports={"user": user, "region": region, "age": age},
        repr="%user is an adult user",
    )

    result = fg.eval.evaluate(adult, head=adult, engine="native")

    print("=" * 70)
    print("Section 1 — per-row anchoring")
    print(f"evaluate(adult_user, native) -> {result.count()} row(s); u-3 (age 16) filtered")
    print("Each row's explanation is anchored to its own entity only.")
    print("=" * 70)
    for row in result:
        print(f"\nrow user={_row_user(row)[-8:]} (status={row.explain().status})")
        for line in _atom_lines(row.explain()):
            print(line)


# ---------------------------------------------------------------------------
# Section 2 — paths-model OR + per-atom verdicts
# ---------------------------------------------------------------------------
def section_paths_and_verdicts() -> None:
    fg = SDKStore([User])
    index = build_schema_index(fg.schema_ir)
    seed_user(fg, "u-1", region="us", age=30)   # resident yes, senior no

    region_pred = field_predicate(index, "User", "region").pred_id
    age_pred = field_predicate(index, "User", "age").pred_id
    user, region, age = Var("$user"), Var("$region"), Var("$age")

    # resident: region == "us"
    resident = Rule(
        id="resident",
        when=(PredAtom(region_pred, [user, region]), CmpAtom("eq", region, Const("us"))),
        ports={"user": user},
        repr="%user is a US resident",
    )
    # senior: age >= 65 AND region == "us"  (age check fails first for u-1)
    senior = Rule(
        id="senior",
        when=(
            PredAtom(age_pred, [user, age]),
            CmpAtom("ge", age, Const(65)),
            PredAtom(region_pred, [user, region]),
            CmpAtom("eq", region, Const("us")),
        ),
        ports={"user": user},
        repr="%user is a senior US resident",
    )

    # eligible := resident OR senior, projected onto the user port
    result = fg.eval.evaluate(
        resident.as_("res") | senior.as_("sen"),
        head=Rule.projection("user"),
        engine="native",
    )

    print("\n" + "=" * 70)
    print("Section 2 — paths-model OR + per-atom verdicts")
    print("rule: resident (region==us) OR senior (age>=65 AND region==us)")
    print("u-1 is a resident but not a senior; both branches appear with verdicts.")
    print("=" * 70)
    for row in result:
        print(f"\nrow user={_row_user(row)[-8:]} (status={row.explain().status})")
        for line in _atom_lines(row.explain()):
            print(line)
    print(
        "\nNote: in the failing 'senior' path, '30 >= 65' Fails, but the later"
        "\nrow-anchored region checks still report their own verdicts; the path stays failed."
    )


def main() -> None:
    section_per_row_anchoring()
    section_paths_and_verdicts()


if __name__ == "__main__":
    main()
