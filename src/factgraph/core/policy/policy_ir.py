from __future__ import annotations

import json
import time
from typing import Any

from factgraph.core.protocol.digests import sha256_token


class PolicyIRValidationError(Exception):
    pass


_REQUIRED_SCHEMA_PROTOCOL_KEYS = ("idref_v1", "tup_v1", "export_v1")


def build_policy_ir_v1(
    schema_ir: dict,
    policy_mode: str = "edb",
    *,
    generated_at: int | None = None,
) -> dict:
    if not isinstance(schema_ir, dict):
        raise PolicyIRValidationError("schema_ir must be dict")
    if policy_mode not in {"edb", "idb"}:
        raise PolicyIRValidationError("policy_mode must be 'edb' or 'idb'")

    schema_protocol = schema_ir.get("protocol_version")
    if not isinstance(schema_protocol, dict):
        raise PolicyIRValidationError("schema_ir.protocol_version must be object")

    copied_protocol: dict[str, str] = {}
    for key in _REQUIRED_SCHEMA_PROTOCOL_KEYS:
        value = schema_protocol.get(key)
        if not isinstance(value, str) or not value:
            raise PolicyIRValidationError(
                f"schema_ir.protocol_version missing required key: {key}"
            )
        copied_protocol[key] = value

    generated_at_value = time.time_ns() if generated_at is None else generated_at
    if not isinstance(generated_at_value, int):
        raise PolicyIRValidationError("generated_at must be int when provided")

    return {
        "policy_ir_version": "policy_ir_v1",
        "protocol_version": {
            "policy_v1": "policy_v1",
            **copied_protocol,
        },
        "generated_at": generated_at_value,
        "active": {"model": "revokes_only"},
        "chosen": {
            "strategy": "latest_by_ingested_at_then_min_assertion_id",
            "required_meta": ["ingested_at"],
        },
        "policy_mode": policy_mode,
    }


def canonicalize_policy_ir_jcs(policy_ir: dict) -> bytes:
    if not isinstance(policy_ir, dict):
        raise PolicyIRValidationError("policy_ir must be dict")

    _reject_floats(policy_ir, "$")

    try:
        return json.dumps(
            policy_ir,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PolicyIRValidationError(f"failed to canonicalize policy_ir: {exc}") from exc


def policy_digest(policy_ir: dict) -> str:
    canonical = canonicalize_policy_ir_jcs(policy_ir)
    return sha256_token(canonical)


def _reject_floats(value: Any, path: str) -> None:
    if isinstance(value, float):
        raise PolicyIRValidationError(f"float is not allowed in policy_ir at {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise PolicyIRValidationError(
                    f"policy_ir object key must be string at {path}"
                )
            _reject_floats(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_floats(child, f"{path}[{index}]")
