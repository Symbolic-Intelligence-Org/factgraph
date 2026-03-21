from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from statistics import median

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from factpy_kernel.core.evidence.write_protocol import set_field
from factpy_kernel.core.mapping.canon import resolve_mapping_predicate
from factpy_kernel.core.policy.chosen import compute_chosen_for_predicate
from factpy_kernel.core.store.api import Store
from factpy_kernel.core.view.projector import project_view_facts


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark core Ledger-heavy paths.")
    parser.add_argument("--rows", type=int, default=3000, help="Number of synthetic entities/mentions")
    parser.add_argument("--rounds", type=int, default=5, help="Benchmark rounds per operation")
    args = parser.parse_args()

    store = Store(_schema())
    _seed(store, args.rows)

    schema_pred_country = next(p for p in store.schema_ir["predicates"] if p["pred_id"] == "person:country")
    schema_pred_map = next(p for p in store.schema_ir["predicates"] if p["pred_id"] == "er:canon_of")

    print(
        {
            "rows": args.rows,
            "claims": len(store.ledger.claims),
            "meta_rows": len(store.ledger.meta_rows),
            "rounds": args.rounds,
        }
    )
    _print_result(
        "compute_chosen_for_predicate(country)",
        _bench(lambda: compute_chosen_for_predicate(store.ledger, schema_pred_country), args.rounds),
    )
    _print_result(
        "project_view_facts()",
        _bench(lambda: project_view_facts(store.ledger, store.schema_ir), args.rounds),
    )
    _print_result(
        "resolve_mapping_predicate(er:canon_of)",
        _bench(lambda: resolve_mapping_predicate(store.ledger, schema_pred_map), args.rounds),
    )


def _bench(fn, rounds: int) -> tuple[float, float]:
    values: list[float] = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        values.append((time.perf_counter() - t0) * 1000.0)
    return min(values), median(values)


def _print_result(name: str, stats: tuple[float, float]) -> None:
    min_ms, median_ms = stats
    print(f"{name}: min_ms={min_ms:.2f} median_ms={median_ms:.2f}")


def _seed(store: Store, rows: int) -> None:
    for i in range(rows):
        person = f"idref_v1:Person:{i}"
        mention = f"idref_v1:Mention:{i}"
        canon = f"idref_v1:Person:{i % 1000}"
        set_field(
            store.ledger,
            "person:country",
            person,
            [("string", f"c{i % 17}")],
            {"source": "bench", "source_loc": f"country-{i}"},
        )
        set_field(
            store.ledger,
            "person:lang",
            person,
            [("string", "en")],
            {"source": "bench", "source_loc": f"lang-a-{i}"},
        )
        set_field(
            store.ledger,
            "person:lang",
            person,
            [("string", "de")],
            {"source": "bench", "source_loc": f"lang-b-{i}"},
        )
        set_field(
            store.ledger,
            "er:canon_of",
            mention,
            [("entity_ref", canon)],
            {"source": "bench", "source_loc": f"map-{i}"},
        )


def _schema() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {"entity_type": "Person", "identity_fields": [{"name": "source_id", "type_domain": "string"}]},
            {"entity_type": "Mention", "identity_fields": [{"name": "source_id", "type_domain": "string"}]},
        ],
        "predicates": [
            {
                "pred_id": "person:country",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "country", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
                "cardinality": "single",
            },
            {
                "pred_id": "person:lang",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "lang", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
                "cardinality": "multi",
            },
            {
                "pred_id": "er:canon_of",
                "arg_specs": [
                    {"name": "mention", "type_domain": "entity_ref"},
                    {"name": "canonical", "type_domain": "entity_ref"},
                ],
                "group_key_indexes": [0],
                "cardinality": "single",
                "is_mapping": True,
                "mapping_kind": "single_valued",
                "mapping_key_positions": [0],
                "mapping_value_positions": [1],
            },
        ],
        "projection": {"entities": [], "predicates": ["person:country", "person:lang", "er:canon_of"]},
        "protocol_version": {"idref_v1": "idref_v1", "tup_v1": "tup_v1", "export_v1": "export_v1"},
        "generated_at": "2026-01-01T00:00:00Z",
    }


if __name__ == "__main__":
    main()
