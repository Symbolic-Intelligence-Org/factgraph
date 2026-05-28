# Synthesis: T5 Result + Evidence + Explain Post-Q Bucketing

- Status: complete
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: working triage document; informs but does not lock implementation. Final scope decisions live in implementing blueprints per CADENCE Stage 3.
- Inputs:
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d20-explanation-envelope.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d21-row-close-closed-head-gate.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d22-why-not-disposition.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d24-final-sdk-rule-flip.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d26-semantics-commitments-scope-adapter-policy.md`
- Outputs / Downstream:
  - T5.1-T5.7 Core implementation blueprint ladder.
  - Optional T5.8 Semantics Lite blueprint.
  - Per-slice preservation invariants, class triggers, and negative-action gates.
  - Stage 3 basis for T5 implementation-phase G7 baselines.
- Related:
  - `workflow/audit/active/2026-05-25_post-q-t4-head-closed-head-synthesis.md`
  - `workflow/memory/current.md`
  - `workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md`
  - `workflow/design/design-points/archive/evidence-tree-rainbird-style-v1.zh.md`
- Source audit: `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Closed Q decisions:
  - D16 T5 Tranche Boundary
  - D17 Result / Row DTO Foundation
  - D18 Return-Shape Transition Strategy
  - D19 Digest Source-of-Truth
  - D20 Explanation Envelope and EvidenceGraph Integration
  - D21 `row.close()` and Closed-Head Gate
  - D22 Why-Not Disposition
  - D23 Legacy SDK Hard-Cut Plan
  - D24 Final SDK Rule Flip
  - D25 Evaluate / Explain Semantics Consistency
  - D26 Semantics Commitments Scope and Adapter Implementation Policy
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`

> Synthesis is required because T5 Stage 1 and Stage 2 closed fourteen audit questions and eighteen parent commitments spanning public result DTOs, explanation, why-not, hard-cut, final SDK naming, digests, closed-head replay, and semantics scope. Implementation now needs a smaller blueprint ladder with explicit cross-slice invariants.

## 1. Purpose

T5 Stage 1 audit and Stage 2 D16-D26 are reviewed clean. This synthesis translates that decision layer into an implementation ladder.

It does not implement T5 and does not supersede D16-D26. It defines the expected Core sequence, optional Semantics Lite lane, and non-goals for implementation blueprints.

T5 remains L-class as a cycle. Individual implementation slices should be scoped M where possible, with L escalation when service-route hard-cut, adapter edits, or cross-namespace deletion makes the blast radius broad.

## 2. D16-D26 Decision Summary

| D-doc | Scope | Final lock |
|---|---|---|
| D16 | Tranche boundary | Split T5 Core from T5 Semantics; Stage 2 must decide C73-C78, but Stage 3 may schedule or defer implementation. Service-route blast-radius inventory is mandatory. |
| D17 | Result / row DTO foundation | Application protocol owns DTOs with SDK re-exports. `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, `DetachedRowError`, and later `Explanation` are the public DTO set. `CandidateSet` becomes internal. |
| D18 | Return-shape transition | `fg.eval.evaluate(...)` hard-cuts to `EvaluateResult`; no `evaluate_v2`, `result_shape=`, `return_candidates=`, or long-lived CandidateSet compatibility lane. |
| D19 | Digest source-of-truth | New T5 digests use `sha256:` tokens. `semantics_digest` comes from normalized `SemanticsProfile`. `view_snapshot_digest` is mandatory. `evaluated_at` is metadata, not digest input. |
| D20 | Explanation envelope | `Explanation` is the public envelope. `row.explain()` is primary; manual `fg.eval.explain(expr, head=closed_head, ...)` is advanced replay. `EvidenceGraph` is public inside Explanation, with audit-facing metadata boundary. |
| D21 | `row.close()` / closed-head gate | Live `EvaluateRow.close()` returns a closed application `Rule`; detached rows raise `DetachedRowError`. Manual explain validates closed heads before D20 pipeline. |
| D22 | Why-not disposition | T5 does not add public `.eval.why_not(...)`. Failed `Explanation` is the v1 why-not envelope; shipped why-not DTOs are D23 legacy hard-cut targets. |
| D23 | Legacy SDK hard-cut | Legacy evaluate/evidence shells, public CandidateSet output, accept round-trip, why-not, and service CandidateSet routes are hard-cut targets. Mixed states are local-only. |
| D24 | Final SDK `Rule` flip | SDK top-level `Rule` becomes application protocol `Rule`. `ApplicationRule` is transition alias only. Top-level `LegacyRule` is a D23 hard-cut target. |
| D25 | Evaluate/explain semantics consistency | Compare normalized `semantics_digest`; row-anchored mismatch raises before Explanation. `raw_kind` / `bound` are copied carrier fields, not consistency proof. |
| D26 | Semantics scope + adapter policy | T5 Core closes without full C73-C78. Optional Semantics Lite may handle non-adapter wrapper/profile work. Adapter-touching C74/C76/C77/C78 work is post-T5 by default. |

