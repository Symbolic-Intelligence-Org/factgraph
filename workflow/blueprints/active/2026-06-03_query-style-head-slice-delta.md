# Task Blueprint: Query-style head Slice δ — `rule.id` decouple + arity opt-in

- Status: scoped
- Created: 2026-06-03
- Last Updated: 2026-06-04 (Step 4.6.5 pre-impl grep)
- Owner: Claude (blueprint draft) / Codex (review + impl) — Slice 4/5 cross-flip per [[feedback_audit_to_archive_cadence]]
- **Cadence**: tight gates default — δ relaxes a shipped strict invariant (`rule.id` must match schema predicate); preflight will surface cross-engine impact
- Fork base: `dd65e776` (Slice ε Step 4.9 archive HEAD)
- Parent design: [`workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.8 + §6 Slice δ
- Predecessors:
  - α / β / γ / ζ / η / ε (all archived) — DTO surface evolution + evidence model layered hierarchy + walker
- Related Modules:
  - `src/factgraph/core/store/_evaluate.py:148-157` (shipped head lookup + arity check — δ rewrites these to opt-in)
  - `src/factgraph/adapters/souffle/engine_eval.py:118-127` (same strict head lookup + arity check)
  - `src/factgraph/adapters/problog/engine_eval.py:68-75` (same strict head lookup + arity check)
  - `src/factgraph/adapters/problog/problog_import.py:110-119` (import-time strict head lookup + arity check)
  - `src/factgraph/core/derivation/candidates.py:126-135` (`CandidateSet(candidate_kind="fact")` canonical payload requires `terms`)
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
- G6 — **LOCKED Option A**: arity mismatch when `head.id` matches a schema predicate remains a strict `WhereValidationError`. Query-style relaxation applies only when no schema predicate matches `head.id`; matched-predicate heads keep the shipped arity contract.
- G7 — Tests:add `id="find_us_users"` style 新 tests + 保留 `id="user:region"` regression tests
- G8 — Docs cascade:quickstart rules + evaluate_and_evidence + namespace-map + SDK docs;clarify `rule.id` 现在自由 + `result.head.id` 是 label
- G9 — Sacred Q-PR1 5-path 0-diff preserved
- G10 — Add a query-style candidate construction path. Shipped `candidates_from_bindings(...)` is schema-bound (`schema_pred`, `arg_specs`, `group_key_indexes`, target arg0 `entity_ref`, legacy fact payload). δ cannot simply pass `schema_pred=None`; it needs an explicit helper/branch that builds candidates from `head.ports` while preserving ζ port-map row bindings and required service/provenance compatibility envelopes.
- G11 — Apply opt-in head lookup consistently across native + adapter engine heads. Souffle / ProbLog adapters currently repeat the same `find_schema_pred(...)` + arity strictness outside `_evaluate.py`; Step 4.7 must update those head paths or Step 4.3 must explicitly prove an engine-specific blocker.

## 3. Non-goals

- N1 — 改变其他 slice 已完成的 surface(α/β/γ/ζ/η/ε artifacts)
- N2 — 改变 `evaluate_row_id_v2` / `evaluate_claim_digest_v2` / `evaluate_result_digest_v1` canonical bytes schema(δ 不动 digest algorithms;只动 head lookup gate)
- N3 — `Rule.projection(*names)` synthetic head support(future scope)
- N4 — 改变 EvidenceGraph vocabulary 或 walker(η + ε done,不动)
- N5 — Service wire `head.id` formatting change(用 same string,只改 strict invariant)
- N6 — Multiple rule version disambiguation redesign(future)
- N7 — Sacred-path edits(Q-PR1 5-path)
- N8 — Dirty baseline files
- N9 — PyReason materialized graph fact conversion substrate (`pyreason/engine_eval.py:637-695`) is excluded unless Step 4.7 proves a safe adapter path. It is not public head validation.
- N10 — Read/query helper lookups (`core/store/_queries.py` and `service/runtime_v1.py:2679`) are excluded; they are not derivation-head evaluation paths.
- N11 — Test-local fake engine evaluators in `src/domains/ecss/tests/test_evidence_tree_explain_contracts.py` remain schema-backed fixtures. They are not production head validation paths and should only change if Step 4.7 test execution proves they need fixture migration.

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
        # Step 4.2 locked Option A: matched-predicate arity mismatch still rejects.
        raise WhereValidationError("head_vars length must match target arg_specs")
else:
    # query-style path: rule.id does not match any schema predicate
    # head.ports shapes the result rows; no arity check
    pass
```

### 5.2 `head.id` validation

Only `_require_non_empty_str(rule.id)`;**no schema predicate lookup required** for δ to accept the rule。

### 5.3 Arity mismatch severity — Step 4.2 LOCK

Parent §5.3 提了 3 选:
- **Option A**(strict reject):保持现行,arity mismatch on matched-predicate path raise WhereValidationError
- **Option B**(warn + go query-style):emit warning,仍走 query-style path(arity 自由)
- **Option C**(silent skip):no warning,完全 query-style

**Step 4.2 LOCK: Option A.** Matched-predicate heads preserve shipped arity rejection. This avoids silent behavior changes for existing `id="entity:field"` users and keeps the backward-compat path easy to reason about. Parent Option B/C remain future policy work only.

### 5.4 cross-engine impact — PF-R1 / PF-r1 / PF-r2 LOCK

`_evaluate.py:148-157` 是 `mode == "native"` path 入口(L146 check `mode != "native"`)。Step 4.2 fresh read found non-native head strictness is **not** only shared through `_evaluate.py`:

- `src/factgraph/adapters/souffle/engine_eval.py:118-127` repeats `find_schema_pred(...)` + arity reject.
- `src/factgraph/adapters/problog/engine_eval.py:68-75` repeats `find_schema_pred(...)` + arity reject.
- `src/factgraph/adapters/problog/problog_import.py:110-119` repeats import-time candidate construction strictness.
- PyReason fact-to-candidate helpers at `pyreason/engine_eval.py:637-695` still require schema predicates for materialized graph facts; Step 4.3 must classify whether this is head validation or a distinct adapter fact-conversion substrate.

**Step 4.4 LOCK from preflight PF-R1**: Native, Souffle, ProbLog runtime, and ProbLog import are in scope for the same opt-in schema lookup rule.

**Step 4.4 carve-outs**:

- PyReason fact-conversion lookups at `pyreason/engine_eval.py:637-695` are substrate conversion from materialized node/edge facts into FactGraph candidates, not public head validation. Do not rewrite them in δ unless implementation proves a safe adapter path.
- `_queries.py` and service read-query lookups are read/query helpers, not derivation-head evaluation paths.

### 5.5 Query-style candidate construction — PF-R2 / PF-R3 LOCK

Shipped `candidates_from_bindings(...)` cannot handle free-form `head.id` because it requires:

- `schema_pred` for `read_group_key_indexes(...)`;
- `arg_specs` to coerce values;
- first tagged arg to be `entity_ref`;
- legacy payload shape `{"pred_id": target_pred_id, "terms": ...}`.

δ implementation therefore needs a separate query-style candidate branch/helper, rather than weakening this schema-bound helper in place. The query-style branch should:

- derive ordered output values from `head.ports` / `head_vars` and binding rows;
- preserve ζ in-process `EvaluateRow.bindings` as `{port_name: term}`;
- keep `candidate_kind="fact"` for δ unless Step 4.4 is explicitly amended again;
- emit a compatibility fact-like payload `{"pred_id": head.id, "terms": ordered_terms}` because `CandidateSet(candidate_kind="fact")` canonical content requires `terms` (`candidates.py:126-135`);
- keep deterministic candidate identity/digests with the existing `cand_v2` / `candk_v2` machinery;
- keep row bindings as ζ port-map at `EvaluateRow` level even when candidate payload remains fact-like for compatibility.

### 5.6 Result label semantics

`result.head.id`(post-δ)可能是 `"find_us_users"` 等 free-form 字符串。Slice ε walker `NODE_CONCLUSION.label` reads from `_claim_name_for_row_result(row, result)` which derives from `result.head.id`。需要 verify walker output 在 free-form head.id 下仍 sensible(probably yes — walker just shows the string)。

### 5.7 Service/runtime compatibility — PF-R4 LOCK

Service and runtime protocol still carry `target_pred_id` in compiled plans, runtime recipes, and response metadata:

- `service/runtime_v1.py:1002-1015` calls `store.evaluate(... target_pred_id=compiled["target_pred_id"], head_vars=..., head=compiled.get("head"))`.
- `service/runtime_v1.py:1795-1803` caches `RuntimeDerivationRecipe(target_pred_id=..., head_vars=...)`.
- `sdk/store.py:3839-3852` rebuilds `CompiledDerivationPlan` from compiled dicts with `target_pred_id` and `head_vars`.
- `sdk/store.py:3885-3889` synthesizes an `ApplicationRule` from compiled plans using `id=head.target_pred_id`.

δ must preserve these wire/key names for compatibility while changing their meaning from "must be schema predicate id" to "head/rule id label, optionally schema-backed". Do not rename runtime DTO keys in δ; update docs/meaning only.

### 5.8 Step 4.6.5 pre-impl grep additions

Pre-impl grep found no new production head-validation sites beyond PF-R1. It did surface three implementation/testing details:

- `src/agent/tests/test_agent_l4a_workflow.py:195-199` asserts the old free-form/missing predicate failure message (`target predicate not found`). Step 4.7 must migrate or reclassify this active test because δ makes missing schema predicates valid query-style head labels.
- Docs wording is broader than the four PF-r3 strict-error lines. Step 4.7 docs cascade must also sweep "known ledger predicate", "head predicate id", "real predicate id", and similar wording in `docs/quickstart/evaluate_and_evidence.md`, `docs/quickstart/rules.md`, `docs/official/kernel/quickstart/evidence.md`, and `docs/official/kernel/quickstart/rules-and-inferences.md`.
- `src/domains/ecss/tests/test_evidence_tree_explain_contracts.py:1450-1455` and `:1572-1574` are test-local fake Souffle evaluators that intentionally exercise schema-backed candidates. They are carved out per N11 unless test execution shows they must be migrated.

### 5.9 Rule DTO validation

`Rule.__post_init__` already only requires `id` to be a non-empty string (`rule.py:62-63`). δ does not need to relax Rule DTO validation; the strictness lives in evaluate/adapters/builders and related docs/tests.

### 5.10 Cadence path locks

- **Tight gates default**:δ 改 shipped strict invariant(`rule.id` must match schema predicate),preflight 必须 surface cross-engine + backward compat scope
- Step 4.2 review locked G6 arity mismatch severity to **Option A strict reject** for matched-predicate heads
- Stage 0 source audit folded into this Step 4.1 draft + Step 4.3 preflight verifies
- δ closes parent design chain — Step 4.9 archive 后 整个 evaluate-result-flatten parent design 7 slices 全部 implemented

## 6. Boundaries And Invariants

- Must preserve:
  - Backward compat: `id="user:region"` style rules continue to work(opt-in path)
  - Matched-predicate arity mismatch continues to reject (G6 Option A)
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
- G6 arity mismatch severity locked at Step 4.2:Option A strict reject for matched-predicate heads

## 7. Acceptance Criteria(Draft)

- [x] Step 4.2 has locked G6 arity severity:Option A strict reject for matched-predicate heads
- [x] Step 4.3 preflight enumerated cross-engine paths + backward compat test cohort
- [ ] `_evaluate.py:148-157` rewrite per §5.1 — strict reject becomes opt-in
- [ ] `rule.id = "find_us_users"` style rule passes `fg.eval.evaluate(rule, head=rule)` end-to-end
- [ ] `rule.id = "user:region"` style rule continues to work(backward compat regression test)
- [ ] Arity mismatch on matched-predicate path follows locked G6 severity
- [ ] Query-style candidate branch/helper exists; implementation does not pass `schema_pred=None` into schema-bound `candidates_from_bindings(...)`
- [ ] Native/Souffle/ProbLog runtime + ProbLog import head strictness follows the same opt-in schema lookup rule
- [ ] PyReason fact-conversion substrate and read/query helper lookups remain excluded per PF-r1/PF-r2
- [ ] Query-style candidates keep `candidate_kind="fact"` + fact-like `{"pred_id": head.id, "terms": ...}` compatibility payload unless a new PF explicitly expands scope
- [ ] Service/runtime compiled-plan fields remain wire-compatible while docs clarify `target_pred_id` / `head.id` now mean head label, optionally schema-backed
- [ ] `src/agent/tests/test_agent_l4a_workflow.py` old `target predicate not found` expectation is migrated or reclassified
- [ ] Test-local fake engine evaluators in `src/domains/ecss/tests/test_evidence_tree_explain_contracts.py` remain schema-backed or are migrated only if test execution requires it
- [ ] All α-ε regression tests pass
- [ ] Walker output(per Slice ε)still sensible for free-form `head.id`
- [ ] Service wire serializes free-form `head.id` without alteration
- [ ] Docs cascade:quickstart rules + evaluate_and_evidence + namespace-map + SDK docs, including "known ledger predicate" / "head predicate id" / "real predicate id" wording
- [ ] D21 walker still works(per ε baseline)
- [ ] Q-PR1 5-path 0-diff vs `4c472b50` preserved
- [ ] Dirty baseline preserved

## 8. Implementation Plan

1. Step 4.2 — Draft review + tightening on blueprint branch. **Required focus**:G6 arity mismatch severity lock + cross-engine path verification + backward compat test cohort design
2. Step 4.3 — Independent preflight on `v0.2.0-query-style-head-preflight-2026-06-03`;produce 5-bucket finding table;**critical A1 cross-engine + A2 backward compat enum**
3. Step 4.4 — Fold preflight findings
4. Step 4.5 — Self-check
5. Step 4.6 — Scope freeze
6. Step 4.6.5 — Pre-impl grep(`find_schema_pred` callers / `target predicate not found` error msg / arity mismatch assertions in tests / CandidateSet fact payload users)
7. Step 4.7 — Implementation on `v0.2.0-impl-query-style-head-2026-06-03`(individual report per D6)
8. Step 4.8 — Closure(individual report per D6)+ **note δ closes parent design chain**
9. Step 4.9 — Archive

## 9. Pre-Impl Audit Tasks for Step 4.3

- A1 — Cross-engine paths:confirm native / Souffle / ProbLog / PyReason head strictness sites and classify which engines can share δ query-style head semantics. Fresh-read anchors include `_evaluate.py:148-157`, `souffle/engine_eval.py:118-127`, `problog/engine_eval.py:68-75`, `problog_import.py:110-119`, and PyReason fact conversion at `pyreason/engine_eval.py:637-695`. **Step 4.4 result**:native/Souffle/ProbLog in scope; PyReason fact conversion excluded unless implementation proves safe.
- A2 — Backward compat:enumerate all `id="entity:field"` style rules in src/ + tests/ + docs;ensure opt-in path covers
- A3 — Query-style candidate construction:verify builder/helper plan for free-form head rows;do not weaken `candidates_from_bindings(...)` in a way that breaks schema-backed candidates. **Step 4.4 result**:new query-style helper/branch required; keep candidate_kind fact + fact-like payload by default.
- A4 — Walker compatibility:does Slice ε `walk_evidence(...)` + `_claim_name_for_row_result` handle free-form `head.id`?
- A5 — Service/runtime wire:does service serializer / runtime recipe / compiled plan metadata treat `target_pred_id` as strict schema id or generic head label?
- A6 — `target predicate not found` error message users:tests / docs / SDK examples
- A7 — Arity mismatch:current usage in `where` ast + RuleExpr validation paths;matched-predicate mismatch must preserve strict reject
- A8 — Docs cascade enum:quickstart rules + evaluate_and_evidence + SDK docs + service docs
- A9 — D21 walker output for free-form `head.id`

## 10. Outcome / Deviations

Pending.

## 11. Deferred / Carry-Forward

- D1 — Synthetic head(`Rule.projection(...)`)support — future scope
- D2 — Multi-rule-same-predicate disambiguation redesign — future scope
- D3 — Parent design §3.7 `row.repr` wording sync(from ε D4)— not in δ scope
- D4 — Parent design §3.9.2 direction wording sync(from η D7)— not in δ scope
- **D5 — δ 完成后,evaluate-result-flatten parent design 7 slices(α-δ)全部 implemented + archived**;design-point 应可移到 archive 状态(per `design/README.md` 三条件)
- D6 — `target_pred_id` wire/key rename to `head_id` / `rule_id` is deferred; δ preserves existing keys and updates semantics/docs only.
