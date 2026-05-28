# Current Operational Memory

最后更新:2026-05-28(T10-2-A PyReason iteration_count migration archived locally; pending push gate)

## 当前阶段

**Current branch:** `v0.2.0-t11-1-attach-view-scope-2026-05-26`

**Published branch head:** `origin/v0.2.0-t11-1-attach-view-scope-2026-05-26 @ f8e08905`

**Most recent local work:** T10-2-A PyReason `iteration_count` migration
archived locally; pending push gate.

**Sacred branch:** `master = 562c74195df43e933bed92a3ff25de94dd8ce666`; do not move it.

**Dirty baseline intentionally preserved(4 M + 1 D + 6 U):**

- `docs/references/working/design-points/readme.md`
- `examples/01_sdk_check_diagnose.ipynb`
- `examples/02_overlay_why_not_frontier.ipynb`
- `examples/archive/01_sdk_basics.ipynb`
- deleted `workflow/working/.gitkeep`
- untracked `docs/references/working/change-requests-2026-05-27/`
- untracked `rainbird-ai sdk code/`
- untracked `workflow/design/design-points/active/append-only-ledger-evaluation.zh.md`
- untracked `workflow/design/design-points/active/identity-and-data-model-redesign.zh.md`
- untracked `workflow/design/design-points/active/identity-mechanism-redesign.zh.md`
- untracked `workflow/design/design-points/active/ledger-schema-specification.zh.md`

Do not absorb these into unrelated release, evidence, docs-sync, or cleanup work
without explicit reclassification.

## Published State

Detailed cycle history lives in `workflow/blueprints/archive/INVENTORY.md`.
Release-facing shipped/deferred summaries live in `CHANGELOG.md`.

- T5.1-T5.8 are complete and pushed on
  `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`.
- T11 release-path work is current through T11.3 release machinery and
  T11.2.10 OR `fg.read.match(...)`; live release / PyPI publish / GitHub
  Release remains a separate explicit user gate.
- N10 reference index cleanup is shipped; the dirty working design-points readme
  remains intentionally untouched.
- Evidence foundation is shipped: T7 audit/rendering bridge, T8 split
  inventory, T8-A 14-key metadata validation, T8-B-1 native Form 1, T8-B-2
  Souffle Form 1, and T8-D rounds 1/2 user docs.
- ProbLog lane is now closed through user docs: T10-1 C76 uncertainty projection
  at `cde072fa`, T8-C-1 row provenance runtime at `5ffd4850`, and T8-D round 3
  user docs at `c23ce097`.
- T8-C / T10 planning remains the source for PyReason: T10-2 inventory pushed
  at `f8e08905`; T10-2-A C78 is complete locally and pending push; T10-2-B C74
  and T10-3 C77 remain future, so T8-C-2 PyReason evidence remains gated.

## Recommended Next Work

1. **T10-2-B C74 PyReason canonical bounds / atom-id conversion**: add
   `derived_bound` / full-atom-id `atom_bounds` while preserving legacy
   `head_bound` / `branch_bounds` compatibility.
2. **T10-3 C77 PyReason temporal migration**: add canonical
   `fact_boundaries` / `time_binned` policy and decouple legacy
   `fixed_timesteps`.
3. **T8-C-2 PyReason Form 2 inventory**: source-back the evidence enrichment
   lane before implementation; expect D11 plus C74/C77 gates.
4. **N6 notebook namespace cleanup**: reduce the dirty baseline by addressing
   the three tracked notebook files.
5. **Design-point intake**: classify the identity/data-model,
   identity-mechanism, append-only-ledger, and ledger-schema untracked files.

## Governance Reminders

- Never auto-push `master`.
- Ask once before each push; prior authorization does not roll forward.
- Keep dirty baseline isolated.
- Use archive inventory, changelog, and archived blueprint pairs as the
  historical source of truth; keep this file as operational handoff only.
- For roadmap-driven work, each later blueprint still needs its own Step 4.6
  inventory against active design-points and shipped source.