## 3. Stage 2 Q-Row Coverage

| Q | Owner | Outcome |
|---|---|---|
| Q1 T5 tranche boundary | D16, D26 | T5 Core owns result/evidence/explain/hard-cut/naming. T5 Semantics C73-C78 are decided in Stage 2, but implementation can be optional or deferred. |
| Q2 DTO export location | D17 | Application protocol owns public DTO definitions; SDK re-exports them. |
| Q3 hard-cut vs additive | D18 | Hard-cut `fg.eval.evaluate(...)->EvaluateResult`; no parallel v2 or shape flag. |
| Q4 CandidateSet mapping | D17 | `CandidateSet` becomes internal. Public row model is `EvaluateRow` with bindings, claim, raw_kind, bound, evidence_ref, and live resolver. |
| Q5 digest sources | D19 | Unique source-of-truth for result, row, claim, evidence ref, context digests, and result digest. |
| Q6 row explain evidence resolution | D20 | Live row uses resolver and D19 anchors to build `Explanation` with `EvidenceGraph`. Detached row is exception. |
| Q7 row.close + closed-head helper | D21 | Live-only `row.close() -> Rule`; D15 strict forms reused; manual explain has must-be-closed gate. |
| Q8 manual explain integration | D20, D21 | `fg.eval.explain(expr, head=closed_head, ...) -> Explanation` consumes D21 closed-head validation and D20 envelope. |
| Q9 why-not disposition | D22 | Fold v1 why-not into failed `Explanation`; no new public `.eval.why_not`. |
| Q10 legacy hard-cut plan | D23 | Enumerated old shells, accept round-trip, public CandidateSet, service routes, and docs migration as hard-cut targets. |
| Q11 final SDK Rule flip | D24 | SDK `Rule` becomes application protocol Rule; `LegacyRule` is not final public alias; `Inference` name remains pending D23 hard-cut mechanics. |
| Q12 semantics commitments | D26 | C73/C75 and non-adapter wrapper/profile work are Semantics Lite eligible; adapter-touching work deferred by default. |
| Q13 service blast radius | D23 | Mandatory service/docs/OpenAPI/examples/tests inventory before hard-cut implementation. |
| Q14 evaluate/explain semantics consistency | D25 | Strict digest comparison; row-anchored mismatch raises; standalone manual explain has no original digest to compare. |

## 4. Commitment Disposition

