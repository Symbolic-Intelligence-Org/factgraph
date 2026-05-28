# Task Blueprint: T10-3 PyReason Temporal Migration Inventory

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S/M (design-only inventory)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_t10-3-pyreason-temporal-migration-inventory.audit.md`
- Trigger: T10 inventory selected the staged hybrid split and left C77 PyReason
  temporal migration as the final adapter-semantics slice after T10-1 / T10-2.
  T10-2-A shipped at `65cc79a3`, decoupling canonical C78 `iteration_count`
  from legacy temporal `fixed_timesteps`. T10-2-B shipped at `92fd6013`,
  completing C74 canonical rule params and proving the existing PyReason
  lowering / adapter-consumption pattern. `workflow/memory/current.md` now lists
  T10-3 C77 PyReason temporal migration as the next recommended work.

## 0. Scope Locks

### In scope

This is a design-only inventory cycle before any T10-3 implementation.

1. Source-backed C77 layer inventory:
   - SDK shell state.
   - SDK lowering state.
   - `SemanticsProfile.temporal_projection` carrier state.
   - Adapter consumption state.
2. Source-backed legacy `valid_time_boundaries` versus canonical
   `fact_boundaries` rename analysis:
   - Rename / alias / deprecate / removal policy options.
   - Compatibility horizon.
3. Source-backed canonical `time_binned` mode design:
   - Whether it is truly new.
   - Relationship to existing `none`, `fixed_timesteps`, and
     `valid_time_boundaries` modes.
   - Adapter consumption shape.
4. T10-2-A-after legacy `fixed_timesteps` disposition:
   - Preserve, deprecate, or remove.
   - Relationship to already-shipped canonical `iteration_count`.
5. T10-3 implementation split decision:
   - Single cycle.
   - T10-3-A `valid_time_boundaries` -> `fact_boundaries` rename plus T10-3-B
     `time_binned` mode.
   - Other split if Step 4.6 finds a better shape.
   - T8-C-2 PyReason evidence unblock relationship.
6. Read-only overlap check for the four untracked active design-point files:
   - `workflow/design/design-points/active/append-only-ledger-evaluation.zh.md`
   - `workflow/design/design-points/active/identity-and-data-model-redesign.zh.md`
   - `workflow/design/design-points/active/identity-mechanism-redesign.zh.md`
   - `workflow/design/design-points/active/ledger-schema-specification.zh.md`

### Out of scope

- Runtime code changes.
- Test code changes.
- T10-3 implementation itself.
- T10-2-A C78 `iteration_count` behavior; do not weaken, redo, or roll it back.
- T10-2-B C74 `derived_bound`, `atom_bounds`, atom-id conversion, asymmetric
  conflict policy, or existing-rule-projection carrier behavior; do not weaken,
  redo, or roll it back.
- C76 ProbLog or ProbLog adapter work; T10-1 already shipped it.
- T8-C-2 PyReason evidence enrichment implementation.
- Changes to T10-1, T8-C-1, or T8-D shipped behavior.
- D11 / Form 2 / Nemo / C119 / C136 / aggregate / failed graph / why-not /
  counterfactual / match witness.
- D20 / service / OpenAPI / Database/view / match API / `fg.eval.run` /
  release / PyPI / tags.
- `EvidenceGraph` DTO, 14-key metadata, `_FORM1_ROW_SUPPORT_KINDS`, or
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- T8-A 14-key validation, T8-B Form 1, T8-D round 1/2/3 user docs, or T10-1
  anti-silent-ignore behavior.
- C110 legacy `confidence` rejection.
- Audit module docs; this inventory ships no behavior.
- User-facing docs; a future T8-D round can follow after T10-2-A/B and T10-3
  all ship.
- Governance / workflow rule changes.
- Sacred `master`.
- Dirty baseline `4 M + 1 D + 6 U`; the four untracked design-point files
  remain adjacent and out-of-scope unless Step 4.6 proves otherwise.
- Reopening T10 inventory, T10-2 inventory, T10-2-A, or T10-2-B decisions. If
  Step 4.6 finds a contradiction, stop and amend the relevant archive instead
  of silently diverging.
- Absorbing or classifying untracked design-point files.

### Stop / amend triggers

Pause and amend if Step 4.6 shows:

1. T10 inventory's C77 deferred classification is materially wrong.
2. C77 canonical design contradicts the T10-2-A shipped `fixed_timesteps` /
   `iteration_count` decoupling policy.
3. `time_binned` cannot be designed independently from `fact_boundaries`.
4. T10-3 cannot be split safely if the rename plus new mode implementation is
   too large for one implementation cycle.
5. Any untracked design-point file is strongly coupled to C77 / temporal
   migration and must be adopted before T10-3.
6. Runtime, tests, user docs, governance, sacred `master`, dirty-baseline files,
   T10-2-A behavior, or T10-2-B behavior would be touched in this inventory.

## 1. Problem

T10-2-A moved PyReason global inference rounds into canonical
`iteration_count`, reducing the legacy coupling where
`temporal_projection.fixed_timesteps` carried execution-depth semantics. T10-3
is now the remaining PyReason semantics slice from the T10 staged-hybrid plan:
canonical C77 temporal projection.

Current shipped behavior is expected to still expose legacy temporal projection
modes, especially `valid_time_boundaries` and `fixed_timesteps`. The inventory
must determine whether C77 implementation should rename
`valid_time_boundaries` to `fact_boundaries`, add a new `time_binned` mode, keep
or remove `fixed_timesteps`, and whether those changes should be one
implementation cycle or split across T10-3-A/T10-3-B.

T10-3 should not start implementation until the current temporal carrier,
adapter consumption, and compatibility policy are source-backed. It must also
avoid regressing the already-shipped T10-2-A C78 and T10-2-B C74 slices.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md` | Parent T10 staged-hybrid split and C77 deferred classification. |
| `workflow/blueprints/archive/2026-05-28_t10-2-pyreason-canonical-migration-inventory.md` | T10-2 split / fixed-timesteps decoupling source. |
| `workflow/blueprints/archive/2026-05-28_t10-2-a-pyreason-iteration-count-migration.md` | Shipped C78 `iteration_count` behavior and compatibility policy. |
| `workflow/blueprints/archive/2026-05-28_t10-2-b-pyreason-canonical-rule-params.md` | Shipped C74 canonical carrier/lowering pattern and T10-2-B invariants. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | C77 / temporal projection canonical design anchor. |
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` | Current roadmap overlay and T10/T8-C dependency framing. |
| `src/factgraph/sdk/semantics.py` | Public `PyReasonSemantics` wrapper surface. |
| `src/factgraph/sdk/store.py` | SDK wrapper -> `SemanticsProfile` lowering. |
| `src/factgraph/core/semantics/profile.py` | Canonical `SemanticsProfile.temporal_projection` substrate and validation. |
| `src/factgraph/adapters/pyreason/engine_eval.py` | PyReason temporal projection / timesteps consumer. |
| PyReason tests | Focused regression baseline and current temporal behavior fixtures. |
| Four untracked active design-point files | Read-only overlap check only. |

## 3. Step 4.6 Source-Backed Inventory

### 3.1 Current Temporal Projection State

| Layer | Current state | Classification |
|---|---|---|
| SDK shell | `PyReasonSemantics.temporal_projection` remains a raw mapping field with default `{"mode": "none"}` at `src/factgraph/sdk/semantics.py:199`; `__post_init__` only copies the mapping at `:246-250`. | **Partial / generic shell.** No SDK-specific C77 validation; profile layer owns mode validation. |
| SDK lowering | Public PyReason lowering copies `temporal_projection=dict(value.temporal_projection)` into `SemanticsProfile` at `src/factgraph/sdk/store.py:3458-3464`; T10-2-A `iteration_count` lowering stays separate through `_pyreason_iteration_count_carrier(...)` at `:3544-3548`. | **Shipped generic pass-through.** |
| Profile carrier | `SemanticsProfile.temporal_projection` is a top-level carrier at `src/factgraph/core/semantics/profile.py:45` and normalizes at `:69`. Supported modes are `none`, `fixed_timesteps`, and `valid_time_boundaries` at `:164-181`; `fact_boundaries` / `time_binned` are rejected as unsupported. | **Partial / legacy.** |
| Adapter consumption | `pyreason.engine_eval` resolves temporal projection before run config at `src/factgraph/adapters/pyreason/engine_eval.py:71-84`. `_resolve_temporal_projection_state(...)` accepts `none`, `fixed_timesteps`, and `valid_time_boundaries` at `:282-336`. `_materialize_valid_time_boundaries(...)` computes active ranges and timesteps from `valid_from` / `valid_to` metadata at `:398-450`. | **Partial / legacy.** `valid_time_boundaries` has real runtime behavior; canonical names are missing. |
| Tests | Existing tests cover `fixed_timesteps` profile acceptance, run-config driving, conflicts, `valid_time_boundaries` profile acceptance, active-step mapping, universe-only behavior, and engine-option conflicts at `tests/test_pyreason_semantics_profile_migration.py:425-627`. | **Legacy coverage.** No `fact_boundaries` / `time_binned` tests yet. |

T10 inventory's C77 classification remains accurate: `none` and legacy
`valid_time_boundaries` ship; canonical `fact_boundaries` / `time_binned` are
missing. T10-2-A changed the C78 side by adding `SemanticsProfile.iteration_count`
at `profile.py:43,67-80` and adapter consumption at
`engine_eval.py:71-84,339-358`; it did not add canonical C77 modes.

### 3.2 C77 Canonical Design Source-Back

The active design anchor states that `temporal_projection` should only decide
fact lifecycle, while global inference rounds are controlled by
`iteration_count` at
`workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1420-1446`.
Its three canonical modes are:

| Mode | Design anchor | Current implementation state | Step 4.6 classification |
|---|---|---|---|
| `none` | `{"mode": "none"}` at `rule-expression-and-proof-attempt.zh.md:1424-1427`. | Shipped in profile and adapter (`profile.py:167-170`; `engine_eval.py:301-304`). | **Shipped.** |
| `fact_boundaries` | Fact metadata automatic mode at `rule-expression-and-proof-attempt.zh.md:1428-1430`; C77 table says legacy `valid_time_boundaries` -> `fact_boundaries` at `:1602`. | Runtime substrate exists under legacy `valid_time_boundaries` (`profile.py:175-178`; `engine_eval.py:317-335,398-450`). | **Rename / alias work.** |
| `time_binned` | Equal time buckets, new in v1, with `bin_size` and `universe` at `rule-expression-and-proof-attempt.zh.md:1431-1439,1456-1465,1602`. | No profile or adapter support found; grep only finds design/docs mentions. | **True new mode.** |

The design also says legacy `fixed_timesteps` should be removed and split to
independent `iteration_count`, and `valid_time_boundaries` should be renamed at
`rule-expression-and-proof-attempt.zh.md:1468-1471`. It records that a
deprecation-warning period for `fixed_timesteps` / `valid_time_boundaries` is
optional and alpha can hard-cut at `:1616`.

### 3.3 `valid_time_boundaries` -> `fact_boundaries` Rename Policy

Candidate comparison:

| Option | Shape | Pros | Cons | Decision |
|---|---|---|---|---|
| Hard rename | Accept only `fact_boundaries`; reject `valid_time_boundaries`. | Matches canonical design and alpha-hard-cut allowance. | Breaks existing tests and users that T10-2-A/T10-2-B kept stable; larger docs blast radius. | Reject for first implementation. |
| Preserve legacy only | Keep `valid_time_boundaries`; do not add canonical mode. | No behavior risk. | Fails C77 canonical migration. | Reject. |
| **Alias canonical + legacy** | Accept `fact_boundaries` and `valid_time_boundaries`, both routed to the existing materialization substrate. Preserve input spelling in normalized profile for compatibility, or normalize canonical to canonical and keep legacy spelling for legacy inputs. | Adds canonical name without breaking legacy tests; fits T10 inventory Q9 "keep `valid_time_boundaries` as compatibility alias initially". | Leaves two spellings until a later cleanup/docs cycle. | **Selected.** |

Conflict behavior: mode is a single scalar field, so users cannot specify both
`fact_boundaries` and `valid_time_boundaries` in one normalized
`temporal_projection`. There is no winner policy to define. Implementation
should reject invalid mixed keys by normal mode validation, and should keep the
existing universe validation shape from `_normalize_valid_time_boundaries(...)`
(`profile.py:193-209`).

Recommended first implementation: add `fact_boundaries` as a canonical alias to
the existing universe-based materialization, keep `valid_time_boundaries`
accepted through at least T10-3, and rename helper/error wording only if tests
record compatibility impact. User-facing docs can move users to canonical
`fact_boundaries` in a later T8-D round.

### 3.4 `time_binned` New Mode Design

`time_binned` is a real new mode, not a rename. The design describes equal
duration buckets with `bin_size` and `universe` at
`rule-expression-and-proof-attempt.zh.md:1431-1439,1456-1465,1602`, and
explicitly says `time_binned` is new at `:1471`.

Relationship to shipped modes:

| Mode | Time coordinate source | Runtime substrate today | T10-3 implication |
|---|---|---|---|
| `none` | No temporal coordinate; facts active from 0 to open end. | Shipped. | Preserve. |
| `fixed_timesteps` | Explicit timesteps count; after T10-2-A it is legacy iteration-depth compatibility, not true C77. | Shipped but semantically legacy. | Preserve as compatibility unless implementation cycle chooses removal with tests/docs. |
| `valid_time_boundaries` / `fact_boundaries` | Boundaries derived from fact `valid_from` / `valid_to` metadata plus explicit universe. | Shipped under legacy name. | Alias canonical name to existing substrate. |
| `time_binned` | Equal bins computed from `universe` and `bin_size`; facts map to bin indexes by their valid-time ranges. | Not shipped. No duration parser or bin materializer exists. | Requires new normalization, duration parsing/whitelist, and adapter materialization. |

Adapter substrate can reuse the `_TemporalProjectionState` shape and the
`active_by_asrt_id` / `timesteps` contract returned by
`_materialize_valid_time_boundaries(...)` at `engine_eval.py:430-433`. However,
`time_binned` needs a new materializer that computes ordered bin boundaries from
`universe` and `bin_size`; it cannot reuse valid-time boundary deduplication
unchanged.

### 3.5 Legacy `fixed_timesteps` Disposition

T10-2-A shipped canonical `iteration_count` and preserved legacy
`fixed_timesteps` as alias/fallback when canonical C78 is absent. The adapter
currently rejects explicit `iteration_count` with both `fixed_timesteps` and
`valid_time_boundaries` (`engine_eval.py:305-320`; tests at
`tests/test_pyreason_semantics_profile_migration.py:502-546`). No warning was
added in T10-2-A.

Disposition options:

| Option | Effect | Assessment |
|---|---|---|
| Remove `fixed_timesteps` in T10-3 | Fully matches design's "old mode -> remove" note. | Too disruptive for the first C77 implementation; breaks accepted legacy tests at `tests/test_pyreason_semantics_profile_migration.py:425-463`. |
| Add warning while preserving behavior | Starts deprecation. | Introduces warning API surface and test churn; not needed for design-only inventory and should be considered in implementation scope if chosen. |
| **Preserve as compatibility alias** | Keep accepting `fixed_timesteps` when canonical `iteration_count` is absent; keep explicit conflict with `iteration_count`. | **Selected for the first T10-3 implementation.** It honors T10-2-A shipped behavior and avoids reopening C78. |
| Narrow to docs-only policy | Record future removal but no runtime change. | Equivalent to preserve for runtime; docs belong to future T8-D round, not this inventory. |

Step 4.6 decision: T10-3 should not remove `fixed_timesteps` in the first
implementation plan. It should keep the T10-2-A compatibility path and conflict
helpers intact. Removal/deprecation can be a later cleanup/docs cycle after
canonical `fact_boundaries` / `time_binned` behavior has shipped and user-facing
docs have a migration story.

### 3.6 T10-3 Split Candidates and T8-C-2 Unblock

| Option | Shape | Pros | Cons | Decision |
|---|---|---|---|---|
| Single T10-3 implementation | Alias `fact_boundaries`, add `time_binned`, and preserve `fixed_timesteps` compatibility in one cycle. | One user-visible C77 ship; no half-C77 state. | Larger runtime/test surface: profile validation, duration parser, two adapter materializers, conflict tests. | Viable, but M-class. |
| **T10-3-A rename/alias, T10-3-B `time_binned`** | First add canonical `fact_boundaries` alias to existing substrate and lock compatibility; then implement new binned materializer. | Best risk split. Keeps first slice small and validates C77 carrier migration before new duration/binning behavior. | Leaves `time_binned` deferred after T10-3-A. | **Selected.** |
| T10-3-A cleanup/removal, T10-3-B new mode | Remove/deprecate legacy `fixed_timesteps` first, then add modes. | Cleans legacy first. | Risks breaking T10-2-A compatibility before canonical C77 is complete. | Reject. |

Recommended split:

1. **T10-3-A C77 rename / compatibility**: add canonical `fact_boundaries` as
   an alias to `valid_time_boundaries`, preserve legacy spelling and
   `fixed_timesteps`, keep T10-2-A conflict behavior, and add tests.
2. **T10-3-B C77 `time_binned`**: add duration/bin-size validation and binned
   temporal materialization, with explicit behavior-change notes.

T8-C-2 unblock: after T10-3-A, C77 is only partially canonical because
`time_binned` remains missing. After T10-3-B, the semantics gates C74/C77/C78
are complete, but T8-C-2 implementation still needs D11/Form 2 evidence design.

### 3.7 Shipped PyReason Invariants

T10-3 must preserve:

| Slice | Invariant | Source-back |
|---|---|---|
| T10-2-A | SDK `PyReasonSemantics.iteration_count: int = 1` with positive-int validation. | `src/factgraph/sdk/semantics.py:193,215-218`; tests `tests/test_pyreason_semantics_profile_migration.py:384-397`. |
| T10-2-A | Optional top-level `SemanticsProfile.iteration_count`. | `src/factgraph/core/semantics/profile.py:43,67-80`; tests `tests/test_pyreason_semantics_profile_migration.py:398-408`. |
| T10-2-A | Lowering omission rule: default `1` plus legacy temporal mode omits canonical carrier. | `src/factgraph/sdk/store.py:3544-3548`; tests `tests/test_pyreason_semantics_profile_migration.py:410-423`. |
| T10-2-A | Adapter consumption maps canonical `iteration_count` to run timesteps when no temporal conflict exists. | `engine_eval.py:71-84,339-358`; test `tests/test_pyreason_semantics_profile_migration.py:464-480`. |
| T10-2-A | Explicit conflicts with `fixed_timesteps` and `valid_time_boundaries`. | `engine_eval.py:305-320`; tests `tests/test_pyreason_semantics_profile_migration.py:502-546`. |
| T10-2-A | No-profile engine default timesteps remains 2. | `tests/test_pyreason_engine_eval.py:355-377`. |
| T10-2-B | SDK `derived_bound` / `atom_bounds` validation. | `src/factgraph/sdk/semantics.py:194-195,221-233`; tests `tests/test_pyreason_semantics_profile_migration.py:292-313`. |
| T10-2-B | `rule_projection["pyreason"]` carrier reuse, not new top-level fields. | `src/factgraph/sdk/store.py:3460-3464,3488-3535`; tests `tests/test_pyreason_semantics_profile_migration.py:315-340`. |
| T10-2-B | SDK atom-id conversion from full ids to `body_atom:0:<index>`. | `src/factgraph/sdk/store.py:3509-3535`; tests `tests/test_pyreason_semantics_profile_migration.py:315-340`. |
| T10-2-B | Legacy Inference / missing application atom ids reject canonical `atom_bounds`. | `src/factgraph/sdk/store.py:3511-3515`; tests `tests/test_pyreason_semantics_profile_migration.py:342-377`. |
| T10-2-B | Asymmetric conflict policy: `derived_bound` + `head_bound` rejects; `atom_bounds` + `branch_bounds` can coexist. | `src/factgraph/sdk/semantics.py:221-227`; tests `tests/test_pyreason_semantics_profile_migration.py:379-410`. |
| T10-2-B | No T8-B witness-key reuse. | Tests assert no `b0.a` witness key shape at `tests/test_pyreason_semantics_profile_migration.py:315-331`; implementation imports no witness helper. |

Hidden coupling assessment: C77 still shares PyReason run `timesteps` with
temporal materialization. T10-2-A intentionally rejects canonical
`iteration_count` with legacy temporal modes. T10-3 implementation must
preserve that conflict unless a later design explicitly introduces a separate
engine-time axis. This is not a stop trigger because T10-2-A already made the
compatibility boundary explicit; it is a behavior warning for T10-3 closure.

### 3.8 Untracked Design-Point Overlap

| File | Relevant mentions | Classification |
|---|---|---|
| `append-only-ledger-evaluation.zh.md` | Lines 83-87 distinguish PyReason `valid_time_boundaries` from ledger valid time; lines 171, 238, and 446 discuss ledger bitemporal gaps and cite current PyReason as adapter-local. | Adjacent, not blocking. It reinforces that PyReason temporal projection is adapter-local and not ledger valid-time schema. |
| `identity-and-data-model-redesign.zh.md` | Line 806 references append-only ledger future gaps; line 873 lists Q-PR1 migration impact, not C77 mode semantics. | Adjacent, not blocking. |
| `identity-mechanism-redesign.zh.md` | Lines 232, 503, 507, 511, and 563 discuss as-of/bitemporal identity future surfaces; lines 525, 533, 539, and 587 discuss PyReason edge relationship modeling. | Adjacent, not blocking. It is about identity/edge modeling, not temporal projection mode implementation. |
| `ledger-schema-specification.zh.md` | Lines 419-420 reserve ledger `valid_from` / `valid_to` fields for future bitemporal; lines 286 and 825 discuss PyReason edge modeling Q-PR1. | Adjacent, not blocking. Ledger valid-time schema is separate from C77 adapter-local temporal projection. |

No untracked file requires adoption before T10-3 inventory or future
implementation.

## 4. Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | What is C77's current ship state across SDK shell, SDK lowering, profile carrier, and adapter consumption? | Partial / legacy. SDK shell and lowering pass through generic `temporal_projection`; profile and adapter support `none`, `fixed_timesteps`, and `valid_time_boundaries`; canonical `fact_boundaries` / `time_binned` are missing. |
| Q2 | What policy should govern `valid_time_boundaries` -> `fact_boundaries`? | Add `fact_boundaries` as canonical alias to the existing valid-time-boundary substrate; keep `valid_time_boundaries` accepted through T10-3; no hard cut in the first implementation. |
| Q3 | What is the `time_binned` mode design and relationship to existing modes? | It is a real new mode, not a spelling alias. It needs `bin_size` validation and a binned materializer; it can reuse `_TemporalProjectionState` output shape but not `_materialize_valid_time_boundaries(...)` unchanged. |
| Q4 | What should happen to legacy `fixed_timesteps` in T10-3? | Preserve as compatibility alias when canonical `iteration_count` is absent; keep explicit conflict with `iteration_count`; no warning/removal in the first T10-3 implementation plan. |
| Q5 | What is the T10-3 implementation split? | Split as T10-3-A `fact_boundaries` alias/compatibility, then T10-3-B `time_binned` new mode. |
| Q6 | After T10-3 ships, does T8-C-2 PyReason evidence only lack D11/Form 2? | After T10-3-B yes: C74/C77/C78 semantics gates are complete and D11/Form 2 remains the major evidence gate. After T10-3-A only, `time_binned` remains a C77 gap. |
| Q7 | Do the four untracked design-point files overlap T10-3 strongly? | No. They are adjacent ledger/identity/PyReason-edge notes and remain out-of-scope. |
| Q8 | Do T10-2-A or T10-2-B shipped behaviors have hidden coupling with C77? | Yes for T10-2-A: PyReason run `timesteps` is still shared by temporal materialization and iteration count, so T10-3 must preserve existing iteration/temporal conflict behavior. T10-2-B has no hidden C77 coupling. |
| Q9 | Are there behavior changes that need warning, like T10-2-A's default timesteps 2 -> 1? | No default shift is expected for T10-3-A. T10-3-B may change behavior by adding binned temporal activation; closure must record bin boundary and conflict semantics. |
| Q10 | Are there stop/amend findings? | None. Current findings refine implementation split and behavior warnings but do not contradict T10/T10-2/T10-2-A/T10-2-B archives. |

## 5. Existing Invariants To Preserve

- T8-A 14-key metadata, `run_id` envelope-only boundary, and always-on
  validation.
- T8-B-1 native Form 1 and T8-B-2 Souffle Form 1 behavior.
- T8-C-1 ProbLog row provenance graphs and namespaced `engine_meta["problog"]`.
- T8-D round 1/2/3 user docs.
- T10-1 C76 ProbLog semantics and anti-silent-ignore behavior.
- T10-2-A C78 `iteration_count`: SDK field, profile carrier, lowering omission
  rule, adapter consumption, dual conflict helpers, and error wording.
- T10-2-B C74 canonical rule params: SDK `derived_bound` / `atom_bounds`,
  `rule_projection["pyreason"]` carrier reuse, SDK atom-id conversion,
  asymmetric conflict policy, no T8-B witness-key reuse, and distinct error
  wording.
- C110 legacy `confidence` rejection.
- `EvidenceGraph` DTO, `_FORM1_ROW_SUPPORT_KINDS`, and
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- C119 / C136 / D11 / D13 / Nemo / Form 2 remain deferred unless a later cycle
  explicitly activates them.
- T10 inventory, T10-2 inventory Q1-Q8, T10-2-A scoped decisions, and T10-2-B
  scoped decisions remain locked unless this inventory stops and amends the
  relevant archive.
- Existing `timestep_delay`, `head_bound`, `branch_bounds`, and
  `iteration_count` behavior.
- Sacred `master = 562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline `4 M + 1 D + 6 U`.

