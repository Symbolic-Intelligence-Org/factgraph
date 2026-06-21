# Audit Log: Souffle reach-chain branch-local seed (fix wide-branch arity)

Paired with [2026-06-21_souffle-reach-branch-local-seed.md](./2026-06-21_souffle-reach-branch-local-seed.md).

## 2026-06-21 — Open (draft): 残留定性 + 连带后果分析 (Claude)

### 由来
eval-arity 单 gate 时,Codex 诚实标出残留:full SAR 的 S1 rich explain 仍 fallback。user 追问"是否与 S1-reach-arity 有关"+"修复连带后果"。深挖确认并定连带边界。

### 实证(同机,souffle 2.5)
- reach 程序的关系逐层增宽(`fg_reach_c0_0`~7 → `fg_reach_c0_13`~20+,截断,实际 >22);手动跑 reach 程序 → `Requested arity not yet supported`(与 eval 同一 arity 崩溃)。**确认:full SAR rich-explain fallback = reach-chain arity > 22。**
- 读 `_parse_reach_outputs` 终态回灌(Codex 的相干性修复):holding 分支每个原子的 witness 从**最后一个 reach 的 terminal_row** 提取(`_witness_terms` 逐个读**本分支原子的项变量**)。

### 连带后果分析(动手前定清)
- **❌ "逐层收窄 reach 关系" UNSAFE**:终态回灌读 terminal_row 里**每个原子的项变量**;丢任何本分支变量/witness → 回灌拿不到 → `<unbound>`/M2a 不相干**回归**。与 Codex 刚修的相干性直接冲突,**排除**。
- **✅ "branch-local seed" SAFE**:全量 seed 携带所有分支头端口变量,但**单分支只引用自己的**;其他分支的 seed 变量是本分支从不读的死重 → 丢之**不碰**回灌/相干/失败值。
- branch-local seed 自身风险(可控):seed 同时是行匹配锚 + 跨分支 join 基 → 必须保留本分支的匹配/join/头端口变量,只丢确属其他分支的;并验**无行选择漂移**。
- 余量:branch-local 丢 ~2-4 列,解 AML ring(余量窄);"本分支原子数"是硬地板,真·超宽单分支仍 Case A → 既有诊断兜底。

### user 拍板
"可以这么修" —— 只做 branch-local seed(每条分支只带自己的列),不做逐层收窄。

### Scope
单点:reach_explain 的 seed 从全量改为 branch-local(每分支只带自己引用的 seed 变量)+ 行匹配逐分支化。本分支变量/witness/回灌/失败值全不动。

### Cadence
draft → Codex 落地(branch-local seed)→ Claude gate(全 SAR rich + gate 复合不回归 + 相干性 + 失败值 + **无漂移** + 超宽分支诊断 + 零回归)→ user merge → demo §5 souffle 端到端 rich 验。

## 2026-06-21 — Claude gate(branch-local seed):correct-but-insufficient + 发现真 lever

### 独立复现(我测了 Codex 没测的 mule)
- **C-EVE**(ring 早失败):c0 全 **Eo**(`exists`/`is by` 都是 Eo,不再 M2a/E1)、c1 失败值 `2000<90`、not_reached 干净 → **rich**。相干性**无回归**(我担心的连带后果没发生)。182 测试 + 全套(仅 1 预存)绿。
- **C-M1**(mule,ring **HOLDS**、over-wide):`rich=False, flat fallback (supported by <hash>)=True` → **仍 fallback**。Codex 只测 `res.first()`=C-EVE,漏了 mule。

### 根因 + 真 lever(gate 中挖到)
branch-local seed 只丢 ~3 列,ring(13 pred)terminal 仍 ~24 > 22。查 `__witness_N` 去向:**reach 每个 pred 挂的 `__witness_N`(asrt)列,装配从不读**(`_witness_terms` 读项变量;`grep __witness` 仅在 emission)。→ **丢掉这些死列(pred 改用普通 view)是真正的 arity lever**:ring → ~14 < 22 → mule rich。安全(标签来自项变量、asrt 本就丢弃)。

### 判定
branch-local seed **改动正确、无回归、解了 C-EVE**,但 **Acceptance #1 对 mule 未达**。**追加主杠杆 §5.1(drop 死 `__witness_N`)**,与 branch-local seed 合并为本单完整范围。

### 修正 Cadence
本单范围扩为 **§5.1 drop `__witness_N`(主)+ §5.2 branch-local seed(已落地,互补)** → Codex 落地 §5.1 → Claude gate(**mule rich** + C-EVE rich + 相干性 + 失败值 + 无漂移 + 超宽诊断 + 零回归)→ user merge。
