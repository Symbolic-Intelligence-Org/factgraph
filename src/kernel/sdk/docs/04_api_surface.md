# SDK API Surface 索引（当前实现）

本页对齐 `kernel/sdk/__init__.py` 的公开导出与核心类方法。SDK API surface 是 Python product surface；query / ingest / compiled derivation 等 runtime execution 由 `kernel.application` 承接,SDK 负责 outward adapter 与兼容形态。

Batch 8 public-surface 决议后,SDK surface 仍保持窄口径:本页列出的导出与 `SDKStore` 既有 facade 是 v0.1 product public API。L Direction G1 新增 `SDKStore.check(...)` / `SDKStore.diagnose(...)` 作为 Check / Diagnose 的窄 SDK shell;G4 新增 `SDKStore.why_not(...)` 作为 Why-not Universe Diagnose 的窄 SDK shell;G2 新增 `SDKStore.check_fact_overlay(...)` 与 `SDKStore.recheck_proof_frame(...)` 作为 Fact Overlay Check 与 ProofFrame Recheck 的窄 SDK shell;G3 新增 `SDKStore.check_rule_disable(...)` / `SDKStore.check_rule_literal_replace(...)` / `SDKStore.check_rule_add_condition(...)` 作为三个 rule-overlay 的窄 SDK shell;G5 新增 `SDKStore.diff_proof_frames(...)` 作为 ProofFrame Diff 查询侧的窄 SDK shell,并显式 defer Round events recorder lifecycle 到 advanced importable。所有 9 个 L 方法都不新增 `kernel.sdk.__all__` 导出,也不 re-export application 或 audit DTO。G2 Phase 0 hygiene 把 5 个 shell 模块迁移到 `kernel/sdk/shells/` 子包(G1 + G4 invariant tests retrofit per `#P1` carve-out);G3 Phase 1/2/3 在该子包下新增三个 rule-overlay shell 文件,并对三个 application-runtime 边界测试(`test_no_sdk_rule_{disable,literal_replace,add_condition}_surface`)完成 `#P1` retrofit;G5 Phase 1 在该子包下新增 `proof_frame_diff.py`,共 9 模块,无 `#P1` retrofit(audit-layer 测试不曾 assert "no SDK surface")。rule-action runtimes 通过 G3 SDK shells 直接可用;ProofFrame diff 通过 G5 SDK shell 直接可用;Round events recorder lifecycle (`start_round` / `record_round_event` / `finalize_round`) 与 Frontier trace 仍通过 `kernel.audit.round_events` / `kernel.core.rules.frontier` advanced importable surface 使用。Frontier 在 G4 §5.4 中显式不进入 SDK facade,evaluator drift gate 与 application no-opt-in 测试继续生效;Round events recorder 在 G5 §5.1 中显式 defer(stateful、raises、persistence-adjacent;现有 UX 已直接 `from kernel.audit.round_events import ...`)。未来若要把 Frontier、Round recorder 或其他族提升为 SDK ergonomic API,必须单独冻结 outward request/result shape,不能直接 re-export application 或 audit DTO。

L Direction 跨边界 DTO 层规则(锁于 G5 §5.3 / §6,承接 G2 §5.1+§5.2 + G3 §5.2):**raw 跨 SDK 边界 DTO 必须满足 "frozen canonical DTO above `kernel.core` using `kernel.application.protocol` vocabulary"**。具体含义:

- **In scope** — `kernel.application.protocol` frozen DTO(如 `EvaluationOverlay` / `SupportArtifact` / `RuleLiteralPath` / `RuleAddedAtom`)与 `kernel.audit` frozen DTO(如 `RoundEvent` / `ProofFrameDiff` / `FrameDelta` / `AtomDelta` / `FrameIdentity` / `FrameStatusChange` / `EventReference` / `WarningDTO`)。
- **Out of scope** — `kernel.core.*` substrate IR(如 `kernel.core.rules.rule_ir.RuleSpec`)。SDK 显式拒绝 raw `RuleSpec`,改用 SDK `Rule` 对象并通过 `_compile_rule_input(...)` 内部 lower。

