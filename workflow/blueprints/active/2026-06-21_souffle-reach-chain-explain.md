# Task Blueprint: Souffle dedicated reach-chain explain (engine separation — step 1 / S1)

- Status: implemented
- Created: 2026-06-21
- Last Updated: 2026-06-21
- Branch: `v0.2.0-souffle-reach-chain-explain`
- Related Modules:
  - `src/factgraph/adapters/souffle/reach_explain.py` (**NEW** — souffle-dedicated reach-chain explain; do NOT extend old `diagnostic_emit.py`)
  - `src/factgraph/sdk/store.py` (`_souffle_row_graph_builder` ~2957 reroute; `_souffle_diagnostic_projection_graph` ~2991 retired for souffle; `_souffle_support_artifact_to_evidence_graph` ~4410 = degrade target)
  - `src/factgraph/adapters/souffle/engine_eval.py` (`_materialize_adapter_derivation_plan(plan, engine="souffle")`, witness columns / `generate_view_dl(include_witness_views=True)` / `witness_rel_name`)
  - `src/factgraph/adapters/souffle/where_compile.py` (atom compile logic for compare/`not`/type domains — extract a small adapter helper, do NOT reuse private `_compile_atom` directly)
  - `src/factgraph/adapters/souffle/package.py` (`export_package`; line ~372 still writes whole-ledger facts — fact filtering DEFERRED out of S1)
  - `src/factgraph/adapters/souffle/{runner.py, provenance.py}` (`run_package`, `find_souffle_binary`; `run_provenance_explain` — borrow subprocess/JSON style only)
  - `src/factgraph/application/explain/diagnostic_projection.py` (shared companion — souffle DECOUPLES; problog keeps it)
  - `src/factgraph/core/rules/{_trace.py, rule_ir.py}` (`RuleTracePredWitness`; `make_pred_condition_key(case_index, condition_index, pred_id)` coordinate)
- Related Docs:
  - [workflow/foundations/architecture_principles.md](../../foundations/architecture_principles.md)
- Audit Log:
  - [2026-06-21_souffle-reach-chain-explain.audit.md](./2026-06-21_souffle-reach-chain-explain.audit.md)
- Related historical blueprints:
  - [2026-03-28_evidence-graph-unified-explain.md](./2026-03-28_evidence-graph-unified-explain.md) (unified EvidenceGraph IR — the unify point)
  - [2026-06-20_problog-companion-explain-rewrite.md](./2026-06-20_problog-companion-explain-rewrite.md) (problog half — DEFERRED until souffle verified)

## 1. Problem

Souffle 下规则的 `Explanation.narrate()`(单规则 + 复合,凡有 `lowering_plan`)走**共享引擎中立 companion 投影**
(`_souffle_diagnostic_projection_graph` → `build_companion_program` → `run_diagnostic_souffle` → `diagnostic_problog_result_to_evidence_graph`),有**两个叠加缺陷**(实测确证):

1. **标签不相干**:companion 的 `_anchor_for_row` 只锚公共头端口,内部证明变量留空;`diagnostic_emit.py::_emit_branch` **逐原子 emit 成独立规则** → 各自重绑、各挑一条代表事实。实测 C-EVE 的 `forwards_out` 证明出现 `Txn M2a exists` / `Txn M1o direction is out` / `27000 >= 20000`(全是别的客户的交易)+ `!<unbound> equals <unbound>`。**结构对、逐原子标签误导**,对可审计 SAR 不可接受。
2. **性能:整跑原推理**:`run_diagnostic_souffle` `export_package(query=None)` 导出整 package + 把诊断追加到**完整 idb** 后整跑 → 每次 explain **重跑整个原推理**(同形状 problog companion 实测 49 笔→32 s)。

对照:native 复合 narrate(`probe_native` meta-interpreter)标签相干、正确。问题集中在 **souffle × 共享 companion**。
**发布暴露**:`narrate()` 与 explain 完整能力**已在对外文档中声明**,视为已交付功能的正确性问题。

## 2. Goals

