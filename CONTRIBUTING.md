# Contributing

This repository contains the FactGraph product package. Cross-project coordination
and internal AI workflow state are maintained outside this repository.

Keep implementation truth in the module docs under `src/factgraph/*/docs/`, and
update public documentation and tests whenever behavior changes.

## Development Setup

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]" pytest
```

## Tests

Run the test suite from the repository root:

```bash
PYTHONPATH=src python -m pytest
```

Cross-module test helpers use the repository-root `tests.*` namespace. A relative
import in a directory without a package marker has no parent under default
pytest collection. Keep the default import mode and the same fixture imports
working for both pytest and unittest; do not hide collection failures with an
import-mode override.

## Quality Checks

The `dev` extra pins Ruff to `0.16.5` so local and CI lint checks use the same
rules. Install that extra before running the checks. Review tool upgrades
separately from source cleanup; Python 3.10 and 3.11 remain supported.

Selected nested generic forward references retain quoted names because removing
them changes `get_type_hints` results on Python 3.10. Their line-local `UP037`
exceptions preserve existing behavior; `tests/sdk/test_annotation_compatibility.py`
checks each affected hint on the supported versions. Do not replace those
exceptions with a blanket rule ignore or silently alter the runtime hints.

```bash
python -m ruff check src/factgraph tests
python -m mypy src/factgraph
```

## Pull Request Expectations

- Keep public behavior changes paired with module doc updates.
- Include the commands you ran and any known gaps.
- Keep commits scoped so doc, config, and production code changes can be reviewed independently.

## Releasing

The complete current repository is the release source. Use the pinned build
extra in a dedicated Python 3.11+ environment, commit the candidate version and
release notes, then build an immutable local candidate:

```bash
python3.11 -m venv /tmp/factgraph-build-env
/tmp/factgraph-build-env/bin/python -m pip install ".[build]"
bash scripts/release.sh 0.4.0rc1 --source-ref HEAD \
  --python /tmp/factgraph-build-env/bin/python --outdir dist/candidates/0.4.0rc1-a
```

The output directory must be new. The script archives the selected commit,
checks version and tool identities, builds the complete package and records
source/commit/tool hashes. It never changes refs, publishes, installs into an
existing environment, or replaces a retained wheel. Repeat in a second output
directory and compare wheel SHA-256 before acceptance.

The old milestone/projection/release-branch pipeline and its source allowlist
are historical tooling; the current builder does not use them. New package
modules must never be omitted by that old list.

[Release and compatibility guidance](docs/releases.md) defines producer checks,
installed-consumer acceptance, artifact rollback and the separate publication
step. A matching `v<PEP440 version>` tag pushed after approval runs the reusable
CI gate and PyPI trusted-publisher workflow. The `pypi` environment/publisher
configuration must already exist. Local candidate builds do not publish.

## Security

Do not commit secrets, API keys, credentials, or private data. Follow [docs/SECURITY.md](docs/SECURITY.md) for reporting and handling security issues.
