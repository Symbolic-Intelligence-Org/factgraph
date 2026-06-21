# Task Blueprint: Souffle reach-chain wide-branch arity — drop dead `__witness_N` columns (+ branch-local seed)

- Status: implemented
- Created: 2026-06-21
- Last Updated: 2026-06-21
- Branch: `v0.2.0-souffle-reach-chain-explain`
- Depends on: committed S1(`reach_explain.py`)+ eval-arity(`359b2ed8`)+ ne(`cad6cf6e`)
- Related Modules:
  - `src/factgraph/adapters/souffle/reach_explain.py`(`_seed_values_for_row`、`_build_reach_program`、`_emit_branch_reaches`、`_parse_reach_outputs`、`_matching_rows`、终态回灌 `_witness_terms`)
  - `src/factgraph/application/protocol/rule_expr_lowering.py`(`probe_seed_vars_by_head_port`)
- Related Docs:
  - [workflow/foundations/architecture_principles.md](../../foundations/architecture_principles.md)
- Audit Log:
  - [2026-06-21_souffle-reach-branch-local-seed.audit.md](./2026-06-21_souffle-reach-branch-local-seed.audit.md)
- Related historical blueprints:
  - [2026-06-21_souffle-reach-chain-explain.md](./2026-06-21_souffle-reach-chain-explain.md)(S1;本单是其宽分支残留的后续)
  - [2026-06-21_souffle-eval-witness-arity.md](./2026-06-21_souffle-eval-witness-arity.md)(同 arity 根因的 eval 侧,已修)

## 1. Problem

reach_explain 建**一张共享 seed 关系** `fg_reach_seed`,列出**所有分支**的头端口变量(`probe_seed_vars_by_head_port`)。每条分支的 reach 链都从这张共享 seed 出发 → **每条分支的表都背着其他分支的、它从不引用的变量**。终态 reach 关系 = (全量 seed) + (本分支自己的变量 + witness)。对**宽分支**(SAR 的 ring:new_account & forwards_out & shared_device),这超过 souffle 的 **22 arity** → reach-chain 的 souffle run 崩(`Requested arity not yet supported`)→ reach_explain fallback → **全 SAR narrate 退化成 flat-raw ProofReceipt(正确但难看),不是 rich**。

已实证:reach 关系逐层增宽到 >22(`fg_reach_c0_*` 截断显示 ~20+);手动跑 reach 程序复现同一 arity 崩溃。

**Gate 实测补充(2026-06-21)**:branch-local seed 单独**不足**——mule(C-M1,ring 分支 HOLDS、需走完整 over-wide reach)narrate **仍 fallback** 成 flat ProofReceipt;ring terminal 仍 ~24。Codex 只测了 `res.first()`=C-EVE(ring 早失败 → rich),漏了 mule(ring HOLDS)。**真正的 lever**:reach 每个 pred 挂了一个**装配从不读**的 `__witness_N`(asrt)死列(ring 13 个 → 撑爆 arity),见 §5.1。

## 2. Goals

- 全 SAR(及一般宽分支)的 reach-chain narrate **rich** 起来:每条分支的 reach 关系只带自己的变量 → 回到 22 以内。
- **完整保留**终态回灌/相干性/失败值所依赖的一切。

## 3. Non-goals

- **不做**对"本分支自己的列"的逐层收窄——终态回灌 `_witness_terms` 从 terminal_row 读**每个原子的项变量**,丢任何一个都会重新打破相干性(已验证 UNSAFE)。
- 不碰 eval(已修)/ native / problog。

## 4. Current Context

- `_build_reach_program` → 一张 `fg_reach_seed`,`_seed_values_for_row` = 全量 seed。
- `_emit_branch_reaches`:每分支 `bound_vars = list(seed_vars)`(全量起步)。
- `_parse_reach_outputs`:`_matching_rows(rows, program.seed_values)`(全量 seed 匹配)+ 终态回灌。
- **终态回灌依赖**:`_witness_terms(atom, terminal_row)` 逐个读本分支原子的项变量 → **本分支变量 + witness 必须留在 terminal**。
- souffle arity = 22;ring 分支 terminal 因"全量 seed 死重"而 >22。

## 5. Proposed Shape

两个互补的 arity 杠杆,目标:每分支 reach 关系 < 22(souffle 上限)。

