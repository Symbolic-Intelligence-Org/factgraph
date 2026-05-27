# Task Blueprint: T11.2.9 Match Runtime Implementation

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: M (first runtime tranche: Rule + AND RuleExpr + docs/tests)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t11-2-9-match-runtime-implementation.audit.md`
- Trigger: T11.2.7 locked the match API design and T6/T11.3 release docs correctly defer match runtime. User selected N9 to close the design -> runtime -> docs loop.

## 0. Scope Locks

### In scope

Implement the v0.2 read-side match runtime described by
`workflow/design/design-points/active/match-api-design.zh.md`.

Primary shipped behavior target:

```python
fg.read.match(EntityCls, template, *, limit=None, **port_constraints)
    -> tuple[EntityCls snapshot, ...]
```

Required implementation areas:

1. **SDK public surface**: add `fg.read.match(...)` and underlying
   `FactGraph.match(...)` / `SDKStore.match(...)` entry points.
2. **Template support**: accept application `Rule` and AND-only `RuleExpr`
   (`&` / `RuleExpr.all(...)`); reject OR `RuleExpr`, legacy `Query`, bare
   list/tuple, and unsupported objects with helpful `SDKStoreError` / DSL
   error text.
3. **Projection contract**: require exactly one entity-ref port matching
   `EntityCls`; return distinct snapshots of that entity type.
4. **Constraint composition**: support literal kwargs and own-class `Field`
   descriptor kwargs; reject cross-entity Field kwargs and unknown ports.
5. **Pattern connectivity**: enforce T11.2.7 M21 before matching, including
   synthetic atoms from F-expression kwargs.
6. **View scope**: honor T11.1 attach-time view scoping; keep method-level
   `view=` rejected with the established attach hint.
7. **Tests**: add focused match runtime tests for success, projection errors,
   kwarg constraints, F-expression constraints, connectivity rejection,
   view-scoped attach, and explicit non-goals.
8. **Docs**: add user-facing match sections only after runtime exists:
   quickstart `read-write.md` / `rules-and-inferences.md` plus SDK docs/API
   surface as needed.
9. **Release docs**: update `CHANGELOG.md` / release-facing deferred language
   only if the runtime actually lands in this cycle.

### Out of scope

- Witness/assertion-returning match output (`.as_assertions()`,
  `.witnesses()`, `.to_view()`).
- Cross-entity tuple returns such as `match((User, Order), expr)`.
- Legacy `Query` adapter or `fg.queries.*` persistence.
- Method-level `view=`.
- Snapshot-at-tx matching (`at=` / `as_of`).
- Streaming / lazy match iterators / pagination cursors.
- Deleting `fg.eval.run`.
- Service / OpenAPI endpoints.
- EvidenceGraph / Explanation changes.
- Adapter semantics changes or new inference-engine behavior.
- Notebook namespace cleanup and remaining dirty baseline files.

### Stop / amend triggers

Pause and amend if Step 4.6 or implementation shows:

- runtime requires a new public DTO or wrapper (`MatchResult`, `MatchView`,
  `MatchRow`) despite T11.2.7 M10;
- AND RuleExpr matching cannot be implemented without broad lowering/runtime
  redesign beyond M scope;
- pattern connectivity cannot be checked reliably from current Rule/RuleExpr
  structures;
- view-scoped attach requires changes to Database view semantics or
  method-level `view=`;
- legacy `Query` compatibility becomes necessary for user-facing docs;
- implementation touches service/OpenAPI/release machinery or unrelated dirty
  baseline files.

## 1. Problem

T11.2.7 made match API design complete, but runtime remains absent. Public
release docs currently defer match implementation. That is correct for
v0.2.0-rc.1 only if match remains unshipped; once this cycle lands, user docs
must teach a runnable path and release-facing deferred language must be revised.

The implementation must preserve the design's central trade-off: match should
feel like `read.find(...)` with a rule-pattern template, not like evaluate,
assertion filtering, or a wrapper result parser.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/design/design-points/active/match-api-design.zh.md` | Canonical M1-M21 match commitments. |
| `workflow/blueprints/archive/2026-05-26_t11-2-7-match-api-design.md` and audit | Amendment trail: V2/V3 rejected, V4 EntityCls-head shape locked, M21 connectivity added. |
| `src/factgraph/sdk/store.py` `_SDKReadManager.find`, `SDKStore.find`, attach-view checks | SDK read namespace and view rejection patterns. |
| `src/factgraph/sdk/facade.py` `sdk_find`, snapshot hydration helpers | Existing read/find snapshot construction path to reuse. |
| `src/factgraph/application/protocol/rule.py` / `rule_expr.py` / `rule_expr_lowering.py` | Rule/RuleExpr ports, joins, lowering, and validation substrate. |
| `src/factgraph/sdk/dsl/application_rule.py` / `expr.py` / `schema.py` | SDK DSL atoms, vars, and field descriptor truth. |
| T11.1 attach-view implementation/tests | View-scoped runtime behavior and method-level `view=` rejection contract. |
| T11.3 release machinery | Release docs and dry-run state if match moves from deferred to shipped. |

