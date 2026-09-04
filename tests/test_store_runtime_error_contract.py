"""Store runtime wrong-type rejections stay ValueError at their documented boundaries.

Every case below reaches one ``raise ValueError`` site in
``factgraph.core.store.runtime`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
The SDK store wraps exactly ``ValueError`` from these paths into
``SDKStoreError``. Each site is paired with a valid-type positive control.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from factgraph.core.rules._trace import RuleTraceArtifact
from factgraph.core.store._support import ProofReceipt, ProvenanceEnvelope
from factgraph.core.store.runtime import Store

_SCHEMA_IR: dict[str, Any] = {
    "schema_ir_version": "v1",
    "entities": [
        {
            "entity_type": "Person",
            "identity_fields": [{"name": "person_id", "type_domain": "string"}],
        }
    ],
    "predicates": [
        {
            "pred_id": "person:name",
            "arg_specs": [
                {"name": "person", "type_domain": "entity_ref"},
                {"name": "name", "type_domain": "string"},
            ],
            "group_key_indexes": [0],
        }
    ],
    "projection": {"entities": ["Person"], "predicates": ["person:name"]},
    "protocol_version": {
        "idref_v1": "idref_v1",
        "tup_v1": "tup_v1",
        "export_v1": "export_v1",
    },
    "generated_at": "2026-05-20T00:00:00Z",
}
_DIGEST = "sha256:" + "0" * 64


def _store() -> Store:
    return Store(deepcopy(_SCHEMA_IR))


def _receipt() -> ProofReceipt:
    return ProofReceipt(kind="rule", root_result_kind="fact", binding_items=(), pred_witnesses=())


def _envelope() -> ProvenanceEnvelope:
    return ProvenanceEnvelope(
        candidate_id="cand_v2:1", engine="pyreason", payload_type="trace", payload={}
    )


def _trace() -> RuleTraceArtifact:
    return RuleTraceArtifact(
        rule_run_id="rr:1",
        root_rule_id="rule:demo",
        root_version="v1",
        select_vars=("$u",),
        invocations=(),
        root_rows=(),
    )


@pytest.mark.parametrize("schema_ir", [[("schema_ir_version", "v1")], "schema", None])
def test_non_dict_schema_ir_is_value_error(schema_ir: object) -> None:
    with pytest.raises(ValueError, match="schema_ir must be dict"):
        Store(schema_ir)


def test_dict_schema_ir_is_accepted() -> None:
    assert isinstance(_store().schema_ir, dict)


@pytest.mark.parametrize("artifact", [object(), {"kind": "rule"}, "receipt"])
def test_foreign_support_artifact_is_value_error(artifact: object) -> None:
    with pytest.raises(ValueError, match="artifact must be ProofReceipt"):
        _store()._remember_support_artifact(_DIGEST, artifact)


def test_proof_receipt_support_artifact_is_accepted() -> None:
    store = _store()
    store._remember_support_artifact(_DIGEST, _receipt())
    assert store._support_artifacts[_DIGEST] == _receipt()


@pytest.mark.parametrize("envelope", [object(), {"engine": "pyreason"}, "envelope"])
def test_foreign_provenance_envelope_is_value_error(envelope: object) -> None:
    with pytest.raises(ValueError, match="envelope must be ProvenanceEnvelope"):
        _store()._remember_provenance_envelope(_DIGEST, envelope)


def test_provenance_envelope_is_accepted() -> None:
    store = _store()
    store._remember_provenance_envelope(_DIGEST, _envelope())
    assert store._provenance_envelopes[_DIGEST] == _envelope()


@pytest.mark.parametrize("target_pred_id", [None, 7, ["person:name"]])
def test_non_string_target_pred_id_is_value_error(target_pred_id: object) -> None:
    with pytest.raises(ValueError, match="target_pred_id must be string"):
        _store()._remember_candidate_support(
            "cand_v2:1", _DIGEST, "proof", target_pred_id=target_pred_id
        )


def test_string_target_pred_id_is_accepted() -> None:
    store = _store()
    store._remember_candidate_support(
        "cand_v2:1", _DIGEST, "proof", target_pred_id="person:name"
    )
    assert store._candidate_support_index["cand_v2:1"] == _DIGEST


@pytest.mark.parametrize("artifact", [object(), {"rule_run_id": "rr:1"}, "trace"])
def test_foreign_rule_trace_artifact_is_value_error(artifact: object) -> None:
    with pytest.raises(ValueError, match="artifact must be RuleTraceArtifact"):
        _store()._remember_rule_trace_artifact("rr:1", artifact)


def test_rule_trace_artifact_is_accepted() -> None:
    store = _store()
    store._remember_rule_trace_artifact("rr:1", _trace())
    assert store._rule_trace_artifacts["rr:1"] == _trace()
