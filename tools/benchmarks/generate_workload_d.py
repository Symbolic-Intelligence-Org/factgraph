from __future__ import annotations

import argparse
import json
from pathlib import Path

from workload_d_reference import build_workload_d_golden, generate_workload_d


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Workload D input and optional golden output.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--conditions", type=int, default=20)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--weighted-ratio", type=float, default=0.8)
    parser.add_argument("--confidence-ratio", type=float, default=0.7)
    parser.add_argument("--scale", default="1x")
    parser.add_argument("--output", required=True, help="Path to workload D input JSON")
    parser.add_argument("--golden-output", help="Optional path to golden output JSON")
    args = parser.parse_args()

    payload = generate_workload_d(
        n_conditions=args.conditions,
        max_depth=args.max_depth,
        weighted_ratio=args.weighted_ratio,
        confidence_ratio=args.confidence_ratio,
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
        golden = build_workload_d_golden(payload)
        golden_path = Path(args.golden_output)
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(
            json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )


if __name__ == "__main__":
    main()