| Commitment | Disposition | Owner |
|---|---|---|
| C61 `.eval` absorbs explain / check / diagnose | Explanation owns the new public envelope; Check/Diagnose become internal substrates; direct shells are D23 hard-cut targets. | D20, D23 |
| C62 `evaluate(...)->EvaluateResult` + param hard-cut | Hard-cut return shape; remove public `engine_options=` / `registry=`. | D18, D23 |
| C63 `fg.eval.run` freeze / deletion | Old run remains hard-cut inventory; deletion timing tied to D23 and future read/match replacement. | D23 |
| C64 `EvaluateRow` | Six data fields plus `_result_resolver`; no row status; CandidateSet internal. | D17 |
| C65 `EvaluateResult` | Session envelope with rows, head, engine metadata, digests, timestamp, and container protocol. | D17, D19 |
| C66 `row.explain()`, manual explain, `row.close()` | Row explain and manual explain in D20; live `row.close()` in D21. | D20, D21 |
| C67 `Explanation` | Public DTO with strict status/evidence matrix; failed explanation is why-not v1 envelope. | D20, D22 |
| C68 digest metadata | Source-of-truth formulas and mandatory snapshot digest. | D19 |
| C69 evaluate/explain semantics consistency | Strict `semantics_digest` policy; mismatch raises for row-anchored replay. | D25 |
| C70 why-not pending | No new public why-not in T5; future door remains with explicit triggers. | D22 |
| C71 what-if shells | Included in D23 hard-cut inventory; final disposition belongs implementation planning. | D23 |
| C72 closed-head inspect | Already shipped in T4.3; D21 consumes without reopening inspect semantics. | D21 |
| C73 per-rule semantics params | Semantics Lite eligible if wrapper/profile-only and no adapter edits. | D26 |
| C74 PyReason rule params + atom bounds | Split: wrapper validation eligible; adapter execution deferred. | D26 |
| C75 wrapper symmetry + raw_kind/bound | Semantics Lite eligible for public wrapper/profile/carrier model. | D26 |
| C76 ProbLog uncertainty projection | Split: SDK shell/lowering eligible; adapter consumption deferred. Conservative reject defaults. | D26 |
| C77 temporal projection modes | Deferred out of T5 Core and Semantics Lite. | D26 |
| C78 PyReason iteration count | Deferred out of T5; requires adapter execution slice. | D26 |

## 5. Recommended Implementation Slice Ladder

### T5.1: DTO Foundation + Digest Harness

Predicted class: M.

Purpose:

- Add D17 public DTOs and D19 digest helpers before changing public evaluate return shape.

Must include:

- application-protocol definitions for `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, and `DetachedRowError`;
- SDK re-exports, without final docs rewrite;
- internal CandidateSet-to-row conversion helper;
- D19 digest helpers for `run_id`, `result_id`, `row_id`, claim digest, evidence-ref id, closed-head digest, context digests, and result digest;
- mandatory `view_snapshot_digest` substrate;
- tests for DTO validation, digest determinism, row id collision handling, `EvidenceRef.fact_digest == row.claim.digest`, and detached row plumbing without public evaluate flip.

Must not include:

- public `evaluate(...)->EvaluateResult` flip;
- `row.explain()` or `row.close()`;
- SDK `Rule` naming flip;
- legacy hard-cut;
- adapter edits.

Acceptance anchors:

- D17 sections 4.1-4.8; D19 sections 4.1-4.8.

### T5.2: Public Evaluate Return-Shape Flip

Predicted class: L unless service blast radius proves narrow; otherwise split into M internal conversion + M public flip.

Purpose:

- Change all public evaluate entry paths to return `EvaluateResult`.

Must include:

- D18 hard-cut for `fg.eval.evaluate(...) -> EvaluateResult`;
- all public evaluate input paths flip together: application Rule / RuleExpr, legacy Inference, structured derivation dict, and aliases that exist at implementation time;
- public rejection of `engine_options=` and `registry=`;
- no public CandidateSet compatibility surface;
- native / Souffle / ProbLog / PyReason paths produce rows through the same result envelope;
- D19 digest population for every result;
- pre-implementation blast-radius inventory for public callers, docs, examples, and service routes.

Must not include:

- `accept` / `accept_many` removal unless Stage 3 folds it into this L-class slice;
- `row.explain()` / Explanation;
- D24 SDK Rule flip;
- C73-C78 implementation.

Acceptance anchors:

- D18 sections 4.1-4.8; D17 CandidateSet internal boundary; D19 digest requirements.

### T5.3: Explanation Envelope + Live Row Resolver

Predicted class: M.

Purpose:

- Implement row-centric explanation without hard-cutting every legacy shell in the same slice.

Must include:

- public `Explanation` DTO with D20 field set;
- live `EvaluateRow.explain()`;
- resolver access to the original `EvaluateResult`;
- D20 status/evidence matrix;
- `EvidenceGraph` reuse and validation gate;
- D19 replay anchors copied into graph metadata / checked scope;
- D25 semantics checked_scope subset and row-sourced semantics reuse;
- Check/Diagnose as private substrates where useful.

Must not include:

- `row.close()`;
- manual `fg.eval.explain(expr, head=closed_head, ...)` unless Stage 3 combines T5.3 and T5.4;
- public `.eval.why_not`;
- renderer product contract or HTML helpers;
- adapter semantics implementation.

Acceptance anchors:

- D20 sections 4.1-4.9; D25 sections 4.1-4.7.

### T5.4: `row.close()` + Manual Explain Closed-Head Gate

Predicted class: M.

Purpose:

- Add advanced replay tools on top of the row/result envelope and T4.3 closed-head substrate.

Must include:

- live-only `EvaluateRow.close() -> Rule`;
- detached row `DetachedRowError`;
- D15 strict value and entity-ref closure atom construction;
- projection placeholder stripping and real closed-head construction;
- manual `fg.eval.explain(expr, head=closed_head, ...)`;
- must-be-closed gate before D20 pipeline;
- D19 closed-head digest alignment;
- D25 row-anchored versus standalone manual semantics behavior.

Must not include:

- new public closed-head DTO;
- general field literal closure;
- transitive equality closure;
- public `.eval.why_not`;
- adapter semantics changes.

Acceptance anchors:

- D21 sections 4.1-4.9; D20 manual explain contract; D25 manual replay policy; T4.3 D15 strict closure.

### T5.5: Why-Not Fold + Legacy Evidence Shell Quarantine

Predicted class: M.

Purpose:

- Align shipped why-not/check/diagnose surfaces with the new Explanation model before the broad hard-cut.

Must include:

- failed `Explanation` as the T5 v1 why-not envelope;
- no public `.eval.why_not(...)`;
- shipped why-not DTOs classified internal or legacy;
- docs/tests demonstrating failed explanation path;
- no lossy conversion from `WhyNotUniverseResult` into `Explanation.failure_class`;
- no batch candidate-universe why-not API.

Must not include:

- full D23 hard-cut deletion unless Stage 3 folds it into T5.7;
- new WhyNot DTO;
- atom locator public surface;
- evidence-tree failed-node schema implementation.

Acceptance anchors:

- D22 sections 4.1-4.7; D20 failed status matrix; D23 legacy target list.

### T5.6: Final SDK `Rule` Flip

Predicted class: M; L if service/docs imports reveal broad migration.

Purpose:

- Complete T1.3 public naming cleanup before final docs rewrite.

Must include:

- SDK top-level `Rule` exports application protocol `Rule`;
- `ApplicationRule` is transition alias only;
- top-level `LegacyRule` becomes D23 hard-cut target;
- runtime checks compare application protocol `Rule` type identity, not alias strings;
- error messages and docs start using final `Rule` naming;
- tests for import identity and legacy class non-ownership of top-level name.

Must not include:

- deleting all legacy shells unless Stage 3 combines with hard-cut;
- changing application protocol Rule behavior;
- changing D17 DTOs;
- semantics adapter work.

Acceptance anchors:

- D24 sections 4.1-4.8; D23 docs migration timing.

### T5.7: Legacy Hard-Cut + Service / Docs Migration

Predicted class: L by default; may split into several M slices with local-only intermediate states.

Purpose:

- Remove old public API surfaces and align SDK, service routes, OpenAPI, docs, and examples with T5 result/evidence model.

Must include:

- D23 hard-cut target inventory;
- public removal or rejection of `accept`, `accept_many`, `run`, direct `check`, direct `diagnose`, direct `why_not`, and `what_if.*` surfaces according to Stage 3 split;
- service route inventory and target state for CandidateSet/accept round-trip routes;
- OpenAPI and docs update after D24 naming;
- no final milestone with SDK/docs/service return-shape disagreement;
- preservation tests for internal runtime behavior that still needs private DTOs.

Must not include:

- C73-C78 adapter semantics implementation;
- parent section 6 task split;
- public CandidateSet compatibility route;
- public why-not replacement.

Acceptance anchors:

- D23 sections 4.1-4.8; D18 hard-cut policy; D24 naming; D22 why-not disposition.

### T5.8 Optional: Semantics Lite

Predicted class: M if included; defer if adapter edits are required.

Purpose:

- Implement non-adapter wrapper/profile semantics cleanup without blocking T5 Core closure.

May include:

- C73 per-rule params wrapper/profile shape;
- C74 PyReason params schema and atom-id validation, without adapter execution;
- C75 wrapper symmetry and carrier-model docs;
- C76 SDK shell/lowering for uncertainty projection with conservative reject defaults, without ProbLog adapter consumption;
- `SemanticsProfile` lowering updates that change D19 `semantics_digest` deterministically.

Must not include:

- ProbLog adapter raw_kind/bound consumption;
- PyReason adapter atom-bound execution;
- temporal runtime behavior;
- iteration-count execution behavior;
- D25 mismatch policy change.

Acceptance anchors:

- D26 sections 4.2-4.10; D25 invariants; D19 `semantics_digest` source.

## 6. Cross-Slice Invariants

| Invariant | Source | Applies to |
|---|---|---|
| Public success evaluate returns `EvaluateResult`, not `list[CandidateSet]`. | D18 | T5.2 onward |
| `CandidateSet` is internal after the flip. | D17, D18 | T5.1-T5.7 |
| `EvaluateRow` has no status field; failures live in `Explanation`. | D17, D20 | All result/explain slices |
| Row lineage is expressed through `EvidenceRef` and `EvidenceGraph`, not direct row fields. | D17, D20 | T5.1-T5.4 |
| `EvidenceRef.fact_digest == EvaluateRow.claim.digest`. | D17, D19 | T5.1 onward |
| `view_snapshot_digest` is mandatory; no placeholder / wall-clock / schema-only fallback. | D19 | T5.1 onward |
| `semantics_digest` compares normalized profile content, not wrapper identity. | D19, D25 | T5.1 onward |
| Row-anchored semantics mismatch raises before `Explanation`. | D25 | T5.3-T5.4 |
| `raw_kind` / `bound` are copied carriers, not semantics proof. | D17, D25, D26 | T5.1 onward |
| `row.close()` is live-only and returns application `Rule`. | D21 | T5.4 onward |
| SDK `Rule` means application protocol Rule after D24 implementation. | D24 | T5.6 onward |
| No public `.eval.why_not(...)` in T5 Core. | D22 | T5.3 onward |
| Adapter-touching C74/C76/C77/C78 work is post-T5 by default. | D26 | All Core slices |

## 7. Class Triggers And Escalation

| Slice | Predicted class | Escalate when |
|---|---|---|
| T5.1 DTO + digest | M | View snapshot digest requires broad store/runtime redesign or database migration. |
| T5.2 evaluate flip | L default | May split if service routes/docs/examples are too broad; cannot push mixed public shape. |
| T5.3 Explanation | M | EvidenceGraph validation requires internal evidence schema redesign. |
| T5.4 row.close/manual explain | M | Closed-head construction requires new closure forms beyond D15 strict v1. |
| T5.5 why-not fold | M | Batch candidate-universe why-not is reintroduced. |
| T5.6 SDK Rule flip | M | Service/agent imports make naming migration broad. |
| T5.7 legacy hard-cut | L default | Can split into M slices only if intermediate states stay local-only and documented. |
| T5.8 Semantics Lite | M optional | Any adapter production edit, temporal runtime behavior, or iteration execution moves it out of T5. |

Global L triggers:

- new public result/evidence DTO beyond D17/D20;
- public CandidateSet compatibility path;
- adapter production edit in a Core slice;
- service route return-shape migration across multiple endpoint families;
- final SDK naming and legacy hard-cut merged with docs/OpenAPI in one large patch;
- reopening T4.3 closed-head closure forms.

## 8. Service-Route Blast Radius

D23 makes service-route inventory mandatory before hard-cut implementation.

Pre-implementation grep should cover:

- `src/service/`;
- `src/agent/`;
- `docs/api/openapi.yaml`;
- service docs under `src/service/docs/`;
- SDK docs under `src/factgraph/sdk/docs/`;
- official docs under `docs/official/`;
- examples and notebooks;
- tests.

Classification buckets:

- hard-cut update: must migrate to `EvaluateResult`, `Explanation`, or final `Rule` naming;
- internal preservation: can keep private DTOs / runtime helpers but not public docs;
- future-track deferred: what-if or adapter semantics surfaces not part of T5 Core;
- unrelated: lexical matches such as prose or historical archive.

A T5 hard-cut milestone is incomplete if service routes still expose CandidateSet / accept round-trip as the public v1 shape while SDK docs advertise `EvaluateResult`.

## 9. Risks And Mitigation

| Risk | Mitigation |
|---|---|
| Broad hard-cut breaks unrelated service routes. | D23 inventory before implementation; split T5.7 if needed; keep mixed states local-only. |
| DTO foundation becomes coupled to adapter semantics. | Keep C73-C78 out of Core; D26 Semantics Lite must not edit adapters. |
| `EvaluateResult` digest helpers duplicate computation paths. | D19 source-of-truth helpers should be centralized before T5.2. |
| `Explanation` becomes a renderer product surface. | D20 keeps rendering in audit utilities; no `Explanation.render()` in Core. |
| `row.close()` expands closure semantics. | D21 consumes D15 strict forms only; no general field/transitive closure. |
| `LegacyRule` survives as hidden public compatibility lane. | D24 classifies top-level `LegacyRule` as D23 hard-cut target. |
| `why_not` reappears as parallel public API. | D22 folds v1 needs into failed `Explanation`; future API needs new D-doc. |
| Semantics mismatch returns misleading evidence. | D25 strict raise before Explanation for row-anchored mismatch. |
| Evidence-tree v1 bloats T5 implementation scope. | T5 cites only public envelope / carrier constraints; internal evidence-tree schema is future cycle. |

## 10. Stage 3 Acceptance

- [x] Stage 1 audit Q1-Q14 mapped to D16-D26 or Stage 3.
- [x] Parent C61-C78 mapped to D16-D26 dispositions.
- [x] Implementation ladder separates T5 Core from optional Semantics Lite.
- [x] D17/D19/D20/D21/D25 cross-slice invariants listed.
- [x] D23 service-route blast-radius gate carried into implementation guidance.
- [x] D26 adapter-touching deferral policy carried into implementation guidance.
- [x] Class triggers identify M/L escalation points.
- [x] No code implementation, no API mutation, no push, no sacred branch movement.

## 11. Audit Trail Of Stage 1 And Stage 2 Closure

| Commit | Artifact | Event |
|---|---|---|
| `7cfe5701` | Stage 1 audit | Draft T5 result / evidence / explain shipped-state audit |
| `d2512a25` | Stage 1 audit | Add Q14 and precision amendments; reviewed clean |
| `f4755ff4` | D16 | Draft T5 tranche boundary |
| `62b165f4` | D16 | Amend D26 naming and Rule naming guidance; reviewed clean |
| `aa50bcc3` | D17 | Draft result / row DTO foundation |
| `902eb86c` | D17 | Clarify bindings, lineage, closed-head digest; reviewed clean |
| `2c0bea70` | D18 | Draft return-shape transition; reviewed clean |
| `11e946a9` | D19 | Draft digest source-of-truth |
| `490cef54` | D19 | Add evidence-tree on-demand citation policy; reviewed clean |
| `9f13c61e` | D20 | Draft Explanation envelope; reviewed clean |
| `9aae5000` | D21 | Draft row.close + closed-head gate |
| `ae25f5c4` | D21 | Normalize acceptance checkboxes; reviewed clean |
| `d57b1640` | D22 | Draft why-not disposition; reviewed clean |
| `0d1658b1` | D23 | Draft legacy SDK hard-cut plan; reviewed clean |
| `0db8937b` | D24 | Draft final SDK Rule flip |
| `759482c0` | D24 | Normalize ADR header; reviewed clean |
| `a76b715a` | D25 | Draft evaluate/explain semantics consistency; reviewed clean |
| `3b85add5` | D26 | Draft semantics scope + adapter policy; reviewed clean |

Lifecycle: this synthesis stays in `workflow/audit/active/` until the final consuming T5 implementation blueprint archives, or until a later synthesis supersedes it.
