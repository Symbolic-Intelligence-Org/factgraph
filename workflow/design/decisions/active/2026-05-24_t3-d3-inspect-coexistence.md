# Q3 Decision: T3 RuleExpr Inspect Coexistence

- Status: proposed
- Created: 2026-05-24
- Last Updated: 2026-05-24
- Authority: design constraint; locks `fg.rules.inspect(...)` coexistence and return-shape policy before T3 inspect implementation.
- Inputs:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md` Q3, D2, D6, A10, and R2 amendment.
  - `workflow/design/decisions/active/2026-05-24_t3-d2-join-constraint-construction.md` for the `RuleExprInspect.joins` input DTO shape.
  - Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` C32, C49-C51, C59.
  - Current SDK store inspect implementation in `src/factgraph/sdk/store.py:2088-2089`, `:2907-2964`.
- Outputs / Downstream:
  - T3 inspect DTO blueprint.
  - T3 RuleExpr public surface docs.
  - Stage 3 synthesis slice split.
- Related:
  - `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
  - `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
- Branch: `v0.2.0-t3-ruleexpr-audit-2026-05-24`
- Depends on: none.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

Parent C32 says `fg.rules.inspect(expr)` returns a `RuleExprInspect` object with:

- `ast`
- `occurrences`
- `joins`
- `unjoined_same_name_ports`
- `render()`
- `render_compact()`
- templates and port-visibility convenience

Parent C49-C51 add richer occurrence and atom descriptor requirements. Parent C59 adds `inspect.ports`.

The shipped SDK already has `fg.rules.inspect(...)`, but it is legacy-oriented. Current implementation accepts legacy SDK `Rule` / `Inference` through `SDKStore.inspect_rule`, delegates to `_inspect_rule_or_inference`, and returns dict payloads with branch-level atom metadata. Existing tests assert this branch inspect behavior.

The Stage 1 audit amendment sharpened Q3: T3 must define behavior for three input classes, not just legacy-vs-RuleExpr:

1. Legacy SDK `Rule` / `Inference`
2. Single application `Rule` via C35 coercion
3. Full `RuleExpr`

## 2. Scope

This decision locks:

- Whether `fg.rules.inspect(...)` stays polymorphic.
- Return shape for legacy SDK Rule / Inference.
- Return shape for single application Rule.
- Return shape for RuleExpr.
- Whether `RuleExprInspect` is an object DTO or dict.
- How C35 single-Rule coercion applies to inspect.

## 3. Non-scope

This decision does not lock:

- Exact fields of every nested occurrence / atom descriptor beyond the parent minimum.
- Rendering text format.
- Execution lowering.
- Final T5 top-level `Rule` flip.
- Join constraint syntax.
- Whether single-Rule coercion produces a real transient RuleExpr value or a synthesized inspect-only view; the T3.5 inspect blueprint must choose one while preserving the return-shape contract locked here.
- The migration path for legacy SDK `Inference`; this decision preserves current legacy `Inference` dict inspect behavior but does not decide whether or how `Inference` changes during the future T5 hard-cut.

## 4. Decision

### 4.1 Keep one polymorphic `fg.rules.inspect(...)` entry point

T3 keeps `fg.rules.inspect(...)` as the public inspect entry point.

The method becomes input-polymorphic, with explicit return-shape rules by input class.

### 4.2 Preserve legacy SDK Rule / Inference dict output

For existing legacy SDK `Rule` and `Inference` inputs, `fg.rules.inspect(...)` MUST preserve the current dict return shape.

This keeps branch identity tests and existing docs stable. The legacy path remains governed by current `_inspect_rule_or_inference` behavior.

### 4.3 Application Rule inspect uses RuleExprInspect via C35 coercion

For a single application `Rule`, `fg.rules.inspect(rule)` returns a `RuleExprInspect` object by coercing the Rule into a single-rule RuleExpr.

This honors C35: a single Rule is accepted where RuleExpr is accepted. It also avoids creating a third inspect DTO family.

### 4.4 RuleExpr inspect returns RuleExprInspect

