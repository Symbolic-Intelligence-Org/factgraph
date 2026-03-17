from __future__ import annotations

import random
from typing import Any

STATUSES = ("active", "inactive", "degraded")
CLASSES = ("A", "B", "C")

T2_POOL = (
    ("active", "A", "degraded"),
    ("active", "B", "inactive"),
    ("active", "C", "degraded"),
    ("inactive", "A", "degraded"),
    ("inactive", "B", "active"),
    ("inactive", "C", "active"),
    ("degraded", "A", "inactive"),
    ("degraded", "B", "active"),
    ("degraded", "C", "inactive"),
)

T3_POOL = (
    ("degraded", "A", "active"),
    ("degraded", "B", "active"),
    ("degraded", "C", "active"),
    ("inactive", "A", "active"),
    ("inactive", "B", "active"),
    ("inactive", "C", "active"),
)


def generate_workload_b(
    *,
    n_entities: int = 100,
    t_max: int = 20,
    seed: int = 42,
    scale: str = "1x",
) -> dict[str, Any]:
    random.seed(seed)
    state_dist = ["active"] * 70 + ["inactive"] * 20 + ["degraded"] * 10

    init_state_facts: list[dict[str, Any]] = []
    property_facts: list[dict[str, Any]] = []
    for idx in range(n_entities):
        entity = f"ent{idx:03d}"
        status = random.choice(state_dist)
        init_state_facts.append({"entity_id": entity, "timestep": 0, "status": status})
        if random.random() < 0.6:
            property_facts.append(
                {
                    "entity_id": entity,
                    "prop_name": "class",
                    "prop_value": random.choice(CLASSES),
                }
            )

    rules = _generate_rules(seed)
    return {
        "workload": "B",
        "seed": seed,
        "scale": scale,
        "t_max": t_max,
        "init_state_facts": sort_init_state_facts(init_state_facts),
        "property_facts": sort_property_facts(property_facts),
        "rules": sort_rules(rules),
    }


def build_workload_b_golden(payload: dict[str, Any]) -> dict[str, Any]:
    simulation = simulate_workload_b(payload)
    return {
        "workload": "B",
        "query": "final_state_at_Tmax",
        "seed": payload.get("seed"),
        "scale": payload.get("scale", "1x"),
        "T_max": payload.get("t_max", 20),
        "results": simulation["results"],
        "state_history_summary": simulation["state_history_summary"],
        "provenance_entries": simulation["provenance_entries"],
    }


def simulate_workload_b(payload: dict[str, Any]) -> dict[str, Any]:
    t_max = int(payload.get("t_max", 20))
    rules = sort_rules(payload["rules"])
    init_state_facts = sort_init_state_facts(payload["init_state_facts"])
    property_facts = sort_property_facts(payload["property_facts"])

    entities = [row["entity_id"] for row in init_state_facts]
    current_state = {row["entity_id"]: row["status"] for row in init_state_facts}
    property_map = {
        row["entity_id"]: row["prop_value"]
        for row in property_facts
        if row["prop_name"] == "class"
    }
    state_by_time: dict[int, dict[str, str]] = {0: dict(current_state)}
    transition_count = {entity: 0 for entity in entities}
    first_transition_at = {entity: None for entity in entities}
    state_history_summary = {entity: [current_state[entity]] for entity in entities}
    provenance_entries: list[dict[str, Any]] = []

    for timestep in range(t_max):
        next_state: dict[str, str] = {}
        active_helpers_by_class: dict[str, list[str]] = {}
        for cls in CLASSES:
            helpers = [
                entity
                for entity in entities
                if current_state[entity] == "active" and property_map.get(entity) == cls
            ]
            active_helpers_by_class[cls] = sorted(helpers)

        for entity in entities:
            candidates = [
                {
                    "status": current_state[entity],
                    "priority": 0,
                    "rule_id": 0,
                    "rule_label": "T1",
                    "trigger_entities": [entity],
                }
            ]

            entity_class = property_map.get(entity)
            for rule in rules:
                if rule["template"] == "T2":
                    if current_state[entity] == rule["source_status"] and entity_class == rule["class_value"]:
                        candidates.append(
                            {
                                "status": rule["target_status"],
                                "priority": rule["rule_id"],
                                "rule_id": rule["rule_id"],
                                "rule_label": rule["rule_label"],
                                "trigger_entities": [entity],
                            }
                        )
                elif rule["template"] == "T3":
                    if current_state[entity] != rule["source_status"]:
                        continue
                    for helper in active_helpers_by_class.get(rule["helper_class"], []):
                        if helper == entity:
                            continue
                        candidates.append(
                            {
                                "status": rule["target_status"],
                                "priority": rule["rule_id"],
                                "rule_id": rule["rule_id"],
                                "rule_label": rule["rule_label"],
                                "trigger_entities": [entity, helper],
                            }
                        )

            chosen = _choose_candidate(candidates)
            next_state[entity] = chosen["status"]
            if chosen["status"] != current_state[entity]:
                transition_count[entity] += 1
                if first_transition_at[entity] is None:
                    first_transition_at[entity] = timestep + 1
                state_history_summary[entity].append(chosen["status"])
                provenance_entries.append(
                    {
                        "entity": entity,
                        "timestep": timestep + 1,
                        "new_status": chosen["status"],
                        "trigger_rule": chosen["rule_label"],
                        "trigger_entities": list(chosen["trigger_entities"]),
                    }
                )
        current_state = next_state
        state_by_time[timestep + 1] = dict(current_state)

    results = [
        {
            "entity": entity,
            "final_status": current_state[entity],
            "first_transition_at": first_transition_at[entity],
            "transition_count": transition_count[entity],
        }
        for entity in entities
    ]

    return {
        "results": results,
        "state_history_summary": state_history_summary,
        "provenance_entries": provenance_entries,
        "state_by_time": state_by_time,
    }


