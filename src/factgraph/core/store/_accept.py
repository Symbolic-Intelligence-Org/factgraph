"""Store-level accept seam (write leg).

Premise admissibility (core/store/premise_filter.py) deliberately does NOT
apply here: accept only consumes candidates produced by an already-filtered
evaluation, and its ledger reads serve candidate_key idempotency dedup,
which must see the full ledger.
"""

from __future__ import annotations

import warnings
from dataclasses import replace
from typing import Any

from factgraph.core.derivation.accept import (
    AcceptOptions,
    AcceptRequest,
    AcceptResult,
    accept_candidate_set,
    accept_many_candidate_sets,
)
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.policy.policy_ir import (
    PolicyIRValidationError,
    build_policy_ir_v1,
)
from factgraph.core.policy.policy_ir import (
    policy_digest as compute_policy_digest,
)
from factgraph.core.schema.schema_ir import (
    SchemaIRValidationError,
)
from factgraph.core.schema.schema_ir import (
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
    return _accept_store_candidate_as_derived_rule(
        store,
        derivation_id=derivation_id,
        version=version,
        candidate_set=candidate_set,
        options=options,
    )


def _accept_store_candidate_as_derived_rule(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    candidate_set: CandidateSet,
    options: AcceptOptions,
) -> AcceptResult:
    """Materialize through Store-owned enrichment under a declared rule identity.

    Application RuleExpr lowering may give an output a compiler-generated
    derivation identity while the caller records the stable authored/business
    rule identity in ledger provenance.  This internal seam preserves that
    established distinction.  Direct ``Store.accept`` remains stricter and
    validates that its derivation identity matches the output.
    """
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
