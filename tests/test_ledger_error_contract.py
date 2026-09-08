"""Ledger wrong-type rejections stay ValueError at their documented boundaries.

Every case below reaches one ``raise ValueError`` site in
``factgraph.core.store.ledger`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
Each site is paired with a valid-type positive control.
"""

from __future__ import annotations

import base64
import json

import pytest

from factgraph.core.store.ledger import (
    _ANNOTATION_COMPAT_PREFIX,
    Ledger,
    LedgerFormatError,
    MetaRow,
    _annotation_from_storage_key,
    _validate_meta_rows_for_append_assertion,
)


def _storage_key(payload: object) -> str:
    token = (
        base64.b64encode(json.dumps(payload).encode("utf-8"), altchars=b"-_")
        .decode("ascii")
        .rstrip("=")
    )
    return f"{_ANNOTATION_COMPAT_PREFIX}{token}"


_VALID_PAYLOAD = {
    "namespace": "ns",
    "category": "source",
    "key": "k",
    "origin": "observed",
    "derivation": None,
}


@pytest.mark.parametrize("payload", [["namespace", "ns"], "ns", 7])
def test_non_object_annotation_payload_keeps_value_error_cause(payload: object) -> None:
    with pytest.raises(LedgerFormatError) as excinfo:
        _annotation_from_storage_key("asrt:1", _storage_key(payload), "str", "v")
    cause = excinfo.value.__cause__
    assert type(cause) is ValueError
    assert "annotation compatibility payload must be an object" in str(cause)


def test_object_annotation_payload_is_accepted() -> None:
    row = _annotation_from_storage_key("asrt:1", _storage_key(_VALID_PAYLOAD), "str", "v")
    assert row.namespace == "ns"
    assert row.key == "k"


@pytest.mark.parametrize("value", [1, None, b"v", ["v"]])
def test_non_string_ledger_metadata_value_is_value_error(value: object) -> None:
    ledger = Ledger()
    with pytest.raises(ValueError, match="ledger metadata values must be strings"):
        ledger.commit_batch(
            assertions=(),
            revocations=(),
            expected_head_tx_id=None,
            head_tx_id="tx:1",
            metadata={"phase": value},
        )


def test_string_ledger_metadata_value_is_accepted() -> None:
    ledger = Ledger()
    ledger.commit_batch(
        assertions=(),
        revocations=(),
        expected_head_tx_id=None,
        head_tx_id="tx:1",
        metadata={"phase": "commit", "head_tx_seq": "1"},
    )


@pytest.mark.parametrize("asrt_id", [7, None, b"asrt:1"])
def test_non_string_meta_asrt_id_is_value_error(asrt_id: object) -> None:
    row = MetaRow(asrt_id=asrt_id, key="k", kind="str", value="v")
    with pytest.raises(ValueError, match="meta asrt_id must be str when provided"):
        _validate_meta_rows_for_append_assertion([row])


def test_string_meta_asrt_id_is_accepted() -> None:
    row = MetaRow(asrt_id="asrt:1", key="k", kind="str", value="v")
    assert _validate_meta_rows_for_append_assertion([row]) is None
