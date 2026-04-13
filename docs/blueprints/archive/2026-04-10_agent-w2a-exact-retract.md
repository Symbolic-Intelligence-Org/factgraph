# Blueprint: Agent W2a — 精确撤回

- Status: implemented
- Created: 2026-04-10
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Depends on: Layer 3A 结构化最小写入 (implemented, archived)
- Related Modules:
  - `src/factpy_kernel/agent/tools/_runtime_api.py` (扩展)
  - `src/factpy_kernel/agent/tools/write.py` (扩展)
  - `src/factpy_kernel/agent/orchestrator.py` (扩展)
  - `src/factpy_kernel/agent/framework.py` (扩展)

---

## 0. 目标与边界

**交付目标**：agent 能对指定 `asrt_id` 执行精确撤回，经确认后调用 `retract_runtime_fact`，成功后 checkpoint。

**冻结决策**：

| # | 决策 | 理由 |
|---|------|------|
| W2a-01 | 只做 exact asrt_id retract，不做 semantic retract | 语义撤回依赖 assertion→candidate 反向索引 + TMS，均不存在 |
| W2a-02 | retract 必须 explicit confirm，agent 不可自主撤回 | 撤回是高危操作；审计场景下必须有确认链 |
| W2a-03 | 不做下游影响评估 (dependency scan / cascade marking) | v1.1-delta 明确 W2b 后移到 P2/P3 |
| W2a-04 | retract 前展示目标 assertion 全貌供用户确认 | 用户必须看到"将要撤回什么"才能做出决定 |

**明确排除**：
- 语义撤回（"删掉张三的年龄"→自动查找匹配 claim）
- 下游影响评估（"撤回这条事实会影响哪些推导"）
- 级联撤回 / Truth Maintenance
- 批量撤回

---

## 1. RuntimeAPI Protocol 扩展

```python
# 追加到 RuntimeAPI Protocol
class RuntimeAPI(Protocol):
    # ... Layer 1 + 2 + 3A existing methods ...

    def retract_fact(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
        """
        对齐 retract_runtime_fact(session_id, dto)。

        dto 结构 (runtime_v1.py:259):
        {
            "asrt_id": str,       # 必填，要撤回的 assertion ID
            "meta": {             # 可选
                "source": str,
                "source_loc": str,
                "trace_id": str,
                "note": str,
                "approved_by": str,       # agent 层写入：人类确认者或 agent_id
                "agent_executor": str,    # agent 层写入：仅当 confirmed_by != agent_id
                # 自定义 meta
            }
        }

        返回: ok_response(write={kind: "retract", assertion_id: revoker_id})
        错误: error_response([{kind, path, details}])

        幂等：同一 asrt_id 重复撤回返回已有 revoker ID。
        """
        ...
```

### 1.1 LocalRuntimeAPI / HttpRuntimeAPI 扩展

```python
# LocalRuntimeAPI
def retract_fact(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    return runtime_v1.retract_runtime_fact(session_id, dto)

# HttpRuntimeAPI
def retract_fact(self, session_id: str, dto: dict[str, Any]) -> dict[str, Any]:
    return self._post_json(f"/sessions/{session_id}/writes/retract", dto)
```

---

## 2. 数据模型

```python
@dataclass
class RetractRequest:
    """Agent 构造的精确撤回请求。"""
    asrt_id: str                                # 要撤回的 assertion ID
    note: str | None = None                     # 撤回原因
    confirmed_by: str | None = None             # 人类确认者
    trace_id: str | None = None                 # 关联批次（可选）

    def to_dto(self, *, agent_id: str) -> dict[str, Any]:
        """生成传给 RuntimeAPI.retract_fact 的 DTO。"""
        meta: dict[str, Any] = {}
        meta["approved_by"] = self.confirmed_by or agent_id
        if self.confirmed_by and self.confirmed_by != agent_id:
            meta["agent_executor"] = agent_id
        if self.note:
            meta["note"] = self.note
        if self.trace_id:
            meta["trace_id"] = self.trace_id
        dto: dict[str, Any] = {"asrt_id": self.asrt_id}
        if meta:
            dto["meta"] = meta
        return dto


@dataclass
class RetractResult:
    """撤回成功的结构化返回。"""
    revoked_asrt_id: str                        # 被撤回的原 assertion ID
    revoker_asrt_id: str                        # 新创建的 revoker assertion ID


@dataclass
class RetractError:
    """撤回失败的结构化返回（不抛异常）。"""
    asrt_id: str
    error_kind: str
    error_message: str
```

---

## 3. WriteTools 扩展

