# Task Blueprint Audit: Result-fingerprint fold Slice β — EvaluateResult provenance digest + engine-meta sub-object folding

- Blueprint: [2026-06-03_result-fingerprint-fold-slice-beta.md](./2026-06-03_result-fingerprint-fold-slice-beta.md)
- Parent design: [`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.1 + §3.2 + §6 Slice β
- Sibling slice (predecessor, archived): [`2026-06-03_eval-result-flatten-slice-alpha.md`](../archive/2026-06-03_eval-result-flatten-slice-alpha.md) — establishes deprecated-property + internal-compatibility-inventory + service-serializer N-1 patterns
- Fork base: `64651454` (Slice α Step 4.9 archive HEAD)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-03 | draft | Blueprint created | Initial scope recorded on `v0.2.0-blueprint-result-fingerprint-fold-2026-06-03` (fork from `64651454`). Reuses Slice α cadence pattern: §6.1 cadence path locks (§5.4 single-Q local fold + Stage 0 audit folded per Slice 4/5 precedent + §5.2 sub-object choice locked to Option A). |
| 2026-06-03 | draft | Step 4.2 review + tightening | Codex Rule 1 spot-check found P1 construction-order risk (`ResultFingerprint.result_digest` cannot exist before `result_digest_for(...)` runs), P1 loose `engine_meta` validation risk, P2 SDK `__all__` guard impact, P2 service serializer concrete scope, and P3 direct-public-field count wording. Tightening landed on blueprint branch; Status remains `draft`. |

## Decision Notes

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-06-03 | `ResultFingerprint` chosen as named sub-object (parent design §5.2 Option A) over `Mapping[str, str]` (Option B) | Type safety + IDE hints + style consistency with other application protocol DTOs. Decision lockable here (single-Q local fold) per Slice α precedent. |
| 2026-06-03 | No `_resolver` pattern for `ResultFingerprint` | EvaluateResult is the container; sub-object access is direct `self.fingerprint.X`. Unlike Slice α's Claim/EvidenceRef which delegated to row context via `_row_resolver`, ResultFingerprint is self-contained pure data. |
| 2026-06-03 | `result_digest_for(...)` helper signature preserved (Option α-style per §5.4) | Lower-risk path; byte-equal `evaluate_result_digest_v1` canonical bytes preservation contract requires no algorithm change; field organization is independent of digest bytes. Step 4.2 reviewer may revisit. |
| 2026-06-03 | `engine_meta` as `Mapping[str, Any]` (not a new named DTO) | Extensible for future engine metadata without proliferating named DTOs; aligns with parent design §3.1 wording. |
| 2026-06-03 | §5.4 deprecation strategy — local Q fold (no separate Q-decision doc) | Per Slice α precedent. Slice β's deprecation cycle is local implementation policy; consolidate via Step 4.2 review + Step 4.4 amendment fold. Escalation rule: public-compat or cross-slice impact triggers upgrade to Q-decision doc before scoped anchor. |
| 2026-06-03 | Stage 1 audit doc deferred per Slice 4/5 precedent | Per Slice α precedent. Stage-0 source audit folded into parent design + this blueprint draft. No separate `workflow/audit/active/2026-06-03_result-fingerprint-fold-vs-shipped.md`. Step 4.2 reviewer verifies via Rule 1 fresh reads. |
| 2026-06-03 | Step 4.2 P1 — construction-order lock added | Shipped `result_digest_for(...)` needs `result_id`, `run_id`, row digests, engine versions, and provenance digests. Because `ResultFingerprint` itself includes `result_digest`, Step 4.7 must compute primitive values → `result_id` → row digests → `result_digest` before constructing `ResultFingerprint`; otherwise the slice creates a circular dependency or rewrites the D19 byte contract. |
| 2026-06-03 | Step 4.2 P1 — `engine_meta` validation tightened | A raw Mapping with deprecated properties using `.get(...)` would silently turn missing or invalid `engine_version` / `adapter_version` values into compatibility defaults. Blueprint now requires immutable normalization plus required compatibility keys with `str | None` values; extra metadata keys remain allowed. |
| 2026-06-03 | Step 4.2 P2 — SDK export guard made explicit | Adding `ResultFingerprint` is an intentional public SDK surface expansion. Existing `tests/test_sdk_find_partial_identity.py` asserts `len(factgraph.sdk.__all__) == 64`; implementation must update that guard and add a positive membership assertion instead of treating the count failure as unrelated drift. |
| 2026-06-03 | Step 4.2 P2 — service serializer scope grounded | `src/service/runtime_v1.py:2445-2462` has `_evaluate_result_to_dict(...)` and reads the soon-deprecated flat fields directly. The blueprint now treats this as required N-1 service scope, not a hypothetical preflight discovery. |
| 2026-06-03 | Step 4.2 P3 — public field-count wording clarified | The draft's "13 user-facing" shorthand could confuse direct fields with sub-object/public properties. Wording now says 13 direct public fields become 7 direct public fields plus 2 sub-objects. |

## Cross-flip checkpoints (per `feedback_audit_to_archive_cadence` + Slice α first-validation precedent)

- [x] Step 4.2 reviewer (Codex) flags polish list P1...PN; tightening applied on blueprint branch
- [ ] Step 4.3 preflight on independent branch `v0.2.0-result-fingerprint-fold-preflight-2026-06-03`
- [ ] Step 4.4 preflight amendment on this blueprint branch
- [ ] Step 4.5 self-check (doc-only, lightweight)
- [ ] Step 4.6 scoped anchor (Status: draft → scoped)
- [ ] Step 4.6.5 pre-impl grep on this blueprint branch (Option 2 fold if N-findings appear)
- [ ] Step 4.7 implementation on `v0.2.0-impl-result-fingerprint-fold-2026-06-03`
- [ ] Step 4.8 closure (Status: scoped → implemented + §10 Outcome filled)
- [ ] Step 4.9 archive (`active/` → `archive/` + INVENTORY.md entry)

## Pre-Impl Audit Tasks (for Step 4.3 preflight to verify)

### Task A1 — Re-confirm `result_digest_for(...)` byte-equal preservation contract

- Re-read [`evaluate_result.py:565-612`](../../../src/factgraph/application/protocol/evaluate_result.py)
- Confirm canonical bytes schema `evaluate_result_digest_v1` is invariant under Slice β
- Capture a pre-Slice-β fixture for byte-equal regression test

### Task A2 — Enumerate `EvaluateResult(...)` construction sites

- `rg -n 'EvaluateResult\(' src/factgraph/ tests/ docs/`
- Bucket: production / test fixture / docs example
- Compare against §5.5 expectations

### Task A3 — Service serializer presence check

- `rg -n '_evaluate_result_to_dict\|EvaluateResult.*to_dict\|EvaluateResult.*serialize' src/service/`
- If present, scope as N-1 analog to Slice α; record file:line range

### Task A4 — Internal metadata snapshot inventory

- Re-read [`evaluate_result.py:1163-1166`](../../../src/factgraph/application/protocol/evaluate_result.py), [`:1245-1254`](../../../src/factgraph/application/protocol/evaluate_result.py), [`sdk/store.py:2529-2537`](../../../src/factgraph/sdk/store.py)
- Confirm these are the 3 production metadata-snapshot consumers
- Confirm no others surfaced by `rg -n 'expr_digest|rule_set_digest|view_snapshot_digest' src/factgraph/`

### Task A5 — Verify anchor drift

- Confirm L206-289 EvaluateResult class
- Confirm L565-612 result_digest_for helper
- Confirm L221-239 internal plumbing field block
- Flag any drift as `PF-cite-drift`

## Codex Audit Findings

_(Empty — to be filled by Step 4.3 preflight on `v0.2.0-result-fingerprint-fold-preflight-2026-06-03` branch.)_
