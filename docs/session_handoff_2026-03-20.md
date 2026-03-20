# Session Handoff: 2026-03-20

This document enables a new agent to resume work with full context. It supersedes all prior handoff documents (`session_handoff_2026-03-18.md`, `docs/session_handoff_2026-03-19.md`). It is a session restart reference, not a substitute for active blueprints, archived blueprints, or module docs.

## 1. Current Stage

The candidate evidence tree surface is now **feature-complete for first-round scope**. Six major implementation rounds have landed on the native candidate-proof line:

1. **RuleRef execution substrate** (`a8e1b5d`) - unified native RuleRef execution for query and derivation
2. **Recursive proof edges** (`f4756d9`) - structured `rule_ref_edges` on `SupportArtifact`, recursive child support expansion in evidence tree
3. **Winning-branch narrowing** (`13b7827`) - native support capture now narrows to a single adopted OR branch
4. **Richer unresolved taxonomy** (`f649c5d`) - four terminal reasons, two node kinds, three owner layers, formally documented as shared contract
5. **Engine degraded tree shape** (`cf7f56d`) - engine candidates return valid degraded tree instead of `runtime_explain_not_supported`
6. **Blueprint archive housekeeping** (`874d256`) - all completed blueprints archived, handoff links refreshed

Current position: **all first-round candidate explain-tree capability lines are closed**. The tree surface covers native recursive proof, winning-branch narrowing, unresolved/boundary taxonomy, and engine degraded candidates. No active implementation work is in flight.

## 2. Capability Baseline

### 2.1 Explain / Audit Delivery Spine (stable, not active work)

- raw explain, summary, narrative, NL explain, audit/static proof-entry
- This is baseline infrastructure.

### 2.2 Candidate Evidence Tree V1 + V2 (archived)

- V1: candidate-centric tree entry, runtime/audit/static delivery
- V2: sectioned tree (`support_section` + `rule_ref_section`), node-kind-aware rendering
- Both archived. Current tree is significantly richer.

### 2.3 RuleRef Execution Substrate (implemented, archived)

Blueprint: `2026-03-19_native-where-ruleref-execution-substrate.md`

- Shared `ruleref_substrate.evaluate_native_where(...)` used by both query and derivation
- `RuleRegistry` injection: SDK uses explicit registry, service uses `override_registry_root` / `registry_root`
- `NativeWhereEvaluation` returns `bindings + rule_refs + rule_ref_resolutions`

Key files:
- `src/factpy_kernel/core/rules/ruleref_substrate.py`
- `src/factpy_kernel/core/rules/ruleref_common.py`
- `src/factpy_kernel/core/rules/ruleref_types.py`

### 2.4 Recursive Proof Semantics (implemented, archived)

Blueprint: `2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md`

Core DTOs:
- **`NativeRuleRefRowSupport`** (`ruleref_types.py`): `row_terms`, `child_support_digest | unresolved_reason` (exactly one)
- **`NativeRuleRefResolution`** (`ruleref_types.py`): `ruleref_atom_key`, `rule_ref_id`, `rule_ref_version`, `row_supports`
- **`RuleRefEdge`** (`_support.py`): `ruleref_atom_key`, `rule_ref_id`, `rule_ref_version`, `child_support_digest | unresolved_reason`
- **`SupportArtifact`** (`_support.py`): now has `rule_ref_edges` alongside legacy `rule_refs`

Capture layer (`_support_capture.py`):
- `build_support_artifact_for_binding(...)` - builds SupportArtifact with structured edges
- `derive_rule_ref_edges_for_binding(...)` - exact tuple match rule (0 match = skip, 1 = emit, >1 = error)
- Only capture-side unresolved reason: `"child_support_unavailable"`

Tree expansion (`_candidate_evidence_tree.py`):
- Recursive child support expansion via `support_lookup` callback
- Cycle detection via `ancestry: set[str]` (support digest set)
- Depth limit: `_MAX_RECURSION_DEPTH = 8`
- Node kinds: `referenced_support`, `unresolved_support`, `recursion_boundary`
- Falls back to legacy `rule_refs` flat rendering when `rule_ref_edges` is empty

### 2.5 Winning-Branch Narrowing (implemented, archived)

Blueprints: `*-winning-branch-semantics.md`, `*-winning-branch-narrowing.md`

- Native support capture adopts exactly one satisfying OR branch per binding
- Selection in `_support_capture.py`, not in tree readback
- Tie rule: `source-order wins`
- No non-winning shadow metadata retained in first-round
- Branch identity recoverable from existing `b{branch}.a{atom}` keys

### 2.6 Richer Unresolved Taxonomy (implemented, archived)

Blueprint: `2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.md`