## 6. Step 4.6 Inventory Plan

Commands:

```bash
rg -n "temporal_projection|valid_time_boundaries|fact_boundaries|time_binned" src/factgraph workflow/design workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md workflow/blueprints/archive/2026-05-28_t10-2-pyreason-canonical-migration-inventory.md
rg -n "C77|fixed_timesteps|_materialize_valid_time_boundaries|_resolve_temporal_projection_state" src/factgraph workflow/design
rg -n "PyReason|temporal|fact_boundaries|time_binned|C77" workflow/design/design-points/active/append-only-ledger-evaluation.zh.md workflow/design/design-points/active/identity-and-data-model-redesign.zh.md workflow/design/design-points/active/identity-mechanism-redesign.zh.md workflow/design/design-points/active/ledger-schema-specification.zh.md
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
git diff --check
git status --short --branch
git rev-parse master
```

Expected Step 4.6 outputs:

1. Current C77 layer table.
2. Canonical design anchor table.
3. Rename / alias / removal policy for `valid_time_boundaries`.
4. `time_binned` design classification.
5. `fixed_timesteps` T10-3 disposition.
6. Implementation split recommendation.
7. T8-C-2 unblock update.
8. Four-file design-point overlap classification.
9. Stop/amend assessment.

## 7. Proposed Output Shape

