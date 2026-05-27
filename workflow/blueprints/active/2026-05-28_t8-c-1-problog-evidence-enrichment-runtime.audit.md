# Audit: T8-C-1 ProbLog Evidence Enrichment Runtime

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t8-c-1-problog-evidence-enrichment-runtime.md`
- Stage: implemented
- Class: M (runtime implementation)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 5 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | `29f32cb1` | T8-C-1 ProbLog evidence enrichment runtime blueprint pair drafted | Triggered by T10-1 C76 ship at `cde072fa` and T8-C-1 inventory at `bd5baeec`; Q1-Q10 pending for Step 4.6. |
| 2026-05-28 | scoped | `6ac4f2cb` | Source-backed T8-C-1 runtime implementation plan completed | Selected optional decision sink for `_claim_probability`, private `_row_provenance_envelopes`, provenance branch before Form 1 dispatch, namespaced `engine_meta["problog"]`, audit-doc-only docs update, and no stop/amend findings. |
| 2026-05-28 | implemented | pending | Runtime implementation completed and Step 4.7-reviewed | Implementation commits `bc0b0b96`, `70f305be`, `b3ec909b`, `22a06ea5`, `a916a856`, and `73c26f5f`; focused 117 OK, full discover `2013 / 72F / 231E`. |

## 2. Draft Inventory Summary

This runtime cycle starts from locked inventory decisions:

- Use trace-payload attachment for ProbLog uncertainty projection decision
  memory.
- Add private provenance row context parallel to `_row_support_artifacts`, not
  a Form 1 support-kind widening.
- Add a ProbLog row branch in `_build_passed_row_evidence_graph(...)` while
  preserving T8-A metadata validation gates.
- Keep top-level graph metadata exactly 14 keys and move ProbLog trace summary
  / projection details under namespaced `engine_meta["problog"]`.
- Preserve the existing candidate converter's flat adapter-local `engine_meta`.
- Keep C119 multi-path DAG and C136 aggregate envelope deferred.

Step 4.6 source-backed concrete implementation choices without reopening these
decisions:

- `ProvenanceEnvelope.payload` can carry the decision table without envelope
  schema changes.
- `_claim_probability(...)` should keep returning `float` and fill an optional
  decision sink, preserving direct callers.
- `EvaluateResult` should add private `_row_provenance_envelopes` mapping
  parallel to `_row_support_artifacts`.
- `_build_passed_row_evidence_graph(...)` should check ProbLog provenance after
  metadata validation and before Form 1 dispatch.
- Row-result graph metadata remains exact 14-key top-level metadata; ProbLog
  trace/projection details move under `engine_meta["problog"]`.
- Existing candidate/readback converter flat `engine_meta` remains unchanged.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What is the projection decision table schema? | Answered: `payload["uncertainty_projections"]` with `schema_version=1` and `decisions_by_asrt_id`; per decision records `asrt_id`, `source`, `raw_kind`, `bound`, `policy`, and `resolved_probability`. |
| Q2 | How should `_claim_probability(...)` expose structured decisions? | Answered: keep returning `float`; add optional decision sink to avoid direct-caller churn. |
| Q3 | What private row provenance context field should `EvaluateResult` use? | Answered: `_row_provenance_envelopes: Mapping[str, ProvenanceEnvelope] | None`, private/frozen/non-comparable like `_row_support_artifacts`. |
| Q4 | Where exactly should `_build_passed_row_evidence_graph(...)` branch? | Answered: after metadata validation and before Form 1 dispatch, validating ProbLog envelope shape before building. |
| Q5 | What is the complete namespaced `engine_meta` field set? | Answered: root `engine_meta["problog"]` with `trace_summary`, `trace`, and `uncertainty_projection`; non-root nodes get namespaced `trace` plus optional projection decision; edges get `trace_edge`. |
| Q6 | What audit docs change is required? | Answered: update audit docs §1/§3/§6 only; user docs deferred to T8-D round 3. |
| Q7 | What implementation commit split should be used? | Answered: projection producer, private row context, row bridge, tests, audit docs, closure, archive. |
| Q8 | How is anti-silent-ignore enforced at row bridge level? | Answered: reject stays export/evaluation failure; no candidates/rows means no row evidence graph. |
| Q9 | Does this unblock T8-D round 3? | Answered: yes after runtime/audit docs ship, but as a separate follow-up cycle. |
| Q10 | Are there stop/amend findings? | Answered: none. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| Inventory decisions are reopened silently | Runtime implementation drifts from the archived source-backed plan | Completed Step 4.6: inventory Q1-Q9 remain locked; no archive amendment needed. |
| Projection decisions are reconstructed after export | Evidence metadata may lie about how probabilities were produced | Completed Step 4.6: selected optional decision sink filled at `_claim_probability(...)` / export time. |
| Row bridge bypasses T8-A validation | ProbLog row graphs could miss 14-key metadata validation | Completed Step 4.6: branch occurs after `_validate_evidence_metadata_for_row_result(...)`; `_explain_live_row(...)` still revalidates. |
| `_FORM1_ROW_SUPPORT_KINDS` is widened | ProbLog provenance could be misclassified as native/Souffle Form 1 | Completed Step 4.6: use private `_row_provenance_envelopes`; do not widen Form 1 allowlist. |
| Existing ProbLog converter flat engine_meta is migrated in-place | Existing candidate/readback tests and service audit-package path may regress | Completed Step 4.6: row-result wrapper owns namespaced metadata; converter flat shape stays protected. |
| Default `reject` is rendered as empty evidence | T10-1 anti-silent-ignore guarantee is weakened | Completed Step 4.6: reject remains export/evaluation failure and should be tested as no-row/no-evidence. |
| C119 multi-path enters scope | M-class bridge grows into graph algorithm work | Completed Step 4.6: no multi-path source correction; keep C119 deferred. |
| User docs are updated in this cycle | T8-D round 3 boundary is violated | Completed Step 4.6: audit docs only; user docs deferred. |
| Dirty baseline is touched | Workflow violation | Completed Step 4.6: only blueprint/audit files touched so far; preserve `4 M + 1 D + 5 U`. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q10 answered.
- [x] Projection memory producer implemented.
- [x] Private row provenance context implemented.
- [x] ProbLog row bridge implemented.
- [x] Focused test matrix implemented.
- [x] Audit docs updated.
- [x] Full discover delta explained.
- [x] Closure notes filled.

## 6. Closure Notes

T8-C-1 runtime shipped the locked inventory plan without reopening the archived
inventory decisions:

- `bc0b0b96` records ProbLog probability/projection decisions at export time and
  embeds them in `ProvenanceEnvelope.payload["uncertainty_projections"]`.
- `70f305be` adds private `_row_provenance_envelopes` plumbing parallel to
  `_row_support_artifacts` and keeps Form 1 support-kind allowlists unchanged.
- `b3ec909b` bridges ProbLog provenance envelopes into row-result
  `EvidenceGraph`s with `EDGE_DERIVES`, exact 14-key top-level metadata, and
  namespaced `engine_meta["problog"]`.
- `22a06ea5` adds focused tests for row provenance validation, row bridge
  topology/metadata, and projection-decision recording.
- `a916a856` updates the audit module docs only; user docs remain a T8-D round 3
  follow-up.
- `73c26f5f` fixes an in-cycle protocol/adapter import cycle by moving the
  ProbLog provenance import into the private row bridge builder.

Verification:

- Focused suite: 117 OK.
- Full discover: `2013 tests / 72 failures / 231 errors`, from T10-1 baseline
  `2011 tests / 72 failures / 231 errors`; failures and errors did not move.
- `ruff check` on touched source files passed.
- `git diff --check` clean.
- Sacred `master` and the `4 M + 1 D + 5 U` dirty baseline were preserved.

Notes for future cycles:

- Projection recording uses compact mode: default `1.0` probability rows are not
  emitted as `source="default"` decisions.
- Projection decisions are available at graph root under
  `engine_meta["problog"]["uncertainty_projection"]`; per-node projection
  attachment remains a possible UI-driven enrichment.
- `trace_summary.uncertainty_projection_decision_count` is a convenience copy of
  the nested decision count.
- The row builder passes `dict(row.bindings)` as the candidate payload to the
  existing converter; the current focused fixture validates it, but broader
  fixture shapes should source-back this fallback before relying on it.
- Full discover total increased by 2 while the focused test method count
  increased by 4. Because failures and errors were unchanged, Step 4.7 found no
  composition-shift regression.
