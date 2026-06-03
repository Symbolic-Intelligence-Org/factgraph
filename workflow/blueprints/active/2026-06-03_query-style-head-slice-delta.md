# Task Blueprint: Query-style head Slice δ — `rule.id` decouple + arity opt-in

- Status: draft
- Created: 2026-06-03
- Last Updated: 2026-06-03 (Step 4.1 draft)
- Owner: Claude (blueprint draft) / Codex (review + impl) — Slice 4/5 cross-flip per [[feedback_audit_to_archive_cadence]]
- **Cadence**: tight gates default — δ relaxes a shipped strict invariant (`rule.id` must match schema predicate); preflight will surface cross-engine impact
- Fork base: `dd65e776` (Slice ε Step 4.9 archive HEAD)
- Parent design: [`workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.8 + §6 Slice δ
- Predecessors:
  - α / β / γ / ζ / η / ε (all archived) — DTO surface evolution + evidence model layered hierarchy + walker
- Related Modules:
  - `src/factgraph/core/store/_evaluate.py:148-157` (shipped head lookup + arity check — δ rewrites these to opt-in)
  - `src/factgraph/core/rules/where_eval.py` (where evaluation may also reference head pred lookup)
  - `src/factgraph/application/protocol/evaluate_result.py` (head field on EvaluateResult + Rule)
  - `src/factgraph/sdk/store.py` (SDK `fg.eval.evaluate(...)` entry)
  - `src/service/runtime_v1.py` (service evaluate path)
  - `tests/application/protocol/test_evaluate_result_dtos.py` + tests in `tests/sdk/` + `tests/test_pyreason_e2e.py` etc.
- Related Docs:
  - `docs/quickstart/evaluate_and_evidence.md` (§1.2 head= parameter + §2.2 pred_id wording)
  - `docs/quickstart/rules.md` (rule.id semantics)
  - `docs/official/kernel/quickstart/evidence.md`
  - SDK + service docs that reference `rule.id` constraints
- Audit Log:
  - [2026-06-03_query-style-head-slice-delta.audit.md](./2026-06-03_query-style-head-slice-delta.audit.md)

## 1. Problem

Shipped strictly requires `rule.id` to match a known ledger predicate id (e.g. `"user:region"` / `"User:exists"`). A natural-looking rule name like `"adult_in_us"` or `"find_us_users"` is rejected:

```python
rule = Rule(
    id="find_us_users",
    when=(PredAtom(pred_id="user:region", terms=[u, r]),),
    ports={"user": u, "region": r},
)
fg.eval.evaluate(rule, head=rule)
# WhereValidationError: target predicate not found: find_us_users
```

Source anchors:
- `_evaluate.py:148-150` — `find_schema_pred(...) is None → raise "target predicate not found"`
- `_evaluate.py:156-157` — `len(head_vars) != len(arg_specs) → raise "head_vars length must match target arg_specs"`

3 user-facing consequences(per parent design §2.1):
1. Rule cannot have semantic name(`is_adult` / `find_us_users` rejected)
2. `row.bindings`(post-ζ port-map)+ `result.head.id` look like fact-shape predicates(`"user:region"`)— confuses user
3. Multiple rules sharing same head predicate must disambiguate via `version`

Parent design §3.8 specifies query-style decoupling:
- `rule.id` 可以是任意合法字符串(`"adult_in_us"` 全 OK)
- `head` 不再被 lookup 成 schema predicate;evaluator 只用 `head.ports` 决定 result 行形态
- arity check 转为 opt-in:只在 `head.id` 恰好 match 某个 schema predicate 时才校验 `len(head.ports) == len(arg_specs)`
- 向后兼容:原 `id="user:region"` 形态仍 work(走 opt-in 校验路径)

Slice δ is the **last slice** in parent design §6 ordering(α → β → γ → ζ → η → ε → **δ**)closing the chain。

## 2. Goals

- G1 — `_evaluate.py:148-150` rewrites:`find_schema_pred(...)` returns `None` 不再 raise;走 query-style path
- G2 — `_evaluate.py:156-157` arity check 改为 opt-in:只在 `find_schema_pred(...)` returns non-None 时才校验 `len(head_vars) == len(arg_specs)`
- G3 — `rule.id` 校验只保留 "non-empty string"(不要求 ledger predicate match);现有 ledger predicate match 风格仍 work(opt-in path)
- G4 — Backward compat:已 ship 的 `id="user:region"` style rules / tests / docs 全部 work without code change
- G5 — Evaluator 用 `head.ports` 决定 result row 形态;`head.id` 仅作为 result label / display
- G6 — Arity mismatch when `head.id` matches schema predicate:**rejection severity TBD** —— Step 4.2 P1 / Step 4.3 lock(parent §5.3 提了 reject / warn / silent skip 三选,parent draft 倾向 warn)
- G7 — Tests:add `id="find_us_users"` style 新 tests + 保留 `id="user:region"` regression tests
- G8 — Docs cascade:quickstart rules + evaluate_and_evidence + namespace-map + SDK docs;clarify `rule.id` 现在自由 + `result.head.id` 是 label
- G9 — Sacred Q-PR1 5-path 0-diff preserved

## 3. Non-goals

- N1 — 改变其他 slice 已完成的 surface(α/β/γ/ζ/η/ε artifacts)
- N2 — 改变 `evaluate_row_id_v2` / `evaluate_claim_digest_v2` / `evaluate_result_digest_v1` canonical bytes schema(δ 不动 digest algorithms;只动 head lookup gate)
- N3 — `Rule.projection(*names)` synthetic head support(future scope)
- N4 — 改变 EvidenceGraph vocabulary 或 walker(η + ε done,不动)
- N5 — Service wire `head.id` formatting change(用 same string,只改 strict invariant)
- N6 — Multiple rule version disambiguation redesign(future)
- N7 — Sacred-path edits(Q-PR1 5-path)
- N8 — Dirty baseline files

## 4. Current Source Anchors(Step 4.1 fresh read)

- `src/factgraph/core/store/_evaluate.py:148-150` — `find_schema_pred + None raise`
- `src/factgraph/core/store/_evaluate.py:152-157` — arg_specs validation + arity check
- `src/factgraph/application/protocol/evaluate_result.py:277-329` — Explanation L277,unchanged for δ
- Parent §3.8 — schema bump + opt-in arity
- Parent §2.1 — friction analysis

## 5. Proposed Shape(Draft, Not Yet Locked)

### 5.1 `_evaluate.py:148-157` rewrite

```python
# δ target
schema_pred = builders.find_schema_pred(store, target_pred_id)

if schema_pred is not None:
    # opt-in path: target_pred_id matches a known schema predicate
    arg_specs = schema_pred.get("arg_specs")
    if not isinstance(arg_specs, list) or not arg_specs:
        raise WhereValidationError("target predicate arg_specs must be non-empty list")
    if not isinstance(head_vars, list) or len(head_vars) != len(arg_specs):
        # Step 4.2/4.3 must lock severity: reject / warn / silent skip
        raise WhereValidationError("head_vars length must match target arg_specs")  # default: reject
else:
    # query-style path: rule.id does not match any schema predicate
    # head.ports shapes the result rows; no arity check
    pass
```

### 5.2 `head.id` validation

Only `_require_non_empty_str(rule.id)`;**no schema predicate lookup required** for δ to accept the rule。

### 5.3 Arity mismatch severity — Open Q for Step 4.2 / 4.3

Parent §5.3 提了 3 选:
- **Option A**(strict reject):保持现行,arity mismatch on matched-predicate path raise WhereValidationError
- **Option B**(warn + go query-style):emit warning,仍走 query-style path(arity 自由)
- **Option C**(silent skip):no warning,完全 query-style

Parent draft 倾向 **B**(保留 schema 协调能力,但不强制)。Step 4.2 review locks one。Default draft bias:Option A(strict reject保 backward compat,降 silent breakage risk;Option B 推迟)。

### 5.4 cross-engine impact

`_evaluate.py:148-157` 是 `mode == "native"` path 入口(L146 check `mode != "native"`)。但 other engines(souffle / problog / pyreason)路径在 L142-145 处独立:engine_kwargs + engine_evaluate(...)。**Step 4.3 必须 verify** other engine paths 是否也 reference head schema lookup independently 或者 share L148-157。

### 5.5 Result label semantics

`result.head.id`(post-δ)可能是 `"find_us_users"` 等 free-form 字符串。Slice ε walker `NODE_CONCLUSION.label` reads from `_claim_name_for_row_result(row, result)` which derives from `result.head.id`。需要 verify walker output 在 free-form head.id 下仍 sensible(probably yes — walker just shows the string)。

### 5.6 Cadence path locks

- **Tight gates default**:δ 改 shipped strict invariant(`rule.id` must match schema predicate),preflight 必须 surface cross-engine + backward compat scope
- Step 4.2 review **必须 lock G6 arity mismatch severity**(Option A / B / C)
- Stage 0 source audit folded into this Step 4.1 draft + Step 4.3 preflight verifies
- δ closes parent design chain — Step 4.9 archive 后 整个 evaluate-result-flatten parent design 7 slices 全部 implemented

## 6. Boundaries And Invariants

- Must preserve:
  - Backward compat: `id="user:region"` style rules continue to work(opt-in path)
  - Sacred Q-PR1 5-path 0-diff
  - Dirty baseline preserved
  - α-ε artifacts unchanged
  - Digest algorithms unchanged(`evaluate_row_id_v2` / `claim_digest_v2` / `result_digest_v1`)
- Explicitly NOT in this slice:
  - Synthetic head(`Rule.projection(...)`)support
  - Multiple-rule-same-predicate disambiguation redesign
- Compatibility constraints:
  - All α-ε tests must pass post-δ unchanged
  - Service wire `head.id` 用 same string format(free-form OR ledger predicate id,both acceptable)

### 6.1 Cadence path locks(per Slice η §10 D6)

- Tight gates default — δ is semantics-relaxing slice with cross-engine impact
- Step 4.7 + 4.8 individual report boundaries required per D6
- Open Q G6(arity mismatch severity)must lock at Step 4.2 / 4.3 before scope freeze

## 7. Acceptance Criteria(Draft)

- [ ] Step 4.2 has locked G6 arity severity(Option A / B / C)
- [ ] Step 4.3 preflight enumerated cross-engine paths + backward compat test cohort
- [ ] `_evaluate.py:148-157` rewrite per §5.1 — strict reject becomes opt-in
- [ ] `rule.id = "find_us_users"` style rule passes `fg.eval.evaluate(rule, head=rule)` end-to-end
- [ ] `rule.id = "user:region"` style rule continues to work(backward compat regression test)
- [ ] Arity mismatch on matched-predicate path follows locked G6 severity
- [ ] All α-ε regression tests pass
- [ ] Walker output(per Slice ε)still sensible for free-form `head.id`
- [ ] Service wire serializes free-form `head.id` without alteration
- [ ] Docs cascade:quickstart rules + evaluate_and_evidence + namespace-map + SDK docs
- [ ] D21 walker still works(per ε baseline)
- [ ] Q-PR1 5-path 0-diff vs `4c472b50` preserved
- [ ] Dirty baseline preserved

## 8. Implementation Plan

1. Step 4.2 — Draft review + tightening on blueprint branch. **Required focus**:G6 arity mismatch severity lock + cross-engine path verification + backward compat test cohort design
2. Step 4.3 — Independent preflight on `v0.2.0-query-style-head-preflight-2026-06-03`;produce 5-bucket finding table;**critical A1 cross-engine + A2 backward compat enum**
3. Step 4.4 — Fold preflight findings
4. Step 4.5 — Self-check
5. Step 4.6 — Scope freeze
6. Step 4.6.5 — Pre-impl grep(`find_schema_pred` callers / `target predicate not found` error msg / arity mismatch assertions in tests)
7. Step 4.7 — Implementation on `v0.2.0-impl-query-style-head-2026-06-03`(individual report per D6)
8. Step 4.8 — Closure(individual report per D6)+ **note δ closes parent design chain**
9. Step 4.9 — Archive

## 9. Pre-Impl Audit Tasks for Step 4.3

- A1 — Cross-engine paths:does other engines(souffle / problog / pyreason)reference head schema lookup independently or share `_evaluate.py:148-157`?
- A2 — Backward compat:enumerate all `id="entity:field"` style rules in src/ + tests/ + docs;ensure opt-in path covers
- A3 — Walker compatibility:does Slice ε `walk_evidence(...)` + `_claim_name_for_row_result` handle free-form `head.id`?
- A4 — Service wire:does service serializer reference `head.id` strict format?
- A5 — `target predicate not found` error message users:tests / docs / SDK examples
- A6 — Arity mismatch:current usage in `where` ast + RuleExpr validation paths
- A7 — Docs cascade enum:quickstart rules + evaluate_and_evidence + SDK docs + service docs
- A8 — D21 walker output for free-form `head.id`

## 10. Outcome / Deviations

Pending.

## 11. Deferred / Carry-Forward

- D1 — Synthetic head(`Rule.projection(...)`)support — future scope
- D2 — Multi-rule-same-predicate disambiguation redesign — future scope
- D3 — Parent design §3.7 `row.repr` wording sync(from ε D4)— not in δ scope
- D4 — Parent design §3.9.2 direction wording sync(from η D7)— not in δ scope
- **D5 — δ 完成后,evaluate-result-flatten parent design 7 slices(α-δ)全部 implemented + archived**;design-point 应可移到 archive 状态(per `design/README.md` 三条件)
