# Blueprint: Agent Layer 4C3-b — Batch Extraction Orchestration

- Status: implemented
- Created: 2026-04-10
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Depends on:
  - Layer 4C1 确定性文档 staging (archived)
  - Layer 4C2 DraftBundle review/approval (archived)
  - Layer 4C3-a single-segment LLM extraction (archived)
- Related Modules:
  - `src/factpy_kernel/agent/extraction/batch.py` (新建)
  - `src/factpy_kernel/agent/extraction/metrics.py` (新建)
  - `src/factpy_kernel/agent/extraction/extractor.py` (只读依赖)
  - `src/factpy_kernel/agent/orchestrator.py` (扩展)
  - `src/factpy_kernel/agent/framework.py` (扩展)

---

## 0. 目标与边界

**交付目标**：把单文档的多个 `DocumentSegment` 通过 4C3-a 的 single-segment extractor 批量驱动，输出 `BatchExtractionResult`（含 per-segment successes/errors + 聚合的 `FactDraftSpec[]` + 轻量 counters/latency）。结果可直接送 4C2 的 `create_document_bundle`。

**冻结决策**（本轮锁定，正文围绕这 5 条展开）：

| # | 决策 | 理由 |
|---|------|------|
| L4C3b-01 | 只做单文档 `segments[] → extraction batch` | 跨文档批量 / 全局队列是后续层；4C3-b 只对齐"一个文档从头到尾" |
| L4C3b-02 | 结果是 BatchExtractionResult，包含 per-segment successes/errors | 对齐 Layer 3A 的 best-effort 语义；调用方拿到完整混合列表 |
| L4C3b-03 | partial failure 不阻断整批 | LLM 调用一定有概率失败；batch 绝不能因一条 segment 失败而终止 |
| L4C3b-04 | bundle 聚合只拼接 validated FactDraftSpec[]，不做 dedupe | dedupe / entity resolution 是 4C3-c；4C3-b 只做纯粹的聚合 |
| L4C3b-05 | observability 只做轻量 counters/latency，不先做 Langfuse 深集成 | 稳定字段先行：model / segment_id / llm_latency_ms / proposal_count / valid_count / rejection_count / error_kind |

**明确排除**：
- 跨文档批量 / 全局 extraction queue
- Cross-segment entity resolution / 去重 / 引用消解（4C3-c）
- Langfuse / OpenTelemetry / Burr 深度集成
- Token budget limit / 自动 model downgrade
- 并发 / 并行 LLM 调用（v1 顺序执行）
- LLM 响应缓存（相同 segment 重试）
- 自动构造 bundle（调用方决定是否送 4C2）

---

## 1. 5 条冻结决策的展开

### 1.1 L4C3b-01：单文档 segments[] → batch

**范围**：
- 输入：`list[DocumentSegment]`（必须全部来自同一 `doc_id`）
- 输出：`BatchExtractionResult` 或 `BatchExtractionError`
- 不接受跨文档混合输入 → 返回 `BatchExtractionError(error_kind="doc_id_mismatch")`
- **永不 raise 异常**（L4C3b-15 冻结）：所有前置校验失败都降为 `BatchExtractionError`，与 Layer 3A/4C2 的 best-effort 语义一致

**为什么限定单文档**：
- bundle 的 `source_document_id` 是单值字段（L4C2）
- 跨文档聚合涉及独立的 bundle 决策，不是 batch extraction 的问题
- 调用方仍可按文档遍历调用

### 1.2 L4C3b-02：BatchExtractionResult 携带 per-segment 混合结果

**结构**：
```
BatchExtractionResult:
  doc_id: str
  total_segments: int
  segment_results: list[ExtractionResult | ExtractionError]
  aggregated_specs: list[FactDraftSpec]   # 所有 successes 的 valid_specs 拼接
  metrics: BatchExtractionMetrics
```

