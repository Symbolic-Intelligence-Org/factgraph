# Codebase Baseline for Rule-Replay Line Redesign

- **Status:** working / Phase 1 inventory complete; Phase 2 P0/P1 deep-dive pending
- **Authority:** non-authoritative reference. Companion to redesign-input bundle (left = design input, right = current code baseline)
- **Branch:** `v0.1-redesign-2026-05-03` (initial reset base `b4d97bf`; this working doc evolves on that branch)
- **Created:** 2026-05-03
- **Method:** Phase 1 file-level inventory + key-file module-level skim. Phase 2 will populate per-capability `current state / gap / redesign starting point` sections via targeted Read on code paths identified below. Phase 3 (Explore agent) only when call chain crosses too many files.

This doc is the right-hand side of the redesign reference. The left-hand side (design input) lives in this same directory's other files. Do not duplicate design-input content here; this doc records only **what current code does**, not **what redesign should do**.

---

## Phase 1: 高级地图(已完成)

### A. 模块结构

```
src/kernel/
├── application/                  # canonical Python runtime authority (reset 完成,真实 substrate)
│   ├── protocol/                 # 7 protocol modules + package init (common/derivation/entity_read/entity_write/ingest/query/schema_runtime)
│   ├── docs/                     # 01_overview.md (last updated 2026-04-28)
│   ├── derivation_runtime.py     # evaluate_derivation_plans / accept_derivation_candidate_set(s)
│   ├── ingest_runtime.py         # apply_ingest_request
│   ├── query_runtime.py          # execute_query
│   ├── schema_runtime.py         # build_schema_index, resolve_selector, materialize_identity, ...
│   ├── entity_view.py            # hydrate_entity, hydrate_entities, execute_read_request
│   └── entity_write.py           # plan_write_command, apply_write_plan
│
├── core/
│   ├── rules/                    # rule_ir.py, rule_ast.py, where_eval.py, ruleref_*.py, _trace*.py, where_ast*.py, backend_profile.py
│   ├── store/                    # _evaluate.py, _builders.py, _support.py, _support_capture.py, runtime.py, ledger.py, evaluation.py, queries.py, types.py, api.py, _candidate_evidence_tree.py, ... (24 files)
│   ├── derivation/               # accept.py, candidates.py, CANDIDATE_PROTOCOL_V2.md
│   ├── evidence/                 # write_protocol.py
│   ├── annotation/, mapping/, policy/, schema/, view/, protocol/
│
├── sdk/                          # ergonomic shell (NO replay/check/overlay residue after reset)
│   ├── facade.py, store.py       # SDKStore + SDK facade objects (delegate to application + still touch core directly)
│   ├── batch.py, compile.py, dsl/, ingest.py, query_lower.py, query_runtime.py, registry.py, schema.py
│   ├── docs/                     # 6 user-facing docs (00_user_guide / 01_alignment / 02_readwrite / 03_rules / 04_api_surface / 05_cn_en_consistency)
│
├── adapters/                     # OUT of scope this round (souffle/problog/pyreason)
├── audit/, authoring/            # not yet surveyed in Phase 1 (note: authoring/ existed pre-design-probe)
└── tests/                        # 63 test files (10+ application-related; 5 sdk-application-delegate/boundary)
```

### B. Input bundle 引用 reset 后的 valid 性

| Bundle 引用位置 | 当前实际位置 | 状态 | 说明 |
|---|---|---|---|
| `where_eval.py:181` `envs=[{}]` no-injection | `where_eval.py:165` | ✓ valid | line shifted -16 only;semantic identical;no-injection invariant 保持 |
| `_builders.py:39` head_vars 候选构造 | `_builders.py:39` `binding_rows = _coerce_binding_rows(...)` | ✓ valid | candidates 仍以 row-by-row binding 物化 |
| `_builders.py:90` candidate_key dedup | `_builders.py:90-96` `unique[candidate.candidate_key]` | ✓ valid | cross-run identity 仍是 candidate_key |
| `evaluate_store(disabled_locators=...)` SDK threading | 不存在 | ✓ clean baseline | reset 已移除 v0.1.3 added kwarg;`_evaluate.py:33` 当前签名见 §C |
| `kernel.sdk.replay` / `replay_runtime.py` | 不存在 | ✓ clean baseline | sdk/__init__.py 已无 replay symbol |
| `kernel.authoring.module_ir` | 待 Phase 2 验证 | TBD | Phase 1 未深入;若不存在则 v0.1.2 module IR 已 reset |

### C. 关键签名 anchor(后续 Phase 2 直接引用)