def compare_result_to_golden(
    result: dict[str, Any],
    golden: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    result_rows = result.get("results", [])
    if not isinstance(result_rows, list):
        raise ValueError("result.results must be a list")
    provenance_entries = result.get("provenance_entries", [])
    if not isinstance(provenance_entries, list):
        raise ValueError("result.provenance_entries must be a list")

    diff = diff_against_golden(result_rows, golden)
    provenance = check_provenance_completeness(provenance_entries, golden, payload)
    return {
        "baseline": result.get("baseline"),
        "unsupported_features": result.get("unsupported_features", []),
        "notes": result.get("notes", ""),
        "result_count": len(result_rows),
        "provenance_check": provenance,
        "golden_diff": diff,
    }


def check_provenance_completeness(
    provenance_entries: list[dict[str, Any]],
    golden: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    simulation = simulate_workload_b(payload)
    state_by_time = simulation["state_by_time"]
    valid_rule_labels = {rule["rule_label"]: rule for rule in payload["rules"]}
    entity_set = {row["entity_id"] for row in payload["init_state_facts"]}
    property_map = {
        row["entity_id"]: row["prop_value"]
        for row in payload["property_facts"]
        if row["prop_name"] == "class"
    }

    entries_by_key: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for entry in provenance_entries:
        key = (entry.get("entity"), entry.get("timestep"), entry.get("new_status"))
        entries_by_key.setdefault(key, []).append(entry)

    golden_entries = golden.get("provenance_entries", [])
    gaps: list[dict[str, Any]] = []
    complete = 0
    for event in golden_entries:
        key = (event["entity"], event["timestep"], event["new_status"])
        candidates = entries_by_key.get(key, [])
        if not candidates:
            gaps.append({"event": _event_key_dict(key), "gap_type": "missing_event_provenance"})
            continue

        valid = False
        for candidate in candidates:
            ok, gap_type = _validate_provenance_entry(
                candidate,
                state_by_time=state_by_time,
                valid_rule_labels=valid_rule_labels,
                entity_set=entity_set,
                property_map=property_map,
            )
            if ok:
                valid = True
                break
        if valid:
            complete += 1
        else:
            gaps.append({"event": _event_key_dict(key), "gap_type": gap_type})

    total = len(golden_entries)
    return {
        "complete_count": complete,
        "total_checked": total,
        "complete_rate": 1.0 if total == 0 else round(complete / total, 6),
        "gaps": gaps,
    }


def diff_against_golden(result_rows: list[dict[str, Any]], golden: dict[str, Any]) -> dict[str, Any]:
    golden_rows = golden.get("results", [])
    result_map = {row["entity"]: row for row in result_rows}
    golden_map = {row["entity"]: row for row in golden_rows}

    missing = [{"entity": entity} for entity in sorted(golden_map.keys() - result_map.keys())]
    extra = [{"entity": entity} for entity in sorted(result_map.keys() - golden_map.keys())]

    mismatches: list[dict[str, Any]] = []
    for entity in sorted(result_map.keys() & golden_map.keys()):
        result_row = result_map[entity]
        golden_row = golden_map[entity]
        if (
            result_row.get("final_status") != golden_row.get("final_status")
            or result_row.get("first_transition_at") != golden_row.get("first_transition_at")
            or int(result_row.get("transition_count", 0)) != int(golden_row.get("transition_count", 0))
        ):
            mismatches.append(
                {
                    "entity": entity,
                    "result": {
                        "final_status": result_row.get("final_status"),
                        "first_transition_at": result_row.get("first_transition_at"),
                        "transition_count": result_row.get("transition_count"),
                    },
                    "golden": {
                        "final_status": golden_row.get("final_status"),
                        "first_transition_at": golden_row.get("first_transition_at"),
                        "transition_count": golden_row.get("transition_count"),
                    },
                }
            )

    return {
        "missing": missing,
        "extra": extra,
        "mismatches": mismatches,
        "matches_golden": not missing and not extra and not mismatches,
    }


def sort_init_state_facts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["entity_id"], int(row["timestep"]), row["status"]))


