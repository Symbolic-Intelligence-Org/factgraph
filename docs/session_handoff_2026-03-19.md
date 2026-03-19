# Session Handoff: 2026-03-19 (Updated)

This document enables a new agent to resume work with full context. It supersedes all prior handoff documents. It is a session restart reference, not a substitute for active blueprints, archived blueprints, or module docs.

## 1. Current Stage

The project has progressed well beyond evidence tree v2. Five major implementation rounds have landed on the native candidate-proof line since the earlier handoff refresh:

1. **RuleRef execution substrate** (commit `a8e1b5d`) - unified native RuleRef execution for query and derivation
2. **Recursive proof edges** (commit `f4756d9`) - structured `rule_ref_edges` on `SupportArtifact`, recursive child support expansion in evidence tree
3. **Winning-branch narrowing** (commit `13b7827`) - native support capture now narrows to a single adopted OR branch
4. **Richer unresolved taxonomy** (commit `f649c5d`) - recursive proof unresolved/boundary reasons are now a formal shared contract
5. **Engine degraded tree shape** (commit `cf7f56d`) - engine candidates now return a valid degraded explain-tree instead of unsupported

Current position: **native candidate proof is implemented through recursive proof + winning-branch narrowing + unresolved taxonomy, and engine degraded candidates now have a legal tree surface**.

## 2. Capability Baseline

### 2.1 Explain / Audit Delivery Spine (stable)

- raw explain, summary, narrative, NL explain, audit/static proof-entry
- This is baseline infrastructure, not active work.

### 2.2 Candidate Evidence Tree V1 + V2 (archived)

- V1: candidate-centric tree entry, runtime/audit/static delivery
- V2: sectioned tree (`support_section` + `rule_ref_section`), node-kind-aware rendering
- Both archived. Current tree is significantly richer than V2.

### 2.3 RuleRef Execution Substrate (implemented)

Blueprint: `2026-03-19_native-where-ruleref-execution-substrate.md` (status: implemented)

- Shared `ruleref_substrate.evaluate_native_where(...)` used by both query and derivation paths
- `RuleRegistry` injection: SDK uses explicit registry, service uses `override_registry_root` / `registry_root` / `session.registry_root`
- `NativeWhereEvaluation` returns `bindings + rule_refs + rule_ref_resolutions`
- `ruleref_common.py` provides shared resolution helpers
- `where_eval.py` still has `allow_ruleref=False` (legacy guard); substrate bypasses it

Key files:
- `src/factpy_kernel/core/rules/ruleref_substrate.py`
- `src/factpy_kernel/core/rules/ruleref_common.py`
- `src/factpy_kernel/core/rules/ruleref_types.py`
- `src/factpy_kernel/core/store/_evaluate.py`
- `src/factpy_kernel/sdk/store.py`

### 2.4 Recursive Proof Semantics (implemented)

Blueprint: `2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md` (status: implemented)

#### Core DTOs

**`NativeRuleRefRowSupport`** (in `ruleref_types.py`):
- `row_terms: tuple[Any, ...]`
- `child_support_digest: str | None`
- `unresolved_reason: str | None`
- Must have exactly one of `child_support_digest` or `unresolved_reason`

**`NativeRuleRefResolution`** (in `ruleref_types.py`):
- `ruleref_atom_key: str` (e.g., `b0.a1:ruleref`)
- `rule_ref_id: str`
- `rule_ref_version: str`
- `row_supports: tuple[NativeRuleRefRowSupport, ...]`

**`RuleRefEdge`** (in `_support.py`):
- `ruleref_atom_key: str`
- `rule_ref_id: str`
- `rule_ref_version: str`
- `child_support_digest: str | None`
- `unresolved_reason: str | None`

**`SupportArtifact`** (in `_support.py`) now has:
- `rule_ref_edges: tuple[RuleRefEdge, ...] = ()` alongside legacy `rule_refs: tuple[str, ...] = ()`
- `root_result_kind` accepts `"row"` for child rule support artifacts

#### Capture Layer