该规则在 §6 invariants 中编入 verbatim,适用任何未来对 audit-layer 或 application-protocol DTO 的 SDK shell。

## 0. Post-L SDK 教学分类（FactGraph taxonomy）

post-L SDK ergonomics redesign 将 30 个 user-facing flat 方法组织为 8 个 top-level taxonomy namespaces + 2 个 sub-namespaces (under `what_if`)。`FactGraph` 是 `SDKStore` 的字面别名（literal alias）,作为 v0.1 SDK 的 canonical 顶层入口名;flat `SDKStore.<method>` 形式仍然受支持作为 **foundational API** ——既不被弃用也不会移除。

新代码推荐使用 taxonomy form:

```python
from kernel.sdk import FactGraph

fg = FactGraph.from_schema_classes([User])

# Taxonomy form (preferred for new code)
fg.read.get(User, user_id="u-1")
fg.write.add(User.tag, alice, "engineer")
fg.what_if.check(rule, binding)
fg.what_if.fact_overlay.check(support, overlay)
fg.what_if.rule.disable(rule, support_artifact, ...)
fg.audit.diff_proof_frames(round_a_id, round_b_id, events_a, events_b)

# Flat form (foundational API; permanently supported)
fg.get(User, user_id="u-1")
fg.add(User.tag, alice, "engineer")
fg.check(rule, binding)
fg.check_fact_overlay(support, overlay)
fg.check_rule_disable(rule, support_artifact, ...)
fg.diff_proof_frames(round_a_id, round_b_id, events_a, events_b)
```

8 top-level namespaces:

| Namespace | 包含方法 |
|---|---|
| `schema` | `ingest`, `validate_provenance` |
| `read` | `get`, `find`, `ref` |
| `write` | `set`, `add`, `retract`, `edit` |
| `eval` | `run`, `evaluate`, `evaluate_compiled`, `accept`, `accept_compiled`, `accept_many` |
| `what_if` (G1+G4 direct) | `check`, `diagnose`, `why_not` |
| `what_if.fact_overlay` (G2) | `check` (was `check_fact_overlay`), `recheck_proof_frame` |
| `what_if.rule` (G3) | `disable`, `literal_replace`, `add_condition` (prefix dropped at sub-namespace level) |
| `audit` | `explain_fact`, `conflicts`, `diff_proof_frames` (G5; placed here per §5.2.1 because it consumes recorded round events) |
| `package` | `export_package`, `run_package` |
| `views` (existing) | `create`, `update`, `delete`, `get`, `list` |

Manager 类（`_SDKSchemaManager` 等）保持私有,不进入 `kernel.sdk.__all__`;读时通过 `FactGraph.<namespace>` 属性访问;写时（如 `fg.what_if.foo = ...`）抛 `FrozenSnapshotError`。详细 design 见 [post-L SDK ergonomics redesign blueprint](../../../../docs/blueprints/archive/2026-05-09_post-l-sdk-ergonomics-redesign.md) §5.2 / §5.4 / §5.7。

## 1. 顶层导出（`from kernel.sdk import ...`）

### 1.1 Schema / Store / Registry

- `Entity`
- `Field`
- `Identity`
- `FactGraph` *(post-L; canonical taxonomy entrypoint;`SDKStore` 的字面别名)*
- `SDKStore` *(foundational; permanently supported)*
- `SDKRegistry`

补充：
- plain `Entity` 实例实现了调试友好的 `__repr__()`；输出按声明顺序展示 identity 与 field 值，未赋值 `Field` 显示为 `None`。

### 1.2 DSL

- `Body`
- `Rule`
- `RuleRef`
- `Derivation`
- `Query`
- `Pred`
- `Not`
- `vars`
- `SDKDSLError`

