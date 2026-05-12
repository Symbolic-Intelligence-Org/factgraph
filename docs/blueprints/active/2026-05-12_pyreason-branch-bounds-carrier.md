# Task Blueprint: Track 3-post PyReason Branch Bounds Carrier

- Status: draft
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/kernel/sdk/semantics.py`
  - `src/kernel/sdk/store.py`
  - `src/kernel/adapters/pyreason/rule_ext.py`
  - `src/kernel/adapters/pyreason/where_compile.py`
  - `src/kernel/adapters/pyreason/engine_eval.py`
  - `src/kernel/tests/test_public_semantics_api_redesign.py`
  - `src/kernel/tests/test_pyreason_where_compile.py`
  - `src/kernel/tests/test_pyreason_engine_eval.py`
- Related Docs:
  - [docs/references/working/design-points/post-track3-semantics-public-api.zh.md](../../references/working/design-points/post-track3-semantics-public-api.zh.md)
  - [docs/blueprints/archive/2026-05-12_public-semantics-api-redesign.md](../archive/2026-05-12_public-semantics-api-redesign.md)
  - [docs/blueprints/archive/2026-05-12_branch-identity-rule-inspect.md](../archive/2026-05-12_branch-identity-rule-inspect.md)
  - [docs/blueprints/archive/2026-05-12_pyreason-semantics-profile-migration.md](../archive/2026-05-12_pyreason-semantics-profile-migration.md)
- Audit Log:
  - [2026-05-12_pyreason-branch-bounds-carrier.audit.md](./2026-05-12_pyreason-branch-bounds-carrier.audit.md)

## 1. Problem

Track 1 added stable inspect-time branch identity. Track 2 added public
`PyReasonSemantics(...)`, but intentionally omitted `branch_bounds` because
the PyReason adapter had no per-branch head-bound carrier.

That leaves one remaining post-Track-3 gap:

```python
fg.eval.evaluate(
    deriv,
    semantics=PyReasonSemantics(
        branch_bounds={
            "sensor_path": [0.8, 1.0],
            "obstacle_path": [0.2, 0.8],
        },
    ),
)
```

The user-facing shape is now clear, but the internal carrier and compiler
flow still need to be decided and implemented.

## 2. Goals

- Add the missing PyReason per-branch head-bound lane behind
  `PyReasonSemantics.branch_bounds`.
- Preserve Track 1's branch identity boundary: branch ids resolve only at the
  SDK object boundary, while SDK `Rule` / `Derivation` objects are still in hand.
- Preserve Track 2's wrapper-to-canonical lowering pattern.
- Preserve Track 3's adapter-time validation pattern.
- Compile per-branch PyReason head annotations without changing public
  `Rule` / `Derivation` structure.
- Keep `SemanticsProfile` and service / compiled paths canonical.

## 3. Non-goals

- Do not add service JSON support for wrapper-shaped `PyReasonSemantics`.
- Do not add branch ids to authoring payloads, compiled plans, registries, or adapters.
- Do not add atom-level public PyReason bounds.
- Do not add multi-head support; public derivations remain single-head.
- Do not change ProbLog semantics or `ProbLogSemantics`.
- Do not redesign `temporal_projection` or multi-interval validity.

## 4. Source Audit

### 4.1 Track 2 wrapper shape

`src/kernel/sdk/semantics.py` currently defines:

```python
@dataclass(frozen=True)
class PyReasonSemantics:
    timestep_delay: int = 0
    head_bound: tuple[float, float] | None = None
    temporal_projection: dict[str, Any] = field(default_factory=lambda: {"mode": "none"})
    uncertainty_projection: dict[str, Any] = field(default_factory=dict)
    name: str | None = None
    fallback: str = "reject_unconfigured"
```

There is no `branch_bounds` field. Track 2 G1 explicitly locks this as a
rejection guard:

```python
_pyreason_semantics_class()(branch_bounds={"sensor_path": [0.7, 0.9]})
```

The Track 3-post slice must intentionally update or replace that guard.

### 4.2 Track 2 SDK lowering boundary

`src/kernel/sdk/store.py` lowers public wrappers into `SemanticsProfile` at
the SDK boundary:

- `_preview_public_semantics(...)` previews wrappers without a derivation object.
- `_lower_public_semantics(...)` lowers wrappers when an SDK `Derivation` is
  available.
- `_branch_id_index_for_derivation(...)` maps explicit branch ids and fallback
  `b0` / `b1` ids to branch indexes using Track 1 inspect helpers.

`ProbLogSemantics` already uses this path:

```python
branch_index = branch_indexes.get(branch_id)
target = f"branch:{branch_index}"
```

Implication: `PyReasonSemantics.branch_bounds` can use the same SDK-local
resolution model and lower to positional/canonical profile entries.

### 4.3 PyReason adapter carrier today

`src/kernel/adapters/pyreason/rule_ext.py` defines:

```python
@dataclass(frozen=True)
class PyReasonRuleExt(EngineExtBase):
    timestep_delay: int = 0
    body_predicate_bounds: dict[str, tuple[float, float] | list[float]] = field(default_factory=dict)
    head_bound: tuple[float, float] | list[float] | None = None