调用方可以：
- 直接用 `aggregated_specs` 送 `create_document_bundle`
- 遍历 `segment_results` 检查失败详情
- 用 `metrics` 做调试/观测

### 1.2a L4C3b-17：batch-level max_batch_size 截断

4C3-a 的 ExtractionAgent 只做 **per-segment** 的 `scope.max_batch_size` 截断。多 segment 跨调用时会出现 overshoot：如果 `max_batch_size=10` 且两个 segment 各返回 8 条 valid specs，batch 级 aggregated_specs 会包含 16 条。

**冻结规则**（L4C3b-17）：BatchExtractor 在当前 segment 接受 valid_specs 时做二次截断：

```
remaining = scope.max_batch_size - accumulated_valid_count
if len(result.valid_specs) <= remaining:
    # 全量接受
else:
    # 只接受前 remaining 条，剩余记录为 scope_max_batch_size rejection
    # 下一个 segment 开始时 batch_cap_reached=True
```

**语义对齐**：
- batch 最终的 `accumulated_valid_count <= scope.max_batch_size` 始终成立
- 后续 segment 进入 batch_cap_reached 分支，不再调 LLM（成本节约）
- 这样"per-segment 截断"和"batch-level 截断"在语义上合并为一条硬上限

**rejection 的 proposal_index 语义**（L4C3b-19 冻结）：

4C3-a 的 `ExtractionResult.valid_specs` **不保留** 每条 valid spec 对应的原始 `proposal_index`（ExtractionAgent 在构造 FactDraftSpec 时就丢弃了）。因此 4C3-b batch 截断时无法恢复被截断 specs 的原始 LLM proposal_index。

4C3-b 不扩展 4C3-a 的 ExtractionResult 结构（避免污染 FactDraftSpec 语义）。改为 **扩展 ExtractionRejection 的 proposal_index 约束**：允许 `-1` 作为 batch-local sentinel。

```python
# 4C3-b 对 4C3-a 的合同扩展（L4C3b-21 冻结）
# src/factpy_kernel/agent/extraction/models.py
# ExtractionRejection.__post_init__ 放宽 proposal_index 校验：
#   允许值：proposal_index >= -1
#   语义：
#     >= 0 : 来自原始 LLM 提议的 index（per-segment validation 拒绝）
#     == -1: batch-local sentinel（4C3-b batch 截断产生的聚合 rejection）
```

```python
ExtractionRejection(
    reason="scope_max_batch_size",
    detail=f"batch cap reached at accumulated valid count {scope.max_batch_size}; "
           f"truncated {len(truncated)} specs from segment valid_specs",
    proposal_index=-1,   # batch-local sentinel
)
```

**约定**：
- 4C3-b 产生的 `scope_max_batch_size` rejection 的 `proposal_index == -1`
- 4C3-a 本身产生的 `scope_max_batch_size` rejection（per-segment 截断）的 `proposal_index >= 0`（来自 LLM 原始输出）
- 调用方可以通过 `proposal_index >= 0` 区分两层截断
- `detail` 字段携带 batch 截断的上下文信息（条数、segment 位置）

**4C3-a 测试兼容性**：4C3-a 现有测试（包括 proposal_index >= 0 的正例）保持不变。新增允许值 `-1` 是前向兼容扩展，不破坏任何已有断言。

### 1.3 L4C3b-03：partial failure 不阻断

**实现规则**：
- batch 循环中捕获所有异常（不仅是 `ExtractionError` 的"良性失败"）
- 任何 segment 失败都降为 `ExtractionError(segment_id, error_kind, error_message)`
- 累加到 `segment_results`，继续下一个 segment
- batch 级别只有一种"早期退出"：`scope` 全局违反（如 `max_batch_size` 已累计到上限）
  - 这也是 graceful：remaining segments 记录为 `ExtractionError(kind="batch_cap_reached")`，batch 正常返回

**ExtractionError 合同扩展**（L4C3b-16 冻结）：

