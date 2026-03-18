# Task Blueprint: ECSS VCD Compliance Delivery

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/adapters/souffle/package.py`
  - `src/factpy_kernel/audit/reader.py`
  - `src/factpy_kernel/audit/query.py`
  - `src/factpy_kernel/audit/dto.py`
  - `src/factpy_kernel/audit/static_ui.py`
  - `src/factpy_kernel/audit/docs/01_overview.md`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/core/docs/01_architecture.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](../active/2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-18_ecss-scenario-anchoring.md](../active/2026-03-18_ecss-scenario-anchoring.md)
  - [src/factpy_kernel/audit/docs/01_overview.md](../../../src/factpy_kernel/audit/docs/01_overview.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
- Audit Log:
  - [2026-03-18_ecss-vcd-compliance-delivery.audit.md](./2026-03-18_ecss-vcd-compliance-delivery.audit.md)

## 1. Problem

`ecss-scenario-anchoring` 已把 `ECSS-M-ST-10 VCD / compliance-matrix` 锁定为近期优先锚点。

当前系统已经具备：

- append-only ledger
- derivation / accept / audit package export
- explainability substrate
- offline audit query / DTO / static UI

但还没有任何 requirement-scoped compliance delivery contract。现实缺口集中在两类：

1. `data modeling`
   - requirement / verification method / status / RID / milestone 之间还没有最小 schema
2. `delivery shape`
   - 当前 audit package 只导出通用 ledger / decision / artifact rows
   - 没有 compliance matrix 专用 artifact、DTO、query view 或静态页面 contract

因此，这个切片的目标不是扩 runtime semantics，而是先把 Scenario B 的最小对象模型和交付边界收口清楚。

## 2. Goals

- 为 VCD / compliance matrix 确定最小 data model：
  - requirement
  - verification method assignment
  - compliance status
  - RID linkage
  - milestone / review node
- 比较并收口第一轮 delivery shape：
  - audit package extension
  - offline audit DTO/query
  - static audit page
  - 是否需要新增 live service endpoint
- 明确与现有 `packages/export`、`AuditQuery`、`explain_ref` 的边界分工。
- 为后续实现切片提供可直接进入 `scoped` 的 shape。

## 3. Non-goals

- 不在本蓝图中恢复 runtime `temporal_view`。
- 不在本蓝图中引入新的 uncertainty / confidence semantics。
- 不在本蓝图中接入 `PyReason` 或其他新 engine。
- 不在本蓝图中构建完整 ECSS ontology 或标准全文知识库。
- 不把本切片扩成通用 requirements-management 产品路线图。

## 4. Current Context

- 当前 audit/export 基座：
  - `package_kind="audit"` 已导出：
    - `run_ledger.jsonl`
    - `candidate_ledger.jsonl`
    - `accept_write_ledger.jsonl`
    - `decision_log.jsonl`
    - `support_artifacts.jsonl`
    - `rule_trace_artifacts.jsonl`
  - `audit` 模块已提供：
    - `AuditQuery`
    - `dto.py`
    - `static_ui.py`
- 当前 service 边界：
  - service v1 只暴露 `packages/export`
  - 没有 requirement-scoped compliance matrix endpoint
- 当前 explainability 边界：
  - `explain_ref` 与 artifact substrate 已足够支撑 requirement-level evidence drill-down
  - 但还没有“VCD 行”或“requirement status”这一层正式对象
- 当前 scenario anchoring 结论：
  - `ECSS-M-ST-10 VCD / compliance-matrix` 是近期优先锚点
  - 其主要缺口是 `data modeling + delivery shape`
  - 不依赖新的 temporal / uncertainty semantics

## 5. Proposed Shape

### 5.1 Data Model

第一轮采用 `hybrid`，并把边界写死：

- requirement identity 作为显式 facts 进入 session ledger
  - 最小 requirement 身份对象包含：
    - `req_id`
    - `title`
    - 可选 `standard_ref`
  - 第一轮可通过新的 requirement-scoped predicates 表达，例如：
    - `ecss:requirement`
    - `ecss:verification_method`
    - `ecss:compliance_status`
    - `ecss:requirement_rid`
    - `ecss:review_milestone`
- verification method assignment、compliance status、RID linkage、milestone 同样作为 facts / assertions 进入 ledger
  - 不引入新的 runtime object
  - 不要求 temporal semantics；milestone 在第一轮只是普通字符串 literal 或枚举值
- compliance matrix row 不进入 ledger，不作为新的 core runtime object
  - matrix row 是 audit-side derived view
  - 由 offline audit consumer 从 package 内容离线组装

adopted conclusion：

- requirement object 是 fact/assertion 层对象
- matrix row 是 delivery 层对象
- 两者不混成一个统一 runtime object

### 5.2 Delivery Shape

第一轮采用 `offline-query-first`。

- 不新增 `compliance_matrix.jsonl` 或其他预组装 raw package artifact
- 现有 `package_kind="audit"` wire format 保持不变
- compliance matrix 由 offline audit consumer 在读取 package 后动态组装

采用这个方向的理由：

1. requirement-scoped facts 一旦进入 package，raw audit/facts 内容已经足以支持 matrix 组装
2. 新增预组装 matrix artifact 会引入双写风险：
   - raw ledger / facts 与 pre-cooked matrix 可能漂移
3. `AuditQuery` / `dto.py` 是当前最自然的消费层，扩展成本低于新增 package wire artifact
4. 若后续 ESA 交付需要固定 matrix 文件，可以在 offline query 层之上再追加 convenience export，而不破坏 v1 contract

实现前提也需要写明：

- 当前 `AuditQuery` 仅消费 JSONL audit ledgers，并不直接暴露 requirement/assertion 级 facts
- 因此 `offline-query-first` 的真实实现路径不是“只改现有 `AuditQuery` list_*`”
- 第一轮需要显式复用 package 内已有的 assertion/fact 读取能力，例如：
  - `audit.assertions.load_assertion_index(...)`
  - 或等价的 requirement/assertion read path
