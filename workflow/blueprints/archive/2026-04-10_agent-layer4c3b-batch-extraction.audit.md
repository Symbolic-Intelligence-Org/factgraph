# Audit Log: Agent Layer 4C3-b — Batch Extraction Orchestration

## 2026-04-10 — 初始设计

### 设计依据

基于 v1.1-delta §4.4 (W4 文档提取批量处理) + 4C3-a 已落地 + 用户指导（先 4C3-b，不做 4C3-c / Burr / Langfuse / W2b）。

### 用户冻结决策

| # | 决策 | 来源 |
|---|------|------|
| L4C3b-01 | 只做单文档 segments[] → extraction batch | 用户 2026-04-10 指导 |
| L4C3b-02 | 结果是 BatchExtractionResult，包含 per-segment successes/errors | 用户 2026-04-10 指导 |
| L4C3b-03 | partial failure 不阻断整批 | 用户 2026-04-10 指导 |
| L4C3b-04 | bundle 聚合只拼接 validated FactDraftSpec[]，不做 dedupe | 用户 2026-04-10 指导 |
| L4C3b-05 | observability 只做轻量 counters/latency，不先做 Langfuse 深集成 | 用户 2026-04-10 指导 |

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| L4C3b-06 | BatchExtractor 纯函数式，不持有 AgentSession | 与 ExtractionAgent / DocumentStaging 一致；简化测试 |
| L4C3b-07 | BatchExtractor 顺序执行，不做并发 | v1 最小可用；并发需要 rate limit 配合，留给 v2 |
| L4C3b-08 | 失败分层：BatchExtractionError（前置）vs ExtractionError（per-segment） | 两种失败语义不同：前置是整 batch 无法开始；per-segment 是单条失败 |
| L4C3b-09 | batch_cap_reached 使用"graceful cap" — 剩余 segments 记录为 ExtractionError | 与 partial failure 语义一致；避免突然终止 |
| L4C3b-10 | unexpected exception 降为 ExtractionError(kind="unexpected") | defensive；batch 绝不应向外抛异常 |
| L4C3b-11 | aggregated_specs 是 tuple，不可变 | 与 BatchExtractionResult 的 frozen dataclass 一致 |
| L4C3b-12 | metrics 不持久化，只在返回值中提供 | 持久化决策留给 observability blueprint（Langfuse/OTel） |
| L4C3b-13 | 不做 dependency 预检短路 | 避免 batch 层重复 probe；4C3-a 已有 local import 检查 |
| L4C3b-14 | extract_and_create_document_bundle 作为便利方法 | 与 4C3-a 的 extract_and_create_bundle 风格一致 |

## 2026-04-10 — 实现前收口修订 (4 处)

### 修订来源

用户 code review 发现 3 处 P1 blocker + 1 处 P2 合同不一致。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| L4C3b-15 | **冻结** 所有前置失败（含 doc_id_mismatch）降为 BatchExtractionError 返回，永不 raise 异常 | §1.1 和错误表/AC 双真相；统一为 BatchExtractionError 返回，与 Layer 3A/4C2 best-effort 语义一致 |
| L4C3b-16 | **冻结** 直接扩展 4C3-a 的 ExtractionError.error_kind Literal，追加 "unexpected" 和 "batch_cap_reached" | 避免造 batch-local wrapper；前向兼容扩展（只加允许值） |
| L4C3b-17 | **冻结** batch-level max_batch_size 二次截断：当前 segment 接受前 remaining 条，超出部分追加到 result.rejections 为 scope_max_batch_size | 4C3-a 只做 per-segment 截断，多 segment 会 overshoot；batch-level 必须再截一次 |
| L4C3b-18 | 修正"5 种 BatchExtractionError"为 4 种（empty_segments / doc_id_mismatch / segments_exceed_limit / config_invalid） | 数据模型只定义 4 种；文档口径不一致 |
| L4C3b-19 | **冻结** batch 截断 rejection 使用 proposal_index=-1 占位；不扩展 4C3-a 的 ExtractionResult 以保留原始 proposal_index | 4C3-a 的 valid_specs 不保留 proposal_index；扩展 ExtractionResult 会污染 FactDraftSpec 语义；占位索引 + detail 字段足够追溯 |
| L4C3b-21 | **扩展** 4C3-a 的 ExtractionRejection.proposal_index 允许 -1 作为 batch-local sentinel；放宽 __post_init__ 校验从 `>= 0` 到 `>= -1` | 原合同要求非负整数，与 L4C3b-19 的占位索引冲突；扩展允许值而非放弃 rejection 载体，保持语义统一 |
| L4C3b-20 | 修正 §3.2 "raise BatchExtractionError" 措辞残影为 "返回 BatchExtractionError" | 与 L4C3b-15 的永不抛异常约定一致 |

