# D25 Decision: T5 Evaluate / Explain Semantics Consistency

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks semantics consistency policy between `evaluate(...)`, `row.explain()`, and manual `fg.eval.explain(...)` replay.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md` Q14, F9, and section 6 C69 triage.
  - D17 `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md` sections 4.3 and 4.7.
  - D19 `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md` sections 4.4, 4.5, and 7.3.
  - D20 `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md` sections 4.1, 4.4, 4.6, and 7.3.
  - D24 `workflow/design/decisions/active/2026-05-25_t5-d24-final-sdk-rule-flip.md` sections 4.1-4.8.
  - Evidence-tree v1 `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` sections 6.1-6.8 and C110-C113.
  - Shipped `src/factgraph/core/semantics/profile.py:24-102`.
  - Shipped SDK semantics lowering `src/factgraph/sdk/store.py:2159-2196`, `src/factgraph/sdk/store.py:2872-2944`.
- Outputs / Downstream:
  - D26 semantics commitments scope and adapter implementation policy.
  - Stage 3 T5 synthesis and implementation ladder.
  - D20 / D21 implementation blueprints that build `Explanation.checked_scope`.
  - D23 / D24 final docs migration for `semantics=` examples.
- Related:
  - `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
  - `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md`
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Depends on: D16-D24 reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

D17 defines `EvaluateRow.raw_kind` and `EvaluateRow.bound` as nullable quantitative carrier fields. It deliberately does not define semantics consistency or projection behavior.

D19 defines `semantics_digest` as the digest of the normalized core `SemanticsProfile`, after SDK wrapper lowering. It explicitly requires D25 to compare `semantics_digest`, not Python wrapper object identity.

D20 defines `Explanation.raw_kind`, `Explanation.bound`, and `Explanation.checked_scope`. It states that raw quantitative carrier values are copied from the evaluated row or manual context, and that D25 owns semantics consistency.

Evidence-tree v1 is a sibling future-design input, still non-authoritative for implementation. D25 cites only its section 6 carrier constraints: `raw_kind` / `bound` are the only canonical quantitative carrier, deterministic cases use `None` / `None`, and adapter-native debug fields are non-contract.

## 2. Scope

D25 decides:

- how `evaluate(..., semantics=A)` and explain replay with `semantics=B` compare semantics;
- whether mismatch warns, raises, or proceeds silently;
- whether comparison uses wrapper identity or normalized `semantics_digest`;
- how `Explanation.checked_scope` records semantics information;
- how `Explanation.raw_kind` / `bound` source-of-truth relates to row data and replay context;
- how standalone manual explain differs from row-anchored replay;
- how D25 stays compatible with D26 semantics implementation choices.

## 3. Non-Scope

D25 does not decide:

- DTO fields; D17 and D20 own them;
- digest formulas; D19 owns them;
- `row.close()` construction; D21 owns it;
- why-not public surface; D22 owns it;
- legacy hard-cut mechanics; D23 owns them;
- final SDK `Rule` naming; D24 owns it;
- whether C73-C78 are implemented in T5 Core or deferred; D26 owns that;
- adapter raw_kind / bound population rules; D26 owns implementation policy;
- probability aggregation, noisy-or, SDD, temporal propagation, or cross-engine bound equivalence;
- evidence-tree internal `engine_meta` schema beyond the local carrier constraints cited above.

## 4. Decision

### 4.1 Semantics comparison uses D19 `semantics_digest`

D25 locks a content-based comparison:

- Normalize public semantics wrappers to core `SemanticsProfile` first.
- Compute or reuse the D19 `semantics_digest`.
- Compare `semantics_digest` values.
- Do not compare Python object identity, wrapper class identity, object `repr`, or raw constructor kwargs.

Two different public wrapper objects that lower to the same normalized `SemanticsProfile` are semantically equal for evaluate/explain consistency.

Two objects with different profile content are semantically different even if they share the same wrapper class or profile name.

`semantics_digest=None` is a real state meaning no semantics profile participated. It is equal only to another `None`.

### 4.2 Row-sourced `row.explain()` reuses original evaluation semantics

`row.explain()` is row-bound. It must use the row's live result resolver and original `EvaluateResult.semantics_digest`.

Rules:

- `row.explain()` does not accept an alternate `semantics=` parameter in T5.
- It must not recompute semantics from current SDK defaults.
- It must not inspect wrapper object identity from the caller.
- It must not silently re-run under a different semantics profile.
- If the live resolver cannot recover the original result semantics context, the row is stale or detached according to D17/D20 boundaries, not a semantics mismatch case.

This keeps row-time evaluate and row-time explain consistent by construction.

### 4.3 Row-anchored manual replay is strict: mismatch raises

Manual explain may be used to replay or compare against a row/result context when the caller supplies row/result anchors such as `result_id`, `row_id`, `evidence_ref_id`, or an `EvidenceRef`-derived replay context.

When an original `semantics_digest` is available from that context:

- if the caller omits `semantics=`, replay uses the original semantics context;
- if the caller supplies `semantics=` that normalizes to the same digest, replay proceeds;
- if the caller supplies `semantics=` that normalizes to a different digest, the API raises an SDK boundary error before returning `Explanation`;
- the mismatch must not be represented as `Explanation(status="failed")`;
- the mismatch must not emit `UserWarning` and proceed;
- the mismatch must not proceed silently.

D25 chooses strict raise over warning or silent behavior because C69 requires semantics differences to be explicit and because replay under a different profile is not evidence for the original row.

The implementation error bucket should use the existing SDK call-boundary error family, not a new public error subclass. Stage 3 may choose the exact existing error (`SDKStoreError` versus `RuleExprError`) based on the call path, but it must be a raised error before `Explanation` construction.

### 4.4 Standalone manual explain has no mismatch to compare

Standalone manual explain means:

```python
fg.eval.explain(expr, head=closed_head, semantics=...)
```

with no original row/result/evidence_ref replay anchor.

In that mode:

- there is no original `semantics_digest` to compare against;
- the supplied `semantics=` is the replay semantics source;
- omitted `semantics=` means `semantics_digest=None`;
- no mismatch warning or error is emitted solely because no original semantics exists;
- `Explanation.checked_scope` records that the semantics source is manual / standalone.

Standalone manual explain can still fail for other D20/D21 reasons, such as missing context, non-closed head, unsupported engine behavior, or graph validation.

### 4.5 `checked_scope` records original and replay semantics explicitly

D20 leaves `checked_scope` as a `Mapping[str, object] | None`. D25 locks the minimum semantics-related keys for successful row-sourced and manual explanations:

```python
checked_scope = {
    "semantics_digest": str | None,
    "semantics_source": "row_result" | "manual_standalone" | "manual_replay",
    "evaluate_semantics_digest": str | None,
    "explain_semantics_digest": str | None,
    "semantics_match": bool | None,
}
```

Interpretation:

- `semantics_digest` is the effective replay digest used by this explanation.
- `semantics_source="row_result"` means `row.explain()` reused the original result context.
- `semantics_source="manual_replay"` means manual explain was anchored to an existing result/row/evidence ref.
- `semantics_source="manual_standalone"` means no original result context existed.
- `evaluate_semantics_digest` is the original digest when available, otherwise `None`.
- `explain_semantics_digest` is the replay digest; it may be `None`.
- `semantics_match=True` when both comparable digests match.
- `semantics_match=False` must not appear in a returned `Explanation`; mismatches raise before construction.
- `semantics_match=None` means standalone manual explain had no original digest to compare.

The mapping may include D19 replay anchors such as `result_id`, `row_id`, `expr_digest`, `view_snapshot_digest`, and `closed_head_digest`, but D25 only locks the semantics-related subset.

### 4.6 `raw_kind` / `bound` are copied carriers, not recomputed consistency proof

D25 consumes evidence-tree v1 section 6 only as a carrier constraint:

- `raw_kind` / `bound` are the only public quantitative carrier fields;
- `raw_kind=None` iff `bound=None`;
- deterministic logical success is `None` / `None`, not `bound=(1.0, 1.0)`;
- adapter-native debug fields such as native probability are non-contract.

For row-sourced explanations:

- `Explanation.raw_kind` and `Explanation.bound` are copied from the evaluated row;
- they are not recomputed during `row.explain()`;
- they are not used as the semantics consistency comparison source;
- they must already reflect the original evaluation semantics and adapter output.

For standalone manual explain:

- `Explanation.raw_kind` and `Explanation.bound` come from the replay result context if the engine/adapter produces them;
- absent quantitative output remains `None` / `None`;
- the semantics profile alone must not fabricate `raw_kind` / `bound`.

This preserves D17's flat row carrier and D20's metadata-copy rule.

### 4.7 No warnings for semantics mismatch

D25 rejects the T4.1-style warning pattern for semantics mismatch.

T4.1 version mismatch warning was safe because rule version metadata was explicitly warning-only and did not enter canonical identity. T5 semantics profile changes can change result rows, evidence, raw quantitative carrier values, and replay conclusions.

Therefore:

- no `UserWarning` + proceed behavior;
- no warning-only `Explanation.warnings` entry for mismatched semantics that still returns evidence;
- no silent replay under a different digest;
- no partial "best effort" graph under mismatched semantics.

Callers who want a different semantics profile must run a fresh `evaluate(..., semantics=B)` or standalone manual explain without claiming it explains row/result A.

### 4.8 D26 may implement semantics features without changing D25 policy

D26 owns whether C73-C78 semantics commitments are in T5 implementation scope and how adapter-touching work is split.

D25's consistency policy is independent of that implementation choice:

- if D26 defers most semantics commitments, D25 still compares `semantics_digest`;
- if D26 implements adapter raw_kind / bound consumption, D25 still copies row/manual carriers;
- if D26 adds adapter version sources, D19/D26 update metadata sources but D25 still compares profile digest content;
- if D26 changes how wrappers lower to `SemanticsProfile`, D25 still compares the normalized digest after lowering.

D25 is therefore a policy contract, not an adapter implementation contract.

## 5. Rejected Alternatives

