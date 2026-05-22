# Session Handoff: 2026-03-21 (Updated)

This document enables a new agent to resume work with full context. It supersedes all prior handoff documents. It is a session restart reference, not a substitute for active blueprints, archived blueprints, or module docs.

Quick orientation:
- `certainty v1` is now **implemented and frozen**
- canonical behavior lives in module docs, especially `core/docs/01_architecture*.md`, `annotation/docs/README.md`, and `service/docs/03_runtime_queries_views.md`
- the recommended next step is **probability feasibility / scoping**, not more certainty semantics work

## 1. Current Stage

Building on the 2026-03-20 baseline (evidence tree NL explain + Souffle partial witness + live permalinks + salience/impact ownership freeze), this session landed the **complete certainty delivery chain** from annotation through audit/static, plus structural cleanup and tooling:

1. **Candidate confidence-kind + rule condition-weight metadata** (`9147008`) — `confidence_kind` on CandidateSet, `condition_weights` on rule payloads, SDK/authoring/service plumbing
2. **Certainty annotation prototype** (`4ce084d`) — `derive_certainty_summary` with bottleneck aggregation, `CertaintySummary` / `ConditionImpact` dataclasses
3. **Certainty explain delivery** (`6f5473c`) — runtime explain-summary / narrative / NL with additive certainty surfaces
4. **Test decomposition** (`c2b061f`) — 10,372-line monolith → 7 focused test files + shared helpers
5. **Certainty audit + static delivery** (`62a6c2a`) — export-time materialization into `certainty_summaries.jsonl`, AuditQuery, static site rendering
6. **Architecture docs sync** (`f62061e`) — CN/EN architecture docs + module docs aligned
7. **Certainty runtime boundary cleanup** (`f0fd28a`) — helper extraction to `_certainty_service.py`, archive inventory table
8. **Certainty salience ranking v1** (`defd56a`) — `rank_certainty_conditions` with bottleneck marking, narrative sorted output, NL weakest-condition sentence
9. **Benchmark Workload D + ledger bench fix** (`5cf1076`) — certainty annotation benchmark, 0.0009s/0.02MB overhead
10. **E2E certainty chain verification** (`d5a9ca0`) — proves no structural gap between real evaluate output and certainty derivation
11. **ConfidenceKindResolver protocol** (`de083d1`) — create-time certainty routing via resolver, not post-evaluation patch
12. **Certainty evidence tree demo notebook** (`4eeb0bc`→`b111553`) — end-to-end Jupyter notebook with tree, summary, narrative, NL, audit, static HTML
13. **Fact-level confidence carrier** (`e2619f0`) — connects `meta.confidence` from assertions through evidence tree to certainty summary
14. **Additive aggregation strategy** (`389708b`) — second certainty strategy: `sum(normalized_weight × confidence)`, query-time selectable
15. **Certainty v1 freeze** (`e9f9bc2`) — frozen contract, explicit non-goals, blueprint gate for any semantics changes
16. **Blueprint lifecycle skill** (`0df60cc`) — `.claude/skills/blueprint/`
17. **Handoff session document skill** (`ce55f56`) — `.claude/skills/handoff/`

Current position: **certainty v1 is complete and frozen** — from fact-level confidence write through create-time routing, dual aggregation strategies (bottleneck + additive), ranking, narrative/NL delivery, audit export, and static site rendering. The recommended next direction is **probability feasibility / scoping**. Chain/recursive certainty propagation remains a legitimate future line, but it is no longer the default next step.

## 2. Capability Baseline

### 2.1 Certainty Delivery Chain (new this session, stable)

Full pipeline:

