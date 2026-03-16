# Task Blueprint: Overall System Blueprint

- Status: draft
- Created: 2026-03-15
- Last Updated: 2026-03-15
- Related Modules:
  - `src/factpy_kernel/core`
  - `src/factpy_kernel/authoring`
  - `src/factpy_kernel/application`
  - `src/factpy_kernel/service`
  - `src/factpy_kernel/sdk`
  - `src/factpy_kernel/adapters`
  - `src/factpy_kernel/audit`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/authoring/docs/01_overview.md](../../../src/factpy_kernel/authoring/docs/01_overview.md)
  - [src/factpy_kernel/application/docs/01_overview.md](../../../src/factpy_kernel/application/docs/01_overview.md)
  - [src/factpy_kernel/service/docs/01_overview.md](../../../src/factpy_kernel/service/docs/01_overview.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-03-15_overall-system-blueprint.audit.md](./2026-03-15_overall-system-blueprint.audit.md)

## 1. Problem

当前仓库已经形成了较清楚的模块级实现文档，但缺少一份跨层总蓝图，把“领域知识如何进入系统、如何被形式化、如何进入运行时、如何被审计消费”串成统一叙事。

这导致几个现实问题：

- 新的方向讨论容易在不同抽象层之间来回跳转，例如语义建模、规则执行、审计追踪、BFF 暴露面混在一起。
- 对外讨论 MVP、PoC、知识摄取或 Semantic Web 集成时，缺少一个稳定的“当前边界 vs. 长期方向”对照框架。
- 未来若要拆成 ingestion、semantic integration、runtime、audit 等子蓝图，没有统一母图作为约束入口。

本蓝图先作为总蓝图草案，建立统一语言和分层骨架；细节方案后续再拆分。

## 2. Goals

- 给项目提供一份跨模块的总蓝图草案，明确系统的主轴、分层、数据流和长期可扩展接口。
- 明确“当前已实现主线”和“未来可能扩展主线”的边界，避免在 draft 阶段误把设想写成现状。
- 为后续子蓝图提供母结构，尤其是：
  - 知识摄取 / normalize
  - semantic integration
  - runtime / derivation / audit
  - service / application 交付面
- 把当前项目定位为“规则执行与审计运行时主轴”，而不是直接重述为某个垂直行业系统。

## 3. Non-goals

- 不在本蓝图中冻结具体协议、DTO、DSL、数据格式细节。
- 不在本蓝图中决定是否正式引入 RDF/OWL/SKOS/SHACL/PROV。
- 不在本蓝图中承诺某个特定垂直领域作为唯一 MVP 方向。
- 不改写任何模块 docs，使其承担跨层总蓝图职责。
- 不把当前 draft 误写为 implementation roadmap 或 release plan。

## 4. Current Context

- 当前实现入口已经围绕 `core / authoring / application / service / sdk / adapters / audit` 形成稳定分工。
- 当前最成熟的主线是：
  - facts 写入与 append-only ledger
  - rule / derivation evaluate
  - candidate accept / accept_many
  - package export 与 audit consumption
- 当前相对薄弱或尚未落地的区域是：
  - 外部知识源到 canonical write items / authoring assets 的 normalize 层
  - 图投影、binding、跨语义层集成
  - 面向文本或标准文档的正式 extraction workflow
- `application` 仍明确缺少 `query_view.py`、`authoring_normalize.py`、`graph_projection.py`、`binding.py`。
- `third_party/rule-parser` 与 `third_party/kg-gen` 当前更接近实验/参考资产，不是主包主线的一部分。
- 当前项目的模块 docs 是实现真相；本蓝图只能描述跨层形状与后续讨论入口。
- 当前相关历史蓝图：
  - [docs/blueprint_history/application_projection_blueprint.md](../../blueprint_history/application_projection_blueprint.md)
  - [docs/symir_blueprint_extraction.md](../../symir_blueprint_extraction.md)
  - [docs/blueprint_history/realtime_execution_blueprint.md](../../blueprint_history/realtime_execution_blueprint.md)

## 5. Proposed Shape

### 5.1 顶层定位

项目整体应被描述为一个“从结构化知识资产到可执行推理与可审计决策”的系统，而不是单纯的图谱建模器，也不是单纯的 DSL 编译器。

