# Sub-Blueprint: RuleRef Souffle Query Export

- Status: implemented
- Created: 2026-03-23
- Last Updated: 2026-03-23
- Parent: [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](../active/2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)
- Related Modules:
  - `src/factpy_kernel/adapters/souffle/where_compile.py`
  - `src/factpy_kernel/adapters/souffle/package.py`
  - `src/factpy_kernel/adapters/docs/01_souffle_adapter.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `examples/ecss_compliance_demo.ipynb`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [memory/session_handoffs/2026-03-23.md](../../../memory/session_handoffs/2026-03-23.md)
  - [2026-03-22_architectural-decisions-v2.md](../active/2026-03-22_architectural-decisions-v2.md)
- Audit Log:
  - [2026-03-23_ruleref-souffle-query-export.audit.md](./2026-03-23_ruleref-souffle-query-export.audit.md)

## 1. Problem

Souffle provenance v0 is now validated on real ECSS flat rules, but the first composed ECSS rule still fails in the query export path:

- native evaluation handles `ruleref` correctly via the shared RuleRegistry substrate;
- `export_runtime_package(query=...)` can produce flat query-bearing packages;
- `compile_where_to_query_dl(...)` still raises `unsupported atom kind: ruleref`.

This is the single remaining blocker preventing Souffle provenance from covering full composed ECSS rule chains such as `q.essb_u007_overall_compliance`.

## 2. Goals

- Add `ruleref` support to Souffle query export for registry-backed queries.
- Keep the change additive to the existing package export and provenance v0 flow.
- Verify that the ECSS top-level compliance rule can produce a Souffle proof tree through exported query packages.

## 3. Non-goals

- No changes to native evaluate / shared Python substrate semantics.
- No ProofNode or cross-engine carrier work.
- No service endpoint expansion beyond query payload fields consumed by exporter internals.
- No audit durable format changes.
- No new explain surface beyond existing demo / adapter-local provenance path.

## 4. Current Context

- Flat query export already works through `export_package(..., query=...)`.
- `ruleref` resolution today exists only in the native substrate (`core/rules/ruleref_substrate.py`).
- `export_package(...)` does not currently own a RuleRegistry, so registry-backed query export must be explicitly threaded.
- The ECSS notebook already has a real failing caller and a clear acceptance case:
  `q.essb_u007_overall_compliance`.

## 5. Proposed Shape

### 5.1 Query payload contract

Keep `export_runtime_package(...)` unchanged at the outer DTO level.

Use an additive query payload field:

```json
{
  "query": {
    "where": [...],
    "query_rel": "overall_compliance_query",
    "registry_root": "/path/to/registry"
  }
}
```

`registry_root` is optional for flat queries and required only when `query.where` contains `ruleref`.

### 5.2 Compiler strategy

- `package.py` loads a transient `RuleRegistry` from `query.registry_root` when present.
- `where_compile.py` accepts an optional registry for query compilation.
- Before normal Souffle query lowering, `ruleref` atoms are recursively rewritten to internal predicate ids.
- The compiler emits Souffle relation declarations and rules for referenced exposed rules into the same `idb.dl`.
- Cycle handling must be explicit and non-infinite; recursive rule references may be emitted once and reused.

### 5.3 Scope boundary

- Internal emitted rule relations stay adapter-local and use the existing internal `__rule_ref__...` naming scheme.
- No witness/provenance carrier changes are introduced in this slice.
- The existing flat query path must remain byte-compatible unless `ruleref` is present.

## 6. Boundaries And Invariants

- Must keep:
  - `run_package(...) -> Path` unchanged.
  - provenance v0 adapter-local boundaries unchanged.
  - native RuleRegistry behavior as the semantic reference for `ruleref`.
- Explicitly not doing:
  - moving RuleRegistry state into `Store`
  - adding new service methods
  - persisting Souffle proof trees into audit packages
- Compatibility constraints:
  - flat `compile_where_to_query_dl(...)` callers must continue to work unchanged
  - `query.registry_root` must be ignored for flat queries when not needed
  - missing registry for a `ruleref` query must fail with a clear validation error

## 7. Acceptance

- [x] Query-bearing export supports `ruleref` when `registry_root` is supplied.
- [x] `q.essb_u007_overall_compliance` can produce a Souffle proof tree through `run_package_provenance(...)`.
- [x] Existing flat query export tests still pass.
- [x] Adapter docs and runtime package export docs are updated.
- [x] Mother blueprint audit records the boundary closure.

## 8. Implementation Plan

1. Add a registry-backed `ruleref` rewrite/emission path to `where_compile.py`.
2. Thread optional `query.registry_root` handling through `package.py` and add regression tests.
3. Update the ECSS demo caller to use the new path, then sync adapter/service docs and blueprint audits.

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/01_souffle_adapter.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - `where_compile.py` 现已支持带 registry 的 `ruleref` query export：递归重写 exposed rules，生成 adapter-local internal Souffle relations，并保持 flat query 行为不变。
  - `package.py` 新增 `query.registry_root` threading，并可从 registry filesystem 加载规则后导出 composed query-bearing package。
  - 回归测试新增了 direct compile、package threading、nested registry-backed `ruleref` export 三类覆盖。
  - 真实 ECSS caller 已验证：`q.essb_u007_overall_compliance` 能通过 `export_runtime_package(..., query={..., registry_root})` + `run_package_provenance(...)` 产出 Souffle proof tree。
- 与 blueprint 不同的地方：
  - 没有修改 `examples/ecss_compliance_demo.ipynb` 以外的 delivery surface，也没有新增任何 service code path；工作集中在 adapter/package compiler 和 docs/test closure。
- 为什么会有这些调整：
  - 真实阻塞点全部位于 query export compiler 与 registry loading，而不是 runtime facade 本身。
- 归档说明：
  - 该子蓝图完成后应归档；母蓝图继续保持 active，承接后续 ECSS/provenance 阶段工作。
