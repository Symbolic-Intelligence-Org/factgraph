# Session Handoff — 2026-03-30 (Session 2)

Supersedes: `docs/session_handoff_2026-03-30.md` (Session 1 — walkthrough/defect remediation)

---

## 1. Current Stage

This session delivered **three major capability lines** on top of the clean, audited baseline from Session 1:

1. **Examples reorganization** — 26 files → 11 files (7 numbered notebooks + README + 3 archive). Eliminated all .py/.ipynb duplication, each domain appears once, each adapter has representation. Added ProbLog notebook (previously missing).
2. **PyReason runtime explain** — New `CandidateProvenanceTimeline` contract with full timeline/summary/narrative/NL pipeline + audit export (`provenance_timelines.jsonl`).
3. **ProbLog CandidateEvidenceTree** — Extended `CandidateEvidenceTree` with `proof_goal`/`proof_leaf` node kinds + probability propagation through summary→narrative→NL.

**Current position:** Three engines all have complete runtime explain surfaces (code + behavioral tests). 636 tests green, 0 open defects. Two implementation blueprints at `implemented` status.

**Prior handoff:** `docs/session_handoff_2026-03-30.md` (Session 1) — HEAD `574cf5b`, 605 tests, 19/19 walkthrough findings closed.

---

## 2. Capability Baseline

### Core Store & Ledger

Append-only assertion ledger with SQLite backing, `set_field`/`retract_by_asrt`/`replace_field` (atomic via preflight validation). Candidate evaluation with deterministic `chosen` selection. Digest collision detection.

### Evidence Tree & Explain Pipeline

4-layer explain: raw tree → summary → narrative → NL. Node kinds now include:
- **witness-bearing**: `predicate_witness_group`, `assertion_fact` (native/souffle)
- **proof-bearing**: `proof_goal`, `proof_leaf` (ProbLog) — **NEW this session**
- structural/constraint/terminal/degraded (shared)

`problog_probability` flows through summary→narrative→NL for ProbLog candidates. `certainty_summary` flows for certainty-routed candidates.

### CandidateProvenanceTimeline (NEW)

PyReason-specific runtime explain contract. Chain-local propagation events with `root_chain_key` identification. Full timeline/summary/narrative/NL pipeline. Audit persistence via `provenance_timelines.jsonl`.

### Certainty Propagation (L1)

`CertaintyConfidenceKindResolver` for single rule-edge scenarios. Child artifact eligibility guard. All early-return paths annotated.

### EvidenceGraph Unified Explain

Frozen DTO with tree + timeline renderers. Converters for all three engines. Durable serialization. This is the **audit/static visualization layer**, not the runtime explain surface.

### PyReason Adapter

Bounded numeric extension, session batch API, thread-safe runner. `CandidateProvenanceTimeline` for runtime explain. `EvidenceGraph(timeline)` for audit.

### ProbLog Adapter

Full evaluation pipeline with proof trace capture. `CandidateEvidenceTree` with `proof_goal`/`proof_leaf` for runtime explain. `EvidenceGraph(tree)` for audit. Export priority chain preserved.

### Souffle Adapter

Witness-bearing provenance, `CandidateEvidenceTree` (original), proof tree conversion to EvidenceGraph.

### Annotation System

`shared/semantic/probability` as first-class write lane. Auto-derives confidence. Adapter-local annotation templates.

### Audit & Static UI

Durable artifact sidecar. Candidate evidence page with EvidenceGraph integration. `proof_goal`/`proof_leaf` rendered without assertion detail links. `provenance_timelines.jsonl` in audit package.

### Examples

7 numbered notebooks covering progressive learning path:
- 01: SDK basics — 02: Rules/derivations — 03: Certainty/evidence tree
- 04: ECSS+Souffle — 05: DORA+PyReason — 06: ProbLog — 07: Multi-engine architecture

### Helper Layering

