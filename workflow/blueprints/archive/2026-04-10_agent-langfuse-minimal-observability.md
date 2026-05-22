# Blueprint: Agent Langfuse 最小接入

- Status: implemented
- Created: 2026-04-10
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Depends on:
  - Layer 4C3-a single-segment LLM extraction (archived)
  - Layer 4C3-b batch extraction (archived)
  - Layer 4C3-c entity resolution (archived)
- Related Modules:
  - `src/factpy_kernel/agent/observability/` (新建)
  - `src/factpy_kernel/agent/extraction/extractor.py` (扩展: hook point)
  - `src/factpy_kernel/agent/extraction/batch.py` (扩展: hook point)
  - `src/factpy_kernel/agent/extraction/resolution.py` (扩展: hook point)
  - `src/factpy_kernel/agent/framework.py` (只读依赖: 复用已有 langfuse_available probe)
  - `src/factpy_kernel/agent/orchestrator.py` (OBS-18: 不改签名)

---

## 0. 目标与边界

**交付目标**：把已有的 4C3-a/4C3-b/4C3-c 稳定 metrics 字段接入 Langfuse，让真实文档跑批时可以在 Langfuse UI 看到三层 trace。不改任何 agent 主合同。

**冻结决策**（本轮锁定，正文围绕这 5 条展开）：

| # | 决策 | 理由 |
|---|------|------|
| OBS-01 | 只接三层：single-segment extraction / batch extraction / resolution | 这三层已有稳定 metrics；其他层无 LLM 调用，tracing 收益低 |
| OBS-02 | 只发稳定字段；不发未收口的中间字段 | 稳定字段清单见 §2.1；防止蓝图和实现漂移 |
| OBS-03 | 不改 agent 主合同；tracer 是可选注入 | 不改 ExtractionAgent / BatchExtractor / EntityResolver 的公开接口；零回归风险 |
| OBS-04 | 不做复杂 dashboard / alerting / cost analysis | 只做"trace 能显示"；dashboard 是 UI 配置，不在蓝图范围 |
| OBS-05 | Langfuse 作为 optional dependency；未安装时降级为 no-op tracer | 与 4C3-a 的 instructor/litellm 依赖感知一致 |

**明确排除**：
- 复杂 dashboard / alerting
- Cost / token budget 跟踪（是独立蓝图）
- OTel span 完整语义（留给 Burr 集成或独立 OTel 蓝图）
- Session-level trace 聚合（当前 trace 只覆盖 extraction 三层）
- Prompt / response 原文上传到 Langfuse（隐私敏感，4C3-a 的 raw_text 仍然在 provenance 中保留审计）
- Burr state machine 集成
- LLM provider-specific 字段（如 OpenAI usage tokens）—— 留给 v2
- Trace 数据持久化到 ledger

---

## 1. 架构约束

### 1.1 为什么不直接用 Langfuse SDK

- 直接在 extractor / batch / resolver 中 `from langfuse import Langfuse` 会：
  - 破坏 optional dependency 原则（4C3-a 刚冻结的）
  - 让业务代码耦合到特定 tracer 实现
  - 单测需要 mock Langfuse，污染测试环境

### 1.2 Tracer Protocol + no-op fallback

引入 agent 层 **tracer protocol**，让业务代码只依赖抽象接口：

```
AgentTracer (Protocol)
  ├── NoOpTracer        — 默认实现，零开销
  ├── LangfuseTracer    — optional，仅在 langfuse 可用时注册
  └── (future) OTelTracer / MultiTracer
```

业务代码只调 `tracer.record_extraction(...)` / `tracer.record_batch(...)` / `tracer.record_resolution(...)`，不知道下层是 Langfuse 还是 no-op。

### 1.3 零侵入原则

- ExtractionAgent / BatchExtractor / EntityResolver 的**现有公开方法签名不变**
- tracer 通过构造时可选注入，默认 no-op
- tracer 调用在业务逻辑结尾（收集完 metrics 之后）
- tracer 异常不能传播到业务代码

---

## 2. 稳定字段清单

### 2.1 三层 Trace 字段（OBS-02 冻结）

**Single-Segment Extraction (4C3-a)**:
```
trace_name: "agent.extraction.single_segment"
attributes:
  segment_id:        str
  doc_id:            str
  model:             str | None
  llm_latency_ms:    int | None
  proposal_count:    int
  valid_count:       int
  rejection_count:   int
  error_kind:        str | None      # "llm_unavailable" | "llm_timeout" | ... | null
  structural_clarity: float          # 来自 segment
  pattern_type:      str             # 来自 segment
```

