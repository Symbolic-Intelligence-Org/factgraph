from __future__ import annotations

import argparse
import json
from pathlib import Path

from workload_b_reference import build_workload_b_golden, generate_workload_b


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Workload B input and optional golden output.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--entities", type=int, default=100)
    parser.add_argument("--t-max", type=int, default=20)
    parser.add_argument("--scale", default="1x")
    parser.add_argument("--output", required=True, help="Path to workload B input JSON")
    parser.add_argument("--golden-output", help="Optional path to golden output JSON")
    args = parser.parse_args()

    payload = generate_workload_b(
        n_entities=args.entities,
        t_max=args.t_max,
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
        golden = build_workload_b_golden(payload)
        golden_path = Path(args.golden_output)
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(
            json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )


if __name__ == "__main__":
    main()
