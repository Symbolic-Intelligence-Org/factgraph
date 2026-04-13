# ephemeral-rule-authoring

- Status: implemented
- Created: 2026-03-31
- Parent: llm-integration-surface

## 1. Problem

LLM agentic 场景需要"生成规则 → 验证 → 注册 → 评估 → 观察 explain"的闭环。当前规则注册是编译期的：每次 `run_runtime_rule()` / `evaluate_runtime_derivation()` 都从 filesystem 冷启动一个新的 `RuleRegistry()`，没有 session 级别的规则存储。LLM 无法在不写文件的前提下动态注册试验性规则。

## 2. Goal

在 `RuntimeSession` 上增加 `ephemeral_rules` 存储，提供：

1. `POST /sessions/{id}/ephemeral-rules` — 编译并注册一条 ephemeral rule
2. `GET /sessions/{id}/ephemeral-rules` — 列出当前 session 的 ephemeral rules
3. `DELETE /sessions/{id}/ephemeral-rules` — 清空 ephemeral rules
4. 评估时 ephemeral rules 与 FS rules 合并，参与 `run_runtime_rule` / `evaluate_runtime_derivation`

## 3. Non-Goals

- 不持久化 ephemeral rules（session 关闭即丢弃）
- 不支持跨 session 共享 ephemeral rules
- 不改变 FS rule 的注册/版本控制机制
- 不实现 ephemeral rule 的 "override FS rule" 语义（重复 key 以 FS 优先、静默 skip 处理；ephemeral rule 不覆盖同名 FS rule）
- 不修改 SouFFle / ProbLog 引擎（ephemeral rules 只对 native rule evaluation 生效）

## 4. Current Context

**RuleRegistry（`rule_ir.py`，line ~49–65）**

```python
class RuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[tuple[str, str], RuleSpec] = {}

    def register(self, rule_spec: RuleSpec) -> None:
        key = (rule_spec.rule_id, rule_spec.version)
        if key in self._rules:
            raise RuleCompileError(f"duplicate rule registration: ...")
        self._rules[key] = rule_spec
```

纯内存对象，每次 evaluate 调用新建，无状态残留。

**RuntimeSession（`runtime_v1.py`，line ~102–111）**

```python
@dataclass
class RuntimeSession:
    session_id: str
    store: Store
    ledger_path: str | None
    registry_root: str | None
    schema_digest: str
    opened_at_ns: int
    views: dict[str, ViewSpec]
    derivation_recipes: dict[str, RuntimeDerivationRecipe] = field(default_factory=dict)
```

目前无规则存储，只有 `derivation_recipes`（评估结果缓存）。

**评估时规则加载（`runtime_v1.py`）**

`run_runtime_rule()`（line ~973）:
```python
active_registry = RuleRegistry()
_load_registered_rules(active_registry, registry_root)  # 从 FS 加载
run_rule(session.store, rule_spec, active_registry)
```

`evaluate_runtime_derivation()`（line ~1031–1035）:
```python
if registry_root is not None:
    active_registry = RuleRegistry()
    _load_registered_rules(active_registry, registry_root)
```

两处都在 evaluate-time 新建 registry；ephemeral rules 的注入点在 `_load_registered_rules` 调用之后。

**`compile_authoring_rule_v1()`** 已完整，接受 normalized dict，返回包含 `rule_id/version/select_vars/where/expose` 的 compiled spec（`rules_v1.py` 也有 validate endpoint）。

## 5. Design

### 5.1 RuntimeSession 扩展

```python
@dataclass
class RuntimeSession:
    ...
    derivation_recipes: dict[str, RuntimeDerivationRecipe] = field(default_factory=dict)
    ephemeral_rules: list[RuleSpec] = field(default_factory=list)   # ← 新增
```

### 5.2 新增函数 `_apply_ephemeral_rules(registry, session)`

```python
def _apply_ephemeral_rules(registry: RuleRegistry, session: RuntimeSession) -> None:
    """Merge session ephemeral rules into an active registry after FS rules are loaded."""
    for rs in session.ephemeral_rules:
        try:
            registry.register(rs)
        except RuleCompileError:
            # duplicate with FS rule — skip silently (FS wins)
            pass
```

调用点：

- `run_runtime_rule`：在 `_load_registered_rules(...)` 调用之后追加 `_apply_ephemeral_rules(active_registry, session)`
- `evaluate_runtime_derivation`：两种情况：
  - `registry_root is not None`：在 `_load_registered_rules(...)` 调用之后追加（正常路径）
  - `registry_root is None`：**当 `session.ephemeral_rules` 非空时**，新建一个空 `RuleRegistry()` 并注入（而非跳过）；否则保持现状（`active_registry = None`）

> **已决策**：ephemeral rule 与 FS rule 重名时，FS rule 优先（skip，不 raise）。

### 5.3 `register_ephemeral_rule(session_id, dto)`

```python
def register_ephemeral_rule(session_id: str, dto: dict) -> dict:
    session = _require_session(session_id)          # 复用现有 helper（非 _get_session）
    rule_raw = dto.get("rule", {})
    normalized = _normalize_rule_dto(rule_raw)      # 复用 run_runtime_rule() 现有 DTO 规范化逻辑
    where_ir = _json_where_to_ir(normalized["where"])
    compiled = compile_authoring_rule_v1(
        {**normalized, "where": list(where_ir)},
        schema_ir=session.store.schema_ir,
    )
    rs = RuleSpec(
        rule_id=str(compiled["rule_id"]),
        version=str(compiled.get("version", "v1")),
        select_vars=list(compiled["select_vars"]),
        where=list(compiled["where"]),
        expose=bool(compiled.get("expose", False)),
    )
    session.ephemeral_rules.append(rs)
    return {"rule_id": rs.rule_id, "version": rs.version, "status": "registered",
            "total_ephemeral": len(session.ephemeral_rules)}
```

