# runtime-session-schema-readback

- Status: implemented
- Created: 2026-03-31
- Parent: llm-integration-surface (archived)

## 1. Problem

`open_runtime_session()` / `get_runtime_session()` 只返回 `schema_digest`，不返回 `schema_ir` 内容。LLM 在 session 打开后无法自主发现可用的 `pred_id` 列表、各 pred 的 arity、或 arg_specs（名称/类型域）。

这意味着 LLM 必须在外部（系统提示、调用方传入）预先获得 schema 知识，否则无法写出合法的 `["pred", pred_id, [terms...]]` 原子。这是当前 agentic loop 唯一剩余的自描述缺口。

## 2. Goal

新增 `GET /v1/runtime/sessions/{session_id}/schema` 端点，返回 session 绑定的 `schema_ir` 全量内容和 `schema_digest`。

LLM 调用完 `open_runtime_session` 后，可以立刻通过这个端点自主获取 pred_id 列表和 arity，再开始写规则，无需外部预告知。

## 3. Non-Goals

- 不改动 `GET /v1/runtime/sessions/{session_id}` 的返回结构（继续保持轻量 summary）
- 不新增 schema 过滤/查询参数（返回完整 schema_ir 即可）
- 不改动 schema_ir 的序列化格式（直接 dict 返回）
- 不在这个 blueprint 里补充 ephemeral rule body 回读（独立问题）

## 4. Current Context

Session 打开时 `schema_ir` 已绑定在 `session.store.schema_ir`，全程可访问。`get_runtime_session()` 调用 `_session_to_dict()` 时只序列化了 `schema_digest`（一个 str），跳过了完整内容。

`schema_ir` 由 `compile_schema_from_classes()` 或 `load_registry_schema_ir()` 产出，包含：
- `entities[]`：实体名、identity fields、其余 fields
- `predicates[]`：`pred_id`、`arity`、`arg_specs[]`（name + type_domain）

`arg_specs` 是 LLM 写规则时最需要的部分——知道 `researcher:expertise` 的 arity=2、第一个参数是 entity_ref、第二个是 string，才能写正确的 term 列表。

## 5. Implementation Plan

### Step 1 — handler（`runtime_v1.py`）

新增函数 `get_runtime_session_schema(session_id)`，紧贴 `get_runtime_session()` 之后：

```python
def get_runtime_session_schema(session_id: str) -> dict[str, Any]:
    try:
        session = _require_session(session_id)
        return ok_response(result={
            "schema_digest": session.schema_digest,
            "schema_ir": session.store.schema_ir,
        })
    except Exception as exc:
        return error_response([exception_to_error(exc)])
```

### Step 2 — route（`app_v1.py`）

在 import 块加 `get_runtime_session_schema`，在 `GET /sessions/{id}` 路由之后加：

```python
@app.get("/v1/runtime/sessions/{session_id}/schema")
def get_runtime_session_schema_route(session_id: str) -> dict[str, Any]:
    return get_runtime_session_schema(session_id)
```

### Step 3 — docs

更新 `src/factpy_kernel/service/docs/02_runtime_sessions.md`，在 session GET 小节后追加 schema readback 端点说明。

### Step 4 — 测试

在 `tests/test_runtime_session_schema.py`（新文件）或已有 session 测试文件里补充 3 个测试用例（见 §7 AC）。

## 6. Open Questions

（无。实现路径和 schema_ir 可访问性已确认，无需预研。）

## 7. Acceptance Criteria

- [x] SR-1：`GET /v1/runtime/sessions/{id}/schema` 对合法 session 返回 `ok=true`，结果包含 `schema_digest` 和 `schema_ir` 两个字段
- [x] SR-2：`schema_ir.predicates` 列表非空（当 schema 包含 predicates 时），每个条目含 `pred_id` 和 `arg_specs`
- [x] SR-3：对不存在的 `session_id` 返回 `ok=false`，`kind="runtime_session_not_found"`
- [x] SR-4：`GET /sessions/{id}` 原有返回结构不变（无回归）
- [x] SR-5：全量测试 green

## 8. Outcome

- 完成日期：2026-03-31
- 与 blueprint 不同的地方：
  - 测试最终落为 4 个用例而不是最初表述的 3 个；额外补了 `GET /sessions/{id}` 无回归断言，直接覆盖 SR-4
- 归档说明：
  - 代码、测试、`02_runtime_sessions.md` 已同步；子蓝图归档到 `docs/blueprints/archive/2026-03-31_runtime-session-schema-readback.md`
