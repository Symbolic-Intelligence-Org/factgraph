# Task Blueprint: Cross-Doc Seams And Quickstart Refresh

- Status: draft
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Related Modules:
  - `docs/official/kernel/quickstart/`
  - `docs/references/working/design-points/`
  - `src/factgraph/*/docs/`
  - `src/service/docs/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [Slice 7C registry final removal archive](../archive/2026-05-21_registry-final-removal.md)
  - [Q6-A registry adapter final removal decision](../../decisions/2026-05-21_q6a-registry-adapter-final-removal-decision.md)
- Audit Log:
  - [2026-05-22_cross-doc-seams-quickstart-refresh.audit.md](./2026-05-22_cross-doc-seams-quickstart-refresh.audit.md)

## 1. Problem

Slice 1-7C closed the DB/view migration and v0.2.0 registry-final-removal chain,
but the user-facing and cross-reference documentation still needs a post-Slice-7C
consistency pass. The main risks are:

- Cross-doc seam references may still describe pre-Slice-7C registry adapters,
  filesystem `registry_root=` flows, or unresolved S1-S6 / I10-A10 seams as if
  they were current implementation truth.
- `docs/official/kernel/quickstart/` needs a coherent user-facing update after
  the registry adapter removal, migration CLI, and in-memory rule/inference
  shape changes.
- Some module docs may still contain stale wording from older Slice 5-7B
  transitional states.

## 2. Goals

- Audit the relevant cross-doc seams before editing durable docs.
- Keep current implementation truth in module docs and quickstart docs, not only
  in references or memory.
- Update quickstart documentation for the post-Slice-7C user path:
  workspace persistence, migration CLI, in-memory rules/inferences, audit
  readback, and removed registry APIs.
- Fix stale references in module/service docs that conflict with the archived
  Slice 7C outcome.

## 3. Non-goals

- Do not edit source code.
- Do not reopen Q1-Q8 or Q6-A decisions.
- Do not publish, tag, push, or start v0.2.0 release operations.
- Do not rewrite legacy archive entries or historical blueprint text.
- Do not convert `docs/references/working/design-points/` wholesale into current
  truth documents.
- Do not touch unrelated dirty files unless they are explicitly in scope and
  re-read as part of the docs audit.

## 4. Current Context

- Current implementation base: Slice 7C impl branch at `f592733a`.
- Current docs feature branch:
  `v0.2.0-docs-cross-doc-quickstart-2026-05-22`.
- Slice 7C archived the registry adapter final-removal blueprint at `a46771c6`.
- Q6-A closed the registry adapter final-removal decision at `c9aeafae`.
- Known unrelated dirty files remain outside this task unless independently
  accepted into scope.

## 5. Proposed Shape

Use a docs-only workflow:

1. Audit cross-doc seam references and quickstart/module docs with `rg` and
   targeted reads.
2. Treat `docs/references/working/design-points/*` as non-authoritative
   reference material. Add current-truth pointers / warning notes where a seam
   could mislead users, but do not rewrite the full future design documents.
3. Rewrite user-facing quickstart persistence content around current Slice 7C
   behavior: in-memory rules/inferences, workspace save/load, and
   `python -m factgraph migrate-workspace`.
4. Fix quickstart namespace/rules pages that still teach saved-rule handles.
5. Update affected module/service docs only when grep shows live-contract drift.
6. Verify with stale-symbol grep and lightweight docs sanity checks.
7. Fill Outcome / Deviations and archive the blueprint.

## 5.1 Audit Findings

| Finding | Severity | Resolution |
| --- | --- | --- |
| A-1 | Required | `docs/official/kernel/quickstart/persistence.md` is still built around `SavedRuleRef`, `SavedInferenceRef`, `fg.rules.save/load/list/get`, `fg.inferences.save/load/list/get`, and workspace `registry/`. Rewrite this page rather than patching small snippets. |
| A-2 | Required | `docs/official/kernel/quickstart/rules-and-inferences.md` still points users to saved refs and a persistence surface. Remove that model; teach in-memory `Rule` / `Inference` values only. |
| A-3 | Required | `docs/official/kernel/quickstart/namespace-map.md` still lists `fg.rules.save/load/list/get`, `fg.inferences.save/load/list/get`, `SavedRuleRef`, and `SavedInferenceRef`. Align namespace table with Slice 7C. |
| A-4 | Recommended | `docs/official/kernel/quickstart/index.md` names the persistence page "Save rules, inferences, and workspaces". Rename the user path to workspace persistence / migration. |
| A-5 | Recommended | `rule-expression-and-proof-attempt.zh.md` and `evidence-tree-rainbird-style-v1.zh.md` are working references, not current truth. Add or preserve explicit current-truth pointers so S1-S6 / I10-A10 do not block quickstart updates. |
| A-6 | Verified | `docs/official/kernel/quickstart/evidence.md` preserves `registry=None` runtime `RuleRegistry` examples; keep these because they are not filesystem registry adapters. |

## 6. Boundaries And Invariants

- `master @ 562c74195df43e933bed92a3ff25de94dd8ce666` remains untouched.
- Slice 7C implementation commits remain untouched.
- Cross-doc seam work is documentation alignment only; source behavior remains
  defined by the implementation branch and module docs.
- Runtime in-memory `RuleRegistry` / `registry=None` examples must be preserved
  when they describe current runtime rule semantics, not filesystem registry
  adapters.
- Historical archive docs may mention removed APIs as history; do not rewrite
  them unless explicitly marked as reconstructed/current.
- `docs/references/working/design-points/readme.md` is currently user-dirty;
  do not edit it in this task unless the user explicitly brings it into scope.

## 7. Acceptance

- [ ] Cross-doc seam audit is recorded in this blueprint/audit log.
- [ ] Quickstart docs no longer teach deleted filesystem registry adapters as
  live APIs.
- [ ] User-facing persistence docs describe the migration CLI and post-Slice-7C
  workspace layout.
- [ ] Rules/inferences docs describe in-memory values and removed persistence
  handles accurately.
- [ ] Evidence docs preserve valid runtime `registry=None` examples while
  removing filesystem-registry confusion.
- [ ] Module/service docs touched by the sweep agree with current source.
- [ ] Stale-symbol grep has only historical/removed-context hits, not live API
  instructions.
- [ ] No source code changes are included.

## 8. Implementation Plan

1. [Audit] Grep quickstart, module docs, service docs, and design-point refs for
   registry-adapter and cross-doc seam symbols. Completed in A-1 through A-6.
2. [Audit] Read `rule-expression-and-proof-attempt.zh.md` and the evidence-tree
   design point enough to classify S1-S6 / I10-A10 references as reference-only
   future design, not current implementation truth.
3. [Scope] Mark this blueprint `scoped`.
4. [Quickstart] Rewrite `persistence.md`.
5. [Quickstart] Update `rules-and-inferences.md`, `namespace-map.md`, and
   `index.md`.
6. [References] Add narrow current-truth warning/pointer notes to the two
   design-point documents if needed; do not edit the dirty design-points README.
7. [Module docs] Update any affected `src/factgraph/*/docs/` and
   `src/service/docs/` files.
8. [Verify] Run stale-symbol grep and lightweight docs sanity checks.
9. [Close] Fill Outcome / Deviations, mark `implemented`, and archive.

## 9. Docs To Update

Initial candidates:

- `docs/official/kernel/quickstart/*.md`
- `docs/references/working/design-points/rule-expression-and-proof-attempt.zh.md`
- `docs/references/working/design-points/evidence-tree-rainbird-style-v1.zh.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/*/docs/*.md`
- `src/service/docs/*.md`

Final list will be locked after audit.

## 10. Outcome / Deviations

Task completion will record:

- Final updated docs:
- Audit findings:
- Deviations from this draft:
- Verification:
- Archive note:
