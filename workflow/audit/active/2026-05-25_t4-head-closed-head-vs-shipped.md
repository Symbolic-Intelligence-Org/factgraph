# Stage 1 Audit: T4 Head + Closed-Head vs Shipped Runtime

Status: draft
Date: 2026-05-25
Branch: `v0.2.0-t4-head-closed-head-audit-2026-05-25`
Base commit: `9a4c4ef9` (`docs(memory): consolidate T3 later push gate + T4 next-track selection`)
Class prediction: L cluster; requires Stage 2 decision docs, Stage 3 synthesis, and implementation slices.
Owner split: Codex drafts; Claude reviews.

## 1. Purpose

T3 later is complete and pushed. Human direction selected T4 Head + closed-head as the next track. This audit starts the T4 cycle by comparing the parent Head commitments against shipped T1/T3/T3L runtime behavior.

This is read-only planning work. It does not implement T4, choose final slice boundaries, or reopen T3 later decisions. It identifies gaps, shipped substrate, cross-track boundaries, and Stage 2 questions that must be resolved before any T4 blueprint.

## 2. Audit Scope

In scope:

1. Parent Head commitments C52-C60: first-class `head=Rule`, existing Rule identity, inline port alignment, unrestricted head body grammar, output port shape, `head.desc`, and `Rule.projection(...)`.
2. Parent C72 closed-head inspect utility: `inspect.is_closed`, `inspect.unbound_ports`, and the two-form v1 closedness rule.
3. T3L.3 shipped public RuleExpr execution as the immediate predecessor substrate.
4. T3L.1/T3L.2 private lowering/materialization substrate where it constrains T4 design.
5. Shipped application `Rule`, RuleExpr, inspect, schema identity, and SDK dispatch code.
6. Error boundary questions around `SDKStoreError`, `RuleExprError`, and `RuleValidationError`.
7. Stage 2 decision questions and likely D-doc split.

Out of scope:

1. T4 implementation or blueprint drafting.
2. T5 `EvaluateResult`, `EvaluateRow`, `Explanation`, `WhyNot`, `row.close()`, or evidence graph DTO implementation.
3. Public result-shape replacement for T3L.3 `list[CandidateSet]`.
4. Adapter grammar expansion, PyReason Form 2, or semantics wrapper redesign.
5. T1.3 final legacy `Rule` hard-cut.
6. Push, branch protection, or dirty-worktree changes.

## 3. Canonical Sources Read

| Source | Lines read | Relevance |
|---|---:|---|
| `workflow/memory/current.md` | 1-16, 504-510 | Confirms T3 later push gate executed and T4 selected as next track. |
| `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md` | 210-230 | T4 planned scope and sub-slices. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | 713-923 | Parent §5.0-§5.7 Head commitments C52-C60. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | 1126-1147, 1163-1208 | T5-adjacent closed-head replay, `row.close()`, and Explanation boundary. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | 1535-1571, 1577-1597 | C72 closed-head inspect utility and consolidated C52-C60/C72 commitment table. |
| `workflow/design/decisions/active/2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md` | 120-166 | T3 later minimal head subset and explicit T4 deferrals. |
| `workflow/blueprints/archive/2026-05-25_t3l-3-public-dispatch-diagnostics-docs.md` | 37-111, 176-246 | T3L.3 public dispatch scope and explicit no-full-T4 boundary. |

## 4. Shipped Code Read

