#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/2] factpy_kernel tests (where AST gate on)"
python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'

echo "[2/2] factpy_kernel tests (where AST gate off compatibility)"
FACTPY_WHERE_AST_VALIDATE=0 python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'
