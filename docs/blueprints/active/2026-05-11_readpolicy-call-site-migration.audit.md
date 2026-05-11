# Task Blueprint Audit: ReadPolicy Call-Site Migration and ViewSpec Removal from `fg.views`

- Blueprint: [2026-05-11_readpolicy-call-site-migration.md](./2026-05-11_readpolicy-call-site-migration.md)
- Parent Blueprint: (none — top-level cleanup)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-11 | draft | Design discussion converged on Option α' | User–Claude design discussion (2026-05-11) on the `fg.views` / `ViewSpec` / `FrozenAssertionView` terminology collision. Evaluated transcript proposal (`fg.projections` namespace + `ProjectionSpec` rename + alias-first slice) against alternative **Option α'** (value-object `ReadPolicy` via `policy=` kwarg; no new registry; no `fg.projections`). Convergence on α' driven by three findings: (1) "projection" terminology already occupies 3 kernel-internal meanings (`ViewProjectionError`, schema IR `projection`, write-protocol annotation projection); (2) ViewSpec field semantics are aggregation + source-preference, not relational-algebra projection; (3) value-object with call-site `policy=` is conceptually cleaner than two parallel registries. Source-grounding for (1) recorded in blueprint §4.3; for (2) in §4.2. |
| 2026-05-11 | draft | Pre-release context clarified | User confirmed factpy-kernel is pre-release (rc-stage only, no PyPI publish, no GitHub Release announcement, no known downstream consumer). Triggered default-to-hard-cutover decision recorded in §0.7; eliminated original "§5.6 hard-cut vs grace" tradeoff and original "§5.11 release timing window" deliberation, collapsing §5 to **10 gaps**. |
| 2026-05-11 | draft | Blueprint seed created | Draft seed `2026-05-11_readpolicy-call-site-migration.md` + paired audit. §0 records initial direction as **pending §5 validation** (not LOCKED). §5 lists 10 gaps for iterative cadence per `feedback_iterative_gap_design`. No code, tests, or memory updates. Design branch `v0.1-readpolicy-call-site-migration-2026-05-11` forked at `ace2563` (current `master` HEAD). Paired impl branch deferred to scope-freeze per `feedback_design_impl_branch_isolation`. |

## Decision Notes

- 2026-05-11: §0 deliberately phrased as **"Initial Direction (pending §5 validation)"**, not "Core Locked Decisions", per audit-cadence discipline. Each of §0.1–§0.7 is a working hypothesis that the corresponding §5.x gate must source-ground before promoting to LOCKED. This preserves the `feedback_iterative_gap_design` cadence — `draft` stage must not contain pre-locked decisions outside the §5 gate sequence.
- 2026-05-11: Rejection of `fg.projections` namespace (§0.5) is the strongest constraint and sets the falsifier baseline for §5.5: any §5.5 outcome that creates a named-string lookup table (registry under a different name) violates §0.3 + §0.5 and must be rejected.
- 2026-05-11: Per `feedback_design_impl_branch_isolation`, paired impl branch `v0.1-readpolicy-call-site-migration-impl-2026-05-11` will be created at design HEAD **at scope-freeze**, not at seed time.
- 2026-05-11: Substrate-level "projection" usage in `kernel.core/view/projector.py` and `kernel.core/schema/schema_ir.py` is **out of scope**; this blueprint does not relitigate or rename those kernel-internal occupations.
- 2026-05-11: The full text of the 2026-05-11 design transcript is intentionally NOT copied into this audit (brevity); substantive findings are summarized in the "Design discussion converged on Option α'" row above. Transcript-derived constraints (e.g. §0.5 rejection of `fg.projections`) appear with source-grounding in the blueprint body, not as raw quotes.