### Option A: Warn and proceed on semantics mismatch

Rejected. A warning would make replay evidence appear valid for the original row while using different semantics. This violates C69 and undercuts D19 digest reproducibility.

### Option B: Proceed silently on semantics mismatch

Rejected. Silent mismatch makes evaluate/explain inconsistency invisible and makes row evidence non-reproducible.

### Option C: Compare wrapper object identity

Rejected. Public wrappers are teaching objects and can lower to the same core profile. Identity comparison would reject equivalent semantics and accept some non-equivalent mutation patterns.

### Option D: Compare wrapper class only

Rejected. Two `ProbLogSemantics` objects may encode different rule parameters, projections, or fallback behavior.

### Option E: Return `Explanation(status="failed")` for mismatch

Rejected. Semantics mismatch is a caller/replay precondition error, not a business semantic failure such as no matching row or closed-head false.

### Option F: Encode mismatch as `unsupported`

Rejected. `unsupported` is reserved for engine gaps or graph validation constraints. A caller supplied mismatched semantics profile is not an engine unsupported case.

### Option G: Require `semantics=` for every manual explain call

Rejected. Standalone deterministic/manual cases with no semantics profile are valid and should record `semantics_digest=None`.

### Option H: Make `raw_kind` / `bound` the semantics comparison source

Rejected. Quantitative carriers are outputs, not the source-of-truth profile. D19 `semantics_digest` is the comparison source.

## 6. Supporting Evidence

| Source | Evidence | D25 consequence |
|---|---|---|
| Stage 1 audit Q14 / C69 | Evaluate/explain semantics consistency was missing after initial Q-row mapping and was added as Q14. | D25 must explicitly choose warn / raise / silent behavior. |
| D17 section 4.3 | `EvaluateRow.raw_kind` and `bound` are nullable carriers; D25/D26 own semantics consistency. | D25 should not redesign row fields, only define consistency policy. |
| D19 section 4.4 | `semantics_digest` is based on normalized core `SemanticsProfile` fields and D25 must consume it. | Comparison source is digest content. |
| D20 section 4.1 | `Explanation` carries `raw_kind`, `bound`, and `checked_scope`. | D25 must define how those fields are populated for semantics. |
| D20 section 4.4 | Manual explain accepts `semantics=...` as replay context. | D25 distinguishes row-anchored replay from standalone manual explain. |
| Evidence-tree v1 section 6.1-6.8 | `raw_kind` / `bound` are the only canonical quantitative carrier; math aggregation is deferred. | D25 treats quantitative fields as carrier-only, not consistency proof. |
| `src/factgraph/core/semantics/profile.py:24-102` | `SemanticsProfile` is the normalized core profile with explicit fields. | D25 compares normalized profile digest, not wrapper object identity. |

## 7. Consequences

### 7.1 Positive consequences

- Row explanations cannot accidentally replay under different semantics.
- Manual replay semantics are explicit and reproducible.
- D20 `checked_scope` becomes the visible place to record semantics comparison state.
- D19 `semantics_digest` becomes the single consistency source.
- Evidence-tree carrier fields stay independent from profile comparison.

### 7.2 Costs

- Callers cannot use `row.explain(semantics=...)` to compare alternate semantics; they must evaluate again or use standalone manual explain.
- Manual replay code must preserve original semantics digest when row/result anchors are supplied.
- Tests must cover `None` semantics, same digest via different wrappers, and mismatched digest raise behavior.
- Docs must explain that mismatch raises rather than warning.

### 7.3 Follow-up decisions

- D26 decides which semantics commitments and adapter implementations land in T5.
- Stage 3 decides whether D25 implementation is part of D20/D21 explain slices or its own semantics-consistency slice.
- D19/D26 may refine digest construction details, but not the D25 comparison source principle.
- Post-T5 evidence-tree work may formalize more internal graph metadata without changing the D25 public policy.

## 8. Acceptance Criteria

- [ ] D25 chooses strict raise on row-anchored semantics mismatch, not warn or silent proceed.
- [ ] D25 compares `semantics_digest`, not wrapper object identity.
- [ ] `row.explain()` reuses original evaluation semantics and does not accept alternate `semantics=` in T5.
- [ ] Standalone manual explain without original row/result context records manual semantics and has no mismatch to compare.
- [ ] `Explanation.checked_scope` minimum semantics keys are specified.
- [ ] `Explanation.raw_kind` / `bound` are copied carriers, not recomputed profile proof.
- [ ] Evidence-tree v1 section 6 is cited only for carrier constraints and does not become an adapter implementation contract.
- [ ] D25 preserves D26 authority over C73-C78 implementation scope.

## 9. Decision Record

| Date | Stage | Summary | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Adopt strict evaluate/explain semantics consistency based on D19 `semantics_digest`. | Drafted after D24 reviewed clean v2. D25 makes `row.explain()` reuse original result semantics, requires row-anchored manual replay to raise on mismatched semantics, records semantics comparison in `Explanation.checked_scope`, and treats `raw_kind` / `bound` as copied carrier fields rather than semantics comparison sources. |