```
fact write with meta.confidence
  → evaluate with CertaintyConfidenceKindResolver (create-time routing)
  → evidence tree: assertion_fact.confidence → predicate_witness_group.condition_confidence
  → derive_certainty_summary (annotation, bottleneck or additive)
  → CertaintySummary { conditions, aggregate_certainty, aggregation }
  → rank_certainty_conditions (impact ascending, bottleneck marked)
  → explain-summary: response-level certainty_summary sibling (with certainty_aggregation option)
  → explain-narrative: certainty_lines (sorted, [bottleneck] tagged in bottleneck mode)
                        + certainty_bottleneck (machine-readable, bottleneck mode only)
  → explain-nl: certainty paragraph + weakest-condition sentence (bottleneck mode)
  → export: certainty_summaries.jsonl (export-time materialization)
  → audit: AuditQuery.get_candidate_certainty_summary()
  → audit narrative: certainty_lines with ranking
  → static site: certainty section in candidate evidence page
```

Key design decisions:
- **Two aggregation strategies**: `"bottleneck"` (min weighted impact, default) and `"additive"` (sum of normalized contributions), switchable at query time via `certainty_aggregation` parameter
- **Fact-level confidence carrier**: `assertion_fact.confidence` → `predicate_witness_group.condition_confidence = max(children)` → used in `impact = weight × confidence`
- **Create-time routing**: `CertaintyConfidenceKindResolver` protocol decides `confidence_kind` at candidate creation, not post-evaluation patch
- **Eligibility guard**: single structured `rule_ref_edge` + no nested `referenced_support`; multi-rule/nested/unresolved degrade to `certainty_summary=null`
- **Three-state lookup**: `_lookup_condition_weights_for_candidate` returns `None` (ineligible) | `{}` (no weights) | `{k:v}` (has weights)
- **Export-time materialization**: `condition_weights` only exist in `FileAuthoringRegistry` filesystem; audit cannot derive at query-time
- **Additive delivery**: `certainty_lines` / `certainty_bottleneck` are optional keys; base narrative/NL unaffected
- **NL consumes structured data**: `certainty_bottleneck` key (not presentation string parsing)
- **Ranking in annotation layer**: `rank_certainty_conditions` is a pure function; narrative/NL only consume its output
- **Impact semantics vary by strategy**: bottleneck = absolute `weight × confidence`; additive = normalized `(weight/Σweights) × confidence`

### 2.2 Certainty V1 Freeze Status (new this session, stable)

