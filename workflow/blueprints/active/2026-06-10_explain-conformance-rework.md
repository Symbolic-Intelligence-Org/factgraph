# Task Blueprint: Explain Layer — Conformance Rework Program (post-v2 structural fixes)

- Status: implementing
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: program (multi-batch structural rework; 子 batch 各自 scoped + gate)
- Predecessor: [2026-06-09_explain-layer-v2.md](./2026-06-09_explain-layer-v2.md)(v2 实现程序;本程序修其 conformance 缺陷)
- Related Modules:
  - `src/factgraph/sdk/store.py`(seed builder)
  - `src/factgraph/application/explain/prober.py`(repr 链 + verdict 级联)
  - `src/factgraph/application/schema_runtime.py`(`render_entity_repr` + float64 解码)
  - `src/factgraph/application/entity_view.py`(identity recovery)
  - `src/factgraph/core/store/_support_capture.py`(aggregate resolver)
- Audit Log:
  - [2026-06-10_explain-conformance-rework.audit.md](./2026-06-10_explain-conformance-rework.audit.md)

---

## 1. Problem

v2 explain 层在 demo 中连续暴露 Bug 1–6 后,用户质疑是否为整体性问题。一轮**多 agent conformance 审计**(52 agents / 11 区域矩阵 / 每发现独立怀疑复验,run `wf_a4091c33-f11`)穷尽特征矩阵,确认 **14 个缺陷、0 个干净区域**,收敛到 **3 个结构性根因 + 一个普遍 evaluate→explain 测试盲区**。结论:**需定向结构重做,不是继续点修。** v1 修复(Bug 1/2)正确,但整体忠实度面未被覆盖。

## 2. Goals

1. 关闭全部 14 个确认缺陷(6 新 Bug 7–12 + 4 复确认 Bug 3–6)。
2. 修复 3 个结构性根因(见 §5),而非逐症状打补丁。
3. 建立 **native prober 忠实度测试电池**(对标 souffle `test_souffle_evidence_graph.py` 的契约测试),关闭 evaluate→explain 测试盲区,防回归。
4. 每个 batch 单独 scoped + 独立 gate,单线性栈续叠。

## 3. Non-goals

- **不缩减支持面**:projection head 是 lowering 一等支持的 `RuleExprHeadBinding.kind=="projection"`,Batch A 只修锚定,**不在 bugfix 里 reject** projection head(若产品要禁,另起 policy/design slice)。
- 不改 EvaluateResult / EvidenceGraph DTO 契约、不改 adapter provenance 契约(repr 渲染除外)。
- 不改 SchemaIR digest 语义(repr 不入 digest 的既有不变式保持)。
- `master` / 发布分支不动(沿用发布分支不变式)。

## 4. Current Context(审计已完成)

- 审计 provenance:`wf_a4091c33-f11`(2026-06-10),40 候选 → 32 通过复验 → 去重 14 确认;1 崩溃 / 4 正确性 / 9 呈现质量。
- 缺陷清单(源码定位见 audit §C):
  - **Bug 7**(正确性)`schema_runtime.py:291-299` `render_entity_repr` 顺序 `str.replace` → 前缀碰撞 + 值注入。
  - **Bug 8**(呈现)`prober.py:385-391` `_term_display` 无值类型解析(float64 hex / idref 裸串 / CmpAtom entity-ref);并入 Bug 3。
  - **Bug 9**(呈现)`schema_runtime.py:479-489` `_normalize_identity_value` float64 分支原样返回(recovery 路径不解码)。
  - **Bug 10**(正确性)`store.py:4100-4117` projection head 的 `$__projection_*` 不在 seed → 空 seed → 解释不锚定。
  - **Bug 11**(正确性)`prober.py:134-173` 上游非 Holds → 下游空 env 级联 → 成立 atom 错标 Fails(违 `explain/docs/README.md:47-48,73`)。
  - **Bug 12**(崩溃)`_support_capture.py:337-341` 用非 aggregate-aware resolver → native aggregate 崩。
  - **Bug 3→8** / **Bug 4**(`store.py:4104-4117` `$__head__*` 不 seed;holding tree 显错实体 + 重复 atom `prober.py:420-426`)/ **Bug 5**(`prober.py:389-390` None BoundVar 返回 term.name)/ **Bug 6**(`prober.py:265-277` not 落 generic else)。