#### `evaluate_store` (`src/kernel/core/store/_evaluate.py:33`)
```python
def evaluate_store(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: HeadVarsIR,
    where: WhereIR,
    mode: EvaluateMode = "native",
    head: HeadSpecIR | None = None,
    engine_evaluate: EngineEvaluatorFn,
    registry: Any | None = None,
    confidence_kind_resolver: Any | None = None,
    engine_ext: EngineExtBase | None = None,
    engine_options: EngineOptionsIR = None,
) -> list[CandidateSet]:
```
- 没有 overlay / disabled_locators / fact_override / check_binding kwarg
- engine boundary: `mode in {native, souffle, problog, pyreason}` (4 engines hard-coded)

#### `evaluate_derivation_plans` (`src/kernel/application/derivation_runtime.py:69`)
```python
def evaluate_derivation_plans(
    request: DerivationEvaluateRequest,
    *,
    store: Store,
    registry: Any | None = None,
) -> list[CandidateSet]:
```
- `DerivationEvaluateRequest` 当前字段:`plans` / `run_id` / `engine`
- 返回直接是 core `CandidateSet` (没有 application-side wrapping)
- 没有 multi-action overlay 容器入口

#### `build_support_artifact_for_binding` (`src/kernel/core/store/_support_capture.py:29`)
```python
def build_support_artifact_for_binding(
    *,
    where: list[Any],
    binding: dict[str, Any],
    witness_facts: dict[str, list[ProjectedFact]],
    root_result_kind: str,
    selected_branch_index: int,
    rule_ref_edges: tuple[RuleRefEdge, ...] = (),
) -> SupportArtifact:
```
- 接受单 binding dict 入参 — 这是 Check operation 最近的 hook 候选(per-binding,post-evaluation)
- 但目前没有"以指定 binding 启动评估"的入口(只是构造 evidence artifact)

#### `DerivationEvaluateRequest` (`src/kernel/application/protocol/derivation.py:74`)
```python
@dataclass(frozen=True)
class DerivationEvaluateRequest:
    plans: tuple[CompiledDerivationPlan, ...]
    run_id: str | None = None
    engine: Literal["souffle", "problog", "pyreason", "native"] = "native"
```
- 完全 no-overlay shape — redesign 任何 overlay capability 都要扩这里(或新建专门 DTO)

### D. SDK boundary 现状

`sdk/store.py` 同时:
- ✓ 走 application:`from kernel.application import apply_write_plan, plan_write_command` / `from kernel.application.derivation_runtime import evaluate_derivation_plans` / `from kernel.application.protocol import ...`
- ✗ 直碰 core:`from kernel.core.derivation.accept import AcceptOptions, AcceptRequest, AcceptResult` / `from kernel.core.evidence.write_protocol import retract_by_asrt` / `from kernel.core.rules.rule_ir import RuleRegistry, RuleSpec, run_rule` / `from kernel.core.store.runtime import Store` / `from kernel.adapters.souffle.* import ...`

**Implication for redesign hard constraint:**
- Hard constraint 应针对**新 capability** 的 SDK shell:不再产生新的 `kernel.core.*` direct import
- **不**强制清理 legacy leak(那是独立的 strangler/cleanup 工作,不属于 redesign)
- 任何新 capability 必须先有 application protocol DTO + executor,SDK 只 thin wrapper

### E. Application docs alignment

读 `src/kernel/application/docs/01_overview.md`:
- 最后更新 **2026-04-28**(早于 design probe 起点 2026-04-30,所以本 doc 不含 design probe 内容)
- 公共 symbols 数量对齐:doc §3 写 "29 public symbols",当前 `__init__.py:__all__` 也导出 **29** 个
- §4(与其他层关系) / §5(SDK Adapter Status) / §6(保守边界) 与当前代码状态一致 — 实质对齐
- §7 测试入口列出 11 个 key tests,与 `tests/` 实际存在的对齐
- **结论:** docs agree(未发现 Phase 1 级别 drift)

### F. Existing tests as executable truth(初步识别)

- Application protocol/runtime:7 个测试覆盖 protocol + 6 个 runtime 模块
  - `test_application_protocol.py`
  - `test_application_schema_runtime.py`
  - `test_application_entity_view.py`
  - `test_application_entity_write.py`
  - `test_application_query_runtime.py`
  - `test_application_ingest_runtime.py`
  - `test_application_derivation_runtime.py`
- SDK delegation / boundary:4 个证明 SDK 走 application + 1 个 consumer boundary guard
  - `test_sdk_facade_application_delegate.py`
  - `test_sdk_batch_application_delegate.py`
  - `test_sdk_ingest_application_delegate.py`
  - `test_sdk_set_add_application_delegate.py`
  - `test_sdk_consumer_boundary.py`