```

There is no per-branch head-bound carrier. `head_bound` is global across all
compiled branches. `body_predicate_bounds` is keyed by predicate id, not by
branch id.

Implication: Track 3-post needs a new internal carrier field, likely one of:

- `branch_head_bounds: dict[int, tuple[float, float]]`
- `branch_head_bounds: dict[str, tuple[float, float]]`
- `branch_head_bounds: list[tuple[float, float] | None]`

### 4.4 PyReason compiler is already branch-aware

`src/kernel/adapters/pyreason/where_compile.py` already compiles one PyReason
rule per OR branch:

```python
rule_name = base_name if len(branches) == 1 else f"{base_name}_b{branch_idx}"
```

Existing test coverage confirms:

```python
[
    ("popular(e) <-0 name(e)", "derived_popular_b0"),
    ("popular(e) <-0 tag(e)", "derived_popular_b1"),
]
```

Implication: per-branch head annotation is mechanically available by choosing
the head bound per `branch_idx` before `_compile_single_branch(...)`.

### 4.5 Existing global head bound path

`where_compile.py` currently resolves one global head bound:

```python
head_bound = _resolve_head_bound(engine_ext)
...
head_bound=head_bound
```

`_compile_single_branch(...)` appends the head annotation:

```python
head_str = f"{_pred_short_name(target_pred_id)}({', '.join(head_terms)})"
if head_bound is not None:
    lo, hi = head_bound
    head_str = f"{head_str} : [{lo}, {hi}]"