- Souffle 复合/单规则 `narrate()`:**逐原子标签相干**(引用该行真正绑定的事实,如 C-EVE 的 Eo),无 `<unbound>`/`edb_fact`/`'='`。
- **失败分支可解释**:给出失败的具体条件 + **失败点的真实绑定值**(如 `tenure 2000 < 90`),取自 souffle 真实求值。
- **成立侧带真实 asrt provenance**。
- **完全来自 souffle 真实求值,不依赖 native/prober**(引擎自治)。
- **性能(诚实表述)**:reach-chain **作为独立 query 程序单跑**——不再 `export_package(query=None)` 现状、不再追加完整 idb、**不再每次 explain 重跑原 idb/rule graph**。(注:S1 仍允许全量 facts export,故 wall-time 仍可能随 ledger 事实数线性;事实导出过滤 deferred。本目标只针对"不重跑原推理",不承诺绝对亚线性。)
- **引擎分离 step 1**:souffle 拥有专属 explain 模块,与共享 companion 解耦;立住"plan 静态骨架 + 引擎真实 trace 回填"模式供后续 problog 复用。

## 3. Non-goals

- **不碰 problog**(仍走共享 companion,修复另立单)、native、pyreason。
- **subject 邻域事实过滤**:DEFERRED(stretch / S2-S3);S1 允许全量 facts export。
- **递归 / `ruleref` / aggregate 的 explain**:S1 **直接降级**,不做半吊子;递归单独立 **S2**。
- **aggregate 失败值**:S1 不承诺。

## 4. Current Context

- **路由**:`store.py::_row_graph_builder_for_engine`(2921)→ `engine=="souffle"` → `_souffle_row_graph_builder`(2957):有 `lowering_plan` → `_souffle_diagnostic_projection_graph`(companion,**错**);失败/无 plan → ProofReceipt 渲染(扁平,fallback)→ minimal。
- **设计岔口已定**(Codex 实查):`provenance.py::run_provenance_explain`(line 151,souffle `-t explain`)**只解释已成立 proof**,无"前缀成立但下一条件失败"模型,输出是 proof-node/rule-number tree、非 `(case,condition)` 坐标,**不能提供失败值**。→ **自建 reach-chain**,只借其 subprocess/JSON 风格。
- **现有可复用件**:`_materialize_adapter_derivation_plan(plan, engine="souffle")` 给 materialized `body_ir` + trace(join/head-link 已成 `eq`,坐标与 engine eval 一致);`generate_view_dl(include_witness_views=True)` / `witness_rel_name` 提供 pred witness 列;`where_compile.py` 有 compare/`not`/类型域逻辑;souffle 真实 witness 已捕获成 `ProofReceipt.pred_witnesses`(`pred_condition_key` 编码 case/condition)。
- **性能现状根因**:`package.py:372` 写全库事实;诊断追加到完整 idb 整跑。
- **souffle 二进制**:`/opt/homebrew/bin/souffle`,**arm64 原生,无 Rosetta**。
- **已知约束**:Datalog 只 witness 成功;失败定位靠固定 head + reach 前缀(已 PoC 验证,§5.4)。

## 5. Proposed Shape

**核心:新建 souffle 专属 reach-chain 模块,完全取代 souffle 走共享 companion 的路径。**

### 5.1 reach-chain(已用真实 souffle 验证 —— §5.4)
对一条 branch 的有序 atom A₁…Aₙ,emit 相互链接、携带累积绑定的 relation,锚在 subject 上:
```
reach1(c, a_c)            :- subject(c), A1(c, a_c).
reach2(c, td, a_c, a_t)   :- reach1(c, a_c), A2(c, td, a_t).
reach3(c, td)             :- reach2(c, td, _, _), A3(td).   ...直到 An
```
读回(逐 subject):**holds(Aᵢ)** = subject ∈ `reachᵢ`(成立 pred 的 asrt 在列里);**fails(A_{k+1})** = subject ∈ `reach_k` 但 ∉ `reach_{k+1}` → 失败条件 = A_{k+1},**失败值/候选事实 = `reach_k` 元组**;**not_reached(A_{>k+1})** = 上游 reach 空。绑定顺着链在 souffle 内部串成一致。

