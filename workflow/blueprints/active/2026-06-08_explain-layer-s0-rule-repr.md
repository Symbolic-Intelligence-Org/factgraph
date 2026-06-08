# Task Blueprint: S0 — Rule.repr Rename

- Status: draft
- Created: 2026-06-08
- Last Updated: 2026-06-08 (scope questions resolved: alpha rename, no compatibility aliases)
- Parent Blueprint: [2026-06-08_explain-layer.md](./2026-06-08_explain-layer.md)
- Related Modules:
  - `src/factgraph/application/protocol/rule.py` (primary)
  - `src/factgraph/application/protocol/evaluate_result.py` (internal caller)
  - `src/factgraph/application/protocol/rule_expr_inspect.py` (public DTO + internal caller)
  - `src/service/runtime_v1.py` (service response)
- Related Docs:
  - [explain-layer-complete-design.zh.md](../../design/design-points/active/explain-layer-complete-design.zh.md) §9 R7
  - [explanation-completion-roadmap.zh.md](../../design/design-points/active/explanation-completion-roadmap.zh.md) D21
- Audit Log:
  - [2026-06-08_explain-layer-s0-rule-repr.audit.md](./2026-06-08_explain-layer-s0-rule-repr.audit.md)

---

## 1. Problem

`Rule.desc` / `Rule.render_desc()` 沿用了"description"语义命名，与本系统统一使用 `repr` 表示"authoring-time 渲染模板"的命名体系不一致。设计决策 R7（`explain-layer-complete-design.zh.md §9`）和 D21（`explanation-completion-roadmap.zh.md`）均已将 `Rule.repr` / `render_repr()` 列为已决待落地。

This is an alpha release surface. S0 does **not** preserve historical `desc` compatibility aliases or old wire keys.

## 2. Goals

1. `Rule.repr: str | None` 成为 canonical dataclass 字段（取代 `desc`）。
2. `Rule.desc` dataclass 字段移除；`Rule(desc=...)` 不再作为兼容构造路径保留。
3. `Rule.render_repr()` 成为 canonical 方法（取代 `render_desc()`）；`render_desc()` 移除。
4. 所有 internal callers 在 `src/` 内更新为 canonical `repr` / `render_repr()`。
5. `OccurrenceInspect.desc_template` 改为 `repr_template`，不保留 alias。
6. evaluate-result dict key `"desc_template"` 改为 `"repr_template"`。
7. service response key `"desc"` 改为 `"repr"`。
8. Shipped tests 更新到 `repr=` / `render_repr()` / `repr_template` / `"repr"`。
9. Shipped docs 更新（`src/factgraph/application/docs/rule.md`、`docs/quickstart/rules.md` 等）。

## 3. Non-goals

- 不修改 `Field(repr=)` / `Identity(repr=)` / `Meta.repr` Schema DSL（S1 slice）。
- 不修改 `EvaluateRow`、`Claim`、`EvidenceRef`（α/β/γ/ζ slices）。
- 不新建 prober 或 `EvidenceTree` 结构（S3 slice）。
- 不修改 `content_digest`（只 hash `ports` + `when`，与 `repr`/`desc` 无关）。
- 不实现 `Explanation.repr_text` 烘焙（S4 slice）。

## 4. Current Context

**Preflight — Shipped State（2026-06-08 source-read）**:

| # | Location | Shipped symbol | Notes |
|---|---|---|---|
| 1 | `rule.py:60` | `desc: str\|None = None` | Dataclass field；`__post_init__` L67 validates non-empty when non-None |
| 2 | `rule.py:94` | `_validate_desc(self.desc, ...)` | Private validator |
| 3 | `rule.py:115-128` | `def render_desc(bindings)` | Canonical method |
| 4 | `rule.py:43` | `_DESC_PORT_RE` | Port interpolation regex |
| 5 | `rule.py:239-247` | `def _validate_desc(desc, port_names)` | Private helper |
| 6 | `evaluate_result.py:827` | `desc=head.desc` | Rule ctor call in internal builder |
| 7 | `evaluate_result.py:952` | `head.render_desc(public_bindings)` | Internal caller |
| 8 | `evaluate_result.py:965` | `"desc_template": result.head.desc` | Dict key in serialization output |
| 9 | `rule_expr_inspect.py:74` | `OccurrenceInspect.desc_template: str\|None` | **Public DTO field** |
| 10 | `rule_expr_inspect.py:302` | `desc_template=rule.desc` | Populate inspect DTO |
| 11 | `rule_expr_inspect.py:151,469-486` | `_render_desc_template()` | Private helper |
| 12 | `service/runtime_v1.py:2498` | `"desc": rule.desc` | Service response dict key |
| 13 | `tests/test_rule.py:102,114` | `desc="..."` | Rule ctor in tests |
| 14 | `tests/test_rule.py:104-105` | `rule.render_desc()` | Method call in tests |
| 15 | `tests/test_evaluate_result.py:1023` | `Rule.render_desc` in docstring | Test comment |
| 16 | `tests/test_application_rule.py:168,172-173` | `desc=`, `render_desc()` | Rule ctor + method in tests |
| 17 | `tests/sdk/test_ruleexpr_inspect.py:44,54` | `desc="..."` | Rule ctor in tests |

