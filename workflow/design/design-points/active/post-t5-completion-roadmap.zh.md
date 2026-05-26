# Post-T5 Completion Roadmap — T6-T12 Planning Artifact

- Status: draft planning artifact
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Authority: non-authoritative implementation roadmap / scheduling reference. This document does **not** override active design-point commitments, D-doc decisions, shipped module docs, or per-slice blueprints.
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Inputs:
  - [`rule-expression-and-proof-attempt.zh.md`](rule-expression-and-proof-attempt.zh.md) — parent Rule / RuleExpr / `.eval` / semantics design source.
  - [`evidence-tree-rainbird-style-v1.zh.md`](evidence-tree-rainbird-style-v1.zh.md) — Evidence tree design source, especially §10 / §11 / §14.
  - [`database-view-fg-layered-architecture.zh.md`](database-view-fg-layered-architecture.zh.md) — Database/view design source, especially §12 / §13 / §14 / §17.
  - [`rule-expression-and-proof-track-plan.zh.md`](rule-expression-and-proof-track-plan.zh.md) — predecessor T1-T5 decomposition model.
  - T5.8 archive `efd65c0e` and T11.1 published branch head `f94c4b63`.

> **Authority reminder**:本文是调度与资源规划文档,不是新的 design truth。每个后续 T6-T12 blueprint 仍必须回链 active design-point 的具体 section / commitment / shipped source line。若本文与 active design-point 冲突,以 active design-point + shipped source + per-slice blueprint 为准。

---

## 1. Current State Anchors

### 1.1 T5 result / evidence / explain cycle

T5.1-T5.8 已完成并推送到 origin。T5 的用户面结果:

| Slice | Anchor | Outcome |
|---|---:|---|
| T5.1 DTO Foundation + Digest Harness | `53781419` | `Claim` / `EvidenceRef` / `EvaluateRow` / `EvaluateResult` / digest helpers |
| T5.2 Public Evaluate Return-Shape Flip | `4e590e8a` | `fg.eval.evaluate(...) -> EvaluateResult` hard-cut |
| T5.3 Explanation Envelope + Live Row Resolver | `ba5e5c26` | `Explanation` DTO + `row.explain()` |
| T5.4 Row Close + Manual Explain | `7464c3e3` | `row.close()` + `fg.eval.explain(expr, head=closed_head)` |
| T5.5 Why-Not Quarantine | `ec45f12f` | failed `Explanation` is v1 why-not envelope; legacy why-not quarantined |
| T5.6 SDK Rule Flip | `7aa1c6a3` | `factgraph.sdk.Rule` is application protocol Rule |
| T5.7 Legacy Hard-Cut + Service/Docs | `8173c715` | service / OpenAPI / docs aligned with EvaluateResult |
| T5.8 Semantics Lite + Wrapper Fix | `efd65c0e` | wrapper semantics works with application Rule / RuleExpr; C73/C75-lite |

T5 leaves these major post-T5 deferred items:

- C74 / C76 / C77 / C78 adapter-touching semantics execution remains post-T5 / T10.
- Evidence tree Phase B design and later implementation remain T6/T8.
- v2 why-not / counterfactual surface remains deferred by D22 / evidence §14.

### 1.2 T11.1 Database/view gap fix

T11.1 attach-based view consumer is implemented and published on:

```text
v0.2.0-t11-1-attach-view-scope-2026-05-26 @ f94c4b63
```

Relevant anchors:

| Commit | Topic |
|---:|---|
| `76f46ada` | `FactGraph.attach(db, view=view)` for durable Database views |
| `eff86ad0` | durable view immutability / update-delete boundary docs |
| `f94c4b63` | quickstart WHY batch fix + archive |

T11.1 closes the "durable view can be created but not consumed" gap. Remaining Database/view work is still substantial:

- `DatabaseValue` public attach / snapshot API.
- Cross-doc S1-S6 / I10-A10 formal unblock.
- Release machinery and packaging governance.
- v2 method-level `view=` consumers.
- Persistent named view registry and branch / writable sub-fg / remote / multi-db items.

### 1.3 Dirty baseline and sacred branch

At roadmap creation:

- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains intentionally isolated: 6 modified + 1 untracked.
- This roadmap must not absorb dirty baseline files.

---

## 2. Dependency Graph

