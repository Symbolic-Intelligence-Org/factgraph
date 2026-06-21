# Task Blueprint: Souffle eval witness — per-branch capture + arity diagnostic (decouple from monolithic)

- Status: draft
- Created: 2026-06-21
- Last Updated: 2026-06-21
- Branch: `v0.2.0-souffle-reach-chain-explain`
- Depends on: [2026-06-21_ne-primitive-lowering.md](./2026-06-21_ne-primitive-lowering.md)(`!=`→`ne`,否则 SAR 在 `!=` 处先崩,到不了 arity)
- Related Modules:
  - `src/factgraph/adapters/souffle/engine_eval.py`(`_run_query_and_read_support_rows` — 当前单体 witness 路径;`_run_query_and_read_bindings` — 精简结果路径)
  - `src/factgraph/adapters/souffle/where_compile.py` / `souffle_view_gen.py`(`build_query_witness_layout`、`witness_rel_name`、`include_pred_witness_columns`)
  - `src/factgraph/core/rules/_trace.py`、`rule_ir.py`(`ProofReceipt.pred_witnesses`、`make_pred_condition_key(case, condition, pred_id)`)
  - `src/factgraph/core/rules/ruleref_substrate.py`(ProofReceipt 的 support 消费者之一)
- Related Docs:
  - [workflow/foundations/architecture_principles.md](../../foundations/architecture_principles.md)
- Audit Log:
  - [2026-06-21_souffle-eval-witness-arity.audit.md](./2026-06-21_souffle-eval-witness-arity.audit.md)
- Related historical blueprints:
  - [2026-06-21_souffle-reach-chain-explain.md](./2026-06-21_souffle-reach-chain-explain.md)(S1 explain;eval 通后需在全 SAR 上实测其逐分支 reach arity < 22)

## 1. Problem

souffle eval 的 witness 路径(`_run_query_and_read_support_rows`)把**整个复合 OR 降成一个单体 `query__` 关系**(一分支一条规则、同头),并把**所有分支的 witness 列并入这一个关系**——实测全 SAR = `C0 + W0…W22` = **24 列**,超 souffle 2.5 的 **arity 上限 22** → `Requested arity not yet supported` → SIGABRT(`fg.eval.evaluate(..., engine="souffle")` 直接崩,demo §5 的真实 blocker)。

实证定性(三分法):**非 Case A**(精简 eval 去 witness → 全 SAR 跑通,4 行);**是 Case B**(eval 能跑、是 explain 的 witness 撑爆)+ **Case C**(用户心智每分支 ~10/13,底层并集成 24)。witness 列 = 每分支"带 witness 的 pred 原子数"(exists+字段;比较/join 不带),非用户条件数。

ProofReceipt **承重**(已核实消费者:`support_digest→ProofReceipt` sidecar readback、`ruleref_substrate` 子规则子证明),**不能直接丢**。

## 2. Goals

- 大复合(全 SAR)在 `engine="souffle"` 下 **eval 成功**,且 **ProofReceipt 保留**(消费者不回归)。
- witness arity 回到**逐分支**量级(对齐用户"逐分支"心智),不再分支并集。
- 残留 Case A(单分支自身 > arity 上限)给**明确诊断**,不再 SIGABRT。
- 与 ne 修复 + S1 合,demo §5 **端到端**(eval + explain)通。

## 3. Non-goals

- 不碰 native / problog eval。
- 不在本单统一 eval-witness 与 S1 reach_explain 的两套逐分支机制(将来可统一,本单不做)。
- exists 折叠为**可选**(stretch),非必做。

## 4. Current Context

- 入口:`engine_eval._run_query_and_read_support_rows`(witness 路径,234 `include_pred_witness_columns: True`);返回 None 则落 `_run_query_and_read_bindings`(精简路径,已存在、实证可跑全 SAR)。
- souffle 2.5 arity 上限 = **22**(实测:22 OK、23 FAIL)。全 SAR 单体 = 24;逐分支 = 10 / 13(均 < 22)。
- ProofReceipt 按 `(case_index, condition_index)` 编码(`make_pred_condition_key`),**天然可逐分支拼装**。
- 依赖 ne 修复(`!=`→`ne`)。

