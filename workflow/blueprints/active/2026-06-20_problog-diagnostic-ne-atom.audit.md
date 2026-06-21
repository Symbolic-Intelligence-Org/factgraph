# Audit Log: ProbLog diagnostic projection supports `!=` atoms

Paired with [2026-06-20_problog-diagnostic-ne-atom.md](./2026-06-20_problog-diagnostic-ne-atom.md).

## 2026-06-20 — Diagnosis + scope-freeze (Claude)

### Trigger
用户报告复合 SAR 在 ProbLog 下 `narrate()` 退化为 `'='(…)` 原始原子。初判"复合渲染坏"——经实验**证伪**。

### Experiments (read-only / scratch；在 `v0.2.0-release-aligned` = factgraph/main 内核)
1. **共享概率事实容斥**:两分支共用 `risk@0.5`;引擎 `P(A∨B)=0.5`(WMC 容斥正确),naive noisy-OR=0.75(错 +0.25)。→ 引擎忠实;§7 的 noisy-OR 分解仅对**独立**分支成立。该(无 `!=`)复合 `narrate` **富渲染且忠实**(逐原子 `(p=0.5)`,顶层 `0.5`)。
2. **形状隔离**:`OR-of-simple`=RICH;`AND+join_by_ports(无 !=)`=RICH;`单规则含 !=`=DEGRADED;`复合含 != 分支`=DEGRADED。→ 触发器是 `!=`,非复合/join/AND-OR。
3. **算子全扫**:`== >= > < <= ==(var vs num) 算术==` 全 RICH;**仅 `!=` DEGRADED**。
4. **代码定位**:`!=` lower 成 `not(eq)` → `_companion_atom` 的 `"not"` 分支 → `_not_inner_atoms`(line 339–340)拒绝非 `pred` 内层 → 抛 `DiagnosticProjectionError` → 退化。下游 `CompanionCompare(negated)`(line 297）+ emission `\+(call)`（diagnostic_emit.py:277)已正确。

### Collateral clearance（确认无连带 / 无误判)
- emission 已对 negated compare 输出 `\+(a==b)` ≡ `a!=b`,逻辑精确 → 重跑 WMC 忠实,**无概率漂移**。
- `!=` 为确定性约束,无概率权重。
- `agg` / `ruleref` / 嵌套 `not` 拒绝逻辑保持不动。
- 其它比较算子已富渲染,本改动不触及。

### Scope-freeze
单点放开 `_not_inner_atoms` 内层白名单(+ 回归测试)。状态 → `scoped`。

### Cadence
Codex 落地代码 → Claude gate(对照 boundaries + 跑测试 + codex review)→ user merge。

## 2026-06-20 — Implementation handoff to Codex (Claude)

- Blueprint frozen at `scoped`；状态推进 → `implementing`。
- 交付 Codex 的指令(经 user 转递):
  1. 先读 blueprint + 本 audit;实现前**确认 IR**:`a != b` 进入 `_not_inner_atoms` 且内层 `item[0] == "eq"`(不同则停下回报)。
  2. 单点改 `_not_inner_atoms` line 339–340 白名单(§8.2);**仅此一处** + 新增测试。
  3. 回归测试覆盖 Acceptance 1–4;`PYTHONPATH=src pytest` 相关模块绿。
  4. 不提交/不推送,回传 diff + 测试输出 + IR 确认,交 Claude gate。
- Scope guard 重申:不动 WMC/emission/lowering/`_companion_atom`/`agg`/`ruleref` 拒绝。

## 2026-06-20 — Claude gate: PASS (Claude)

Codex 回传:仅 `_not_inner_atoms` 改动 + 测试;IR 确认 `not(eq)`(对象-DSL `!=`),直接 `CmpAtom("ne")` 本已支持;pytest 环境 `readline` segfault,unittest 61 OK;`git diff --check` 通过;无 shipped 限制 doc 需改。

Gate 复核(在 `v0.2.0-release-aligned` 内核):
- **Scope**:diff 仅 `diagnostic_projection.py`(4 行)+ `tests/sdk/test_rule_expr_evaluate.py`(+165);boundaries 全守(WMC/emission/lowering/`_companion_atom`/`agg`/`ruleref` 未动)。✓
- **生产改动**逐字符合 §8.2(`pred` → `{pred,eq,ne,gt,ge,lt,le}` 白名单 + 错误文案)。✓
- **新测试**:4 条均 RUN(`problog` CLI 在场,非 skip)且 PASS——unittest 4/4 OK;pytest 4 passed。覆盖 Acceptance 1–4。✓
- **回归**:全相关模块 `pytest` 61 passed, 7 subtests passed(`test_diagnostic_projection` + `test_problog_diagnostic_emit` + `test_rule_expr_evaluate`)。✓
- **独立复现**(SDK 对象-DSL `!=`):narrate 富渲染——`paired [holds] (p = 1 × 0.5 × … = 0.5)`,逐条件 `[c0:atom:N]`,负比较 `!… equals …`,无 `edb_fact`/`'='`。✓
- **pytest** 在 gate 环境正常运行(Codex 的 segfault 为环境/`readline` 问题,非本改动)。✓

判定:**PASS** → 交 user merge。可选:user 侧跑一次 `codex review` 做对抗复核。

## 2026-06-20 — REVERTED:真实 demo 性能回归 (Claude)

**Gate PASS 是假阳性**——只对 19-笔玩具数据成立。User 在真实 demo 上报:ProbLog explain **30 秒**且 narrate **仍是 `'='`**。排查链:

1. 先误判"kernel 未重启"——错(user 已重启 VSCode)。
2. 再疑"未加载 src 修复"——错(`factgraph.__file__` = 工作树 src,`FIX present: True`)。
3. **复现根因**(同机、同 src):
   ```
   ledger 19 笔: 1.4s  RICH
   ledger 49 笔: 32.1s DEGRADED   ← 撞 run_diagnostic_problog 的 30s 超时 → 退化
   ```
   `emit_diagnostic_problog` 把整个 ledger 重编译进新 ProbLog 程序重跑,**O(ledger)**。修复前 `!=` 在 `build_companion_program` **快速失败**(不触发重算);修复后**成功 → 触发 30s 重算** → 真实 ledger 上超时退化。**净负:快+退化 → 30s+退化。**

**回退**:`git checkout -- diagnostic_projection.py tests/sdk/test_rule_expr_evaluate.py`(未 commit)。回退后 49 笔→**1.2s**,30s 消失。

**教训**:① 没测 ledger 规模/性能;② 回归只断言结构、没断言标签正确性(`Txn 错/<unbound>` 漏网);③ 没先核对 user 实际跑哪份代码/ledger 状态,用错误猜测搪塞。

**结论**:`!=` 是表象;真问题是 companion 重算路径(性能 + 标签绑定)。本单作废,折叠进 **B**(`2026-06-20_problog-companion-explain-rewrite`)。
