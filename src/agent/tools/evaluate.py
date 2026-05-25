from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from ..candidate_cache import CandidatePayloadCache
from ..errors import AgentContractError, AgentRuntimeError
from ..session import AgentSession
from ._runtime_api import RuntimeAPI, require_ok
from .explain import ExplainTools


@dataclass(frozen=True)
class EvaluateRequest:
    """Structured runtime evaluate request body."""

    inference: dict[str, Any]
    engine: str = "native"
    limit: int | None = None

    def to_dto(self) -> dict[str, Any]:
        dto: dict[str, Any] = {"engine": self.engine, "inference": dict(self.inference)}
        if self.limit is not None:
            dto["limit"] = int(self.limit)
        return dto


@dataclass(frozen=True)
class EvaluateResult:
    inference_id: str
    version: str
    target_pred_id: str
    result_id: str
    run_id: str
    mode: str
    row_count: int
    returned_count: int
    truncated: bool
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class CandidateReviewItem:
    candidate_id: str
    pred_id: str
    payload: dict[str, Any]
    summary: dict[str, Any] | None = None
    steps: list[dict[str, Any]] | None = None
    cache_status: Literal["active", "stale", "missing"] = "active"


@dataclass(frozen=True)
class AcceptRequest:
    candidate: dict[str, Any]
    dry_run: bool = False

    def to_dto(self) -> dict[str, Any]:
        return {
            "candidate": dict(self.candidate),
            "options": {"dry_run": self.dry_run},
        }


@dataclass(frozen=True)
class AcceptResult:
    candidate_id: str
    dry_run: bool
    terminal: bool
    accept_detail: dict[str, Any]


@dataclass(frozen=True)
class CacheRecoveryOutcome:
    candidate_id: str
    status: Literal["stale", "missing"]
    message: str
    stale_runtime_session_id: str | None = None
    action_required: str = "re-evaluate"


