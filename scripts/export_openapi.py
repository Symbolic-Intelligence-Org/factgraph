#!/usr/bin/env python3
"""OpenAPI spec drift guard.

Compares the checked-in ``docs/api/openapi.yaml`` against the live FastAPI
spec produced by ``service.app_v1.app`` at ``(path, method)``
granularity. Does NOT rewrite the yaml — the checked-in file is hand-curated
and its schema precision is intentionally higher than the FastAPI
auto-generated output.

Exit codes:
    0  — yaml ``(path, method)`` set matches live spec exactly
    1  — drift detected (missing in yaml and/or extra in yaml)
    2  — runtime error (cannot import app, cannot read yaml, etc.)

Usage:
    PYTHONPATH=src python scripts/export_openapi.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "docs" / "api" / "openapi.yaml"
ALLOWED_METHODS = {"get", "post", "delete", "put", "patch"}


def _load_live_pairs() -> set[tuple[str, str]]:
    sys.path.insert(0, str(ROOT / "src"))
    os.environ.setdefault("FACTPY_KERNEL_AUTH_DISABLED", "true")
    from service.app_v1 import app  # noqa: E402

    spec = app.openapi()
    pairs: set[tuple[str, str]] = set()
    for path, ops in spec.get("paths", {}).items():
        if not isinstance(ops, dict):
            continue
        for method in ops:
            if method.lower() in ALLOWED_METHODS:
                pairs.add((path, method.upper()))
    return pairs


def _load_yaml_pairs() -> set[tuple[str, str]]:
    try:
        import yaml  # type: ignore
    except ImportError:
        print(
            "ERROR: PyYAML not installed. `pip install pyyaml`",
            file=sys.stderr,
        )
        sys.exit(2)

    if not YAML_PATH.exists():
        print(f"ERROR: {YAML_PATH} does not exist", file=sys.stderr)
        sys.exit(2)

    with YAML_PATH.open() as f:
        spec = yaml.safe_load(f)

    pairs: set[tuple[str, str]] = set()
    paths = (spec or {}).get("paths", {}) or {}
    for path, ops in paths.items():
        if not isinstance(ops, dict):
            continue
        for method in ops:
            if method.lower() in ALLOWED_METHODS:
                pairs.add((path, method.upper()))
    return pairs


def _print_pairs(label: str, pairs: set[tuple[str, str]]) -> None:
    print(f"  {label} ({len(pairs)}):")
    for path, method in sorted(pairs):
        print(f"    {method:6s} {path}")


def main() -> int:
    try:
        live = _load_live_pairs()
    except Exception as exc:
        print(f"ERROR: cannot load live FastAPI spec: {exc}", file=sys.stderr)
        return 2

    yaml_pairs = _load_yaml_pairs()

    missing_in_yaml = live - yaml_pairs
    extra_in_yaml = yaml_pairs - live

    if not missing_in_yaml and not extra_in_yaml:
        print(
            f"OK: {YAML_PATH.relative_to(ROOT)} covers all "
            f"{len(live)} (path, method) pairs from the live FastAPI spec."
        )
        return 0

    print(
        f"DRIFT: {YAML_PATH.relative_to(ROOT)} does not match the live "
        f"FastAPI spec at (path, method) granularity."
    )
    if missing_in_yaml:
        _print_pairs("missing in yaml (present in live spec but absent in yaml)", missing_in_yaml)
    if extra_in_yaml:
        _print_pairs("extra in yaml (absent in live spec but present in yaml)", extra_in_yaml)
    print()
    print("To fix: hand-edit docs/api/openapi.yaml; do not overwrite with auto-generated output.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