### 1.3 Schema 编译辅助

- `build_authoring_schema_from_classes`
- `compile_schema_from_classes`
- `schema_preflight_from_classes`

### 1.4 Ingest / Provenance

- `IngestResult`
- `ValidationReport`

### 1.5 错误与错误码

- 错误类：`SDKSchemaError`、`SDKStoreError`、`SDKRegistryError`、`EntityNotFoundError`、`FrozenSnapshotError`、`CardinalityError`、`EditorClosedError`
- 导出错误码：
  - `INVALID_ROW_FORMAT`
  - `QUERY_MISSING_REF`
  - `QUERY_TYPE_MISMATCH`
  - `QUERY_ALIAS_CONFLICT`
  - `QUERY_UNBOUND_VAR`
  - `QUERY_INVALID_ROW_FORMAT`
  - `QUERY_NOT_IMPLEMENTED`

## 2. `SDKStore` 公开方法

- `from_schema_classes(..., ledger=None, ledger_path=None, artifact_store_root=None, default_row_format=None)`
- `batch(...)`
- `get(...)`
- `find(...)`
- `edit(...)`
- `ingest(...)`
- `validate_provenance(...)`
- `check(...)`
- `diagnose(...)`
- `why_not(...)`
- `check_fact_overlay(...)`
- `recheck_proof_frame(...)`
- `check_rule_disable(...)`
- `check_rule_literal_replace(...)`
- `check_rule_add_condition(...)`
- `diff_proof_frames(...)`
- `ref(...)`
- `set(...)`
- `add(...)`
- `retract(...)`
- `run(...)`
- `evaluate(...)`
- `evaluate_compiled(...)`
- `accept(...)`
- `accept_many(...)`
- `accept_compiled(...)`
- `explain_fact(...)`
- `conflicts(...)`
- `export_package(...)`
- `run_package(...)`