Four terminal reasons, frozen:
| Reason | Owner | Node Kind |
|---|---|---|
| `child_support_unavailable` | capture | `unresolved_support` |
| `artifact_missing` | lookup/readback | `unresolved_support` |
| `cycle` | traversal | `recursion_boundary` |
| `depth_limit` | traversal | `recursion_boundary` |

- `unresolved_support` vs `recursion_boundary` stays split: wanted-but-failed vs intentional-stop
- Runtime / audit / static share same raw enum surface, no consumer-specific translation
- Only applies to structured `rule_ref_edges` path; legacy `rule_refs` produces flat `rule_ref` nodes only

### 2.7 Engine Degraded Tree Shape (implemented, archived)

Blueprint: `2026-03-19_engine-candidate-explain-tree-degraded-node-shape.md`

- `support_kind in {"engine_no_witness_v1", "none"}` → valid degraded tree (not `runtime_explain_not_supported`)
- Fixed shape: `candidate_result → support_section → degraded_support`
- `degraded_support` is a dedicated node kind; does NOT reuse native recursive terminals
- Minimal fields: `node_kind`, `support_kind`, `witness_status="degraded"`, `children=[]`
- No `support_digest` on `degraded_support` node; zero digest is top-level envelope compatibility only
- `engine_no_witness_v1` and `"none"` are tree-surface isomorphic
- `_DEGRADED_SUPPORT_KINDS = {"none", "engine_no_witness_v1"}` in `_support.py`

## 3. Git State

- Branch: `master`
- Commits on evidence-tree line (chronological):
  - `a8e1b5d` - unify native RuleRef execution
  - `f4756d9` - recursive proof edges
  - `13b7827` - winning-branch narrowing
  - `f649c5d` - richer unresolved taxonomy contract
  - `cf7f56d` - engine degraded tree shape
  - `874d256` - archive completed blueprints, refresh handoff links
- Remote: ahead of `origin/master` by multiple commits (not pushed)
- Working tree: clean except for 2 untracked files:
  - `docs/blueprints/active/2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md` (status: draft)
  - `docs/blueprints/active/2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.audit.md`

**Known issue**: Git `index.lock` files sometimes appear spuriously. If a git operation fails with "Unable to create index.lock", run `rm -f .git/index.lock` and retry.

## 4. Blueprint Status Summary

### Active Blueprints

| Blueprint | Status | Notes |
| --- | --- | --- |
| `2026-03-15_overall-system-blueprint.md` | draft | Top-level system blueprint |
| `2026-03-16_temporal-hybrid-reasoning-blueprint.md` | draft | Temporal reasoning |
| `2026-03-17_durable-artifact-storage.md` | scoped | Storage layer |
| `2026-03-17_runtime-traceability-explainability-blueprint.md` | draft | Parent blueprint for evidence tree line |
| `2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md` | **draft** | Next candidate line; opened but not yet scoped |

### Key Archived Blueprints (evidence tree lineage, in order)

1. `2026-03-18_runtime-traceability-evidence-tree-realignment.md` - why evidence tree belongs to the plan
2. `2026-03-18_native-candidate-evidence-tree-v1.md` - V1 shape
3. `2026-03-19_native-candidate-evidence-tree-v2.md` - V2 sectioned tree
4. `2026-03-19_native-derivation-ruleref-execution-decision.md` - decision to unify RuleRef execution
5. `2026-03-19_native-where-ruleref-execution-substrate.md` - shared RuleRef substrate
6. `2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md` - recursive proof edges
7. `2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md` - winning-branch contract
8. `2026-03-19_native-candidate-evidence-tree-winning-branch-narrowing.md` - winning-branch implementation
9. `2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.md` - recursive proof taxonomy
10. `2026-03-19_engine-candidate-explain-tree-degraded-node-shape.md` - engine degraded tree

## 5. Complete Tree Node Kind Taxonomy

This is the current full set of node kinds on the `candidate_evidence_tree` surface:

### Native Recursive Proof Path (requires `support_kind="native_binding_v1"`)

| Node Kind | Parent | Description |
|---|---|---|
| `candidate_result` | root | Top-level candidate node |
| `support_section` | `candidate_result` | Groups support-derived children |
| `rule_ref_section` | `candidate_result` | Groups rule-ref-derived children (optional) |
| `predicate_witness_group` | `support_section` | Witness bindings per predicate |
| `non_fact_check` | `support_section` | Non-fact-check items |
| `assertion_fact` | `predicate_witness_group` | Individual assertion references |
| `rule_ref` | `rule_ref_section` | Legacy flat rule_ref (no recursive proof) |
| `referenced_support` | `rule_ref_section` | Resolved recursive child proof subtree |
| `unresolved_support` | `rule_ref_section` | Wanted child proof but failed (`child_support_unavailable`, `artifact_missing`) |
| `recursion_boundary` | `rule_ref_section` | Traversal intentionally stopped (`cycle`, `depth_limit`) |

