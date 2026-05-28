# D16 Decision: T5 Tranche Boundary

- Status: adopted
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: adopted design constraint; locks the T5 Stage 2 / Stage 3 boundary before result/evidence/explain decisions.
- Implementation Anchors: T5.1-T5.8 archived at `53781419`, `4e590e8a`, `ba5e5c26`, `7464c3e3`, `ec45f12f`, `7aa1c6a3`, `8173c715`, `efd65c0e`.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md` Q1, Q10, Q11, Q12, Q13, Q14, F8, F9, F12, and §6 commitment triage.
  - Parent design `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md` §5.8, C61-C78, and §5.12 deferred / pending table.
  - Track plan `workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md:233-264`.
  - T4 Stage 3 synthesis `workflow/audit/active/2026-05-25_post-q-t4-head-closed-head-synthesis.md`.
  - T4.1 archived blueprint `workflow/blueprints/archive/2026-05-25_t4-1-head-identity-declared-port-foundation.md`.
  - T4.2 archived blueprint `workflow/blueprints/archive/2026-05-25_t4-2-external-projection-head-execution.md`.
  - T4.3 archived blueprint `workflow/blueprints/archive/2026-05-25_t4-3-closed-head-inspect-docs.md`.
  - Shipped `src/factgraph/sdk/store.py:420-475`, `:1178-1278`, and `:2211-2384`.
  - Shipped `src/factgraph/sdk/__init__.py:28-56` and `:88-108`.
  - Shipped `src/factgraph/core/derivation/candidates.py:13-70`.
- Outputs / Downstream:
  - D17 result/row DTO foundation.
  - D18 return-shape transition and hard-cut mode.
  - D19 digest source-of-truth.
  - D20 explanation envelope and Check/Diagnose/EvidenceGraph integration.
  - D21 `row.close()` and closed-head gate.
  - D22 why-not disposition.
  - D23 legacy SDK hard-cut plan.
  - D24 T1.3 final SDK `Rule` flip.
  - D25 evaluate/explain semantics consistency.
  - D26 semantics commitments scope and adapter implementation policy, if Stage 2 keeps C73-C78 in this decision cluster.
- Related:
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
  - `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md`
  - `workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md`
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Depends on: T4 cycle complete and pushed; T5 Stage 1 audit reviewed clean v2.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

T5 starts after T4 completed the full Head surface:

- T4.1 validates existing heads and branch-total declared ports.
- T4.2 evaluates external and projection heads through the existing public `fg.eval.evaluate(...)->list[CandidateSet]` path.
- T4.3 adds read-only closed-head inspect fields and a private closed-head validator.

The parent T5 target is larger than a return-shape change. Parent C61-C78 include:

- `.eval` namespace cleanup and explain absorption;
- `EvaluateResult` / `EvaluateRow` / `Claim` / `EvidenceRef`;
- `Explanation` and row-centric `row.explain()`;
- `row.close()`;
- why-not disposition;
- old API hard-cut;
- semantics wrapper commitments, uncertainty projection, temporal projection, and engine iteration commitments.

Stage 1 audit found the shipped state still returns `list[CandidateSet]`, still exposes `accept`, `accept_many`, `run`, `check`, `diagnose`, and `why_not`, and still exports legacy SDK `Rule` as the top-level `Rule` name.

D16 decides what T5 owns and what remains deferred before narrower D-docs can safely lock DTOs, explain behavior, hard-cut sequencing, and implementation slices.

## 2. Scope

This decision locks:

- T5 Core vs T5 Semantics boundary;
- whether C73-C78 are part of this Stage 2 cluster;
- whether service-route blast radius must be audited before hard-cut implementation;
- whether parent §6 task split and §9 RuleExpr x evidence joins are in scope;
- where the T1.3 final SDK `Rule` flip belongs;
- the expected D17-D26 decision-doc ladder.

## 3. Non-Scope

This decision does not lock:

- exact DTO fields for `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, or `Explanation`;
- exact return-shape migration mechanics;
- row digest formulas;
- evidence graph metadata shape;
- why-not keep / migrate / delete final answer;
- exact semantics wrapper fields or adapter consumption details;
- implementation slice count;
- code changes;
- public docs migration details.

