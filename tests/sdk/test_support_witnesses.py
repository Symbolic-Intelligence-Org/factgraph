"""The public support read distinguishes evidence kind from material availability."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from factgraph.core.store._support import (
    compute_support_digest,
    support_artifact_bytes,
    support_artifact_from_dict,
    support_artifact_to_dict,
)
from factgraph.sdk import (
    Entity,
    FactGraph,
    Field,
    Identity,
    SupportWitnessError,
    build_application_rule,
    vars,
)


class Person(Entity):
    name: str = Identity()
    active: bool = Field()


def captured():
    fg = FactGraph.create(schema_classes=[Person])
    person = fg.entities.create(Person, name="Alice")
    fg.fields.set(Person.active, person, True)
    with vars("p") as (p,):
        rule = build_application_rule(
            id="witness_person_active",
            when=[Person(p), Person(p).active == True],
            ports={"P": p},
        )
    candidates = fg.eval.evaluate_candidates(rule, head=rule, engine="native")
    assert len(candidates) == 1
    return fg, candidates[0].support_digest


def test_public_report_preserves_original_mixed_witnesses():
    fg, digest = captured()
    report = fg.audit.support_witnesses(digest)
    assert report.status == "available"
    assert report.capture_version == 1
    assert report.support_digest == digest
    assert {item.kind for item in report.items} == {"assertion", "virtual"}
    tree = fg.store.explain_support(digest)
    assert {(item.condition_key, item.witness_ref) for item in report.items} == {
        (row["pred_condition_key"], ref)
        for row in tree["pred_witnesses"] for ref in row["asrt_ids"]
    }
    for item in report.items:
        assert item.availability == "available"
        assert item.reason is None
        assert item.predicate_id
        assert item.terms
        assert (fg.assertions.by_id(item.witness_ref) is not None) == (item.kind == "assertion")
    assert fg.audit.support_witnesses(digest) == report
    assert report.report_digest.startswith("sha256:")


def test_missing_support_is_explicit_and_invalid_digest_is_rejected():
    fg = FactGraph.create(schema_classes=[Person])
    report = fg.audit.support_witnesses("sha256:" + "0" * 64)
    assert report.status == "support_missing"
    assert report.items == ()
    with pytest.raises(ValueError):
        fg.audit.support_witnesses("not-a-support-digest")


@pytest.mark.parametrize("defect", ["missing", "predicate", "typed_value"])
def test_missing_or_mismatched_real_material_never_becomes_virtual(monkeypatch, defect):
    fg, digest = captured()
    before = fg.audit.support_witnesses(digest)
    real = next(item for item in before.items if item.kind == "assertion")
    original = fg.ledger.get_claim

    def changed(ref):
        claim = original(ref)
        if ref != real.witness_ref:
            return claim
        if defect == "missing":
            return None
        if defect == "predicate":
            return replace(claim, pred_id="other:active")
        # Claim argument rows remain bool; alter captured expectation to int below.
        return claim

    if defect == "typed_value":
        artifact = fg.store._lookup_support_artifact(digest)
        rows = tuple(replace(row, witnesses=tuple(
            replace(item, terms=(item.terms[0], 1)) if item.kind == "assertion" else item
            for item in row.witnesses
        )) for row in artifact.pred_witnesses)
        artifact = replace(artifact, pred_witnesses=rows)
        digest = compute_support_digest(artifact)
        fg.store._remember_support_artifact(digest, artifact)
    monkeypatch.setattr(fg.ledger, "get_claim", changed)
    after = fg.audit.support_witnesses(digest)
    item = next(item for item in after.items if item.witness_ref == real.witness_ref)
    assert item.kind == "assertion"
    assert item.availability == "unavailable"
    assert item.reason == ("assertion_missing" if defect == "missing" else "assertion_mismatch")
    assert all(item.availability == "available" for item in after.items if item.kind == "virtual")
    assert after.report_digest != before.report_digest


def test_old_capture_bytes_are_preserved_and_never_backfilled(monkeypatch):
    fg, digest = captured()
    old = support_artifact_to_dict(fg.store._lookup_support_artifact(digest))
    del old["witness_capture_version"]
    for row in old["pred_witnesses"]:
        del row["witnesses"]
    payload = json.dumps(old, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    artifact = support_artifact_from_dict(old)
    assert support_artifact_bytes(artifact) == payload
    old_digest = compute_support_digest(artifact)
    assert old_digest != digest
    fg.store._remember_support_artifact(old_digest, artifact)
    monkeypatch.setattr(fg.ledger, "get_claim", lambda _: pytest.fail("old capture must not be reclassified"))
    report = fg.audit.support_witnesses(old_digest)
    assert report.status == "not_captured"
    assert report.capture_version is None
    assert report.items
    assert {(item.kind, item.availability, item.reason) for item in report.items} == {
        ("unknown", "unavailable", "not_captured")
    }
    assert support_artifact_bytes(fg.store._lookup_support_artifact(old_digest)) == payload


def test_unknown_capture_origin_is_not_inferred_from_ref():
    fg, digest = captured()
    artifact = fg.store._lookup_support_artifact(digest)
    rows = tuple(replace(row, witnesses=tuple(replace(item, kind="unknown") for item in row.witnesses))
                 for row in artifact.pred_witnesses)
    artifact = replace(artifact, pred_witnesses=rows)
    digest = compute_support_digest(artifact)
    fg.store._remember_support_artifact(digest, artifact)
    report = fg.audit.support_witnesses(digest)
    assert all(item.reason == "unsupported_witness_kind" for item in report.items)
    assert all(item.kind == "unknown" for item in report.items)


@pytest.mark.parametrize("defect", ["version", "bool_version", "coverage", "extra_field", "digest"])
def test_corrupt_capture_fails_closed(monkeypatch, defect):
    fg, digest = captured()
    artifact = fg.store._lookup_support_artifact(digest)
    row = support_artifact_to_dict(artifact)
    if defect == "version":
        row["witness_capture_version"] = 2
    elif defect == "bool_version":
        row["witness_capture_version"] = True
    elif defect == "coverage":
        row["pred_witnesses"][0]["witnesses"] = []
    elif defect == "extra_field":
        row["pred_witnesses"][0]["witnesses"][0]["extra"] = "not allowed"
    else:
        row["binding"].append(["zz", "tampered"])

    def load(_digest):
        return support_artifact_from_dict(row)

    monkeypatch.setattr(fg.store, "_lookup_support_artifact", load)
    with pytest.raises(SupportWitnessError) as error:
        fg.audit.support_witnesses(digest)
    assert error.value.code == ("support_digest_mismatch" if defect == "digest" else "invalid_support_capture")


def test_cold_sidecar_reload_is_read_only_and_has_same_report(tmp_path, monkeypatch):
    from factgraph.core.store._artifact_sidecar import FileArtifactSidecar

    fg, digest = captured()
    expected = fg.audit.support_witnesses(digest)
    sidecar = FileArtifactSidecar(tmp_path)
    sidecar.write_support(digest, fg.store._lookup_support_artifact(digest))
    before = {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    fg.store._artifact_sidecar = sidecar
    fg.store._support_artifacts.clear()
    monkeypatch.setattr(sidecar, "write_support", lambda *_: pytest.fail("read wrote sidecar"))
    monkeypatch.setattr(fg.store, "_remember_support_artifact", lambda *_: pytest.fail("read captured support"))
    assert fg.audit.support_witnesses(digest) == expected
    assert fg.audit.support_witnesses(digest).report_digest == expected.report_digest
    assert {str(path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


def test_souffle_receipt_adaptation_retains_origin_metadata():
    from factgraph.adapters.souffle.engine_eval import _build_souffle_support_artifact

    fg, digest = captured()
    original = fg.store._lookup_support_artifact(digest)
    selected = original.pred_witnesses
    # Use the selected captured terms to exercise adapter reconstruction, not
    # an external executable or a mock classified public response.
    where = [("pred", row.witnesses[0].predicate_id, list(row.witnesses[0].terms)) for row in selected]
    from factgraph.core.store._support import make_pred_condition_key
    artifact = _build_souffle_support_artifact(
        store=fg.store, where=where, binding_items=(), root_result_kind="fact", selected_case_index=0,
        witness_ids_by_atom_key={make_pred_condition_key(0, i, atom[1]): set(row.asrt_ids)
                                 for i, (atom, row) in enumerate(zip(where, selected))},
    )
    assert artifact.witness_capture_version == 1
    assert {item.kind for row in artifact.pred_witnesses for item in row.witnesses} == {"assertion", "virtual"}
