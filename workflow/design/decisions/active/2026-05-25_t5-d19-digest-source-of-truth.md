# D19 Decision: T5 Digest Source-of-Truth

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks authoritative sources and formulas for T5 result, row, claim, evidence, and audit digests before return-shape implementation.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md` Q5, F2, F6, F11, and section 6 C68 triage.
  - D16 `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md` sections 4.1, 4.7, and 4.8.
  - D17 `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md` sections 4.3-4.8.
  - D18 `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md` sections 4.1-4.8.
  - Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` sections 5.8.2, 5.8.5, C64-C68, and C69.
  - Sibling future-design note `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md:1-14`, `:272-325`, and `:771-792` as non-authoritative evidence runtime context.
  - Shipped `src/factgraph/core/protocol/digests.py:7-12`, `src/factgraph/application/protocol/rule.py:107-113`, `src/factgraph/core/derivation/candidates.py:13-115`, `src/factgraph/core/semantics/profile.py:25-95`, `src/factgraph/sdk/store.py:2289-2390`, `src/factgraph/application/derivation_runtime.py:64-148`, and `src/factgraph/core/store/database.py:193-199`, `:407-410`.
- Outputs / Downstream:
  - D20 explanation envelope and evidence graph replay.
  - D21 `row.close()` and closed-head construction.
  - D23 legacy hard-cut implementation plan.
  - D25 evaluate/explain semantics consistency.
  - D26 semantics commitments scope and adapter implementation policy.
  - Stage 3 T5 synthesis and DTO / return-shape implementation blueprints.
- Related:
  - `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md`
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Depends on: D16, D17, and D18 reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

Parent C68 requires stable `row_id`, `row_digest`, `result_digest`, `bindings_digest`, and `expr_digest` values based on canonical serialization. D17 turns those parent commitments into public DTO fields, but deliberately leaves formulas and source-of-truth questions to D19. D18 then hard-cuts public `evaluate(...)` to `EvaluateResult`, so T5 cannot defer digest fields until after the return-shape implementation.

Shipped code already has several digest-like sources:

- `sha256_hex(...)` and `sha256_token(...)` helpers in `core.protocol.digests`;
- application `Rule.content_digest`, a bare SHA-256 hex digest over rule `ports` and `where`, excluding `id` and `version`;
- `CandidateSet.candidate_key` / `candidate_id`, content- and run-scoped candidate identifiers that remain internal after D17 / D18;
- `support_digest`, `key_tuple_digest`, and tuple digests in the core derivation runtime;
- `SemanticsProfile`, a normalized core profile shape consumed by ProbLog and PyReason;
- database-layer `view_digest_for(...)`, but no shipped SDK-level `EvaluateResult.view_snapshot_digest` source.

Evidence-tree v1 is a sibling future-design input, not current implementation truth: its header marks it as a draft skeleton and non-authoritative reference note. D19 cites it only for local evidence-runtime context: `EvidenceNode` / `EvidenceEdge` extension data lives in `engine_meta`, `raw_kind` / `bound` are the canonical quantitative carriers, and evidence runtime consumes `EvaluateRow.bindings` rather than re-evaluating bindings. D19 does not adopt the internal evidence graph schema; D20, D22, D25, and D26 will cite evidence-tree v1 on demand, while full evidence-tree schema implementation remains a separate future cycle.

D19 decides how T5 uses those sources without exposing internal candidate identifiers or inventing duplicate formulas in downstream D-docs.

## 2. Scope

This decision locks:

- public ID format principles for `EvaluateResult.result_id`, `EvaluateRow.row_id`, and `EvidenceRef.ref_id`;
- digest algorithm and canonical serialization rules for new T5 public `*_digest` fields;
- authoritative sources for `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `semantics_digest`, `result_digest`, `Claim.digest`, `EvidenceRef.fact_digest`, and `EvidenceRef.closed_head_digest`;
- how existing shipped `Rule.content_digest` and `CandidateSet` identifiers may be consumed;
- how `engine_version`, `adapter_version`, and `evaluated_at` relate to result digesting;
- failure behavior when a mandatory digest source is unavailable.

## 3. Non-Scope

This decision does not lock:

- DTO ownership or field presence; D17 owns those;
- public return-shape migration mechanics; D18 owns them;
- `Explanation` and `EvidenceGraph` field shapes; D20 owns them;
- `row.close()` construction semantics for the closed head; D21 owns them;
- why-not migration; D22 owns it;
- legacy API hard-cut mechanics and service-route updates; D23 owns them;
- final SDK `Rule` naming; D24 owns it;
- evaluate/explain warning or raise policy for semantics mismatch; D25 owns it;
- semantics commitment implementation details for C73-C78; D26 owns them;
- database/view architecture beyond selecting a required source for `view_snapshot_digest`.

## 4. Decision

### 4.1 New T5 public digests use canonical bytes plus `sha256:` tokens

All new public T5 fields ending in `_digest` use canonical serialization bytes and `sha256_token(...)`, producing `sha256:<64 hex>` strings. D19 does not allow Python `repr(...)`, incidental `dict` ordering, display strings, object ids, timestamps, or adapter-native structures as digest input.

Existing shipped `Rule.content_digest` remains a bare SHA-256 hex string. T5 may embed it in canonical payloads under an explicit field name such as `rule_content_sha256_hex`, but T5 must not reformat existing `Rule.content_digest` into `sha256:` or change the rule digest formula.

Public IDs are not all `sha256:` digest tokens:

- `EvaluateResult.result_id` is an `evalr_v1:<hex>` identifier;
- `EvaluateRow.row_id` keeps the parent format `<run_id>:<short_bindings_hash>`;
- `EvidenceRef.ref_id` is an `evref_v1:<hex>` identifier.

Those IDs are still computed from canonical bytes. The prefix difference makes it clear whether a field is a public object id or a reusable audit digest.

### 4.2 `run_id`, `result_id`, and `row_id` have one public source each

`EvaluateResult.run_id` is the public evaluation invocation id. The T5 evaluate wrapper owns it once per public `evaluate(...)` call. It may pass that id into existing `DerivationEvaluateRequest.run_id` or normalize internal `CandidateSet.run_id` values after runtime evaluation, but the public `EvaluateResult.run_id` must not be an arbitrary "first candidate wins" value.

`EvaluateResult.result_id` is computed after `run_id` and the evaluation context digests are known, before row evidence refs are exposed:

```text
result_id = "evalr_v1:" + sha256_hex(
  canonical(
    "evaluate_result_id_v1",
    run_id,
    expr_digest,
    rule_set_digest,
    view_snapshot_digest,
    semantics_digest,
    engine,
    head.id,
    head.content_digest,
  )
)
```

It intentionally excludes row data, `EvidenceRef.ref_id`, `result_digest`, `evaluated_at`, and live resolver state. This avoids cyclic references and lets each `EvidenceRef` point back to a stable result envelope id.

`EvaluateRow.row_id` follows the parent format:

```text
row_id = f"{run_id}:{sha256_hex(canonical(bindings))[:16]}"
```

The short hash uses public `EvaluateRow.bindings` after all application-level value normalization. It must not include internal lowering vars, support artifacts, resolver callables, adapter-native evidence, or `CandidateSet.candidate_id`. If two public rows in one result would produce the same `row_id`, the implementation must collapse them into one row or raise an implementation error before returning `EvaluateResult`; duplicate public row ids are not allowed.

### 4.3 Claim, evidence-ref, and row digest formulas are flat

`Claim.digest` is:

```text
sha256_token(canonical("evaluate_claim_v1", kind, name, arguments))
```

where `arguments` are the public claim arguments after the same value normalization used for `bindings`. D17's public `Claim` remains distinct from storage-layer `ledger.Claim`.

`EvidenceRef.fact_digest` is always exactly `EvaluateRow.claim.digest`. No runtime candidate digest, ledger assertion id, or support digest may substitute for it.

`EvidenceRef.closed_head_digest` is the digest of the closed-head form used for this row. D19 locks the formula shape:

```text
sha256_token(canonical("closed_head_v1", closed_head.id, closed_head.content_digest))
```

D21 owns how `closed_head` is constructed. D19 only requires the digest to include the closed head id and the closed head `content_digest`; using `Rule.content_digest` alone is insufficient because shipped `Rule.content_digest` excludes `id`.

`EvidenceRef.ref_id` is:

```text
"evref_v1:" + sha256_hex(
  canonical("evidence_ref_v1", result_id, row_id, fact_digest, closed_head_digest)
)
```

A private row digest may be used as input to `EvaluateResult.result_digest`:

```text
row_digest = sha256_token(
  canonical(
    "evaluate_row_v1",
    row_id,
    bindings,
    claim.digest,
    raw_kind,
    bound,
    evidence_ref.fact_digest,
    evidence_ref.closed_head_digest,
  )
)
```

`row_digest` is not a D17 public `EvaluateRow` field. It is an implementation helper for deterministic result auditing.

### 4.4 Expression, rule-set, view, and semantics digests are separate

`expr_digest` is the canonical digest of the evaluated expression or compiled derivation source before result-row mapping. For RuleExpr input, it is based on the lowered expression structure: branch shape, occurrence aliases, source rule identity pairs `(rule.id, rule.content_digest)`, joins, and head-dispatch category metadata needed to distinguish inline, external, and projection heads. It excludes live store data and output row values. For legacy `Inference` or structured derivation dict input, it is based on the normalized compiled derivation plan shape. It must not be a rendered expression string.

`rule_set_digest` is the canonical aggregate digest of authoring rule definitions that participate in the evaluated source. Each application Rule entry uses `(rule.id, rule.content_digest)`. Rule `version` stays warning / documentation metadata and must not enter this digest. The application head Rule is represented separately by `EvaluateResult.head`, `result_id`, and `result_digest`; it is not duplicated into `rule_set_digest` unless the head also appears as a source rule in the expression body.

Legacy derivation dict / `Inference` inputs that do not have application Rule occurrences use a compiled-plan pseudo-entry containing derivation id, derivation version, normalized heads, and body IR. This keeps `rule_set_digest` populated without pretending legacy SDK rules are application Rules before D24.

`view_snapshot_digest` is mandatory for every public `EvaluateResult`. Its authoritative source is a private store/view snapshot helper over the exact facts visible to the evaluation. Attached database views should use the database view digest substrate when available. In-memory SDK stores without database view identity must compute a deterministic digest over the projected view facts plus schema digest. T5 must not return a placeholder, wall-clock-derived value, schema-only digest, or empty string for `view_snapshot_digest`.

`semantics_digest` is `None` when no semantics profile participates. When semantics is present, wrappers are lowered first, and the digest is computed from the normalized core `SemanticsProfile` fields (`name`, `engine`, `version`, `engine_options`, `uncertainty_projection`, `temporal_projection`, `rule_projection`, `certainty_projection`, `output_readback`, and `fallback`). D25 may decide mismatch behavior between evaluate and explain, but it must consume the D19 digest source.

Evidence-tree v1 `engine_meta` keys, including `raw_kind` / `bound`, are not authoritative digest sources in D19. They are downstream evidence rendering carriers. D19 keeps quantitative identity on the D17 row fields and leaves internal graph-node metadata to D20 / a future evidence-tree cycle.

### 4.5 `engine_version`, `adapter_version`, and `evaluated_at` are metadata, not hidden digest sources

`EvaluateResult.engine` is the resolved engine name used by evaluation.

`EvaluateResult.engine_version` is nullable unless the selected engine exposes a stable runtime version string. `EvaluateResult.adapter_version` is nullable unless the selected adapter exposes a stable adapter version string. D19 forbids synthetic versions derived from Python module names, object reprs, or installed package guesses. D26 may add adapter-specific version sources when it decides semantics adapter implementation policy.

`EvaluateResult.evaluated_at` is a frozen evaluation timestamp. It is not input to `result_id`, `row_id`, `ref_id`, row digests, or `result_digest`. Re-running the same evaluation at a different time should change `evaluated_at`, but not change deterministic audit digests unless the view, semantics, rule source, engine, or rows changed.

### 4.6 `result_digest` summarizes the public result without cycles

`EvaluateResult.result_digest` is:

```text
sha256_token(
  canonical(
    "evaluate_result_v1",
    result_id,
    run_id,
    row_digests_in_public_row_order,
    head.id,
    head.content_digest,
    engine,
    engine_version,
    adapter_version,
    expr_digest,
    rule_set_digest,
    view_snapshot_digest,
    semantics_digest,
  )
)
```

It excludes `evaluated_at`, live resolver state, Python object identity, `EvidenceRef.ref_id`, and private support artifacts. Row digests exclude `EvidenceRef.ref_id`, so no digest cycle exists.

The public row order must be deterministic before constructing `EvaluateResult`. D19 does not force a particular sorting key if a prior D-doc or implementation blueprint needs user-visible ordering, but the same rows in the same public order must produce the same `result_digest`.

### 4.7 CandidateSet identifiers remain internal

T5 may use existing `CandidateSet` data as input to row construction, but the following fields are not public source-of-truth for T5 row identity:

- `CandidateSet.candidate_id`;
- `CandidateSet.candidate_key`;
- `CandidateSet.key_tuple_digest`;
- `CandidateSet.tup_digest`;
- `CandidateSet.support_digest`;
- `CandidateSet.generated_at`.

They may help implement conversion and evidence lookup, but D17/D18 classify `CandidateSet` as an internal artifact. Public row identity comes from `run_id + bindings`; public fact identity comes from `Claim.digest`; public evidence lookup comes from `EvidenceRef`.

### 4.8 Missing mandatory digest sources are SDK boundary errors

If T5 cannot compute `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `Claim.digest`, `EvidenceRef.closed_head_digest`, `EvidenceRef.ref_id`, or `result_digest`, public `evaluate(...)` must fail before returning `EvaluateResult`.

