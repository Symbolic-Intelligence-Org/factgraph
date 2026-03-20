# Session Handoff: 2026-03-20 (Updated)

This document enables a new agent to resume work with full context. It supersedes all prior handoff documents. It is a session restart reference, not a substitute for active blueprints, archived blueprints, or module docs.

## 1. Current Stage

Building on the 2026-03-19 baseline (recursive proof + winning-branch + unresolved taxonomy + engine degraded tree), this session landed six additional capability lines across the traceability-explainability surface:

1. **Provenance-role taxonomy** (`729362f`, doc-only) — `node_kind` formally promoted to carrier-level provenance-role taxonomy; deeper assertion-origin taxonomy deferred
2. **Candidate evidence tree NL explain** (`9560fd2`) — pure summary, narrative, and NL helpers for candidate evidence trees across runtime/audit/static
3. **Salience / impact ownership freeze** (`69d45d9`, doc-only) — annotation/value-semantics layer, query-time derived, blocked on certainty/weight vocabulary
4. **Souffle partial witness** (`0157c57`) — adapter rule rewriting produces `SupportArtifact(kind=souffle_witness_v1)` with real pred witnesses
5. **Engine witness audit/static parity** (`18bcd2c`) — audit query gate accepts `_WITNESS_BEARING_SUPPORT_KINDS`; souffle_witness_v1 flows through audit/DTO/static
6. **Live evidence URL** (`9eb6f8b`) — session-bound GET permalink routes returning HTML for candidate evidence tree and rule trace detail

Current position: **the traceability-explainability mother blueprint's actionable lines are substantially closed**. Remaining open directions all have significant prerequisites or wider scope.

## 2. Capability Baseline

### 2.1 Explain / Audit Delivery Spine (stable)

- raw explain, summary, narrative, NL explain, audit/static proof-entry
- Candidate evidence tree now has its own summary/narrative/NL chain (parallel to rule_run)
- Live HTML permalinks available for candidate and rule-trace objects

### 2.2 Candidate Evidence Tree (stable, all rounds closed)

Full lineage from V1 through current state:
- V1: candidate-centric tree entry
- V2: sectioned tree (`support_section` + `rule_ref_section`)
- Recursive proof edges with cycle/depth guards
- Winning-branch narrowing (source-order wins)
- Richer unresolved taxonomy (4 formal reasons)
- Engine degraded tree shape
- Provenance-role taxonomy (node_kind as carrier contract)
- NL explain chain (summary → narrative → NL)

### 2.3 Engine Witness Parity (Souffle partial, ProbLog deferred)

- Souffle adapter generates `_w` witness-variant view rules via rule rewriting
- Query compilation supports witness-aware column layout with stable `pred_atom_key` mapping
- Adapter aggregates TSV rows into `SupportArtifact(kind=souffle_witness_v1)` with real `PredWitness` entries
- Runtime, audit query, audit DTO, and static pages all accept `souffle_witness_v1`
- ProbLog continues on degraded path (`engine_no_witness_v1`)
- `_WITNESS_BEARING_SUPPORT_KINDS = {"native_binding_v1", "souffle_witness_v1"}`
- `_DEGRADED_SUPPORT_KINDS = {"none", "engine_no_witness_v1"}`

### 2.4 Live Evidence Permalinks (implemented)

- `GET /v1/runtime/sessions/{session_id}/evidence/candidate/{candidate_id}` → HTML
- `GET /v1/runtime/sessions/{session_id}/evidence/rule-trace/{rule_run_id}` → HTML
- Session-bound, ephemeral — not durable permalinks
- Reuses static_ui page renderers with runtime-side data helpers
- Static audit export remains the durable proof-entry surface

### 2.5 Frozen Decision-Only Lines

| Line | Decision | Commit |
| --- | --- | --- |
| Provenance-role taxonomy | `node_kind` is the carrier-level taxonomy; no new `source_kind` field | `729362f` |
| Salience / impact | Annotation layer, query-time derived, blocked on certainty/weight | `69d45d9` |

## 3. Git State

- Branch: `master`
- All commits pushed to `origin/master` — remote is up to date
- This session's commits (chronological):
  - `9560fd2` - candidate evidence tree NL explain
  - `729362f` - worktree cleanup + provenance blueprint archive
  - `69d45d9` - salience/impact ownership freeze
  - `c64a2e3` - engine partial witness blueprint scoped
  - `0157c57` - Souffle partial witness via adapter rule rewriting
  - `18bcd2c` - audit/static surface accepts souffle_witness_v1
  - `1ae7d12` - live evidence URL blueprint scoped
  - `9eb6f8b` - session-bound live evidence permalink GET routes

**Known issue**: Git `index.lock` files sometimes appear spuriously. If a git operation fails with "Unable to create index.lock", run `rm -f .git/index.lock` and retry.