```python
class WriteTools:
    # ... Layer 3A existing methods ...

    def retract(self, request: RetractRequest) -> RetractResult | RetractError:
        """
        精确撤回单条 assertion。

        步骤：
        1. runtime_api.retract_fact(runtime_session_id, request.to_dto(agent_id=...))
        2. 检查 response["ok"]
           - True: RetractResult(revoked_asrt_id=request.asrt_id,
                                  revoker_asrt_id=response["write"]["assertion_id"])
           - False: RetractError(asrt_id, error_kind, error_message)

        幂等：同一 asrt_id 重复撤回时 runtime 返回已有 revoker ID，
        此方法仍返回 RetractResult（不报错）。
        """
        ...
```

---

## 4. Orchestrator 扩展

```python
class ReadReviewOrchestrator:
    # ... Layer 2 + 3A existing methods ...

    # ── W2a: Exact Retract ──

    def preview_retract(self, asrt_id: str) -> ClaimResult | None:
        """
        撤回前预览：展示目标 assertion 的全貌。

        实现策略（W2a-09 冻结）：adapter 层全量扫描当前 session claims，
        不新增 runtime endpoint。

        具体步骤：
        1. kg_read_tools.query_claims(session_id, pred_id=None, e_ref=None)
           → 拉取 session 全量 claims
        2. 在 agent 侧按 asrt_id 过滤匹配
        3. 找到: 返回 ClaimResult（含 pred_id, e_ref, rest_terms, meta, is_revoked）
        4. 未找到: 返回 None
        5. 已撤回: 返回 ClaimResult（is_revoked=True）
           → 调用方据此决定是否仍要提交（runtime 的幂等会返回已有 revoker）

        性能注意：全量扫描对大 ledger 有开销。这是 W2a 的可接受权衡——
        按 asrt_id 查询需要新 runtime endpoint，留给后续优化。

        W2a-04 保证：用户确认前必须看到"将要撤回什么"。
        """
        ...

    def confirm_and_retract(
        self,
        asrt_id: str,
        *,
        note: str | None = None,
        confirmed_by: str | None = None,
        trace_id: str | None = None,
    ) -> RetractResult | RetractError:
        """
        确认 + 撤回 + checkpoint。

        完整时序：
        1. Defensive check: preview_retract(asrt_id)
           - None: 返回 RetractError("unknown assertion")
           - is_revoked=True: 仍继续（幂等语义——runtime 返回已有 revoker）

        2. 构造 RetractRequest(asrt_id, note, confirmed_by, trace_id)

        3. write_tools.retract(request)

        4a. RetractResult:
            - _checkpoint()
            - 返回 RetractResult

        4b. RetractError:
            - _checkpoint()（状态可能已变更，defensive checkpoint）
            - 返回 RetractError

        W2a-02 保证：explicit confirm required（调用方在调此方法前已展示 preview 并获取确认）。
        """
        ...
```

### 4.1 为什么不用 DraftManager 管理 retract

Layer 3A 的 FactDraft 是为事实写入设计的（entity_type, pred_id, field_values 等字段）。Retract 只需要一个 `asrt_id`——用 FactDraft 来包装会造成字段语义错配。

W2a 的确认链通过 `preview_retract → [用户确认] → confirm_and_retract` 的调用时序保证，不走 DraftManager。审计信息通过 `meta.approved_by` / `meta.note` / `meta.trace_id` 写入 ledger。

---

## 5. Tool Registry 扩展

Layer 3A 注册了 20 个 tool。W2a 扩展 `build_layer3a_tool_registry()`（W2a-10 冻结），
不新建独立 registry builder。追加 2 个 tool：

```python
"preview_retract":      → orchestrator.preview_retract
"confirm_and_retract":  → orchestrator.confirm_and_retract
```

W2a 总计 22 个 tool（20 Layer 3A + 2 W2a）。

---

## 6. 实现顺序

```
Step 1: RuntimeAPI Protocol 扩展
        → 追加 retract_fact
        → LocalRuntimeAPI / HttpRuntimeAPI 实现
        → 单测

Step 2: 数据模型
        → RetractRequest / RetractResult / RetractError
        → RetractRequest.to_dto() 单测

Step 3: WriteTools.retract
        → 调用 RuntimeAPI + 解析 response + 幂等处理
        → mock RuntimeAPI 单测

Step 4: Orchestrator 扩展
        → preview_retract + confirm_and_retract
        → 集成测试（写入 → 撤回 → 验证 revocation 生效）

Step 5: Tool Registry 扩展
        → 扩展 build_layer3a_tool_registry()（W2a-10 冻结）
        → 22 tool 全量注册验证
```

---

## 7. 目录结构增量

