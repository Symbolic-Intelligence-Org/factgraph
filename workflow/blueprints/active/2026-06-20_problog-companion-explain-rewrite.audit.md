# Audit Log: ProbLog composite explanation — companion path rewrite

Paired with [2026-06-20_problog-companion-explain-rewrite.md](./2026-06-20_problog-companion-explain-rewrite.md).

## 2026-06-20 — Open (draft), carrying findings from the reverted `!=` 单 (Claude)

### 由来
`!=` 单(`2026-06-20_problog-diagnostic-ne-atom`)被回退——它只是表象。真问题是 companion 重算路径本身。本单承接全部前置调查。

### 已确证事实(只读实验,均在 `v0.2.0-release-aligned` = factgraph/main 内核,同机)
1. **性能 O(ledger) → 30s 超时 → 退化**:同一 SAR,ledger 19 笔→1.4s RICH;**49 笔→32.1s 撞 `run_diagnostic_problog` 的 30s 超时 → 退化成 `'='`**。`emit_diagnostic_problog` 把整个 ledger 重编译进新 ProbLog 程序重跑。
2. **回退即恢复**:去掉 `!=` 放开后,49 笔→1.2s(`build_companion_program` 在 `!=` 处快速失败,不触发重算)。
3. **标签绑定错**:多实体/多事实复合下 companion 挑错代表事实(`Txn M2a to US` 本应 `M1o to IR`;`<unbound> < 90` 本应 `20 < 90`;`!<unbound> equals <unbound>`)。
4. **proof_trace 忠实但无逐节点概率**:`_attach_problog_provenance` 解析真实 evaluate 的 `raw_output`(SLD trace,逻辑结构);逐节点概率靠 companion 的 `expl_branch/expl_occ/expl_head` 各发 WMC query 才有。
5. **WMC 本身忠实**:共享概率事实 `P(A∨B)=0.5`(容斥正确),非 naive noisy-OR 的 0.75。

### 结论 / 方向
- 核心张力:**结构可从忠实 trace 拿;逐节点概率需逐节点 WMC,当前用"整库重跑"获取 → 性能 + 标签双输**。
- 优先级:**D 守卫(止血:超时→明确降级 + 正确总概率;ledger-embedding 收敛到相关事实)** → **B/C 根因(非重算/有界获取逐节点概率 + 忠实标签)**。
- 忠实性是硬约束(user 判据):展示的数必须可追溯到 evaluate,不得重构出与 WMC 不一致的值。

### Gate 教训(自上一单)
只测玩具数据、回归只查结构不查标签/性能、未核对真实运行环境/数据 → 假阳性 PASS。本单 Acceptance 已把**标签正确 + 性能上界**列为强制回归。

### Cadence
draft → 设计评估选路线(A/B/C/D)→ scoped → Codex 落地(D 先,B/C 后)→ Claude gate(含标签+性能回归)→ user merge。