### 合同对齐验证

确认以下已实现合同在 Layer 4C3-b 中正确引用：
- `DocumentSegment` (Layer 4C1) ✓
- `FactDraftSpec` (Layer 4C2) ✓
- `ExtractionAgent.extract_from_segment(segment, schema_ir, scope, config)` (Layer 4C3-a) ✓
- `ExtractionResult / ExtractionError` (Layer 4C3-a) ✓
- `ExtractionConfig` (Layer 4C3-a) ✓
- `AgentScope.max_batch_size` (Layer 1) ✓
- `ReadReviewOrchestrator.create_document_bundle` (Layer 4C2) ✓
- Schema source resolution (L4C3a-17) ✓ 复用

### 边界声明

Layer 4C3-b 明确不涉及：
- 跨文档批量 / 全局 extraction queue
- Cross-segment entity resolution / 去重 / 引用消解（4C3-c）
- Langfuse / OpenTelemetry / Burr 深集成
- Token budget limit / 自动 model downgrade
- 并发 / 并行 LLM 调用
- LLM 响应缓存
- 自动构造 bundle（调用方决定）
- Retry 扩展（Instructor 原生 retry 已覆盖最常见场景）

### 与其他 Layer 的关系

```
4C1 staging → list[DocumentSegment]
     ↓
4C3-b batch orchestration
     ↓ (per segment)
4C3-a single extraction → ExtractionResult | ExtractionError
     ↓ (aggregation)
BatchExtractionResult.aggregated_specs → list[FactDraftSpec]
     ↓
4C2 create_document_bundle → DraftBundle
     ↓
4C2 review/approval + commit → ledger
```

4C3-b 是 4C3-a 之上的薄编排层，不重新发明业务逻辑。所有 LLM 调用、validation、provenance 注入仍然在 4C3-a 中完成。4C3-b 的职责是顺序驱动 + 失败捕获 + metrics 聚合 + batch cap。

### Observability 最小集声明

L4C3b-05 冻结的稳定字段清单：

**Per segment**: `segment_id / model / llm_latency_ms / proposal_count / valid_count / rejection_count / error_kind`

**Per batch**: `doc_id / total_segments / success_segment_count / error_segment_count / total_proposal_count / total_valid_count / total_rejection_count / batch_started_at_ns / batch_finished_at_ns / batch_duration_ms`

这套字段在后续 Langfuse/OTel 深集成时应当作为最小保证集：任何 observability 后端至少能消费这些字段。

### 为什么不先做 Langfuse

4C3-a 刚引入第一次 model call，batch 之后才是第一次规模化 model call。真正有观测价值的是：
1. 批量调用的失败率分布
2. 不同 model 的 latency 分布
3. rejection_count 的构成（哪类 validation 拒绝最多）

这些问题在 4C3-b 的 metrics 稳定之后再接 Langfuse，能让 trace schema 对准真实问题而不是想象问题。

## 2026-04-10 — 实现完成 / 归档前收口

### 实现结果

- 新建：
  - `src/factpy_kernel/agent/extraction/batch.py`
  - `src/factpy_kernel/agent/extraction/metrics.py`
- 扩展：
  - `src/factpy_kernel/agent/extraction/models.py`
  - `src/factpy_kernel/agent/extraction/__init__.py`
  - `src/factpy_kernel/agent/orchestrator.py`
  - `src/factpy_kernel/agent/framework.py`
  - `src/factpy_kernel/agent/__init__.py`
  - `src/factpy_kernel/agent/docs/README.md`
  - `src/factpy_kernel/agent/extraction/docs/README.md`
  - `docs/README.md`

### 验证

- `python -m py_compile` 覆盖 extraction/orchestrator/framework 通过
- 4C3-b 定向：14 tests 通过
- 相关回归：57 tests 通过
- 全量：`898 tests`, `1 skipped`

### 实现偏差

1. `early_stop_on_batch_cap_reached=False` 保留为未主推的扩展配置
   - blueprint 的默认语义和 AC 只覆盖 hard-stop 分支。
   - 实现没有删掉这个配置位，但主路径仍以默认 `True` 为准。
