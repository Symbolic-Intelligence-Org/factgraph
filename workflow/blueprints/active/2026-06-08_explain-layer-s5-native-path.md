# Task Blueprint: Explain Layer S5 — native 路径接通

- Status: implemented
- Created: 2026-06-08
- Last Updated: 2026-06-08 (Step 4.8 closure)
- Parent Blueprint: [`2026-06-08_explain-layer.md`](./2026-06-08_explain-layer.md)
- Slice: S5 (depends on S3 ✅, S4 ✅)
- Related Modules:
  - `src/factgraph/application/protocol/evaluate_result.py` — Explanation 不变式修改 + passed-row 证据路径更新
  - `src/factgraph/sdk/store.py` — `_explain` failed 路径接通 `probe_native`
  - `src/factgraph/application/explain/prober.py` — `probe_native` 被接通（已就绪）
  - `src/factgraph/audit/evidence_graph.py` — thin re-export（S3 已改，S5 整合时需合入）
- Related Docs:
  - [explain-layer-complete-design.zh.md §9](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-08_explain-layer-s5-native-path.audit.md](./2026-06-08_explain-layer-s5-native-path.audit.md)

---

## 1. Problem

S4 后，`probe_native` 能产出有意义的 `repr_text` 烘焙证据树，但它从未被接入 `Explanation` 路径：

```python
# 当前 Explanation 不变式（evaluate_result.py:293-294）
if (self.status == "passed") != (self.evidence is not None):
    raise ProtocolShapeError("Explanation.status='passed' iff Explanation.evidence is not None")
# ↑ 只有 passed 才能有 evidence；failed 状态的 evidence 永远 None
```

加之两个谱系尚未合并：
- S3/S4（master lineage）：有 prober + 新 `EvidenceGraph(paths=...)` 形态
- feature branch lineage：有 `Explanation` class、`_explain_live_row`、`_explain()`

`evaluate_result.py` 内的 `_build_passed_row_evidence_graph` 目前用旧
`EvidenceGraph(graph_id, nodes, edges, ...)` 构造，合入 S3 后会立刻 TypeError。

## 2. Goals

1. **谱系整合（前置步骤）**：S5 impl branch 以 feature branch 为基，整合 S3/S4 改动（`audit/evidence_graph.py` thin re-export + `application/explain/` subpackage + prober repr baking）。
2. **不变式放宽**：`Explanation.evidence non-None` iff `status ∈ {passed, failed}`（设计文档 §9 ★必改不变式）。
3. **passed 路径修复**：`_build_passed_row_evidence_graph` 改为用 `probe_native` 产出 `EvidenceGraph(paths=...)`（当前用旧 nodes/edges 构造）。
4. **failed 路径接通**：`sdk/store.py` `_explain` 中 `closed_head_false` 分支调 `probe_native`，产出 evidence 并传入 `Explanation`。

## 3. Non-Goals

- 不实现 souffle / problog / pyreason adapter 的 rich explain path（归 S6）。
- 不实现 `no_matching_row` / `stale_row` / `row_not_in_result` 的 evidence（这些协议层失败案例暂保持 `evidence=None`；只有 `closed_head_false` 接通）。
- 不修改 `EvidenceAtom` / `EvidenceTree` / `EvidenceRule` DTO（S3/S4 已就绪）。
- 不修改 `diagnose_runtime.py`（各 slice 均 0-diff）。
- 不实现 `Explanation.repr_text` walker；S5 仅将 feature-branch `Explanation.repr` walker 从旧 nodes/edges 迁移到新 paths model。

## 4. Preflight Source Read — 关键发现（2026-06-08）

### 4.1 谱系拓扑

| 谱系 | HEAD | 关键内容 |
|---|---|---|
| master (S3/S4 base) | `562c7419` | 有 prober（S3/S4），无 Explanation class，无 evaluate_result.py |
| S3 impl | `69593d36` | 新 `EvidenceGraph(paths=...)` + `audit/evidence_graph.py` thin re-export |
| S4 impl | `83be07b9` | prober `repr_text` 烘焙（在 S3 之上） |
| feature branch | `ed054fd0` | `evaluate_result.py` + `Explanation` class + `_explain_live_row` + `_explain()` |

S5 impl 必须以 feature branch 为起点，cherry-pick S3/S4 的改动（3 个文件集：`audit/evidence_graph.py` + `application/explain/` subpackage + `prober.py` repr baking）。

### 4.2 当前 Explanation 不变式（待修改）

