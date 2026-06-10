# Task Blueprint: explain — terminal-env re-bake for entity anchoring (`:exists` mislabel)

- Status: implemented
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: explain render-layer fix (scoped → **Codex 落地**,Claude scope-review/gate;按既有 explain conformance 惯例)
- Authority: `src/factgraph/application/explain/prober.py` + explain conformance program (archived `2026-06-10_explain-conformance-rework`)
- Audit Log:
  - [2026-06-10_explain-exists-anchoring-fix.audit.md](./2026-06-10_explain-exists-anchoring-fix.audit.md)

---

## 1. Problem

在 join / Entity-DSL 规则的解释里,**编译器自动前置的 `<Type>:exists(u)` 原子显示成一个固定见证实体,而非本行用户**(例:Carol/u-3 行显示 `User:exists(User u-2)`)。

- **已验证:不影响推理正确性**(缺 `:exists` 的实体不会漏进结果;verdict/行/绑定全对)。纯**显示层**瑕疵。
- 范围:`exists` 原子从不真正按行锚定——钉在固定见证(本例 u-2),仅当本行用户恰为该见证时才"对"。字段原子(`user:name` 等)锚定正确。单规则与 join 规则一致(非 join 独有)。

## 2. Root Cause(已在代码确认)

`prober.py`:
- `_probe_branch` 按顺序逐原子处理,`_probe_atom` 在**处理到该原子时**就用当时的 `form_envs` 把 `repr_text` 烤死(:184-188)。
- 自动前置的 `exists(u)` 排在最前,处理时 `u` 尚未被任何字段原子绑定 → `_extend_env_with_atom` 枚举所有存在用户 → `form_envs` 多环境。
- `_atom_form(atom, envs)` 取 **`envs[0]`**(:320)→ 落到任意见证(u-2)。
- 后续字段原子把 `u` 收敛到本行用户,但 exists 的 `repr_text` 已烤好,**无人回烤**。

## 3. Fix(提议)

在 `_probe_branch` 的原子循环**结束后、调用 `_body_rules_for_branch` 之前**(`prober.py:128–129`,此处 `view_facts`/`schema_index`/终态 `envs` 均在手),对 `atom_results` 做一次**终态环境重烤**:

```
for (idx, atom, ev, envs_after) in atom_results:
    if (not ev.negated) and terminal_envs and _all_atom_vars_bound(atom, terminal_envs[0].bindings):
        form = _atom_form(atom, terminal_envs)
        repr_text = _bake_repr_text(form, schema_index, view_facts=view_facts)
        ev = replace(ev, form=form, repr_text=repr_text)
```

- **守卫**:仅当该原子的全部 `$var` 在终态环境里已绑定才重烤;否则保留原烤(保住"纯存在性 / 变量本就自由"的合法用法,见 Q1)。
- 仅改**显示(form/repr_text)**;verdict / atom_id / 结构 / 求值一概不动。
- (待定)`_head_rule_for_plan` 的 head 原子若同理欠锚,可同法处理;本 demo 中 head 原子为 0,需实现时核。

## 4. Evidence — 改前/改后(runtime monkeypatch demo,未改 src)

joined 规则 / 3 用户:
| 行 | 改动原子数 / 总数 | exists 原子 | 字段原子 |
|---|---|---|---|
| Alice(u-1) | 3 / 15 | `User u-2` → `User u-1` ✅ | 不变 |
| Carol(u-3) | 3 / 15 | `User u-2` → `User u-3` ✅ | 不变 |
| Bob(u-2) | **0** / 15 | 本就 = u-2,重烤同值 → 不变 | 不变 |

→ **只修错的、不动对的**;已正确的行(Bob)零改动。

## 5. Impact Surface(已测)

- **直接断言 exists repr 的测试**:`tests/sdk/test_rule_expr_evaluate.py:661`(`atoms[0].repr_text == "Person:exists(...)"`)——重核;若它断言的是"被修正后的正确实体"则照过,若烤进了旧 buggy 实体则更新期望。
- **native explain 测试 battery**(需改前/改后跑):`test_prober`、`test_explanation_render`、`test_evaluate_result_dtos`、`test_explain_conformance_native`、`test_audit_evidence_graph`、`test_application_schema_runtime`、`test_sdk_schema_repr`。按 demo 性质,**只应有 `:exists` 断言变化,字段原子断言不变**。
- **引擎测试**(problog/pyreason/souffle):走各自 provenance,**不经 `probe_native`** → 预期不受影响;需确认。
- **文档**:quickstart + 模块 docs **0 处**硬编码 `:exists(` 输出 → 无需改文档。
- **notebook**:`examples/03_rules_and_evaluation.ipynb` 有 4 处 `User:exists(User u-2)` 输出 → 修后需**重跑**(会自动修正为本行用户)。

## 6. Risk

- 改的是**共享烤制路径**,理论 blast radius = 所有 native 解释的原子文字;但 demo 证明**对的不动、错的修正**,实际变更面被守卫收窄到欠锚的 `exists` 原子。
- 缓解:改前/改后全跑 §5 battery,逐条核对 diff,只接受"`:exists` 实体被修正"这一类变化;其余任何变化即回退排查。给用户过目后再合。

## 7. Test Plan / Acceptance

- [ ] 改前快照 §5 battery 输出;改后重跑,diff 仅含 `:exists` 实体修正(字段/verdict/结构 0 变)。
- [ ] `test_rule_expr_evaluate:661` 通过(必要时更新为正确实体期望)。
- [ ] 引擎 evidence 测试 0 变。
- [ ] `examples/03` 重跑,exists 行显示本行用户。
- [ ] 纯存在性 / 自由变量场景(守卫分支)repr 不变。

## 8. Non-goals

- 不改求值 / verdict / 结构 / 引擎 provenance。
- 不引入"折叠冗余 exists 行"的显示启发式(那是另一条可选路;本 slice 选"修正"而非"隐藏")。

## 9. Outcome / Deviations

Codex 落地(`prober.py` +53,仅此文件),Claude 独立 gate **PASS**(未 commit,待用户定):
- diff:`_probe_branch` 循环后插一行 rebake 调用 + 新增 `_atom_var_names` / `_rebake_atom_results_from_terminal`;只换 `form`+`repr_text`,保留 `verdict`/`atom_id`/`negated`/`timestep`。
- **偏差(Codex 自加,已审 + 实测安全)**:额外收窄护栏——若原子 `envs_after[0]` 与终态对所有变量一致则跳过 rebake(避免单实体/已正确场景重复渲染)。实测 4 场景(单/join × 多/单用户)exists **全部正确锚定**,确认该护栏不误跳。
- 实测修正:Carol→`User:exists(User u-3)`、Alice→`u-1`(原 u-2);Bob/单用户不变。
- 独立测试:native explain battery **82 OK** + 引擎 evidence **9 OK** + DTO/schema-runtime/schema-repr **52 OK** = **143 OK**;字段/verdict/结构未变。
- `test_rule_expr_evaluate`(含 :661,ProbLog provenance 路径、不经 probe_native)原样过。
- `examples/03` 重跑:exists 标签 4 处全 `User:exists(User u-3)`(本行 Carol)。
- sacred master `854d03b9` 不变;tracked diff 仅 `prober.py`。
- 模块 docs:无需改(修复使行为符合既有锚定预期,无 doc 声明旧 buggy 行为)。
- 待:`prober.py` 改动 + 本蓝图 commit 决策(归入 examples notebook 提交决策一并定)。
