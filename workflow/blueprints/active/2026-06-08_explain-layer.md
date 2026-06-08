# Task Blueprint: Explain + EvaluateResult Layer — Program Blueprint

- Status: draft
- Created: 2026-06-08
- Last Updated: 2026-06-08
- Related Modules:
  - `src/factgraph/application/protocol/` (EvaluateResult / EvaluateRow / Claim / EvidenceRef / Explanation)
  - `src/factgraph/application/protocol/rule.py` (Rule.desc → Rule.repr)
  - `src/factgraph/application/explain/` (新建 — prober 主体)
  - `src/factgraph/core/store/_evaluate.py` (query-style head decoupling)
  - `src/factgraph/core/schema/` (Field/Identity repr DSL)
  - `src/factgraph/sdk/store.py` (SDK re-exports)
  - `src/factgraph/audit/evidence_graph.py` (旧 nodes/edges 迁移)
- Related Docs:
  - [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)
  - [explanation-completion-roadmap.zh.md](../../design/design-points/active/explanation-completion-roadmap.zh.md)
- Audit Log:
  - [2026-06-08_explain-layer.audit.md](./2026-06-08_explain-layer.audit.md)

---

## 1. Problem

当前 `explain()` 路径只能产出"获胜单分支快照":
- OR 失败分支零痕迹;join 失败无 mismatch 定位;成功路径只记获胜线。
- 现有 `EvidenceGraph` body 是 flat nodes/edges DAG,丢失结构层级,无法呈现 per-atom 三态(Holds/Fails/NotReached)。
- `EvaluateRow` 携带 `Claim`/`EvidenceRef` wrapper,字段冗余且 Datalog-style predicate 绑定过紧,无法支持 query-style `rule.id` 自由命名。
- repr 层(Rule.desc / Field 无 repr / Meta 无 repr)分散不统一,无法支持 atom-level 自然语言渲染。

## 2. Goals

1. 新建穷尽逐条件探查器(`application/explain/`),覆盖 native 路径全部 OR branch + AND atom 三态。
2. 将 `EvidenceGraph` body 换芯为 `paths: tuple[EvidenceTree | EvidenceTimeline, ...]` 层级结构。
3. 扁平化 `EvaluateRow`(删 Claim/EvidenceRef wrapper),迁移至 `Certainty` 统一不确定度载体。
4. 引入 `Rule.repr`(从 `Rule.desc` 改名)+ Schema DSL `Field(repr=)/Identity(repr=)/Meta.repr`。
5. 支持 query-style `rule.id` 自由命名(free-form head → skip arity check;matched schema predicate → 保持 reject)。

## 3. Non-goals

**本 program blueprint 不承诺实施内容**,只锁定 slice program 和设计边界。具体 non-goals 按子 slice 拆分:

- 旧 `nodes/edges/root_node_id/support_kind` flat DAG surface 已由 S3 完全替换；`support_kind` 仍可作为 candidate/support protocol metadata 存在。
- 不实施 Souffle / ProbLog / PyReason rich prober 填充(S6,后续子 slice)。
- 不实施 `Why-not / D5` counterfactual(路线图 Tier S,以本 prober 为前提但不在本 program 内)。
- 不开 `fg.diagnose` SDK shell(D1,prober 稳定后)。
- 不修改 `fg.audit`(与 ledger Claim 直接绑定,0 影响)。
- 不修改 PyReason grounding parser 实现细节(R5 已决形态,parser 细节留实施阶段)。
- 不引入 `Explanation.narrate()` prose mode(R4,future slice)。

## 4. Current Context

- 当前实现入口:
  - `src/factgraph/application/protocol/evaluate_result.py:86-116`(Claim/EvidenceRef 定义)
  - `src/factgraph/application/protocol/evaluate_result.py:119-157`(EvaluateRow + D17 invariant)
  - `src/factgraph/application/protocol/evaluate_result.py:162-256`(EvaluateResult + 13 fields)
  - `src/factgraph/application/protocol/rule.py`(`Rule.desc`/`render_desc`)
  - `src/factgraph/core/store/_evaluate.py:148-157`(arity check raises)
  - `src/factgraph/audit/evidence_graph.py`(旧 NodeKind/EdgeKind/nodes/edges)