```

Implication: the minimal implementation is to keep global `head_bound` and add
an optional branch-specific override map. The compiler chooses:

```text
branch_head_bounds[branch_idx] if present else head_bound
```

### 4.6 Profile consumption path

Track 3 / D added `SemanticsProfile.rule_projection.pyreason` consumption:

- `target="head:0", kind="interval"` maps to global `head_bound`.
- `target="rule", kind="timestep_delay"` maps to `timestep_delay`.
- `target="body_atom:{branch}:{atom}", kind="interval_threshold"` maps to
  `body_predicate_bounds`.

There is no existing `target="branch:{index}"` PyReason entry. Track 3-post
must decide whether public wrapper lowering should:

- use a new canonical profile target such as `branch:{index}`;
- bypass profile entries and lower directly to internal `PyReasonRuleExt`; or
- add an SDK-only lowering side channel.

The existing Track 2 architecture favors wrapper -> canonical
`SemanticsProfile` -> adapter-local bridge. Deviating from that should require
an explicit G0 decision.

## 5. Open Design Questions

### 5.1 Q1: Public `branch_bounds` shape

Options:

- **P1a** `PyReasonSemantics(branch_bounds={"sensor_path": [0.8, 1.0]})`
- **P1b** `branch_head_bounds={...}` to mirror the internal carrier name
- **P1c** keep no public field and require advanced `SemanticsProfile`

Recommendation: **P1a**. The public concept is branch-level semantics, and the
post-Track-3 design point already uses `branch_bounds`.

### 5.2 Q2: Public key namespace

Options:

- **P2a** accept explicit branch ids and fallback `b0` / `b1`, same as
  `ProbLogSemantics.branch_probabilities`
- **P2b** accept explicit branch ids only
- **P2c** accept positional integers only

Recommendation: **P2a**. It preserves Track 2 symmetry and allows users to
adopt the feature before naming every branch, while docs can warn that
fallback ids are positional.

### 5.3 Q3: Internal carrier shape

Options:

- **P3a** `branch_head_bounds: dict[int, tuple[float, float]]`
- **P3b** `branch_head_bounds: dict[str, tuple[float, float]]`
- **P3c** `branch_head_bounds: list[tuple[float, float] | None]`

Recommendation: **P3a**. SDK branch ids should not leak past the SDK boundary.
The compiler already iterates by `branch_idx`, so index-keyed carrier is the
minimal adapter shape.

### 5.4 Q4: Canonical profile target

Options:

- **P4a** add `target="branch:{index}", kind="interval"` in
  `rule_projection.pyreason`
- **P4b** add `target="branch_head:{index}", kind="interval"`
- **P4c** bypass `SemanticsProfile` and lower wrappers directly to
  `PyReasonRuleExt`

Recommendation: **P4a**. It mirrors ProbLog's branch target and keeps
wrapper -> profile -> adapter lowering intact. The engine bucket
(`rule_projection.pyreason`) disambiguates the meaning from ProbLog.

### 5.5 Q5: Conflict rule with global `head_bound`

Options:

- **P5a** branch-specific bounds override global `head_bound` for those
  branches; no conflict
- **P5b** branch-specific bounds conflict with any global `head_bound`
- **P5c** branch-specific bounds must equal global `head_bound` when both present

Recommendation: **P5a**. This makes `head_bound` a default and
`branch_bounds` an override, matching the design point's intended public
shape.

### 5.6 Q6: Branch count validation

Options:

- **P6a** adapter validates `branch:{index}` range against `where` branch count
- **P6b** SDK-only validation is enough

Recommendation: **P6a**. `SemanticsProfile` remains advanced/canonical and can
be constructed directly, so adapter consumption must validate indexes with
rule context.

### 5.7 Q7: Single-branch behavior

Options:

- **P7a** allow `branch_bounds={"b0": ...}` for single-branch derivations
- **P7b** reject branch-specific bounds unless there are at least two branches

Recommendation: **P7a**. Single-branch still has a branch index and fallback
id. Rejecting it would create an unnecessary special case.

### 5.8 Q8: Service and compiled paths

Options:

- **P8a** keep Track 2 boundary: service wrapper JSON and compiled wrapper
  semantics still reject; canonical `SemanticsProfile` may carry the new
  `rule_projection.pyreason` branch target
- **P8b** add service wrapper-shaped JSON now

Recommendation: **P8a**. Branch id resolution still requires SDK objects.

### 5.9 Q9: Preservation guards

Track 3-post must preserve:

- `PyReasonSemantics` existing lowerable lanes.
- `SemanticsProfile` direct advanced/canonical path.
- ProbLog semantics and Track 2 engine auto-derivation.
- Track 1 branch inspect output and fallback ids.

### 5.10 Q10: Docs / memory update

G4 should update:

- Track 3-post blueprint archive.
- `post-track3-semantics-public-api.zh.md` from "future" to "landed" for
  branch bounds if implemented.
- `project_post_track3_semantics_api_direction.md`.
- A new `project_track3_post_pyreason_branch_bounds_implemented.md` memory.

## 6. Boundaries And Invariants

- Public `Branch` remains structural; it does not regain engine semantics.
- Branch ids remain SDK metadata and do not enter authoring payloads,
  compiled plans, registries, or adapters.
- SDK wrappers remain the preferred public shape; `SemanticsProfile` remains
  advanced/canonical.
- Adapter-specific validation remains at PyReason consumption time.
- Profile-derived values are not written into facts, registry state, or
  stored derivation metadata.
- `body_atom:{branch}:{atom}` remains advanced/canonical only; public
  `PyReasonSemantics` branch bounds are branch-level head interval overrides.

## 7. Acceptance

- [ ] G0 locks Q1-Q10 and records decisions in the audit.
- [ ] G1 red baseline covers public `branch_bounds`, branch-id resolution,
  carrier validation, compiler output, and preservation guards.
- [ ] `PyReasonSemantics(branch_bounds=...)` accepts explicit branch ids and
  fallback ids if G0 chooses P1a/P2a.
- [ ] Unknown branch ids reject at the SDK object boundary.
- [ ] Lowered canonical `SemanticsProfile` carries PyReason branch targets if
  G0 chooses P4a/P4b.
- [ ] Direct `SemanticsProfile.rule_projection.pyreason` branch targets are
  validated at adapter consumption time.
- [ ] `PyReasonRuleExt` carries branch-specific head bounds without leaking
  SDK branch ids.
- [ ] `where_compile.py` emits per-branch head annotations.
- [ ] Global `head_bound` existing behavior remains green.
- [ ] ProbLog / Track 2 wrapper behavior remains green.
- [ ] Service and compiled wrapper boundaries remain green.
- [ ] Release-facing docs document `branch_bounds` as current behavior after
  implementation.

## 8. Implementation Plan

1. G0: freeze public field name, key namespace, internal carrier shape,
   canonical profile target, conflict rules, and service/compiled boundary.
2. G1: add forward-failing tests for public wrapper, profile consumption,
   compiler output, and preservation guards.
3. G2: implement wrapper field, SDK lowering, adapter carrier, profile
   materialization, and compiler branch-bound selection.
4. G3: sync SDK / adapter / core semantics docs and update the working design
   point from future to current for landed branch-bound parts.
5. G4: fill outcome/deviations, archive blueprint pair, and prepare publish.

## 9. Docs To Update

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/adapters/docs/03_pyreason_adapter.md`
- `src/kernel/core/semantics/docs/README.md`
- `docs/references/working/design-points/post-track3-semantics-public-api.zh.md`

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
