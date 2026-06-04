# vs-shipped Audit: `fg.meta.capabilities()` Read-Only Introspection

Status: complete
Date: 2026-06-04
Branch: `v0.2.0-impl-query-style-head-2026-06-03`
Class: tiny additive feature (per [`workflow/CADENCE.md`](../../CADENCE.md) Scope-and-Applicability) — no blueprint pair
Trigger: human request for runtime enumeration introspection of SDK-accepted value-kinds / scalar tags / cardinalities

## 1. Purpose

Add a small read-only `fg.meta.capabilities()` method that mirrors shipped enumeration constants so callers can programmatically discover which values the runtime accepts at API boundaries.

Scope intentionally limited to **shipped-truth keys only**: the human-proposed shape additionally included `constraint_kinds` (`requires`/`excludes`/`range`) and `predicate_id_pattern` (regex), neither of which is implemented in shipped code. Both were dropped from the report to avoid the report becoming a design commitment.

## 2. Shipped-truth verification (pre-implementation)

| Reported key | Shipped source | Audited values |
|---|---|---|
| `value_kinds` | `application/schema_runtime.py:34` + `application/protocol/entity_read.py:38` (`Literal["scalar", "entity_ref"]`) | `{"scalar", "entity_ref"}` |
| `scalar_tags` | `core/protocol/tup_v1.py:14-23` `CANONICAL_TAGS` minus the `entity_ref` tag (which is reported via `value_kinds`) | `{"string", "int", "float64", "bool", "bytes", "time", "uuid"}` |
| `cardinalities` | `application/schema_runtime.py:35` + `application/protocol/entity_read.py:39` (`Literal["single", "multi"]`) | `{"single", "multi"}` |

Dropped keys (no shipped backing):

| Dropped key | Reason |
|---|---|
| `field_types` (human proposal: `{int, float, string, enum, bool, ref}`) | Conflates `value_kind` and primitive tag namespaces; values don't match either (e.g. no `enum`, `float` is `float64`, `ref` is `entity_ref`). Split into `value_kinds` + `scalar_tags`. |
| `constraint_kinds` (human proposal: `{requires, excludes, range}`) | No constraint-system implementation in shipped code (`grep` across `sdk/dsl`, `application` returns only `RuleJoinConstraint`, a different concept). Including this would commit to future API surface without a design. |
| `predicate_id_pattern` (human proposal: `r"[a-z][a-z0-9_]*"`) | No regex validator on `pred_id` in shipped code; predicates are only validated as non-empty strings. The proposed pattern is aspirational. |

## 3. Fix scope

**Application layer** (new file):
- `src/factgraph/application/capabilities.py` (~45 lines) — module-private `_VALUE_KINDS` / `_SCALAR_TAGS` / `_CARDINALITIES` frozensets + `compute_capabilities()` returning `MappingProxyType` of the three. Comments cite shipped constant sources.

**SDK shell** (changes in `src/factgraph/sdk/store.py`):
- New `_SDKMetaManager` class (~17 lines) — read-only namespace, frozen `__setattr__`, `capabilities()` delegates to application-layer function via lazy import (preserves SDK module import cost)
- `__init__` adds `self._meta_manager = _SDKMetaManager(self)`
- New `@property def meta(self)` returning the manager (kept distinct from `package` per alphabetic placement)

Total SDK shell delta: +25 lines, no breaking change.

**Tests** (new file, +52 lines):
- `tests/sdk/test_meta_capabilities.py` `FgMetaCapabilitiesTests`:
  - `test_fg_has_meta_namespace_with_capabilities` — fg.meta + capabilities() exist; key set is `{value_kinds, scalar_tags, cardinalities}`
  - `test_capabilities_values_match_shipped_constants` — each value matches the shipped constants (with `scalar_tags` derived from `CANONICAL_TAGS - {entity_ref}` for cross-source verification)
  - `test_capabilities_result_is_immutable` — outer is `MappingProxyType`, all values are `frozenset`
  - `test_fg_meta_is_read_only` — assignment raises `FrozenSnapshotError`
  - `test_application_layer_compute_capabilities_matches_sdk_shell` — application-layer function and SDK shell return identical content

## 4. Verification

```
PYTHONPATH=src python -m pytest tests/sdk tests/application/protocol
→ 252 passed in 0.47s (5 new FgMetaCapabilitiesTests pass; 247 prior tests no regression)
```

## 5. Why no blueprint pair

- Pure additive read-only namespace; mirrors three already-shipped constants
- Application layer is a 3-frozenset declarative module + 1 function
- SDK shell mirrors the existing `_SDKAuditManager` / `_SDKPackageManager` pattern verbatim
- No protocol shape change, no DTO addition that would propagate elsewhere
- Test coverage in same commit batch

Falls under "tiny additive" exemption. Recorded here so the addition is discoverable + the dropped-key rationale is preserved.

## 6. Application-first compliance

Per [[project_application_first_runtime_authority]]: every new runtime capability lands as application-layer DTO + pure function first; SDK is the ergonomic shell with no substrate.

- ✓ `factgraph.application.capabilities.compute_capabilities()` is the application-layer source of truth
- ✓ `_SDKMetaManager.capabilities()` is a thin shell calling the application function
- ✓ Cross-layer parity is asserted by `test_application_layer_compute_capabilities_matches_sdk_shell`

## 7. Follow-ups (out of scope here)

- If `constraint_kinds` (or similar declarative constraints on field/predicate semantics) ever ship, capabilities() should be extended to include them — but only **after** the underlying validator/enforcement exists.
- If `predicate_id_pattern` ever becomes a real shipped regex (e.g. for normalized predicate id v2), capabilities() can extend.
- Both extensions go through a blueprint (introduce new validator surface, not "tiny additive").
