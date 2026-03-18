# Task Blueprint: AML Case-Review Walkthrough

- Status: implemented
- Created: 2026-03-18
- Last Updated: 2026-03-18
- Related Modules:
  - `src/factpy_kernel/tests/test_phase3_contracts_v1.py`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
  - `src/factpy_kernel/audit/docs/01_overview.md`
  - `src/factpy_kernel/core/docs/01_architecture.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-15_overall-system-blueprint.md](./2026-03-15_overall-system-blueprint.md)
  - [2026-03-16_temporal-hybrid-reasoning-blueprint.md](./2026-03-16_temporal-hybrid-reasoning-blueprint.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-18_aml-suspicious-account-anchoring.md](../archive/2026-03-18_aml-suspicious-account-anchoring.md)
  - [docs/references/working/cross-domain-compliance-framing.md](../../references/working/cross-domain-compliance-framing.md)
  - [docs/references/external/rainbird-evidence-chain-compare.md](../../references/external/rainbird-evidence-chain-compare.md)
- Audit Log:
  - [2026-03-18_aml-case-review-walkthrough.audit.md](./2026-03-18_aml-case-review-walkthrough.audit.md)

## 1. Problem

`AML suspicious-account anchoring` 已经回答了 gate question：

- 对 first-round walkthrough，单个 `rule_run_id` 足以作为 proof-entry
- 现有五层 explain delivery 栈足以支撑 single-rule-run investigator-facing consumption

这意味着下一步不需要先开 case-level aggregation gap blueprint，而是可以直接做一个 **single composite rule-run walkthrough**，验证当前 explain/delivery substrate 在 AML 场景中是否真的可复用。

当前还缺的不是新的 public contract，而是一条具体、可执行、可回归的场景链路：

- synthetic AML-like facts
- single composite suspicious-account rule
- single `rule_run_id` entry point
- runtime `raw -> summary -> narrative -> NL`
- audit package + static proof-entry page

如果这条 walkthrough 顺畅，就说明现有 explain delivery 栈已经具备跨域复用价值；如果不顺畅，暴露的缺口就会更具体地落在：

- domain modeling
- prose composition
- proof-entry packaging

而不是再次回到抽象的 temporal/LLM 讨论。

## 2. Goals

- 用一个具名 AML suspicious-account walkthrough 验证现有 explain delivery substrate 的跨域复用能力。
- walkthrough 必须严格建立在 **single composite rule run** 之上。
- walkthrough 必须完整穿过：
  - runtime raw explain
  - runtime summary
  - runtime narrative
  - runtime NL explain
  - audit package / static proof-entry
- walkthrough 必须显式验证 investigator-facing readability，而不新增新的 delivery contract。

## 3. Non-goals

- 不实现 case-level aggregation、`case_id`、或 multi-run rollup。
- 不新增 `judgment` / `obligation` kind。
- 不实现事件时间聚合或 36-hour window semantics。
- 不引入新的 probabilistic / certainty engine contract。
- 不新增 case-management UI 或独立 investigator workbench。
- 不修改现有 raw / summary / narrative / NL explain contract。

## 4. Current Context

- 当前 explain delivery 栈已经闭环：
  - runtime raw explain
  - runtime summary
  - runtime narrative
  - runtime NL explain
  - audit static proof-entry page
- `AML suspicious-account anchoring` 的 gate resolution 已确认：
  - first-round 可直接用单个 `rule_run_id` 作为 walkthrough entry
  - 当前不需要先引入 case-level aggregation layer
- 当前最需要验证的新点是：
  - 多实体 fan-out（account / transaction / beneficiary / device / ownership signal）在同一个 composite rule run 下是否仍然清晰可读
  - investigator-facing prose 是否仍可用现有 narrative/NL renderer 直接承载，而不需要新 delivery shape

authority note:

- 本切片使用 AML suspicious-account 作为 design scenario，不构成监管规则解释或法律意见。
- synthetic facts / rule walkthrough 的作用是压测 explain delivery substrate，而不是提供真实 AML 决策逻辑。

## 5. Proposed Shape

### 5.1 Scenario Shape

第一轮 walkthrough 使用一个 synthetic suspicious-account scenario，至少包含以下要素：

- 一个 `account`
- 多条 `transaction` facts
- 一个或多个 `beneficiary` / `jurisdiction` risk facts
- 一个或多个 weak supporting signals，例如：
  - shared device
  - shared beneficiary
  - beneficial-ownership mismatch

这些 facts 不要求表达完整 AML ontology，只要求足够驱动一条单次 composite rule run。

为了让这条 walkthrough 真正对 explain delivery substrate 形成压力，synthetic facts 至少要满足以下多样性约束：

- `>=3 transaction facts`
  - 针对同一个 account，而不是只放 1 条交易；
  - 这样 rule-run trace 中会出现同一 predicate 的多条 witness assertions，可检验 summary / narrative 在“同类 predicate 多次命中”时是否仍然可读。
- `>=2 distinct supporting signal types`
  - 例如 `shared-device` + `BO-mismatch`，而不是同一种 supporting signal 的重复；
  - 这样 rule-run trace 中会同时出现结构不同的 predicate witness groups，可检验 narrative prose 在 predicate kinds 不同时是否仍然连贯。
- `>=1 beneficiary/jurisdiction risk fact`
  - 且必须与交易/受益方链路关联，而不是一个孤立的 free-standing risk fact；
  - 这样 explain trace 才会真正体现 cross-entity reference chain，而不是几个彼此独立的平铺条件。

这些约束不是 AML 领域要求，而是 **explain delivery pressure constraints**。目的就是避免 walkthrough 用一个过于平坦的 happy-path fact set 轻易通过，却没有真正回答 anchoring 阶段提出的 multi-entity fan-out 问题。

### 5.2 Rule / Entry Shape

walkthrough 应以一条 **single composite rule** 为中心，而不是多个 runs 的拼接：

- single `rule_id`
- single `rule_run_id`
- single proof-entry

这条 composite rule 至少要同时覆盖：

- 核心 suspicious movement predicate(s)
- 至少 2 类 supporting signals
- 最终把这些条件汇聚到同一个 suspicious-account result row

第一轮不要求 sequence/aggregation semantics；如果需要窗口内聚合结果，可先假定其已被上游写成 facts。

### 5.3 Delivery Path To Validate

这条 walkthrough 必须完整验证当前已有的五层 explain delivery 链：

1. `POST /queries/explain` with `kind="rule_run"`
2. `POST /queries/explain-summary`
3. `POST /queries/explain-narrative`
4. `POST /queries/explain-nl`
5. audit export + `rule_traces/{rule_run_id}.html`

关键要求：

- 不新增 endpoint
- 不新增 DTO shape
- 不新增 static page 类型
- 只验证当前 surfaces 在跨域场景下是否足够 readable/useful

### 5.4 Success Criteria For The Walkthrough

这条 walkthrough 若要算成功，至少需要同时满足：

1. `multi-entity fan-out remains readable`
   - 一个 `rule_run_id` 下的 witness predicates 仍能清晰展示 account / transactions / beneficiaries / devices / ownership signals 的组合关系
2. `investigator-facing prose remains sufficient`
   - 现有 narrative / NL explain 虽是为通用 explain 设计，但在 AML case-review 语境下仍能形成可理解的 walkthrough，而不需要新 renderer contract
3. `proof-entry remains enough`
   - investigator 能从单个 `rule_run_id` 一路 drill-down 到 assertion detail / static proof-entry page，而无需 case-level wrapper

若其中任一条件不成立，这条 walkthrough 的失败方式就应被显式记录为下一条 gap blueprint 的来源。

### 5.5 Expected Implementation Boundary

第一轮更像一个 **scenario walkthrough / regression slice**，不是新的 runtime feature slice。

当前 draft 倾向的实现边界是：

- 以 tests 为主，必要时补最小 benchmark or fixture helper
- 复用现有 runtime/audit contracts
- 若需要 durable operator-facing record，可在 archive blueprint 的 `Outcome` 中记录 walkthrough 结论，而不是新增新的 module docs contract

这里的关键约束是：

- walkthrough 可以验证“是否足够”
- 但不能为了让 walkthrough 更好看而临时改 explain contract

## 6. Boundaries And Invariants

- 必须保持的边界：
  - single composite rule run
  - single `rule_run_id` proof-entry
  - 只消费现有五层 explain delivery 栈
- 明确不做的内容：
  - 不做 case-level aggregation
  - 不做新的 AML-specific renderer / DTO
  - 不做新的 runtime semantic extension
- 兼容性约束：
  - 所有现有 explain delivery contract 必须保持不变
  - 若 walkthrough 暴露 gap，应新开 blueprint，而不是在本切片里偷扩 scope

## 7. Acceptance

- [x] synthetic AML walkthrough 已形成 single composite rule run
- [x] runtime raw / summary / narrative / NL explain 全部在该 walkthrough 下被验证
- [x] audit package / static proof-entry 在该 walkthrough 下被验证
- [x] walkthrough 已明确回答现有 substrate 对 investigator-facing consumption 是否足够
- [x] 若发现真实 gap，已在 outcome 中明确记录，但未越过本蓝图 scope

## 8. Implementation Plan

1. 定义 synthetic AML walkthrough 的最小 facts/rule shape，确保它是 single composite rule run，而不是多次运行的拼接。
2. 以该 scenario 补 runtime + audit + static 的 walkthrough regression，验证五层 explain delivery 栈。
3. 记录 walkthrough 结论：当前 substrate 是否足够，若不足，缺口具体落在哪一层。

## 9. Docs To Update

- 无默认新增；若 walkthrough 实际改变了 operator-facing truth，再补对应模块 docs

## 10. Outcome / Deviations

- 最终落地结果：
  - 在 `test_phase3_contracts_v1.py` 中新增了一条 synthetic AML suspicious-account walkthrough regression：
    - 单个 `account`
    - `>=3` 条 `transaction` facts
    - `>=2` 类 supporting signals（`shared_device_signal`、`bo_mismatch_signal`）
    - `>=1` 条与交易/受益方链路绑定的 `beneficiary_risk` fact
  - walkthrough 使用一条 single composite rule run，产出单个 `rule_run_id`，并完整验证了：
    - runtime raw explain
    - runtime summary
    - runtime narrative
    - runtime NL explain
    - audit export + static proof-entry page
  - walkthrough 结论是：对 single-rule-run investigator case review，当前 substrate 足够；尚未暴露必须先开 gap blueprint 的结构性缺口。
- 与 blueprint 不同的地方：
  - 无实质偏离；实现保持为 regression/test slice，没有新增 runtime feature、DTO 或页面类型。
- 为什么会有这些调整：
  - 不适用。
- 归档说明：
  - 本切片作为 implementation-facing walkthrough regression 完成后归档到 `docs/blueprints/archive/`。