- 任何新 capability 的测试 pattern 应:
  1. 先加 `test_application_<capability>_protocol.py`(DTO 测试)
  2. 再加 `test_application_<capability>_runtime.py`(executor 测试)
  3. SDK shell 加 `test_sdk_<capability>_application_delegate.py`(证明 SDK delegate 而非 substrate)

### G. Phase 1 关键发现

1. **Application 层是真实 substrate**(reset 后):6 个 runtime 模块 + 完整 protocol package。新 capability 的 hard constraint 已具备落地土壤。
2. **SDK boundary 清晰但有 legacy leak**(见 §D)。redesign hard constraint 应只约束新 capability 的 leak,不强制清理 legacy。
3. **测试 executable truth 已分层**:application + SDK-delegate 两段式 pattern 是新 capability 的强制 template。
4. **Input bundle 引用全部 reset-after valid**(见 §B):no-injection / candidate_key dedup / clean evaluate_store 签名都核实。
5. **Reset 完成度高**:`kernel.sdk.replay` / `evaluate_store(disabled_locators)` / 等 v0.1.x SDK substrate 痕迹均不存在。
6. **没看到的(标 unknown)**:`kernel/authoring/` 内容 / fact write/audit 完整链路 / candidate.state 字段全集 / `BindingSupportCapture` 完整 API。Phase 2 按 P0/P1/P2 分别填。

---

## Phase 2: 待填(skeleton — Phase 2 每完成一个主题就写入)

### P0-1 Application baseline(完整 protocol/runtime/executor inventory)

#### Current state

**Protocol modules (7 files, ~30 frozen-dataclass DTO + ~6 TypeAliases):**

| Module | DTO 类(frozen=True) | TypeAlias / 异常 |
|---|---|---|
| `common.py` | `ErrorDTO`, `WarningDTO` | `JSONValue`, `ProtocolShapeError` |
| `schema_runtime.py` | `EntitySelector`, `EntityRef`, `FieldPath`, `SchemaCapability` | `IdentityValue` |
| `entity_read.py` | `FieldValueDTO`, `AssertionRecordDTO`, `FieldAssertionsDTO`, `EntitySnapshotDTO`, `EntityReadRequest`, `EntityReadResponse` | `FieldValue`, `FieldFilterValue` |
| `entity_write.py` | `FieldMutation`, `EntityWriteCommand`, `PlannedOpDTO`, `EntityWritePlan`, `AppliedOpResultDTO`, `EntityWriteResult` | `WriteValue` |
| `ingest.py` | `IngestSetItem`, `IngestAddItem`, `IngestRetractItem`, `IngestRequest`, `IngestResult` | `IngestItem` |
| `query.py` | `QueryReturnSlot`, `QueryReturnContract`, `QueryRuntimeRequest`, `QueryRuntimeResponse` | `WhereIR`, `QueryRowValue` |
| `derivation.py` | `CompiledHeadCall`, `CompiledDerivationPlan`, `DerivationEvaluateRequest`, `DerivationAcceptRequest` | — |

**Runtime modules (6 files, 1-3 executor each):**

| Module | Executor entries | 错误类 | 输入 | 输出 |
|---|---|---|---|---|
| `derivation_runtime.py` | `evaluate_derivation_plans`, `accept_derivation_candidate_set`, `accept_derivation_candidate_sets` | `DerivationRuntimeError` | `DerivationEvaluateRequest`/`DerivationAcceptRequest` | `list[CandidateSet]`(core 直透) / `AcceptResult` |
| `entity_view.py` | `hydrate_entity`, `hydrate_entities`, `execute_read_request` | `EntityViewError` | `EntityReadRequest` 或 raw `e_ref` | `EntitySnapshotDTO` / `EntityReadResponse` |
| `entity_write.py` | `plan_write_command`, `apply_write_plan` | `EntityWriteError` | `EntityWriteCommand` | `EntityWritePlan` / `EntityWriteResult` |
| `ingest_runtime.py` | `apply_ingest_request` | `IngestRuntimeError` | `IngestRequest` | `IngestResult` |
| `query_runtime.py` | `execute_query` | `QueryRuntimeError` | `QueryRuntimeRequest` | `QueryRuntimeResponse` |
| `schema_runtime.py` | `build_schema_index`, `resolve_selector`, `materialize_identity`, `entity_info`, `field_predicate`, `field_value_type`, `entity_type_from_ref`, `encode_entity_ref` | `SchemaResolutionError` | varied | varied |

**Standard pattern(7 protocol modules + 6 runtime modules 中反复出现,等于"redesign 新 capability 的 template"):**

