# ephemeral-rule-hardening

- Status: implemented
- Created: 2026-04-01
- Parent: (none; follow-up to llm-integration-surface)

## 1. Problem

当前 ephemeral rule 注册和错误反馈存在三处语义漏洞，在 agentic loop 中会产生误导行为：

**P1-1 注册不幂等**
`register_ephemeral_rule()` 对相同 `(rule_id, version)` 始终 append，`_apply_ephemeral_rules()` 在评估时跳过重复项（静默）。结果：agent 重试注册 → `total_ephemeral` 累增 → `list_ephemeral_rules()` 显示两条 → 但实际只用第一条。Agent 误以为规则已更新，实际上没有。

**P1-2 注册成功不等于可用**
`register_ephemeral_rule()` 调用 `compile_authoring_rule_v1()`，只做结构校验，不检查 `pred_id` 是否在 `schema_ir` 中存在。注册 `missing:pred` 返回 `ok=True, status="registered"`，首次 `run_runtime_rule()` 才失败，错误来自 `_eval_pred_atom()`。对 autonomous loop 来说：step 2 成功不保证 step 3 能跑。

**P1-3 错误信息不够机器可读**
`exception_to_error()` 把大多数非 facade 异常折叠成 `kind="runtime"`。Agent 需要靠 substring 匹配英文 message（如 `"unknown RuleRef"` / `"unknown predicate in where"`）来判断如何恢复，这对自动化来说既脆弱又不可维护。

## 2. Goal

三点全部在 service 层修复，不改 `compile_authoring_rule_v1` 的全局语义。修复后：

- 重复注册 = upsert replace（agent iterate 的自然语义）
- 含未知谓词的规则在注册时失败，不是评估时失败
- 关键失败路径返回结构化 `error_code` + `remediation_hint`，agent 无需解析英文

## 3. Non-Goals

- 不改 `compile_authoring_rule_v1()` 的全局行为（其他调用点未审视）
- 不加 per-session 并发锁（P2-6，无真实使用面，先 TODO）
- 不实现 rule/candidate inventory endpoints（Blueprint B 跟进）
- 不扩展 `kind` 枚举（保持 `kind="runtime"` 不变，只在 `details` 里加字段）

## 4. Decisions（已冻结，不在实现时重开）

### D1 — 重复注册语义：upsert replace

`register_ephemeral_rule(session_id, dto)` 遇到相同 `(rule_id, version)` 时：
- 移除旧条目，追加新条目
- 返回 `status="replaced"`（区别于首次注册的 `"registered"`）
- `total_ephemeral` 保持 ≤ 注册过的唯一 key 数量

`_apply_ephemeral_rules()` 的 try/except 逻辑不变（仍做 FS 优先保护），但 session 内的列表已保证无重复 key。

### D2 — 谓词存在性校验：注册时 fail

在 `register_ephemeral_rule()` 里，`compile_authoring_rule_v1()` 成功后、append 之前，对 compiled rule 的 where 原子做 pred_id 存在性检查：
- 遍历所有 `pred` 原子（已转 IR），查 `session.store.schema_ir.predicates`
- 发现未知 pred_id → 立即返回错误，不 append
- 不对 `ruleref` 原子做此时检查（ruleref 目标可能是另一条 ephemeral rule，检查时序复杂）

检查辅助函数 `_validate_ephemeral_rule_preds(compiled_where, schema_ir)` 放在 `runtime_v1.py`（私有）。

### D3 — 结构化错误反馈：stable error_code + remediation_hint

对 agentic loop 最常见的失败路径，在 `details` 里加两个稳定字段：

| 场景 | `error_code` | `remediation_hint` | 可选附加字段 |
|------|-------------|-------------------|------------|
| 注册含未知 pred | `"unknown_predicate"` | `"verify_pred_id_via_GET_sessions_schema"` | `"missing_pred_id": "..."` |
| evaluate 遇 unknown ruleref | `"unknown_rule_ref"` | `"register_referenced_rule_first_or_check_fs_registry"` | `"missing_rule_ref": "id@version"` |
| ruleref target 无 expose | `"rule_not_expose"` | `"add_expose_true_to_rule_definition"` | `"rule_ref_id": "..."` |
| 重复 key upsert | 不报错，返回 `status="replaced"` | — | — |

