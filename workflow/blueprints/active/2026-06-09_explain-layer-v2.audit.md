# Audit Log: Explain + EvaluateResult Layer — v2 Program

Paired with [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md).

---

## A. Preflight basis (v1 forensic audit, 2026-06-09)

v2 的预审输入是对**已弃用 v1** 的逐项审计(本会话完成,实读各 impl 分支 tip,非蓝图 ✅ 标记)。结论已固化进 program 蓝图 §1/§5,要点:

1. **分支拓扑(实测)**:8 个 impl 分支 = 3 个互不集成的簇:
   - 簇A(S0/S1/S2)fork 自 monorepo lineage(`c9ba32f8`,base `30e4488c`)。
   - 簇B(Certainty)+ 簇C(S3–S6)fork 自 release 投影面 `ed054fd0`。
   - `merge-tree` 实测:A↔C = 8 内容冲突 + ~15 modify/delete(基线不兼容,不可 forward-port)。
2. **prober 健全性 bug(实跑复现)**:`probe_native([("pred","p",["$x"]),("gt","$x",1)], {}, {"p":[(1,),(2,)]})` → `fails`,而 `{"p":[(2,)]}` → `holds`。加真事实翻转结论(单调性违反)。根因:`_primary_env` 取字典序最小 witness,不回溯。
3. **prober 结构降级(实跑)**:每分支仅 1 个 `role="body"` 合成 rule(`occurrence_alias="branch:N"`),无 head rule,`joins=()`,join 退化为 `eq` compare-atom(渲染成 "NYC is NYC")。
4. **dispatch(实读 S6 tip)**:passed 仅 problog/pyreason 走 adapter;native/souffle passed → `_build_minimal_passed_evidence_graph`(head-only)。prober 仅接 `closed_head_false` 失败路径(`sdk/store.py:_manual_explain_probe_evidence`)。souffle converter 存在但 dispatch 无 souffle 分支。
5. **Certainty / Rule.repr / schema DSL / render_entity_repr**:仅存在于各自(已弃用)簇,从未在同一分支共存。

详细 SHA 与复现见 `workflow/memory/project_explain_layer_v2_baseline.md`。

## B. Seed (854d03b9) shipped-vs-design 状态

| 维度 | 种子现状 | v2 动作 |
|---|---|---|
| `EvaluateRow` | `raw_kind/bound`(无 certainty) | Certainty slice 替换 |
| `Rule` | `desc/render_desc`(无 repr) | S0 改名 |
| `application/explain/` | 仅 docs/README,无 prober | S3 新建 |
| schema DSL repr | 无 | S1/S2 新增 |
| flat-DAG EvidenceNode/Edge | 已无(纯净) | 直接建 paths 模型 |
| eval-result-flatten α–η / query-style | 已在 | 复用,不重做 |

种子对 explain 碎片纯净,是正确白板。

## C. v2 locked decisions(纳入蓝图,slice 不再重议)

- **G1**:prober atom 判定 = 存在量化("任一 witness 成立 ⇒ Holds"),需 witness 回溯。INV-prober-soundness。
- **G2**:EvidenceTree 必含 `role="head"` 结论 rule + body rules(真 occurrence_alias)+ `EvidenceJoin`。
- **G3**:passed + failed 双路径都走 prober(passed 不得只给占位)。
- **G4**:native/souffle/problog/pyreason 四引擎 dispatch 全接。
- **G5**:Certainty 三路映射(boolean/probabilistic/possibilistic)。
- **G6**:prober assembly 实调 `render_entity_repr`(两遍渲染);结论用 `render_repr`。
- **G7**:单条线性栈 + 每 slice 内容矩阵集成闸。
- **INV-baseline-monorepo**:绝不在 release 投影面做实现(v1 碎片化根因)。
- 沿用 design-point 已锁:R1–R7、Q-D(arity opt-in)、paths 模型、EvidenceRef 不复活。

## D. Slice-level lock points & open items

### S3 prober — Codex 实现层锁点(2026-06-09,升格为 S3 **acceptance**,非 implementation note)

Codex 提出并锁定,S3 子蓝图必须把以下写成 acceptance(红/绿覆盖):

1. **G1 witness 回溯(候选 env 集语义)**:prober 不维护单一 env,而维护一组 candidate env/state。每个 atom 对所有 incoming env 求值,收集所有可继续的 output env。**只要某个 witness 成立,atom verdict = `Holds`**;不得因首个 witness failed 就判 `Fails`。
   - **Acceptance(必须红/绿)**:monotonic witness test —— `p($x) & $x>1` 在 `p=[(2,)]` 与 `p=[(1,),(2,)]` 下都判 `holds`(加真事实不翻转)。
2. **G2 结构保真(从 lowering metadata 重建)**:prober 输入保留 lowering plan / occurrence metadata,而非只拿 DNF flat atoms。`EvidenceRule(role="head")` + body rules + `occurrence_alias` + join 信息从 rule AST/lowering metadata + env binding provenance 重建。
   - **Acceptance(必须断言)**:graph shape test —— `role="head"` 存在、body 为真实 occurrence(非 `branch:N` 合成)、有 join 时 `EvidenceJoin` 非空。

### 其余 slice open items

- S0:hard-rename vs deprecated alias 决策(见 S0 子蓝图;倾向 hard-rename,匹配 v1 实证 + pre-1.0);`rule_expr_inspect.desc_template` 是否源自 `rule.desc` 待核(疑独立概念)。
- S3:witness 回溯枚举策略(全枚举 vs 惰性)与复杂度上界;`_normalize_where` 是否在 lowering 前即可取 occurrence/join 结构,或需从 `occurrence_map/join_materializations` 重建。
- S6:adapter 转换失败回退策略 —— v1 是 Option B minimal 回退;v2 因 passed 也走 prober(G3),回退目标改为 **native prober 树**而非 head-only 占位。
- Q-A(design §9 未锁):`ClaimKind`/`fact_triple` 在 query-style 下是否调整 —— Certainty slice 前重新评估。

## E. Deviations from v1

记录 v2 执行中相对本蓝图的偏差(slice 进行中填写)。
