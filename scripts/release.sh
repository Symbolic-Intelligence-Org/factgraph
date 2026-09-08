#!/usr/bin/env bash
# Build local distributions from one immutable commit. No Git refs or installs.
set -euo pipefail

usage() {
  echo "Usage: $0 VERSION --outdir NEW_DIRECTORY [--source-ref REF] [--python PYTHON]"
  echo "Requires Python 3.11+ with the project's pinned build extra installed."
  echo "Builds a local candidate only; never tags, pushes or publishes."
}
fail() { echo "FAIL: $*" >&2; exit 1; }

VERSION=""
SOURCE_REF="HEAD"
OUTPUT=""
BUILD_PYTHON="python3"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-ref|--outdir|--python)
      [[ $# -ge 2 ]] || fail "missing value for $1"
      case "$1" in
        --source-ref) SOURCE_REF="$2" ;;
        --outdir) OUTPUT="$2" ;;
        --python) BUILD_PYTHON="$2" ;;
      esac
      shift 2 ;;
    -h|--help) usage; exit 0 ;;
    -*) fail "unsupported option: $1 (the old projection/push workflow is retired)" ;;
    *) [[ -z "$VERSION" ]] || fail "unexpected argument: $1"; VERSION="$1"; shift ;;
  esac
done
[[ -n "$VERSION" && -n "$OUTPUT" ]] || { usage >&2; exit 1; }
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || fail "commit tracked changes before building"
SOURCE_SHA="$(git rev-parse --verify "$SOURCE_REF^{commit}")"
SOURCE_TREE="$(git rev-parse "$SOURCE_SHA^{tree}")"
SOURCE_EPOCH="$(git show -s --format=%ct "$SOURCE_SHA")"
BUILD_PYTHON="$("$BUILD_PYTHON" -c 'import sys; assert sys.version_info >= (3, 11), "build requires Python 3.11+"; print(sys.executable)')"
OUTPUT="$("$BUILD_PYTHON" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve())' "$OUTPUT")"
[[ ! -e "$OUTPUT" ]] || fail "output already exists; choose a new candidate directory: $OUTPUT"

TEMPORARY="$(mktemp -d "${TMPDIR:-/tmp}/factgraph-release.XXXXXXXX")"
trap 'rm -rf "$TEMPORARY"' EXIT
mkdir "$TEMPORARY/source"
git archive "$SOURCE_SHA" | tar -x -C "$TEMPORARY/source"
"$BUILD_PYTHON" - "$TEMPORARY/source/pyproject.toml" "$VERSION" <<'PY'
import sys, tomllib
from importlib.metadata import version
from packaging.version import Version
with open(sys.argv[1], "rb") as stream:
    project = tomllib.load(stream)["project"]
assert project["name"] == "factgraph"
assert Version(project["version"]) == Version(sys.argv[2]), "version does not match source commit"
for name, expected in (("build", "1.6.0"), ("setuptools", "84.0.0"), ("wheel", "0.48.0")):
    assert version(name) == expected, f"install pinned build extra: {name}=={expected}"
PY
SOURCE_DATE_EPOCH="$SOURCE_EPOCH" "$BUILD_PYTHON" -m build \
  --sdist --wheel --no-isolation --outdir "$TEMPORARY/dist" "$TEMPORARY/source"
"$BUILD_PYTHON" - "$TEMPORARY/dist" "$SOURCE_SHA" "$SOURCE_TREE" "$SOURCE_EPOCH" <<'PY'
import hashlib, json, platform, sys, zipfile
from email.parser import BytesParser
from importlib.metadata import version
from pathlib import Path
root = Path(sys.argv[1])
wheels = list(root.glob("*.whl"))
assert len(wheels) == 1 and len(list(root.glob("*.tar.gz"))) == 1
with zipfile.ZipFile(wheels[0]) as archive:
    metadata = BytesParser().parsebytes(archive.read(next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))))
artifacts = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "size_bytes": p.stat().st_size} for p in sorted(root.iterdir())}
manifest = {
    "artifact_kind": "factgraph.release-candidate.v1",
    "source_commit": sys.argv[2], "source_tree": sys.argv[3], "source_date_epoch": int(sys.argv[4]),
    "distribution": metadata["Name"], "version": metadata["Version"],
    "build_python": platform.python_version(),
    "build_tools": {n: version(n) for n in ("build", "setuptools", "wheel")},
    "artifacts": artifacts, "published": False,
}
(root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
(root / "SHA256SUMS").write_text("".join(f"{v['sha256']}  {k}\n" for k, v in artifacts.items()))
PY
mkdir -p "$(dirname "$OUTPUT")"
mkdir "$OUTPUT"
cp "$TEMPORARY/dist/"* "$OUTPUT/"
echo "Local candidate: $OUTPUT"
echo "Source: $SOURCE_SHA (tree $SOURCE_TREE)"
echo "Run producer and installed-consumer acceptance before publication or promotion."
