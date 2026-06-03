# Task Blueprint Audit: Eval-row inline Claim/EvidenceRef Slice gamma — wrapper removal + row evidence fields

- Blueprint: [2026-06-03_eval-row-inline-claim-evidence-ref-slice-gamma.md](./2026-06-03_eval-row-inline-claim-evidence-ref-slice-gamma.md)
- Parent design: [`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.3-§3.5 + §4.1 + §4.5 + §6 Slice gamma
- Predecessor slices:
  - [`2026-06-03_eval-result-flatten-slice-alpha.md`](../archive/2026-06-03_eval-result-flatten-slice-alpha.md)
  - [`2026-06-03_result-fingerprint-fold-slice-beta.md`](../archive/2026-06-03_result-fingerprint-fold-slice-beta.md)
- Fork base: `e2f7f655` (Slice beta Step 4.9 archive HEAD)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-03 | draft | Step 4.1 blueprint pair created | Initial scope recorded on `v0.2.0-blueprint-eval-row-inline-claim-evidence-ref-2026-06-03` (fork from `e2f7f655`). Gamma treated as higher-risk breaking surface: SDK exports, protocol DTO shape, `Explanation`, service projection, and docs cascade all require Step 4.2/4.3 tightening before scope freeze. |

## Decision Notes

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-06-03 | Tight cadence selected for Slice gamma | Unlike Slice beta's mostly mechanical sub-object fold, gamma removes or compatibility-wraps public SDK/protocol DTO classes (`Claim`, `EvidenceRef`) and changes `Explanation.claim`. Use full 4.2/4.3/4.4/4.6.5 gates. |
| 2026-06-03 | `repr` conflict surfaced instead of silently resolved | User-stated gamma scope included `repr` flattening, while parent design §3.3/§3.7 says `repr` is view concern and should not live on `EvaluateRow`. Blueprint records R1/R2/R3 options; Step 4.2/4.3 must lock. |
| 2026-06-03 | SDK compatibility strategy left open for review | Immediate removal is cleanest but may break `from factgraph.sdk import Claim, EvidenceRef`; compatibility aliases/properties may be required for one release cycle. Step 4.3 must enumerate real consumers before locking C1/C2/C3. |
| 2026-06-03 | Stage 0 source audit folded into Step 4.1 draft | Follows Slice alpha/beta precedent, but with mandatory independent preflight. Step 4.1 fresh reads include `evaluate_result.py`, SDK/protocol exports, DTO tests, quickstart docs, and service runtime import collision. |
| 2026-06-03 | Ledger `Claim` explicitly out of scope | Service runtime imports ledger `Claim` for claim/candidate payloads; gamma only concerns application-protocol `Claim` in `evaluate_result.py`. Preflight must preserve this layer boundary. |

## Step 4.2 Review Focus

- P0/P1 risk: `Claim.repr` handling conflicts between user prompt and parent design.
- P0/P1 risk: public SDK `Claim` / `EvidenceRef` import compatibility and `__all__` count.
- P0/P1 risk: `Explanation.claim` cascade and service JSON wire compatibility.
- P1 risk: `row.claim` / `row.evidence_ref` deprecated property strategy might preserve wrapper abstraction longer than intended.
- P1 risk: `EvidenceRef.ref_id` removal vs cross-process `(result_id, row_id)` handle must preserve D17/D19 semantics or explicitly document break.
- P2 risk: docs cascade likely broad; quickstart currently has full `Claim` / `EvidenceRef` sections.

## Cross-flip checkpoints

- [ ] Step 4.2 review + tightening on blueprint branch
- [ ] Step 4.3 preflight on independent branch `v0.2.0-eval-row-inline-claim-evidence-ref-preflight-2026-06-03`
- [ ] Step 4.4 preflight amendment on blueprint branch
- [ ] Step 4.5 self-check
- [ ] Step 4.6 scoped anchor
- [ ] Step 4.6.5 pre-impl grep
- [ ] Step 4.7 implementation on `v0.2.0-impl-eval-row-inline-claim-evidence-ref-2026-06-03`
- [ ] Step 4.8 closure
- [ ] Step 4.9 archive

## Preflight Seed Queries

```bash
rg -n 'Claim\(|EvidenceRef\(' src/factgraph src/service tests docs
rg -n '\.claim\b|\.evidence_ref\b|claim\.kind|claim\.repr|claim\.digest|evidence_ref\.closed_head_digest' src/factgraph src/service tests docs
rg -n 'Claim|EvidenceRef|DetachedClaimError|DetachedEvidenceRefError' src/factgraph/application/protocol/__init__.py src/factgraph/sdk/__init__.py tests docs
rg -n 'Explanation\(|claim:' src/factgraph src/service tests docs
```