## 3. Preliminary Implementation Hypothesis

T11.2.9 should try a narrow implementation path:

1. Normalize `Rule` into a one-rule expression and normalize `RuleExpr` through
   the existing inspect/lowering substrate where possible.
2. Resolve the unique projection port for `EntityCls`.
3. Compose kwarg constraints as match-runtime predicates without mutating the
   input Rule/RuleExpr.
4. Enumerate visible snapshots for `EntityCls` using the existing view-scoped
   read facade, then check each candidate against the effective template.
5. Materialize distinct snapshots via existing `sdk_get` / `sdk_find` helpers
   or lower-level DTO hydration helpers.

This is a hypothesis for Step 4.6 verification, not a locked design. If the
existing runtime has a better query/lowering path that can satisfy M1-M21
without extra complexity, use it.

## 4. Design Commitments To Preserve

Implementation must preserve these T11.2.7 commitments:

| ID | Runtime requirement |
|---|---|
| M1-M3 | Public shape is `fg.read.match(EntityCls, template, **kwargs)` and EntityCls is the match head. |
| M4 | Template has exactly one matching entity-ref port for EntityCls. |
| M5-M7 | Accept `Rule` and AND-only `RuleExpr`; do not use legacy `Query` head semantics. |
| M8 | Pattern matching only; no inference engine involvement. |
| M9-M11 | Return `tuple[EntityCls snapshot, ...]`; no wrapper DTO or chain methods. |
| M12-M15 | Literal / own-class Field kwargs compose synthetic constraints; Rule objects remain immutable. |
| M16 | Attach-time view scope only; method-level `view=` rejected. |
| M17-M18 | No witness/assertion output and no cross-entity tuple output. |
| M19 | Do not delete `fg.eval.run`. |
| M20 | Do not couple to assertion facade ergonomics. |
| M21 | Reject disconnected effective patterns before matching. |

## 4.1 Final Scoped Decisions

| Decision | Scoped lock |
|---|---|
| RuleExpr OR support(N1) | **Defer OR**. T11.2.9 implements single `Rule` and AND-only `RuleExpr`(`&` / `RuleExpr.all(...)`). OR `RuleExpr` (`|` / `RuleExpr.any(...)`) raises a clear unsupported error and becomes a follow-up runtime tranche. `match-api-design.zh.md` now records this implementation note. |
| Entity-ref comparison(N2) | Compare entity-ref bindings by canonical `idref_v1` token. Snapshot object identity is never used. Literal entity constraints should accept canonical refs and snapshots by normalizing snapshots to `.ref`; returned snapshots hydrate from refs. |
| Runtime strategy(N3) | Use a simple materialized matcher for the first tranche: enumerate visible snapshots / candidate bindings through current store/view data and filter with the effective AND pattern. No new index. Future optimization triggers: large datasets, OR, streaming, or performance failure in focused tests. |
| RuleExpr connectivity(N5) | Single Rule connectivity is built from `Rule.where`; AND RuleExpr connectivity uses lowered branch atoms plus pending joins/materialized join edges; F-expression synthetic atoms join constrained port vars to the projected entity var. OR is deferred before connectivity. |
| Limit timing | Apply `limit` **after** distinct projection de-duplication so returned tuple semantics remain stable. |
| Docs scope | Update `read-write.md`, `rules-and-inferences.md`, SDK rules/read docs, API surface, and `CHANGELOG.md` deferred line only after runtime passes. Do not teach OR, witness, Query adapter, or method-level `view=`. |
| Class | Narrowed to M for the first runtime tranche. Escalate if AND RuleExpr cannot use existing lowering data or if implementation needs new DTO/runtime architecture. |

