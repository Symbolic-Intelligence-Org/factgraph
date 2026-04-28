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
python -m pip install -e ".[extraction,documents,service,observability,dev]"
```

The `documents` extra includes PyMuPDF-based parsing dependencies. Review their upstream license terms before redistributing a build that enables document parsing by default.

## Test Baseline

Run the five test segments from the repository root:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/agent/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/service/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/domains/ecss/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s tools/benchmarks/tests -p "test_*.py"
```

## Quality Checks

The current OSS-prep baseline stages quality tooling before making all checks blocking:

```bash
python -m ruff check src/kernel/application
python -m ruff check src/kernel src/service tools
python -m mypy src/kernel src/service
```

Only the narrow application ruff check is expected to be clean today. Broader ruff and mypy output is tracked as audit/report input until follow-up cleanup work makes those checks blocking.

## Pull Request Expectations

- Link the relevant active blueprint for non-trivial work.
- Keep public behavior changes paired with module doc updates.
- Include the commands you ran and any known gaps.
- Keep commits scoped so doc, config, and production code changes can be reviewed independently.

## Security

Do not commit secrets, API keys, credentials, or private data. Follow [docs/SECURITY.md](docs/SECURITY.md) for reporting and handling security issues.
