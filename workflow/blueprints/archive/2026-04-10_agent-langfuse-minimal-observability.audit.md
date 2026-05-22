# Audit Log: Agent Langfuse 最小接入

## 2026-04-10 — 初始设计

### 设计依据

基于 v1.1-delta §1.2 (Langfuse 选型) + 4C3-b/4C3-c 已落地的稳定 metrics 字段 + 用户指导（只接三层、稳定字段、不改主合同）。

### 用户冻结决策

| # | 决策 | 来源 |
|---|------|------|
| OBS-01 | 只接三层：single-segment / batch / resolution | 用户 2026-04-10 指导 |
| OBS-02 | 只发稳定字段；不发未收口字段 | 用户 2026-04-10 指导 |
| OBS-03 | 不改 agent 主合同；tracer 是可选注入 | 用户 2026-04-10 指导 |
| OBS-04 | 不做复杂 dashboard / alerting / cost analysis | 用户 2026-04-10 指导 |
| OBS-05 | Langfuse 作为 optional dependency；未安装时降级为 no-op tracer | 用户 2026-04-10 指导 + 与 4C3-a instructor/litellm 依赖策略一致 |

### 关键设计决策

| # | 决策 | 理由 |
|---|------|------|
| OBS-06 | 不扩展 OptionalDependencyStatus（复用已有 langfuse_available 字段） | Layer 1 framework.py 已经有此字段；本蓝图只是真正使用它 |
| OBS-07 | tracer 构造时注入，不改现有方法签名 | OBS-03 的具体实现；保持方法签名稳定，tracer 生命周期与业务对象对齐 |
| OBS-08 | NoOpTracer 是默认实现 | 未注入 tracer 的调用路径不应为了 tracing 付出任何开销 |
| OBS-09 | Tracer 异常永不传播到业务代码 | observability 失败不能阻断业务；defensive 捕获 |
| OBS-10 | 不上传原文字段（raw_text / entity_identity / field_values / rejections[].detail） | 隐私 / 合规 / 成本三重考虑；审计底座仍在 ExtractionProvenance |
| OBS-11 | 三层 trace 独立，不建立 parent-child span 关系 | 完整 span tree 需要 OTel 或 Burr 集成；最小接入不做 |
| OBS-12 | 不覆盖 read / write / rule authoring / retract 路径 | 这些路径无 LLM 调用，tracing 收益低；保持最小集 |
| OBS-13 | BatchExtractor 不重复 emit per-segment trace | ExtractionAgent 自己负责 single-segment trace；batch 只补 aggregate trace |
| OBS-14 | LangfuseError → tracer 构造不抛，内部 client 为 None，trace 调用静默 | 配置错误不应导致业务启动失败 |
| OBS-15 | 版本锁定 langfuse>=2.0 | Langfuse 1.x 和 2.x API 差异大；锁定 2.x 系列 |

## 2026-04-10 — 实现前收口修订 (3 处)

### 修订来源

用户 code review 发现 2 处 P1 + 1 处 P2 合同不一致。

### 修订记录

| # | 修订 | 理由 |
|---|------|------|
| OBS-16 | **冻结** batch_cap_reached 双表现检测：同时检查 ExtractionError(batch_cap_reached) 和 ExtractionResult 中 ExtractionRejection(scope_max_batch_size, proposal_index=-1) | 4C3-b batch.py:96-115 的真实实现会在当前 segment 追加 rejection 而非产生 error；单一检查漏报 |
| OBS-17 | **冻结** dedupe_enabled 从 effective_config.enable_dedupe 读取，不从"返回 ResolutionResult"倒推 | resolution.py:129 在 enable_dedupe=False 时仍返回 ResolutionResult（passthrough）；倒推会把 passthrough 误标为 true |
| OBS-18 | **冻结** ReadReviewOrchestrator v1 不新增 tracer 字段；tracer 由调用方直接注入到 extraction 栈 | orchestrator 当前无自身 trace 点；占位字段会让 Step 6 wiring 有多种不一致落法 |

### 合同对齐验证

确认以下已实现合同在本蓝图中正确引用：
- `SegmentMetric` (4C3-b metrics) ✓
- `BatchExtractionMetrics` (4C3-b) ✓
- `ResolutionStats` (4C3-c) ✓
- `ExtractionResult / ExtractionError` (4C3-a) ✓
- `BatchExtractionResult` (4C3-b) ✓
- `ResolutionResult` (4C3-c) ✓
- `ExtractionAgent / BatchExtractor / EntityResolver` 构造签名（4C3-a/b/c，仅追加可选 tracer 参数） ✓
- Layer 1 `OptionalDependencyStatus.langfuse_available` 字段 ✓

### 边界声明

Langfuse 最小接入明确不涉及：
- 复杂 dashboard / alerting / visualization
- Cost / token budget 跟踪（独立蓝图）
- OTel span 完整语义（留给 Burr 或 OTel 专门蓝图）
- Session-level trace 聚合
- Prompt / response 原文上传
- Burr state machine 集成
- Provider-specific metrics（OpenAI tokens、Anthropic usage 等）
- Trace 数据持久化到 ledger
- 采样率控制 / trace filtering
- 自动错误告警 / PagerDuty 集成

### 为什么现在做 Langfuse

在 agent 能力面完整闭环后，最近瓶颈是"真实文档跑批时看不清"。具体痛点：
1. 4C3-b 批量跑一个文档时无法快速看到哪些 segment 失败了
2. 4C3-c 的 merge_count 现在只在 ResolutionResult 返回值里，跑完就丢
3. 不同 model 的 llm_latency_ms 分布不可见
4. rejection_count 高时不知道是 schema / scope / field_type 哪层问题

这些痛点在 Langfuse trace 中会立即可见。dashboard / alerting 是下一步的事，本蓝图只保证 trace 数据能进入 Langfuse。

### 为什么不先做 Burr

- Burr 是状态机显式化，当前主要痛点是"观测缺失"而不是"状态机缺失"
- Langfuse 的数据会告诉我们真正需要什么样的 state machine
- Burr 集成会触及所有 Layer；Langfuse 只触及 extraction 三层
- 风险和收益不对称

## 2026-04-10 — 实现收口

### 结果

- observability 子包已落地：`AgentTracer` / `NoOpTracer` / `LangfuseTracer` / `build_tracer(...)`
- `ExtractionAgent` / `BatchExtractor` / `EntityResolver` 均已完成 tracer hook 接入
- 4 个新增测试文件覆盖 no-op、builder fallback、Langfuse mock 行为，以及 extraction 三层 hook / shared tracer wiring

### 偏差

- 无架构级偏差。实现以 `importlib.import_module()` helper 替代伪代码中的直接 `import langfuse`，仅为测试注入与 lazy import 稳定性服务，不改变 OBS-05 / OBS-14 / OBS-15 合同。
