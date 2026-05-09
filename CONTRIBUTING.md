# Contributing

FactPy Kernel uses a blueprint-driven workflow for non-trivial changes.

## Before You Change Code

- Read [AGENTS.md](AGENTS.md) for the repository workflow.
- For architecture-facing work, protocol changes, cross-module changes, features, or refactors, create or reuse an active blueprint under `docs/blueprints/active/`.
- Keep implementation truth in module docs under `src/*/docs/`; references under `docs/references/` are supporting material, not current behavior.
- Do not edit archived blueprints except for explicitly marked reconstructed archive work.

Tiny typo fixes, comment-only edits, and clearly local test fixes may skip a blueprint.

## Development Setup

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Test Baseline

Run the kernel test suite from the repository root:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
```

Current baseline: 709 tests, 1 skip.

## Quality Checks

```bash
python -m ruff check src/kernel/application
python -m ruff check src/kernel
python -m mypy src/kernel
```

Only the narrow `kernel.application` ruff check is expected to be clean today. Broader kernel ruff and mypy output is tracked as audit/report input until follow-up cleanup work makes those checks blocking.

## Pull Request Expectations

- Link the relevant active blueprint for non-trivial work.
- Keep public behavior changes paired with module doc updates.
- Include the commands you ran and any known gaps.
- Keep commits scoped so doc, config, and production code changes can be reviewed independently.

## Releasing

Releases follow a 3-layer model: `master` (dev) → `milestone/rc-vX.Y.Z-<date>`
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
3. Commit those changes on `master` and ensure the tree is clean.
4. Run the dry-run; if it passes, run live.

The script enforces:
- `vX.Y.Z[-rc.N]` tag-name shape.
- Clean working tree.
- Source ref exists; tag does not exist yet (locally or on origin).
- Projection allowlist + deny patterns + bad-link checks all pass.
- (Unless `--skip-verify`) `pip install -e .` + full kernel test suite pass on
  the projected content.

The release branch (`release/X.Y.x`) is created on first release of a minor
version and reused for subsequent patches and rcs.

## Security

Do not commit secrets, API keys, credentials, or private data. Follow [docs/SECURITY.md](docs/SECURITY.md) for reporting and handling security issues.