`_support_capture.py` (new module) provides:
- `build_support_artifact_for_binding(...)` - builds SupportArtifact with structured edges
- `derive_rule_ref_edges_for_binding(...)` - implements exact tuple match rule:
  - Grounds ruleref terms from binding
  - Matches against `row_supports` by exact `row_terms` equality
  - 0 matches = skip (no edge emitted)
  - 1 match = emit edge
  - >1 matches = `WhereValidationError` (contract violation)
- `unresolved_reason` on capture side: only `"child_support_unavailable"` in first-round

#### Tree Expansion

`_candidate_evidence_tree.py` now supports:
- Recursive child support expansion via `support_lookup` callback
- Cycle detection via `ancestry: set[str]` (support digest set)
- Depth limit: `_MAX_RECURSION_DEPTH = 8`
- New tree node kinds:
  - `referenced_support` - resolved child proof subtree
  - `unresolved_support` - proof data missing (reason: `artifact_missing`, `child_support_unavailable`)
  - `recursion_boundary` - traversal stopped (reason: `cycle`, `depth_limit`)
- Falls back to legacy `rule_refs` flat rendering when `rule_ref_edges` is empty

#### Consumer Updates

- `runtime_v1.py`: `_explain_tree_candidate()` passes `support_lookup=session.store.explain_support`
- `audit/query.py`: `get_candidate_evidence_tree()` passes `support_lookup=self._get_support_artifact`
- `audit/static_ui.py`: renders `referenced_support`, `unresolved_support`, `recursion_boundary` node kinds

### 2.5 Winning-Branch Semantics + Narrowing (implemented)

Blueprints:
- `2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md`
- `2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md`

- Native support capture now adopts exactly one satisfying OR branch per binding.
- Selection happens in `_support_capture.py`, not in tree readback.
- Tie rule is `source-order wins`.
- No non-winning shadow metadata is retained in first-round artifacts.
- Selected branch identity remains recoverable from existing `b{branch}.a{atom}` keys; no new top-level branch field was introduced.

### 2.6 Richer Unresolved Taxonomy (implemented)

Blueprint: `2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.md`

- First-round recursive proof taxonomy now formally freezes four reasons:
  - `child_support_unavailable`
  - `artifact_missing`
  - `cycle`
  - `depth_limit`
- `unresolved_support` and `recursion_boundary` stay split:
  - unresolved = wanted child proof but could not obtain it
  - boundary = traversal stopped intentionally
- Owner split is explicit:
  - capture owns `child_support_unavailable`
  - lookup/readback owns `artifact_missing`
  - traversal owns `cycle` / `depth_limit`
- Runtime, audit, and static share the same raw enum surface.

### 2.7 Engine Degraded Tree Shape (implemented)

Blueprint: `2026-03-19_engine-candidate-explain-tree-degraded-node-shape.md`

- Engine candidates with `support_kind in {"engine_no_witness_v1", "none"}` no longer return `runtime_explain_not_supported` on the tree surface.
- First-round engine degraded tree shape is:
  - `candidate_result`
  - `support_section`
  - `degraded_support`
- `degraded_support` is its own node kind and does not reuse native recursive proof terminals.
- `engine_no_witness_v1` and legacy `"none"` are tree-isomorphic, differing only in the raw `support_kind` value.

## 3. Git State

- Branch: `master`
- Latest landed commits on this line:
  - `a8e1b5d` - unify native RuleRef execution
  - `f4756d9` - recursive proof edges
  - `13b7827` - winning-branch narrowing
  - `f649c5d` - richer unresolved taxonomy contract
  - `cf7f56d` - engine degraded tree shape
- Working tree state is not a stable truth source; inspect `git status` at session start.
- Remote: ahead of `origin/master` by multiple commits (not pushed)

**Known issue**: Git `index.lock` files sometimes appear spuriously. If a git operation fails with "Unable to create index.lock", run `rm -f .git/index.lock` and retry immediately.

## 4. Blueprint Status Summary

### Active Blueprints

