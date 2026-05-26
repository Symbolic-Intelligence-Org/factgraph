#!/usr/bin/env bash
set -euo pipefail

MONOREPO="${MONOREPO:-$(pwd)}"
STAGING="${STAGING:-/tmp/factgraph_projection}"
ALLOWLIST="${ALLOWLIST:-$MONOREPO/scripts/release_surface_allowlist.txt}"
MANIFEST="${MANIFEST:-$STAGING.manifest}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

require_file() {
  local path="$1"
  [[ -f "$path" ]] || fail "required file does not exist: $path"
}

require_file "$ALLOWLIST"
require_file "$MONOREPO/pyproject.toml"

case "$STAGING" in
  ""|"/"|"$MONOREPO"|"$MONOREPO/"*)
    fail "refusing unsafe STAGING path: $STAGING"
    ;;
esac

rm -rf "$STAGING" "$MANIFEST"
mkdir -p "$STAGING"

rsync -a --files-from="$ALLOWLIST" "$MONOREPO/" "$STAGING/"

(
  cd "$STAGING"
  find . -type f -o -type l | sed 's|^\./||' | sort > "$MANIFEST"
)

unexpected="$(
  comm -23 "$MANIFEST" <(sort "$ALLOWLIST") || true
)"
if [[ -n "$unexpected" ]]; then
  echo "FAIL: projection contains files not in allowlist:" >&2
  echo "$unexpected" >&2
  exit 1
fi

missing="$(
  comm -13 "$MANIFEST" <(sort "$ALLOWLIST") || true
)"
if [[ -n "$missing" ]]; then
  echo "FAIL: allowlisted files missing from projection:" >&2
  echo "$missing" >&2
  exit 1
fi

deny_patterns=(
  ".claude/*"
  "AGENTS.md"
  "*/AGENTS.md"
  "CLAUDE.md"
  "*/CLAUDE.md"
  "memory/*"
  "docs/blueprints/*"
  "docs/blueprint_history/*"
  "docs/references/*"
  "src/agent/*"
  "src/service/*"
  "src/domains/*"
  "third_party/*"
  "tools/*"
  ".tmp_backend_preview/*"
  ".gitmodules"
  "requirements/dev.txt"
  "scripts/*"
  "*/__pycache__/*"
  "*.pyc"
  "dist/*"
  "build/*"
  "*.egg-info/*"
  "archive/*"
  "out/*"
  "*_demo_output/*"
  "test.ipynb"
  "context.md"
  "关于mvp的思考.md"
  "best_conf.csv"
  "path_conf.csv"
)

while IFS= read -r rel; do
  for pattern in "${deny_patterns[@]}"; do
    case "$rel" in
      $pattern)
        fail "denylist hit: $rel matches $pattern"
        ;;
    esac
  done
done < "$MANIFEST"

bad_link_pattern='docs/blueprints|docs/blueprint_history|docs/references|memory/|\.claude|AGENTS\.md|src/agent|src/service|src/domains|src/kernel|kernel\.sdk|from kernel|third_party|tools/|requirements/dev\.txt|examples/|samples/'
bad_links="$(
  grep -RInE "$bad_link_pattern" \
    "$STAGING/README.md" \
    "$STAGING/README.en.md" \
    "$STAGING/docs" \
    "$STAGING/src/factgraph" \
    --include='*.md' 2>/dev/null || true
)"
if [[ -n "$bad_links" ]]; then
  echo "FAIL: projected docs contain private/excluded path references:" >&2
  echo "$bad_links" >&2
  exit 1
fi

echo "PROJECTION READY: $STAGING"
echo "manifest: $MANIFEST"
echo "files: $(wc -l < "$MANIFEST" | tr -d ' ')"
