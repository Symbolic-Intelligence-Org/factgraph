# Task Blueprint: Rule Run Trace Schema Contract

- Status: implemented
- Created: 2026-03-17
- Last Updated: 2026-03-17
- Related Modules:
  - `src/factpy_kernel/core/rules/_trace.py`
  - `src/factpy_kernel/core/rules/rule_ir.py`
  - `src/factpy_kernel/core/view/projector.py`
  - `src/factpy_kernel/core/docs/01_architecture.md`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
  - [2026-03-17_run-rule-trace-capture.md](../archive/2026-03-17_run-rule-trace-capture.md)
  - [2026-03-17_explain-ref-service-unification.md](../archive/2026-03-17_explain-ref-service-unification.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/service/docs/03_runtime_queries_views.md](../../../src/factpy_kernel/service/docs/03_runtime_queries_views.md)
- Audit Log:
  - [2026-03-17_rule-run-trace-schema-contract.audit.md](./2026-03-17_rule-run-trace-schema-contract.audit.md)

## 1. Problem

`rule_run` explainability 的主要缺口已经不再是“没有 trace capture”。当前 core 实现实际上已经具备完整的 rule runtime trace carrier、capture context、memo-hit replay、以及 sidecar-backed readback；母蓝图里把 `rule_run` 描述成“有名无实占位符”的那段判断已经过时。

现在真正未收口的，是 **trace schema 与 service contract**：

1. `RuleTraceNonFactStep.status` 目前只有 `"no_match"` / `"satisfied"` 两个值，且语义不够稳定。
   - `not` atom 用 `"no_match"` 表示“否定成立”
   - 其他非 `pred` atom 一律写 `"satisfied"`
   - 对 `cmp` / `in` / arithmetic 而言，消费方只能回看 `details`，无法从 `status` 本身判断更细的执行语义
2. `ruleref` atom 在 witness 构建阶段被直接跳过。
   - invocation 树里能看到子规则调用
   - 但 `where` 里哪一个 `ruleref` atom 对应哪次子调用，没有显式映射
3. `original_where` / `rewritten_where` 目前是刻意保持的 opaque passthrough。
   - 这本身不是 bug
   - 但其“故意不做 typed schema”应作为显式边界写清楚，而不是让消费方误以为这里还有待补全的结构化 contract
4. service 层的 `rule_run` explain response 目前只是 `_to_jsonable(RuleTraceArtifact)` 的直接暴露，缺少独立文档化的 payload contract。

因此，这个切片的任务不是重新发明 trace capture，而是审计现有 `RuleTraceArtifact` 形状、冻结若干尚未定稿的枚举/映射语义，并把 `rule_run` explain surface 收口成清晰的 schema contract。

## 2. Goals

- 审计当前 `RuleTraceArtifact` / `RuleTraceInvocation` / witness capture 现实，明确“哪些部分已经实现完成，哪些部分仍未冻结”。
- 纠正母蓝图中关于 `rule_run` trace 仍属占位符的过时 framing，并把新切片聚焦到 schema/contract 收口。
- 为 `RuleTraceNonFactStep.status` 冻结第一轮可消费的枚举语义，而不是继续让其停留在“内部实现细节”状态。
- 比较并收口 `ruleref` atom 与 invocation 树之间的最小显式映射方案。
- 明确 `rule_run` explain 的 service payload 边界：哪些字段是稳定 contract，哪些字段继续保持 opaque passthrough。
- 为后续实现型切片准备可验证的 acceptance，包括 core trace shape、service response 文档和兼容性约束。

## 3. Non-goals

- 本蓝图不重做 `run_rule_with_trace(...)`、`RuleTraceArtifact`、`RuleTraceCaptureContext` 的基础 capture 机制。
- 不重新设计 invocation 树结构、memo-hit 表达方式、或 `rule_run_id` 的持久化路径。
- 不改变 `original_where` / `rewritten_where` 当前“opaque JSON-native payload”策略。
- 不把 `rule_run` trace schema 收口与 engine witness parity（`souffle` / `problog`）混成同一任务。
- 不在本轮重写 `explain_ref` 协议，也不改动 `candidate` / `assertion` explain surface。
- 不在本轮引入 proof-tree UI、NL explain、或额外的 graph contract。

## 4. Current Context

- 当前 core trace capture 已存在：
  - `run_rule_with_trace(...)` 在执行期创建 `RuleTraceCaptureContext`、组装 `RuleTraceArtifact`，并通过 `Store._remember_rule_trace_artifact(...)` 登记 explain artifact。
  - `_trace.py` 已定义：
    - `RuleTraceArtifact`
    - `RuleTraceInvocation`
    - `RuleTracePredWitness`
    - `RuleTraceNonFactStep`
    - `RuleRunResult`
    - `rule_trace_artifact_to_dict(...)` / `rule_trace_artifact_from_dict(...)`
  - `project_view_facts_with_witness(...)` 已为 `pred` atom witness capture 提供 `asrt_id` 关联。
  - `_append_rule_trace_memo_hit(...)` 已在 memo-hit invocation 上复用原始 bindings / witnesses / where snapshots。
- 当前 service/readback surface 已存在：
  - `/rules/run` 在 `capture_trace=true` 时返回 `rule_run_id`
  - `Store.explain_rule_trace(rule_run_id)` 已可 in-process / sidecar readback
  - `POST /queries/explain-rule-trace` 与统一 `POST /queries/explain` 的 `kind="rule_run"` 都已可读取该 artifact
- 当前架构文档也已把这条链路记录为“已存在的 Rule Runtime 链路”，见 `core/docs/01_architecture.md`。
- 当前已知 gap 更像 schema/contract 问题，而非 capture 缺失：
  - `G1`: `_build_rule_trace_non_fact_step(...)` 中 `status = "no_match" if tag == "not" else "satisfied"`；该枚举尚未冻结为稳定对外语义。
  - `G2`: `_build_rule_trace_witnesses(...)` 遇到 `ruleref` atom 时直接 `continue`；call-site atom 与子 invocation 之间没有显式链接。
  - `G3`: `original_where` / `rewritten_where` 当前刻意保持 opaque passthrough；这应被记录为有意边界，而非未完成工作。
  - `G4`: service `rule_run` explain 目前直接暴露 `_to_jsonable(explain)` 结果；消费方只能从 `rule_trace_artifact_to_dict(...)` 逆推出 payload 结构。
- 当前相关历史蓝图：
  - [2026-03-17_run-rule-trace-capture.md](../archive/2026-03-17_run-rule-trace-capture.md)
    - 已完成 trace capture 与 artifact/readback 基座。
  - [2026-03-17_explain-ref-service-unification.md](../archive/2026-03-17_explain-ref-service-unification.md)
    - 已把 `rule_run` 放进统一 service `explain_ref` contract，但没有进一步冻结 typed trace payload。
  - [2026-03-17_runtime-traceability-explainability-blueprint.md](./2026-03-17_runtime-traceability-explainability-blueprint.md)
    - 仍保留较早期的“rule_run trace 尚未真正存在”叙述；这份新蓝图应以当前代码现实为准重新收口问题。

## 5. Proposed Shape

### 5.1 `ruleref` Atom To Invocation Mapping

`G2` 的首轮方案选择为 **Option C：在 `RuleTraceInvocation` 上新增显式 `ruleref_links` 字段**，而不是尝试把 `ruleref` 伪装成 `pred_witnesses` 或 `non_fact_steps`。

原因：

- `ruleref` 本质上不是 base fact witness，也不是普通 non-fact step。
- 子规则调用在 invocation 树里已经作为独立 event 存在；缺的是 call-site atom 与该 event 的显式链接。
- 独立字段最容易表达“这个 `where` 里的 `ruleref` atom 对应哪次 child invocation”，且不会污染已存在的 `pred_witnesses` / `non_fact_steps` 语义。

新增 dataclass 方向：

```python
@dataclass(frozen=True)
class RuleTraceRuleRefLink:
    ruleref_atom_key: str
    child_invocation_id: str
```

字段语义：

- `ruleref_atom_key`
  - 采用统一 key 格式：`b{branch_index}.a{atom_index}:{tag}`
  - 对 `ruleref` 固定为 `b{branch_index}.a{atom_index}:ruleref`
  - 实现上复用 `make_non_fact_step_key(branch_index, atom_index, "ruleref")`
