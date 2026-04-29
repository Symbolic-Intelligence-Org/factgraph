# Architecture Principles

## 角色

本文档记录 `factpy-kernel` 中相对稳定的设计哲学、系统边界和长期维护规则。

它不是：

- 单个任务的实现草案
- 当前代码行为的逐项说明
- 详细变更记录的替代品

当前代码行为仍以各模块 `docs/` 为准。

## 稳定原则

### 1. 结构化优先于字符串拼接

- rule / derivation / protocol / schema 应优先走结构化对象、IR 和可校验 DTO。
- 不把临时字符串格式提升为长期契约。

### 2. 模块边界优先于一次性大统一

- `core` 负责运行时语义内核。
- `authoring` 负责编译、预检、registry 工作流。
- `application` 负责 core 之上的 canonical Python runtime authority。
- `service` 负责前端/BFF 形态的 HTTP 交付面。
- `sdk` 负责 Python authoring 与 facade 体验。

### 2.1 Layer authority

- 新 runtime 能力默认进入 `core` 或 `application`,不直接塞回 SDK god files。
- `application` 拥有 runtime-normalized DTO 与 executor surface,例如 read/write/query/ingest/compiled derivation evaluate/accept。
- `sdk` 拥有 product surface:Python schema/DSL authoring、`SDKStore` facade、snapshot/editor/batch outward objects、compatibility aliases 与用户可见错误。
- SDK 可以调用 application,但 application 不 import SDK。
- service / agent production runtime code 不应新增 SDK runtime imports；确有 authoring/ergonomic 例外时必须显式登记并说明理由。
- 若需要把 SDK DSL primitive 下沉给 adapter 或 domain 使用,应通过单独 primitive-contract blueprint 处理,不要在运行时迁移中偷渡。

### 3. 当前实现真相必须贴近模块

- 当前行为、约束、兼容面、已完成迁移范围，应记录在模块自己的 `docs/` 目录中。
- 任务蓝图只负责约束实现方向和记录决策，不负责声明当前代码真相。

### 4. 蓝图是实现约束，不是永久真相

- 新任务应先有蓝图，再有多轮实现。
- 蓝图在实现过程中用于防止范围漂移。
- 任务结束后，蓝图应归档为 rationale，不能继续充当当前实现说明。

### 5. 设计背景不伪装成现状

- 历史设计材料可以提供背景，但不能替代当前代码、模块文档或公开 API contract。
- 若历史内容仍有价值，应提炼到原则文档或当前模块 docs，而不是让读者去追溯内部工作记录。

### 6. 当前真相应贴近代码

- 当前行为应记录在靠近实现的模块 docs 中。
- 稳定原则应记录在本文件或公开模块 docs 中。
- 临时工作记录、个人笔记和内部实现日志不应成为公开 contract。

## 当前系统边界

- 当前实现真相以 `src/kernel/**/docs/` 为准。
- root README 面向安装与快速开始。
- 模块 docs 面向当前实现边界、公共入口和兼容面。

## 长期方向

- 让模块 docs 成为稳定、贴近代码、可在 review 中维护的当前真相。
- 逐步把关键架构原则从历史讨论中抽出，减少重复争论。