1. DTO:`@dataclass(frozen=True)` + `__post_init__` 做 shape validation,raise `ProtocolShapeError`
2. 集合用 `tuple[X, ...]`(不用 `list`,避免 mutation;与 `feedback_invariant_defense_in_depth` 一致)
3. JSON-like meta 走 `_validate_json_mapping` 重建 fresh dict(input mutation 不污染 DTO)
4. Cross-DTO 类型约束 inline 在 `__post_init__`(如 `EntitySnapshotDTO.fields[k].field.field_name == k`)
5. Error code 必须 `^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$`(SCREAMING_SNAKE_CASE,`_CODE_RE` 强制)
6. Runtime executor 显式接收 request / store / index / registry 等依赖;不从 SDK facade 或全局状态读取输入。具体依赖按 capability 需要出现(derivation/query 有 registry,entity read/write 有 index,ingest 主要用 store)。
7. Runtime 模块通常自有 `<Capability>RuntimeError(ValueError)`,带 `code` / `path` / `details` 三字段 + `to_error_dto()` / 偶尔 `to_warning_dto()`;`schema_runtime` 的 `SchemaResolutionError` 是命名例外但同样带 code/path/details。

#### Structural observations(对任何新 capability 都成立的事实)

- **No hidden-overlay invariant 由现状佐证:** 现有 request DTO **没有任何**字段带 overlay / disabled_* / fact_override / selected_binding / as_of / recompute 语义。这与 input bundle B'' invariant("rule operable + evidence read-only")一致 — 任何"what-if"必须显式落在 request 层,不能隐藏在 store/state。
- **derivation_runtime 是唯一 pass-through executor:** 它返回 raw `list[CandidateSet]`(没有 application-DTO wrapping),因为 `CandidateSet` 在 `core/derivation/candidates.py` 已是稳定 protocol(P0-2 verify)。其他 5 个 executor 都返 application-owned DTO,这意味着任何新 capability 若**没有现成可 pass-through 的 core 类型**,默认要自带 application response DTO。
- **Status vocabulary 在 application 层完全不存在:** 现有 DTO 没有任何 Literal 表达"why didn't this produce"类语义(`CandidateSet.state` 在 core 里有但**未被 application 暴露**,P0-2 verify)。任何引入 status 词汇的 capability 都要在 application 起新类型,不能复用现有 Literal。
- **Engine boundary 仅在 derivation 一处显式:** 只有 `DerivationEvaluateRequest.engine: Literal["souffle","problog","pyreason","native"]` 把 4 engines 写死;query / ingest / write / read 都没有 engine 字段。任何引入"评估行为"的新 capability 都要决定:是镜像同样 Literal,还是收窄(如仅 native),还是完全不暴露给消费者。

#### Integration anchors(架构约束,不是具体提案)

任何概念 + 交互设计在变成代码前,要落在以下既有 anchor 上(由 baseline 决定,不可妥协):

- **Application-first hard constraint:** 新 capability 的 substrate 必须先在 `kernel/application/` 起 protocol DTO + pure-fn executor,SDK 仅 thin shell。这是 reset 后的硬约束,baseline 已为此准备好了 substrate(7 protocol module + 6 runtime module 的 template)。
- **DTO immutability template:** 新 DTO 必须 `@dataclass(frozen=True)` + `__post_init__` shape validation + `tuple[X, ...]` 集合 + JSON-meta 走 `_validate_json_mapping`。这是 7 处一致的硬模板。
- **Executor dependency-injection template:** runtime 函数显式接收 request / store / index / registry 等依赖;不同 capability 的依赖集合不同,但共同点是**不读取 SDK facade state,不从全局 singleton 取上下文**。新 capability 若需要 runtime context,应作为显式参数或 request 字段出现。
- **Error model template:** 自有 `<Capability>RuntimeError(ValueError)` 带 `code`(SCREAMING_SNAKE_CASE,`_CODE_RE` 强制) / `path` / `details` + `to_error_dto()`。错误模型与 request DTO 严格分层,new capability 不得共用其他 capability 的错误类。
- **Test pattern template:** 新 capability 测试覆盖按 §F 三段式(`test_application_<capability>_protocol.py` / `test_application_<capability>_runtime.py` / 必要时 SDK delegate test)。
- **Public surface narrowing:** 新 capability 默认 internal(application-only),SDK shell 仅在交互层设计**显式要求消费者可见**时才扩(per `feedback_narrow_public_api`)。

#### 必须先解决的概念 + 交互层问题(baseline 不回答,记录待决)

baseline 不能也不应回答这些;列在这里是为了让概念 + 交互讨论 **不会绕过它们**。每个问题之前不该出现具体 file / class 命名:

- **概念**:这条新 capability 在 B'' framing 里属于"rule operable"的哪一层?是 evaluate 的变体、check 的子集、还是新顶层动作?
- **交互**:消费者(application protocol caller)给什么、拿什么?最小输入 set 是什么?最小输出 set 是什么?是否需要 partial / streaming?
- **状态边界**:如果 capability 有 status 词汇,词汇集来自哪里(input bundle "Status Vocabulary"原 6 项 / 子集 / 扩展)?谁定义"unsupported"边界?
- **engine 边界**:capability 在 4 engines 里有几个 valid?哪个是 MVP only?其余如何信号化(unsupported status / 报错 / silent fallback)?
- **persistence / replay**:capability 的 result 是不是 replayable?如果是,key 是什么?如果否,为什么?
- **identity / locator**:capability 是否引用 rule/condition/atom/binding identity?引用哪类(owner-scoped / shared / content-hash)?
- **failure mode set**:input bundle B' notes §5.6 列出 9 类 failure mode,本 capability 有哪些 valid?新增哪些?

回答完这些(在专门的概念 + 交互讨论 venue 里)再回到本 doc 的对应 capability section,把"具体代码 anchor"作为 blueprint 的预备材料填入。

#### Existing tests(factual,作为后续测试 pattern 模板)

- `test_application_protocol.py`(全 protocol 模块综合测试)
- `test_application_derivation_runtime.py`(executor pattern 模板;新 capability 测试架构 mirror 此)
- `test_sdk_facade_application_delegate.py`(SDK delegate test 模板)

> **Skeleton 模板字段(P0-1 之后调整):** 每个 capability 的 section 写以下五项,**不**出现具体 file/class 命名(那是 blueprint 阶段的事,不在 baseline 范围)。
> - **Current state:** 当前代码客观事实(模块 / 函数 / 类型签名 / 调用链)
> - **Structural observations:** 当前代码对任何新设计施加的结构性约束(no-overlay / no-status-vocabulary / engine-boundary 单点暴露 等)
> - **Integration anchors:** 任何概念 + 交互设计在变成代码前必须落到的既有架构 anchor(application-first / DTO immutability / executor signature / error model 等)
> - **Open conceptual + interaction questions:** baseline 不回答、必须由概念 + 交互设计 venue 先决的问题
> - **Existing tests:** 已有 executable truth(模板,不是新 capability 的强制名)

### P0-2 Evaluate flow / derivation runtime

#### Current state

**Application 入口(`derivation_runtime.py`,3 个 entry):**

- `evaluate_derivation_plans(request, *, store, registry=None) -> list[CandidateSet]`(:69)
  - 循环 `request.plans`,每个 plan 调 `_evaluate_plan(plan, *, request, store, registry)`(:92)
  - `_evaluate_plan` 二分:`plan.head_spec is not None` → single-head call(`heads[0]` + `head=dict(plan.head_spec)`);否则 → 循环 `plan.heads` 每 head 一次 `evaluate_store`
  - 每次 `evaluate_store(store, ..., mode=request.engine, engine_evaluate=store.evaluate_engine, ...)`
  - 多 plan 共享 run_id:循环结束后 `_attach_run_id(candidates, run_id=request.run_id)`(:140)— `replace(candidate, run_id=..., payload=dict(...), candidate_id="")`,candidate_id reset 触发 `__post_init__` 重算
  - **返回 raw `list[CandidateSet]`,无 application-side wrapping**
- `accept_derivation_candidate_set(candidate_set, accept_request, *, store, derived_rule_id, derived_rule_version) -> AcceptResult`(:152)
  - 把 application `DerivationAcceptRequest` 收窄到 core `AcceptOptions`(只取 `approved_by` / `note` / `dry_run` / `identity_override` 4 字段;单条 accept 不使用 `accept_mode` / `idempotent_duplicate_ok` / `meta`)
- `accept_derivation_candidate_sets(candidate_sets, accept_request, *, store) -> list[dict[str, Any]]`(:186)
  - Pass-through 到 `accept_many_candidate_sets`,把 `accept_request.accept_mode` 映射到 core `mode`,把 `idempotent_duplicate_ok` 转发给 core;`meta` 仍不使用;返 raw `list[dict]`(无 typed wrap)

**Core 评估核心(`_evaluate.py`,签名见 §C):**

- `evaluate_store` body(:33-163):
  1. 校验 mode ∈ {native, souffle, problog, pyreason}
  2. 若 `head["callee_kind"] == "entity_type"`(entity-targeted):
     - mode 非 native → `engine_evaluate(**kwargs)` 直接交给 engine adapter
     - mode native → `builders.entity_spec_from_head` + `_evaluate_where_over_view_with_support` + `builders.entity_candidates_from_bindings`
  3. 否则(fact-targeted):
     - mode 非 native → `engine_evaluate(**kwargs)` 直接交给 engine adapter
     - mode native → `builders.find_schema_pred` + 校验 head_vars arity = arg_specs arity + `_evaluate_where_over_view_with_support` + `builders.candidates_from_bindings`
  4. 两条 native 路径都 `_remember_candidate_support_backrefs(store, candidates)`(:241)— 把 candidate_id → support_digest/support_kind/confidence_kind/target_pred_id mapping 写到 store
