# Audit: T11.2.7 Match API Design

- Status: scoped
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-2-7-match-api-design.md`
- Stage: scoped
- Class: M/L (predicted docs-only design synthesis)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve 6 modified tracked files plus untracked `rainbird-ai sdk code/`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | `83e452f3` | T11.2.7 blueprint pair drafted | Triggered by user-identified match API design gap and T11.2.5 facade.py verdict. |
| 2026-05-26 | scoped | TBD | Step 4.6 match API design inventory recorded | Namespace/template/return-shape comparison matrices locked; design remains docs-only. |
| 2026-05-26 | scoped-amend | TBD | V2 match ergonomics incorporated | User rejected evaluate-style wrapper parsing; scoped design now locks snapshot/value-native `MatchView` with kwargs and `.select(...)`. |

## 2. Pre-Draft Source Scan

Read-only scan findings:

- Active parent `rule-expression-and-proof-attempt.zh.md` has §6 as a TOC
  stub but §4.9 already demonstrates `fg.read.match(R1)` /
  `fg.read.match(R1 & R2)` / `fg.read.match(RuleExpr.all(...))` as a
  type-boundary illustration.
- Archived `query-view-and-inference-handles.zh.md` is the most direct prior
  art. It separates Query/Search from Inference, warns that Query rows lack
  witness assertion ids, and explicitly lists future questions including
  `AssertionRecordSet.match(query)` and namespace migration away from
  `fg.eval.run(query)`.
- Archived `factgraph-lifecycle-and-assets.zh.md` §9.3 says Query persistence
  (`fg.queries.save/load/list`) is future work and should not be exposed for
  symmetry before real persistence exists.
- Shipped SDK still exports legacy `Query` from `src/factgraph/sdk/dsl/rule.py`;
  `query_lower.py` and `query_runtime.py` lower it to runtime rows/snapshots,
  not witness assertion sets.
- T11.1/T11.2 established attach-time view scoping and continued rejection of
  method-level `view=`.

## 3. Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | Active parent §4.9 / §6 references | Parent §6 is a TOC stub at `rule-expression-and-proof-attempt.zh.md:31`; §4.9 shows `fg.read.match(R1)`, `fg.read.match(R1 & R2)`, and `fg.read.match(RuleExpr.all(R1, R2))` at lines 664-674. |
| 2 | Archived Query/View/Inference prior-art references | `query-view-and-inference-handles.zh.md:30-33` says Query returns rows/snapshots/scalars, not witness records; lines 69-82 say `AssertionRecordSet` is assertion selection, not general query engine; lines 186-198 sketch `fg.query.match(...)` and `AssertionRecordSet.match(query)` only as possible future directions. |
| 3 | Shipped `Query` class / lower / runtime shape | `sdk/dsl/rule.py:198-220` defines legacy `Query(head, where, on_missing, on_type_mismatch)`; `query_lower.py:25-80` lowers it into a digest query rule plan; `query_runtime.py:35-74` returns dict rows or instances, not witness ids. |
| 4 | Application `Rule` vs legacy `Query` comparison | Application `Rule` is `id + where + ports` with no projection head (`application/protocol/rule.py:53-120`); legacy `Query` has `head` as projection/return contract and no ports (`sdk/dsl/rule.py:198-220`). Match should be Rule/RuleExpr-port based, not Query-head based. |
| 5 | Current public SDK exports and namespaces | `sdk/__init__.py:39-55` imports `Rule`, `RuleExpr`, `Inference`, and `Query`; `__all__` includes them at lines 100-115. `Query` is still public legacy DSL, but not chosen as the primary match template. |
| 6 | Existing docs mentions | SDK docs still discuss Query and `fg.eval.run` removal; active parent has C63 trigger references at `rule-expression-and-proof-attempt.zh.md:955`, `:1588`, `:1610`; roadmap also lists parent §5.12 `fg.eval.run` deletion trigger as replacement read/match/query entrypoint locked. |
| 7 | Candidate namespace comparison | Matrix recorded in §3.1 below. Chosen namespace: `fg.read.match(...)`. |
| 8 | Candidate template type comparison | Matrix recorded in §3.2 below. Chosen templates: `Rule | RuleExpr`; no list/tuple shorthand; legacy `Query` compatibility deferred. |
| 9 | Candidate return shape comparison and facade impact | Matrix recorded in §3.3 below. Chosen semantic return shape: transparent `MatchView` rows with direct snapshot/value port access and `.select(...)`, not `AssertionRecordSet`, `Claim`, `EvaluateRow`, or `Explanation`. Dirty `facade.py` is not required by match. |
| 10 | View integration and `view=` rule | T11.1 store has attach-time view support and method-level `view=` rejection (`store.py:1083-1107`, `:1275-1278`). Match follows attach-only view scoping; no method-level `view=` in v0.2. |
| 11 | `fg.eval.run` migration timing | This design locks replacement direction only. Deletion remains future hard-cut after `fg.read.match(...)` implementation/docs migration; T11.2.7 does not delete or edit `run`. |
| 12 | Port constraint syntax | User feedback rejects `match(rule=RuleExpr, ports={...})` unless no better option exists. Scoped design chooses `fg.read.match(template, **port_constraints)` plus `.where(**port_constraints)`; control knobs use chaining methods like `.limit(n)`. |
| 13 | Output location decision | Use a new active design-point `workflow/design/design-points/active/match-api-design.zh.md`; add only a narrow parent §6 cross-link/stub. Avoid D-doc only because this is synthesis, not a single decision. |
| 14 | Final class decision | Class narrows from M/L to M for scoped design work: docs-only synthesis plus one parent cross-link, no implementation, no new DTO, no release machinery. |
| 15 | Dirty baseline preservation check | Scoped commit edits only blueprint/audit files. Dirty baseline remains 6 modified tracked files plus untracked `rainbird-ai sdk code/`. |

### 3.1 Namespace Comparison Matrix

| Candidate | Pro | Con | Shipped impact | Result |
|---|---|---|---|---|
| `fg.read.match(...)` | Aligns parent §4.9; keeps match in read namespace; separates search from inference/evidence. | Requires future new read method. | No current code change in this design cycle. | **Chosen.** |
| `fg.assertions.match(...)` | Directly connected to assertion-record filtering. | Too narrow for snapshot/value rows; prior note warns `AssertionRecordSet` is not a general query engine. | Would couple to dirty `facade.py`. | Rejected as primary v0.2 namespace. |
| `AssertionRecordSet.match(...)` | Chainable after assertion selection. | Puts query engine into record-set DSL; only works after caller already has assertions. | Would force facade design first. | Rejected/deferred. |
| `fg.query.match(...)` / `fg.queries.*` | Names Query/Search explicitly. | Query persistence is deferred; `fg.queries` should not exist only for symmetry. | Would imply query asset namespace. | Rejected/deferred. |
| `fg.eval.run(...)` / `rules.run(query)` | Historical surface. | T5 froze/deprecated run and uses `eval` for evaluate/explain, not read matching. | Conflicts with C63 replacement intent. | Freeze only, not target. |

### 3.2 Template Type Comparison Matrix

| Candidate | Pro | Con | Result |
|---|---|---|---|
| Application `Rule` | Current top-level `factgraph.sdk.Rule`; `ports` give explicit output contract. | Requires `build_application_rule(...)` bridge in docs. | **Chosen.** |
| `RuleExpr` | Supports composed AND/OR/join match templates; parent §4.9 already demonstrates it. | Requires RuleExpr validity/join constraints. | **Chosen.** |
| Legacy `Query` | Existing object with projection head. | Head/projection model differs from Rule ports; keeps old Query mental model alive. | Compatibility/deferred; not primary v0.2 match template. |
| list/tuple of Rules | Convenient multi-template input. | Ambiguous AND vs OR; duplicates `RuleExpr.all/any(...)`. | Rejected; use `&`, `|`, or RuleExpr factories. |

### 3.3 Return Shape / Facade Impact Matrix

| Candidate | Pro | Con | Facade impact | Result |
|---|---|---|---|---|
| Transparent `MatchView` rows + `.select(...)` | Fits `Rule.ports`; supports entity and scalar ports; entity ports resolve to snapshots and value ports return raw values; `.select("port")` yields direct snapshots/values. | Exact runtime class mechanics deferred to implementation blueprint. | Dirty `facade.py` not required. | **Chosen semantic shape.** |
| `AssertionRecordSet` | Reuses assertion selection and makes `facade.py` directly relevant. | Cannot naturally express multi-port snapshot/value rows; prior note says it is not a general query engine. | Would make dirty `facade.py` blocking. | Rejected as primary match return. |
| Rows + witness assertion ids | Bridges to views/assertion selection. | Witness semantics not designed; risk of accidental evidence/proof semantics. | Future bridge may use assertion APIs later. | Future/deferred. |
| `Claim` / `EvaluateRow` / `Explanation` | Reuses T5 DTO ladder. | These are evaluation/explanation/evidence outputs, not read-side matching. | No direct facade relation. | Rejected. |

### 3.4 Constraint Syntax / Head Treatment

| Topic | Scoped result |
|---|---|
| Positional input | `fg.read.match(template, ...)` where `template` is the only required positional argument. |
| Port constraints | Direct kwargs: `fg.read.match(rule, region="US")`; chained `.where(region="US")` accumulates constraints. |
| Control parameters | Avoid keyword conflicts by using chain methods (`.limit(n)`, `.select(...)`, `.one()`, `.first()`, `.count()`), not control kwargs. |
| Head/projection | Match output is determined by Rule/RuleExpr ports. Query/evaluate-style head/projection does not control match output. |
| Row visibility | `MatchRow` may exist internally, but user examples should prefer attribute access (`row.user`) and `.select("user")` for direct snapshots. |

## 4. Verification Plan

- `git status --short --branch`.
- `git diff --check`.
- `git rev-parse master`.
- `rg` targeted sources for `read.match`, `fg.eval.run`, `Query`,
  `AssertionRecordSet.match`, and `fg.queries`.
- No tests required unless implementation accidentally touches code.

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 inventory complete.
- [x] Namespace decision reviewed.
- [x] Template type decision reviewed.
- [x] Return shape decision reviewed.
- [x] Facade impact reviewed.
- [x] V2 snapshot/value-native ergonomics reviewed.
- [ ] Closure notes filled.