| Module | Layer | Dependencies | Role |
|--------|-------|-------------|------|
| `core/store` | storage | sqlite3 | Ledger, Store, runtime indices |
| `core/evidence` | protocol | core/store | write_protocol, validation |
| `core/annotation` | domain | core/store | certainty, confidence |
| `adapters/pyreason` | adapter | core | Session, runner, accept, provenance, **timeline** |
| `adapters/problog` | adapter | core | Export, import, accept, provenance, **tree builder** |
| `adapters/souffle` | adapter | core | Witness, provenance, proof tree, **package export** |
| `audit` | presentation | core, adapters | EvidenceGraph, reader, query, static_ui |
| `service` | API | core, adapters | Runtime queries, views, **timeline+tree explain** |
| `sdk` | user-facing | core | SDKStore, schema, derivation |

---

## 3. Git State

- **Branch:** `master`
- **HEAD:** `f1ba1b7`
- **This session's commits (6):**

| Hash | Description |
|------|-------------|
| `26f03c5` | docs: archive 6 decision blueprints + add evidence-graph and dialog-agent blueprints |
| `bf56c15` | refactor: reorganize examples directory (26 → 11 files) |
| `a2fa21a` | feat: PyReason CandidateProvenanceTimeline with full explain pipeline |
| `ac24da9` | feat: ProbLog CandidateEvidenceTree with proof_goal/proof_leaf + probability pipeline |
| `8f2747c` | test: PyReason timeline explain family behavioral verification |
| `523b132` | docs: session handoff 2026-03-30 (session 2) |

---

## 4. Blueprint Status Summary

### Active Blueprints

| File | Status | Notes |
|------|--------|-------|
| `2026-03-22_architectural-decisions-v2.md` | landed | Design-phase decisions (reference) |
| `2026-03-28_evidence-graph-unified-explain.md` | landed | Parent blueprint for explain architecture |
| `2026-03-29_dialog-agent-blueprint-v1.md` | draft | Dialog agent — untouched this session |
| `2026-03-30_pyreason-runtime-explain-timeline.md` | **implemented** | PyReason timeline explain — full pipeline |
| `2026-03-30_problog-candidate-evidence-tree.md` | **implemented** | ProbLog tree explain — full pipeline |

### Key Archived Blueprints (This Session)

- 6 decision blueprints moved from `active/` to `archive/`: ecss-domain, assertion-annotation-store, engine-options, multi-engine-execution (x2), value-carrying-semantics

### Full Archive Inventory

`docs/blueprints/archive/README.md` — ~171 entries (165 prior + 6 newly archived decisions)

---

## 5. Test Baseline

- **Total:** 636 passed, 1 warning, 4 subtests passed
- **Command:** `PYTHONPATH=src python -m pytest src/factpy_kernel/tests/ -q`
- **Warning:** DeprecationWarning on `evaluate_dummy` (expected, non-blocking)
- **No flaky or skipped tests**

Tests added this session: +31 (from 605 → 636):
- `test_candidate_provenance_timeline.py` — 18 tests (timeline dataclass + builder + summary + narrative)
- `test_provenance_timeline_audit_delivery.py` — 3 tests (export round-trip)
- `test_problog_candidate_evidence_tree.py` — 3 tests (ProbLog tree builder + explain integration)
- `test_pyreason_timeline_explain_family.py` — 7 tests (full explain family behavioral verification)

---

## 6. Key Implementation Files

### New/Changed Files This Session

| File | Role |
|------|------|
| `core/store/_candidate_provenance_timeline.py` | **NEW** — Timeline dataclass, builder, summary, narrative, NL |
| `adapters/problog/provenance.py` | ProbLog → CandidateEvidenceTree builder |
| `core/store/_candidate_evidence_tree_summary.py` | +proof role, +problog_probability |
| `core/store/_candidate_evidence_tree_narrative.py` | +proof lines, +probability_lines |
| `core/store/_candidate_evidence_tree_nl.py` | +probability paragraph |
| `service/runtime_v1.py` | Timeline endpoints + ProbLog/PyReason explain dispatch |
| `service/app_v1.py` | 3 new HTTP routes (explain-timeline family) |
| `audit/reader.py` | +provenance_timelines optional key |
| `audit/query.py` | +get_candidate_provenance_timeline, +get_candidate_timeline_summary |
| `audit/static_ui.py` | proof_goal/proof_leaf rendering |
| `adapters/souffle/package.py` | +provenance_timelines.jsonl export |
| `examples/01-07_*.ipynb` | **NEW** — 7 reorganized notebooks |

