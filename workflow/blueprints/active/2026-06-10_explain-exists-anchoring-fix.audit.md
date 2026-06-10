# Audit Log: explain — terminal-env re-bake for entity anchoring

Paired with [2026-06-10_explain-exists-anchoring-fix.md](./2026-06-10_explain-exists-anchoring-fix.md).

---

## A. Investigation (2026-06-10, read-only)

发现链(均有实测/代码留痕):

1. **症状**:joined `build_application_rule` 解释里 `User:exists` 显示 `User u-2`,而本行是 Carol/u-3。
2. **范围实验**(`/tmp/exists_scope.py`):单规则与 join 规则一致;`exists` 钉在固定见证(u-2),仅本行用户恰为该见证时"对"(Bob/u-2 行对;1 用户场景对)。字段原子始终正确按行。
3. **可靠性实验**(`/tmp/exists_reliability.py`):造"有全字段、无 `:exists`"的 Dave/u-9,求值**正确排除**他 → 存在性守卫在 evaluate 逐行严格生效 → **纯显示层问题,不影响正确性**。
4. **根因**(`prober.py` 读码):`_probe_atom` 在处理到原子时即用中间 `form_envs` 烤 `repr_text`(:184-188);前置 `exists(u)` 处理时 `u` 未绑;`_atom_form` 取 `envs[0]`(:320)落到任意见证。终态 `envs`(`u` 已绑)在 `_probe_branch` 循环后可得(:128),`_body_rules_for_branch` 已收 `terminal_envs`。
5. **修法验证**(`/tmp/exists_fix_demo.py`,runtime monkeypatch,未改 src):在循环后按终态环境重烤(守卫:原子全部 `$var` 在终态已绑才烤)。结果:Alice u-2→u-1、Carol u-2→u-3,字段原子不变,Bob(本就 u-2)0 改动。
6. **影响面**(grep):直接 exists-repr 断言仅 `test_rule_expr_evaluate:661`;native explain battery ~8 文件;引擎测试不经 probe_native;docs 0 处硬编码;notebook 03 有 4 处需重跑。

## B. Build Log

### Codex 落地 spec (handed off 2026-06-10)

File: `src/factgraph/application/explain/prober.py`(仅此文件)

1. 新增模块级 helper:
   - `_atom_var_names(atom) -> set[str]`:递归收集原子里所有 `$`-前缀变量名。
   - `_rebake_atom_results_from_terminal(atom_results, *, terminal_envs, view_facts, schema_index)`:终态为空→原样返回;否则对每个 `(idx, atom, ev, envs_after)`,若 `not ev.negated` 且该原子全部 `$var` 在 `terminal_envs[0].bindings` 已绑(非 None),则 `form=_atom_form(atom, terminal_envs)`、`repr_text=_bake_repr_text(form, schema_index, view_facts=view_facts)`,以新 `EvidenceAtom` 替换(仅换 `form`+`repr_text`,保留 `verdict`/`atom_id`/`negated`/`timestep`)。
2. 在 `_probe_branch` 原子循环结束后、`_body_rules_for_branch` 调用前插入一行:`atom_results = _rebake_atom_results_from_terminal(atom_results, terminal_envs=envs, view_facts=view_facts, schema_index=schema_index)`。

约束:只改 `form`+`repr_text`;不碰 verdict/结构/求值/引擎 provenance/`_head_rule_for_plan`(head 原子同问题作 follow-up)。守卫:negated 跳过、终态空跳过、变量未全绑跳过(保住纯存在性/自由变量)。

Gate（Claude 验收）:native explain battery 改前/改后 diff 仅 `:exists` 实体修正(字段/verdict/结构 0 变);`test_rule_expr_evaluate`(含 :661)过;引擎 evidence 测试 0 变;`examples/03` 重跑;期望 Carol→`User:exists(User u-3)`、Alice→`User:exists(User u-1)`。

## C. Closure

Codex 落地 `prober.py`(+53);Claude 独立 gate **PASS**:diff 仅换 `form`/`repr_text`(verdict/结构保留);4 场景 exists 全部正确锚定(Carol→u-3 / Alice→u-1);**143 独立测试 OK**(native explain 82 + 引擎 evidence 9 + DTO/schema 52);引擎 provenance 路径 0 变;`examples/03` 重跑修正(4×`User:exists(User u-3)`)。Codex 自加的"已一致则跳过 rebake"收窄护栏经实测不误跳。master `854d03b9` 不变。蓝图 → **implemented**;`prober.py` + 蓝图 commit 待用户定(并入 examples notebook 提交决策)。