**Batch Extraction (4C3-b)**:
```
trace_name: "agent.extraction.batch"
attributes:
  doc_id:                   str
  total_segments:           int
  success_segment_count:    int
  error_segment_count:      int
  total_proposal_count:     int
  total_valid_count:        int
  total_rejection_count:    int
  batch_duration_ms:        int
  batch_cap_reached:        bool      # 派生：是否触发 scope.max_batch_size 截断
```

**Entity Resolution (4C3-c)**:
```
trace_name: "agent.extraction.resolution"
attributes:
  doc_id:                   str
  input_spec_count:         int
  output_spec_count:        int
  merge_count:              int
  unique_entity_count:      int
  unique_fact_count:        int
  resolution_duration_ms:   int
  dedupe_enabled:           bool   # OBS-17: 读 effective_config.enable_dedupe
                                    # passthrough 模式（enable_dedupe=False）时为 false
```

### 2.2 明确不发送的字段

- `raw_text` / prompt 原文 / LLM response 原文（隐私）
- `entity_identity` 内容 / `field_values` 内容（可能含 PII）
- `rejections[].detail`（可能包含 LLM 输出片段）
- `merge_events[].fact_key_repr`（可能包含业务实体名）
- `per_segment_metrics` 完整列表（batch trace 只发聚合值）

### 2.3 为什么不发原文

- Langfuse 是 agent 层的观测后端，不是审计底座
- 审计仍然在 `ExtractionProvenance.raw_text` + kernel meta 中保留
- 原文上传涉及隐私 / 合规 / 成本三重问题，v1 全部排除
- v2 可以加 opt-in 原文上传 flag，但不在本蓝图范围

---

## 3. AgentTracer Protocol

### 3.1 接口定义

```python
from typing import Protocol, Any


class AgentTracer(Protocol):
    """
    Agent 层观测 tracer 抽象接口。

    所有方法必须：
    - 永不 raise 异常（tracer 失败不能传播到业务代码）
    - 是同步调用（LangfuseTracer 内部 flush 策略自理）
    - 接受标准字段 dict，不接受业务对象
    """

    def record_single_segment_extraction(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None: ...

    def record_batch_extraction(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None: ...

    def record_resolution(
        self,
        *,
        attributes: dict[str, Any],
    ) -> None: ...
```

### 3.2 NoOpTracer

```python
class NoOpTracer:
    """默认 tracer 实现。所有方法空操作。"""

    def record_single_segment_extraction(self, *, attributes: dict[str, Any]) -> None:
        pass

    def record_batch_extraction(self, *, attributes: dict[str, Any]) -> None:
        pass

    def record_resolution(self, *, attributes: dict[str, Any]) -> None:
        pass
```

### 3.3 LangfuseTracer

```python
class LangfuseTracer:
    """
    Langfuse-backed tracer 实现。

    仅在 langfuse package 可 import 时由 build_tracer() 注册。
    永不直接构造；总是通过 build_tracer(config) 工厂获取。
    """

    def __init__(
        self,
        *,
        public_key: str,
        secret_key: str,
        host: str | None = None,
        release: str | None = None,
    ) -> None:
        """
        lazy 构造 Langfuse client。构造时不抛异常；所有错误延迟到
        record_* 调用时捕获并静默。
        """
        from langfuse import Langfuse   # lazy import
        try:
            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
                release=release,
            )
        except Exception:
            self._client = None

    def record_single_segment_extraction(self, *, attributes: dict[str, Any]) -> None:
        self._safe_trace(
            name="agent.extraction.single_segment",
            attributes=attributes,
        )

    def record_batch_extraction(self, *, attributes: dict[str, Any]) -> None:
        self._safe_trace(
            name="agent.extraction.batch",
            attributes=attributes,
        )

    def record_resolution(self, *, attributes: dict[str, Any]) -> None:
        self._safe_trace(
            name="agent.extraction.resolution",
            attributes=attributes,
        )

    def _safe_trace(self, *, name: str, attributes: dict[str, Any]) -> None:
        """内部 helper。捕获所有异常，tracer 失败不影响业务。"""
        if self._client is None:
            return
        try:
            self._client.trace(name=name, metadata=attributes)
        except Exception:
            # 故意吞异常；observability 失败不能阻断业务
            pass
```

