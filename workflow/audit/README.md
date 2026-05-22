# Audit Pillar

Drift / anti-drift records: design-doc-vs-shipped triage, pre-implementation safety checks, and post-Q re-bucketing syntheses. Governs the `workflow/audit/` pillar per Q3 (commit `ae375ce5`).

For the umbrella governance see [`workflow/AGENTS.md`](../AGENTS.md). For the canonical methodology see [`workflow/CADENCE.md`](../CADENCE.md).

## ⚠️ Two distinct "audit" concepts (per Q3 §4.2)

The word "audit" in this repo refers to **two distinct things**. Do not confuse them:

| Concept | Filename | Location | Role | Governed by |
|---|---|---|---|---|
| **Paired blueprint audit log** | `<basename>.audit.md` (sibling to blueprint) | `workflow/blueprints/{active,archive}/` | Per-blueprint event log of state transitions + decision notes | [`workflow/blueprints/README.md`](../blueprints/README.md) |
| **Standalone audit record** | `YYYY-MM-DD_<topic>-<subtype>.md` | `workflow/audit/{active,archive}/` | Cross-cutting drift triage, preflight safety check, post-Q synthesis | this file |

This document governs the **standalone audit record** concept. For the paired blueprint audit log, see [`workflow/blueprints/README.md`](../blueprints/README.md) §Paired vs standalone audit.

## Layout

```
workflow/audit/
├── README.md            (this file — pillar governance + orientation)
├── active/              (audits whose consuming blueprint is in workflow/blueprints/active/)
└── archive/             (audits whose consuming blueprint has archived)
```

Flat `active/archive` split — no sub-type subdirectories. Sub-type is encoded in the filename suffix.

## Three standalone sub-types (per Q3 §4.3)

| Sub-type | Filename suffix | Purpose | CADENCE stage |
|---|---|---|---|
| **`vs-shipped`** | `YYYY-MM-DD_<topic>-vs-shipped.md` | Compares a design doc against shipped runtime code completely (not grep snippets). Builds 5-state triage table + open question list. | Stage 1 audit |
| **`preflight`** | `YYYY-MM-DD_<topic>-preflight.md` | Re-reads blueprint-referenced shipped files at preflight-row-drafting time. Surfaces 5-bucket severity findings before scoped anchor. | Step 4.3 |
| **`synthesis`** | `YYYY-MM-DD_post-q-<topic>-synthesis.md` (with `post-q-` prefix when Q chain exists) | Re-buckets audit drift after Q decisions close. 5-bucket output. | Stage 3 |

No other sub-types are recognized; adding one requires a Q-delta-decision against Q3.

## Preflight trigger conditions (per Q3 §4.4)

Standalone preflight is **REQUIRED** when any of the following applies:

1. **Subtractive removal** — slice deletes a shipped public symbol / method / route.
2. **Cross-module protocol change** — DTO shape / ledger format / identity formula spanning ≥2 modules.
3. **Namespace migration** — package rename or structural restructure.
4. **Historical-design compatibility** — implementation must precisely match a historical design (e.g., compatibility shim).
5. **Pre-release verification** — rc.N → release tag or PyPI publish.

Standalone preflight is **OPTIONAL** when:

1. Pure additive feature within a single module.
2. Bug fix in established API surface.
3. Pure refactor with full test coverage + no observable behavior change.
4. Cleanup-style slice (per [`workflow/blueprints/README.md`](../blueprints/README.md) cleanup-slice cadence section).
5. Tiny local fix (per [`workflow/CADENCE.md`](../CADENCE.md) Scope-and-Applicability).

**Voluntary preflight is permitted** when not required, provided the rationale is recorded in the blueprint §6 or §10. Default on doubt: **required**.

## Synthesis trigger conditions (per Q3 §4.5)

Standalone synthesis is **REQUIRED** when:

1. ≥3 Q decisions close in a single audit's chain, AND
2. Audit findings span ≥2 of the 5 buckets (blueprint-eligible / cross-doc blocked / no independent action / already aligned / deferred).

Standalone synthesis is **OPTIONAL** when:
- Single Q decision closes (Q1-only slice), OR
- All audit findings are obviously single-bucket, OR
- Cleanup-style slice with no Q-resolution chain.

## Lifecycle (per Q3 §4.6)

- `active/` while the consuming blueprint is `draft` / `scoped` / `implementing` / `implemented` (i.e., still in `workflow/blueprints/active/`).
- `archive/` moves in the same commit batch as the consuming blueprint's Step 4.9 archive.
- An audit serving multiple consuming slices moves to archive when the **last** consumer archives.

Optional `Status:` header field for drafting visibility: `skeleton` / `complete` / `superseded`. The directory placement (`active/` vs `archive/`) is the canonical lifecycle signal; `Status` is convenience only.

## Cross-branch visibility (per Q3 §4.7)

Standalone audit files are **slice-scoped artifacts**, not globally-visible reference documents:

- An audit lives on the branch that created it (typically the audit-only branch or the consuming blueprint branch).
- Within the consuming slice's lifetime, audits are branch-local. Cross-slice reference requires explicit branch checkout.
- At slice closure (Step 4.9 archive), the audit + decision + blueprint chain is completed on the slice branch. Archive itself does **not** integrate to `master` or any release branch.
- Integration into `master` is a **separate, explicit, user-authorized push or merge** governed by CADENCE Sacred-branch isolation rule.
- "Globally visible" means **authorized canonical-branch integration**, not the archive commit itself.

## Header convention (per Q3 §4.8)

Every standalone audit file includes the 7-field metadata header per Q4 §4.3, with audit-specific values:

- `Status: <skeleton | complete | superseded>` (optional; directory placement is canonical)
- `Authority: working triage document; informs but does not lock implementation`

Plus sub-type-specific extensions:

- **vs-shipped**: `Source intent:` (link to design doc being audited)
- **preflight**: `Blueprint:` (link to consuming blueprint)
- **synthesis**: `Source audit:` (link to vs-shipped) + `Closed Q decisions:` (list of Q decision links)

## Templates (per Q4 §4.4)

Authoritative starting points live in `workflow/templates/audit/`:

- [vs-shipped.md](../templates/audit/vs-shipped.md) — Stage 1 audit template
- [preflight.md](../templates/audit/preflight.md) — Step 4.3 preflight template (includes trigger condition check)
- [synthesis.md](../templates/audit/synthesis.md) — Stage 3 synthesis template (includes 5-bucket structure)

Manual drafting (not from template) is discouraged; see [`workflow/templates/README.md`](../templates/README.md) §customization policy.

## See also

- [`workflow/blueprints/README.md`](../blueprints/README.md) §Paired vs standalone audit — the other "audit" concept
- [`workflow/CADENCE.md`](../CADENCE.md) Stage 1 / Step 4.3 / Stage 3 — how the 3 sub-types integrate with the broader cadence
