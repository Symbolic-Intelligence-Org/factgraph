# Session Handoff: 2026-03-19 (Updated)

This document enables a new agent to resume work with full context. It supersedes all prior handoff documents. It is a session restart reference, not a substitute for active blueprints, archived blueprints, or module docs.

## 1. Current Stage

The project has progressed well beyond evidence tree v2. Three major implementation rounds have landed since the last handoff:

1. **RuleRef execution substrate** (commit `a8e1b5d`) - unified native RuleRef execution for query and derivation
2. **Recursive proof edges** (commit `f4756d9`) - structured `rule_ref_edges` on `SupportArtifact`, recursive child support expansion in evidence tree
3. **Winning-branch semantics blueprint** (draft, untracked) - capability decision opened but not yet scoped

Current position: **recursive proof semantics are implemented; winning-branch semantics are the next open decision**.

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

### 2.5 Winning-Branch Semantics (draft - CURRENT OPEN QUESTION)

Blueprint: `2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md` (status: **draft**, untracked/uncommitted)

This is a **capability decision** blueprint, not an implementation blueprint. It asks:

- Should each native support artifact only express one "winning" OR branch, or continue conservative full-branch capture?
- If winning-branch semantics are adopted, at which layer should branch selection happen?
  - `where_eval` / substrate
  - `_support_capture`
  - `_builders` candidate merge
  - tree readback
- What is the minimal identity for a winning branch? (`branch_index`, branch-local key namespace, etc.)
- How to handle ties when multiple branches satisfy the same final binding?

**Current state**: The user wrote the draft and stated: "the next step is to discuss the freeze of section 5 questions." This discussion has NOT yet started. The agent responded "ready when you are" and the session ended.

**Key constraint**: This blueprint explicitly does NOT reopen execution substrate DTOs or recursive proof DTOs. It also does NOT introduce multi-support candidates or branch-set carriers.

## 3. Git State

- Branch: `master`
- Latest commit: `f4756d9` (recursive proof edges)
- Working tree: clean except for 2 untracked files:
  - `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md`
  - `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.audit.md`
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
| `2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md` | implemented | Recursive proof edges |
| `2026-03-19_native-derivation-ruleref-execution-decision.md` | implemented | Decision to unify RuleRef execution |
| `2026-03-19_native-where-ruleref-execution-substrate.md` | implemented | Shared RuleRef substrate |
| `2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md` | **draft** | **Current open question** |

### Key Archived Blueprints (evidence tree lineage)

- `2026-03-18_runtime-traceability-evidence-tree-realignment.md` - why evidence tree belongs to the plan
- `2026-03-18_native-candidate-evidence-tree-v1.md` - V1 shape
- `2026-03-19_native-candidate-evidence-tree-v2.md` - V2 sectioned tree
- `2026-03-19_native-where-ruleref-execution-substrate.md` - also in archive copy
- `2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md` - also in archive copy

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

After recursive proof, the natural next candidates are:

1. **Winning-branch semantics** - currently open as draft blueprint (see section 2.5)
2. **Richer unresolved taxonomy** - expand `unresolved_reason` beyond `child_support_unavailable`
3. **Engine witness parity** - let evidence tree work for non-native (souffle/problog) candidates
4. **Proof graph / graph UI** - promote tree to graph-oriented evidence surface
5. **Annotation / value semantics / salience** - contribution / impact annotations on tree nodes
6. **Finer provenance** - snippet/span level source positioning

## 8. Collaboration Protocol

The established working protocol between user and agent is:

1. **Blueprint-driven**: all non-trivial work starts with a blueprint that goes through `draft -> scoped -> implementing -> implemented -> archived`
2. **User implements, agent reviews**: the user writes code; the agent reviews implementations against scoped blueprint acceptance criteria, proposes modifications, and performs git commits
3. **Agent never creates files or modifies code** without explicit user instruction
4. **Scope discipline**: each blueprint opens exactly one capability line; deferred lines are not pulled in
5. **M1 testing principle**: if blueprint says X is load-bearing, test must assert it
6. **Single commit per coherent phase**: one commit for each implementation round
7. **Git housekeeping**: agent handles commits when requested, using detailed multi-line messages

## 9. What the Next Agent Should Do

### If user opens winning-branch discussion

The user said "the next step is to discuss the freeze of section 5 questions." The winning-branch blueprint's section 5 contains five open questions:

1. Should winning-branch become a formal contract?
2. At which layer should selection happen?
3. What is the minimal identity shape?
4. How to handle multi-branch ties?
5. Should non-winning branch capture be retained as shadow metadata?

The agent should be ready to discuss these questions using knowledge of the current implementation. Key code context: `_support_capture.build_support_artifact_for_binding(...)` currently iterates all `_normalize_where_branches(where)` branches and captures all matching `pred_witnesses`, `non_fact_steps`, and `rule_ref_edges`.

### If user wants to move to a different line

Respect the user's choice. Do not advocate for winning-branch if user wants engine parity, richer taxonomy, or another direction.

### What NOT to do

- Do not reopen recursive proof DTOs
- Do not reopen RuleRef execution substrate
- Do not write code without user implementing first
- Do not run full test suite unless asked
- Do not commit the untracked winning-branch blueprint files unless asked

## 10. Minimal Startup Reading List

For a new agent, read in this order:

1. **This handoff** (you're reading it)
2. **Winning-branch blueprint** (current open question):
   - `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md`
   - `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.audit.md`
3. **Recursive proof blueprint** (implemented, for context on what's already decided):
   - `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md`
   - `docs/blueprints/active/2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.audit.md`
4. **Key implementation files** (current truth):
   - `src/factpy_kernel/core/store/_support_capture.py` - capture layer
   - `src/factpy_kernel/core/store/_support.py` - DTOs
   - `src/factpy_kernel/core/store/_candidate_evidence_tree.py` - tree builder
   - `src/factpy_kernel/core/rules/ruleref_substrate.py` - execution substrate
5. **Module docs**:
   - `src/factpy_kernel/core/docs/01_architecture.md`
   - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
   - `src/factpy_kernel/audit/docs/01_overview.md`

Then wait for user direction on whether to proceed with winning-branch section 5 discussion.
