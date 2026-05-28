# Post-T5 Completion Roadmap — T6-T12 Planning Artifact

- Status: working planning artifact
- Created: 2026-05-26
- Last Updated: 2026-05-28
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
| T5.5 Why-Not Quarantine | `ec45f12f` | failed `Explanation` is v1 why-not envelope; legacy `WhyNotResult` / why-not shells quarantined |
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

2026-05-28 status note:

- Sacred `master` still remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Current dirty baseline observed during T10-3-A archive is 4 modified tracked
  files, 1 deleted tracked file, and 6 untracked files/directories.
- This roadmap still must not absorb dirty baseline files.

---

## 2. Dependency Graph

```text
T12 housekeeping ─────────────────────────────┐
                                               │
T11.2 cross-doc unblock ──> T11.3 release ─────┼──> v0.2.0 release gate
                                               │
T6 evidence Phase B design ──> T8 evidence implementation ──> T9 evidence docs/release alignment
          ▲                         ▲                            ▲
          │                         │                            │
          └──────── T10 semantics adapter execution ─────────────┘
                                    │
                                    ▼
T7 evidence audit/rendering bridge ──────────────────────────────┘
```

Interpretation:

- **T11/T12 are release-track independent** of the larger evidence implementation chain. They can move before T6/T8.
- **T6 → T8 → T9 is the evidence chain**: complete design skeleton first, then implementation, then docs / release claims.
- **T10 is cross-cutting**: adapter-level semantics execution affects T6/T7/T8 evidence completeness and may alter T9 evidence documentation claims, but can run in parallel if its scope is kept engine-local.
- **T7 is a bridge track**: it can advance audit/rendering substrate without waiting for every T8 evidence feature, but it still feeds T9 release/docs alignment and its engine metadata choices must not conflict with T10.

2026-05-28 status note:

- T6 and T7 are complete and archived.
- T8 has been split into T8-A/B/C/D. T8-A, T8-B-1(native Form 1),
  T8-B-2(Souffle Form 1), T8-D A+B docs, T8-D round 2 Souffle user docs, and
  T8-D round 3 ProbLog user docs are pushed. T8-C engine enrichment inventory
  is complete as a design-only planning artifact. T8-C-1 ProbLog evidence
  enrichment inventory and runtime implementation are pushed.
- Remaining evidence candidates are T8-C-2 PyReason runtime implementation
  after its semantics locks, plus later T8-D/T9 docs after any future T8-C
  behavior.

---

## 3. T6-T12 Track Map

### 3.1 Summary Table

Owner candidate values are coordination hints, not authority rules:

- `shared` means both Codex and Claude are expected to contribute materially, normally via cross-flip cadence.
- `either` means either side can own the cycle after a local kickoff decision.
- `Codex primary` means Codex drafts / implements and Claude reviews by default.
- If Codex is unavailable or parallel work makes that impractical, a self-owned cycle is acceptable when the audit records the ownership change.

| Track | Title | Prediction | Est. LOC / commits | Owner candidate | Release role |
|---|---|---:|---:|---|---|
| T6 | Evidence-tree Phase B design skeleton completion | L | 800-1500 docs LOC / 6-10 commits | shared(Codex draft, Claude review) | post-release unless v0.2.0 claims full evidence tree |
| T7 | Audit channel + rendering bridge hardening | M/L | 400-1000 LOC / 4-8 commits | either | optional release enhancer |
| T8 | Evidence tree implementation tranche | L | 1500-3500 LOC / 8-14 commits | shared | post-release default |
| T9 | Evidence docs / product boundary release alignment | M | 400-900 docs LOC / 4-7 commits | Claude or Codex | depends on T8 if evidence claims change |
| T10 | Semantics adapter execution completion(C74/C76/C77/C78) | L | 1200-3000 LOC / 7-12 commits | Codex primary | post-release default unless semantics advertised |
| T11.2 | Cross-doc S1-S6 / I10-A10 formal unblock | L | 800-1800 docs+tests LOC / 6-10 commits | shared | release blocker candidate |
| T11.3 | v0.2.0 release machinery | L | 600-1600 LOC / 5-9 commits | Codex primary | release blocker |
| T11.4 | DatabaseValue attach / snapshot API | M/L | 400-1000 LOC / 4-7 commits | either | tentative; activates only if T11.2/T11.3 reveal public snapshot need |
| T11.5 | Broader Database docs migration | M | 300-800 docs LOC / 3-6 commits | either | tentative; activates only if T11.2/T11.3 leave user-facing Database docs gaps |
| T12 | Lifecycle / design housekeeping | S/M | 200-700 docs LOC / 2-5 commits | either | release hygiene |