Blueprint-only inventory, matching the T10-2 inventory and T8-C-1 inventory
Option B shape. Durable output is the archived blueprint/audit pair. No runtime
code, test code, user docs, audit docs, or design-point note should be created
unless Step 4.6 proves an upstream archive amendment is required.

Candidate chain:

1. `docs(blueprint): draft T10-3 PyReason temporal inventory`
2. `docs(blueprint): scope T10-3 PyReason temporal inventory`
3. `docs(blueprint): close T10-3 PyReason temporal inventory`
4. `docs(blueprint): archive T10-3 PyReason temporal inventory`

## 8. Acceptance Checklist

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed inventory completed.
- [x] Q1-Q10 answered.
- [x] C77 current layer state recorded.
- [x] `valid_time_boundaries` -> `fact_boundaries` policy recorded.
- [x] `time_binned` design and split recommendation recorded.
- [x] `fixed_timesteps` disposition recorded.
- [x] T8-C-2 unblock map updated.
- [x] Four untracked design-point files classified as blocking or adjacent.
- [x] T10-2-A and T10-2-B invariants preserved.
- [x] No runtime, test, user-doc, audit-doc, governance, sacred, or dirty
  baseline files touched.
- [x] `git diff --check` clean.
- [x] Focused PyReason no-op baseline remains `90 OK`.
- [x] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Design-only no-op verification:

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Design-only inventory completed with no runtime, test, user-doc, audit-doc,
governance, dirty-baseline, or sacred-master edits.

