# Codebase Baseline for Rule-Replay Line Redesign

- **Status:** working / Phase 1 inventory complete; Phase 2 P0/P1 deep-dive pending
- **Authority:** non-authoritative reference. Companion to redesign-input bundle (left = design input, right = current code baseline)
- **Branch:** `v0.1-redesign-2026-05-03` @ commit `b4d97bf`
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

- **Current state:** _Phase 2 待填_
- **Gap (vs redesign needs):** _Phase 2 待填_
- **Redesign starting point:** _Phase 2 待填_
- **Existing tests:** `test_application_protocol.py`, `test_application_derivation_runtime.py`
- **Files to read in Phase 2:** all `src/kernel/application/protocol/*.py`, all `src/kernel/application/*_runtime.py`

### P0-2 Evaluate flow / derivation runtime

- **Current state:** _Phase 2 待填_
- **Gap:** _Phase 2 待填_
- **Redesign starting point:** _Phase 2 待填_
- **Existing tests:** `test_application_derivation_runtime.py`, `test_sdk_facade_application_delegate.py`
- **Files to read in Phase 2:** `derivation_runtime.py` 完整 / `_evaluate.py:60-end` / `core/derivation/{accept,candidates}.py`

### P0-3 Check operation hook(final bindings + support capture)

- **Current state:** _Phase 2 待填_
- **Gap:** _Phase 2 待填_
- **Redesign starting point:** _Phase 2 待填_
- **Existing tests:** _待识别(可能在 test_engine_provenance_surface.py / test_candidate_evidence_steps.py 中)_
- **Files to read in Phase 2:** `where_eval.py` 完整 / `_support_capture.py` 完整 / `_support.py`(BindingSupportCapture class)

### P1-1 Fact read path(facts → where_eval / store view)

- **Current state:** _Phase 2 待填_
- **Gap:** _Phase 2 待填_
- **Redesign starting point:** _Phase 2 待填_
- **Existing tests:** `test_application_ingest_runtime.py`(write side), _read 侧测试待识别_
- **Files to read in Phase 2:** `core/view/projector.py` / `_evaluate.py` 与 view 的接合 / `core/store/runtime.py`(view materialization)
- **OUT-of-scope(per user):** fact write/audit/retract semantics(避免提前展开 FactOverlay 方向)

### P1-2 Candidate shape / status gap

- **Current state:** _Phase 2 待填_
- **Gap:** _Phase 2 待填_
- **Redesign starting point:** _Phase 2 待填_
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
