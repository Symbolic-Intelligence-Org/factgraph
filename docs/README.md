# Docs Index

本目录用于收口几类不同职责的文档：

- 稳定原则与系统边界
- 参考/桥接/工作材料
- 任务级蓝图与审计
- 历史蓝图与提炼记录

仓库级 operational memory 已迁移到 [memory/README.md](/Users/zhenzhili/hnsm-backend/memory/README.md)，不再放在 `docs/` 根目录。

## 入口

- [architecture_principles.md](/Users/zhenzhili/hnsm-backend/docs/architecture_principles.md)
  - 项目的稳定设计哲学、系统边界和长期方向。
- [SECURITY.md](/Users/zhenzhili/hnsm-backend/docs/SECURITY.md)
  - 本地 secret handling、kernel API key 认证约定与密钥轮换 checklist。
- [../LICENSE](/Users/zhenzhili/hnsm-backend/LICENSE)
  - 项目代码的 Apache License 2.0 文本。
- [../CONTRIBUTING.md](/Users/zhenzhili/hnsm-backend/CONTRIBUTING.md)
  - 贡献者工作流、开发环境、测试基线、质量检查与安全入口。
- [../CODE_OF_CONDUCT.md](/Users/zhenzhili/hnsm-backend/CODE_OF_CONDUCT.md)
  - 仓库协作行为准则。
- [blueprints/README.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/README.md)
  - 任务蓝图工作流、状态机、模板与标准归档 / reconstructed 归档规则。
- [decisions/README.md](/Users/zhenzhili/hnsm-backend/docs/decisions/README.md)
  - 设计审计后的 load-bearing Q-resolution 记录；先锁具体设计问题,再进入 blueprint 或实现。
- [module_docs_convention.md](/Users/zhenzhili/hnsm-backend/docs/module_docs_convention.md)
  - 模块文档最小结构要求、写作约定、触发更新的场景、起点模板。
- [references/README.md](/Users/zhenzhili/hnsm-backend/docs/references/README.md)
  - 外部比较、桥接提炼、design-point research notes 和工作参考材料的管理规则；可作为 blueprint 输入材料，但不是当前实现真相。
  - Current design-point entry: [Rule / Query / Inference head semantics](/Users/zhenzhili/hnsm-backend/docs/references/working/design-points/rule-query-inference-head-semantics.zh.md) records a post-release optimization direction, not current implementation truth.
- [../examples/README.md](/Users/zhenzhili/hnsm-backend/examples/README.md)
  - 仓库示例与 notebook 的维护索引；说明哪些 demo 是当前口径、哪些是低层 spike、哪些是导出产物。
- [official/kernel/index.md](/Users/zhenzhili/hnsm-backend/docs/official/kernel/index.md)
  - `factpy-kernel` 官方用户 quickstart 文档入口；kernel-only, 不包含 service、agent、extraction 或 domain bundle 文档。
- [memory/README.md](/Users/zhenzhili/hnsm-backend/memory/README.md)
  - 仓库级 operational memory 说明；定义 handoff 与 `current.md` 的边界。
- [memory/current.md](/Users/zhenzhili/hnsm-backend/memory/current.md)
  - 当前 canonical operational memory 入口；用于新 session 恢复上下文，不是模块真相，也不替代 active blueprint。
- [blueprint_history/README.md](/Users/zhenzhili/hnsm-backend/docs/blueprint_history/README.md)
  - 旧蓝图归档区的说明与使用边界。

## 当前实现文档

以下模块目录中的 `docs/` 才是对应实现的当前真相：

- [src/kernel/core/docs/01_architecture.en.md](/Users/zhenzhili/hnsm-backend/src/kernel/core/docs/01_architecture.en.md)
  - core semantics scaffolding docs live at
    [src/kernel/core/semantics/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/core/semantics/docs/README.md).
- [src/kernel/application/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/application/docs/README.md)
  - application runtime authority docs, including the application-layer walker docs at `src/kernel/application/walker/docs/README.md`.
- [src/service/docs/README.md](/Users/zhenzhili/hnsm-backend/src/service/docs/README.md)
  - service HTTP surface 与 audit static site delivery contract 的当前实现文档。
