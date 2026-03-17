from __future__ import annotations

import argparse
import json
from pathlib import Path

from workload_c_reference import build_workload_c_golden, generate_workload_c


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Workload C input and optional golden output.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--struct-facts", type=int, default=1000)
    parser.add_argument("--evidence-facts", type=int, default=200)
    parser.add_argument("--entities", type=int, default=100)
    parser.add_argument("--scale", default="1x")
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--output", required=True, help="Path to workload C input JSON")
    parser.add_argument("--golden-output", help="Optional path to golden output JSON")
    args = parser.parse_args()

    payload = generate_workload_c(
        n_struct=args.struct_facts,
        n_evidence=args.evidence_facts,
        n_entities=args.entities,
        seed=args.seed,
        scale=args.scale,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    if args.golden_output:
        golden = build_workload_c_golden(payload, top_k=args.top_k)
        golden_path = Path(args.golden_output)
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(
            json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )


if __name__ == "__main__":
    main()
