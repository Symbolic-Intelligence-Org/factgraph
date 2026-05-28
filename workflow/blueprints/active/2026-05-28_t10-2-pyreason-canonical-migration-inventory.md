# Task Blueprint: T10-2 PyReason Canonical Migration Inventory

- Status: scoped
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S/M (design-only inventory)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_t10-2-pyreason-canonical-migration-inventory.audit.md`
- Trigger: T10 inventory selected the staged hybrid path: T10-1 C76 ProbLog,
  T10-2 C74+C78 PyReason canonical migration, and T10-3 C77 PyReason temporal
  migration. T10-1 shipped at `cde072fa`, closing the ProbLog semantics lane.
  `workflow/memory/current.md` now lists T10-2 as the next recommended work.

## 0. Scope Locks

### In scope

This is a design-only inventory cycle before any T10-2 implementation.

1. Source-backed C74 layer inventory:
   - SDK shell state.
   - SDK lowering state.
   - Adapter consumption state.
   - Per-field state for `timestep_delay`, canonical `derived_bound` versus
     legacy `head_bound`, and canonical `atom_bounds` versus legacy targets.
2. Source-backed C78 layer inventory:
   - SDK shell state.
   - SDK lowering state.
   - Adapter consumption state.
   - Legacy `fixed_timesteps` substrate and what behavior it currently covers.
3. Source-backed atom-id convention inventory:
   - Application canonical `<rule_id>:atom_<index>`.
   - Current PyReason `body_atom:{branch}:{atom}` / `branch:{index}` targets.
   - T8-B witness `b<n>.a<n>:pred_id` keys.
   - Whether a conversion layer is required.
4. Legacy `fixed_timesteps` coupling analysis:
   - Whether it currently mixes C77 temporal projection with C78 iteration
     count.
   - Whether T10-2 can decouple C78 without implementing C77.
5. T10-2 implementation split decision:
   - Single T10-2 cycle versus T10-2-A C74 + T10-2-B C78.
   - Relationship to T8-C-2 PyReason evidence unblock rules.
6. Read-only overlap check for the four untracked active design-point files:
   - `workflow/design/design-points/active/append-only-ledger-evaluation.zh.md`
   - `workflow/design/design-points/active/identity-and-data-model-redesign.zh.md`
   - `workflow/design/design-points/active/identity-mechanism-redesign.zh.md`
   - `workflow/design/design-points/active/ledger-schema-specification.zh.md`

### Out of scope

- Runtime code changes.
- Test code changes.
- T10-2 implementation itself.
- C77 temporal projection implementation; T10-3 owns canonical `fact_boundaries`
  / `time_binned`.
- C76 ProbLog work; T10-1 already shipped it.
- ProbLog adapter work.
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
- Governance / workflow rule changes.
- Sacred `master`.
- Dirty baseline `4 M + 1 D + 6 U`, including the four untracked active
  design-point files.
- Audit module docs; this inventory ships no runtime behavior.
- User-facing docs; a future docs cycle can follow shipped behavior.
- Absorbing or classifying the four untracked design-point files. If Step 4.6
  finds they are strongly coupled to T10-2, stop and run a design-point intake
  cycle first.

### Stop / amend triggers

Pause and amend if Step 4.6 shows:

1. T10 inventory's C74/C78 layer classification is materially wrong.
2. A fourth atom-id convention exists, or the three known conventions are
   actually the same convention through different spellings.
3. `fixed_timesteps` cannot be decoupled from C77; C78 and C77 must ship
   together.
4. Any untracked design-point file is strongly coupled to PyReason canonical
   migration and must be adopted before T10-2.
5. Runtime, tests, user docs, governance, sacred `master`, or dirty-baseline
   files would be touched.

## 1. Problem

T10 inventory established that PyReason semantics are partial under legacy
names. C74's canonical public shape requires `derived_bound`, full-atom-id
`atom_bounds`, and `timestep_delay`, but current surfaces still expose
`head_bound`, `branch_bounds`, `body_atom:{branch}:{atom}`, `branch:{index}`,
and `head:0`. C78's canonical `iteration_count` is missing, while legacy
`fixed_timesteps` currently lives under `temporal_projection` and feeds adapter
timesteps.

T10-2 should not jump straight to implementation because two migration seams
need source-backed locking first:

- Atom identity: application, PyReason lowering, and T8-B witness support use
  different key spaces.
- Iteration count: canonical C78 should be orthogonal to C77 temporal fact
  lifecycle, but shipped legacy `fixed_timesteps` couples those concerns.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md` | Parent inventory and staged-hybrid split source. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | C74/C78 canonical design anchors. |
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` | T10 roadmap and current shipped/deferred overlay. |
| `src/factgraph/sdk/semantics.py` | Public `PyReasonSemantics` wrapper surface. |
| `src/factgraph/sdk/store.py` | SDK wrapper -> `SemanticsProfile` lowering. |
| `src/factgraph/core/semantics/profile.py` | Canonical `SemanticsProfile` substrate and temporal modes. |
| `src/factgraph/adapters/pyreason/rule_ext.py` | PyReason rule projection consumer and adapter-local ext. |
| `src/factgraph/adapters/pyreason/engine_eval.py` | Temporal projection / timesteps consumer. |
| `src/factgraph/application/docs/rule.md` | Application canonical `atom_ids` documentation. |
| `src/factgraph/core/store/_support.py` | T8-B witness key helpers. |
| Four untracked active design-point files | Read-only overlap check only. |

## 3. Step 4.6 Source-Backed Inventory

### 3.1 C74 Layer Inventory

| C74 field | SDK shell | SDK lowering / carrier | Adapter consumption | Classification |
|---|---|---|---|---|
| `timestep_delay` | Shipped as `PyReasonSemantics.timestep_delay` with int / non-negative validation at `src/factgraph/sdk/semantics.py:167,183-186`. | Lowered to `{"target": "rule", "kind": "timestep_delay"}` in preview and runtime lowering at `src/factgraph/sdk/store.py:3381-3382,3450-3451`; accepted by generic `SemanticsProfile.rule_projection` at `src/factgraph/core/semantics/profile.py:45,105-125`. | Materialized in `_materialize_profile_rule_ext(...)` at `src/factgraph/adapters/pyreason/rule_ext.py:173-179`, then compiled into the PyReason rule delay at `:99-105`. | **Shipped end-to-end** under the canonical name. |
| `derived_bound` | **Missing canonical shell.** Public wrapper exposes legacy `head_bound` instead at `src/factgraph/sdk/semantics.py:168,189-190`. | Legacy `head_bound` lowers to `target="head:0"` at `src/factgraph/sdk/store.py:3377-3378,3435-3436`. | Adapter consumes `head:0` into `PyReasonRuleExt.head_bound` at `src/factgraph/adapters/pyreason/rule_ext.py:181-187,224-228`, and compile paths read `head_bound` at `:99` plus `where_compile.py:49-63`. | **Partial / legacy.** Behavior ships, but public/canonical name is `head_bound`, not C74 `derived_bound`. |
| `atom_bounds` | **Missing canonical shell.** Public wrapper exposes `branch_bounds`, keyed by branch id, at `src/factgraph/sdk/semantics.py:169,191-195`; no `atom_bounds`. | Lowering only writes branch-head targets `branch:{index}` from `branch_bounds` at `src/factgraph/sdk/store.py:3379-3380,3442-3449`. Direct profile users can write adapter-local `body_atom:{branch}:{atom}` targets, but SDK wrapper does not expose full atom-id input. | Adapter consumes `body_atom:{branch}:{atom}` into `body_predicate_bounds` at `src/factgraph/adapters/pyreason/rule_ext.py:199-218` and consumes `branch:{index}` into `branch_head_bounds` at `:188-198`; these are positional adapter targets. | **Partial / legacy.** Branch/head and positional body-atom substrates ship, but canonical full-atom-id `atom_bounds` is missing. |

Design anchor: C74 requires `PyReasonRuleParams` fields
`derived_bound` / `atom_bounds` / `timestep_delay`, and `atom_bounds` keys
must be full atom ids (`<rule_id>:atom_<index>`) at
`workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1599`.
T10 inventory's C74 partial/legacy classification remains accurate
(`workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md:113`).

### 3.2 C78 Layer Inventory

| Layer | Current source-backed state | Classification |
|---|---|---|
| Canonical design | C78 requires `PyReasonSemantics.iteration_count: int = 1`, orthogonal to fact temporal lifecycle, and says ProbLog does not get this field at `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1603`; the detailed design repeats the orthogonality and relation to per-rule `timestep_delay` at `:1420-1446`. | Required. |
| SDK shell | `PyReasonSemantics` fields are `timestep_delay`, `head_bound`, `branch_bounds`, `rule_params`, `temporal_projection`, and `uncertainty_projection` at `src/factgraph/sdk/semantics.py:167-172`; no `iteration_count`. | **Missing**. |
| SDK lowering / carrier | `SemanticsProfile` has `engine_options`, `uncertainty_projection`, `temporal_projection`, `rule_projection`, etc. at `src/factgraph/core/semantics/profile.py:39-48`; no canonical `iteration_count`. PyReason lowering only copies temporal projection and rule projection at `src/factgraph/sdk/store.py:3458-3464`. | **Missing**, except generic `engine_options` substrate. |
| Adapter consumption | PyReason currently consumes `temporal_projection.mode == "fixed_timesteps"` and writes `engine_options["timesteps"]` through `_engine_options_with_temporal_projection(...)` at `src/factgraph/adapters/pyreason/engine_eval.py:301-308,327-335`; it does not read `iteration_count`. | **Missing canonical consumer** with legacy substrate. |
| Tests | `tests/test_pyreason_semantics_profile_migration.py:271-327` verifies `fixed_timesteps` acceptance and `timesteps` conflict behavior. Grep finds no test for `iteration_count`. | Legacy coverage only. |

The old-name migration note explicitly says `fixed_timesteps` should be removed
and its function split to the independent `iteration_count` field at
`workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1468-1470`.
T10 inventory's C78 classification remains accurate
(`workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md:116`).

### 3.3 Atom-ID Convention Inventory

| Convention | Source | Purpose | T10-2 decision |
|---|---|---|---|
| `<rule_id>:atom_<index>` | Application docs state `Rule.atom_ids` use this deterministic form at `src/factgraph/application/docs/rule.md:47-49`; C74 requires this full atom id for `atom_bounds` at `rule-expression-and-proof-attempt.zh.md:1599`. | Application/protocol canonical rule atom identity. | **Canonical input for future C74 `atom_bounds`**. |
| `body_atom:{branch}:{atom}` / `branch:{index}` / `head:0` / `rule` | SDK lowering writes `head:0`, `branch:{index}`, and `rule` at `src/factgraph/sdk/store.py:3377-3382,3435-3451`; adapter materialization accepts `branch:{index}` and `body_atom:{branch}:{atom}` at `src/factgraph/adapters/pyreason/rule_ext.py:188-221`. | Adapter-local positional profile targets. | Keep as internal lowering target space; add conversion from full atom id instead of exposing this as user-facing canonical form. |
| `b<n>.a<n>:pred_id` | `make_pred_atom_key(...)` returns `f"b{branch_index}.a{atom_index}:{pred_id}"` at `src/factgraph/core/store/_support.py:201-212`. | T8-B support/witness atom key for evidence topology, not PyReason semantics input. | **Do not reuse for C74.** It is evidence-layer support identity, not adapter-execution semantics identity. |

No fourth T10-2-relevant atom-id convention was found. The three conventions
are distinct by ownership and shape, matching T10 inventory's Q10 finding at
`workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md:167-173,193-195`.
Future C74 implementation needs a conversion layer from full application atom id
to adapter-local positional targets, not a shared key-space rewrite.

### 3.4 `fixed_timesteps` Coupling Analysis

`fixed_timesteps` is currently a C77/C78 coupling point: it is normalized as a
`temporal_projection` mode at `src/factgraph/core/semantics/profile.py:150-176`,
but the value is consumed as PyReason run `timesteps` at
`src/factgraph/adapters/pyreason/engine_eval.py:301-308,327-335`. The parent
essay says temporal projection should only decide fact lifecycle, while
`iteration_count` controls global inference rounds at
`rule-expression-and-proof-attempt.zh.md:1420-1446`; it also explicitly says
`fixed_timesteps` should be removed and split to `iteration_count` at `:1468-1470`.

Decoupling is feasible without implementing C77 in T10-2:

- C78 can add `iteration_count` as a PyReason wrapper/profile adapter-execution
  input and map it to PyReason engine timesteps.
- T10-2 can keep legacy `temporal_projection={"mode": "fixed_timesteps"}` as a
  compatibility alias or explicitly documented legacy path during migration.
- T10-3 remains owner of canonical C77 modes (`fact_boundaries` rename and
  `time_binned`) and should handle the eventual removal or narrowing of
  `fixed_timesteps` from `temporal_projection`.

Stop trigger #3 is **not hit**: source-back shows a coupling point, not an
inseparable implementation dependency.

### 3.5 Implementation Split Options

| Option | Shape | File / test surface | Estimate | Risk / unblock implication |
|---|---|---|---:|---|
| A. Single T10-2 implementation | Ship C74 and C78 together. | `sdk/semantics.py`, `sdk/store.py`, `core/semantics/profile.py`, `adapters/pyreason/{rule_ext,engine_eval}.py`, PyReason semantics/rule tests. | M/L, ~300-650 runtime/test LOC | One coherent PyReason semantics release, but it mixes the simple `iteration_count` migration with riskier atom-id conversion. Higher Step 4.7 regression surface. |
| B. T10-2-A C74, then T10-2-B C78 | Canonical rule params first, iteration count second. | A: SDK/store/rule_ext/rule tests. B: SDK/profile/engine_eval/temporal tests. | Two S/M cycles | Lets atom-id conversion lead, but leaves `fixed_timesteps` coupling in place before T10-3 planning. |
| **C. T10-2-A C78, then T10-2-B C74 (selected)** | **Decouple `iteration_count` first; then add canonical C74 bounds/conversion.** | A: `PyReasonSemantics`, `SemanticsProfile` or profile option, `engine_eval`, fixed-timesteps compatibility tests. B: SDK shell/lowering plus `rule_ext` conversion tests. | **Two S/M cycles** | Best risk split. C78 is smaller and must be clarified before T10-3 temporal work; C74's atom-id conversion can then proceed with fewer moving parts. T8-C-2 still needs both C74 and C77 after C78 lands. |
| D. Defer T10-2 until design-point intake | Pause for untracked identity/ledger design points. | No runtime. | S | Not needed: §3.7 found adjacent PyReason edge/ledger topics, not blocking C74/C78 semantics migration. |

Selected direction: keep the umbrella **T10-2** label but implement as
**T10-2-A C78 canonical `iteration_count`** followed by **T10-2-B C74 canonical
rule params / atom-bound conversion**. This refines, but does not contradict,
T10 inventory's staged hybrid (`T10-2 PyReason C74 + C78`) at
`workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md:143-148`.

### 3.6 Shipped PyReason Behavior Invariants

Future T10-2-A/B implementation must preserve or explicitly migrate:

- `PyReasonSemantics.timestep_delay` validation and lowering
  (`src/factgraph/sdk/semantics.py:167,183-186`;
  `src/factgraph/sdk/store.py:3450-3451`).
- Legacy `head_bound` and `branch_bounds` behavior until a compatibility policy
  is recorded (`src/factgraph/sdk/semantics.py:168-169`;
  `src/factgraph/sdk/store.py:3435-3449`).
- Existing direct `SemanticsProfile.rule_projection.pyreason` targets
  `rule`, `head:0`, `branch:{index}`, and `body_atom:{branch}:{atom}` until a
  migration cycle changes them (`src/factgraph/adapters/pyreason/rule_ext.py:173-221`).
- Legacy temporal modes `none`, `fixed_timesteps`, and `valid_time_boundaries`
  remain accepted until T10-2-A/T10-3 define compatibility / removal policy
  (`src/factgraph/core/semantics/profile.py:150-176`).
- PyReason test coverage around rule extension, branch bounds, engine eval, and
  temporal migration remains a regression guard; the Step 4.6 no-op focused
  suite ran 78 tests OK.

### 3.7 Untracked Design-Point Overlap Check

| File | Matches | Classification |
|---|---|---|
| `append-only-ledger-evaluation.zh.md` | Mentions PyReason `valid_time_boundaries` as adapter-local temporal reasoning, not ledger valid time, at lines 83-87; later references valid time / bitemporal gaps at lines 171, 238, and 446. | **Adjacent, not blocking.** C77/ledger temporal context only; no C74 atom-bound or C78 iteration-count directive. |
| `identity-and-data-model-redesign.zh.md` | Mentions adapter internals generally at line 63, annotation namespace cleanup at line 115, and a downstream PyReason edge impact survey Q-PR1 at line 873. | **Adjacent, not blocking.** PyReason edge/data-model intake is separate from C74/C78 semantics migration. |
| `identity-mechanism-redesign.zh.md` | Tracks Q-PR1 PyReason edge vs unary relationship shape at lines 234, 525, 533, 539, 587, and 608. | **Adjacent, not blocking.** It may affect future PyReason ingest/edge relationship modeling, but it does not define full rule atom ids, `atom_bounds`, `derived_bound`, `iteration_count`, or `fixed_timesteps`. |
| `ledger-schema-specification.zh.md` | Contains ledger `claim_args.val_atom` at line 67 and Q-PR1 PyReason edge/Relationship references at lines 286 and 825. | **Adjacent, not blocking.** `val_atom` is ledger value terminology, not the C74 rule `atom_id` convention; Q-PR1 remains outside T10-2. |

Stop trigger #4 is **not hit**. The four untracked files remain dirty baseline
and should be handled by a future design-point intake / dirty-baseline cycle,
not by this inventory.

## 4. Step 4.6 Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | What is the precise C74 ship state for `timestep_delay`, `derived_bound`, and `atom_bounds`? | `timestep_delay` ships end-to-end. `derived_bound` is shipped only as legacy `head_bound`; canonical name missing. `atom_bounds` is missing as a full-atom-id SDK field; only branch-head and adapter-local positional body-atom targets ship. |
| Q2 | What is the precise C78 ship state and what does legacy `fixed_timesteps` cover today? | Canonical `iteration_count` is missing at SDK/profile/adapter layers. Legacy `fixed_timesteps` is a `temporal_projection` mode that feeds PyReason engine `timesteps`, so it currently covers iteration depth through the wrong carrier. |
| Q3 | What are the three atom-id conventions, where do they originate, and is a conversion layer required? | Application full atom ids (`<rule_id>:atom_<index>`) are canonical for C74. PyReason positional targets are adapter-local. T8-B `b<n>.a<n>:pred_id` keys are evidence support keys. A conversion layer is required; do not reuse witness keys. |
| Q4 | Can `fixed_timesteps` be decoupled so C78 ships independently from C77? | Yes. Add canonical `iteration_count` and migrate/alias `fixed_timesteps` as iteration-depth compatibility, while leaving C77 `fact_boundaries` / `time_binned` to T10-3. |
| Q5 | Should T10-2 implementation be one cycle or split into T10-2-A/T10-2-B? | Split under the T10-2 umbrella: T10-2-A C78 first, then T10-2-B C74. This lowers risk and clears the `fixed_timesteps` coupling before T10-3 temporal work. |
| Q6 | After T10-2 ships, does T8-C-2 PyReason evidence only lack C77, or are other gates still present? | After both T10-2-A and T10-2-B ship, PyReason evidence still needs T10-3 C77 and D11/Form 2 evidence design before T8-C-2 implementation. C78 no longer blocks multi-round enrichment after T10-2-A. |
| Q7 | Do the four untracked active design-point files overlap T10-2? | All four are adjacent but not blocking. They mention PyReason edge/ledger/valid-time topics, not C74 canonical atom-bound conversion or C78 iteration-count execution. Leave them untouched. |
| Q8 | Are any stop/amend findings present? | None. T10 inventory's C74/C78 classifications are confirmed, no fourth T10-2 atom-id convention was found, fixed_timesteps is decouplable, and dirty design points are not blocking. |

## 5. Existing Invariants To Preserve

- T8-A 14-key metadata, `run_id` envelope-only boundary, and always-on
  validation.
- T8-B-1 native Form 1 and T8-B-2 Souffle Form 1 behavior.
- T8-C-1 ProbLog row provenance graphs and namespaced `engine_meta["problog"]`.
- T8-D round 1/2/3 user docs.
- T10-1 C76 ProbLog semantics and anti-silent-ignore behavior.
- C110 legacy `confidence` rejection.
- `EvidenceGraph` DTO, `_FORM1_ROW_SUPPORT_KINDS`, and
  `_WITNESS_BEARING_SUPPORT_KINDS`.
- C119 / C136 / D11 / D13 / Nemo / Form 2 remain deferred unless a later cycle
  explicitly activates them.
- Sacred `master = 562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline `4 M + 1 D + 6 U`.

