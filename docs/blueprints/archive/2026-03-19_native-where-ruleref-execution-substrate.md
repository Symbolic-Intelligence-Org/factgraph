# Task Blueprint: Native Where RuleRef Execution Substrate

- Status: implemented
- Created: 2026-03-19
- Last Updated: 2026-03-19
- Related Modules:
  - `src/factpy_kernel/core/rules/where_eval.py`
  - `src/factpy_kernel/core/rules/rule_ir.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/_builders.py`
  - `src/factpy_kernel/core/derivation/candidates.py`
  - `src/factpy_kernel/sdk/store.py`
  - `src/factpy_kernel/sdk/query_runtime.py`
  - `src/factpy_kernel/sdk/dsl/rule.py`
  - `src/factpy_kernel/authoring/derivation_compile.py`
  - `src/factpy_kernel/service/runtime_v1.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/session_handoff_2026-03-19.md](../../session_handoff_2026-03-19.md)
  - [2026-03-19_native-derivation-ruleref-execution-decision.md](./2026-03-19_native-derivation-ruleref-execution-decision.md)
  - [2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md](./2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](../active/2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/sdk/docs/03_rules_and_derivations.md](../../../src/factpy_kernel/sdk/docs/03_rules_and_derivations.md)
  - [src/factpy_kernel/authoring/docs/01_overview.md](../../../src/factpy_kernel/authoring/docs/01_overview.md)
- Audit Log:
  - [2026-03-19_native-where-ruleref-execution-substrate.audit.md](./2026-03-19_native-where-ruleref-execution-substrate.audit.md)

## 1. Problem

上一轮 capability decision 已经确认：

- `native derivation` 应支持 `RuleRef` 执行语义
- 这是一条独立 capability line，不属于 recursive proof tree 的尾部补丁

但当前代码扫描显示，如果只在 derivation path 上补 `RuleRef`，很容易把现有漂移状态扩大成更多 patch：

- `Query` 的 where 语言也接受 `RuleRef`，但 runtime 仍直接走 `evaluate_where(...)`
- `sdk.run(rule)` 拥有 registry wiring 与 dependency registration，而 `query + derivation` 都没有
- native support capture 仍按 “所有 OR 分支都遍历一遍” 的保守策略构建 witness
- candidate plumbing 仍假设单 candidate 对应单 support

因此，这一轮不应再写成 `derivation-only RuleRef support`。更合理的重构单位是：

- **native where execution substrate**

它的 owner 至少应覆盖：

- `query`
- `derivation`

并尽量与 `rule runtime` 的 `RuleRef` resolution semantics 对齐，而不是继续让三条路径各自持有半套 where 语义。

## 2. Goals

- 把当前问题从 `derivation 支持 RuleRef` 提升为 `native where RuleRef execution substrate` 的共享重构。
- 明确 first-round owner 是 `query + derivation`，不是仅 derivation。
- 冻结这条共享 substrate 在分层、registry 注入、执行边界、capture 边界上的基本形状。
- 把这轮实际代码扫描暴露的雷点写成 scope freeze 前必须正视的约束。
- 为后续 `scoped` implementation 提供明确的“不允许的补丁式做法”。

## 3. Non-goals

- 不在本蓝图中直接实现 shared substrate。
- 不把 `run_rule` trace 与 `SupportArtifact` 合并成一个 explain carrier。
- 不在本轮引入 graph、salience、certainty、snippet/span provenance。
- 不在本轮承诺完整 multi-proof / full alternative-support preservation。
- 不把 query 变成 explain-producing API；query 仍只返回 rows / hydrated values。
- 不在本轮重新设计整个 `RuleTraceArtifact`。

## 4. Current Context

- 当前 formal native where execution 已分裂成两套主路径：
  - `query` / `derivation` 走 `core.rules.where_eval.evaluate_where(...)`
  - `rule runtime` 走 `core.rules.rule_ir` 中的 registry-backed `RuleRef` rewrite/evaluate path
- 当前直接代码证据：
  - `where_eval.evaluate_where(...)` 在 AST gate 中固定 `capabilities={"allow_ruleref": False}`
  - `_validate_atom(...)` 也会把 `ruleref` 视为 unsupported atom kind
  - `sdk.query_runtime.execute_query_plan(...)` 直接 lower query 再调用 `evaluate_where(...)`
  - `sdk.store._run_dispatch_query(...)` 当前直接丢弃 `registry`
  - `sdk.evaluate(...)` 的 derivation path 最终调用 `core.store.evaluate(...)`，也没有 registry-backed `RuleRef` substrate
  - 与之相对，`sdk.run(rule)` 会自动注册 dependency rules，`rule_ir` 也已具备 `RuleRef` rewrite、registry lookup、cycle guard、memo 与 child invocation capture
- 当前 contract 漂移：
  - SDK 文档把 `RuleRef(...)(...)` 列为通用 where 支持语法
  - `Query` 构造期 where AST 校验并未显式禁用 `RuleRef`
  - authoring 文档也把 runtime session 与 `RuleRef` 解析联系起来
  - 但 formal native execution path 仍拒绝 `ruleref`
- 当前额外雷点：
  - native support capture 目前会遍历所有 OR 分支，而不是 narrowing 到真正产生 binding 的 winning branch
  - candidate support backref 仍是一对一，且 builder 以 `candidate_key` 折叠 support
  - derivation / query 编译阶段都没有做 registry-backed `RuleRef` target preflight

## 5. Proposed Shape

### 5.1 Scope Positioning

本蓝图要冻结的不是某个 call site 的补丁，而是一个共享分层：

1. `where language`
   - `pred / eq / cmp / not / ruleref` 继续属于同一套 where 语言
2. `RuleRef resolution / lowering substrate`
   - 显式接收 registry context
   - 负责 `RuleRef` target lookup、arity/expose 校验、recursion guard、memo 语义
   - 产出 lowered where / overlay facts / child evaluation handles
3. `execution consumers`
   - `query`
   - `derivation`
4. `artifact consumers`
   - `query` 继续只消费 bindings / hydrated rows
   - `derivation` 继续消费 `CandidateSet + SupportArtifact`
   - `rule runtime` 继续拥有 `RuleTraceArtifact`，但其 `RuleRef` resolution semantics 应尽量与共享 substrate 对齐

### 5.2 First-Round Owner

first-round 必须同时覆盖：

1. `query`
2. `derivation`

拒绝的路线：

- 只让 derivation 支持 `RuleRef`
- query 继续停留在 “语法允许、执行不支持”

原因是这会把当前 contract drift 从一处保留成两处。

### 5.3 Registry Injection Rule

`RuleRef` 不能依赖隐式全局 registry，也不能只在底层 core 中偷偷“如果有就用”。

first-round 必须冻结一条显式规则：

- 任何 native where 执行若允许 `RuleRef`，都必须拥有明确的 registry context

这意味着后续实现至少要回答：

1. `SDKStore.run(Query(...), registry=...)` 是否正式接入 registry
2. `sdk.evaluate(Derivation(...))` 如何拿到 registry-backed substrate
3. service/runtime 的 derivation evaluate path 如何接入相同输入，而不是继续只走裸 `Store.evaluate(...)`

没有 registry context 的场景，应保持 fail fast 或显式不支持，而不是隐式降级。

基于当前代码表面，first-round 更合理的 registry injection shape 应明确收口为：

#### A. SDK surface: use `RuleRegistry`, not `SDKRegistry`

- `SDKStore.run(Query(...), registry=RuleRegistry | None)` 继续作为 query 的 canonical registry injection surface
- `SDKStore.evaluate(..., registry=RuleRegistry | None)` 应新增为 derivation 的 canonical registry injection surface
- first-round 不建议把 runtime execution surface 直接做成 `SDKRegistry` / `root_dir` 驱动
  - `SDKRegistry` 属于 authoring/registry facade
  - shared execution substrate 应消费已经规范化的 `RuleRegistry`

#### B. SDK default behavior: auto-register only object-backed dependencies

- 当 `registry is None` 且 where 中使用的是 `RuleRef(existing_rule_obj)`：
  - 可以沿用当前 `sdk.run(rule)` 的 ergonomic 方向
  - 但不应再只限于 `Rule`，而应提升成 where-level dependency extraction，可服务 `Query + Derivation`
- 当 where 中使用的是字符串 `RuleRef("rule_id", version=...)`：
  - first-round 不应猜测或隐式装载外部 registry
  - 应要求显式提供 `RuleRegistry`
  - 否则 fail fast

也就是说，自动补依赖只适用于 SDK object graph 内已携带的 `RuleObj` 引用，不适用于裸字符串 rule id/version。

#### C. Service surface: reuse `registry_root` semantics already used by `/rules/run`

- `POST /v1/runtime/sessions/{session_id}/derivations/evaluate` 不应发明新的 registry DTO 字段
- first-round 应直接复用：
  - `override_registry_root`
  - legacy alias `registry_root`
  - fallback to `session.registry_root`
- 这与当前 `/rules/run` 的 registry surface 保持一致

当前 service 并没有与 SDK `Query` 对称的 runtime query-execution endpoint，因此 first-round service scope 不需要额外定义 `query` 的 HTTP registry DTO。若未来新增该端点，应复用同一套 root-based surface，而不是再发明第三种注入方式。

#### D. Internal normalized form: always enter substrate with explicit `RuleRegistry | None`

- SDK object-facing surface 与 service root-facing surface 可以不同
- 但在进入 shared substrate 之前，必须统一成显式的 `RuleRegistry | None`
- derivation path 最自然的 first-round 位置是：
  - `Store.evaluate(..., registry=RuleRegistry | None)`
- query path 则应把同一类型的 registry 显式传入 shared executor，而不是继续依赖裸 `evaluate_where(...)`

#### E. Preflight surface stays separate

- 编译 / preflight 层可以继续采用 `registry_payloads` 一类的结构化输入
- first-round 不要求把 preflight surface 与 runtime injection surface 做成同一种参数形态
- 但二者都必须指向同一个规则：`RuleRef` target 校验不能只在最深执行层才失败

### 5.4 Shared Semantics Rule

这轮重构的目标不是复制 `rule_ir` 到别处，而是共享或抽取其核心 `RuleRef` 语义：

- target resolution
- expose gate
- arity validation
- recursion / cycle guard
- memo behavior

但 first-round 不要求把 `rule_ir` 的全部 `RuleRef` 语义一次性抽走。这里需要显式划定抽取边界：

- first-round shared substrate **必须至少覆盖**：
  - target resolution
  - expose gate
  - arity validation
  - recursion / cycle guard
- memo behavior 在 first-round 可以保持保守：
  - 不做 memo
  - 或只做 per-evaluation scope memo
- first-round **不要求** shared substrate 产出 `RuleTraceArtifact` 级别的细节：
  - overlay rewrite 可继续保留为 `rule_ir` 独有实现细节
  - child invocation capture 可继续保留在 `rule_ir` path
  - `ruleref_links` recording 也可继续保留在 `rule_ir` path

这意味着 first-round 的 shared substrate 更像是：

- 为 `query + derivation` 提供统一的 `RuleRef` execution semantics

而不是：

- 直接重建整个 `rule runtime trace` 体系

对 derivation 来说，first-round 的 capture 目标也应保持克制：

- 只需要为后续 proof work 预留最小 child-proof edge handle
- 不需要拿到完整 child invocation tree

允许的结果：

- `query + derivation` 复用一个共享 substrate
- `rule runtime` 继续保留独立 trace carrier

不允许的结果：

- `where_eval.py` 一套 `ruleref` 逻辑
- `_evaluate.py` 再一套
- service/runtime 再一套 call-site patch

### 5.5 Branch-Winning Constraint

当前 native support capture 对 OR-of-AND 采用“全分支遍历”策略，这在只记录 `pred_witnesses` 时还算可接受，但如果直接挂上 `RuleRef` child handles，会把 non-winning branch 也解释成 proof dependency。

因此 first-round 必须明确：

- shared execution substrate 可以先落地于 execution semantics
- 但 derivation-side `RuleRef` support capture 不能盲目复用当前全分支遍历语义

在 freeze 到 `scoped` 之前，至少要明确二选一：

1. 先定义 winning-branch narrowing
2. 或 first-round 暂不承诺多分支 `RuleRef` child proof capture，只先让 execution substrate 成立

当前更稳的 first-round 选择是第 2 条：

- 先让 shared execution substrate 成立
- 多分支 `RuleRef` child proof capture 继续 deferred
- 等 execution substrate 与单-support capture 边界稳定后，再单独讨论 winning-branch semantics

### 5.6 Single-Support Constraint

当前 candidate plumbing 仍是单 support 假设：

- builder 会按 `candidate_key` 折叠候选
- runtime 只保留单个 `candidate_id -> support_digest`
- `candidate_id` 自身也不编码 `support_digest`

因此 first-round 不应假装已经支持 “同一 candidate 持有多条 `RuleRef` proof path”。

更稳的 first-round 边界是：

- shared execution substrate 可以先支持 `RuleRef`
- derivation support capture 只在单-support 约束内工作
- multi-support / alternative proof preservation 继续显式 deferred

### 5.7 Preflight Rule

如果 `RuleRef` target lookup / expose / arity 只在深层执行时才失败，`query + derivation` 会继续保留糟糕的 operator experience。

因此 first-round 至少要冻结一个原则：

- registry-backed `RuleRef` target validation 不能只存在于最深执行层

它可以落在：

- 编译/preflight 层
- 或 shared execution substrate 的入口 preflight

但不能继续只有 `rule_ir` path 才拥有这类校验。

### 5.8 Sequencing With Recursive Proof Work

本蓝图是 `recursive proof semantics` 的上游依赖，但不等于树语义本身。

顺序保持如下：

1. 先收口 shared native where `RuleRef` execution substrate
2. 再决定 derivation capture 在 first-round 能稳定交出什么 child-proof handle
3. 之后 `recursive proof semantics` 蓝图才有资格从 `draft` 推进到 `scoped`

## 6. Boundaries And Invariants

- 必须保持的边界：
  - owner 至少覆盖 `query + derivation`
  - `SupportArtifact` 与 `RuleTraceArtifact` 继续分离
  - registry injection 必须显式
  - shared substrate 先于 recursive proof tree freeze
- 明确不做的内容：
  - 不用补丁式方式在多个 call site 各写一段 `ruleref` 分支
  - 不承诺第一轮就解决 multi-support
  - 不把 query 变成 explain API
- 兼容性约束：
  - 若后续实现正式开放 `RuleRef` in query/derivation，必须同步收口 SDK/docs、authoring/docs、core/docs 与 service/docs，消除当前 contract drift

## 7. Acceptance

- [x] 已明确 first-round owner 是 `query + derivation`
- [x] 已明确 shared substrate 的分层、registry 规则与禁止的补丁式做法
- [x] 已把 branch-winning、single-support、preflight 三类雷点写成 freeze 前约束
- [x] 已明确与 `recursive proof semantics` 蓝图的前后依赖关系
- [x] 进入实现后，相关模块 docs 已同步更新

## 8. Implementation Plan

1. 先把本蓝图保持在 `draft`，继续验证 shared substrate 最小边界，而不是直接改某个 call site。
2. 明确 registry injection 的 owner 和入口，至少覆盖 `SDK Query`、`SDK evaluate(Derivation)` 与 service/runtime derivation evaluate。
3. 设计或抽取共享 `RuleRef` resolution/lowering substrate，避免 `where_eval` / `_evaluate` / service 三处复制逻辑。
4. 在不打开 multi-support 的前提下，定义 derivation first-round capture 如何与 shared substrate 对接。
5. 只有当上面这些点收口后，才把蓝图推进到 `scoped` 并进入实现。

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`
- `src/factpy_kernel/authoring/docs/01_overview.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - 新增了 `core.rules.ruleref_substrate.evaluate_native_where(...)`，作为 `query + derivation` 共享的 native `RuleRef` execution substrate。
  - `Store.evaluate(..., registry=RuleRegistry | None)` 现在可显式接入 registry-backed native `RuleRef` 执行；native support capture 也会记录 direct `rule_refs`。
  - `sdk.run(Query(...), registry=...)` 与 `sdk.evaluate(Derivation(...), registry=...)` 已接入相同的 registry-normalized substrate。
  - SDK object graph 内的 `RuleRef(RuleObj)` 依赖提取已提升到 where-level，可同时服务 `Query + Derivation + Rule`。
  - service `/derivations/evaluate` 已复用 `/rules/run` 的 `override_registry_root` / `registry_root` / `session.registry_root` 语义，并把它规范化为 runtime `RuleRegistry` 后再执行。
  - `rule_ir` 没有被整段复制；first-round 仅抽取了共享 resolution helper，trace carrier 仍保持独立。
- 与 blueprint 不同的地方：
  - 没有额外新增单独的编译期 registry preflight surface；first-round 采用 shared substrate 入口 preflight 来兑现 target/expose/arity 校验。
  - first-round 的 support capture 只记录 direct `rule_refs`，没有把 `rule_ref_id + child_support_digest` 级别的 child-proof handle 一起引入。
- 为什么会有这些调整：
  - 入口 preflight 已满足 blueprint 对 operator experience 的最低要求，同时避免把 authoring/preflight scope 一起拉宽。
  - child-proof handle 与多分支 winning semantics 仍然耦合，继续 defer 更符合 scoped freeze 的窄边界。
- 归档说明：
  - 本蓝图已实现；归档副本应保留 first-round shared substrate 的冻结边界与当前 deferred 项。
