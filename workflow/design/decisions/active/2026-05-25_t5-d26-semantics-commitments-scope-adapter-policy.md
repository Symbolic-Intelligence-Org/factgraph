# D26 Decision: Semantics Commitments Scope and Adapter Implementation Policy

- Status: adopted
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: adopted design constraint; locks T5 semantics commitment scope, adapter-touching deferral policy, and the boundary between T5 Core and post-Core semantics work.
- Implementation Anchors: T5.8 semantics-lite wrapper fix feat `58ba78e1`, archive `efd65c0e`; adapter-touching C74/C76/C77/C78 remain deferred to T10 per roadmap `e6bfe357`.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md` Q1, Q12, F9, and C73-C78 triage.
  - D16 `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md` sections 4.1, 4.2, and 4.7.
  - D17 `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md` section 4.3.
  - D19 `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md` section 4.4.
  - D25 `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md` sections 4.1-4.8.
  - Parent design `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md:1598-1603`.
  - Track plan `workflow/design/design-points/archive/rule-expression-and-proof-track-plan.zh.md:244-250`.
  - Evidence-tree v1 `workflow/design/design-points/archive/evidence-tree-rainbird-style-v1.zh.md` sections 6.1-6.8 and C110-C113.
  - Shipped semantics wrappers `src/factgraph/sdk/semantics.py:61-149`.
  - Shipped semantics lowering `src/factgraph/sdk/store.py:2870-2950`.
  - Shipped core `SemanticsProfile` `src/factgraph/core/semantics/profile.py:24-102`.
- Outputs / Downstream:
  - Stage 3 T5 synthesis.
  - T5 implementation slice ladder.
  - Optional post-Core semantics-lite blueprint.
  - Post-T5 semantics-adapter / evidence-tree cycle planning.
- Related:
  - `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t5-d25-evaluate-explain-semantics-consistency.md`
  - `workflow/design/design-points/archive/evidence-tree-rainbird-style-v1.zh.md`
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Depends on: D16-D25 reviewed clean.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

D16 splits T5 into T5 Core and T5 Semantics. T5 Core owns result, row, evidence, explain, hard-cut, naming, and consistency policy. T5 Semantics owns C73-C78. D16 requires Stage 2 to decide C73-C78, but it explicitly allows Stage 3 to schedule or defer their implementation.

D25 already locks the minimal T5 Core semantics contract: compare normalized `semantics_digest`, use strict raise for row-anchored mismatch, and treat `raw_kind` / `bound` as copied carrier fields.

The parent track plan lists T5.6-T5.8 as semantics work, including wrapper changes and a ProbLog adapter slice. That track plan is implementation decomposition, not design semantics authority; D26 decides which parts remain in the current T5 implementation ladder.

Evidence-tree v1 is cited only for its carrier constraints: `raw_kind` / `bound` are the unique canonical quantitative carrier, deterministic results use `None` / `None`, and adapter-native debug fields are non-contract.

## 2. Scope

D26 decides:

- whether C73-C78 belong to T5 Core, a post-Core semantics-lite lane, or a later adapter cycle;
- which parts of C73-C78 may be implemented without adapter production edits;
- which adapter-touching parts are deferred;
- how D26 preserves D17/D19/D25 contracts;
- how Stage 3 should classify semantics slices;
- what implementation states are milestone-safe versus local-only.

## 3. Non-Scope

D26 does not decide:

- `EvaluateRow` / `Explanation` public fields; D17 and D20 own them;
- `semantics_digest` formula or digest format; D19 owns them;
- evaluate/explain mismatch behavior; D25 owns it;
- exact Python dataclass field layout for future `*RuleParams`;
- exact adapter implementation algorithms for ProbLog, PyReason, Souffle, or native;
- temporal model semantics beyond classifying C77 scope;
- probability aggregation, SDD, noisy-or, path-level versus atom-level propagation, or cross-engine bound equivalence;
- service route hard-cut; D23 owns it;
- SDK `Rule` naming; D24 owns it;
- parent section 6 task split or parent section 9 RuleExpr x evidence joins.

## 4. Decision

### 4.1 T5 Core closes without implementing full C73-C78

D26 decides that full C73-C78 implementation is not required for T5 Core closure.

T5 Core remains complete when it implements:

- D17 result / row DTOs;
- D18 hard-cut return shape;
- D19 digest sources including `semantics_digest`;
- D20 `Explanation`;
- D21 `row.close()` and closed-head gate;
- D22 why-not fold;
- D23 legacy hard-cut;
- D24 final SDK `Rule` flip;
- D25 strict evaluate/explain semantics consistency.

C73-C78 must not be silently implemented inside those Core slices. Any implementation slice that changes semantics wrapper fields, adapter behavior, or carrier population must declare itself as a semantics slice and run its own Step 4.6 grep and G7 baseline.

### 4.2 D26 creates a post-Core "Semantics Lite" lane

D26 allows Stage 3 to schedule an optional Semantics Lite lane after T5 Core slices and before final T5 archive if the work remains M-class and does not edit adapter production files.

Semantics Lite may include:

- C73 wrapper-level per-rule params map shape;
- C75 wrapper symmetry and public wrapper normalization cleanup;
- SDK wrapper to `SemanticsProfile` lowering changes that do not require adapter behavior changes;
- validation that unknown rule ids in wrapper-level `rule_params` raise before adapter dispatch;
- documentation that `raw_kind` / `bound` remain carrier-only fields.

Semantics Lite must not include:

- ProbLog adapter consumption of `raw_kind` / `bound`;
- PyReason adapter atom-bound execution changes;
- temporal projection runtime behavior;
- iteration-count execution behavior;
- changes to D25 mismatch policy.

If Stage 3 judges Semantics Lite too large or too entangled with adapter behavior, it must defer the lane to a post-T5 semantics cycle.

### 4.3 C73 is Semantics Lite eligible, not T5 Core

C73 requires per-rule semantics params:

```python
rule_params: dict[Rule.id, *RuleParams]
```

with fallback:

```text
rule_params -> wrapper default_* -> engine native
```

D26 classifies C73 as Semantics Lite eligible because it can be implemented as SDK wrapper shape plus `SemanticsProfile` lowering and validation.

Constraints:

- `rule_params` keys must refer to application Rule ids in the evaluated expression and head context.
- Unknown rule ids must raise before adapter dispatch.
- Rule id validation must consume the same rule identity substrate used by T5 Core evaluation; it must not reopen T4 head identity.
- C73 must not require adapter production edits to be milestone-safe.
- If a concrete `*RuleParams` field requires adapter behavior to be meaningful, that field is deferred with its adapter commitment.

### 4.4 C74 is split: wrapper schema eligible, atom-bound execution deferred

C74 requires PyReason rule params:

- `derived_bound`;
- `atom_bounds`;
- `timestep_delay`;
- full atom id keys for `atom_bounds`.

D26 splits C74:

- A wrapper schema and validation subset is Semantics Lite eligible if it only validates field shapes, full atom-id keys, and lowering into `SemanticsProfile.rule_projection`.
- Any PyReason adapter execution change that consumes `atom_bounds`, changes timestep execution, or changes result `raw_kind` / `bound` population is deferred to the post-T5 semantics-adapter cycle.

Rules:

- short atom names are rejected; full atom ids such as `<rule_id>:atom_<index>` are required;
- invalid atom ids raise before adapter dispatch;
- validation may use Rule atom ids but must not alter Rule content digests;
- adapter behavior must not be implied by docs until the adapter implementation lands.

### 4.5 C75 wrapper symmetry and carrier model are Semantics Lite eligible

C75 requires wrapper symmetry between `PyReasonSemantics` and `ProbLogSemantics`, wrapper-level defaults, and a raw quantitative model based on `raw_kind` / `bound`.

D26 classifies the public wrapper symmetry and carrier documentation portion as Semantics Lite eligible.

Minimum target:

- public wrappers normalize to core `SemanticsProfile`;
- both wrappers use `raw_kind` / `bound` vocabulary rather than public `probability`, `confidence`, or `certainty`;
- ProbLog point probability is represented as `raw_kind="probabilistic", bound=(p, p)`;
- deterministic output remains `None` / `None`;
- wrapper defaults are reflected in normalized profile content so D19 `semantics_digest` changes when defaults change.

D26 does not require adapter math to be implemented for C75. Adapter output population remains governed by C74/C76 and the post-T5 adapter policy.

### 4.6 C76 is split: schema may be defined, adapter consumption is deferred

C76 has three parts:

1. SDK shell / public wrapper shape for `ProbLogSemantics.uncertainty_projection`;
2. lowering into core `SemanticsProfile.uncertainty_projection`;
3. ProbLog adapter consumption of fact-level `raw_kind` / `bound` by policy.

D26 classifies parts 1 and 2 as Semantics Lite eligible only if they do not edit adapter production files.

D26 defers part 3 to a post-T5 semantics-adapter cycle.

The default policy remains conservative:

```python
{
    "probabilistic": {"policy": "reject"},
    "possibilistic": {"policy": "reject"},
    "fallback": "reject_unconfigured",
}
```

Opt-in projection policies such as midpoint, lower, upper, probability interval, or identity probability must not appear as silently active defaults. They require explicit user configuration and adapter implementation review.

### 4.7 C77 temporal projection is deferred out of T5

C77 requires temporal projection modes:

- `none`;
- `fact_boundaries`;
- `time_binned`;
- ISO 8601 duration validation for `time_binned.bin_size`;
- migration from old names such as `valid_time_boundaries`.

D26 defers C77 implementation to a post-T5 semantics-adapter / temporal cycle.

Rationale:

- temporal projection changes runtime interpretation of fact lifetimes;
- service docs and runtime v1 already have temporal policy surfaces that need a separate blast-radius audit;
- adapter behavior, view snapshot semantics, and evidence rendering would all be affected;
- C77 is not needed for D25 strict digest comparison.

SemanticsProfile may continue to carry a normalized `temporal_projection` field for digest and future compatibility, but T5 Core and Semantics Lite must not add new temporal runtime behavior.

### 4.8 C78 PyReason iteration count is deferred out of T5

C78 requires `PyReasonSemantics.iteration_count: int = 1` and separates iteration count from temporal projection.

D26 defers C78 implementation to the post-T5 semantics-adapter cycle.

Rationale:

- iteration count changes PyReason execution behavior;
- it has no ProbLog analog;
- it may change evidence topology and result convergence;
- it is not required for T5 Core result / explain DTOs;
- it should be tested with PyReason adapter G7 and service-route coverage as its own slice.

Until that slice lands, T5 docs must not imply that users can configure PyReason iteration depth through the public T5 evaluation API.

### 4.9 Adapter production edits are post-T5 by default

D26 sets the default policy:

- any slice that edits `src/factgraph/adapters/`, engine-specific runtime execution, or service runtime adapter dispatch for C74/C76/C77/C78 is out of T5 Core;
- such a slice is at least M-class and may be L-class depending on cross-adapter blast radius;
- it requires its own Step 4.6 grep and G7 baseline;
- it must explicitly restate D17/D19/D25 invariants;
- it must not be batched into DTO / explain / hard-cut implementation slices.

Stage 3 may propose a post-Core adapter slice only if it is clearly separated from Core closure. Otherwise, adapter work is deferred to the next semantics/evidence cycle.

### 4.10 D25 policy remains fixed across all D26 outcomes

D26 must not change:

- compare by `semantics_digest`;
- strict raise on row-anchored mismatch;
- no warning / silent replay;
- `raw_kind` / `bound` as copied carrier fields;
- `checked_scope` minimum semantics keys.

If later semantics slices add wrapper fields, adapter output, or temporal behavior, they change the digest input and row carrier population. They do not change the D25 comparison policy.

## 5. Rejected Alternatives

### Option A: Implement all C73-C78 inside T5 Core

Rejected. This would turn the result/evidence/explain tranche into a broad semantics and adapter redesign. It would also risk batching adapter changes into DTO and hard-cut slices.

### Option B: Defer all semantics decisions, including C73-C78 scope

Rejected. D16 requires Stage 2 to decide C73-C78 scope because semantics digest and explain consistency are already T5 Core concerns.

### Option C: Implement adapter consumption before wrapper schema cleanup

Rejected. Adapter consumption needs stable wrapper/profile input and validation rules first.

### Option D: Treat existing shipped wrappers as complete C73-C78 implementation

Rejected. Shipped wrappers are partial. They do not fully cover per-rule params, atom-bound keys, ProbLog raw_kind/bound projection, temporal projection, or iteration count.

### Option E: Let ProbLog adapter silently consume raw_kind/bound with default midpoint

Rejected. C76 requires conservative reject defaults and explicit opt-in for strong semantic projection choices.

### Option F: Put temporal projection into T5 Core because `SemanticsProfile` has a field

Rejected. Carrying a normalized field for digest compatibility is not the same as implementing temporal runtime behavior.

### Option G: Add `iteration_count` in wrapper only with no adapter behavior

Rejected. A wrapper field that cannot affect PyReason execution would be misleading. C78 is deferred with adapter behavior.

### Option H: Change D25 mismatch policy based on which semantics features land

Rejected. D25 is a policy contract independent of C73-C78 implementation schedule.

## 6. Supporting Evidence

| Source | Evidence | D26 consequence |
|---|---|---|
| D16 sections 4.1-4.2 | T5 Semantics owns C73-C78, but full implementation is not required for T5 Core. | D26 can split Core, Semantics Lite, and adapter cycle. |
| Stage 1 audit F9 | Semantics wrappers are partially shipped and C73-C78 are larger than result DTOs. | D26 must avoid pretending shipped wrappers are complete. |
| Parent C73-C78 | Commitments include wrapper shape, atom bounds, uncertainty projection, temporal projection, and iteration count. | D26 must classify each commitment explicitly. |
| Track plan T5.6-T5.8 | Semantics wrappers and ProbLog adapter consumption were planned as separate slices. | D26 can preserve the separation and defer adapter work. |
| Shipped `src/factgraph/sdk/semantics.py:61-149` | Wrappers expose partial ProbLog and PyReason semantics fields. | C73-C78 are not greenfield, but gaps remain. |
| Shipped `src/factgraph/sdk/store.py:2870-2950` | Wrapper lowering already produces `SemanticsProfile` entries. | Semantics Lite can build on lowering without adapter edits. |
| Evidence-tree v1 section 6 | `raw_kind` / `bound` are carrier-only and math aggregation is deferred. | D26 must not make carrier fields imply adapter math. |
| D25 section 4.8 | D25 policy is independent of D26 implementation choices. | D26 cannot reopen mismatch behavior. |

## 7. Consequences

### 7.1 Positive consequences

- T5 Core can close without waiting for adapter semantics redesign.
- Stage 3 has a clear optional Semantics Lite lane.
- Adapter-touching semantics work gets its own risk classification and verification.
- D17/D19/D25 invariants remain stable.
- C73-C78 are decided rather than left ambiguous.

### 7.2 Costs

- Some parent semantics commitments will not land in the initial T5 Core implementation.
- Users may see `semantics_digest` and strict mismatch behavior before full wrapper symmetry lands.
- Docs must be careful not to advertise deferred C76/C77/C78 capabilities.
- A follow-up semantics-adapter cycle remains necessary for full parent parity.

### 7.3 Follow-up decisions

- Stage 3 synthesis decides whether Semantics Lite is included before T5 archive or deferred.
- A later semantics-adapter cycle must decide concrete ProbLog and PyReason adapter implementation details.
- Evidence-tree internal schema work remains a separate future cycle.
- Service-route temporal / semantics blast radius should be audited before C77 implementation.

## 8. Acceptance Criteria

- [ ] D26 classifies T5 Core as not requiring full C73-C78 implementation.
- [ ] D26 defines a Semantics Lite lane for non-adapter wrapper/profile work.
- [ ] C73 is classified as Semantics Lite eligible.
- [ ] C74 is split between wrapper validation and deferred PyReason adapter execution.
- [ ] C75 wrapper symmetry and carrier model are Semantics Lite eligible.
- [ ] C76 SDK shell/lowering is split from deferred ProbLog adapter consumption.
- [ ] C77 temporal projection is deferred out of T5.
- [ ] C78 PyReason iteration count is deferred out of T5.
- [ ] Adapter production edits are at least M-class and post-T5 by default.
- [ ] D25 mismatch policy remains fixed.

## 9. Decision Record

| Date | Stage | Summary | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Split C73-C78 into T5 Core-independent Semantics Lite eligibility and post-T5 adapter work. | Drafted after D25 reviewed clean v1. D26 closes Stage 2 semantics scope by deciding that T5 Core does not require full C73-C78 implementation, C73/C75 and selected non-adapter wrapper/profile work may form an optional Semantics Lite lane, and adapter-touching C74/C76/C77/C78 work is deferred by default to a post-T5 semantics-adapter cycle. |