- `_evaluate_where_over_view_with_support`(:186-239)— **redesign 任何 per-binding 操作的 hook 候选**:
  - `project_view_facts_with_witness(store.ledger, store.schema_ir)` 拿 witness 信息
  - `evaluate_native_where(view_facts, where, ...)` 拿 `evaluation.bindings`
  - For each binding:`find_winning_branch_index` + `derive_rule_ref_edges_for_binding` + `build_support_artifact_for_binding` + `compute_support_digest`,store 记 artifact
  - 返回 `list[BindingSupportCapture]`(`binding_items` + `support_digest` + `support_kind`),按 (binding_items, support_digest, support_kind) 排序

**Core 数据契约(`candidates.py`):**

- `CandidateSet`(frozen DC,14 字段):
  - **identity**:`derivation_id` / `derivation_version` / `run_id` / `candidate_id`(prefix `cand_v2:`,**run-scoped**) / `candidate_key`(prefix `candk_v2:`,**cross-run stable**)
  - **target**:`target`(pred_id 或 entity_type)
  - **payload**:`payload: dict[str, Any]`(fact: `{pred_id, terms}`;entity: `{entity_type, identity_fields, resolved_identity, missing_identity_fields, ...}`)
  - **support**:`support_digest`(sha256 token) / `support_kind`(string)
  - **confidence**:`confidence: float | None` + `confidence_kind: str ∈ {none, probability, certainty}`(`CONFIDENCE_KINDS` frozenset 校验)
  - **state**:`state: str = "generated"` — **free-form 字符串,无 Literal 约束**
  - **kind**:`candidate_kind: str ∈ {fact, entity}`(post_init 校验)
  - **digest**:`key_tuple_digest: str`(必须 `sha256:` 前缀) / `tup_digest: str | None`
- `make_candidate(...)`(:228)— factory:计算 candidate_key + candidate_id;`state` 默认 `"generated"`
- `extract_candidate_refs(candidate_set)`(:167)— 从 payload terms 抽 candidate_ref 依赖(供 accept 拓扑排序)
- 关键函数:`compute_candidate_key_v2(...)`(:78)按 derivation_id + version + kind + target + payload 计算;`compute_candidate_id_v2(...)`(:103)在 candidate_key 基础上叠加 run_id

**Core accept 入口(`accept.py`,1083 行,只列接口):**

- `AcceptOptions`(frozen DC,:33):approved_by / note / dry_run / identity_override
- `AcceptRequest`(frozen DC,:55):candidate_set / identity_override / approved_by / note
- `AcceptResult`(frozen DC,:41):run_id / accepted_count / skipped_count / written_assertions / skipped_reason_counts / diagnostics / diagnostics_contract_version / entity_ref / candidate_id / candidate_key
- `accept_candidate_set(...)`(:80):按 candidate_kind 分流到 `_accept_entity_candidate_v2`(:589)或 `_accept_fact_candidate_v2`(:465);`_attach_candidate_identity` 注入 candidate identity
- `accept_many_candidate_sets(...)`(:158):
  - `_topological_request_order`(:348)按 `extract_candidate_refs` 拓扑排序;cycle → `WriteProtocolError("CANDIDATE_DEPENDENCY_CYCLE")`
  - mode `atomic`:任一失败 → `_rollback_atomic_accept_many` rollback 所有已 accept,后续未处理的标 `ATOMIC_ABORTED`
  - mode `best_effort`:失败 candidate 标 `BLOCKED_DEPENDENCY`,其下游级联 BLOCKED
  - 返回 `list[dict[str, Any]]`,每项 5 字段:`candidate_id` / `candidate_key` / `state` / `entity_ref` / `error`
- **batch state 词汇集(7 项,只是 string convention,非 Literal):** `ACCEPTED` / `DUPLICATE` / `BLOCKED_DEPENDENCY` / `FAILED_VALIDATION` / `FAILED_RUNTIME` / `ATOMIC_ROLLBACK` / `ATOMIC_ABORTED`
- core 错误类:`WriteProtocolError`(**不是** `DerivationRuntimeError`;application 层错误类不下沉到 core)

#### Structural observations

