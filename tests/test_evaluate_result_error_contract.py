"""EvidenceGraph.metadata validation keeps its exact ValueError contract.

``explain_row`` builds the row EvidenceGraph inside ``except ValueError`` --
narrowly, with no ``TypeError`` -- and turns the failure into
``Explanation(status="unsupported", errors=(ErrorDTO(code="GRAPH_VALIDATION_FAILED"), ...))``.
A ``TypeError`` rewrite of the metadata shape guard would escape ``explain``
entirely instead of producing that closed Explanation payload.  The cases below
reach the ``raise ValueError`` site with a wrong-type input and pin the message.
"""

from __future__ import annotations

import re

import pytest

from factgraph.application.protocol.evaluate_result import (
    BOOLEAN_CERTAINTY,
    EvaluateResult,
    EvaluateRow,
    ResultFingerprint,
    _evidence_metadata_for_row_result,
    _validate_evidence_metadata_for_row_result,
    claim_digest_for,
    closed_head_digest_for,
    result_digest_for,
    result_id_for,
    row_id_for,
)
from factgraph.core.protocol.digests import sha256_token
from tests._t3_error_contract_fixtures import build_fixture

_INDEX, _SPACE, _POLICY, _QUERY = build_fixture()
_MESSAGE = "EvidenceGraph.metadata must be a mapping"


def _row_and_result():
    head = _QUERY.projection_head
    run_id = "run_v1:" + "1" * 64
    expr_digest = f"sha256:{_QUERY.query_digest}"
    rule_set = sha256_token(b"rules")
    view = sha256_token(b"view")
    result_id = result_id_for(
        run_id=run_id,
        expr_digest=expr_digest,
        rule_set_digest=rule_set,
        view_snapshot_digest=view,
        config_digest=None,
        engine="native",
        head_id=head.id,
        head_content_digest=head.content_digest,
    )
    bindings = {"age": {"kind": "literal", "tag": "int", "value": 41}}
    row = EvaluateRow(
        row_id=row_id_for(run_id, bindings),
        bindings=bindings,
        kind="projection",
        digest=claim_digest_for("projection", head.id, bindings),
        closed_head_digest=closed_head_digest_for(head),
        certainty=BOOLEAN_CERTAINTY,
    )
    result_digest = result_digest_for(
        result_id=result_id,
        run_id=run_id,
        row_digests=(),
        head_id=head.id,
        head_content_digest=head.content_digest,
        engine="native",
        engine_version=None,
        adapter_version=None,
        expr_digest=expr_digest,
        rule_set_digest=rule_set,
        view_snapshot_digest=view,
        config_digest=None,
    )
    result = EvaluateResult(
        result_id=result_id,
        rows=(row,),
        head=head,
        engine="native",
        evaluated_at="now",
        fingerprint=ResultFingerprint(
            expr_digest, rule_set, view, None, result_digest, run_id
        ),
        engine_meta={"engine_version": None, "adapter_version": None},
    )
    return row, result


_ROW, _RESULT = _row_and_result()


@pytest.mark.parametrize(
    "metadata",
    ["metadata", None, object(), (), [("result_id", "x")]],
)
def test_metadata_guard_rejects_non_mapping_as_value_error(metadata):
    with pytest.raises(ValueError, match=re.escape(_MESSAGE)) as caught:
        _validate_evidence_metadata_for_row_result(metadata, _ROW, _RESULT)
    assert type(caught.value) is ValueError
    assert str(caught.value) == _MESSAGE


def test_metadata_guard_accepts_the_canonical_row_result_mapping():
    metadata = _evidence_metadata_for_row_result(_ROW, _RESULT)
    assert _validate_evidence_metadata_for_row_result(metadata, _ROW, _RESULT) is None
    assert _validate_evidence_metadata_for_row_result(dict(metadata), _ROW, _RESULT) is None