### 3.4 build_tracer 工厂

```python
@dataclass(frozen=True)
class LangfuseConfig:
    public_key: str
    secret_key: str
    host: str | None = None
    release: str | None = None


def build_tracer(
    *,
    langfuse_config: LangfuseConfig | None = None,
) -> AgentTracer:
    """
    构造 tracer。

    策略：
    - langfuse_config is None → NoOpTracer
    - langfuse_config 提供但 langfuse 包未安装 → NoOpTracer（记录 warning）
    - langfuse_config 提供且包可用 → LangfuseTracer
    """
    if langfuse_config is None:
        return NoOpTracer()

    try:
        import langfuse  # noqa: F401
    except ImportError:
        # 静默降级为 NoOpTracer。
        # 调用方可通过 probe_optional_dependencies().langfuse_available 预检依赖是否可用。
        return NoOpTracer()

    return LangfuseTracer(
        public_key=langfuse_config.public_key,
        secret_key=langfuse_config.secret_key,
        host=langfuse_config.host,
        release=langfuse_config.release,
    )
```

---

## 4. 集成点

### 4.1 ExtractionAgent

```python
class ExtractionAgent:
    def __init__(
        self,
        *,
        config: ExtractionConfig | None = None,
        llm_client: Any | None = None,
        tracer: AgentTracer | None = None,   # 新增，默认 None
    ) -> None:
        ...
        self._tracer: AgentTracer = tracer or NoOpTracer()

    def extract_from_segment(self, *, segment, schema_ir, scope, config=None):
        # ... 现有逻辑不变 ...
        result = <existing extraction>  # ExtractionResult or ExtractionError

        # tracer hook（末尾，不影响主逻辑）
        self._emit_single_segment_trace(segment, result)

        return result

    def _emit_single_segment_trace(
        self,
        segment: DocumentSegment,
        result: ExtractionResult | ExtractionError,
    ) -> None:
        """
        从 result 提取稳定字段，调用 tracer。
        永不 raise。
        """
        try:
            if isinstance(result, ExtractionResult):
                attributes = {
                    "segment_id": segment.segment_id,
                    "doc_id": segment.doc_id,
                    "model": result.model,
                    "llm_latency_ms": result.llm_latency_ms,
                    "proposal_count": result.total_proposals,
                    "valid_count": len(result.valid_specs),
                    "rejection_count": len(result.rejections),
                    "error_kind": None,
                    "structural_clarity": segment.structural_clarity,
                    "pattern_type": segment.pattern_type,
                }
            else:  # ExtractionError
                attributes = {
                    "segment_id": segment.segment_id,
                    "doc_id": segment.doc_id,
                    "model": None,
                    "llm_latency_ms": None,
                    "proposal_count": 0,
                    "valid_count": 0,
                    "rejection_count": 0,
                    "error_kind": result.error_kind,
                    "structural_clarity": segment.structural_clarity,
                    "pattern_type": segment.pattern_type,
                }
            self._tracer.record_single_segment_extraction(attributes=attributes)
        except Exception:
            pass   # defensive: tracer 提取逻辑失败也不阻断
```

### 4.2 BatchExtractor

