# Task Blueprint: Lower `!=` to the `ne` primitive (root fix, supersedes `not(eq)`)

- Status: draft
- Created: 2026-06-21
- Last Updated: 2026-06-21
- Branch: `v0.2.0-souffle-reach-chain-explain` (or a sibling; decide at scope-freeze)
- Related Modules:
  - `src/factgraph/sdk/dsl/expr.py` (`_lower_compare` line 414, `_lower_compare_with_aggregate` line 459 — the two `ne → not(eq)` sites at 448 / 476)
  - `src/factgraph/adapters/souffle/where_compile.py` (`_compile_ne_filter` — direct `ne` → `!=`, already correct)
  - `src/factgraph/adapters/problog/problog_export.py` (line 513 `ne`, line 583 `{"ne": "\\=", ...}` — direct `ne` → `\=`, already correct)
  - `src/factgraph/core/rules/where_eval.py` (native direct `ne`, line 397 etc. — already correct)
  - `src/factgraph/adapters/souffle/reach_explain.py` (souffle explain `_compile_compare("ne")` — already handles direct `ne`)
- Related Docs:
  - [workflow/foundations/architecture_principles.md](../../foundations/architecture_principles.md)
- Audit Log:
  - [2026-06-21_ne-primitive-lowering.audit.md](./2026-06-21_ne-primitive-lowering.audit.md)
- Related historical blueprints:
  - [2026-06-21_souffle-reach-chain-explain.md](./2026-06-21_souffle-reach-chain-explain.md) (souffle EXPLAIN; orthogonal — handles `ne` already)
  - [2026-06-20_problog-companion-explain-rewrite.md](./2026-06-20_problog-companion-explain-rewrite.md) (problog explain `<unbound>` label bug — separate; NOT fixed here)
  - [2026-06-20_problog-diagnostic-ne-atom.md](./2026-06-20_problog-diagnostic-ne-atom.md) (reverted `!=` companion patch — this root fix is the real cure for its `!=` symptom)

## 1. Problem

在 SDK object-DSL 里,**所有比较算子都 lower 成各自的直接原语,唯独 `ne` 被写成 `("not",[("eq",l,r)])`**(`expr.py::_lower_compare` line 448 + `_lower_compare_with_aggregate` line 476),**且无任何注释/理由**:
```python
if expr.op == "ne":  out.append(("not", [("eq", left, right)]))   # 反常
if expr.op == "eq":  out.append(("eq", left, right))
if expr.op in {"gt","ge","lt","le"}: out.append((expr.op, left, right))
```
而 `ne` 是 AST 一等算子(`where_ast.py::_CMP_OPS` 含 `ne`),**每个引擎都有健全的直接 `ne` 处理**:souffle `_compile_ne_filter`→`!=`、problog `\=`、native `where_eval`、souffle/native explain。

这一处反常 lowering 是**多个已观测故障的同一病根**:
1. **最初的 problog 复合 narrate 退化成 `'='`**(本轮调查的起点)——`not(eq)` 被 `diagnostic_projection._not_inner_atoms` 拒。
2. **souffle EVAL `!=` 崩**(`WhereValidationError exit_code 1`,demo `engine="souffle"` 的真实报错)——`not(eq)` 在 `where_compile` 生成**空参** `__not_xxx() :- C3=C4.`,C3/C4 ungrounded。
3. 跨引擎处理复杂度(souffle reach_explain 要特判 `ne`/`not(eq)`)。

## 2. Goals

- `a != b` 在 SDK lower 成 `("ne", left, right)` 直接原语(与 `eq`/`gt`/... 一致),不再绕 `not(eq)`。
- 在**源头**修复:souffle EVAL `!=`(demo 的 souffle 路径求值通)+ problog EXPLAIN `!=` 退化(不再 `'='`)。
- 消除 `not(eq)` 跨引擎地雷。
- 所有引擎 `!=` 行为正确,**全量测试零回归**。

## 3. Non-goals

- **不修** problog companion 的 `<unbound>` 标签 bug(根治后 problog `!=` explain 从"退化"变成"富但 `<unbound>`";`<unbound>` 是 companion 标签问题,属 [2026-06-20_problog-companion-explain-rewrite] deferred 单)。
- **不碰** souffle EXPLAIN reach-chain(S1,已 gate PASS,正交,已处理 `ne`)。
- **不修** souffle `not(<comparison>)` 的空参 helper codegen(genuine `not(comparison)` 仍有此 bug,但已不在 `!=` 热路径;独立低优先级单)。

