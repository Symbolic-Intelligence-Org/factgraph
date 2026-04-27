# Module Docs Convention

## 角色

本文档定义 `src/<package>/**/docs/`(`<package>` ∈ {kernel, agent, service, domains})下各模块文档的**最小结构要求**和**写作约定**。

它不是：

- 对具体模块实现的说明
- 对 API 签名的逐行注释
- 蓝图或设计草案

目标是让每个模块文档都能作为独立的入口，让读者在不看其它文档的情况下快速定位：这个模块做什么、不做什么、当前边界在哪、从哪里开始读代码和测试。

---

## 最小结构要求

每个模块的 `docs/README.md` 必须覆盖以下六项。内容可以简短，但不能缺项。

### 1. 范围（Scope）

用一到两句话说明：这个模块覆盖哪些代码路径，从哪里到哪里。

示例：
> 本文档覆盖 `src/kernel/core` 的语义内核，包括 ledger、evidence、policy、view、rules、derivation、mapping。

### 2. 当前职责（Responsibilities）

列出这个模块**实际承担**的核心职责，对应当前代码行为，不是设计目标。

每条职责建议写成"做什么 → 通过什么入口/机制"的形式。

示例：
> - 维护 append-only 事实账本 → `Ledger.append_assertion / append_revocation`
> - 执行规则与派生 → `Store.evaluate(..., mode=...)`

### 3. 不负责什么（Non-responsibilities）

明确列出容易被误解为"这个模块应该做"但**实际上不在范围内**的事。

这一节是边界防御，防止调用方在错误的层做事。

示例：
> - 不负责 HTTP 路由和 DTO 序列化（属于 `service`）
> - 不负责 schema 编译和 registry 工作流（属于 `authoring`）
> - 不静态依赖 `adapters`（通过注册机制接入）

### 4. 当前限制与兼容边界（Limitations & Compatibility）

列出当前实现中**已知的限制**、**已标记 deprecated 的接口**、**兼容层的存在原因**，以及**不保证向后兼容的范围**。

这一节防止调用方踩坑，也是 review 时检查遗漏的信号。

示例：
> - `Store.evaluate_dummy(...)` 已标记 deprecated，仅保留历史调用兼容，不应在新代码中使用
> - `store/api.py` 是旧导入路径兼容 shim，内容不代表当前推荐入口
> - 当前 `evaluate` 仅支持 `native | souffle | problog`；`python / engine` 模式已移除

### 5. 相关测试入口（Test Entry Points）

指向本模块的主要测试文件或目录，帮助读者快速找到行为验证的代码。

可以是目录路径、具体文件名，或关键测试文件列表。

示例：
> - `src/kernel/tests/test_protocol_v1.py`
> - `src/kernel/tests/test_annotation_store.py`
> - 集成测试：`tests/integration/test_store_evaluate.py`

### 6. 相关历史蓝图（Related Historical Blueprints）

列出与本模块设计 rationale 最相关的历史蓝图，标注来源区域（`blueprint_history/` 或 `blueprints/archive/`）。

这一节是从"当前真相"反向链接到"当时为什么这样设计"的入口，不要求覆盖所有历史，只需列出仍有参考价值的。

示例：
> - [`docs/blueprint_history/candidate_protocol_v2.md`](../../docs/blueprint_history/candidate_protocol_v2.md) — CandidateSet v2 协议设计 rationale
> - [`docs/blueprints/archive/2024-10_claim-evidence-protocol.md`](../../docs/blueprints/archive/2024-10_claim-evidence-protocol.md) — claim/meta/revocation 协议 rationale

---

## 详细专题文档的约定

`README.md` 之外的专题文档（如 `01_overview.md`、`02_readwrite_and_ingest.md`）没有固定模板，但必须遵守以下规则：

- **文件头必须标明适用范围和最后更新时间**，格式参考 `core/docs/01_architecture.md` 的前 6 行
- **描述的是当前实现行为**，不是设计目标或未来计划；计划内容可以放在独立的 `roadmap` 文件中
- **与 README.md 保持一致**：README.md 中列出的文件就是当前有效的文档集；从 README 删除条目等同于废弃该文档
- **双语文档**：如果模块需要中英双语（参考 `sdk/docs/`），中文文档是语义基线；先更新中文，再同步英文；`_cn_en_consistency_checklist.md` 类文件是可选的，但如果存在，必须保持同步

---

## README.md 的完整结构示例

以下是一个符合最小要求的 `docs/README.md` 示例，可以直接作为新模块的起点：

```markdown
# <Module Name> 文档

- 适用范围：`src/<package>/<module>`(`<package>` ∈ {kernel, agent, service, domains})
- 最后更新：YYYY-MM-DD
- 目标读者：<一句话描述读者场景>

本目录记录 `src/<package>/<module>` 的当前实现口径。

## 范围

<模块覆盖哪些代码路径>

## 当前职责

- <职责1> → <入口/机制>
- <职责2> → <入口/机制>

## 不负责什么

- <不在范围内的事1>
- <不在范围内的事2>

## 当前限制与兼容边界

- <已知限制或 deprecated 接口>

## 相关测试入口

- `<测试文件路径>`

## 相关历史蓝图

- [`<蓝图路径>`](<相对链接>) — <一句描述>

## 当前文档

- `<文档文件名>` — <一句描述>
```

---

## 触发更新的场景

以下情况**必须**同步更新受影响模块的 `docs/`：

| 变更类型 | 必须更新的内容 |
|----------|---------------|
| 新增或删除公共入口 | `README.md` 职责列表 + 对应专题文档 |
| 行为语义变更（返回值、错误码、副作用） | 对应专题文档的行为描述 |
| 新增或废弃 deprecated 接口 | `README.md` 限制与兼容边界 |
| 模块边界调整（职责移入/移出） | `README.md` 职责 + 不负责什么 |
| 新增测试覆盖关键路径 | `README.md` 测试入口（如果测试文件有变化） |
| 添加与蓝图的关联 | `README.md` 相关历史蓝图 |

以下情况**不需要**更新 `docs/`：

- 纯内部重构（行为不变，入口不变）
- 注释修改、变量重命名（无行为变更）
- 测试辅助代码的调整（非关键路径）

---

## 不符合约定的常见问题

| 问题 | 处理方式 |
|------|----------|
| README.md 只有文件列表，没有职责说明 | 补全六项最小结构 |
| 专题文档有"未来计划"段落混在当前行为里 | 把未来计划移到独立 `roadmap.md` 或蓝图 |
| 文档描述的行为与代码不一致 | 以代码为准，修正文档；如有疑问建蓝图讨论 |
| 缺少历史蓝图链接，但有相关的历史文档 | 在 `README.md` 的历史蓝图节补充链接 |
| 双语文档中英文版比中文版滞后 | 优先对齐 `01_overview.md`；在 checklist 文件中标记待同步项 |
