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

## Quality Checks

The `dev` extra pins Ruff to `0.16.5` so local and CI lint checks use the same
rules. Install that extra before running the checks. Review tool upgrades
separately from source cleanup; Python 3.10 and 3.11 remain supported.

```bash
python -m ruff check src/factgraph tests
python -m mypy src/factgraph
```

## Pull Request Expectations

- Keep public behavior changes paired with module doc updates.
- Include the commands you ran and any known gaps.
- Keep commits scoped so doc, config, and production code changes can be reviewed independently.

## Releasing

Releases follow a 3-layer model: the development branch → `milestone/rc-vX.Y.Z-<date>`
(frozen anchor) → `release/X.Y.x` (clean projection) → `vX.Y.Z[-rc.N]` (tag).

The full pipeline is encapsulated in `scripts/release.sh`:

```bash
# Always dry-run first to validate the projection + verify pass
./scripts/release.sh v0.1.0-rc.1 --dry-run

# Then execute live (creates milestone, projects, verifies, tags, pushes)
./scripts/release.sh v0.1.0-rc.1
```

Before running:

1. Bump `version` in `pyproject.toml` to match the release (PEP 440 form, e.g.
   `0.1.0rc1` for tag `v0.1.0-rc.1`).
2. Move new entries from `## [Unreleased]` to a new versioned section in
   `CHANGELOG.md` with the release date.
3. Commit those changes on the development branch and ensure the tree is clean.
4. Run the dry-run; if it passes, run live.

The script enforces:
- `vX.Y.Z[-rc.N]` tag-name shape.
- Clean working tree.
- Source ref exists; tag does not exist yet (locally or on origin).
- Projection allowlist + deny patterns + bad-link checks all pass.
- (Unless `--skip-verify`) `pip install -e .` + the focused FactGraph test suite pass on
  the projected content.

The release branch (`release/X.Y.x`) is created on first release of a minor
version and reused for subsequent patches and rcs.

## Security

Do not commit secrets, API keys, credentials, or private data. Follow [docs/SECURITY.md](docs/SECURITY.md) for reporting and handling security issues.
