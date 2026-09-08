"""Canonical domain export through both actual ProbLog consumers and real CLI."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from factgraph.adapters.problog.problog_export import export_problog
from factgraph.adapters.problog.reach_explain import _fact_lines
from factgraph.core.evidence.write_protocol import retract_by_asrt, set_field
from factgraph.core.store.ledger import AnnotationRow
from factgraph.core.store.premise_filter import PredicatePremiseBlock
from factgraph.core.view.projector import project_view_facts_with_witness
from factgraph.sdk import EmitSpec, Entity, Field, Identity, Inference, Pred, SDKStore, vars


class DomainPerson(Entity):
    person_id: str = Identity()
    tenant: str = Identity()
    tag: str = Field()
    result: str = Field()


def _fixture():
    fg = SDKStore([DomainPerson])
    ref = fg.entities.ref(DomainPerson, person_id="alice", tenant="acme")
    seed = fg.fields.set(DomainPerson.tag, ref, "vip", meta={"origin_binding": "hidden"})
    return fg, ref, seed


def _inference():
    with vars("person", "tag") as (person, tag):
        return Inference(
            id="domain_test",
            version="v1",
            when=[Pred("DomainPerson:exists", person), Pred("domain_person:tag", person, tag)],
            emits=EmitSpec("domain_person:result", [person, tag]),
        )


def _stored_facts(fg):
    # Includes schema, meta, revocations and all durable ledger tables.
    return tuple(fg.ledger._get_connection().iterdump())


def _programs(fg, tmp_path):
    from factgraph.core.store.runtime import premise_scoped_store_view

    compiled = fg._compile_derivation_input(_inference())[0]
    output = tmp_path / "domain.pl"
    # Same boundary used by Store.evaluate_engine; reach-explain scopes its
    # input itself because the SDK passes a base Store there.
    export_problog(premise_scoped_store_view(fg.store), compiled, output)
    return output.read_text(), "\n".join(_fact_lines(fg.store, uncertainty_projection=None))


def test_both_exporters_use_virtual_witness_not_legacy_marker(tmp_path):
    fg, ref, _seed = _fixture()
    marker = set_field(fg.ledger, "DomainPerson:exists", ref, [])
    (domain,) = project_view_facts_with_witness(fg.ledger, fg.store.schema_ir)[
        "DomainPerson:exists"
    ]
    before = _stored_facts(fg)
    original_lookup = fg.ledger.find_annotations

    def annotations(*args, **kwargs):
        assert kwargs.get("asrt_id") != domain.asrt_id
        return original_lookup(*args, **kwargs)

    with patch.object(fg.ledger, "find_annotations", side_effect=annotations):
        for program in _programs(fg, tmp_path):
            assert (
                program.count(
                    f"1::edb_fact('{domain.asrt_id}', 'DomainPerson:exists', '{ref}', '__none__')."
                )
                == 1
            )
            assert marker not in program
            assert "edb_fact(_, _, _, _) :- fail." in program
    assert before == _stored_facts(fg)


@pytest.mark.parametrize(
    "bad_row",
    [
        "answer(X3,X4): 0.82",
        "answer('not-an-entity-ref','bad'): 0.82",
    ],
)
def test_late_bad_output_never_remembers_partial_annotations_or_provenance(bad_row):
    fg, ref, _seed = _fixture()
    before = _stored_facts(fg)
    from factgraph.adapters.problog.engine_eval import evaluate_problog

    with (
        patch(
            "factgraph.adapters.problog.engine_eval.run_problog",
            return_value=f"answer('{ref}','vip'): 0.82\n{bad_row}",
        ),
        patch.object(fg.store, "_remember_provenance_envelope") as remember,
    ):
        with pytest.raises(Exception) as error:
            evaluate_problog(
                fg.store,
                derivation_id="atomic",
                version="v1",
                target_pred_id="domain_person:result",
                head_vars=["$person", "$tag"],
                where=[("pred", "domain_person:tag", ["$person", "$tag"])],
            )
        from factgraph.adapters.problog.problog_import import ProbLogImportError
        from factgraph.core.rules.where_eval import WhereValidationError

        assert isinstance(error.value, (ProbLogImportError, WhereValidationError, ValueError))
        remember.assert_not_called()
    assert not getattr(fg.store, "_problog_pending_annotations", {})
    assert _stored_facts(fg) == before


@pytest.mark.parametrize(
    "predicate", ["domain_person:person_id", "domain_person:tenant", "domain_person:tag"]
)
def test_both_evaluation_export_paths_preserve_premise_filter(tmp_path, predicate):
    fg, _ref, _seed = _fixture()
    fg.set_premise_blocks(
        [
            PredicatePremiseBlock(
                pred_id=predicate,
                key="origin_binding",
                blocked_values=frozenset({"hidden"}),
            )
        ]
    )
    # Tag already has the marker; set it on the selected Identity assertion too.
    from factgraph.core.store.ledger import MetaRow

    for claim in fg.ledger.find_claims(pred_id=predicate):
        fg.ledger.append_meta(
            [MetaRow(asrt_id=claim.asrt_id, key="origin_binding", kind="str", value="hidden")]
        )
    hidden_ids = [claim.asrt_id for claim in fg.ledger.find_claims(pred_id=predicate)]
    for program in _programs(fg, tmp_path):
        for hidden_id in hidden_ids:
            assert hidden_id not in program
        if predicate != "domain_person:tag":
            assert "::edb_fact('virtual-entity-exists:" not in program


@pytest.mark.parametrize("probability", [None, 0.82])
def test_real_domain_evaluation_is_read_only_and_keeps_trace_authority(probability):
    fg, ref, seed = _fixture()
    if probability is not None:
        fg.ledger.append_annotations(
            [
                AnnotationRow(
                    asrt_id=seed,
                    namespace="problog",
                    category="semantic",
                    key="probability",
                    kind="float",
                    value=probability,
                    origin="derived",
                    derivation="fixture",
                )
            ]
        )
    before = _stored_facts(fg)
    result = fg.eval.evaluate_candidates(_inference(), engine="problog")
    assert len(result) == 1
    candidate = result[0]
    assert candidate.payload["terms"][0]["value"] == ref
    assert candidate.confidence == pytest.approx(1 if probability is None else probability)
    assert candidate.support_kind == "problog_provenance_v1"
    report = fg.audit.support_witnesses(candidate.support_digest)
    assert report.status == "support_missing"
    assert report.capture_version is None
    assert not report.items
    assert before == _stored_facts(fg)


@pytest.mark.parametrize("raw_input_bound", [False, True])
def test_real_explain_has_domain_and_probability_atoms_without_trace_fallback(raw_input_bound):
    from factgraph.application.protocol import Rule
    from factgraph.core.rules.where_ast import PredAtom, Var

    fg, _ref, seed = _fixture()
    fg.ledger.append_annotations(
        [
            AnnotationRow(
                asrt_id=seed,
                namespace="problog",
                category="semantic",
                key="probability",
                kind="float",
                value=0.82,
                origin="derived",
                derivation="fixture",
            )
        ]
    )
    if raw_input_bound:
        from factgraph.core.store.ledger import MetaRow

        fg.ledger.append_meta(
            [
                MetaRow(seed, "raw_kind", "str", "probabilistic"),
                MetaRow(seed, "bound", "json", [0.82, 0.82]),
            ]
        )
    person, tag = Var("$person"), Var("$tag")
    rule = Rule(
        id="domain_probability",
        when=(
            PredAtom("DomainPerson:exists", [person]),
            PredAtom("domain_person:tag", [person, tag]),
        ),
        ports={"person": person, "tag": tag},
    )
    result = fg.eval.evaluate(rule, head=rule, engine="problog")
    assert len(result) == 1
    with patch(
        "factgraph.sdk.store.problog_trace_to_evidence_graph",
        side_effect=AssertionError("trace fallback is not acceptance"),
    ):
        explanation = result[0].explain()
    assert explanation.evidence is not None
    tree = explanation.evidence.paths[0]
    assert tree.metadata.get("fallback") is None
    assert tree.metadata["branch_probability"] == pytest.approx(0.82)
    atoms = [atom for block in tree.rules if block.role == "body" for atom in block.atoms]
    by_predicate = {atom.form.predicate: atom for atom in atoms}
    domain = by_predicate["DomainPerson:exists"]
    assert domain.verdict.certainty.lo == 1.0
    # Existing input certainty is sourced from raw_kind/bound, not the adapter's
    # probability annotation. Branch probability is 0.82 in both cases.
    tag_certainty = by_predicate["domain_person:tag"].verdict.certainty
    assert tag_certainty.kind == ("probabilistic" if raw_input_bound else "boolean")
    assert tag_certainty.lo == pytest.approx(0.82 if raw_input_bound else 1.0)


@pytest.mark.parametrize("missing", ["empty", "person_id", "tenant", "hidden"])
def test_real_no_domain_is_empty_not_engine_failure(missing):
    fg, _ref, _seed = _fixture()
    if missing == "empty":
        fg = SDKStore([DomainPerson])
    elif missing == "hidden":
        fg.set_premise_blocks(
            [
                PredicatePremiseBlock(
                    pred_id="domain_person:tag",
                    key="origin_binding",
                    blocked_values=frozenset({"hidden"}),
                )
            ]
        )
    else:
        for claim in fg.ledger.find_claims(pred_id=f"domain_person:{missing}"):
            retract_by_asrt(fg.ledger, claim.asrt_id)
    before = _stored_facts(fg)
    assert fg.eval.evaluate_candidates(_inference(), engine="problog") == []
    assert before == _stored_facts(fg)
