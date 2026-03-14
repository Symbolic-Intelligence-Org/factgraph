# Blueprint Manual Review

## Goal

Resolve the remaining manual-review items in `docs/blueprint/` and decide whether each file should be treated as:

- current reference
- long-lived spec
- target-state blueprint
- history

This review uses the same standard as the broader docs cleanup:

1. classify by document role first
2. check semantic alignment against current code and current authoritative docs
3. if a file mixes multiple roles, recommend split or archival instead of forcing a single misleading label

## `docs/blueprint/factpy_kernel_compat_shim_cleanup.md`

**Scope**

Cleanup checklist for removing an older generation of compatibility shims after the `core` / `adapters.souffle` path split.

**Classification**

- `history`

**Key Evidence**

- The file is explicitly written as a staged removal checklist for a past migration wave: [factpy_kernel_compat_shim_cleanup.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/factpy_kernel_compat_shim_cleanup.md#L1).
- It lists top-level compatibility packages such as `src/factpy_kernel/protocol/`, `schema/`, `store/`, `export/`, and `runner/`: [factpy_kernel_compat_shim_cleanup.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/factpy_kernel_compat_shim_cleanup.md#L9).
- Those listed top-level shim directories are no longer present in the current tree; the active code now lives under `src/factpy_kernel/core/*` and `src/factpy_kernel/adapters/*`.
- It also lists `src/factpy_kernel/core/rules/where_compile.py` and `src/factpy_kernel/core/view/souffle_view_gen.py` as internal shims to delete: [factpy_kernel_compat_shim_cleanup.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/factpy_kernel_compat_shim_cleanup.md#L25), but those files are not present anymore.
- Current codebase docs still mention smaller remaining compatibility surfaces such as `core.store.api`, `Store.evaluate_dummy`, and `store/_*.py`, which are a different and narrower cleanup scope than this document tracks: [02_quality_assessment.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/core/docs/02_quality_assessment.md#L93), [03_progress_roadmap.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/core/docs/03_progress_roadmap.md#L61), [api.py](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/core/store/api.py#L3).

**Stale or Diverged Sections**

- The “current compatibility layers” section is no longer current for the package-level shims it lists.
- The removal batches no longer match the actual remaining compatibility work in the repository.

**Decision**

- Target area: `docs/history/migrations/`
- Do not treat it as an active plan
- If the remaining `core.store.api` / `evaluate_dummy` cleanup needs planning, create a new smaller-scope plan document instead of reusing this one

## `docs/blueprint/设计.md`

**Scope**

High-level design principles and compilation pipeline overview, from schema/rule authoring through export/runner targets.

**Classification**

- `history`

**Key Evidence**

- The opening sentence explicitly frames the file as a summary of previously practiced methods: [设计.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/设计.md#L1).
- The document uses older schema vocabulary such as `fact_key` and `functional`-style replace semantics: [设计.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/设计.md#L19), [设计.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/设计.md#L59).
- It points to outdated doc locations such as `/Users/zhenzhili/symbolic_agent/docs/Authoring 层契约.md` and `/Users/zhenzhili/symbolic_agent/docs/导出与运行.md`, while the actual files are under `docs/blueprint/`: [设计.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/设计.md#L24), [设计.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/设计.md#L88).
- The file ends abruptly at `# 数据层次:` and appears unfinished: [设计.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/设计.md#L90).

**Stale or Diverged Sections**

- The field/cardinality model still reflects the older `fact_key` / replace pipeline rather than the newer `single|multi` application/service-facing model.
- The document mixes concept design with a point-in-time implementation status section (`当前实现状态（2026-02）`), which will continue to age poorly.

**Decision**

- Target area: `docs/history/design-evolution/`
- Do not treat it as active blueprint or spec
- If any content is still valuable, mine only the high-level design principles into a newer overview doc; do not migrate this file wholesale

## `docs/blueprint/语法.md`

**Scope**

Unified syntax document spanning SDK object DSL, authoring DSL, and core `where` IR / AST validation rules.

**Classification**

- `spec` intent, but the current file is `partial` and should not be used as-is as authoritative

**Key Evidence**

- The file is trying to define semantic baseline and validation rules for `where` IR and the AST gate: [语法.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/语法.md#L13), [语法.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/语法.md#L33), [语法.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/语法.md#L221).
- The referenced implementation files exist and are active: `src/factpy_kernel/core/rules/where_ast.py`, `src/factpy_kernel/core/rules/where_ast_validate.py`, and the `where_eval/where_compile` gates.
- However, the SDK-facing examples are stale. For example, it still uses `Field(cardinality="functional")`: [语法.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/语法.md#L95), while current SDK docs define `single|multi`: [01_alignment_matrix.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/01_alignment_matrix.md#L10), [02_readwrite_and_ingest.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md#L86).
- It references `docs/service.md`, which is not the current location: [语法.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/语法.md#L70).
- It still presents derivation/store examples that do not match the current SDK reference surface documented in [03_rules_and_derivations.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/03_rules_and_derivations.md) and [02_readwrite_and_ingest.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md).

**Stale or Diverged Sections**

- SDK schema example uses old cardinality naming
- SDK derivation/store examples should defer to current SDK docs instead of restating them here
- Some path references are stale

**Decision**

- Target area after rewrite: `docs/architecture/specs/rules/`
- Do not archive it outright, because the `where` IR / AST validation parts are still valuable and close to normative semantics
- Required cleanup before migration:
  - split or reduce stale SDK-facing tutorial examples
  - keep the canonical `where` IR / AST sections
  - replace direct SDK behavior claims with links to [03_rules_and_derivations.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/03_rules_and_derivations.md)
  - fix stale links

## `docs/blueprint/审计.md`

**Scope**

Audit taxonomy and recommended storage/query model across assertion audit, run audit, candidate audit, materialization audit, mapping audit, and export audit.

**Classification**

- `blueprint`

**Key Evidence**

- The file is structured as a recommended audit inventory and future-oriented organization, not as a current implementation contract: [审计.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/审计.md#L7), [审计.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/审计.md#L317).
- The ending is explicitly conversational draft text: [审计.md](/Users/zhenzhili/symbolic_agent/docs/blueprint/审计.md#L327).
- The repository already has active audit implementation docs under [audit/docs/README.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/audit/docs/README.md) and [01_overview.md](/Users/zhenzhili/symbolic_agent/src/factpy_kernel/audit/docs/01_overview.md), so this file should not be treated as current audit reference.
- Some concepts align with implemented package artifacts such as run/candidate/accept audit ledgers, but the file also proposes broader logical containers like `ExportLedger`, `RunLedger`, and `MaterializeLedger` at a conceptual level rather than documenting the exact current contract.

**Stale or Diverged Sections**

- The conversational tail makes it unsuitable as a formal doc without cleanup
- Some ledger naming is conceptual rather than matching the exact exported artifact names

**Decision**

- Target area after cleanup: `docs/architecture/blueprints/audit/`
- Until rewritten, treat it as `draft`, not as current reference
- Required cleanup before migration:
  - remove the conversational ending
  - add status header clarifying that it is blueprint-only
  - link to current audit implementation docs under `src/factpy_kernel/audit/docs/`
  - distinguish clearly between “current exported audit artifacts” and “recommended future audit model”

## Final Outcome

Resolved manual-review items:

- `factpy_kernel_compat_shim_cleanup.md` -> `history`
- `设计.md` -> `history`
- `语法.md` -> `spec` intent, but rewrite required before promotion
- `审计.md` -> `blueprint` draft, rewrite required before promotion

This means the remaining high-risk ambiguity in `docs/blueprint/` is now materially smaller:

- `factpy_kernel_compat_shim_cleanup.md` should stop competing with any live cleanup plan
- `设计.md` should stop competing with active docs
- `语法.md` should be preserved, but only after being narrowed to real semantic spec content
- `审计.md` should be preserved as design intent, not mistaken for implementation reference