## 6. Step 4.6 Inventory Plan

Commands:

```bash
rg -n "timestep_delay|derived_bound|atom_bounds|head_bound" src/factgraph workflow/design workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md
rg -n "iteration_count|fixed_timesteps|valid_time_boundaries" src/factgraph workflow/design workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md
rg -n "atom_id|body_atom|atom_index|make_pred_atom_key|branch:" src/factgraph tests workflow/blueprints/archive/2026-05-27_t10-semantics-adapter-inventory.md
rg -n "PyReason|atom|timestep|iteration_count|fixed_timesteps|C74|C78" workflow/design/design-points/active/append-only-ledger-evaluation.zh.md workflow/design/design-points/active/identity-and-data-model-redesign.zh.md workflow/design/design-points/active/identity-mechanism-redesign.zh.md workflow/design/design-points/active/ledger-schema-specification.zh.md
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
git diff --check
git status --short --branch
git rev-parse master
```

Expected outputs:

1. C74 and C78 per-layer classification.
2. Atom-id convention map and conversion decision.
3. `fixed_timesteps` decoupling assessment.
4. T10-2 implementation split recommendation.
5. T8-C-2 unblock map update.
6. Untracked design-point overlap classification.

## 7. Proposed Output Shape

Blueprint-only inventory. The durable output is the archived blueprint/audit
pair, matching T8-C-1 inventory and T10 inventory. Do not create a new
design-point note unless Step 4.6 finds the T10 inventory archive itself must be
amended.

Candidate chain:

1. `docs(blueprint): draft T10-2 pyreason canonical inventory`
2. `docs(blueprint): scope T10-2 pyreason canonical inventory`
3. `docs(blueprint): close T10-2 pyreason canonical inventory`
4. `docs(blueprint): archive T10-2 pyreason canonical inventory`

## 8. Acceptance Checklist

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed inventory completed.
- [x] Q1-Q8 answered.
- [x] C74/C78 per-layer state recorded.
- [x] Atom-id convention map and conversion decision recorded.
- [x] `fixed_timesteps` decoupling assessment recorded.
- [x] T10-2 implementation split shape recorded.
- [x] T8-C-2 unblock map updated.
- [x] Untracked design-point overlap check completed.
- [x] No runtime/test/user-doc/governance/dirty-baseline edits.
- [x] T8-A/B/C-1/D and T10-1 invariants preserved.
- [x] `git diff --check` clean.
- [x] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Design-only no-op baseline:

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Pending closure.
