# Audit Log: S0 — Rule.repr Alias Migration

- Blueprint: [2026-06-08_explain-layer-s0-rule-repr.md](./2026-06-08_explain-layer-s0-rule-repr.md)
- Status: draft

---

## Event Log

| Date | Event | Notes |
|---|---|---|
| 2026-06-08 | blueprint created (draft) | Preflight source-read of `rule.py` (629 lines) + blast-radius grep complete. 17 shipped symbols catalogued. 3 scope questions Q-S0-A/B/C identified, must resolve before `scoped`. |

---

## Decision Notes

### D-1: Frozen dataclass deprecated alias pattern
**Decision**: `desc` stays as a real (but metadata-excluded) dataclass field rather than a `@property`, because `@property` cannot intercept dataclass `__init__` kwargs. The `compare=False, hash=False, repr=False` exclusions ensure deprecated field has zero impact on identity/equality semantics.

**Rationale**: Only approach that allows `Rule(desc=...)` constructor call to continue working while being intercepted in `__post_init__` for migration + warning.

### D-2: `content_digest` stability
**Decision**: `content_digest` hashes only `ports` and `when` (verified at `rule.py:108-113`). Adding/renaming `repr`/`desc` does NOT affect digest values. No digest migration needed.

**Rationale**: Verified from shipped source — payload dict keys are `"ports"` and `"when"` only.

### D-3: Pending — Q-S0-A/B/C scope resolution
**Status**: Open. Three items require user confirmation before status can advance to `scoped`:
- **Q-S0-A**: `evaluate_result.py:965` `"desc_template"` wire key — in S0 or defer?
- **Q-S0-B**: `OccurrenceInspect.desc_template` public DTO field — in S0 (with deprecated alias) or separate slice?
- **Q-S0-C**: `service/runtime_v1.py:2498` `"desc"` service response key — in S0 or defer?
