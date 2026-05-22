# Preflight: <topic>

- Status: complete
- Created: YYYY-MM-DD
- Last Updated: YYYY-MM-DD
- Authority: working triage document; surfaces blueprint-vs-shipped drift before scoped anchor per CADENCE Step 4.3. Does not lock implementation; findings feed back into Step 4.4 amendment.
- Inputs:
  - <implementing blueprint at scoped-pre-amendment HEAD>
  - <stage 1 audit, synthesis, Q decisions if applicable>
  - <re-read of shipped state at preflight-row-drafting time per Rule 1>
- Outputs / Downstream:
  - <Step 4.4 amendment commit on blueprint branch>
- Related:
  - <stage 1 audit, synthesis>
- Blueprint: <pointer to consuming blueprint>
- Branch: `v<version>-<topic>-preflight-<date>` (independent from blueprint branch)

> Preflight is REQUIRED per Q3 §4.4 trigger conditions when the slice is: subtractive removal / cross-module protocol change / namespace migration / historical-design compatibility / pre-release verification. Optional otherwise (with rationale recorded in blueprint §6 or §10).

## 1. Preflight scope

Re-read targets at preflight-row-drafting time per Rule 1. Lists which shipped files were re-read and the trigger condition that justifies preflight for this slice.

## 2. 5-bucket findings

### 2.1 Required amendment before scoped (PF-R*)
True blockers — blueprint section X cannot land as-is.

### 2.2 Recommended amendment before scoped (PF-Rec*)
Substance polish — implementation may surface ambiguity without.

### 2.3 Verified assumptions (PF-V*)
Confirms blueprint assumption against current shipped state (positive finding, no action).

### 2.4 Scoped-detail items (PF-S*)
Push to scoped-blueprint or implementation phase.

### 2.5 Abandonment blockers
Stop the slice — design assumption is wrong, must revise upstream Q or audit.

Healthy distribution: 1-4 Required, 1-2 Recommended, 0-3 Verified, 0-2 Scoped-detail, 0 Abandonment.

## 3. Cross-slice contract preservation

Verify the blueprint preserves all prior-slice contracts (identity formulas, API surfaces, sacred branches, N-3 protective locks).

## 4. Findings summary table

| Bucket | Count | Items |
|---|---|---|
| Required | N | <list> |
| Recommended | N | <list> |
| Verified | N | <list> |
| Scoped-detail | N | <list> |
| Abandonment | 0 | — |

## 5. Recommended Step 4.4 amendment actions

Per-PF action: which blueprint section gets amended and how. Reviewer applies on the blueprint branch (NOT preflight branch) per CADENCE + Preemptive Option A pattern.

## 6. Acceptance for this preflight

- [ ] All blueprint-referenced shipped state re-read per Rule 1
- [ ] Findings classified into 5 buckets
- [ ] At least 2 critical findings spot-checked independently
- [ ] No abandonment blocker surfaced
- [ ] Cross-slice contract preservation verified

Lifecycle (per Q3 §4.6): stays in `workflow/audit/active/` until consuming blueprint archives at Step 4.9.