## 4. Blueprint Status Summary

### Active Blueprints

| Blueprint | Status | Notes |
| --- | --- | --- |
| `2026-03-15_overall-system-blueprint.md` | draft | Top-level system blueprint |
| `2026-03-16_temporal-hybrid-reasoning-blueprint.md` | draft | Temporal reasoning |
| `2026-03-17_durable-artifact-storage.md` | scoped | Storage layer |
| `2026-03-17_runtime-traceability-explainability-blueprint.md` | draft | Parent blueprint for evidence tree line |

### Key Archived Blueprints (this session, 2026-03-20)

- `2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md` — node_kind as provenance-role taxonomy
- `2026-03-20_candidate-evidence-tree-nl-explain.md` — summary/narrative/NL for candidate evidence trees
- `2026-03-20_candidate-evidence-tree-salience-impact.md` — salience ownership freeze (blocked)
- `2026-03-20_engine-partial-witness-adapter-contract.md` — Souffle partial witness via adapter rewriting
- `2026-03-20_engine-partial-witness-audit-static-surface.md` — audit/static parity for souffle_witness_v1
- `2026-03-20_live-evidence-url-runtime-permalink.md` — session-bound live evidence permalinks

### Prior Archived Blueprints (evidence tree lineage, 2026-03-19)

1. `2026-03-18_runtime-traceability-evidence-tree-realignment.md`
2. `2026-03-18_native-candidate-evidence-tree-v1.md`
3. `2026-03-19_native-candidate-evidence-tree-v2.md`
4. `2026-03-19_native-derivation-ruleref-execution-decision.md`
5. `2026-03-19_native-where-ruleref-execution-substrate.md`
6. `2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md`
7. `2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md`
8. `2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md`
9. `2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.md`
10. `2026-03-19_engine-candidate-explain-tree-degraded-node-shape.md`

## 5. Test Baseline