关键边界：
- `SDKStore` 是用户入口和 facade 聚合器,不是 canonical runtime authority。runtime-normalized query / ingest / compiled derivation orchestration 已委托到 `kernel.application`。
- `from_schema_classes(...)` / `schema_preflight_from_classes(...)` 的 `classes` 校验错误抛 `SDKSchemaError`（`SDKStore(...)` 构造器路径对应为 `SDKStoreError`）。
- `SDKStore.__init__(..., artifact_store_root=None)` 与 `from_schema_classes(..., artifact_store_root=None)` 都支持 sidecar-backed explain artifact readback；若已显式传入 `store=...`，构造器上的 `artifact_store_root` 会被忽略。
- `run(...)` 支持 Rule/Query，不支持 Derivation。
- `run(rule, view=...)` 支持具名/内联视图；Query 路径不支持 `view` 与 `return_display_meta`。
- `evaluate(...)` 显式拒绝 `view` 与 `temporal_view`。
- `evaluate(..., engine_options={...})` 支持 engine run-time 配置；该参数是 call-time only，不进入 `Derivation` / authoring payload。
- `evaluate(mode="native", engine_options={...})` 会显式报错；engine_options 的 key 校验与默认值由目标 adapter 负责。
- `check(Derivation(...), binding, *, engine="native", registry=None)` 与 `diagnose(...)` 只接受 SDK `Derivation` 和 `$` 前缀 binding `Mapping`；返回 application `CheckResult` / `DiagnoseResult` 原始 DTO,但这些 DTO 不进入 `kernel.sdk.__all__`。
- `why_not(Derivation(...), candidates, *, engine="native", registry=None)` 接受 SDK `Derivation` + 显式有限 candidate universe (`Sequence[Mapping[str, Any] | Sequence[Any]]`,与 `kernel.application.capability_helpers.build_why_not_candidate_universe(...)` 同型),返回 application `WhyNotUniverseResult` 原始 DTO；不进入 `kernel.sdk.__all__`。Why-not 不接受 `CompiledDerivationPlan` 也不在 store 内做 universe 自动发现。所有非-SDK 异常 (`ValueError` / `RuleCompileError` / `CapabilityHelperError` / `ProtocolShapeError` / `WhyNotRuntimeError`) 都 remap 成 `SDKStoreError(..., path="$.why_not[.derivation|.dependencies|.candidates|.request|]") from exc`。
- `check_fact_overlay(Derivation(...), binding, overlay, *, engine="native", registry=None)` 接受 SDK `Derivation` + `$` 前缀 binding `Mapping` + 原始 `EvaluationOverlay` protocol DTO,返回 application `FactOverlayCheckResult` 原始 DTO；不进入 `kernel.sdk.__all__`。`EvaluationOverlay` 是 author-time intent (G1 §5.7 拒绝 `CompiledDerivationPlan` 的 already-lowered 理由不适用); SDK 显式拒绝 `tuple[FactValueOverride, ...]` 形态(虽然 application `FactOverlayCheckRequest.overlay` 字段会容忍它)。Runtime 把 unsupported overlay / rule_actions / 内部 phase 错误表示为 `FactOverlayCheckResult(status="invalid_request")`,SDK 直接透传;只有 unexpected 运行时异常才走 base path remap。所有非-SDK 异常 (`ValueError` / `RuleCompileError` / `ProtocolShapeError` / 其它 unexpected) remap 成 `SDKStoreError(..., path="$.check_fact_overlay[.derivation|.binding|.overlay|.dependencies|.request|]") from exc`。
- `recheck_proof_frame(support_artifact, overlay)` 接受原始 `SupportArtifact`(从前一次 `sdk.check(...)` 的 `result.evidence_envelope.engine_payload` 取出)和原始 `EvaluationOverlay`,返回 application `ProofFrameRecheckResult` 原始 DTO；不进入 `kernel.sdk.__all__`。无 derivation lowering / registry resolution / engine 参数。SDK 不 wrap `SupportArtifact`,不从 `CheckResult` argument 中抽取,不内部调 `sdk.check(...)`。所有非-SDK 异常 (validation / `ProtocolShapeError` / 运行时 unexpected) remap 成 `SDKStoreError(..., path="$.recheck_proof_frame[.support_artifact|.overlay|.request|]") from exc`。
- `check_rule_disable(rule, support, *, branch_index, atom_index, overlay=None, note=None)` 接受 SDK `Rule`(经 `_compile_rule_input` 内部 lower 到 `RuleSpec`)+ 原始 `SupportArtifact` + 可选 `EvaluationOverlay`(只接受 `None` 或空 overlay,rule-action overlay 由 A helper 内部构造),返回 application `RuleDisableResult` 原始 DTO；不进入 `kernel.sdk.__all__`。SDK 拒绝 raw `RuleSpec`(substrate IR layer mismatch per §5.2 lock)与 SDK `Derivation`。Runtime 把 unsupported support / rule_ref-bearing support / target-not-found / rule-id mismatch / native-eval 错误表示为 `RuleDisableResult(status="invalid_request"|"unsupported")`,SDK 直接透传。所有非-SDK 异常 (`SDKStoreError`/`RuleCompileError`/`ValueError` from lowering、`RuleCompileError` from registry、`CapabilityHelperError`/`ProtocolShapeError` from A helper、unexpected 运行时) remap 成 `SDKStoreError(..., path="$.check_rule_disable[.rule|.support|.overlay|.dependencies|.request|]") from exc`。
- `check_rule_literal_replace(rule, support, *, branch_index, atom_index, literal_path, old_literal, new_literal, overlay=None, note=None)` 与 `check_rule_disable` 同形,但额外接受原始 `RuleLiteralPath`(`kernel.application.protocol.RuleLiteralPath`,frozen application DTO,适用 G2 §5.1+§5.2 cross-cutting precedent)、`old_literal`/`new_literal: Any`,返回 `RuleLiteralReplaceResult`。Non-`RuleLiteralPath` `literal_path` 输入会从 SDK pre-validation 漏过(无对应 shared validator),被 A helper / action DTO `__post_init__` 抛 `ProtocolShapeError`,remap 成 `$.check_rule_literal_replace.request`。其它非-SDK 异常 remap 路径与 `check_rule_disable` 同型。
- `check_rule_add_condition(rule, support, *, branch_index, added_atom, overlay=None, note=None)` 与 `check_rule_disable` 同形,但**没有 `atom_index` 参数**(Add Condition 在 branch 末尾追加新 atom,不指向已有 locator),且接受原始 `RuleAddedAtom`(`kernel.application.protocol.RuleAddedAtom`,frozen application DTO),返回 `RuleAddConditionResult`。Non-`RuleAddedAtom` `added_atom` 输入会从 SDK pre-validation 漏过,被 A helper / action DTO `__post_init__` 抛 `ProtocolShapeError`,remap 成 `$.check_rule_add_condition.request`。其它非-SDK 异常 remap 路径与 `check_rule_disable` 同型。
- `diff_proof_frames(round_a_id, round_b_id, round_a_events, round_b_events, *, warnings=(), include_unchanged=False)` 接受两个非空字符串 round id + 两组原始 `tuple[RoundEvent, ...]`(`kernel.audit.round_events.RoundEvent`,frozen audit DTO,适用 G5 §5.3 跨边界层规则)+ 可选 `tuple[WarningDTO, ...]`,返回 application-canonical `ProofFrameDiff` 原始 DTO(`kernel.audit.proof_frame_diff.ProofFrameDiff`);不进入 `kernel.sdk.__all__`。SDK shell 是纯函数(no Store / no registry / no engine arg / no IO),mirror `kernel.audit.proof_frame_diff.build_proof_frame_diff(...)` 1:1;用户通过 `kernel.audit.load_audit_package` 加载或从 fresh recorder 取得 events。**Round events recorder lifecycle (`start_round` / `record_round_event` / `finalize_round`) 显式 defer 到 `kernel.audit.round_events` advanced importable**(G5 §5.1 锁——recorder 是 mutable / stateful / persistence-adjacent;现有 UX 已直接 `from kernel.audit.round_events import ...`)。所有非-SDK 异常 remap 成 `SDKStoreError(..., path="$.diff_proof_frames[.round_a_id|.round_b_id|.round_a_events|.round_b_events|.warnings|.include_unchanged|.request|]") from exc`(**8-path** 共 6 个 inline pre-validation input paths + `ProofFrameDiffError` 到 `.request` + defensive `Exception` 到 base;`.include_unchanged` 是严格 `isinstance(.., bool)` 检查,`1`/`0` 也会被拒,匹配 `return_display_meta` 的 SDK 先例)。Walker view `kernel.application.walker.ProofFrameDiffView` 仍是 Tier 2 advanced importable opt-in,不被 SDK shell 自动 wrap。
- `run(rule)` 的 `row_format` 优先级：调用参数 > `default_row_format` > `FACTPY_ROW_FORMAT` > `"dict"`。
- `FACTPY_ROW_FORMAT` 在 `SDKStore` 初始化时读取并缓存。
- `row_format="tuple"` 仍可用但会触发 `DeprecationWarning`。
- Query 默认返回 `list[dict]`；支持 `row_format="instance"`（仅 head 为单个 `Entity(var)`）。
- Query 使用非法 `row_format`、instance 模式 head 不匹配、或对 Derivation 调用 `run(...)`，都会抛 `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`。
- `accept(CandidateSet, ...)` 只接受一个位置参数；支持 `approved_by`/`note`/`dry_run`/`identity_override`（也可通过 `meta_overrides` 传）。

