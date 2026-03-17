from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

_SUPPORT_RE = re.compile(r"^(?P<src>.+?) -\[(?P<rel>.+?)\]-> (?P<dst>.+)$")


def derive_struct_candidates_proto(
    struct_facts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    depends_forward: dict[str, list[str]] = {}
    monitors_forward: dict[str, list[str]] = {}
    component_of_forward: dict[str, list[str]] = {}

    for row in _sort_struct_facts(struct_facts):
        subject = _require_str(row.get("subject_id", row.get("subject")))
        relation = _require_str(row.get("relation"))
        obj = _require_str(row.get("object_id", row.get("object")))
        if relation == "depends_on":
            depends_forward.setdefault(subject, []).append(obj)
        elif relation == "monitors":
            monitors_forward.setdefault(subject, []).append(obj)
        elif relation == "is_component_of":
            component_of_forward.setdefault(subject, []).append(obj)

    out: list[dict[str, Any]] = []
    for subject, mids in depends_forward.items():
        for mid in sorted(mids):
            for obj in sorted(depends_forward.get(mid, [])):
                out.append(
                    {
                        "subject": subject,
                        "relation": "indirect_dependency",
                        "object": obj,
                        "confidence": 1.0,
                        "source_type": "derived",
                        "claim_id": None,
                    }
                )

    for subject, mids in monitors_forward.items():
        for mid in sorted(mids):
            for obj in sorted(component_of_forward.get(mid, [])):
                out.append(
                    {
                        "subject": subject,
                        "relation": "reachable_monitor",
                        "object": obj,
                        "confidence": 1.0,
                        "source_type": "derived",
                        "claim_id": None,
                    }
                )

    return sort_raw_candidates_proto(out)


def build_direct_evidence_candidates_proto(
    evidence_facts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out = [
        {
            "subject": _require_str(row.get("subject_id", row.get("subject"))),
            "relation": _require_str(row.get("relation")),
            "object": _require_str(row.get("object_id", row.get("object"))),
            "confidence": round(float(row.get("confidence")), 6),
            "source_type": "direct_evidence",
            "claim_id": _require_str(row.get("claim_id")),
        }
        for row in _sort_evidence_facts(evidence_facts)
    ]
    return sort_raw_candidates_proto(out)


def build_max_evidence_provenance(
    struct_facts: Sequence[Mapping[str, Any]],
    evidence_facts: Sequence[Mapping[str, Any]],
    raw_candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    claims_by_triple: dict[tuple[str, str, str], list[str]] = {}
    for row in evidence_facts:
        key = (
            _require_str(row.get("subject_id", row.get("subject"))),
            _require_str(row.get("relation")),
            _require_str(row.get("object_id", row.get("object"))),
        )
        claims_by_triple.setdefault(key, []).append(_require_str(row.get("claim_id")))
    for values in claims_by_triple.values():
        values.sort()

    struct_support = build_struct_support_index_proto(struct_facts)
    triples = sorted(
        {
            (
                _require_str(row.get("subject")),
                _require_str(row.get("relation")),
                _require_str(row.get("object")),
            )
            for row in raw_candidates
        }
    )
    out: list[dict[str, Any]] = []
    for subject, relation, obj in triples:
        out.append(
            {
                "candidate": {
                    "subject": subject,
                    "relation": relation,
                    "object": obj,
                },
                "direct_evidence": claims_by_triple.get((subject, relation, obj), []),
                "struct_support": struct_support.get((subject, relation, obj), []),
            }
        )
    return out


def build_struct_support_index_proto(
    struct_facts: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], list[str]]:
    depends_forward: dict[str, list[str]] = {}
    monitors_forward: dict[str, list[str]] = {}
    component_edges: set[tuple[str, str]] = set()

    for row in _sort_struct_facts(struct_facts):
        subject = _require_str(row.get("subject_id", row.get("subject")))
        relation = _require_str(row.get("relation"))
        obj = _require_str(row.get("object_id", row.get("object")))
        if relation == "depends_on":
            depends_forward.setdefault(subject, []).append(obj)
        elif relation == "monitors":
            monitors_forward.setdefault(subject, []).append(obj)
        elif relation == "is_component_of":
            component_edges.add((subject, obj))

    out: dict[tuple[str, str, str], list[str]] = {}
    for subject, mids in depends_forward.items():
        for mid in sorted(mids):
            for obj in sorted(depends_forward.get(mid, [])):
                out.setdefault(
                    (subject, "indirect_dependency", obj),
                    [
                        f"{subject} -[depends_on]-> {mid}",
                        f"{mid} -[depends_on]-> {obj}",
                    ],
                )

    for subject, mids in monitors_forward.items():
        for mid in sorted(mids):
            for edge_subject, edge_object in sorted(component_edges):
                if edge_subject != mid:
                    continue
                out.setdefault(
                    (subject, "reachable_monitor", edge_object),
                    [
                        f"{subject} -[monitors]-> {mid}",
                        f"{mid} -[is_component_of]-> {edge_object}",
                    ],
                )
    return out


def apply_max_evidence_aggregation(
    raw_candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in sort_raw_candidates_proto(raw_candidates):
        key = (
            _require_str(row.get("subject")),
            _require_str(row.get("relation")),
            _require_str(row.get("object")),
        )
        prev = best.get(key)
        candidate = {
            "subject": key[0],
            "relation": key[1],
            "object": key[2],
            "confidence": round(float(row.get("confidence")), 6),
            "source_type": _require_str(row.get("source_type")),
            "claim_id": row.get("claim_id"),
        }
        if prev is None:
            best[key] = candidate
            continue
        prev_conf = float(prev["confidence"])
        cur_conf = float(candidate["confidence"])
        if cur_conf > prev_conf:
            best[key] = candidate
            continue
        if cur_conf == prev_conf:
            prev_key = (prev["source_type"], prev.get("claim_id") or "")
            cur_key = (candidate["source_type"], candidate.get("claim_id") or "")
            if cur_key < prev_key:
                best[key] = candidate

    return sorted(
        best.values(),
        key=lambda row: (-float(row["confidence"]), row["subject"], row["relation"], row["object"]),
    )


def sort_raw_candidates_proto(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "subject": _require_str(row.get("subject")),
                "relation": _require_str(row.get("relation")),
                "object": _require_str(row.get("object")),
                "confidence": round(float(row.get("confidence")), 6),
                "source_type": _require_str(row.get("source_type")),
                "claim_id": row.get("claim_id"),
            }
            for row in rows
        ],
        key=lambda row: (
            row["subject"],
            row["relation"],
            row["object"],
            -float(row["confidence"]),
            row["source_type"],
            row.get("claim_id") or "",
        ),
    )


def validate_struct_support_proto(
    triple: tuple[str, str, str],
    struct_support: Sequence[Any],
    struct_edges: set[tuple[str, str, str]],
) -> tuple[bool, str]:
    parsed: list[tuple[str, str, str]] = []
    for item in struct_support:
        if not isinstance(item, str):
            return False, "internal_engine_node"
        match = _SUPPORT_RE.match(item)
        if match is None:
            return False, "internal_engine_node"
        edge = (match.group("src"), match.group("rel"), match.group("dst"))
        if edge not in struct_edges:
            return False, "broken_struct_chain"
        parsed.append(edge)

    if not parsed:
        return False, "broken_struct_chain"
    if parsed[0][0] != triple[0]:
        return False, "broken_struct_chain"
    if parsed[-1][2] != triple[2]:
        return False, "broken_struct_chain"
    for left, right in zip(parsed, parsed[1:]):
        if left[2] != right[0]:
            return False, "broken_struct_chain"
    return True, ""


def _sort_struct_facts(
    rows: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _require_str(row.get("subject_id", row.get("subject"))),
            _require_str(row.get("relation")),
            _require_str(row.get("object_id", row.get("object"))),
        ),
    )


def _sort_evidence_facts(
    rows: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            _require_str(row.get("subject_id", row.get("subject"))),
            _require_str(row.get("relation")),
            _require_str(row.get("object_id", row.get("object"))),
            -float(row.get("confidence")),
            _require_str(row.get("claim_id")),
        ),
    )


def _require_str(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("evidence prototype expects non-empty strings")
    return value