- **evaluate_store 是 4-engine dispatch 的单点:** 全 evaluation 路径只有 `evaluate_store` 一处显式枚举 `mode in {native, souffle, problog, pyreason}`。`engine_evaluate` 是 `EngineEvaluatorFn` callable,通过 `Store.register_engine_evaluator(...)` 注册。任何新 evaluation-related capability 必须决定是否复用此 dispatch,或在 dispatch 之前/之后 hook,或完全旁路(走 `evaluate_native_where` 直接拿 bindings)。
- **bindings 是 native 路径的中间层 hook:** `evaluate_native_where` 返回 `evaluation.bindings`(list of binding dict);`_evaluate_where_over_view_with_support` 在此之后 wrap 成 `BindingSupportCapture`。任何"per-binding 操作"capability 必须 hook 在 bindings 这一层(input bundle §3.1 lesson:不要 hook 在 candidate 构造之后,因为 body-only 变量丢失)。
- **CandidateSet.state 是 free-form `str`:** 没有 Literal,没有 Enum,默认 `"generated"`。**"status vocabulary" 在数据契约层不存在**;accept_many 自有 7-item batch state(ACCEPTED/...),但也只是 string convention。redesign 引入任何 status 词汇必须**自带新 application Literal**,**不能 reuse** `CandidateSet.state` 或 accept_many state。
- **accept_many 返回 raw `list[dict[str, Any]]`:** application 层 `accept_derivation_candidate_sets` pass-through。这是 application-DTO 包装原则的例外,**baseline 不建议改**(独立 cleanup,不属于 redesign);redesign 新 capability 应自带 typed result DTO,**不要复用此 pass-through pattern**。
- **identity 已分清 candidate_id vs candidate_key:** input bundle §3.3 已落实 — `candidate_key`(`candk_v2:`)是 cross-run stable 的 content-hash;`candidate_id`(`cand_v2:`)叠加 run_id。redesign 任何"两次评估比对"必用 `candidate_key`,**不**用 `candidate_id`。
- **candidate_kind ∈ {fact, entity} 已硬编码:** payload shape 严格按 candidate_kind 分。新增 candidate kind 要同时改 `__post_init__` + `make_candidate` + accept routing(`_accept_entity_candidate_v2` 与 `_accept_fact_candidate_v2`)— 工作量大,**redesign 应避免**新增 kind。
- **support digest 是 evaluate-side 与 accept-side 的桥:** `_remember_candidate_support_backrefs` 把 candidate.support_digest 存到 store,accept 时(以及未来的 replay/diff)通过它找回 SupportArtifact。redesign 涉及 evidence 相关 capability 必须经过这条桥,不能旁路。
- **engine 路径是 application 不可见的 callable injection:** application 层只看到 `request.engine` 字符串和 `store.evaluate_engine` callable;实际 adapter 在 `kernel/adapters/{souffle,problog,pyreason}/` 通过 `register_engine_evaluator` 注入。redesign 不应在 application 层引入 engine-specific 字段(只能用 enum literal)。

#### Integration anchors

- **DerivationEvaluateRequest 是唯一 evaluate 入口 DTO:** 任何"evaluate variant" capability 要决定是新建 sibling DTO,还是扩 DerivationEvaluateRequest(扩字段可能违反 B'' "no overlay" 原则)。
- **CompiledDerivationPlan 是 plan 携带物:** `derivation_id` / `version` / `body_ir` / `heads` / `body_confidence` / `head_spec` / `engine_ext` / `engine_options`。新 capability 若需要 plan-targeted 操作,要决定是 reuse 还是新 plan-like type。
- **store.evaluate_engine 是 engine adapter 注入点:** 新 capability 若 engine-aware,必须复用此注入,不直接 import adapter。
- **CandidateSet 是 evaluate→accept 的契约:** 新 capability 若产 candidate-like 结果,要决定是 reuse `CandidateSet` 还是新类型(后者要在 accept 路径加 routing)。
- **AcceptOptions 是单条 accept 入参收窄点:** application `DerivationAcceptRequest` 比 core `AcceptOptions` 多 3 字段(`accept_mode` / `idempotent_duplicate_ok` / `meta`)。`accept_mode` / `idempotent_duplicate_ok` 只在 batch accept path 影响 core `accept_many_candidate_sets`;`meta` 当前不使用。新 accept-related capability 要决定是 application 层多包还是 core 加新选项。
- **engine boundary 显式 4 engines:** `mode in {native, souffle, problog, pyreason}` 硬编码。新 capability 若涉及评估行为,必须决定支持哪些 engine,以及非 native engine 怎么信号化。
- **WriteProtocolError 是 core accept 错误类:** 不与 application `DerivationRuntimeError` 共用。新 capability 若有 accept-side 行为,application 层与 core 层错误必须分开。

