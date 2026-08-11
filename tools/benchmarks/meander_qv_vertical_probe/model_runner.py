"""Step 4 readiness (LOCAL ONLY): raw-HTTP projection adapters + offline conformance.

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

Two experiment-owned raw HTTP projections (§5.11 PreScopedProviderProfileFreezeV0):
  openai-gpt-responses-v1      — Responses tool-call JSON dialect
  anthropic-claude-messages-v1 — Messages tool_use/tool_result JSON dialect

Offline conformance contract (three items ONLY): request serialization,
canonical schema embed->extract byte identity, canned response normalization.
ZERO network, ZERO credentials, ZERO provider calls. Real API acceptance stays
NOT_TESTED_UNTIL_AUTHORIZED_EXECUTION. Exact model IDs remain candidates until
the user-confirmed first-scored-call freeze (ScoredArmManifestV0).
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

_PROBE_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROBE_ROOT not in sys.path:
    sys.path.insert(0, _PROBE_ROOT)

from contracts import canonical_json, full_digest  # noqa: E402
from profiles import load_fixture  # noqa: E402

MODEL_CELLS = ("Q02", "Q04", "E03", "A01-AMB", "A01-AUTH", "X01")

PROVIDER_PROFILES = [
    {
        "record_type": "ProviderProfileV0",
        "profile_id": "openai-gpt-responses-v1",
        "provider_organization": "OpenAI",
        "base_model_family": "GPT",
        "wire_dialect": "Responses tool-call JSON",
        "adapter_strategy": "experiment-owned raw HTTP projection",
        "offline_conformance_contract_version": "v0 (serialization / embed-extract byte identity / canned normalization)",
        "model_id_state": "pending_until_first_scored_call_freeze",
        "candidate_exact_model_id": "CANDIDATE: latest generally-available GPT reasoning model at freeze time (user confirms exact ID in model-stage package)",
        "remote_api_acceptance": "NOT_TESTED_UNTIL_AUTHORIZED_EXECUTION",
    },
    {
        "record_type": "ProviderProfileV0",
        "profile_id": "anthropic-claude-messages-v1",
        "provider_organization": "Anthropic",
        "base_model_family": "Claude",
        "wire_dialect": "Messages tool_use/tool_result JSON",
        "adapter_strategy": "experiment-owned raw HTTP projection",
        "offline_conformance_contract_version": "v0 (serialization / embed-extract byte identity / canned normalization)",
        "model_id_state": "pending_until_first_scored_call_freeze",
        "candidate_exact_model_id": "CANDIDATE: latest generally-available Claude model at freeze time (user confirms exact ID in model-stage package)",
        "remote_api_acceptance": "NOT_TESTED_UNTIL_AUTHORIZED_EXECUTION",
    },
]


def canonical_tool_schema(profile: dict) -> tuple[str, bytes]:
    """Agent-visible tool schema for one assigned profile.

    Recursive additionalProperties=false; every declared property required;
    optional semantics via nullable union (§5.11.1). Canonical digest is
    computed on these bytes BEFORE any provider wrapping.
    """
    props: dict[str, Any] = {}
    for d in profile.get("slot_descriptors", ()):
        props[d["slot"]] = {"type": "string",
                            "description": f"typed {d['type']} slot"
                            + (f" ({d.get('entity_type')})" if d.get("entity_type") else "")}
    schema = {
        "type": "object",
        "properties": props,
        "required": sorted(props.keys()),
        "additionalProperties": False,
    }
    name = "probe_" + profile["profile_ref"].replace(".", "_")
    payload = {
        "name": name,
        "description": "EXPERIMENTAL vertical_probe.p0a0.v0 fixed-profile invocation; "
                       "server owns policy/mode/projection/expectations.",
        "schema": schema,
    }
    b = canonical_json(payload).encode("utf-8")
    return name, b


def project_openai(tool_name: str, canonical_bytes: bytes) -> dict:
    payload = json.loads(canonical_bytes.decode("utf-8"))
    return {
        "model": "<PENDING_FREEZE>",
        "input": [{"role": "user", "content": "<frozen task text placeholder>"}],
        "tools": [{
            "type": "function",
            "name": payload["name"],
            "description": payload["description"],
            "parameters": payload["schema"],
            "strict": True,  # transport flag frozen separately in ScoredArmManifestV0
        }],
        "tool_choice": "auto",
    }


def extract_openai(wrapper: dict) -> bytes:
    t = wrapper["tools"][0]
    return canonical_json({"name": t["name"], "description": t["description"],
                           "schema": t["parameters"]}).encode("utf-8")


def project_anthropic(tool_name: str, canonical_bytes: bytes) -> dict:
    payload = json.loads(canonical_bytes.decode("utf-8"))
    return {
        "model": "<PENDING_FREEZE>",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": "<frozen task text placeholder>"}],
        "tools": [{
            "name": payload["name"],
            "description": payload["description"],
            "input_schema": payload["schema"],
        }],
    }


def extract_anthropic(wrapper: dict) -> bytes:
    t = wrapper["tools"][0]
    return canonical_json({"name": t["name"], "description": t["description"],
                           "schema": t["input_schema"]}).encode("utf-8")


# ---- canned response normalization (dialect -> vendor-neutral) --------------------

def normalize_openai(resp: dict) -> dict:
    if "error" in resp:
        return {"kind": "provider_error", "code": resp["error"].get("code", "unknown")}
    for item in resp.get("output", ()):
        if item.get("type") == "function_call":
            return {"kind": "tool_call", "tool": item["name"],
                    "slots": json.loads(item["arguments"])}
    for item in resp.get("output", ()):
        if item.get("type") == "message":
            text = "".join(c.get("text", "") for c in item.get("content", ())
                           if c.get("type") == "output_text")
            return {"kind": "final", "text": text}
    return {"kind": "provider_error", "code": "unrecognized_shape"}


def normalize_anthropic(resp: dict) -> dict:
    if resp.get("type") == "error":
        return {"kind": "provider_error", "code": (resp.get("error") or {}).get("type", "unknown")}
    for block in resp.get("content", ()):
        if block.get("type") == "tool_use":
            return {"kind": "tool_call", "tool": block["name"], "slots": block["input"]}
    text = "".join(b.get("text", "") for b in resp.get("content", ()) if b.get("type") == "text")
    if text:
        return {"kind": "final", "text": text}
    return {"kind": "provider_error", "code": "unrecognized_shape"}


def run_conformance() -> dict:
    per_profile = []
    for cell in MODEL_CELLS:
        prof = load_fixture(cell)["profile"]
        name, canon = canonical_tool_schema(prof)
        canon_digest = full_digest(json.loads(canon.decode("utf-8")))
        oa = project_openai(name, canon)
        an = project_anthropic(name, canon)
        oa_bytes = json.dumps(oa, ensure_ascii=False).encode()  # serialization check
        an_bytes = json.dumps(an, ensure_ascii=False).encode()
        oa_extract = extract_openai(oa)
        an_extract = extract_anthropic(an)
        per_profile.append({
            "cell": cell,
            "tool_name": name,
            "canonical_digest": canon_digest,
            "serialization_ok": bool(oa_bytes) and bool(an_bytes),
            "openai_embed_extract_byte_identical": oa_extract == canon,
            "anthropic_embed_extract_byte_identical": an_extract == canon,
        })
    canned = {
        "tool_call": {
            "openai": normalize_openai({"output": [{"type": "function_call", "name": "probe_x",
                                                    "arguments": "{\"team_ref\": \"red\"}"}]}),
            "anthropic": normalize_anthropic({"content": [{"type": "tool_use", "name": "probe_x",
                                                           "input": {"team_ref": "red"}}]}),
        },
        "final": {
            "openai": normalize_openai({"output": [{"type": "message", "content": [
                {"type": "output_text", "text": "three members: alice, bob, dan"}]}]}),
            "anthropic": normalize_anthropic({"content": [
                {"type": "text", "text": "three members: alice, bob, dan"}]}),
        },
        "provider_error": {
            "openai": normalize_openai({"error": {"code": "rate_limited"}}),
            "anthropic": normalize_anthropic({"type": "error", "error": {"type": "rate_limited"}}),
        },
    }
    canned_identity = {
        "tool_call": canned["tool_call"]["openai"] == canned["tool_call"]["anthropic"],
        "final": canned["final"]["openai"] == canned["final"]["anthropic"],
        "provider_error": (canned["provider_error"]["openai"]["kind"]
                           == canned["provider_error"]["anthropic"]["kind"] == "provider_error"),
    }
    all_ok = (all(p["serialization_ok"] and p["openai_embed_extract_byte_identical"]
                  and p["anthropic_embed_extract_byte_identical"] for p in per_profile)
              and all(canned_identity.values()))
    report = {
        "record_type": "Step4ReadinessConformanceV0",
        "network_calls": 0, "credentials_touched": 0, "provider_calls": 0,
        "provider_profiles": PROVIDER_PROFILES,
        "per_profile_conformance": per_profile,
        "canned_normalization": canned,
        "canned_normalization_identity": canned_identity,
        "conformance_all_ok": all_ok,
        "remote_api_acceptance": "NOT_TESTED_UNTIL_AUTHORIZED_EXECUTION (both arms)",
        "note": "strict:true transport flag and exact model IDs freeze into ScoredArmManifestV0 "
                "before the first scored call; canonical schemas already satisfy "
                "additionalProperties=false + all-properties-required, so strict mode "
                "cannot mutate the required set (preflight PF-Rec3 honored).",
    }
    out = os.path.join(_PROBE_ROOT, "reports", "step4_readiness_conformance.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return report


if __name__ == "__main__":
    r = run_conformance()
    print("profiles:", len(r["per_profile_conformance"]),
          "| conformance_all_ok:", r["conformance_all_ok"],
          "| canned identity:", r["canned_normalization_identity"])
    sys.exit(0 if r["conformance_all_ok"] else 1)
