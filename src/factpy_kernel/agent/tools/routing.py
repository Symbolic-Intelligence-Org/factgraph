from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..errors import AgentContractError, AgentRuntimeError
from ..session import AgentSession
from ._runtime_api import RuntimeAPI, require_ok

if TYPE_CHECKING:
    from .rules import RuleSpec


_VALID_ENGINES = frozenset({"native", "souffle", "problog", "pyreason"})

SUPPORT_KIND_TO_ENGINE: dict[str, str | None] = {
    "native_binding_v1": "native",
    "souffle_witness_v1": "souffle",
    "problog_provenance_v1": "problog",
    "pyreason_provenance_v1": "pyreason",
    "engine_no_witness_v1": None,
}


@dataclass(frozen=True)
class EngineRoutingHint:
    suggested_engine: str | None = None
    reason: str = ""
    source: str = "unspecified"
    overrideable: bool = True
    confidence: float = 0.0


@dataclass(frozen=True)
class ConsistencyWarning:
    message: str
    pred_id: str
    historical_engine: str
    suggested_engine: str


class EngineRoutingAdvisor:
    """Conservative engine recommendation over current runtime/session surfaces."""

    def __init__(self, *, runtime_api: RuntimeAPI, session: AgentSession) -> None:
        if not isinstance(session, AgentSession):
            raise AgentContractError("session must be AgentSession")
        self._runtime = runtime_api
        self._session = session

    @property
    def _runtime_session_id(self) -> str:
        runtime_session_id = self._session.runtime_session_id
        if not isinstance(runtime_session_id, str) or not runtime_session_id:
            raise AgentRuntimeError(
                "AgentSession is not bound to a runtime session",
                kind="runtime_session_missing",
            )
        return runtime_session_id

    def recommend_for_rule(self, spec: RuleSpec) -> EngineRoutingHint:
        explicit_hint = getattr(spec, "routing_hint", None)
        if isinstance(explicit_hint, EngineRoutingHint) and explicit_hint.suggested_engine:
            engine = _normalize_engine_name(explicit_hint.suggested_engine)
            if engine is None:
                raise AgentContractError("routing_hint.suggested_engine must be valid engine name")
            return EngineRoutingHint(
                suggested_engine=engine,
                reason=explicit_hint.reason,
                source="explicit",
                overrideable=explicit_hint.overrideable,
                confidence=explicit_hint.confidence,
            )

        tag_hint = _hint_from_tags(getattr(spec, "tags", None))
        if tag_hint is not None:
            return tag_hint

        key = (_require_non_empty_str(getattr(spec, "rule_id", None), "rule_id"), _require_non_empty_str(getattr(spec, "version", None), "version"))
        if key in self._ephemeral_rule_keys():
            return EngineRoutingHint(
                suggested_engine="native",
                reason="rule is already registered as an ephemeral rule; native only",
                source="heuristic",
                overrideable=False,
                confidence=1.0,
            )

        return EngineRoutingHint(
            suggested_engine="native",
            reason="no routing signal detected; defaulting to native",
            source="heuristic",
            overrideable=True,
            confidence=0.3,
        )

    def recommend_for_evaluate(self, derivation: dict[str, Any]) -> EngineRoutingHint:
        if not isinstance(derivation, dict):
            raise AgentContractError("derivation must be object")
        mode = _normalize_engine_name(derivation.get("mode"))
        if mode is not None:
            return EngineRoutingHint(
                suggested_engine=mode,
                reason=f"derivation.mode explicitly set to {mode}",
                source="explicit",
                overrideable=True,
                confidence=1.0,
            )

        ephemeral_keys = self._ephemeral_rule_keys()
        for rule_id, version in _find_ruleref_atoms(derivation.get("where")):
            if (rule_id, version) in ephemeral_keys:
                return EngineRoutingHint(
                    suggested_engine="native",
                    reason="ruleref references an ephemeral rule; native only",
                    source="heuristic",
                    overrideable=False,
                    confidence=1.0,
                )

        return EngineRoutingHint(
            suggested_engine="native",
            reason="no routing signal detected; defaulting to native",
            source="heuristic",
            overrideable=True,
            confidence=0.3,
        )

    def check_consistency(
        self,
        pred_id: str,
        suggested_engine: str,
    ) -> ConsistencyWarning | None:
        pred_id = _require_non_empty_str(pred_id, "pred_id")
        engine = _normalize_engine_name(suggested_engine)
        if engine is None:
            return None

        response = require_ok(
            self._runtime.list_candidates(
                self._runtime_session_id,
                pred_id_filter=pred_id,
            )
        )
        result = _require_dict(response.get("result"), "result")
        raw_candidates = result.get("candidates", [])
        if not isinstance(raw_candidates, list):
            raise AgentContractError("result.candidates must be list")

        historical: set[str] = set()
        for item in raw_candidates:
            entry = _require_dict(item, "result.candidates[]")
            support_kind = entry.get("support_kind")
            if not isinstance(support_kind, str) or not support_kind:
                continue
            historical_engine = SUPPORT_KIND_TO_ENGINE.get(support_kind)
            if historical_engine is not None:
                historical.add(historical_engine)

        if not historical or engine in historical:
            return None

        historical_engine = ", ".join(sorted(historical))
        return ConsistencyWarning(
            message=(
                f"historical candidates for {pred_id} used {historical_engine}, "
                f"but suggested engine is {engine}"
            ),
            pred_id=pred_id,
            historical_engine=historical_engine,
            suggested_engine=engine,
        )

    def _ephemeral_rule_keys(self) -> set[tuple[str, str]]:
        response = require_ok(self._runtime.list_ephemeral_rules(self._runtime_session_id))
        result = _require_dict(response.get("result"), "result")
        raw_rules = result.get("ephemeral_rules", [])
        if not isinstance(raw_rules, list):
            raise AgentContractError("result.ephemeral_rules must be list")
        out: set[tuple[str, str]] = set()
        for item in raw_rules:
            entry = _require_dict(item, "result.ephemeral_rules[]")
            out.add(
                (
                    _require_non_empty_str(entry.get("rule_id"), "rule_id"),
                    _require_non_empty_str(entry.get("version"), "version"),
                )
            )
        return out


def _find_ruleref_atoms(node: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def _walk(value: Any) -> None:
        if isinstance(value, (list, tuple)) and value:
            head = value[0]
            if head == "ruleref" and len(value) >= 3:
                rule_id = value[1]
                version = value[2]
                if isinstance(rule_id, str) and rule_id and isinstance(version, str) and version:
                    out.append((rule_id, version))
                return
            for child in value:
                _walk(child)

    _walk(node)
    return out


def _hint_from_tags(tags: Any) -> EngineRoutingHint | None:
    if not isinstance(tags, list):
        return None
    for tag in tags:
        if not isinstance(tag, str):
            continue
        if not tag.startswith("engine:"):
            continue
        engine = _normalize_engine_name(tag.split(":", 1)[1])
        if engine is None:
            continue
        return EngineRoutingHint(
            suggested_engine=engine,
            reason=f"tag {tag}",
            source="tag",
            overrideable=True,
            confidence=1.0,
        )
    return None


def _normalize_engine_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in _VALID_ENGINES:
        return normalized
    return None


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentContractError(f"{name} must be object")
    return dict(value)


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string")
    return value