4C3-a 的 `ExtractionError.error_kind` 当前只接受：
`llm_unavailable | llm_timeout | instructor_retry_exhausted | config_invalid | dependency_missing`

4C3-b 需要追加两个 kind 到 **4C3-a 的原合同**（不造 batch-local wrapper）：
- `"unexpected"`: batch 循环中捕获的非预期异常（defensive fallback）
- `"batch_cap_reached"`: 累计 valid 数量达到 scope.max_batch_size 后的剩余 segments

**实施方式**：直接修改 `src/factpy_kernel/agent/extraction/models.py` 的 `ExtractionError.error_kind` Literal，追加两个值。这是 4C3-a 合同的前向兼容扩展（只增加允许值，不改变已有行为）。

**不做**：
- 新建 `BatchExtractionError` 的 per-segment 变体
- 新建 wrapper 类包装已有 ExtractionError

**不做（batch 失败处理）**：
- rate limit 自动退避（v1）
- per-segment retry（Instructor 原生 retry 已覆盖最常见场景）
- 全局失败计数阈值（"失败率超过 X% 就停"）—— 这是 4C3-b 的 v2 考虑

### 1.4 L4C3b-04：aggregated_specs 只是拼接

**明确**：
- `aggregated_specs = [spec for result in segment_results if isinstance(result, ExtractionResult) for spec in result.valid_specs]`
- 保持 segment 顺序
- 保持 segment 内 proposal 顺序
- 不做任何 dedupe / 合并 / 消歧
- 同一 `(entity_type, entity_identity, pred_id)` 可能出现多次 → 送 bundle 后 kernel 的 `ingest_key` 幂等机制会处理重复写入

**为什么不在这层 dedupe**：
- dedupe 需要 entity resolution 知识（"李四" vs "Li Si"）
- 是 4C3-c 的核心问题
- 过早 dedupe 会丢失 provenance 信息（哪个 segment 最先提出）

### 1.5 L4C3b-05：轻量 observability

**稳定字段清单**（per segment + per batch）：

Per segment:
```python
SegmentMetric:
  segment_id: str
  model: str | None                # None if ExtractionError
  llm_latency_ms: int | None       # None if ExtractionError
  proposal_count: int              # LLM 原始提议数；0 if error
  valid_count: int                 # 通过 validation 的数
  rejection_count: int             # 被拒绝的数
  error_kind: str | None           # None if success
```

Per batch:
```python
BatchExtractionMetrics:
  doc_id: str
  total_segments: int
  success_segment_count: int       # 返回 ExtractionResult 的数
  error_segment_count: int         # 返回 ExtractionError 的数
  total_proposal_count: int        # sum of proposal_count
  total_valid_count: int           # sum of valid_count
  total_rejection_count: int       # sum of rejection_count
  batch_started_at_ns: int
  batch_finished_at_ns: int
  batch_duration_ms: int
  per_segment_metrics: list[SegmentMetric]
```

**不做**：
- 全局 counter 持久化（每次 batch 独立）
- metrics 导出到 Prometheus / StatsD / OTel
- Langfuse trace / span / generation 结构
- 按 model 分组聚合
- 成本估算 / token counting

这些都留给后续专门的 observability blueprint。

---

## 2. 数据模型

### 2.1 SegmentMetric

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentMetric:
    """Per-segment extraction 的轻量度量。"""
    segment_id: str
    model: str | None                # 实际使用的 LLM 模型名；ExtractionError 时为 None
    llm_latency_ms: int | None       # LLM 调用耗时；ExtractionError 时为 None
    proposal_count: int              # LLM 原始提议数
    valid_count: int                 # 通过 validation 的数
    rejection_count: int             # 被拒绝的数
    error_kind: str | None           # 失败 kind；成功时为 None