- 测试盲区:除 str.replace 外每个缺陷都对应一条没测的 evaluate→explain 路径;souffle 有忠实度测试故正确,native prober 无故失效。

## 5. Proposed Shape

### 三个结构性裂缝(根因)

1. **锚定 seed 模型先天不完整**(Bug 10 + Bug 4)。`_initial_probe_bindings_for_row` 只 seed occurrence source var;projection(`$__projection_*`)/ external-head(`$__head__*`)拿空 seed → prober 重新枚举第一个实体。
2. **repr 值渲染逐 case,无统一渲染函数**(Bug 8/3、9、7、5/6 标签部分)。标签恢复只接进 `%ENT`;共享 `_term_display` `str()` 裸存储 token;`render_entity_repr` 不安全顺序替换。
3. **verdict / resolver 语义偏离规范**(Bug 11、Bug 12)。空 env 级联误判 Fails;support-capture aggregate resolver 不对称崩溃。

### Batch 矩阵(风险优先序,单线性栈顺序叠加)

> 顺序 **A → E/D → B → C → final**(Codex 对齐):正确性/崩溃(A/E/D)不排在呈现(B/C)之后。每 batch:子蓝图 draft → 我 scope-review → Codex 落地 + 本缺陷红/绿测试 → 我独立 gate。

| Batch | 缺陷 | 类别 | 范围 |
|---|---|---|---|
| **A** | Bug 10 + Bug 4 | 正确性(最高) | 重写 seed builder 覆盖 inline/projection/external 三类 head var |
| **E** | Bug 12 | 崩溃 | support-capture 用 aggregate-aware resolver(evaluate 路径;可并行准备) |
| **D** | Bug 11 | 正确性 | 修下游 verdict 空 env 级联语义 |
| **D2** | §308 post-closure deviation | 正确性 | 前序 Fails 后 explanation track 继续穷尽推进;仅真未绑定触发 NotReached |
| **B** | Bug 8 + 3 + 9 + 7 | 呈现为主 | 统一值渲染(`_term_display` + `render_entity_repr` + float64 解码) |
| **C** | Bug 6 | 呈现 | NotAtom 友好渲染(依赖 B 的 value renderer) |
| **final** | — | 收口 | native 忠实度测试电池统一命名 + 文档 + 跑 full matrix |

### Batch A 实现锁点(Codex 锁定)

覆盖三类 head 变量来源,**从 `RuleExprLoweringPlan` 结构推导,不猜**:
- inline occurrence vars:保留现有 occurrence source-var 多值映射。
- projection/external head vars:把 `row.bindings[head_port]` seed 到 lowering 生成的 head var 名。
- branch-specific source aliases:对 projection/external head-port link,seed 到所有 branch source alias-local vars(避免 OR/branch 下欠 seed)。
- 推导来源:`plan.head_binding` / `plan.declared_ports[*].branch_sources` / `plan.occurrence_map[*].port_bindings`;必要时复用/暴露 lowering 内部 `_head_var_names(plan)` 等价逻辑。

## 6. Boundaries And Invariants

- 单线性栈续在当前 explain v2 impl 栈(HEAD `b2b8ca6b`),逐 batch 叠加。
- `master` 仍 `854d03b9`,未动未 push。
- **v2 explain 程序蓝图暂不归档**(带 1 崩溃 + 4 正确性,conformance 未达)。
- 既有不变式保持:`{passed,failed}↔evidence`、repr 不入 digest、adapter 按 row_id 锚定。
- 测试电池为一等交付物,非附属。

## 7. Acceptance (Program Level)

