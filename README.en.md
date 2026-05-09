# factpy-kernel

**Append-only fact substrate and auditable reasoning kernel.**

> Language: [中文](README.md) | **English**

The v0.1 open-source / PyPI surface of `factpy-kernel` contains only the `kernel` package. It provides:

- an append-only fact ledger and field/assertion write semantics
- the canonical Python runtime authority: `kernel.application`
- the Python product surface: `kernel.sdk`
- rule / query / derivation authoring and runtime adapters
- audit package reader, query, DTO, and evidence graph surfaces

The v0.1 public source and PyPI wheel are both scoped to the kernel-only surface. LLM extraction, HTTP delivery, domain bundles, and other companion surfaces are not part of the `factpy-kernel` v0.1 release.

For architecture principles, see [docs/architecture_principles.md](docs/architecture_principles.md).

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

## Quickstart

```python
from kernel.sdk import Entity, Field, Identity, FactGraph


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


fg = FactGraph.from_schema_classes([User])

alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.name, alice, "Alice")

snapshot = fg.read.get(User, user_id="u-1")
print(snapshot.name)  # Alice
```

`FactGraph` is the v0.1 SDK top-level entrypoint. Its 8 taxonomy namespaces (`schema` / `read` / `write` / `eval` / `what_if` / `audit` / `package` / `views`) teach the conceptual layering at first contact. `FactGraph` is a literal alias of `SDKStore`; the flat form `fg.ref(...)` / `fg.set(...)` / `fg.get(...)` is supported alongside the nested form as **foundational API** — neither deprecated nor scheduled for removal.

`kernel.sdk` is the user-facing Python product surface. Runtime authority lives in `kernel.application`; the SDK adapts ergonomic APIs, schema/DSL authoring, snapshots, batches, editors, and compatibility errors into the application runtime contract.

## Choose Your Layer

| Scenario | Recommended entry | Why |
|---|---|---|
| Human-authored Python product code defining `Entity` / `Field` and running queries or derivations | `kernel.sdk` | Provides descriptors, DSL sugar, snapshots, batches, editors, and user-facing exceptions |
| Automation process / HTTP bridge / wire protocol receiving JSON-like requests | `kernel.application` protocol + executor | Accepts SDK-independent DTOs and does not require SDK `Field` descriptors or Python DSL objects |
| Lowest-level ledger / evidence / rule primitives | `kernel.core` | Intended for runtime implementers, not as the normal user entrypoint |
| Reading an exported audit package | `kernel.audit` | Offline reader/query/DTO/evidence consumer surface |

## v0.1 Public Boundary

| Tier | Surface | Commitment |
|---|---|---|
| Product public | `kernel.sdk` | Ergonomic API and outward compatibility surface for human-authored Python product code. |
| Advanced importable | `kernel.application`, `kernel.audit` | Runtime/query authority for automation, wire bridges, and audit consumers; importable directly, but not an SDK ergonomic facade. |
| Out of v0.1 package | `service`, `agent`, `domains`, internal workflow docs, tutorial/demo add-back candidates | Not part of the `factpy-kernel` v0.1 kernel-only wheel or public source surface. |

L Direction G1-G5 added narrow SDK shells for Check, Diagnose, Why-not, Fact Overlay, ProofFrame Recheck, rule-action what-if, and ProofFrame Diff, now exposed through the `FactGraph` taxonomy as product API. Round events recorder lifecycle (`start_round` / `record_round_event` / `finalize_round`) and Frontier trace remain on `kernel.audit` / `kernel.core` advanced importable surfaces; promoting those boundaries to product-facing wrappers still requires a separate public API blueprint.

## Kernel Surface

| Area | Entry | Notes |
|---|---|---|
| SDK product API | `kernel.sdk` | Entity / Field / Identity / FactGraph (with alias SDKStore) / Query / Derivation user entrypoints |
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

## Tests

Kernel-only package guard:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_wheel_kernel_only_packaging.py"
```

Kernel regression:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
```

The current kernel suite baseline is tracked by CI and blueprint audit records; local environments may show additional environment-only errors for optional adapters or cold-start import order.

## License And Security

This project is licensed under the Apache License 2.0; see [LICENSE](LICENSE).

Secret handling and API key rotation: [docs/SECURITY.md](docs/SECURITY.md).