Those are downstream D-doc and Stage 3 responsibilities.

## 4. Decision

### 4.1 T5 is split into T5 Core and T5 Semantics lanes

T5 Stage 2 covers both lanes, but implementation ordering must keep them distinct.

**T5 Core** owns:

- C61 `.eval` explain namespace and check/diagnose absorption;
- C62 `fg.eval.evaluate(...)->EvaluateResult` and public evaluate parameter hard-cut;
- C63 `fg.eval.run` freeze / deletion trigger;
- C64 `EvaluateRow`;
- C65 `EvaluateResult`;
- C66 `row.explain()`, manual `fg.eval.explain(...)`, and `row.close()`;
- C67 `Explanation`;
- C68 result / row digest metadata;
- C69 evaluate/explain semantics consistency policy;
- C70 why-not disposition;
- C71 what-if shell disposition;
- C72 consumption of already-shipped T4.3 closed-head inspect;
- T1.3 final SDK `Rule` naming flip;
- docs migration for the new T5 public surface.

**T5 Semantics** owns C73-C78:

- per-rule semantics params;
- PyReason rule params;
- wrapper symmetry and raw_kind/bound model;
- ProbLog uncertainty projection and adapter raw_kind/bound consumption;
- temporal projection modes;
- PyReason iteration count.

D16 does not let T5 Core silently implement C73-C78, and it does not let C73-C78 block T5 Core DTO / explain decisions.

### 4.2 Stage 2 must decide C73-C78, but Stage 3 may schedule or defer their implementation

Stage 2 must include a semantics-boundary decision because C69 and C68 interact with result/explain:

- `EvaluateResult.semantics_digest` needs a source-of-truth policy.
- `Explanation.checked_scope` needs semantics comparison rules.
- Evaluate and explain with different semantics need a warning / raise / silent policy.

However, full C73-C78 implementation is not a prerequisite for T5 Core.

Stage 3 may choose one of three outcomes:

1. include T5 Semantics implementation after T5 Core slices in the same T5 cycle;
2. split T5 Semantics into a follow-up tranche after T5 Core closure;
3. defer adapter-touching C76 / temporal C77 / iteration C78 to a later track while keeping C69/C68 minimal consistency in T5 Core.

Any implementation slice that edits adapter production files because of C76 is automatically at least M-class, potentially L-class depending on cross-adapter blast radius, and requires its own Step 4.6 grep and G7 baseline.

### 4.3 Parent §6 task split and §9 RuleExpr x evidence joins remain deferred

D16 keeps the Stage 1 audit boundary:

- parent §6 `match` / `evaluate` / `prove` decomposition is not part of T5;
- parent §9 RuleExpr x evidence join semantics are not part of T5;
- T5 may avoid blocking future §6 / §9 work by choosing names and DTO boundaries carefully, but it must not implement those surfaces.

This preserves the track plan's explicit not-in-T5 items.

### 4.4 Service-route blast radius is mandatory audit scope before hard-cut implementation

Track plan identifies `src/service/` as an affected surface for old API hard-cut.

D16 does not require service-route edits in early DTO slices. It does require that D23 or the hard-cut blueprint:

- grep service routes and tests for old `check`, `diagnose`, `why_not`, `accept`, `accept_many`, `run`, `engine_options`, and `registry` assumptions;
- classify each hit as update, preserve, deprecate, or out-of-scope;
- prevent silent breakage of external service callers.

No T5 hard-cut implementation may start without that scoped blast-radius inventory.

### 4.5 T1.3 final SDK `Rule` flip belongs inside T5 Core

T1.3 transitional state is now a blocker for a clean T5 public surface:

- top-level SDK `Rule` is still the legacy query class;
- `LegacyRule` is an alias to the same class;
- application `Rule` is exported as `ApplicationRule`;
- `Inference` remains a separate derivation authoring object.

T5 Core must decide the final naming and transition plan before docs migration and legacy hard-cut close.

