"""Deterministic P0/A0 fixed-profile resolver (§5.4.2).

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

Ingress -> ResolutionArtifactV0. All authority attempts, type errors, ambiguous
identities and pin mismatches fail typed BEFORE any engine involvement.
Failure never equals zero rows (§5.4.2).
"""
from __future__ import annotations

from typing import Any

from contracts import (
    AMBIGUOUS_IDENTITY,
    INGRESS_UNKNOWN_FIELDS,
    PIN_MISMATCH,
    ProbeError,
    digest,
    validate_task_kind_coherence,
)

# Fields an Agent may NEVER supply (P0/A0 ownership, blueprint §5.2)
FORBIDDEN_AUTHORITY_FIELDS = (
    "policy_ref", "policy", "occurrence", "path", "bind", "select",
    "expect", "expectation", "config", "engine", "mode", "authority",
    "verdict", "premise", "source",
)


def _identity_candidates(world: dict, entity_type: str, raw: str, matching: str | None) -> list[str]:
    """Known identities of a lookup-typed entity: subjects appearing in facts."""
    known: list[str] = []
    seen = set()
    for fact in world.get("facts", ()):  # [pred, subj, *rest]
        if len(fact) >= 2 and isinstance(fact[1], str) and fact[1] not in seen:
            seen.add(fact[1])
            known.append(fact[1])
    if matching == "case_insensitive_lookup_case_sensitive_identity":
        return [k for k in known if k.lower() == raw.lower()]
    return [k for k in known if k == raw]


def resolve(fixture: dict, snapshot: dict) -> dict:
    """ProbeInvocationV0 -> ResolutionArtifactV0 (dict form)."""
    prof = snapshot["profile"]
    invocation = fixture["invocation"]
    artifact: dict[str, Any] = {
        "raw_submission_digest": digest(invocation),
        "profile_ref": snapshot["profile_ref"],
        "profile_digest": snapshot["profile_digest"],
        "normalized_slot_values": {},
        "attempted_authority_fields": [],
        "status": None,
        "diagnostics": [],
    }

    # --- ingress: additionalProperties=false over the whole submission ---
    extra = invocation.get("extra_fields") or {}
    # Submission order preserved (frozen-oracle convention; experiment-v0 only,
    # NOT a public canonical-ordering contract — see final report note).
    attempted = list(extra.keys())
    artifact["attempted_authority_fields"] = attempted
    if attempted:
        artifact["status"] = "rejected_unknown_field"
        artifact["diagnostics"] = attempted
        raise ProbeError(
            INGRESS_UNKNOWN_FIELDS, stage="ingress",
            diagnostics=attempted, artifact=artifact,
        )
    unknown_top = set(invocation.keys()) - {"slots", "extra_fields"}
    if unknown_top:
        artifact["status"] = "rejected_unknown_field"
        raise ProbeError(INGRESS_UNKNOWN_FIELDS, stage="ingress",
                         diagnostics=sorted(unknown_top), artifact=artifact)

    # --- schema pin (NAV02 pin-mismatch probe path) ---
    pin = prof.get("schema_digest_pin")
    if pin is not None:
        actual = digest(fixture["world"].get("entity_types", []))
        if pin != actual:
            artifact["status"] = PIN_MISMATCH
            raise ProbeError(PIN_MISMATCH, stage="resolution",
                             diagnostics=[f"pinned={pin}", f"actual={actual}"], artifact=artifact)

    # --- task-kind coherence (server-owned; §5.4.3) ---
    validate_task_kind_coherence(prof["task_kind"], prof.get("expectation_template"))

    # --- typed slot validation + identity normalization ---
    declared = {d["slot"]: d for d in prof.get("slot_descriptors", ())}
    slots = invocation.get("slots") or {}
    unknown_slots = set(slots) - set(declared)
    if unknown_slots:
        artifact["status"] = "rejected_unknown_field"
        raise ProbeError(INGRESS_UNKNOWN_FIELDS, stage="ingress",
                         diagnostics=sorted(unknown_slots), artifact=artifact)
    missing = set(declared) - set(slots)
    if missing:
        artifact["status"] = "rejected_type"
        raise ProbeError("INGRESS_MISSING_SLOT", stage="ingress",
                         diagnostics=sorted(missing), artifact=artifact)

    matching = prof.get("resolver_identity_matching")
    lookup_types = {et["name"] for et in fixture["world"].get("entity_types", ())
                    if et.get("identity") not in (None, "value")}
    for name, desc in declared.items():
        raw = slots[name]
        if desc["type"] == "entity_ref":
            if not isinstance(raw, str):
                artifact["status"] = "rejected_type"
                raise ProbeError("INGRESS_SLOT_TYPE", stage="ingress",
                                 diagnostics=[name], artifact=artifact)
            etype = desc.get("entity_type")
            if etype in lookup_types:
                # identity-by-lookup: existence + uniqueness under the declared matching rule
                cands = _identity_candidates(fixture["world"], etype, raw, matching)
                if len(cands) > 1:
                    rich = [{
                        "code": AMBIGUOUS_IDENTITY, "slot": name, "submitted": raw,
                        "candidates": [{"entity": etype, "id": c} for c in sorted(cands)],
                    }]
                    artifact["status"] = AMBIGUOUS_IDENTITY
                    artifact["diagnostics"] = rich
                    raise ProbeError(AMBIGUOUS_IDENTITY, stage="resolution",
                                     diagnostics=rich, artifact=artifact)
                # zero candidates: identity-by-lookup miss is a resolution failure
                if not cands:
                    artifact["status"] = "UNKNOWN_IDENTITY"
                    raise ProbeError("UNKNOWN_IDENTITY", stage="resolution",
                                     diagnostics=[raw], artifact=artifact)
                artifact["normalized_slot_values"][name] = {"entity": etype, "id": cands[0]}
            else:
                # identity-by-value (SCHEMA.md ruling #6): resolved without existence check
                artifact["normalized_slot_values"][name] = {"entity": etype, "id": raw}
        else:
            artifact["normalized_slot_values"][name] = {"value": raw}

    artifact["status"] = "resolved"
    artifact["resolved_request_digest"] = digest(
        {"profile": snapshot["profile_digest"], "slots": artifact["normalized_slot_values"]}
    )
    return artifact
