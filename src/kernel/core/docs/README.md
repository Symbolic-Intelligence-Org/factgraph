# Core Module Docs

`src/kernel/core/` 是 FactPy 的内核 substrate 层 —— 提供 Store / Ledger / native evaluator / engine adapters / projection 等所有上层模块依赖的基础语义。本目录文档面向 advanced importable 的使用者(integrator / contributor),不是 SDK 用户入门文档。

## 入口

- [01_architecture.md](./01_architecture.md) / [.en.md](./01_architecture.en.md) —— Core 架构总览:Store / Ledger / native evaluator + 引擎支持矩阵(`native | souffle | problog | pyreason`) + 关键 data model + entry points。
- [02_quality_assessment.md](./02_quality_assessment.md) / [.en.md](./02_quality_assessment.en.md) —— 质量评估框架(代码 snapshot 视角)。
- [03_progress_roadmap.md](./03_progress_roadmap.md) / [.en.md](./03_progress_roadmap.en.md) —— 开发进度与 future trajectory(post-routemap 状态)。
- [04_public_contract_v1.md](./04_public_contract_v1.md) —— Public contract v1:`core / service / sdk` v1 对外稳定行为约束。
- [04_service_layer.md](./04_service_layer.md) —— Service 层现状(HTTP/BFF delivery 与 core 的 boundary)。

> 注:`04` 编号在历史中分给两个不同主题(`04_public_contract_v1` + `04_service_layer`),两者不冲突,沿用既有文件名。

## 边界

- 本目录**不是 SDK 入门文档** —— SDK user guide 在 [`src/kernel/sdk/docs/00_user_guide.md`](../../sdk/docs/00_user_guide.md)。
- 本目录**不是 application capability docs** —— Check / Diagnose / Fact Overlay / ProofFrame / rule actions / Why-not 在 [`src/kernel/application/docs/`](../../application/docs/)。
- 本目录**不是 audit consumer docs** —— audit package + round events + ProofFrame diff 在 [`src/kernel/audit/docs/`](../../audit/docs/)。
- 本目录**不是 routemap closure narrative** —— round story 闭环故事由 round-story-completion-plan blueprint(internal design record)在 §10 Outcome 记录。