- 也就是说，package wire format 保持不变，但 offline query layer 会扩展到底层 fact/assertion 视图，而不是只停留在当前 JSONL ledger 视图

明确排除：

- `live-service-first`
  - Scenario B 的主要消费形态是 review artifact，不是 live runtime query
- `audit-package-first`
  - 第一轮不新增专用 compliance raw artifact

### 5.3 Service Boundary

第一轮边界采用以下分工：

- `packages/export`
  - 保持当前 contract 不变
  - 不增加 compliance-oriented raw file
- `AuditQuery` + `dto.py`
  - 成为 compliance matrix 的主要消费 API
  - 第一轮新增 `list_compliance_matrix()` 或等价 DTO/query 能力
  - 其实现可以下探到 assertion/fact 读取层
- `explain_ref`
  - 只作为 matrix row 的 evidence drill-down helper
  - 不承担 matrix contract 本身
- live service endpoint
  - 本切片不做
  - 若后续需要 live delivery，另开切片处理

adopted conclusion：

- compliance matrix 是 `audit/delivery object`
- `AuditQuery` 是主要读取边界
- `explain_ref` 只做下钻，不做 matrix contract
- `packages/export` 继续是唯一的 service-side package 入口

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 现有 explainability substrate 作为证据下钻层复用，不重新发明 explain contract
  - audit package / offline audit consumer 仍然是第一轮优先交付面
  - 不把 requirement matrix 直接伪装成 runtime derivation result
  - 不新增 v1 compliance raw package artifact；matrix 由 offline query layer 从既有 package 内容派生
- 明确不做的内容：
  - 不提前引入 temporal runtime semantics
  - 不提前把 compliance matrix 设计成通用 graph UI
  - 不在没有 requirement identity/data model 之前就直接做静态页面样式
  - 不把 matrix delivery 首轮做成 live service endpoint
- 兼容性约束：
  - 第一轮不改变 `package_kind="audit"` wire format
  - requirement/compliance matrix 的 offline 读取若需访问事实层，必须复用 package 内现有 assertion/fact 读取路径，而不是发明平行存储
  - 若后续扩展为预组装 matrix artifact，需另开切片并同步 audit docs 和 service `packages/export` 文档

## 7. Acceptance

- [x] requirement identity、verification method、compliance status、RID linkage、milestone 的 v1 data-model 边界已冻结为 `hybrid`
- [x] 第一轮 delivery shape 已冻结为 `offline-query-first`，且明确不新增 `compliance_matrix.jsonl` 之类的 raw package artifact
- [x] `offline-query-first` 的实现前提已写明：offline query layer 可下探到 package 内 assertion/fact 读取路径，而不是仅依赖当前 JSONL audit ledger 视图
- [x] `packages/export`、`AuditQuery` / `dto.py`、`explain_ref` 的边界分工已冻结
- [x] 下一步实现可以在不重开 Scenario B 比较的前提下直接进入 data-model + offline query delivery 落地

## 8. Implementation Plan

1. 将本蓝图切到 `scoped`，冻结 `hybrid + offline-query-first + audit-boundary` 三个决策。
2. 实现时先定义 requirement/compliance 的最小 predicate schema。
3. 在 `audit` 层新增 compliance matrix query / DTO，必要时复用 assertion-index 读取能力。
4. 如需展示层，最后再评估 `static_ui.py` 是否需要最小 matrix 渲染。

## 9. Docs To Update

- `docs/blueprints/active/2026-03-18_ecss-vcd-compliance-delivery.md`
- `docs/blueprints/active/2026-03-18_ecss-vcd-compliance-delivery.audit.md`
- `src/factpy_kernel/audit/docs/01_overview.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`（若 `packages/export` contract 变化）
- `src/factpy_kernel/core/docs/01_architecture.md`（若 audit/export 边界发生持久变化）

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增 `audit/compliance.py`，提供 ECSS VCD requirement predicate schema helper 与 offline matrix row 组装逻辑。
  - `AuditQuery` 新增 `list_compliance_matrix(...)`，`dto.py` 新增 `build_compliance_matrix_dto(...)`。
  - 第一轮实现保持 `packages/export` contract 不变，matrix 完全从既有 package facts/assertions 离线派生。
  - `audit/docs/01_overview.md` 已同步记录 compliance matrix 的 offline-query-first 工作流。
- 与 blueprint 不同的地方：
  - requirement facts 的 join key 最终采用内部 `requirement_ref`（canonical `idref_v1`）作为 `e_ref`，而不是直接把裸 `req_id` 放进 `e_ref`。
  - `req_id` 仍然作为 requirement identity fact 的显式字段暴露，并成为 matrix row 的对外稳定标识。
- 为什么会有这些调整：
  - 写协议要求 `e_ref` 是 canonical `idref_v1` token；因此 requirement/compliance predicates 的内部关联键必须是 `requirement_ref`，而不能是裸 requirement code。
  - 这个调整不改变蓝图的 `hybrid` / `offline-query-first` / `AuditQuery-first` 三个核心决策，只是把 requirement identity 的内部承载方式与现有 runtime invariants 对齐。
- 归档说明：
  - 本切片实现完成后仍未引入新的 live service endpoint，也未新增专用 raw package artifact。
  - 本轮验证命令：`PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1`，结果 `47 tests` 全部通过。
