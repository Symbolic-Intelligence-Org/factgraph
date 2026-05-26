# Current Operational Memory

最后更新:2026-05-26(T5/T11.1 complete, T12 + T11.2 published, T11.2.5 dirty baseline triage in progress)

## 当前阶段

**Current branch:** `v0.2.0-t11-1-attach-view-scope-2026-05-26`

**Published branch head before T11.2.5:** `origin/v0.2.0-t11-1-attach-view-scope-2026-05-26 @ a864ada7`

**Current local work:** T11.2.5 dirty baseline triage (`workflow/blueprints/active/2026-05-26_t11-2-5-dirty-baseline-triage.md`) after scoped commit `ca45729a`.

**Sacred branch:** `master = 562c74195df43e933bed92a3ff25de94dd8ce666`; do not move it.

**Dirty baseline intentionally preserved:**

- `docs/references/working/design-points/readme.md`
- `examples/01_sdk_check_diagnose.ipynb`
- `examples/02_overlay_why_not_frontier.ipynb`
- `examples/archive/01_sdk_basics.ipynb`
- `src/factgraph/sdk/facade.py`
- `tests/test_sdk_assertion_record_set_view_filters.py`
- untracked `rainbird-ai sdk code/`

Do not absorb these into unrelated T12 / release / evidence work without explicit reclassification.

## Published Milestones

### T5 Result / Evidence / Explain Cycle

T5.1-T5.8 are complete and pushed on `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`.

| Slice | Archive | Key outcome |
|---|---:|---|
| T5.1 DTO Foundation + Digest Harness | `53781419` | `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, `DetachedRowError`, D19 digest harness. |
| T5.2 Public Evaluate Return-Shape Flip | `4e590e8a` | Public `fg.eval.evaluate(...) -> EvaluateResult`; CandidateSet internal. |
| T5.3 Explanation Envelope + Live Row Resolver | `ba5e5c26` | `Explanation` DTO and live `row.explain()`. |
| T5.4 Row Close + Manual Explain | `7464c3e3` | `row.close() -> Rule` and `fg.eval.explain(expr, head=closed_head)`. |
| T5.5 Why-Not Quarantine | `ec45f12f` | Failed `Explanation` is v1 why-not envelope; legacy why-not quarantined. |
| T5.6 SDK Rule Flip | `7aa1c6a3` | `factgraph.sdk.Rule` is application protocol Rule. |
| T5.7 Legacy Hard-Cut + Service/Docs | `8173c715` | SDK/service/OpenAPI/docs aligned with EvaluateResult; legacy shells removed. |
| T5.8 Semantics Lite + Wrapper Fix | `efd65c0e` | `ProbLogSemantics` / `PyReasonSemantics` work with application Rule / RuleExpr; C73/C75-lite. |

Current T5 D-docs D16-D26 were moved from `proposed` to `adopted` in T12 with implementation anchors.

### T11.1 Attach-Based View Consumer

T11.1 is complete and pushed on `v0.2.0-t11-1-attach-view-scope-2026-05-26`.

| Anchor | Outcome |
|---:|---|
| `76f46ada` | `FactGraph.attach(db, schema_classes=[...], view=view)` for durable Database views. |
| `eff86ad0` | Durable view immutability/update/delete boundary documented. |
| `f94c4b63` | Quickstart WHY batch fix archived. |

T11.1 closes the "durable view can be created but not consumed" gap. Method-level `view=` remains deferred; use attach-time view scoping.

### N1 Post-T5 Roadmap

`workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` is the working T6-T12 scheduling reference.

| Commit | Outcome |
|---:|---|
| `74668e41` | Draft roadmap. |
| `cbbd5b68` | Scoped roadmap + dependency graph / owner model / inventory. |
| `e6bfe357` | Working roadmap published to origin. |

Roadmap ordering default: `N1 -> T12 minimal housekeeping -> T11.2 cross-doc unblock -> T11.3 release machinery -> T6/T10/T8/T9`.

### T12 Minimal Housekeeping

T12 is complete and pushed on the T11 branch at `b3d17ac9`.

- `rule-expression-and-proof-track-plan.zh.md` remains active with a lifecycle note: T1-T5 are complete; future scheduling is superseded by the post-T5 roadmap; the file is retained as historical decomposition index because many active/historical references still cite it.
- D16-D26 are adopted with `Implementation Anchors:` metadata.
- `workflow/design/decisions/README.md` has the adopted D16-D26 index.
- `workflow/design/design-points/README.md` has the compact active design-point inventory.
- This repo-local memory has been compacted. The global Claude memory index at `/Users/zhenzhili/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/MEMORY.md` remains an explicit follow-up.

### T11.2 Cross-Doc Metadata Unblock

T11.2 is complete and pushed at `a864ada7`.

- `view_snapshot_digest` is accepted as the v0.2 public metadata bridge.
- Exact tuple fields (`db_id`, `tx_id`, `schema_digest`, `data_digest`, `view_digest`) remain v2/internal and require a new blueprint to expose.
- Stale "view-scoped attach is future" docs were corrected; method-level `view=` and snapshot attach remain deferred.

## Current T11.2.5 Dirty Baseline Triage

T11.2.5 classifies the standing dirty baseline before T11.3 release machinery.

- `src/factgraph/sdk/facade.py` + `tests/test_sdk_assertion_record_set_view_filters.py`: include as dedicated `T11.2.6 SDK assertion property access` behavior slice before release, or explicitly stash/revert by user.
- `examples/01_sdk_check_diagnose.ipynb`, `examples/02_overlay_why_not_frontier.ipynb`, `examples/archive/01_sdk_basics.ipynb`: defer to notebook namespace/output cleanup unless release scope changes.
- `docs/references/working/design-points/readme.md`: defer as reference-index cleanup.
- `rainbird-ai sdk code/`: leave untracked; optional provenance/license review only if user wants to retain it.
- T11.3 may rely on this classification, but `scripts/release.sh` still requires tracked dirty files to be landed, stashed, or explicitly reverted before dry-runs.

## Recommended Next Work

1. **Finish T11.2.5 dirty baseline triage**: close, archive, and push with explicit authorization.
2. **T11.2.6 SDK assertion property access**: resolve the only release-relevant tracked production/test dirty pair.
3. **T11.3 v0.2.0 release machinery**: release branch / changelog / CI / package governance after tracked dirty state is resolved.
4. **T6 Evidence-tree Phase B design skeleton**: large post-release design track unless release claims full evidence tree.
5. **T10 semantics adapter execution**: adapter-touching C74/C76/C77/C78, post-release default.

## Governance Reminders

- Never auto-push `master`.
- Ask once before each push; prior authorization does not roll forward.
- Keep dirty baseline isolated.
- For adopted decisions, keep files in `workflow/design/decisions/active/`; only `superseded` / `withdrawn` decisions move to archive.
- For design-points, archive only when lifecycle criteria in `workflow/design/design-points/README.md` are satisfied.
- For roadmap-driven work, each later blueprint still needs its own Step 4.6 inventory against active design-points and shipped source.