- `child_invocation_id`
  - 指向 **这次 call-site 实际产生的 invocation**
  - 若命中 memo，则填写 memo-hit invocation 的 `invocation_id`
  - 若首次执行，则填写首次调用 invocation 的 `invocation_id`
  - 消费方若要追到 primary invocation，可再通过 `memo_source_invocation_id` 跳转

`RuleTraceInvocation` 新增字段：

```python
ruleref_links: tuple[RuleTraceRuleRefLink, ...] = ()
```

位置约束：

- 放在现有字段末尾（`non_fact_steps` 之后）
- 保持新增字段 append-only，有利于旧 row 的 graceful fallback

排序约束：

- `ruleref_links` 与 `pred_witnesses` / `non_fact_steps` 一样，要求稳定排序
- 第一轮按 `ruleref_atom_key` 排序

`_rewrite_where_rule_refs(...)` 的返回值需要扩展为三元组：

```python
tuple[
    list[Any],                        # rewritten_where
    dict[str, list[tuple[Any, ...]]], # overlay
    dict[tuple[int, int], str],       # {(branch_index, atom_index) -> child_invocation_id}
]
```

实现约束：

- `rewrite_atom(...)` 本身拿不到 child invocation id，因为 `_evaluate_rule(...)` 不返回该值。
- 第一轮允许在 `_evaluate_rule(...)` 返回后，立即读取 `trace_ctx.invocations[-1].invocation_id` 作为这次 `ruleref` 触发的 child invocation id。
- 这一点必须被视为**显式实现约束**，不是可延迟、可推断的隐式契约：
  - 只有在 `trace_ctx is not None` 时才构建该 map
  - 必须在 `_evaluate_rule(...)` 调用后立即读取 `trace_ctx.invocations[-1]`
  - 不能在更晚阶段再通过“最后一个 invocation 大概就是它”做推断

其可靠性前提当前成立：

- 首次调用路径：`_evaluate_rule(...)` 在尾部 `append_invocation(...)`
- memo-hit 路径：`_append_rule_trace_memo_hit(...)` 也会立即追加 memo-hit invocation
- 因此两种情况下 `trace_ctx.invocations[-1]` 都是当前 `rewrite_atom(...)` 触发的那次 child invocation

序列化 / 反序列化方向：

- `rule_trace_artifact_to_dict(...)` 新增：

```json
"ruleref_links": [
  {"ruleref_atom_key": "b0.a1:ruleref", "child_invocation_id": "abc123:i2"}
]
```

- `rule_trace_artifact_from_dict(...)` / `_rule_trace_invocation_from_dict(...)` 对旧 row 使用 `row.get("ruleref_links", ())` 做 fallback

### 5.2 `non_fact_steps.status` Enum Freeze

`G1` 的第一轮收口是：冻结对外语义，但 **暂不把 dataclass validator 收紧成硬枚举校验**。

writer 侧（`_build_rule_trace_non_fact_step(...)`）从本轮起只写新值：

| `kind` | 新 `status` | 旧 `status`（legacy） | 语义 |
| --- | --- | --- | --- |
| `not` | `negated` | `no_match` | 否定条件成立 |
| `cmp` | `evaluated` | `satisfied` | 比较计算完成 |
| `in` | `evaluated` | `satisfied` | 成员测试完成 |
| arithmetic 等其他 | `evaluated` | `satisfied` | 计算完成 |

命名选择：

- `no_match -> negated`
  - 旧值容易被误读成“否定条件失败”或“查找失败”
  - 新值更准确表达“该否定条件成立”
- `satisfied -> evaluated`
  - 对 `cmp` / `in` / arithmetic 而言，`satisfied` 混淆了“条件满足”和“表达式被执行”
  - `evaluated` 更中性，允许消费方再结合 `details` 解读

reader 侧（`_rule_trace_invocation_from_dict(...)`）要做一次 legacy normalize：

```python
_LEGACY_STATUS_MAP = {
    "no_match": "negated",
    "satisfied": "evaluated",
}
```

并通过 helper 归一化：

```python
def _normalize_non_fact_status(status: str) -> str:
    return _LEGACY_STATUS_MAP.get(status, status)
```

兼容性立场：