class EvaluateTools:
    """Agent-side evaluate/review/accept loop over runtime derivations."""

    def __init__(
        self,
        *,
        runtime_api: RuntimeAPI,
        candidate_cache: CandidatePayloadCache,
        explain_tools: ExplainTools,
        session: AgentSession,
    ) -> None:
        self._runtime = runtime_api
        self._candidate_cache = candidate_cache
        self._explain_tools = explain_tools
        self._session = session

    @property
    def runtime_api(self) -> RuntimeAPI:
        return self._runtime

    @property
    def session(self) -> AgentSession:
        return self._session

    @property
    def _runtime_session_id(self) -> str:
        runtime_session_id = self._session.runtime_session_id
        if not isinstance(runtime_session_id, str) or not runtime_session_id:
            raise AgentRuntimeError(
                "AgentSession is not bound to a runtime session",
                kind="runtime_session_missing",
            )
        return runtime_session_id

    @property
    def _agent_session_id(self) -> str:
        return self._session.agent_session_id

    def evaluate(self, request: EvaluateRequest) -> EvaluateResult:
        if not isinstance(request, EvaluateRequest):
            raise AgentContractError("request must be EvaluateRequest")
        response = require_ok(
            self._runtime.evaluate_derivation(self._runtime_session_id, request.to_dto())
        )
        meta = _require_dict(response.get("meta"), "meta")
        evaluation = _require_dict(response.get("evaluation"), "evaluation")
        rows = _require_list_of_dicts(evaluation.get("rows"), "evaluation.rows")
        return EvaluateResult(
            inference_id=_require_non_empty_str(evaluation.get("inference_id"), "evaluation.inference_id"),
            version=_require_non_empty_str(evaluation.get("version"), "evaluation.version"),
            target_pred_id=_require_non_empty_str(
                evaluation.get("target_pred_id"),
                "evaluation.target_pred_id",
            ),
            result_id=_require_non_empty_str(evaluation.get("result_id"), "evaluation.result_id"),
            run_id=_require_non_empty_str(evaluation.get("run_id"), "evaluation.run_id"),
            mode=_require_non_empty_str(meta.get("mode"), "meta.mode"),
            row_count=_require_int(meta.get("row_count"), "meta.row_count"),
            returned_count=_require_int(meta.get("returned_count"), "meta.returned_count"),
            truncated=_require_bool(meta.get("truncated"), "meta.truncated"),
            rows=[dict(row) for row in rows],
        )

    def review_candidate(
        self,
        candidate_id: str,
        *,
        include_steps: bool = True,
        include_summary: bool = True,
    ) -> CandidateReviewItem | CacheRecoveryOutcome:
        candidate_payload, recovery = self._lookup_candidate(candidate_id)
        if recovery is not None:
            return recovery
        assert candidate_payload is not None
        summary_payload: dict[str, Any] | None = None
        if include_summary:
            summary_payload = self._explain_tools.get_summary(
                self._runtime_session_id,
                candidate_id,
            ).summary
        steps_payload: list[dict[str, Any]] | None = None
        if include_steps:
            steps_payload = [
                asdict(step)
                for step in self._explain_tools.get_steps(
                    self._runtime_session_id,
                    candidate_id,
                )
            ]
        return CandidateReviewItem(
            candidate_id=candidate_id,
            pred_id=_candidate_pred_id(candidate_payload),
            payload=dict(candidate_payload),
            summary=summary_payload,
            steps=steps_payload,
            cache_status="active",
        )

    def review_all(
        self,
        *,
        include_steps: bool = False,
        include_summary: bool = True,
    ) -> list[CandidateReviewItem | CacheRecoveryOutcome]:
        active_candidates = self._candidate_cache.lookup_active_by_runtime(self._runtime_session_id)
        out: list[CandidateReviewItem | CacheRecoveryOutcome] = []
        for candidate in active_candidates:
            candidate_id = _require_non_empty_str(candidate.get("candidate_id"), "candidate_id")
            out.append(
                self.review_candidate(
                    candidate_id,
                    include_steps=include_steps,
                    include_summary=include_summary,
                )
            )
        return out

    def accept_candidate(
        self,
        candidate_id: str,
        *,
        dry_run: bool = False,
    ) -> AcceptResult | CacheRecoveryOutcome:
        candidate_payload, recovery = self._lookup_candidate(candidate_id)
        if recovery is not None:
            return recovery
        assert candidate_payload is not None
        request = AcceptRequest(candidate=dict(candidate_payload), dry_run=dry_run)
        response = require_ok(
            self._runtime.accept_derivation(self._runtime_session_id, request.to_dto())
        )
        meta = _require_dict(response.get("meta"), "meta")
        accept = _require_dict(response.get("accept"), "accept")
        return AcceptResult(
            candidate_id=candidate_id,
            dry_run=_require_bool(meta.get("dry_run"), "meta.dry_run"),
            terminal=_require_bool(meta.get("terminal"), "meta.terminal"),
            accept_detail=accept,
        )

    def accept_many(
        self,
        candidate_ids: list[str],
        *,
        dry_run: bool = False,
    ) -> list[AcceptResult | CacheRecoveryOutcome]:
        if not isinstance(candidate_ids, list):
            raise AgentContractError("candidate_ids must be list")
        return [
            self.accept_candidate(
                _require_non_empty_str(candidate_id, "candidate_id"),
                dry_run=dry_run,
            )
            for candidate_id in candidate_ids
        ]

    def _lookup_candidate(
        self,
        candidate_id: str,
    ) -> tuple[dict[str, Any] | None, CacheRecoveryOutcome | None]:
        candidate_id = _require_non_empty_str(candidate_id, "candidate_id")
        active = self._candidate_cache.lookup_active(self._runtime_session_id, candidate_id)
        if active is not None:
            return active, None
        for stale in self._candidate_cache.list_stale(
            self._agent_session_id,
            self._runtime_session_id,
        ):
            if stale.get("candidate_id") == candidate_id:
                return None, CacheRecoveryOutcome(
                    candidate_id=candidate_id,
                    status="stale",
                    message=(
                        "candidate belongs to a stale runtime session and must be re-evaluated"
                    ),
                    stale_runtime_session_id=_optional_non_empty_str(
                        stale.get("runtime_session_id"),
                        "stale.runtime_session_id",
                    ),
                )
        return None, CacheRecoveryOutcome(
            candidate_id=candidate_id,
            status="missing",
            message="candidate payload not found in cache; re-evaluate first",
        )


def _candidate_pred_id(candidate_payload: dict[str, Any]) -> str:
    return _require_non_empty_str(candidate_payload.get("target"), "candidate.target")


def _require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentContractError(f"{name} must be object")
    return dict(value)


def _require_list_of_dicts(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise AgentContractError(f"{name} must be list")
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise AgentContractError(f"{name} entries must be objects")
        out.append(dict(item))
    return out


def _require_non_empty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string")
    return value


def _optional_non_empty_str(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise AgentContractError(f"{name} must be non-empty string when provided")
    return value


def _require_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AgentContractError(f"{name} must be int")
    return value


def _require_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise AgentContractError(f"{name} must be bool")
    return value