### 5.2 装配:plan 静态骨架 + reach 回填
`EvidenceGraph` 结构形状取自**静态 `lowering_plan` / `rules_by_id`**(引擎无关,非 native 执行);每原子 verdict/标签/asrt/失败值按 `make_pred_condition_key(case, condition, pred_id)` 坐标回填。**多候选 tuple 必须选与该行 binding 一致的那条,不得任取第一条。** 全程无 native/prober。

### 5.3 S1 实现(专属模块 `reach_explain.py`)
1. **codegen**:从 `_materialize_adapter_derivation_plan(plan, engine="souffle")` 拿 materialized body_ir + trace → 按 branch atom 顺序生成 reach-chain relations(累积绑定列;pred 用 witness-view 列带 asrt)。compare/`not`/类型域走从 `where_compile` 抽出的 adapter 内部小 helper(不直接复用私有 `_compile_atom`)。
2. **独立单跑**:reach-chain 作为**独立 query 程序**运行(base 关系 + reach 规则;**不追加完整 idb、不重跑原推理**)。S1 全量 facts export 可接受。
3. **解析 + 装配**:reach 输出 → 逐 (branch,condition) holds/fails/not_reached + 失败值 + asrt(§5.2 多候选规则)→ `EvidenceGraph`。
4. **改路由 + 降级**:`_souffle_row_graph_builder` 主路由到 `reach_explain`;`_souffle_diagnostic_projection_graph` 不再用于 souffle。

### 5.4 可行性证据(真实 souffle PoC,2026-06-21 —— 见 `…poc/`,`run.sh` 复现)
- 比较失败取值:`na_r2=(C-EVE,2000,…)`,`na_r3`(td<90)无 C-EVE → 失败值 td=2000 + 成立侧 asrt。
- pred 链失败定位+取值:`fo_r3=(C-DANA,Do,4000,a_do)`,`fo_r4`(amt>=20000)无 C-DANA → 失败值 amt=4000 + 真实事实 Do + asrt。
- 一次 run 出 2 分支 × 3 subject;绑定相干;asrt 贯穿。→ **"souffle 引擎内给失败值"已证可行**。

### 5.5 S1 supported **materialized** atom set + 降级
S1 支持的是 **materialized where IR**(`_materialize_adapter_derivation_plan` 之后,非源 DSL/AST)里的:`pred`、`eq`、`ne`、`gt`、`ge`、`lt`、`le`、以及包一个 `pred` 或比较的简单 `not`(`not(pred)` / `not(eq)` 等)。
**其余 materialized atom(`ruleref`、`agg`、嵌套/多原子 `not`)→ 降级**(见 §6 降级不变量)。

### 5.6 递归 / `ruleref` / aggregate —— DEFERRED
S1 遇到 `ruleref`/递归/aggregate **直接降级**(不做半吊子 explain)。递归的 reach-chain 设计(`ruleref_links` 嵌套子链 vs souffle 递归)独立成 **S2**。

## 6. Boundaries And Invariants

- **降级不变量(硬)**:任何不支持的 materialized atom、或 `ruleref`/递归/aggregate → souffle row builder 路由到现有 **ProofReceipt 渲染(`_souffle_support_artifact_to_evidence_graph`)或 minimal**;**Souffle 的 `lowering_plan` 绝不再走旧 shared companion(`_souffle_diagnostic_projection_graph`)**。此项优先级高于"尽量 rich"。
- 只改 souffle explain 路径;共享 companion 对 problog 不动;native / pyreason 不回归。
- 忠实性:展示的标签/值/asrt 必须来自 souffle 真实求值;`not(pred)` 成立时只展示相关外层绑定,**不编造缺失事实**。
- 多候选 tuple 选择必须与行 binding 一致;比较的数值/符号类型域对齐 `where_compile.py`。
- v1 per-row;批量多 subject 后续。
- `EvidenceGraph`/`EvidenceTree`/`EvidenceAtom` IR 不变(统一点);仅 souffle builder + 新模块内部。

## 7. Acceptance

