# Audit Log: S3 — exhaustive prober + evidence_tree

Paired with [2026-06-09_explain-layer-s3-prober.md](./2026-06-09_explain-layer-s3-prober.md).

---

## A. Preflight (2026-06-09)

- diagnose 求值器:`diagnose_runtime._extend_env_with_atom`(:260)/ `_normalize_where` / `diagnose_derivation_binding`(:91)—— 复用基础。
- `CompiledDerivationPlan`(protocol/derivation.py:35)= 执行 plan(body_ir flat + heads),**无** occurrence/join。
- `_lower_application_rule`/`_lower_rule_expr`(protocol/rule_expr_lowering.py:303/309)产 **`RuleExprLoweringPlan`** —— v1 prober 的真实输入。

## B. ★G2 gating 问题解决:metadata 充足,无需新 carrier

`RuleExprLoweringPlan`(:117)已携带 G2 所需全部结构:
- `occurrence_map: tuple[RuleExprOccurrenceBinding(alias)]`(:122/:63)
- `RuleExprLoweringBranch(branch_id, occurrence_aliases)`(:99)
- `RuleExprJoinMaterialization(branch_id, left_occurrence_alias, right_occurrence_alias)`(:141)
- `RuleExprPortBinding(occurrence_alias, alias_local_execution_var)`(:45)、head binding(:83)

→ **回答 Codex #2**:无需先补 metadata carrier;S3 直接消费上述结构重建 head/body-occurrence/join。
**v1 失败根因**:v1 prober 只用 `plan.branches`/`body_ir`(DNF flat),**丢弃**了这些结构 → 单合成 rule + joins=()。

(若实现中发现某具体结构不足,按 Codex #2:回蓝图补 carrier,不在 prober 里猜。)

## C. Codex S3 lock points(升格 acceptance,程序 audit §D + 本片 §7)

1. **G1 candidate_envs backtracking**:维护 `candidate_envs: tuple[ProbeEnv,...]`;每 bind-producing atom 对所有 env 展开;**≥1 next env ⇒ Holds**(非首 witness)。acceptance:monotonic witness test 红/绿(`p=[1,2]` 不翻转)。
2. **G2 structure from metadata**:不从 flat branch 反推;head 单独 `role="head"`,body 按 occurrence 分组,join 来自变量绑定关系(`RuleExprJoinMaterialization`),非退化 eq atom。acceptance:graph shape test 断言 head + 真 occurrence + EvidenceJoin 非空。

## D. Locked decisions

- 类型在 `application/explain/evidence_tree.py`;`certainty` import 自 `protocol/certainty.py`(explain→protocol 方向正确)。
- S3 scope = 结构 + 三态(G1/G2);`repr_text` schema 烘焙留 S4(S3 可 None/最小)。
- native tree;pyreason timeline 留 S6。

## E. Open items for Codex

- `EvidenceAtom.repr_text` 在 S3 给 None 还是最小 fallback(S4 正式烘焙)—— 你定。
- `Aggregate` form 在 S3 是否完整(v1 留 None repr);本片只需类型存在 + verdict。
- candidate_envs 去重/上界(避免 env 爆炸)—— 实现策略你定,记录复杂度。

## F. Gate result (Claude 独立验证 2026-06-09)

impl `57c7c87e`(parent = S3 蓝图 `3ad3cb24`,线性栈)。**PASS**:
- scope:6 文件(explain/__init__ + evidence_tree + prober + diagnose fix + docs + test);无 memory/无关混入。
- ★**G1 健全性(逻辑实读 + 实测)**:`_probe_atom`(prober.py:131-159)对所有 candidate env 展开,deduped 非空 ⇒ Holds + 携全部存活;`test_monotonic_witness_backtracking` 证 `p=[(2,)]` 与 `p=[(1,),(2,)]` 都 holds —— **v1 翻转 bug 根除**。
- ★**G2 结构**:`role="head"`(:207)+ body 真 occurrence 分组(:173)+ `EvidenceJoin` from materialization(:228);`test_structure_preserves...` 断言 head/{left,right}/join occurrence。
- diagnose 共享改动安全:`_extend_env_with_atom` cmp/ne 补 view_facts;diagnose cohort 通过。
- cohort 33 OK(独立)/ Codex 4 + 44。

裁决:**PASS**(核心 prober + v1 bug 修复确认)。

## G. metadata 充足以 G2(Codex #2 收口)

G2 全程从既有 `RuleExprLoweringPlan` 重建(occurrence_map / RuleExprJoinMaterialization / head binding);**未加新 carrier**。Codex #2 的 gating 问题以"metadata 充足"收口。

## H. Deviations(良性)

- `repr_text` S3 = None(S4 烘焙)。
- candidate_envs `_dedupe_envs` 防爆炸(我 open item 已被处理)。
- diagnose `_extend_env_with_atom` 源头修复,消除 v1 prober 的 `_fallback_extend_env_with_atom` 绕坑需求。
