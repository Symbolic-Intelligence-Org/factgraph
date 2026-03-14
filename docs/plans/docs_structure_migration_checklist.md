# Docs Structure Migration Checklist

## Goal

This checklist defines how the current `docs/` contents should be reclassified so later cleanup can be done without mixing:

- current truth
- canonical semantics
- target design
- unfinished plans
- how-to guidance
- historical context

This phase does not move files yet.

It establishes the target role for each major area and identifies the highest-risk ambiguities.

## Target Structure

```text
docs/
  README.md
  reference/
  architecture/
    specs/
    blueprints/
  plans/
  guides/
  history/
```

## Priority Legend

- `P0`
  - highly misleading if left ambiguous
- `P1`
  - important cleanup, but low immediate implementation risk
- `P2`
  - useful structural cleanup, lower urgency

## Root-Level Mapping

| Current path | Target role | Proposed target area | Priority | Notes |
| --- | --- | --- | --- | --- |
| `docs/application_protocol_spec.md` | reference | `docs/reference/application/` | P0 | current application protocol contract; tied to existing code |
| `docs/application_projection_blueprint.md` | blueprint | `docs/architecture/blueprints/application/` | P0 | contains both completed and pending migration state |
| `docs/frontend_entity_ui_design.md` | blueprint | `docs/architecture/blueprints/frontend/` | P0 | frontend interaction design, not verified current implementation |

## Directory-Level Mapping

| Current path | Target role | Proposed target area | Priority | Notes |
| --- | --- | --- | --- | --- |
| `docs/api/` | reference | `docs/reference/service/api/` | P1 | current service DTO and endpoint contract |
| `docs/tutorials/` | guide | `docs/guides/tutorials/` | P1 | instructional material and troubleshooting |
| `docs/plans/` | plan | `docs/plans/` | P2 | already close to intended role |
| `docs/Logs/` | history | `docs/history/logs/` | P0 | design logs and implementation records should not be treated as current truth |
| `docs/blueprint/` | mixed | split required | P0 | currently mixes specs, blueprints, current implementation docs, and historical design |
| `docs/history/legacy/sdk/` | history | `docs/history/legacy/sdk/` | P0 | previously `docs/sdk_old/`; archived legacy snapshot, non-authoritative |

## `docs/blueprint/` Split Recommendation

### Move to `docs/reference/`

| Current path | Proposed target area | Priority | Why |
| --- | --- | --- | --- |
| `docs/blueprint/candidate_protocol_v2.md` | `docs/reference/core/` | P0 | title explicitly says `Current Implementation Spec` |
| `docs/blueprint/service.md` | `docs/reference/service/` | P0 | describes current `service v1` boundary and current API grouping |

### Move to `docs/architecture/specs/`

| Current path | Proposed target area | Priority | Why |
| --- | --- | --- | --- |
| `docs/blueprint/规范.md` | `docs/architecture/specs/schema/` | P0 | canonical schema semantics |
| `docs/blueprint/断言层 证据层.md` | `docs/architecture/specs/core/` | P0 | canonical assertion/evidence semantics |
| `docs/blueprint/视图层.md` | `docs/architecture/specs/core/` | P0 | canonical view semantics |
| `docs/blueprint/导出与运行.md` | `docs/architecture/specs/runtime/` | P1 | canonical exporter/runner semantics |
| `docs/blueprint/Authoring 层契约.md` | `docs/architecture/specs/authoring/` | P0 | canonical authoring-to-IR contract |
| `docs/blueprint/Authoring 层契约 fixtures.md` | `docs/architecture/specs/authoring/` | P1 | fixtures for the authoring contract |
| `docs/blueprint/sdk_accept_ingest_provenance_spec.md` | `docs/architecture/specs/sdk/` | P1 | SDK write-entry contract, more spec than plan |

### Move to `docs/architecture/blueprints/`

| Current path | Proposed target area | Priority | Why |
| --- | --- | --- | --- |
| `docs/blueprint/声明元数据统一化蓝图.md` | `docs/architecture/blueprints/core/` | P1 | explicit blueprint content |
| `docs/blueprint/概率推理适配层设计文档.md` | `docs/architecture/blueprints/runtime/` | P1 | design proposal for a future adaptation layer |

### Move to `docs/history/`

| Current path | Proposed target area | Priority | Why |
| --- | --- | --- | --- |
| `docs/blueprint/factpy_kernel_compat_shim_cleanup.md` | `docs/history/migrations/` | P1 | tracks an older compat-shim cleanup wave whose listed shim targets are already gone |
| `docs/blueprint/规则.md` | `docs/history/design-evolution/` | P0 | document contains explicit historical discussion note and points to newer references |
| `docs/blueprint/从Rule到Query的迭代设计.md` | `docs/history/design-evolution/` | P1 | iterative design history |
| `docs/blueprint/从dims到n元Identity的设计演进.md` | `docs/history/design-evolution/` | P1 | explicit design evolution record |

### Manual Review Status

There are currently no unresolved manual-review items for `docs/blueprint/`.

For the reviewed decisions on `factpy_kernel_compat_shim_cleanup.md`, `设计.md`, `语法.md`, and `审计.md`, see [blueprint_manual_review.md](./blueprint_manual_review.md).

## Archived SDK Legacy Docs

The old SDK docs have been archived under `docs/history/legacy/sdk/`.

Why this was necessary:

- the old folder name created a strong source-of-truth ambiguity
- the files are not identical to the current SDK docs
- the content diverges semantically from the active SDK documentation under `src/factpy_kernel/sdk/docs/`

Required invariants after archival:

1. archived files must carry a header note pointing to the active SDK docs
2. active SDK docs may backlink to the archive for design-evolution context
3. `docs/history/legacy/sdk/` must remain non-authoritative

Review record:

- [sdk_old_review.md](./sdk_old_review.md)

## Immediate Actions For The Next Pass

### P0

- classify the three root-level application/frontend docs
- mark `docs/Logs/` as historical in practice
- split `docs/blueprint/` at least conceptually into `reference/spec/blueprint/history`
- keep `docs/history/legacy/sdk/` as linked archive, not active reference

### P1

- add status headers to high-impact docs
- move `docs/api/` into the future `reference/` structure
- move `docs/tutorials/` into the future `guides/` structure
- review `docs/blueprint/设计.md`, `语法.md`, and `审计.md`

### P2

- rename or restructure remaining low-risk folders
- add backlinks from plans to the final reference/spec docs once migrations land

## Default Rule During Transition

Before the structure is fully migrated, use this rule:

- if a file lives in `docs/Logs/`, treat it as history
- if a file lives in `docs/plans/`, treat it as unfinished plan
- if a file lives in `docs/tutorials/`, treat it as guide material
- if a file lives in `docs/api/`, treat it as current service contract
- if a file lives in `docs/blueprint/`, do not trust the folder name alone; inspect whether the file is actually a spec, blueprint, reference, or history
- if a file lives in `docs/history/legacy/sdk/`, treat it as archived history and follow its pointer to current SDK docs

## Archive Cross-Reference Rule

When a file is moved to `docs/history/`:

1. add a header note in the archived file pointing to the current authoritative source
2. when useful, add a backlink from the current authoritative doc to the archived file for design-evolution context
3. prefer linked archival over silent burial, especially for high-confusion areas like SDK, rules, and audit