### 5.2 建议的跨层骨架

1. `Source / Evidence Layer`
   - 外部文档、表格、业务事实、传感器或其他来源。
   - 本层只定义来源类型与证据边界，不定义最终运行时语义。

2. `Ingestion / Normalize Layer`
   - 把外部来源转成可审查的候选结构。
   - 未来可能包含 text extraction、schema-guided normalize、entity linking、controlled vocabulary mapping。
   - 当前仓库尚未正式落地，应作为后续子蓝图。

3. `Semantic / Authoring Layer`
   - 管理 schema、rule、derivation 等 authoring assets。
   - 这里是“受控形式化”的主入口，而不是 live runtime。

4. `Runtime Kernel Layer`
   - 以 `Store / Ledger / Policy / Evaluate / Accept` 为核心。
   - 负责事实写入、规则求值、候选生成、物化接受与运行时约束。

5. `Execution Adapter Layer`
   - Native、Souffle、ProbLog 等执行后端。
   - 负责将统一运行时语义投递到不同执行引擎，而不是改变上层 authoring contract。

6. `Delivery Layer`
   - `application` 负责中性运行时能力。
   - `service` 负责 HTTP/BFF 交付面。
   - `sdk` 负责 Python facade 与 authoring ergonomics。

7. `Audit / Provenance Layer`
   - 负责导出的 audit package、candidate decision、apply event、静态审计消费。
   - 长期上应成为跨层可追溯性的统一汇点。

### 5.3 与 Semantic Web 栈的关系

如果未来引入 RDF/OWL/SKOS/SHACL/PROV，这套栈更适合作为 `Source / Evidence Layer` 与 `Semantic / Authoring Layer` 之间的可选扩展，而不是替代当前 runtime kernel：

- `RDF/SKOS/OWL` 更偏上游知识表示与术语/语义建模
- `SHACL` 更偏 graph/data validation
- `PROV` 与当前 audit/provenance 最接近
- `factpy_kernel` 当前主线仍是显式规则执行、物化接受和审计导出

### 5.4 后续建议的子蓝图拆分

- `overall-system-blueprint`：母图，只管总形状和边界
- `knowledge-ingestion-blueprint`：外部来源 -> normalized candidates / items
- `semantic-integration-blueprint`：是否以及如何接入 RDF/OWL/SKOS/SHACL/PROV
- `runtime-governance-blueprint`：evaluate / accept / audit / provenance 的跨层口径
- `delivery-surface-blueprint`：application/service/sdk 的对外交付面

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 模块 docs 仍然是当前实现真相。
  - `core` 仍然是运行时语义内核，不被总蓝图改写成语义网平台。
  - `authoring` 仍然负责资产编译与发布，不直接承担 live runtime。
  - `audit` 仍然是审计消费层，不直接承担 live query。
- 明确不做的内容：
  - 不在当前 draft 中把 semantic web 集成写成既定路线。
  - 不在当前 draft 中定义 extraction pipeline 的实现细节。
  - 不在当前 draft 中决定单一垂直行业。
- 兼容性约束：
  - 后续任何总蓝图推进都不能模糊 `append-only ledger`、显式 `accept`、以及模块边界。
  - 若总蓝图与现有模块 docs 出现冲突，以模块 docs 和实际代码为准，并在后续子蓝图中修正总蓝图。

## 7. Acceptance

- [ ] 一份跨模块的总蓝图草案已经形成，可作为后续讨论入口
- [ ] 蓝图明确区分了当前主线、未来扩展和未决问题
- [ ] 蓝图没有越过当前模块 docs 的实现真相边界
- [ ] 后续需要拆分的子蓝图方向已经被点名

## 8. Implementation Plan

1. 建立总蓝图 draft，只收口跨层问题、目标、分层和边界，不冻结细节协议。
2. 在后续讨论中，把“需要决定的事项”从总蓝图中挑出，分别沉淀为子蓝图。
3. 只有当某个子方向进入 `scoped` 或开始实现时，才更新对应模块 docs 或新增持久入口。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-15_overall-system-blueprint.md`
- `docs/blueprints/active/2026-03-15_overall-system-blueprint.audit.md`
- `docs/README.md`（当前 draft 阶段暂不更新；若后续归档或变成持久入口，再讨论）

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
