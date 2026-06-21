# Audit Log: Souffle eval witness — per-branch capture + arity diagnostic

Paired with [2026-06-21_souffle-eval-witness-arity.md](./2026-06-21_souffle-eval-witness-arity.md).

## 2026-06-21 — Open (draft): root + 三分法定性 + 实证 (Claude)

### 由来
ne 根治单 gate 时发现:`!=` 修好后,全 SAR souffle eval 从 exit-1 变 **SIGABRT(-6)**。挖出真因 = souffle **arity 上限**。user 用三分法(A 引擎硬限制 / B eval 能跑 explain 不能 / C 心智<23 构造≥23)要求定性。

### 实证(均真实 souffle 2.5,同机)
1. **arity 上限 = 22**(逐 arity 探测:22 OK、23 FAIL `Requested arity not yet supported`)。
2. **全 SAR 单体 witness 查询 = 24 列**(`C0 + W0…W22`;一分支一规则、同头、witness 并集)。
3. **精简 eval(去 witness)全 SAR 跑通,4 行** → 非 Case A(eval 内在窄)。
4. **逐分支 witness = 10 / 13**(均 < 22)→ 24 是分支并集(Case C),非用户规则复杂度。
5. **链长 ≠ 用户条件数**:实体首次引用补隐式 `:exists`(带 witness);字段约束→字段 pred(带 witness);比较/join→无 witness。一个用户条件 → 0/1/2 个带 witness pred。
6. **ProofReceipt 承重**(消费者已核实:`support_digest→ProofReceipt` sidecar、`ruleref_substrate` 子证明)→ 不能 lean-always 丢。

### 定性结论
**Case B + Case C(严肃,必修),非 Case A。** 修法 = 解耦:精简结果 + **逐分支 witness**(保 ProofReceipt + arity 回逐分支量级 + 对齐心智)。

### user 拍板(Case A 处置)
- Case A(残留:单分支自身 > 22)→ **简单明确诊断作为临时补丁**(Phase 1),不再 SIGABRT。
- 其余改进(逐分支 witness 主修 + exists 折叠可选)按 Claude 设想(Phase 2/3)。
- 同意和 Codex 对接。

### Scope(三段)
Phase 1 arity 诊断(临时补丁,先行)→ Phase 2 逐分支 witness(主修,解锁 demo + 保 ProofReceipt)→ Phase 3 `:exists` 折叠(可选,压低 arity;需确认 asrt 取舍)。

### 依赖 / 正交
- 依赖 ne 根治(`!=`→`ne`)。
- 正交:S1 reach_explain(eval 通后在全 SAR 上实测其逐分支 reach arity < 22)。

### Cadence
draft → Codex 落地(Phase 1+2,Phase 3 可选)→ Claude gate(全 SAR eval 通 + ProofReceipt 等价 + ruleref 不回归 + 诊断清晰 + S1 全 SAR 实测 + 零回归)→ user merge → demo §5 souffle 端到端验。