```

### 2.2 BatchExtractionMetrics

```python
@dataclass(frozen=True)
class BatchExtractionMetrics:
    """Batch 级别的轻量度量。"""
    doc_id: str
    total_segments: int
    success_segment_count: int
    error_segment_count: int
    total_proposal_count: int
    total_valid_count: int
    total_rejection_count: int
    batch_started_at_ns: int
    batch_finished_at_ns: int
    batch_duration_ms: int
    per_segment_metrics: tuple[SegmentMetric, ...]

    def to_dict(self) -> dict[str, Any]:
        """供调试/日志输出的 JSON-friendly dict。"""
        ...
```

### 2.3 BatchExtractionConfig

```python
@dataclass(frozen=True)
class BatchExtractionConfig:
    """
    Batch-level 配置。与 ExtractionConfig（per-call LLM 配置）分开。
    """
    extraction_config: ExtractionConfig | None = None   # 透传给 per-segment 调用
    max_segments_per_batch: int = 1000                  # 防止意外大 batch 耗尽资源
    early_stop_on_batch_cap_reached: bool = True        # L4C3b-03 的 graceful cap
    # v1 不做 rate limit / retry / concurrency
```

### 2.4 BatchExtractionResult

```python
@dataclass(frozen=True)
class BatchExtractionResult:
    """
    单文档 batch extraction 的结构化返回（L4C3b-02）。
    """
    doc_id: str
    total_segments: int
    segment_results: tuple[ExtractionResult | ExtractionError, ...]
    aggregated_specs: tuple[FactDraftSpec, ...]         # L4C3b-04: 纯拼接，无 dedupe
    metrics: BatchExtractionMetrics

    def success_count(self) -> int: ...
    def error_count(self) -> int: ...
    def has_any_valid(self) -> bool: ...
```

### 2.5 BatchExtractionError

```python
@dataclass(frozen=True)
class BatchExtractionError:
    """
    Batch 级别的失败（如：doc_id 不一致、segments 列表为空、config 非法）。
    不用于 per-segment 失败（那是 segment_results 内的 ExtractionError）。
    """
    doc_id: str | None
    error_kind: Literal[
        "empty_segments",
        "doc_id_mismatch",
        "segments_exceed_limit",
        "config_invalid",
    ]
    error_message: str
```

---

## 3. BatchExtractor

### 3.1 职责

对单文档的 segment 列表顺序执行 `ExtractionAgent.extract_from_segment`，捕获所有失败，聚合 metrics，返回 `BatchExtractionResult` 或 `BatchExtractionError`。

**不做**：
- 不持有 AgentSession（与 ExtractionAgent 同样纯函数式）
- 不 checkpoint
- 不调用 BundleManager
- 不并发

### 3.2 接口

```python
class BatchExtractor:
    """
    单文档 batch extraction orchestrator（L4C3b-01）。

    纯函数式：输入 segments + schema_ir + scope + config，
    输出 BatchExtractionResult 或 BatchExtractionError。

    内部顺序调用 ExtractionAgent，捕获所有失败，聚合 metrics。
    """

    def __init__(
        self,
        *,
        extraction_agent: ExtractionAgent,
        batch_config: BatchExtractionConfig | None = None,
    ) -> None: ...

    def extract_batch(
        self,
        *,
        segments: list[DocumentSegment],
        schema_ir: dict[str, Any],
        scope: AgentScope,
        batch_config: BatchExtractionConfig | None = None,
    ) -> BatchExtractionResult | BatchExtractionError:
        """
        对 segments 顺序执行 extraction，聚合结果。

        步骤：
        1. 前置校验（返回 BatchExtractionError，永不 raise 异常）：
           - segments 非空
           - 所有 segment.doc_id 一致
           - len(segments) <= batch_config.max_segments_per_batch
           - batch_config 合法

        2. 初始化：
           - started_at_ns = time_ns()
           - segment_results = []
           - per_segment_metrics = []
           - aggregated_specs = []
           - batch_cap_reached = False
           - accumulated_valid_count = 0

        3. 对每个 segment 顺序调用：
           a. 如果 batch_cap_reached：
              result = ExtractionError(segment_id, "batch_cap_reached", ...)
              metric = SegmentMetric(...with error_kind="batch_cap_reached")
           b. 否则 try:
              result = extraction_agent.extract_from_segment(
                  segment=segment,
                  schema_ir=schema_ir,
                  scope=scope,
                  config=batch_config.extraction_config,
              )
              根据 result 类型构造 metric
              如果是 ExtractionResult：
                  # L4C3b-17 冻结的 batch-level 截断
                  remaining = scope.max_batch_size - accumulated_valid_count
                  if remaining <= 0:
                      # 理论上不会到这里（已被 batch_cap_reached 拦截）
                      batch_cap_reached = True
                  elif len(result.valid_specs) <= remaining:
                      # 全量接受
                      aggregated_specs.extend(result.valid_specs)
                      accumulated_valid_count += len(result.valid_specs)
                      if accumulated_valid_count >= scope.max_batch_size:
                          batch_cap_reached = True
                  else:
                      # 部分接受：只拿前 remaining 条
                      accepted = result.valid_specs[:remaining]
                      truncated = result.valid_specs[remaining:]
                      aggregated_specs.extend(accepted)
                      accumulated_valid_count += len(accepted)
                      batch_cap_reached = True
                      # truncated 部分追加一条（注意：一条，不是每条一条）
                      # batch-level rejection，proposal_index=-1（L4C3b-19）
                      batch_rejection = ExtractionRejection(
                          reason="scope_max_batch_size",
                          detail=(
                              f"batch cap reached at accumulated valid count "
                              f"{scope.max_batch_size}; truncated {len(truncated)} "
                              f"specs from segment {segment.segment_id}"
                          ),
                          proposal_index=-1,  # batch-local 占位
                      )
                      # 生成新的 ExtractionResult 副本（原对象 frozen）：
                      #   valid_specs = accepted
                      #   rejections = (*result.rejections, batch_rejection)
                      #   metric 的 valid_count / rejection_count 同步调整
                      result = _rebuild_with_batch_truncation(result, accepted, batch_rejection)
           c. except Exception as exc:  # defensive
              result = ExtractionError(segment_id, "unexpected", str(exc))
              metric = SegmentMetric(...with error_kind="unexpected")
           d. segment_results.append(result)
              per_segment_metrics.append(metric)

        4. 构造 BatchExtractionMetrics

        5. 返回 BatchExtractionResult(
               doc_id=...,
               total_segments=len(segments),
               segment_results=tuple(segment_results),
               aggregated_specs=tuple(aggregated_specs),
               metrics=metrics,
           )

        异常处理：
        - 前置校验失败 → 返回 BatchExtractionError（不抛异常）
        - per-segment 任何失败 → 降为 ExtractionError 加入 segment_results
        - ExtractionAgent 本身抛 AgentContractError（config 问题）→ 捕获降为 ExtractionError
        - 其他意外异常 → 捕获降为 ExtractionError(kind="unexpected")
        """
        ...
