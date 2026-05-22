# Audit Log: dialog-agent-blueprint-v1.1-delta

## 2026-04-09 — 初始 delta 创建

### 讨论上下文

基于两轮深度讨论（产品落地审计 + agent 能力设计 + 技术栈调研 + 代码 API surface 校准），对 v1 蓝图进行系统性修订。

### 关键讨论参与方输入

**用户（架构所有者）提出的 5 条核心修正**：

1. **R3 explain 默认载体**：从 summary→narrative→NL 改为 summary→steps→tree/timeline。理由：`explain_runtime_steps()` 已线性化三引擎，最适合 agent 消费。
2. **W2 撤回拆分**：W2a（精确撤回，P1）+ W2b（语义撤回，P2/P3）。理由：无 assertion→candidate 反向索引。
3. **W3 native-first**：ephemeral rules 仅 native evaluate 生效。不应承诺 ProbLog/PyReason rule authoring。
4. **I2+M1 前移**：candidate review + session 恢复是核心 loop，不是可选项。accept 需要完整 candidate object。
5. **W4 Stage 1 保持确定性**：不用 LLM 替代分段。offset 是审计链锚点。

**用户进一步收紧的 4 点**：

1. Candidate readback 不是低成本端点——support_artifact ≠ 完整 CandidateSet。P0 做 agent-side 持久化。
2. Lineage Index 不重复已有 meta（accept 时已写 candidate_id/candidate_key 等）。真正缺的是 premise→candidate 反向边。先做 session-scoped scan。
3. W2b 再后移——依赖 truth maintenance 语义。
4. Steps detail 跨引擎不一致——stable fields vs unstable detail depth。

**用户的执行顺序指导**：

> 下一步不该先推进生成逻辑，应该先推进 agent 的会话、draft、恢复、tool 调用和 steps-first explain 这套底盘。生成是第二层，不是第一层。

### 技术栈决策记录

| 决策 | 选项考量 | 最终选择 | 排除原因 |
|------|---------|---------|---------|
| Agent framework | PydanticAI / LangGraph / CrewAI / smolagents | PydanticAI | LangGraph 过度工程化+LangSmith锁定；CrewAI 控制粒度不足；smolagents 无持久化 |
| State machine | Burr / LangGraph / 自建 | Burr (Apache) | LangGraph 同上；自建缺追踪UI和持久化 |
| Structured output | Instructor / DSPy / BAML / Outlines | Instructor | DSPy 学习曲线高（降级为优化器）；BAML 需额外DSL；Outlines 仅本地模型 |
| LLM gateway | LiteLLM / OpenRouter / Portkey | LiteLLM (保持v1) | OpenRouter 5%加价+数据过第三方；Portkey 商业 |
| Observability | Langfuse / LangSmith / Braintrust / Phoenix | Langfuse | LangSmith 闭源；Braintrust SaaS-only；Phoenix 评估能力弱 |
| PDF extraction | PyMuPDF / Docling / LlamaParse / Unstructured | PyMuPDF + Docling | LlamaParse $3000/百万页+SaaS；Unstructured 复杂表格75% |

### 市场调研基础

- 调研范围：10 个 agent 框架、3 个 LLM gateway、5 个结构化输出库、4 个 state manager、5 个文档提取工具、5 个 observability 平台
- 数据来源：GitHub stars/release cadence、Nextbuild 90-day benchmark、Gartner reviews、社区批评
- 详细调研报告：见对话记录（未单独持久化为文档）

### 审计报告交叉引用

产品落地审计报告 (`docs/references/working/product-readiness-audit-2026-04-09.md`) 中识别的 14 条隐患对 agent 设计的影响已在 delta 文档 Section 8 中显式映射。