### 5.4 HTTP 端点（`app_v1.py` 路由 + `runtime_v1.py` handler）

Handler 函数（`register_ephemeral_rule` / `list_ephemeral_rules` / `clear_ephemeral_rules`）落在 `runtime_v1.py`；HTTP 路由注册落在 `app_v1.py`，与现有 `/sessions` 路由族保持一致，**不放在 `rules_v1.py`**（后者是全局 validate/preview，不是 session-bound 生命周期入口）。

```
POST   /sessions/<session_id>/ephemeral-rules    → register_ephemeral_rule()
GET    /sessions/<session_id>/ephemeral-rules    → list_ephemeral_rules()
DELETE /sessions/<session_id>/ephemeral-rules    → clear_ephemeral_rules()
```

`list_ephemeral_rules()` 返回 `[{"rule_id": ..., "version": ...}]`。
`clear_ephemeral_rules()` 清空 `session.ephemeral_rules`，返回 `{"cleared": N}`。

## 6. Implementation Plan

| Step | 文件 | 内容 | 估计 LOC |
|------|------|------|---------|
| 1 | `runtime_v1.py` | `RuntimeSession` 增加 `ephemeral_rules` 字段 | ~3 |
| 2 | `runtime_v1.py` | `_apply_ephemeral_rules()` helper | ~12 |
| 3 | `runtime_v1.py` | `run_runtime_rule` + `evaluate_runtime_derivation` 各加一行调用 | ~4 |
| 4 | `runtime_v1.py` | `register_ephemeral_rule()` / `list_ephemeral_rules()` / `clear_ephemeral_rules()` | ~50 |
| 5 | `app_v1.py` | 3 条 HTTP 路由注册 | ~15 |
| 6 | `tests/test_ephemeral_rule_authoring.py` | 新建测试文件 | ~80 |

总变更：~165 LOC，1 个主文件 + 1 个测试文件。

## 7. Acceptance Criteria

- [x] AC1：`POST /sessions/{id}/ephemeral-rules` 接受合法 DTO，返回 `{"status": "registered", "rule_id": ..., "version": ...}`
- [x] AC2：注册后，`run_runtime_rule` 对该规则的引用可以正常解析（不再 `unknown RuleRef`）
- [x] AC3：注册后，`evaluate_runtime_derivation` 在 `mode="native"` 且 derivation/where 使用 ruleref 时，ephemeral rule 参与推导，结果与手动写文件等价；Souffle / ProbLog / PyReason 路径不承诺 ephemeral rules 生效
- [x] AC4：FS 已有同名规则时，ephemeral rule 被静默忽略（FS 优先，不 500）
- [x] AC5：`DELETE /sessions/{id}/ephemeral-rules` 后，ephemeral rules 不再参与评估
- [x] AC6：session 关闭后 ephemeral rules 消失（内存生命周期，无 ledger 残留）
- [x] AC7：全量测试 green（落地时 `python -m unittest discover -s src/factpy_kernel/tests` 共 731 tests）

## 8. Decisions

- D1（duplicate-skip 语义）：FS 优先，静默 skip。ephemeral rule 与 FS rule 重名时不 raise，也不覆盖。已体现于 Non-Goals §3 和 Design 5.2。
- D2（`registry_root is None` 时的 ephemeral rules）：当 `session.ephemeral_rules` 非空时，即使 `registry_root is None` 也创建一个空 `RuleRegistry()` 并注入。已体现于 Design 5.2 调用点说明。

## 9. Outcome

最终落地结果：

- `RuntimeSession` 增加 `ephemeral_rules: list[RuleSpec]`
- `_apply_ephemeral_rules()` 在 `run_runtime_rule` 与 native `evaluate_runtime_derivation` 中 merge session-scoped rules
- 新增 runtime handlers：
  - `register_ephemeral_rule()`
  - `list_ephemeral_rules()`
  - `clear_ephemeral_rules()`
- 新增 HTTP routes：
  - `POST /v1/runtime/sessions/{session_id}/ephemeral-rules`
  - `GET /v1/runtime/sessions/{session_id}/ephemeral-rules`
  - `DELETE /v1/runtime/sessions/{session_id}/ephemeral-rules`
- 测试覆盖了 register/list/clear、session isolation、FS 优先、native `run`/`evaluate`、以及 `evaluate -> accept -> explain-steps` 端到端链路

与 blueprint 不同的地方：

- 测试文件最终不止骨架，而是直接补齐了 AC2 / AC3 / Milestone B end-to-end 覆盖
- `run_runtime_rule` / `evaluate_runtime_derivation` 的实现继续复用现有 DTO 规范化 helper，没有额外引入新的 `_normalize_rule_dto()` 公开函数

为什么会有这些调整：

- MB-3 需要真实验证 `evaluate -> accept -> explain-steps`，否则母蓝图的 agentic-ready 结论只是代码推断
- 复用既有 helper 可以减少 surface 扩张，保持 runtime_v1 局部改动

归档说明：

- 子蓝图完成后归档到 `docs/blueprints/archive/2026-03-31_ephemeral-rule-authoring.md`
- 对应 audit 一并归档；母蓝图 Milestone B 关闭
