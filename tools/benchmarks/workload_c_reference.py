from __future__ import annotations

import random
import re
from typing import Any

RELATIONS = (
    "reports_to",
    "is_component_of",
    "depends_on",
    "monitors",
    "triggers",
    "overrides",
    "supports",
    "conflicts_with",
)

SOURCES = (
    ("sensor", 40),
    ("llm_extraction", 40),
    ("manual", 20),
)

_SUPPORT_RE = re.compile(r"^(?P<src>.+?) -\[(?P<rel>.+?)\]-> (?P<dst>.+)$")


def generate_workload_c(
    *,
    n_struct: int = 1000,
    n_evidence: int = 200,
    n_entities: int = 100,
    seed: int = 42,
    scale: str = "1x",
) -> dict[str, Any]:
    random.seed(seed)
    entities = [f"ent{i:03d}" for i in range(n_entities)]
    source_population: list[str] = []
    for source, weight in SOURCES:
        source_population.extend([source] * weight)

    struct_facts: list[dict[str, Any]] = []
    seen_struct: set[tuple[str, str, str]] = set()
    attempts = 0
    while len(struct_facts) < n_struct and attempts < n_struct * 10:
        attempts += 1
        subject = random.choice(entities)
        obj = random.choice(entities)
        relation = random.choice(RELATIONS)
        if subject == obj:
            continue
        key = (subject, relation, obj)
        if key in seen_struct:
            continue
        seen_struct.add(key)
        struct_facts.append(
            {
                "subject_id": subject,
                "relation": relation,
                "object_id": obj,
            }
        )

    evidence_facts: list[dict[str, Any]] = []
    for idx in range(n_evidence):
        subject = random.choice(entities)
        obj = random.choice(entities)
        if subject == obj:
            obj = entities[(entities.index(subject) + 1) % len(entities)]
        evidence_facts.append(
            {
                "claim_id": f"claim{idx:04d}",
                "subject_id": subject,
                "relation": random.choice(RELATIONS),
                "object_id": obj,
                "confidence": round(random.uniform(0.4, 0.99), 4),
                "source": random.choice(source_population),
            }
        )

    return {
        "workload": "C",
        "seed": seed,
        "scale": scale,
        "struct_facts": sort_struct_facts(struct_facts),
        "evidence_facts": sort_evidence_facts(evidence_facts),
    }


def build_workload_c_golden(payload: dict[str, Any], *, top_k: int = 50) -> dict[str, Any]:
    raw_candidates = derive_workload_c_raw_candidates(payload)
    aggregated = apply_max_aggregation(raw_candidates)
    ranked = apply_top_k(aggregated, k=top_k)
    provenance_entries = build_provenance_entries(
        payload["struct_facts"],
        payload["evidence_facts"],
        raw_candidates,
    )
    provenance_map = _index_provenance_entries(provenance_entries)
    results: list[dict[str, Any]] = []
    for row in ranked:
        triple = (row["subject"], row["relation"], row["object"])
        provenance = provenance_map.get(triple, {"direct_evidence": [], "struct_support": []})
        results.append(
            {
                "rank": row["rank"],
                "subject": row["subject"],
                "relation": row["relation"],
                "object": row["object"],
                "confidence": row["confidence"],
                "source_type": row["source_type"],
                "provenance": {
                    "direct_evidence": provenance["direct_evidence"],
                    "struct_support": provenance["struct_support"],
                },
            }
        )

    return {
        "workload": "C",
        "query": "ranked_candidate",
        "aggregation": "max",
        "top_k": top_k,
        "seed": payload.get("seed"),
        "scale": payload.get("scale", "1x"),
        "results": results,
    }


def derive_workload_c_raw_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_candidates = build_direct_evidence_candidates(payload["evidence_facts"])
    raw_candidates.extend(derive_struct_candidates(payload["struct_facts"]))
    return sort_raw_candidates(raw_candidates)


