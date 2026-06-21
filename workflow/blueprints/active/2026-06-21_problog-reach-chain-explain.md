# Task Blueprint: ProbLog reach-chain explain — engine-own method (per-node WMC + faithful labels, retire companion)

- Status: implemented
- Created: 2026-06-21
- Last Updated: 2026-06-21
- Branch: `v0.2.0-problog-reach-chain-explain`
- Depends on: committed ne(`cad6cf6e`,`!=`→`ne`,否则 `!=` 复合在 problog 侧退化) + souffle reach-chain 整组(`359b2ed8`/`fb3044c5`,作为对称参照与装配复用先例)
- Related Modules:
  - **新建** `src/factgraph/adapters/problog/reach_explain.py`(镜像 `adapters/souffle/reach_explain.py`)
  - `src/factgraph/sdk/store.py`(`_problog_row_graph_builder` line 3019 路由改向;退役 `_problog_diagnostic_projection_graph` line 3079）
  - `src/factgraph/adapters/problog/problog_export.py`(`export_problog` line 44 / `edb_fact` 发射 line 101-108 / `_format_probability` / `_claim_probability` / where→edb_fact 体编译 — **复用**)
  - `src/factgraph/application/explain/diagnostic_assemble.py`(`diagnostic_problog_result_to_evidence_graph` — souffle 已复用的装配器,problog 同样复用)
  - `src/factgraph/adapters/problog/diagnostic_emit.py`(旧 companion `emit/run_diagnostic_problog` — problog 退役后无 caller,核实后留置/标注)
- Related Docs:
  - [workflow/foundations/architecture_principles.md](../../foundations/architecture_principles.md)
- Audit Log:
  - [2026-06-21_problog-reach-chain-explain.audit.md](./2026-06-21_problog-reach-chain-explain.audit.md)
- Supersedes / folds in:
  - [2026-06-20_problog-companion-explain-rewrite.md](./2026-06-20_problog-companion-explain-rewrite.md)(draft;探索 A/B/C/D。**M2 = 把其 B/C「逐节点 WMC + 忠实结构」具体化为 reach-chain,并更进一步退役 companion**)
  - [2026-06-20_problog-diagnostic-ne-atom.md](./2026-06-20_problog-diagnostic-ne-atom.md)(`!=` 表象,已由 ne lowering 根治)
- Related historical blueprints:
  - [2026-06-21_souffle-reach-chain-explain.md](./2026-06-21_souffle-reach-chain-explain.md)(对称:souffle 自己的 reach-chain;M2 是 problog 的对称实现 + 逐节点概率)

## 1. Problem

problog 是**最后一个仍走共享(坏)companion** 的引擎(native=prober、souffle=reach_explain、pyreason=event_log 都已各自独立)。`_problog_row_graph_builder` → `_problog_diagnostic_projection_graph` → `build_companion_program` 有三叠加缺陷:

1. **标签错**:companion `_anchor_for_row` 只锚公共端口、内部变量乱挑事实。实测(C-EVE,gate 复合):`Txn M2a exists`/`Txn M2a to US`(应 Eo→IR)、`<unbound> < 90`(应 `2000<90`)。结构对、概率对,但**逐原子标签误导**。
2. **性能 O(ledger) → 超时退化**:companion 把整库重编译再跑一遍拿逐节点 WMC;实测 49 笔→32s 撞 30s 超时 → 退化成单条 `'='`。
3. ne 历史症状(已由 `cad6cf6e` 根治,标签问题独立残留)。

根因同 souffle pre-S1。**M2:给 problog 它自己的 reach-chain explain,退役 companion**,完成 per-engine 分治最后一块。

## 2. Goals

- problog 复合/单规则 `narrate()`:**逐原子标签相干**(该行真实绑定的 txn/值,无 `<unbound>`/张冠李戴)、**逐节点 WMC 概率**(problog 实跑,忠实)、**性能不随 ledger 爆炸**(有界,绝不重现 16GB/超时退化)。
- 完全独立、与 souffle 对称(engine-own,不复用 native prober)。
- 失败/缺失/错误事实仍给推理链(reach 停在出错点,摊出真实值)。

## 3. Non-goals

- 不碰 native / souffle / pyreason explain。
- **scoping(只嵌 subject 邻域事实)本单延后**——首版用现有全库 `export_problog`,实测 O(ledger) 有界(327MB@20k vs companion 16GB),demo 快、大库慢但不崩。超大库 scoping 作后续优化单(对称 souffle 延后 scoping)。
- 聚合(count/sum)/递归 explain 不在本单(对称 souffle S2 延后;聚合若引入额外 helper 谓词,其守卫另议)。
- 不改 WMC 数值(`.certainty` 已忠实)。

## 4. Current Context(全部经真实 problog PoC 实证,2026-06-21)

- **逐节点 WMC**:`query(reach_i)` 给逐前缀概率。PoC:`reach1-4=1.0`(确定性),`reach5/6=0.8`(IR-risk 概率事实进入处)。一次 problog run 同时算所有 reach query(一次编译)。
- **绑定相干**:reach 绑真实事实并串到底(`reach2(eve,eo)`…)。绑定从 grounded query 答案取,过滤到 subject。
- **失败值**:确定性失败 → reach 停(prob 0、变量 ungrounded);上一个非零 reach 携带值(`reach2(eve,2000)` + `reach3=0`)。
- **完整 SAR 组合**(两分支 + 设备环 `\=` + 概率):C-EVE c0=0.8/c1 失败值 2000;mule c0=0.8/c1 设备环 0.81(绑 C2=m2、排除自身)、总 `sar=0.962`=problog 真实 WMC(= `.certainty`,非手算)。多分支共享变量正确。
- **规模**:线性 O(ledger)、内存有界(N=1k/5k/20k → 0.46/1.83/6.77s,107/327MB)。**不重现 companion 的 16GB/超时**。瓶颈是 grounder 读全库(scoping 可后续压);逐行锚定单 subject 使内存有界。
- **鲁棒性**:事实错误 → reach 绑错误值停在校验(`reach(eve,eo,5000)` + `5000>=20000` 空,**摊出真凶值**);缺失字段 → reach 优雅空。
- **守卫(problog 专属)**:现有 export 所有事实走统一 `edb_fact/4`(pred_id 是参数)→ **缺失字段天生优雅**(无匹配行=空)。**仅 `edb_fact/4` 整个零子句**(全库零事实退化)触发 `UnknownClause`。修法 = 顶部**无条件发一条** `edb_fact(_,_,_,_) :- fail.`(实测:有事实时概率不变、无害;零事实时优雅空)。比较 `<`/`>=`、ne `\=`、`reach_i` 均为 builtin/已定义 → **不需守卫**。souffle(Datalog 强制 `.decl`、空关系即空)无此问题——problog 专属。

## 5. Proposed Shape(镜像 souffle reach_explain + 逐节点概率)

新 `adapters/problog/reach_explain.py`,入口 `problog_reach_explain_to_evidence_graph(...)`,与 souffle 对称的几段:

### 5.1 codegen `_build_reach_program`(problog 语法)
- **事实**:复用 `export_problog` 的 `edb_fact/4` 发射(`_format_probability(_claim_probability(...))::edb_fact(asrt,pred,e_ref,value)`)。首版全库(scoping 延后)。
- **守卫**:顶部一条 `edb_fact(_,_,_,_) :- fail.`(无条件)。
- **逐分支 reach 链** `_emit_branch_reaches`:锚定 subject(`reach_c{b}_0(C) :- C = <subject>, edb_fact(_,"<subj pred>",C,_)`);逐原子串联 `reach_i :- reach_{i-1}, <atom_i>`,`<atom_i>` 复用现有 where→edb_fact 体编译(fact-lookup→`edb_fact(_,"pred",e_ref,val)`;比较/ne→builtin)。**绑定线程**:reach_i 携带到该步为止的项变量(供终态相干 + 失败值)。
- **逐节点 query**:对每个 `reach_i` 发 `query(reach_i(...))`(subject 锚定、其余自由)。

### 5.2 run
- 一次 problog 调用(所有 reach query 同时算 → 一次编译)。

### 5.3 parse `_parse_reach_outputs`
- **逐节点 WMC**:每个 `reach_i` 的概率 = 该前缀 WMC。
- **绑定/相干**:取 grounded reach 答案,`_matching_rows` 过滤到 subject(及该行 witness);终态回灌每原子项变量(对称 souffle,标签来自项变量)。
- **失败点 / 缺失 vs 比较失败**:首个 prob=0/空的 reach = 失败原子;**区分**——若该原子是 fact-lookup(edb_fact)空 → 「缺失事实/未达」;若是比较/ne 空且前缀已绑值 → 「`<值> op <阈值>` 失败」。复用 souffle 的 not_reached/fails 渲染(`diagnostic_assemble`)。
- **失败值**:上一个非零 reach 的绑定。

### 5.4 assemble
- 复用 `diagnostic_problog_result_to_evidence_graph`(souffle 已复用)喂入 reach 解析结果,**逐节点挂 WMC 概率**。
- **总概率 = 行 `.certainty`**(真实 WMC,正确处理跨分支共享变量);逐分支 = 各分支终态 reach;noisy-OR 仅作展示(分支独立时精确)。
- runner-exit 安全检查(对称 souffle:防空输出被当 rich)。

### 5.5 route + retire
- `_problog_row_graph_builder` → `problog_reach_explain_to_evidence_graph`;异常 → 明确降级(正确总概率 + 「逐条件证明不可用」),**绝不**回旧 companion 的 `'='`/错标签。
- 退役 `_problog_diagnostic_projection_graph`(核实 0 caller 后)。

## 6. Boundaries And Invariants

- **忠实性第一**:展示的概率/标签必须可追溯到真实 problog 计算;总概率 == `.certainty`;共享概率事实容斥正确(回归:`P(A∨B)` 非朴素 0.75)。
- native/souffle/pyreason/单规则 不回归。
- 守卫 `edb_fact(_,_,_,_) :- fail.` 不改变任何有事实场景的概率(实测无害)。
- 降级是**明确文案 + 正确总概率**,不是误导性证明。

## 7. Acceptance

- [ ] problog 复合 `narrate()`(gate + full SAR):**逐原子标签相干**(Eo→IR 非 M2a/US;无 `<unbound>`),**逐节点 WMC 概率**呈现,顶层 probability == `.certainty`。
- [ ] **C-EVE**:c0 成立(IR-risk)、c1 在 new_account **失败值正确**(`2000<90`,非 `<unbound>`)。
- [ ] **mule**:c1 设备环 rich(两客户同设备 + `id1≠id2` 绑定真正的另一客户)、概率正确。
- [ ] **性能**:explain 不随 ledger 线性爆炸到崩;给定规模内不撞超时/不 16GB(大库→慢但有界,或后续 scoping);**新增计时回归**。
- [ ] **鲁棒性**:事实错误→链摊出真凶值;缺失字段→优雅停并定位;`edb_fact/4` 零子句(零事实程序)→守卫兜底不 `UnknownClause`。
- [ ] 共享概率事实容斥正确;native/souffle/单规则**零回归**。
- [ ] 退役 companion:`_problog_diagnostic_projection_graph` 0 caller;失败路径明确降级(无 `'='`/错标签)。
- [ ] `PYTHONPATH=src` 相关 problog/explain 测试绿 + 新增 reach 相干/失败值/守卫/性能回归。

## 8. Implementation Plan

1. [reach_explain] 实现前确认:`export_problog` 的 where→edb_fact 体编译能否按原子拆出、逐步串入 reach(fact-lookup / 比较 / ne 三类);plan 能否拿到逐分支原子序 + subject 锚。**拿不到干净就停下回报。**
2. [reach_explain] codegen(`edb_fact` 复用 + 守卫 + 逐分支 reach + 逐节点 query)。
3. [reach_explain] parse(逐节点 WMC + 绑定过滤 + 终态回灌 + 失败点缺失/比较区分)。
4. [reach_explain] assemble(复用装配器 + 逐节点概率 + 总概率取 `.certainty` + 安全检查)。
5. [store] 路由改向 + 退役 companion(核实 caller)。
6. [tests] 相干 + 失败值 + mule 设备环 + 守卫 + 性能上界 + 容斥 + 零回归。
7. [docs] problog adapter docs:reach-chain explain、逐节点 WMC、守卫、性能/scoping 限制、降级。

## 9. Docs To Update

- `src/factgraph/adapters/problog/docs/`(reach-chain explain、逐节点 WMC、`edb_fact` 守卫、性能/scoping 限制、降级行为)
- explain 模块 docs(若有跨引擎 explain 能力/限制表)

## 10. Outcome / Deviations

- 最终落地结果:新 `adapters/problog/reach_explain.py`(逐分支 reach-chain + 逐节点 `query` + 复用 `export_problog` 的 `edb_fact` 发射 + 一条 `edb_fact(_,_,_,_):-fail` 守卫 + 终态回灌相干 + 失败值);`_problog_row_graph_builder` 改向、退役 companion(`_problog_diagnostic_projection_graph` 删除、SDK 不再 import `diagnostic_emit`)。**per-engine 分治完成**(native/souffle/problog/pyreason 各自独立)。gate PASS、demo 验过。
- 与 blueprint 不同的地方:装配复用共享 `diagnostic_problog_result_to_evidence_graph`(喂合成 `CompanionProgram` anchor + reach 解析出的 atom/witness/branch/occurrence 概率),非全新装配器(同 souffle 先例)。
- 为什么会有这些调整:复用已验证装配器更稳、改动面更小。
- 归档说明:已实现 + gate PASS;待 user merge;保留 active/ 与 souffle 组一并归档。**另:gate 发现 native prober 在全 SAR 上预存不相干(见 audit),独立于本单。**
