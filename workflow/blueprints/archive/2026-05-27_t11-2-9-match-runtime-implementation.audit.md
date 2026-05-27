# Audit: T11.2.9 Match Runtime Implementation

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t11-2-9-match-runtime-implementation.md`
- Stage: implemented
- Class: M (first runtime tranche: Rule + AND RuleExpr + docs/tests)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current 4 modified tracked files plus untracked `rainbird-ai sdk code/`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | `90b6c59e` | T11.2.9 blueprint pair drafted | Triggered by user selecting N9 after T11.2.7 match design and T6 evidence design were published. |
| 2026-05-27 | scoped | `ee59414d` | Step 4.6 match runtime inventory recorded | OR support deferred; idref comparison, materialized matcher, test matrix, and docs scope locked. |
| 2026-05-27 | implementation | `4dad8a33` | Runtime core implemented | Added `sdk/match_runtime.py` plus `fg.read.match(...)` / `SDKStore.match(...)` wiring. |
| 2026-05-27 | implementation | `37e3662c` | Match runtime tests added | New focused matrix plus attach-view scoped match coverage. |
| 2026-05-27 | implementation | `49960bef` | Match runtime docs updated | Quickstart, SDK docs, and CHANGELOG now teach only shipped AND-only match behavior. |
| 2026-05-27 | closure | this commit | T11.2.9 implemented | Outcome, full-discovery caveat, and verification recorded. |

## 2. Pre-Draft Source Scan

Read-only draft scan findings:

- `match-api-design.zh.md` commitments M1-M21 lock the target runtime shape:
  `fg.read.match(EntityCls, template, **kwargs) -> tuple[EntityCls snapshot, ...]`.
- `_SDKReadManager` currently exposes `get`, `find`, and `ref`, but no `match`
  method (`src/factgraph/sdk/store.py` read namespace).
- `SDKStore.find(...)` rejects method-level `view=` with the T11.1 attach hint
  and delegates to `sdk_find(...)`; match should mirror that rejection style.
- `sdk_find(...)` and snapshot hydration live in `src/factgraph/sdk/facade.py`;
  Step 4.6 must decide whether match reuses those helpers or lower-level
  entity-view DTO helpers.
- Application `Rule` carries `ports` and inferred `_port_types`; legacy `Query`
  still exists but is not the v0.2 match template.
- RuleExpr has existing join/lowering/inspect substrate, but draft did not yet
  verify whether it is enough for direct read-side matching.

## 3. Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | SDK read namespace call chain | `_SDKReadManager` currently exposes `get` / `find` / `ref` and no `match` at `src/factgraph/sdk/store.py:527-559`; `SDKStore.read` returns that manager at `store.py:1186-1189`; `SDKStore.find(...)` is at `store.py:1265-1286`. Add read manager + store match entrypoints next to `find`. |
| 2 | Snapshot hydration path | `sdk_find(...)` validates entity class, calls `execute_read_request(mode="find")`, and hydrates DTOs to SDK snapshots at `src/factgraph/sdk/facade.py:585-669`; `_build_snapshot(...)` and `_dto_to_sdk_snapshot(...)` exist at `facade.py:794-851`. Match should reuse these helpers instead of constructing snapshots directly. |
| 3 | Rule ports / `_port_types` projection data | `Rule.__post_init__` validates and freezes ports, then sets `_port_types` at `src/factgraph/application/protocol/rule.py:85-104`; entity-ref type inference comes from `:exists` atoms at `rule.py:508-545`. Projection validation can require exactly one `PortType(kind="entity_ref", entity_type=EntityCls.__name__)`. |
| 4 | RuleExpr lowering / inspect support | RuleExpr supports AND/OR via factories/operators at `rule_expr.py:43-64`; joins only attach to `_AndGroup`, and OR group join methods raise at `rule_expr.py:97-131`; lowering branches expose `body_atoms`, `occurrence_aliases`, and `pending_joins` at `rule_expr_lowering.py:99-137`; lowerer supports OR branches at `rule_expr_lowering.py:614-625`. T11.2.9 supports only single Rule and AND RuleExpr; OR raises unsupported for first tranche. |
| 5 | SDK Field descriptor validation path | SDK `Field` descriptors are declared at `src/factgraph/sdk/schema.py:91-125`; descriptor names come from `_DeclaredMember.sdk_attr_name` at `schema.py:22-33`; `SDKStore._index_schema` maps descriptor objects to schema predicate/declaration at `store.py:3010-3033`. Own-class Field kwargs are valid only when descriptor belongs to the projected EntityCls; cross-entity descriptors reject. |
| 6 | Legacy Query runtime reuse / non-reuse | Legacy `Query` is defined at `src/factgraph/sdk/dsl/rule.py:198-224` with head/where projection semantics. `execute_query_plan(...)` lowers to a `QueryRuntimeRequest` and returns dict/instance rows at `sdk/query_runtime.py:35-74`; it dedups rows by row key at `query_runtime.py:200-240`. It is not reused as the public match path because it preserves Query-head semantics, but row dedup ideas may inform implementation. |
| 7 | Pattern connectivity algorithm data sources | Single Rule connectivity uses `Rule.where` atoms and `Rule.ports`. AND RuleExpr connectivity uses lowered branch atoms/pending joins from `RuleExprLoweringBranch` and `RuleJoinConstraint` materialization data (`rule_expr_lowering.py:99-145`, `:629-650`). Synthetic F-expression kwargs add edges between the constrained port var and projected entity var. OR is rejected before connectivity. |
| 8 | View-scoped attach read path | `FactGraph.attach(db, view=view)` replaces the ledger via `_ledger_for_durable_database_view(...)` and marks the runtime read-only at `store.py:1078-1114`. `sdk_find(...)` reads `sdk.store` (`facade.py:642-652`), so match must also read only `self.store` / `self.ledger`, not `Database.head()`. |
| 9 | Error taxonomy and message lock | Public runtime rejections use `SDKStoreError`. Locked messages: method-level `view=` mirrors find (`store.py:1275-1278`); unsupported OR: `"fg.read.match(...) currently supports Rule and AND RuleExpr only"`; unsupported Query/list/tuple names accepted types; unknown port lists valid ports; cross-entity Field says use `RuleExpr.join_by_ports`; disconnected pattern mentions cross-product risk. |
| 10 | Test matrix | New `tests/test_sdk_read_match_runtime.py`: Rule literal constraints, own-class Field constraints, idref/snapshot entity-ref constraints, distinct snapshots, limit-after-dedup, projection missing/ambiguous, unknown port, Query/list/tuple reject, OR reject, disconnected reject. Extend `tests/test_db_attach_lifecycle.py` for attach-view scoped match and method-level `view=` rejection. Run existing RuleExpr suites: `tests/application/protocol/test_rule_expr.py`, `tests/application/protocol/test_rule_expr_lowering.py`, `tests/sdk/test_rule_expr_evaluate.py`. |
| 11 | User docs update set | If runtime lands, update `docs/official/kernel/quickstart/read-write.md`, `docs/official/kernel/quickstart/rules-and-inferences.md`, `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`, and `src/factgraph/sdk/docs/04_api_surface.en.md`. Existing quickstart currently teaches Query as future/internal and `read.find(...)` as snapshot read (`rules-and-inferences.md`, `read-write.md` grep hits); docs must teach only AND match behavior. |
| 12 | Release-facing docs/deferred language update set | `CHANGELOG.md:53-58` currently lists "Match API implementation" as deferred. If match lands, remove that phrase while keeping witness/assertion-returning output, method-level view, as_of, EvidenceGraph Phase B, and adapter-consuming semantics deferred. No release machinery changes. |
| 13 | Stop-amend findings and final class | No blocker for Rule + AND RuleExpr first tranche. OR support is explicitly deferred and recorded in `match-api-design.zh.md`. Final class narrows to M. Stop/amend if AND RuleExpr matching still requires broad runtime redesign during implementation. |

## 3.1 Final Scoped Decisions

| Decision | Lock |
|---|---|
| OR support(N1) | Defer. T11.2.9 implements single Rule and AND-only RuleExpr. OR `RuleExpr.any(...)` / `|` raises clear unsupported error and gets a follow-up runtime tranche. |
| Entity-ref comparison(N2) | Compare canonical `idref_v1` tokens. Snapshot constraints normalize to `.ref`; Python object identity is never used. |
| Runtime strategy(N3) | Use a materialized first-tranche matcher with visible snapshot/candidate enumeration, effective AND pattern filtering, and no new index. Future optimization trigger: performance failure, large datasets, streaming, OR, or pagination. |
| Test matrix(N4) | New match runtime test module plus attach lifecycle extension, as listed in inventory item 10. |
| Connectivity RuleExpr path(N5) | Single Rule graph from `where`; AND RuleExpr graph from lowered branch atoms + pending joins + synthetic F-expression atoms; OR rejected before connectivity. |
| Limit timing | Apply `limit` after distinct de-duplication. |
| Docs scope | Quickstart + SDK docs + CHANGELOG deferred line only after runtime passes. No OR/witness/Query adapter teaching. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| RuleExpr matching needs broad new runtime | Could escalate from M/L to L | Inspect existing lowering/join data before implementation. |
| Connectivity check cannot see all effective vars | M21 safety invariant would be under-specified | Prototype/check data sources before coding. |
| F-expression kwargs cannot be represented without mutating Rule | Violates M15 | Confirm synthetic constraint strategy. |
| View-scoped match reads current head by accident | Violates T11.1 | Use attach-view tests and source inspection. |
| Docs overclaim witness/query persistence | User-facing confusion | Keep docs scoped to shipped tuple snapshots. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 inventory complete.
- [x] Runtime scope accepted or amended.
- [x] Test matrix accepted.
- [x] Docs update scope accepted.
- [x] Implementation reviewed.
- [x] Closure notes filled.

## 6. Closure Notes

T11.2.9 shipped the first read-side match runtime tranche:

- Public entry: `fg.read.match(EntityCls, Rule | AND RuleExpr, *, limit=None, **port_constraints)`.
- Runtime core: `src/factgraph/sdk/match_runtime.py` reuses Rule/RuleExpr
  lowering, `project_view_facts(...)`, `evaluate_where(...)`, and existing
  snapshot hydration. It returns distinct projected snapshots and applies
  `limit` after de-duplication.
- Scope preserved: OR, legacy Query adapter, witness/assertion output,
  cross-entity tuple output, method-level `view=`, service/OpenAPI, and
  EvidenceGraph changes remain deferred.
- Error coverage: unsupported OR, unsupported template, unknown port,
  cross-entity Field, disconnected pattern, projection missing/ambiguous, and
  method-level `view=` all raise `SDKStoreError` with scoped messages.
- Tests: `tests.test_sdk_read_match_runtime` + `tests.test_db_attach_lifecycle`
  passed 22 tests; the broader focused RuleExpr/match/attach suite passed
  108 tests.
- Full discovery note: `PYTHONPATH=src python -m unittest discover tests`
  ran 1998 tests and reported unrelated existing legacy/frontier/why-not and
  stale invariant failures. This was recorded in the blueprint outcome and is
  not a T11.2.9 gate.
- Verification: touched-file ruff and `git diff --check` passed; dirty
  baseline and sacred master were preserved.
