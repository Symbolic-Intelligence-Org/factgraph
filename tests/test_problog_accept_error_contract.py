"""ProbLog post-accept binder keeps its ValueError argument rejection contract.

Every case below reaches the ``raise ValueError`` site in
``factgraph.adapters.problog.accept`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from factgraph.adapters.problog.accept import persist_problog_annotations
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.store.ledger import Ledger

# --- persist_problog_annotations: "ledger must be a Ledger instance" ---


@pytest.mark.parametrize("ledger", ["not_a_ledger", None, object(), {"append_annotations": None}])
def test_persist_rejects_non_ledger_as_value_error(ledger):
    with pytest.raises(ValueError, match=re.escape("ledger must be a Ledger instance")) as caught:
        persist_problog_annotations(ledger, "run-1", SimpleNamespace(), SimpleNamespace())
    assert type(caught.value) is ValueError
    assert str(caught.value) == "ledger must be a Ledger instance"


def test_persist_with_real_ledger_binds_pending_template_to_written_assertion():
    ledger = Ledger()
    asrt_id = set_field(
        ledger,
        pred_id="user:name",
        e_ref="idref_v1:User:Alice",
        rest_terms=[("string", "Alice")],
        meta={"source": "test"},
    )
    store = SimpleNamespace(
        _problog_pending_annotations={
            "run-1": {
                "cand-1": [
                    {
                        "namespace": "problog",
                        "category": "semantic",
                        "key": "probability",
                        "kind": "float",
                        "value": 0.8,
                        "origin": "derived",
                        "derivation": "drv.problog_tag",
                        "fact_index": 0,
                    }
                ]
            }
        }
    )
    accept_result = SimpleNamespace(
        candidate_id="cand-1",
        written_assertions=[{"asrt_id": asrt_id, "pred_id": "user:name"}],
    )

    assert persist_problog_annotations(ledger, "run-1", store, accept_result) == 1

    rows = ledger.find_annotations(asrt_id=asrt_id, namespace="problog")
    assert [row.key for row in rows] == ["probability"]
    assert not store._problog_pending_annotations
    ledger.close()
