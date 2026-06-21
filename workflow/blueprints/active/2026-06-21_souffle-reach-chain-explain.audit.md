# Audit Log: Souffle dedicated reach-chain explain (engine separation — step 1)

Paired with [2026-06-21_souffle-reach-chain-explain.md](./2026-06-21_souffle-reach-chain-explain.md).

## 2026-06-21 — Open (draft) + 前置调查 + PoC 验证 (Claude)

### 由来
源自 problog 复合 narrate 退化调查([2026-06-20_problog-*]):`!=` 标准修复回退后,深挖发现问题**不止 problog、不止复合**——是**非 native 引擎的 explain 标签绑定整体坏掉**。本单把 souffle 半边单独立项,作为**引擎分离 step 1**。

### 已确证事实(只读实验,均在 `v0.2.0-release-aligned` = factgraph/main 内核,同机)
1. **标签错跨 souffle/problog 一致**:同一 C-EVE,正确证明只能引用 Eo/E1/28000。实测:native **全对**;problog **全错**(M2a/M1o/27000/`<unbound>`);souffle **与 problog 字节级一致地错**。**单规则 + 复合都错**。
2. **共用坏路径**:problog 与 souffle 的 `lowering_plan` 规则都路由进**引擎中立 companion**(`build_companion_program` + `diagnostic_problog_result_to_evidence_graph`);native 走专属 `_probe_evidence_graph_for_lowering_plan`(`probe_native` meta-interpreter,串绑定 + 终态回灌 → 相干)。
3. **根因**:`diagnostic_projection.py::_anchor_for_row`(line 198)只锚公共头端口,内部变量留空;`diagnostic_emit.py::_emit_branch` 逐原子独立 emit → 各挑各的事实。
4. **性能**:`run_diagnostic_souffle` `export_package(query=None)` 整库 + 追加完整 idb 整跑;每次 explain 重跑整推理(同形状 problog:19→1.x s,49→32 s)。
5. **souffle 已捕获真实 witness**:`engine_eval.py` `include_pred_witness_columns: True` → souffle 实跑吐每条件真实事实 → `ProofReceipt.pred_witnesses`(`pred_condition_key` 编码 case/condition);但 `_souffle_support_artifact_to_evidence_graph` 渲染成扁平。
6. **souffle 二进制 arm64 原生**(`/opt/homebrew/bin/souffle`),无 Rosetta;另有 `run_provenance_explain` 未考(实现前查)。

### 架构判定(逐引擎分治)
native 之所以对 = 解释**捕获自其真实执行**;非 native 引擎"事后重构 + 猜代表事实"必错。→ 每引擎专属、从实跑捕获。souffle 路线选定 **S(reach-chain)**:plan 静态骨架 + souffle 真实 trace 回填,**完全不依赖 native**。否决 P(prober + 叠加):P 的失败侧是 native 重证,与 souffle 实跑信息相同但非自治;且 souffle 特有语义(递归/聚合/否定)下 native 可能发散。

### 关键讨论结论(供实现参照)
- **三态信息来源**:Holds = souffle 真实 asrt;Fails/NotReached 在 **固定 head** 下 souffle **也能给**(逐前缀/reach-chain),非 prober 专属——纠正了"Datalog 不 witness 失败"的过度表述。
- **失败值**:不靠"跑 N 次前缀再 diff",而是 reach-chain 一次 run,**最后非空 reach 的元组即失败点绑定值**。
- **多分支**:NotReached 是分支内概念,非跨分支;每分支独立判定;一次 run 可出多分支 × 多 subject。

### PoC(真实 souffle,arm64,2026-06-21)—— 决定性验证
手写目标 `reach.dl`(见 `2026-06-21_souffle-reach-chain-explain.poc/`),`/opt/homebrew/bin/souffle -F facts -D out reach.dl` 跑出:
```
# 比较失败取值 (new_account, C-EVE):
na_r2:  C-EVE | 2000 | a_eve_c | a_eve_t      # 最后非空 → 失败值 td=2000 + 成立侧 asrt
na_r3:  C-M1  | 20                            # C-EVE 不在(td<90 失败)

# pred 链失败定位+取值 (forwards_out, C-DANA 无大额转出):
fo_r3:  C-DANA | Do | 4000 | a_do             # 最后非空 → 失败值 amt=4000 + 真实事实 Do + asrt
fo_r4:  C-EVE | Eo | 28000 ; C-M1 | M1o | 28000   # C-DANA 不在(4000<20000 失败)
```
验证:**失败值可取(td=2000 / amt=4000)、比较 + pred 两种失败都行、成立侧 asrt 贯穿、绑定相干、一次 run 多分支×多 subject**。→ S 的核心风险点(souffle 引擎内给失败值)**已证可行**。

### Scope-freeze 准备度
范围已通过整轮对话收口(§5 四块 + 递归设计点)。**进 `scoped` 前剩一个前置调查**:Implementation Plan step 1(读 `run_provenance_explain`,定 codegen 是自建还是借 souffle provenance)。

### Cadence
draft → (前置调查 run_provenance_explain) → user 审阅 + "可以推进" → scoped → Codex 落地 → Claude gate(标签相干 + 失败值 + 性能上界 + 其他引擎零回归)→ user merge。

## 2026-06-21 — Codex consult + scope ratification → scoped (Claude)

### Codex 对接(relay;本机无 codex CLI)
本机未装 codex CLI;沿用既有 relay 协议(Claude 拟稿 → user 转递 Codex → 回传)。分工:Codex 落地代码、Claude 规划,**真讨论方案落地**(非 Claude 单方设计)。