## 3. `SDKRegistry` 公开方法

- `apply_schema_classes(...)`
- `apply_authoring_bundle(...)`
- `read_manifest(...)`
- `upsert_schema_ir(...)`
- `register_rule_spec(...)`
- `register_rule(...)`
- `register_derivation_spec(...)`
- `register_derivation(...)`
- `get_schema_entry(...)`
- `list_rule_ids(...)`
- `list_derivation_ids(...)`
- `list_rule_versions(...)`
- `list_derivation_versions(...)`
- `list_apply_run_ids(...)`
- `list_apply_runs(...)`
- `show_apply_run(...)`
- `get_latest_rule_spec(...)`
- `get_latest_derivation_spec(...)`
- `read_rule_spec(...)`
- `read_derivation_spec(...)`

说明：
- `register_derivation(...)` 当前按单 head 语义编译发布。
- 如需发布多 head，建议在调用方先拆成多个单 head derivation。

## 4. Facade 返回对象

- `EntitySnapshot`
  - 属性：`ref`、`entity_type`、`identity_available`、`identity`、`assertions`
  - 方法：`field(name)`
- `EntityEditor`
  - `preview()`、`commit(meta=...)`、`rollback()`
  - 属性：`ref`、`entity_type`
- `FieldEditor`
  - `set(...)`、`add(...)`、`retract(*, asrt_id=..., meta=...)`（关键字参数）

