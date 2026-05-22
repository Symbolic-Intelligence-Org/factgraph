# session-agent-inventory

- Status: implemented
- Created: 2026-04-01
- Parent: (none; follow-up to llm-integration-surface)

## 1. Problem

Agentic LLM 在长循环或中断恢复时需要问 session "现在有哪些规则、有哪些候选"。当前有两个缺口：

**缺口 1 — rule inventory**
- `list_ephemeral_rules()` 只回 `{rule_id, version}`，无 rule body
- FS rules 只能通过 `/v1/registry/*` 全局端点发现，不是 session-scoped
- agent 无法问一个端点"这个 session 现在 effective 的规则集是什么"

**缺口 2 — candidate rediscovery**
- `explain_runtime_steps()` 等所有 explain surface 都要求 `candidate_id`
- store 内部已有 `list_candidate_ids()`（`runtime.py` L403），但没有暴露到 service 层
- agent 若丢失 `evaluate` 响应（中断、重启、工具链故障），无法重新找回已有 candidate handles

## 2. Goal

新增两个 session-scoped 端点，让 agent 可以自主做 session inventory：

**G-R：Rule inventory**
`GET /v1/runtime/sessions/{id}/rules`
- 返回 effective rule set = FS rules ∪ ephemeral rules
- 默认只返回 `{rule_id, version, source}` summary（`source = "fs" | "ephemeral"`）
- 可选 `?include_spec=true` 返回完整 rule body（`select_vars`, `where`, `expose`）

**G-C：Candidate inventory**
`GET /v1/runtime/sessions/{id}/candidates`
- 返回 store 内所有已评估的 candidate handles
- 每条包含 `{candidate_id, pred_id, support_kind, confidence_kind}`
- 支持可选 `?pred_id=...` 过滤

## 3. Non-Goals

- 不改变 `list_ephemeral_rules()` 现有响应结构（保持向后兼容）
- 不实现 rule body diff / version history
- 不对 candidate body 做全文检索
- 不改动 FS rule 的写入路径
- 不涉及并发锁（P2-6 已明确 TODO，不在此处处理）

## 4. Design

### 4.1 Rule inventory

handler `get_runtime_session_rules(session_id, include_spec=False)` 在 `runtime_v1.py`：

```
1. _require_session(session_id)
2. 若 session.registry_root is not None：
     用 FileAuthoringRegistry 枚举所有 (rule_id, version)
     可选读 spec body
3. 追加 session.ephemeral_rules，标记 source="ephemeral"
4. 合并去重（FS 优先，ephemeral 同 key 标记 source="ephemeral_shadowed_by_fs"）
5. 返回 {"rules": [...], "total": N, "fs_count": M, "ephemeral_count": K}
```

`include_spec=true` 时每条追加：
```json
{
  "select_vars": [...],
  "where": [...],
  "expose": true
}
```

### 4.2 Candidate inventory

handler `list_runtime_candidates(session_id, pred_id_filter=None)` 在 `runtime_v1.py`：

```
1. _require_session(session_id)
2. session.store.list_candidate_ids() → [candidate_id]
3. 对每个 id 读 store._candidate_support_kind_index / _confidence_kind_index
4. 读 pred_id：需在 store._remember_candidate_support() 时同步写一个
   _candidate_pred_index: dict[str, str]，在此读取
5. 可选过滤 pred_id（filter 在 handler 层做）
6. 返回 {"candidates": [...], "total": N}
```

**数据可用性约束（已核实代码）**
- `support_kind` / `confidence_kind`：已在 `_candidate_support_kind_index` / `_candidate_confidence_kind_index`，直接可用
- `pred_id`：当前 store 无 per-candidate pred 索引；需在 `runtime.py` `_remember_candidate_support()` 追加 `_candidate_pred_index` (~5 LOC store 改动)
- `accepted` 状态：在 Ledger，不在 Store；**初版不提供此字段**，避免引入跨层查询

Candidate meta 字段（每条，初版）：
```json
{
  "candidate_id": "cand_v2:...",
  "pred_id": "researcher:qualifies_grant",
  "support_kind": "native",
  "confidence_kind": "additive"
}
```

### 4.3 Route 归属

两条路由均落在 `app_v1.py`，handler 在 `runtime_v1.py`，和现有 session surface 风格一致。

## 5. Affected Files

| 文件 | 变更 |
|------|------|
| `runtime_v1.py` | 新增 `get_runtime_session_rules()` + `list_runtime_candidates()` |
| `runtime.py` | `_remember_candidate_support()` 追加 `_candidate_pred_index` (~5 LOC) |
| `app_v1.py` | 新增两条 GET route + import |
| `02_runtime_sessions.md` | 新增两个端点文档 |
| `test_session_agent_inventory.py` | 新建测试文件 |

## 6. Implementation Plan

1. `get_runtime_session_rules()` handler — FS 枚举 + ephemeral merge
2. `list_runtime_candidates()` handler — store 调用 + meta 组装
3. `app_v1.py` 路由注册 + import
4. 测试补齐
5. 文档更新

## 7. Acceptance Criteria

**Rule inventory**
- [ ] RI-1：无 `registry_root` 的 session，返回只含 ephemeral rules（若有）的列表
- [ ] RI-2：有 `registry_root` 的 session，返回 FS rules + ephemeral rules 合并列表，各有正确 `source` 标注
- [ ] RI-3：同 `(rule_id, version)` 同时存在于 FS 和 ephemeral，`source` 标注为 `"ephemeral_shadowed_by_fs"`，列表中只出现一次
- [ ] RI-4：`?include_spec=true` 时每条带完整 `select_vars / where / expose` body
- [ ] RI-5：unknown session 返回 `ok=false`，`kind="runtime_session_not_found"`

**Candidate inventory**
- [ ] CI-1：空 session 返回空列表
- [ ] CI-2：evaluate 后，所有产出的 candidate_id 均出现在列表中
- [ ] CI-3：`pred_id` 字段正确（需 store 追加 `_candidate_pred_index`）
- [ ] CI-4：`?pred_id=` 过滤正确，只返回匹配的 candidates
- [ ] CI-5：unknown session 返回 `ok=false`

**回归**
- [ ] REG-1：现有 `list_ephemeral_rules()` 响应结构不变
- [ ] REG-2：全量 test suite green

## 8. Outcome

任务完成后填写：

- 完成日期：2026-04-01
- 与 blueprint 不同的地方：
  - `GET /sessions/{id}/rules` 对 shadowed key 只返回一条 effective inventory 行，并将其 `source` 标记为 `"ephemeral_shadowed_by_fs"`；`ephemeral_count` 只统计实际生效的 session-only ephemeral entries，不重复计入 shadowed 行
  - Candidate inventory v1 维持 store-scoped readback：返回 `{candidate_id, pred_id, support_kind, confidence_kind}`，不追加 accepted/ledger status
- 为什么会有这些调整：
  - 规则 inventory 需要保持“effective rule set”语义，避免同 key 的 FS + ephemeral 在 readback 中重复出现
  - accepted 状态属于 ledger 层；本任务刻意保持 session inventory 不跨层查询，避免把 store/session readback 和 ledger 状态耦合在一起
- 归档说明：
  - 代码、tests、`02_runtime_sessions.md` 已同步；定向 `test_session_agent_inventory` 与全量 suite 均通过后归档
