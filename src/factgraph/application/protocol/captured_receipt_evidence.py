"""Sealed, capture-only native receipt inventory DTOs for private R3d use.

FactGraph Contract:
    These immutable shapes represent one receipt-selected native branch from a
    fully validated ``EvaluationRunBundleV0`` snapshot.  They carry only native
    condition coordinates, predicate ids, and captured assertion ids.  They do
    not carry values, source metadata, certainty, a verdict, Policy or Rule
    attribution, an ``EvidenceGraph``, an ``Explanation``, or a generic codec.

    Nested seals detect inconsistency in the stated capture linkage.  They are
    not authenticity, source provenance, admission, governance, authorization,
    business truth, proof parity, verification, or replay evidence.  The fixed
    ``unverified``, ``not_performed``, and ``not_claimed`` labels describe work
    that this contract did not perform; they do not mean falsehood.

    This module is an application-internal protocol detail.  It is deliberately
    absent from the application and protocol root façades and is not a Product,
    SDK, Meander, Agent, or MCP data contract.  DTO construction and validation
    read and write no Store, ledger, cache, sidecar, registry, or evaluator.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from factgraph.core.protocol.digests import sha256_hex

from .common import ProtocolShapeError

_MAX_BRANCH_CONDITIONS = 1_024
_MAX_ASSERTION_IDS_PER_CONDITION = 20_000


def _token(label: str, payload: object) -> str:
    """Return the canonical private seal for a scalar-only receipt payload."""

    try:
        raw = json.dumps(
            {"format": label, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, UnicodeEncodeError, ValueError, RecursionError) as exc:
        raise ProtocolShapeError("Captured receipt seal payload is not canonical JSON") from exc
    return f"sha256:{sha256_hex(raw)}"


def _require_text(value: object, field_name: str) -> str:
    if type(value) is not str or not value:
        raise ProtocolShapeError(f"{field_name} must be a non-empty string")
    return value


def _require_sha256_token(value: object, field_name: str) -> str:
    token = _require_text(value, field_name)
    if not token.startswith("sha256:") or len(token) != 71 or token != token.lower():
        raise ProtocolShapeError(f"{field_name} must be a lowercase sha256 token")
    try:
        int(token[7:], 16)
    except ValueError as exc:
        raise ProtocolShapeError(f"{field_name} must be a lowercase sha256 token") from exc
    return token


def _require_sha256_hex(value: object, field_name: str) -> str:
    digest = _require_text(value, field_name)
    if len(digest) != 64 or digest != digest.lower():
        raise ProtocolShapeError(f"{field_name} must be lowercase sha256 hex")
    try:
        int(digest, 16)
    except ValueError as exc:
        raise ProtocolShapeError(f"{field_name} must be lowercase sha256 hex") from exc
    return digest


def _require_non_negative_int(value: object, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise ProtocolShapeError(f"{field_name} must be a non-negative int")
    return value


def _branch_index(branch_id: str) -> int:
    if type(branch_id) is not str or not branch_id.startswith("c") or not branch_id[1:].isdigit():
        raise ProtocolShapeError("Captured receipt branch_id must have the form c<index>")
    if len(branch_id) > 10:
        raise ProtocolShapeError("Captured receipt branch_id exceeds the v0 limit")
    index = int(branch_id[1:])
    if branch_id != f"c{index}":
        raise ProtocolShapeError("Captured receipt branch_id is not canonical")
    return index


def _capture_context_digest(
    *,
    bundle_digest: str,
    row_capture_digest: str,
    native_plan_digest: str,
    proof_receipt_digest: str,
    branch_id: str,
) -> str:
    """Seal immutable bundle/row/plan/receipt linkage for one branch."""

    return _token(
        "captured_receipt_evidence_context_v0",
        (
            bundle_digest,
            row_capture_digest,
            native_plan_digest,
            proof_receipt_digest,
            branch_id,
        ),
    )


@dataclass(frozen=True, repr=False)
class CapturedReceiptConditionV0:
    """Seal one native receipt condition without values, verdict, or lineage.

    Args:
        capture_context_digest: Seal linking the condition to one snapshot.
        branch_id: Canonical selected native branch identifier, ``c<index>``.
        condition_index: Non-negative contiguous branch-local coordinate.
        condition_id: Exact ``<branch_id>:native:<condition_index>`` coordinate.
        receipt_condition_key: Exact native receipt condition key.
        native_kind: Captured native condition kind.
        predicate_id: Predicate identifier for ``pred`` conditions only.
        assertion_ids: Sorted unique captured assertion identifiers for ``pred``.
        captured_step_kind: Non-fact step kind, matching ``native_kind``.
        condition_digest: Seal over this condition's exact local inventory.

    Returns:
        An immutable, locally sealed native-condition inventory entry.

    Raises:
        ProtocolShapeError: If the coordinate, variant fields, bounds, or seal
            is malformed or stale.

    FactGraph Contract:
        This says only that the application captured this native coordinate and
        receipt inventory.  It establishes neither a logical conclusion nor
        source/admission/governance/authenticity truth, proof parity,
        verification, replay, Explain, EvidenceGraph, Rule, or Policy lineage.
        Its digest is an integrity link, never an authorization credential.
    """

    capture_context_digest: str
    branch_id: str
    condition_index: int
    condition_id: str
    receipt_condition_key: str
    native_kind: str
    predicate_id: str | None
    assertion_ids: tuple[str, ...]
    captured_step_kind: str | None
    condition_digest: str

    def __post_init__(self) -> None:
        _require_sha256_token(self.capture_context_digest, "Captured receipt condition context")
        branch_id = _require_text(self.branch_id, "Captured receipt condition branch_id")
        branch_index = _branch_index(branch_id)
        condition_index = _require_non_negative_int(
            self.condition_index, "Captured receipt condition index"
        )
        condition_id = _require_text(self.condition_id, "Captured receipt condition_id")
        receipt_condition_key = _require_text(
            self.receipt_condition_key, "Captured receipt condition key"
        )
        if condition_id != f"{branch_id}:native:{condition_index}":
            raise ProtocolShapeError(
                "Captured receipt condition_id does not match branch coordinate"
            )
        native_kind = _require_text(self.native_kind, "Captured receipt native_kind")
        if (
            type(self.assertion_ids) is not tuple
            or len(self.assertion_ids) > _MAX_ASSERTION_IDS_PER_CONDITION
            or any(type(item) is not str or not item for item in self.assertion_ids)
            or tuple(sorted(self.assertion_ids)) != self.assertion_ids
            or len(set(self.assertion_ids)) != len(self.assertion_ids)
        ):
            raise ProtocolShapeError(
                "Captured receipt assertion ids must be a bounded sorted unique string tuple"
            )
        if native_kind == "pred":
            predicate_id = _require_text(self.predicate_id, "Captured receipt predicate_id")
            if self.captured_step_kind is not None:
                raise ProtocolShapeError(
                    "Captured predicate condition cannot carry a captured step kind"
                )
            if not self.assertion_ids:
                raise ProtocolShapeError("Captured predicate condition requires assertion ids")
            captured_step_kind: str | None = None
            expected_key = f"c{branch_index}.c{condition_index}:{predicate_id}"
        else:
            if self.predicate_id is not None:
                raise ProtocolShapeError("Captured non-fact condition cannot carry a predicate_id")
            if self.assertion_ids:
                raise ProtocolShapeError("Captured non-fact condition cannot carry assertion ids")
            captured_step_kind = _require_text(
                self.captured_step_kind, "Captured non-fact step kind"
            )
            if captured_step_kind != native_kind:
                raise ProtocolShapeError(
                    "Captured non-fact step kind must match native condition kind"
                )
            expected_key = f"c{branch_index}.c{condition_index}:{native_kind}"
            predicate_id = None
        if receipt_condition_key != expected_key:
            raise ProtocolShapeError(
                "Captured receipt condition key does not match native coordinate"
            )
        expected = _token(
            "captured_receipt_condition_v0",
            (
                self.capture_context_digest,
                branch_id,
                condition_index,
                condition_id,
                receipt_condition_key,
                native_kind,
                predicate_id,
                self.assertion_ids,
                captured_step_kind,
            ),
        )
        _require_sha256_token(self.condition_digest, "Captured receipt condition digest")
        if self.condition_digest != expected:
            raise ProtocolShapeError("Captured receipt condition digest is stale")

    def validate(self) -> None:
        """Recheck this immutable condition's local shape and seal.

        Returns:
            ``None`` after local consistency checks pass.

        Raises:
            ProtocolShapeError: If a field or local digest is malformed or stale.

        FactGraph Contract:
            This is not bundle decoding, snapshot freshness, authentication,
            source/admission/governance recovery, verification, replay, proof
            parity, Explain, or EvidenceGraph construction.
        """

        CapturedReceiptConditionV0.__post_init__(self)

    def __repr__(self) -> str:
        return (
            "CapturedReceiptConditionV0("
            f"condition_id={self.condition_id!r}, native_kind={self.native_kind!r}, "
            "assertion_ids=<sealed>)"
        )


@dataclass(frozen=True, repr=False)
class CapturedReceiptBranchV0:
    """Seal the one native branch selected by a captured receipt.

    Args:
        capture_context_digest: Seal linking this branch to capture linkage.
        branch_id: Canonical selected native branch identifier.
        conditions: Non-empty, contiguous, sealed native condition inventory.
        branch_digest: Seal over context, branch id, and ordered condition seals.

    Returns:
        An immutable selected-branch inventory.

    Raises:
        ProtocolShapeError: If linkage, order, shape, limits, or seal fails.

    FactGraph Contract:
        The branch is receipt-selection metadata only.  It is not a Policy
        branch, Rule explanation, source provenance, verification, replay, or
        proof-parity result, and has no Store or evaluator behavior.
    """

    capture_context_digest: str
    branch_id: str
    conditions: tuple[CapturedReceiptConditionV0, ...]
    branch_digest: str

    def __post_init__(self) -> None:
        _require_sha256_token(self.capture_context_digest, "Captured receipt branch context")
        branch_id = _require_text(self.branch_id, "Captured receipt branch_id")
        _branch_index(branch_id)
        if (
            type(self.conditions) is not tuple
            or not self.conditions
            or len(self.conditions) > _MAX_BRANCH_CONDITIONS
            or not all(type(item) is CapturedReceiptConditionV0 for item in self.conditions)
        ):
            raise ProtocolShapeError(
                "Captured receipt branch conditions must be a bounded non-empty condition tuple"
            )
        for condition in self.conditions:
            condition.validate()
        if any(
            condition.capture_context_digest != self.capture_context_digest
            or condition.branch_id != branch_id
            for condition in self.conditions
        ):
            raise ProtocolShapeError("Captured receipt branch condition has a foreign context")
        if tuple(condition.condition_index for condition in self.conditions) != tuple(
            range(len(self.conditions))
        ):
            raise ProtocolShapeError(
                "Captured receipt branch condition indexes must be contiguous and canonical"
            )
        expected = _token(
            "captured_receipt_branch_v0",
            (
                self.capture_context_digest,
                branch_id,
                tuple(condition.condition_digest for condition in self.conditions),
            ),
        )
        _require_sha256_token(self.branch_digest, "Captured receipt branch digest")
        if self.branch_digest != expected:
            raise ProtocolShapeError("Captured receipt branch digest is stale")

    def validate(self) -> None:
        """Recheck this branch's nested local seals without reopening a run."""

        CapturedReceiptBranchV0.__post_init__(self)

    def __repr__(self) -> str:
        return (
            "CapturedReceiptBranchV0("
            f"branch_id={self.branch_id!r}, conditions=<sealed>, "
            f"branch_digest={self.branch_digest!r})"
        )


