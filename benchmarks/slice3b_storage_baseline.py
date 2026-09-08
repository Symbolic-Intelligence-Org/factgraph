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
lock are excluded after an explicit checkpoint.  SQLite allocation is sampled
at least five times and reported as a median plus jitter band; only the
content-addressed tx-object delta is expected to be byte-exact across runs.
Each assertion has the same five-entry effective meander-shaped meta profile in
all three phases.  The ``three-table`` profile keeps all five entries claim
scoped.  The ``three-table-tiered`` profile keeps ``trace_id`` claim scoped but
lazy, while only ``request_id`` is lifted to a tx default.  This deliberately
separates the workset contribution of lazy projection from the storage-row
contribution of tx lifting (Phase 3 audit item F6).  Projected Ledger rows,
physical persisted rows and the eager in-memory workset are reported separately
instead of fixing their ratio.
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
PROFILE_THREE_TABLE = "three-table"
PROFILE_THREE_TABLE_TIERED = "three-table-tiered"
PROFILES = (PROFILE_THREE_TABLE, PROFILE_THREE_TABLE_TIERED)
LOGICAL_META_PER_ASSERTION = 5
CLAIM_META_PER_ASSERTION = {
    PROFILE_THREE_TABLE: 5,
    PROFILE_THREE_TABLE_TIERED: 4,
}
TX_DEFAULT_META_PER_BATCH = {
    PROFILE_THREE_TABLE: 0,
    PROFILE_THREE_TABLE_TIERED: 1,
}
CLAIM_DOMAIN_LAZY_KEY = "trace_id"
TX_LIFTED_KEY = "request_id"
DEFAULT_BATCH_SIZES = (3,)
DEFAULT_STORAGE_RUNS = 5


def _schema_ir(profile: str = PROFILE_THREE_TABLE_TIERED) -> dict[str, Any]:
    if profile not in PROFILES:
        raise ValueError(f"unknown storage profile: {profile!r}")
    schema_ir: dict[str, Any] = {
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
    if profile == PROFILE_THREE_TABLE_TIERED:
        schema_ir["meta_keys"] = {
            TX_LIFTED_KEY: {
                "load_policy": "lazy",
                "reader_class": "audit",
                "storage_scope": "tx_liftable",
            },
            CLAIM_DOMAIN_LAZY_KEY: {
                "load_policy": "lazy",
                "reader_class": "audit",
            },
        }
    return schema_ir


def _parse_batch_sizes(raw: str) -> tuple[int, ...]:
    try:
        values = tuple(int(part.strip()) for part in raw.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("batch sizes must be comma-separated integers") from exc
    if not values or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("batch sizes must contain positive integers")
    return values


def _assertion(
    index: int,
    *,
    profile: str,
    batch_index: int,
    batch_time: int,
    entity_count: int,
) -> AssertionInput:
    entity_index = index % entity_count
    e_ref = f"idref_v1:Benchmark:{entity_index:032x}"
    shared_suffix = f"{batch_index:08d}"
    rows = [
        MetaEntry("ingested_at", "time", batch_time),
        MetaEntry("provenance_class", "str", "observed"),
        MetaEntry("origin_binding", "str", "otel.span"),
        MetaEntry(CLAIM_DOMAIN_LAZY_KEY, "str", f"trace-{shared_suffix}"),
    ]
    if profile == PROFILE_THREE_TABLE:
        rows.append(MetaEntry(TX_LIFTED_KEY, "str", f"request-{shared_suffix}"))
    meta = tuple(rows)
    if len(meta) != CLAIM_META_PER_ASSERTION[profile]:
        raise AssertionError("the selected claim meta profile changed unexpectedly")
    return AssertionInput(
        pred_id=PRED_ID,
        fact_tuple=(("entity_ref", e_ref), ("string", f"value-{index:08d}")),
        meta=meta,
    )


def _batch_meta_defaults(profile: str, batch_index: int) -> tuple[MetaEntry, ...]:
    shared_suffix = f"{batch_index:08d}"
    rows = (
        (MetaEntry(TX_LIFTED_KEY, "str", f"request-{shared_suffix}"),)
        if profile == PROFILE_THREE_TABLE_TIERED
        else ()
    )
    if len(rows) != TX_DEFAULT_META_PER_BATCH[profile]:
        raise AssertionError("the selected tx-default profile changed unexpectedly")
    if CLAIM_META_PER_ASSERTION[profile] + len(rows) != LOGICAL_META_PER_ASSERTION:
        raise AssertionError("the cross-phase effective meta profile must stay at five entries")
    return rows


def _populate(
    workspace: Path,
    *,
    profile: str,
    claim_count: int,
    batch_sizes: Sequence[int],
) -> tuple[Database, list[str], Counter[int]]:
    database = Database.create(workspace, schema_ir=_schema_ir(profile))
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
                profile=profile,
                batch_index=batch_index,
                batch_time=batch_time,
                entity_count=entity_count,
            )
            for index in range(next_index, next_index + actual)
        )
        defaults = _batch_meta_defaults(profile, batch_index)
        if defaults:
            result = database.commit_changes(
                assertions=inputs,
                revocations=(),
                meta_defaults=defaults,
            )
        else:
            # Keep the pre-tiering profile runnable against the Phase 2 source
            # revision, before ``meta_defaults`` was part of commit_changes.
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
        "get_claim_256": lambda: sum(
            ledger.get_claim(asrt_id) is not None for asrt_id in point_ids
        ),
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
        if path.name in excluded_names or any(
            path.name.endswith(suffix) for suffix in excluded_suffixes
        ):
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
        physical_meta_rows = {}
        for table in tables:
            columns = {
                str(row[1])
                for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            }
            if {"asrt_id", "key", "value"}.issubset(columns):
                physical_meta_rows[table] = int(
                    conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                )
    return {
        "durable_bytes": durable_bytes,
        "sqlite_bytes": sqlite_bytes,
        "tx_object_bytes": tx_object_bytes,
        "schema_object_bytes": schema_object_bytes,
        "tables": tables,
        "dbstat_bytes": dbstat,
        "physical_meta_rows": physical_meta_rows,
    }


