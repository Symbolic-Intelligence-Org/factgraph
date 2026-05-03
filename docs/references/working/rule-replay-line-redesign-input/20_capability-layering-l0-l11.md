# Evidence Vision Synthesis (2026-05-02)

- Status: working / design exploration only
- Companion: [README.md](./README.md)
- Source-checked against: kernel @ `61e5380` (rollup containing v0.1.1 + v0.1.2 + v0.1.3)
- Branch invariant: see [project_release_branch_invariants.md](~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_release_branch_invariants.md). This document does not propose any change to `v0.1-oss-prep` or `master`.

## 0. The non-negotiable invariant: B'' pivot

Everything below assumes the **B'' design pivot** holds:

- **Rule / derivation is operable.** Users can replay with patches, disable conditions, build variants. v0.1.1-v0.1.3 implements this.
- **Evidence is read-only and run-derived.** Evidence is what the runtime produced; users do not edit it. v0.1.1-v0.1.3 enforces this in code (no write surface, immutable DTOs, sidecar-only mapping).

Reversing this is `L11` below — explicitly **design-reserved**, likely v0.2 major if ever, and out of scope for any v0.1.x or v0.2 minor.

If a future capability appears to require evidence mutation, the right response is almost always to push the operation back to the rule side (a new replay action, a sidecar annotation, or a new derived view) — not to relax B''.

## 1. Layered capability map

These eleven layers are not a tower (each does not depend strictly on all below). They are a taxonomy. The dependency graph in §2 spells out actual blocking relationships.

| Layer | What it gives users | Status | Where it lives today (or would live) |
|---|---|---|---|
| **L0. Structured evidence data** | `SupportArtifact` with `pred_witnesses` / `non_fact_steps` / `rule_ref_edges`; JSON-friendly shape via `support_artifact_to_dict` | ✅ pre-v0.1 | `kernel.core.store._support` |
| **L1. Shallow metadata diff** | `EvidenceComparison` over retained candidate pairs; status `available` / `degraded` / `unsupported`; flags `support_kind_changed` / `support_digest_changed` / `confidence_changed` / `confidence_kind_changed` | ✅ v0.1.1 | `kernel.sdk.replay_runtime.compare_evidence` |
| **L2. Reverse-mapping evidence → rule module** | `support_key_to_module_id(key, module_map)`; `ReplayResult.{original,variant}_module_map` | ✅ v0.1.2 | `kernel.authoring.module_ir`, `kernel.sdk.replay_runtime` |
| **L3. Locator stability under disable** | `b{branch}.a{atom}` survives disable-condition without index shift; disabled atoms still in `module_map.locator_to_module_id` | ✅ v0.1.3 | `kernel.core.rules.where_eval`, `kernel.core.store._support_capture` |
| **L4. Per-frame proof tree diff** | Beyond shallow metadata: structural diff over individual `pred_witnesses` and `non_fact_steps` rows between two retained candidates ("at this exact step, evidence used to be X, now Y") | ❌ deferred | would extend `kernel.sdk.replay_runtime.compare_evidence` |
| **L5. Cross-run module aggregation** | "How did evidence for this `module_id` change across our last N replay runs?" — index existing data by `(module_id, run_id)` | ❌ deferred (data exists, no aggregation/index layer) | new `kernel.audit` query helper or `kernel.sdk` aggregator |
| **L6. Lazy why-not / candidate-universe board** | The red/green completeness view: "what almost matched but was excluded, and why?" — Decision Assurance positioning depends on this | ❌ deferred | new evaluator hook to capture "branches that almost succeeded"; large scope |
| **L7. Cross-engine evidence translation** | PyReason / Souffle / ProbLog evidence shapes unified for comparison; cross-engine replay diff | ❌ deferred | touches all three adapters; engine-neutral evidence schema needed |
| **L8. Audit JSONL replay persistence** | Replay session events (input payload, action, ReplayResult, diff) recorded as engine-neutral JSONL inside the audit package; replay can be re-loaded and re-run from the package alone | ❌ deferred (engine-neutral export owner is prerequisite) | extend `kernel.audit` query package + replay runtime hook |
| **L9. Interactive UI** | SPA-style tree navigation, drill-down, search, filter, side-by-side replay diff. Today only static HTML via `service.static_ui.render_audit_static_site` | ⚠️ data fully present, **frontend layer empty** | new frontend artifact (likely separate repo or `service/web/` subtree); not a kernel concern |
| **L10. Sidecar annotation** | Users add notes / tags / approvals on evidence nodes WITHOUT mutating evidence. Stored as separate schema referencing `(support_digest, atom_key, author, body, timestamp)` | ❌ not designed | new schema + write surface; B'' compatible (annotation ≠ mutation) |
| **L11. Mutable evidence tree** | Users edit evidence directly; partial proof re-evaluation as source of truth | ❌ **design-reserved by B'' pivot** | would invalidate every v0.1.x/v0.2 minor invariant; v2.0 major-bump territory at earliest |