## 5. Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | SDK read namespace call chain | `_SDKReadManager` currently exposes `get`/`find`/`ref` and no `match`(`store.py:527-559`). `SDKStore.read` returns that manager at `store.py:1186-1189`. Add `_SDKReadManager.match(...)` delegating to `SDKStore.match(...)`, then implement `SDKStore.match(...)` near `find(...)`. |
| 2 | Snapshot hydration path | `SDKStore.find(...)` rejects `view=` then delegates to `sdk_find(...)`(`store.py:1265-1286`). `sdk_find(...)` validates entity class, uses `execute_read_request(..., mode="find")`, hydrates each DTO through `_dto_to_sdk_snapshot(...)`, and applies filters/limit(`facade.py:585-669`). Match should reuse `_dto_to_sdk_snapshot(...)` / `_build_snapshot(...)` rather than duplicating `EntitySnapshot` construction(`facade.py:794-851`). |
| 3 | Rule ports / `_port_types` projection data | `Rule.__post_init__` freezes `ports` and infers `_port_types`(`rule.py:85-104`). Entity-ref port typing is inferred from `:exists` atoms(`rule.py:508-545`). Projection validation can use `rule.port_types[name].kind == "entity_ref"` and `entity_type == EntityCls.__name__`; exactly one match required. |
| 4 | RuleExpr lowering / inspect support | RuleExpr supports AND and OR (`RuleExpr.all/any`, `__and__`, `__or__`) at `rule_expr.py:43-64`; joins attach only to `_AndGroup` and OR `.join_by_ports` raises(`rule_expr.py:97-131`). Lowering plans expose branches, occurrence aliases, body atoms, and pending joins(`rule_expr_lowering.py:99-137`, `:597-625`). T11.2.9 uses only one-branch / AND paths; OR is deferred because it produces multiple branches (`_lower_or` path) and needs alternative enumeration/dedup policy. |
| 5 | SDK Field descriptor validation path | SDK `Field` descriptors live at `schema.py:91-125`; descriptor names come from `_DeclaredMember.sdk_attr_name`(`schema.py:22-33`). `SDKStore._index_schema` maps Field descriptor objects to schema predicate/declaration (`store.py:3010-3033`). Match can validate own-class Field kwargs through `_field_decl_by_descriptor` / active entity class lookup; cross-entity descriptor means reject. |
| 6 | Legacy Query runtime reuse / non-reuse | Legacy `Query` is `Query(head, where, ...)` (`sdk/dsl/rule.py:198-224`) and runtime maps query rows/instances through `execute_query_plan(...)` (`sdk/query_runtime.py:35-74`). It uses Query head/return-contract semantics and does not expose witness ids. Do not reuse as public match path; at most borrow private row-dedup ideas later. |
| 7 | Pattern connectivity data sources | Single Rule: use `Rule.where` atoms + `Rule.ports`. AND RuleExpr: use lowering branch `body_atoms`, `pending_joins`, occurrence map, and `RuleExprPortBinding` data from lowering (`rule_expr_lowering.py:99-145`, `:629-650`). F-expression kwargs add synthetic edges between constrained port var and projected entity field var. OR is rejected before connectivity. |
| 8 | View-scoped attach read path | `FactGraph.attach(db, view=view)` swaps in a durable-view ledger and marks runtime read-only (`store.py:1078-1114`). Existing read/evaluate then operate on `sdk.store`/`sdk.ledger`, so match must only read from `self.store` / `self.ledger`, never from `Database.head()` or current db directly. Attach-view tests already cover read/evaluate scoping in `tests/test_db_attach_lifecycle.py`. |
| 9 | Error taxonomy and message lock | Use `SDKStoreError` for public SDK runtime rejections. Messages: unsupported OR `"fg.read.match(...) currently supports Rule and AND RuleExpr only"`; unsupported Query/list/tuple `"fg.read.match(...) accepts application Rule or AND RuleExpr, not <type>"`; method-level view hint mirrors find; unknown port names list valid ports; cross-entity Field says use `RuleExpr.join_by_ports`; disconnected pattern mentions cross-product risk. |
| 10 | Test matrix | New `tests/test_sdk_read_match_runtime.py` for Rule literal, own-class Field, projection missing/ambiguous, unknown port, Query/list/tuple reject, OR reject, disconnected reject, distinct snapshots, limit-after-dedup, idref/snapshot entity-ref constraint. Extend `tests/test_db_attach_lifecycle.py` for view-scoped match + method-level `view=` rejection. Reuse `tests/sdk/test_rule_expr_evaluate.py` / `tests/application/protocol/test_rule_expr.py` only as focused regression suites, not primary match tests. |
| 11 | User docs update set | Update `docs/official/kernel/quickstart/read-write.md` and `docs/official/kernel/quickstart/rules-and-inferences.md` with AND-only runnable examples. Update `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` and `04_api_surface.en.md`. Do not teach OR, Query adapter, witness, or method-level `view=`. |
| 12 | Release-facing docs/deferred language update set | Update `CHANGELOG.md` v0.2.0-rc.1 deferred line if runtime lands: remove "Match API implementation" from deferred, keep witness/method-level view/as_of/EvidenceGraph/adapter semantics deferred. No release machinery changes. |
| 13 | Stop-amend findings and final class | No blocker found for Rule + AND RuleExpr first tranche. OR support is explicitly deferred and recorded in `match-api-design.zh.md`. Final class narrows to M; stop/amend only if AND path requires broad runtime redesign during implementation. |

