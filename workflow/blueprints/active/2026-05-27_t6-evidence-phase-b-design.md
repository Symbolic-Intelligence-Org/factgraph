# Task Blueprint: T6 Evidence Phase B Design Skeleton

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: L (design skeleton; may narrow after Step 4.6)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t6-evidence-phase-b-design.audit.md`
- Trigger: Post-T5/T11 roadmap N2. `EvidenceGraph` is shipped as a minimal
  opaque graph, match witness output is explicitly deferred, and T8/T9 depend
  on evidence design sources that can guide implementation and release-facing
  docs without inventing semantics during implementation.

## 0. Scope Locks

### In scope

T6 makes the active evidence design implementable for Phase B. It is a
design-source cycle, not a runtime implementation cycle.

1. **Audit Channel v1 (`evidence-tree-rainbird-style-v1.zh.md` §10)**:
   - replace the skeleton with an implementable v1 audit channel contract;
   - lock the shipped metadata bridge and the durable graph metadata stance;
   - define immutability / hash / signature boundaries for v1 vs v2+;
   - define validator and JSON roundtrip expectations without changing code.
2. **Rendering (`evidence-tree-rainbird-style-v1.zh.md` §11)**:
   - replace the skeleton with a reference-renderer contract;
   - distinguish reference HTML renderers from product UI obligations;
   - lock layout mode matrix, JSON roundtrip, error / empty / large graph
     behavior, and custom UI boundaries.
3. **Deferred Items (`evidence-tree-rainbird-style-v1.zh.md` §14)**:
   - expand D1-D19 with owner candidate, trigger, v1/non-v1 boundary, and
     stop-amend notes;
   - keep failure-side why-not, per-fact ACL, session logs, match witness APIs,
     and engine-specific advanced evidence out of v1 unless a scoped decision
     says otherwise.
4. **T8 implementation split proposal**:
   - add a follow-on split matrix for T8 evidence implementation;
   - separate validator / metadata population, native/Souffle topology, and
     engine-specific enrichments gated by T10 or later cycles.
5. **Cross-reference hygiene**:
   - update the parent rule-expression essay §7 only if needed to point to the
     Phase B design source;
   - preserve quickstart/user docs silence about full EvidenceGraph internals
     unless the change is a narrow forward reference.

### Out of scope

- Production code changes in `src/factgraph/audit`, SDK, adapters, service,
  release tooling, or tests.
- Changing public DTOs (`Claim`, `EvidenceRef`, `EvaluateRow`, `EvaluateResult`,
  `Explanation`, `EvidenceGraph`).
- Implementing richer evidence graph population.
- Adapter evidence semantics, ProbLog/PyReason/Nemo enrichment, or T10 carrier
  execution.
- Failed graph / why-not tree runtime implementation.
- Match witness APIs such as `.as_assertions()`, `.witnesses()`, or `.to_view()`.
- Service/OpenAPI routes, ACL, signature, session log, or LLM explain channels.
- Broad quickstart teaching for EvidenceGraph internals before runtime support.
- v0.2 release machinery or live release work.
- Dirty baseline cleanup.

### Stop / amend triggers

Pause and amend if Step 4.6 or implementation shows:

- T6 cannot write an implementable design without changing shipped DTOs;
- `EvidenceGraph` internals must become public user-facing guarantees in v0.2;
- failed/why-not evidence, match witness output, or session log APIs need to be
  pulled into this cycle;
- adapter production semantics or engine math must change;
- service/OpenAPI, ACL, signature, or persistence-layer schema changes are
  required;
- the work expands into the full T8 implementation instead of a T6 design
  source.

## 1. Problem

The active evidence design has shipped Phase A/B-1 through B-6 decisions, and
T5 delivered a minimal `Explanation` + `EvidenceGraph` bridge. But the sections
that should guide the next evidence implementation step are still skeletons:

- §10 only says v1 audit is carried by `EvaluateResult` and `Explanation`
  metadata, while session logs and signatures are deferred.
- §11 only lists existing render/roundtrip helpers and says product UI should
  remain custom.
- §14 lists D1-D19 but still says Phase B should later fill triggers and scope
  sketches.

This leaves T8 at risk of inventing audit metadata, renderer behavior, and
deferred-item boundaries during implementation. T6 closes that design gap.

## 2. Goals

- Turn §10, §11, and §14 into implementable design sources.
- Preserve the shipped v0.2 boundary: `EvidenceGraph` remains opaque in user
  docs and minimal in runtime behavior.
- Record a T8 implementation split that can start from stable design facts.
- Clarify what remains v2+ or T10/T7-dependent.
- Keep the release path and dirty baseline untouched.

## 3. Inputs

| Source | Role |
|---|---|
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` | Primary design target; §10/§11/§14 are the skeletons to complete. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | Parent essay; §7 delegates evidence authority to the evidence design. |
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` | T6/T8/T9 dependency and release-boundary source. |
| `workflow/design/design-points/active/match-api-design.zh.md` | Match witness boundary; witness/assertion-returning match output is deferred to evidence/witness design. |
| `src/factgraph/audit/evidence_graph.py` | Shipped `EvidenceGraph`, renderer, validation, and JSON roundtrip truth. |
| `src/factgraph/application/protocol/evaluate_result.py` | Shipped `Claim`, `EvidenceRef`, `EvaluateRow`, `EvaluateResult`, `Explanation`, and metadata bridge truth. |
| `docs/official/kernel/quickstart/evidence.md` | User-facing boundary: EvidenceGraph internals remain intentionally opaque in v0.2 docs. |
| `src/factgraph/audit/docs/02_evidence_graph.md` | Current audit module docs for `EvidenceGraph` structure and reference renderer. |
| T5.1 / T5.3 archived blueprints | DTO and minimal evidence bridge anchors. |
| Hubble read-only inventory | Pre-draft evidence Phase B inventory and recommended scope. |

## 4. Draft Decisions To Lock

| # | Decision | Draft leaning |
|---|---|---|
| D1 | T6 output shape | Directly edit `evidence-tree-rainbird-style-v1.zh.md` §10/§11/§14, plus narrow parent §7 cross-link only if needed. |
| D2 | Audit channel v1 | Define v1 as metadata carried by `EvaluateResult`, `Explanation`, and `EvidenceGraph.metadata`; no session log or signatures in v1. |
| D3 | Audit immutability stance | v1 requires deterministic IDs/digests and JSON roundtrip validation; cryptographic signatures and append-only session logs are v2+. |
| D4 | Renderer boundary | Reference HTML renderers are diagnostic utilities, not product UI obligations; product UI remains custom. |
| D5 | Renderer modes | Keep `tree` and `timeline` as shipped modes; matrix should say which engines/forms each mode is appropriate for. |
| D6 | Deferred registry | Expand D1-D19 with trigger, owner, v1 boundary, and implementation-cycle hint; do not promote any deferred item by default. |
| D7 | T8 split | Propose T8-A validator/metadata, T8-B native/Souffle topology, T8-C engine-specific enrichment gated by T10/PyReason work. |
| D8 | User docs | Do not add full EvidenceGraph teaching until implementation exists; at most keep forward references. |
| D9 | Match witness seam | Keep witness-returning match output deferred; T6 may record the seam but must not design the runtime API in detail. |

## 5. Expected Step 4.6 Inventory

The scoped commit must fill concrete results for:

1. current branch / dirty baseline status;
2. exact current content of §10 and its missing fields;
3. exact current content of §11 and its missing rendering decisions;
4. exact current D1-D19 deferred table and any numbering gaps;
5. shipped `EvidenceGraph` fields, validation rules, renderer modes, and
   dict roundtrip functions with file:line refs;
6. shipped `Claim` / `EvidenceRef` / `EvaluateRow` / `EvaluateResult` /
   `Explanation` fields and invariants with file:line refs;
7. current metadata bridge keys copied into evidence graph metadata;
8. T5.1/T5.3 archived blueprint anchors for DTO and minimal EvidenceGraph
   behavior;
9. current quickstart / audit docs stance on EvidenceGraph internals;
10. match design witness boundary and how T6 should avoid overclaiming it;
11. roadmap T6/T8/T9 dependency and v0.2 release boundary;
12. final class confirmation and implementation file set;
13. any stop-amend findings.

## 6. Expected Implementation Shape

Implementation should be staged in design commits:

1. **§10 Audit Channel**: metadata field table, audit package boundary,
   immutability stance, validation and roundtrip expectations, v2+ exclusions.
2. **§11 Rendering**: reference renderer boundary, layout matrix, product UI
   split, JSON roundtrip, error/empty/large graph behavior.
3. **§14 Deferred Items + T8 split**: D1-D19 owner/trigger/non-goal expansion
   and follow-on T8 implementation split proposal.
4. **Cross-link cleanup**: parent §7 and roadmap/quickstart references only if
   Step 4.6 shows stale pointers.

If any step requires production code or public DTO changes, stop and amend.

## 7. Verification Gates

- `git diff --check` clean.
- No production, test, service, OpenAPI, adapter, release, or notebook changes.
- Design references have file:line-supported source anchors from Step 4.6.
- Deferred items D1-D19 retain explicit trigger and non-goal boundaries.
- T8 split proposal is specific enough to seed a future blueprint.
- Sacred `master` unchanged.
- Dirty baseline preserved.

## 8. Acceptance

- [ ] Step 4.6 inventory completed with source refs.
- [ ] §10 Audit Channel is no longer a skeleton.
- [ ] §11 Rendering is no longer a skeleton.
- [ ] §14 Deferred Items has owner / trigger / non-goal / implementation hint
      coverage for D1-D19.
- [ ] T8 implementation split proposal exists.
- [ ] Match witness boundary remains deferred.
- [ ] No production / DTO / adapter / service / release changes.
- [ ] Dirty baseline and sacred master preserved.

