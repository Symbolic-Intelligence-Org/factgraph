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
2. Amend this blueprint if the audit surfaces new docs that must be in scope.
3. Move the blueprint to `scoped` before broad multi-file edits.
4. Update quickstart docs and affected module/service docs.
5. Verify with stale-symbol grep and lightweight docs sanity checks.
6. Fill Outcome / Deviations and archive the blueprint.

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
   registry-adapter and cross-doc seam symbols.
2. [Audit] Read `rule-expression-and-proof-attempt.zh.md` and the evidence-tree
   design point enough to classify S1-S6 / I10-A10 references as current,
   stale, or deferred.
3. [Blueprint] Amend scope if the audit surfaces additional current-truth docs.
4. [Scope] Mark this blueprint `scoped`.
5. [Quickstart] Update the relevant `docs/official/kernel/quickstart/` files.
6. [Module docs] Update any affected `src/factgraph/*/docs/` and
   `src/service/docs/` files.
7. [Verify] Run stale-symbol grep and lightweight docs sanity checks.
8. [Close] Fill Outcome / Deviations, mark `implemented`, and archive.

## 9. Docs To Update

Initial candidates:

- `docs/official/kernel/quickstart/*.md`
- `docs/references/working/design-points/rule-expression-and-proof-attempt.zh.md`
- `docs/references/working/design-points/evidence-tree-rainbird-style-v1.zh.md`
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
