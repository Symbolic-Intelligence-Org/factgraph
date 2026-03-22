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
- [blueprints/README.md](/Users/zhenzhili/hnsm-backend/docs/blueprints/README.md)
  - 任务蓝图工作流、状态机、模板与标准归档 / reconstructed 归档规则。
- [module_docs_convention.md](/Users/zhenzhili/hnsm-backend/docs/module_docs_convention.md)
  - 模块文档最小结构要求、写作约定、触发更新的场景、起点模板。
- [references/README.md](/Users/zhenzhili/hnsm-backend/docs/references/README.md)
  - 外部比较、桥接提炼和工作参考材料的管理规则；可作为 blueprint 输入材料，但不是当前实现真相。
- [memory/README.md](/Users/zhenzhili/hnsm-backend/memory/README.md)
  - 仓库级 operational memory 说明；定义 handoff 与 `current.md` 的边界。
- [memory/current.md](/Users/zhenzhili/hnsm-backend/memory/current.md)
  - 当前 canonical operational memory 入口；用于新 session 恢复上下文，不是模块真相，也不替代 active blueprint。
- [blueprint_history/README.md](/Users/zhenzhili/hnsm-backend/docs/blueprint_history/README.md)
  - 旧蓝图归档区的说明与使用边界。

## 当前实现文档

以下模块目录中的 `docs/` 才是对应实现的当前真相：

- [src/factpy_kernel/core/docs/01_architecture.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/core/docs/01_architecture.md)
- [src/factpy_kernel/application/docs/README.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/application/docs/README.md)
- [src/factpy_kernel/service/docs/README.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/service/docs/README.md)
- [src/factpy_kernel/sdk/docs/README.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/sdk/docs/README.md)
- [src/factpy_kernel/authoring/docs/README.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/authoring/docs/README.md)
- [src/factpy_kernel/adapters/docs/README.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/adapters/docs/README.md)
- [src/factpy_kernel/audit/docs/README.md](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/audit/docs/README.md)

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