### Module Docs (Implementation Truth)

| File | Scope |
|------|-------|
| `core/docs/01_architecture.md` | Core store, node_kind taxonomy (updated: +proof_goal/proof_leaf), summary contract |
| `adapters/docs/02_problog_adapter.md` | ProbLog pipeline, CandidateEvidenceTree support |
| `adapters/docs/03_pyreason_adapter.md` | PyReason session, runner, timeline explain |
| `service/docs/03_runtime_queries_views.md` | Runtime queries including timeline + ProbLog explain |
| `audit/docs/02_evidence_graph.md` | EvidenceGraph DTO, renderers, converters |
| `core/annotation/docs/README.md` | Annotation system, certainty propagation |

---

## 7. Frozen Contracts

Prior contracts 1–67 remain frozen. This session adds:

68. **`CandidateProvenanceTimeline` contract** — `chains` sorted by `(component_type, component, label)` lexicographic; `root_chain_key` tuple identifier
69. **Timeline narrative chain-local only** — does NOT infer cross-chain causality from `groundings`
70. **`proof_goal` / `proof_leaf` node kinds** — role `"proof"`, not `"witness"`; `proof_leaf` does NOT carry `asrt_id`
71. **`problog_probability` in summary** — read from root `engine_meta.probability`; absent when not ProbLog
72. **`probability_lines` in narrative** — optional, symmetric with `certainty_lines`; absent when not ProbLog
73. **`explain_runtime_nl` PyReason dispatch** — `PYREASON_PROVENANCE_KIND` only (not `_PROVENANCE_BEARING_SUPPORT_KINDS`), avoids ProbLog misroute
74. **`provenance_timelines.jsonl` audit package** — row format `{candidate_id, provenance_timeline}`, PyReason candidates only
75. **Three-layer explain architecture** — engine-native provenance (L1) → runtime contract (L2: tree OR timeline) → EvidenceGraph (L3: audit/static)
76. **Runtime explain surface mapping** — native/souffle/problog → `CandidateEvidenceTree`; pyreason → `CandidateProvenanceTimeline`

**Total: 76 frozen contracts.** Do NOT reopen without explicit user approval.

---

## 8. Known Gaps

### Cross-fact causal edges (P3, deferred)
- PyReason converter only builds intra-fact `EDGE_UPDATES`
- Cross-fact causality edges deferred; narrative is chain-local by contract

### Recursive certainty propagation L2 (P3, deferred)
- L1 covers single rule-edge
- Multi-rule chain propagation deferred; nested child support degrades to `null`

### Fact-level confidence in evidence tree (P3, known gap)
- `write_protocol` writes meta confidence
- `_runtime_assertion_detail_for_tree()` skips all meta; tree nodes lack confidence field

### Pre-accept candidate payload not reconstructable (P2, structural)
- Live explain (tree/timeline) only works for accepted candidates
- Payload reconstructed from ledger claims; pre-accept candidates have no persistent payload index
- Affects both ProbLog tree and PyReason timeline paths

### SDK lacks runtime explain surface (P3, gap)
- SDK has `sdk.evaluate()/accept()/export_package()` but no `sdk.explain_tree()/explain_summary()/explain_nl()`
- Runtime explain only accessible through `service/runtime_v1.py` functions
- Examples 03/04 work around this via audit package path

### EvidenceGraph summary/NL (P4, nice-to-have)
- Demoted from gap: all three engines now have runtime explain surfaces
- Audit/static already has HTML rendering; text summary for EvidenceGraph is additive

**0 open defects. All items above are scope-deferred or structural limitations.**

