from __future__ import annotations

import argparse
import json
from pathlib import Path

from workload_c_reference import compare_result_to_golden


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Workload C baseline results against golden output.")
    parser.add_argument("--input", required=True, help="Workload C input JSON used to produce the results")
    parser.add_argument("--golden", required=True, help="Golden output JSON")
    parser.add_argument("--results", nargs="+", required=True, help="One or more normalized result JSON files")
    parser.add_argument("--output", required=True, help="Comparison report JSON")
    parser.add_argument("--top-k", type=int, help="Optional Top-K override; defaults to golden.top_k")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    golden = json.loads(Path(args.golden).read_text(encoding="utf-8"))

    reports = []
    for result_path_str in args.results:
        result_path = Path(result_path_str)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        report = compare_result_to_golden(result, golden, payload, top_k=args.top_k)
        report["result_file"] = str(result_path)
        reports.append(report)

    output = {
        "workload": "C",
        "golden_file": str(Path(args.golden)),
        "input_file": str(Path(args.input)),
        "reports": reports,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
