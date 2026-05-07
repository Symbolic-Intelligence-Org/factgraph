# FactPy Application 文档

本目录记录 `src/kernel/application` 的当前实现口径。`application` 是 `core` 之上的 canonical Python runtime authority；`sdk` 负责 Python product surface、DSL authoring 和 outward facade compatibility。

> **Audience note**
>
> 如果你是在写普通 Python product code,并希望用 `Entity` / `Field` / `Identity` classes、Query DSL、snapshot、batch 或 user-facing exceptions,优先阅读 `src/kernel/sdk/docs/` 并从 `kernel.sdk` 开始。
>
> 本目录面向 integration / automation / pipeline / RPC bridge 作者:调用方可能只拥有 JSON-like payload、schema identity 字符串、field path 和 error DTO,不应依赖 SDK descriptor 或 Python DSL object。这里记录的是 SDK 之下的 Layer 2 runtime contract。

## 当前文档

- `src/kernel/application/docs/01_overview.md`
  - application 模块职责、runtime protocol / executor 结构、SDK adapter 关系、保守 fallback 边界与测试入口。
- `src/kernel/application/docs/01_overview_en.md`
  - English mirror of the overview.
- `src/kernel/application/walker/docs/README.md`
  - Current implementation contract for the application-layer walker module.

## 使用约定

- 本目录文档以当前实现行为为准，不是独立设计草案。
- 新增或调整 `application` 公共入口时，应同步更新本目录文档与对应测试。
- application protocol 不接收 SDK facade objects、SDK `Field` descriptors 或 SDK DSL objects；SDK 负责把 ergonomic 输入 lower/adapter 成 application runtime DTO。