## 4. Current Context

- **病根位置**:`expr.py:448`(`_lower_compare`)+ `expr.py:476`(`_lower_compare_with_aggregate`)。
- **各引擎直接 `ne` 处理(均已存在、正确)**:native `where_eval.py:397`;souffle eval `where_compile.py::_compile_ne_filter`(→`{lhs} != {rhs}`,要求两侧已绑);problog `problog_export.py:513` + `:583`(→`\=`);souffle explain `reach_explain.py::_compile_compare("ne")`;native explain prober(materialized IR `ne`)。
- **实证(monkeypatch,2026-06-21)**:把 `("not",[("eq",l,r)])` 改写成 `("ne",l,r)` 后——souffle EVAL of `shared_device`(含 `id1!=id2`)**OK,2 rows**;problog narrate of `!=` **degraded=False、11 atoms、无 `'='`**。→ 根治方向已验。
- **已知约束 / 待审**:直接 `ne` handler 要求**两侧已绑**(unbound 会 raise);`not(eq)` 可能容许过 unbound 边(`eq` 先绑、再否定)。常见(双绑)场景等价已验;**unbound 边场景需审计**(见 §6/§7)。

## 5. Proposed Shape

`expr.py` 两处 `if expr.op == "ne":` 改为发射 `("ne", left, right)`:
```python
# _lower_compare (448):                  out.append(("ne", left, right))
# _lower_compare_with_aggregate (476):   return [("ne", left, right)]
```
其余链路无需改动——各引擎的直接 `ne` 处理均已就绪。`not(...)` 机制保持不变(仍服务 genuine `not(...)`)。

## 6. Boundaries And Invariants

- 只改 `ne` 的 lowering;不碰各引擎的 `ne`/`not` 处理(已正确);不碰 `eq`/`gt`/`ge`/`lt`/`le`。
- **unbound 语义**:直接 `ne` 要求两侧已绑——这是更严格(更安全)的行为。必须审计现有代码/测试是否有 `!=` 用在 unbound 边上;若有,确认其在 `ne` 下是"应报错的真 bug"还是需要保留的行为(后者则本根治需附加处理或暂缓)。
- **测试形状**:可能有测试断言 `!=` 的 IR 是 `not(eq)` 形;这些需更新为 `ne`。
- problog companion `<unbound>` 标签 bug 不在本单(根治不引入也不修复它)。

## 7. Acceptance

- [ ] `a != b` 的 materialized IR 为 `("ne", l, r)`(不再 `("not",[("eq"...)])`)。
- [ ] **souffle EVAL**:含 `!=` 的规则/复合(如 `shared_device`、完整 SAR)在 `engine="souffle"` 下求值成功(不再 `exit_code 1` ungrounded)。
- [ ] **problog EXPLAIN**:含 `!=` 规则 `narrate()` 不退化(无 `'='`/`edb_fact`;`ne` 原子以"does not equal"语义呈现)。(注:problog `<unbound>` 标签属另一单,不在本单验收。)
- [ ] **native** `!=` eval + explain 行为不变。
- [ ] **unbound 审计**:全代码/测试无依赖 `!=`-on-unbound 的 `not(eq)` 旧行为;若有,记录并处置。
- [ ] **全量测试零回归**:`PYTHONPATH=src` 全套(native/souffle/problog/explain)绿;断言旧 `not(eq)` IR 形状的测试已更新。
- [ ] 受影响 docs 同步(若有"`!=` lower 成 `not(eq)`"的说明)。

## 8. Implementation Plan

1. [challenge 先行] Codex 先**对抗性核查**:`git log`/`git blame` `expr.py:448/476` 看是否有历史理由;搜全仓有无依赖 `!=`-as-`not(eq)`(IR 形状断言、unbound `!=` 用法、problog `\+`/negation-as-failure 语义依赖)。**发现真实理由就停下回报**,否则继续。
2. [expr.py] 两处改为 `("ne", left, right)`。
3. [audit] unbound 边 `!=` 全量审计(代码 + 测试);处置或记录。
4. [tests] 跑全套;更新断言旧 IR 的测试;新增 `!=` 在 souffle eval + problog explain 的端到端回归。
5. [docs] 同步。

## 9. Docs To Update

- 任何描述 `!=`/`ne` lowering 的 docs(SDK DSL / where IR 文档)。
- `docs/README.md`(通常无新持久入口)。

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
