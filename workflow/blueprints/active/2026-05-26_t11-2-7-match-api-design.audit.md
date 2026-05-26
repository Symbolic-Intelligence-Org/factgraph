# Audit: T11.2.7 Match API Design

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-2-7-match-api-design.md`
- Stage: draft
- Class: M/L (predicted docs-only design synthesis)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve 6 modified tracked files plus untracked `rainbird-ai sdk code/`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | TBD | T11.2.7 blueprint pair drafted | Triggered by user-identified match API design gap and T11.2.5 facade.py verdict. |

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

## 3. Step 4.6 Inventory Checklist

To fill during scoped inventory:

| # | Item | Result |
|---|---|---|
| 1 | Active parent §4.9 / §6 references | TBD |
| 2 | Archived Query/View/Inference prior-art references | TBD |
| 3 | Shipped `Query` class / lower / runtime shape | TBD |
| 4 | Current public SDK exports and namespaces | TBD |
| 5 | Existing docs mentions of `fg.eval.run`, `Query`, and match-like behavior | TBD |
| 6 | Candidate namespace comparison | TBD |
| 7 | Candidate template type comparison | TBD |
| 8 | Candidate return shape comparison and facade impact | TBD |
| 9 | View integration and `view=` rule | TBD |
| 10 | `fg.eval.run` migration timing | TBD |
| 11 | Output location decision | TBD |
| 12 | Final class decision | TBD |
| 13 | Dirty baseline preservation check | TBD |

## 4. Verification Plan

- `git status --short --branch`.
- `git diff --check`.
- `git rev-parse master`.
- `rg` targeted sources for `read.match`, `fg.eval.run`, `Query`,
  `AssertionRecordSet.match`, and `fg.queries`.
- No tests required unless implementation accidentally touches code.

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 inventory complete.
- [ ] Namespace decision reviewed.
- [ ] Template type decision reviewed.
- [ ] Return shape decision reviewed.
- [ ] Facade impact reviewed.
- [ ] Closure notes filled.