```

### 3.3 错误分类对照表

| 失败点 | 返回 | 结构化原因 |
|-------|------|-----------|
| 前置校验：segments 空 | `BatchExtractionError` | `empty_segments` |
| 前置校验：doc_id 不一致 | `BatchExtractionError` | `doc_id_mismatch` |
| 前置校验：超过 max_segments_per_batch | `BatchExtractionError` | `segments_exceed_limit` |
| 前置校验：config 非法 | `BatchExtractionError` | `config_invalid` |
| 单 segment：LLM 不可达 | `ExtractionError` in segment_results | `llm_unavailable` |
| 单 segment：依赖缺失 | `ExtractionError` in segment_results | `dependency_missing` |
| 单 segment：意外异常 | `ExtractionError` in segment_results | `unexpected` |
| 单 segment：batch cap reached | `ExtractionError` in segment_results | `batch_cap_reached` |
| 单 segment：成功但 valid_specs 为空 | `ExtractionResult` in segment_results | — |
| 单 segment：成功且有 valid_specs | `ExtractionResult` in segment_results | — |

---

## 4. Orchestrator 扩展

```python
class ReadReviewOrchestrator:
    # ... existing methods ...

    # ── Layer 4C3-b: Batch Extraction ──

    def extract_from_segments(
        self,
        *,
        segments: list[DocumentSegment],
        batch_config: BatchExtractionConfig | None = None,
    ) -> BatchExtractionResult | BatchExtractionError:
        """
        对单文档的多个 segments 批量执行 LLM extraction。

        前置：
        - orchestrator 构造时 batch_extractor 已注入（可选，None 时方法不可用）
        - session.scope 必须已设置
        - 所有 segments.doc_id 必须一致

        Schema source 解析：与 extract_from_segment 一致（L4C3a-17）。

        委托：
        - batch_extractor.extract_batch(
              segments=segments,
              schema_ir=<resolved schema_ir>,
              scope=session.scope,
              batch_config=batch_config,
          )

        不创建 bundle。调用方自行决定是否送 create_document_bundle。
        不 checkpoint（纯函数式）。
        """
        ...

    def extract_and_create_document_bundle(
        self,
        *,
        segments: list[DocumentSegment],
        source_document_name: str,
        batch_config: BatchExtractionConfig | None = None,
    ) -> tuple[
        BatchExtractionResult | BatchExtractionError,
        DraftBundle | None,
    ]:
        """
        便利方法：batch extract + 自动 create bundle。

        时序：
        1. result = extract_from_segments(segments, batch_config)

        2. 如果是 BatchExtractionError → 返回 (error, None)

        3. 如果 result.aggregated_specs 为空 → 返回 (result, None)

        4. bundle = create_document_bundle(
               source_document_id=result.doc_id,
               source_document_name=source_document_name,
               facts=list(result.aggregated_specs),
           )
           → 自动 checkpoint（Layer 4C2 行为）

        5. 返回 (result, bundle)

        注意：
        - 这是便利方法；调用方也可以分两步走
        - aggregated_specs 不做 dedupe（L4C3b-04）；重复条目由 kernel ingest_key 幂等处理
        """
        ...
```

### 4.1 不与 4C3-a 的 `extract_from_segment` 冲突

两者共存：
- `extract_from_segment(segment)` — single segment，4C3-a 的基础能力
- `extract_from_segments(segments)` — batch，4C3-b 新增

4C3-b 在实现上调用 4C3-a 的 ExtractionAgent，不复制业务逻辑。

---

## 5. Tool Registry 扩展

Layer 4C3-a 注册了 41 个 tool。Layer 4C3-b 追加：

```python
"extract_from_segments":                  → orchestrator.extract_from_segments
"extract_and_create_document_bundle":     → orchestrator.extract_and_create_document_bundle
```

Layer 4C3-b 总计 43 个 tool（41 Layer 4C3-a + 2 Layer 4C3-b）。

扩展 `build_layer3a_tool_registry()`，与之前所有 Layer 的累进模式一致。

---

## 6. 实现顺序

```
Step 1: 数据模型
        → SegmentMetric / BatchExtractionMetrics
        → BatchExtractionConfig / BatchExtractionResult / BatchExtractionError
        → 纯 dataclass + 序列化
        → 单测

Step 2: BatchExtractor
        → 前置校验（4 种 BatchExtractionError: empty_segments, doc_id_mismatch, segments_exceed_limit, config_invalid）
        → 主循环 + per-segment 错误捕获
        → batch_cap_reached 逻辑
        → metrics 聚合
        → 单测：mock ExtractionAgent
          - 全部 success
          - 混合 success/error
          - 前置校验失败
          - batch cap reached
          - unexpected exception

