# Agent Observability 文档

本目录记录 `src/agent/observability` 的当前实现口径，覆盖 Langfuse 最小接入所需的 tracer 抽象、默认 no-op 实现和可选 Langfuse backend。

## Scope

- `AgentTracer`
- `NoOpTracer`
- `LangfuseConfig`
- `LangfuseTracer`
- `build_tracer(...)`

## Responsibilities

- 为 extraction 三层提供统一的 agent-layer tracing 抽象
- 提供默认零开销的 `NoOpTracer`
- 在 `langfuse` 可用且显式提供配置时构造 `LangfuseTracer`
- 保证 tracer 失败、Langfuse backend 不可用或配置异常时不会影响业务路径

## Non-responsibilities

- 不做 dashboard / alerting / sampling / token accounting
- 不建立 parent-child span 关系
- 不上传原始 prompt、response 或文档原文
- 不覆盖 read/write/rule/retract 等非 extraction 路径

## Limitations

- `build_tracer()` 在未提供配置或缺少 `langfuse` 包时静默降级为 `NoOpTracer`
- `LangfuseTracer` 没有本地 buffering 或 retry 队列；只依赖 SDK 自身行为
- 当前 trace 只发稳定聚合字段，不发送可能携带 PII 的业务内容

## Test Entry Points

- `src/agent/tests/test_agent_observability_noop.py`
- `src/agent/tests/test_agent_observability_build_tracer.py`
- `src/agent/tests/test_agent_observability_langfuse.py`
- `src/agent/tests/test_agent_observability_extraction_hooks.py`
