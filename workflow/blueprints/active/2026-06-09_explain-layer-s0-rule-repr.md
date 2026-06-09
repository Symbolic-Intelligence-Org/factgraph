# Task Blueprint: S0 — Rule.desc → Rule.repr rename

- Status: implemented
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/application/protocol/rule.py` (rename target)
  - `src/factgraph/application/protocol/evaluate_result.py` (1 caller)
- Related Docs:
  - Design spec §12 (R7): [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-09_explain-layer-s0-rule-repr.audit.md](./2026-06-09_explain-layer-s0-rule-repr.audit.md)

---

## 1. Problem

design §12 (R7):统一 repr 命名体系 —— `Field.repr` / `Identity.repr` / `Meta.repr` / `Rule.repr` 全部叫 `repr`(措辞模板)。当前 `Rule.desc` 名称语义模糊。这是 G6(repr 链路)的第一步,也是最小、无依赖的 slice。

## 2. Goals

1. `Rule.desc: str | None` → `Rule.repr: str | None`(field)。
2. `Rule.render_desc(bindings)` → `Rule.render_repr(bindings)`(method)。
3. `_validate_desc` → `_validate_repr`(内部函数);regex `_DESC_PORT_RE`/`_MALFORMED_PERCENT_RE` 可同步改名(内部,非必须)。
4. 更新唯一 src 调用点 `evaluate_result.py:952`。
5. 迁移 4 个测试文件的 `desc=` / `render_desc` 引用。
6. 纯改名,**零行为变化**。

## 3. Non-goals

- schema DSL `Field(repr=)/Identity(repr=)/Meta.repr`(S1)。
- `render_entity_repr`(S2)。
- prober / EvidenceGraph(S3+)。
- 不改 `Rule.render_repr` 的占位符语义(仍 `%port`,`<port>` for unbound)。
- 不动 `rule_expr_inspect` 的 `desc_template`/`_render_desc_template`(独立 inspect-layer 概念,见 §4 待核)。

## 4. Current Context(preflight 已完成,实读 rule.py 全文)

**rename 目标(rule.py):**
- `desc: str | None = None`(:60);`__post_init__` `_require_non_empty_str(self.desc, ...)`(:66-67);`_validate_desc(self.desc, ...)`(:94)。
- `render_desc()`(:115-128);`_validate_desc()`(:239-247);`_DESC_PORT_RE`(:43)/`_MALFORMED_PERCENT_RE`(:44)。

**唯一 src 调用点:**
- `evaluate_result.py:952` —— `result.head.render_desc(public_bindings) if result.head.desc is not None else ""`。

**测试影响(4 文件):**
- `tests/application/protocol/test_rule.py`(render_desc tests, desc=)
- `tests/application/protocol/test_evaluate_result_dtos.py`(desc=, render_desc 语义)
- `tests/sdk/dsl/test_application_rule.py`(render_desc, desc=)
- `tests/sdk/test_ruleexpr_inspect.py`(desc=)

**关键 de-risk:** `Rule.content_digest` payload(:108-113)= `{ports, when}`,**不含 desc** → 改名**不影响 content_digest / rule_set_digest**,无 digest churn。

**待核(impl 时确认,不阻塞):** `rule_expr_inspect.py:151/469` 的 `occurrence.desc_template` / `_render_desc_template` 是否源自 `rule.desc`。若源自 → 更新该 source read;若独立 → 不动(inspect-layer `desc_template` 命名保留,可后续单独处理)。

## 5. Proposed Shape

**决策:hard rename,不保留 `desc` deprecated alias。**
- 理由:① v1 已实证 hard-rename 可行(parent §6 "Alpha rename 原则: 不保留旧名 alias");② pre-1.0 preview line,调用面极小(1 src + 4 test);③ design §9 Q-C 的 alias 倾向是为公开 release 过渡,本 v2 在 publish 前完成,无需 dual-name 维护。
- (若 `<user>` 要求保留 alias,改为 `desc` property → `repr` 归一 + DeprecationWarning。)

形状:`Rule.repr: str | None = None`;`render_repr(bindings)`;`_validate_repr`。占位符语义、validation 规则、错误消息文本里的 "desc" 改为 "repr"。

## 6. Boundaries And Invariants

- 纯改名,无语义/行为变化;`render_repr` 输出与旧 `render_desc` 逐字符相同。
- `content_digest` 不变(见 §4 de-risk)。
- INV-6 application-first:仅 `application/protocol` 层。
- 单线性栈:本 slice 在 v2 impl 分支上作为**第一个** commit 单元。
- 精确 stage,不碰工作树其余 dirty 文件。

## 7. Acceptance

- [ ] `Rule.repr` / `render_repr` / `_validate_repr` 落地;rule.py 内无 `desc`/`render_desc` 残留(错误消息文本同步)
- [ ] `evaluate_result.py:952` 调用点更新为 `render_repr`/`.repr`
- [ ] 4 测试文件迁移到 `repr=`/`render_repr`,全绿
- [ ] `rule_expr_inspect.desc_template` 来源已核(源自 rule.desc 则更新;否则记录为独立、不动)
- [ ] `content_digest` 测试不变(无 digest churn)
- [ ] 全量相关 cohort(rule / evaluate_result / ruleexpr_inspect / sdk dsl)green
- [ ] 受影响 docs:`application/protocol/docs/README.md` 如述及 desc 则同步(impl 时确认)

## 8. Implementation Plan

1. `rule.py`:rename field `desc→repr`、method `render_desc→render_repr`、`_validate_desc→_validate_repr`、regex 名(可选)、`__post_init__` 引用、错误消息文本。
2. `evaluate_result.py:952`:`render_desc`→`render_repr`,`.desc`→`.repr`。
3. 4 测试文件:`desc=`→`repr=`,`render_desc`→`render_repr`。
4. 核 `rule_expr_inspect.desc_template` 来源;按 §4 处理。
5. 运行 cohort + content_digest 测试;Step 4.7/4.8 报告。

## 9. Docs To Update

- `src/factgraph/application/protocol/docs/README.md`(若述及 `Rule.desc`/`render_desc`,改 repr)。

## 10. Outcome / Deviations

**落地**:impl 分支 `v0.2.0-impl-explain-layer-v2-2026-06-09 @ 2c8f8c71`(基于 design HEAD `e662b54c`,单线性栈)。`master` 未动,未 push。

**结果**:`Rule.repr` / `render_repr` / `_validate_repr` 落地;`evaluate_result.py`(carry-over `repr=head.repr` + `render_repr` + metadata key `repr_template`)、`rule_expr_inspect`、`sdk/dsl/application_rule.py(repr=)` 全同步;4 测试 + 4 docs 同步。

**Gate(我独立验证)**:src 全树 desc/render_desc 残留 0;`content_digest` 不受 repr 影响断言已补并通过(`test_rule.py:137` + `:239`);S0 cohort **86 tests OK**(worktree 独立重跑);commit 12 文件全属 S0 范围,无 memory/无关 dirty 混入。

**与蓝图的偏差(均良性)**:
- §4 "待核" 解决:`rule_expr_inspect.desc_template` **确认源自 `Rule.desc`**(非独立),已随之改 `repr_template`。
- Codex 多抓一处 preflight 漏列的 caller:`sdk/dsl/application_rule.py` `build_application_rule(..., repr=...)`。
- metadata key 由 desc 系改为 `repr_template`(rename 的自然结果,无行为变化)。
- 决策 hard-rename(无 alias)按 §5 执行。

**归档**:暂留 active/,随程序里程碑批量归档(减少 per-slice churn)。
