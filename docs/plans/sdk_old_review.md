# `docs/sdk_old/` Review

## Goal

Determine whether `docs/sdk_old/` should be treated as:

- current implementation reference
- duplicated snapshot
- diverged historical material
- source material that still needs to be merged into current SDK docs

## Review Standard

The comparison standard is semantic, not filename-only.

For each file, review in this order:

1. Does it cover the same scope as a current file under `src/factpy_kernel/sdk/docs/`?
2. If yes, is the documented behavior still aligned with current SDK semantics?
3. If it diverges, is the divergence historical-only, or does it contain still-useful material missing from the current docs?

Classification labels used here:

- `duplicate`
  - effectively the same document, low-risk snapshot
- `stale-diverged`
  - same scope, but semantic content has drifted and is no longer safe as current truth
- `merge-candidate`
  - contains still-useful material not yet captured in current docs
- `keep-current`
  - should remain part of the active documentation set

## Summary Judgment

Current overall judgment:

- `docs/sdk_old/` is **not** a safe current reference
- the folder is **not** just a byte-for-byte duplicate
- the files are best treated as **historical snapshots of an older SDK semantic layer**
- default action should be **archive**, not “keep in place”

Archived target:

- `docs/history/legacy/sdk/`

Current status:

- archived
- non-authoritative

## File-by-File Result

### `README.md`

Matching current file:

- `src/factpy_kernel/sdk/docs/README.md`

Classification:

- `stale-diverged`

Why:

- old README points to a three-document set (`01` to `03`)
- current README documents a broader active set, including:
  - `00_user_guide.md`
  - `04_api_surface.md`
  - bilingual CN/EN sync rules
- current README also defines a stronger maintenance rule: update `00` first, then synchronize the rest

Decision:

- archive old README as historical snapshot
- do not use it as entrypoint for current SDK docs

### `01_alignment_matrix.md`

Matching current file:

- `src/factpy_kernel/sdk/docs/01_alignment_matrix.md`

Classification:

- `stale-diverged`

Key stale claims in old file:

- schema semantics still include `Meta.is_record`, `dims`, and `fact_key`
- `FieldAssertions.chosen` is described as a live API surface
- `find` dims-aware filtering is deferred rather than removed
- `accept` options are documented under the older shape

Current doc explicitly states newer boundaries:

- old field semantics `functional/temporal/dims/fact_key` are removed
- assertion view no longer exposes `.chosen`
- `Query DSL + sdk.run(query)` is now part of active SDK behavior
- `temporal_view` is removed from the runtime SDK path

Decision:

- archive old matrix
- do not merge wholesale
- if any wording is still valuable, selectively port phrasing only after semantic verification

### `02_readwrite_and_ingest.md`

Matching current file:

- `src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md`

Classification:

- `stale-diverged`

Key stale claims in old file:

- write semantics still use `functional` / `temporal`
- `find(...)` still documents `temporal_view`
- dims-aware values and `DimensionedValue` are part of snapshot semantics
- assertions API still documents `.chosen`
- ingest items still carry optional `dims`

Current doc explicitly states newer boundaries:

- wire ops no longer carry `dims/fact_key`
- `temporal_view` is not supported
- SDK field cardinality is described via `single|multi`
- assertion view is described as `active/history/at/version`

Decision:

- archive old read/write reference
- do not merge behavior claims without revalidation against code

### `03_rules_and_derivations.md`

Matching current file:

- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`

Classification:

- `stale-diverged`

Key stale claims in old file:

- derivation examples still use `materialize_as="fact" | "record"`
- document scope is only Rule/Derivation, without the current Query DSL framing
- older path-sugar and lowering narrative predates several current rule/query constraints

Current doc explicitly states newer boundaries:

- Query DSL is part of the active SDK documentation set
- `Body(...)` with confidence is documented and constrained
- derivation `head` semantics are stricter, including `primary_key` restrictions
- runtime `temporal_view` derivation path is explicitly rejected

Decision:

- archive old rule/derivation reference
- do not treat it as current DSL contract

## Final Recommendation

Recommended disposition for all files in `docs/sdk_old/`:

- classify as `stale-diverged`
- archive under `docs/history/legacy/sdk/`
- add a clear note that the active SDK reference lives under `src/factpy_kernel/sdk/docs/`

## Practical Migration Action

1. mark `docs/sdk_old/` as non-authoritative immediately
2. preserve it only as legacy reference
3. point readers to `src/factpy_kernel/sdk/docs/README.md`
4. only mine specific wording or examples from `sdk_old` when a concrete gap is found in current docs

## Notable Risk If Left Unchanged

The biggest risk is not duplication.

The biggest risk is **semantic misread**:

- a reader sees `sdk_old` and still opens it because it is under `docs/`
- the file looks implementation-aligned
- but it documents removed concepts such as `dims`, `functional/temporal`, `.chosen`, or `materialize_as`
- the reader then writes new code against an obsolete semantic model

That makes `docs/sdk_old/` a documentation hazard, not just a cleanup nuisance.
