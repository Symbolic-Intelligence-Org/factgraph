# Session Handoff: 2026-03-21

This document enables a new agent to resume work with full context. It supersedes the 2026-03-20 handoff. It is a session restart reference, not a substitute for active blueprints, archived blueprints, or module docs.

## 1. Current Stage

Building on the 2026-03-20 baseline (evidence tree NL explain + Souffle partial witness + live permalinks + salience/impact ownership freeze), this session landed the **certainty delivery chain** end-to-end and began **salience/ranking** delivery:

1. **Candidate confidence-kind + rule condition-weight metadata** (`9147008`) — `confidence_kind` on CandidateSet, `condition_weights` on rule payloads, SDK/authoring/service plumbing
2. **Certainty annotation prototype** (`4ce084d`) — `derive_certainty_summary` with bottleneck aggregation, `CertaintySummary` / `ConditionImpact` dataclasses
3. **Certainty explain delivery** (`6f5473c`) — runtime explain-summary / narrative / NL with additive certainty surfaces
4. **Test decomposition** (`c2b061f`) — 10,372-line monolith → 7 focused test files + shared helpers
5. **Certainty audit + static delivery** (`62a6c2a`) — export-time materialization into `certainty_summaries.jsonl`, AuditQuery, static site rendering
6. **Architecture docs sync** (`f62061e`) — CN/EN architecture docs + module docs aligned
7. **Certainty runtime boundary cleanup** (`f0fd28a`) — helper extraction to `_certainty_service.py`, archive inventory table
8. **Certainty salience ranking v1** (`defd56a`) — `rank_certainty_conditions` with bottleneck marking, narrative sorted output, NL weakest-condition sentence

Current position: **certainty lane is complete from annotation through salience ranking**. The next capability direction is **probability lane scoping** (decision freeze, not implementation).

## 2. Capability Baseline

### 2.1 Certainty Delivery Chain (new this session, stable)

Full pipeline:

```
confidence_kind="certainty" + condition_weights (rule metadata)
  → derive_certainty_summary (annotation, bottleneck = min weighted impact)
  → CertaintySummary { conditions, aggregate_certainty }
  → rank_certainty_conditions (annotation, impact ascending, bottleneck marked)
  → explain-summary: response-level certainty_summary sibling
  → explain-narrative: additive certainty_lines (sorted, [bottleneck] tagged)
                        + certainty_bottleneck (machine-readable)
  → explain-nl: certainty paragraph + weakest-condition sentence
  → export: certainty_summaries.jsonl (export-time materialization)
  → audit: AuditQuery.get_candidate_certainty_summary()
  → audit narrative: certainty_lines with ranking
  → static site: certainty section in candidate evidence page
```

Key design decisions:
- **Eligibility guard**: single structured `rule_ref_edge` + no nested `referenced_support`; multi-rule/nested/unresolved degrade to `certainty_summary=null`
- **Three-state lookup**: `_lookup_condition_weights_for_candidate` returns `None` (ineligible) | `{}` (no weights) | `{k:v}` (has weights)
- **Export-time materialization**: `condition_weights` only exist in `FileAuthoringRegistry` filesystem; audit cannot derive at query-time
- **Additive delivery**: `certainty_lines` / `certainty_bottleneck` are optional keys; base narrative/NL unaffected
- **NL consumes structured data**: `certainty_bottleneck` key (not presentation string parsing)
- **Ranking in annotation layer**: `rank_certainty_conditions` is a pure function; narrative/NL only consume its output

### 2.2 Confidence Kind Infrastructure (new this session, stable)

- `CONFIDENCE_KINDS = frozenset({"none", "probability", "certainty"})` — frozen
- `CandidateSet.confidence_kind: str = "none"` — validated at creation
- Native / Souffle deterministic → `"none"`
- ProbLog adapter → `"probability"`
- Certainty lane consumers → `"certainty"` (requires authoring rule with `condition_weights`)
- `Store.get_candidate_confidence_kind(candidate_id)` — public accessor
- `Store.list_candidate_ids()` — enumeration for export-time batch

### 2.3 Test Decomposition (new this session, stable)

Original monolith `test_phase3_contracts_v1.py` (10,372 lines) split into:

| File | Focus | Tests |
|------|-------|-------|
| `test_certainty_explain_contracts.py` | Certainty + explain + audit round-trip | ~20 |
| `test_evidence_tree_explain_contracts.py` | Evidence tree + rule trace | 15 |
| `test_domain_walkthrough_contracts.py` | Domain walkthroughs | 11 |
| `test_ecss_compliance_contracts.py` | ECSS VCD/temporal | 11 |
| `test_winning_branch_rule_trace_contracts.py` | Winning branch + rule trace | 10 |
| `test_artifact_sidecar_contracts.py` | Artifact sidecar + audit package | 11 |
| `test_phase3_contracts_v1.py` (residual) | Core entity/schema/query/derivation | 28 |
| `_test_helpers.py` | Shared fixtures | — |