```python
# evaluate_result.py:293-294（feature branch）
if (self.status == "passed") != (self.evidence is not None):
    raise ProtocolShapeError("Explanation.status='passed' iff Explanation.evidence is not None")
```

目标（Q-S5-A Option A 已锁定）：
```python
if (self.status in {"passed", "failed"}) != (self.evidence is not None):
    raise ProtocolShapeError(
        "Explanation.status must be passed or failed iff evidence is not None"
    )
```

**同时**：`stale_row`/`row_not_in_result` 分支将 `status` 从 `"failed"` 改为 `"unsupported"` — 从而与新不变式相容（`unsupported + evidence=None` 合法）。

### 4.3 `_build_passed_row_evidence_graph` 依赖旧 EvidenceGraph

feature branch `evaluate_result.py:1040+`：
```python
return EvidenceGraph(
    graph_id=..., engine=..., root_node_id=...,
    nodes=..., edges=...,
    support_kind="evaluate_row",
    metadata=...,
)
```

整合 S3 后，`EvidenceGraph` 只接受 `paths=...`。必须更新。

### 4.4 `_explain` 的 `closed_head_false` 分支（接通目标）

```python
# sdk/store.py:2531-2540（feature branch）
if first is None:
    return Explanation(
        status="failed",
        evidence=None,  # ← S5 在此接通 probe_native
        ...
        failure_class="closed_head_false",
    )
```

接通后所需资源：
- **plan**：需要 compiled derivation plan（从 `args[0]` 重编译，调 `_compile_derivation_input(args[0])`）
- **bindings**：从 closed head 的端口绑定提取（`head.ports` → `{port_name: value}`）
- **view_facts**：`project_view_facts(self._store.ledger, self._store.schema_ir)`
- **schema_index**：`self._application_schema_index`

### 4.5 `ProofReceipt` 不含 `body_ir`

`ProofReceipt` 字段：`kind`, `root_result_kind`, `binding_items`, `pred_witnesses`, `non_fact_steps`, `rule_refs`。无 `body_ir` / `branches`。

因此 passed 路径的 `_build_form1_evidence_graph`（目前靠 `ProofReceipt`）**无法直接复用** `probe_native`——需要另外获取 compiled plan（同 failed 路径：重编译或透传）。

## 5. Proposed Shape

### 5.1 关键设计问题

#### Q-S5-A（不变式变更 + `stale_row`/`row_not_in_result` 兼容性）— **✅ 已锁定 Option A**

**决策**：`stale_row`/`row_not_in_result` 的 `status` 从 `"failed"` 改为 `"unsupported"`。

**完整不变式（S5 后）**：

```
status ∈ {"passed", "failed"}  ↔  evidence is not None
status ∈ {"unsupported", "invalid_request"}  ↔  evidence is None
```

**理由（用户确认）**：
- `failed` 语义 = 规则/断言被实际探查过，结果不成立（有可解释的逻辑失败路径）
- `stale_row`/`row_not_in_result` 是请求上下文不满足，无法构造解释，语义为"请求无法完成" → `unsupported`
- Alpha 阶段无兼容负担，直接改语义比保留例外更干净
- Test 语义更明确：`failed + EvidenceGraph(paths)` vs `unsupported + evidence=None`

#### Q-S5-B（passed 路径 probe_native 接入方式）— 委托 Codex

`_build_form1_evidence_graph`（从 `ProofReceipt` 建图）需要替换。两路：

**Option B1**：dropped — 从 `ProofReceipt.pred_witnesses` + `binding_items` 重建 `EvidenceTree`（不调 probe_native；但 `ProofReceipt` 无 body_ir 信息，只记成功路径，无法重现 Fails/NotReached 语义）

**Option B2（推荐）**：对 passed 行也重编译 rule + 调 `probe_native(plan, bindings, view_facts)`：
- bindings = `row.bindings`（已有）
- plan = 重编译 rule（从 result.head 或 support_artifact 的 rule 信息取）
- 优点：统一 passed/failed 的 probe 路径；`repr_text` 自动烘焙

**Option B3**：passed 路径暂保留占位 `EvidenceGraph(paths=())`，只接通 failed 路径 — 最小改动但 passed 解释为空图

推荐 B2；如 plan 重编译成本高，B3 作为临时占位。

#### Q-S5-C（谱系整合顺序）— 委托 Codex

