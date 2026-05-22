# Audit Log: Agent Layer 4C3-c — Single-Document Entity Resolution

## 2026-04-10 — 初始设计

### 设计依据

基于 v1.1-delta §4.4 (W4 文档提取 Stage 3 去重) + 4C3-b 已知约束 #4（同 entity 多 segment 重复）+ 用户指导（单文档收窄，4 条冻结决策）。

### 用户冻结决策

| # | 决策 | 来源 |
|---|------|------|
| L4C3c-01 | 只做单文档 / 单 bundle resolution | 用户 2026-04-10 指导 |
| L4C3c-02 | 只对 FactDraftSpec[] 做 dedupe / merge，不改 4C1/4C3-a 原始产物 | 用户 2026-04-10 指导 |
| L4C3c-03 | Provenance 必须保留"多 segment 来源集合"，不能因为 merge 丢证据 | 用户 2026-04-10 指导 |
| L4C3c-04 | v1 不做跨文档 entity linking，不做外部 KB 对齐 | 用户 2026-04-10 指导 |

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| L4C3c-05 | ExtractionProvenance 扩展 merged_from tuple 字段，默认空 tuple | 前向兼容；不破坏 4C1/4C3-a/4C3-b 现有构造；primary + merged_from 保持 Layer 3A write path 零侵入 |
| L4C3c-06 | entity_key = (entity_type, sorted identity pairs) | 顺序无关的结构化元组；不做 fuzzy matching |
| L4C3c-07 | fact_key = (entity_key, pred_id, sorted field_values) | 严格匹配；sorted 保证顺序无关 |
| L4C3c-08 | v1 只做严格 fact_key 匹配，不做 fuzzy / semantic matching | 需要真实数据确定规则；严格匹配是 fuzzy 的正确子集 |
| L4C3c-09 | Primary 选择 = 输入顺序中首次出现的 spec | 自然保留 "文档中最早" 语义；Python dict 插入顺序保证稳定 |
| L4C3c-10 | Confidence merge 取 max（两者非 None 时） | 最简单、语义清晰；排除 min/avg/weighted/bayesian |
| L4C3c-11 | Merged provenance → source 格式追加 `:merged_from:N` + segment 列表 | 与 Layer 3A write path 兼容的字符串格式；kernel 不解析；审计可按子串搜索 |
| L4C3c-12 | EntityResolver 纯函数式，不持有 state | 与 ExtractionAgent / BatchExtractor / DocumentStaging 一致 |
| L4C3c-13 | Merged specs 仍然 commit 为单条 assertion，不展开为多条 | Dedupe 的目的是减少 assertion 数量；meta.source 的 segment 列表足够审计 |
| L4C3c-14 | 提供 `extract_resolve_and_create_document_bundle` 一站式方法 + 保留分步 API | 一站式是生产推荐路径；分步用于调试和审计 |
| L4C3c-15 | 不引入新的 ResolutionError kind "merge_failure" | Deterministic merge 不会 runtime 失败；任何异常都是 bug，应抛出 |

## 2026-04-10 — 实现前收口修订 (3 处)

### 修订来源

用户 code review 发现 2 处 P1 + 1 处 P2 合同不一致。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| L4C3c-16 | **冻结** fact_key 的 field_values 保留原始顺序，不按 tag 排序 | 4C3-a validation 使用 `zip(field_values, arg_specs, strict=True)` 逐位置对齐；对有重复 type_domain 的 predicate，field 顺序本身是语义的一部分；按 tag 排序会把语义不同的 spec 误判为相同 |
| L4C3c-17 | **冻结** all_sources() / source_segment_ids() 使用递归扁平展开 + 按 segment_id 去重 | 支持对已 merged provenance 的递归展开；避免"只展开一层"导致多次 resolution 时丢失 segment 集合 |
| L4C3c-18 | **冻结** EntityResolver 输入不限制 merged_from 为空，resolution 必须幂等 | 允许对已 resolved 的 specs 再次跑（调用方不需要知道 "这批是否已 resolve"）；_merge_specs 按 segment_id 去重避免重复追加 |
| L4C3c-19 | 清除正文 `resolve_batch(specs, schema_ir, scope)` 旧签名残影 | 正式接口是 `resolve_batch(specs, config)`；resolver 不依赖 schema_ir / scope |

### 合同对齐验证