| Source | Lines read | Shipped facts relevant to T4 |
|---|---:|---|
| `src/factgraph/application/protocol/rule.py` | 35-39, 47-108, 125-127, 145-185, 226-230 | `Rule` has `version`, `desc`, `content_digest`, `ports`, `port_types`, and occurrence aliases; no `Rule.projection(...)`; occurrence alias regex exists. |
| `src/factgraph/application/protocol/rule_expr.py` | 12-67, 73-152, 182-236, 283-334 | RuleExpr authoring, C35 coercion, identity-by-id/digest canonicalization, join validation, and no `declared_ports` public property. |
| `src/factgraph/application/protocol/rule_expr_inspect.py` | 36-135, 155-172, 189-228, 243-257 | Inspect DTOs expose occurrences, ports, joins, and unjoined same-name port hints; no `is_closed` or `unbound_ports`. |
| `src/factgraph/application/protocol/rule_expr_lowering.py` | 42-188, 219-280, 320-334, 506-536 | Private T3L plan/head-binding substrate; inline head projection by same id+digest; external heads still fail during materialization. |
| `src/factgraph/application/protocol/rule_expr_lowering.py` | 448-482, 528-553 | Join materialization and head var projection require head ports on the inline occurrence. |
| `src/factgraph/sdk/store.py` | 21-41, 120, 419-447, 2210-2387 | Public `fg.eval.evaluate(...)` now dispatches application `Rule` / RuleExpr with required `head=`, rejects external heads, forwards engine options, and returns `list[CandidateSet]`. |
| `tests/sdk/test_rule_expr_evaluate.py` | 59-181 | T3L.3 tests prove public dispatch, missing/invalid `head=`, external-head rejection, adapters, PyReason rejection, and legacy path preservation. |
| `tests/sdk/test_ruleexpr_inspect.py` | 89-113, 173-191 | T3.5 inspect tests prove current inspect shape and absence of closed-head fields. |
| `src/factgraph/sdk/schema.py` | 50-88, 155-199 | SDK schema already records identity fields and `primary_key` flags. |
| `src/factgraph/application/schema_runtime.py` | 13-57, 82-111, 189-222 | Application schema index preserves identity fields, predicates, and primary-key metadata usable by closed-head rules. |

## 5. Executive Findings

### F1 — T3L.3 shipped a minimal public `head=` path, not full T4 Head

`SDKStore.evaluate(...)` now dispatches application `Rule` / RuleExpr inputs before legacy paths and requires `head=` (`store.py:2210-2240`, `2323-2352`). This satisfies the narrow T3 later entrypoint but not parent C52-C60 in full.

The shipped path rejects external heads before materialization (`store.py:2364-2368`). T4 must decide whether to supersede that rejection with body concatenation, keep rejection as a first T4 slice, or split external-head semantics behind a later T4 decision.

### F2 — Application `Rule` is structurally head-ready, but projection sugar conflicts with current shape invariants

`Rule` already has the fields parent Head needs: `id`, non-empty `where`, non-empty `ports`, optional `version`, optional `desc`, deterministic `content_digest`, and inferred `port_types` (`rule.py:47-108`). This is strong substrate for C52, C53, C54, and C60.

However, C56 shows `Rule.projection(...)` as a pure projection helper with an empty `where` example. Shipped `Rule` requires a non-empty `where` tuple and non-empty `ports` mapping (`rule.py:63-66`). T4 must decide whether projection sugar creates a private non-empty placeholder body, relaxes `Rule` validation for projection heads, or changes the parent example's concrete shape.

### F3 — Existing Rule identity is partially shipped; version warning semantics are not

The shipped `Rule` includes `version` (`rule.py:54`) and `content_digest` (`rule.py:101-108`). RuleExpr canonical identity uses `(rule.id, rule.content_digest)` (`rule_expr.py:333-334`), and T3L lowering binds heads by same id + same digest (`rule_expr_lowering.py:506-525`).

Parent C53 also requires version mismatch warning for same id + same digest + different version. There is no shipped warning path in T3L.3. Stage 2 must decide warning mechanics, whether version is included in head identity records, and how this interacts with no-new-public-DTO discipline.

### F4 — `expr.declared_ports` is a design concept, not a shipped API

Parent C54 relies on `expr.declared_ports`. Shipped RuleExpr has operands, joins, canonical forms, and validation (`rule_expr.py:73-152`, `182-236`) but no `declared_ports` public property.

Inspect derives public port descriptors from operand rules (`rule_expr_inspect.py:212-228`) and unjoined same-name hints (`rule_expr_inspect.py:243-257`). Lowering also has per-occurrence port bindings (`rule_expr_lowering.py:42-72`). T4 must choose the canonical source for declared ports, especially when two occurrences expose the same port name with different `PortType` values.

### F5 — Inline head projection is currently same-id/same-digest only

T3L lowering marks a head as inline only when exactly one occurrence has the same rule id and same content digest (`rule_expr_lowering.py:506-525`). Head output vars are then taken from that occurrence's port bindings (`rule_expr_lowering.py:528-536`).

This is narrower than parent C54, which allows inline heads whose port keys are a subset of the expression's declared port namespace and whose internal vars are private. T4 must decide whether "inline head" means same Rule occurrence, a new Rule projected against declared ports, or both.

