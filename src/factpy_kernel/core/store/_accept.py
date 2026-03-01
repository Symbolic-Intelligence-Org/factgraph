from __future__ import annotations

import warnings
from dataclasses import replace
from typing import Any

from factpy_kernel.core.derivation.accept import (
    AcceptOptions,
    AcceptRequest,
    AcceptResult,
    accept_candidate_set,
    accept_many_candidate_sets,
)
from factpy_kernel.core.derivation.candidates import CandidateSet
from factpy_kernel.core.policy.policy_ir import (
    PolicyIRValidationError,
    build_policy_ir_v1,
    policy_digest as compute_policy_digest,
)
from factpy_kernel.core.schema.schema_ir import (
    SchemaIRValidationError,
    schema_digest as compute_schema_digest,
)


class AcceptDigestWarning(RuntimeWarning):
    pass


def _accept_diagnostic(*, code: str, message: str, error_type: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "warning",
        "path": "$.accept.meta",
        "message": message,
        "data": {"error_type": error_type},
    }


def accept_store_candidate(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    candidate_set: CandidateSet,
    options: AcceptOptions,
) -> AcceptResult:
    if candidate_set.derivation_id != derivation_id:
        raise ValueError("derivation_id mismatch")
    if candidate_set.derivation_version != version:
        raise ValueError("derivation_version mismatch")
    schema_digest_token, policy_digest_token, diagnostics = _compute_accept_meta_digests(store)
    result = accept_candidate_set(
        ledger=store.ledger,
        candidate_set=candidate_set,
        options=options,
        derived_rule_id=derivation_id,
        derived_rule_version=version,
        schema_digest_token=schema_digest_token,
        policy_digest_token=policy_digest_token,
        schema_ir=store.schema_ir,
    )
    if not diagnostics:
        return result
    return replace(result, diagnostics=diagnostics)

def accept_store_candidates_many(
    store: Any,
    *,
    requests: list[AcceptRequest | CandidateSet | dict[str, Any]],
    mode: str = "atomic",
    idempotent_duplicate_ok: bool = True,
) -> list[dict[str, Any]]:
    schema_digest_token, policy_digest_token, diagnostics = _compute_accept_meta_digests(store)
    rows = accept_many_candidate_sets(
        ledger=store.ledger,
        requests=requests,
        mode=mode,
        idempotent_duplicate_ok=idempotent_duplicate_ok,
        schema_digest_token=schema_digest_token,
        policy_digest_token=policy_digest_token,
        schema_ir=store.schema_ir,
    )
    if not diagnostics:
        return rows
    for row in rows:
        if row.get("error") is None:
            continue
        err = row["error"]
        if not isinstance(err, dict):
            continue
        err.setdefault("diagnostics", list(diagnostics))
    return rows


def _compute_accept_meta_digests(
    store: Any,
) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    schema_digest_token: str | None = None
    policy_digest_token: str | None = None
    diagnostics: list[dict[str, Any]] = []

    try:
        schema_digest_token = compute_schema_digest(store.schema_ir)
    except SchemaIRValidationError as exc:
        msg = f"accept meta schema_digest unavailable: {exc}"
        warnings.warn(
            msg,
            AcceptDigestWarning,
            stacklevel=2,
        )
        diagnostics.append(
            _accept_diagnostic(
                code="accept_meta_schema_digest_unavailable",
                message=msg,
                error_type=type(exc).__name__,
            )
        )

    try:
        # policy_digest in accept meta must align with export/package policy_digest.
        # We build the same canonical policy artifact by fixing generated_at to 0.
        policy_ir = build_policy_ir_v1(
            store.schema_ir,
            policy_mode="edb",
            generated_at=0,
        )
        policy_digest_token = compute_policy_digest(policy_ir)
    except PolicyIRValidationError as exc:
        msg = f"accept meta policy_digest unavailable: {exc}"
        warnings.warn(
            msg,
            AcceptDigestWarning,
            stacklevel=2,
        )
        diagnostics.append(
            _accept_diagnostic(
                code="accept_meta_policy_digest_unavailable",
                message=msg,
                error_type=type(exc).__name__,
            )
        )

    return schema_digest_token, policy_digest_token, diagnostics
