#!/usr/bin/env bash
#
# release.sh — one-command release for FactGraph.
#
# Encapsulates the full milestone → projection → release-branch → tag flow
# documented in CONTRIBUTING.md "Releasing" section.
#
# USAGE
#   ./scripts/release.sh <version> [options]
#
# ARGUMENTS
#   <version>       Tag name in semver-with-v form, e.g. v0.1.0-rc.1, v0.1.0,
#                   v0.2.0-rc.1. Determines the release branch (release/X.Y.x).
#
# OPTIONS
#   --dry-run       Run the full pipeline locally; do NOT push to origin and
#                   clean up local refs at the end. Use to validate the
#                   workflow without affecting the remote.
#   --skip-verify   Skip the pip install + test step. Faster but less safe.
#   --source-ref R  Source dev ref to release from (default: master).
#   --yes           Skip interactive confirmation prompt.
#   -h | --help     Show this help.
#
# EXAMPLES
#   ./scripts/release.sh v0.1.0-rc.1 --dry-run
#   ./scripts/release.sh v0.1.0-rc.1
#   ./scripts/release.sh v0.1.0 --source-ref milestone/post-l-2026-05-09
#

set -euo pipefail

# --- argument parsing ---------------------------------------------------------

VERSION=""
DRY_RUN=false
SKIP_VERIFY=false
SOURCE_REF="master"
ASSUME_YES=false

usage() {
  sed -n '2,/^$/p' "$0" | sed 's|^# \?||'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)      DRY_RUN=true; shift ;;
    --skip-verify)  SKIP_VERIFY=true; shift ;;
    --source-ref)   SOURCE_REF="$2"; shift 2 ;;
    --yes)          ASSUME_YES=true; shift ;;
    -h|--help)      usage 0 ;;
    -*)             echo "unknown option: $1" >&2; usage 1 ;;
    *)              [[ -z "$VERSION" ]] && VERSION="$1" || { echo "unexpected arg: $1" >&2; usage 1; }; shift ;;
  esac
done

[[ -z "$VERSION" ]] && { echo "error: version is required" >&2; usage 1; }

# --- helpers ------------------------------------------------------------------

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

color() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
info()  { color "36" "  $*"; }
warn()  { color "33" "WARN  $*"; }
fail()  { color "31" "FAIL  $*"; exit 1; }
step()  { echo; color "1;34" "==> $*"; }

# --- validate version ---------------------------------------------------------

if ! [[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]]; then
  fail "version must match vX.Y.Z[-rc.N], got: $VERSION"
fi

VERSION_BARE="${VERSION#v}"                                # 0.1.0-rc.1
VERSION_MAJOR_MINOR="$(echo "$VERSION_BARE" | cut -d. -f1-2)"  # 0.1
RELEASE_BRANCH="release/${VERSION_MAJOR_MINOR}.x"          # release/0.1.x
DATE_TAG="$(date +%Y-%m-%d)"
MILESTONE_BRANCH="milestone/rc-${VERSION_BARE}-${DATE_TAG}"

# --- preflight checks ---------------------------------------------------------

step "Preflight checks"

# Working tree clean (no staged or unstaged tracked changes; untracked OK)
if ! git diff --quiet || ! git diff --cached --quiet; then
  fail "working tree has uncommitted changes; commit or stash first"
fi
info "working tree clean"

# Source ref exists and resolves
if ! SOURCE_SHA="$(git rev-parse --verify "$SOURCE_REF^{commit}" 2>/dev/null)"; then
  fail "source ref does not exist: $SOURCE_REF"
fi
info "source ref: $SOURCE_REF @ ${SOURCE_SHA:0:8}"

# Tag does not already exist
if git rev-parse --verify "refs/tags/$VERSION" >/dev/null 2>&1; then
  fail "tag already exists locally: $VERSION (delete it first if reissuing)"
fi
if git ls-remote --tags origin "$VERSION" 2>/dev/null | grep -q "$VERSION"; then
  fail "tag already exists on origin: $VERSION"
fi
info "tag $VERSION does not exist yet"