| Blueprint | Status | Notes |
| --- | --- | --- |
| `2026-03-15_overall-system-blueprint.md` | draft | Top-level system blueprint |
| `2026-03-16_temporal-hybrid-reasoning-blueprint.md` | draft | Temporal reasoning |
| `2026-03-17_durable-artifact-storage.md` | scoped | Storage layer |
| `2026-03-17_runtime-traceability-explainability-blueprint.md` | draft | Parent blueprint for evidence tree line |

### Key Archived Blueprints (evidence tree lineage)

- `2026-03-18_runtime-traceability-evidence-tree-realignment.md` - why evidence tree belongs to the plan
- `2026-03-18_native-candidate-evidence-tree-v1.md` - V1 shape
- `2026-03-19_native-candidate-evidence-tree-v2.md` - V2 sectioned tree
- `2026-03-19_native-derivation-ruleref-execution-decision.md` - decision to unify RuleRef execution
- `2026-03-19_native-where-ruleref-execution-substrate.md` - shared RuleRef substrate
- `2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md` - recursive proof edges
- `2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md` - winning-branch contract
- `2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md` - winning-branch implementation
- `2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.md` - recursive proof taxonomy contract
- `2026-03-19_engine-candidate-explain-tree-degraded-node-shape.md` - engine degraded tree contract

## 5. Test Baseline