```python
class BatchExtractor:
    def __init__(
        self,
        *,
        extraction_agent: ExtractionAgent,
        batch_config: BatchExtractionConfig | None = None,
        tracer: AgentTracer | None = None,   # 新增
    ) -> None:
        ...
        self._tracer = tracer or NoOpTracer()

    def extract_batch(self, ...) -> BatchExtractionResult | BatchExtractionError:
        # ... 现有逻辑不变 ...
        result = <existing batch extraction>

        if isinstance(result, BatchExtractionResult):
            self._emit_batch_trace(result)
        # BatchExtractionError 不触发 batch trace（因为没有实际执行 batch）

        return result

    def _emit_batch_trace(self, result: BatchExtractionResult) -> None:
        try:
            metrics = result.metrics
            batch_cap_reached = self._detect_batch_cap_reached(result)
            attributes = {
                "doc_id": metrics.doc_id,
                "total_segments": metrics.total_segments,
                "success_segment_count": metrics.success_segment_count,
                "error_segment_count": metrics.error_segment_count,
                "total_proposal_count": metrics.total_proposal_count,
                "total_valid_count": metrics.total_valid_count,
                "total_rejection_count": metrics.total_rejection_count,
                "batch_duration_ms": metrics.batch_duration_ms,
                "batch_cap_reached": batch_cap_reached,
            }
            self._tracer.record_batch_extraction(attributes=attributes)
        except Exception:
            pass

    @staticmethod
    def _detect_batch_cap_reached(result: BatchExtractionResult) -> bool:
        """
        检测 batch 是否触发了 scope.max_batch_size 截断。

        OBS-16 冻结的双表现检测规则：

        真实 batch cap 在 4C3-b 实现中会有两种表现（见 batch.py:96-115）：

        表现 A: 后续 segment 被短路
          - 存在 ExtractionError(error_kind="batch_cap_reached")

        表现 B: 当前 segment 部分接受 + 追加 scope_max_batch_size rejection
          - 存在 ExtractionResult，其 rejections 含
            ExtractionRejection(reason="scope_max_batch_size", proposal_index=-1)
          - 注意：proposal_index=-1 是 L4C3b-19 冻结的 batch-local sentinel
          - per-segment 级别的 scope_max_batch_size rejection (proposal_index >= 0)
            来自 4C3-a 的 per-segment 截断，不是 batch cap

        任一表现出现即认为 batch_cap_reached=True。
        """
        for sr in result.segment_results:
            # 表现 A
            if isinstance(sr, ExtractionError) and sr.error_kind == "batch_cap_reached":
                return True
            # 表现 B
            if isinstance(sr, ExtractionResult):
                for rejection in sr.rejections:
                    if (
                        rejection.reason == "scope_max_batch_size"
                        and rejection.proposal_index == -1
                    ):
                        return True
        return False
```

**重要**：BatchExtractor 内部的 per-segment 调用已经由 ExtractionAgent 自己 emit single-segment trace（4.1 节）。BatchExtractor 不重复 emit，只补充 batch-level aggregate trace。

### 4.3 EntityResolver

```python
class EntityResolver:
    def __init__(
        self,
        *,
        config: ResolutionConfig | None = None,
        tracer: AgentTracer | None = None,   # 新增
    ) -> None:
        ...
        self._tracer = tracer or NoOpTracer()

    def resolve_batch(self, specs, *, config=None) -> ResolutionResult | ResolutionError:
        # ... 现有逻辑不变 ...
        effective_config = config or self._config
        result = <existing resolution using effective_config>

        if isinstance(result, ResolutionResult):
            self._emit_resolution_trace(result, effective_config)
        # ResolutionError 不触发 trace

        return result

    def _emit_resolution_trace(
        self,
        result: ResolutionResult,
        effective_config: ResolutionConfig,
    ) -> None:
        try:
            stats = result.stats
            attributes = {
                "doc_id": result.doc_id,
                "input_spec_count": stats.input_spec_count,
                "output_spec_count": stats.output_spec_count,
                "merge_count": stats.merge_count,
                "unique_entity_count": stats.unique_entity_count,
                "unique_fact_count": stats.unique_fact_count,
                "resolution_duration_ms": stats.resolution_duration_ms,
                # OBS-17 冻结：dedupe_enabled 从 effective_config 直接读取
                # 不从"返回了 ResolutionResult"倒推——resolver 在
                # enable_dedupe=False 时仍然返回 ResolutionResult（passthrough）
                "dedupe_enabled": effective_config.enable_dedupe,
            }
            self._tracer.record_resolution(attributes=attributes)
        except Exception:
            pass
```

---

## 5. Framework 扩展

### 5.1 OptionalDependencyStatus 追加

```python
@dataclass(frozen=True)
class OptionalDependencyStatus:
    pydantic_ai_available: bool
    burr_available: bool
    langfuse_available: bool        # 已有（Layer 1）
    # langfuse 已经在现有清单中；无需新增字段
```

**OBS-06 冻结**：不扩展 `OptionalDependencyStatus`。`langfuse_available` 字段已经存在于 Layer 1 framework.py，本蓝图只是真正使用它。

### 5.2 Orchestrator 不持有 tracer

**OBS-18 冻结**：`ReadReviewOrchestrator` v1 **不新增 tracer 字段**。

