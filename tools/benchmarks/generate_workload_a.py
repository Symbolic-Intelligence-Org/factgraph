from __future__ import annotations

import argparse
import json
from pathlib import Path

from workload_a_reference import build_workload_a_golden, generate_workload_a


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Workload A input and optional golden output.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--nodes", type=int, default=200)
    parser.add_argument("--edges", type=int, default=800)
    parser.add_argument("--scale", default="1x")
    parser.add_argument("--output", required=True, help="Path to workload A input JSON")
    parser.add_argument("--golden-output", help="Optional path to golden output JSON")
    args = parser.parse_args()

    payload = generate_workload_a(
        n_nodes=args.nodes,
        n_edges=args.edges,
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
        golden = build_workload_a_golden(payload)
        golden_path = Path(args.golden_output)
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(
            json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )


if __name__ == "__main__":
    main()
