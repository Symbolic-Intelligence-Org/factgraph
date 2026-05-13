from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping


def _normalize_binding_items(binding: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    if not isinstance(binding, dict):
        raise ValueError("binding must be dict[str, Any]")
    items: list[tuple[str, Any]] = []
    for key, value in binding.items():
        if not isinstance(key, str) or not key.startswith("$"):
            raise ValueError("binding keys must be variable names prefixed with '$'")
        items.append((key, value))
    return tuple(sorted(items, key=lambda item: item[0]))


def _normalize_asrt_ids(asrt_ids: list[str]) -> tuple[str, ...]:
    out = sorted({asrt_id for asrt_id in asrt_ids if isinstance(asrt_id, str) and asrt_id})
    return tuple(out)


def _normalize_detail_items(details: dict[str, Any] | list[tuple[str, Any]]) -> tuple[tuple[str, Any], ...]:
    if isinstance(details, dict):
        items = list(details.items())
    elif isinstance(details, list):
        items = list(details)
    else:
        raise ValueError("details must be dict[str, Any] or list[tuple[str, Any]]")
    out: list[tuple[str, Any]] = []
    for key, value in items:
        if not isinstance(key, str) or not key:
            raise ValueError("detail keys must be non-empty strings")
        out.append((key, value))
    return tuple(sorted(out, key=lambda item: item[0]))


@dataclass(frozen=True)
class RuleTracePredWitness:
    binding_index: int
    pred_atom_key: str
    asrt_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.binding_index, int) or self.binding_index < 0:
            raise ValueError("binding_index must be non-negative int")
        if not isinstance(self.pred_atom_key, str) or not self.pred_atom_key:
            raise ValueError("pred_atom_key must be non-empty string")
        if self.asrt_ids != _normalize_asrt_ids(list(self.asrt_ids)):
            raise ValueError("asrt_ids must be sorted unique non-empty strings")


@dataclass(frozen=True)
class RuleTraceNonFactStep:
    binding_index: int
    step_key: str
    kind: str
    status: str
    details: tuple[tuple[str, Any], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.binding_index, int) or self.binding_index < 0:
            raise ValueError("binding_index must be non-negative int")
        if not isinstance(self.step_key, str) or not self.step_key:
            raise ValueError("step_key must be non-empty string")
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("kind must be non-empty string")
        if not isinstance(self.status, str) or not self.status:
            raise ValueError("status must be non-empty string")
        if self.details != _normalize_detail_items(list(self.details)):
            raise ValueError("details must be sorted detail tuples")


@dataclass(frozen=True)
class RuleTraceRuleRefLink:
    ruleref_atom_key: str
    child_invocation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.ruleref_atom_key, str) or not self.ruleref_atom_key:
            raise ValueError("ruleref_atom_key must be non-empty string")
        if not isinstance(self.child_invocation_id, str) or not self.child_invocation_id:
            raise ValueError("child_invocation_id must be non-empty string")


@dataclass(frozen=True)
class RuleTraceInvocation:
    invocation_id: str
    parent_invocation_id: str | None
    rule_id: str
    version: str
    memo_hit: bool
    memo_source_invocation_id: str | None
    original_where: Any
    rewritten_where: Any
    bindings: tuple[tuple[tuple[str, Any], ...], ...]
    output_rows: tuple[tuple[Any, ...], ...]
    pred_witnesses: tuple[RuleTracePredWitness, ...] = ()
    non_fact_steps: tuple[RuleTraceNonFactStep, ...] = ()
    ruleref_links: tuple[RuleTraceRuleRefLink, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.invocation_id, str) or not self.invocation_id:
            raise ValueError("invocation_id must be non-empty string")
        if self.parent_invocation_id is not None and (
            not isinstance(self.parent_invocation_id, str) or not self.parent_invocation_id
        ):
            raise ValueError("parent_invocation_id must be None or non-empty string")
        if not isinstance(self.rule_id, str) or not self.rule_id:
            raise ValueError("rule_id must be non-empty string")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be non-empty string")
        if not isinstance(self.memo_hit, bool):
            raise ValueError("memo_hit must be bool")
        if self.memo_source_invocation_id is not None and (
            not isinstance(self.memo_source_invocation_id, str) or not self.memo_source_invocation_id
        ):
            raise ValueError("memo_source_invocation_id must be None or non-empty string")
        if self.bindings != tuple(_normalize_binding_items(dict(binding)) for binding in self.bindings):
            raise ValueError("bindings must be sorted binding tuples")
        if self.pred_witnesses != tuple(
            sorted(self.pred_witnesses, key=lambda item: (item.binding_index, item.pred_atom_key))
        ):
            raise ValueError("pred_witnesses must be sorted by binding_index and pred_atom_key")
        if self.non_fact_steps != tuple(
            sorted(self.non_fact_steps, key=lambda item: (item.binding_index, item.step_key))
        ):
            raise ValueError("non_fact_steps must be sorted by binding_index and step_key")
        if self.ruleref_links != tuple(
            sorted(self.ruleref_links, key=lambda item: item.ruleref_atom_key)
        ):
            raise ValueError("ruleref_links must be sorted by ruleref_atom_key")


