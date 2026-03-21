# Task Blueprint: Phase3 Test Decomposition

- Status: implemented
- Created: 2026-03-21
- Last Updated: 2026-03-21
- Related Modules:
  - `src/factpy_kernel/tests/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
- Audit Log:
  - [2026-03-21_phase3-test-decomposition.audit.md](./2026-03-21_phase3-test-decomposition.audit.md)

## 1. Problem

`test_phase3_contracts_v1.py` 是 10,372 行、103 个 test method 的单文件巨石，
是当前仓库最大的结构性负债：

- **定位困难**：查找某个 capability 的 contract test 需要在万行文件里搜索
- **脆弱耦合**：31 处直调 `store._remember_*` 等 private API；任何 Store / Support 内部重构都同时破 N 个测试
- **Schema helper 散落**：12 个 module-level `_*_schema_ir()` helper（L9510–L10289）和 `_seed_*` / `_register_*` fixtures 只被各自 1-2 个 test 消费，但全部挤在同一文件
- **叠加风险**：后续 salience/impact、annotation contract 等新 capability 如果继续往这个文件里写，拆分成本只会更高

目标不是"一次拆完"，而是定义一个 **3-phase staged refactor**，每个 phase 可独立落地、独立验证。

## 2. Goals

- 按 capability line 将 103 个 test 拆成 ≤7 个独立文件，每个文件有清晰的职责边界
- Phase 1 优先抽出 certainty / confidence 相关测试并补齐 `ValueError` + tri-state explicit tests
- 引入最小共享 test helper module，消除跨文件重复的 fixture 构造代码
- 每个 phase 结束后全量 200 tests 必须 green，不允许中间态红

## 3. Non-goals

- 不重写测试逻辑本身（除补齐 P1 缺失 coverage）
- 不消除 private API 调用（那是另一个独立任务）
- 不改变测试发现机制（继续用 `unittest discover -p 'test_*.py'`）
- 不触碰 `test_phase3_contracts_v1.py` 以外的已有测试文件

## 4. Current Context

- 当前实现入口：`src/factpy_kernel/tests/test_phase3_contracts_v1.py`（10,372 行，103 methods，1 class）
- 共享 fixtures：12 个 module-level schema IR helpers + `_seed_users_for_syntax_matrix` + `_register_exposed_user_tag_rule` + `_seed_ecss_compliance_facts`
- 当前文件内部 test 分布（按行号段）：

| 行号范围 | 测试数 | Capability line |
|----------|--------|-----------------|
| 180–1027 | 19 | Core: entity/schema/query/derivation/temporal/rule-DSL |
| 1028–1295 | 7 | Confidence meta + write protocol + derivation multi-head + registry root |
| 1296–1860 | 6 | **Certainty explain-summary delivery** |
| 1861–3334 | 12 | Evidence tree + rule-trace explain + narrative/NL parity |
| 3335–6591 | 9 | **Domain walkthroughs** (AML×4, form-doc, single-note, multi-note×2, mixed-source) |
| 6592–7082 | 2 | Domain walkthroughs (process-safety, clinical) |
| 7083–7593 | 3 | Degraded/engine evidence tree + runtime explain route |
| 7594–7793 | 3 | Artifact store + audit-package + candidate-support-backrefs |
| 7794–8594 | 11 | **ECSS** (VCD/temporal/uncertainty helpers + scenario-A + compliance matrix) |
| 8597–9099 | 10 | Winning branch + rule-ref-edge + rule-trace artifact |
| 9101–9509 | 8 | **Artifact sidecar** (file sidecar + store sidecar + SDK cross-instance) |
| 9510–10372 | — | Module-level schema IR helpers + seed fixtures |

- 已知约束：hook 阻止助手直接编辑 `src/factpy_kernel/` 下的 `.py` 文件
- 相关历史蓝图：`certainty-weight-vocabulary`（已归档）、`certainty-summary-explain-delivery`（已归档）

## 5. Proposed Shape

### 5.1 目标文件结构

Phase 结束后的 `tests/` 目录（新增文件标 ★）：

```
tests/
├── _test_helpers.py                          ★ 共享 fixtures
├── test_phase3_contracts_v1.py               残留：core entity/schema/query/derivation/temporal/rule-DSL (~19 tests)
├── test_certainty_explain_contracts.py       ★ Phase 1
├── test_evidence_tree_explain_contracts.py   ★ Phase 2
├── test_domain_walkthrough_contracts.py      ★ Phase 3a
├── test_ecss_compliance_contracts.py         ★ Phase 3b
├── test_winning_branch_rule_trace_contracts.py  ★ Phase 3c
├── test_artifact_sidecar_contracts.py        ★ Phase 3d
├── ... (existing files unchanged)
```

### 5.2 Phase 1：Certainty + Confidence（本轮实施）

**抽出 → `test_certainty_explain_contracts.py`**：

| 原始 test method | 原始行号 |
|-----------------|---------|
| `test_confidence_meta_requires_float_in_range` | 1028 |
| `test_candidate_confidence_kind_defaults_validates_and_preserves_identity` | 1040 |
| `test_problog_parse_output_sets_probability_confidence_kind` | 1108 |
| `test_candidate_summary_certainty_uses_override_registry_root_and_child_rule_weights` | 1296 |
| `test_candidate_summary_certainty_all_unweighted_when_rule_has_no_condition_weights` | 1414 |
| `test_candidate_summary_non_certainty_lanes_return_null_certainty_summary` | 1510 |
| `test_candidate_summary_certainty_null_for_multiple_rule_ref_edges` | 1602 |
| `test_candidate_summary_certainty_null_for_nested_referenced_support` | 1696 |
| `test_candidate_summary_certainty_null_for_unresolved_child_support` | 1793 |

**同时补齐（P1 coverage gap）**：

- `test_derive_certainty_summary_rejects_invalid_tree_dict_type`
- `test_derive_certainty_summary_rejects_invalid_condition_weights_type`
- `test_condition_weight_rejects_non_numeric_value`
- `test_condition_weight_rejects_non_positive_or_non_finite_value`
- `test_tri_state_lookup_none_vs_empty_vs_populated`（显式验证三态语义）
- `test_condition_confidence_fallback_field`（验证 `confidence` fallback）

**提取共享 fixture → `_test_helpers.py`**：

- `User` entity class（原 L151-156）
- `_register_exposed_user_tag_rule()`（原 L158-177）
- `_schema_ir()`（原 L9510-9556）
- `_seed_users_for_syntax_matrix()`（原 L10267-10287）

`Account` 未提取：它只被 residual core/entity docstring test 使用，继续留在 `test_phase3_contracts_v1.py`。

### 5.3 Phase 2：Evidence Tree + Rule-Trace Explain

**抽出 → `test_evidence_tree_explain_contracts.py`**：

| 原始 test method | 原始行号 |
|-----------------|---------|
| `test_recursive_candidate_evidence_tree_round_trips_through_audit_and_static` | 1861 |
| `test_runtime_service_explain_support_and_rule_trace` | 1957 |
| `test_runtime_explain_ref_candidate_assertion_and_rule_run` | 2056 |
| `test_native_candidate_evidence_tree_runtime_audit_and_static` | 2189 |
| `test_native_candidate_evidence_tree_v2_emits_rule_ref_section_only_when_present` | 2346 |
| `test_runtime_rule_run_explain_ref_is_canonical_and_locks_stable_shape` | 2411 |
| `test_runtime_rule_run_explain_summary_is_pure_derivation_from_raw_payload` | 2529 |
| `test_audit_rule_trace_summary_matches_runtime_summary_contract` | 2649 |
| `test_rule_run_narrative_is_deterministic_from_summary` | 2751 |
| `test_rule_run_nl_explain_is_deterministic_from_summary_and_narrative` | 2793 |
| `test_candidate_evidence_tree_summary_narrative_and_nl_are_deterministic_for_native_tree` | 3018 |
| `test_candidate_evidence_tree_summary_narrative_and_nl_are_deterministic_for_degraded_tree` | 3240 |
| `test_runtime_explain_ref_candidate_degraded_for_engine_and_legacy_none` | 7083 |
| `test_engine_candidate_evidence_tree_round_trips_through_audit_and_static` | 7205 |
| `test_runtime_explain_ref_route_http_200_and_shape_errors` | 7349 |

### 5.4 Phase 3：Remaining Capability Lines

**3a → `test_domain_walkthrough_contracts.py`**（11 tests）：
所有 `_walkthrough_` 命名的 test + 对应的 `_*_schema_ir()` helpers。

**3b → `test_ecss_compliance_contracts.py`**（11 tests）：
ECSS VCD/temporal/uncertainty helpers、scenario-A、compliance matrix、audit static site、SDK requirement bundle。

**3c → `test_winning_branch_rule_trace_contracts.py`**（10 tests）：
Winning branch 6 tests + rule-ref-edge + rule-trace artifact round-trip 3 tests + unresolved rule-ref-edge terminal node。

**3d → `test_artifact_sidecar_contracts.py`**（11 tests）：
File sidecar R/W/GC、store sidecar、SDK cross-instance readback、runtime artifact store root、audit-package export、candidate-support-backrefs。

**残留在 `test_phase3_contracts_v1.py`**：
core entity/schema/query/derivation/temporal/rule-DSL 相关的 ~19 tests + `_seed_users_for_syntax_matrix` 等被多文件共享的 fixtures（如果 Phase 1 已提取到 `_test_helpers.py` 则可留 import）。

### 5.5 共享 Test Helper Module

`_test_helpers.py`（前缀 `_` 表示非 test-discoverable）：

```python
"""Shared fixtures for factpy_kernel contract tests.

NOT a test file — prefixed with _ to avoid unittest discovery.
"""