- [x] Batch A:非 mock 端到端 `.evaluate().row.explain()` 覆盖 inline / projection / external head + OR branch + join/multi-occurrence + 多行各自锚定无串行;Bug 10 + Bug 4 关闭。
- [x] Batch E:5 种 aggregate kind native evaluate + explain 端到端通过;Bug 12 关闭。
- [x] Batch D:下游 atom verdict 反映自身真值(或 NotReached),不再空 env 误判 Fails;对齐 `explain/docs/README.md`;Bug 11 关闭。
- [ ] Batch D2:对齐设计 §307-308;前序 `Fails` 后仍穷尽推进 explanation track,依赖已绑定的下游 atom 得到 `Holds/Fails`,仅真未绑定依赖得到 `NotReached`;分支 candidate track 不复活。
- [x] Batch B:`%FLD` / compare / builtin 的 entity-ref 显友好标签、float64 显十进制、`render_entity_repr` 单遍替换无碰撞/注入;Bug 8/3/9/7 关闭。
- [x] Batch C:NotAtom 友好渲染(实体标签 + 无 `$`var + 无 tuple,`negated=True`),对齐 souffle 契约;Bug 6 关闭。
- [x] final:native prober 忠实度测试电池齐全(对标 souffle);6 忠实度判据全覆盖;全 explain cohort 绿。
- [x] 受影响 module docs 同步。

## 8. Implementation Plan

> 每 batch 一个可独立落地单元,同一 impl 分支顺序叠加。子蓝图按 `feedback_preflight_code_audit_required` 做 shipped 预审,按 `feedback_audit_to_archive_cadence` 走 draft→preflight→scoped→impl→闸→closure。

1. **Batch A**(Bug 10 + Bug 4)— seed-model 重写 + 端到端锚定测试矩阵。**最高优先,先做。**
2. **Batch E**(Bug 12)— support-capture aggregate resolver + aggregate kind 端到端测试。可紧跟 A 或并行准备。
3. **Batch D**(Bug 11)— verdict 空 env 级联修复。A 后尽快。
4. **Batch B**(Bug 8+3+9+7)— value renderer 统一 + `render_entity_repr` 单遍替换 + float64 解码。
5. **Batch C**(Bug 6)— NotAtom 友好渲染。排 B 后(依赖 value renderer)。
6. **final** — 测试电池收口 + 文档 + full matrix。
7. **Batch D2**(post-closure §308)— exhaustive verdict advance after upstream failure; candidate track remains failed.

## 9. Docs To Update

- `src/factgraph/application/explain/docs/README.md`(prober repr + verdict 语义 + 测试电池)。
- `src/factgraph/application/protocol/docs/README.md`(若 verdict 语义对外可见)。
- `src/factgraph/core/schema/docs/README.md`(`render_entity_repr` 替换语义,如有行为变更说明)。
- `docs/quickstart/evaluate_and_evidence.md`(随 v2 + conformance 收尾)。

## 10. Outcome / Deviations

Reopened after final closure. Design verification found a residual deviation
from `explain-layer-complete-design.zh.md` §307-308: Batch D computes downstream
verdicts from a frozen last-prefix environment after upstream failure, but it
does not keep advancing the explanation track. D2 is split out to align code and
docs with the exhaustive semantics before this parent can be archived.

Previously implemented on the single linear stack ending at `e48f99c4` plus
final program closure. That closure remains historical evidence, but the active
program state is now `implementing` until D2 passes gate.

Outcome:

- Closed all confirmed conformance defects from the audit:
  - Batch A `a31892ca`: Bug 10 + Bug 4 row anchoring / seed-model defects.
  - Batch E `1a23ae87`: Bug 12 aggregate support-capture crash.
  - Batch D `9b3c912f`: Bug 11 verdict cascade semantics.
  - Batch B `587057f6`: Bug 8 + Bug 3 + Bug 9 + Bug 7 + Bug 5 value rendering.
  - Batch C `ad37f290`: Bug 6 NotAtom repr / `negated=True`.
- Addressed the three structural seams:
  - seed model now follows lowering-owned seed var mapping;
  - repr value rendering is unified and display-only;
  - verdict/support-capture resolver semantics now match evaluation intent.
- Native conformance battery is documented and covers the audit matrix surfaces.
- Module docs were synchronized for final paths-model behavior.
- Final reviewer gate passed with a broader explain cohort (`190 OK`) and a
  coherent demo run.

Deviations / follow-up:

- `docs/quickstart/evaluate_and_evidence.md` still contains broad legacy
  flat-DAG content. It is deferred to a dedicated quickstart rewrite rather
  than patched piecemeal in the final cleanup slice.
- No branch push was performed in this program.