For a RuleExpr input, `fg.rules.inspect(expr)` returns `RuleExprInspect`.

The initial `RuleExprInspect` DTO must include at least:

- `ast`
- `occurrences`
- `joins`
- `unjoined_same_name_ports`
- `render()`
- `render_compact()`

Stage 3 synthesis or the T3 inspect blueprint must decide whether `templates`, `port_visibility`, and `ports` ship in the first inspect slice or a follow-up.

### 4.5 RuleExprInspect is an object DTO, not a dict

`RuleExprInspect` should be a frozen object DTO with methods for render surfaces.

Reason: parent C32 names an object-like inspect result with methods. A dict cannot cleanly expose `render()` / `render_compact()` without a parallel helper API.

### 4.6 Unsupported input types remain explicit errors

Legacy SDK Rule / Inference, application Rule, and RuleExpr are the only supported T3 inspect inputs. Other objects should continue to raise the existing SDK error style.

## 5. Rejected Alternatives

### Option A: Convert legacy inspect to RuleExprInspect

- **Why rejected**: breaks existing branch inspect tests and existing users that consume dict payloads.

### Option B: Add a separate `fg.rules.inspect_expr(...)`

- **Why rejected**: avoids polymorphism but fragments the public API. Parent explicitly names `fg.rules.inspect(expr)`.

### Option C: Return dicts for RuleExpr inspect

- **Why rejected**: conflicts with parent C32 render methods and makes rich descriptors harder to evolve.

### Option D: Make application Rule inspect return legacy dict

- **Why rejected**: conflicts with C35 single-Rule coercion and creates a confusing split where a single application Rule and a RuleExpr over that same Rule inspect differently.

## 6. Supporting Evidence

- Current store inspect entry point is `SDKStore.inspect_rule` at `src/factgraph/sdk/store.py:2088-2089`.
- Current legacy implementation is `_inspect_rule_or_inference` plus `_inspect_where_branches` at `src/factgraph/sdk/store.py:2907-2964`.
- Stage 1 audit Q3 requires three-way input split.
- Parent C32 names `RuleExprInspect` and its core fields/methods.
- Parent C35 requires single Rule accepted where RuleExpr is accepted.

## 7. Consequences

### 7.1 Downstream unblocking

This decision unblocks:

- T3 inspect DTO design.
- T3.5 inspect slice scoping.
- C35 inspect behavior for single application Rules.
- Stage 3 docs plan for legacy-vs-new inspect behavior.

`RuleExprInspect.joins` must consume the `RuleJoinConstraint` shape locked by T3-D2 or a later adopted successor decision. D3 does not redefine join constraints.

### 7.2 Required follow-up actions

The T3 inspect blueprint must:

- Preserve legacy SDK Rule / Inference dict inspect tests.
- Add `RuleExprInspect` DTO tests for application Rule input.
- Add `RuleExprInspect` DTO tests for RuleExpr input.
- Verify unsupported input errors remain explicit.
- Document that legacy Rule inspect and RuleExpr inspect have intentionally different return shapes during the T1.3 staged naming period.

### 7.3 Documentation boundary

Docs must distinguish:

- Legacy inspect: dict payload for legacy SDK Rule / Inference.
- New RuleExpr inspect: `RuleExprInspect` object for application Rule / RuleExpr.

This distinction remains until a future T5 hard-cut or a later decision supersedes this policy.

## 8. Acceptance Criteria

- [ ] Existing legacy branch inspect tests continue to pass unchanged.
- [ ] `fg.rules.inspect(application_rule)` returns `RuleExprInspect`.
- [ ] `fg.rules.inspect(rule_expr)` returns `RuleExprInspect`.
- [ ] `RuleExprInspect.render()` and `.render_compact()` exist.
- [ ] Unsupported inputs raise explicit SDK errors.
- [ ] Docs explain the polymorphic return shape.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-24 | proposed | Decision drafted | Stage 1 audit review requested the three-way inspect input split be made load-bearing before T3 inspect blueprinting. |