### Completeness by interpretation

| Scope interpretation | What it includes | Done % |
|---|---|---|
| Read-only foundation only | L0-L3 | **100%** |
| Foundation + static rendering | L0-L3 + service.static_ui | ~40% |
| Read-only complete picture | L0-L9 (excludes L10/L11) | **~30-35%** |
| Including sidecar annotation | L0-L10 (still B'' compatible) | ~25-30% |
| Maximalist "everything I might want" | L0-L11 | ~20-25% |

### Clarifying what "interactive UI scenario" needs

The UX a user might describe — "看完整 evidence tree + 点开条件查推理状态 + 倒出 + 标注" — maps to:

| User action | Layer needed | Currently? |
|---|---|---|
| See structured evidence | L0 | ✅ |
| Click condition → see "this came from rule module X" | L2 | ✅ |
| Click condition → see step-by-step proof | L4 | ❌ |
| Track this condition's evidence across runs | L5 | ❌ (data exists, no helper) |
| Export full audit including replay | L8 | ❌ |
| Add note to evidence node | L10 | ❌ |
| See "what almost matched" | L6 | ❌ |
| Compare PyReason vs Souffle reasoning of same query | L7 | ❌ |
| Browse/search/drill-down in browser | L9 | ❌ (only static HTML today) |

Most of the scenario is doable **without breaking B''**. None of it requires L11.

## 2. Dependency graph

```
L0 (data) ────────────────────┬──────────────┬──────────┬─────────────┬────────────┐
                              │              │          │             │            │
                              ▼              ▼          ▼             ▼            ▼
                          L1 (shallow      L2 (reverse  L4 (per-      L8 (audit    L10 (sidecar
                          metadata          map)         frame proof   JSONL        annotation,
                          diff)             │            diff)         persistence) refs into L0)
                              │              │          │             │ │
                              │              ▼          │             │ │
                              │          L3 (locator    │             │ │
                              │           stability     │             │ │
                              │           under disable)│             │ │
                              │              │          │             │ │
                              │              ▼          │             ▼ │
                              │          L5 (cross-run  │      L5 also  │
                              │           aggregation,  │      benefits │
                              │           per module_id)│      from L8  │
                              │                         │               │
                              ▼                         ▼               │
                          L6 (lazy why-not /         L9 (interactive    │
                          candidate universe;         UI; consumes      │
                          new evaluator hook;         everything below) │
                          structurally separate       depends on        │
                          from L1-L5)                 L0-L8 + L10       │
                                                                        │
                          L7 (cross-engine                              │
                          evidence translation;                         │
                          touches PyReason/Souffle/ProbLog;             │
                          structurally separate, can land any time)     │
                                                                        │
                          L11 (mutable evidence; B'' reversal)          │
                          would invalidate every other layer's          │
                          read-only assumption ────────────────────────-┘
                          DO NOT plan around this.
```

### Key dependencies stated explicitly

