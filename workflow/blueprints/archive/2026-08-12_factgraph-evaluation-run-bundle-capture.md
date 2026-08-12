# Task Blueprint: FactGraph EvaluationRun bundle capture

- Status: archived
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: task-scoped implementation contract for F4B1 only.
- Inputs:
  - [`2026-08-12_q6b-evaluation-run-bundle-capture-decision.md`](../../design/decisions/active/2026-08-12_q6b-evaluation-run-bundle-capture-decision.md)
  - Q6A / F4A implementation and independent CLEAR review
  - 2026-08-12 three-way read-only F4B audit
- Outputs / Downstream:
  - Opt-in `EvaluationRunBundleV0`
  - Strict canonical bundle codec and detached playback
  - F4B2 isolated replay verification input
- Related:
  - [`2026-08-12_factgraph-evaluation-run-bundle-capture.audit.md`](./2026-08-12_factgraph-evaluation-run-bundle-capture.audit.md)
- Audit Log:
  - [`2026-08-12_factgraph-evaluation-run-bundle-capture.audit.md`](./2026-08-12_factgraph-evaluation-run-bundle-capture.audit.md)
- Related Modules:
  - `src/factgraph/core/store/_evaluate.py`
  - `src/factgraph/application/derivation_runtime.py`
  - `src/factgraph/application/protocol/evaluation_run_bundle.py`
  - `src/factgraph/application/evaluation_run_bundle_runtime.py`
  - `src/factgraph/application/protocol/evaluate_result.py`
  - `src/factgraph/sdk/store.py`
- Branch: `codex/v0.3.0-f4b-evaluation-run-replay-2026-08-12`
- Base: `b7eea261`

## 1. Goal

Capture the complete plan-scoped input and output of an opted-in native
`EvaluationQuery` as a strict, portable, content-addressed bundle that remains
inspectable without the originating Store. Do not execute replay yet.

## 2. Invariants

- Default Query evaluation remains unchanged and `run_bundle` is absent.
- Captured evaluation and bundle use the same single projected relation; no
  post-hoc Store read may fill missing material.
- Predicate coverage is complete for the exact materialized plan and records
  empty relations explicitly; evaluator and capture consume the same reduced
  relation rather than independently filtering/projecting it.
- Bundle values preserve canonical types, duplicate semantic rows and support
  occurrence multiplicity. Relation rows preserve observed evaluator order.
- Bundle decode touches no Store, DB, registry, filesystem path, network or
  import-by-name object.
- Integrity is not authentication. Sensitive cleartext and caller-managed
  custody are explicit protocol facts.
- Existing `EvaluateResult` remains the sole live execution result; the bundle
  is its optional detached audit artifact.
- F4B1 adds no evaluator, replay comparison, detached Explain, Policy overlay,
  What-if or repository.
- Gross added production Python is hard-capped at 1,750 lines relative to
  `b7eea261`. The review-ready implementation is 1,692 lines; the remaining
  58 lines are reserved only for review fixes, not new behavior.

## 3. Implementation Plan

1. Collapse native witness and evaluator projection onto one immutable
   effective relation behind a private atomic capture seam. Public core and
   application evaluation signatures expose no callback or raw-relation bypass.
2. Add strict bundle DTOs, canonical typed-value/plan/schema/support codecs,
   cross-component seals and bounded decoding.
3. Build the bundle synchronously inside the existing compiled Query execution
   window when `capture="run_bundle_v0"` is requested.
4. Attach and cross-check the bundle against the F4A anchor and exact
   `EvaluateResult`; expose only detached decode/inspection.
5. Test corruption/splicing, seven scalar domains plus entity-ref and bool,
   empty predicates, negation/zero rows, duplicate rows, competing chosen
   claims, revocation, stale-view rejection, size limits and legacy behavior.
6. Run application/SDK regression cohorts, Ruff, targeted mypy, diff/cap check
   and an independent adversarial review.

## 4. Acceptance

- [x] Capture is opt-in and cannot be added after execution.
- [x] Evaluator and capture share one effective projected relation.
- [x] Plan dependency inventory is complete; empty and missing differ.
- [x] Schema, actual Query values, exact native plan, effective facts, rows,
      F4A anchor and support inventory round-trip through a strict codec.
- [x] Actual row values/certainty recompute and match claim, binding and
      certainty digests; every positive row has exactly one canonical
      ProofReceipt whose binding/branch structure reconstructs from the
      captured plan and whose witnesses resolve uniquely in captured facts.
      Non-fact logical re-evaluation remains F4B2.
- [x] Unknown/missing fields, duplicate keys, unsupported types, corruption and
      cross-bundle splice fail closed before producing a partial bundle.
- [x] Decoded rows/support remain inspectable after the source Store changes or
      is destroyed, with no live fallback.
- [x] Duplicate semantic rows and zero-row summaries retain F4A semantics.
- [x] Bundle reports `authenticity=unverified`, sensitive cleartext custody and
      `replay_availability=not_implemented`.
- [x] Codec enforces the adopted 1 MiB / 128 predicates / 20,000 facts / 1,000
      result rows / 64 values / depth 64 ceilings, and object repr is redacted.
- [x] Unsupported engines/config/premise/registry/Operator/Scenario inputs are rejected.
- [x] Existing Query/Policy/evaluate/Explain behavior remains green within cap.

## 5. Review Basis

Three independent read-only audits covered snapshot sufficiency, existing
support/Explain reuse and pseudo-replay attacks. All required the same ordering:
capture+strict codec first, isolated replay second, detached Explain third.
This lightweight review basis replaces a separate preflight document but not
implementation tests or final independent review.

## 6. Outcome / Deviations

- Implementation lineage `62655986`, `d6f70252` and terminal feature commit
  `6d32beb1` add opt-in `capture="run_bundle_v0"`, an atomic private native
  relation-capture seam, strict `EvaluationRunBundleV0` DTOs/codecs and detached
  decode/inspection. Default and legacy evaluation remain unchanged.
- Evaluator witnesses and capture consume the same deeply frozen,
  dependency-complete relation object. Empty dependencies are explicit and the
  public core/application surfaces expose no observer or raw-relation bypass.
- Schema, normalized Query values, exact native plan, typed facts/results,
  certainty, F4A anchor and canonical ProofReceipts are bounded and
  cross-sealed. ProofReceipt checking is structural playback only; logical
  re-execution remains F4B2.
- The application/SDK cohort passed **480 tests + 108 subtests**; the focused
  post-commit cohort passed **36 tests + 12 subtests**. Ruff, targeted mypy for
  both new production modules and `git diff --check` passed.
- Three internal fixed-state reviews and the user-side independent review
  returned CLEAR with zero P0/P1/P2. The external reviewer repeated the full
  application/SDK cohort and added approximately 40 passing adversarial checks,
  including exhaustive cross-bundle field-splice attacks.
- Production Python growth is **1,692 gross additions / 1,750 allowed** relative
  to `b7eea261`; the remaining margin is unused. Raising the original estimate
  admitted strict codec, type/reflection and callback-bypass guards, not new
  product behavior.
- The bundle truthfully remains unauthenticated, contains captured cleartext,
  is caller-managed and states replay unavailable. No replay evaluator,
  detached Explain, What-if, Scenario, repository, Policy overlay or Meander
  integration was introduced; those remain separate downstream decisions.
- Application, protocol and SDK current-truth docs were synchronized in
  `6d32beb1`. This blueprint and its paired audit are archived together;
  archival does not start F4B2 or F4B3.
