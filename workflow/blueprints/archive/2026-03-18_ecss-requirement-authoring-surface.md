# Task Blueprint: ECSS Requirement Authoring Surface

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/ecss/vcd.py`
  - `src/factpy_kernel/ecss/docs/01_overview.md`
  - `src/factpy_kernel/audit/compliance.py`
  - `src/factpy_kernel/audit/docs/01_overview.md`
  - `src/factpy_kernel/authoring/docs/01_overview.md`
  - `src/factpy_kernel/sdk/ecss.py`
  - `src/factpy_kernel/sdk/docs/00_user_guide.md`
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
  - `docs/README.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/session_handoff_2026-03-18.md](../../session_handoff_2026-03-18.md)
  - [2026-03-18_ecss-scenario-anchoring.md](../active/2026-03-18_ecss-scenario-anchoring.md)
  - [2026-03-18_ecss-vcd-compliance-delivery.md](../archive/2026-03-18_ecss-vcd-compliance-delivery.md)
  - [2026-03-18_audit-compliance-matrix-ui.md](../archive/2026-03-18_audit-compliance-matrix-ui.md)
- Audit Log:
  - [2026-03-18_ecss-requirement-authoring-surface.audit.md](./2026-03-18_ecss-requirement-authoring-surface.audit.md)

## 1. Problem

`Scenario B` 的读侧和交付侧已经闭环：

- requirement/compliance facts 可由 offline query 组装成 compliance matrix
- static audit site 可生成 `compliance_matrix.html`
- `offline-query-first`、`assertion drill-down`、`no live endpoint` 都已经收口

但写侧仍停留在“底层能力可用、上层工作流缺位”的状态：

- 当前只有 `audit.compliance.extend_schema_ir_with_ecss_vcd_predicates(...)` 这一最小 schema helper
- runtime/service 只有通用 `writes/set` / `writes/add`
- SDK 虽然已有 `batch` / `ingest` / `SDKRegistry`，但没有 requirement-scoped authoring helper

这会导致下一步实现存在两个明显风险：

1. 把写侧 helper 继续放在 `audit` 读侧模块里，模糊模块边界
2. 在没有先收口最小 authoring surface 的前提下，过早新增 live service endpoint 或更重的 UI

因此，下一条切片不应再扩 delivery，而应先把 `ECSS requirement authoring / data-entry surface` 的归属、最小工作流和验证闭环冻结下来。

## 2. Goals

- 为 `ECSS-M-ST-10` 风格 requirement/compliance facts 冻结第一轮写侧入口。
- 明确 canonical ECSS VCD predicate preset 的归属，不再让它只停留在 `audit` 读侧语境。
- 定义最小写入工作流：
  - schema/registry 如何启用 ECSS predicates
  - requirement/status/method/RID/milestone 如何写入
  - 如何验证写入结果能被现有 offline delivery 无缝消费
- 保持当前 `Scenario B` 的核心结论不变：
  - `offline-query-first`
  - `matrix is delivery object`
  - `assertion detail / explainability substrate` 负责更深下钻

## 3. Non-goals

- 不新增 live compliance matrix service endpoint。
- 不把本切片扩成通用 requirements-management 产品。
- 不引入新的 temporal semantics 或 uncertainty semantics。
- 不改变现有 `audit` package wire format，也不新增 `compliance_matrix.jsonl`。
- 不重做 `Scenario B` 的 data model / DTO / static UI contract。

## 4. Current Context

- 当前 `Scenario B` 已完成的切片：
  - `ecss-vcd-compliance-delivery`
  - `audit-compliance-matrix-ui`
- 当前 `audit` 模块已能消费以下 predicates：
  - `ecss:requirement`
  - `ecss:verification_method`
  - `ecss:compliance_status`
  - `ecss:requirement_rid`
  - `ecss:review_milestone`
- 当前 requirement/compliance matrix 的 join key 已固定为内部 `requirement_ref`（canonical `idref_v1`），`req_id` 只是对外稳定标识。
- `authoring` 负责 schema compile / registry workflow，但还没有 Scenario B 专用 schema preset。
- `sdk` 已提供 `batch`、`ingest`、`SDKRegistry` 等通用入口，但还没有 requirement-scoped ergonomics。
- `service` 已提供通用 runtime writes 与 registry 读取，但没有必要在本轮引入新的 compliance 专用 HTTP surface。
- `session_handoff_2026-03-18.md` 已明确：当前最自然的下一步是 requirement authoring / data-entry surface，而不是重开 explainability 或继续补 Scenario B delivery 尾巴。

## 5. Proposed Shape

### 5.1 Ownership And Layering

第一轮需要把 ECSS VCD predicate preset 从“只在 `audit` 中出现的 helper”升级为写侧也可正式依赖的 capability。

adopted conclusion：

- canonical predicate preset 应由写侧可接受的模块拥有，不能继续只停留在 `audit` consumer surface
- `audit` 可以继续保留兼容包装或消费入口，但不应成为 requirement authoring 的主拥有者

这意味着下一轮实现至少需要完成以下其中一种稳定形状，并以不让写侧依赖 `audit` 为准：

- 在 `authoring` 侧引入 schema preset helper，并让 `audit` 复用
- 或引入同样窄、但边界清楚的共享 helper 落点，并同步让 `audit` / `sdk` 消费

### 5.2 SDK-First Authoring Surface

第一轮 requirement authoring 采用 `SDK-first`，而不是 `service-first`。

原因：

1. 当前已有最成熟的写入 ergonomics 在 `sdk.batch(...)` / `sdk.ingest(...)`
2. `Scenario B` 近期目标是演示和样例 authoring workflow，不是前端直连 live endpoint
3. service 现有 `writes/set` / `writes/add` 已足够承载底层协议，无需先开一层 compliance 专用 HTTP facade