- **L4 (proof diff)** depends only on L0; can land independently of L5/L8.
- **L5 (cross-run aggregation)** depends on L0 + L2; gains substantially from L8 (without persistence, "across runs" is limited to same-process state).
- **L6 (why-not / candidate universe)** depends on a NEW evaluator hook (capture near-misses), independent of L1-L5. Largest scope item.
- **L7 (cross-engine translation)** depends on L0 + per-engine internal knowledge; orthogonal to other layers but very wide (touches three adapters + needs unified schema).
- **L8 (audit JSONL persistence)** depends on L0 + an engine-neutral export owner (which doesn't exist yet); enables L5 and L4-historical use cases.
- **L9 (interactive UI)** is a frontend artifact; depends on whatever data layers ship; pure orthogonal to kernel work.
- **L10 (sidecar annotation)** depends only on L0 (needs to reference evidence nodes); can land any time without affecting other layers.
- **L11 (mutable evidence)** would require revisiting B'' pivot, invalidating every layer's read-only assumption. Treat as v2.0 or never.

## 3. Recommended phasing

The user's instinct (L8 first, then L4/L5, then UI) is correct, with one addition: L10 sidecar annotation is independent and could land in parallel with the main line.

### Phase A — Persistence as the fulcrum (L8)

Rationale: L8 unlocks "load a replay session from an audit package and re-run / re-inspect it." Without persistence, every replay is in-memory only and disappears at the end of the process. This is the prerequisite for:
- L5 cross-run aggregation against historical packages
- Any L4 use case where you want to compare "today's replay" vs "yesterday's replay"
- L9 UI loading from an audit package
- Reproducible bug reports
- Any future integration with external audit / governance systems

Scope estimate: 5-7 rounds (one full v0.x patch line). Requires deciding on:
- engine-neutral export owner (probably new module in `kernel.audit`)
- JSONL schema (replay event types, payload format, version field)
- read-back API
- backward compat with existing audit package format

### Phase B — Read-richer evidence (L4 + L5 in parallel)

Once L8 lands, L4 and L5 both become substantially more valuable AND can proceed in parallel (different code paths):

- **L4** extends `compare_evidence` from shallow metadata to per-frame structural diff. Returns "this `pred_witness` row was present in original but missing in variant" or "this `non_fact_step` had status `succeed`, now `fail`". Pure read-only deepening of L1.
- **L5** indexes evidence by `(module_id, run_id, support_digest)` and exposes "all evidence variants for module X across the last N runs" or "this module's confidence drift over time." Reads from in-process data + audit packages (L8).

Each is a 5-7 round patch. Order doesn't matter; do whichever is more user-driven.

### Phase C — Interactive UI (L9)

Once L4/L5 exist, interactive navigation has rich data behind it. L9 itself is mostly frontend (SPA, tree widget, search, filter, side-by-side diff). Backend support is just exposing the L0/L1/L4/L5 data over HTTP (likely extending `service.static_ui` into a real `service.web/` subtree, or a separate frontend artifact altogether).

Scope estimate: large but mostly outside kernel — could be a separate repo or a new top-level subtree. Frontend rounds dominate.

### Independent track — Sidecar annotation (L10)

Can land any time (3-5 rounds). New schema for `EvidenceAnnotation`, write API for adding annotations referencing `(support_digest, atom_key)`, read API for querying annotations alongside evidence. Doesn't block or require any other layer beyond L0.

### Larger v0.2 minor candidates (post Phase A-C)

- **L6 (lazy why-not / candidate-universe board)**: 6-10 rounds; needs new evaluator capture; this is the Decision Assurance positioning differentiator. High value, large scope.
- **L7 (cross-engine evidence translation)**: 8-12 rounds; touches PyReason, Souffle, ProbLog adapters; needs unified evidence schema design before any code. Very wide.

### Explicit non-candidate

- **L11 (mutable evidence)**: NOT a recommended candidate. If a real user need surfaces that seems to require it, the first response should be to find an L1-L10 alternative. Reversing B'' is a major-bump decision and would invalidate v0.1.x/v0.2.x semantic guarantees.

## 4. Candidate blueprints (sketches only)

Each of these could become a concrete `docs/blueprints/active/2026-XX-XX_*.md` when the user wants to start a new patch line. **Sketches only — not commitments.** Real implementation requires its own Step 0 spike.

### Candidate 1 — `audit-jsonl-replay-persistence` (L8)

- **One-line:** Persist replay events (input, action, result, diff) into the existing audit package as an engine-neutral JSONL stream; provide read-back to reload + inspect a replay from disk alone.
- **Estimated scope:** 5-7 rounds (one v0.x patch line).
- **Step 0 must answer:** Where does the engine-neutral export owner live (`kernel.audit` extension vs new module)? What's the JSONL row schema and version field? How does it interact with existing `kernel.audit` query package? Backward compat for audit packages without replay events?
- **Why first:** Unlocks L5 historical aggregation, L4 historical diff, and L9 UI loading from packages. Highest-leverage single piece.
- **Risk:** Schema decisions are sticky once persisted; needs careful Step 0.

### Candidate 2 — `per-frame-evidence-proof-diff` (L4)

- **One-line:** Extend `compare_evidence` from shallow metadata to per-frame structural diff over `pred_witnesses` and `non_fact_steps` rows of two retained candidate pairs.
- **Estimated scope:** 5-7 rounds.
- **Step 0 must answer:** What's the diff granularity (atom-key level? row level? subfield level)? How to handle ordering (`pred_witnesses` is sorted by `pred_atom_key`, but diff should be position-agnostic)? When should diff status escalate to `degraded` / `unsupported`? Should it reuse `EvidenceComparison` shape or a new richer DTO?
- **Why valuable:** Closes the gap between "metadata says something changed" and "show me what changed." Direct user-visible improvement.
- **Risk:** Can become big quickly if scope creeps to "render the diff prettily" — keep it data-only.

### Candidate 3 — `evidence-sidecar-annotation` (L10)

- **One-line:** New schema for `EvidenceAnnotation(support_digest, atom_key, author, body, created_at)`; write API to add annotations; read API to fetch annotations alongside evidence; storage independent of evidence (sidecar table or separate JSONL stream).
- **Estimated scope:** 3-5 rounds (smallest, most self-contained).
- **Step 0 must answer:** Storage backend (in-process? sqlite sidecar? audit package extension?)? Identity and auth model for `author` field? Mutability of annotations (edit / delete or append-only)? Schema versioning? Permissions / scoping?
- **Why valuable:** First B''-compatible "write" capability on evidence side without breaking read-only invariant. Opens space for review workflows, governance signoffs, "I disagree with this reasoning" trails.
- **Risk:** Can become a full annotation/review/workflow system if not scoped tightly.

### Honorable mention — `cross-run-module-evidence-tracking` (L5)

- **One-line:** Helper that aggregates evidence per `module_id` across multiple `ReplayResult`s and historical audit packages.
- **Estimated scope:** 3-5 rounds **after L8** (without L8, "historical" is in-process only).
- **Why deferred:** Best done after L8 lands; in-process-only version would be small and limited.

## 5. What this synthesis explicitly does NOT do

- Does not commit any of these to a release schedule.
- Does not commit to any specific v0.2 numbering or branch convention.
- Does not propose any change to `v0.1-oss-prep` or `master` (release branches frozen, see invariant memory).
- Does not propose merging any v0.1.x patch line into release base.
- Does not lock down API signatures — sketches in §4 are illustrative.
- Does not pre-decide which candidate becomes the next active blueprint — that's a user decision when ready.
- Does not address L11 (mutable evidence) beyond noting it's design-reserved.

## 6. When to use this document

- **Future blueprint authors:** when proposing a new evidence-side patch, cite this synthesis as the design context. Adopt only the layers your scope actually covers; do not bundle multiple layers.
- **When a user request appears to need evidence mutation:** check if it can be satisfied by L0-L10 first. If genuinely needs L11, escalate as a B'' pivot reversal decision (probably v2.0 conversation).
- **When updating v0.1.x:** this document is informational only; no v0.1.x patch should claim to address an evidence layer beyond L0-L3 unless we explicitly start a new evidence-focused patch line.
- **When this synthesis becomes stale:** when an L4-L10 layer actually lands, mark it ✅ here AND update the dependency graph for what becomes unblocked.

## 7. Trace to source

This document was synthesized from:
- `kernel.sdk.replay_runtime` (L1, L2, L3 surface)
- `kernel.authoring.module_ir` (L2 join helper, module map)
- `kernel.core.store._support` (L0 data shape, key generators)
- `kernel.core.rules.where_eval` (L3 disable threading)
- `service.static_ui` (existing rendering)
- archived blueprints `2026-05-01_rule-replay-with-evidence-diff.md`, `2026-05-02_v0.1.2-rule-module-ir.md`, `2026-05-02_v0.1.3-disable-condition.md`
- abandoned blueprint `2026-05-02_v0.1.4-param-override.md` (lesson: don't bundle distinct capabilities under one name)
- session memory `feedback_invariant_defense_in_depth.md`, `feedback_narrow_public_api.md`, `project_release_branch_invariants.md`

If any layer assignment looks wrong against current source, the source is authoritative — fix this synthesis.
