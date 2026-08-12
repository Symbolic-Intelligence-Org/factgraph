# Task Blueprint Audit: FactGraph F4 completion

- Blueprint: [`2026-08-12_factgraph-f4-completion.md`](./2026-08-12_factgraph-f4-completion.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-12 | draft | Shared F4 completion blueprint created | Consolidates the already-authorized F4B2/F4B3/F4C tail to avoid three repetitive document lifecycles. |
| 2026-08-12 | scoped | Three-way read-only contract audit completed | Replay, detached-evidence and Policy-projection audits found no structural blocker and supplied explicit safety boundaries. |
| 2026-08-12 | implementing | User directed F4 continuation and fast completion | Implementation proceeds as three independently committed code slices with one combined external review. |
| 2026-08-13 | implementing | F4B2 independent red-team found a resource-gate undercount | The preflight was tightened before F4B2 acceptance: it now charges primary bindings plus captured-row receipt reconstruction against a saturating relation-scan bound. A high-cardinality, projection-collapsing regression must reject before evaluator entry. |
| 2026-08-13 | implementing | F4B2 code stop amended from 650 to 750 production additions | This is a narrow consequence of the required DoS correction, not a new feature surface; final review must separately verify that no runtime/API scope expanded. |
| 2026-08-13 | implementing | F4B2 red-team tightened early-return receipt validation | A second red-team pass showed that receipt reconstruction may be deferred only after one-pass receipt-to-branch, condition, and assertion-witness consistency validation. Re-sealed invalid bundles now raise before compatibility/resource records. |
| 2026-08-13 | implementing | F4B2 red-team found remaining receipt-inventory gaps | The preflight now also requires unique receipt binding/condition keys, exact non-fact details, and complete witness assertion inventories indexed in one pass. This keeps the resource gate bounded while preventing invalid, self-sealed receipts from receiving non-executed records. |
| 2026-08-13 | implementing | F4C red-team found a body-rule/evidence contradiction | Projection now rejects a body `EvidenceRule.status` that disagrees with the deterministic fold of its exact authored atoms; public exports and module documentation are added before combined review. |
| 2026-08-13 | implementing | F4B2/F4C code stops amended to 925/980 additions | Both adjustments are bounded security/integrity and public-contract completion work found by independent review; no new evaluator, Scenario, UI, or Meander surface is introduced. |
| 2026-08-13 | implementing | F4C final review clarified its pure-value boundary | The projector does not create or change live Explain state, but may consume any compatible anchored/lineaged `EvidenceGraph`; documentation now states this without claiming a detached-only input restriction. |
| 2026-08-13 | implementing | F4B2 final review tightened typed receipt preflight | Static receipt/witness matching now preserves captured tup-v1 tags and canonical storage values, so Python-equal but schema-incompatible values such as `True`/`1` or `1.0`/`1` cannot receive a non-executed verification record. The F4B2 stop rises to 1,050 solely for this bounded, selected-branch check; no generic type inference, Scenario, or API surface is added. |

## Decision Notes

- The compressed lifecycle is deliberate: Q6A/Q6B are adopted, F4A/F4B1 were
  independently reviewed CLEAR, and three fresh read-only audits serve as the
  implementation preflight. This does not waive per-slice test or stop boundaries.
- F4B2 statically rejects estimated work above 100,000 before invoking native
  evaluation. The bound includes raw-binding enumeration and per-binding/captured-row
  receipt reconstruction over witness relations; captured byte/fact limits alone do
  not bound intermediate joins or support rebuilding.
- Before a non-executed F4B2 record is emitted, the bundle must still pass full
  DTO/schema/row consistency plus one-pass receipt-to-selected-branch and witness
  checks. Those checks include exact unique receipt inventories and all matching
  captured assertion identities. Only repeated receipt reconstruction is deferred
  behind the work gate.
- Stable runtime pins are semantic-contract versions, not package/build claims.
  Old unpinned bundles remain usable only with an explicitly weaker verdict.
- F4B3 owns assertion-backed inner evidence; F4C owns only the readonly authored
  topology projection. Neither owns Scenario, UI or authorization semantics.
- F4C treats the inner evidence rule status as an integrity assertion, not optional
  display metadata: a disagreement with its atom fold is a total-or-error
  contradiction.
- Final `implemented` and archive transitions wait for the user-side combined
  independent review.