- 当前已知约束:
  - `master` @ `562c74195df43e933bed92a3ff25de94dd8ce666` — sacred,不可动
  - shipped tests 中约 30-50 处 `row.claim.*`/`row.evidence_ref.*`/`result.expr_digest` access path 需更新
  - `Rule.desc`/`render_desc` 已在公开 API;改名需 deprecated alias 过渡一个 minor cycle
  - `EvidenceGraph` nodes/edges 被 adapters/audit/`walk_evidence`/round events/大量测试引用
- 当前相关历史蓝图:
  - 无直接前驱(本 program 是新起点);设计来源见 [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md)

## 5. Proposed Shape

### Slice Program(执行顺序)

**§10.0 DTO 前置切片 — 状态校正（2026-06-08 source-read）**

> 2026-06-08 source-read 发现 §10.0 所有主要 slice 均已在此 blueprint 之前的历史实施中落地。
> 无需重开 α/β/γ/ζ/δ 子 blueprint。剩余工作仅为两个小型 cleanup items（见下）。

| Slice | 描述 | 当前状态 |
|---|---|---|
| α | Claim/EvidenceRef 冗余字段删除 | ✅ pre-blueprint 已落地（wrapper class 不存在） |
| β | ResultFingerprint sub-object 折叠 | ✅ pre-blueprint 已落地（`EvaluateResult.fingerprint: ResultFingerprint`）；`expr_digest` deprecated property cleanup 仍 pending → **Cleanup-β** |
| γ | Claim/EvidenceRef wrapper 撤销 + 字段平铺 | ✅ pre-blueprint 已落地（`EvaluateRow` 有 flat fields） |
| ζ | bindings 形態簡化 {port_name: term} | ✅ pre-blueprint 已落地（`_bindings_from_candidate` 已产出 `{port_name: term}`） |
| δ | query-style head decoupling | ✅ pre-blueprint 已落地（`_evaluate.py` 已实现 Option A：schema_pred is None → query-style；arity mismatch → reject） |

**真实遗留 DTO cleanup（各可作 tiny slice 或合并）**:

```
Cleanup-β   EvaluateResult.expr_digest deprecated property 删除 — tiny slice
Certainty   EvaluateRow.raw_kind + bound → Certainty 统一 — ✅ 已落地 @ 26671525；archived @ c7502913
```

**§10.1 Explain-layer 切片**(各自独立子 blueprint):

```
S0  Rule.desc → Rule.repr rename — ✅ 已落地 @ eb79f1c5 (2026-06-08)
S1  Schema DSL: Field(repr=)/Identity(repr=)/Meta.repr — ✅ 已落地 @ 6090eb05 (2026-06-08)
S2  Schema IR + render_entity_repr 纯函数 — ✅ 已落地 @ f13841b1 (2026-06-08)
S3  Prober 主体: application/explain/ + ProbeEnv + EvidenceTree 装配 — ✅ 已落地 @ 69593d36；S7 已并入 S3（Q-S3-A: 完全替换）
S4  渲染集成: repr_text 烘焙 + 渲染器默认表 — ✅ 已落地 @ 83be07b9
S5  native 路径接通: Explanation.evidence non-None iff passed/failed — ✅ 已落地 @ 9ba5f526
S6  adapters 迁移: souffle/problog/pyreason rich explain — 独立子 blueprint(依赖 S5)
S7  ~~旧 nodes/edges/root_node_id/support_kind 字段删除~~ — **已并入 S3 并随 S3 落地**
```

**推荐下一个 implementable slice**: `S6`（souffle/problog/pyreason rich explain 迁移，依赖 S5）。

### Program-level Questions — 状态校正