### Engine Degraded Path (requires `support_kind in _DEGRADED_SUPPORT_KINDS`)

| Node Kind | Parent | Description |
|---|---|---|
| `candidate_result` | root | Top-level candidate node (same shape, `root_result_kind=None`) |
| `support_section` | `candidate_result` | Contains single degraded child |
| `degraded_support` | `support_section` | Engine candidate with no witness artifact |

## 6. Test Baseline

- Test file: `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
- Run command: `PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1`
- **Note**: Full suite was NOT run after the latest implementation rounds. Only targeted tests were executed and passed.

Key tests for the evidence tree line:
- `test_query_ruleref_object_dependency_auto_registers` - SDK query with RuleRef(RuleObj)
- `test_query_ruleref_string_requires_explicit_registry` - string RuleRef without registry fails fast
- `test_derivation_ruleref_object_dependency_auto_registers_and_captures_rule_refs` - SDK derivation with RuleRef
- `test_runtime_derivation_ruleref_uses_session_registry_root` - service-level with FileAuthoringRegistry
- `test_recursive_candidate_evidence_tree_round_trips_through_audit_and_static` - full native round-trip
- `test_runtime_tree_renders_unresolved_rule_ref_edge_terminal_node` - unresolved_support terminal
- `test_rule_ref_edge_derivation_skips_zero_match_rows` - 0-match → no edge
- `test_rule_ref_edge_derivation_fails_fast_on_duplicate_row_support_match` - >1 match → error
- `test_engine_candidate_evidence_tree_round_trips_through_audit_and_static` - engine degraded full round-trip (runtime → audit → static)

## 7. Key Implementation Files

### Core (proof substrate)

| File | Role |
| --- | --- |
| `src/factpy_kernel/core/rules/ruleref_substrate.py` | Shared native where evaluation with RuleRef support |
| `src/factpy_kernel/core/rules/ruleref_common.py` | Shared resolution helpers |
| `src/factpy_kernel/core/rules/ruleref_types.py` | `NativeRuleRefRowSupport`, `NativeRuleRefResolution` DTOs |
| `src/factpy_kernel/core/store/_support.py` | `RuleRefEdge`, `SupportArtifact`, `BindingSupportCapture`, `_DEGRADED_SUPPORT_KINDS` |
| `src/factpy_kernel/core/store/_support_capture.py` | `build_support_artifact_for_binding`, `derive_rule_ref_edges_for_binding` |
| `src/factpy_kernel/core/store/_evaluate.py` | `evaluate_store`, `_evaluate_where_over_view_with_support` |
| `src/factpy_kernel/core/store/_candidate_evidence_tree.py` | Native recursive tree builder + `build_degraded_candidate_evidence_tree` |

### Consumers

| File | Role |
| --- | --- |
| `src/factpy_kernel/service/runtime_v1.py` | Runtime service: `_explain_tree_candidate()` — routes native vs degraded |
| `src/factpy_kernel/audit/query.py` | Audit query: `get_candidate_evidence_tree()` — routes native vs degraded |
| `src/factpy_kernel/audit/static_ui.py` | Static site rendering for all tree node kinds including `degraded_support` |
| `src/factpy_kernel/sdk/store.py` | SDK surface: `RuleRegistry` injection |

### Module Docs (implementation truth)

| File | Scope |
| --- | --- |
| `src/factpy_kernel/core/docs/01_architecture.md` | Core architecture, tree taxonomy contract, degraded tree contract |
| `src/factpy_kernel/service/docs/03_runtime_queries_views.md` | Runtime service queries/views, tree shape, unresolved taxonomy, degraded contract |
| `src/factpy_kernel/audit/docs/01_overview.md` | Audit package overview, shared taxonomy, degraded tree audit contract |

## 8. Frozen Contracts (DO NOT REOPEN)

These contracts are formally frozen and documented in module docs. Do not reopen without a concrete regression or new requirement trigger:

1. **Recursive proof DTO** — `RuleRefEdge`, `NativeRuleRefRowSupport`, `NativeRuleRefResolution`, `SupportArtifact.rule_ref_edges`
2. **RuleRef execution substrate** — `ruleref_substrate.evaluate_native_where()`, registry injection model
3. **Winning-branch narrowing** — source-order-wins, single adopted branch, capture-side selection
4. **Unresolved/boundary taxonomy** — four reasons, two node kinds, three owner layers, shared raw enum
5. **Engine degraded tree shape** — `degraded_support` node kind, minimal fields, no `support_digest` on node, `"none"` ≡ `engine_no_witness_v1` on tree surface

## 9. Deferred Gaps

### 9.1 Scenario-driven deferred gaps (still no trigger)

- `T2 sequence/state semantics`
- judgment / obligation contract
- `U2` weak-signal uncertainty
- snippet/span provenance
- extraction uncertainty
- source-linkage contract

Rule: no concrete trigger = no capability blueprint.

### 9.2 Evidence-tree-adjacent deferred lines (ordered by readiness)

1. **Provenance / source taxonomy** — blueprint already drafted (`active/2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md`, status: draft). Asks whether tree nodes need formal `source_kind` / `provenance_kind` fields beyond the current implicit `node_kind + support_kind + witness_status` combination. This is the **most natural next step**.
2. **Engine witness parity** — go beyond degraded tree shape toward richer non-native explain surfaces. Current degraded tree is the baseline, not to be discarded.
3. **Proof graph / graph UI** — promote tree to graph-oriented evidence surface
4. **Annotation / value semantics / salience** — contribution / impact annotations on tree nodes
5. **Finer provenance** — snippet/span level source positioning

## 10. Collaboration Protocol

The established working protocol between user and agent:

1. **Blueprint-driven**: all non-trivial work starts with a blueprint: `draft → scoped → implementing → implemented → archived`
2. **Scope discipline**: each blueprint covers exactly one capability line; deferred lines are not pulled in
3. **Role split**: user implements code; agent reviews, advises, and validates. Agent never creates or modifies code files without explicit instruction.
4. **Contract-first**: freeze DTO / taxonomy / owner boundaries before multi-file implementation
5. **Docs sync is mandatory**: module docs must be updated before a blueprint is marked `implemented` and archived
6. **Testing principle**: if a blueprint says X is load-bearing, targeted tests should assert it
7. **Single commit per coherent phase**: keep capability, implementation, and pure docs promotions as separate commits when possible
8. **Git commits only on explicit request**: agent does not commit without user asking
9. **Doc-and-contract promotion pattern**: when existing code already matches a scoped contract, the blueprint can go directly from `scoped` to `implemented` with only doc updates (no implementation blueprint needed)

## 11. What the Next Agent Should Do

### Default: wait for user direction

All first-round evidence-tree lines are closed. No active implementation work. Wait for the user to indicate what to work on next.

### If user opens provenance / source taxonomy discussion

The blueprint is already drafted at `docs/blueprints/active/2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md`. Continue from there:

1. Review the 5 freeze questions in the blueprint's "Proposed Shape" section
2. Do NOT reopen unresolved taxonomy, winning-branch, or degraded tree shape
3. Determine if this is a carrier contract (fields on tree nodes) or display-only contract (consumer rendering layer)
4. Keep scope narrow: this is about naming/taxonomy, not about graph UI or snippet/span provenance

### If user opens engine witness parity discussion

The degraded tree shape is the established baseline. Build on it, don't discard it. Keep the first slice narrow — full adapter parity is too broad for a single blueprint.

### If user wants to run full test suite

```bash
PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1
```

Note: full suite has not been run after the latest rounds. Targeted tests passed, but full regression is recommended before pushing.

### What NOT to do

- Do not reopen any of the 5 frozen contracts (Section 8)
- Do not run full test suite unless asked
- Do not treat handoff documents as implementation truth; module docs are canonical
- Do not push to remote unless user explicitly asks
- Do not commit without user's explicit request

## 12. Minimal Startup Reading List

For a new agent, read in this order:

1. **This handoff** (you're reading it)
2. **Active provenance/source taxonomy blueprint** (if continuing that line):
   - `docs/blueprints/active/2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md`
3. **Module docs** (implementation truth):
   - `src/factpy_kernel/core/docs/01_architecture.md`
   - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
   - `src/factpy_kernel/audit/docs/01_overview.md`
4. **Key implementation files** (current truth):
   - `src/factpy_kernel/core/store/_candidate_evidence_tree.py` — tree builder
   - `src/factpy_kernel/core/store/_support.py` — DTOs
   - `src/factpy_kernel/core/store/_support_capture.py` — capture layer
   - `src/factpy_kernel/core/rules/ruleref_substrate.py` — execution substrate
5. **Archived blueprints** (for historical context only, not for implementation decisions):
   - `docs/blueprints/archive/2026-03-19_*.md` — the full evidence-tree lineage
6. **Parent blueprints** (still active, provide strategic context):
   - `docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md`
   - `docs/blueprints/active/2026-03-17_durable-artifact-storage.md`

Then wait for user direction.
