# Docs Index

本目录承载**项目级非 workflow 文档**(per Q1 §4.1 split-with-retention)。工作流治理已迁移至 [`workflow/`](/Users/zhenzhili/hnsm-backend/workflow/)。

## 入口

| 文件 / 目录 | 说明 |
|---|---|
| [`SECURITY.md`](./SECURITY.md) | v0.1 kernel-only wheel 的 local secret handling、`.env` hygiene、release-surface expectations |
| [`SECURITY_monorepo.md`](./SECURITY_monorepo.md) | Monorepo-specific 安全:kernel API key auth、`FACTPY_KERNEL_API_KEYS`、service v1 routes 认证约定 |
| [`api/openapi.yaml`](./api/openapi.yaml) | Service API spec(技术契约)|
| [`official/kernel/`](./official/kernel/) | `factgraph` 官方用户 quickstart 文档(公开 SDK / kernel 发布面)|
| [`references/external/`](./references/external/) + [`references/bridges/`](./references/bridges/) | **Parked**:等待迁移到 `~/obsidian_workspace/`(per Q1 §4.3,obsidian integration slice 未启动)|

## 工作流治理

- [`workflow/AGENTS.md`](/Users/zhenzhili/hnsm-backend/workflow/AGENTS.md) — workflow 治理总入口
- [`workflow/CADENCE.md`](/Users/zhenzhili/hnsm-backend/workflow/CADENCE.md) — Audit-to-Archive Cadence(大型工作流任务的方法论)
- [`workflow/blueprints/README.md`](/Users/zhenzhili/hnsm-backend/workflow/blueprints/README.md) — 任务蓝图工作流、8 状态机、模板与归档规则

## 模块实现真相

- [`src/factgraph/AGENTS.md`](/Users/zhenzhili/hnsm-backend/src/factgraph/AGENTS.md) — `src/factgraph/*/docs/` 的最小结构约定
- 各模块 `docs/README.md` 是该模块当前实现真相

## 约定

新增**项目级非 workflow 文档**入口时(security、api、public 用户文档等)更新本文件。Workflow 治理内容**不应**回流到 docs/ — 应在 `workflow/` 内对应 pillar 落地。
