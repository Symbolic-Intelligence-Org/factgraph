# Task Blueprint: ProbLog diagnostic projection supports `!=` (negated comparison) atoms

- Status: scoped (standalone fix **REVERTED** — net-negative; superseded by `2026-06-20_problog-companion-explain-rewrite`)
- Created: 2026-06-20
- Last Updated: 2026-06-20 (reverted after real-demo perf regression; folded into companion-rewrite blueprint B)
- Related Modules:
  - `src/factgraph/application/explain/diagnostic_projection.py`
  - `src/factgraph/adapters/problog/diagnostic_emit.py` (reference only — already correct)
- Related Docs:
  - [workflow/foundations/architecture_principles.md](../../foundations/architecture_principles.md)
- Audit Log:
  - [2026-06-20_problog-diagnostic-ne-atom.audit.md](./2026-06-20_problog-diagnostic-ne-atom.audit.md)

## 1. Problem

含 `!=` 的规则,其 `Explanation.narrate()` 在 ProbLog 引擎下退化为原始 companion-program 原子(`'='(…)` / `edb_fact` / `[c0:head:0]`),而不是逐条件证明。根因:`a != b` 被 lower 成 `not(eq(a,b))`;companion 投影的 `_not_inner_atoms` 仅允许 `not` 内层为 `pred`(EDB)原子,遇到 `eq` 即抛 `DiagnosticProjectionError("not atom companion only supports EDB predicate bodies")`,从而退化。

经隔离实验确认:**仅 `!=` 触发**(`== >= > < <=`、算术比较均正常富渲染);单规则与复合(如 `shared_device` 的 `id1 != id2`)都受影响;**结果集与概率(`.certainty`)不受影响**,纯解释渲染问题。仅存在于 `factgraph/main` 线(post-v0.2.0);release `v0.2.0` 无 `narrate()`,不受影响。

## 2. Goals

- 含 `!=` 的规则/复合在 ProbLog 下 `narrate()` 产出逐条件富证明(与 native 结构对齐),负向比较以 `≠` 语义呈现。
- 概率忠实性不变:WMC 路径不受影响,负向比较以 negation-as-failure 精确表达。

## 3. Non-goals

- 不触碰 WMC / 概率计算路径。
- 不改 `_companion_atom` 递归、`diagnostic_emit.py` 的 `\+(…)` emission、`CompanionCompare` 渲染(均已正确)。
- 不放开 `agg` / `ruleref` / 嵌套 `not` 的现有拒绝。
- 不扩展到其它比较算子(它们已正常)。

## 4. Current Context

- 当前实现入口:`src/factgraph/sdk/store.py::_problog_row_graph_builder`;复合(有 `lowering_plan`)走 `_problog_diagnostic_projection_graph` → `build_companion_program`。
- 失败点:`diagnostic_projection.py::_not_inner_atoms`(约 331–342 行;line 339–340 的 `pred`-only 判定)。
- 下游已就绪:`_companion_atom` 的 `"not"` 分支 `negated=not negated` 递归(302 行)→ `CompanionCompare(op, negated=True)`;`diagnostic_emit.py:277` 对 negated compare 输出 `\+(call)`(≡ `a != b`),逻辑精确。
- 验证证据:见 audit 的实验记录(形状隔离 + 算子全扫 + 共享事实容斥)。

## 5. Proposed Shape

单点放开 `_not_inner_atoms` 的内层原子白名单:在 `pred` 之外,允许比较类 kind(`eq ne gt ge lt le`)。其余链路无需改动——既有递归(`_companion_atom`)与 emission(`diagnostic_emit`)已支持负向比较。

## 6. Boundaries And Invariants

- 必须保持的边界:WMC/概率路径不变;`agg`/`ruleref`/嵌套 `not` 仍拒绝;其它比较算子行为不变;`not(pred)` 负向仍正常。
- 明确不做:不重写 companion 生成,不改 emission/渲染,不改 lowering。
- 兼容性约束:实现 diff 仅落在 `_not_inner_atoms` + 新增测试。

