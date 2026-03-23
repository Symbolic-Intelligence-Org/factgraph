# Sub-Blueprint: Provenance Audit Consumer Surface

- Status: implemented
- Created: 2026-03-23
- Last Updated: 2026-03-23
- Parent Blueprint:
  - [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](../active/2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)
- Related Modules:
  - `src/factpy_kernel/adapters/souffle/provenance.py`
  - `src/factpy_kernel/adapters/souffle/package.py`
  - `src/factpy_kernel/audit/reader.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `examples/esa_demo.py`
- Related Docs:
  - [2026-03-22_architectural-decisions-v2.md](../active/2026-03-22_architectural-decisions-v2.md) — ADR #19, #20
  - [01_souffle_adapter.md](../../../src/factpy_kernel/adapters/docs/01_souffle_adapter.md) — provenance v0 spec
  - [01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md) — audit package artifact files
  - [03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md) — audit package export DTO and artifact notes
  - [certainty-audit-static-delivery](./2026-03-21_certainty-audit-static-delivery.md) — reference pattern
- Audit Log:
  - [2026-03-23_provenance-audit-consumer-surface.audit.md](./2026-03-23_provenance-audit-consumer-surface.audit.md)

## 1. Problem

Souffle provenance (`SouffleProofTreeV0`) currently exists only as an adapter-local demo artifact:
- `run_package_provenance(...)` produces proof trees
- `esa_demo.py` writes them as standalone JSON files in `provenance/`
- Static HTML audit site does NOT render provenance
- Audit package does NOT contain provenance
- `AuditQuery` has no provenance access

This means the richest traceability data (engine-native proof trees showing recursive derivation chains, assertion identity, negation, comparison leaves) is invisible to the product's audit pipeline. Reviewers opening the static site see the reconstructed evidence tree but not the engine's own proof.

## 2. Goals

- Make Souffle provenance flow through the same audit package → reader → query → static site pipeline that `certainty_summaries.jsonl` already uses.
- Candidate evidence pages in the static site gain an "Engine Provenance" section showing the actual Souffle proof tree.
- The pattern must be **additive** — old packages without provenance continue to work.
- Provenance data format remains **adapter-local** (`SouffleProofTreeV0`) — no core contract yet.

## 3. Non-Goals

- NOT defining a cross-engine `ProofNode v1` (deferred per ADR)
- NOT replacing the existing evidence tree (coexistence)
- NOT adding provenance to service endpoints (adapter-local only)
- NOT persisting provenance in the ledger / candidate meta dict
- NOT handling ProbLog or PyReason provenance (Souffle only)
- NOT changing `run_package(...)` return type

## 4. Design

### 4.1 Reference Pattern: certainty_summaries.jsonl

The certainty audit delivery (archived blueprint) established this additive pattern:

```
Export time:  runtime computes certainty → writes certainty_summaries.jsonl
Reader:       loads JSONL → AuditPackageData.certainty_summaries dict
Query:        get_candidate_certainty_summary(cid) reads from dict
Narrative:    passes certainty to renderer → certainty_lines
Static site:  renders certainty section in candidate evidence page
Old packages: no file → empty dict → no certainty section (backward compat)
```

Provenance follows the exact same pattern.

### 4.2 New Artifact: audit/provenance_trees.jsonl

```jsonl
{"candidate_id": "cand_v2:abc...", "provenance_tree": {"query": "...", "root": {...}, "rules": {...}}}
{"candidate_id": "cand_v2:def...", "provenance_tree": {"query": "...", "root": {...}, "rules": {...}}}
```

Each line is `SouffleProofTreeV0` serialized to dict, keyed by `candidate_id`.

**Export-time computation**: requires a **derivation recipe** to replay each candidate's evaluation as a query-bearing Souffle package. See §4.3 for how the recipe is obtained.

### 4.3 Provenance Query Recipe

**Problem**: At audit export time, we need each candidate's derivation `where` clause + `head_vars` + `target_pred_id` to construct a provenance query. But `accept` only persists `derivation_id` / `derivation_version` — the compiled where clause is discarded after evaluate.

**Solution**: Session-scoped derivation recipe cache.

```python
# In RuntimeSession (or equivalent session state):
derivation_recipes: dict[str, dict] = {}
# Keyed by run_id (stable per evaluate invocation), value = {
#   "where": [...],          # compiled where IR (supports ruleref)
#   "head_vars": [...],      # e.g., ["$m", "$status"]
#   "target_pred_id": "...", # e.g., "mission:overall_compliance_status"
#   "registry_root": "...",  # needed for ruleref expansion in query export
#   "derivation_id": "...", # for reference
#   "derivation_version": "...",
# }
```

**Why `run_id`, not `derivation_id`**: A session may call `evaluate_runtime_derivation` multiple times with the same `derivation_id` but different `where` clauses. `derivation_id` is a user-supplied label, not a unique execution key. `run_id` is generated per evaluate invocation and is the stable key preserved in accepted candidate durable meta (see `accept.py` line 756, `runtime_v1.py` line 774).

**Lifecycle**:
1. `evaluate_runtime_derivation(...)` already has `compiled["where"]`, `compiled["head_vars"]`, `compiled["target_pred_id"]`, and the resulting `run_id`. After successful evaluate, cache recipe in `session.derivation_recipes[run_id]`.
2. `export_runtime_package(package_kind="audit")` iterates accepted candidates. For each candidate, look up its `run_id` in the recipe cache. If found, attempt provenance materialization.
3. Session close clears the cache (no durable persistence needed — recipe is session-scoped only).

**Provenance materialization per candidate**:
1. Look up recipe by `candidate.run_id`
2. `export_package(store, tmpdir, options, query={"where": recipe["where"], "query_rel": query_rel, "registry_root": recipe["registry_root"]})`
3. `run_package(tmpdir, ["__query__"])` to execute
4. Read output rows, find the row matching this candidate's payload terms
5. `run_package_provenance(tmpdir, [query_string])` to get proof tree
6. Serialize `SouffleProofTreeV0` to dict

**Skip gate**: A candidate is skipped (no provenance) when:
- Its `derivation_id` is not in the recipe cache (e.g., accepted from a prior session)
- The query export fails (e.g., where clause contains atoms the export path doesn't support)
- Souffle execution or provenance explain returns no result
- No output row matches this candidate

This is NOT the old "non-Souffle / ruleref failure" framing. The real gate is: **can we replay this candidate's derivation as a query-bearing Souffle package and match a concrete output row to the candidate?**

### 4.4 Changes by Layer

**adapters/souffle/package.py**:
- `export_package(...)` gains optional `provenance_trees: dict[str, dict] | None = None`
- When non-None and non-empty, writes `audit/provenance_trees.jsonl`
- Pure writer, no computation (same as `certainty_summaries`)

**service/runtime_v1.py**:
- `evaluate_runtime_derivation(...)`: after successful evaluate, cache recipe in `session.derivation_recipes[run_id]`
- `export_runtime_package(package_kind="audit")`: iterate accepted candidates, look up recipe, attempt provenance materialization, collect results
- Pass resulting dict to `export_package(..., provenance_trees=...)`
- Silent skip per candidate when gate conditions fail (logged, not raised)

**audit/reader.py**:
- `AuditPackageData` gains `provenance_trees: dict[str, dict]` field
- `_read_provenance_trees(...)` helper reads JSONL (missing file → empty dict)

**audit/query.py**:
- `AuditQuery.get_candidate_provenance_tree(candidate_id) -> dict | None`
- Returns the raw serialized `SouffleProofTreeV0` dict, or `None`

**audit/static_ui.py**:
- Candidate evidence page gains "Engine Provenance" section after certainty
- Renders proof tree as nested HTML nodes (reusing existing tree node CSS/styling)
- Node types: RULE (derived), FACT (axiom), NOT (negation), SUBPROOF (depth limit)
- Section only appears when provenance exists for this candidate

**examples/esa_demo.py**:
- Remove standalone provenance JSON generation (now in audit package)
- Or keep both (standalone + audit) for backward compat

### 4.5 Boundary Constraints

- `SouffleProofTreeV0` is serialized as-is (dict). No conversion to `ProofNode` or core types.
- `provenance_trees.jsonl` is an audit-package-local artifact, not a durable API contract.
- If the field shapes evolve (e.g., when ProofNode v1 is designed), the JSONL format changes too.
- The static site renderer reads the dict directly — no DTO layer.

## 5. Implementation Plan

```
Step 1: Derivation recipe cache (keyed by run_id)
  - runtime_v1.py: add session.derivation_recipes dict keyed by run_id
  - evaluate_runtime_derivation: cache compiled where/head_vars/target/registry_root after success
  - Export path: look up recipe by candidate's run_id, not derivation_id