---

## 9. Collaboration Protocol

1. **Blueprint-driven workflow** — one blueprint per task, draft → scoped → implementing → implemented → archived
2. **Hook restriction** — non-`.md` edits in `src/factpy_kernel/` (except `tests/`) blocked by pre-commit hook; provide code for user to apply
3. **Scope discipline** — each blueprint does ONE thing; no scope creep
4. **Contract-first** — freeze decisions before implementation
5. **Docs sync** — update module docs at implementation close
6. **Commit conventions** — `fix:` / `feat:` / `docs:` prefixes; `Co-Authored-By` trailer
7. **Decision-only blueprints** — design phase decisions stay in `active/` as reference
8. **Archive inventory** — maintain `docs/blueprints/archive/README.md` with sequential numbering
9. **Semantic boundaries** — probability/bound/active_from are fact semantic properties, not engine parameters; engine_ext = definition-time, engine_options = call-time
10. **Three-layer explain** — engine-native provenance → runtime contract (tree OR timeline) → EvidenceGraph (audit/static)
11. **Runtime explain is engine-appropriate** — do not force all engines into one contract shape

---

## 10. What the Next Agent Should Do

### First action

```bash
PYTHONPATH=src python -m pytest src/factpy_kernel/tests/ -q
```
Expected: **636 passed**, 1 warning, 4 subtests passed. HEAD: `f1ba1b7`.

### Recommended next direction

The codebase has complete runtime explain surfaces for all three engines. Natural next directions (in order of impact):

1. **Pre-accept candidate payload index (#7 P2)** — enables live explain before accept; unblocks interactive decision workflows
2. **SDK explain surface (#8 P3)** — expose explain-tree/summary/narrative/NL through SDK, eliminating service-layer dependency in examples
3. **Domain-specific demo expansion** — ECSS/DORA with real Souffle + PyReason evaluation
4. **Production hardening** — error surface, logging, metrics, API layer

### What NOT to do

- Do not reopen any of 76 frozen contracts
- Do not force PyReason into `CandidateEvidenceTree` — it uses `CandidateProvenanceTimeline`
- Do not put engine-specific params in shared `meta_rows`
- Do not serialize `engine_ext` into `to_authoring_payload()`
- Do not use `meta.confidence` for ProbLog probability input (use `meta.probability`)
- Do not manually construct `EvidenceGraph` in user-facing code
- Do not write `probability=0.0` to the ledger (use `retract` instead)
- Do not remove the `_PYREASON_LOCK` or `try/finally` cleanup in `runner.py`
- Do not infer cross-chain causality from PyReason `clause_groundings` in narrative
- Do not use `_PROVENANCE_BEARING_SUPPORT_KINDS` for PyReason-specific dispatch (use `PYREASON_PROVENANCE_KIND`)

---

## 11. Minimal Startup Reading List

1. **This handoff** (`docs/session_handoff_2026-03-30.md`)
2. `src/factpy_kernel/core/docs/01_architecture.md` — core store, node_kind taxonomy, summary contract
3. `src/factpy_kernel/service/docs/03_runtime_queries_views.md` — runtime explain endpoints (tree + timeline)
4. `src/factpy_kernel/adapters/docs/02_problog_adapter.md` — ProbLog pipeline + CandidateEvidenceTree
5. `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md` — PyReason pipeline + CandidateProvenanceTimeline
6. `src/factpy_kernel/core/annotation/docs/README.md` — annotation system, certainty
7. `src/factpy_kernel/audit/docs/02_evidence_graph.md` — EvidenceGraph (audit layer)
8. `docs/blueprints/active/2026-03-30_pyreason-runtime-explain-timeline.md` — PyReason explain design decisions
9. `docs/blueprints/active/2026-03-30_problog-candidate-evidence-tree.md` — ProbLog explain design decisions
10. `examples/07_evidence_graph_multi_engine.ipynb` — three-layer explain architecture overview
11. `docs/blueprints/archive/README.md` — full archive inventory
