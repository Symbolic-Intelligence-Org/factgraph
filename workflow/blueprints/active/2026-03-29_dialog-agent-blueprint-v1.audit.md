# Task Blueprint Audit: 对话式知识录入 Agent (v1)

- Blueprint: [2026-03-29_dialog-agent-blueprint-v1.md](./2026-03-29_dialog-agent-blueprint-v1.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-29 | draft | Blueprint created | 完整架构设计：三层分离（Agent / 适配 / 逻辑基底）、三模式录入（对话 / 文档 / 路由）、三阶段路线图（Phase 1~3） |
| 2026-03-30 | draft | Placed in active blueprints | 从仓库根目录迁入 `docs/blueprints/active/`；补 audit pair；元数据对齐仓库 blueprint 格式 |

## Decision Notes

### 架构分层决策
- Agent 层不持有 Ledger/Store 引用，通过 IR（FactDraft/RuleDraft）与适配层通信
- 逻辑基底零改动原则：所有新逻辑在 Agent 层和适配层
- LLM 路由通过 LiteLLM，不绑定单一 provider

### 写入权限决策
- 所有写操作需用户显式确认，agent 不能自主提交
- BatchCommitEndpoint 采用"尽力提交 + 失败日志"语义（Ledger 无原子批量事务）
- Phase 1 限制单条提交规避部分提交问题

### 引擎路由决策
- Agent 层不直接选择引擎，通过 EngineRoutingHint 推荐
- 用户可覆盖引擎推荐
- 引擎路由影响 confidence_kind 元数据，不影响事实物理存储

### 文档提取决策
- 混合提取：确定性预处理 + 受约束 LLM 精炼 + 人工逐条确认
- 非纯 AI：每条提取结果携带文档来源 provenance（文档 ID、章节、字符偏移）
- DSPy 强制输出符合 SchemaIR 的结构化 JSON

### 分期边界
- Phase 1（MVP）：单条事实对话录入，Markdown 预览，无规则/文档/路由
- Phase 2：规则生成 + 引擎路由 + 文档提取 MVP
- Phase 3：SchemaDraft、高级文档提取、事务支持、LiteLLM 路由策略

### 与现有系统的接口约束
- 复用 `write_protocol.set_field` / `add_field` / `retract_by_asrt`
- 复用 `EvidenceGraph` + `render_evidence_graph_html` 做预览
- 复用 `list_runtime_claims` 做查询
- `_SYSTEM_MANAGED_META_KEYS` 不可由 agent 写入
- `confidence` 值域 `(0, 1]` 遵循现有 frozen contract #9

## Open Questions

| 问题 | 当前立场 | 决策时点 |
|------|---------|---------|
| AgentSession 与 RuntimeSession 生命周期绑定 | 松耦合：持有 session_id 字符串 | Phase 1 |
| 置信度模糊语言映射表固定 vs 可配置 | 先固定内置 | Phase 2 |
| 对话历史持久化 | Phase 1 不持久化 | Phase 3 |
| RuleDraft 可视化方式 | 待定 | Phase 2 |
| 文档提取 LLM 是否需 fine-tuning | 先 prompt engineering + few-shot | Phase 2 |
| SchemaDraft 是否限管理员 | 默认关闭 | Phase 3 |
