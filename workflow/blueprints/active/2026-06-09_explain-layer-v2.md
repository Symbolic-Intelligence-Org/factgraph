# Task Blueprint: Explain + EvaluateResult Layer — v2 Program Blueprint (clean re-implementation)

- Status: draft
- Created: 2026-06-09
- Last Updated: 2026-06-09
- Related Modules:
  - `src/factgraph/application/protocol/` (EvaluateResult / EvaluateRow / Explanation / rule.py)
  - `src/factgraph/application/explain/` (prober + evidence_tree — to be built)
  - `src/factgraph/core/schema/` (Field/Identity/Meta repr DSL)
  - `src/factgraph/application/schema_runtime.py` (render_entity_repr)
  - `src/factgraph/adapters/{problog,pyreason,souffle}/provenance.py`
  - `src/factgraph/sdk/store.py`
- Related Docs:
  - Design spec (authoritative): [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
  - Roadmap: [explanation-completion-roadmap.zh.md](../../design/design-points/active/explanation-completion-roadmap.zh.md)
  - v1 archived parent (superseded): [2026-06-08_explain-layer.md](../archive/2026-06-08_explain-layer.md)
  - v1 state / abandonment record: `workflow/memory/project_explain_layer_v2_baseline.md`
- Audit Log:
  - [2026-06-09_explain-layer-v2.audit.md](./2026-06-09_explain-layer-v2.audit.md)

---

## 1. Problem

2026-06-08 的 explain-layer 实现已**弃用**(2026-06-09 清理)。根因(状态层面,非归因):

1. **碎片化跨两条不兼容基线**:S0/S1/S2 建在 monorepo `30e4488c`;Certainty + S3–S6 建在**剥离的发布投影面** `ed054fd0`。从未集成;无任何单一分支持有完整特性;forward-port 因基线不兼容而不可行。
2. **prober 有健全性 bug**:单 witness 提交、不回溯 → 往视图加一条为真的事实可把存在量化推导从 holds 翻成 fails(单调性违反,已复现)。
3. **prober 结构降级**:产 DNF 扁平输出,每分支仅一个合成 body rule,无 `role="head"`、`joins=()`(join 退化为 eq-atom),未实现设计 §3/§4 层级。
4. **prober 只接失败路径**:passed native/souffle 行只得 minimal head-only 占位,设计 §5.3 招牌"成功逐条件展开"从不产生;souffle rich dispatch 从未接线。
5. 缺**集成验证闸**:无任何一步检查"跨 slice 是否合体"。

v2 在干净 monorepo 种子 `854d03b9` 上,作为**单条线性栈**重新实现,并把上述缺陷作为显式纠正要求。

## 2. Goals

设计目标沿用 design-point(穷尽逐条件 prober + paths 模型 EvidenceGraph + 扁平 EvaluateRow/Certainty + repr DSL + query-style head)。v2 在此之上**强制**以下纠正项:

1. **G1 prober 健全性**:atom 求值采用"**任一 witness 成立 ⇒ atom Holds**"语义(witness 回溯 / 存在量化),根除单 witness 翻转 bug。加针对性测试:多 witness + 下游依赖时不得误报 fails;单调性测试(加真事实不改变 holds 结论)。
2. **G2 prober 结构保真**:产出设计 §3/§4 层级 —— `role="head"` 结论 rule + body rules 带真实 occurrence_alias + `EvidenceJoin`(join 不退化为 eq-atom)。
3. **G3 双路径接通**:passed **与** failed 路径都走 prober 全树;native/souffle passed 行不得只给 minimal 占位。
4. **G4 全引擎 dispatch**:native / souffle / problog / pyreason 四引擎 passed 行都接到对应富 evidence(souffle rich 必须接线,不留占位)。
5. **G5 Certainty 统一**:`EvaluateRow.raw_kind + bound` → `certainty: Certainty | None`,三路映射(native boolean / problog probabilistic / pyreason possibilistic)。
6. **G6 repr 全链路接通**:`Rule.desc → Rule.repr`(S0)+ schema DSL `Field(repr=)/Identity(repr=)/Meta.repr`(S1)+ `render_entity_repr` 纯函数(S2),且 **prober assembly 实际调用** render_entity_repr 做两遍渲染(§5.3),结论行用 `render_repr`。
7. **G7 单条线性栈 + 每步集成闸**:全部 slice 在**同一条 impl 分支**顺序叠加;每并入一片跑"内容矩阵"确认前序符号仍在 + 新接线生效。

## 3. Non-goals

- `narrate()` / prose 散文模式(R4):形态已决,v2 **不实施**(future slice)。
- D5 Why-not / counterfactual、D1 `fg.diagnose` SDK 薄壳、D6/D7 attribution、D15/D18 aggregate 扩展、D20 match witness:均独立设计链,不在 v2。
- v2 无内联派生(ruleref 禁;无递归/环/子图)—— 沿用 design §4。
- 多原子 `Not([..])` 富解释:v2 不做(单原子 `\+` 的 `negated` 仍支持)。
- 不动 release 投影面(见 §6);不动 sacred 分支。

## 4. Current Context

- **种子 / 基线**:`854d03b9` = `v0.2.0-blueprint-explain-layer-2026-06-08`(已 FF 到本地 `master`)。完整 monorepo,含全部 v0.2.0 基础(eval-result-flatten α–η、query-style-head、schema-digest-stability),含完整设计文档,**对 explain 碎片纯净**(无 prober / 无 `certainty` 字段 / `rule.py` 仍 `desc`)。
- **v2 工作分支**:`v0.2.0-blueprint-explain-layer-v2-2026-06-09`(本蓝图所在;doc-only)。impl 走配对 impl 分支(见 §6)。
- **当前 src 起点**:`EvaluateRow` 有 `raw_kind/bound`;`Rule` 有 `desc/render_desc`;无 `application/explain/prober.py`。
- **设计权威**:design-point 内容仍有效,v2 **不重开**其已锁决策(R1–R7、Q-D、三路 Certainty 映射等);v2 只补 v1 实现缺陷。
- **v1 教训记录**:`workflow/memory/project_explain_layer_v2_baseline.md`(分支 SHA、缺陷清单)。

## 5. Proposed Shape

### 单条线性栈(同一 impl 分支顺序叠加)

```
基线 854d03b9 (DTO flatten α–η + query-style 已在)
 └─ S0  Rule.desc → Rule.repr (+ render_repr)
     └─ S1  schema DSL: Field(repr=)/Identity(repr=)/Meta.repr + 占位符校验 + 默认 label
         └─ S2  schema IR repr 存储 + render_entity_repr 纯函数
             └─ Certainty  EvaluateRow.raw_kind/bound → certainty (三路映射)
                 └─ S3  prober 主体 (G1 健全 witness 语义 + G2 结构保真 head/body/join)
                     └─ S4  repr_text 烘焙 (prober 调 render_entity_repr 两遍渲染 + 默认表)
                         └─ S5  native 路径接通: passed+failed 都走 prober (G3); 不变式 evidence non-None iff passed/failed
                             └─ S6  adapters: problog/pyreason/souffle 四引擎 dispatch 全接 (G4)
```

§7/§8 详见各 slice。每个 slice 在**同一条 impl 分支**上叠加(非平行分支),每片结束跑 §6 集成闸。

### 关键纠正(对照 v1 缺陷)

| v1 缺陷 | v2 纠正要求 | 验收锚点 |
|---|---|---|
| 单 witness 翻转(健全性) | 任一 witness 成立 ⇒ Holds | 多 witness + 下游依赖测试;单调性测试 |
| DNF 扁平 / 无 head / 无 join | head rule + 真 occurrence_alias + EvidenceJoin | 结构断言测试(roles 含 head;joins 非空) |
| passed 仅占位 | passed+failed 都走 prober | passed native 行有完整 body atoms |
| souffle 未接 | 四引擎 dispatch 全接 | souffle passed 行有 rich evidence |
| raw_kind/bound | certainty 三路 | 三引擎 certainty kind 断言 |
| repr DSL 未接 prober | prober 调 render_entity_repr | atom repr_text 用 schema 措辞 |
| 碎片化 | 单线性栈 + 每步闸 | 内容矩阵每片通过 |

## 6. Boundaries And Invariants

- **INV-baseline-monorepo**:v2 全部工作在 **monorepo** 上(种子 854d03b9 / 本地 master)。**绝不**在 release 投影面(`feature/v0.2.0-factgraph-publish` / `ed054fd0`)上做实现。这是 v1 碎片化的直接根因,硬性禁止。
- **INV-single-stack**:全部 slice 在**一条** impl 分支顺序叠加,不开平行分支。配对 design(本分支,doc-only)+ impl(代码),per `feedback_design_impl_branch_isolation`。
- **INV-integration-gate**:每并入一 slice,跑"内容矩阵"闸 —— 确认前序 slice 符号仍存在 + 当前 slice 新接线生效(防止 v1 式"各自孤立"复发)。
- **INV-prober-soundness (G1)**:prober 对任一 atom,只要存在一个满足的 witness 即判 Holds;不得因提交到某个失败 witness 而误判。属健全性硬约束。
- **INV-6 application-first**:全部改动在 `application` + `sdk` 两层;无 SDK 反向依赖,无 substrate 上移。
- **Sacred**:`master`(本地已 FF,未 push)/ `v0.1-oss-prep` 不可推送/不可改写,除非显式 publish 决策。
- **不做**:narrate / Why-not / diagnose 薄壳 / 内联派生 / 多原子 Not 富解释。
- **兼容**:沿用 design-point 已锁决策;不重开 R1–R7 / Q-D。

## 7. Acceptance (Program Level)

- [ ] G1 prober 健全性:多 witness + 下游 + 单调性测试通过,无 holds→fails 翻转
- [ ] G2 结构保真:EvidenceTree 含 head rule + body rules(真 occurrence_alias)+ 非空 EvidenceJoin(有 join 时)
- [ ] G3 双路径:passed native 行产出完整逐条件 body(非占位);failed 行产出三态全展开
- [ ] G4 四引擎 dispatch:native/souffle/problog/pyreason passed 行各得对应富 evidence
- [ ] G5 Certainty 三路映射验证
- [ ] G6 repr 链路:prober 调 render_entity_repr;atom repr_text 用 schema 措辞;结论用 render_repr
- [ ] G7 单线性栈:所有 slice 在一条 impl 分支;每片内容矩阵闸通过
- [ ] 旧 nodes/edges flat-DAG 完全不复现;EvidenceGraph 全走 paths 模型
- [ ] 受影响 module docs 同步;`docs/README.md` 如有新入口已更新

## 8. Implementation Plan

> 每个 slice 一个可独立落地单元,在**同一条 impl 分支**顺序叠加。slice 启动前按 `feedback_preflight_code_audit_required` 做 shipped-vs-design 预审;按 `feedback_audit_to_archive_cadence` 走 draft→preflight→scoped→impl→闸→closure。

1. **S0** ✅ **implemented @ `2c8f8c71`**(2026-06-09)— `Rule.desc → Rule.repr` + `render_repr`,hard-rename;gate PASS(86 tests OK,content_digest 不变,0 残留)。子蓝图已 implemented。
2. **S1** ✅ **implemented @ `e6ff7940`**(2026-06-09)— schema DSL `Field/Identity/Meta repr` surface + 共享校验 helper(两路)；占位符矩阵按 §5.2 锁定;**repr 不入 IR / digest 不变**(gate PASS)。默认 label 归 S2。子蓝图已 implemented。
2b. **CLEANUP-description**(scoped,`<user>` 决定 2026-06-09)— 删除 schema entity/field/Meta `description`(repr 下位替代;preflight 实证零消费 / 0 测试 / 0 example;Rule/Inference description 不动)。排在 S2 前,使 S2 digest 排除只管 repr。子蓝图 `2026-06-09_explain-layer-cleanup-schema-description.md`。
3. **S2** schema IR repr 存储(**排除出 identity digest**,已锁 — repr 是纯呈现模板,不应使 schema identity 失效)+ `render_entity_repr` 纯函数 + §5.2 默认 label。description 已由 2b 删除,S2 digest 排除仅针对 repr。
4. **Certainty** `EvaluateRow.raw_kind+bound → certainty: Certainty|None`;三路映射;更新构造点 `_candidate_set_to_evaluate_row`。
5. **S3** prober 主体 `application/explain/`:ProbeEnv + 穷尽遍历 + **G1 健全 witness 语义** + **G2 head/body/join 结构** + EvidenceTree/Atom/Verdict 类型。
6. **S4** repr_text 烘焙进 prober assembly:**调 render_entity_repr**(G6)+ 渲染器默认表;INV-reprtext-fact-always。
7. **S5** native 路径接通:`Explanation.evidence non-None iff passed/failed`;**passed+failed 都走 prober**(G3);stale_row/row_not_in_result → unsupported。
8. **S6** adapters dispatch:problog/pyreason/souffle **四引擎全接**(G4);adapter graph → paths-model;转换失败的回退策略在 audit 里定。
9. **收口**:旧 flat-DAG 残留清零;module docs 同步;parent 填 §10 + 归档。

> S7(旧字段删除)按 v1 经验并入 S3(paths 模型直接替换)。

## 9. Docs To Update

- `src/factgraph/application/protocol/docs/README.md`(EvaluateResult/Explanation/dispatch)
- `src/factgraph/application/explain/docs/README.md`(prober + 类型 + 健全性语义)
- `src/factgraph/core/schema/docs/README.md`(repr DSL — v1 deferred,v2 补)
- `src/factgraph/audit/docs/02_evidence_graph.md`(paths 模型 thin re-export)
- `src/factgraph/application/docs/README.md` + `01_overview_en.md`(索引)
- `docs/quickstart/evaluate_and_evidence.md`(§5.1 结构章仍是旧 4-tier flat-DAG,v2 必须改写)

## 10. Outcome / Deviations

任务完成后填写。