## 6. Implementation Split Proposal

Likely commit split after Step 4.6:

1. **Runtime core**: SDK read entry, template/projection validation, constraint
   composition, connectivity check, and snapshot matching.
2. **View + rejection tests**: attach-view behavior, method-level `view=`,
   unsupported Query/list/tuple, error message coverage.
3. **Docs**: quickstart + SDK docs + release-facing deferred language update.
4. **Verification**: focused tests, broader relevant suite, ruff, diff check.

Step 4.6 may revise this split if implementation is smaller or if RuleExpr
requires a separate helper slice.

## 7. Acceptance

- [ ] Step 4.6 inventory completed with file:line references.
- [ ] Final runtime path preserves T11.2.7 M1-M21 or records an explicit amend.
- [ ] `fg.read.match(EntityCls, Rule, **kwargs)` works for literal constraints.
- [ ] `fg.read.match(EntityCls, Rule, field=EntityCls.other_field)` works for own-class Field constraints.
- [ ] `fg.read.match(EntityCls, RuleExpr, **kwargs)` works for AND joined patterns.
- [ ] OR `RuleExpr` raises a clear unsupported error and remains documented as deferred.
- [ ] Projection ambiguity / missing projection / unsupported template / unknown port / cross-entity Field / disconnected pattern all raise clear errors.
- [ ] View-attached runtime scopes match to the attached view; method-level `view=` remains rejected.
- [ ] Runtime returns `tuple` of distinct snapshots, no wrapper DTO.
- [ ] User-facing docs teach only shipped match behavior and do not teach deferred witness/query persistence features.
- [ ] Focused tests and relevant SDK/application suites pass.
- [ ] `ruff` for touched Python files clean.
- [ ] `git diff --check` clean.
- [ ] Dirty baseline and sacred master preserved.

## 8. Verification Commands

Draft expected commands, to be finalized after Step 4.6:

```bash
python -m unittest tests.test_sdk_read_match_runtime
python -m unittest tests.test_db_attach_lifecycle tests.test_sdk_frozen_view_read_runtime_boundaries
python -m unittest tests.sdk.test_rule_expr_evaluate tests.application.protocol.test_rule_expr tests.application.protocol.test_rule_expr_lowering
python -m ruff check <touched files>
git diff --check
git status --short --branch
```

## 9. Step 4.6 Open Question Resolutions

1. RuleExpr matching will use existing lowering artifacts for AND only; if this
   proves insufficient in implementation, stop and amend.
2. OR support is deferred to keep the first runtime tranche M-class.
3. `limit` applies after distinct de-duplication.
4. Entity-ref comparison uses canonical `idref_v1`; snapshots normalize to
   `.ref`.
5. Docs update includes quickstart + SDK docs + CHANGELOG deferred line, but
   only for shipped AND-only behavior.