```text
T12 housekeeping ─────────────────────────────┐
                                               │
T11.2 cross-doc unblock ──> T11.3 release ─────┼──> v0.2.0 release gate
                                               │
T6 evidence Phase B design ──> T8 evidence implementation ──> T9 evidence docs/release alignment
          ▲                         ▲
          │                         │
          └──────── T10 semantics adapter execution ────────┘

T7 evidence audit/rendering bridge ────────────┘
          ▲
          └──────── T10 may affect engine-specific evidence metadata
```

Interpretation:

- **T11/T12 are release-track independent** of the larger evidence implementation chain. They can move before T6/T8.
- **T6 → T8 → T9 is the evidence chain**: complete design skeleton first, then implementation, then docs / release claims.
- **T10 is cross-cutting**: adapter-level semantics execution affects T6/T7/T8 evidence completeness but can run in parallel if its scope is kept engine-local.
- **T7 is a bridge track**: it can advance audit/rendering substrate without waiting for every T8 evidence feature, but engine metadata choices must not conflict with T10.

---

## 3. T6-T12 Track Map

### 3.1 Summary Table

| Track | Title | Prediction | Est. LOC / commits | Owner candidate | Release role |
|---|---|---:|---:|---|---|
| T6 | Evidence-tree Phase B design skeleton completion | L | 800-1500 docs LOC / 6-10 commits | shared(Codex draft, Claude review) | post-release unless v0.2.0 claims full evidence tree |
| T7 | Audit channel + rendering bridge hardening | M/L | 400-1000 LOC / 4-8 commits | either | optional release enhancer |
| T8 | Evidence tree implementation tranche | L | 1500-3500 LOC / 8-14 commits | shared | post-release default |
| T9 | Evidence docs / product boundary release alignment | M | 400-900 docs LOC / 4-7 commits | Claude or Codex | depends on T8 if evidence claims change |
| T10 | Semantics adapter execution completion(C74/C76/C77/C78) | L | 1200-3000 LOC / 7-12 commits | Codex primary | post-release default unless semantics advertised |
| T11.2 | Cross-doc S1-S6 / I10-A10 formal unblock | L | 800-1800 docs+tests LOC / 6-10 commits | shared | release blocker candidate |
| T11.3 | v0.2.0 release machinery | L | 600-1600 LOC / 5-9 commits | Codex primary | release blocker |
| T12 | Lifecycle / design housekeeping | S/M | 200-700 docs LOC / 2-5 commits | either | release hygiene |

Class predictions are planning hints only. A per-track blueprint may downgrade or escalate after Step 4.6 inventory.

### 3.2 T6 — Evidence-tree Phase B Design Skeleton

**Goal**: turn `evidence-tree-rainbird-style-v1.zh.md` §10 / §11 / §14 from skeleton/deferred notes into implementable design source.

Primary source anchors:

- evidence-tree §10 Audit Channel(v1)
- evidence-tree §11 Rendering
- evidence-tree §12 Product Boundary Declaration
- evidence-tree §14 Deferred Items
- parent §7 evidence migration statement

Expected outputs:

- Audit channel shape: sessionless v1 audit metadata, durable graph metadata, immutability / signature stance.
- Rendering stance: reference renderer vs product UI boundary, layout mode matrix, JSON roundtrip.
- Deferred registry expansion: D1-D12 and D14-D19 with triggers, owners, and "not v1" boundaries.
- Evidence implementation split proposal for T8.

Out of scope:

- Production code changes.
- Adapter execution semantics.
- Public why-not API.

### 3.3 T7 — Audit Channel + Rendering Bridge

**Goal**: implement or harden the non-invasive substrate that evidence rendering and audit channel need, without claiming full evidence tree implementation.

Possible slices:

- EvidenceGraph serialization roundtrip tests and docs.
- Renderer reference contract hardening.
- Metadata validator gates around existing `audit.evidence_graph`.
- Audit-channel naming / storage boundary if T6 design makes it concrete.

Dependencies:

- Can start after enough of T6 is scoped.
- Must not contradict T10 engine-specific metadata choices.

### 3.4 T8 — Evidence Tree Implementation Tranche

**Goal**: implement the first substantial evidence tree tranche after T6 design locks shape.

Candidate scope:

- S1 IR replay core/default path for native/Souffle-style rules.
- Strict EvidenceGraph validator gate.
- NODE_CONCLUSION / NODE_PREMISE / NODE_SEED schema population.
- Quantitative carrier propagation using C110 raw_kind/bound only.
- Winning-path-only OR handling and aggregate count-only envelope where substrate exists.

