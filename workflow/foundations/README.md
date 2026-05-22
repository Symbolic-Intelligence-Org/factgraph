# Foundations(基础原则层)

稳定架构原则与模块文档约定。内容是**基础治理** — 缓慢演变,只通过明确的 slice 工作更新。

## 内容

- [`architecture_principles.md`](./architecture_principles.md) — 稳定设计哲学、系统边界、长期方向。含 6 条稳定原则(结构化优先 / 模块边界 / 实现真相贴近模块 / 蓝图非永久真相 / 设计背景非现状 / 真相贴近代码),§2.1 layer authority,§2.2 release surface governance。
- [`module_docs_convention.md`](./module_docs_convention.md) — 模块 `docs/README.md` 6-item 最小结构、写作约定、触发更新场景、起点模板。

## 权威

两份文件都是**它们所描述约定的当前真相**。各模块引用回这里;新模块从创建起遵循 `module_docs_convention.md`。

任务级约束见 [`workflow/blueprints/`](../blueprints/);决策级约束见 [`workflow/design/decisions/`](../design/decisions/)。Foundations 居于这些之上。