### F6 — Full C55 head body grammar is not shipped for public execution

Parent C55 says `head.where` has no evaluate-specific grammar restriction. T3L.3 public execution rejects external head bodies and requires the head rule to appear as an expression occurrence (`store.py:2364-2368`). This was intentionally conservative.

T4 owns the unresolved body-concatenation semantics: where to append external head atoms, how to alias their variables, how to prevent leaking internal variable names into port alignment, and whether head body atoms participate in joins, branch alternatives, aggregates, and adapter rejection policy.

### F7 — Closed-head detection has schema substrate but no rule-level algorithm

Schema declarations and runtime indexes preserve primary-key identity metadata (`schema.py:50-88`, `155-199`; `schema_runtime.py:13-57`, `82-111`, `189-222`). This can support C72's entity-ref primary identity rule.

No shipped code computes whether a `Rule` is closed. Inspect has port metadata but no `is_closed` or `unbound_ports` (`rule_expr_inspect.py:89-135`). Stage 2 must lock a closed-head algorithm over core AST (`CmpAtom`, `PredAtom`, literals, identity predicates), including how it receives schema context.

### F8 — Closed-head explanation/replay is T5-adjacent and must stay bounded

Parent §5.8 describes `row.close()`, manual `fg.eval.explain(expr, head=closed_head)`, Explanation envelopes, and failure classes (`rule-expression-and-proof-attempt.zh.md:1126-1208`). Track plan places these larger DTO/API commitments under T5, while T4 specifically owns head + closed-head + projection (`rule-expression-and-proof-track-plan.zh.md:210-230`).

T4 can define closed-head validation and inspect utilities, but it should not ship `EvaluateResult`, `EvaluateRow`, `Explanation`, `row.close()`, or WhyNot behavior unless a later decision explicitly changes the track boundary.

### F9 — Error buckets need fresh T4 alignment

D6 split public call-shape errors into `SDKStoreError` and RuleExpr/head semantic validation into `RuleExprError` (`2026-05-25_t3-later-d6-public-entrypoint-head-dependency.md:156-166`). T3L.3 currently treats missing/invalid `head=` and external-head rejection as `SDKStoreError` (`store.py:2333-2345`, `2364-2368`).

T4 will add semantic cases: stale existing head digest, version mismatch warning, undeclared head port, non-closed head, projection sugar validation, and schema-missing primary identity metadata. These need a reviewed error/warning bucket before implementation.

## 6. Commitment Triage

| Commitment | Parent claim | Shipped state | Stage 2 disposition needed |
|---|---|---|---|
| C52 | `head=` accepts first-class `Rule` only | T3L.3 accepts application `Rule` as `head=` for RuleExpr path; legacy paths remain unchanged | Decide whether T4 broadens this beyond RuleExpr execution or keeps path-specific. |
| C53 | Existing Rule identity uses id + digest; version mismatch warns | id + digest are shipped; version exists; no warning path | Lock warning mechanism and stale-head diagnostics. |
| C54 | `head.ports.keys` strict subset of `expr.declared_ports`; internal vars private | No `expr.declared_ports`; inline projection currently same id + digest | Define declared-port source and alignment semantics. |
| C55 | `head.where` has no evaluate-specific grammar restriction | External head body rejected in T3L.3 | Decide body concatenation / aliasing / adapter boundary. |
| C56 | `Rule.projection(*port_names)` same-name sugar | No method; current `Rule` rejects empty `where` | Decide projection representation under current Rule invariants. |
| C60 | `head.desc` anchors evidence narrative | `Rule.desc` and `render_desc(...)` shipped; no evidence integration | Keep narrative anchor for T5; maybe document head desc guidance in T4. |
| C72 | `inspect.is_closed` and `inspect.unbound_ports` read-only utilities | Inspect DTOs shipped without these fields | Decide DTO extension and shared closed-head validator. |

## 7. Questions Recommended for Stage 2

### Q1 — What is the precise T4 scope after T3L.3?

T3L.3 already shipped minimal public `fg.eval.evaluate(rule_expr_or_application_rule, head=...)`. Does T4 now own all remaining C52-C60 behavior, or only external-head semantics, projection sugar, and closed-head utilities? This should become D11 or equivalent scope/boundary decision.

### Q2 — How should T4 define `expr.declared_ports`?

