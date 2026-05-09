# FactPy Kernel

`kernel` is the FactPy kernel implementation: a Python package that
provides schema authoring, fact storage, rule/derivation evaluation,
counterfactual analysis, and audit/proof primitives.

## Where to start

| Audience | Start here |
|---|---|
| **End users** of the SDK | [`sdk/docs/README.md`](sdk/docs/README.md) — Python product surface (FactGraph, DSL, errors) |
| **Contributors** working in a specific module | Pick the module's `docs/README.md` from the table below |
| **AI coding agents** working in this directory | [`AGENTS.md`](AGENTS.md) — module docs convention + update rules |

## Module map

| Module | Role | Docs |
|---|---|---|
| `sdk/` | Python product surface — `FactGraph` / `SDKStore`, schema authoring, DSL primitives, public error hierarchy. The recommended entry point for end users. | [`sdk/docs/README.md`](sdk/docs/README.md) |
| `application/` | Canonical runtime authority. Owns read/write/query/ingest plans + compiled-derivation runtime + frozen DTOs. SDK delegates here. Advanced importable for wire bridges and automation. | [`application/docs/README.md`](application/docs/README.md) |
| `audit/` | Audit DTOs (`RoundEvent`, `ProofFrameDiff`, etc.), round-event recorder lifecycle, audit package loader. | [`audit/docs/README.md`](audit/docs/README.md) |
| `core/` | Substrate — ledger, store, rules, evidence, derivation, protocol primitives. Low-level; consumed by `application`. | [`core/docs/README.md`](core/docs/README.md) |
| `adapters/` | Engine adapters (Souffle, ProbLog, PyReason). Registered at import time. | [`adapters/docs/README.md`](adapters/docs/README.md) |
| `authoring/` | Registry + authoring helpers for compiled rules / derivations. | [`authoring/docs/README.md`](authoring/docs/README.md) |
| `tests/` | Unit + integration tests for all modules. | (no separate doc — see test files directly) |

## Architecture in one sentence

User code → `kernel.sdk` (ergonomic facade) → `kernel.application` (canonical runtime) → `kernel.core` (substrate). Engine adapters plug into `core` via registration; audit DTOs and proof structures cross all layers as frozen types.

For the longer architectural narrative see
[`core/docs/01_architecture.en.md`](core/docs/01_architecture.en.md)
and
[`application/docs/01_overview_en.md`](application/docs/01_overview_en.md).
