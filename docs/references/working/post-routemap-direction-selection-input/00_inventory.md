# 00 — Inventory: Loose Ends & Deferred Items

> See [README.md](README.md) for context.

## 1. Branch state (snapshot 2026-05-07)

- Active branch: `v0.1-public-surface-2026-05-06`, based on Batch 7 hardening final `3baf4ac`
- Sacred branches not touched: `master`, `v0.1-oss-prep`
- Round Story Completion Plan (Batches 0-8) all implemented and archived; final Batch 8 closed at `6b32972` (2026-05-06)
- Master plan §10 close-out filled
- `kernel.application` and `kernel.audit` documented as **advanced importable surfaces**; `kernel.sdk` remains the only product public surface

## 2. Active blueprints — by status (31 total in `docs/blueprints/active/`)

### A. Truly in-flight (status: draft, strategic, post-v0.1)

5 blueprints. None are blocking the immediate next decision; all are post-v0.1 in nature:

| Blueprint | Subject |
|---|---|
| [2026-03-29_dialog-agent-blueprint-v1.md](../../../blueprints/active/2026-03-29_dialog-agent-blueprint-v1.md) | Original product-public layer for non-technical SMEs (multi-turn dialogue + document extraction + engine routing); v0.1 explicitly deferred |
| [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](../../../blueprints/active/2026-04-09_dialog-agent-blueprint-v1.1-delta.md) | Delta refinement to dialog agent v1; same deferral status |
| [2026-03-31_ontology-feasibility-analysis.md](../../../blueprints/active/2026-03-31_ontology-feasibility-analysis.md) | Ontology integration feasibility spike; reference-stage |
| [2026-03-31_ontology-integration-concept.md](../../../blueprints/active/2026-03-31_ontology-integration-concept.md) | Ontology integration concept design; concept-stage |
| [2026-04-03_market-alignment-guide.md](../../../blueprints/active/2026-04-03_market-alignment-guide.md) | Market positioning / persona alignment; reference doc |

### B. Parked governance docs (status: implemented, retained for reference; 26 entries)

These are post-implementation governance/authority anchors that remain in `active/` for cross-reference. They are **not in-flight work**, but they are referenced by future blueprints and so live next to active items rather than archive:

- 2026-03-22 architectural-decisions-v2 (architecture authority record)
- **2026-03-28 evidence-graph-unified-explain** (cross-engine evidence DTO; **possibly overlaps with candidate B** below)
- 2026-03-30 problog-candidate-evidence-tree (adapter evidence rendering)
- 2026-03-30 pyreason-runtime-explain-timeline (adapter evidence rendering)
- 2026-04-27 oss-prep-v0.1 (OSS preparation gate; passed)
- 2026-04-28 audit-delivery-contract (audit package contract)
- 2026-04-28 release-surface-cleanup (release tooling)
- 2026-04-28 runtime-authority-cleanup (application-first authority anchor)
- 2026-04-28 v0.1-release-candidate (RC verification gate; PASSED, no publish action in Batch 8)
- 2026-04-29 v0.1-onboarding-hardening (README/quickstart hardening)
- 2026-05-05 round-story-completion-plan (master plan; closed)
- (15 more older governance/reference items)

> **Action item — outside the scope of this bundle:** the `active/` vs `archive/` convention has drift. Per `.claude/skills/blueprint/SKILL.md` lifecycle, `implemented` should typically transition to `archived`. The team has chosen to keep governance anchors in `active/` for reference. Worth a separate housekeeping pass.

## 3. Deferred items + reactivation triggers (19 total)

### A. From [Batch 8 Public Surface §5.5.5](../../../blueprints/archive/2026-05-06_public-surface.md) — 7 items

| Deferred item | Reactivation trigger |
|---|---|
| SDK shell for Check / Diagnose | A concrete user-facing workflow needs a human-friendly method and can define outward result shapes without exposing application DTOs |
| SDK shell for Fact Overlay / ProofFrame / Why-not / rule actions | Same as above, **but each family must get its own Step 0** (Batch 8 falsifier #3 TRUE: heterogeneous families, one method family would be false merge) |
| Service routes (HTTP) | A delivery/auth/session blueprint scopes HTTP DTOs and route ownership |
| Projection example add-back | A selected example passes projection import/link/smoke gates and is explicitly allowlisted |
| Batch 6 Frontier / rule-action event families | A persistence consumer requires them; round-event schema upgrade in own blueprint |
| Batch 7 single-frame diff / L5 aggregation public methods | Public SDK or repeated internal caller proves a stable API need |
| Batch 4 ProofFrame `rule_refs` hardening | Independent post-archive hardening; not bundled into Batch 8 |

### B. From [Round Story Plan §3 / §10.4](../../../blueprints/active/2026-05-05_round-story-completion-plan.md) — 12 items

| Deferred item | Reactivation trigger |
|---|---|
| L7 cross-engine evidence translation | New engine adapter + concrete evidence schema unification need |
| L9 Interactive UI / SPA tree visualization | Explicit product UX requirement |
| L10 Sidecar annotation system | Product demand |
| L11 Mutable evidence tree | v2.0 reserved (non-target for v0.1) |
| §6.7 Declarative engine capability schema | New engine onboarding fires |
| Direction D unified status vocabulary | Cross-capability single-vocabulary consumer need |
| Direction F shared condition identity (`shared_id`) | Shared library condition reuse becomes product-critical |
| L6 lazy why-not carrier / near-miss tracking | UI-level near-miss exploration or lazy candidate consumer |
| Minimal cause identification (status flips) | Concrete causal-analysis consumer |
| L5 cross-run aggregation | Persisted events gain stable `module_id`, OR fresh aggregation scope without module identity |
| Any new substrate in `kernel.sdk` | Hard constraint violation proof (per application-first authority); see [60_lessons-learned.md](../rule-replay-line-redesign-input/60_lessons-learned.md) |
| Batch 3 fact-side `add` | Step 0 clarifies add policy semantics |

## 4. Production verification gate state

Per [2026-04-28_v0.1-release-candidate.md](../../../blueprints/active/2026-04-28_v0.1-release-candidate.md) and Batch 8 §5.5.4:

- RC: **PASSED**
- Wheel/projection: 261 files, default-deny, kernel-only
- README quickstart blocks: print `Alice` (verified)
- Public-doc deny-pattern scan: clean
- `git diff --check`: clean
- Batch 8 release-day checkpoint: gate added but no publish action
- **Publish trigger: explicit user authorization** (`v0.1-oss-prep` and `master` are sacred per memory)