S5 impl 分支以 feature branch `ed054fd0` 为起点，cherry-pick/apply：
1. S3 改动：`audit/evidence_graph.py` thin re-export + `application/explain/` subpackage（新增文件集）
2. S4 改动：`prober.py` repr baking

冲突预期：`audit/evidence_graph.py` 在 feature branch 有旧 EvidenceGraph 定义，cherry-pick S3 版（thin re-export）时可能冲突，需手工合并。

### 5.2 主要改动文件（改动量估算）

| 文件 | 改动类型 | 复杂度 |
|---|---|---|
| `audit/evidence_graph.py` | cherry-pick S3（thin re-export）；可能手工合并冲突 | 中 |
| `application/explain/` | cherry-pick S3 + S4（新增文件集） | 低（新增）|
| `application/protocol/evaluate_result.py` | 不变式修改 + `_build_passed_row_evidence_graph` 更新 + Option A status 迁移 | 高 |
| `sdk/store.py` | `_explain` `closed_head_false` 分支接通 probe_native | 中 |

### 5.3 `closed_head_false` 接通示意

```python
# sdk/store.py _explain，closed_head_false 分支
if first is None:
    # S5 新增：重编译 rule → probe_native → EvidenceGraph(paths=...)
    try:
        compiled_plans = self._compile_derivation_input(args[0])
        app_plans = _application_plans_from_compiled_dicts(compiled_plans, mode=engine)
        head_bindings = _closed_head_bindings(head)   # 从 closed head 提取端口绑定
        view_facts = project_view_facts(self._store.ledger, self._store.schema_ir)
        probe_result = probe_native(
            app_plans[0], head_bindings, view_facts,
            schema_index=self._application_schema_index,
        )
        evidence = EvidenceGraph(paths=probe_result.paths)
    except Exception:
        evidence = None  # fallback：失败时保留 None（若 Option A，此分支状态已是 failed）
    return Explanation(
        status="failed",
        evidence=evidence,
        ...
        failure_class="closed_head_false",
    )
```

## 6. Boundaries And Invariants

- **INV-evidence-iff-passed-failed**（S5 后，已锁定）:
  - `status ∈ {"passed", "failed"}` ↔ `evidence is not None`
  - `status ∈ {"unsupported", "invalid_request"}` ↔ `evidence is None`
- **INV-stale-protocol-errors-unsupported**: `stale_row`/`row_not_in_result` 的 `status` 为 `"unsupported"`（非 `"failed"`）；`failure_class` 字段仅在 `status="failed"` 时存在。
- **INV-probe-native-fallback**: `probe_native` 调用异常时，`Explanation` 回落到 `status="unsupported"`（不能产出 `failed+evidence=None`，因为新不变式禁止）。
- **INV-no-problog-pyreason-touch**: souffle/ProbLog/PyReason adapter 证据路径不在 S5 scope。
- **INV-zero-diff-diagnose**: `diagnose_runtime.py` 零改动。
- **INV-no-sdk-import-in-protocol**: `evaluate_result.py` 不直接 import SDK 层。

## 7. Acceptance

- [x] `fg.eval.explain(expr, head=closed_head)` 当 `closed_head_false` 时：`explanation.status == "failed"` 且 `explanation.evidence is not None`
- [x] `explanation.evidence.paths` 包含至少一个 `EvidenceTree`，其中有 `Fails` 或 `NotReached` atom
- [x] `explanation.evidence.paths[0].rules[0].atoms[i].repr_text` 非 `None`（S4 烘焙已接通）
- [x] `fg.eval.explain(expr, head=closed_head)` 当 assertion PASSES 时：`status == "passed"` 且 `evidence is not None` 且 `evidence.paths` 非空
- [x] `stale_row`/`row_not_in_result` 返回 `status="unsupported", evidence=None`（**Q-S5-A Option A 已锁定**）
- [x] 不变式：`Explanation(status="failed", evidence=None)` 构造时抛出 `ProtocolShapeError`
- [x] 不变式：`Explanation(status="unsupported", evidence=<not None>)` 构造时抛出 `ProtocolShapeError`
- [x] 所有既有 S3/S4 prober 测试仍 pass
- [x] compileall + import sweep pass（含整合后的 feature branch 代码）
- [x] `diagnose_runtime.py` 0-diff

## 8. Implementation Plan

1. **[已锁定 Q-S5-A Option A]** `stale_row`/`row_not_in_result` → `status="unsupported"`
2. **[Codex]** 以 feature branch `ed054fd0` 为基，创建 S5 impl 分支（命名 `v0.2.0-impl-native-explain-path-2026-06-08`）
3. **[Codex]** Cherry-pick/apply S3 改动（`audit/evidence_graph.py` thin re-export + `application/explain/` 新建文件集）；手工解决冲突
4. **[Codex]** Cherry-pick/apply S4 改动（`prober.py` repr baking）
5. **[Codex]** 修改 `evaluate_result.py`：不变式更新 + Option A status 迁移 + `_build_passed_row_evidence_graph` 更新（B2 或 B3）
6. **[Codex]** 修改 `sdk/store.py` `_explain`：`closed_head_false` 分支接通 probe_native（§5.3）
7. **[Codex]** 运行测试、compileall、import sweep，验证 acceptance

## 9. Docs To Update

- `src/factgraph/application/explain/docs/README.md` — 记录 native 路径接通机制
- `src/factgraph/application/protocol/docs/README.md` — 更新 Explanation 不变式说明
- 父 blueprint `2026-06-08_explain-layer.md` — 标记 S5 已落地

## 10. Outcome / Deviations

Implemented at `9ba5f526` on `v0.2.0-impl-native-explain-path-2026-06-08`.

Delivered:
- Integrated the S3/S4 paths-model evidence layer into the feature branch lineage: `factgraph.application.explain`, `audit/evidence_graph.py` thin re-export, adapter provenance converters, and paths-model audit docs/tests.
- Updated `Explanation` invariant to `{passed, failed} ↔ evidence is not None`.
- Reclassified `row_not_in_result` and `stale_row` live-row protocol failures as `unsupported + evidence=None + ErrorDTO`.
- Replaced passed live-row evidence construction with a paths-model `EvidenceGraph(paths=(EvidenceTree(...),))`.
- Rewrote the feature-branch `walk_evidence(...)` renderer from old `nodes/edges/root_node_id` traversal to paths/tree/timeline traversal.
- Wired SDK `_explain(...)` `closed_head_false` to `probe_native(...)`; prober failure falls back to `unsupported` and never produces `failed + evidence=None`.

Verification:
- `PYTHONPATH=src python -m unittest tests.application.protocol.test_evaluate_result_dtos tests.application.protocol.test_evaluate_result_digests tests.application.protocol.test_explanation_render tests.sdk.test_evaluate_result_exports tests.sdk.test_rule_expr_evaluate tests.sdk.test_ruleexpr_inspect tests.sdk.dsl.test_application_rule tests.test_application_explain_prober tests.test_audit_evidence_graph tests.test_problog_evidence_graph tests.test_pyreason_evidence_graph tests.test_souffle_evidence_graph` → 120 tests OK.
- `PYTHONPATH=src python -m unittest tests.sdk.test_rule_expr_evaluate tests.sdk.test_t5_why_not_quarantine tests.test_sdk_why_not tests.test_sdk_diagnose tests.test_sdk_check tests.test_application_diagnose_protocol tests.test_application_check_protocol tests.test_application_why_not_protocol` → 224 tests OK.
- `PYTHONPATH=src python -m unittest tests.test_problog_semantics_profile_migration tests.test_problog_engine_eval tests.test_pyreason_e2e` → 46 tests OK.
- `PYTHONPATH=src python -m unittest discover tests` → 1996 tests run / 32 skipped; only remaining failure is unrelated environment import `ModuleNotFoundError: No module named 'service'` in `test_a20e_registry_final_removal.ServiceRouteRemovalTests.test_service_app_v1_drops_registry_routes`.
- `PYTHONPATH=src python -m compileall -q src/factgraph tests` clean.
- `git diff --check` clean.
- Working diff on Q-PR1 sacred paths (`src/factgraph/core`, `src/factgraph/authoring`, `src/factgraph/mapping`, `src/factgraph/schema`, `docs/release`) is 0 lines.
- `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.

Deviations:
- Q-S5-B landed as a lightweight passed-row head evidence tree rather than a full probe recompile. Reason: `EvaluateResult` does not carry source rule/body plan, and `ProofReceipt` has no `body_ir`; the lightweight tree preserves `passed + evidence.paths` without inventing a plan.
- S3/S4 adapter converter changes were integrated into the S5 lineage so paths-model imports/tests compile. Rich adapter explain behavior remains S6 scope.
- `probe_native(...)` added a local compare-atom fallback because current `diagnose_runtime._extend_env_with_atom` calls `_eval_cmp_atom` with an incompatible signature; `diagnose_runtime.py` remains 0-diff.
