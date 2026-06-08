# Audit Log: S0 — Rule.repr Rename

- Blueprint: [2026-06-08_explain-layer-s0-rule-repr.md](./2026-06-08_explain-layer-s0-rule-repr.md)
- Status: scoped

---

## Event Log

| Date | Event | Notes |
|---|---|---|
| 2026-06-08 | blueprint created (draft) | Preflight source-read of `rule.py` (629 lines) + blast-radius grep complete. 17 shipped symbols catalogued. 3 scope questions Q-S0-A/B/C identified, must resolve before `scoped`. |
| 2026-06-08 | scope questions resolved (draft) | User clarified alpha-version policy: no historical compatibility required. Q-S0-A/B/C all resolve in-scope as direct rename (`desc_template` → `repr_template`, service `"desc"` → `"repr"`). Rule-level deprecated alias plan removed; S0 is direct `desc` → `repr` rename. |
| 2026-06-08 | scoped | Step 4.6 scope freeze. S0 scope locked as direct alpha rename across Rule, evaluate-result template key, `OccurrenceInspect`, and service response; no compatibility aliases or old wire keys retained. |

---

## Decision Notes

### D-1: Direct alpha rename, no compatibility alias
**Decision**: S0 removes the deprecated-alias plan. `Rule.desc`, `Rule.render_desc()`, `OccurrenceInspect.desc_template`, evaluate-result `"desc_template"`, and service `"desc"` are all renamed directly to `repr` naming in the implementation slice. No duplicate alias fields, deprecated methods, or old wire keys are retained.

**Rationale**: User clarified this is an alpha surface, so historical compatibility is not a requirement. Direct rename keeps the implementation smaller and avoids carrying compatibility semantics into a still-forming API.

### D-2: `content_digest` stability
**Decision**: `content_digest` hashes only `ports` and `when` (verified at `rule.py:108-113`). Adding/renaming `repr`/`desc` does NOT affect digest values. No digest migration needed.

**Rationale**: Verified from shipped source — payload dict keys are `"ports"` and `"when"` only.

### D-3: Q-S0-A/B/C resolution
**Status**: Resolved. All three blast-radius questions are in S0 scope:
- **Q-S0-A**: `evaluate_result.py:965` `"desc_template"` becomes `"repr_template"`.
- **Q-S0-B**: `OccurrenceInspect.desc_template` becomes `repr_template`.
- **Q-S0-C**: `service/runtime_v1.py:2498` `"desc"` becomes `"repr"`.

**Rationale**: These are the same naming surface as `Rule.desc`; splitting them into separate compatibility slices would preserve stale public wording without product value in alpha.