Class predictions are planning hints only. A per-track blueprint may downgrade or escalate after Step 4.6 inventory. T11.4/T11.5 are not committed release-track work; they are named here so they do not disappear if T11.2/T11.3 surface the need.

2026-05-28 shipped status overlay:

| Track | Current status |
|---|---|
| T6 | Complete: Phase B design source landed and archived at `8fe7abdc`. |
| T7 | Complete: audit/rendering bridge landed and archived at `e2abc6d2`. |
| T8 | Split inventory complete at `a872fa5b`; T8-A complete at `40a0ce47`; T8-B-1 native Form 1 complete at `9e9a7f49`; T8-D A+B docs complete at `22891808`; T8-B-2 Souffle Form 1 complete at `5fcf7722`; T8-D round 2 Souffle user docs complete at `c6fa481f`; T8-C engine enrichment inventory complete at `f45739de`; T8-C-1 ProbLog evidence enrichment inventory complete at `bd5baeec`; T8-C-1 ProbLog runtime pushed at `5ffd4850`; T8-D round 3 ProbLog user docs pushed at `c23ce097`. T8-C-2 PyReason runtime implementation remains future. |
| T9 | Superseded in part by T8-D docs for shipped native + Souffle + ProbLog evidence behavior; broader release alignment remains conditional on any later T8-C behavior. |
| T10 | Semantics adapter execution inventory complete at `580b2636`; T10-1 C76 ProbLog implementation complete and pushed at `cde072fa`; T10-2 PyReason canonical migration inventory pushed at `f8e08905`; T10-2-A C78 PyReason `iteration_count` pushed at `65cc79a3`; T10-2-B C74 PyReason canonical rule params pushed at `92fd6013`; T10-3 C77 temporal inventory pushed at `da896f0c`; T10-3-A `fact_boundaries` alias / compatibility complete locally and pending push; T10-3-B `time_binned` remains future. |
| T11.2/T11.3/T12 | Complete for the release-path work described here. |

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

**Status(2026-05-27)**: complete and archived at `e2abc6d2`.

**Goal**: implement or harden the non-invasive substrate that evidence rendering and audit channel need, without claiming full evidence tree implementation.

Shipped slices:

- Renderer reference contract hardening: non-`EvidenceGraph` type guard and
  large graph warning at `>250` nodes or `>500` edges.
- Metadata bridge tests: exact §10.3 14-key graph metadata set with `run_id`
  envelope-only.
- Audit docs alignment for the sessionless three-layer contract and safe JSON
  render path.

Dependencies:

- Can start after enough of T6 is scoped.
- Must not contradict T10 engine-specific metadata choices.

### 3.4 T8 — Evidence Tree Implementation Tranche

**Status(2026-05-28)**: partially complete after T8 split inventory, T8-A,
T8-B-1, T8-D A+B docs, T8-B-2, T8-D round 2 Souffle docs, T8-C
engine-enrichment inventory, T8-C-1 ProbLog evidence enrichment inventory,
T8-C-1 ProbLog evidence enrichment runtime, and T8-D round 3 ProbLog user docs.

**Goal**: implement the first substantial evidence tree tranche after T6 design locks shape.

Shipped / split scope:

- T8 split inventory locked T8-A/B/C/D boundaries and the dependency graph.
- T8-A shipped metadata/validation foundation: C135 is runtime-enforced for the
  §10.3 14-key graph metadata bridge.