确认以下已实现合同在 Layer 4C3-c 中正确引用：
- `BatchExtractionResult.aggregated_specs` (Layer 4C3-b) ✓
- `FactDraftSpec` (Layer 4C2) ✓
- `ExtractionProvenance` 基础字段 (Layer 4C2) ✓
- `ReadReviewOrchestrator.create_document_bundle` (Layer 4C2) ✓
- `BundleManager._provenance_to_draft_source` 会扩展支持 merged（L4C3c-11） ✓

### 边界声明

Layer 4C3-c 明确不涉及：
- 跨文档 entity resolution
- 外部 KB 对齐（Wikidata / MDM / Knowledge Graph）
- Anaphora resolution（"上述条款" / "前一段" 引用消解）
- Fuzzy entity matching（跨语言 / 拼写变体 / 大小写）
- 语义级别的 field merge（"年龄 25" vs "生于 1999"）
- LLM 辅助的合并判断（v1 纯 deterministic）
- Resolution 结果持久化（纯 in-memory pipeline）
- Merge 事件写入 ledger / audit trail

### 与 4C3-b 的关系

4C3-b 的已知约束 #4 明确指出"同 entity 多 segment 重复"是需要下一步解决的问题。4C3-c 正是这条约束的闭环：

```
4C3-b 产出                      4C3-c 转化
──────────                      ──────────
aggregated_specs (may repeat)   → resolved_specs (dedupe)
per-segment provenance          → merged provenance with all_sources()
ingest_key 层不同 source         → agent 层 dedupe, ledger 单条
```

### ExtractionProvenance 扩展的审计意义

这是 4C3-c 引入的唯一跨 Layer 数据结构变更。风险控制：

| 风险点 | 缓解措施 |
|--------|---------|
| 破坏 4C1/4C3-a/4C3-b 构造 | merged_from 默认值 `()`，等价于现有单来源语义 |
| Layer 3A write path 污染 | primary 字段保持不变；write path 不感知 merged_from |
| checkpoint 序列化失败 | to_checkpoint / from_checkpoint 递归处理 merged_from tuple |
| 序列化大小爆炸 | 已知约束 #3 明确此 trade-off；v1 不做 raw_text 截断 |
| 测试回归 | Step 1 单测覆盖 default/merged/checkpoint 往返，确保前向兼容 |

### 为什么先做 4C3-c 而不是 Langfuse

4C3-b metrics 已经稳定，但当前主要用于调试而不是生产观测。先做 4C3-c 的好处：

1. 完整闭环"整文档提取"能力面，这是明显的产品缺口
2. Resolution 的 merge_events + stats 会为后续 Langfuse 集成提供更多可观测维度
3. Langfuse 接入时可以同时观测 extraction + resolution 两层，一次接入获得更完整的画面
4. 4C3-c 的 metrics（merge_count, unique_entity_count）在没有 Langfuse 的情况下仍然可用（通过 ResolutionResult 返回）

## 2026-04-10 — 实现完成 / 归档前收口

### 实现结果

- 新建：
  - `src/factpy_kernel/agent/extraction/resolution.py`
  - `src/factpy_kernel/tests/test_agent_l4c3c_provenance.py`
  - `src/factpy_kernel/tests/test_agent_l4c3c_resolver.py`
  - `src/factpy_kernel/tests/test_agent_l4c3c_merge_meta.py`
  - `src/factpy_kernel/tests/test_agent_l4c3c_workflow.py`
- 扩展：
  - `src/factpy_kernel/agent/documents/models.py`
  - `src/factpy_kernel/agent/documents/bundle.py`
  - `src/factpy_kernel/agent/extraction/__init__.py`
  - `src/factpy_kernel/agent/orchestrator.py`
  - `src/factpy_kernel/agent/framework.py`
  - `src/factpy_kernel/agent/__init__.py`
  - `src/factpy_kernel/agent/docs/README.md`
  - `src/factpy_kernel/agent/documents/docs/README.md`
  - `src/factpy_kernel/agent/extraction/docs/README.md`
  - `docs/README.md`

### 验证

- `python -m py_compile` 覆盖 documents/extraction/orchestrator/framework/test files 通过
- 4C3-c 定向：13 tests 通过
- 相关回归：82 tests 通过
- 全量：`911 tests`, `1 skipped`

### 实现偏差

1. merged provenance 的 `source` 计数采用递归去重后的来源总数
   - `:merged_from:N` 中的 `N` 实现为 `len(source_segment_ids()) - 1`，而不是直接 `len(merged_from)`。
   - 这是为了与 L4C3c-17/L4C3c-18 的递归展开和幂等 re-resolution 语义保持一致。