### 2.4 Evidence Tree + Traceability (from prior sessions, still stable)

Unchanged from 2026-03-20 handoff §2.1–§2.4. All 8 frozen contracts remain frozen.

### 2.5 Helper Layering (cleaned up this session)

| Module | Layer | Dependencies | Role |
|--------|-------|-------------|------|
| `annotation/_certainty.py` | core | core only | `derive_certainty_summary`, `rank_certainty_conditions`, dataclasses |
| `store/_certainty_materializer.py` | core | core only | `materialize_certainty_summary`, tree eligibility, serialization |
| `service/_certainty_service.py` | service | core + authoring | `_lookup_condition_weights_for_candidate`, `_compute_certainty_summary_from_tree`, `_compute_all_certainty_summaries` |
| `adapters/souffle/package.py` | adapters | core only | `export_package(..., *, certainty_summaries)` pure writer |
| `audit/reader.py` | audit | core | `AuditPackageData.certainty_summaries` |
| `audit/query.py` | audit | core | `get_candidate_certainty_summary()`, narrative with certainty |

Import graph verified clean: no core→authoring, no adapters→service, no audit→service.

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

## 4. Blueprint Status Summary

### Active Blueprints

| Blueprint | Status | Notes |
|-----------|--------|-------|
| `2026-03-15_overall-system-blueprint.md` | draft | Top-level system blueprint |
| `2026-03-16_temporal-hybrid-reasoning-blueprint.md` | draft | Temporal reasoning |
| `2026-03-17_runtime-traceability-explainability-blueprint.md` | draft | Parent blueprint for evidence tree line |

### Key Archived Blueprints (this session, 2026-03-21)

- `certainty-summary-explain-delivery` — runtime explain endpoints with certainty
- `certainty-aware-narrative-nl-delivery` — narrative/NL additive certainty
- `certainty-audit-static-delivery` — export-time materialization
- `phase3-test-decomposition` — 10K-line monolith split
- `certainty-runtime-boundary-cleanup` — helper extraction + archive index
- `certainty-salience-ranking-v1` — impact ranking + bottleneck marking

### Archived From Prior Sessions (certainty infrastructure, 2026-03-20)

- `candidate-confidence-kind` — confidence_kind enum on CandidateSet
- `rule-condition-weight-metadata` — condition_weights in rule payloads
- `certainty-weight-vocabulary` — certainty vocabulary definition
- `certainty-propagation-prototype` — derive_certainty_summary implementation

### Full Archive Inventory

`docs/blueprints/archive/README.md` contains a 86-entry inventory table covering all archived blueprints from 2026-03-15 through 2026-03-21.

## 5. Test Baseline

- **222 tests, all green**
- Run command: `PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p "test_*.py"`
- Full regression verified after every blueprint implementation

## 6. Key Implementation Files

### Certainty Delivery Chain (new this session)

| File | Role |
|------|------|
| `src/factpy_kernel/core/annotation/_certainty.py` | `derive_certainty_summary`, `rank_certainty_conditions`, `CertaintySummary`, `ConditionImpact`, `RankedCondition` |
| `src/factpy_kernel/core/annotation/__init__.py` | Public exports for annotation module |
| `src/factpy_kernel/core/store/_certainty_materializer.py` | Service-neutral certainty materialization |
| `src/factpy_kernel/core/store/_candidate_evidence_tree_narrative.py` | Narrative with sorted `certainty_lines` + `certainty_bottleneck` |
| `src/factpy_kernel/core/store/_candidate_evidence_tree_nl.py` | NL with weakest-condition sentence |
| `src/factpy_kernel/service/_certainty_service.py` | Condition weights lookup + certainty computation |
| `src/factpy_kernel/service/runtime_v1.py` | Runtime explain orchestration (thin, certainty helpers extracted) |
| `src/factpy_kernel/adapters/souffle/package.py` | `export_package` with optional `certainty_summaries` |
| `src/factpy_kernel/audit/reader.py` | Reads `certainty_summaries.jsonl` |
| `src/factpy_kernel/audit/query.py` | `get_candidate_certainty_summary()` + narrative with certainty |
| `src/factpy_kernel/audit/static_ui.py` | Certainty section rendering |

### Module Docs (implementation truth)