Step 3: Orchestrator 扩展
        → extract_from_segments / extract_and_create_document_bundle
        → schema_ir 解析复用 4C3-a 的 helper
        → 集成测试：segments → batch → bundle → review → commit

Step 4: Tool Registry 扩展
        → 43 tool 全量注册验证
```

---

## 7. 目录结构增量

```
src/factpy_kernel/agent/extraction/
  ├── batch.py                   # (新建) BatchExtractor
  ├── metrics.py                 # (新建) SegmentMetric / BatchExtractionMetrics
  ├── models.py                  # (扩展) BatchExtractionConfig / BatchExtractionResult / BatchExtractionError
  └── __init__.py                # (扩展) export new symbols

src/factpy_kernel/agent/
  ├── orchestrator.py            # (扩展) +extract_from_segments +extract_and_create_document_bundle
  └── framework.py               # (扩展) tool registry 43 tools

src/factpy_kernel/tests/
  ├── test_agent_l4c3b_models.py          # (新建)
  ├── test_agent_l4c3b_batch_extractor.py # (新建)
  └── test_agent_l4c3b_workflow.py        # (新建) 端到端：segments → batch → bundle → commit
```

---

## 8. 验收标准

1. **L4C3b-01 单文档约束**：segments 来自不同 doc_id → BatchExtractionError(doc_id_mismatch)；空列表 → empty_segments；超长 → segments_exceed_limit
2. **L4C3b-02 混合结果**：BatchExtractionResult.segment_results 对每个输入 segment 都有一个对应项（成功或失败）
3. **L4C3b-03 partial failure**：单 segment 抛任意异常不阻断 batch；最终返回包含该 segment 的 ExtractionError(kind="unexpected")
4. **L4C3b-04 无 dedupe**：aggregated_specs 按 segment 顺序 + segment 内 proposal 顺序拼接；重复条目不去除
5. **L4C3b-05 metrics 完整**：每个 SegmentMetric 字段正确（成功/失败分支）；BatchExtractionMetrics 的 total/duration 正确
6. **Batch cap reached**：累计 valid_count 达到 scope.max_batch_size 时，后续 segments 记录为 ExtractionError(kind="batch_cap_reached")，batch 正常返回
7. **extract_and_create_document_bundle**：aggregated_specs 为空 → 不创建 bundle；非空 → 正确委托 create_document_bundle
8. **不 checkpoint**：extract_from_segments 调用本身不触发 checkpoint；只有 create_document_bundle 触发（Layer 4C2 行为）
9. **依赖感知**：ExtractionAgent dependency_missing → 第一个 segment 返回 dependency_missing；后续 segments 继续尝试（不短路，因为 v1 不做全局 dependency 预检）
10. **Tool 数量**：43 个
11. **单测 + 集成测试**覆盖

---

## 9. 已知约束

1. **顺序执行**：v1 不做并发。大文档的 batch 会是线性时间累加（N × per-segment latency）。4C3-b 的 v2 可以引入并发（需要 rate limit 配合）。
2. **依赖缺失不短路**：如果 instructor/litellm 未安装，4C3-a 的每个 segment 都会返回 `dependency_missing`，batch 跑完所有 segments。这是代价较小的 trade-off（避免在 batch 层重复 dependency probe）。
3. **batch_cap_reached 是硬截断**：达到 scope.max_batch_size 后剩余 segments 不再尝试 LLM 调用。调用方如果需要"部分提取再审批"，可以拆小 segments 列表。
4. **aggregated_specs 可能有重复**（L4C3b-04）：同一 entity 在多个 segments 中出现会产生多条 FactDraftSpec。送 bundle 后 kernel 的 ingest_key 幂等机制会把 identical (pred_id, e_ref, rest_terms, source) 折叠。但 `source` 中包含 `segment_id`，所以不同 segment 来源的"同一事实"会产生不同 assertion。4C3-c 才会处理真正的语义 dedupe。
5. **Metrics 不持久化**：metrics 只在 BatchExtractionResult 中返回；调用方负责日志记录或后续消费。4C3-b 不写入 ledger / audit trail。
6. **No retry at batch level**：Instructor 原生 retry（max_retries in ExtractionConfig）仍然生效。batch 层不额外加 retry；避免隐藏失败率。
7. **Schema 解析每次重新 resolve**：extract_from_segments 每次调用都解析一次 schema_ir。大文档的 batch 不会缓存（segments 已经来自同一 doc，理论上可优化，留给 v2）。
8. **No concurrent batch extraction safety**：两个线程同时调 extract_from_segments 对同一 session 会各自独立运行——没有锁。与整个 agent 层的单线程假设一致。
9. **扩展 4C3-a 的 ExtractionError.error_kind**（L4C3b-16）：4C3-b 实现时需要修改 `src/factpy_kernel/agent/extraction/models.py` 追加 "unexpected" 和 "batch_cap_reached" 两个 kind。这是 4C3-a 合同的前向兼容扩展，不影响 4C3-a 已有测试。
9a. **放宽 4C3-a 的 ExtractionRejection.proposal_index 校验**（L4C3b-21）：从 `>= 0` 放宽到 `>= -1`，允许 `-1` 作为 batch-local sentinel。同样是前向兼容扩展；所有已有 rejection（proposal_index >= 0）仍然合法。
10. **batch-level 截断使用 proposal_index=-1 占位**（L4C3b-19）：4C3-a 的 `ExtractionResult.valid_specs` 不保留每条 spec 的原始 LLM proposal_index，因此 4C3-b 截断时无法恢复。改为追加一条 `scope_max_batch_size` rejection，`proposal_index=-1`，详情写入 `detail` 字段。调用方可通过 `proposal_index >= 0` 区分 per-segment 截断（来自 4C3-a） vs batch 截断（来自 4C3-b）。
11. **Batch 截断 rejection 是单条聚合**（L4C3b-19）：不为每个被截断的 spec 生成独立 rejection，而是生成一条聚合 rejection（`detail` 中包含截断数量）。这与 per-segment 的"每条 proposal 一条 rejection"不同，因为被截断的是**已通过校验的 valid specs**，不再具有 LLM proposal 级别的身份。

---

## 10. Outcome / Deviations

### Outcome

- 新建 `src/factpy_kernel/agent/extraction/batch.py` 与 `src/factpy_kernel/agent/extraction/metrics.py`
- 扩展 `src/factpy_kernel/agent/extraction/models.py`：
  - `BatchExtractionConfig`
  - `BatchExtractionResult`
  - `BatchExtractionError`
  - `ExtractionError.error_kind += {"unexpected", "batch_cap_reached"}`
  - `ExtractionRejection.proposal_index >= -1`
- 扩展 `ReadReviewOrchestrator`：
  - `extract_from_segments(...)`
  - `extract_and_create_document_bundle(...)`
- 扩展 `build_layer3a_tool_registry()`：41 → 43 tools
- 新增测试：
  - `src/factpy_kernel/tests/test_agent_l4c3b_models.py`
  - `src/factpy_kernel/tests/test_agent_l4c3b_batch_extractor.py`
  - `src/factpy_kernel/tests/test_agent_l4c3b_workflow.py`
- 全量验证通过：`python -m unittest discover -s src/factpy_kernel/tests` → `898 tests`, `1 skipped`

### Deviations

1. `BatchExtractionConfig.early_stop_on_batch_cap_reached=False` 保留为配置面
   - blueprint 的 v1 路径和验收标准只覆盖默认 hard-stop 行为。
   - 实现保留了 `False` 这个配置值，但当前测试与文档主路径只验证默认 `True` 语义。
   - 这是非破坏性扩展，不改变 blueprint 冻结的默认行为。