from factpy_kernel.core.derivation.candidates import CandidateSet, CONFIDENCE_KINDS
from factpy_kernel.core.schema import Entity
# ... other common imports

class User(Entity):
    """A user in the system."""
    name: str
    tag: str

def _register_exposed_user_tag_rule(sdk, *, registry_root=None):
    ...

def _schema_ir() -> dict[str, object]:
    ...

def _seed_users_for_syntax_matrix(sdk) -> dict[str, str]:
    ...
```

提取原则：
- 被 ≥2 个目标文件消费的 fixture 才提取
- 只被 1 个文件消费的 helper 跟着那个文件走
- 不做 pytest fixture 化（保持 unittest 风格）

## 6. Boundaries And Invariants

- **零行为变更**：每个 phase 只做 move + import 调整，不改测试逻辑（补齐新 test 除外）
- **全量 green**：每个 phase 结束后 `python -m unittest discover -s src/factpy_kernel/tests -p 'test_*.py'` 必须 OK
- **不改已有文件**：不触碰 `test_declaration_metadata_v1.py`、`test_core_annotation_certainty.py` 等已有的独立测试文件
- **不消除 private API 调用**：`store._remember_*` 等调用原样搬迁，不做 public API 化
- **文件命名**：新文件遵循 `test_<capability_line>_contracts.py` 命名；helper module 用 `_test_helpers.py`（前缀 `_` 避免 discover）
- **Import 风格**：各文件独立 import，不引入 conftest 或 pytest fixture 机制

## 7. Acceptance

- [x] Phase 1 完成：`test_certainty_explain_contracts.py` 包含 9 个迁移 test + 6 个新增 test，全量 206 tests green
- [x] Phase 2 完成：`test_evidence_tree_explain_contracts.py` 包含 15 个迁移 test，全量 206 tests green
- [x] Phase 3 完成：4 个新文件各自包含对应迁移 capability line tests，全量 206 tests green
- [x] `test_phase3_contracts_v1.py` 缩减至 ≤2,500 行（当前 `1,166` 行，`28` 个残留 tests）
- [x] `_test_helpers.py` 存在且被 ≥2 个文件 import
- [ ] 没有越过 blueprint 明示的边界

## 8. Implementation Plan

### Phase 1（本轮实施）

1. **[tests/_test_helpers.py]** 创建共享 fixture module：提取 `User`、`_register_exposed_user_tag_rule`、`_schema_ir`、`_seed_users_for_syntax_matrix`
2. **[tests/test_certainty_explain_contracts.py]** 创建新文件：
   - 迁移 9 个 certainty/confidence test methods（L1028–L1860）
   - 新增 6 个 coverage gap tests（ValueError×4 + tri-state×1 + confidence-fallback×1）
   - 从 `_test_helpers` import 共享 fixtures
3. **[tests/test_phase3_contracts_v1.py]** 删除已迁移的 9 个 methods + 不再被引用的 local helpers
4. **验证** `python -m unittest discover` 全量 green，test count = 200 + 6 = 206

### Phase 2

5. **[tests/test_evidence_tree_explain_contracts.py]** 创建新文件：迁移 15 个 evidence-tree + rule-trace + explain tests
6. **[tests/test_phase3_contracts_v1.py]** 删除已迁移的 15 个 methods
7. **验证** 全量 green，test count 不变（206）

### Phase 3

8. **[tests/test_domain_walkthrough_contracts.py]** 迁移 11 个 walkthrough tests + 对应 schema IR helpers
9. **[tests/test_ecss_compliance_contracts.py]** 迁移 11 个 ECSS tests
10. **[tests/test_winning_branch_rule_trace_contracts.py]** 迁移 10 个 winning-branch + rule-trace tests
11. **[tests/test_artifact_sidecar_contracts.py]** 迁移 11 个 sidecar tests
12. **[tests/test_phase3_contracts_v1.py]** 清理：删除已迁移 methods + 不再被引用的 helpers
13. **验证** 全量 green，test count 不变（206），残留文件 ≤2,500 行

## 9. Docs To Update

- 无模块文档变更（纯测试结构重组）
- `docs/README.md` 不变（无新持久入口）

## 10. Outcome / Deviations

- 当前进度：
  - Phase 1 已落地：
    - 新增 `src/factpy_kernel/tests/_test_helpers.py`
    - 新增 `src/factpy_kernel/tests/test_certainty_explain_contracts.py`
    - `test_phase3_contracts_v1.py` 已删除 9 个 certainty/confidence tests，并改为 import shared helpers
    - 全量回归 `206` tests green
  - Phase 2 已落地：
    - 新增 `src/factpy_kernel/tests/test_evidence_tree_explain_contracts.py`
    - `test_phase3_contracts_v1.py` 已删除 15 个 evidence-tree / rule-trace / explain route tests
    - `test_phase3_contracts_v1.py` 缩减到 `7,857` 行
    - 全量回归 `206` tests green
  - Phase 3 已落地：
    - 新增 `src/factpy_kernel/tests/test_domain_walkthrough_contracts.py`
    - 新增 `src/factpy_kernel/tests/test_ecss_compliance_contracts.py`
    - 新增 `src/factpy_kernel/tests/test_winning_branch_rule_trace_contracts.py`
    - 新增 `src/factpy_kernel/tests/test_artifact_sidecar_contracts.py`
    - walkthrough helpers 和 `_seed_ecss_compliance_facts` 已随对应 capability line 迁移
    - `test_phase3_contracts_v1.py` 现仅保留 `28` 个 core entity/schema/query/derivation/temporal/rule-DSL tests
    - residual 文件收缩到 `1,166` 行
    - 全量回归 `206` tests green
- 与 blueprint 不同的地方：
  - `Account` 没有提取进 `_test_helpers.py`
  - `test_evidence_tree_explain_contracts.py` 中的 fake Souffle evaluator cleanup 改为恢复真实 `evaluate_store_engine`，而不是清空为 `None`
  - Phase 3 的实际迁移数量高于初始估算：`test_winning_branch_rule_trace_contracts.py` 最终承接 `14` 个 tests，`test_ecss_compliance_contracts.py` 承接 `14` 个 tests，`test_artifact_sidecar_contracts.py` 承接 `12` 个 tests
  - walkthrough capability line 依赖的一组 module-level predicate-id constants 起初被误带到 artifact-sidecar 文件，随后回迁到 `test_domain_walkthrough_contracts.py`
- 为什么会有这些调整：
  - `Account` 目前只被 residual core/schema docstring tests 消费，提前共享只会扩大 helper 面
  - Phase 2 抽出后，文件 discover 顺序变化暴露了全局 engine evaluator 的顺序依赖；恢复真实 evaluator 可以保持 suite 对文件顺序不敏感
  - Phase 3 的真实 contiguous block 边界包含若干相邻的 support/rule-trace/legacy-package tests；与其再做人工二次切分，直接按 capability line 收拢到新文件更稳妥
  - walkthrough constants 本质上属于 domain walkthrough fixture 面，保留在 artifact-sidecar 文件会造成作用域错误
- 归档说明：
  - blueprint 已完成，实现与测试已收口，可归档