`certainty v1` is now frozen. The freeze is recorded in:
- `src/factpy_kernel/core/annotation/docs/README.md` §5
- `src/factpy_kernel/core/docs/01_architecture.md` §8.1
- `src/factpy_kernel/core/docs/01_architecture.en.md` §8.1
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`

Frozen contract categories:
- producer contract: create-time certainty routing on native path
- carrier contract: `assertion_fact.confidence` and `predicate_witness_group.condition_confidence`
- summary contract: `bottleneck` default + `additive` optional explain-time strategy
- delivery contract: runtime dual-strategy support, audit/static fixed to default bottleneck

Semantics changes now require a blueprint. Safe direct changes without reopening the contract:
- bug fixes
- performance work
- docs clarification

### 2.3 Confidence Kind Infrastructure (new this session, stable)

- `CONFIDENCE_KINDS = frozenset({"none", "probability", "certainty"})` — frozen
- `CandidateSet.confidence_kind: str = "none"` — validated at creation
- `ConfidenceKindResolver` protocol in `core/store/_confidence_kind_resolver.py`
- `CertaintyConfidenceKindResolver` implementation: checks single resolved rule_ref_edge + condition_weights via `RuleSpecReader` protocol
- `RuleSpecReader` protocol: `read_rule_spec(rule_id, version) -> dict | None` — service injects `FileAuthoringRegistry`, SDK parity deferred
- `Store.evaluate(..., confidence_kind_resolver=None)` → `evaluate_store` → builders thread resolver
- Native / Souffle deterministic → `"none"` (unless resolver marks `"certainty"`)
- ProbLog adapter → `"probability"`
- `Store.get_candidate_confidence_kind(candidate_id)` — public accessor
- `Store.list_candidate_ids()` — enumeration for export-time batch

### 2.4 Test Decomposition (new this session, stable)

Original monolith `test_phase3_contracts_v1.py` (10,372 lines) split into:

| File | Focus | Tests |
|------|-------|-------|
| `test_certainty_explain_contracts.py` | Certainty + explain + audit round-trip + additive | ~30 |
| `test_evidence_tree_explain_contracts.py` | Evidence tree + rule trace | 15 |
| `test_domain_walkthrough_contracts.py` | Domain walkthroughs | 11 |
| `test_ecss_compliance_contracts.py` | ECSS VCD/temporal | 11 |
| `test_winning_branch_rule_trace_contracts.py` | Winning branch + rule trace | 10 |
| `test_artifact_sidecar_contracts.py` | Artifact sidecar + audit package | 11 |
| `test_phase3_contracts_v1.py` (residual) | Core entity/schema/query/derivation | 28 |
| `test_core_annotation_certainty.py` | Certainty derivation + ranking + additive unit tests | ~30 |
| `_test_helpers.py` | Shared fixtures | — |

### 2.5 Evidence Tree + Traceability (from prior sessions, still stable)

Unchanged from 2026-03-20 handoff §2.1–§2.4. All 8 frozen contracts remain frozen.

### 2.6 Helper Layering (cleaned up this session)

| Module | Layer | Dependencies | Role |
|--------|-------|-------------|------|
| `annotation/_certainty.py` | core | core only | `derive_certainty_summary`, `rank_certainty_conditions`, `CertaintySummary`, `ConditionImpact`, `RankedCondition`, dual aggregation strategies |
| `store/_certainty_materializer.py` | core | core only | `materialize_certainty_summary`, tree eligibility, serialization |
| `store/_confidence_kind_resolver.py` | core | core only | `RuleSpecReader` protocol, `ConfidenceKindResolver` protocol, `CertaintyConfidenceKindResolver`, `check_certainty_artifact_eligibility` |
| `store/_candidate_evidence_tree.py` | core | core only | Tree builder: `assertion_fact.confidence` carrier, `predicate_witness_group.condition_confidence` aggregation |
| `service/_certainty_service.py` | service | core + authoring | `_lookup_condition_weights_for_candidate`, `_compute_certainty_summary_from_tree`, `_compute_all_certainty_summaries` |
| `adapters/souffle/package.py` | adapters | core only | `export_package(..., *, certainty_summaries)` pure writer |
| `audit/reader.py` | audit | core | `AuditPackageData.certainty_summaries` |
| `audit/query.py` | audit | core | `get_candidate_certainty_summary()`, narrative with certainty |

Import graph verified clean: no core→authoring, no adapters→service, no audit→service.

### 2.7 Benchmarks (new this session, stable)

- Workload D (`tools/benchmarks/workload_d_reference.py`): certainty derivation + ranking pipeline benchmark
- Performance: **0.0009s / 0.02MB** for 20 conditions, depth 4 — certainty overhead negligible
- All 4 workloads (A/B/C/D) verified: `matches_golden=true`
- `bench_core_ledger_paths.py`: 3 bugs fixed, now runnable
- `README.md`: documents all workloads, baselines (including stub status), CLI usage

## 3. Git State

- Branch: `master`
- This session's commits (2026-03-21, chronological):
  - `85e94aa` — archive durable-artifact-storage blueprint
  - `9147008` — candidate confidence-kind + rule condition-weight metadata
  - `4ce084d` — certainty annotation prototype
  - `6f5473c` — certainty explain delivery (summary + narrative + NL)
  - `c2b061f` — test decomposition (10K → 7 files)
  - `62a6c2a` — certainty audit + static delivery
  - `f62061e` — architecture + module docs sync
  - `1c4a352` — misc docs cleanup + worktree removal
  - `f0fd28a` — certainty runtime boundary cleanup
  - `defd56a` — certainty salience ranking delivery
  - `d72a1b8` — session handoff (initial)
  - `5cf1076` — benchmark Workload D + ledger bench fix
  - `d5a9ca0` — e2e certainty chain compatibility verification
  - `de083d1` — ConfidenceKindResolver protocol for create-time routing
  - `4eeb0bc`→`b111553` — certainty evidence tree demo notebook (multiple iterations)
  - `e85ebcd` — document fact-level confidence known gap
  - `e2619f0` — connect fact-level confidence to evidence tree
  - `389708b` — weighted additive certainty aggregation strategy
  - `e9f9bc2` — freeze certainty v1 contract
  - `0df60cc` — blueprint lifecycle skill
  - `a568732` — gitignore third-party gstack skill directory
  - `ce55f56` — handoff session document skill
- Uncommitted:
  - `examples/certainty_evidence_tree.ipynb` (modified — notebook updates in progress)
  - `src/factpy_kernel/audit/static_ui.py` (modified — unrelated worktree change)
  - `.claude/agents/blueprint-editor.md` (deleted — migrated to skill)
  - `.claude/commands/blueprint.md` (deleted — migrated to skill)
  - `.claude/skills/*` (multiple untracked skill directories)
  - `tools/apply_static_ui_visual_upgrade.py` (untracked utility script)

## 4. Blueprint Status Summary

### Active Blueprints

| Blueprint | Status | Notes |
|-----------|--------|-------|
| `2026-03-15_overall-system-blueprint.md` | draft | Top-level system blueprint |
| `2026-03-16_temporal-hybrid-reasoning-blueprint.md` | draft | Temporal reasoning |
| `2026-03-17_runtime-traceability-explainability-blueprint.md` | draft | Parent blueprint for evidence tree line |

### Key Archived Blueprints (this session)

- `certainty-summary-explain-delivery` — runtime explain endpoints with certainty
- `certainty-aware-narrative-nl-delivery` — narrative/NL additive certainty
- `certainty-audit-static-delivery` — export-time materialization
- `phase3-test-decomposition` — 10K-line monolith split
- `certainty-runtime-boundary-cleanup` — helper extraction + archive index
- `certainty-salience-ranking-v1` — impact ranking + bottleneck marking
- `confidence-kind-certainty-routing` — ConfidenceKindResolver protocol
- `fact-confidence-to-evidence-tree` — fact-level confidence carrier
- `certainty-additive-aggregation-v1` — dual aggregation strategies

### Full Archive Inventory

`docs/blueprints/archive/README.md` contains a 90+ entry inventory table covering all archived blueprints from 2026-03-15 through 2026-03-21.

## 5. Test Baseline

- **234 tests, all green**
- Run command: `PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p "test_*.py"`
- Full regression verified after every blueprint implementation
- No flaky or skipped tests

## 6. Key Implementation Files

### Certainty Delivery Chain (new this session)

| File | Role |
|------|------|
| `src/factpy_kernel/core/annotation/_certainty.py` | `derive_certainty_summary`, `rank_certainty_conditions`, `CertaintySummary`, `ConditionImpact`, `RankedCondition`, dual aggregation |
| `src/factpy_kernel/core/annotation/__init__.py` | Public exports for annotation module |
| `src/factpy_kernel/core/store/_certainty_materializer.py` | Service-neutral certainty materialization |
| `src/factpy_kernel/core/store/_confidence_kind_resolver.py` | `RuleSpecReader`, `ConfidenceKindResolver`, `CertaintyConfidenceKindResolver`, shared eligibility |
| `src/factpy_kernel/core/store/_candidate_evidence_tree.py` | Tree builder with confidence carrier |
| `src/factpy_kernel/core/store/_candidate_evidence_tree_narrative.py` | Narrative with sorted `certainty_lines` + `certainty_bottleneck` |
| `src/factpy_kernel/core/store/_candidate_evidence_tree_nl.py` | NL with weakest-condition sentence |
| `src/factpy_kernel/service/_certainty_service.py` | Condition weights lookup + certainty computation |
| `src/factpy_kernel/service/runtime_v1.py` | Runtime explain orchestration (thin, certainty helpers extracted) |
| `src/factpy_kernel/adapters/souffle/package.py` | `export_package` with optional `certainty_summaries` |
| `src/factpy_kernel/audit/reader.py` | Reads `certainty_summaries.jsonl` |
| `src/factpy_kernel/audit/query.py` | `get_candidate_certainty_summary()` + narrative with certainty |
| `src/factpy_kernel/audit/static_ui.py` | Certainty section rendering |
| `examples/certainty_evidence_tree.ipynb` | End-to-end demo notebook with fact confidence + dual aggregation |

### Module Docs (implementation truth)

| File | Scope |
|------|-------|
| `src/factpy_kernel/core/docs/01_architecture.md` | Core architecture (CN, source of truth) |
| `src/factpy_kernel/core/docs/01_architecture.en.md` | Core architecture (EN, synced) |
| `src/factpy_kernel/core/annotation/docs/README.md` | Annotation prototype: certainty + ranking + aggregation |
| `src/factpy_kernel/service/docs/01_overview.md` | Service module overview |
| `src/factpy_kernel/service/docs/03_runtime_queries_views.md` | Runtime queries, views, export |
| `src/factpy_kernel/audit/docs/01_overview.md` | Audit package, query, static |

## 7. Frozen Contracts (DO NOT REOPEN)

All 8 frozen contracts from 2026-03-20 handoff §7 remain frozen, plus:

9. **CertaintySummary shape** — `confidence_kind`, `condition_count`, `weighted_condition_count`, `conditions`, `aggregate_certainty`, `aggregation`
10. **Certainty eligibility guard** — single structured `rule_ref_edge` + no nested `referenced_support`
11. **Export-time materialization** — `certainty_summaries.jsonl` in audit package; audit does not do query-time derivation
12. **Ranking in annotation layer** — `rank_certainty_conditions` is the single ranking source; narrative/NL only consume, never re-sort
13. **ConfidenceKindResolver protocol** — create-time routing via `ConfidenceKindResolver` + `RuleSpecReader`; no post-evaluation patching
14. **Fact-level confidence carrier** — `assertion_fact.confidence` → `predicate_witness_group.condition_confidence = max(children)`; tree is carrier only, no baked scoring
15. **Additive aggregation semantics** — `impact = (weight / Σweights) × confidence`, `aggregate = sum(impacts)`; `ConditionImpact.impact` semantics vary by strategy

## 8. Known Gaps / Risk Assessment

### 8.1 Chain / Recursive Certainty Propagation

**What exists**:
- Evidence tree recursively captures nested `referenced_support` nodes
- Each rule payload can have its own `condition_weights`
- `derive_certainty_summary` computation model is reusable per level

**What's missing**:
- Eligibility guard blocks nested `referenced_support` (returns `null`)
- No recursive aggregation: child rule's `aggregate_certainty` is not fed as parent's condition `confidence`
- No cycle detection for recursive certainty

**Key decision**: each level's `aggregate_certainty` becomes the parent's `condition_confidence` for that referenced_support edge. Implementable; deferred by design.

### 8.2 Probability Lane

**What exists**:
- `CONFIDENCE_KINDS` includes `"probability"`
- ProbLog adapter produces `confidence_kind="probability"` with `confidence: float`
- Service DTO round-trip works
- CandidateSet validation works

**What's missing**:
- No probability-specific summary derivation (annotation layer hard-guards `!= "certainty" → None`)
- No probability aggregation semantics defined
- No probability delivery surface (explain / narrative / NL / audit / static)

**Key scoping questions**:
1. Aggregation semantics: certainty uses bottleneck/additive; probability uses ___?
2. Per-condition model: reuse `condition_weights` or different metadata?
3. Cross-engine mapping: ProbLog `confidence: float` vs native `condition_weights`
4. Delivery surface: shared namespace or independent `probability_summary`?
5. Engine dependency: must be engine-agnostic (like certainty lane)

### 8.3 SDK Parity for Certainty Routing

**What exists**:
- `ConfidenceKindResolver` protocol is in core layer
- `Store.evaluate` accepts `confidence_kind_resolver` parameter
- SDKStore can pass resolver if it has a `RuleSpecReader`

**What's missing**:
- SDKStore does not have a built-in `RuleSpecReader` implementation
- SDK evaluate calls currently pass `None` (no resolver)
- SDK users cannot get `confidence_kind="certainty"` automatically

**Status**: Explicitly deferred. The seam exists; SDK just needs a reader implementation.

### 8.4 Certainty V1 Non-Goals (frozen, not accidental omissions)

These are explicitly deferred, not forgotten:
- chain / recursive certainty propagation
- rule-level certainty cap
- thresholded certainty gating
- additional aggregation strategies beyond `bottleneck` and `additive`
- additive parity in audit/static export
- SDK certainty auto-routing parity
- engine parity for certainty delivery outside native
- probability-specific explainability

## 9. Collaboration Protocol

1. **Blueprint-driven**: all non-trivial work starts with a blueprint: `draft → scoped → implementing → implemented → archived`
2. **Hook restriction**: PreToolUse hook blocks non-.md file edits in `src/factpy_kernel/`; agent provides code, user applies
3. **Scope discipline**: each blueprint covers exactly one capability line; deferred lines are not pulled in
4. **Contract-first**: freeze DTO / taxonomy / owner boundaries before multi-file implementation
5. **Docs sync is mandatory**: module docs must be updated before a blueprint is archived
6. **Single commit per coherent phase**: keep capability, implementation, and pure docs as separate commits; `.claude` changes committed separately
7. **Decision-only blueprints are valid**: freezing ownership/scope is a legitimate deliverable
8. **Archive inventory**: update `docs/blueprints/archive/README.md` when archiving blueprints

## 10. What the Next Agent Should Do

### Recommended first action

Run a full test suite regression:
```bash
PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p "test_*.py"
```
Expected: 234 tests, OK.

### Recommended next direction

Primary recommendation:

**Probability feasibility / scoping blueprint** (decision-freeze, not implementation).

Why this is the recommended next move:
- `certainty v1` is now frozen, so more certainty semantics work has lower immediate leverage
- the largest remaining asymmetry in the confidence system is `confidence_kind="probability"`
- the real open question is not scalar delivery, but whether probability can support an honest explain surface at all

This blueprint should answer:
1. What artifacts ProbLog actually produces today
2. Whether scalar probability v0 is independently valuable even without attribution
3. Which explain / attribution surfaces are blocked and must remain blocked
4. Whether any probability summary should share namespace with certainty or stay independent

Secondary future option:

**Chain/recursive certainty propagation** remains valid, but should be treated as a later `certainty v2` line rather than the default next step.

### What NOT to do

- Do not reopen any of the 15 frozen contracts (Section 7)
- Do not assume probability reuses certainty's bottleneck/additive aggregation
- Do not couple probability lane to ProbLog (must be engine-agnostic)
- Do not treat this handoff as implementation truth; module docs remain canonical
- Do not skip blueprint scoping for non-trivial work
- Do not reopen certainty semantics without first treating it as a contract change

## 11. Minimal Startup Reading List

For a new agent, read in this order:

1. **This handoff** (you're reading it)
2. **Module docs**:
   - `src/factpy_kernel/core/docs/01_architecture.md`
   - `src/factpy_kernel/core/annotation/docs/README.md`
   - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
   - `src/factpy_kernel/audit/docs/01_overview.md`
3. **Certainty implementation** (to understand the pattern):
   - `src/factpy_kernel/core/annotation/_certainty.py`
   - `src/factpy_kernel/core/store/_confidence_kind_resolver.py`
   - `src/factpy_kernel/core/store/_certainty_materializer.py`
   - `src/factpy_kernel/service/_certainty_service.py`
4. **Demo notebook**: `examples/certainty_evidence_tree.ipynb`
5. **Archive index**: `docs/blueprints/archive/README.md`

## 12. Suggested First Blueprint After This Handoff

If starting a new capability line immediately, prefer:

`probability-feasibility` (name tentative)

Target outcome:
- a scoped decision document, not implementation
- clear answer on whether `probability summary v0` has standalone product value
- explicit blocked surface list for probability attribution

Avoid turning this into a hidden implementation blueprint. The first deliverable should be a framing decision, not code.
