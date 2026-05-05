"""End-to-end demo for the shipped v0.1 capability portfolio.

Run from the repository root:

    python examples/11_capabilities_e2e_demo.py

The script is intentionally assertion-bearing. It is both a readable showcase
and a deterministic smoke target for integration drift across:

- Check
- Diagnose
- Fact Overlay Check
- Why-not Universe Diagnose
- Evaluator Frontier Trace
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any


def _ensure_repo_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


_ensure_repo_src_on_path()

from kernel.application import (  # noqa: E402
    build_schema_index,
    check_derivation_binding,
    check_fact_overlay_binding,
    check_why_not_universe,
    diagnose_derivation_binding,
    entity_info,
    field_predicate,
    resolve_selector,
)
from kernel.application.protocol import (  # noqa: E402
    CheckRequest,
    CompiledDerivationPlan,
    CompiledHeadCall,
    DiagnoseRequest,
    EntitySelector,
    FactOverlayCheckRequest,
    FactValueOverride,
    WhyNotUniverseRequest,
)
from kernel.core.evidence.write_protocol import set_field  # noqa: E402
from kernel.core.rules.frontier import evaluate_native_where_frontier  # noqa: E402
from kernel.core.store import Store  # noqa: E402
from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes  # noqa: E402


class Person(Entity):
    name: str = Identity(primary_key=True)
    age: int = Field(cardinality="single")
    region: str = Field(cardinality="single")


@dataclass(frozen=True)
class SeededPerson:
    e_ref: str
    age: int
    region: str
    exists_asrt_id: str
    name_asrt_id: str
    age_asrt_id: str
    region_asrt_id: str
    exists_pred_id: str
    name_pred_id: str
    age_pred_id: str
    region_pred_id: str


@dataclass(frozen=True)
class DemoFixture:
    store: Store
    index: Any
    plan: CompiledDerivationPlan
    people: dict[str, SeededPerson]


def _binding(*items: tuple[str, object]) -> tuple[tuple[str, object], ...]:
    return tuple(sorted(items, key=lambda item: item[0]))


def _announce(verbose: bool, message: str) -> None:
    if verbose:
        print(message)


def _build_store() -> tuple[Store, Any]:
    schema_ir = compile_schema_from_classes([Person])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


def _seed_person(
    store: Store,
    index: Any,
    *,
    name: str,
    age: int,
    region: str,
) -> SeededPerson:
    ref = resolve_selector(
        EntitySelector(entity_type="Person", identity={"name": name}),
        index=index,
    )
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    exists_asrt_id = set_field(store.ledger, info.exists_predicate_id, encoded, [])
    name_pred_id = info.identity_predicates["name"].pred_id
    name_asrt_id = set_field(store.ledger, name_pred_id, encoded, [("string", name)])
    age_pred_id = field_predicate(index, "Person", "age").pred_id
    age_asrt_id = set_field(store.ledger, age_pred_id, encoded, [("int", age)])
    region_pred_id = field_predicate(index, "Person", "region").pred_id
    region_asrt_id = set_field(
        store.ledger,
        region_pred_id,
        encoded,
        [("string", region)],
    )
    return SeededPerson(
        e_ref=encoded,
        age=age,
        region=region,
        exists_asrt_id=exists_asrt_id,
        name_asrt_id=name_asrt_id,
        age_asrt_id=age_asrt_id,
        region_asrt_id=region_asrt_id,
        exists_pred_id=info.exists_predicate_id,
        name_pred_id=name_pred_id,
        age_pred_id=age_pred_id,
        region_pred_id=region_pred_id,
    )


def _build_person_plan(index: Any) -> CompiledDerivationPlan:
    info = entity_info(index, "Person")
    age_pred = field_predicate(index, "Person", "age").pred_id
    region_pred = field_predicate(index, "Person", "region").pred_id
    return CompiledDerivationPlan(
        derivation_id="capabilities-e2e-person-snapshot",
        version="1.0",
        body_ir=[
            ("pred", info.exists_predicate_id, ["$p"]),
            ("pred", age_pred, ["$p", "$age"]),
            ("pred", region_pred, ["$p", "$region"]),
        ],
        heads=(
            CompiledHeadCall(
                target_pred_id=info.exists_predicate_id,
                head_var_names=("$p", "$age", "$region"),
            ),
        ),
    )


def _build_fixture() -> DemoFixture:
    store, index = _build_store()
    people = {
        "alice": _seed_person(store, index, name="alice", age=25, region="us"),
        "bob": _seed_person(store, index, name="bob", age=30, region="eu"),
        "carol": _seed_person(store, index, name="carol", age=28, region="us"),
    }
    return DemoFixture(
        store=store,
        index=index,
        plan=_build_person_plan(index),
        people=people,
    )


def _ledger_dump(store: Store) -> bytes:
    return "\n".join(store.ledger._get_connection().iterdump()).encode("utf-8")


def _phase_check(fixture: DemoFixture, *, verbose: bool) -> str:
    alice = fixture.people["alice"]
    binding = _binding(
        ("$p", alice.e_ref),
        ("$age", 25),
        ("$region", "us"),
    )

    result = check_derivation_binding(
        CheckRequest(plan=fixture.plan, binding=binding, engine="native"),
        store=fixture.store,
    )

    assert result.status == "passed", result
    assert result.matched_count == 1, result
    assert result.matched_binding == binding, result
    _announce(verbose, "Phase 1 - Check: Alice's actual binding passes.")
    return result.status


def _phase_diagnose(fixture: DemoFixture, *, verbose: bool) -> str:
    alice = fixture.people["alice"]
    wrong_age = _binding(
        ("$p", alice.e_ref),
        ("$age", 99),
        ("$region", "us"),
    )

    result = diagnose_derivation_binding(
        DiagnoseRequest(plan=fixture.plan, binding=wrong_age, engine="native"),
        store=fixture.store,
    )

    assert result.status == "failed", result
    assert result.failure_kind == "atom_localized", result
    locator = result.diagnostic_payload
    assert locator is not None, result
    assert locator.branch_index == 0, locator
    assert locator.failed_atom_index == 1, locator
    _announce(verbose, "Phase 2 - Diagnose: Alice age=99 fails at the age atom.")
    return result.failure_kind


def _phase_fact_overlay(fixture: DemoFixture, *, verbose: bool) -> str:
    alice = fixture.people["alice"]
    binding = _binding(
        ("$p", alice.e_ref),
        ("$age", 30),
        ("$region", "us"),
    )
    ledger_before = _ledger_dump(fixture.store)

    result = check_fact_overlay_binding(
        FactOverlayCheckRequest(
            plan=fixture.plan,
            binding=binding,
            overlay=(
                FactValueOverride(
                    asrt_id=alice.age_asrt_id,
                    pred_id=alice.age_pred_id,
                    e_ref=alice.e_ref,
                    old_fact_tuple=(alice.e_ref, 25),
                    new_fact_tuple=(alice.e_ref, 30),
                    note="demo overlay: Alice turns 30",
                ),
            ),
            engine="native",
        ),
        store=fixture.store,
    )

    assert result.status == "passed", result
    assert result.before is not None and result.before.status == "failed", result
    assert result.after is not None and result.after.status == "passed", result
    assert result.diff is not None and result.diff.status_changed, result
    assert _ledger_dump(fixture.store) == ledger_before, "Fact Overlay must not write ledger"
    _announce(verbose, "Phase 3 - Fact Overlay: Alice age override flips failed to passed.")
    return result.status


def _phase_why_not(fixture: DemoFixture, *, verbose: bool) -> str:
    alice = fixture.people["alice"]
    bob = fixture.people["bob"]
    carol = fixture.people["carol"]
    alice_30 = _binding(("$p", alice.e_ref), ("$age", 30), ("$region", "us"))
    bob_30 = _binding(("$p", bob.e_ref), ("$age", 30), ("$region", "eu"))
    carol_30 = _binding(("$p", carol.e_ref), ("$age", 30), ("$region", "us"))

    request = WhyNotUniverseRequest(
        plan=fixture.plan,
        candidate_universe=(alice_30, bob_30, carol_30),
        engine="native",
    )
    result = check_why_not_universe(request, store=fixture.store)

    assert result.status == "completed", result
    assert result.green == (bob_30,), result
    assert tuple(row.binding for row in result.red) == (alice_30, carol_30), result
    for row in result.red:
        assert row.diagnostic.status == "failed", row
        assert row.diagnostic.failure_kind == "atom_localized", row
        assert row.diagnostic.diagnostic_granularity == "atom_localized", row
        locator = row.diagnostic.atom_locator
        assert locator is not None, row
        assert locator.failed_atom_index == 1, locator

    _announce(
        verbose,
        "Phase 4 - Why-not: Bob is green; Alice and Carol are age-localized red rows.",
    )
    return result.status


def _frontier_view_facts(fixture: DemoFixture) -> dict[str, list[tuple[object, ...]]]:
    any_person = next(iter(fixture.people.values()))
    return {
        any_person.exists_pred_id: [(person.e_ref,) for person in fixture.people.values()],
        any_person.age_pred_id: [
            (person.e_ref, person.age) for person in fixture.people.values()
        ],
        any_person.region_pred_id: [
            (person.e_ref, person.region) for person in fixture.people.values()
        ],
    }


def _phase_frontier(fixture: DemoFixture, *, verbose: bool) -> str:
    any_person = next(iter(fixture.people.values()))
    where = [
        ("pred", any_person.exists_pred_id, ["$p"]),
        ("pred", any_person.age_pred_id, ["$p", 99]),
        ("pred", any_person.region_pred_id, ["$p", "us"]),
    ]

    result = evaluate_native_where_frontier(_frontier_view_facts(fixture), where)

    assert result.bindings == [], result
    assert len(result.frontier_rows) == 1, result
    row = result.frontier_rows[0]
    assert row.branch_index == 0, row
    assert row.failed_atom_index == 1, row
    assert row.atoms_satisfied == 1, row
    assert row.frontier_count == 3, row
    assert row.failure_kind == "atom_filter_empty", row
    _announce(verbose, "Phase 5 - Frontier: age=99 collapses after 3 person candidates.")
    return row.failure_kind


def run_demo(*, verbose: bool = True) -> dict[str, str]:
    fixture = _build_fixture()
    if verbose:
        print("FactPy v0.1 capabilities E2E demo")
        print("-----------------------------------")

    outcomes = {
        "check": _phase_check(fixture, verbose=verbose),
        "diagnose": _phase_diagnose(fixture, verbose=verbose),
        "fact_overlay": _phase_fact_overlay(fixture, verbose=verbose),
        "why_not": _phase_why_not(fixture, verbose=verbose),
        "frontier": _phase_frontier(fixture, verbose=verbose),
    }

    if verbose:
        print("-----------------------------------")
        print("All demo assertions passed.")
    return outcomes


if __name__ == "__main__":
    run_demo()