def derive_struct_candidates(struct_facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    depends_forward: dict[str, list[str]] = {}
    monitors_forward: dict[str, list[str]] = {}
    component_of_forward: dict[str, list[str]] = {}

    for row in sort_struct_facts(struct_facts):
        subject = row["subject_id"]
        relation = row["relation"]
        obj = row["object_id"]
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
    return sort_raw_candidates(out)


def build_direct_evidence_candidates(evidence_facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = [
        {
            "subject": row["subject_id"],
            "relation": row["relation"],
            "object": row["object_id"],
            "confidence": round(float(row["confidence"]), 6),
            "source_type": "direct_evidence",
            "claim_id": row["claim_id"],
        }
        for row in sort_evidence_facts(evidence_facts)
    ]
    return sort_raw_candidates(out)


def build_provenance_entries(
    struct_facts: list[dict[str, Any]],
    evidence_facts: list[dict[str, Any]],
    raw_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    claims_by_triple: dict[tuple[str, str, str], list[str]] = {}
    for row in evidence_facts:
        key = (row["subject_id"], row["relation"], row["object_id"])
        claims_by_triple.setdefault(key, []).append(row["claim_id"])
    for values in claims_by_triple.values():
        values.sort()

    struct_support = build_struct_support_index(struct_facts)
    triples = sorted({(c["subject"], c["relation"], c["object"]) for c in raw_candidates})
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


def build_struct_support_index(
    struct_facts: list[dict[str, Any]],
) -> dict[tuple[str, str, str], list[str]]:
    depends_forward: dict[str, list[str]] = {}
    monitors_forward: dict[str, list[str]] = {}
    component_edges: set[tuple[str, str]] = set()

    for row in sort_struct_facts(struct_facts):
        subject = row["subject_id"]
        relation = row["relation"]
        obj = row["object_id"]
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


def apply_max_aggregation(raw_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in sort_raw_candidates(raw_candidates):
        key = (row["subject"], row["relation"], row["object"])
        prev = best.get(key)
        if prev is None:
            best[key] = dict(row)
            continue
        prev_conf = float(prev["confidence"])
        cur_conf = float(row["confidence"])
        if cur_conf > prev_conf:
            best[key] = dict(row)
            continue
        if cur_conf == prev_conf:
            prev_key = (prev["source_type"], prev.get("claim_id") or "")
            cur_key = (row["source_type"], row.get("claim_id") or "")
            if cur_key < prev_key:
                best[key] = dict(row)
    return sorted(best.values(), key=lambda row: (-float(row["confidence"]), row["subject"], row["relation"], row["object"]))


def apply_top_k(aggregated: list[dict[str, Any]], *, k: int = 50) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for idx, row in enumerate(aggregated[:k], start=1):
        ranked.append(
            {
                "rank": idx,
                "subject": row["subject"],
                "relation": row["relation"],
                "object": row["object"],
                "confidence": round(float(row["confidence"]), 6),
                "source_type": row["source_type"],
            }
        )
    return ranked


def check_provenance_completeness(
    ranked: list[dict[str, Any]],
    provenance_entries: list[dict[str, Any]],
    payload: dict[str, Any],
) -> dict[str, Any]:
    evidence_claim_ids = {row["claim_id"] for row in payload["evidence_facts"]}
    struct_edges = {(row["subject_id"], row["relation"], row["object_id"]) for row in payload["struct_facts"]}
    entry_map = _index_provenance_entries(provenance_entries)

    gaps: list[dict[str, Any]] = []
    complete = 0

    for row in ranked:
        triple = (row["subject"], row["relation"], row["object"])
        entry = entry_map.get(triple)
        if entry is None:
            gaps.append({"candidate": _candidate_triplet_dict(triple), "gap_type": "missing_provenance_entry"})
            continue

        direct_evidence = entry.get("direct_evidence", [])
        struct_support = entry.get("struct_support", [])
        if not isinstance(direct_evidence, list) or not isinstance(struct_support, list):
            gaps.append({"candidate": _candidate_triplet_dict(triple), "gap_type": "internal_engine_node"})
            continue
        if not direct_evidence and not struct_support:
            gaps.append({"candidate": _candidate_triplet_dict(triple), "gap_type": "missing_provenance_entry"})
            continue

        gap_type: str | None = None
        if direct_evidence:
            for claim_id in direct_evidence:
                if not isinstance(claim_id, str):
                    gap_type = "internal_engine_node"
                    break
                if claim_id not in evidence_claim_ids:
                    gap_type = "missing_claim_id"
                    break
        if gap_type is None and struct_support:
            ok, chain_gap = _validate_struct_support(
                triple,
                struct_support,
                struct_edges,
            )
            if not ok:
                gap_type = chain_gap

        if gap_type is None:
            complete += 1
        else:
            gaps.append({"candidate": _candidate_triplet_dict(triple), "gap_type": gap_type})

    total = len(ranked)
    rate = 1.0 if total == 0 else round(complete / total, 6)
    return {
        "complete_count": complete,
        "total_checked": total,
        "complete_rate": rate,
        "gaps": gaps,
    }


def diff_against_golden(ranked: list[dict[str, Any]], golden: dict[str, Any]) -> dict[str, Any]:
    golden_rows = golden.get("results", [])
    if not isinstance(golden_rows, list):
        raise ValueError("golden.results must be a list")

    ranked_map = {
        (row["subject"], row["relation"], row["object"]): row
        for row in ranked
    }
    golden_map = {
        (row["subject"], row["relation"], row["object"]): row
        for row in golden_rows
    }

    ranked_keys = set(ranked_map)
    golden_keys = set(golden_map)
    missing = [_candidate_triplet_dict(key) for key in sorted(golden_keys - ranked_keys)]
    extra = [_candidate_triplet_dict(key) for key in sorted(ranked_keys - golden_keys)]

    deltas: list[dict[str, Any]] = []
    confidence_ok = True
    for key in sorted(ranked_keys & golden_keys):
        ranked_conf = round(float(ranked_map[key]["confidence"]), 6)
        golden_conf = round(float(golden_map[key]["confidence"]), 6)
        abs_delta = round(abs(ranked_conf - golden_conf), 6)
        rel_delta = 0.0 if golden_conf == 0.0 else round(abs_delta / golden_conf, 6)
        if abs_delta >= 0.001:
            confidence_ok = False
        deltas.append(
            {
                "candidate": _candidate_triplet_dict(key),
                "ranked_confidence": ranked_conf,
                "golden_confidence": golden_conf,
                "absolute_delta": abs_delta,
                "relative_delta": rel_delta,
            }
        )

    return {
        "missing": missing,
        "extra": extra,
        "confidence_deltas": deltas,
        "matches_golden": not missing and not extra and confidence_ok,
    }


def compare_result_to_golden(
    result: dict[str, Any],
    golden: dict[str, Any],
    payload: dict[str, Any],
    *,
    top_k: int | None = None,
) -> dict[str, Any]:
    raw_candidates = result.get("raw_candidates", [])
    if not isinstance(raw_candidates, list):
        raise ValueError("result.raw_candidates must be a list")
    provenance_entries = result.get("provenance_entries", [])
    if not isinstance(provenance_entries, list):
        raise ValueError("result.provenance_entries must be a list")

    target_k = int(top_k if top_k is not None else golden.get("top_k", 50))
    aggregated = apply_max_aggregation(raw_candidates)
    ranked = apply_top_k(aggregated, k=target_k)
    provenance = check_provenance_completeness(ranked, provenance_entries, payload)
    diff = diff_against_golden(ranked, golden)
    return {
        "baseline": result.get("baseline"),
        "unsupported_features": result.get("unsupported_features", []),
        "notes": result.get("notes", ""),
        "raw_candidate_count": len(raw_candidates),
        "aggregated_candidate_count": len(aggregated),
        "ranked_results": ranked,
        "provenance_check": provenance,
        "golden_diff": diff,
    }


def sort_struct_facts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["subject_id"], row["relation"], row["object_id"]))


def sort_evidence_facts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            row["subject_id"],
            row["relation"],
            row["object_id"],
            -float(row["confidence"]),
            row["claim_id"],
        ),
    )


def sort_raw_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            row["subject"],
            row["relation"],
            row["object"],
            -float(row["confidence"]),
            row["source_type"],
            row.get("claim_id") or "",
        ),
    )


def _index_provenance_entries(
    provenance_entries: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in provenance_entries:
        candidate = entry.get("candidate", {})
        if not isinstance(candidate, dict):
            continue
        subject = candidate.get("subject")
        relation = candidate.get("relation")
        obj = candidate.get("object")
        if not all(isinstance(value, str) and value for value in (subject, relation, obj)):
            continue
        out[(subject, relation, obj)] = entry
    return out


def _validate_struct_support(
    triple: tuple[str, str, str],
    struct_support: list[Any],
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


def _candidate_triplet_dict(triple: tuple[str, str, str]) -> dict[str, str]:
    return {"subject": triple[0], "relation": triple[1], "object": triple[2]}
