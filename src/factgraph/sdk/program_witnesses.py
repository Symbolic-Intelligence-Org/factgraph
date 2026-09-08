"""Result-local native witness capture; never a Store query or a permission.

The evaluation owns a temporary origin inventory. Only the successful support
closure is sealed into a report; original receipts and their digests are untouched.
The immutable encoding is also the ownership boundary for nested caller data.
"""

from __future__ import annotations

import base64
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from factgraph.application.explain import (
    EvidenceGraph,
    evidence_graph_from_dict,
    evidence_graph_to_dict,
)
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.protocol.tup_v1 import claim_args_from_rest_terms
from factgraph.core.store._support import (
    _to_jsonable,
    compute_support_digest,
    support_artifact_from_dict,
    support_artifact_to_dict,
)

RULE_PROGRAM_WITNESS_CONTRACT_V1 = "factgraph.rule-program-witness-report.v1"


class RuleProgramWitnessError(ValueError):
    """Invalid capture is an error, not unavailable material or failed entailment."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _json_value(value: Any) -> Any:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, Mapping) and all(isinstance(key, str) for key in value):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise RuleProgramWitnessError(
        "invalid_capture_shape", "Capture requires finite JSON values and string keys"
    )


def _encode(value: Any) -> bytes:
    try:
        return json.dumps(
            _json_value(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        if isinstance(exc, RuleProgramWitnessError):
            raise
        raise RuleProgramWitnessError(
            "invalid_capture_shape", "Capture is not canonical UTF-8 JSON"
        ) from exc


def _digest(value: Any) -> str:
    return sha256_token(_encode(value))


@dataclass(frozen=True)
class RuleProgramWitnessReportV1:
    """Sealed report value. Projections are detached; no live dependencies."""

    _encoded: bytes

    def __post_init__(self) -> None:
        try:
            payload = json.loads(self._encoded, object_pairs_hook=_unique_object)
            _validate_report(payload)
            object.__setattr__(self, "_encoded", _encode(payload))
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            if isinstance(exc, RuleProgramWitnessError):
                raise
            raise RuleProgramWitnessError(
                "invalid_capture_shape", "Invalid native witness report"
            ) from exc

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RuleProgramWitnessReportV1:
        """Validate a complete detached report including original graph links."""
        return cls(_encode(payload))

    @classmethod
    def from_json(cls, payload: bytes | str) -> RuleProgramWitnessReportV1:
        """Decode a closed V1 report; duplicate JSON keys are invalid."""
        try:
            return cls(payload.encode("utf-8") if isinstance(payload, str) else payload)
        except UnicodeError as exc:
            raise RuleProgramWitnessError("invalid_capture_shape", "Capture is not UTF-8") from exc

    def to_json(self) -> bytes:
        """Return immutable canonical UTF-8 bytes."""
        return self._encoded

    @property
    def evidence(self) -> EvidenceGraph:
        """Return detached original evidence, restoring canonical binary leaves."""
        return evidence_graph_from_dict(_evidence_values(self.to_dict()["evidence"]))

    @property
    def report_digest(self) -> str:
        """Integrity seal, not authenticity or authorization."""
        return str(self.to_dict()["report_digest"])

    @property
    def status(self) -> str:
        """Whether the original successful support closure was fully captured."""
        return str(self.to_dict()["status"])

    def to_dict(self) -> dict[str, Any]:
        """Return a detached complete canonical JSON projection."""
        return dict(json.loads(self._encoded))


class ProgramWitnessCapture:
    """Private, evaluation-local origin inventory; never persisted wholesale."""

    def __init__(self, schema: dict[str, Any], projected: dict[str, list[Any]]) -> None:
        self._specs = {row["pred_id"]: row["arg_specs"] for row in schema["predicates"]}
        self._origins: dict[str, dict[str, Any]] = {}
        self._links: dict[str, list[dict[str, str]]] = {}
        for predicate, rows in projected.items():
            for row in rows:
                self._add(row.asrt_id, predicate, row.fact_tuple, row.witness_kind, None)

    def _terms(self, predicate: str, terms: tuple[Any, ...]) -> list[dict[str, Any]]:
        specs = self._specs.get(predicate, ())
        if len(specs) != len(terms):
            raise RuleProgramWitnessError(
                "invalid_capture_shape", "Captured predicate arity is unknown"
            )
        try:
            values = claim_args_from_rest_terms(
                [
                    (spec["type_domain"], _raw_value(spec["type_domain"], term))
                    for spec, term in zip(specs, terms)
                ]
            )
        except (TypeError, ValueError) as exc:
            raise RuleProgramWitnessError(
                "invalid_capture_shape", "Captured term is not canonical typed material"
            ) from exc
        return [{"tag": tag, "value": value} for _, value, tag in values]

    def _add(
        self, ref: str, predicate: str, terms: tuple[Any, ...], kind: str, provenance: Any
    ) -> None:
        material = {
            "kind": kind,
            "predicate_id": predicate,
            "terms": self._terms(predicate, terms),
            "program_fact_provenance": _json_value(provenance),
        }
        previous = self._origins.get(ref)
        if previous is not None and _encode(previous) != _encode(material):
            raise RuleProgramWitnessError(
                "program_witness_ref_collision",
                "Selected witness ref has conflicting origin or material",
            )
        self._origins[ref] = material

    def program_inserted(self, fact: Any) -> None:
        """Record only an actual overlay insertion, after original tuple dedup."""
        self._add(fact.fact_id, fact.predicate, fact.terms, "program_fact", fact.provenance)

    def source_rendered(self, pointer: str, coordinates: list[dict[str, str]]) -> None:
        """Bind an exact source position while its receipt context is in hand."""
        if pointer in self._links:
            raise RuleProgramWitnessError(
                "invalid_source_link", "Duplicate rendered source position"
            )
        self._links[pointer] = coordinates

    def freeze(
        self,
        *,
        goal: Any,
        engine: str,
        rule_set_digest: str,
        view_snapshot_digest: str,
        premise_scope_digest: str,
        root_support_digest: str | None,
        steps: tuple[dict[str, Any], ...],
        evidence: Any,
    ) -> RuleProgramWitnessReportV1:
        items = []
        for step in steps:
            for witness in step["factgraph_explain"].get("pred_witnesses", ()):
                for ref in witness["asrt_ids"]:
                    origin = self._origins.get(
                        ref,
                        {
                            "kind": "unknown",
                            "predicate_id": None,
                            "terms": [],
                            "program_fact_provenance": None,
                        },
                    )
                    reason = "origin_not_captured" if origin["kind"] == "unknown" else None
                    items.append(
                        {
                            "support_digest": step["support_digest"],
                            "condition_key": witness["pred_condition_key"],
                            "witness_ref": ref,
                            **origin,
                            "availability": "unavailable" if reason else "available",
                            "reason": reason,
                        }
                    )
        # Reuse the original receipt's canonical binary-leaf JSON encoding;
        # this does not alter the original EvidenceGraph or support bytes.
        evidence_payload = _to_jsonable(evidence_graph_to_dict(evidence))
        links = [
            {
                "pointer": pointer,
                "status": "captured"
                if pointer in self._links
                else ("diagnostic_only" if root_support_digest is None else "not_captured"),
                "occurrences": self._links.get(pointer, []),
            }
            for pointer in sorted(_sources(evidence_payload))
        ]
        issues = _support_inventory(list(steps), root_support_digest)[1]
        partial = (
            bool(issues)
            or any(item["availability"] == "unavailable" for item in items)
            or any(link["status"] == "not_captured" for link in links)
        )
        payload = {
            "contract": RULE_PROGRAM_WITNESS_CONTRACT_V1,
            "capture_scope": "successful_support_closure",
            "availability_basis": "captured_evaluation",
            "goal": {"predicate": goal.predicate, "terms": self._terms(goal.predicate, goal.terms)},
            "engine": engine,
            "rule_set_digest": rule_set_digest,
            "view_snapshot_digest": view_snapshot_digest,
            "premise_scope_digest": premise_scope_digest,
            "root_support_digest": root_support_digest,
            "status": "not_applicable"
            if root_support_digest is None
            else ("partial" if partial else "complete"),
            "occurrences": sorted(
                items,
                key=lambda item: (
                    item["support_digest"],
                    item["condition_key"],
                    item["witness_ref"],
                ),
            ),
            "support_steps": steps,
            "support_graph_digest": _digest(steps),
            "evidence": evidence_payload,
            "evidence_digest": _digest(evidence_payload),
            "source_links": links,
            "issues": issues,
        }
        return RuleProgramWitnessReportV1(_encode({**payload, "report_digest": _digest(payload)}))


def _sources(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Enumerate canonical verdict source slots, never infer a witness origin."""
    found: dict[str, dict[str, Any]] = {}

    def walk(node: Any, pointer: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                child = pointer + "/" + key.replace("~", "~0").replace("/", "~1")
                if key == "support" and pointer.endswith("/verdict"):
                    for index, source in enumerate(value):
                        found[f"{child}/{index}"] = source
                else:
                    walk(value, child)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{pointer}/{index}")

    walk(evidence, "")
    return found


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuleProgramWitnessError("invalid_capture_shape", "Duplicate JSON key")
        result[key] = value
    return result


def _evidence_values(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"__bytes_hex__"}:
            raw = bytes.fromhex(value["__bytes_hex__"])
            _require(raw.hex() == value["__bytes_hex__"], "Noncanonical evidence binary leaf")
            return raw
        return {key: _evidence_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_evidence_values(item) for item in value]
    return value


def _require(condition: bool, message: str, code: str = "invalid_capture_shape") -> None:
    if not condition:
        raise RuleProgramWitnessError(code, message)


def _fields(row: Any, keys: str) -> None:
    _require(
        isinstance(row, dict) and set(row) == set(keys.split()), "Invalid closed capture fields"
    )


def _text(value: Any) -> None:
    _require(isinstance(value, str) and bool(value), "Expected nonempty capture text")


def _token(value: Any) -> None:
    _require(
        isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None,
        "Expected canonical capture digest",
    )


def _coordinate(item: dict[str, Any]) -> tuple[str, str, str]:
    _token(item["support_digest"])
    _text(item["condition_key"])
    _text(item["witness_ref"])
    return item["support_digest"], item["condition_key"], item["witness_ref"]


def _typed_terms(terms: Any) -> None:
    _require(isinstance(terms, list), "Typed terms must be a list")
    for term in terms:
        _fields(term, "tag value")
        tag, value = term["tag"], term["value"]
        raw = _raw_value(tag, value)
        normalized = claim_args_from_rest_terms([(tag, raw)])[0][1]
        _require(type(normalized) is type(value) and normalized == value, "Noncanonical typed term")


def _raw_value(tag: str, value: Any) -> Any:
    if tag != "bytes" or not isinstance(value, str):
        return value
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    _require(
        base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") == value,
        "Noncanonical bytes storage",
    )
    return raw


def _support_inventory(
    steps: list[dict[str, Any]], root: str | None
) -> tuple[set[tuple[str, str, str]], list[dict[str, str]]]:
    _require(isinstance(steps, list), "Support steps must be a list")
    by_digest: dict[str, dict[str, Any]] = {}
    coordinates: set[tuple[str, str, str]] = set()
    for step in steps:
        _fields(step, "support_digest child_support_digests factgraph_explain")
        digest = step["support_digest"]
        _token(digest)
        _require(digest not in by_digest, "Duplicate support step")
        by_digest[digest] = step
        receipt = step["factgraph_explain"]
        if not receipt:
            _require(
                receipt == {} and step["child_support_digests"] == [],
                "Invalid missing support marker",
            )
            continue
        try:
            artifact = support_artifact_from_dict(receipt)
        except (ValueError, TypeError, KeyError) as exc:
            raise RuleProgramWitnessError("invalid_support_capture", "Invalid original receipt") from exc
        _require(support_artifact_to_dict(artifact) == receipt, "Noncanonical original receipt")
        _require(
            compute_support_digest(artifact) == digest,
            "Original receipt digest mismatch",
            "support_digest_mismatch",
        )
        children = sorted(
            {
                edge["child_support_digest"]
                for edge in receipt["rule_ref_edges"]
                if edge["child_support_digest"] is not None
            }
        )
        _require(
            step["child_support_digests"] == children,
            "Child support links differ from original receipt",
        )
        for child in children:
            _token(child)
        for witness in receipt["pred_witnesses"]:
            for ref in witness["asrt_ids"]:
                coordinate = _coordinate(
                    {
                        "support_digest": digest,
                        "condition_key": witness["pred_condition_key"],
                        "witness_ref": ref,
                    }
                )
                _require(coordinate not in coordinates, "Duplicate original occurrence")
                coordinates.add(coordinate)
    _require(list(by_digest) == sorted(by_digest), "Support steps must be sorted")
    if root is None:
        _require(not steps, "Failed evaluation cannot carry successful support")
        return coordinates, []
    _token(root)
    visited: set[str] = set()
    visiting: set[str] = set()
    missing: set[str] = set()

    def walk(digest: str) -> None:
        _require(digest not in visiting, "Cyclic original support closure")
        if digest in visited:
            return
        visited.add(digest)
        step = by_digest.get(digest)
        if step is None or not step["factgraph_explain"]:
            missing.add(digest)
            return
        visiting.add(digest)
        for child in step["child_support_digests"]:
            walk(child)
        visiting.remove(digest)

    walk(root)
    _require(set(by_digest) <= visited, "Report contains support outside the selected closure")
    return coordinates, [
        {"support_digest": digest, "reason": "support_not_captured"} for digest in sorted(missing)
    ]


def _validate_report(row: Any) -> None:
    _fields(
        row,
        "contract capture_scope availability_basis goal engine rule_set_digest view_snapshot_digest "
        "premise_scope_digest root_support_digest status occurrences support_steps support_graph_digest "
        "evidence evidence_digest source_links issues report_digest",
    )
    _require(row["contract"] == RULE_PROGRAM_WITNESS_CONTRACT_V1, "Unknown witness report contract")
    _require(row["capture_scope"] == "successful_support_closure", "Unknown capture scope")
    _require(row["availability_basis"] == "captured_evaluation", "Invalid availability basis")
    _require(row["engine"] == "native", "Invalid native capture engine")
    _fields(row["goal"], "predicate terms")
    _text(row["goal"]["predicate"])
    _typed_terms(row["goal"]["terms"])
    _require(bool(row["goal"]["terms"]), "Empty closed goal")
    for name in (
        "rule_set_digest",
        "view_snapshot_digest",
        "premise_scope_digest",
        "support_graph_digest",
        "evidence_digest",
        "report_digest",
    ):
        _token(row[name])
    _require(
        _digest({key: value for key, value in row.items() if key != "report_digest"})
        == row["report_digest"],
        "Report digest mismatch",
        "report_digest_mismatch",
    )
    _require(
        _digest(row["support_steps"]) == row["support_graph_digest"],
        "Support graph digest mismatch",
    )
    _require(_digest(row["evidence"]) == row["evidence_digest"], "Evidence digest mismatch")
    expected, issues = _support_inventory(row["support_steps"], row["root_support_digest"])
    _require(row["issues"] == issues, "Missing support issues differ from original closure")
    evidence = row["evidence"]
    _require(
        _to_jsonable(evidence_graph_to_dict(evidence_graph_from_dict(_evidence_values(evidence))))
        == evidence,
        "Noncanonical evidence graph",
    )
    _require(evidence["engine"] == row["engine"], "Evidence engine mismatch")
    for name in ("rule_set_digest", "view_snapshot_digest", "premise_scope_digest"):
        _require(evidence["metadata"].get(name) == row[name], "Evidence pin mismatch")
    items: dict[tuple[str, str, str], dict[str, Any]] = {}
    materials: dict[str, bytes] = {}
    _require(isinstance(row["occurrences"], list), "Occurrences must be a list")
    for item in row["occurrences"]:
        _fields(
            item,
            "support_digest condition_key witness_ref kind predicate_id terms program_fact_provenance availability reason",
        )
        coordinate = _coordinate(item)
        _require(coordinate not in items, "Duplicate captured occurrence")
        items[coordinate] = item
        _require(
            item["kind"] in ("assertion", "program_fact", "virtual", "unknown"),
            "Unknown witness origin",
        )
        _typed_terms(item["terms"])
        if item["predicate_id"] is not None:
            _text(item["predicate_id"])
        if item["kind"] == "program_fact":
            _require(
                isinstance(item["program_fact_provenance"], dict)
                and bool(item["program_fact_provenance"]),
                "Program fact requires original provenance",
            )
        else:
            _require(
                item["program_fact_provenance"] is None,
                "Non-program witness cannot have program provenance",
            )
        if item["availability"] == "available":
            _require(
                item["kind"] != "unknown"
                and item["reason"] is None
                and item["predicate_id"] is not None
                and bool(item["terms"]),
                "Invalid available witness",
            )
        else:
            _require(
                item["availability"] == "unavailable"
                and item["reason"] in ("origin_not_captured", "material_not_captured"),
                "Invalid unavailable witness",
            )
            _require(
                (item["kind"] == "unknown") == (item["reason"] == "origin_not_captured"),
                "Invalid origin availability",
            )
        material = _encode(
            {
                key: value
                for key, value in item.items()
                if key not in ("support_digest", "condition_key", "witness_ref")
            }
        )
        _require(
            item["witness_ref"] not in materials or materials[item["witness_ref"]] == material,
            "Conflicting captured material for witness ref",
            "program_witness_ref_collision",
        )
        materials[item["witness_ref"]] = material
    _require(list(items) == sorted(expected), "Captured occurrences do not match original support")
    sources = _sources(evidence)
    pointers = []
    _require(isinstance(row["source_links"], list), "Source links must be a list")
    for link in row["source_links"]:
        _fields(link, "pointer status occurrences")
        pointer = link["pointer"]
        _text(pointer)
        _require(pointer in sources, "Unknown source position", "invalid_source_link")
        pointers.append(pointer)
        _require(isinstance(link["occurrences"], list), "Source occurrences must be a list")
        if link["status"] == "captured":
            _require(
                bool(link["occurrences"]) and row["root_support_digest"] is not None,
                "Empty captured source link",
            )
            keys = []
            for occurrence in link["occurrences"]:
                _fields(occurrence, "support_digest condition_key witness_ref")
                key = _coordinate(occurrence)
                _require(
                    key in items, "Source links to nonexistent occurrence", "invalid_source_link"
                )
                keys.append(key)
                item, source = items[key], sources[pointer]
                _require(
                    item["witness_ref"] == source["ref"]
                    and item["predicate_id"] == source["field"],
                    "Source material differs from occurrence",
                    "invalid_source_link",
                )
                values = _evidence_values(source["value"])
                _require(
                    isinstance(values, list) and len(values) == len(item["terms"]),
                    "Source term arity differs",
                )
                canonical = claim_args_from_rest_terms(
                    [
                        (term["tag"], _raw_value(term["tag"], value))
                        for term, value in zip(item["terms"], values)
                    ]
                )
                _require(
                    _encode([{"tag": tag, "value": value} for _, value, tag in canonical])
                    == _encode(item["terms"]),
                    "Source terms differ from occurrence",
                    "invalid_source_link",
                )
            _require(keys == sorted(set(keys)), "Source occurrence links must be unique and sorted")
        else:
            _require(link["occurrences"] == [], "Uncaptured source has occurrence links")
            _require(
                link["status"]
                == ("diagnostic_only" if row["root_support_digest"] is None else "not_captured"),
                "Invalid uncaptured source status",
            )
    _require(pointers == sorted(sources), "Source positions must be complete, unique and sorted")
    partial = (
        bool(issues)
        or any(item["availability"] == "unavailable" for item in items.values())
        or any(link["status"] == "not_captured" for link in row["source_links"])
    )
    expected_status = (
        "not_applicable"
        if row["root_support_digest"] is None
        else ("partial" if partial else "complete")
    )
    _require(row["status"] == expected_status, "Status differs from captured completeness")


__all__ = [
    "RULE_PROGRAM_WITNESS_CONTRACT_V1",
    "RuleProgramWitnessError",
    "RuleProgramWitnessReportV1",
]
