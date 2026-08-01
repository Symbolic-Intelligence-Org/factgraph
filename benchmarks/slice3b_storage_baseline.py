#!/usr/bin/env python3
"""Repeatable storage/read baseline for the Slice 3b three-way comparison.

The harness deliberately uses only the durable ``Database`` write contract and
the stable ``Ledger`` read surface.  It therefore remains the same executable
for the three measurements required by Q-SAE-9:

1. the current seven-table layout;
2. the three-table layout before meta tiering;
3. the three-table layout after meta tiering.

The default batch size is the observed ``plan.ingest`` request shape in the
local meander development workspace on 2026-08-01: one request_id grouped three
claims.  ``--batch-sizes`` accepts a comma-separated repeating distribution so
the exact same harness can replay a wider production histogram when available.

Storage is reported as the filled workspace delta over an empty workspace with
the same schema.  This removes fixed schema/genesis costs while retaining
SQLite pages and per-commit tx-object cost.  WAL files, SHM files and the writer
lock are excluded after an explicit checkpoint.  Each assertion carries five
meander-shaped input meta entries; Stage A injects the three integrity anchors
(``schema_digest``, ``assertion_digest``, ``tx_id``), preserving the established
eight persisted meta rows per claim sizing profile.
"""

from __future__ import annotations

import argparse
import gc
import json
import platform
import sqlite3
import statistics
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from factgraph.core.policy.chosen import compute_chosen_for_predicate
from factgraph.core.store.database import (
    AssertionInput,
    Database,
    MetaEntry,
    resolve_database_workspace_paths,
)
from factgraph.core.store.ledger import Ledger
from factgraph.core.store.premise_filter import (
    MetaExclusion,
    PredicatePremiseAllowance,
    PredicatePremiseBlock,
    is_predicate_premise_blocked,
    is_predicate_premise_excluded,
    is_premise_excluded,
)


PRED_ID = "benchmark:value"
INPUT_META_PER_ASSERTION = 5
EXPECTED_PERSISTED_META_PER_ASSERTION = 8
DEFAULT_BATCH_SIZES = (3,)


