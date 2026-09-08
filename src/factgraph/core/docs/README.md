# Core Module Docs

`src/factgraph/core/` is FactPy's substrate layer — it provides the
Store / Ledger / native evaluator / engine adapters / projection
semantics that every higher layer depends on. The documents in this
directory target advanced importable consumers (integrators /
contributors), not SDK end-users learning the surface.

## Entry points

- [01_architecture.en.md](./01_architecture.en.md) — Core
  architecture overview: Store / Ledger / native evaluator + the
  engine support matrix (`native | souffle | problog | pyreason`),
  key data models, and entry points.
- [02_quality_assessment.en.md](./02_quality_assessment.en.md) —
  Quality assessment framework (code-snapshot perspective).
- [03_progress_roadmap.en.md](./03_progress_roadmap.en.md) —
  Development progress and future trajectory (post-routemap state).
- [04_public_contract_v1.md](./04_public_contract_v1.md) — Public
  contract v1: stable external behavioral constraints across `core /
  service / sdk` v1.
- [04_service_layer.md](./04_service_layer.md) — Current state of
  the service layer (the boundary between HTTP/BFF delivery and
  core).
- [../semantics/docs/README.md](../semantics/docs/README.md) —
  Core semantics scaffolding: `SemanticsProfile` validation and
  inspection helpers for future runtime projection work.
- [../store/docs/README.md](../store/docs/README.md) — Core store
  substrate docs: three-table `Ledger` storage, metadata events/tiering,
  and the Database identity boundary built above it.
- [../policy/README.md](../policy/README.md) — Active/chosen projection,
  premise-key closure, and two-level effective metadata policy.

> Note: the `04` numeric prefix was historically split between two
> different topics (`04_public_contract_v1` + `04_service_layer`);
> the two do not conflict and the existing filenames are preserved.

## Boundaries

### Canonical codec errors

`protocol/tup_v1.py` rejects the explicitly validated invalid tag and value
types with `ValueError`, just as it does invalid value syntax or range.
`evidence/write_protocol.py` relies on that error family to raise
`WriteProtocolError` with the original cause before appending any assertion.
`protocol/idref_v1.py` likewise rejects a non-string entity type with
`ValueError`. These are existing codec contracts, not requests to coerce input.
Their individual `TRY004` exceptions must not be replaced by `TypeError`
as a lint-only repair. `tests/test_protocol_v1.py` covers the affected branches,
canonical float bytes, and the no-write error translation at `set_field` and
`add_field`. This does not promise to normalize every arbitrary malformed
Python object into `ValueError`.

### Documentation ownership

- This directory is **not the SDK getting-started guide** — the SDK
  user guide lives at
  [`src/factgraph/sdk/docs/00_user_guide.en.md`](../../sdk/docs/00_user_guide.en.md).
- This directory is **not the application capability docs** — Check
  / Diagnose / Fact Overlay / ProofFrame / rule actions / Why-not
  live in
  [`src/factgraph/application/docs/`](../../application/docs/).
- This directory is **not the audit consumer docs** — audit package
  + round events + ProofFrame diff live in
  [`src/factgraph/audit/docs/`](../../audit/docs/).
- This directory is **not the routemap closure narrative** — the
  round-story closure narrative is recorded in §10 Outcome of the
  round-story-completion-plan blueprint (an internal design record).
