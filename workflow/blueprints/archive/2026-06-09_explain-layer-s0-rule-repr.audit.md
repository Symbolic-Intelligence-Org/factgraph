# Audit Log: S0 — Rule.desc → Rule.repr

Paired with [2026-06-09_explain-layer-s0-rule-repr.md](./2026-06-09_explain-layer-s0-rule-repr.md).

---

## A. Preflight (2026-06-09, 实读种子 854d03b9 工作树)

完整读 `rule.py`(629 行)+ `git grep` 全树 desc 调用点。

### Shipped vs Design 三角表

| 项 | Shipped(种子) | Design §12 | S0 动作 |
|---|---|---|---|
| field | `Rule.desc: str \| None`(rule.py:60) | `Rule.repr` | rename |
| render method | `render_desc(bindings)`(:115) | `render_repr` | rename |
| validator | `_validate_desc`(:239) | — | rename `_validate_repr` |
| 占位符语义 | `%port` → 值;unbound → `<port>` | 不变 | 保留 |
| content_digest | payload `{ports, when}`,不含 desc(:108-113) | — | **不受影响**(无 digest churn) |
| deprecated alias | 无 | §9 Q-C 倾向 alias | **hard-rename**(v1 实证 + pre-1.0,见子蓝图 §5) |

### 调用点清单(改名影响面 = 1 src + 4 test)

- src:`evaluate_result.py:952`(`render_desc` + `.desc`)。
- test:`test_rule.py`、`test_evaluate_result_dtos.py`、`test_application_rule.py`(sdk dsl)、`test_ruleexpr_inspect.py`。

### 待核(不阻塞)

- `rule_expr_inspect.py:151/469` `occurrence.desc_template`/`_render_desc_template`:疑为独立 inspect-layer 概念(occurrence 描述模板),非 `Rule.desc`。impl 时确认来源:源自 `rule.desc` 则更新 source read;否则不动。

## B. Locked decisions

- **hard rename,无 alias**(子蓝图 §5;若 `<user>` 要 alias 再改)。
- 纯改名零行为变化;`render_repr` 输出逐字符等于旧 `render_desc`。
- content_digest 不变 → 无 rule_set_digest churn。

## C. Gate result (Claude 独立验证 2026-06-09)

impl `2c8f8c71`(parent = design HEAD `e662b54c`,干净线性栈;854d03b9 + e662b54c 均祖先)。

- commit 12 文件全属 S0 范围(rule.py / evaluate_result.py / rule_expr_inspect.py / sdk/dsl/application_rule.py / 4 tests / 4 docs);**无** memory 迁移或既有 dirty 混入。
- desc/render_desc 残留:src 全树 **0**。
- repr 接通:`rule.py:60/115/239` + `evaluate_result.py:827/952/965` 确认。
- content_digest 断言已补且通过(`test_rule.py:137` `same_with_repr` 等值 + `:239` alias-independent)。
- cohort:**86 tests OK**(worktree `/tmp/wt-s0` 独立重跑,已清理)。

裁决:**PASS**。

## D. Deviations(良性)

- 待核项解决:`rule_expr_inspect.desc_template` 源自 `Rule.desc`,已改 `repr_template`。
- Codex 补漏:`sdk/dsl/application_rule.py build_application_rule(repr=)`(preflight 未列)。
- metadata key → `repr_template`(rename 自然结果)。