## 5. Batch 相关对象

- `SDKBatchTx`
  - `entity(...)`、`preview(...)`、`commit(...)`、`save(...)`
  - context manager `__exit__` 不自动 commit/rollback
- `BatchPlan`
  - `ops`、`warnings`、`export(sdk)`、`to_json(sdk)`、`apply(sdk)`
- `WireBatchPlan`
  - `to_dict()`、`to_json()`、`from_dict(...)`、`from_json(...)`、`apply(sdk, strict_schema=True)`

补充：
- batch 托管句柄的撤销方法是 `ManagedFieldHandle.retract(assertion_id, ...)`（参数名为 `assertion_id`，也支持位置参数）。

## 6. Query / Derivation 运行速查

### 6.1 Query

- `sdk.run(Query(...)) -> list[dict]`（默认）或 `list[EntitySnapshot|None]`（`row_format="instance"` 且 head 仅单个 `Entity(var)`）
- SDK 保留 `Query` DSL lowering 与 outward row formatting; application `execute_query(...)` 执行 runtime-normalized request。
- `on_missing` / `on_type_mismatch`: `error|skip|null`
- Query field head 只支持 schema 的 `single` 字段

### 6.2 Derivation

- `sdk.evaluate(Derivation(...), mode="native|souffle|problog|pyreason") -> list[CandidateSet]`
- SDK 保留 `Derivation` DSL lowering、mode sugar 与 compatibility checks; application `evaluate_derivation_plans(...)` 执行 compiled plan orchestration。
- 旧名 `python|engine` 传入会明确报错并提示新名称
- `head` 形态决定 candidate kind
- `head=[...]` 支持 evaluate 展平输出
- `CandidateSet.confidence`：`problog` 为概率 `float`，`pyreason` 为 lower bound `float`，`native/souffle` 为 `None`
- `sdk.accept(...)` / `sdk.accept_many(...)` 负责写入与幂等
- `engine_ext`：共享的 definition-time 引擎语义 carrier；可挂在 `Rule.engine_ext` 或 `Derivation.engine_ext`（如 `PyReasonRuleExt(timestep_delay=1)`），必须继承 `EngineExtBase`
- `engine_options`：`sdk.evaluate(..., engine_options={"timesteps": 5})` 传递运行时配置，call-time only，不进入 Derivation 或 Ledger
- `mode="native"` 拒绝非空 `engine_options`
- 语义 annotation：PyReason 结果自动生成 `pyreason/semantic/*`，ProbLog 结果生成 `problog/semantic/probability`；accept 后需显式调用 `persist_pyreason_annotations()` 或 `persist_problog_annotations()` 完成持久化