- 这轮 writer 改写序列化值，但不是“拒绝旧 row”的 breaking change
- 当前 `RuleTraceNonFactStep.__post_init__` 仍只要求 `status` 是非空字符串
- 因此旧 sidecar / export row 仍可在 normalize 后被读回
- 若未来需要把 `status` 收紧成真正枚举校验，应另开后续 slice，再显式处理历史 row 兼容

### 5.3 Service Payload Contract Boundary

`G4` 的第一轮收口不是重新包装 `rule_run` explain payload，而是**文档化当前 `rule_trace_artifact_to_dict(...)` 暴露出来的稳定 contract 边界**。

进入稳定 contract 的字段：

- 顶层：
  - `rule_run_id`
  - `root_rule.rule_id`
  - `root_rule.version`
  - `select_vars`
  - `root_rows`
- `invocations[]`：
  - `invocation_id`
  - `parent_invocation_id`
  - `rule.rule_id`
  - `rule.version`
  - `memo_hit`
  - `memo_source_invocation_id`
  - `bindings`
  - `output_rows`
  - `pred_witnesses[]`
    - `binding_index`
    - `pred_atom_key`
    - `asrt_ids`
  - `ruleref_links[]`（若 5.1 落地后新增）
    - `ruleref_atom_key`
    - `child_invocation_id`
  - `non_fact_steps[]`
    - `binding_index`
    - `step_key`
    - `kind`
    - `status`

`non_fact_steps.details` 的边界按“部分稳定”处理：

- `details.binding`
  - 进入稳定 contract
  - 表示该 binding index 下参与该 non-fact step 的 binding snapshot
- `details.atom`
  - 保持 opaque
  - 不进入 typed contract

明确保持 opaque 的字段：

- `original_where`
  - 整体 opaque
  - 只承诺它是 JSON-native passthrough
  - 不承诺其内部结构对 service/client 是稳定 schema
- `rewritten_where`
  - 同上
- `non_fact_steps.details.atom`
  - 同样视为 opaque passthrough

这意味着第一轮 service docs 应做到：

- 清楚列出哪些字段可供 typed 消费
- 明确标出哪些字段是“为了 debug / replay / internal explain 保留的 opaque payload”
- 不让消费方误以为 `original_where` / `rewritten_where` / `details.atom` 已经进入稳定的 service-level schema 承诺

## 6. Boundaries And Invariants

- 必须保持现有 `RuleTraceArtifact` 可序列化 / 可 sidecar readback / 可 service explain 的基本链路不回退。
- 必须显式区分“需要冻结的 typed fields”与“继续保持 opaque 的 payload”。
- 不得把这个切片扩成新的 engine witness parity 或新的 proof-tree carrier 任务。

## 7. Acceptance

- [x] `RuleTraceRuleRefLink` dataclass 已存在且字段/校验正确：
  - `ruleref_atom_key: str`，非空，格式 `b{n}.a{m}:ruleref`
  - `child_invocation_id: str`，非空
  - `__post_init__` 对两个字段执行基本校验
- [x] `RuleTraceInvocation.ruleref_links` 字段已存在并保持 append-only 兼容：
  - 默认值为 `()`
  - 位于 `non_fact_steps` 之后
  - `__post_init__` 对 `ruleref_links` 做按 `ruleref_atom_key` 的排序校验
- [x] 含 `ruleref` atom 的 invocation 能正确捕获 `ruleref_links`：
  - 运行含 `ruleref` atom 的 `run_rule_with_trace(...)`
  - 包含该 `ruleref` atom 的 invocation 上 `ruleref_links` 非空
  - 每个 `ruleref_atom_key` 格式正确
  - 每个 `child_invocation_id` 都能在同一 `RuleTraceArtifact.invocations` 中找到对应 invocation
- [x] memo-hit 场景下 `ruleref_links.child_invocation_id` 指向 memo-hit invocation，而不是 primary invocation：
  - 构造同一 exposed 子规则被重复 `ruleref` 引用的场景
  - 第二次引用对应的 `child_invocation_id` 指向 `memo_hit=True` 的 invocation
  - 该 invocation 的 `memo_source_invocation_id` 指向 primary invocation
- [x] `non_fact_steps.status` 的新 writer 语义已生效：
  - `not` atom 写出 `status="negated"`，不再写 `"no_match"`
  - `cmp` / `in` / arithmetic 等非 `pred` atom 写出 `status="evaluated"`，不再写 `"satisfied"`