Dependencies:

- T6 must complete enough design to avoid evidence schema churn.
- T10 may affect ProbLog/PyReason enrichment and metadata; T8 can start with native/Souffle S1 only if scoped narrowly.

### 3.5 T9 — Evidence Docs / Product Boundary Release Alignment

**Goal**: align public docs and release claims with whatever T6-T8 actually ship.

Scope:

- Quickstart evidence docs.
- SDK docs for `row.explain()`, `fg.eval.explain(...)`, `EvidenceGraph`.
- Release notes / expectation boundary if v0.2.0 claims evidence improvements.

T9 should not invent behavior. It documents only shipped evidence capabilities and explicit deferred items.

### 3.6 T10 — Semantics Adapter Execution Completion

**Goal**: finish adapter-touching semantics deferred from T5.8.

Primary parent anchors:

- C74 PyReason per-rule atom bounds / timestep delay.
- C76 ProbLog uncertainty projection actual adapter consumption.
- C77 temporal projection runtime behavior.
- C78 PyReason iteration_count execution.

Scope warning:

- T10 touches adapters and may be L-class by default.
- It may affect evidence metadata for T6/T7/T8, but does not block T11 release-track work.
- If a sub-slice only handles one engine and one wrapper field, it may be M-class.

### 3.7 T11 — Database/View Release Track

T11.1 is complete. Remaining candidates:

| Slice | Purpose | Notes |
|---|---|---|
| T11.2 | Cross-doc S1-S6 / I10-A10 formal unblock | release blocker candidate; aligns Database/view metadata with evaluate/evidence docs |
| T11.3 | v0.2.0 release machinery | release branch, changelog, CI, package tagging / publish prep |
| T11.4 | DatabaseValue attach / snapshot API | only if release requires public snapshot consumer |
| T11.5 | broader Database docs migration | if docs remain inconsistent after T11.2 / release prep |

Database-view anchors:

- §12 method-level `view=` remains v2 unless user demand emerges.
- §13 stale/scope validation is already partially shipped by T11.1.
- §14 I10/A10 metadata seam remains release-cross-doc work.
- §17 A11/A18 and named view registry remain v2.

### 3.8 T12 — Lifecycle / Design Housekeeping

**Goal**: cleanly close the T1-T5 planning era and normalize lifecycle state.

Candidate slices:

- Archive or supersede `rule-expression-and-proof-track-plan.zh.md` once T1-T5 are recorded as complete.
- D16-D26 D-doc lifecycle review: proposed → adopted / archive / superseded.
- Active design-point index update.
- Memory/progress sync if required by workflow.

T12 should be small and docs-only unless it uncovers stale design/source conflicts.

---

## 4. Release Blockers vs Post-Release Tracks

### 4.1 Release Blocker Candidates

| Item | Why blocker | Default action |
|---|---|---|
| T11.2 cross-doc S1-S6 / I10-A10 unblock | release docs must not claim inconsistent Database/evidence metadata | run before release |
| T11.3 release machinery | publish requires branch/tag/changelog/CI/package governance | run before release |
| T12 minimal lifecycle housekeeping | reduces stale planning docs before public release | run narrow subset before release |
| Dirty baseline anomaly triage | unknown dirty files may hide intended docs/examples changes | inspect before release branch |

### 4.2 Post-Release Default

| Item | Reason |
|---|---|
| T6 Evidence-tree Phase B full design | large and valuable, but not required if release claims only existing evidence envelope |
| T8 Evidence implementation tranche | large behavior tranche; avoid delaying v0.2.0 unless explicitly in release scope |
| T10 adapter semantics execution | adapter-touching L-class; can ship as later semantics cycle |
| v2 method-level `view=` | user simplification explicitly deferred |
| schema migration / canonicalization | requires separate Database design and migration semantics |

### 4.3 Release Claim Rule

No release note may claim a capability unless one of these is true:

1. the capability is shipped and tested in code;
2. the capability is explicitly documented as design-only / deferred;
3. the release note states a narrower shipped subset.

This rule is especially important for evidence tree, Database views, semantics wrappers, and why-not.

---

## 5. Suggested Ordering and Split Policy

Recommended sequence:

```text
N1 roadmap(this doc)
  -> T12 minimal housekeeping
  -> T11.2 cross-doc unblock
  -> T11.3 release machinery
  -> release gate decision
  -> T6 evidence Phase B
  -> T10 semantics adapter execution (parallel or before T8)
  -> T8 evidence implementation
  -> T9 evidence docs/release alignment
```

Rationale:

- T12/T11.2/T11.3 are release-path clarifiers and have lower implementation uncertainty than T6/T8/T10.
- T6/T8 are large evidence work; they should not block release unless v0.2.0 scope explicitly includes full evidence tree.
- T10 is adapter-touching and should be sliced by engine / commitment to avoid mixing C74-C78 into one oversized commit.

Split policy:

- L-class tracks should use local sub-slices but no push-ready intermediate state unless the branch is coherent.
- Public API hard-cuts and release machinery require a single coherent push gate.
- Design-only tracks may push after archive if no code behavior changed and dirty baseline is isolated.

---

## 6. Deferred Items Registry

### 6.1 Parent Rule / Eval Deferred Items

| Source | Deferred item | Reactivation trigger |
|---|---|---|
| parent §5.12 | `fg.eval.why_not` first-class API | real user need not covered by failed Explanation envelope + top-down algorithm proposal |
| parent §5.12 | `fg.eval.run` deletion | replacement read/match/query entrypoint locked and docs migrated |
| parent C74 | PyReason atom bounds / timestep delay | PyReason adapter work starts or temporal semantics release claim appears |
| parent C76 | ProbLog uncertainty projection adapter consumption | user needs raw_kind/bound projection beyond carrier-only wrappers |
| parent C77 | temporal projection runtime behavior | time-binned facts or fact-boundary runtime use case appears |
| parent C78 | PyReason iteration_count execution | user needs multi-round PyReason inference exposed |

### 6.2 Evidence Deferred Items

| Source | Deferred cluster | Reactivation trigger |
|---|---|---|
| evidence §14 D1-D5 | failure-side / why-not algorithms | user asks "why not this binding" and envelope diagnostic is insufficient |
| evidence §14 D6-D7 | salience / impact attribution | attribution analysis request + math policy selected |
| evidence §14 D8-D10 | session / LLM / ACL channels | service deployment or interactive session demand |
| evidence §14 D11-D12 | PyReason Form 2 / lazy evidence | temporal evidence or large graph UX demand |
| evidence §14 D14-D19 | compound / aggregate schema extensions | complex expressions or contributor expansion become product requirements |

### 6.3 Database/View Deferred Items

| Source | Deferred item | Reactivation trigger |
|---|---|---|
| database §12 | method-level `view=` consumer | user needs per-call view without separate attached runtime |
| database §17 / A11 | branch / writable sub-fg / remote / multi-db | long-lived alternative heads or remote deployment requirements |
| database §17 / A18 | persistent named view registry | users need stable names across sessions |
| database §17 | schema migration tx | schema evolution need with existing data |
| database §17 | materialized derived views | derived fact lifecycle policy is selected |
| T11.1 follow-up | schema class order canonicalization | repeated user confusion from order-sensitive schema digest |

---

## 7. Governance, Push, and Lifecycle

### 7.1 Push Governance

- Never push `master` automatically.
- Each branch push needs explicit single-use human authorization.
- Prior push authorization does not roll forward.
- Dirty baseline files must remain excluded unless explicitly reclassified.
- Milestone tags should be created only at slice archive / cycle complete anchors, not at draft/scoped commits.

### 7.2 Roadmap Lifecycle

This roadmap can remain active while T6-T12 are in motion.

Archive criteria:

1. T6-T12 are either archived, explicitly superseded, or intentionally deferred;
2. v0.2.0 release path is resolved;
3. v2 deferred items have a new roadmap or are moved into per-design §deferred registries;
4. active design-point index no longer needs this as current scheduling reference.

### 7.3 Open Questions / Decision Gates

| Question | Default | Decision gate |
|---|---|---|
| Is T6 required before v0.2.0? | No | if release claims full evidence tree |
| Is T10 required before v0.2.0? | No | if release claims ProbLog/PyReason semantic execution beyond carrier-only wrappers |
| Does T11.2 need code changes? | Unknown | Step 4.6 inventory of S1-S6 / I10-A10 shipped metadata |
| Should dirty baseline be triaged before release branch? | Yes | before T11.3 release machinery |
| Should `rule-expression-and-proof-track-plan.zh.md` archive now? | likely after minimal T12 | T12 Step 4.2 review |

