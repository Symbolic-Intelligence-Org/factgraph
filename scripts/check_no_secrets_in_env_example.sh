#!/usr/bin/env bash
set -euo pipefail

if grep -Eq '^[A-Z][A-Z0-9_]*=[^[:space:]#]+' .env.example; then
  echo "ERROR: .env.example contains uncommented non-empty values."
  exit 1
fi

echo "OK: .env.example contains no uncommented non-empty values."