- T8-B-1 shipped native row Form 1 topology: native passed-row explanations now
  populate `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, and `EDGE_SUPPORTS`
  seed -> premise -> conclusion edges.
- T8-D A+B docs aligned user-facing evidence quickstart and SDK guide with
  T8-A/T8-B-1 shipped behavior.
- T8-B-2 shipped Souffle row-result Form 1 conformance through the same
  row-level Form 1 bridge as native rows.
- T8-D round 2 aligned user-facing evidence quickstart and SDK guide with
  T8-B-2 Souffle shipped behavior.
- T8-C inventory selected adapter-side metadata bridge / provenance row bridge
  as the planning direction and split future runtime into T8-C-1 ProbLog and
  T8-C-2 PyReason. It did **not** ship ProbLog/PyReason runtime enrichment.
- T10 inventory refined the T8-C gates: T8-C-1 requires full C76 ProbLog ship;
  T8-C-2 requires C74 + C77, with C78 required if multi-round PyReason
  enrichment is in scope.
- T10-1 implemented and pushed C76 at `cde072fa`:
  `ProbLogSemantics.uncertainty_projection`,
  SDK lowering, and adapter `raw_kind` / `bound` consumption now ship together
  with explicit reject / point-projection semantics. This does **not** ship
  ProbLog evidence enrichment; it only satisfies the C76 prerequisite.
- T8-C-1 ProbLog evidence enrichment inventory completed locally as a
  design-only plan: future runtime should use trace-payload projection memory,
  private provenance row context, exact T8-A 14-key top-level metadata, and
  namespaced `engine_meta["problog"]`. It did **not** ship runtime row-level
  ProbLog evidence.
- T8-C-1 ProbLog evidence enrichment runtime pushed at `5ffd4850` after the
  inventory plan: ProbLog passed-row explanations now use row-result
  provenance graphs with `EDGE_DERIVES`, exact T8-A 14-key top-level metadata,
  namespaced `engine_meta["problog"]`, and export-time uncertainty projection
  decisions.
- T8-D round 3 pushed at `c23ce097`: quickstart and SDK guide now teach
  ProbLog row provenance graphs as shipped while preserving native/Souffle Form
  1 wording and keeping PyReason row-level evidence deferred.

Remaining candidate scope:

- T8-C-2 PyReason enrichment after C74 + C77 are locked, with C78 required for
  multi-round PyReason enrichment.
- Later T8-D docs passes after additional T8-C behavior ships.
- Aggregate count-only envelope remains deferred until matched-count substrate
  exists.

Dependencies:

- T6 must complete enough design to avoid evidence schema churn.
- T10 may affect ProbLog/PyReason enrichment and metadata; T8 can start with native/Souffle S1 only if scoped narrowly.

### 3.5 T9 — Evidence Docs / Product Boundary Release Alignment

**Status(2026-05-27)**: T8-D A+B and T8-D round 2 have aligned user-facing
docs for the T8-A/T8-B-1/T8-B-2 shipped subset. Broader T9 remains conditional
on future evidence behavior and release claims.

**Goal**: align public docs and release claims with whatever T6-T8 actually ship.

Remaining scope, if reactivated:

- Release notes / expectation boundary if v0.2.0 claims evidence improvements
  beyond the T8-D A+B docs pass.
- Additional quickstart/SDK docs after T8-C ships.

T9 should not invent behavior. It documents only shipped evidence capabilities and explicit deferred items.

### 3.6 T10 — Semantics Adapter Execution Completion

**Status(2026-05-28)**: design-only T10 inventory complete at `580b2636`;
T10-1 C76 ProbLog runtime implementation complete and pushed at `cde072fa`;
T10-2 PyReason canonical migration inventory pushed at `f8e08905`; T10-2-A
C78 PyReason `iteration_count` pushed at `65cc79a3`; T10-2-B C74 PyReason
canonical rule params pushed at `92fd6013`; T10-3 C77 temporal inventory
complete locally and pending push.

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

Inventory result:

- C76 ProbLog gap is broader than adapter consumption: `ProbLogSemantics`
  lacks the SDK `uncertainty_projection` shell, SDK lowering, and adapter
  `raw_kind + bound` consumption. Only the generic core
  `SemanticsProfile.uncertainty_projection` carrier exists.
- C77 is partial under legacy names: `valid_time_boundaries` and
  `fixed_timesteps` ship, while canonical `fact_boundaries` and `time_binned`
  remain future. T10-3 inventory selected `fact_boundaries` alias /
  compatibility as T10-3-A and `time_binned` as T10-3-B.
- C74 canonical `derived_bound` / full-atom-id `atom_bounds` is pushed at
  `92fd6013`. It lowers through existing
  `rule_projection["pyreason"]`, converts application atom ids to PyReason
  body-atom targets, rejects duplicate `derived_bound` / `head_bound`, and
  preserves legacy `head_bound` / `branch_bounds` compatibility.
- C78 `iteration_count` is pushed at `65cc79a3` through SDK shell, canonical
  profile carrier, adapter consumption, and conflict tests; legacy
  `fixed_timesteps` remains an alias/fallback when canonical C78 is absent.

Planned implementation split:

1. **T10-1 ProbLog C76**: full three-layer ship for SDK shell, lowering, and
   adapter consumption. Shipped at `cde072fa`: default reject projection, explicit
   raw-uncertainty consumption in ProbLog export, point-projection policies, and
   fixture migration off legacy `confidence`.
2. **T10-2-A PyReason C78**: canonical `iteration_count` migration pushed at
   `65cc79a3`. It ships wrapper default `iteration_count=1`, optional
   `SemanticsProfile.iteration_count`, adapter consumption, and explicit
   conflict rejection with legacy temporal timesteps modes.
3. **T10-2-B PyReason C74**: canonical `derived_bound` and full-atom-id
   `atom_bounds` conversion pushed at `92fd6013`. It preserves legacy
   `head_bound` / `branch_bounds` compatibility and does not reuse T8-B witness
   keys.
4. **T10-3-A PyReason C77 alias**: canonical `fact_boundaries` rename /
   compatibility alias, preserving legacy `valid_time_boundaries`,
   `fixed_timesteps`, and T10-2-A conflict behavior.
5. **T10-3-B PyReason C77 bins**: `time_binned` temporal runtime behavior with
   strict `bin_size` validation and binned materialization.

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

This original sequence has been partially executed. As of 2026-05-28:
T12, T11.2, T11.3, T6, T7, T8 split inventory, T8-A, T8-B-1, T8-D A+B docs,
T8-B-2, T8-D round 2 Souffle docs, T8-C inventory, T10 inventory, T10-1,
T8-C-1 inventory/runtime, T8-D round 3, T10-2 inventory, T10-2-A, and T10-2-B
are complete and pushed. T10-3 C77 temporal inventory is complete locally and
pending push. T10-3-A/B implementation, T8-C-2 runtime implementation, and any
later T8-D/T9 release-alignment pass remain open.

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

---

## 8. Implementation / Use Note

This roadmap is now the working scheduling reference for post-T5 planning. Future T6-T12 blueprints should use:

- §2 for dependency orientation;
- §3 for initial class / ownership / split expectations;
- §4 for release-blocker vs post-release classification;
- §6 for deferred-item reactivation checks.

Those later blueprints must still perform their own Step 4.6 inventory against active design-points and shipped source. This roadmap stays active until the lifecycle criteria in §7.2 are met.

---

## 9. Step 4.6 Scoped Inventory

This scoped inventory records what this roadmap is allowed to claim before later tracks create authoritative blueprints.

| Area | Scoped lock | Result |
|---|---|---|
| Current anchors | T5.1-T5.8 archive anchors and T11.1 published head are scheduling inputs only. | Anchor table in §1 remains valid as of scoped review; later tracks must cite their own source commits. |
| Active design sources | Parent Rule/Eval, Evidence Tree, and Database/View active design-points remain the authoritative source. | This roadmap links those files but does not rewrite their §deferred registries. |
| Dependency graph | T6→T8→T9 evidence chain, T10 cross-cutting semantics influence, and T11/T12 release-track independence are planning assumptions. | Later blueprints may narrow or reorder after their own Step 4.6 inventory. |
| Release blockers | T11.2, T11.3, minimal T12, and dirty-baseline triage are release-blocker candidates. | Release blocker status is not final until T11.2/T11.3 blueprints inspect shipped source and docs. |
| Deferred items | Parent §5.12/C77 implementation, evidence §14 clusters, and database §12/§17 items remain deferred unless a future blueprint activates them; C74/C76/C78 have been activated by T10-1/T10-2 implementation cycles, and C77 has a T10-3-A/B inventory split. | Reactivation triggers in §6 are planning triggers, not implementation authorization. |
| Owner model | Owner candidates are coordination hints. | Cross-flip remains default for `shared`; self-owned fallback is allowed when recorded in the relevant audit. |
| Dirty baseline | Roadmap work must not absorb dirty baseline files. | Creation-time baseline was 6M+1U; 2026-05-28 observed baseline is 4M+1D+6U. This document remains docs-only. |
| Push governance | Prior push authorization does not roll forward. | Any roadmap push requires explicit single-use authorization. |