| ID | 原影响 slice | 问题 | 校正后状态 |
|---|---|---|---|
| Q-A | α/γ | `RowKind`/`ClaimKind` 在 query-style 下调整 | ⚠️ 仍 open：`ClaimKind` 含 `fact_triple`；query-style 路径已落地但 kind 未调整；影响 Certainty slice 前重新评估 |
| Q-B | δ | `:exists` auto-prepend 在 query-style 下行为 | ✅ 已随 δ 落地解决（free-form head 不走 schema 路径） |
| Q-C | α/β/γ/ζ | deprecated alias 保留多长；`expr_digest` fallback | 部分 resolved：alpha 无 alias（S0 实证）；`expr_digest` deprecated property cleanup = Cleanup-β |

### 设计来源

所有子 slice 的设计权威来源为 [`explain-layer-complete-design.zh.md`](../../design/design-points/active/explain-layer-complete-design.zh.md)。

## 6. Boundaries And Invariants

- **INV-6 application-first**: 全部改动在 `factgraph.application.protocol` + `factgraph.sdk` + `application/explain/`;无 SDK 反向依赖,无 substrate 上移。
- **Sacred branches**: `master`/`v0.1-oss-prep` 不可动。每个子 slice 在 `v0.2.0-impl-<slice-slug>-<date>` 分支上实施。
- **Unrelated dirty files**: 当前 working tree 有 unrelated dirty/untracked 文件,所有子 slice 实施中必须精确 stage,不得 `git add .`。
- **Alpha rename 原则**: 不保留旧名 alias（S0 已实证）；`result.expr_digest` deprecated property 由 Cleanup-β slice 清理。
- **Certainty 三路映射**: native→`Certainty(1,1,"boolean")`;problog→`Certainty(p,p,"probabilistic")`;pyreason→`Certainty(l,u,"possibilistic")`。Certainty slice acceptance 必须验证三路。
- **Q-D 已决(Option A)、δ 已落地**: matched schema predicate 端口数不符 → reject;free-form head → query-style。`_evaluate.py` 已实现。

## 7. Acceptance(Program Level)

- [ ] 设计文档 `explain-layer-complete-design.zh.md` 已 stage/commit 到 blueprint 分支
- [ ] 归档 design-points(evidence-proof-model、entity-repr、evaluate-result、rejected-alternatives)已 stage
- [ ] Slice program(§10.0 α/β/γ/ζ/δ + §10.1 S0-S7)已在 blueprint 中记录并有子 slice 顺序
- [ ] Program-level open questions(Q-A/B/C)已记录,不阻塞 S0 启动
- [ ] 所有子 slice 完成后:旧 nodes/edges 已删除,EvidenceGraph 全路径走新 paths 结构

## 8. Implementation Plan

1. **[当前 commit]** Stage 设计文档 + 归档 design-points + blueprint pair → blueprint branch 第一个 commit
2. **[S0 子 blueprint]** `Rule.desc → Rule.repr` alias migration — 最先启动,无依赖
3. **[α 子 blueprint]** Claim/EvidenceRef 冗余字段删除(Q-C 锁定后)
4. **[β 子 blueprint]** ResultFingerprint sub-object 折叠
5. **[γ 子 blueprint]** wrapper 撤销 + 字段平铺(依赖 α/β;Q-A/Q-C 锁定后)
6. **[ζ 子 blueprint]** bindings 形态简化
7. **[S1-S2 子 blueprint]** Schema DSL + IR
8. **[δ 子 blueprint]** query-style head decoupling(Q-B 锁定后)
9. **[S3-S5 子 blueprint]** Prober 主体 + 渲染 + native 路径接通(依赖 γ/ζ + S1-S2；S3 已落地)
10. **[S6 子 blueprint]** adapters 迁移
11. **[S7]** 旧字段删除已并入 S3

## 9. Docs To Update

- `src/factgraph/application/protocol/docs/README.md` — EvaluateRow/Explanation 结构变更
- `src/factgraph/application/explain/docs/README.md` — 新模块 docs(S3 时建)
- `src/factgraph/core/schema/docs/README.md` — repr DSL 新增(S1 时更新)
- `docs/quickstart/evaluate_and_evidence.md` — souffle 漏列 fix + 新 explain API

## 10. Outcome / Deviations

任务完成后填写。
