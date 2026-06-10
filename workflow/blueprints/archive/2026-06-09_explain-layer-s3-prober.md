# Task Blueprint: S3 — exhaustive per-condition prober + evidence_tree types

- Status: implemented
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Parent: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)
- Related Modules:
  - `src/factgraph/application/explain/evidence_tree.py`(**新建** paths-model 类型)
  - `src/factgraph/application/explain/prober.py`(**新建** `probe_native` + `ProbeEnv`)
  - `src/factgraph/application/explain/__init__.py`(**新建** re-export)
  - `src/factgraph/application/diagnose_runtime.py`(复用 `_extend_env_with_atom` / `_normalize_where`)
  - `src/factgraph/application/protocol/rule_expr_lowering.py`(消费 `RuleExprLoweringPlan` 结构)
  - `src/factgraph/application/protocol/certainty.py`(`EvidenceTree.certainty` 等 import Certainty)
- Related Docs:
  - Design spec §2-§8(prober 核心): [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
- Audit Log:
  - [2026-06-09_explain-layer-s3-prober.audit.md](./2026-06-09_explain-layer-s3-prober.audit.md)

---

## 1. Problem

design §2:解释 = 专门的穷尽逐条件探查器。S3 建 `application/explain/`:paths-model 类型(§3)+ `probe_native` 穷尽探查(§2/§4)。**这是 v1 出健全性 bug(单 witness 翻转)+ 结构降级(DNF 扁平/无 head/无 join)的地方** —— S3 必须修对(G1/G2)。

## 2. Goals

1. **新建 paths-model 类型**(`evidence_tree.py`,design §3):`EvidenceGraph` / `EvidenceTree` / `EvidenceRule` / `EvidenceAtom` / AtomForm(`Fact`/`Compare`/`Builtin`/`Aggregate`)/ Verdict(`Holds`/`Fails`/`NotReached`)/ `BoundVar`/`Const`/`Source`/`PortRef`/`EvidenceJoin`;`certainty` 字段 import 自 `protocol/certainty.py`。
2. **`probe_native`(G1 健全 witness 语义)**:维护 `candidate_envs: tuple[ProbeEnv,...]`;每个 bind-producing atom 对所有当前 env 展开收集 0..N next env;**atom verdict = 至少一个 next env 存在 ⇒ Holds**(非取首个 witness)。穷尽所有 branch + atom 三态。
3. **G2 结构保真**:消费 `RuleExprLoweringPlan` 的 `occurrence_map` + `RuleExprLoweringBranch.occurrence_aliases` + `RuleExprJoinMaterialization`(left/right occurrence)+ head binding → `EvidenceRule(role="head")` + body rules(真 `occurrence_alias`)+ `EvidenceJoin`(来自 join_materializations,非退化 eq atom)。
4. 复用 `diagnose_runtime._extend_env_with_atom` 做 env 展开。

## 3. Non-goals

- `repr_text` schema 烘焙(S4:prober assembly 调 render_entity_repr;S3 的 `repr_text` 可 None/最小)。
- `Explanation.evidence` 接通 / passed+failed 路径(S5)。
- adapters dispatch(S6)。
- 内联派生 / ruleref / 多原子 Not 富解释(v1 scope 外)。
- pyreason timeline(S6;S3 是 native tree)。

## 4. Current Context(preflight 已完成)

- **diagnose 求值器**:`diagnose_runtime` `_extend_env_with_atom`(:260)/ `_normalize_where`(DNF branches)/ `diagnose_derivation_binding`(:91)。
- **★G2 结构来源(已确认充足,无需新 carrier)**:`_lower_application_rule`/`_lower_rule_expr`(rule_expr_lowering.py:303/309)产 `RuleExprLoweringPlan`(:117),携带:
  - `occurrence_map: tuple[RuleExprOccurrenceBinding(alias,...)]`(:122/:63)
  - `RuleExprLoweringBranch(branch_id, occurrence_aliases)`(:99)
  - `RuleExprJoinMaterialization(branch_id, left_occurrence_alias, right_occurrence_alias)`(:141)—— join 关系
  - `RuleExprPortBinding(occurrence_alias, alias_local_execution_var)`(:45)、head binding(:83)
- **v1 失败根因**:v1 prober 只用 `plan.branches`/`body_ir`(DNF flat),无视上述结构 → 单 rule 合成 + joins=()。S3 消费结构即修。
- Certainty 已在 `protocol/certainty.py`(`Certainty`/`BOOLEAN_CERTAINTY`)。

## 5. Proposed Shape

### evidence_tree.py(design §3 类型)

frozen DTO 全套;`EvidenceGraph(graph_id, engine, layout_hint, subject_binding, paths, certainty, metadata)`;`EvidenceTree(tree_id, status, rules, joins, certainty)`;`EvidenceRule(occurrence_alias, rule_id, role, status, ports, atoms)`;`EvidenceAtom(form, verdict, atom_id, repr_text=None, negated, timestep)`;`Holds(certainty, support)`/`Fails(certainty)`/`NotReached(blocked_by)`;`certainty` 用 `protocol.certainty.Certainty`。

### probe_native(G1 + G2)

- **G1 candidate_envs**:`probe_native(plan, bindings, view_facts, schema_index=None) -> EvidenceProbeResult`。每 branch 起 `candidate_envs=(ProbeEnv.from_bindings(bindings),)`;每 bind-producing atom 对所有 env 调 `_extend_env_with_atom` 收集所有 next env;非空 ⇒ atom `Holds`(取所有存活 env 继续),空 ⇒ `Fails`;依赖变量未绑定 ⇒ `NotReached`。**穷尽,不取首 witness,不短路。**
- **G2 结构**:用 `occurrence_map` + branch `occurrence_aliases` 把 atoms 按 occurrence 分组成多个 body `EvidenceRule`(真 alias);head binding → `EvidenceRule(role="head")`;`RuleExprJoinMaterialization` → `EvidenceJoin(left, right, held)`(`PortRef`)。
- 三层 status 自底向上(atom→rule→tree)按 design §4。

## 6. Boundaries And Invariants

- **★INV-prober-soundness(G1)**:任一 atom,存在一个满足 witness 即 `Holds`;**绝不**因首个 witness fail 而误判。加真事实不得翻转结论(monotonicity)。
- **★INV-structure(G2)**:EvidenceTree 含 `role="head"` rule;body rules 用真实 `occurrence_alias`(非 `branch:N` 合成);join 表为 `EvidenceJoin`(非 eq atom 退化);`joins` 在有 join 时非空。
- **metadata 充足**:G2 从既有 `RuleExprLoweringPlan` 结构重建,**不新增 carrier**(preflight 已证);若实现中发现某结构缺失,**回蓝图补 carrier,不在 prober 里猜**(Codex #2)。
- `certainty` 类型来自 protocol(explain→protocol 依赖方向正确);native tree 用 `BOOLEAN_CERTAINTY`。
- INV-6;单线性栈(Certainty 之上)。

## 7. Acceptance

- [ ] evidence_tree.py 全套 frozen 类型(design §3);`certainty` import 自 protocol
- [ ] **★G1 monotonic witness test(红/绿必备)**:`p($x) & $x>1` 在 `p=[(2,)]` 与 `p=[(1,),(2,)]` 下都 `holds`(加真事实不翻转)
- [ ] **★G2 graph shape test(必断言)**:`role="head"` 存在;body 为真实 occurrence(非 `branch:N`);有 join 时 `EvidenceJoin` 非空(非 eq atom)
- [ ] 穷尽:多 OR branch → 多 EvidenceTree;失败分支也出现;atom 三态(Holds/Fails/NotReached)
- [ ] NotReached 仅由变量未绑定触发(前序 Fails 不触发后续 NotReached)
- [ ] `probe_native` 复用 `_extend_env_with_atom`;不短路
- [ ] 受影响 docs(explain 模块)同步

## 8. Implementation Plan

1. `evidence_tree.py`:design §3 全套类型 + 序列化(`evidence_graph_to_dict`/`from_dict`)+ `__init__` re-export。
2. `prober.py`:`ProbeEnv`(candidate set 友好)+ `probe_native`:G1 candidate_envs 展开 + 三态 + G2 从 `RuleExprLoweringPlan` 结构装配(head/body-occurrence/join)。
3. 复用 `_extend_env_with_atom`;form 提取(Fact/Compare/Builtin)。
4. 测试:G1 monotonic + G2 shape + 穷尽三态 + NotReached 语义;Step 4.7/4.8。

## 9. Docs To Update

- `src/factgraph/application/explain/docs/README.md`(prober + 类型 + G1 健全性语义)。

## 10. Outcome / Deviations

**落地**:impl `57c7c87e`(线性栈 `… → 3ad3cb24(S3蓝图) → 57c7c87e(S3 code)`);master 未动,未 push。

**结果**:
- 新建 `application/explain/`:`evidence_tree.py`(design §3 paths-model 全套)+ `prober.py`(`probe_native` + `ProbeEnv`)+ `__init__`。
- **G1 candidate_envs backtracking**:`_probe_atom` 对所有 env 展开 `_extend_env_with_atom`,收集全部 next_envs;deduped 非空 ⇒ Holds 且携全部存活前进(:154-156);空+blocked ⇒ NotReached;空 ⇒ Fails。穷尽不短路。
- **G2 结构**:从 `RuleExprLoweringPlan` 消费 —— `role="head"` rule(:207)+ body 按真实 occurrence_alias 分组(:173)+ `EvidenceJoin` 从 join materialization(:228,PortRef left/right occurrence)。
- 共享 `diagnose_runtime._extend_env_with_atom` 修正:cmp/ne 补传 `view_facts`(源头修 v1 当年的 `_fallback` 绕坑)。

**Gate(我独立验证)**:
- ★**G1 v1 翻转复现已修**:`test_monotonic_witness_backtracking` —— `p=[(2,)]` 和 `p=[(1,),(2,)]` **都 holds**(v1 后者会 fails);逻辑实读确认携全部存活 env,根除单 witness 提交。
- ★**G2 shape**:`test_structure_preserves...` —— head=`left_region`、body occurrence={left,right}(非 branch:N)、`EvidenceJoin` left/right occurrence(非 eq 退化)。
- NotReached 仅未绑定触发 + OR branch 穷尽(holds/fails)均有测试。
- diagnose 共享函数改动安全:diagnose cohort 通过。
- cohort 33 OK(独立,含 prober + diagnose + lowering)。

**metadata 充足验证**:G2 全程从既有 `RuleExprLoweringPlan`(occurrence_map + join_materializations + head binding)重建,**未加新 carrier**(Codex #2 gating 问题以"充足"收口)。

**Deviations / open(良性)**:`repr_text` S3 给 None(S4 烘焙);candidate_envs 用 `_dedupe_envs` 防爆炸;Aggregate form 类型存在即可。

**归档**:暂留 active/,随里程碑批量归档。
