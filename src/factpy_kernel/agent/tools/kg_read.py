from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import AgentContractError
from ._entity_ref import encode_entity_ref
from ._runtime_api import RuntimeAPI, require_ok, resolve_runtime_api


@dataclass
class ClaimResult:
    asrt_id: str
    pred_id: str
    e_ref: str
    rest_terms: list[tuple[str, object]]
    meta: dict[str, object]
    is_revoked: bool


@dataclass
class EntitySnapshot:
    entity_type: str
    identity: dict[str, object]
    e_ref: str
    claims: list[ClaimResult]


@dataclass
class CandidateSummary:
    candidate_id: str
    pred_id: str
    support_kind: str
    confidence_kind: str


@dataclass
class RuleSummary:
    rule_id: str
    version: str
    source: str
    spec: dict[str, Any] | None = None


class KGReadTools:
    """Adapter composition over the existing runtime inventory/query surface."""

    def __init__(
        self,
        runtime_api_base: str | None = None,
        *,
        runtime_api: RuntimeAPI | None = None,
    ) -> None:
        self._runtime = resolve_runtime_api(
            runtime_api_base=runtime_api_base,
            runtime_api=runtime_api,
        )

    def query_claims(
        self,
        session_id: str,
        pred_id: str | None = None,
        e_ref: str | None = None,
    ) -> list[ClaimResult]:
        resp = require_ok(
            self._runtime.list_claims(
                session_id,
                pred_id=pred_id,
                e_ref=e_ref,
                include_meta=True,
                include_args=False,
            )
        )
        claims = resp.get("claims", [])
        if not isinstance(claims, list):
            raise AgentContractError("runtime claims payload must be list")
        return [_claim_from_payload(item) for item in claims]

    def get_entity_snapshot(
        self,
        session_id: str,
        entity_type: str,
        identity: dict[str, object],
    ) -> EntitySnapshot:
        schema_resp = require_ok(self._runtime.get_schema(session_id))
        schema_ir = schema_resp.get("result", {}).get("schema_ir")
        if not isinstance(schema_ir, dict):
            raise AgentContractError("runtime schema result must include schema_ir")
        e_ref = _encode_entity_ref(schema_ir, entity_type=entity_type, identity=identity)
        claims = self.query_claims(session_id, pred_id=None, e_ref=e_ref)
        return EntitySnapshot(
            entity_type=entity_type,
            identity=dict(identity),
            e_ref=e_ref,
            claims=claims,
        )

    def list_candidates(
        self,
        session_id: str,
        pred_id: str | None = None,
    ) -> list[CandidateSummary]:
        resp = require_ok(
            self._runtime.list_candidates(session_id, pred_id_filter=pred_id)
        )
        raw = resp.get("result", {}).get("candidates", [])
        if not isinstance(raw, list):
            raise AgentContractError("runtime candidates payload must be list")
        out: list[CandidateSummary] = []
        for item in raw:
            if not isinstance(item, dict):
                raise AgentContractError("runtime candidate entries must be objects")
            out.append(
                CandidateSummary(
                    candidate_id=_require_non_empty_str(item.get("candidate_id"), "candidate_id"),
                    pred_id=_require_non_empty_str(item.get("pred_id"), "pred_id"),
                    support_kind=_require_non_empty_str(item.get("support_kind"), "support_kind"),
                    confidence_kind=_require_non_empty_str(item.get("confidence_kind"), "confidence_kind"),
                )
            )
        return out

    def list_rules(self, session_id: str, include_spec: bool = False) -> list[RuleSummary]:
        resp = require_ok(self._runtime.list_rules(session_id, include_spec=include_spec))
        raw = resp.get("result", {}).get("rules", [])
        if not isinstance(raw, list):
            raise AgentContractError("runtime rules payload must be list")
        out: list[RuleSummary] = []
        for item in raw:
            if not isinstance(item, dict):
                raise AgentContractError("runtime rule entries must be objects")
            spec = None
            if include_spec:
                spec = {
                    "select_vars": list(item.get("select_vars", [])),
                    "where": list(item.get("where", [])),
                    "expose": bool(item.get("expose", False)),
                }
            out.append(
                RuleSummary(
                    rule_id=_require_non_empty_str(item.get("rule_id"), "rule_id"),
                    version=_require_non_empty_str(item.get("version"), "version"),
                    source=_require_non_empty_str(item.get("source"), "source"),
                    spec=spec,
                )
            )
        return out

    def get_schema_summary(self, session_id: str) -> dict[str, Any]:
        resp = require_ok(self._runtime.get_schema(session_id))
        result = resp.get("result", {})
        schema_ir = result.get("schema_ir")
        if not isinstance(schema_ir, dict):
            raise AgentContractError("runtime schema result must include schema_ir")
        entities = schema_ir.get("entities", [])
        predicates = schema_ir.get("predicates", [])
        return {
            "schema_digest": result.get("schema_digest"),
            "entity_types": [
                {
                    "entity_type": entity.get("entity_type"),
                    "identity_fields": [
                        field.get("name")
                        for field in entity.get("identity_fields", [])
                        if isinstance(field, dict)
                    ],
                }
                for entity in entities
                if isinstance(entity, dict)
            ],
            "predicates": [
                {
                    "pred_id": predicate.get("pred_id"),
                    "arg_specs": [
                        {
                            "name": arg.get("name"),
                            "type_domain": arg.get("type_domain"),
                        }
                        for arg in predicate.get("arg_specs", [])
                        if isinstance(arg, dict)
                    ],
                }
                for predicate in predicates
                if isinstance(predicate, dict)
            ],
        }


def _claim_from_payload(payload: dict[str, Any]) -> ClaimResult:
    rest_terms_raw = payload.get("rest_terms", [])
    if not isinstance(rest_terms_raw, list):
        raise AgentContractError("claim.rest_terms must be list")
    rest_terms: list[tuple[str, object]] = []
    for item in rest_terms_raw:
        if isinstance(item, tuple) and len(item) == 2:
            rest_terms.append(item)
        elif isinstance(item, list) and len(item) == 2:
            rest_terms.append((item[0], item[1]))
        else:
            raise AgentContractError("claim.rest_terms entries must be pairs")
    meta_rows = payload.get("meta_rows", [])
    meta = _meta_rows_to_map(meta_rows)
    return ClaimResult(
        asrt_id=_require_non_empty_str(payload.get("asrt_id"), "asrt_id"),
        pred_id=_require_non_empty_str(payload.get("pred_id"), "pred_id"),
        e_ref=_require_non_empty_str(payload.get("e_ref"), "e_ref"),
        rest_terms=rest_terms,
        meta=meta,
        is_revoked=bool(payload.get("is_revoked", False)),
    )


def _meta_rows_to_map(rows: Any) -> dict[str, object]:
    if not isinstance(rows, list):
        return {}
    out: dict[str, object] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get("key")
        if not isinstance(key, str) or not key:
            continue
        out[key] = row.get("value")
    return out


def _encode_entity_ref(
    schema_ir: dict[str, Any],
    *,
    entity_type: str,
    identity: dict[str, object],
) -> str:
    return encode_entity_ref(schema_ir, entity_type=entity_type, identity=identity)


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string")
    return value
