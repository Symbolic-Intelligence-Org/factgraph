# Agent Observability 文档

本目录记录 `src/agent/observability` 的当前实现口径,覆盖 Langfuse 最小接入所需的 tracer 抽象、默认 no-op 实现和可选 Langfuse backend。

## Scope

- `AgentTracer`(Protocol)
- `NoOpTracer`(默认实现)
- `LangfuseConfig`(frozen dataclass)
- `LangfuseTracer`(Langfuse backend)
- `build_tracer(...)`(factory)

## API Contract

`AgentTracer` 是 Protocol,定义 3 个 record 方法,全部 keyword-only:

```python
def record_single_segment_extraction(*, attributes: dict[str, Any]) -> None
def record_batch_extraction(*, attributes: dict[str, Any]) -> None
def record_resolution(*, attributes: dict[str, Any]) -> None
```

每方法对应 extraction 流程的一个抽象阶段:

- **single_segment** —— 单段(单 chunk / 单 LLM 调用)extraction
- **batch** —— 多段批处理 extraction(含 entity context header / gleaning 等批协议)
- **resolution** —— entity resolution / dedupe / alias merge

`attributes` 字段约定:

- 必含稳定聚合字段:`{model, input_token_count, output_token_count, latency_ms}` 或类似
- 可选诊断字段:`{document_id, segment_id, batch_id, error_class, retry_count}`
- **不**含:raw prompt、raw response、文档原文、PII —— 这些走 dedicated extraction logging,而非 tracer

## Default Behavior

`NoOpTracer` 是 zero-overhead 默认实现:所有 record 方法直接 `return None`。设计原则:

- 业务路径**永远不**因 tracer 失败而失败
- 默认配置(无 Langfuse)= no-op,无外部依赖
- 任何环境变量 / 配置文件**不**自动启用 Langfuse;必须 explicit `build_tracer(langfuse_config=...)` 调用

## Langfuse Integration

### Configuration

`LangfuseConfig`(frozen dataclass):

```python
@dataclass(frozen=True)
class LangfuseConfig:
    public_key: str
    secret_key: str
    host: str | None = None     # default Langfuse cloud
    release: str | None = None  # 可选,标记 release version
```

### Build Decision Tree

```
build_tracer(langfuse_config=None)
  └─ return NoOpTracer  ✓ default

build_tracer(langfuse_config=LangfuseConfig(...))
  ├─ try: import langfuse
  │   ├─ ImportError → return NoOpTracer  (silent degrade)
  │   └─ success → return LangfuseTracer(...)
```

调用方**不需**捕获 ImportError;`build_tracer` 自身保证返回有效 `AgentTracer`。

### Trace Name Mapping

| record method | Langfuse trace name |
|---|---|
| `record_single_segment_extraction` | `agent.extraction.single_segment` |
| `record_batch_extraction` | `agent.extraction.batch` |
| `record_resolution` | `agent.extraction.resolution` |

`attributes` dict 直接传入 Langfuse `client.trace(name=..., metadata=attributes)`。

### Safe-Trace Guarantee

`LangfuseTracer._safe_trace(...)` 包裹 Langfuse 调用:

```python
try:
    self._client.trace(name=name, metadata=attributes)
except Exception:
    return  # 静默吞;业务不阻塞
```

如果 Langfuse client 在初始化时失败(网络 / auth 错),`self._client = None`,后续 record 直接 return,无 raise。

## Cross-Module Tracing Flow

Tracer 由 `src/agent/extraction` 三层调用,典型 flow:

```
src/agent/extraction/single_segment.py
  └─ tracer.record_single_segment_extraction(attributes={...})

src/agent/extraction/batch.py
  └─ tracer.record_batch_extraction(attributes={...})

src/agent/extraction/resolution.py
  └─ tracer.record_resolution(attributes={...})
```

Tracer 通过 dependency injection 传入(extraction agent 构造时);**不**通过 module global 或 thread local。这保证:

- 测试时可注入 `NoOpTracer`,不需 mock Langfuse
- 不同 extraction session 可用不同 tracer 实例

## Responsibilities

- 为 extraction 三层提供统一的 agent-layer tracing 抽象
- 提供默认零开销的 `NoOpTracer`
- 在 `langfuse` 可用且显式提供配置时构造 `LangfuseTracer`
- 保证 tracer 失败、Langfuse backend 不可用或配置异常时不会影响业务路径

## Non-Responsibilities

- 不做 dashboard / alerting / sampling / token accounting(由 Langfuse / 外部 system 拥有)
- 不建立 parent-child span 关系(每 record 是 flat trace,Langfuse 自身可后期 group)
- 不上传原始 prompt、response 或文档原文(privacy / cost boundary)
- 不覆盖 read / write / rule / retract 等非 extraction 路径
- 不处理 `kernel.application` capability runtime 的 tracing(application 层无 tracer 抽象;若需要,走 separate observability layer)

## Limitations

- `build_tracer()` 在未提供配置或缺少 `langfuse` 包时静默降级为 `NoOpTracer`(无 warning)
- `LangfuseTracer` 没有本地 buffering 或 retry 队列;只依赖 SDK 自身行为
- 当前 trace 只发稳定聚合字段,不发送可能携带 PII 的业务内容
- `release` 字段需调用方手动维护;不自动从 git tag / version 推断
- `LangfuseConfig` 是 frozen dataclass;运行时切换 host / key 需重新 `build_tracer(...)` 构造新实例

## Test Entry Points

- `src/agent/tests/test_agent_observability_noop.py` —— NoOp 行为
- `src/agent/tests/test_agent_observability_build_tracer.py` —— factory 决策树
- `src/agent/tests/test_agent_observability_langfuse.py` —— Langfuse backend(含 import / init / trace failure 路径)
- `src/agent/tests/test_agent_observability_extraction_hooks.py` —— extraction 三层 hook 集成