- [x] `rule_trace_artifact_to_dict(...)` 已新增 `ruleref_links` 序列化字段：
  - 含 `ruleref` atom 的 invocation 在 dict 形态中输出 `ruleref_links`
  - 每项至少包含 `ruleref_atom_key` 与 `child_invocation_id`
- [x] `_rule_trace_invocation_from_dict(...)` 对旧 row 保持 graceful fallback：
  - 不含 `ruleref_links` 的旧 dict 可正确反序列化为 `ruleref_links=()`
  - 旧 `status="no_match"` 读回后归一化为 `"negated"`
  - 旧 `status="satisfied"` 读回后归一化为 `"evaluated"`
- [x] 含 `ruleref_links` 的 `RuleTraceArtifact` round-trip 不丢信息：
  - `to_dict(...) -> from_dict(...)` 后 artifact 仍等价
  - `ruleref_links.ruleref_atom_key` / `child_invocation_id` 均完整保留
- [x] `src/factpy_kernel/service/docs/03_runtime_queries_views.md` 已文档化 `rule_run` explain payload 的稳定 contract：
  - 顶层 `rule_run_id` / `root_rule` / `select_vars` / `root_rows`
  - `invocations[]` 的稳定字段
  - `pred_witnesses[]`
  - `ruleref_links[]`
  - `non_fact_steps[]` 顶层字段
  - 并明确 `original_where` / `rewritten_where` / `non_fact_steps.details.atom` 为 opaque passthrough，`non_fact_steps.details.binding` 为稳定 contract
- [x] 父级与模块文档中不再保留“`rule_run` trace 尚未真正存在 / 仍是占位符”的过时 framing；如存在相应表述，已在本切片中同步纠正。

## 8. Implementation Plan

1. 对现有 `RuleTraceArtifact` / `RuleTraceInvocation` / service `rule_run` explain surface 做 schema audit，确认哪些字段已稳定、哪些仍属 open gap。
2. 比较并冻结 `non_fact_steps.status` 与 `ruleref` atom mapping 的第一轮语义。
3. 比较并冻结 `rule_run` explain 的 service response contract、文档落点与兼容约束。
4. 在 scope 冻结后再决定是否需要多文件实现型切片，或仅需 docs/contract + focused tests。

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/core/docs/01_architecture.en.md`
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md`
- `docs/README.md`（仅当新增稳定文档入口时）

## 10. Outcome / Deviations

- 最终落地结果：
  - `_trace.py` 新增了 `RuleTraceRuleRefLink` 与 `RuleTraceInvocation.ruleref_links`，并把 `ruleref_links` 接入了 rule-trace serde。
  - `rule_ir.py` 现在会在 `_rewrite_where_rule_refs(...)` 内部为每个 `ruleref` atom 记录 `(branch_index, atom_index) -> child_invocation_id`，并在 root/parent invocation 上写出稳定排序的 `ruleref_links`。
  - memo-hit 场景下，`ruleref_links.child_invocation_id` 指向这次调用实际产生的 memo-hit invocation，消费方可再沿 `memo_source_invocation_id` 跳到 primary invocation。
  - `non_fact_steps.status` writer 已切换到 `negated` / `evaluated`；reader 同时保留从 `no_match` / `satisfied` 到新值的 legacy normalize。
  - `service/docs/03_runtime_queries_views.md`、`core/docs/01_architecture.md` 与 `core/docs/01_architecture.en.md` 已同步 `rule_run` payload 的稳定 contract 与 opaque boundary。
  - `src.factpy_kernel.tests.test_phase3_contracts_v1` 已补齐 focused 合同测试，`44 tests` 全通过。
- 与 blueprint 不同的地方：
  - `RuleTraceRuleRefLink.__post_init__` 只做非空字符串校验，没有把 `ruleref_atom_key` 收紧成正则级格式校验。
- 为什么会有这些调整：
  - 第一轮真正稳定的是 key 的生成规则与序列化 contract，而不是对所有外部输入做更强格式拒绝；保持 validator 最小化更有利于历史 row 兼容与后续增量收紧。
- 归档说明：
  - Blueprint 与 audit 已在实现、测试、docs 对齐后归档到 `docs/blueprints/archive/`；父级蓝图中的 child link 也已同步指向 archive 路径。