### 设计岔口 RESOLVED
Codex 实查 `provenance.py::run_provenance_explain`(line 151,souffle `-t explain`):**只解释已成立 proof**,无"前缀成立但下一条件失败"模型,输出是 proof-node/rule-number tree(非 `(case,condition)` 坐标),**不能给失败值**。→ 决定**自建 reach-chain**,仅借其 subprocess/JSON 风格,不以 provenance 为主路径。

### 落地路线(吸收 Codex,无实质分歧)
- 新建专属 `src/factgraph/adapters/souffle/reach_explain.py`,**不扩写旧 `diagnostic_emit.py`**;
- codegen 入口 `_materialize_adapter_derivation_plan(plan, engine="souffle")`(materialized body_ir + trace,join/head-link 为 `eq`、坐标与 engine eval 一致);
- pred 用 `generate_view_dl(include_witness_views=True)` / `witness_rel_name` witness 列;compare/`not`/类型域抽 adapter 内部 helper(不直接复用私有 `_compile_atom`);
- 装配复用静态 plan/rules_by_id + `make_pred_condition_key`;`_souffle_row_graph_builder` 改主路由。

### Scope 收窄(user 拍板 5 条)
1. **事实邻域过滤不进 S1**(stretch / S2-S3);S1 允许全量 facts export。
2. **递归 / `ruleref` / aggregate 不进 S1**,直接降级;递归独立 **S2**。
3. **S1 atom 集 = materialized where IR** 的 `pred`/`eq`/`ne`/`gt`/`ge`/`lt`/`le`/简单 `not(pred|eq)`(措辞用 "materialized",避免与源 AST/lowered IR 混淆)。
4. **降级不变量硬写**:unsupported → ProofReceipt/minimal;**souffle lowering_plan 绝不再走旧 companion**(优先级高于"尽量 rich")。
5. **性能验收诚实化**(user 加约束):不写"显著下降且不随 ledger 线性"(全量 export 仍 O(ledger) load),改为"**不再重跑原 idb/rule graph;事实过滤 deferred**"。

### Hard parts(记入 §6 Boundaries)
多候选 tuple **按行 binding 选**(非任取第一条);`not(pred)` 成立只展示相关外层绑定、**不编造缺失事实**;数值/符号类型域对齐 `where_compile.py`;v1 per-row(批量后续);aggregate 失败值 v1 不承诺。

### 状态
draft → **scoped**(范围已冻结,落地骨架已与 Codex 对齐;蓝图 §1-10 已据此更新)。

### Cadence(更新)
scoped → **Codex 落地 S1**(`reach_explain.py` + 改路由 + 降级)→ Claude gate(标签相干 + 失败值 + 降级路由 + 零回归)→ user merge → **验证通过后**再开 problog 修复单 / 递归 S2。

## 2026-06-21 — Codex S1 impl + Claude gate (FAIL → fix → PASS) (Claude)

### Codex 落地 S1
新增 `src/factgraph/adapters/souffle/reach_explain.py`(reach-chain codegen + 独立单跑 + 解析 + 装配复用 `diagnostic_problog_result_to_evidence_graph`);`store.py::_souffle_row_graph_builder` 改路由到 `souffle_reach_explain_to_evidence_graph`,异常/unsupported → ProofReceipt/minimal;`_souffle_diagnostic_projection_graph` 对 souffle 退役(零调用者);新增回归 + souffle/explain docs。

### Claude gate round 1 — FAIL(独立复现)
`/tmp/gate_repro.py`(无 `!=` 复合 `(forwards_out & cross_border) | (new_account & forwards_out)`,C-EVE 一支成立一支失败):**成立分支 c0 的 forwards_out 标签不相干** —— `Txn M2a exists` / `Txn E1 is by C-EVE` / `Txn Eo direction`(同一 `t` 指三笔);**native 为全 Eo**。根因:reach 用**每原子中间 reach 行**取 witness(早期 `exists`/customer-link 未充分约束),未回灌终态。Codex 原测试只查跨客户泄漏(Mallory),漏同客户交易相干。

### Codex 修复
`_parse_reach_outputs` 改两阶段:branch holds → 所有原子 witness 从**终态 reach 行**(全绑定 t=Eo)回灌(镜像 native `prober.py::_rebake_atom_results_from_terminal`);branch fails → 前缀行 + 失败行。新增 `test_souffle_reach_chain_explain_rebakes_holding_branch_witnesses_from_terminal_row`。

### Claude gate round 2 — PASS(独立重验,非信 Codex 数)
- 成立分支 c0/c1 forwards_out **全 Eo**(自跑 SHOW=1 eyeball);失败值 `✗ 2000 < 90` 在;
- 性能 scale10 narrate 0.20s,idb 覆盖、不重跑原推理(代码核实 `_run_reach_program`);
- 降级不变量:`_souffle_diagnostic_projection_graph` 零调用者;`!=` SAR → 降级;
- 零回归:native 仍全 Eo(独立确认)、problog 不变;`unittest` `test_rule_expr_evaluate` 50(含新相干测试)+ broader 5 套件 49,全绿。

### 诚实 caveat
- full SAR(含 shared_device `!=`)souffle **EVAL** 失败(分离的 `!=` ungrounded-variable codegen bug,**eval 层、非本单**)→ demo §5 souffle 路径仍卡在求值,需另立 **eval `!=` 单**;
- 因 eval 受阻,`!=`/shared_device 的 **narrate** 无法独立复现,依赖 Codex 单测 + 终态回灌的通用性;
- 递归/`ruleref`/aggregate 按 S1 降级(未行使,属 S2);
- `pytest` 收集前 segfault = 环境 `readline` 问题(同上一单),非本改动;`unittest` 为既定 workaround。

### 判定
**PASS** → 交 user merge。后续待办:eval `!=` 单(解锁 souffle demo 路径)→ 递归 S2 → problog 修复单。