```
src/factpy_kernel/agent/
  ├── tools/
  │   ├── write.py              # (扩展) +RetractRequest/Result/Error +WriteTools.retract
  │   └── _runtime_api.py       # (扩展) +retract_fact
  ├── orchestrator.py            # (扩展) +preview_retract +confirm_and_retract
  └── framework.py               # (扩展) tool registry 22 tools

src/factpy_kernel/tests/
  ├── test_agent_w2a_retract.py         # (新建)
  └── test_agent_w2a_runtime_api.py     # (新建)
```

---

## 8. 验收标准

1. **RuntimeAPI 扩展**：retract_fact 在 LocalRuntimeAPI 和 HttpRuntimeAPI 上均可调用
2. **preview_retract**：能查到已有 assertion 并返回全貌；不存在返回 None；已撤回返回 is_revoked=True
3. **confirm_and_retract**：正常撤回返回 RetractResult（含 revoker_asrt_id）
4. **幂等**：同一 asrt_id 重复撤回返回 RetractResult（不报错）
5. **不存在的 asrt_id**：返回 RetractError（不抛异常）
6. **审计完整**：revoker assertion 的 meta 含 approved_by + note + trace_id
7. **checkpoint**：撤回后自动 checkpoint
8. **W2a-01**：无 semantic retract 路径
9. **W2a-03**：无 dependency scan / impact analysis
10. **Tool 数量**：22 个
11. **单测 + 集成测试**覆盖

---

## 9. 已知约束

1. **preview_retract 使用全量扫描**（W2a-09 冻结）：当前 `query_claims` 不支持按 asrt_id 直接查询。preview_retract 拉取全量 claims 后在 agent 侧过滤。对大 ledger 有性能开销——按 asrt_id 查询的 runtime endpoint 留给后续优化。
2. **retract 不影响 DraftManager 状态**：即使被撤回的 assertion 是由某个 committed draft 写入的，retract 不会回退 draft 状态。draft.status 仍然是 committed。这是正确的——retract 是新的审计事件，不是回滚。
3. **retract 不影响 CandidatePayloadCache**：retract 是对 assertion 的操作，不是对 candidate 的操作。cached candidates 不受影响。
4. **没有 "undo retract"**：retract 是 append-only（创建 revoker assertion）。如果误撤回，需要重新写入一条新 assertion。

---

## 10. Outcome / Deviations

### Delivered

- `src/factpy_kernel/agent/tools/_runtime_api.py`
  - 扩展 `RuntimeAPI` / `LocalRuntimeAPI` / `HttpRuntimeAPI`
  - 新增 `retract_fact()`
- `src/factpy_kernel/agent/tools/write.py`
  - 新增 `RetractRequest` / `RetractResult` / `RetractError`
  - 新增 `WriteTools.retract()`
- `src/factpy_kernel/agent/orchestrator.py`
  - 新增 `preview_retract()`
  - 新增 `confirm_and_retract()`
- `src/factpy_kernel/agent/framework.py`
  - 扩展 `build_layer3a_tool_registry()`
  - Layer 3A/W2a tool 总数扩到 22
- `src/factpy_kernel/agent/docs/README.md`
  - 更新 W2a exact retract 的当前实现文档
- 新增测试：
  - `src/factpy_kernel/tests/test_agent_w2a_runtime_api.py`
  - `src/factpy_kernel/tests/test_agent_w2a_retract.py`

### Key Deviations

1. **revoker meta 的审计验证走 ledger lookup，不走 claims surface**
   - runtime `claims` 视图只暴露 claim assertions；revoker assertion 本身不属于 claim
   - 因此测试里对 `approved_by` / `agent_executor` / `trace_id` 的验证通过 `_require_session(...).store.ledger.find_meta(...)` 完成
   - 结论：采纳；不为 W2a 额外扩展新的 readback endpoint

2. **Layer 3A registry 直接升级到 22 tools**
   - W2a 没有新建独立 registry builder
   - 现有 `build_layer3a_tool_registry()` 继续作为累进 registry 入口，追加 `preview_retract` / `confirm_and_retract`
   - 结论：采纳；与 Layer 1/2/3A 的累进模式保持一致

### Validation

- `python -m py_compile` 覆盖 W2a 变更文件与新增测试：通过
- `python -m unittest src.factpy_kernel.tests.test_agent_w2a_runtime_api src.factpy_kernel.tests.test_agent_w2a_retract`：通过（12 tests）
- `python -m unittest src.factpy_kernel.tests.test_agent_layer2_runtime_api src.factpy_kernel.tests.test_agent_layer2_workflow src.factpy_kernel.tests.test_agent_layer3a_runtime_api src.factpy_kernel.tests.test_agent_layer3a_write src.factpy_kernel.tests.test_agent_w2a_runtime_api src.factpy_kernel.tests.test_agent_w2a_retract`：通过（36 tests）
- `python -m unittest discover -s src/factpy_kernel/tests`：通过（807 tests）