`kind` 字段不变，仍为 `"runtime"` 或 `"rule_ast_validate"`，不新增 kind 值。

## 5. Affected Files

| 文件 | 变更类型 |
|------|---------|
| `runtime_v1.py` | `register_ephemeral_rule()` upsert 逻辑 + D2 校验 + `_apply_ephemeral_rules()` 微调 |
| `runtime_v1.py` | `_validate_ephemeral_rule_preds()` 新增私有函数 |
| `runtime_v1.py` | `run_runtime_rule()` / `evaluate_runtime_derivation()` 错误路径加 `error_code`/`remediation_hint` |
| `test_ephemeral_rule_authoring.py` | 更新 upsert 相关测试 + 新增 D2/D3 覆盖 |

## 6. Implementation Plan

```
Step 1  register_ephemeral_rule() — upsert replace 语义（D1）
        - 注册前查 session.ephemeral_rules 是否有相同 (rule_id, version)
        - 有 → 移除，再 append，返回 status="replaced"
        - _apply_ephemeral_rules() 去掉 try/except（列表已无重复），或保留做 FS 优先保护

Step 2  register_ephemeral_rule() — pred 存在性校验（D2）
        - 新增 _validate_ephemeral_rule_preds(compiled_where, schema_ir) → list[str] 未知 pred
        - 发现未知 → error_response with error_code + remediation_hint + missing_pred_id

Step 3  错误路径结构化（D3）
        - run_runtime_rule() / evaluate_runtime_derivation() 的 except 块
          检查 exception message 分类，包装 details
        - 优先覆盖 unknown_predicate / unknown_rule_ref / rule_not_expose 三种

Step 4  测试
        - test_ephemeral_rule_authoring.py：upsert 测试（register×2 → total=1, status="replaced"）
        - D2：register unknown pred → ok=False, error_code="unknown_predicate", missing_pred_id
        - D3：unknown ruleref → error_code="unknown_rule_ref", remediation_hint
        - D3：ruleref without expose → error_code="rule_not_expose", remediation_hint
        - 回归：所有既有测试 green
```

## 7. Acceptance Criteria

- [x] AC1：重复注册同 `(rule_id, version)` → `total_ephemeral` 不增加，`status="replaced"`
- [x] AC2：`list_ephemeral_rules()` 在 upsert 后只返回一条同 key 条目
- [x] AC3：注册含未知 pred 的规则 → `ok=False`, `details.error_code="unknown_predicate"`, `details.missing_pred_id` 存在
- [x] AC4：evaluate 遇 unknown ruleref → `ok=False`, `details.error_code="unknown_rule_ref"`, `details.remediation_hint` 存在
- [x] AC5：ruleref target 无 expose → `ok=False`, `details.error_code="rule_not_expose"`, `details.remediation_hint` 存在
- [x] AC6：全量测试 green（零回归；`unittest discover` 743 tests）

## 8. Outcome

- 完成日期：2026-04-01
- 与 blueprint 不同的地方：
  - D1 的 upsert replace 最终采用“in-place replace”而非“remove then append”；语义相同，但保留了 session 内现有顺序
  - D3 的 unknown RuleRef 测试需要先注册一条无关 ephemeral rule，确保 evaluate 命中真正的 `unknown_rule_ref` 分支，而不是更早的 “RuleRef execution requires explicit RuleRegistry”
- 为什么会有这些调整：
  - in-place replace 改动更小，且不影响 replace 语义与 AC
  - native derivation 在完全无 registry 时存在更早的 fail-fast 路径，测试必须按真实控制流建前提
- 归档说明：
  - `runtime_v1.py`、相关 service docs 和 `test_ephemeral_rule_authoring.py` 已同步
  - 蓝图归档到 `docs/blueprints/archive/2026-04-01_ephemeral-rule-hardening.md`