## 7. Acceptance

- [ ] 含 `!=` 的单规则 ProbLog `narrate()` 富渲染(出现 `[cN:atom:` 逐条件;不含 `edb_fact` / `'='(` / `cN:head:0`)。
- [ ] 含 `!=` 分支的复合(`shared_device` 形状)ProbLog `narrate()` 富渲染,顶层 probability 与行 `.certainty` 一致。
- [ ] 共享概率事实的复合总概率正确(容斥;`0.5` 而非 `0.75`)——锁住"未改变模型"。
- [ ] `not(pred)` 既有负向无回归;其它比较算子无回归。
- [ ] `PYTHONPATH=src pytest`(相关 explain / problog 测试模块)绿。
- [ ] 受影响模块 docs 已同步(如有 `!=` / companion 限制说明则更新)。

## 8. Implementation Plan

1. [diagnostic_projection.py] 实现前确认 IR:`a != b` 确实进入 `_not_inner_atoms` 且内层 `item[0] == "eq"`(若不同,停下回报,不强改)。
2. [diagnostic_projection.py::_not_inner_atoms] 将 line 339–340 的 `if item[0] != "pred"` 放开为 `if item[0] not in {"pred","eq","ne","gt","ge","lt","le"}`,并更新错误信息为 `"...EDB predicate or comparison bodies only"`。
3. [tests] 新增回归:Acceptance 1–4 各一条最小用例(单规则 `!=`、复合 `!=` 分支、共享事实总数、`not(pred)` 与其它比较无回归)。
4. [docs] 检查 explain 模块 docs 是否有"含 `!=` 的规则 ProbLog narrate 退化"的限制说明,若有则改为已支持。

## 9. Docs To Update

- `src/factgraph/application/docs/`(explain / narrate 相关,若有 `!=` 限制说明)
- `docs/README.md`(无新持久入口,通常不需要)

## 10. Outcome / Deviations — REVERTED

- 实现并 gate PASS(仅对 19-笔小数据),但 **user 在真实 demo 上复现严重回归**,经复现确认根因后**回退**:
  - **根因**:companion 路径 `run_diagnostic_problog` 把**整个 ledger** 重新编译进新 ProbLog 程序再跑一遍,**O(ledger)**。实测 19 笔→1.4s(RICH);**49 笔→32.1s 撞 30s 超时→仍退化成 `'='`**。
  - **本修复的副作用**:修复前 `!=` 在 `build_companion_program` **快速失败 → 快速回退**;修复后它**成功 → 触发那次昂贵重算 → 真实 ledger 上 30s 超时**。即把"快+退化"变成"30s+退化",**对非平凡 ledger 严格更差**。
  - **回退**:`git checkout` 丢弃 `diagnostic_projection.py` + `tests/sdk/test_rule_expr_evaluate.py` 的工作树改动(未 commit)。回退后 49 笔→1.2s(快,`!=` 回到快速退化)。
- **Gate 失误教训**(写给以后):
  1. 只测了 19-笔玩具数据,**没测 ledger 规模/性能** → 漏掉 O(ledger) 超时。
  2. 回归断言只查"有 `[atom:` 且无 `'='`"(结构),**没查标签正确性** → 漏掉 `Txn 错/<unbound>` 标签 bug。
  3. **没核对 user 实际 import 的是哪份代码 / 实际 ledger 状态**,先用"没重启 kernel"等错误猜测搪塞 → 浪费信任。
- **结论**:`!=` 仅为表象;真问题是 **companion 重算路径本身**(性能 + 标签)。本单**作废/折叠进 B**(`2026-06-20_problog-companion-explain-rewrite`)。
- 归档说明:本单不单独归档为"已实现";随 B 推进时作为"reverted 前置调查"引用。