第一轮最小 surface 应覆盖两件事：

1. schema/registry helper
   - 让调用方能以显式 helper 启用 ECSS VCD predicates
   - helper 既适用于内存 `schema_ir` 扩展，也适用于 registry/schema registration 工作流
2. write helper
   - 为 requirement identity、status、verification methods、RID、milestone 提供最小批量写入构造
   - 底层仍然落到普通 facts/assertions，不新增 runtime object

### 5.3 Minimal Write Workflow

第一轮写入工作流冻结为：

1. 基于现有 schema，启用 ECSS VCD predicate preset
2. 创建 requirement entity/reference，并以 `requirement_ref` 作为内部 join key
3. 通过普通写协议写入：
   - requirement identity fact
   - compliance status fact
   - verification method facts
   - RID linkage facts
   - review milestone fact
4. 使用既有 `packages/export -> AuditQuery.list_compliance_matrix(...)` 或 static site 渲染验证输出

adopted conclusion：

- 第一轮需要的是“更薄的 authoring helper + end-to-end validation loop”
- 不需要新增 live read model
- 不需要让 matrix row 反向进入 runtime

### 5.4 Verification Shape

第一轮验收必须继续走现有 `offline-query-first` 闭环：

- authored facts -> export `package_kind="audit"` -> `AuditQuery.list_compliance_matrix(...)`
- authored facts -> export -> `render_audit_static_site(...)` -> `compliance_matrix.html`

这一步的目的不是重复验证 audit/delivery 层，而是证明新写侧 surface 与现有 Scenario B 读侧 contract 无缝对接。

### 5.5 Service Boundary

第一轮不新增 compliance 专用 HTTP endpoint。

service 只需要保持两类既有边界：

- runtime 通用写协议：`writes/set` / `writes/add`
- registry 读取能力

若后续出现“前端必须直接录入 requirement facts”的明确需求，再单独开 live service 切片，不在本任务中提前实现。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `offline-query-first` 仍是既定结论
  - requirement/compliance data 继续作为普通 facts/assertions 落入 ledger
  - `requirement_ref` 继续是内部 join key，`req_id` 继续是对外 requirement 标识
  - `audit` 继续是消费层，而不是 authoring 主入口
- 明确不做的内容：
  - 不新增 compliance raw package artifact
  - 不新增 live matrix endpoint
  - 不新增 temporal / uncertainty runtime contract
  - 不引入更重的 requirement UI 或 registry 管理前端
- 兼容性约束：
  - 现有 `AuditQuery.list_compliance_matrix(...)`、DTO、static UI contract 不应被打破
  - 若移动或抽取当前 `audit.compliance` 中的 schema helper，需要保持现有消费代码可平滑兼容

## 7. Acceptance

- [x] canonical ECSS VCD schema preset 已从 `audit`-only helper 升级为写侧可正式依赖的公共能力
- [x] SDK/registry 路径可以在不手写散乱 predicate 细节的情况下完成最小 requirement/compliance authoring
- [x] authored facts 导出后仍能被现有 compliance matrix query / static UI 正确消费
- [x] 受影响模块 docs 已同步
- [x] 若新增了新的 durable docs 入口，`docs/README.md` 已更新

## 8. Implementation Plan

1. 冻结 shared ECSS VCD schema preset 的归属，并让 `audit` 不再作为唯一 owner。
2. 在 `sdk`/registry 工作流上补 requirement-scoped authoring helper，覆盖 schema 启用与最小写入构造。
3. 在 phase-3 contract tests 中增加“authoring helper -> audit matrix delivery”的端到端回归。
4. 更新 `authoring` / `audit` / `sdk` 文档；仅在 workflow 文案发生变化时补充 `service` 文档。

## 9. Docs To Update

- `src/factpy_kernel/ecss/docs/README.md`
- `src/factpy_kernel/ecss/docs/01_overview.md`
- `src/factpy_kernel/authoring/docs/01_overview.md`
- `src/factpy_kernel/audit/docs/01_overview.md`
- `src/factpy_kernel/sdk/docs/00_user_guide.md`
- `src/factpy_kernel/service/docs/02_runtime_sessions.md`（如工作流说明发生变化）
- `docs/README.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增 `src/factpy_kernel/ecss/` 共享模块，并把 ECSS VCD predicate constants/schema preset 从 `audit` 中抽出到 `factpy_kernel.ecss.vcd`。
  - `audit.compliance` 保留 matrix row 组装与兼容 re-export，不再拥有 canonical preset definition。
  - 新增 `factpy_kernel.sdk.ecss`，提供 `apply_ecss_vcd_schema(...)`、`make_ecss_requirement_ref(...)`、`write_ecss_requirement_bundle(...)` 三个最小写侧 helper。
  - 新增 `ecss` 模块 docs，并同步更新 `audit` / `authoring` / `sdk` 文档与 `docs/README.md` 索引。
  - `test_phase3_contracts_v1.py` 已补 shared helper 校验与 `SDK helper -> audit compliance matrix` 端到端回归。
- 与 blueprint 不同的地方：
  - 第一轮除了 schema preset helper，还额外落了一个最小 `write_ecss_requirement_bundle(...)` convenience wrapper。
- 为什么会有这些调整：
  - 仅有 schema preset helper 不足以形成可验证的 write-side workflow；当前通用 `sdk.batch()` / `sdk.ingest()` 也不能直接表达这些没有 `Entity` descriptor 的 preset predicates，因此需要一个很薄的 SDK 写侧 wrapper 完成最小闭环。
- 归档说明：
  - 验证命令：`PYTHONPATH=src python -m unittest src.factpy_kernel.tests.test_phase3_contracts_v1`
  - 结果：`50 tests` 全部通过。
