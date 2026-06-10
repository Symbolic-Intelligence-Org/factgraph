# Audit Log: Explain Layer — Conformance Rework Program

Paired with [2026-06-10_explain-conformance-rework.md](./2026-06-10_explain-conformance-rework.md).

---

## A. Audit Provenance (2026-06-10)

- 方法:多 agent conformance 审计 workflow,run `wf_a4091c33-f11`(52 agents,3 phase:Detect 11 区域 → Verify 每发现独立怀疑复验 → Synthesize 去重)。
- 触发:demo 连出 Bug 1–6 后用户质疑整体性;Claude 判断不能保证为最后一批,改穷尽审计。
- 规模:40 候选 → 32 通过怀疑复验 → 去重 **14 确认**;0 干净区域。
- 复验默认 `is_real_defect=false`,亲自最小复现,过滤构造错误/预期行为类假阳性(防 Probe C/D 那类误报)。
- 全部 11 区域(repr 占位符 / atom 类型 / 锚定×结构 / verdict×未绑定 / cardinality / closed-head / souffle / problog / pyreason / certainty+DTO / 不变式+API)均非干净。
- 完整结构化输出:workflow task `w2d37ymyb` result(每条含源码行号 + 真实 probe 证据)。

## B. Locked Decisions(2026-06-10,Claude 简报 + Codex 确认)

1. **结构**:program 父蓝图 + Batch 子蓝图;父记 14 缺陷 / 3 根因 / 测试盲区 / 批次矩阵;每 batch 单独 scoped + gate。
2. **批次顺序**:`A → E/D → B → C → final`(风险优先 —— 正确性/崩溃 A/E/D 不排在呈现 B/C 之后)。B 在 C 前(C 依赖统一 value renderer)。E 可并行准备。
3. **测试电池**:逐 batch 增量(Batch A 起建 native conformance battery 文件,每 batch 先加本缺陷红/绿测试再修)+ 最后短收口 slice(统一命名 / 文档 / full matrix)。**不**先做独立全测试 slice(多数测试需 batch 内 helper/fixture)。
4. **projection head 防御**:**不**在 Batch A reject。lowering 一等支持 `RuleExprHeadBinding.kind=="projection"` + head port link materialization;Batch A 只修锚定,缩减支持面须另起 policy/design slice。
5. **Batch A 范围下限**:不止修当前 occurrence source-var 映射,须覆盖三类 head 变量来源(inline / projection·external head vars / branch-specific source aliases),从 `RuleExprLoweringPlan` 结构推导。
6. **防回归**:Batch A 测试须非 mock 端到端 `.evaluate().row.explain()`,覆盖 inline / projection / external head + OR branch + join/multi-occurrence + 多行各自锚定。

## C. Defect Inventory(14 确认,源码定位)

**新(Bug 7–12)**
- Bug 7(正确性,repr)`schema_runtime.py:291-299` `render_entity_repr` 顺序 `str.replace` + `_identity_value_text:310` 裸 str → 前缀碰撞(`%org` 改写 `%org_unit`,声明序依赖)+ 值注入(字段值含 `%其他占位符`)。修:单遍替换。
- Bug 8(呈现)`prober.py:385-391` `_term_display` else→`str(value)`;被 `%FLD`(:311)、`_repr_compare`(361-373)共用 → float64 hex / idref 裸串 / CmpAtom entity-ref。标签恢复只在 `_entity_repr_for_fact`(326-354)。**并入 Bug 3**。
- Bug 9(呈现)`entity_view._recover_identity_from_predicates ~327` 取裸 hex + `schema_runtime._normalize_identity_value:479-489` 原样返回 → float64 identity 标签显裸 hex(直接调 `render_entity_repr` 用 native float 却正常,掩盖)。
- Bug 10(正确性)`store.py:4100-4117` projection head ports → `$__projection_*` 合成 var 不在 `exec_by_source` → 空 seed → `probe_native` 无锚定枚举第一个实体渲染给每行(可单路径混两实体)。lowering `rule_expr_lowering.py:80` 一等支持 projection。**同 Bug 4 根**。
- Bug 11(正确性)`prober.py:134-173` `_probe_atom` NotReached(:172)/Fails(:173)返回空 `()` env 元组前传且不 re-seed → 下游 atom 默认 Fails(成立也判 Fails),tree 状态 not_reached→fails。违 `explain/docs/README.md:47-48,73`。
- Bug 12(崩溃)`_support_capture.py:337-341` `_eq_atom_satisfies` 用裸 `_resolve`(`where_eval.py:744`)非 aggregate-aware `_resolve_eval_term`(`where_eval.py:752-766`);`_atom_satisfies:263-296` 无 aggregate 分支 → 5 种 kind 在 `_support_capture.py:167` 崩,evaluate 内,explain 到不了。