- Test file: `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Test count: **85 tests** (`def test_` count)
- Test file size: ~8925 lines
- Run command: `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1`
- **Note**: Full suite was NOT run after the recursive proof implementation. Only targeted tests were executed and passed during development.

Key recursive-proof-specific tests:
- `test_query_ruleref_object_dependency_auto_registers` - SDK query with RuleRef(RuleObj)
- `test_query_ruleref_string_requires_explicit_registry` - string RuleRef without registry fails fast
- `test_derivation_ruleref_object_dependency_auto_registers_and_captures_rule_refs` - SDK derivation with RuleRef, verifies `rule_ref_edges`
- `test_runtime_derivation_ruleref_uses_session_registry_root` - service-level with FileAuthoringRegistry
- `test_recursive_candidate_evidence_tree_round_trips_through_audit_and_static` - full round-trip runtime -> explain tree -> accept -> audit -> static
- `test_runtime_tree_renders_unresolved_rule_ref_edge_terminal_node` - unresolved_support terminal
- `test_rule_ref_edge_derivation_skips_zero_match_rows` - 0-match -> no edge
- `test_rule_ref_edge_derivation_fails_fast_on_duplicate_row_support_match` - >1 match -> error

## 6. Key Implementation Files

### Core (proof substrate)

| File | Role |
| --- | --- |
| `src/factpy_kernel/core/rules/ruleref_substrate.py` | Shared native where evaluation with RuleRef support |
| `src/factpy_kernel/core/rules/ruleref_common.py` | Shared resolution helpers |
| `src/factpy_kernel/core/rules/ruleref_types.py` | `NativeRuleRefRowSupport`, `NativeRuleRefResolution` DTOs |
| `src/factpy_kernel/core/store/_support.py` | `RuleRefEdge`, `SupportArtifact`, `BindingSupportCapture` |
| `src/factpy_kernel/core/store/_support_capture.py` | `build_support_artifact_for_binding`, `derive_rule_ref_edges_for_binding` |
| `src/factpy_kernel/core/store/_evaluate.py` | `evaluate_store`, `_evaluate_where_over_view_with_support` |
| `src/factpy_kernel/core/store/_candidate_evidence_tree.py` | Recursive tree builder with cycle/depth guards |

### Consumers

| File | Role |
| --- | --- |
| `src/factpy_kernel/service/runtime_v1.py` | Runtime service: `_explain_tree_candidate()`, derivation evaluate |
| `src/factpy_kernel/audit/query.py` | Audit query: `get_candidate_evidence_tree()` |
| `src/factpy_kernel/audit/static_ui.py` | Static site rendering for all tree node kinds |
| `src/factpy_kernel/sdk/store.py` | SDK surface: `RuleRegistry` injection |

### Module Docs (implementation truth)

| File | Scope |
| --- | --- |
| `src/factpy_kernel/core/docs/01_architecture.md` | Core architecture |
| `src/factpy_kernel/service/docs/03_runtime_queries_views.md` | Runtime service queries/views |
| `src/factpy_kernel/audit/docs/01_overview.md` | Audit package overview |

## 7. Deferred Gaps

### 7.1 Scenario-driven deferred gaps (still no trigger)

- `T2 sequence/state semantics`
- judgment / obligation contract
- `U2` weak-signal uncertainty
- snippet/span provenance
- extraction uncertainty
- source-linkage contract

Rule: no concrete trigger = no capability blueprint.

### 7.2 Evidence-tree-adjacent deferred lines

After recursive proof, winning-branch narrowing, richer taxonomy, and engine degraded tree shape, the natural next candidates are:

1. **Provenance / source taxonomy** - decide whether tree nodes need a formal `source_kind` / `provenance_kind` contract
2. **Engine witness parity** - go beyond degraded tree shape toward richer non-native explain surfaces
3. **Proof graph / graph UI** - promote tree to graph-oriented evidence surface
4. **Annotation / value semantics / salience** - contribution / impact annotations on tree nodes
5. **Finer provenance** - snippet/span level source positioning

## 8. Collaboration Protocol

The established working protocol between user and agent is:

1. **Blueprint-driven**: all non-trivial work starts with a blueprint that goes through `draft -> scoped -> implementing -> implemented -> archived`
2. **Scope discipline**: each blueprint opens exactly one capability line; deferred lines are not pulled in
3. **Contract-first**: freeze DTO / taxonomy / owner boundaries before multi-file implementation
4. **Docs sync is mandatory**: module docs must be updated before a blueprint is archived
5. **Testing principle**: if a blueprint says X is load-bearing, targeted tests should assert it
6. **Single commit per coherent phase**: keep capability, implementation, and pure docs promotions as separate commits when possible

## 9. What the Next Agent Should Do

### If user opens provenance / source taxonomy discussion

Open a new narrow capability blueprint. Keep it focused on the tree-surface contract:

1. Which node kinds need a formal source/provenance taxonomy?
2. Whether native recursive nodes and engine degraded nodes share the same vocabulary
3. Whether provenance is a carrier contract or only a display contract
4. How to avoid reopening the already-frozen unresolved taxonomy or winning-branch contracts

### If user opens broader engine witness parity discussion

Keep it narrower than full adapter parity at first. The already-landed degraded tree shape should be treated as the current baseline, not thrown away.

### What NOT to do

- Do not reopen recursive proof DTOs
- Do not reopen RuleRef execution substrate
- Do not reopen winning-branch or unresolved taxonomy unless there is a concrete regression
- Do not run full test suite unless asked
- Do not treat `docs/session_handoff_2026-03-19.md` as implementation truth; module docs remain canonical

## 10. Minimal Startup Reading List

For a new agent, read in this order:

1. **This handoff** (you're reading it)
2. **Archived 2026-03-19 evidence-tree lineage blueprints**:
   - `docs/blueprints/archive/2026-03-19_native-where-ruleref-execution-substrate.md`
   - `docs/blueprints/archive/2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md`
   - `docs/blueprints/archive/2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md`
   - `docs/blueprints/archive/2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md`
   - `docs/blueprints/archive/2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.md`
   - `docs/blueprints/archive/2026-03-19_engine-candidate-explain-tree-degraded-node-shape.md`
3. **Still-active parent blueprints**:
   - `docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md`
   - `docs/blueprints/active/2026-03-17_durable-artifact-storage.md`
4. **Key implementation files** (current truth):
   - `src/factpy_kernel/core/store/_support_capture.py` - capture layer
   - `src/factpy_kernel/core/store/_support.py` - DTOs
   - `src/factpy_kernel/core/store/_candidate_evidence_tree.py` - tree builder
   - `src/factpy_kernel/core/rules/ruleref_substrate.py` - execution substrate
5. **Module docs**:
   - `src/factpy_kernel/core/docs/01_architecture.md`
   - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
   - `src/factpy_kernel/audit/docs/01_overview.md`

Then wait for user direction on whether to proceed with provenance/source taxonomy, engine witness parity, or another deferred line.
