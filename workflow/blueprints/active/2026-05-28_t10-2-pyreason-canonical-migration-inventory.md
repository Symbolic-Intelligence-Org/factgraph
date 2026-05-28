# Task Blueprint: T10-2 PyReason Canonical Migration Inventory

- Status: draft
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

Pending Step 4.6. Required subsections:

### 3.1 C74 Layer Inventory

Classify `timestep_delay`, `derived_bound` / `head_bound`, and `atom_bounds`
per layer:

- SDK shell.
- SDK lowering.
- `SemanticsProfile` carrier.
- PyReason adapter consumption.

### 3.2 C78 Layer Inventory

Classify canonical `iteration_count` per layer:

- SDK shell.
- SDK lowering.
- `SemanticsProfile` carrier.
- PyReason adapter consumption.
- Legacy `fixed_timesteps` behavior currently standing in the way.

### 3.3 Atom-ID Convention Inventory

Source-back all known conventions, their files, their purpose, and whether they
are interoperable:

- `<rule_id>:atom_<index>`.
- `body_atom:{branch}:{atom}` / `branch:{index}`.
- `b<n>.a<n>:pred_id`.

### 3.4 `fixed_timesteps` Coupling Analysis

Decide whether C78 can be implemented independently by moving iteration depth
out of legacy `temporal_projection.fixed_timesteps`, while leaving canonical C77
`fact_boundaries` / `time_binned` for T10-3.

### 3.5 Implementation Split Options

Compare at least three options:

- Single T10-2 implementation cycle for C74 + C78.
- T10-2-A C74 then T10-2-B C78.
- T10-2-A C78 then T10-2-B C74.
- Any other split Step 4.6 finds.

Each option should include file/test surface, rough LOC, risk, and T8-C-2
unblock implications.

### 3.6 Shipped PyReason Behavior Invariants

List existing PyReason SDK/profile/adapter behaviors that future implementation
must preserve or explicitly migrate with compatibility policy.

### 3.7 Untracked Design-Point Overlap Check

Classify the four untracked active design-point files as unrelated,
adjacent-but-not-blocking, or blocking for T10-2. If blocking, trigger stop /
amend.

## 4. Step 4.6 Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | What is the precise C74 ship state for `timestep_delay`, `derived_bound`, and `atom_bounds`? | Per-field, per-layer table with source refs. |
| Q2 | What is the precise C78 ship state and what does legacy `fixed_timesteps` cover today? | Per-layer table plus coupling analysis. |
| Q3 | What are the three atom-id conventions, where do they originate, and is a conversion layer required? | Source-backed convention table and decision. |
| Q4 | Can `fixed_timesteps` be decoupled so C78 ships independently from C77? | Yes/no with migration policy and stop-trigger assessment. |
| Q5 | Should T10-2 implementation be one cycle or split into T10-2-A/T10-2-B? | Compare options with file/test/LOC/risk estimates. |
| Q6 | After T10-2 ships, does T8-C-2 PyReason evidence only lack C77, or are other gates still present? | Updated unblock map. |
| Q7 | Do the four untracked active design-point files overlap T10-2? | Grep-backed classification and next action. |
| Q8 | Are any stop/amend findings present? | None or explicit trigger with next action. |

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

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed inventory completed.
- [ ] Q1-Q8 answered.
- [ ] C74/C78 per-layer state recorded.
- [ ] Atom-id convention map and conversion decision recorded.
- [ ] `fixed_timesteps` decoupling assessment recorded.
- [ ] T10-2 implementation split shape recorded.
- [ ] T8-C-2 unblock map updated.
- [ ] Untracked design-point overlap check completed.
- [ ] No runtime/test/user-doc/governance/dirty-baseline edits.
- [ ] T8-A/B/C-1/D and T10-1 invariants preserved.
- [ ] `git diff --check` clean.
- [ ] Sacred master and dirty baseline preserved.

## 9. Verification Commands

Design-only no-op baseline:

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Pending Step 4.6 / closure.
