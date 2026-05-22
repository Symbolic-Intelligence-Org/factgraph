# Audit: <design doc> vs Shipped Runtime

- Status: skeleton
- Created: YYYY-MM-DD
- Last Updated: YYYY-MM-DD
- Authority: working triage document; informs but does not lock implementation. Implementation decisions follow only after audit-row review.
- Inputs:
  - <design doc being audited, with §-cites>
  - <shipped source files read completely, per Rule 1>
- Outputs / Downstream:
  - <Q decisions surfaced from open questions; synthesis if applicable; implementing blueprint downstream>
- Related:
  - <prior audits, cross-doc seams, parallel design-points>
- Source intent: <pointer to design doc being audited>
- Branch: `<branch ref where authored>`

## 1. Scope

Primary surface (read completely per Rule 1):

| Layer | File | Path |
|---|---|---|
| ... | ... | ... |

Out-of-scope items explicitly listed.

## 2. Inputs

Expanded narrative of upstream sources.

## 3. Triage Table

5-state classification per CADENCE Stage 1:

- **(a) shipped covers** — honors design intent
- **(b) small gap** — minor mv / rename / metadata sync
- **(c) shape conflict** — semantic or structural mismatch requires decision
- **(d) genuinely new** — no shipped equivalent
- **(e) deferred-aligned** — design defers + shipped honors

### 3.1 A-series: Architectural commitments
### 3.2 I-series: Invariants and protocols
### 3.3 D-series: Discrepancies between current and proposed
### 3.4 N-series: Non-discrepancies (verified shipped honors design)

## 4. Open Questions

Q1, Q2, ..., each blocking specific drift rows. Will become formal `workflow/design/decisions/` entries.

## 5. Frictions

Frictions identified through audit; carry forward to synthesis or blueprint.

## 6. Cross-doc seams (out of scope)

Items requiring independent sibling-doc work or future slices.

## 7. Recommendations for blueprint

What the implementing blueprint should derive from this audit.

## 8. Audit method notes

Cadence deviations, retrofits, or method observations worth tracking.

## 9. Audit completeness checklist

- [ ] All in-scope rows triaged
- [ ] All open Qs surfaced
- [ ] All frictions enumerated
- [ ] Out-of-scope explicitly listed
- [ ] Recommendations provided

Status transitions: `skeleton` → `complete` when all rows filled.