# Required scripts exist
[[ -x scripts/project_release_surface.sh ]] || fail "scripts/project_release_surface.sh not found or not executable"
[[ -f scripts/release_surface_allowlist.txt ]] || fail "scripts/release_surface_allowlist.txt not found"
info "projection script + allowlist present"

# Release branch state on origin
if git ls-remote --heads origin "$RELEASE_BRANCH" 2>/dev/null | grep -q "$RELEASE_BRANCH"; then
  RELEASE_BRANCH_EXISTS=true
  info "release branch exists on origin: $RELEASE_BRANCH (will add new commit)"
  # Snapshot local release-branch SHA so dry-run cleanup can restore it.
  RELEASE_BRANCH_PREDRY="$(git rev-parse --verify "refs/heads/$RELEASE_BRANCH" 2>/dev/null || true)"
else
  RELEASE_BRANCH_EXISTS=false
  info "release branch does not exist: $RELEASE_BRANCH (will create orphan)"
  RELEASE_BRANCH_PREDRY=""
fi

# --- plan summary -------------------------------------------------------------

step "Plan"
cat <<EOF
  Version            : $VERSION
  Source ref         : $SOURCE_REF (@ ${SOURCE_SHA:0:8})
  Milestone (new)    : $MILESTONE_BRANCH
  Release branch     : $RELEASE_BRANCH ($([[ "$RELEASE_BRANCH_EXISTS" == true ]] && echo "exists, will append" || echo "new orphan"))
  Tag                : $VERSION (annotated)
  Verify             : $([[ "$SKIP_VERIFY" == true ]] && echo "SKIPPED (--skip-verify)" || echo "pip install -e . && focused tests")
  Mode               : $([[ "$DRY_RUN" == true ]] && echo "DRY-RUN (no push, full cleanup)" || echo "LIVE (push + persist)")
EOF

if [[ "$ASSUME_YES" == false ]]; then
  echo
  read -r -p "Proceed? [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || { warn "aborted by user"; exit 0; }
fi

# --- cleanup trap -------------------------------------------------------------

SOURCE_WT="/tmp/release-source-${VERSION_BARE}"
RELEASE_WT="/tmp/release-branch-${VERSION_BARE}"
STAGING="/tmp/release-staging-${VERSION_BARE}"

cleanup() {
  local rc=$?
  step "Cleanup"
  git worktree remove --force "$SOURCE_WT" 2>/dev/null || true
  git worktree remove --force "$RELEASE_WT" 2>/dev/null || true
  rm -rf "$STAGING" "$STAGING.manifest" 2>/dev/null || true
  if [[ "$DRY_RUN" == true ]]; then
    # Drop local milestone + tag created during dry-run
    git branch -D "$MILESTONE_BRANCH" 2>/dev/null || true
    git tag -d "$VERSION" 2>/dev/null || true
    # Restore local release branch ref to whatever it was before the dry-run
    # (the worktree's git checkout -B advanced it; here we revert)
    if [[ "$RELEASE_BRANCH_EXISTS" == true && -n "${RELEASE_BRANCH_PREDRY:-}" ]]; then
      git update-ref "refs/heads/$RELEASE_BRANCH" "$RELEASE_BRANCH_PREDRY" 2>/dev/null || true
    elif [[ "$RELEASE_BRANCH_EXISTS" == false ]]; then
      git branch -D "$RELEASE_BRANCH" 2>/dev/null || true
    fi
  fi
  if [[ $rc -ne 0 ]]; then
    color "31" "release.sh exited with status $rc"
  fi
  exit $rc
}
trap cleanup EXIT

# --- 1. milestone branch ------------------------------------------------------

step "1/8 Create milestone branch"
if git rev-parse --verify "refs/heads/$MILESTONE_BRANCH" >/dev/null 2>&1; then
  warn "milestone $MILESTONE_BRANCH already exists locally; reusing"
else
  git branch "$MILESTONE_BRANCH" "$SOURCE_SHA"
  info "created $MILESTONE_BRANCH at ${SOURCE_SHA:0:8}"
fi

if [[ "$DRY_RUN" == false ]]; then
  git push origin "$MILESTONE_BRANCH"
  info "pushed milestone to origin"
else
  info "(dry-run) would push milestone to origin"
fi

# --- 2. source worktree -------------------------------------------------------

