# Task Blueprint: S0 — Rule.repr Alias Migration

- Status: draft
- Created: 2026-06-08
- Last Updated: 2026-06-08
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

## 2. Goals

1. `Rule.repr: str | None` 成为 canonical dataclass 字段（取代 `desc`）。
2. `Rule.desc: str | None` 保留为 deprecated alias 字段（`repr=False, compare=False, hash=False`），在 `__post_init__` 中迁移值并发出 `DeprecationWarning`。
3. `Rule.render_repr()` 成为 canonical 方法（取代 `render_desc()`）。
4. `Rule.render_desc()` 成为 deprecated alias，发出 `DeprecationWarning` 后委托 `render_repr()`。
5. 所有 internal callers 在 `src/` 内更新为 canonical `repr` / `render_repr()`。
6. Shipped tests 更新到 `repr=` / `render_repr()`。
7. Shipped docs 更新（`src/factgraph/application/docs/rule.md`、`docs/quickstart/rules.md` 等）。

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

**Scope questions (must resolve before `scoped`)**:

| ID | Location | Question |
|---|---|---|
| Q-S0-A | `evaluate_result.py:965` `"desc_template"` dict key | wire format key — rename in S0 or defer? |
| Q-S0-B | `OccurrenceInspect.desc_template` (public DTO field) | rename + deprecated alias in S0, or separate slice? |
| Q-S0-C | `service/runtime_v1.py:2498` `"desc"` key | service response key — rename in S0 or defer? |

## 5. Proposed Shape

### Implementation approach for `Rule` (frozen dataclass)

```python
@dataclass(frozen=True)
class Rule:
    id: str
    when: tuple[Atom, ...]
    ports: Mapping[str, Var]
    version: str | None = None
    repr: str | None = None                          # NEW canonical (was: desc)
    desc: str | None = field(default=None,           # DEPRECATED alias
                             repr=False,
                             compare=False,
                             hash=False)

    def __post_init__(self) -> None:
        # ... existing validation ...
        # Deprecated desc migration:
        if self.desc is not None:
            import warnings
            warnings.warn(
                "Rule(desc=...) is deprecated; use Rule(repr=...) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            if self.repr is not None:
                raise RuleValidationError(
                    "Rule: provide repr= or desc= (deprecated), not both"
                )
            object.__setattr__(self, "repr", self.desc)
        # Validate repr (was: validate desc):
        _validate_repr(self.repr, port_names=frozenset(frozen_ports))
        # ... rest unchanged ...
```

### Method deprecation

```python
def render_repr(self, bindings: Mapping[str, Any] | None = None) -> str:
    """Canonical replacement for render_desc()."""
    if self.repr is None:
        return ""
    # ... same body as current render_desc ...

def render_desc(self, bindings: Mapping[str, Any] | None = None) -> str:
    """Deprecated. Use render_repr() instead."""
    import warnings
    warnings.warn(
        "Rule.render_desc() is deprecated; use Rule.render_repr() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return self.render_repr(bindings)
```

### Private helper renames (internal only)

- `_validate_desc` → `_validate_repr`
- `_DESC_PORT_RE` → `_REPR_PORT_RE`

### `OccurrenceInspect.desc_template` (pending Q-S0-B)

If in scope: same pattern — `repr_template: str | None` canonical + `desc_template` deprecated property/field.

### Internal callers (#6, #7, #10, #11, #12)

All updated to canonical `repr` / `render_repr()` / `repr_template` once Q-S0-A/B/C resolved.

## 6. Boundaries And Invariants

- `content_digest` hashes `ports` + `when` only — unaffected.
- `Rule.__eq__`/`__hash__` unaffected — `desc` field excluded via `compare=False, hash=False`.
- No new exported symbols; `__all__` unchanged.
- `DeprecationWarning` is `stacklevel=2` so warning points at call site, not `rule.py`.
- **No src/ code edits without authorization** — implementation requires explicit go-ahead per session rule.
- Branch for implementation: `v0.2.0-impl-rule-repr-alias-2026-06-08` (fork from master or blueprint branch per user decision).

## 7. Acceptance

- [ ] `Rule(repr="...")` works; `Rule(desc="...")` works (with DeprecationWarning)
- [ ] `Rule(repr="...", desc="...")` raises `RuleValidationError`
- [ ] `rule.render_repr({"x": "v"})` renders correctly
- [ ] `rule.render_desc(...)` delegates + issues DeprecationWarning
- [ ] `content_digest` unchanged for same `id/when/ports/version/repr` regardless of deprecated `desc` path
- [ ] All shipped tests pass (updated to `repr=` / `render_repr()`)
- [ ] Q-S0-A/B/C resolved; their acceptance items added here at `scoped`
- [ ] `src/factgraph/application/docs/rule.md` updated
- [ ] `docs/quickstart/rules.md` updated

## 8. Implementation Plan

1. Resolve Q-S0-A/B/C (scope freeze → status: scoped)
2. Fork impl branch from master
3. Edit `rule.py`: add `repr` field, deprecated `desc` field, `render_repr()`, deprecate `render_desc()`, rename private helpers
4. Update internal callers: `evaluate_result.py`, `rule_expr_inspect.py`, `service/runtime_v1.py`
5. Update `OccurrenceInspect` (if Q-S0-B in scope)
6. Update all tests
7. Update docs

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `docs/quickstart/rules.md`
- `docs/official/kernel/quickstart/rules-and-inferences.md` (public)

## 10. Outcome / Deviations

任务完成后填写。
