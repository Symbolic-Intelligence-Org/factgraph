# Audit Log: Lower `!=` to the `ne` primitive (root fix)

Paired with [2026-06-21_ne-primitive-lowering.md](./2026-06-21_ne-primitive-lowering.md).

## 2026-06-21 — Open (draft): root-cause traced + empirically validated (Claude)

### 由来
souffle reach-chain S1 gate PASS 后,user 在 demo 上跑 `engine="souffle"` 撞 `WhereValidationError exit_code 1`(eval 层)。user 追问"`!=` eval 是否涉及更深本质"。深挖确认:**是,且一路追到整轮调查的总根**。

### 根因(代码确证)
- `expr.py::_lower_compare`(448)+ `_lower_compare_with_aggregate`(476):**所有比较算子都 lower 成直接原语,唯独 `ne` 写成 `("not",[("eq",l,r)])`,无注释/理由**。
- `ne` 是一等算子(`where_ast.py::_CMP_OPS`),每引擎都有直接处理:native `where_eval.py:397`;souffle `where_compile.py::_compile_ne_filter`(→`!=`);problog `problog_export.py:513/583`(→`\=`);souffle explain `reach_explain._compile_compare("ne")`。
- 同一病根制造三症:① 最初 problog 复合 narrate 退化 `'='`(`not(eq)` 被 `_not_inner_atoms` 拒)② souffle EVAL `!=` 崩(`not(eq)`→空参 `__not() :- C3=C4.` ungrounded)③ 跨引擎特判复杂度。

### 实证(monkeypatch,read-only,2026-06-21)
把 `("not",[("eq",l,r)])` 改写成 `("ne",l,r)`(patch `_lower_compare*` / `lower_where_atom`)后:
```
① souffle EVAL of shared_device (id1!=id2):  OK, 2 rows      ← demo eval 障碍消失
② problog narrate of != :                    11 lines, degraded=False, [atom] 富证明   ← 退化消失
```
注:problog `ne` 原子仍 `<unbound> does not equal <unbound>` —— **退化(`'='` 塌缩)已修;`<unbound>` 是 companion 标签 bug,属另一 deferred 单,根治不碰**。

### Scope
- 改 `expr.py` 两处 `ne` lowering → `("ne",...)`。
- 取代:standalone souffle `!=` eval-codegen 单;deferred problog 单里"`!=` 退化"部分。
- 正交保留:S1(souffle explain reach-chain);problog companion `<unbound>` 标签单。

### 待验(scope-freeze / Codex challenge 前必须)
1. **隐藏理由**:`git blame` expr.py:448/476 + 搜全仓有无依赖 `!=`-as-`not(eq)`(IR 形状断言 / unbound `!=` / problog negation-as-failure 语义)。
2. **unbound 语义**:直接 `ne` 要求两侧已绑(更严);审有无 `!=`-on-unbound 旧用法。
3. **全量测试**:本次仅 2 规则;改 lowering 影响所有 `!=`,需全套绿 + 更新旧-IR 断言测试。

### Cadence
draft → Codex challenge(隐藏理由 + unbound + 全量影响,**发现真理由就停**)→ 若清白 → scoped → Codex 落地(2 行改 + unbound 审计 + 全套测试)→ Claude gate(souffle eval 通 + problog `!=` 不退化 + native 不变 + 全套零回归)→ user merge。