- [ ] souffle **单规则** narrate(forwards_out, C-EVE):标签全部引用 C-EVE 自己的交易(`Txn Eo …`),**无 `M*` / `<unbound>` / `edb_fact` / `'='`**。
- [ ] souffle **复合** narrate(SAR, C-EVE):分支结构与 native 一致;成立分支原子带 souffle **真实 asrt**;**失败分支给出失败条件 + 真实失败值**(`tenure 2000 < 90`)。
- [ ] **失败值正确**:取自 reach-chain 最后非空 reach 的真实绑定值,非 `<unbound>`;多候选时与行 binding 一致。
- [ ] **性能(诚实)**:souffle explain **不再 `export_package(query=None)` 现状、不再追加完整 idb、不再重跑原 idb/rule graph**(reach-chain 独立单跑)。*不要求*绝对亚线性(全量 facts export 仍可能随 ledger 线性;事实过滤 deferred)。
- [ ] **降级不变量**:`ruleref`/递归/aggregate/不支持 atom → 路由 ProofReceipt 或 minimal;**souffle lowering_plan 不再触发旧 companion**(`_souffle_diagnostic_projection_graph` 对 souffle 成死路)。
- [ ] **零回归**:native / problog / pyreason narrate 不变(problog 仍走旧 companion)。
- [ ] `PYTHONPATH=src pytest` 相关 souffle / explain 测试绿;新增 reach-chain 回归(标签相干 + 失败值 + 降级路由 + S1 atom 集)。
- [ ] souffle explain 模块 docs 更新(reach-chain 机制、S1 能力/降级、失败语义)。

## 8. Implementation Plan

1. [impl 前确认] 核对 `_materialize_adapter_derivation_plan(plan, engine="souffle")` 产出 materialized body_ir + trace(join/head-link 为 `eq`、`(case,condition)` 坐标一致);`generate_view_dl(include_witness_views=True)` / `witness_rel_name` 可用。**有出入停下回报。**
2. [reach_explain.py 新建] codegen:materialized branch/atom → reach-chain relations(累积绑定列 + pred witness-view + asrt);S1 atom 集(§5.5);compare/`not`/类型域用抽出的 helper;遇不支持 → 标记降级。
3. [reach_explain.py] 独立 query 程序单跑(不追加完整 idb / 不重跑原推理);全量 facts export 可接受。
4. [reach_explain.py] 解析 reach 输出 → 逐 (branch,condition) verdict + 失败值 + asrt;多候选按行 binding 选。
5. [装配] reach 结果 → `EvidenceGraph`(静态 plan/rules_by_id 形状 + `make_pred_condition_key` 坐标)。
6. [store.py] `_souffle_row_graph_builder` 主路由到 `reach_explain`;降级 → ProofReceipt → minimal;**绝不回旧 companion**;`_souffle_diagnostic_projection_graph` 对 souffle 退役。
7. [tests] 标签相干 / 失败值 / 降级路由(`ruleref`/`agg` → ProofReceipt/minimal,非 companion)/ 其他引擎零回归。
8. [docs] souffle explain 模块 docs。

## 9. Docs To Update

- `src/factgraph/adapters/souffle/docs/` + `src/factgraph/application/explain/docs/`(souffle reach-chain 机制、S1 能力/降级边界、失败语义、与 native/companion 分工)
- `docs/README.md`(通常无新持久入口,不需)

## 10. Outcome / Deviations

- 最终落地结果：`reach_explain.py` 专属 reach-chain explain;souffle lowering_plan 不再走旧 companion(`_souffle_diagnostic_projection_graph` 死路);commit `359b2ed8`(+ `fb3044c5` 收窄宽分支 arity)。
- 与 blueprint 不同的地方：装配复用共享 `diagnostic_problog_result_to_evidence_graph`(喂 reach 解析结果),非全新装配器;新增 runner-exit 安全检查防"空输出假 rich"。
- 为什么会有这些调整：复用已验证装配器更稳;安全检查防止 souffle 崩/假 rich。
- 归档说明：已实现并提交;保留 active/ 作 problog 参照(同模式),后续与同组一并归档。
