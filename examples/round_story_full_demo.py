"""Canonical full round-story demo for the current v0.2 kernel surface.

Run from the repository root:

    python examples/round_story_full_demo.py

The demo is intentionally deterministic and assertion-bearing. It uses the
default native engine only and demonstrates the current recommended journey:

- SDK-authored schema and data setup.
- Q1-Q5 application capabilities.
- ProofFrame recheck and the three rule overlay operations.
- Durable round events and ProofFrame diff.
- Batch 8 public-boundary note: latest advanced capabilities are importable
  from ``factgraph.application`` / ``factgraph.audit``; SDK shells and service routes
  for Batch 3-7 are intentionally not shipped in v0.2.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


def _ensure_repo_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if src_dir.exists() and str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


_ensure_repo_src_on_path()

from factgraph.application import (  # noqa: E402
    build_fact_value_override,
    build_frontier_view_facts,
    build_schema_index,
    build_why_not_candidate_universe,
    check_derivation_binding,
    check_fact_overlay_binding,
    check_rule_add_condition_action,
    check_rule_disable_action,
    check_rule_literal_replace_action,
    check_why_not_universe,
    diagnose_derivation_binding,
    entity_info,
    field_predicate,
    recheck_proof_frame,
    resolve_selector,
)
from factgraph.application.protocol import (  # noqa: E402
    CheckRequest,
    CompiledDerivationPlan,
    CompiledHeadCall,
    DiagnoseRequest,
    EntitySelector,
    FactOverlay,
    FactOverlayCheckRequest,
    FieldPath,
    ProofFrameRecheckRequest,
    RuleAddConditionAction,
    RuleAddConditionRequest,
    AddedCondition,
    RuleDisableAction,
    RuleDisableRequest,
    ConditionPath,
    RuleLiteralReplaceAction,
    RuleLiteralReplaceRequest,
    WhyNotUniverseRequest,
)
from factgraph.audit import AuditQuery, load_audit_package  # noqa: E402
from factgraph.audit.round_events import (  # noqa: E402
    finalize_round,
    project_check_event_payload,
    project_diagnose_event_payload,
    project_fact_overlay_event_payload,
    project_proof_frame_event_payload,
    project_why_not_event_payload,
    record_round_event,
    start_round,
)
from factgraph.core.evidence.write_protocol import set_field  # noqa: E402
from factgraph.core.rules.frontier import evaluate_native_where_frontier  # noqa: E402
from factgraph.core.rules.rule_ir import RuleSpec  # noqa: E402
from factgraph.core.store import Store  # noqa: E402
from factgraph.core.store._support import NonFactStep, PredWitness, ProofReceipt  # noqa: E402
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes  # noqa: E402


EXPECTED_PHASE_SUMMARY = {
    "check": "passed",
    "diagnose": "atom_localized",
    "fact_overlay": "passed",
    "why_not": "completed",
    "frontier": "atom_filter_empty",
    "proofframe": "invalidated",
    "rule_disable": "completed",
    "rule_literal_replace": "completed",
    "rule_add_condition": "completed",
    "round_diff": "frame_status_changed",
}


class Person(Entity):
    name: str = Identity()
    age: int = Field()
    region: str = Field()


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


@dataclass(frozen=True)
class RuleContext:
    rule_spec: RuleSpec
    support_artifact: ProofReceipt


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
        derivation_id="round-story-person-snapshot",
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
        "dave": _seed_person(store, index, name="dave", age=17, region="us"),
    }
    return DemoFixture(
        store=store,
        index=index,
        plan=_build_person_plan(index),
        people=people,
    )


def _ledger_dump(store: Store) -> bytes:
    return "\n".join(store.ledger._get_connection().iterdump()).encode("utf-8")


def _rule_spec(index: Any) -> RuleSpec:
    info = entity_info(index, "Person")
    age_pred = field_predicate(index, "Person", "age").pred_id
    region_pred = field_predicate(index, "Person", "region").pred_id
    return RuleSpec(
        rule_id="person.eligible",
        version="1.0",
        select_vars=["$p"],
        where=[
            ("pred", info.exists_predicate_id, ["$p"]),
            ("pred", age_pred, ["$p", "$age"]),
            ("pred", region_pred, ["$p", "$region"]),
            ("eq", "$region", "us"),
        ],
    )


def _rule_support_artifact(person: SeededPerson) -> ProofReceipt:
    return ProofReceipt(
        kind="native_binding_v1",
        root_result_kind="row",
        binding_items=(("$p", person.e_ref),),
        pred_witnesses=(
            PredWitness(
                pred_atom_key=f"b0.a0:{person.exists_pred_id}",
                asrt_ids=(person.exists_asrt_id,),
            ),
            PredWitness(
                pred_atom_key=f"b0.a1:{person.age_pred_id}",
                asrt_ids=(person.age_asrt_id,),
            ),
            PredWitness(
                pred_atom_key=f"b0.a2:{person.region_pred_id}",
                asrt_ids=(person.region_asrt_id,),
            ),
        ),
        non_fact_steps=(
            NonFactStep(step_key="b0.a3:eq", kind="eq", status="satisfied"),
        ),
    )


def _phase_check(
    fixture: DemoFixture,
    *,
    verbose: bool,
) -> tuple[CheckRequest, Any, ProofReceipt]:
    alice = fixture.people["alice"]
    request = CheckRequest(
        plan=fixture.plan,
        binding=_binding(("$p", alice.e_ref), ("$age", 25), ("$region", "us")),
        engine="native",
    )
    result = check_derivation_binding(request, store=fixture.store)

    assert result.status == "passed", result
    assert result.matched_count == 1, result
    assert result.matched_binding == request.binding, result
    assert result.evidence_envelope is not None, result
    support = result.evidence_envelope.engine_payload
    assert isinstance(support, ProofReceipt), result.evidence_envelope

    _announce(verbose, "1. SDK setup + Q1 Check")
    _announce(
        verbose,
        "   Schema uses factgraph.sdk Entity/Field/Identity; Check passes for Alice.",
    )
    return request, result, support


def _phase_diagnose(fixture: DemoFixture, *, verbose: bool) -> tuple[DiagnoseRequest, Any]:
    alice = fixture.people["alice"]
    request = DiagnoseRequest(
        plan=fixture.plan,
        binding=_binding(("$p", alice.e_ref), ("$age", 99), ("$region", "us")),
        engine="native",
    )
    result = diagnose_derivation_binding(request, store=fixture.store)

    assert result.status == "failed", result
    assert result.failure_kind == "atom_localized", result
    locator = result.diagnostic_payload
    assert locator is not None, result
    assert locator.branch_index == 0, locator
    assert locator.failed_atom_index == 1, locator

    _announce(verbose, "2. Q2 Diagnose")
    _announce(verbose, "   Alice age=99 fails at the age atom.")
    return request, result


def _phase_fact_overlay(
    fixture: DemoFixture,
    *,
    verbose: bool,
) -> tuple[FactOverlayCheckRequest, Any, FactOverlay]:
    alice = fixture.people["alice"]
    overlay = FactOverlay(
        fact_actions=(
            build_fact_value_override(
                fixture.store,
                fixture.index,
                e_ref=alice.e_ref,
                field=FieldPath(entity_type="Person", field_name="age"),
                new_value=30,
                note="demo overlay: Alice turns 30",
            ),
        ),
    )
    request = FactOverlayCheckRequest(
        plan=fixture.plan,
        binding=_binding(("$p", alice.e_ref), ("$age", 30), ("$region", "us")),
        overlay=overlay,
        engine="native",
    )
    ledger_before = _ledger_dump(fixture.store)
    result = check_fact_overlay_binding(request, store=fixture.store)

    assert result.status == "passed", result
    assert result.before is not None and result.before.status == "failed", result
    assert result.after is not None and result.after.status == "passed", result
    assert result.diff is not None and result.diff.status_changed, result
    assert _ledger_dump(fixture.store) == ledger_before, "Fact Overlay must not write ledger"

    _announce(verbose, "3. Q3 Fact Overlay Check")
    _announce(verbose, "   A hypothetical Alice age override flips failed to passed.")
    return request, result, overlay


def _phase_why_not(
    fixture: DemoFixture,
    *,
    verbose: bool,
) -> tuple[WhyNotUniverseRequest, Any]:
    alice = fixture.people["alice"]
    bob = fixture.people["bob"]
    carol = fixture.people["carol"]
    request = WhyNotUniverseRequest(
        plan=fixture.plan,
        candidate_universe=build_why_not_candidate_universe(
            fixture.plan,
            (
                {"$p": alice.e_ref, "$age": 30, "$region": "us"},
                {"$p": bob.e_ref, "$age": 30, "$region": "eu"},
                {"$p": carol.e_ref, "$age": 30, "$region": "us"},
            ),
        ),
        engine="native",
    )
    result = check_why_not_universe(request, store=fixture.store)

    assert result.status == "completed", result
    assert result.green == (_binding(("$p", bob.e_ref), ("$age", 30), ("$region", "eu")),)
    assert len(result.red) == 2, result
    for row in result.red:
        assert row.diagnostic.status == "failed", row
        assert row.diagnostic.failure_kind == "atom_localized", row
        assert row.diagnostic.diagnostic_granularity == "atom_localized", row
        locator = row.diagnostic.atom_locator
        assert locator is not None, row
        assert locator.failed_atom_index == 1, locator

    _announce(verbose, "4. Q4 Why-not Universe Diagnose")
    _announce(verbose, "   Bob is green; Alice and Carol are localized red rows.")
    return request, result


def _phase_frontier(fixture: DemoFixture, *, verbose: bool) -> str:
    any_person = next(iter(fixture.people.values()))
    where = [
        ("pred", any_person.exists_pred_id, ["$p"]),
        ("pred", any_person.age_pred_id, ["$p", 99]),
        ("pred", any_person.region_pred_id, ["$p", "us"]),
    ]
    result = evaluate_native_where_frontier(build_frontier_view_facts(fixture.store), where)

    assert result.bindings == [], result
    assert len(result.frontier_rows) == 1, result
    row = result.frontier_rows[0]
    assert row.branch_index == 0, row
    assert row.failed_atom_index == 1, row
    assert row.failure_kind == "atom_filter_empty", row

    _announce(verbose, "5. Q5 Evaluator Frontier Trace")
    _announce(verbose, "   age=99 collapses the native where-body at atom 1.")
    return row.failure_kind


def _phase_proofframe(
    fixture: DemoFixture,
    support: ProofReceipt,
    overlay: FactOverlay,
    *,
    verbose: bool,
) -> tuple[ProofFrameRecheckRequest, Any, ProofFrameRecheckRequest, Any]:
    baseline_request = ProofFrameRecheckRequest(
        support_artifact=support,
        overlay=FactOverlay(),
    )
    baseline = recheck_proof_frame(baseline_request, store=fixture.store)
    overlay_request = ProofFrameRecheckRequest(support_artifact=support, overlay=overlay)
    result = recheck_proof_frame(overlay_request, store=fixture.store)

    assert baseline.status == "still_valid", baseline
    assert result.status == "invalidated", result
    assert any(verdict.verdict == "invalidated" for verdict in result.atom_verdicts), result

    _announce(verbose, "6. ProofFrame Rechecker")
    _announce(verbose, "   The fact overlay invalidates Alice's original age witness.")
    return baseline_request, baseline, overlay_request, result


def _phase_rule_disable(
    fixture: DemoFixture,
    context: RuleContext,
    *,
    verbose: bool,
) -> Any:
    action = RuleDisableAction(
        rule_id="person.eligible",
        version="1.0",
        branch_index=0,
        atom_index=3,
    )
    result = check_rule_disable_action(
        RuleDisableRequest(
            rule_spec=context.rule_spec,
            support_artifact=context.support_artifact,
            overlay=FactOverlay(rule_actions=(action,)),
        ),
        store=fixture.store,
    )

    assert result.status == "completed", result
    assert result.variant_rows, result
    assert result.proof_frame is not None and result.proof_frame.status == "invalidated"

    _announce(verbose, "7. Rule Disable")
    _announce(verbose, "   Disabling the region equality widens the native variant rows.")
    return result


def _phase_rule_literal_replace(
    fixture: DemoFixture,
    context: RuleContext,
    *,
    verbose: bool,
) -> Any:
    action = RuleLiteralReplaceAction(
        rule_id="person.eligible",
        version="1.0",
        branch_index=0,
        atom_index=3,
        literal_path=ConditionPath(kind="rhs"),
        old_literal="us",
        new_literal="eu",
    )
    result = check_rule_literal_replace_action(
        RuleLiteralReplaceRequest(
            rule_spec=context.rule_spec,
            support_artifact=context.support_artifact,
            overlay=FactOverlay(rule_actions=(action,)),
        ),
        store=fixture.store,
    )

    assert result.status == "completed", result
    assert result.variant_rows == ((("$p", fixture.people["bob"].e_ref),),), result
    assert result.proof_frame is not None and result.proof_frame.status == "invalidated"

    _announce(verbose, "8. Rule Literal Replace")
    _announce(verbose, "   Replacing region='us' with 'eu' moves the variant row to Bob.")
    return result


def _phase_rule_add_condition(
    fixture: DemoFixture,
    context: RuleContext,
    *,
    verbose: bool,
) -> Any:
    action = RuleAddConditionAction(
        rule_id="person.eligible",
        version="1.0",
        branch_index=0,
        added_atom=AddedCondition(("lt", "$age", 20)),
    )
    result = check_rule_add_condition_action(
        RuleAddConditionRequest(
            rule_spec=context.rule_spec,
            support_artifact=context.support_artifact,
            overlay=FactOverlay(rule_actions=(action,)),
        ),
        store=fixture.store,
    )

    assert result.status == "completed", result
    assert result.variant_rows == ((("$p", fixture.people["dave"].e_ref),),), result
    assert result.proof_frame is not None and result.proof_frame.status == "invalidated"

    _announce(verbose, "9. Rule Add Condition")
    _announce(verbose, "   Adding age < 20 narrows the variant row to Dave.")
    return result


def _phase_round_persistence_and_diff(
    *,
    check_request: CheckRequest,
    check_result: Any,
    diagnose_request: DiagnoseRequest,
    diagnose_result: Any,
    fact_overlay_request: FactOverlayCheckRequest,
    fact_overlay_result: Any,
    why_not_request: WhyNotUniverseRequest,
    why_not_result: Any,
    baseline_pf_request: ProofFrameRecheckRequest,
    baseline_pf_result: Any,
    overlay_pf_request: ProofFrameRecheckRequest,
    overlay_pf_result: Any,
    verbose: bool,
) -> str:
    with TemporaryDirectory() as tmpdir:
        package_dir = _minimal_audit_package(Path(tmpdir) / "audit_pkg")

        baseline = start_round("round-baseline", event_ts=100)
        for offset, (kind, payload) in enumerate(
            (
                ("check_result", project_check_event_payload(check_request, check_result)),
                (
                    "diagnose_result",
                    project_diagnose_event_payload(diagnose_request, diagnose_result),
                ),
                (
                    "fact_overlay_result",
                    project_fact_overlay_event_payload(
                        fact_overlay_request,
                        fact_overlay_result,
                    ),
                ),
                ("why_not_result", project_why_not_event_payload(why_not_request, why_not_result)),
                (
                    "proof_frame_result",
                    project_proof_frame_event_payload(
                        baseline_pf_request,
                        baseline_pf_result,
                    ),
                ),
            ),
            start=1,
        ):
            record_round_event(baseline, kind=kind, payload=payload, event_ts=100 + offset)
        finalize_round(baseline, package_dir, event_ts=200)

        overlay = start_round("round-overlay", event_ts=300)
        record_round_event(
            overlay,
            kind="proof_frame_result",
            payload=project_proof_frame_event_payload(overlay_pf_request, overlay_pf_result),
            event_ts=301,
        )
        finalize_round(overlay, package_dir, event_ts=302)

        package = load_audit_package(package_dir)
        query = AuditQuery(package)
        assert set(query.list_rounds()) == {"round-baseline", "round-overlay"}
        diff = query.diff_proof_frames("round-baseline", "round-overlay")

    assert len(diff.frame_deltas) == 1, diff
    delta = diff.frame_deltas[0]
    assert delta.frame_status_change is not None, delta
    assert delta.frame_status_change.before == "still_valid", delta
    assert delta.frame_status_change.after == "invalidated", delta

    _announce(verbose, "10. Round Persistence + Evidence Diff")
    _announce(
        verbose,
        "    The finalized rounds persist proof_frame_result rows and diff to a status change.",
    )
    return "frame_status_changed"


def _minimal_audit_package(package_dir: Path) -> Path:
    audit_dir = package_dir / "audit"
    audit_dir.mkdir(parents=True)
    audit_files = {
        "run_ledger": "audit/run_ledger.jsonl",
        "candidate_ledger": "audit/candidate_ledger.jsonl",
        "accept_write_ledger": "audit/accept_write_ledger.jsonl",
        "accept_failed": "audit/accept_failed.jsonl",
        "mapping_resolution": "audit/mapping_resolution.json",
        "decision_log": "audit/decision_log.jsonl",
    }
    for key, rel_path in audit_files.items():
        path = package_dir / rel_path
        if key == "mapping_resolution":
            path.write_text("{}", encoding="utf-8")
        else:
            path.write_text("", encoding="utf-8")
    manifest = {"package_kind": "audit", "paths": {"audit_files": audit_files}}
    (package_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True),
        encoding="utf-8",
    )
    return package_dir


def run_demo(*, verbose: bool = True) -> dict[str, str]:
    fixture = _build_fixture()
    alice = fixture.people["alice"]
    rule_context = RuleContext(
        rule_spec=_rule_spec(fixture.index),
        support_artifact=_rule_support_artifact(alice),
    )

    if verbose:
        print("FactGraph full round-story demo")
        print("============================")
        print(
            "Product setup uses factgraph.sdk for schema authoring; advanced current "
            "capabilities are imported from factgraph.application and factgraph.audit."
        )

    check_request, check_result, support = _phase_check(fixture, verbose=verbose)
    diagnose_request, diagnose_result = _phase_diagnose(fixture, verbose=verbose)
    fact_overlay_request, fact_overlay_result, fact_overlay = _phase_fact_overlay(
        fixture,
        verbose=verbose,
    )
    why_not_request, why_not_result = _phase_why_not(fixture, verbose=verbose)
    frontier_status = _phase_frontier(fixture, verbose=verbose)
    (
        baseline_pf_request,
        baseline_pf_result,
        overlay_pf_request,
        overlay_pf_result,
    ) = _phase_proofframe(fixture, support, fact_overlay, verbose=verbose)
    rule_disable = _phase_rule_disable(fixture, rule_context, verbose=verbose)
    rule_literal_replace = _phase_rule_literal_replace(
        fixture,
        rule_context,
        verbose=verbose,
    )
    rule_add_condition = _phase_rule_add_condition(fixture, rule_context, verbose=verbose)
    round_diff = _phase_round_persistence_and_diff(
        check_request=check_request,
        check_result=check_result,
        diagnose_request=diagnose_request,
        diagnose_result=diagnose_result,
        fact_overlay_request=fact_overlay_request,
        fact_overlay_result=fact_overlay_result,
        why_not_request=why_not_request,
        why_not_result=why_not_result,
        baseline_pf_request=baseline_pf_request,
        baseline_pf_result=baseline_pf_result,
        overlay_pf_request=overlay_pf_request,
        overlay_pf_result=overlay_pf_result,
        verbose=verbose,
    )

    outcomes = {
        "check": check_result.status,
        "diagnose": diagnose_result.failure_kind or "",
        "fact_overlay": fact_overlay_result.status,
        "why_not": why_not_result.status,
        "frontier": frontier_status,
        "proofframe": overlay_pf_result.status,
        "rule_disable": rule_disable.status,
        "rule_literal_replace": rule_literal_replace.status,
        "rule_add_condition": rule_add_condition.status,
        "round_diff": round_diff,
    }
    assert outcomes == EXPECTED_PHASE_SUMMARY, outcomes

    if verbose:
        print("11. Public boundary")
        print(
            "    v0.2 intentionally ships no SDK shells or service routes for "
            "Batch 3-7 capabilities; use factgraph.application/factgraph.audit for "
            "advanced workflows."
        )
        print("============================")
        print(json.dumps(outcomes, indent=2, sort_keys=True))
    return outcomes


def main() -> None:
    run_demo(verbose=True)


if __name__ == "__main__":
    main()
