# Synthesis: <topic> Post-Q Bucketing

- Status: complete
- Created: YYYY-MM-DD
- Last Updated: YYYY-MM-DD
- Authority: working triage document; informs but does not lock implementation. Final scope decisions live in the implementing blueprint per CADENCE Stage 3.
- Inputs:
  - <source vs-shipped audit>
  - <closed Q decisions>
- Outputs / Downstream:
  - <implementing blueprint §4 lock table + §8 phase plan>
- Related:
  - <prior synthesis, parallel slices>
- Source audit: <pointer to vs-shipped audit being re-bucketed>
- Closed Q decisions: <list of Q decision pointers>
- Branch: `<branch ref where authored>`

> Synthesis is REQUIRED per Q3 §4.5 when ≥3 Q closures span ≥2 buckets; optional for single-Q or single-bucket slices.

## 1. Scope of synthesis

Re-buckets the audit drift inventory + cross-doc seams + recommendations into CADENCE 5-bucket classification, now that Q decisions are all `adopted`.

## 2. 5-bucket classification

### 2.1 blueprint-eligible
Gated only by closed Qs; ready for implementing blueprint §8 phase plan.

### 2.2 cross-doc blocked
Requires sibling-doc redraft or independent slice; Q closure necessary but not sufficient.

### 2.3 no independent action
Projection / release-gate / conditional row; folds into parent blueprint.

### 2.4 already aligned
Shipped state already honors design intent.

### 2.5 deferred / v2+
Design defers + shipped does not implement; no action this slice.

## 3. Recommended blueprint phase order (with dependency analysis)

Recommended sequence of phases the implementing blueprint should derive. Annotate dependencies (e.g., "Phase X before Phase Y because ...").

## 4. Cadence reminders for the implementing blueprint

Drawn from CADENCE + Q decisions. Examples: lock table cites Q1-QN; N-3 protective preservation lock; preflight required per Q3 §4.4; 3-commit impl pattern; pre-impl grep amendment; Q-delta-decision discipline.

## 5. Audit trail of Stage 2 closure

Commit lineage table for traceability. Note: self-referential lineage may have minor commit-count drift; see CADENCE Anti-patterns + Slice 7 lessons.

## 6. Acceptance for this synthesis

- [ ] All audit drift rows + cross-doc seams + recommendations classified into exactly one bucket
- [ ] Recommended phase order consistent with Q decision dependencies
- [ ] Cadence reminders capture all Q-derived constraints
- [ ] Audit trail current as of recent commit

Lifecycle (per Q3 §4.6): stays in `workflow/audit/active/` until consuming blueprint archives at Step 4.9.