Key outcomes:

1. C77 is **partial / legacy** across the shipped stack. SDK shell and SDK
   lowering pass through `temporal_projection`; `SemanticsProfile` and the
   PyReason adapter support `none`, `fixed_timesteps`, and legacy
   `valid_time_boundaries`; canonical `fact_boundaries` and `time_binned` are
   missing.
2. `fact_boundaries` should ship first as a canonical alias to the existing
   valid-time-boundary substrate. Legacy `valid_time_boundaries` should remain
   accepted through T10-3; no hard cut in the first implementation.
3. `time_binned` is a true new C77 mode, not an alias. It needs
   `bin_size` validation, a duration/short-form parser, and a binned
   materializer; it can reuse `_TemporalProjectionState` output shape but not
   `_materialize_valid_time_boundaries(...)` unchanged.
4. Legacy `fixed_timesteps` should remain accepted as a compatibility alias
   when canonical `iteration_count` is absent. T10-3 must preserve T10-2-A's
   explicit conflict between canonical `iteration_count` and temporal modes.
5. Recommended implementation split is **T10-3-A C77 `fact_boundaries`
   alias/compatibility** followed by **T10-3-B C77 `time_binned`**. T10-3-A is
   a smaller rename/alias slice; T10-3-B owns the new binning materializer.