step "2/8 Create source worktree"
git worktree add "$SOURCE_WT" "$MILESTONE_BRANCH"
info "worktree at $SOURCE_WT"

# --- 3. projection ------------------------------------------------------------

step "3/8 Run projection"
MONOREPO="$SOURCE_WT" \
ALLOWLIST="$REPO_ROOT/scripts/release_surface_allowlist.txt" \
STAGING="$STAGING" \
bash "$REPO_ROOT/scripts/project_release_surface.sh"
info "projection ready: $STAGING ($(wc -l < "$STAGING.manifest" | tr -d ' ') files)"

# --- 4. verify ----------------------------------------------------------------

if [[ "$SKIP_VERIFY" == false ]]; then
  step "4/8 Verify (pip install + tests)"
  (
    cd "$STAGING"
    python -m pip install -e . --quiet
    PYTHONPATH=src python -m unittest \
      tests.application.protocol.test_rule \
      tests.application.protocol.test_rule_expr \
      tests.sdk.test_ruleexpr_inspect \
      tests.sdk.test_rule_naming \
      tests.application.protocol.test_rule_aggregate \
      tests.test_branch_identity_rule_inspect \
      tests.application.protocol.test_rule_expr_lowering \
      tests.application.protocol.test_rule_expr_lowering_adapter \
      tests.sdk.test_rule_expr_evaluate \
      tests.application.protocol.test_rule_expr_head_validation \
      tests.test_sdk_assertion_record_set_view_filters 2>&1 | tail -3
  )
  info "verify passed"
else
  step "4/8 Verify"
  warn "skipped (--skip-verify)"
fi

# --- 5. release branch worktree ----------------------------------------------

step "5/8 Create release branch worktree"
if [[ "$RELEASE_BRANCH_EXISTS" == true ]]; then
  git fetch origin "$RELEASE_BRANCH"
  git worktree add "$RELEASE_WT" "origin/$RELEASE_BRANCH"
  cd "$RELEASE_WT"
  git checkout -B "$RELEASE_BRANCH"
  # clear tracked content to fully replace with new projection
  git rm -rf . >/dev/null 2>&1 || true
else
  git worktree add --detach "$RELEASE_WT" "$SOURCE_SHA"
  cd "$RELEASE_WT"
  git checkout --orphan "$RELEASE_BRANCH"
  git rm -rf . >/dev/null 2>&1 || true
fi
info "release worktree at $RELEASE_WT (branch $RELEASE_BRANCH)"

# --- 6. commit ----------------------------------------------------------------

step "6/8 Commit projected content"
rsync -a "$STAGING/" ./
git add .
git commit -m "release $VERSION

Projected from $MILESTONE_BRANCH (${SOURCE_SHA:0:8}).
$(wc -l < "$STAGING.manifest" | tr -d ' ') files in release surface.

See CHANGELOG.md for changes."
RELEASE_SHA="$(git rev-parse HEAD)"
info "committed: ${RELEASE_SHA:0:8}"

# --- 7. push branch + tag -----------------------------------------------------

cd "$REPO_ROOT"

step "7/8 Tag + push"
git tag -a "$VERSION" "$RELEASE_SHA" -m "Release $VERSION"
info "tag $VERSION created locally"

if [[ "$DRY_RUN" == false ]]; then
  git push origin "$RELEASE_BRANCH"
  git push origin "$VERSION"
  info "pushed branch + tag to origin"
else
  info "(dry-run) would push: $RELEASE_BRANCH and tag $VERSION"
fi

# --- 8. summary ---------------------------------------------------------------

step "8/8 Done"
cat <<EOF
  Released:       $VERSION
  Release commit: ${RELEASE_SHA:0:8}
  Branch:         $RELEASE_BRANCH
  Source:         $SOURCE_REF (${SOURCE_SHA:0:8})
  Milestone:      $MILESTONE_BRANCH
EOF

if [[ "$DRY_RUN" == true ]]; then
  warn "DRY-RUN mode — nothing pushed; local refs cleaned up"
else
  echo
  info "next: optionally create GitHub Release"
  info "  gh release create $VERSION --title \"$VERSION\" --notes-from-tag"
fi