**Scope questions (resolved before `scoped`)**:

| ID | Location | Question |
|---|---|---|
| Q-S0-A | `evaluate_result.py:965` `"desc_template"` dict key | **Resolved in S0**: rename to `"repr_template"`; no old key retained. |
| Q-S0-B | `OccurrenceInspect.desc_template` (public DTO field) | **Resolved in S0**: rename to `repr_template`; no deprecated alias retained. |
| Q-S0-C | `service/runtime_v1.py:2498` `"desc"` key | **Resolved in S0**: rename to `"repr"`; no old key retained. |

## 5. Proposed Shape

### Implementation approach for `Rule` (frozen dataclass)

```python
@dataclass(frozen=True)
class Rule:
    id: str
    when: tuple[Atom, ...]
    ports: Mapping[str, Var]
    version: str | None = None
    repr: str | None = None                          # canonical (was: desc)

    def __post_init__(self) -> None:
        # ... existing validation ...
        # Validate repr (was: validate desc):
        _validate_repr(self.repr, port_names=frozenset(frozen_ports))
        # ... rest unchanged ...
```

### Method rename

```python
def render_repr(self, bindings: Mapping[str, Any] | None = None) -> str:
    """Render this rule's repr template."""
    if self.repr is None:
        return ""
    # ... same body as current render_desc ...
```

### Private helper renames (internal only)

- `_validate_desc` → `_validate_repr`
- `_DESC_PORT_RE` → `_REPR_PORT_RE`

### Public / wire rename decisions

Because this is alpha, all known `desc`-named public/wire surfaces move in S0:
- `evaluate_result.py` emits `"repr_template"` instead of `"desc_template"`.
- `OccurrenceInspect` exposes `repr_template` instead of `desc_template`.
- `service/runtime_v1.py` emits `"repr"` instead of `"desc"`.
- No deprecated alias fields or duplicate wire keys are retained.

## 6. Boundaries And Invariants

- `content_digest` hashes `ports` + `when` only — unaffected.
- `Rule.__eq__`/`__hash__` unaffected — renamed metadata field remains outside `content_digest`.
- No new exported symbols; `__all__` unchanged.
- No historical compatibility path: tests and docs must use `repr` naming only.
- **No src/ code edits without authorization** — implementation requires explicit go-ahead per session rule.
- Branch for implementation: `v0.2.0-impl-rule-repr-rename-2026-06-08` (fork from master or blueprint branch per user decision).

## 7. Acceptance

- [ ] `Rule(repr="...")` works
- [ ] `Rule(desc="...")` is no longer used by shipped tests or docs
- [ ] `rule.render_repr({"x": "v"})` renders correctly
- [ ] `render_desc` is no longer used by shipped tests or docs
- [ ] `content_digest` unchanged for same `id/when/ports/version`
- [ ] All shipped tests pass (updated to `repr=` / `render_repr()`)
- [ ] `evaluate_result.py` emits `"repr_template"` and has no `"desc_template"` residual
- [ ] `OccurrenceInspect` uses `repr_template` and has no `desc_template` residual
- [ ] `service/runtime_v1.py` emits `"repr"` for rule template output and has no rule `"desc"` residual
- [ ] `src/factgraph/application/docs/rule.md` updated
- [ ] `docs/quickstart/rules.md` updated

## 8. Implementation Plan

1. Scope freeze → status: scoped
2. Fork impl branch from master or scoped blueprint HEAD
3. Edit `rule.py`: rename field/method/helper surface to `repr` / `render_repr()` / `_validate_repr()` / `_REPR_PORT_RE`
4. Update internal callers: `evaluate_result.py`, `rule_expr_inspect.py`, `service/runtime_v1.py`
5. Update `OccurrenceInspect` to `repr_template`
6. Update all tests
7. Update docs

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `docs/quickstart/rules.md`
- `docs/official/kernel/quickstart/rules-and-inferences.md` (public)

## 10. Outcome / Deviations

任务完成后填写。
