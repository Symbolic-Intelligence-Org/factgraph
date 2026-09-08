"""Real runtime queries use projected domains, never persisted exists markers."""

from __future__ import annotations

import pytest

from factgraph.core.evidence.write_protocol import retract_by_asrt, set_field
from factgraph.core.store.premise_filter import PredicatePremiseBlock
from factgraph.sdk import Entity, Field, Identity, SDKStore
from tests.test_problog_virtual_domains import _fixture, _inference, _stored_facts


@pytest.mark.parametrize("legacy_marker", [False, True])
def test_real_souffle_domain_query_matches_native_without_ledger_writes(legacy_marker):
    fg, ref, _ = _fixture()
    if legacy_marker:
        set_field(fg.ledger, "DomainPerson:exists", ref, [])
    before = _stored_facts(fg)
    native = fg.eval.evaluate_candidates(_inference(), engine="native")
    actual = fg.eval.evaluate_candidates(_inference(), engine="souffle")
    assert len(native) == len(actual) == 1
    assert actual[0].payload == native[0].payload
    assert before == _stored_facts(fg)


class TypedDomain(Entity):
    key: str = Identity()
    age: int = Field()
    active: bool = Field()


@pytest.mark.parametrize("member,value,encoded", [("age", 22, "22"), ("active", True, "true")])
def test_witness_import_recovers_typed_values_and_rejects_noncanonical_transport(member, value, encoded):
    from factgraph.adapters.souffle.engine_eval import _build_souffle_support_artifact
    from factgraph.core.rules.where_eval import WhereValidationError

    fg = SDKStore([TypedDomain])
    ref = fg.entities.ref(TypedDomain, key="alice")
    assertion = fg.fields.set(getattr(TypedDomain, member), ref, value)
    predicate = "typed_domain:" + member
    where = [("pred", predicate, ["$entity", "$value"])]

    def capture(raw):
        return _build_souffle_support_artifact(
            store=fg.store, where=where,
            binding_items=(("$entity", ref), ("$value", raw)),
            root_result_kind="row", selected_case_index=0,
            witness_ids_by_atom_key={"c0.c0:" + predicate: {assertion}},
        )

    proof = capture(encoded)
    actual = dict(proof.binding_items)["$value"]
    assert type(actual) is type(value) and actual == value
    for invalid in ("0" + encoded, encoded.upper(), "other"):
        if invalid != encoded:
            with pytest.raises(WhereValidationError, match="witness fact binding conflict"):
                capture(invalid)


@pytest.mark.parametrize("absent", ["person_id", "tenant"])
@pytest.mark.parametrize("mode", ["revoked", "hidden"])
def test_real_souffle_legacy_marker_cannot_restore_incomplete_domain(absent, mode):
    fg, ref, _ = _fixture()
    set_field(fg.ledger, "DomainPerson:exists", ref, [])
    predicate = "domain_person:" + absent
    if mode == "revoked":
        for claim in fg.ledger.find_claims(pred_id=predicate):
            retract_by_asrt(fg.ledger, claim.asrt_id)
    else:
        from factgraph.core.store.ledger import MetaRow

        for claim in fg.ledger.find_claims(pred_id=predicate):
            fg.ledger.append_meta([MetaRow(claim.asrt_id, "origin_binding", "str", "hidden")])
        fg.set_premise_blocks([
            PredicatePremiseBlock(
                pred_id=predicate, key="origin_binding", blocked_values=frozenset({"hidden"})
            )
        ])
    before = _stored_facts(fg)
    assert not fg.eval.evaluate_candidates(_inference(), engine="native")
    assert not fg.eval.evaluate_candidates(_inference(), engine="souffle")
    assert before == _stored_facts(fg)