@dataclass(frozen=True, repr=False)
class CapturedReceiptEvidenceV0:
    """Seal one detached selected-native-receipt inventory.

    Args:
        bundle_digest: Exact source-bundle root seal.
        run_anchor_digest: Exact source-run anchor seal.
        native_plan_digest: Exact captured native-plan seal.
        native_where_digest: Exact captured native Where-bytes seal.
        query_digest: Lowercase SHA-256 compiled-query identity.
        result_id: Opaque source result identifier for linkage only.
        result_digest: Source-result digest seal.
        row_id: Opaque source row identifier for linkage only.
        claim_digest: Captured row claim digest seal.
        row_capture_digest: Exact selected row capture selector/seal.
        semantic_row_anchor_digest: Source semantic-row-anchor seal.
        proof_receipt_digest: Exact selected proof-receipt seal.
        capture_status: Fixed selected-receipt capture label.
        capture_basis: Fixed native plan/relation/receipt basis label.
        integrity: Fixed digest-sealed-not-authenticated label.
        authenticity: Fixed ``unverified`` label.
        logical_verification: Fixed ``not_performed`` label.
        replay_verification: Fixed ``not_performed`` label.
        proof_parity: Fixed ``not_claimed`` label.
        branch: Exactly one sealed receipt-selected native branch.
        evidence_digest: Root seal over all linkage and branch seal.

    Returns:
        An immutable capture-only receipt inventory with nested seals.

    Raises:
        ProtocolShapeError: If linkage, fixed availability labels, nested
            branch, or root seal is malformed or stale.

    FactGraph Contract:
        The private application builder is the approved construction path,
        because it starts from a fresh fully decoded bundle snapshot.  This DTO
        is not an ``EvidenceGraph``, ``Explanation``, Policy conclusion,
        verification record, replay result, logical proof, or Product-facing
        output.  ``unverified`` and the ``not_*`` labels are absence labels,
        never claims about source, admission, governance, business truth, or
        falsehood.  Seals are integrity checks, not authenticity or authority.
    """

    bundle_digest: str
    run_anchor_digest: str
    native_plan_digest: str
    native_where_digest: str
    query_digest: str
    result_id: str
    result_digest: str
    row_id: str
    claim_digest: str
    row_capture_digest: str
    semantic_row_anchor_digest: str
    proof_receipt_digest: str
    capture_status: Literal["selected_receipt_captured"]
    capture_basis: Literal["sealed_native_plan_relation_receipt"]
    integrity: Literal["digest_sealed_not_authenticated"]
    authenticity: Literal["unverified"]
    logical_verification: Literal["not_performed"]
    replay_verification: Literal["not_performed"]
    proof_parity: Literal["not_claimed"]
    branch: CapturedReceiptBranchV0
    evidence_digest: str

    def __post_init__(self) -> None:
        for name in (
            "bundle_digest",
            "run_anchor_digest",
            "native_plan_digest",
            "native_where_digest",
            "result_digest",
            "claim_digest",
            "row_capture_digest",
            "semantic_row_anchor_digest",
            "proof_receipt_digest",
        ):
            _require_sha256_token(getattr(self, name), f"Captured receipt evidence {name}")
        _require_sha256_hex(self.query_digest, "Captured receipt evidence query_digest")
        for name in ("result_id", "row_id"):
            _require_text(getattr(self, name), f"Captured receipt evidence {name}")
        if (
            self.capture_status,
            self.capture_basis,
            self.integrity,
            self.authenticity,
            self.logical_verification,
            self.replay_verification,
            self.proof_parity,
        ) != (
            "selected_receipt_captured",
            "sealed_native_plan_relation_receipt",
            "digest_sealed_not_authenticated",
            "unverified",
            "not_performed",
            "not_performed",
            "not_claimed",
        ):
            raise ProtocolShapeError("Captured receipt evidence semantics are outside v0")
        if type(self.branch) is not CapturedReceiptBranchV0:
            raise ProtocolShapeError("Captured receipt evidence requires a sealed native branch")
        self.branch.validate()
        expected_context = _capture_context_digest(
            bundle_digest=self.bundle_digest,
            row_capture_digest=self.row_capture_digest,
            native_plan_digest=self.native_plan_digest,
            proof_receipt_digest=self.proof_receipt_digest,
            branch_id=self.branch.branch_id,
        )
        if self.branch.capture_context_digest != expected_context:
            raise ProtocolShapeError(
                "Captured receipt branch context does not match evidence linkage"
            )
        expected = _token(
            "captured_receipt_evidence_v0",
            (
                self.bundle_digest,
                self.run_anchor_digest,
                self.native_plan_digest,
                self.native_where_digest,
                self.query_digest,
                self.result_id,
                self.result_digest,
                self.row_id,
                self.claim_digest,
                self.row_capture_digest,
                self.semantic_row_anchor_digest,
                self.proof_receipt_digest,
                self.capture_status,
                self.capture_basis,
                self.integrity,
                self.authenticity,
                self.logical_verification,
                self.replay_verification,
                self.proof_parity,
                self.branch.branch_digest,
            ),
        )
        _require_sha256_token(self.evidence_digest, "Captured receipt evidence digest")
        if self.evidence_digest != expected:
            raise ProtocolShapeError("Captured receipt evidence digest is stale")

    def validate(self) -> None:
        """Recheck only this DTO's nested seals and local field shapes.

        Returns:
            ``None`` after all local consistency checks pass.

        Raises:
            ProtocolShapeError: If an in-memory field, nested branch, or seal
                no longer matches this evidence record.

        FactGraph Contract:
            This does not decode or validate a source bundle, establish fresh
            capture, open a Store, inspect a registry, execute an evaluator,
            verify/replay a run, prove parity, authenticate source, recover
            admission/governance context, or construct Explain/EvidenceGraph.
        """

        CapturedReceiptEvidenceV0.__post_init__(self)

    def __repr__(self) -> str:
        return (
            "CapturedReceiptEvidenceV0("
            f"bundle_digest={self.bundle_digest!r}, row_id={self.row_id!r}, "
            f"evidence_digest={self.evidence_digest!r})"
        )