理由：
- Orchestrator 当前没有自己需要 emit 的 trace（不发 model call、不做 dedupe）
- 让 orchestrator 持有一个"暂不使用"的字段会给实现者留下多种不一致的 wiring 可能
- extraction 栈的 tracer 应该在构造 ExtractionAgent / BatchExtractor / EntityResolver 时**由调用方直接注入**
- orchestrator 只负责编排，不负责 tracer 分发

**典型调用方 wiring 示例**：

```python
tracer = build_tracer(langfuse_config=LangfuseConfig(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
))

extraction_agent = ExtractionAgent(config=..., tracer=tracer)
batch_extractor = BatchExtractor(extraction_agent=extraction_agent, tracer=tracer)
entity_resolver = EntityResolver(config=..., tracer=tracer)

orchestrator = ReadReviewOrchestrator(
    session=...,
    draft_manager=...,
    # ... 其他 existing params，不新增 tracer 参数 ...
    extraction_agent=extraction_agent,
    batch_extractor=batch_extractor,
    entity_resolver=entity_resolver,
)
```

**三个业务对象共享同一 tracer 实例**。Langfuse SDK 内部做 batching，调用方共享一个 `tracer` 变量即可。

**OBS-07 冻结**：tracer 注入是"构造时注入"而非"调用时传参"。理由：
- 保持 extraction 栈的现有方法签名不变（OBS-03）
- tracer 生命周期与 agent/extractor/resolver 对齐
- 不同 extraction 调用共用同一 tracer（Langfuse client 内部 batching）

### 5.3 未来扩展点

如果后续（例如 Burr 集成）需要 orchestrator-level trace，那时再引入 `orchestrator.tracer` 字段，并在同一蓝图中明确 wiring helper。本蓝图不预留占位字段。

---

## 6. 目录结构增量

```
src/factpy_kernel/agent/
  ├── observability/                    # (新建)
  │   ├── __init__.py
  │   ├── tracer.py                     # AgentTracer Protocol + NoOpTracer
  │   ├── langfuse_tracer.py            # LangfuseTracer + LangfuseConfig + build_tracer
  │   └── docs/
  │       └── README.md
  ├── extraction/
  │   ├── extractor.py                  # (扩展) +tracer param +_emit_single_segment_trace
  │   ├── batch.py                      # (扩展) +tracer param +_emit_batch_trace
  │   └── resolution.py                 # (扩展) +tracer param +_emit_resolution_trace
  └── orchestrator.py                   # (OBS-18) 不改签名，不新增 tracer 字段

src/factpy_kernel/tests/
  ├── test_agent_observability_noop.py          # (新建) NoOpTracer 所有方法不 raise
  ├── test_agent_observability_langfuse.py      # (新建) mock Langfuse client 验证字段
  ├── test_agent_observability_extraction_hooks.py  # (新建) extraction 三层 hook 调用正确
  └── test_agent_observability_build_tracer.py  # (新建) 依赖缺失降级
```

### 6.1 pyproject.toml 变更

```toml
[project.optional-dependencies]
observability = [
    "langfuse>=2.0",
]
```

与 4C3-a 的 extraction / 4C1 的 documents 依赖策略一致：optional dependency，不装则降级为 NoOpTracer。

---

## 7. 实现顺序

```
Step 1: AgentTracer Protocol + NoOpTracer
        → 纯接口定义 + 空实现
        → 单测：所有方法可被调用 + 不 raise

Step 2: LangfuseTracer + build_tracer
        → lazy import
        → _safe_trace 异常捕获
        → 单测：mock langfuse.Langfuse，验证字段透传
        → 单测：import 失败 → NoOpTracer fallback

Step 3: ExtractionAgent 集成
        → 构造时注入 tracer（默认 NoOpTracer）
        → _emit_single_segment_trace 辅助
        → 单测：mock tracer，验证 attributes 字段正确
        → 单测：默认 tracer（NoOp）不影响现有测试
        → 回归 4C3-a 测试全部通过

Step 4: BatchExtractor 集成
        → 构造时注入 tracer
        → _emit_batch_trace 辅助
        → batch_cap_reached 派生逻辑
        → 单测：mock tracer，验证字段
        → 回归 4C3-b 测试全部通过

Step 5: EntityResolver 集成
        → 构造时注入 tracer
        → _emit_resolution_trace 辅助
        → 单测：mock tracer，验证字段
        → 回归 4C3-c 测试全部通过

Step 6: End-to-end wiring 验证
        → orchestrator 构造签名不变（OBS-18）
        → 验证 probe_optional_dependencies 的 langfuse_available 真实工作
        → 集成测试：调用方按 §5.2 wiring 示例构造 → end-to-end 三层 trace 都被触发
        → 集成测试：所有业务对象共享同一 tracer 实例时，Langfuse client 被复用
```