#### Open conceptual + interaction questions

baseline 不回答,留给 conceptual + interaction venue:

- **evaluate variant 的概念边界:** 一条新 capability 算 "evaluate 的 variant"(扩 `DerivationEvaluateRequest` 字段 / sibling DTO)、"evaluate 后处理"(以 `list[CandidateSet]` 为输入的新 executor)、还是 "evaluate 旁路"(直接调 `evaluate_native_where` 跳过 evaluate_store dispatch)?
- **status vocabulary 的归属层:** 新词汇是 application 层定义、还是先在 core `CandidateSet.state` 加 Literal、还是两层都不动只在新 capability 自带?
- **accept-time 行为的扩展点:** 若 capability 影响 accept(条件性 accept、shadow accept、不 accept 只 evaluate),要扩 `DerivationAcceptRequest` 还是新 sibling Request?或完全不通过 accept(只 evaluate-side)?
- **multi-plan / multi-binding 并发约束:** 现有 evaluate 同步 sequential;multi-plan 共享 run_id 通过 `_attach_run_id` 后处理。新 capability 若要 "多 plan / 多 binding 并行评估",并发模型要重定义(streaming response? batch result with partial?)
- **engine support matrix:** 新 capability 在 4 engines 哪些 valid?MVP 是否 native-only?非 native 信号化为 unsupported / 报错 / silent fallback?
- **support / evidence 边界:** 新 capability 是否产生 support artifact?如是,经过 `_remember_candidate_support_backrefs` 桥还是新桥?如否,evidence 比对(per B'' counterfactual replay)如何对接?
- **identity / dependency 拓扑:** 若 capability 触发 candidate 间依赖(类似 `candidate_ref`),拓扑排序逻辑(`_topological_request_order`)是否要扩展支持新依赖类型?

#### Existing tests

- `test_application_derivation_runtime.py`(application executor 测试,evaluate + accept 两 path)
- `test_application_protocol.py`(包含 derivation DTO 测试)
- `test_sdk_facade_application_delegate.py`(SDK → application 的 evaluate/accept delegation)

### P0-3 Check operation hook(final bindings + support capture)

- **Current state:** _Phase 2 待填_
- **Structural observations:** _Phase 2 待填_
- **Integration anchors:** _Phase 2 待填_
- **Open conceptual + interaction questions:** _Phase 2 待填_
- **Existing tests:** _待识别(可能在 test_engine_provenance_surface.py / test_candidate_evidence_steps.py 中)_
- **Files to read in Phase 2:** `where_eval.py` 完整 / `_support_capture.py` 完整 / `_support.py`(BindingSupportCapture class)

### P1-1 Fact read path(facts → where_eval / store view)

- **Current state:** _Phase 2 待填_
- **Structural observations:** _Phase 2 待填_
- **Integration anchors:** _Phase 2 待填_
- **Open conceptual + interaction questions:** _Phase 2 待填_
- **Existing tests:** `test_application_ingest_runtime.py`(write side), _read 侧测试待识别_
- **Files to read in Phase 2:** `core/view/projector.py` / `_evaluate.py` 与 view 的接合 / `core/store/runtime.py`(view materialization)
- **OUT-of-scope(per user):** fact write/audit/retract semantics(避免提前展开 FactOverlay 方向)

### P1-2 Candidate shape / status gap

- **Current state:** _Phase 2 待填_
- **Structural observations:** _Phase 2 待填_
- **Integration anchors:** _Phase 2 待填_
- **Open conceptual + interaction questions:** _Phase 2 待填_
- **Existing tests:** `test_application_derivation_runtime.py`
- **Files to read in Phase 2:** `core/derivation/candidates.py`(`CandidateSet` / `make_candidate` / state 全集)

### P2-* foothold check(只查"现在是否有 anchor",不深挖)

- **shared_id / identity:** _Phase 2 待填(≤3 sentences)_
- **add-condition:** _Phase 2 待填(≤3 sentences)_
- **lazy why-not:** _Phase 2 待填(≤3 sentences)_

---

## Phase 3: 跨模块 query(按需)

仅在 Phase 2 某个主题发现"调用链跨太多文件" 时启用 Explore agent。Phase 1 没有触发条件。

---

## 与 Input Bundle 的对接

- 本 doc(右半边 baseline)与 `README.md` / `00_brainstorm-original.md` / `10..60_*.md`(左半边 design input)同目录平级
- Redesign blueprint(未来在 `docs/blueprints/active/` 起)的 §4 Current Context 应:
  1. 引用本 doc 的对应 capability section(右半边)
  2. 引用 input bundle 的对应 capability 入口(左半边)
  3. 自身只声明"this blueprint 在两边之间的 specific design choice"
