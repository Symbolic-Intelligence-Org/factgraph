# factpy-kernel

**Append-only fact substrate and auditable reasoning kernel.**

> Language: [中文](README.md) | **English**

The v0.1 open-source / PyPI surface of `factpy-kernel` contains only the `kernel` package. It provides:

- an append-only fact ledger and field/assertion write semantics
- the canonical Python runtime authority: `kernel.application`
- the Python product surface: `kernel.sdk`
- rule / query / derivation authoring and runtime adapters
- audit package reader, query, DTO, and evidence graph surfaces

This repository is still a monorepo. `agent`, `service`, and `domains` are private / companion surfaces for internal development, HTTP delivery, LLM extraction, and ECSS domain bundles. They are not part of the v0.1 PyPI wheel and should not be treated as kernel-only OSS install targets.

For architecture principles, see [docs/architecture_principles.md](docs/architecture_principles.md). For the docs index, see [docs/README.md](docs/README.md). For contributor workflow, see [AGENTS.md](AGENTS.md).

## Install

After release:

```bash
pip install factpy-kernel
```

Use the kernel from source:

```bash
git clone <repo-url>
cd hnsm-backend
pip install -e .
```

Develop the full monorepo, including private companion surfaces and test dependencies:

```bash
pip install -r requirements/dev.txt
```

`requirements/dev.txt` installs service, agent, documents, extraction, observability, and other internal development dependencies. PyMuPDF / PyMuPDF4LLM belong to the private agent document parser surface and do not appear in the `factpy-kernel` PyPI metadata.

## Quickstart

```python
from kernel.sdk import Entity, Field, Identity, SDKStore


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


sdk = SDKStore.from_schema_classes([User])

alice = sdk.ref(User, user_id="u-1")
sdk.set(User.name, alice, "Alice")

snapshot = sdk.get(User, user_id="u-1")
print(snapshot.name)  # Alice
```

`kernel.sdk` is the user-facing Python product surface. Runtime authority lives in `kernel.application`; the SDK adapts ergonomic APIs, schema/DSL authoring, snapshots, batches, editors, and compatibility errors into the application runtime contract.

## Kernel Surface

| Area | Entry | Notes |
|---|---|---|
| SDK product API | `kernel.sdk` | Entity / Field / Identity / SDKStore / Query / Derivation user entrypoints |
| Runtime authority | `kernel.application` | read/write/query/ingest/derivation protocol DTOs and executors |
| Core primitives | `kernel.core` | ledger, rules, evidence, candidate support, low-level store semantics |
| Authoring | `kernel.authoring` | rule/schema authoring helpers and validation surfaces |
| Adapters | `kernel.adapters` | optional engine integration surfaces, depending on installed third-party engines |
| Audit | `kernel.audit` | exported audit package reader/query/DTO/evidence graph consumer contract |

Current implementation docs:

- [src/kernel/sdk/docs/README.md](src/kernel/sdk/docs/README.md)
- [src/kernel/application/docs/README.md](src/kernel/application/docs/README.md)
- [src/kernel/core/docs/01_architecture.md](src/kernel/core/docs/01_architecture.md)
- [src/kernel/audit/docs/README.md](src/kernel/audit/docs/README.md)
- [src/kernel/adapters/docs/README.md](src/kernel/adapters/docs/README.md)
- [src/kernel/authoring/docs/README.md](src/kernel/authoring/docs/README.md)

## Audit And Optional Domains

`kernel.audit` reads exported audit packages and provides offline queries for runs, candidates, rule traces, evidence graphs, and related DTOs.

ECSS compliance matrix row assembly belongs to `domains.ecss.compliance`; it is not a required capability of the kernel-only wheel. For monorepo compatibility, `AuditQuery.list_compliance_matrix(...)` remains as an optional-domain convenience. If `domains.ecss` is missing, it raises `AuditOptionalDomainError` instead of silently making the domain package a kernel dependency.

## Monorepo Companion Surfaces

These directories exist in the repository, but they are not part of the v0.1 PyPI wheel:

| Surface | Purpose |
|---|---|
| `agent` | LLM document extraction, workflow/session helpers, agent HTTP app |
| `service` | FastAPI delivery for runtime/rules/registry and audit static UI |
| `domains` | Domain bundles such as ECSS compliance presets and helpers |

Use the monorepo development install path when working on those companion surfaces:

```bash
pip install -r requirements/dev.txt
```

## Tests

Kernel-only package guard:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_wheel_kernel_only_packaging.py"
```

Full monorepo regression is split across 5 segments:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/agent/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/service/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s src/domains/ecss/tests -p "test_*.py"
PYTHONPATH=src python -m unittest discover -s tools/benchmarks/tests -p "test_*.py"
```

Current branch baseline:1097 tests,3 skips.

## License And Security

This project is licensed under the Apache License 2.0; see [LICENSE](LICENSE).

Secret handling and API key rotation: [docs/SECURITY.md](docs/SECURITY.md).