D16 places the final `Rule` flip after DTO / return-shape decisions and before final public docs migration. D24 owns the exact decision. Stage 3 may schedule the implementation as its own slice or as part of the legacy hard-cut slice, but it cannot leave the flip unplanned.

D17-D23 should describe head and rule values with generic terminology such as "head Rule" or "application head Rule", not by current SDK alias names. This keeps D24 free to choose the final naming flip without forcing retroactive edits on earlier D-doc design language. Concrete SDK public names appear only after D24 is reviewed clean.

### 4.6 Why-not is last among user-facing behavior decisions

Parent explicitly marks `fg.eval.why_not(...)` pending. Shipped why-not exists as an independent SDK/application surface.

D16 requires why-not disposition after the explanation envelope decision because:

- `Explanation.status="failed"` may cover the main why-not mental model;
- shipped `WhyNotUniverseResult` covers batch counterfactual analysis that may not fit row-centric explain;
- deleting or migrating why-not is subtractive and should not be decided before D20 explanation scope.

D22 owns the final why-not keep / migrate / fold / delete decision.

### 4.7 D17-D26 decision-doc ladder is the expected Stage 2 shape

D16 adopts this initial D-doc ladder:

| D-doc | Title | Primary questions |
|---|---|---|
| D17 | Result / row DTO foundation | Q2, Q4 |
| D18 | Return-shape transition strategy | Q3 |
| D19 | Digest source-of-truth | Q5 |
| D20 | Explanation envelope and Check/Diagnose/EvidenceGraph integration | Q6, Q8 |
| D21 | `row.close()` and closed-head gate | Q7 |
| D22 | Why-not disposition | Q9 |
| D23 | Legacy SDK hard-cut plan | Q10, Q13 |
| D24 | T1.3 final SDK `Rule` flip | Q11 |
| D25 | Evaluate/explain semantics consistency | Q14, C69 |
| D26 | Semantics commitments scope and adapter implementation policy | Q1, Q12, C73-C78 |

Stage 2 may merge or split adjacent documents only with an explicit rationale. It must not batch-draft multiple D-docs ahead of review.

### 4.8 Stage 3 owns implementation slice count, but D16 predicts T5 Core first

D16 does not lock implementation slice count. It predicts Stage 3 should schedule T5 Core first:

1. DTO foundation and compatibility harness.
2. Evaluate return-shape flip.
3. Explanation envelope and row resolver path.
4. `row.close()` / closed-head gate.
5. Why-not disposition.
6. T1.3 final `Rule` flip.
7. Legacy hard-cut and docs migration.

If D26 adopts T5 Semantics implementation in the same cycle, those slices should follow after Core slices unless a narrow semantics prerequisite is required for `semantics_digest` or C69 consistency.

## 5. Rejected Alternatives

### Option A: Put all C61-C78 implementation in one undifferentiated T5 tranche

- **Why rejected**: This would mix public result/evidence redesign, subtractive API hard-cut, SDK naming flip, adapter changes, temporal semantics, and uncertainty projection into one implementation queue. The blast radius is too broad for reviewed per-slice cadence.

### Option B: Exclude all semantics commitments from Stage 2

- **Why rejected**: C69 and C68 require semantics consistency and digest decisions before `EvaluateResult` and `Explanation` can be coherent. Stage 2 must at least decide the semantics boundary.

### Option C: Implement semantics wrappers before result/explain

- **Why rejected**: T5 was selected because result/evidence/explain is the public API gap after T4. C73-C78 are important but should not block DTO and explanation design unless D25/D26 finds a hard dependency.

### Option D: Move T1.3 final `Rule` flip outside T5

- **Why rejected**: T5 public APIs use application `Rule` for `head=`, while SDK `Rule` still names the legacy query class. Leaving the flip outside T5 would make the new docs and hard-cut incoherent.

### Option E: Decide why-not before `Explanation`

- **Why rejected**: Parent says explain may cover the core why-not need. Why-not should be evaluated after the explanation envelope and failure semantics are locked.

### Option F: Treat service routes as out-of-scope for hard-cut