| File | Scope |
|------|-------|
| `src/factpy_kernel/core/docs/01_architecture.md` | Core architecture (CN, source of truth) |
| `src/factpy_kernel/core/docs/01_architecture.en.md` | Core architecture (EN, synced) |
| `src/factpy_kernel/core/annotation/docs/README.md` | Annotation prototype: certainty + ranking |
| `src/factpy_kernel/service/docs/01_overview.md` | Service module overview |
| `src/factpy_kernel/service/docs/03_runtime_queries_views.md` | Runtime queries, views, export |
| `src/factpy_kernel/audit/docs/01_overview.md` | Audit package, query, static |

## 7. Frozen Contracts (DO NOT REOPEN)

All 8 frozen contracts from 2026-03-20 handoff §7 remain frozen, plus:

9. **CertaintySummary shape** — `confidence_kind`, `condition_count`, `weighted_condition_count`, `conditions: tuple[ConditionImpact, ...]`, `aggregate_certainty`
10. **Certainty eligibility guard** — single structured `rule_ref_edge` + no nested `referenced_support`
11. **Export-time materialization** — `certainty_summaries.jsonl` in audit package; audit does not do query-time derivation
12. **Ranking in annotation layer** — `rank_certainty_conditions` is the single ranking source; narrative/NL only consume, never re-sort

## 8. Probability Lane Gap Analysis

### What exists

- `CONFIDENCE_KINDS` includes `"probability"`
- ProbLog adapter produces `confidence_kind="probability"` with `confidence: float`
- Service DTO round-trip works
- CandidateSet validation works

### What's missing

- No probability-specific summary derivation (annotation layer hard-guards `!= "certainty" → None`)
- No probability aggregation semantics defined (bottleneck? product? weighted average?)
- No probability-specific `condition_weights` consumption model
- No probability delivery surface (explain / narrative / NL / audit / static)
- No tests for probability explain chain

### Key scoping questions (for next blueprint)

1. **Aggregation semantics**: certainty uses bottleneck (min); probability uses ___?
2. **Per-condition model**: reuse `condition_weights` or different metadata?
3. **Cross-engine mapping**: ProbLog `confidence: float` vs native `condition_weights` — how do they relate?
4. **Delivery surface**: shared `confidence_summary` namespace or independent `probability_summary`?
5. **Engine dependency**: probability lane must be engine-agnostic (like certainty lane)

## 9. Collaboration Protocol

1. **Blueprint-driven**: all non-trivial work starts with a blueprint: `draft → scoped → implementing → implemented → archived`
2. **Hook restriction**: PreToolUse hook blocks non-.md file edits in `src/factpy_kernel/`; agent provides code, user applies
3. **Scope discipline**: each blueprint covers exactly one capability line; deferred lines are not pulled in
4. **Contract-first**: freeze DTO / taxonomy / owner boundaries before multi-file implementation
5. **Docs sync is mandatory**: module docs must be updated before a blueprint is archived
6. **Single commit per coherent phase**: keep capability, implementation, and pure docs as separate commits
7. **Decision-only blueprints are valid**: freezing ownership/scope is a legitimate deliverable
8. **Archive inventory**: update `docs/blueprints/archive/README.md` when archiving blueprints

## 10. What the Next Agent Should Do

### Recommended first action

Run a full test suite regression:
```bash
PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p "test_*.py"
```
Expected: 222 tests, OK.

### Recommended next direction

**Open a probability lane scoping blueprint**. The certainty lane is complete; the structural asymmetry (certainty has full pipeline, probability has none) is the biggest remaining gap.

This should be a **decision-freeze blueprint** (like the 2026-03-20 `candidate-evidence-tree-salience-impact`), answering:
1. Aggregation semantics
2. Per-condition model
3. Cross-engine mapping
4. Delivery surface naming
5. Whether first-round produces implementation or just contract freeze

### If user opens probability lane scoping

Key files to read first:
- `src/factpy_kernel/core/annotation/_certainty.py` — certainty pattern to mirror
- `src/factpy_kernel/adapters/problog/problog_import.py` — ProbLog confidence source
- `src/factpy_kernel/core/derivation/candidates.py` — `CONFIDENCE_KINDS`
- `docs/references/external/rainbird-evidence-chain-compare.md` — probability vs certainty semantics

### What NOT to do

- Do not reopen any of the 12 frozen contracts (Section 7)
- Do not assume probability reuses certainty's bottleneck aggregation
- Do not couple probability lane to ProbLog (must be engine-agnostic)
- Do not treat this handoff as implementation truth; module docs remain canonical

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
   - `src/factpy_kernel/core/store/_certainty_materializer.py`
   - `src/factpy_kernel/service/_certainty_service.py`
4. **Archive index**: `docs/blueprints/archive/README.md`
5. **Active blueprints**: `docs/blueprints/active/`

Then wait for user direction.
