# Architecture Principles

## 角色

本文档记录项目中相对稳定的设计哲学、系统边界和长期维护规则。

它不是：

- 单个任务的实现草案
- 当前代码行为的逐项说明
- 历史蓝图的替代品

当前代码行为仍以各模块 `docs/` 为准。

## 稳定原则

### 1. 结构化优先于字符串拼接

- rule / derivation / protocol / schema 应优先走结构化对象、IR 和可校验 DTO。
- 不把临时字符串格式提升为长期契约。

### 2. 模块边界优先于一次性大统一

- `core` 负责运行时语义内核。
- `authoring` 负责编译、预检、registry 工作流。
- `application` 负责 core 之上的中性运行层。
- `service` 负责前端/BFF 形态的 HTTP 交付面。
- `sdk` 负责 Python authoring 与 facade 体验。

### 3. 当前实现真相必须贴近模块

- 当前行为、约束、兼容面、已完成迁移范围，应记录在模块自己的 `docs/` 目录中。
- 任务蓝图只负责约束实现方向和记录决策，不负责声明当前代码真相。

### 4. 蓝图是实现约束，不是永久真相

- 新任务应先有蓝图，再有多轮实现。
- 蓝图在实现过程中用于防止范围漂移。
- 任务结束后，蓝图应归档为 rationale，不能继续充当当前实现说明。

### 5. 历史文档保留上下文，不伪装成现状

- `docs/blueprint_history/` 保存历史阶段讨论、旧设计和未完成方向。
- 若历史内容仍有价值，应提炼到原则文档、当前模块 docs 或新任务蓝图中，而不是直接重写旧文档。
- 若需要把历史蓝图桥接到新归档区，应创建显式标注的 reconstructed archive 条目，并保留 `Historical Source` 与可验证 provenance。

### 6. Operational Memory 不等于当前真相

- `memory/` 用于 session continuity、handoff 和当前工作记忆。
- `memory/` 不应承担当前实现真相、稳定原则或 active blueprint 约束。
- 当 memory 中的结论变成 durable boundary，应迁回 blueprint、模块 docs 或原则文档。

## 当前系统边界

- 当前实现真相以 `src/<package>/**/docs/` 为准(`<package>` ∈ {kernel, agent, service, domains})。
- `memory/` 承载 operational memory，不承担当前实现真相。
- `docs/blueprints/active/` 只放正在推进的任务蓝图。
- `docs/blueprints/archive/` 放按新流程归档的蓝图。
- `docs/blueprint_history/` 保留历史遗留蓝图，不承担新的活动任务。

## 长期方向

- 让蓝图成为任务收口、多轮生成和文档同步的标准入口。
- 让模块 docs 成为稳定、贴近代码、可在 review 中维护的当前真相。
- 让历史蓝图继续承担设计 rationale，而不是与代码竞争权威性。
- 逐步把关键架构原则从历史讨论中抽出，减少重复争论。
