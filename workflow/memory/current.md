# Current Operational Memory

最后更新:2026-05-27(T8-D shipped to origin; docs sync micro-pass in progress)

## 当前阶段

**Current branch:** `v0.2.0-t11-1-attach-view-scope-2026-05-26`

**Published branch head:** `origin/v0.2.0-t11-1-attach-view-scope-2026-05-26 @ 22891808`

**Most recent local work:** docs synchronization micro-pass for shipped-state indexes
(`CHANGELOG.md`, repo memory, roadmap, docs index, design-point index). This
work reflects already-published state only and does not change runtime, tests,
release machinery, or design commitments.

**Sacred branch:** `master = 562c74195df43e933bed92a3ff25de94dd8ce666`; do
not move it.

**Dirty baseline intentionally preserved(4 M + 3 U as of this sync):**

- `docs/references/working/design-points/readme.md`
- `examples/01_sdk_check_diagnose.ipynb`
- `examples/02_overlay_why_not_frontier.ipynb`
- `examples/archive/01_sdk_basics.ipynb`
- untracked `docs/references/working/change-requests-2026-05-27/`
- untracked `docs/references/working/identity-and-data-model-redesign-2026-05-27/`
- untracked `rainbird-ai sdk code/`

Do not absorb these into unrelated release, evidence, docs-sync, or cleanup work
without explicit reclassification.

## Published Milestones

### T5 Result / Evidence / Explain Cycle

T5.1-T5.8 are complete and pushed on
`v0.2.0-t5-result-evidence-explain-audit-2026-05-25`.

| Slice | Archive | Key outcome |
|---|---:|---|
| T5.1 DTO Foundation + Digest Harness | `53781419` | `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, `DetachedRowError`, D19 digest harness. |
| T5.2 Public Evaluate Return-Shape Flip | `4e590e8a` | Public `fg.eval.evaluate(...) -> EvaluateResult`; CandidateSet internal. |
| T5.3 Explanation Envelope + Live Row Resolver | `ba5e5c26` | `Explanation` DTO and live `row.explain()`. |
| T5.4 Row Close + Manual Explain | `7464c3e3` | `row.close() -> Rule` and `fg.eval.explain(expr, head=closed_head)`. |
| T5.5 Why-Not Quarantine | `ec45f12f` | Failed `Explanation` is v1 why-not envelope; legacy why-not quarantined. |
| T5.6 SDK Rule Flip | `7aa1c6a3` | `factgraph.sdk.Rule` is application protocol Rule. |
| T5.7 Legacy Hard-Cut + Service/Docs | `8173c715` | SDK/service/OpenAPI/docs aligned with EvaluateResult. |
| T5.8 Semantics Lite + Wrapper Fix | `efd65c0e` | `ProbLogSemantics` / `PyReasonSemantics` work with application Rule / RuleExpr; C73/C75-lite. |

### T11 / Release-Path Work

| Cycle | Head | Outcome |
|---|---:|---|
| T11.1 Attach-Based View Consumer | `f94c4b63` | `FactGraph.attach(db, schema_classes=[...], view=view)` for durable Database views. |
| T12 Minimal Housekeeping | `b3d17ac9` | T1-T5 planning lifecycle normalized, D16-D26 adopted, active design-point inventory added, repo memory compacted. |
| T11.2 Cross-Doc Metadata Unblock | `a864ada7` | `view_snapshot_digest` accepted as v0.2 public metadata bridge; stale view-scoped attach wording fixed. |
| T11.2.5 Dirty Baseline Triage | `28df81b7` | Dirty baseline classified; notebooks/reference index deferred; assertion property pair isolated for T11.2.6. |
| T11.2.7 Match API Design | `d69189d2` | `fg.read.match(EntityCls, template, **port_constraints)` design locked. |
| T11.2.6 SDK Assertion Property Access | `ecc8a8df` | Property-style assertion access shipped; old call forms preserved. |
| T11.3 Release Machinery | `80b9a2a3` | PyPI metadata renamed to `factgraph`; dry-run release gate passed with 271-file projection and 187 OK. |
| T11.2.9 Match Runtime | `ad349407` | First read-side match runtime shipped for `Rule` + AND `RuleExpr`. |
| T11.2.10 OR Match Runtime | `fd20338a` | OR `RuleExpr` support shipped for `fg.read.match(...)`; M5 completed. |

Live release / PyPI publish / GitHub Release remains a separate explicit user
gate.

### Reference / Docs Housekeeping

| Cycle | Head | Outcome |
|---|---:|---|
| N10 Reference Index Cleanup | `1c11a740` | `docs/references/README.md` rebased onto current `workflow/` and `src/factgraph/` paths; dirty working design-points readme left untouched. |

### Evidence Track

| Cycle | Head | Outcome |
|---|---:|---|
| T6 Evidence Phase B Design | `8fe7abdc` | Evidence §10 audit channel, §11 rendering, §14 D1-D20 deferred registry, and §15 T8 split proposal completed. |
| T7 Audit + Rendering Bridge | `e2abc6d2` | Renderer type guard, large-graph warning, 14-key metadata strict test, and audit docs alignment shipped. |
| T8 Split Inventory | `a872fa5b` | T8-A/B/C/D split quantified; T8-A first slice selected; T8-B reuse-before-rewrite plan recorded. |
| T8-A Metadata + Validation Foundation | `40a0ce47` | C135 runtime-enforced with 14-key exact-set/value checks and always-on metadata validation gates. |
| T8-B-1 Native Form 1 Topology | `9e9a7f49` | Native row `EvidenceGraph` now uses Form 1 topology with `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, and `EDGE_SUPPORTS`. |
| T8-D A+B Docs Alignment | `22891808` | Quickstart and SDK guide now document T8-A + T8-B-1 shipped behavior and deferred evidence boundaries. |

Evidence track current state:

- C135 metadata sufficiency is runtime-enforced and documented.
- C129 winning-path-only OR is runtime-visible and documented.
- C115 `EDGE_SUPPORTS` direction is runtime-enforced and documented.
- C118 intra-graph seed reuse is runtime-enforced and documented.
- Souffle row Form 1 conformance remains T8-B-2.
- ProbLog/PyReason enrichment remains T8-C and is gated by T10 or an
  engine-specific semantics lock.

## Recommended Next Work

1. **T8-B-2 Souffle conformance**: align the existing Souffle converter with
   row-result Form 1 metadata and T8-B native topology expectations.
2. **T8-C engine enrichment inventory**: decide whether ProbLog/PyReason can
   start from engine-specific semantics locks or must wait for broader T10.
3. **N6 notebook namespace cleanup**: reduce the dirty baseline by addressing
   the three tracked notebook files.
4. **T10 semantics adapter execution**: adapter-touching C74/C76/C77/C78 work,
   likely L-class unless narrowed by engine.

## Governance Reminders

- Never auto-push `master`.
- Ask once before each push; prior authorization does not roll forward.
- Keep dirty baseline isolated.
- For adopted decisions, keep files in `workflow/design/decisions/active/`;
  only `superseded` / `withdrawn` decisions move to archive.
- For design-points, archive only when lifecycle criteria in
  `workflow/design/design-points/README.md` are satisfied.
- For roadmap-driven work, each later blueprint still needs its own Step 4.6
  inventory against active design-points and shipped source.