Step 2: Export writer
  - package.py: add provenance_trees parameter + JSONL writer
  - Mirror certainty_summaries pattern exactly

Step 3: Runtime export computation
  - runtime_v1.py: iterate accepted candidates, look up recipe, materialize provenance
  - Silent skip per candidate when gate fails

Step 4: Reader + Query
  - reader.py: AuditPackageData.provenance_trees + loader
  - query.py: get_candidate_provenance_tree(cid)

Step 5: Static site rendering
  - static_ui.py: "Engine Provenance" section on candidate evidence page
  - Nested tree visualization with node-type styling

Step 6: Tests
  - Audit round-trip: export → load → query provenance matches runtime
  - Backward compat: old package without provenance_trees.jsonl → no errors
  - Static site: provenance section appears when data exists
  - Recipe cache: evaluate caches by run_id, export looks up by run_id
  - Same derivation_id reused with different where: each gets correct recipe

Step 7: Docs + demo update
  - Adapter docs, audit docs, demo walkthrough
  - esa_demo.py updated to show provenance in audit site
```

## 6. Acceptance Criteria

1. `export_runtime_package(package_kind="audit")` produces `audit/provenance_trees.jsonl` when provenance is available
2. `AuditQuery.get_candidate_provenance_tree(cid)` returns serialized proof tree dict
3. Static site candidate evidence page shows "Engine Provenance" section with nested tree
4. Old audit packages without `provenance_trees.jsonl` continue to load and display without errors
5. 244+ tests green (new tests for round-trip + backward compat + static rendering)
6. `esa_demo.py` audit site shows provenance in candidate evidence pages

## 7. Outcome / Deviations

- 最终落地结果：
  - `RuntimeSession` 新增 run-scoped `derivation_recipes` cache；`evaluate_runtime_derivation(...)` 成功后按 `run_id` 缓存 compiled `where` / `head_vars` / `target_pred_id` / `registry_root`，供后续 audit export replay 使用。
  - `export_runtime_package(package_kind="audit")` 现在会尝试为 accepted candidates 物化 `audit/provenance_trees.jsonl`；写入格式与 `certainty_summaries.jsonl` 同样是 additive JSONL pattern。
  - `audit.reader` / `AuditQuery` / static UI 已打通正式 consumer surface：audit package 读取 provenance tree，candidate evidence page 渲染 additive `Engine Provenance` section。
  - 回归测试覆盖了 export materialization、reader/query round-trip、旧 package backward compatibility、static HTML rendering。
- 与原蓝图相比的实现细节：
  - provenance replay 不是按 `candidate.derivation_id` 匹配，而是按 accepted candidate durable meta 里的 `run_id` 取 recipe；这避免了同一 session 内重复复用 `derivation_id` 时的 recipe 污染。
  - candidate 到 query output row 的匹配不是直接用 accepted claim arg 顺序，而是先对 query export 做 `ruleref` expansion，再按生成后的 query variable order 绑定；这是为了与 Souffle exporter 实际输出列顺序保持一致。
  - `examples/esa_demo.py` 继续保留 standalone `provenance/*.json` 产物，但 audit package / static HTML 现在已经成为正式的产品内 provenance consumer surface。
- 归档说明：
  - 该子蓝图已完成并归档；母蓝图继续保持 active，用于后续 provenance consumer surface / ECSS 阶段决策。