The error bucket is `SDKStoreError` when the failure is an SDK/runtime integration gap, not a user-authored semantic invalidity. D20/D21 may introduce user-facing errors for invalid explain/close calls, but D19 does not add a public error subclass.

`semantics_digest=None`, `engine_version=None`, and `adapter_version=None` are valid when the corresponding source is absent by design. Those are the only nullable audit metadata fields in D19.

## 5. Rejected Alternatives

### Option A: Use random `result_id` and row ids

Rejected. Random identifiers would make replay, manual explain, detached row serialization, and audit comparisons depend on incidental object identity instead of canonical content.

### Option B: Reuse `CandidateSet.candidate_id` as `EvaluateRow.row_id`

Rejected. `CandidateSet.candidate_id` is run- and candidate-protocol-specific, includes internal target and candidate key details, and remains internal after D17/D18. Parent C68 requires row identity based on public bindings.

### Option C: Use `CandidateSet.support_digest` as `EvidenceRef.fact_digest`

Rejected. `support_digest` identifies support artifacts, not the public claim. D17 requires `EvidenceRef.fact_digest == EvaluateRow.claim.digest`.

### Option D: Use `Rule.content_digest` alone for closed-head digest

Rejected. Shipped `Rule.content_digest` excludes `Rule.id`, while D21 closed-head ids encode row-specific closure. D19 therefore wraps closed-head id and content digest in a `closed_head_v1` canonical payload.

