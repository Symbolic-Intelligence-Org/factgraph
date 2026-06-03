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
| 2026-06-03 | draft | Step 4.2 review + tightening | Folded reviewer P1-P5: C3 compatibility sub-shape must be locked or rejected by preflight; gamma must not add placeholder `Explanation.repr`; `Explanation.row` direct-reference shape is locked; ledger Claim name-friction cross-reference added; Explanation cross-process semantics recorded. Status remains `draft`. |
| 2026-06-03 | draft | Step 4.4 preflight amendment | Folded Step 4.3 preflight `ef09030c`: PF-R1 no `EvaluateRow.repr`; PF-R2 C1 immediate wrapper removal; PF-R3 expanded `Explanation.row` cascade; PF-R4 service wire split; PF-r1 ledger Claim carve-outs; PF-r2 SDK/protocol export count. Status remains `draft`; no abandonment blockers. |
| 2026-06-03 | draft | Step 4.5 self-check PASS | Verified PF coverage, G/N structure, open-question disposition, stale wording scan, Q-PR1/dirty invariants, and no abandonment blockers. One stale "unless Step 4.3" phrase normalized before scope freeze. |
| 2026-06-03 | scoped | Step 4.6 scope freeze | Status `draft` → `scoped`; scope frozen with PF-R1/PF-R2/PF-R3/PF-R4 Required, PF-r1/PF-r2 Recommended, PF-v1..PF-v8 verified, PF-s1/PF-s2 scoped details, 0 abandonment. |

## Decision Notes

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-06-03 | Tight cadence selected for Slice gamma | Unlike Slice beta's mostly mechanical sub-object fold, gamma removes or compatibility-wraps public SDK/protocol DTO classes (`Claim`, `EvidenceRef`) and changes `Explanation.claim`. Use full 4.2/4.3/4.4/4.6.5 gates. |
| 2026-06-03 | `repr` conflict surfaced instead of silently resolved | User-stated gamma scope included `repr` flattening, while parent design §3.3/§3.7 says `repr` is view concern and should not live on `EvaluateRow`. Blueprint initially recorded R1/R2/R3 options; Step 4.4 PF-R1 locked R1. |
| 2026-06-03 | SDK compatibility strategy left open for review | Immediate removal is cleanest but may break `from factgraph.sdk import Claim, EvidenceRef`; compatibility aliases/properties may be required for one release cycle. Step 4.3 must enumerate real consumers before locking C1/C2/C3. |
| 2026-06-03 | Stage 0 source audit folded into Step 4.1 draft | Follows Slice alpha/beta precedent, but with mandatory independent preflight. Step 4.1 fresh reads include `evaluate_result.py`, SDK/protocol exports, DTO tests, quickstart docs, and service runtime import collision. |
| 2026-06-03 | Ledger `Claim` explicitly out of scope | Service runtime imports ledger `Claim` for claim/candidate payloads; gamma only concerns application-protocol `Claim` in `evaluate_result.py`. Preflight must preserve this layer boundary. |
| 2026-06-03 | Step 4.2 P1 — C3 compatibility sub-shape made explicit | "Lightweight view object" was underspecified. Step 4.3 must either reject C3 or lock C3a SimpleNamespace-style proxy, C3b minimal deprecated compatibility class, or C3c removal/raising behavior after consumer enumeration. |
| 2026-06-03 | Step 4.2 P2 — no placeholder `Explanation.repr` in gamma | A `repr` field without the evidence walker would advertise unsupported behavior. Gamma updates `Explanation.claim` to row data only; Slice epsilon ships the `repr` field and walker together. |
| 2026-06-03 | Step 4.2 P3 — `Explanation.row` direct reference locked | Parent design §4.1 chooses `row: EvaluateRow | None`, not inlined `row_*` fields. Blueprint now locks that shape before preflight to avoid implementation-time drift. |
| 2026-06-03 | Step 4.2 P4 — ledger Claim friction cross-reference added | `rule-namespace-rulespec-redesign.zh.md` §3.5/§4.6 proposed renaming application protocol Claim to `ResultClaim`. Slice gamma resolves the same cross-layer name friction by removing the protocol wrapper instead; ledger `Claim` remains untouched. |
| 2026-06-03 | Step 4.2 P5 — Explanation cross-process semantics recorded | Explanation serializes through inline `row` plus `result_id`; re-location uses `(result_id, row.row_id)` per parent design §4.5. |
| 2026-06-03 | Step 4.4 PF-R1 — no `EvaluateRow.repr` | Preflight confirmed `Claim.repr` is compatibility/rendering data derived from head id + row bindings, not row-owned state. Slice gamma uses helper-derived compatibility values where needed; Slice epsilon owns `Explanation.repr` + walker. |
| 2026-06-03 | Step 4.4 PF-R2 — C1 immediate wrapper removal locked | Active protocol-wrapper consumers are bounded. `Claim`, `EvidenceRef`, `DetachedClaimError`, and `DetachedEvidenceRefError` leave protocol/SDK exports; `row.claim` / `row.evidence_ref` compatibility properties are not kept. |
| 2026-06-03 | Step 4.4 PF-R3 — `Explanation` cascade expanded | `Explanation.row` direct reference replaces `claim`; redundant direct `row_id`, `evidence_ref_id`, `raw_kind`, and `bound` fields are removed from in-process DTO shape. |
| 2026-06-03 | Step 4.4 PF-R4 — service wire split locked | Service JSON keeps nested `claim` / `evidence_ref` compatibility dictionaries, but `_evaluate_row_to_dict(...)` must source them from row-owned fields and helpers, not protocol wrappers. |
| 2026-06-03 | Step 4.4 PF-r1 — ledger Claim carve-outs added | Many grep hits are ledger `Claim` (`asrt_id`, `pred_id`, `e_ref`, `rest_terms`) and are out of scope. Pre-impl grep must bucket protocol wrappers vs ledger false positives. |
| 2026-06-03 | Step 4.4 PF-r2 — SDK export count pinned | Removing `Claim`, `EvidenceRef`, `DetachedClaimError`, and `DetachedEvidenceRefError` drops SDK `__all__` count from 65 to 61 unless implementation adds a deliberate replacement symbol. |

## Step 4.2 Review Focus (Completed; Superseded by Step 4.4 Locks Where Applicable)

- P0/P1 risk: `Claim.repr` handling conflicts between user prompt and parent design.
- P0/P1 risk: public SDK `Claim` / `EvidenceRef` import compatibility and `__all__` count.
- P0/P1 risk: `Explanation.claim` cascade and service JSON wire compatibility.
- P1 risk: `row.claim` / `row.evidence_ref` deprecated property strategy might preserve wrapper abstraction longer than intended. Resolved by Step 4.4 PF-R2 C1 lock.
- P1 risk: `EvidenceRef.ref_id` removal vs cross-process `(result_id, row_id)` handle must preserve D17/D19 semantics or explicitly document break.
- P2 risk: docs cascade likely broad; quickstart currently has full `Claim` / `EvidenceRef` sections.

## Cross-flip checkpoints

- [x] Step 4.2 review + tightening on blueprint branch
- [x] Step 4.3 preflight on independent branch `v0.2.0-eval-row-inline-claim-evidence-ref-preflight-2026-06-03`
- [x] Step 4.4 preflight amendment on blueprint branch
- [x] Step 4.5 self-check
- [x] Step 4.6 scoped anchor
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