@dataclass(frozen=True)
class RuleTraceArtifact:
    rule_run_id: str
    root_rule_id: str
    root_version: str
    select_vars: tuple[str, ...]
    invocations: tuple[RuleTraceInvocation, ...]
    root_rows: tuple[tuple[Any, ...], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rule_run_id, str) or not self.rule_run_id:
            raise ValueError("rule_run_id must be non-empty string")
        if not isinstance(self.root_rule_id, str) or not self.root_rule_id:
            raise ValueError("root_rule_id must be non-empty string")
        if not isinstance(self.root_version, str) or not self.root_version:
            raise ValueError("root_version must be non-empty string")
        if not self.select_vars or any(not isinstance(var, str) or not var.startswith("$") for var in self.select_vars):
            raise ValueError("select_vars must be non-empty '$'-prefixed variable names")


@dataclass(frozen=True)
class RuleRunResult:
    rule_run_id: str
    rows: list[tuple[Any, ...]]

    def __post_init__(self) -> None:
        if not isinstance(self.rule_run_id, str) or not self.rule_run_id:
            raise ValueError("rule_run_id must be non-empty string")
        if not isinstance(self.rows, list):
            raise ValueError("rows must be list[tuple[Any, ...]]")


@dataclass
class RuleTraceCaptureContext:
    rule_run_id: str
    invocations: list[RuleTraceInvocation] = field(default_factory=list)
    primary_invocation_by_rule_key: dict[tuple[str, str], str] = field(default_factory=dict)
    invocation_by_id: dict[str, RuleTraceInvocation] = field(default_factory=dict)
    _next_invocation_ordinal: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.rule_run_id, str) or not self.rule_run_id:
            raise ValueError("rule_run_id must be non-empty string")

    def next_invocation_id(self) -> str:
        invocation_id = f"{self.rule_run_id}:i{self._next_invocation_ordinal}"
        self._next_invocation_ordinal += 1
        return invocation_id

    def append_invocation(
        self,
        invocation: RuleTraceInvocation,
        *,
        primary_key: tuple[str, str] | None = None,
    ) -> None:
        self.invocations.append(invocation)
        self.invocation_by_id[invocation.invocation_id] = invocation
        if primary_key is not None and primary_key not in self.primary_invocation_by_rule_key:
            self.primary_invocation_by_rule_key[primary_key] = invocation.invocation_id


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return {"__bytes_hex__": value.hex()}
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value


def _from_jsonable(value: Any) -> Any:
    if isinstance(value, dict) and tuple(value.keys()) == ("__bytes_hex__",):
        return bytes.fromhex(value["__bytes_hex__"])
    if isinstance(value, list):
        return [_from_jsonable(item) for item in value]
    return value


_LEGACY_STATUS_MAP: dict[str, str] = {
    "no_match": "negated",
    "satisfied": "evaluated",
}


def _normalize_non_fact_status(status: str) -> str:
    return _LEGACY_STATUS_MAP.get(status, status)


class RuleTraceSummaryError(ValueError):
    def __init__(self, message: str, *, path: str) -> None:
        super().__init__(message)
        self.kind = "runtime"
        self.path = path
        self.details = {"message": message}


