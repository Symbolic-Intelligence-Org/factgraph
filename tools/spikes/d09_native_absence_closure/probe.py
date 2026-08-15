"""Disposable D09 native absence/closure observation probe.

This is deliberately *not* a FactGraph feature or public contract.  It uses
existing native components to record what the evaluator sees for a correlated
negation-as-failure (NAF) body.  Equal bindings across fixture cells do not
mean that their factual, provenance, authorization, or closure states are the
same.

Run directly:

    PYTHONPATH=src python -B tools/spikes/d09_native_absence_closure/probe.py --verify
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from factgraph.application import (
    build_schema_index,
    check_fact_overlay_binding,
    entity_info,
    field_predicate,
    resolve_selector,
)
from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    EntitySelector,
    FactOverlay,
    FactOverlayCheckRequest,
    RemoveFact,
    ReplaceFact,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.ruleref_substrate import evaluate_native_where
from factgraph.core.schema.meta_policy import MetaKeyPolicy
from factgraph.core.store.premise_filter import MetaExclusion
from factgraph.core.store.runtime import Store, premise_scoped_store_view
from factgraph.core.view.projector import project_view_facts
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


_INTERPRETATION_BOUNDARY = (
    "A native relation-empty NAF result is not a public MISSING, MASKED, NEGATED, "
    "UNKNOWN, source-authority, or closed-world conclusion."
)
_EXPECTED_MATRIX = (
    (
        "O1",
        "base relation with one visible age row",
        0,
        None,
        "A positive age row blocks correlated native NAF.",
    ),
    (
        "O2",
        "base relation with no age row",
        1,
        None,
        "An empty age relation leaves the correlated outer binding in native NAF.",
    ),
    (
        "O3",
        "existing FactOverlay RemoveFact for one visible assertion id",
        0,
        1,
        "Removing the sole projected blocker makes the native overlay phase match.",
    ),
    (
        "O4",
        "RemoveFact for one of two visible multi-value rows",
        0,
        0,
        "The remaining projected row still blocks native NAF; RemoveFact is assertion-specific.",
    ),
    (
        "O5",
        "existing premise exclusion hides a positive age assertion from evaluation",
        0,
        1,
        "The filtered evaluator sees no matching age row; this does not decide source authority or factual absence.",
    ),
    (
        "O6",
        "ordinary positive not_age predicate beside a positive age row",
        0,
        1,
        "Predicate spelling does not give not_age a negative-fact meaning in native NAF.",
    ),
    (
        "O7",
        "existing FactOverlay ReplaceFact on one visible age assertion",
        0,
        0,
        "Replacing one positive value retains a positive blocker; replacement is not relation absence.",
    ),
)


class Person(Entity):
    employee_id: str = Identity()
    age: int = Field()
    ages: list[int] = Field()
    not_age: bool = Field()


@dataclass(frozen=True)
class Observation:
    """One current-engine observation, intentionally not a product DTO."""

    cell: str
    mechanism: str
    before_matches: int
    after_matches: int | None
    observation: str


@dataclass(frozen=True)
class SeededPerson:
    e_ref: str
    exists_predicate_id: str
    age_predicate_id: str
    ages_predicate_id: str
    not_age_predicate_id: str


def run_matrix() -> tuple[Observation, ...]:
    """Run Q17 O1--O7 against real current native components."""

    return (
        _o1_present_age_blocks_naf(),
        _o2_empty_relation_allows_naf(),
        _o3_remove_one_visible_assertion(),
        _o4_remove_one_of_two_multi_value_assertions(),
        _o5_premise_filter_hides_a_blocker(),
        _o6_named_negative_predicate_is_ordinary_data(),
        _o7_replace_keeps_a_positive_blocker(),
    )


def verify_matrix() -> tuple[Observation, ...]:
    """Fail if a current-engine observation drifts from the frozen Q17 matrix."""

    observations = run_matrix()
    actual = tuple(
        (
            item.cell,
            item.mechanism,
            item.before_matches,
            item.after_matches,
            item.observation,
        )
        for item in observations
    )
    if actual != _EXPECTED_MATRIX:
        raise AssertionError(
            "D09 native observation matrix drifted; this does not resolve D09: "
            f"expected={_EXPECTED_MATRIX!r}, actual={actual!r}"
        )
    return observations


def observations_as_json() -> str:
    """Return deterministic, non-sensitive reporting output for review."""

    return json.dumps(
        {
            "interpretation_boundary": _INTERPRETATION_BOUNDARY,
            "observations": [asdict(observation) for observation in verify_matrix()],
            "protocol": "Q17 native observation only",
        },
        indent=2,
        sort_keys=True,
    )


def _new_store() -> tuple[Store, Any]:
    schema_ir = compile_schema_from_classes(
        [Person],
        meta_keys={"provenance_class": MetaKeyPolicy(premise_eligible=True)},
    )
    return Store(schema_ir), build_schema_index(schema_ir)


def _seed_person(store: Store, index: Any, *, employee_id: str = "alice") -> SeededPerson:
    selector = resolve_selector(
        EntitySelector(
            entity_type="Person",
            identity={"employee_id": employee_id},
        ),
        index=index,
    )
    e_ref = selector.encoded_ref
    if not isinstance(e_ref, str) or not e_ref:
        raise AssertionError("D09 fixture entity selector did not resolve an encoded ref")
    info = entity_info(index, "Person")
    set_field(store.ledger, info.exists_predicate_id, e_ref, [])
    return SeededPerson(
        e_ref=e_ref,
        exists_predicate_id=info.exists_predicate_id,
        age_predicate_id=field_predicate(index, "Person", "age").pred_id,
        ages_predicate_id=field_predicate(index, "Person", "ages").pred_id,
        not_age_predicate_id=field_predicate(index, "Person", "not_age").pred_id,
    )


def _no_value_where(person: SeededPerson, *, predicate_id: str) -> list[Any]:
    return [
        ("pred", person.exists_predicate_id, ["$person"]),
        ("not", [("pred", predicate_id, ["$person", "$value"])]),
    ]


def _positive_value_where(person: SeededPerson, *, predicate_id: str, value: Any) -> list[Any]:
    return [
        ("pred", person.exists_predicate_id, ["$person"]),
        ("pred", predicate_id, ["$person", value]),
    ]


def _native_matches(store: Store, where: list[Any], *, filtered: bool = False) -> int:
    relation_store = premise_scoped_store_view(store) if filtered else store
    view_facts = project_view_facts(relation_store.ledger, store.schema_ir)
    return len(evaluate_native_where(view_facts, where).bindings)


def _overlay_plan(person: SeededPerson, *, predicate_id: str) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="d09.native_absence_observation",
        version="v1",
        body_ir=_no_value_where(person, predicate_id=predicate_id),
        heads=(
            CompiledHeadCall(
                target_pred_id=person.exists_predicate_id,
                head_var_names=("$person",),
            ),
        ),
    )


def _overlay_match_counts(
    store: Store,
    person: SeededPerson,
    *,
    predicate_id: str,
    actions: tuple[RemoveFact | ReplaceFact, ...],
) -> tuple[int, int]:
    request = FactOverlayCheckRequest(
        plan=_overlay_plan(person, predicate_id=predicate_id),
        binding=(("$person", person.e_ref),),
        overlay=FactOverlay(fact_actions=actions),
        engine="native",
    )
    result = check_fact_overlay_binding(request, store=store)
    if result.errors or result.before is None or result.after is None:
        raise AssertionError(f"D09 fixture overlay unexpectedly failed: {result!r}")
    return result.before.matched_count, result.after.matched_count


def _o1_present_age_blocks_naf() -> Observation:
    store, index = _new_store()
    person = _seed_person(store, index)
    set_field(store.ledger, person.age_predicate_id, person.e_ref, [("int", 35)])
    matches = _native_matches(store, _no_value_where(person, predicate_id=person.age_predicate_id))
    return Observation(
        cell="O1",
        mechanism="base relation with one visible age row",
        before_matches=matches,
        after_matches=None,
        observation="A positive age row blocks correlated native NAF.",
    )


def _o2_empty_relation_allows_naf() -> Observation:
    store, index = _new_store()
    person = _seed_person(store, index)
    matches = _native_matches(store, _no_value_where(person, predicate_id=person.age_predicate_id))
    return Observation(
        cell="O2",
        mechanism="base relation with no age row",
        before_matches=matches,
        after_matches=None,
        observation="An empty age relation leaves the correlated outer binding in native NAF.",
    )


def _o3_remove_one_visible_assertion() -> Observation:
    store, index = _new_store()
    person = _seed_person(store, index)
    assertion_id = set_field(store.ledger, person.age_predicate_id, person.e_ref, [("int", 35)])
    before, after = _overlay_match_counts(
        store,
        person,
        predicate_id=person.age_predicate_id,
        actions=(
            RemoveFact(
                asrt_id=assertion_id,
                pred_id=person.age_predicate_id,
                e_ref=person.e_ref,
                old_fact_tuple=(person.e_ref, 35),
            ),
        ),
    )
    return Observation(
        cell="O3",
        mechanism="existing FactOverlay RemoveFact for one visible assertion id",
        before_matches=before,
        after_matches=after,
        observation="Removing the sole projected blocker makes the native overlay phase match.",
    )


def _o4_remove_one_of_two_multi_value_assertions() -> Observation:
    store, index = _new_store()
    person = _seed_person(store, index)
    first = set_field(store.ledger, person.ages_predicate_id, person.e_ref, [("int", 35)])
    set_field(store.ledger, person.ages_predicate_id, person.e_ref, [("int", 44)])
    before, after = _overlay_match_counts(
        store,
        person,
        predicate_id=person.ages_predicate_id,
        actions=(
            RemoveFact(
                asrt_id=first,
                pred_id=person.ages_predicate_id,
                e_ref=person.e_ref,
                old_fact_tuple=(person.e_ref, 35),
            ),
        ),
    )
    return Observation(
        cell="O4",
        mechanism="RemoveFact for one of two visible multi-value rows",
        before_matches=before,
        after_matches=after,
        observation="The remaining projected row still blocks native NAF; RemoveFact is assertion-specific.",
    )


def _o5_premise_filter_hides_a_blocker() -> Observation:
    store, index = _new_store()
    person = _seed_person(store, index)
    set_field(
        store.ledger,
        person.age_predicate_id,
        person.e_ref,
        [("int", 35)],
        meta={"provenance_class": "claimed_by_agent"},
    )
    where = _no_value_where(person, predicate_id=person.age_predicate_id)
    before = _native_matches(store, where)
    store.set_premise_exclusions(
        MetaExclusion("provenance_class", frozenset({"claimed_by_agent"}))
    )
    after = _native_matches(store, where, filtered=True)
    return Observation(
        cell="O5",
        mechanism="existing premise exclusion hides a positive age assertion from evaluation",
        before_matches=before,
        after_matches=after,
        observation="The filtered evaluator sees no matching age row; this does not decide source authority or factual absence.",
    )


def _o6_named_negative_predicate_is_ordinary_data() -> Observation:
    store, index = _new_store()
    person = _seed_person(store, index)
    set_field(store.ledger, person.age_predicate_id, person.e_ref, [("int", 35)])
    set_field(store.ledger, person.not_age_predicate_id, person.e_ref, [("bool", True)])
    naf_matches = _native_matches(store, _no_value_where(person, predicate_id=person.age_predicate_id))
    positive_matches = _native_matches(
        store,
        _positive_value_where(person, predicate_id=person.not_age_predicate_id, value=True),
    )
    return Observation(
        cell="O6",
        mechanism="ordinary positive not_age predicate beside a positive age row",
        before_matches=naf_matches,
        after_matches=positive_matches,
        observation="Predicate spelling does not give not_age a negative-fact meaning in native NAF.",
    )


def _o7_replace_keeps_a_positive_blocker() -> Observation:
    store, index = _new_store()
    person = _seed_person(store, index)
    assertion_id = set_field(store.ledger, person.age_predicate_id, person.e_ref, [("int", 35)])
    before, after = _overlay_match_counts(
        store,
        person,
        predicate_id=person.age_predicate_id,
        actions=(
            ReplaceFact(
                asrt_id=assertion_id,
                pred_id=person.age_predicate_id,
                e_ref=person.e_ref,
                old_fact_tuple=(person.e_ref, 35),
                new_fact_tuple=(person.e_ref, 22),
            ),
        ),
    )
    return Observation(
        cell="O7",
        mechanism="existing FactOverlay ReplaceFact on one visible age assertion",
        before_matches=before,
        after_matches=after,
        observation="Replacing one positive value retains a positive blocker; replacement is not relation absence.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="fail if the frozen matrix drifts")
    args = parser.parse_args()
    payload = observations_as_json() if args.verify else json.dumps(
        [asdict(observation) for observation in run_matrix()],
        indent=2,
        sort_keys=True,
    )
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
