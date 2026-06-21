# Task Blueprint: ProbLog composite explanation — companion path rewrite (perf + faithful labels)

- Status: superseded
- Created: 2026-06-20
- Last Updated: 2026-06-21
- **Superseded by**: [2026-06-21_problog-reach-chain-explain.md](./2026-06-21_problog-reach-chain-explain.md)（M2 = 把本 draft 的 B/C「逐节点 WMC + 忠实结构」具体化为 problog 自己的 reach-chain，并更进一步退役 companion；经真 problog PoC 实证后 scoped）
- Related Modules:
  - `src/factgraph/sdk/store.py` (`_problog_row_graph_builder`, `_problog_diagnostic_projection_graph`)
  - `src/factgraph/application/explain/diagnostic_projection.py` (`build_companion_program`, atom handling)
  - `src/factgraph/adapters/problog/diagnostic_emit.py` (`emit_diagnostic_problog`, `run_diagnostic_problog`, 30s timeout)
  - `src/factgraph/adapters/problog/provenance.py` (`problog_trace_to_evidence_graph` — the faithful proof_trace path)
  - `src/factgraph/adapters/problog/engine_eval.py` (`_attach_problog_provenance` — evaluate-captured trace)
- Related Docs:
  - [workflow/foundations/architecture_principles.md](../../foundations/architecture_principles.md)
- Audit Log:
  - [2026-06-20_problog-companion-explain-rewrite.audit.md](./2026-06-20_problog-companion-explain-rewrite.audit.md)
- Supersedes / folds in:
  - [2026-06-20_problog-diagnostic-ne-atom.md](./2026-06-20_problog-diagnostic-ne-atom.md) (`!=` 仅为本问题暴露的表象;已回退)

## 1. Problem

ProbLog 下**复合规则**的 `Explanation.narrate()` 走 companion/diagnostic 投影
(`_problog_diagnostic_projection_graph` → `build_companion_program` → `run_diagnostic_problog`),
该路径有**三个叠加缺陷**:

1. **性能 O(ledger) → 超时退化**:`emit_diagnostic_problog` 把**整个 ledger 的事实**重新编译进一个新 ProbLog 程序再跑一遍。实测 19 笔交易→1.4s,**49 笔→32.1s 撞 30s 超时**([diagnostic_emit.py](../../../src/factgraph/adapters/problog/diagnostic_emit.py) `run_diagnostic_problog` 默认 `timeout=30`),超时即退化成单条 `'='` 头原子。真实数据必然踩中。
2. **标签绑定错**:对多实体/多同谓词事实的复合,companion 投影**挑错代表事实**——如 cross_border 的原子显示 `Txn M2a to US`(本应 `M1o to IR`)、`<unbound> < 90`(本应 `20 < 90`)、`!<unbound> equals <unbound>`。结构对、概率对,但**逐原子标签误导**,对可审计产品不可接受。
3. **`!=`(`not(eq)`)不被支持**:`_not_inner_atoms` 仅认 `pred` 内层(已回退的前置单已隔离;但单放开会触发缺陷 1 的超时,故必须连同 1/2 一起解决)。

对照:**native** 复合 narrate 标签正确、快;**单规则** ProbLog narrate 走 proof_trace(evaluate 捕获)也正确。问题集中在 **ProbLog × 复合 × companion 重算**。

## 2. Goals

- ProbLog 复合 `narrate()`:**忠实**(与 evaluate 的 WMC 一致,无重算漂移)、**逐原子标签正确**、**性能不随 ledger 爆炸**。
- 失败时**优雅降级**(明确"逐条件证明不可用 + 仍给正确总概率"),**绝不**输出误导性的 `'='`/错标签当证明。

## 3. Non-goals

- 不改 native 路径(已正确)。
- 不改 WMC/概率数值(`.certainty` 已忠实)。
- 不追求"任意规模实时";可接受"超时 → 明确降级"。

## 4. Current Context / Findings(来自前置调查,见 ne-atom audit)

- **proof_trace 路径是忠实的**(`_attach_problog_provenance` 解析**那次真实 evaluate** 的 `raw_output`;`problog_trace_to_evidence_graph` 已支持多路 tree)。**但**它是 ProbLog 的 SLD 执行 trace(逻辑结构),**不含逐节点 WMC 概率**。
- **companion 重算**之所以存在,是为拿**逐节点概率**(它对 `expl_branch/expl_occ/expl_head` 各发一次 WMC query)。代价:整个 ledger 重编译 + 重跑 → O(ledger) + 标签靠重构(易错)。
- 即:**结构可从忠实 trace 拿到;逐节点概率需要逐节点 WMC,而当前实现用"重跑整个 ledger"去拿,这是性能与标签问题的共同根源。**

## 5. Candidate Approaches(设计空间,未定 —— draft 阶段需评估)

- **A. companion 程序只嵌入"相关事实"**,不嵌整个 ledger → 直接攻击 O(ledger)。最小改动,但标签问题仍在。
- **B. 逐节点概率不靠整库重跑**:只对所需子目标发 WMC query(或复用 evaluate 已编译的 SDD/d-DNNF,若可获取),结构用忠实 trace。最贴 user 的"evaluate+采集、不重算"判据。
- **C. 结构走忠实 proof_trace,概率分两类**:整体总概率取 evaluate `.certainty`(忠实);逐节点仅在**可证明无共享重叠**时标注,否则不编造(诚实降级)。
- **D. 兜底守卫(可先行的小步)**:超时/失败时,**给明确降级文案 + 正确总概率**,不再吐 `'='`/错标签。把 ledger-embedding 改成相关事实(A 的子集)以避免无谓超时。

倾向:**先 D(止血式守卫,低风险)→ 再 B/C(根因,需设计)**。A 可作为 B 的性能前置。

## 6. Boundaries And Invariants

- **忠实性第一**:任何展示的概率/标签必须可追溯到 evaluate 真实计算,**不得重构出与 WMC 不一致的数**(user 核心判据)。
- 共享概率事实的容斥必须正确(回归:`P(A∨B)=0.5` 非 0.75)。
- native / 单规则路径不回归。

## 7. Acceptance(草案 —— scoped 时细化)

- [ ] 含 `!=` 的复合 ProbLog `narrate()`:逐条件富证明,**标签正确**(对应行实际绑定的 txn/值,无 `<unbound>`),顶层 probability == `.certainty`。
- [ ] **性能**:explain 时间不随 ledger 线性爆炸;给定规模上限内不撞 30s 超时(或超时→明确降级而非 `'='`)。
- [ ] 共享概率事实容斥正确;native/单规则无回归。
- [ ] **回归断言增强**:不仅查"无 `'='`",还查**标签正确**(原子文本含该行实际绑定值)+ **性能上界**(大 ledger 用例计时)。

## 8. Implementation Plan(draft —— 待 scoped)

1. 设计评估 A/B/C/D,选定路线(需读 `expl_*` query 机制 + proof_trace 能给到的结构粒度 + 能否复用 evaluate 的编译产物)。
2. 先落 **D 守卫**(超时/失败→明确降级 + 正确总概率;ledger-embedding 收敛到相关事实)。
3. 落根因(B/C):逐节点概率的非重算/有界获取 + 标签从忠实 trace/plan 绑定。
4. 增强回归(标签正确 + 性能上界)。

## 9. Docs To Update

- explain 模块 docs:明确 ProbLog 复合证明的能力/限制与降级行为。

## 10. Outcome / Deviations

待实现后补齐。