def _workset_snapshot(ledger: Ledger, *, claim_count: int) -> dict[str, Any]:
    projected_meta_rows = len(ledger.find_meta())
    effective_meta_rows = len(ledger.effective_meta_rows())
    projected_annotation_rows = len(ledger.find_annotations())
    configured_lazy_meta_keys = sorted(getattr(ledger, "_lazy_meta_keys", ()))
    lazy_meta_keys = frozenset(configured_lazy_meta_keys)
    resident_claim_meta_events = len(ledger._claim_meta_events)
    resident_meta_rows = len(ledger._meta_rows_data)
    resident_annotation_rows = len(ledger._annotation_rows_data)
    claim_meta_event_index_references = resident_claim_meta_events + sum(
        len(rows)
        for index in (
            ledger._claim_meta_events_by_asrt_id,
            ledger._claim_meta_events_by_asrt_id_key,
        )
        for rows in index.values()
    )
    meta_index_references = resident_meta_rows + sum(
        len(rows)
        for index in (
            ledger._meta_by_asrt_id,
            ledger._meta_by_kind,
            ledger._meta_by_key,
            ledger._meta_by_asrt_id_key,
            ledger._meta_by_asrt_id_key_kind,
            ledger._meta_ingest_key_asrt_ids,
        )
        for rows in index.values()
    )
    annotation_index_references = (
        resident_annotation_rows
        + sum(len(rows) for rows in ledger._anno_by_asrt_id.values())
        + sum(len(rows) for rows in ledger._anno_by_ns_cat.values())
        + sum(len(rows) for rows in ledger._anno_by_key.values())
        + len(ledger._anno_by_identity)
    )
    eager_projection_meta_rows = resident_meta_rows + resident_annotation_rows
    resident_meta_bearing_row_objects = (
        resident_claim_meta_events + resident_meta_rows + resident_annotation_rows
    )
    resident_lazy_meta_event_objects = sum(
        event.key in lazy_meta_keys for event in ledger._claim_meta_events
    )
    resident_claim_domain_lazy_event_objects = sum(
        event.key == CLAIM_DOMAIN_LAZY_KEY for event in ledger._claim_meta_events
    )
    projected_lazy_meta_rows = sum(
        len(ledger.find_meta(key=key)) for key in configured_lazy_meta_keys
    )
    effective_lazy_meta_rows = sum(
        len(ledger.effective_meta_rows(key=key)) for key in configured_lazy_meta_keys
    )
    resident_tx_default_objects = sum(
        len(rows)
        for rows in getattr(ledger, "_tx_meta_defaults_by_tx_seq", {}).values()
    )
    return {
        "configured_lazy_meta_keys": configured_lazy_meta_keys,
        "claim_domain_lazy_key": CLAIM_DOMAIN_LAZY_KEY,
        "tx_lifted_key": TX_LIFTED_KEY,
        "projected_claim_domain_lazy_rows": len(
            ledger.find_meta(key=CLAIM_DOMAIN_LAZY_KEY)
        ),
        "resident_claim_domain_lazy_event_objects": (
            resident_claim_domain_lazy_event_objects
        ),
        "projected_lazy_meta_rows": projected_lazy_meta_rows,
        "projected_lazy_meta_rows_per_claim": round(
            projected_lazy_meta_rows / claim_count, 6
        ),
        "effective_lazy_meta_rows": effective_lazy_meta_rows,
        "effective_lazy_meta_rows_per_claim": round(
            effective_lazy_meta_rows / claim_count, 6
        ),
        "resident_lazy_meta_event_objects": resident_lazy_meta_event_objects,
        "resident_tx_default_objects": resident_tx_default_objects,
        "effective_ledger_meta_rows": effective_meta_rows,
        "effective_ledger_meta_rows_per_claim": round(
            effective_meta_rows / claim_count, 6
        ),
        "projected_ledger_meta_rows": projected_meta_rows,
        "projected_ledger_meta_rows_per_claim": round(projected_meta_rows / claim_count, 6),
        "projected_annotation_rows": projected_annotation_rows,
        "projected_annotation_rows_per_claim": round(projected_annotation_rows / claim_count, 6),
        "eager_projection_meta_rows": eager_projection_meta_rows,
        "eager_projection_meta_rows_per_claim": round(eager_projection_meta_rows / claim_count, 6),
        "resident_meta_row_objects": resident_meta_rows,
        "resident_annotation_row_objects": resident_annotation_rows,
        "resident_claim_meta_event_objects": resident_claim_meta_events,
        "resident_meta_bearing_row_objects": resident_meta_bearing_row_objects,
        "resident_claim_meta_event_index_references": claim_meta_event_index_references,
        "resident_meta_index_references": meta_index_references,
        "resident_annotation_index_references": annotation_index_references,
        "resident_meta_index_references_total": (
            claim_meta_event_index_references
            + meta_index_references
            + annotation_index_references
        ),
    }


