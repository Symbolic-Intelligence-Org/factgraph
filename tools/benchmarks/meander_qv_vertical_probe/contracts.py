"""Experimental contract helpers for the P0/A0 vertical probe.

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

Dict-shaped DTOs mirror the frozen fixture/golden JSON schema (fixtures/SCHEMA.md);
the scoped blueprint §5.4 is the sole authority. Nothing here is a public API.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

CONTRACT_ID = "vertical_probe.p0a0.v0"

# --- typed failure / diagnostic codes (blueprint §5.4/§5.9, SCHEMA.md rulings) ---
INGRESS_UNKNOWN_FIELDS = "INGRESS_UNKNOWN_FIELDS"
AMBIGUOUS_IDENTITY = "AMBIGUOUS_IDENTITY"
PIN_MISMATCH = "PIN_MISMATCH"
JOIN_ENDPOINT_NOT_TOTAL = "JOIN_ENDPOINT_NOT_TOTAL"
DNF_BRANCH_LIMIT_EXCEEDED = "DNF_BRANCH_LIMIT_EXCEEDED"
SYNTHETIC_QUERY_NAMESPACE_COLLISION = "SYNTHETIC_QUERY_NAMESPACE_COLLISION"
EXECUTION_ENGINE_FAULT = "EXECUTION_ENGINE_FAULT"
EXPECTATION_SET_MODE_UNSUPPORTED = "EXPECTATION_SET_MODE_UNSUPPORTED"
FIELD_NAVIGATION_RESTRICTED = "FIELD_NAVIGATION_RESTRICTED"
FIELD_NAVIGATION_UNKNOWN_FIELD = "FIELD_NAVIGATION_UNKNOWN_FIELD"
PATH_UNRESOLVED_ALIAS = "PATH_UNRESOLVED_ALIAS"
NAVIGATION_BRANCH_UNBOUND = "NAVIGATION_BRANCH_UNBOUND"

RESERVED_NAMESPACE_PREFIXES = ("__query__",)  # exact "__query__" or "__query__:*" (§5.9 AC-21)

QUERY = "query"
VALIDATION = "validation"

_SLOT_ALLOWED_INVOCATION_KEYS = {"slots", "extra_fields"}


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()[:16]


def full_digest(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


class ProbeError(Exception):
    """Typed pre-engine failure carrying a stable code and diagnostics."""

    def __init__(self, code: str, stage: str, diagnostics: list | None = None, **extra: Any):
        super().__init__(code)
        self.code = code
        self.stage = stage
        self.diagnostics = diagnostics or []
        self.extra = extra

    def as_failure(self) -> dict:
        payload = {"code": self.code, "stage": self.stage}
        if self.diagnostics:
            payload["diagnostics"] = list(self.diagnostics)
        payload.update(self.extra)
        return payload


def typed_failure_result(failure: Mapping[str, Any]) -> dict:
    """Canonical typed_failure shape: null rows fields (SCHEMA.md ruling #2)."""
    return {
        "kind": "typed_failure",
        "rows": None,
        "row_count": None,
        "completeness": None,
        "truncated": None,
        "query_summary": None,
        "failure": dict(failure),
    }


def static_validation_result(diagnostics: list, assertions_ok: bool, failure: Mapping[str, Any] | None = None) -> dict:
    out = {
        "kind": "static_validation",
        "rows": None,
        "row_count": None,
        "completeness": None,
        "truncated": None,
        "query_summary": None,
        "failure": dict(failure) if failure else None,
    }
    if diagnostics:
        out["diagnostics"] = list(diagnostics)
    return out


def rows_result(rows: list[dict], completeness: str, truncated: bool, query_summary: dict | None) -> dict:
    return {
        "kind": "rows",
        "rows": rows,
        "row_count": len(rows),
        "completeness": completeness,
        "truncated": truncated,
        "query_summary": query_summary,
        "failure": None,
    }


def exists_summary_result(status: Any, observed: int, completeness: str) -> dict:
    return {
        "kind": "exists_summary",
        "rows": [],
        "row_count": observed,
        "completeness": completeness,
        "truncated": False,
        "query_summary": {"status": status},
        "failure": None,
    }


def validate_task_kind_coherence(task_kind: str, expectation_template: Any) -> None:
    if task_kind == QUERY and expectation_template is not None:
        raise ProbeError("QUERY_WITH_EXPECTATION", stage="normalization")
    if task_kind == VALIDATION and expectation_template is None:
        raise ProbeError("VALIDATION_WITHOUT_EXPECTATION", stage="normalization")


def check_invocation_shape(invocation: Mapping[str, Any]) -> None:
    unknown = set(invocation.keys()) - _SLOT_ALLOWED_INVOCATION_KEYS
    if unknown:
        raise ProbeError(INGRESS_UNKNOWN_FIELDS, stage="ingress", diagnostics=sorted(unknown))