## 5. Proposed Shape(分三段)

### Phase 1 — 临时补丁:arity 诊断(简单、低风险、先行)
在 witness layout / 构建时**计算每(子)关系的 witness arity**(带 witness 的 pred 数 + key 列)。**若 ≥ souffle 上限(22)**,抛**明确 `WhereValidationError`**:点名是哪条分支、多少个带 witness 的 pred、**哪些原子贡献(含隐式 `:exists`)**、以及上限——取代当前 cryptic SIGABRT。这让 Case A/超限**可预测、可读**(对齐心智)。

### Phase 2 — 主修:逐分支 witness 捕获
- **结果关系精简**:`query__(C0)` 只出结果(窄,任意复合都 < 22)。
- **逐分支 witness 关系**:每分支一个 `query__b{k}_w(C0, <该分支 witness>)`,各自窄(≤ 该分支 pred 数 + key)。
- **ProofReceipt 从逐分支 witness 关系拼装**(按 case/condition;ProofReceipt 结构已支持)。
- 结果:eval 不再撞 arity;ProofReceipt 全保留(consumers 不回归)。

### Phase 3 — 可选:`:exists` 折叠
同实体已有字段 pred 时,其隐式 `:exists` 的 witness 可折叠(字段查找已蕴含存在)→ 进一步压低逐分支 arity。代价:exists claim 单独 asrt 不再单列(需确认可接受)。**stretch,非必做。**

## 6. Boundaries And Invariants

- 只改 souffle eval 的 witness 捕获;native/problog 不动;S1 explain 不动(正交)。
- **ProofReceipt 语义保留**:逐分支拼出的 ProofReceipt 与原单体在 `pred_witnesses` 内容上等价(consumers:sidecar/ruleref 不回归)。
- 诊断是**明确报错(clear error)**,不是静默降级。
- 精简结果路径与逐分支 witness 路径**结果集一致**(与 native 对齐)。

## 7. Acceptance

- [ ] 全 SAR `engine="souffle"` **eval 成功**(4 行,与 native 一致),**ProofReceipt 存在**且 `pred_witnesses` 与逐分支证据一致。
- [ ] ProofReceipt **consumers 零回归**(support_digest 读回、ruleref 子证明)。
- [ ] 构造一个**单分支带 witness 的 pred > 22** 的规则 → 得到**明确诊断**(点名分支/计数/贡献原子/上限),**非 SIGABRT**。
- [ ] eval 通后,**S1 reach_explain 在全 SAR 上实测**:各分支 reach 关系 arity < 22,narrate 相干(Eo 非 M*)。
- [ ] native / problog eval + explain **零回归**。
- [ ] ne + S1 + 本单:**demo §5 souffle 端到端**(eval + narrate)通。
- [ ] `PYTHONPATH=src` 相关 souffle/explain/ruleref 测试绿 + 新增 arity 诊断 + 逐分支 ProofReceipt 等价回归。

## 8. Implementation Plan

1. [Phase 1] witness arity 计算 + 上限诊断(`engine_eval`/`where_compile` 构建期),clear `WhereValidationError`。先行、可独立验。
2. [Phase 2] 逐分支 witness 关系 codegen(结果精简 + 每分支 witness 关系)+ ProofReceipt 逐分支拼装。
3. [验证] 全 SAR eval 通 + ProofReceipt 等价 + ruleref consumer 不回归 + S1 全 SAR 实测。
4. [Phase 3, 可选] `:exists` 折叠(确认 asrt 取舍后)。
5. [docs] souffle adapter docs:witness arity、逐分支捕获、Case A 诊断、残留限制。

## 9. Docs To Update

- `src/factgraph/adapters/souffle/docs/`(witness 捕获、arity 上限与诊断、逐分支)
- `src/factgraph/core/docs/01_architecture.en.md`(ProofReceipt 逐分支捕获,如涉及)

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
