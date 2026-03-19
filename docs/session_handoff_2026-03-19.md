# Session Handoff: 2026-03-19

这份文档用于让新的 agent 快速恢复当前仓库状态。它是 session handoff / restart reference，不替代 active blueprint、archived blueprint 或模块 docs。

## 1. 当前阶段结论

项目已经从 `cross-domain validation stable stopping point` 进一步推进到了 **native candidate evidence tree v2**：

- cross-domain / mixed-source walkthrough 阶段已经完成并归档
- `Rainbird-style evidence chain` 相关工作已经不再停留在 flat explain
- 当前已具备一个可信的 **candidate-centric evidence tree v2 底座**
  - native only
  - candidate entry
  - runtime / audit / static 三层交付
  - sectioned tree shape
  - minimal `rule_ref` nodes

因此，下一次 session 的默认起点不再是“是否要开始做 tree”，而是：

- **evidence tree 之后的下一条 capability decision 是什么**

## 2. 当前能力基线

### 2.1 Explain / Audit Delivery Spine

当前 explain / audit 主线已经稳定存在：

- raw explain
- summary
- narrative
- NL explain
- audit/static proof-entry

这部分不再是待建能力，而是当前实现基线。

### 2.2 Candidate Evidence Tree V1

已完成并归档：

- `candidate_id` 成为 result-centric tree entry
- runtime 新增 `POST /v1/runtime/sessions/{session_id}/queries/explain-tree`
- audit 新增 `get_candidate_evidence_tree(candidate_id)`
- static 新增 candidate evidence page
- tree leaf 保持窄边界：
  - `asrt_id`
  - `pred_id`
  - `e_ref`
  - `claim_args`

### 2.3 Candidate Evidence Tree V2

已完成并归档：

- tree 从 v1 的 shallow grouping 深化为 **sectioned tree**
- `root.children` 现在是：
  - `support_section`（始终存在）
  - `rule_ref_section`（仅当 `rule_refs` 非空时出现）
- static candidate tree page 已改为 node-kind-aware nested rendering
- assertion leaf 继续保持 v1 的窄边界，没有退化成 full assertion dump

## 3. 当前最重要的 truth 入口

新的 agent 若要继续，不应从 handoff 文档本身推断实现细节，而应先看这些入口：

### 3.1 Parent Blueprint

- [2026-03-17_runtime-traceability-explainability-blueprint.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md)

这是当前 evidence tree 所属的母蓝图。当前位置已经被对齐为：

- `audit-log-first` / delivery spine 已完成第一阶段
- `proof-tree / support-graph` 是原计划中的下一子阶段

### 3.2 Evidence Tree 相关归档蓝图

- [2026-03-18_runtime-traceability-evidence-tree-realignment.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-18_runtime-traceability-evidence-tree-realignment.md)
- [2026-03-18_native-candidate-evidence-tree-v1.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-18_native-candidate-evidence-tree-v1.md)
- [2026-03-19_native-candidate-evidence-tree-v2.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-19_native-candidate-evidence-tree-v2.md)

这三份 archive 基本定义了：

- 为什么 evidence tree 属于原计划
- v1 做了什么
- v2 又深化了什么
- 哪些能力仍然继续 deferred

### 3.3 模块真相文档

