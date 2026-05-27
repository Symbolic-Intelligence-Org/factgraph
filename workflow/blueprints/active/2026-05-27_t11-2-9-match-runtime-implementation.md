# Task Blueprint: T11.2.9 Match Runtime Implementation

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: M/L (runtime + tests + user docs; may narrow after Step 4.6)
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
2. **Template support**: accept application `Rule` and `RuleExpr`; reject
   legacy `Query`, bare list/tuple, and unsupported objects with helpful
   `SDKStoreError` / DSL error text.
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
- RuleExpr matching cannot be implemented without broad lowering/runtime
  redesign beyond M/L scope;
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
| M5-M7 | Accept `Rule` / `RuleExpr`; do not use legacy `Query` head semantics. |
| M8 | Pattern matching only; no inference engine involvement. |
| M9-M11 | Return `tuple[EntityCls snapshot, ...]`; no wrapper DTO or chain methods. |
| M12-M15 | Literal / own-class Field kwargs compose synthetic constraints; Rule objects remain immutable. |
| M16 | Attach-time view scope only; method-level `view=` rejected. |
| M17-M18 | No witness/assertion output and no cross-entity tuple output. |
| M19 | Do not delete `fg.eval.run`. |
| M20 | Do not couple to assertion facade ergonomics. |
| M21 | Reject disconnected effective patterns before matching. |

## 5. Step 4.6 Inventory Plan

Scoped inventory must fill concrete results for:

1. Existing SDK read namespace call chain (`fg.read.match` absence, `find`
   patterns, aliases).
2. Existing snapshot hydration path and whether match should reuse `sdk_find`,
   `sdk_get`, or lower-level helpers.
3. Current Rule `ports` / inferred `_port_types` API and how to identify the
   unique EntityCls projection port.
4. Current RuleExpr lowering/inspect APIs and whether they expose enough
   occurrence/port/join information for match.
5. Field descriptor object shape in `src/factgraph/sdk/schema.py` and how to
   validate own-class vs cross-entity Field kwargs.
6. Existing query runtime and whether any narrow helper can be reused without
   exposing legacy `Query`.
7. Pattern connectivity algorithm data sources for Rule and RuleExpr, including
   synthetic kwarg atoms.
8. View-scoped attach data path: which in-memory ledger/snapshot data match
   should read from in attached and non-attached runtimes.
9. Error taxonomy: `SDKStoreError` vs DSL errors and exact messages for
   projection ambiguity, unknown port, unsupported template, cross-entity Field,
   disconnected pattern, and method-level `view=`.
10. Test matrix and expected new test files / modified existing files.
11. User docs files to update once runtime lands.
12. Release-facing docs/deferred language to update once runtime lands.
13. Stop-amend findings and final class decision.

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
- [ ] `fg.read.match(EntityCls, RuleExpr, **kwargs)` works for joined patterns.
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
python -m unittest tests.test_<new_match_runtime_module>
python -m unittest tests.test_db_attach_lifecycle tests.test_sdk_frozen_view_read_runtime_boundaries
python -m unittest tests.test_rule_expr_evaluate tests.test_rule_expr_lowering tests.test_rule_expr_inspect
python -m ruff check <touched files>
git diff --check
git status --short --branch
```

## 9. Open Questions For Step 4.6

1. Can RuleExpr matching reuse existing lowering artifacts directly, or does N9
   need a small read-side matcher helper?
2. Should the first runtime support OR (`RuleExpr.any` / `|`) immediately, or
   should OR support trigger a split? T11.2.7 permits `RuleExpr`, but Step 4.6
   must verify cost.
3. Should `limit` be applied before or after distinct projection de-duplication?
   Default leaning: after de-duplication to match returned tuple semantics.
4. How should match compare entity_ref port values: encoded `idref_v1`, snapshot
   identity mapping, or both? Step 4.6 must lock one consistent path.
5. Which docs should update now: minimal quickstart only, or full SDK docs/API
   surface plus CHANGELOG deferred language?
