# Annotation Prototype

- 适用范围：`src/factpy_kernel/core/annotation`
- 状态：internal / prototype
- 最后更新：2026-03-21

## 1. 模块边界

本目录承载 `Souffle annotation kernel prototype` 的内部语义能力。

当前目标不是提供稳定 public API，而是把上一轮 benchmark spike 中已证明有价值的 annotation 逻辑，从 `tools/benchmarks` 中拆出一个可维护的内部实现落点。

## 2. 当前能力

- `_min_max.py`
  - `Workload A` 对应的 `min-max` 路径置信度传播
  - 产出带 `confidence`、`min_support_depth`、`support_path` 的结论
- `_evidence.py`
  - `Workload C` 对应的结构候选 / 直接证据 / provenance 重建与 `max` 聚合 helper
  - 当前已实现 prototype 级 raw candidate 与 provenance 能力；Top-K 仍留在 benchmark harness
- `_certainty.py`
  - certainty-weight vocabulary 的 first-consumer prototype
  - 消费 `confidence_kind="certainty"`、rule metadata `condition_weights` 与 candidate evidence tree
  - 产出 `CertaintySummary` / `ConditionImpact`，用于 candidate-level certainty summary 派生
  - `rank_certainty_conditions(conditions, aggregate_certainty)` → `list[RankedCondition]`
    - 按 impact 升序排序（weighted first → unweighted last）
    - `is_bottleneck=True` 当 condition impact == aggregate_certainty（tie 全标）
    - narrative / NL 消费 ranked view，不自行排序
  - 当前只实现 certainty lane；`probability` / `none` 直接返回 `None`
  - 当前 production consumers：
    - runtime candidate explain delivery：
      - `queries/explain-summary` 的 response-level sibling `certainty_summary`
      - `queries/explain-narrative` 的 additive `certainty_lines`
      - `queries/explain-nl` 的 additive certainty paragraph
    - audit package + static site delivery：
      - `export_package` 通过预计算写入 `certainty_summaries.jsonl`
      - `AuditQuery.get_candidate_certainty_summary(candidate_id)` 读取物化值
      - `AuditQuery.get_candidate_evidence_tree_narrative(candidate_id)` 传入 certainty_summary，产出含 `certainty_lines` 的 narrative
      - static site candidate evidence page 渲染 certainty section
  - runtime / audit / static 三面共享同一条 certainty 派生链路：
    - 只在 candidate tree 能定位到唯一 child-rule `referenced_support` subtree 时派生
    - `condition_weights` 从该 subtree 对应的单条 `rule_ref_edge -> rule_ref_id@version -> registry rule payload` 查询
    - 多 rule、递归 nested subtree、unresolved child support、或 registry 链路缺失时 graceful degrade 为 `certainty_summary=null`
- `types.py`
  - 仅放最小共享基础类型
  - 不在第一轮 prototype 中引入通用 annotation algebra

## 3. 与 Benchmark 的关系

- `tools/benchmarks/workload_*_reference.py`
  - 继续作为 oracle / golden 参考实现
- `src/factpy_kernel/core/annotation/*`
  - 作为新的 prototype 实现

这两者必须保持独立，避免同一份代码同时充当“参考真值”和“候选实现”。

## 4. 不变量

- 不直接进入正式 `Store.evaluate(...)` public contract
- 不修改 `CandidateSet` 稳定结构
- 不把 certainty summary 写回 `CandidateSet`、`SupportArtifact` 或 evidence tree core summary 12 字段
- 结构化 `certainty_summary` 只允许以 response-level sibling 形式暴露，不嵌入 core 12 字段 summary set
- runtime narrative / NL 允许消费已派生的 certainty summary，并以 additive `certainty_lines` / certainty paragraph 呈现
- narrative 中 `certainty_lines` 按 `rank_certainty_conditions` 排序输出，bottleneck 行标 `[bottleneck]`
- narrative 同时产出 machine-readable `certainty_bottleneck` key（`{atom_keys, impact}`），NL 从此 key 消费 weakest-condition 句
- audit package 允许物化 certainty_summary（export-time 预计算），但不导出 `condition_weights` 本身
- 不把 `Workload B` 时序语义混入第一轮 prototype

## 5. Provenance Summary Schema

prototype 当前保留两套 **按领域区分** 的 provenance 摘要形态；它们不强行统一字段命名，这是刻意设计，不是遗漏。

### 5.1 `_min_max.py`

`build_min_max_provenance_entries(...)` 产出：

```json
{
  "candidate": {
    "source": "e000",
    "target": "e002"
  },
  "support_path": [
    "e000 -[0.900000]-> e001",
    "e001 -[0.800000]-> e002"
  ]
}
```

字段约定：

- `candidate.source / candidate.target`
  - 对应图路径问题中的起点 / 终点
- `support_path`
  - 边路径字符串列表
  - 格式固定为 `"X -[0.900000]-> Y"`
  - 边权使用 6 位小数浮点表示

### 5.2 `_evidence.py`

`build_max_evidence_provenance(...)` 产出：

```json
{
  "candidate": {
    "subject": "ent001",
    "relation": "indirect_dependency",
    "object": "ent003"
  },
  "direct_evidence": ["claim0001"],
  "struct_support": [
    "ent001 -[depends_on]-> ent002",
    "ent002 -[depends_on]-> ent003"
  ]
}
```

字段约定：

- `candidate.subject / candidate.relation / candidate.object`
  - 对应关系三元组问题中的候选主键
- `direct_evidence`
  - `claim_id` 列表
- `struct_support`
  - 结构支持链字符串列表
  - 格式固定为 `"X -[relation]-> Y"`
  - 中括号中的内容是关系名，不是数值权重

### 5.3 为什么不统一 `candidate` 字段名

- `_min_max.py` 表达的是图路径结论，主键天然是 `(source, target)`
- `_evidence.py` 表达的是关系三元组结论，主键天然是 `(subject, relation, object)`

prototype 当前明确保留这一区分，以避免为了“字段统一”而引入一层没有必要的抽象。若未来进入正式 runtime，再根据实际调用面决定是否需要统一 carrier。