**复确认(Bug 3–6)**
- Bug 3 → 并入 Bug 8(self-ref `User.manager:User` + cross-type `Emp.dept:Dept` 两 schema 复现)。
- Bug 4(正确性)`rule_expr_lowering.py:775,871,782` 把 head var 重映射为 `$__head__*` 并 inline head 合取谓词;`store.py:4104-4117` 不 seed → 自由 re-derive。新表现:holding tree 直接显错实体标签 + 重复 atom(`prober._alias_for_atom:420-426` 对 `$__head__*` 返回 None → fallback_alias)。
- Bug 5(呈现)`prober.py:389-390` None BoundVar 返回 `term.name`;`$head__*` 在 failed_upstream 下未绑定 → 裸名。
- Bug 6(呈现)`prober.py:265-277` `kind=='not'` 落 generic else 包成 `Const(list)`;`_repr_builtin:380-381` `str(list)`;`negated` 留 False。souffle 契约 `test_souffle_evidence_graph.py:64-70` 为正确范例。

## D. Systemic Patterns(synthesis)

1. 锚定 seed 模型不覆盖完整 lowering 结构(Bug 10 + 4)—— 单一最高影响。
2. repr 值渲染逐 case 而无统一渲染函数(Bug 8/3、9、7、5/6 标签)。
3. `render_entity_repr` 不安全顺序替换(Bug 7,标签组装内损坏,异于漏解码)。
4. 存储标量形式 recovery 路径漏解码(Bug 9 + Bug 8 float 半)。
5. eval 与 support-capture resolver 不对称(Bug 12)。
6. verdict 把"上游清空 env"与"本 atom Fails"混同(Bug 11,加重 Bug 5)。
7. **evaluate→explain seam 普遍测试盲区** —— 几乎每个缺陷都对应未测路径;souffle 有忠实度测试故对,native prober 无故错。

## E. Open Items for Per-Batch Sub-Blueprints

- **Batch A**:seed builder 从 plan 结构推导三类 head var 的精确算法(`_head_var_names` 复用 vs 暴露);projection/external head 端到端锚定测试 fixture。
- **Batch E**:`_atom_satisfies` aggregate 分支形态;view_facts/witness 如何 thread 进 support-capture resolver;5 kind 端到端测试。
- **Batch D**:下游 atom 选 re-evaluate(按行锚定 seed 独立判真)还是标 NotReached(skip);tree 状态不再误翻 fails。
- **Batch B**:统一 value renderer 的归处(`_term_display` 内联 vs 提共享 helper);float64 解码点(`tup_v1` 规范形 + epoch-nanos time 是否同补);`render_entity_repr` 单遍替换实现(regex sub vs mask)。
- **Batch C**:`_atom_form` not 分支递归渲染 inner atoms;`negated=True`;对齐 souffle 输出风格。
- **final**:测试电池命名统一 + module docs + full matrix 跑。

## F. Per-Batch Gate Records

逐 batch gate-pass 后追加(impl commit / 测试数 / 边界 / 独立验证 / 裁决)。

- **Batch A — native row seed model**: PASS.
  - Impl commit: `a31892ca`.
  - Closed defects: Bug 10 projection-head row anchoring and Bug 4
    external/projection head seed leakage.
  - Boundary: lowering owns `probe_seed_vars_by_head_port(...)`; `store.py`
    is a thin consumer; `prober.py` / DTO / adapter paths untouched.
  - Tests: Codex focused `74 OK`; Codex broader `207 OK`; reviewer focused
    `74 OK`; reviewer broader `212 OK`; demo coherent.
  - Independent reviewer probes confirmed projection, external, OR, and join
    multi-entity rows have zero cross-entity leakage and Holds atoms have no
    internal `$` variables.
  - Carry-forward: existing Bug 5 internal `$` on failed OR branches moves to
    Batch B with `_term_display` / value-rendering work.
- **Batch E — support-capture aggregate resolver**: PASS.
  - Impl commit: `1a23ae87`.
  - Closed defect: Bug 12 aggregate support-capture crash.
  - Boundary: only `_support_capture.py` plus aggregate conformance tests
    changed; prober / DTO / adapter / explain rendering paths untouched.
  - Tests: Codex focused `67 OK`; Codex broader `293 OK`; reviewer aggregate
    subset `52 OK`; reviewer broader subset `218 OK`.
  - Correctness construction: `_resolve_eval_term(...)` falls back to
    `_resolve(...)` for non-aggregate terms, while aggregate terms use
    evaluation's own `_resolve_aggregate_term_for_env(...)`.
  - Independent reviewer probes validated `count`, `sum`, `min`, `max`, and
    `mean`, including fractional mean handling and unchanged mean/int-comparison
    rejection.