def _distribution(values: Sequence[int], *, claim_count: int) -> dict[str, Any]:
    median = float(statistics.median(values))
    minimum = min(values)
    maximum = max(values)
    max_deviation = max(abs(minimum - median), abs(maximum - median))
    return {
        "median_bytes": median,
        "median_bytes_per_claim": round(median / claim_count, 3),
        "min_bytes": minimum,
        "max_bytes": maximum,
        "jitter_band_bytes": [minimum, maximum],
        "max_abs_deviation_percent": round(100 * max_deviation / median, 6),
    }


def _storage_summary(samples: Sequence[dict[str, int]], *, claim_count: int) -> dict[str, Any]:
    sqlite_values = [sample["sqlite_bytes"] for sample in samples]
    durable_values = [sample["durable_bytes"] for sample in samples]
    tx_object_values = [sample["tx_object_bytes"] for sample in samples]
    if len(set(tx_object_values)) != 1:
        raise AssertionError(
            "content-addressed tx-object byte delta must be exact across storage runs"
        )
    tx_object_bytes = tx_object_values[0]
    return {
        "sqlite_allocated": _distribution(sqlite_values, claim_count=claim_count),
        "durable_total": _distribution(durable_values, claim_count=claim_count),
        "tx_objects_exact": {
            "bytes": tx_object_bytes,
            "bytes_per_claim": round(tx_object_bytes / claim_count, 3),
        },
    }


