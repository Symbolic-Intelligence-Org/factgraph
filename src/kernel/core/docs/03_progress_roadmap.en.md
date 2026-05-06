# Core Development Progress and Roadmap

- Scope: `src/kernel/core`
- Last updated: 2026-05-06 (post Round Story Completion routemap closure @ `6b32972`)
- Baseline: current source behavior, not historical versions

## 0. Post-Routemap Status (2026-05-06)

The Round Story Completion routemap (2026-05-05 → 2026-05-06, 9 main batches + 3 sub-batches) closed at `6b32972`. The routemap added new capabilities primarily under `kernel.application/` and `kernel.audit/`; `kernel.core/` work during the routemap window was constrained by the application-first invariant and limited to native evaluator parameter extensions that support upper-layer capabilities.

The full closure narrative and deferred items are recorded in the round-story-completion-plan master plan (§10 Outcome) inside the monorepo; this kernel-only package does not bundle routemap blueprints.

## 1. Current Status Snapshot

Completed structural work:

- `Store` public entrypoints are grouped under `runtime/evaluation/queries/builders`
- `Store.evaluate` modes cover `native | souffle | problog | pyreason` (four engines)
- `mode='python'|'engine'` has been removed and now fails explicitly
- `core` and `adapters` are decoupled through `register_engine_evaluator`
- `Ledger` uses a SQLite truth + in-memory read-cache write-through model
- `project_view_facts_with_audit` uses `ProjectorAudit(contract_version=2)`
- `accept_many` supports `atomic` / `best_effort` and candidate dependency topological ordering
- the where AST gate is integrated (`FACTPY_WHERE_AST_VALIDATE`)
- `evaluate_where(...)` accepts `disabled_locators` + `literal_replacements` + `added_conditions` parameters (supporting Batch 5a/5b/5c rule action native evaluation)
- `where_ast_validate.atom_binds_new_variables(...)` is available for add-condition validation
- upper-layer declaration metadata is now unified as `version / description / tags`; core explicitly remains non-semantic with respect to those fields

## 2. Completed Milestones

### M1. Store boundary consolidation (done)

Result: `runtime.py` owns the facade / `evaluation.py` owns the evaluate flow / `queries.py` owns query facades / `builders.py` owns candidate construction.

### M2. Engine injection decoupling (done)

Result: core no longer needs static adapter imports; `souffle/problog/pyreason` register evaluators on adapter import.

### M3. Ledger persistence (done)

Result: SQLite tables and indexes are in place; append transactions and read-cache updates are synchronized; the ledger can run in memory mode or file-backed mode.

### M4. Batch accept capability (done)

Result: introduced `accept_many_candidate_sets(...)`; supports dependency topological ordering, cycle detection, and atomic rollback.

### M5. Projector audit interface (done)

Result: `project_view_facts_with_audit(...)` returns an audit structure; audit fields focus on active/selected/policy-drop statistics.

### M6. where_eval rule-action parameter extension (done, routemap window)

Result: `evaluate_where(...)` gained `disabled_locators` + `literal_replacements` + `added_conditions` parameters; new private helpers `_apply_literal_replacements` + `_apply_added_conditions`; supports Batch 5a/5b/5c rule action capabilities natively without an application-layer rewrite of the native engine. The AST validator `atom_binds_new_variables(...)` is used for add-condition validation.

## 3. Current Main Risks

1. Compatibility layers are still numerous: `store.api`, `Store.evaluate_dummy`, and `store/_*.py`; gradual reduction is needed.
2. `accept_many` state-machine complexity has increased, but examples are still not systematic enough.
3. Consistency boundaries for file-backed multi-process ledger usage are still undefined.
4. **New (post-routemap):** the native evaluator parameter surface expanded along with rule actions (`disabled_locators` / `literal_replacements` / `added_conditions`); future rule actions introducing new parameters require a signature-drift gate (per Batch 5a/b/c precedent — `evaluate_native_where(...)` signature is hard-stable; extensions go through `evaluate_where(...)` private parameters).

## 4. Next Priorities

### P1. Compatibility entrypoint reduction

Goals: define a clear removal plan for `evaluate_dummy`; fully converge new code on `runtime/evaluation/queries/builders`.

### P1. `accept_many` contract strengthening

Goals: document caller guidance for each `state/error.code`; add fixed examples for atomic rollback and blocked dependency.

### P1. Ledger runtime-boundary definition

Goals: document that the current guarantee is a single-process cache model; if multi-process support is needed, define refresh/invalidation semantics first.

### P2. Rule and engine semantic parity governance

Goals: keep native and adapter behavior aligned for new where features; add parity regressions on critical paths. In particular, Batch 5a/b/c rule actions are currently native-only; non-native engines either handle them through adapter-side support or return explicit unsupported errors.

### P2. Performance baselines as standard practice

Goals: fix benchmark scenarios and recording format; make performance changes traceable before and after implementation.

### P3 (post-routemap reactivation triggers)

The following directions were explicitly deferred in the routemap; if their reactivation triggers fire, core may need adjustment:

- Batch 4 ProofFrame symmetric `rule_refs` hardening — currently RuleRef-bearing artifacts return an `unsupported`-equivalent in the ProofFrame Rechecker; hardening may affect ruleref reverse propagation in `kernel.core.store._support`.
- Frontier event family / rule action event kinds — persistence reactivation does not directly touch core, but round-event parameter extensions (per Batch 6 §5.5.4) may affect audit-side schema.
- L5 cross-run aggregation — Batch 7 §5.5.3 #11 reactivation requires a module-mapping mechanism, potentially requiring core to expose a `module_id` derivation interface.
- Multi-action rule runtime / variable binding planner / RuleRef-recursive overlay — these reactivations would all touch `evaluate_where(...)` parameters and the AST validator surface.

## 5. Execution Principles

1. stabilize semantics before optimizing performance
2. reduce compatibility surface before expanding API surface
3. for external contract changes: update docs first, then implementation, then regression coverage
4. **(post-routemap)** Application-first runtime authority is preserved: new capabilities remain DTO + pure fn in `kernel.application/`; core only exposes stable substrate (per `project_application_first_runtime_authority.md` memory anchor).