### Option E: Let missing `view_snapshot_digest` fall back to schema digest

Rejected. A schema-only digest cannot detect fact drift. D20 explanations need a real evaluate-time view anchor to compare replay context with original evaluation context.

### Option F: Include `evaluated_at` in `result_digest`

Rejected. `evaluated_at` is useful metadata, but including it would make digest equality fail for identical reruns with the same rows and context.

### Option G: Require non-null engine and adapter versions for every engine

Rejected. Shipped native evaluation and some adapter paths do not expose stable version strings. D19 permits nullable versions and lets D26 define adapter-specific version sources when necessary.

### Option H: Compute digests from rendered strings or Python reprs

Rejected. Display strings are not canonical, and Python reprs can include object identity, type formatting, or ordering differences. All D19 digests require canonical bytes.

## 6. Supporting Evidence

| Evidence | Source | D19 conclusion |
|---|---|---|
| Shipped digest helpers expose `sha256_hex` and `sha256_token` only. | `src/factgraph/core/protocol/digests.py:7-12` | New public digest fields use `sha256_token`; prefixed ids use `sha256_hex` inside an id namespace. |
| `Rule.content_digest` is bare hex over `ports` and `where`, excluding id/version. | `src/factgraph/application/protocol/rule.py:107-113` | D19 embeds existing rule digest as source data, but wraps closed-head identity with id. |
| `CandidateSet` already has run-, key-, tuple-, support-, and candidate-level identifiers. | `src/factgraph/core/derivation/candidates.py:13-115` | T5 must not expose CandidateSet ids as public row/evidence ids. |
| SDK evaluation can derive shared run ids for multi-plan legacy paths. | `src/factgraph/sdk/store.py:2289-2390` | T5 wrapper can own one public `run_id` per evaluate call instead of first-candidate semantics. |
| Application derivation runtime currently returns flattened `list[CandidateSet]`. | `src/factgraph/application/derivation_runtime.py:64-148` | T5 conversion must build result-level ids and digests above current runtime output. |
| `SemanticsProfile` is normalized in core with explicit fields. | `src/factgraph/core/semantics/profile.py:25-95` | `semantics_digest` source is the normalized core profile after SDK wrapper lowering. |
| Database substrate has a view digest helper, while SDK in-memory result envelope lacks `view_snapshot_digest`. | `src/factgraph/core/store/database.py:193-199`, `:407-410`; Stage 1 F11 | T5 must add a private result view snapshot source before public `EvaluateResult`. |

