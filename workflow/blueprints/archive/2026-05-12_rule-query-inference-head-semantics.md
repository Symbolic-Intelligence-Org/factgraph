# Task Blueprint: Rule / Query / Inference head semantics design note

- Status: implemented
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/kernel/sdk`
  - `src/kernel/application`
  - `src/kernel/core`
- Related Docs:
  - [docs/references/working/design-points/rule-query-inference-head-semantics.zh.md](../../references/working/design-points/rule-query-inference-head-semantics.zh.md)
  - [src/kernel/sdk/docs/03_rules_and_inferences.en.md](../../../src/kernel/sdk/docs/03_rules_and_inferences.en.md)
  - [src/kernel/sdk/docs/04_api_surface.en.md](../../../src/kernel/sdk/docs/04_api_surface.en.md)
- Audit Log:
  - [2026-05-12_rule-query-inference-head-semantics.audit.md](./2026-05-12_rule-query-inference-head-semantics.audit.md)

## 1. Problem

Recent design discussion identified a conceptual mismatch in the public
positioning of `Rule`, `Query`, and `Inference`. All three share a similar
`where` language, but their head-like surfaces mean different things:
`Query.head` is projection, `Rule.select` is relation signature, and
`Inference.head` is conclusion / candidate target.

The immediate task is not to redesign this area before release. The task is to
record the design collision and future optimization direction as a
non-authoritative reference note.

## 2. Goals

- Capture the current conceptual mismatch without changing runtime behavior.
- Record the release stance: this should not block release unless a direct
  launch blocker is found.
- Preserve the head-related design discussion as future redesign input.
- Keep current implementation truth in module docs unchanged.

## 3. Non-goals

- No SDK API redesign in this slice.
- No renaming of `Rule`, `Query`, `Inference`, `CandidateSet`, or `head`.
- No evidence tree API changes.
- No updates to current module docs, because current behavior is unchanged.

## 4. Current Context

- Current SDK docs define `Rule`, `Query`, and `Inference` as separate DSL
  classes with shared `where` syntax.
- `Query` and `Rule` run through `fg.run(...)`.
- `Inference` runs through `fg.evaluate(...)` and returns `CandidateSet`.
- Evidence tree surfaces are currently tied to inference candidates rather than
  to a free-standing proof object.
- Application-layer `CompiledDerivationPlan` still has plural `heads`, while
  the public SDK `Inference` boundary is single-head.

## 5. Proposed Shape

Add a working design-point reference document under
`docs/references/working/design-points/`. The document must explicitly say it
is not current implementation truth and is intended as post-release redesign
input.

## 6. Boundaries And Invariants

- The reference note must not redefine current SDK behavior.
- The note must preserve the release-first stance.
- Any future implementation work must create a new active blueprint before
  changing public API, evidence behavior, or module docs.

## 7. Acceptance

- [x] Code behavior unchanged.
- [x] No public API or module-doc current-truth changes made.
- [x] New reference note records the head semantics collision and future
  redesign direction.
- [x] `docs/references/README.md` includes the new design-point note.
- [x] `docs/README.md` mentions the new design-point entry.

## 8. Implementation Plan

1. Add a design-point reference note for the Rule / Query / Inference head
   semantics discussion.
2. Update reference documentation index entries.
3. Archive this blueprint immediately because this is a documentation-only
   capture task with no code implementation phase.

## 9. Docs To Update

- `docs/references/working/design-points/rule-query-inference-head-semantics.zh.md`
- `docs/references/README.md`
- `docs/README.md`

## 10. Outcome / Deviations

- 最终落地结果：新增 non-authoritative design-point note，记录
  `Rule` / `Query` / `Inference` 三层的定位错位、head 语义碰撞、evidence
  归属问题、release stance 和 future redesign 方向。
- 与 blueprint 不同的地方：无。
- 为什么会有这些调整：不适用。
- 归档说明：本任务没有代码改动，蓝图创建后直接作为已实现的文档捕获任务归档。
