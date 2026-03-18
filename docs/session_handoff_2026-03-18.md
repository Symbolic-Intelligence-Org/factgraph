# Session Handoff: 2026-03-18

这份文档用于让新的 session 中的 LLM 快速恢复当前仓库状态。它是 handoff 材料，不替代 active blueprint、archived blueprint 或模块 docs。

## 1. 当前整体状态

近期两条主线都已经收到了稳定停点：

- explainability / durable storage / unified explain surface
  - 第一阶段基座已经完成
- temporal-hybrid / Scenario B (`ECSS-M-ST-10` 风格 VCD/compliance matrix)
  - 近期闭环已经完成

这意味着新 session 不需要再回去补 explainability substrate，也不需要再补 Scenario B 的 delivery 尾巴，除非用户明确要求开启第二阶段工作。

## 2. Explainability 主线现状

已经完成并归档的能力包括：

- native binding -> `SupportArtifact` capture
- `rule_run` trace capture + schema contract
- durable sidecar readback + retention / GC
- `explain_ref` service-level unification
- engine degraded explain 的显式语义

当前结论：

- explainability 第一阶段基座已完整
- 仍未做的内容属于第二阶段：
  - `souffle true witness`
  - `problog proof-tree`
  - proof / evidence 对外消费形态

相关母蓝图仍在 active：

- [2026-03-17_runtime-traceability-explainability-blueprint.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md)

但这份母蓝图当前更像 umbrella blueprint，而不是“还有未收尾的第一阶段任务”。

## 3. Temporal-Hybrid / Scenario B 现状

当前已完成的切片：

- [2026-03-18_ecss-scenario-anchoring.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-18_ecss-scenario-anchoring.md)
  - `scoped` / active
  - 作用：作为分析锚点，固定近期 `Scenario B` 与中期 `Scenario A`
- [2026-03-18_ecss-vcd-compliance-delivery.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-18_ecss-vcd-compliance-delivery.md)
  - 已归档
  - 收口了：
    - `K1` hybrid fact model
    - `K2` offline-query-first
    - `K3` service boundary frozen
- [2026-03-18_audit-compliance-matrix-ui.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-18_audit-compliance-matrix-ui.md)
  - 已归档
  - 让 static audit site 生成 `compliance_matrix.html`

Scenario B 当前闭环是：

`fact model -> offline query -> static delivery -> assertion drill-down`

已落地代码的关键入口：

- [compliance.py](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/compliance.py)
- [query.py](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/query.py)
- [dto.py](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/dto.py)
- [static_ui.py](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/static_ui.py)
- [01_overview.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/docs/01_overview.md)

## 4. 下一步最自然的入口

如果继续沿 temporal-hybrid / Scenario B 往前走，最自然的下一步是：

- requirement authoring / data-entry surface

建议的起点问题：

1. 是否为 ECSS predicates 提供 authoring helper
2. 最小写入工作流长什么样
3. 是否需要 registry/schema registration helper
4. 如何验证写入侧与现有 offline delivery 无缝对接

这一步仍然不需要：

- live service endpoint
- 新 package artifact
- temporal semantics
- uncertainty semantics

## 5. 中期而非近期的入口

以下方向仍然明确存在，但应视为中期切口，而不是当前默认继续项：

- `temporal-semantics`
- `uncertainty-and-confidence`
- `pyreason-integration-spike`
- `souffle true witness`

其中：

- `Scenario A`（ESSB-ST-U-007 风格 debris mitigation）是 temporal/uncertainty 工作的真正驱动场景
- 当前只做到了锚点分析，没有进入实现

## 6. 不要重新开启的已收口争议

新 session 默认不需要再重新讨论这些点：

- explainability 第一阶段是否还缺基础设施
- Scenario B 是否应该先开 live endpoint
- Scenario B 是否应该新增 `compliance_matrix.jsonl`
- `packages/export` 是否需要为了 Scenario B 改 wire format
- `explain_ref` 是否应承担 compliance matrix contract

这些都已经在 archived blueprints 和代码里收口：

- `offline-query-first` 是既定结论
- static UI 只是 additive delivery layer
- `explain_ref` 仍然只是更深的 drill-down helper

## 7. 验证基线

最近一次完整回归命令：

```bash
PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1
```

最近一次结果：

- `48 tests` 全通过

如果新 session 要继续从 Scenario B 往前走，先保持这条回归为绿色基线即可。

## 8. 使用建议

如果新 session 用户的意图不明确，优先按以下顺序判断：

1. 若是继续 Scenario B：
   - 从 requirement authoring surface 开始
2. 若是回 explainability：
   - 先确认是否明确要进入第二阶段（`souffle true witness` / `problog proof-tree`）
3. 若是开启新主题：
   - 不要把当前 explainability 或 Scenario B 当成“还有尾巴必须补”的 workstream
