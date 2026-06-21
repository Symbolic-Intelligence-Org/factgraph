# Audit Log: ProbLog reach-chain explain (engine-own, retire companion)

Paired with [2026-06-21_problog-reach-chain-explain.md](./2026-06-21_problog-reach-chain-explain.md).

## 2026-06-21 — Open (scoped): 方法选型 + 真 problog PoC 实证 (Claude)

### 由来
souffle 整组(ne + reach-chain + eval-arity + 宽分支)落地后,problog 是最后一个仍走共享坏 companion 的引擎。user:「先总览可行方法,不一定和 souffle 一致」。

### 方法选型(讨论 + user 拍板)
- 总览 4 法:**M1**(prober + 概率叠加,半独立、借 native prober)/ **M2**(problog 自己的 reach-chain,全独立、对称 souffle,逐节点 WMC,dsharp 代价)/ M3(SLD trace 重建)/ M4(修 companion,已弃)。
- 关键差异澄清:labels 引擎无关(同 souffle);**概率(WMC)+ dsharp 性能**是 problog 特有真问题。
- user 问「是否已配备每引擎独立方法」→ 点出 M1 复用 prober **没做到完全独立**;souffle 选了完全独立(自己的 reach_explain)。
- **user 拍板 M2**(完全独立、对称),并定:**正确性优先、逐节点 WMC 全用、先测试确定再交 Codex**。

### 真 problog PoC 实证(同机 `/Users/zhenzhili/miniforge3/bin/problog`)
1. **逐节点 WMC + 绑定相干**:6 事实 reach-chain,`reach1-4=1.0`、`reach5/6=0.8`(IR-risk 进入),绑定 `eo` 串到底。0.2s。
2. **规模**:噪声账本 N=1k/5k/20k → 0.46/1.83/6.77s、107/327MB。**线性有界,不重现 16GB**。reorder 把宽中间关系输出压窄(20001→1)但不压时间 → 瓶颈是 grounder 读全库;**逐行锚定单 subject 使内存有界**。→ scoping 是超大库优化,可延后。
3. **失败值**:`reach2(eve,2000)` + `reach3=0`(确定性失败停),上一个非零 reach 携带值。
4. **完整 SAR 组合**(两分支 + 设备环 `\=` + 概率):C-EVE c0=0.8 / c1 失败值 2000 / sar=0.8;mule c0=0.8 / c1 设备环 0.81(绑 C2=m2、`id1≠id2` 排除自身)/ **sar=0.962=problog 真实 WMC(= `.certainty`)**。多分支共享变量正确。
5. **鲁棒性**(user 追问缺失/错误事实):事实错误 → reach 绑错误值 `(eve,eo,5000)` 停在 `5000>=20000`,**摊出真凶值**;缺失字段 → 优雅空。

### 守卫精度(user 连续追问「是否每 atom 一个守卫」)
- 早期 PoC 用**独立谓词** → 零事实谓词触发 `UnknownClause`(假象)。
- 读真实 `export_problog`:所有事实走统一 **`edb_fact/4`**(pred_id 是参数)。实证四态:
  - A edb_fact 包装 + 缺失字段 → 优雅空;B edb_fact 零子句 → `UnknownClause`(唯一触发);C 零子句 + 守卫 → 优雅空;D 守卫 + 有事实 → 概率不变(0.8/0.4,无害)。
  - 混合链(fact + 比较 + ne + 中途缺失) + **单条守卫** → 全程零报错。
- **判据**:需守卫 = 「被规则体引用、但可能零子句(无事实且无规则)」的谓词。M2 里**只有 `edb_fact/4` 一个** → **一条** `edb_fact(_,_,_,_) :- fail.`,无条件发;比较/ne(builtin)、`reach_i`(总有规则)不需守卫。
- 对照 souffle:Datalog 强制 `.decl`、声明的空关系即空(仅 warning),**未声明才报错**;codegen 必声明引用关系 → souffle 天生安全。**守卫是 problog 专属**——又一处引擎差异。

### Scope(scope-freeze)
新 `adapters/problog/reach_explain.py`(镜像 souffle):codegen(edb_fact 复用 + 一条守卫 + 逐分支 reach + 逐节点 query)→ run(一次)→ parse(逐节点 WMC + 绑定过滤 + 终态回灌 + 缺失/比较失败区分)→ assemble(复用装配器 + 逐节点概率 + 总概率取 `.certainty`)→ 路由改向 + 退役 companion。**scoping/聚合/递归延后。**

### Cadence
scoped → Codex 落地(`codex落地代码,你主要计划`,但切实讨论)→ Claude gate(相干 + 失败值 + mule 设备环 + 守卫 + 性能上界 + 容斥 + 零回归 + companion 0 caller)→ user merge → demo problog narrate 端到端验。

### 待 Codex 落地前确认(Plan step 1)
`export_problog` 的 where→edb_fact 体编译能否按原子拆解、逐步串入 reach(fact-lookup / 比较 / ne 三类),以及 plan 能否拿到逐分支原子序 + subject 锚。**拿不到干净就停下回报,不硬凑。**
