#!/usr/bin/env bash
set -euo pipefail

# Release-facing guard for the ReadPolicy call-site migration.
#
# Scope is intentionally narrow: current module docs, OpenAPI, and the
# maintained assertion-view example. Tests, active blueprints, archives, and
# historical references may still mention legacy syntax when documenting or
# asserting rejection behavior.

targets=(
  "src/kernel/sdk/docs"
  "src/service/docs"
  "src/kernel/core/docs/04_service_layer.md"
  "docs/api/openapi.yaml"
  "examples/05_sdk_assertion_views.ipynb"
)

status=0

run_forbidden_check() {
  local label="$1"
  local pattern="$2"

  if rg -n --glob '!**/archive/**' --glob '!**/.ipynb_checkpoints/**' "$pattern" "${targets[@]}"; then
    echo "ERROR: legacy view syntax found: ${label}" >&2
    status=1
  fi
}

run_forbidden_check "ViewSpec name" 'ViewSpec'
run_forbidden_check "view_spec key/name" 'view_spec'
run_forbidden_check "legacy projection-policy wording" 'projection-policy'
run_forbidden_check "old view= call-site keyword on read/run" 'fg\.(read\.find|run)\([^\n]*\bview\s*='
run_forbidden_check "ReadPolicy/ViewSpec stored through fg.views.create" 'fg\.views\.create\([^\n]*(ReadPolicy|ViewSpec)'
run_forbidden_check "old runtime queries/views doc path" '03_runtime_queries_views\.md|runtime_queries_views'

if [[ "$status" -ne 0 ]]; then
  exit "$status"
fi

echo "OK: no legacy ViewSpec/view syntax in release-facing docs and examples."