- **Why rejected**: Track plan identifies service routes as affected. Hard-cut without service inventory risks non-SDK caller breakage.

### Option G: Reopen T4 closed-head inspect in T5 Stage 2

- **Why rejected**: T4.3 already shipped strict read-only inspect. T5 may consume it for `row.close()` / manual explain gates but must not reopen its algorithm unless a new reviewed decision explicitly supersedes D15.

## 6. Supporting Evidence

- T4 memory marks T4 complete and T4.3 archived with 163 preservation tests and 77 focused tests (`workflow/memory/current.md:3-9`, `workflow/memory/current.md:43-45`).
- Parent §5.8 defines the new `.eval` surface, DTOs, row-centric explain, and why-not pending state.
- Parent C61-C78 combine result DTOs, explanation, hard-cut, semantics wrappers, uncertainty projection, temporal projection, and PyReason iteration.
- Track plan T5 predicts roughly ten sub-slices and lists SDK store, SDK shells, application protocol/runtime, and service routes as affected surfaces.
- Shipped SDK still returns `list[CandidateSet]` and still exposes `accept`, `accept_many`, `check`, `diagnose`, and `why_not`.
- Shipped SDK namespace still has legacy `Rule` as top-level `Rule`.
- T4.3 shipped only inspect fields, not `row.close()` or `fg.eval.explain`.

## 7. Consequences

### 7.1 Downstream unblocking

D16 unblocks:

- D17 result/row DTO foundation without re-litigating whether T5 owns the result surface.
- D18 return-shape transition with an explicit hard-cut vs additive decision target.
- D20 explanation envelope design against shipped Check/Diagnose/EvidenceGraph.
- D24 final SDK naming decision.
- D25/D26 semantics decisions without letting semantics block early Core DTO design.

### 7.2 Implementation constraints

Future T5 blueprints must:

- identify whether they belong to T5 Core or T5 Semantics;
- avoid adapter edits in T5 Core slices unless a reviewed D-doc makes them mandatory;
- preserve T4.1/T4.2/T4.3 private helpers unless explicitly superseded;
- include service-route grep before any hard-cut implementation;
- include docs migration in the same tranche as public hard-cut;
- not implement parent §6 or §9 deferred surfaces.

### 7.3 Stage 3 gating

Stage 3 synthesis must classify:

- T5 Core blueprint-eligible items;
- T5 Semantics blueprint-eligible or deferred items;
- hard-cut blast-radius blockers;
- service-route update requirements;
- T1.3 final `Rule` flip placement;
- why-not final disposition.

Stage 3 must not produce implementation blueprints until D17-D26, or a reviewed equivalent set, are complete.

## 8. Acceptance Criteria

- [ ] D17-D26 cite D16 for T5 Core vs T5 Semantics boundary.
- [ ] D17-D25 do not implement full C73-C78 semantics unless D26 adopts that scope.
- [ ] D23 or the hard-cut blueprint includes service-route blast-radius grep before implementation.
- [ ] D24 decides the T1.3 final SDK `Rule` flip before final T5 docs migration.
- [ ] D22 decides why-not only after D20 explanation envelope scope is reviewed.
- [ ] Stage 3 synthesis separates Core result/explain work from Semantics wrapper / adapter work.
- [ ] No T5 decision reopens T4.3 closed-head inspect without explicitly superseding D15.
- [ ] Parent §6 task split and §9 RuleExpr x evidence joins remain deferred.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | T5 Stage 1 audit v2 mapped Q1/Q10/Q11/Q12/Q13/Q14 to D16. D16 locks T5 Core vs T5 Semantics boundary, requires C73-C78 Stage 2 coverage without making full semantics implementation a Core blocker, places T1.3 final `Rule` flip inside T5 Core, and requires service-route blast-radius inventory before hard-cut implementation. |
| 2026-05-25 | proposed-amend | Step 4.2 v1 precision amendments | Renamed D26 to "Semantics commitments scope and adapter implementation policy", clarified adapter-touching slices are at least M and potentially L depending on blast radius, and added generic head Rule naming guidance for D17-D23 before D24 decides the final SDK `Rule` flip. |
