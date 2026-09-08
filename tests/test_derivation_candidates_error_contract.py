"""Derivation-output wrong-type rejections stay ValueError at their documented boundary.

Every case below reaches one ``raise ValueError`` site in
``factgraph.core.derivation.candidates`` with a wrong-type input (the input a
``TypeError`` rewrite would re-classify) and pins the exact message, so the
exception class is part of the tested contract rather than a lint accident.
Each site is paired with a valid-type positive control.
"""

from __future__ import annotations

from typing import Any

import pytest

from factgraph.core.derivation.candidates import (
    DerivationOutput,
    compute_key_tuple_digest,
    make_derivation_output,
)

_KEY_TERMS: list[tuple[str, Any]] = [("string", "subject")]


def _factory_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "derivation_id": "rule:demo",
        "derivation_version": "v1",
        "run_id": "run:1",
        "target": "user:popular",
        "key_terms": _KEY_TERMS,
        "payload": {"pred_id": "user:popular", "terms": [["string", "subject"]]},
        "support_digest": "sha256:" + "0" * 64,
        "support_kind": "proof",
        "generated_at": 1,
    }
    kwargs.update(overrides)
    return kwargs


def test_dataclass_payload_wrong_type_is_value_error() -> None:
    with pytest.raises(ValueError, match="payload must be object"):
        DerivationOutput(
            derivation_id="rule:demo",
            derivation_version="v1",
            run_id="run:1",
            target="user:popular",
            key_tuple_digest=compute_key_tuple_digest(_KEY_TERMS),
            tup_digest=None,
            payload=[("a", 1)],
            support_digest="sha256:" + "0" * 64,
            support_kind="proof",
            generated_at=1,
            state="generated",
        )


def test_dataclass_dict_payload_is_accepted() -> None:
    output = DerivationOutput(
        derivation_id="rule:demo",
        derivation_version="v1",
        run_id="run:1",
        target="user:popular",
        key_tuple_digest=compute_key_tuple_digest(_KEY_TERMS),
        tup_digest=None,
        payload={"pred_id": "user:popular", "terms": [["string", "subject"]]},
        support_digest="sha256:" + "0" * 64,
        support_kind="proof",
        generated_at=1,
        state="generated",
    )
    assert output.payload["terms"] == [["string", "subject"]]


@pytest.mark.parametrize("payload", [[("a", 1)], "a=1", None])
def test_factory_payload_wrong_type_is_value_error(payload: object) -> None:
    with pytest.raises(ValueError, match="payload must be dict"):
        make_derivation_output(**_factory_kwargs(payload=payload))


@pytest.mark.parametrize("generated_at", ["1", 1.0, True, None])
def test_factory_generated_at_wrong_type_is_value_error(generated_at: object) -> None:
    with pytest.raises(ValueError, match="generated_at must be epoch-nanos int"):
        make_derivation_output(**_factory_kwargs(generated_at=generated_at))


def test_factory_accepts_dict_payload_and_int_generated_at() -> None:
    output = make_derivation_output(**_factory_kwargs())
    assert output.payload["terms"] == [["string", "subject"]]
    assert output.generated_at == 1
    assert output.candidate_id.startswith("cand_v2:")