def sort_property_facts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (row["entity_id"], row["prop_name"], row["prop_value"]))


def sort_rules(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: int(row["rule_id"]))


def _generate_rules(seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    t2_rules = list(T2_POOL)
    t3_rules = list(T3_POOL)
    rng.shuffle(t2_rules)
    rng.shuffle(t3_rules)

    rules: list[dict[str, Any]] = []
    for idx, (source_status, class_value, target_status) in enumerate(t2_rules, start=1):
        rule_id = 100 + idx
        rules.append(
            {
                "rule_id": rule_id,
                "rule_label": f"T2_{rule_id}",
                "template": "T2",
                "source_status": source_status,
                "class_value": class_value,
                "target_status": target_status,
            }
        )
    for idx, (source_status, helper_class, target_status) in enumerate(t3_rules, start=1):
        rule_id = 200 + idx
        rules.append(
            {
                "rule_id": rule_id,
                "rule_label": f"T3_{rule_id}",
                "template": "T3",
                "source_status": source_status,
                "helper_class": helper_class,
                "target_status": target_status,
            }
        )
    return rules


def _choose_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    max_priority = max(int(candidate["priority"]) for candidate in candidates)
    finalists = [candidate for candidate in candidates if int(candidate["priority"]) == max_priority]
    finalists.sort(key=lambda item: tuple(item["trigger_entities"]))
    return finalists[0]


def _validate_provenance_entry(
    entry: dict[str, Any],
    *,
    state_by_time: dict[int, dict[str, str]],
    valid_rule_labels: dict[str, dict[str, Any]],
    entity_set: set[str],
    property_map: dict[str, str],
) -> tuple[bool, str]:
    entity = entry.get("entity")
    timestep = entry.get("timestep")
    new_status = entry.get("new_status")
    trigger_rule = entry.get("trigger_rule")
    trigger_entities = entry.get("trigger_entities")

    if not isinstance(entity, str) or entity not in entity_set:
        return False, "invalid_trigger_entities"
    if not isinstance(timestep, int) or timestep <= 0:
        return False, "invalid_event_key"
    if not isinstance(new_status, str) or new_status not in STATUSES:
        return False, "invalid_event_key"
    if not isinstance(trigger_entities, list) or not trigger_entities:
        return False, "invalid_trigger_entities"
    if any(not isinstance(item, str) or item not in entity_set for item in trigger_entities):
        return False, "invalid_trigger_entities"
    if trigger_entities[0] != entity:
        return False, "invalid_trigger_entities"

    previous_state = state_by_time[timestep - 1][entity]
    if trigger_rule == "T1":
        if new_status == previous_state:
            return True, ""
        return False, "invalid_trigger_rule"

    rule = valid_rule_labels.get(trigger_rule)
    if rule is None:
        return False, "invalid_trigger_rule"

    if rule["template"] == "T2":
        if len(trigger_entities) != 1:
            return False, "invalid_trigger_entities"
        if previous_state != rule["source_status"]:
            return False, "invalid_trigger_rule"
        if property_map.get(entity) != rule["class_value"]:
            return False, "invalid_trigger_rule"
        if new_status != rule["target_status"]:
            return False, "invalid_trigger_rule"
        return True, ""

    if rule["template"] == "T3":
        if len(trigger_entities) != 2:
            return False, "invalid_trigger_entities"
        helper = trigger_entities[1]
        if helper == entity:
            return False, "invalid_trigger_entities"
        if previous_state != rule["source_status"]:
            return False, "invalid_trigger_rule"
        helper_state = state_by_time[timestep - 1][helper]
        if helper_state != "active":
            return False, "invalid_trigger_rule"
        if property_map.get(helper) != rule["helper_class"]:
            return False, "invalid_trigger_rule"
        if new_status != rule["target_status"]:
            return False, "invalid_trigger_rule"
        return True, ""

    return False, "invalid_trigger_rule"


def _event_key_dict(key: tuple[str, int, str]) -> dict[str, Any]:
    return {"entity": key[0], "timestep": key[1], "new_status": key[2]}