- [01_architecture.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/core/docs/01_architecture.md)
- [03_runtime_queries_views.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- [01_overview.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/docs/01_overview.md)

这里才是当前实现真相。

### 3.4 关键实现文件

- [\_candidate_evidence_tree.py](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/core/store/_candidate_evidence_tree.py)
- [runtime_v1.py](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/service/runtime_v1.py)
- [query.py](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/query.py)
- [static_ui.py](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/static_ui.py)
- [test_phase3_contracts_v1.py](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/tests/test_phase3_contracts_v1.py)

## 4. 已验证的旧基线仍然有效

在 evidence tree 之前，仓库已经完成了一轮很长的 cross-domain validation。那些结论仍然成立，不应被新 agent 重新打开：

- 多域 walkthrough 已完成：
  - ECSS
  - AML
  - process safety
  - clinical weak-signal
- 多种 source shape 已完成：
  - structured feed
  - structured form-like document
  - single-note free-text
  - correlated multi-note
  - conflicting multi-note
  - mixed-source same-case pack

这些工作共同证明：

- 当前 substrate 的适用边界比最初预期更宽
- 没有 concrete trigger 时，不应主动重开旧的 scenario walkthrough 线

## 5. Deferred Gaps 当前状态

### 5.1 旧的 scenario-driven deferred gaps

以下旧 gap 仍然存在，但**仍无 concrete trigger**：

- `T2 sequence/state semantics`
- judgment / obligation contract
- `U2` weak-signal uncertainty
- snippet/span provenance
- extraction uncertainty
- source-linkage contract

当前结论仍是：

- 没有 trigger，就不开 capability blueprint

### 5.2 Evidence-tree-adjacent deferred capability lines

在 evidence tree v2 之后，真正值得作为下一条 capability decision 比较的，是这些方向：

1. **proof graph / graph UI**
   - 把 tree 继续提升为 graph-oriented evidence surface
2. **engine parity**
   - 让 evidence tree 不再只支持 native candidate
3. **annotation / value semantics / salience**
   - 给 tree 增加 contribution / impact / value-level semantics
4. **finer provenance**
   - 例如 snippet/span 级来源定位
5. **richer recursive proof semantics**
   - 比 v2 更深的 rule-chain / referenced-support expansion

这些都还没有被选成“下一条”，只是当前最自然的候选集。

## 6. 新 agent 不应误判的边界

下一位 agent 默认不应该把当前状态误判成下面这些：

- 不是“tree 还没开始做”
- 不是“应该继续补更多 explain delivery layer”
- 不是“必须立刻做 graph”
- 不是“应该顺手一起开 engine parity / salience / snippet/span”
- 不是“应该重开一轮 synthetic walkthrough 再找 blocker”

当前更准确的边界是：

- tree 核心已经有一个稳定的 v2 底座
- 下一步应是新的 capability decision
- 那个 decision 应只打开一条主线，而不是并行铺开多条高级能力

## 7. 下一步 capability decision 的推荐起手方式

若新 agent 要继续推进，不建议直接写代码。推荐顺序是：

1. 先确认下一条 capability line 要开哪一条
2. 若没有明确用户指示，优先做一个很窄的 active blueprint
   - 比较 1 到 2 条最合理的下一步
   - 不要同时比较所有 deferred lines
3. 默认只开下面之一：
   - proof graph
   - engine parity
   - annotation/value semantics
   - finer provenance
   - richer recursive proof semantics
4. 一旦选中，就保持 native-first / scoped-first 的纪律，不把其他 deferred lines 顺手带进来

## 8. 推荐的下一步起点

如果下一次 session 没有额外用户偏好，我建议新 agent 先做：

- **一条很窄的 capability-direction blueprint**

它的目的不是立刻实现，而是回答：

- evidence tree v2 之后，下一条主线究竟先开哪条

当前更值得优先考虑的通常是：

- `richer recursive proof semantics`
  - 因为它最直接延续现有 tree 本体

而不是马上切去：

- engine parity
- graph
- salience
- snippet/span

但这仍然是 **下一次 capability decision**，不是当前已冻结结论。

## 9. 验证基线

当前最近一次完整回归命令：

```bash
PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1
```

当前结果：

- `77 tests` 全通过

## 10. 给新 agent 的最小启动清单

开始前先看：

1. [2026-03-17_runtime-traceability-explainability-blueprint.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/active/2026-03-17_runtime-traceability-explainability-blueprint.md)
2. [2026-03-18_runtime-traceability-evidence-tree-realignment.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-18_runtime-traceability-evidence-tree-realignment.md)
3. [2026-03-18_native-candidate-evidence-tree-v1.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-18_native-candidate-evidence-tree-v1.md)
4. [2026-03-19_native-candidate-evidence-tree-v2.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/archive/2026-03-19_native-candidate-evidence-tree-v2.md)
5. [01_architecture.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/core/docs/01_architecture.md)
6. [03_runtime_queries_views.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/service/docs/03_runtime_queries_views.md)
7. [01_overview.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/docs/01_overview.md)

然后再决定：

- 是继续 evidence tree 本体
- 还是转向 graph / engine parity / value semantics / finer provenance 中的某一条