def run(
    *,
    profile: str = PROFILE_THREE_TABLE_TIERED,
    claim_count: int,
    batch_sizes: Sequence[int],
    repeats: int,
    storage_runs: int,
) -> dict[str, Any]:
    if claim_count <= 0:
        raise ValueError("claim_count must be positive")
    if profile not in PROFILES:
        raise ValueError(f"unknown storage profile: {profile!r}")
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    if storage_runs < 5:
        raise ValueError("storage_runs must be at least five")
    if not batch_sizes or any(size <= 0 for size in batch_sizes):
        raise ValueError("batch_sizes must contain positive integers")

    storage_samples: list[dict[str, int]] = []
    reads: dict[str, Any] | None = None
    workset: dict[str, Any] | None = None
    layout: dict[str, Any] | None = None
    histogram: Counter[int] | None = None
    with tempfile.TemporaryDirectory(prefix="factgraph-slice3b-baseline-") as raw_tmp:
        root = Path(raw_tmp)
        for run_index in range(storage_runs):
            run_root = root / f"run-{run_index}"
            empty_workspace = run_root / "empty"
            empty = Database.create(empty_workspace, schema_ir=_schema_ir(profile))
            empty.close()
            empty_storage = _storage_snapshot(empty_workspace)

            filled_workspace = run_root / "filled"
            database, asrt_ids, current_histogram = _populate(
                filled_workspace,
                profile=profile,
                claim_count=claim_count,
                batch_sizes=batch_sizes,
            )
            database.close()

            if run_index == 0:
                database = Database.open(
                    filled_workspace,
                    schema_ir=_schema_ir(profile),
                )
                ledger = database._ledger_for_attach()
                workset = _workset_snapshot(ledger, claim_count=claim_count)
                reads = _read_benchmarks(ledger, asrt_ids, repeats=repeats)
                database.close()
                histogram = current_histogram

            filled_storage = _storage_snapshot(filled_workspace)
            if layout is None:
                layout = {
                    "tables": filled_storage["tables"],
                    "dbstat_bytes_first_run": filled_storage["dbstat_bytes"],
                    "persisted_physical_meta_rows": filled_storage["physical_meta_rows"],
                    "persisted_physical_meta_rows_total": sum(
                        filled_storage["physical_meta_rows"].values()
                    ),
                }
            storage_samples.append(
                {
                    key: filled_storage[key] - empty_storage[key]
                    for key in ("durable_bytes", "sqlite_bytes", "tx_object_bytes")
                }
            )

        if reads is None or workset is None or layout is None or histogram is None:
            raise AssertionError("storage baseline did not produce a first-run sample")

        return {
            "harness": "slice3b_storage_baseline_v3",
            "environment": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "sqlite": sqlite3.sqlite_version,
            },
            "workload": {
                "claim_count": claim_count,
                "profile": profile,
                "logical_effective_meta_entries_per_assertion": (
                    LOGICAL_META_PER_ASSERTION
                ),
                "claim_scoped_meta_entries_per_assertion_input": (
                    CLAIM_META_PER_ASSERTION[profile]
                ),
                "tx_default_meta_entries_per_commit": TX_DEFAULT_META_PER_BATCH[profile],
                "batch_sizes_repeating": list(batch_sizes),
                "batch_histogram": {str(size): count for size, count in sorted(histogram.items())},
                "commit_count": sum(histogram.values()),
                "meander_profile": (
                    "plan.ingest request group; five fixed effective meta entries; "
                    "projected and persisted meta profiles are measured outputs"
                ),
            },
            "layout": layout,
            "workset_after_cold_attach": workset,
            "storage": {
                "measurement_runs": storage_runs,
                "precision": (
                    "SQLite and durable totals are median estimates with a jitter band; "
                    "tx_objects_exact is the only byte-exact component"
                ),
                "delta_samples": storage_samples,
                "summary": _storage_summary(storage_samples, claim_count=claim_count),
            },
            "reads": reads,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", type=int, default=3_000)
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        default=PROFILE_THREE_TABLE_TIERED,
        help="storage/meta policy profile (default: three-table-tiered)",
    )
    parser.add_argument(
        "--batch-sizes",
        type=_parse_batch_sizes,
        default=DEFAULT_BATCH_SIZES,
        help="comma-separated repeating batch-size distribution (default: 3)",
    )
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--storage-runs", type=int, default=DEFAULT_STORAGE_RUNS)
    args = parser.parse_args()
    result = run(
        profile=args.profile,
        claim_count=args.claims,
        batch_sizes=args.batch_sizes,
        repeats=args.repeats,
        storage_runs=args.storage_runs,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