- [src/kernel/sdk/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/sdk/docs/README.md)
- [src/kernel/authoring/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/authoring/docs/README.md)
- [src/kernel/adapters/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/adapters/docs/README.md)
- [src/kernel/audit/docs/README.md](/Users/zhenzhili/hnsm-backend/src/kernel/audit/docs/README.md)
  - audit package 读取/查询/DTO、EvidenceGraph 统一 explainability DTO，以及 audit package contract 的当前实现文档。
- [src/domains/ecss/docs/README.md](/Users/zhenzhili/hnsm-backend/src/domains/ecss/docs/README.md)
  - ECSS domain preset、compliance row assembly、写侧 helper 边界的当前实现文档。
- [src/agent/docs/README.md](/Users/zhenzhili/hnsm-backend/src/agent/docs/README.md)
  - agent 控制面、draft/checkpoint、candidate payload cache、read-first review loop、Layer 3A 结构化最小写入、W2a 精确撤回、Layer 4A/4B 规则 authoring + 保守引擎路由，以及 Layer 4C1-4C3 文档提取/去重链路的当前实现文档。
- [src/agent/documents/docs/README.md](/Users/zhenzhili/hnsm-backend/src/agent/documents/docs/README.md)
  - agent Layer 4C1/4C2 document surface：deterministic staging、segment provenance、bundle review/approval carrier，以及 merged provenance carrier 的当前实现文档。
- [src/agent/extraction/docs/README.md](/Users/zhenzhili/hnsm-backend/src/agent/extraction/docs/README.md)
  - agent Layer 4C3 extraction surface：single-segment / batch LLM extraction、schema-constrained response model、deterministic validation、batch metrics，以及 single-document entity resolution 的当前实现文档。
- [src/agent/extraction/docs/USAGE.md](/Users/zhenzhili/hnsm-backend/src/agent/extraction/docs/USAGE.md)
  - `extract_document()` Python 产品 API 使用手册：最小示例、参数语义、返回值结构、常见失败诊断、已知限制与模型推荐。
- [src/agent/service/docs/05_extraction.md](/Users/zhenzhili/hnsm-backend/src/agent/service/docs/05_extraction.md)
  - `POST /v1/extraction/documents` 的 DTO 契约：请求 / 200 / 422 / 500 envelope 与 curl 示例。
- [src/service/docs/06_frontend_integration.md](/Users/zhenzhili/hnsm-backend/src/service/docs/06_frontend_integration.md)
  - 前端/BFF 集成指南；envelope 解包、典型调用链路、HTTP 状态码速查表。
- `docs/api/openapi.yaml` — **归属待定**(deferred to OS-prep)
  - namespace split 后 service 拆出 kernel,extraction 路由迁至 agent.service,原 yaml 不再与单一 live FastAPI spec 一致;归属决定(kernel-only / agent-only / composed)与重新生成方式见 OS-prep blueprint。漂移守卫 `scripts/export_openapi.py` 同此降级。
- [src/agent/observability/docs/README.md](/Users/zhenzhili/hnsm-backend/src/agent/observability/docs/README.md)
  - agent extraction 三层的 Langfuse 最小 observability：tracer 抽象、NoOp fallback、可选 Langfuse backend 与稳定字段边界。

## 工作流摘要

1. 新任务先建立蓝图与 audit。
2. 边界收口后将蓝图状态切到 `scoped`，再开始多轮实现。
3. 实现过程中如需扩边界，先改蓝图和 audit，再改代码。
4. session continuity 材料进入 `memory/`，不要回流到 `docs/` 根目录。
5. 完成后更新对应模块 docs，并在必要时补主索引。
6. 最后将蓝图归档为历史 rationale。

## 维护规则

- 蓝图不替代模块 docs。
- memory 不替代 blueprint、模块 docs 或稳定原则文档。
- reference 文档不替代 blueprint、模块 docs 或稳定原则文档。
- 模块 docs 不回填历史讨论过程。
- 历史蓝图保留设计上下文，但不宣称当前实现语义。