### 5.1 主杠杆:丢掉死的 `__witness_N` 列(gate 时发现,是真正的 lever)
reach 的每个 pred 都挂一个 `__witness_N`(asrt)列,但**装配从不读它**——`_witness_terms` 读的是**项变量**(`row.get(term)`),`_append_witness` 只存项变量;`grep __witness` 证它**仅出现在 emission**(line 49/163-214/237-252)+ bootstrap(316),**parse/assembly 零引用**。即:asrt 被采集后**直接丢弃**(rich narrate 也不显示 asrt)。
**改动**:reach 的 pred 改用**普通 view**(`normalize_pred_id`)而非 witness-view(`witness_rel_name`),**去掉 `__witness_N` 列**(及对应 `include_pred_witness_columns`)。
**效果**:ring 13 个 pred → 丢 13 死列 → terminal 从 ~24/27 降到 **~14 < 22 → mule(ring HOLDS)也 rich**。
**为什么安全**:标签来自项变量(终态回灌 `_witness_terms` 不变);asrt 本就丢弃,不损失任何在用的东西;普通 view 同样绑定项变量,reach 计算不变。

### 5.2 互补:branch-local seed(已落地)
每分支只带自己引用的 seed 变量(丢其他分支的)+ 行匹配逐分支化。额外余量、无回归(C-EVE 已 rich)。

### 5.3 一个不动
**本分支的项变量**(终态回灌 `_witness_terms` 要从 terminal_row 读的)**一个不动**——这是相干性的命根,绝不收窄。

## 6. Boundaries And Invariants

- **只丢"其他分支的 seed 变量"**(可证本分支无任何原子/join 引用);本分支的头端口/匹配/join 变量、以及回灌要读的全部变量+witness,**全部保留**。
- **无行选择漂移**:对改前能跑的用例,选中的 witness/失败值与改前**一致**。
- 终态回灌(holding 分支相干性)必须保持。

## 7. Acceptance

- [ ] 全 SAR souffle narrate **rich reach-chain**(不再 fallback),覆盖**两类行**:
  - **C-EVE(ring 早失败)**:c0 全 Eo + c1 失败值 `2000<90` + not_reached 干净。
  - **mule C-M1(ring HOLDS,over-wide)**:**ring 分支也 rich**(设备环展开:两客户同设备 + `id1≠id2`),不再 flat fallback。
- [ ] gate 复合(无 shared_device):仍 rich(零回归)。
- [ ] holding 分支相干性保持(Eo 非 M2a)——全 SAR + gate 复合。
- [ ] 失败值保持正确。
- [ ] **无漂移**:改前能跑的用例,标签/值不变。
- [ ] 真·超宽单分支(自身 > 22 原子)→ 既有 arity 诊断清晰报错(不崩、不假 rich)。
- [ ] native / problog / eval **零回归**;相关 souffle/explain 测试绿 + 新增全 SAR rich + 无漂移回归。

## 8. Implementation Plan

1. [reach_explain] 实现前确认:plan 能否按分支拿到"本分支引用的 seed 变量"(`probe_seed_vars_by_head_port` + 分支原子变量交集)。若拿不到干净,停下回报。
2. [reach_explain] branch-local seed:per-branch seed 计算 + 每分支 reach 链本地起步。
3. [reach_explain] `_parse_reach_outputs` 行匹配逐分支化(对 branch-local seed values)。
4. [tests] 全 SAR rich + gate rich + 相干性 + 失败值 + 无漂移 + 超宽分支诊断。

## 9. Docs To Update

- `src/factgraph/adapters/souffle/docs/`(reach-chain branch-local seed;残留 Case A 由诊断兜底)

## 10. Outcome / Deviations

- 最终落地结果：reach 收窄 arity = **drop 死 `__witness_N`(主杠杆)+ branch-local seed(互补)**;宽分支/mule 现在 rich(设备环展开);`not_reached` 不再泄漏 `<unbound>`;commit `fb3044c5`。
- 与 blueprint 不同的地方：gate 中发现 branch-local seed 单独不足,真 lever 是 drop 装配从不读的死 `__witness_N` 列(§5.1,gate 后补)。
- 为什么会有这些调整：`__witness_N` 是装配从不读的死列(13/ring),drop 它才把宽分支降到 22 以下、mule 也 rich。
- 归档说明：已实现并提交;保留 active/ 作 problog 参照,后续一并归档。