def _require_summary_non_empty_str(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuleTraceSummaryError("must be non-empty string", path=path)
    return value


def rule_trace_artifact_to_dict(artifact: RuleTraceArtifact) -> dict[str, Any]:
    if not isinstance(artifact, RuleTraceArtifact):
        raise ValueError("artifact must be RuleTraceArtifact")
    return {
        "rule_run_id": artifact.rule_run_id,
        "root_rule": {"rule_id": artifact.root_rule_id, "version": artifact.root_version},
        "select_vars": list(artifact.select_vars),
        "invocations": [
            {
                "invocation_id": invocation.invocation_id,
                "parent_invocation_id": invocation.parent_invocation_id,
                "rule": {"rule_id": invocation.rule_id, "version": invocation.version},
                "memo_hit": invocation.memo_hit,
                "memo_source_invocation_id": invocation.memo_source_invocation_id,
                "original_where": _to_jsonable(invocation.original_where),
                "rewritten_where": _to_jsonable(invocation.rewritten_where),
                "bindings": [
                    [[key, _to_jsonable(value)] for key, value in binding]
                    for binding in invocation.bindings
                ],
                "output_rows": [[_to_jsonable(item) for item in row] for row in invocation.output_rows],
                "pred_witnesses": [
                    {
                        "binding_index": witness.binding_index,
                        "pred_atom_key": witness.pred_atom_key,
                        "asrt_ids": list(witness.asrt_ids),
                    }
                    for witness in invocation.pred_witnesses
                ],
                "non_fact_steps": [
                    {
                        "binding_index": step.binding_index,
                        "step_key": step.step_key,
                        "kind": step.kind,
                        "status": step.status,
                        "details": [[key, _to_jsonable(value)] for key, value in step.details],
                    }
                    for step in invocation.non_fact_steps
                ],
                "ruleref_links": [
                    {
                        "ruleref_atom_key": link.ruleref_atom_key,
                        "child_invocation_id": link.child_invocation_id,
                    }
                    for link in invocation.ruleref_links
                ],
            }
            for invocation in artifact.invocations
        ],
        "root_rows": [[_to_jsonable(item) for item in row] for row in artifact.root_rows],
    }


def rule_trace_artifact_bytes(artifact: RuleTraceArtifact) -> bytes:
    return json.dumps(
        rule_trace_artifact_to_dict(artifact),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def rule_trace_artifact_from_dict(row: Mapping[str, Any]) -> RuleTraceArtifact:
    if not isinstance(row, Mapping):
        raise ValueError("row must be Mapping[str, Any]")
    root_rule = row["root_rule"]
    return RuleTraceArtifact(
        rule_run_id=row["rule_run_id"],
        root_rule_id=root_rule["rule_id"],
        root_version=root_rule["version"],
        select_vars=tuple(row["select_vars"]),
        invocations=tuple(_rule_trace_invocation_from_dict(item) for item in row["invocations"]),
        root_rows=tuple(tuple(_from_jsonable(item) for item in output_row) for output_row in row["root_rows"]),
    )


def _rule_trace_invocation_from_dict(row: Mapping[str, Any]) -> RuleTraceInvocation:
    rule = row["rule"]
    return RuleTraceInvocation(
        invocation_id=row["invocation_id"],
        parent_invocation_id=row["parent_invocation_id"],
        rule_id=rule["rule_id"],
        version=rule["version"],
        memo_hit=row["memo_hit"],
        memo_source_invocation_id=row["memo_source_invocation_id"],
        original_where=row["original_where"],
        rewritten_where=row["rewritten_where"],
        bindings=tuple(
            tuple((key, _from_jsonable(value)) for key, value in binding)
            for binding in row["bindings"]
        ),
        output_rows=tuple(
            tuple(_from_jsonable(item) for item in output_row)
            for output_row in row["output_rows"]
        ),
        pred_witnesses=tuple(
            RuleTracePredWitness(
                binding_index=item["binding_index"],
                pred_atom_key=item["pred_atom_key"],
                asrt_ids=tuple(item["asrt_ids"]),
            )
            for item in row.get("pred_witnesses", ())
        ),
        non_fact_steps=tuple(
            RuleTraceNonFactStep(
                binding_index=item["binding_index"],
                step_key=item["step_key"],
                kind=item["kind"],
                status=_normalize_non_fact_status(item["status"]),
                details=tuple((key, _from_jsonable(value)) for key, value in item["details"]),
            )
            for item in row.get("non_fact_steps", ())
        ),
        ruleref_links=tuple(
            RuleTraceRuleRefLink(
                ruleref_atom_key=link["ruleref_atom_key"],
                child_invocation_id=link["child_invocation_id"],
            )
            for link in row.get("ruleref_links", ())
        ),
    )


def summarize_rule_trace_artifact_dict(explain: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(explain, Mapping):
        raise RuleTraceSummaryError("explain must be object", path="$.explain")

    rule_run_id = _require_summary_non_empty_str(explain.get("rule_run_id"), path="$.explain.rule_run_id")
    root_rule = explain.get("root_rule")
    if not isinstance(root_rule, Mapping):
        raise RuleTraceSummaryError("root_rule must be object", path="$.explain.root_rule")
    invocations = explain.get("invocations")
    if not isinstance(invocations, list):
        raise RuleTraceSummaryError("invocations must be list", path="$.explain.invocations")
    root_rows = explain.get("root_rows")
    if not isinstance(root_rows, list):
        raise RuleTraceSummaryError("root_rows must be list", path="$.explain.root_rows")

    witness_assertion_ids: set[str] = set()
    predicate_witness_groups: dict[str, dict[str, Any]] = {}
    non_fact_step_groups: dict[str, dict[str, Any]] = {}

    for invocation in invocations:
        if not isinstance(invocation, Mapping):
            raise RuleTraceSummaryError("invocation row must be object", path="$.explain.invocations[]")
        invocation_id = _require_summary_non_empty_str(
            invocation.get("invocation_id"),
            path="$.explain.invocations[].invocation_id",
        )
        pred_witnesses = invocation.get("pred_witnesses")
        if isinstance(pred_witnesses, list):
            for witness in pred_witnesses:
                if not isinstance(witness, Mapping):
                    raise RuleTraceSummaryError(
                        "pred_witness row must be object",
                        path="$.explain.invocations[].pred_witnesses[]",
                    )
                pred_atom_key = _require_summary_non_empty_str(
                    witness.get("pred_atom_key"),
                    path="$.explain.invocations[].pred_witnesses[].pred_atom_key",
                )
                pred_id = _pred_id_from_pred_atom_key(pred_atom_key)
                group = predicate_witness_groups.setdefault(
                    pred_id,
                    {"pred_id": pred_id, "asrt_ids": set(), "invocation_ids": set()},
                )
                group["invocation_ids"].add(invocation_id)
                asrt_ids = witness.get("asrt_ids")
                if isinstance(asrt_ids, list):
                    for asrt_id in asrt_ids:
                        if isinstance(asrt_id, str) and asrt_id:
                            witness_assertion_ids.add(asrt_id)
                            group["asrt_ids"].add(asrt_id)

        non_fact_steps = invocation.get("non_fact_steps")
        if isinstance(non_fact_steps, list):
            for step in non_fact_steps:
                if not isinstance(step, Mapping):
                    raise RuleTraceSummaryError(
                        "non_fact_step row must be object",
                        path="$.explain.invocations[].non_fact_steps[]",
                    )
                kind = _require_summary_non_empty_str(
                    step.get("kind"),
                    path="$.explain.invocations[].non_fact_steps[].kind",
                )
                group = non_fact_step_groups.setdefault(
                    kind,
                    {"kind": kind, "count": 0, "invocation_ids": set()},
                )
                group["count"] += 1
                group["invocation_ids"].add(invocation_id)

    return {
        "rule_run_id": rule_run_id,
        "root_rule": {
            "rule_id": root_rule.get("rule_id"),
            "version": root_rule.get("version"),
        },
        "root_row_count": len(root_rows),
        "invocation_count": len(invocations),
        "witness_assertion_ids": sorted(witness_assertion_ids),
        "predicate_witness_groups": [
            {
                "pred_id": pred_id,
                "asrt_ids": sorted(group["asrt_ids"]),
                "invocation_ids": sorted(group["invocation_ids"]),
            }
            for pred_id, group in sorted(predicate_witness_groups.items())
        ],
        "non_fact_step_groups": [
            {
                "kind": kind,
                "count": int(group["count"]),
                "invocation_ids": sorted(group["invocation_ids"]),
            }
            for kind, group in sorted(non_fact_step_groups.items())
        ],
    }


def _pred_id_from_pred_atom_key(pred_atom_key: str) -> str:
    if ":" not in pred_atom_key:
        return pred_atom_key
    return pred_atom_key.split(":", 1)[1]


__all__ = [
    "RuleRunResult",
    "RuleTraceArtifact",
    "RuleTraceCaptureContext",
    "RuleTraceInvocation",
    "RuleTraceNonFactStep",
    "RuleTracePredWitness",
    "RuleTraceRuleRefLink",
    "RuleTraceSummaryError",
    "rule_trace_artifact_bytes",
    "rule_trace_artifact_from_dict",
    "rule_trace_artifact_to_dict",
    "summarize_rule_trace_artifact_dict",
]