Possible sources:

- derive from T3.5 `RuleExprInspect.ports`;
- derive from T3L.1 `RuleExprOccurrenceBinding` / `RuleExprPortBinding`;
- add a private helper returning deterministic declared ports;
- expose a new public property or inspect-only field.

The answer affects C54, `Rule.projection(...)`, and closed-head diagnostics.

### Q3 — What are the exact existing-head identity and warning rules?

Parent C53 includes three states: same id+same digest+same version, same id+same digest+different version, and same id+different digest. T4 must lock:

- whether stale same-id different digest raises `RuleExprError` or `SDKStoreError`;
- whether version mismatch warning uses Python `warnings.warn`, SDK warning DTOs, or docs-only behavior;
- whether warnings are emitted in public execution, inspect, projection construction, or all three.

### Q4 — Does T4 implement external head body concatenation?

If yes, Stage 2 must specify where head body atoms enter the T3L plan, how head variables are aliased, and how branch lists, joins, aggregates, and adapter rejection behave. If no, T4 should explicitly keep T3L.3's external-head rejection and limit C55 to a later slice.

### Q5 — What is the concrete shape of `Rule.projection(*port_names)`?

Parent C56's pure projection example conflicts with shipped `Rule(where=...)` non-empty validation. Stage 2 must choose between:

- a generated non-empty body atom;
- a special projection-rule flag/private sentinel;
- relaxing `Rule.where` only for projection heads;
- changing projection sugar to require an expression/context at evaluation time.

### Q6 — What is the closed-head algorithm and schema input?

C72 v1 accepts exactly two closure forms: value port literal binding and entity-ref primary identity literal binding. Stage 2 must lock:

- literal term definition;
- equality direction and `Const` handling;
- how to map entity-ref ports to schema primary identity predicates;
- compound primary identity behavior;
- whether missing schema context yields unsupported, unbound, or validation error.

### Q7 — Where do `is_closed` and `unbound_ports` live?

Parent says inspect-only, not on `Rule` or RuleExpr. Stage 2 must decide whether to extend `RuleExprInspect`, create a `RuleInspect`/head inspect path, add private helper outputs, or add properties computed lazily from existing inspect data.

### Q8 — What are T4 error and warning buckets?

T4 should align with D6/D9 rather than introducing new public subclasses. It needs a bucket table for invalid `head=`, stale head identity, undeclared head ports, projection invalidity, non-closed head, unsupported closed-head pattern, and missing schema metadata.

### Q9 — What is the T4/T5 boundary for closed-head evidence?

T4 should likely define closed-head validation and inspect utility only, while T5 owns `EvaluateResult`, `row.close()`, `fg.eval.explain(...)`, failure classes, and evidence narratives. Stage 2 should make that boundary explicit.

### Q10 — What implementation slice ladder should T4 use?

Track plan proposes T4.1-T4.5. Stage 2 should decide whether to preserve that five-slice split or combine:

- T4.1 head identity/error boundary;
- T4.2 declared ports + inline/external alignment;
- T4.3 projection sugar;
- T4.4 closed-head core validator;
- T4.5 inspect utilities + docs.

## 8. Reviewer Focus Areas

1. Verify the C56 conflict with shipped non-empty `Rule.where` is real and not already solved by a projection-specific helper.
2. Spot-check whether T3L.3 stale same-id/different-digest behavior is merely external-head rejection or has a dedicated stale diagnostic elsewhere.
3. Check whether `expr.declared_ports` appears in any un-read module or docs.
4. Validate the T4/T5 boundary: C72 belongs to T4, while `row.close()` / Explanation DTOs stay T5.
5. Check whether schema primary identity metadata is sufficient for C72's entity-ref closure rule.
6. Confirm T4 should remain L-class and needs Stage 2 D-docs before blueprinting.

## 9. Acceptance Criteria for This Audit

- [x] T4 Human selection and current memory were read.
- [x] Parent C52-C60 and C72 were read and triaged.
- [x] D6 T3-later deferral boundary was read.
- [x] Shipped application Rule, RuleExpr, inspect, lowering, SDK dispatch, tests, and schema identity substrate were read.
- [x] No code implementation or public API mutation was performed.
- [x] At least 8 Stage 2 questions were identified.
- [x] Dirty worktree and sacred branch invariants remain untouched.

