# Templates

Centralized inventory of all workflow document templates. Per Q4 §4.1, this is the **only canonical location** for workflow templates; no per-pillar `templates/` subdirectories exist.

## Inventory (9 templates)

| Pillar | Template | Purpose |
|---|---|---|
| `blueprints/` | `task_blueprint.md` | Standard task blueprint (8-state lifecycle) |
| `blueprints/` | `task_blueprint.audit.md` | Sibling paired audit log |
| `blueprints/` | `legacy_reconstructed_archive.md` | Reconstructed legacy archive |
| `blueprints/` | `legacy_reconstructed_archive.audit.md` | Reconstructed legacy audit log |
| `design/` | `design-point.md` | Conceptual design essay (iterative, non-authoritative) |
| `design/` | `decision.md` | ADR-style decision record (4-state) |
| `audit/` | `vs-shipped.md` | Stage 1 drift-vs-shipped audit |
| `audit/` | `preflight.md` | Step 4.3 preflight safety check |
| `audit/` | `synthesis.md` | Stage 3 post-Q re-bucketing |

## Unified 7-field metadata header (per Q4 §4.3)

Every workflow document created from a template includes this block as the first content section after the H1 title:

```
- Status: <pillar-specific value>
- Created: YYYY-MM-DD
- Last Updated: YYYY-MM-DD
- Authority: <pillar-specific statement>
- Inputs:
  - <pointers to upstream sources>
- Outputs / Downstream:
  - <pointers to consuming documents>
- Related:
  - <cross-references>
```

**Field semantics**:
- `Status` — always present; value varies by pillar (8 states for blueprints; 4 ADR states for decisions; optional drafting marker / `n/a` for design-points + audits; paired audit logs mirror their sibling)
- `Created` / `Last Updated` — `YYYY-MM-DD` format
- `Authority` — pillar-specific role declaration
- `Inputs` / `Outputs / Downstream` / `Related` — bullet lists; use `- (none)` if empty

**Pillar-specific extensions** are allowed *beyond* the 7-field minimum (not as substitutes). Examples: blueprints add `Related Modules` + `Audit Log`; decisions add `Branch` + `Depends on`; audits add `Source intent` / `Blueprint` / `Source audit` / `Closed Q decisions` per sub-type.

**Paired blueprint audit log convention**: paired logs (`<basename>.audit.md` siblings to blueprints) carry the 7-field header with `Status` mirroring the sibling, `Authority: paired blueprint audit log`, `Inputs` pointing to the sibling blueprint, and `Outputs / Downstream` typically `- (none)`.

## Customization policy (per Q4 §4.5)

**Templates are the only approved starting point** for new workflow documents. Manual drafting from scratch is discouraged.

- **Allowed**: extending with additional sections; reordering within hierarchical level (where pillar AGENTS permits); omitting clearly-marked optional sections.
- **Not allowed**: modifying the 7-field header schema, omitting required fields, substituting field names, silently dropping empty `Inputs:` / `Outputs / Downstream:` / `Related:` bullets (use `- (none)` instead).

Rationale: templates encode hard-won cadence lessons. Free-form drafting loses those lessons in drift.

## Per-pillar pointer rule (per Q4 §4.4)

Each pillar's `README.md` (which absorbs the former pillar-AGENTS content post SC-1 merge) includes a "Templates" section pointing to the templates that pillar consumes. Agents do not perform global search per use; they look up locally in the pillar README.
