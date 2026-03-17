from __future__ import annotations

import argparse
import json
from pathlib import Path

from workload_a_reference import compare_result_to_golden


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Workload A baseline results against golden output.")
    parser.add_argument("--input", required=True, help="Workload A input JSON used to produce the results")
    parser.add_argument("--golden", required=True, help="Golden output JSON")
    parser.add_argument("--results", nargs="+", required=True, help="One or more normalized result JSON files")
    parser.add_argument("--output", required=True, help="Comparison report JSON")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    golden = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    reports = []
    for result_file in args.results:
        result_path = Path(result_file)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        report = compare_result_to_golden(result, golden, payload)
        report["result_file"] = str(result_path)
        reports.append(report)

    output = {
        "workload": "A",
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