---

## 8. 验收标准

1. **OBS-01 三层覆盖**：single-segment / batch / resolution 三层各有独立 trace
2. **OBS-02 字段稳定**：三层 trace 的 attributes 只包含 §2.1 清单中的字段；无额外字段
3. **OBS-03 零回归**：4C3-a/4C3-b/4C3-c 现有测试全部通过；ExtractionAgent / BatchExtractor / EntityResolver 现有方法签名未变
4. **OBS-04 无 dashboard**：蓝图不包含 dashboard 配置；只保证 trace 写入
5. **OBS-05 依赖感知**：未安装 langfuse → build_tracer 返回 NoOpTracer；LangfuseTracer 构造不抛异常
6. **Tracer 异常不传播**：mock 一个 raise 异常的 tracer，业务方法仍正常返回
7. **原文不上传**：trace attributes 中不含 raw_text / entity_identity 内容 / field_values 内容 / rejections[].detail
8. **batch_cap_reached 双表现检测**（OBS-16）：检测两种真实表现中的任一种：
   - 表现 A：`ExtractionError(error_kind="batch_cap_reached")`
   - 表现 B：`ExtractionResult` 含 `ExtractionRejection(reason="scope_max_batch_size", proposal_index=-1)`
   单测必须覆盖两种情形都能正确置 `true`
9. **Build tracer 降级**：未装 langfuse → NoOpTracer；langfuse 可用但 config 非法 → tracer 构造不抛，内部 client 为 None，trace 调用静默
10. **单测 + 集成测试**覆盖

---

## 9. 已知约束

1. **NoOpTracer 是默认**：生产部署需要显式提供 LangfuseConfig，否则所有 trace 被丢弃
2. **Trace 是 best-effort**：tracer 异常、网络错误、Langfuse 后端不可用都不影响业务；意味着 trace 数据可能不完整
3. **不保证 trace 完整性**：LangfuseTracer 没有 retry / buffer / persistent queue；依赖 Langfuse SDK 自身的 flushing 策略
4. **Span 关联**：三层 trace 目前是独立的，没有 parent-child span 关系。如果 batch 有 10 个 segment，会产生 1 个 batch trace + 10 个 single-segment trace 互相独立。Langfuse UI 可以按 doc_id 聚合查看。完整 span tree 留给 OTel 或 Burr 集成蓝图
5. **不覆盖非 extraction 路径**：read / write / rule authoring / retract 等路径都不发 trace。这些路径没有 LLM 调用，tracing 的价值相对低
6. **配置管理**：LangfuseConfig 的 public_key / secret_key 由调用方从环境变量或 secret manager 读取。蓝图不指定读取方式
7. **并发安全**：Langfuse SDK 线程安全，但 agent 层目前是单线程假设；两者不冲突
8. **版本锁定**：langfuse>=2.0。Langfuse 1.x 和 2.x API 差异大；lazy import 可能在运行时才发现版本不兼容
9. **Trace 数据保留**：Langfuse 后端自行管理；agent 层不关心
10. **成本敏感**：Langfuse 对 trace 数量按量计费；大批量跑时调用方应自行评估。v1 不做采样率控制，v2 可加

---

## 10. Outcome / Deviations

### Outcome

- 新增 `src/factpy_kernel/agent/observability/` 子包，落地 `AgentTracer`、`NoOpTracer`、`LangfuseTracer`、`LangfuseConfig`、`build_tracer(...)`
- `ExtractionAgent` / `BatchExtractor` / `EntityResolver` 都支持构造时可选注入 tracer，默认 `NoOpTracer`
- single-segment / batch / resolution 三层都按冻结字段发 trace，且 tracer 异常永不传播
- `langfuse` 作为新的 optional dependency 落在 `pyproject.toml` 的 `observability` extra 中
- 模块文档、仓库 docs 索引与测试入口已同步更新

### Deviations

- 无产品语义偏差。实现采用 `importlib.import_module("langfuse")` 的 helper 进行 lazy import，以便单测稳定 mock；这不改变蓝图冻结的 dependency-aware / no-op fallback 合同。