def _schema_ir() -> dict[str, Any]:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {
                "entity_type": "Benchmark",
                "identity_fields": [{"name": "benchmark_id", "type_domain": "string"}],
            }
        ],
        "predicates": [
            {
                "pred_id": PRED_ID,
                "arg_specs": [
                    {"name": "benchmark", "type_domain": "entity_ref"},
                    {"name": "value", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
                "cardinality": "single",
            }
        ],
        "projection": {"entities": ["Benchmark"], "predicates": [PRED_ID]},
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": "2026-08-01T00:00:00Z",
    }


def _parse_batch_sizes(raw: str) -> tuple[int, ...]:
    try:
        values = tuple(int(part.strip()) for part in raw.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("batch sizes must be comma-separated integers") from exc
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("batch sizes must contain positive integers")
    return values


def _assertion(index: int, *, batch_index: int, batch_time: int, entity_count: int) -> AssertionInput:
    entity_index = index % entity_count
    e_ref = f"idref_v1:Benchmark:{entity_index:032x}"
    shared_suffix = f"{batch_index:08d}"
    meta = (
        MetaEntry("ingested_at", "time", batch_time),
        MetaEntry("provenance_class", "str", "observed"),
        MetaEntry("origin_binding", "str", "otel.span"),
        MetaEntry("trace_id", "str", f"trace-{shared_suffix}"),
        MetaEntry("request_id", "str", f"request-{shared_suffix}"),
    )
    if len(meta) != INPUT_META_PER_ASSERTION:
        raise AssertionError("the cross-phase input meta profile must stay fixed at five entries")
    return AssertionInput(
        pred_id=PRED_ID,
        fact_tuple=(("entity_ref", e_ref), ("string", f"value-{index:08d}")),
        meta=meta,
    )


def _populate(
    workspace: Path,
    *,
    claim_count: int,
    batch_sizes: Sequence[int],
) -> tuple[Database, list[str], Counter[int]]:
    database = Database.create(workspace, schema_ir=_schema_ir())
    asrt_ids: list[str] = []
    histogram: Counter[int] = Counter()
    entity_count = max(1, claim_count // 10)
    next_index = 0
    batch_index = 0
    while next_index < claim_count:
        requested = batch_sizes[batch_index % len(batch_sizes)]
        actual = min(requested, claim_count - next_index)
        batch_time = 1_788_220_800_000_000_000 + batch_index
        inputs = tuple(
            _assertion(
                index,
                batch_index=batch_index,
                batch_time=batch_time,
                entity_count=entity_count,
            )
            for index in range(next_index, next_index + actual)
        )
        result = database.commit_assertions(inputs)
        asrt_ids.extend(record.asrt_id for record in result.assertions)
        histogram[actual] += 1
        next_index += actual
        batch_index += 1
    if len(asrt_ids) != claim_count:
        raise AssertionError("Database commit result lost benchmark assertions")
    return database, asrt_ids, histogram


def _median_ms(call: Callable[[], Any], *, repeats: int) -> float:
    call()
    samples: list[float] = []
    for _ in range(repeats):
        gc.collect()
        started = time.perf_counter_ns()
        call()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return round(statistics.median(samples), 6)


def _read_benchmarks(
    ledger: Ledger,
    asrt_ids: Sequence[str],
    *,
    repeats: int,
) -> dict[str, Any]:
    if not asrt_ids:
        raise ValueError("read benchmarks require at least one assertion")
    first_id = asrt_ids[0]
    first_claim = ledger.get_claim(first_id)
    if first_claim is None:
        raise AssertionError("first committed assertion is missing from Ledger")
    point_ids = tuple(asrt_ids[: min(256, len(asrt_ids))])

    exclusion = (MetaExclusion("provenance_class", frozenset({"claimed_by_agent"})),)
    allowances = {
        PRED_ID: PredicatePremiseAllowance(
            PRED_ID,
            "provenance_class",
            frozenset({"observed"}),
        )
    }
    blocks = {
        PRED_ID: PredicatePremiseBlock(
            PRED_ID,
            "origin_binding",
            frozenset({"revoked-binding"}),
        )
    }

    def premise_scan() -> int:
        excluded = 0
        for asrt_id in asrt_ids:
            excluded += is_premise_excluded(ledger, asrt_id, exclusion)
            excluded += is_predicate_premise_excluded(ledger, asrt_id, allowances)
            excluded += is_predicate_premise_blocked(ledger, asrt_id, blocks)
        return excluded

    chosen_schema = {
        "pred_id": PRED_ID,
        "cardinality": "single",
        "group_key_indexes": [0],
    }

    def chosen_projection() -> int:
        return len(compute_chosen_for_predicate(ledger, chosen_schema))

    read_cases: dict[str, Callable[[], Any]] = {
        "get_claim_256": lambda: sum(ledger.get_claim(asrt_id) is not None for asrt_id in point_ids),
        "find_claims_all": lambda: len(ledger.find_claims()),
        "find_claims_pred": lambda: len(ledger.find_claims(pred_id=PRED_ID)),
        "find_claims_e_ref": lambda: len(ledger.find_claims(e_ref=first_claim.e_ref)),
        "find_claims_pred_e_ref": lambda: len(
            ledger.find_claims(pred_id=PRED_ID, e_ref=first_claim.e_ref)
        ),
        "find_claim_args_all": lambda: len(ledger.find_claim_args()),
        "find_claim_args_asrt": lambda: len(ledger.find_claim_args(asrt_id=first_id)),
        "find_claim_args_filtered": lambda: len(ledger.find_claim_args(idx=0, tag="entity_ref")),
        "find_meta_all": lambda: len(ledger.find_meta()),
        "find_meta_asrt": lambda: len(ledger.find_meta(asrt_id=first_id)),
        "find_meta_asrt_key": lambda: len(
            ledger.find_meta(asrt_id=first_id, key="provenance_class")
        ),
        "find_meta_key_kind": lambda: len(ledger.find_meta(key="trace_id", kind="str")),
        "find_annotations_all": lambda: len(ledger.find_annotations()),
        "find_annotations_asrt": lambda: len(ledger.find_annotations(asrt_id=first_id)),
        "find_annotations_ns_category": lambda: len(
            ledger.find_annotations(namespace="source", category="observed")
        ),
        "find_annotations_key": lambda: len(ledger.find_annotations(key="trace_id")),
        "has_active_revocation_256": lambda: sum(
            ledger.has_active_revocation(asrt_id) for asrt_id in point_ids
        ),
        "find_revoker_256": lambda: sum(
            ledger.find_revoker(asrt_id) is not None for asrt_id in point_ids
        ),
        "claims_property": lambda: len(ledger.claims),
        "claim_args_property": lambda: len(ledger.claim_args),
        "meta_rows_property": lambda: len(ledger.meta_rows),
        "annotation_rows_property": lambda: len(ledger.annotation_rows),
        "revokes_property": lambda: len(ledger.revokes),
        "get_ledger_meta": lambda: ledger.get_ledger_meta("head_tx_id") is not None,
        "get_ledger_meta_snapshot": lambda: len(
            ledger.get_ledger_meta_snapshot(("head_tx_id", "tx_seq", "schema_digest"))
        ),
    }

    def full_read_api_suite() -> int:
        checksum = 0
        for call in read_cases.values():
            value = call()
            checksum += int(value)
        return checksum

    return {
        "premise_filter_full_scan_ms": _median_ms(premise_scan, repeats=repeats),
        "chosen_full_projection_ms": _median_ms(chosen_projection, repeats=repeats),
        "ledger_read_api_suite_ms": _median_ms(full_read_api_suite, repeats=repeats),
        "ledger_read_api_cases_ms": {
            name: _median_ms(call, repeats=repeats) for name, call in read_cases.items()
        },
        "point_lookup_sample_size": len(point_ids),
    }


def _checkpoint_and_sqlite_stats(path: Path) -> tuple[int, dict[str, int]]:
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
        page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
        try:
            rows = conn.execute(
                "SELECT name, SUM(pgsize) FROM dbstat GROUP BY name ORDER BY name"
            ).fetchall()
        except sqlite3.DatabaseError:
            breakdown: dict[str, int] = {}
        else:
            breakdown = {str(name): int(size) for name, size in rows}
    return page_size * page_count, breakdown


def _durable_file_bytes(workspace: Path) -> tuple[int, dict[str, int]]:
    excluded_names = {"write.lock"}
    excluded_suffixes = {"-wal", "-shm"}
    files: dict[str, int] = {}
    for path in sorted(candidate for candidate in workspace.rglob("*") if candidate.is_file()):
        if path.name in excluded_names or any(path.name.endswith(suffix) for suffix in excluded_suffixes):
            continue
        files[str(path.relative_to(workspace))] = path.stat().st_size
    return sum(files.values()), files


def _storage_snapshot(workspace: Path) -> dict[str, Any]:
    paths = resolve_database_workspace_paths(workspace)
    sqlite_bytes, dbstat = _checkpoint_and_sqlite_stats(paths.assertions)
    durable_bytes, files = _durable_file_bytes(workspace)
    tx_object_bytes = sum(
        size for relative, size in files.items() if relative.startswith("db/objects/tx/")
    )
    schema_object_bytes = sum(
        size for relative, size in files.items() if relative.startswith("db/objects/schema/")
    )
    with sqlite3.connect(paths.assertions) as conn:
        tables = [
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
    return {
        "durable_bytes": durable_bytes,
        "sqlite_bytes": sqlite_bytes,
        "tx_object_bytes": tx_object_bytes,
        "schema_object_bytes": schema_object_bytes,
        "tables": tables,
        "dbstat_bytes": dbstat,
    }


def run(*, claim_count: int, batch_sizes: Sequence[int], repeats: int) -> dict[str, Any]:
    if claim_count <= 0:
        raise ValueError("claim_count must be positive")
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    if not batch_sizes or any(size <= 0 for size in batch_sizes):
        raise ValueError("batch_sizes must contain positive integers")

    with tempfile.TemporaryDirectory(prefix="factgraph-slice3b-baseline-") as raw_tmp:
        root = Path(raw_tmp)
        empty_workspace = root / "empty"
        empty = Database.create(empty_workspace, schema_ir=_schema_ir())
        empty.close()
        empty_storage = _storage_snapshot(empty_workspace)

        filled_workspace = root / "filled"
        database, asrt_ids, histogram = _populate(
            filled_workspace,
            claim_count=claim_count,
            batch_sizes=batch_sizes,
        )
        ledger = database._ledger_for_attach()
        persisted_meta_per_assertion = len(ledger.find_meta()) / claim_count
        if persisted_meta_per_assertion != EXPECTED_PERSISTED_META_PER_ASSERTION:
            raise AssertionError(
                "sizing profile drifted: expected eight projected meta rows per assertion, "
                f"got {persisted_meta_per_assertion}"
            )
        reads = _read_benchmarks(ledger, asrt_ids, repeats=repeats)
        database.close()
        filled_storage = _storage_snapshot(filled_workspace)

        storage_delta = {
            key: filled_storage[key] - empty_storage[key]
            for key in ("durable_bytes", "sqlite_bytes", "tx_object_bytes")
        }
        storage_delta["bytes_per_claim"] = round(
            storage_delta["durable_bytes"] / claim_count,
            3,
        )
        storage_delta["sqlite_bytes_per_claim"] = round(
            storage_delta["sqlite_bytes"] / claim_count,
            3,
        )
        storage_delta["tx_object_bytes_per_claim"] = round(
            storage_delta["tx_object_bytes"] / claim_count,
            3,
        )

        return {
            "harness": "slice3b_storage_baseline_v1",
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "sqlite": sqlite3.sqlite_version,
            },
            "workload": {
                "claim_count": claim_count,
                "meta_entries_per_assertion_input": INPUT_META_PER_ASSERTION,
                "projected_meta_rows_per_assertion": persisted_meta_per_assertion,
                "batch_sizes_repeating": list(batch_sizes),
                "batch_histogram": {
                    str(size): count for size, count in sorted(histogram.items())
                },
                "commit_count": sum(histogram.values()),
                "meander_profile": (
                    "plan.ingest request group; five workload meta entries plus three "
                    "Stage A integrity anchors"
                ),
            },
            "layout": {
                "tables": filled_storage["tables"],
                "dbstat_bytes": filled_storage["dbstat_bytes"],
            },
            "storage": {
                "empty": empty_storage,
                "filled": filled_storage,
                "delta": storage_delta,
            },
            "reads": reads,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", type=int, default=3_000)
    parser.add_argument(
        "--batch-sizes",
        type=_parse_batch_sizes,
        default=DEFAULT_BATCH_SIZES,
        help="comma-separated repeating batch-size distribution (default: 3)",
    )
    parser.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()
    result = run(
        claim_count=args.claims,
        batch_sizes=args.batch_sizes,
        repeats=args.repeats,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
