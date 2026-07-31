from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from statistics import median

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from factgraph.core.store.database import (  # noqa: E402
    AssertionInput,
    Database,
    resolve_database_workspace_paths,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure Phase 1 O(delta) Database commit latency against ledger cardinality."
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=int,
        default=(100_000, 1_000_000),
        help="Synthetic ledger cardinalities to measure (default: 100000 1000000)",
    )
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument(
        "--max-median-ratio",
        type=float,
        default=3.0,
        help="Fail when slowest/fastest median exceeds this bound (default: 3.0)",
    )
    args = parser.parse_args()
    sizes = sorted(set(args.sizes))
    if not sizes or sizes[0] < 0:
        parser.error("--sizes must contain non-negative integers")
    if args.rounds < 1:
        parser.error("--rounds must be positive")

    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="factgraph-phase1-bench-") as tmp:
        workspace = Path(tmp) / "workspace"
        db = Database.create(workspace, schema_ir=_schema_ir())
        paths = resolve_database_workspace_paths(workspace)
        seeded = 0
        with sqlite3.connect(paths.assertions) as seed_conn:
            # Fixture setup intentionally bypasses Database so cardinality can be
            # varied without paying the protocol cost under measurement. The
            # disposable workspace is never opened or treated as valid afterward.
            seed_conn.execute("PRAGMA synchronous = OFF")
            for size in sizes:
                _seed_claim_rows(seed_conn, seeded, size)
                seed_conn.commit()
                seeded = size
                samples = _measure_commits(db, size=size, rounds=args.rounds)
                results.append(
                    {
                        "ledger_rows": size,
                        "median_ms": median(samples),
                        "min_ms": min(samples),
                        "samples_ms": samples,
                    }
                )
        db.close()

    medians = [float(result["median_ms"]) for result in results]
    ratio = max(medians) / min(medians) if min(medians) > 0 else float("inf")
    report = {
        "gate": "stage-a-phase1-write-latency-flatness",
        "max_median_ratio": args.max_median_ratio,
        "observed_median_ratio": ratio,
        "passed": ratio <= args.max_median_ratio,
        "results": results,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


def _seed_claim_rows(conn: sqlite3.Connection, start: int, stop: int) -> None:
    conn.executemany(
        "INSERT INTO claims (asrt_id, pred_id, e_ref, rest_terms) VALUES (?, ?, ?, ?)",
        (
            (
                f"asrt:{index:032x}",
                "bench:seed",
                f"idref_v1:Bench:{index}",
                "[]",
            )
            for index in range(start, stop)
        ),
    )


def _measure_commits(db: Database, *, size: int, rounds: int) -> list[float]:
    samples: list[float] = []
    for round_index in range(rounds):
        assertion = AssertionInput(
            pred_id="bench:write",
            fact_tuple=(
                ("entity_ref", f"idref_v1:Bench:write-{size}-{round_index}"),
                ("string", "value"),
            ),
        )
        started = time.perf_counter_ns()
        db.commit_assertions((assertion,))
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return samples


def _schema_ir() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {
                "entity_type": "Bench",
                "identity_fields": [{"name": "id", "type_domain": "string"}],
            }
        ],
        "predicates": [
            {
                "pred_id": "bench:write",
                "arg_specs": [
                    {"name": "entity", "type_domain": "entity_ref"},
                    {"name": "value", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            }
        ],
        "projection": {"entities": ["Bench"], "predicates": ["bench:write"]},
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": "2026-07-31T00:00:00Z",
    }


if __name__ == "__main__":
    main()