6. T8-C-2 PyReason evidence remains gated after T10-3-A because `time_binned`
   is still missing. After T10-3-B, C74/C77/C78 semantics gates are complete,
   but D11/Form 2 remains required.
7. The four untracked design-point files were classified as adjacent, not
   blocking. They discuss ledger valid time, identity/as-of, or PyReason edge
   modeling rather than C77 adapter-local temporal mode implementation.

Future implementation pings:

- The active design says `fixed_timesteps` is ultimately an old mode to remove,
  but this inventory deliberately defers removal to preserve T10-2-A
  compatibility. A later cleanup/docs cycle should own deprecation or removal.
- T10-3-A must choose and test the exact normalization strategy for
  `fact_boundaries` / `valid_time_boundaries`: preserve spelling or normalize
  canonical spelling while keeping legacy spelling for legacy inputs.
- T10-3-B must follow the strict `bin_size` design: ISO 8601 durations plus the
  small short-form whitelist (`1d`, `1h`, `15m`, `1m`), and reject ambiguous
  human-readable strings such as `"1 month"`.
- Future T10-3-A/B Step 4.7 reviews should spot-check the §3.7 12-item shipped
  PyReason invariant manifest because line numbers may drift after runtime
  edits.
- T10-3-A must preserve `_reject_iteration_temporal_conflict` behavior for the
  new `fact_boundaries` alias unless a future blueprint explicitly changes the
  iteration/temporal coexistence policy.

Verification:

- Focused PyReason no-op suite remained `90 OK`.
- `git diff --check` was clean.
- Sacred master remained `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remained `4 M + 1 D + 6 U`.