- Primary test file: `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Additional Souffle witness test files:
  - `src/factpy_kernel/tests/test_souffle_partial_witness_v1.py`
  - `src/factpy_kernel/tests/test_souffle_witness_view_gen_v1.py`
  - `src/factpy_kernel/tests/test_souffle_witness_where_compile_v1.py`
- Run command: `PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p "test_*.py"`
- **Note**: Full suite was NOT run after this session's implementation rounds. Only targeted tests were executed during development. A full regression run is recommended before starting new capability lines.

## 6. Key Implementation Files

### Core (NL explain chain — new this session)

| File | Role |
| --- | --- |
| `src/factpy_kernel/core/store/_candidate_evidence_tree_summary.py` | Pure tree → summary helper |
| `src/factpy_kernel/core/store/_candidate_evidence_tree_narrative.py` | Summary → narrative renderer |
| `src/factpy_kernel/core/store/_candidate_evidence_tree_nl.py` | Summary + narrative → NL explain |

### Souffle Adapter (partial witness — new this session)

| File | Role |
| --- | --- |
| `src/factpy_kernel/adapters/souffle/souffle_view_gen.py` | `_w` witness-variant view rules |
| `src/factpy_kernel/adapters/souffle/where_compile.py` | Witness-aware query compilation |
| `src/factpy_kernel/adapters/souffle/engine_eval.py` | TSV → SupportArtifact(souffle_witness_v1) |

### Service (live permalinks — new this session)

| File | Role |
| --- | --- |
| `src/factpy_kernel/service/app_v1.py` | GET route registration |
| `src/factpy_kernel/service/runtime_v1.py` | Permalink handlers + runtime explain helpers |

### Core (proof substrate — from prior sessions, still canonical)

| File | Role |
| --- | --- |
| `src/factpy_kernel/core/store/_support.py` | DTOs, support kind constants |
| `src/factpy_kernel/core/store/_candidate_evidence_tree.py` | Recursive tree builder |
| `src/factpy_kernel/core/store/_support_capture.py` | Support capture layer |
| `src/factpy_kernel/core/rules/ruleref_substrate.py` | Shared native where evaluation |

### Module Docs (implementation truth)

| File | Scope |
| --- | --- |
| `src/factpy_kernel/core/docs/01_architecture.md` | Core architecture, tree taxonomy, provenance-role contract |
| `src/factpy_kernel/service/docs/03_runtime_queries_views.md` | Runtime queries/views, live permalinks |
| `src/factpy_kernel/audit/docs/01_overview.md` | Audit package, shared taxonomy |
| `src/factpy_kernel/adapters/docs/01_souffle_adapter.md` | Souffle adapter, witness variant |

## 7. Frozen Contracts (DO NOT REOPEN)

1. **Recursive proof DTO** — `RuleRefEdge`, `NativeRuleRefRowSupport`, `NativeRuleRefResolution`, `SupportArtifact.rule_ref_edges`
2. **RuleRef execution substrate** — `ruleref_substrate.evaluate_native_where()`, registry injection model
3. **Winning-branch narrowing** — source-order-wins, single adopted branch, capture-side selection
4. **Unresolved/boundary taxonomy** — four reasons, two node kinds, three owner layers, shared raw enum
5. **Engine degraded tree shape** — `degraded_support` node kind, minimal fields
6. **Provenance-role taxonomy** — `node_kind` is the carrier-level source taxonomy; 6 categories (structural/witness/constraint/rule_chain/terminal/degraded)
7. **Souffle adapter contract** — `_w` witness variant rules, TSV column layout, `souffle_witness_v1` support kind
8. **NL explain chain** — candidate tree summary (12 core fields) → narrative → NL; delivery matrix: runtime full, audit summary+narrative, static narrative block

## 8. Remaining Open Directions

### 8.1 Mother blueprint (traceability-explainability) remaining lines

| Direction | Status | Blocker |
| --- | --- | --- |
| Assertion-origin taxonomy | deferred | Requires assertion provenance metadata from assertion_lookup |
| ProbLog witness parity | deferred | Widest scope — would reopen adapter/library integration |
| Missing optional conditions | deferred | Depends on authoring/rule IR optional semantics |
| Salience / impact | blocked | Requires certainty/weight vocabulary (not yet designed) |

### 8.2 Suggested priority for next session

1. **Assertion-origin taxonomy** — if assertion provenance metadata becomes available
2. **ProbLog witness parity** — scope widest but follows Souffle pattern
3. **Missing optional conditions** — depends on authoring
4. **Salience / impact** — continues blocked until certainty/weight

### 8.3 Scenario-driven deferred gaps (still no trigger)

- `T2 sequence/state semantics`
- judgment / obligation contract
- `U2` weak-signal uncertainty
- snippet/span provenance
- extraction uncertainty
- source-linkage contract

Rule: no concrete trigger = no capability blueprint.

## 9. Collaboration Protocol

1. **Blueprint-driven**: all non-trivial work starts with a blueprint: `draft → scoped → implementing → implemented → archived`
2. **Scope discipline**: each blueprint covers exactly one capability line; deferred lines are not pulled in
3. **Contract-first**: freeze DTO / taxonomy / owner boundaries before multi-file implementation
4. **Docs sync is mandatory**: module docs must be updated before a blueprint is archived
5. **Testing principle**: if a blueprint says X is load-bearing, targeted tests should assert it
6. **Single commit per coherent phase**: keep capability, implementation, and pure docs promotions as separate commits when possible
7. **Decision-only blueprints are valid**: not every blueprint produces code; freezing ownership/scope is a legitimate deliverable

## 10. What the Next Agent Should Do

### Recommended first action

Run a full test suite regression before starting any new capability line:
```bash
PYTHONPATH=src python -m unittest discover -s src/factpy_kernel/tests -p "test_*.py"
```

### If user opens assertion-origin taxonomy

This extends provenance beyond `node_kind` roles. Key questions:
1. What assertion provenance metadata does `assertion_lookup` need to return?
2. Is `assertion_source` a field on `assertion_fact` tree nodes, or on the assertion detail itself?
3. What are the origin categories (direct_write, derivation_accept, import)?

### If user opens ProbLog witness parity

Follow the Souffle pattern but expect wider scope:
1. ProbLog proof tree API differs from Souffle TSV
2. May require ProbLog-specific adapter contract
3. Keep `problog_witness_v1` as distinct support_kind

### What NOT to do

- Do not reopen any of the 8 frozen contracts (Section 7)
- Do not run full test suite unless asked (but recommend it at session start)
- Do not treat this handoff as implementation truth; module docs remain canonical

## 11. Minimal Startup Reading List

For a new agent, read in this order:

1. **This handoff** (you're reading it)
2. **Mother blueprint**: `docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md`
3. **This session's archived blueprints** (`docs/blueprints/archive/2026-03-20_*`)
4. **Key implementation files**:
   - `src/factpy_kernel/core/store/_support.py` — DTOs and support kind constants
   - `src/factpy_kernel/core/store/_candidate_evidence_tree.py` — tree builder
   - `src/factpy_kernel/adapters/souffle/engine_eval.py` — Souffle witness adapter
   - `src/factpy_kernel/service/runtime_v1.py` — runtime explain + permalink handlers
5. **Module docs**:
   - `src/factpy_kernel/core/docs/01_architecture.md`
   - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
   - `src/factpy_kernel/audit/docs/01_overview.md`
   - `src/factpy_kernel/adapters/docs/01_souffle_adapter.md`

Then wait for user direction.