## 7. Consequences

### 7.1 Downstream D-docs

- D20 must use `result_id`, `row_id`, `EvidenceRef.ref_id`, `fact_digest`, `closed_head_digest`, and context digests as replay anchors for `Explanation` and `EvidenceGraph`.
- D21 must construct closed heads in a way that feeds D19 `closed_head_digest`.
- D23 cannot preserve public CandidateSet ids as compatibility row ids.
- D25 must compare `semantics_digest`, not wrapper object identity, when deciding evaluate/explain semantics consistency behavior.
- D26 owns future adapter version sources and semantics adapter policies, but must not change D19 canonical source separation without superseding D19.

### 7.2 Implementation constraints

T5 implementation needs private helpers for:

- canonical bytes for public values used in `bindings`, `Claim.arguments`, and semantics profiles;
- expression / compiled-plan canonicalization;
- rule-set digest aggregation;
- view snapshot digest extraction;
- closed-head digest construction input handoff from D21;
- result assembly that avoids `result_id` / `EvidenceRef.ref_id` / `result_digest` cycles.

These helpers are implementation-private unless a later D-doc explicitly exports them.

### 7.3 Stage 3 synthesis

Stage 3 must sequence implementation so that D17 DTOs and D19 digest helpers land before the D18 public return-shape hard-cut. A slice that cannot compute `view_snapshot_digest` must not expose `EvaluateResult` publicly.

## 8. Acceptance Criteria

- [ ] Every D17 public id or digest field has exactly one authoritative source in D19.
- [ ] New `*_digest` fields use canonical bytes plus `sha256_token`, except existing embedded `Rule.content_digest` remains bare hex source data.
- [ ] `CandidateSet.candidate_id`, `candidate_key`, `support_digest`, and tuple digests remain internal conversion inputs, not public row identity.
- [ ] `EvidenceRef.fact_digest == EvaluateRow.claim.digest` remains mandatory.
- [ ] `closed_head_digest` includes closed-head id and content digest, with D21 owning construction.
- [ ] `view_snapshot_digest` has no placeholder fallback.
- [ ] `evaluated_at` is excluded from deterministic digests.
- [ ] D20, D21, D25, and D26 can consume the D19 sources without inventing duplicate digest formulas.

## 9. Decision Record

| Date | State | Reviewer / Commit | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Codex draft | Initial D19 source-of-truth decision for T5 result, row, claim, evidence, and audit digests. |
| 2026-05-25 | proposed-amend | Codex follow-up | Added non-authoritative evidence-tree v1 sibling input and locked on-demand citation policy without reopening D16-D18 or adopting internal evidence graph schema. |
