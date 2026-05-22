# Task Blueprint: Track 3-post PyReason Branch Bounds Carrier

- Status: implemented
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

## 5. Scope Freeze Decisions

G0 locks Track 3-post as the final, bounded PyReason branch-bound slice.
It adds the public `PyReasonSemantics.branch_bounds` lane and the internal
carrier / compiler support needed to make it real. It does not broaden
service, compiled, atom-level, or multi-head semantics.

### 5.1 D1: Public `branch_bounds` shape

Options:

- **P1a** `PyReasonSemantics(branch_bounds={"sensor_path": [0.8, 1.0]})`
- **P1b** `branch_head_bounds={...}` to mirror the internal carrier name
- **P1c** keep no public field and require advanced `SemanticsProfile`

Locked: **P1a**. Add public
`PyReasonSemantics.branch_bounds: dict[str, tuple[float, float]] | None`.
The public concept is branch-level semantics, and the post-Track-3 design
point already uses `branch_bounds`.

### 5.2 D2: Public key namespace

Options:

- **P2a** accept explicit branch ids and fallback `b0` / `b1`, same as
  `ProbLogSemantics.branch_probabilities`
- **P2b** accept explicit branch ids only
- **P2c** accept positional integers only

Locked: **P2a**. Accept explicit branch ids and fallback `b0` / `b1`
ids, same as `ProbLogSemantics.branch_probabilities`. Docs should still
warn that fallback ids are positional.

### 5.3 D3: Internal carrier shape

Options:

- **P3a** `branch_head_bounds: dict[int, tuple[float, float]]`
- **P3b** `branch_head_bounds: dict[str, tuple[float, float]]`
- **P3c** `branch_head_bounds: list[tuple[float, float] | None]`

Locked: **P3a**. Add internal
`PyReasonRuleExt.branch_head_bounds: dict[int, tuple[float, float]]`.
SDK branch ids do not leak past the SDK boundary. The compiler already
iterates by `branch_idx`, so an index-keyed carrier is the minimal adapter
shape.

### 5.4 D4: Canonical profile target

Options:

- **P4a** add `target="branch:{index}", kind="interval"` in
  `rule_projection.pyreason`
- **P4b** add `target="branch_head:{index}", kind="interval"`
- **P4c** bypass `SemanticsProfile` and lower wrappers directly to
  `PyReasonRuleExt`

Locked: **P4a**. Add `target="branch:{index}", kind="interval"` in the
`rule_projection.pyreason` bucket. It mirrors ProbLog's branch target and
keeps wrapper -> profile -> adapter lowering intact. The engine bucket
disambiguates the meaning from ProbLog.

### 5.5 D5: Conflict rule with global `head_bound`

Options:

- **P5a** branch-specific bounds override global `head_bound` for those
  branches; no conflict
- **P5b** branch-specific bounds conflict with any global `head_bound`
- **P5c** branch-specific bounds must equal global `head_bound` when both present

Locked: **P5a**. Branch-specific bounds override global `head_bound` for
those branches. Global `head_bound` is the default; `branch_bounds` is the
branch-level override.

### 5.6 D6: Branch count validation

Options:

- **P6a** adapter validates `branch:{index}` range against `where` branch count
- **P6b** SDK-only validation is enough

Locked: **P6a**. Adapter consumption validates `branch:{index}` range against
the rule's branch count. `SemanticsProfile` remains advanced/canonical and
can be constructed directly, so SDK-only validation is insufficient.

### 5.7 D7: Single-branch behavior

Options:

- **P7a** allow `branch_bounds={"b0": ...}` for single-branch derivations
- **P7b** reject branch-specific bounds unless there are at least two branches

Locked: **P7a**. Single-branch derivations allow
`branch_bounds={"b0": ...}`. Single-branch still has a branch index and
fallback id.

### 5.8 D8: Service and compiled paths

Options:

- **P8a** keep Track 2 boundary: service wrapper JSON and compiled wrapper
  semantics still reject; canonical `SemanticsProfile` may carry the new
  `rule_projection.pyreason` branch target
- **P8b** add service wrapper-shaped JSON now

Locked: **P8a**. Service wrapper JSON and compiled wrapper semantics still
reject. Canonical `SemanticsProfile` may carry the new
`rule_projection.pyreason` branch target. Branch id resolution still
requires SDK objects.

### 5.9 D9: Wrapper-lowered profile equivalence

Locked: `PyReasonSemantics(branch_bounds={"sensor_path": [0.8, 1.0]})`
lowered against a derivation where `sensor_path -> branch:0` must produce
the same canonical profile shape as direct construction:

```python
SemanticsProfile(
    engine="pyreason",
    rule_projection={"pyreason": [
        {"target": "branch:0", "kind": "interval", "value": [0.8, 1.0]},
    ]},
)
```

This ensures `fg.eval.inspect_semantics(wrapper)` and an equivalent
direct `SemanticsProfile` preview the same projection lane.

### 5.10 D10: Anchored rejection text contracts

G1 tests should lock stable substrings:

- unknown SDK branch id:
  `"branch_bounds contains unknown branch id 'X'"`
- direct profile branch index range:
  `"rule_projection.pyreason[N] branch index out of range"`
- invalid branch-bound value:
  `"branch_bounds[...] value must be [lower, upper]"`
- Track 2's old constructor-level `branch_bounds` rejection guard is
  inverted to a positive acceptance test.

### 5.11 D11: Empty `branch_bounds`

Locked: `PyReasonSemantics(branch_bounds={})` is equivalent to omitting
`branch_bounds`. Empty dict means no branch-specific overrides.

### 5.12 D12: Preservation guards

Track 3-post must preserve:

- `PyReasonSemantics` existing lowerable lanes.
- `SemanticsProfile` direct advanced/canonical path.
- ProbLog semantics and Track 2 engine auto-derivation.
- Track 1 branch inspect output and fallback ids.

### 5.13 D13: Track 2 guard inversion

Locked: Track 2 G1's
`test_pyreason_semantics_rejects_branch_bounds_until_track3_post` guard is
inverted to a positive Track 3-post acceptance test. This mirrors the
earlier B -> C and C -> D guard-evolution pattern.

### 5.14 D14: Docs / memory update

G4 should update:

- Track 3-post blueprint archive.
- `post-track3-semantics-public-api.zh.md` from "future" to "landed" for
  branch bounds if implemented.
- `project_post_track3_semantics_api_direction.md`.
- A new `project_track3_post_pyreason_branch_bounds_implemented.md` memory.

### 5.15 Consolidated D-decision table

| ID | Decision |
|---|---|
| D1 | Add public `PyReasonSemantics.branch_bounds`. |
| D2 | Accept explicit branch ids and fallback `b0` / `b1` ids. |
| D3 | Add internal `PyReasonRuleExt.branch_head_bounds: dict[int, tuple]`. |
| D4 | Lower to canonical `rule_projection.pyreason` target `branch:{index}`, `kind="interval"`. |
| D5 | Branch-specific bounds override global `head_bound` per branch. |
| D6 | Adapter validates branch index range with rule context. |
| D7 | Single-branch derivations allow `branch_bounds={"b0": ...}`. |
| D8 | Service/compiled wrapper boundaries remain Track 2 canonical-only. |
| D9 | Wrapper-lowered profile shape equals direct canonical `SemanticsProfile` shape. |
| D10 | Rejection text anchors locked for G1. |
| D11 | Empty `branch_bounds={}` is no-op / no override. |
| D12 | Preservation invariants locked. |
| D13 | Track 2 branch_bounds rejection guard inverted to positive. |
| D14 | G4 updates docs and memory to mark Track 3-post complete. |

### 5.16 Resolved G0 Questions Map

| Draft / reviewer question | Locked D |
|---|---|
| Q1 public field name | D1 |
| Q2 public branch-key namespace | D2 |
| Q3 internal carrier shape | D3 |
| Q4 canonical profile target | D4 |
| Q5 global vs branch-bound conflict rule | D5 |
| Q6 branch count validation | D6 |
| Q7 single-branch behavior | D7 |
| Q8 service/compiled boundary | D8 |
| Reviewer Q11 wrapper-lowered profile equivalence | D9 |
| Reviewer Q12 anchored rejection text | D10 |
| Reviewer Q13 empty branch_bounds | D11 |
| Q9 preservation guards | D12 |
| Guard evolution | D13 |
| Q10 docs / memory | D14 |

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
- `head_bound` remains a global default for all branches unless overridden by
  branch-specific `branch_bounds`.
- `branch_head_bounds` is internal and index-keyed; SDK branch id strings do
  not cross the SDK/core boundary.

## 7. Acceptance

- [x] G0 locks Q1-Q13 and records decisions in the audit.
- [x] G1 red baseline covers public `branch_bounds`, branch-id resolution,
  carrier validation, compiler output, and preservation guards.
- [x] `PyReasonSemantics(branch_bounds=...)` accepts explicit branch ids and
  fallback ids.
- [x] `PyReasonSemantics(branch_bounds={})` is equivalent to omitting it.
- [x] Unknown branch ids reject at the SDK object boundary.
- [x] Lowered canonical `SemanticsProfile` carries PyReason
  `target="branch:{index}", kind="interval"` entries.
- [x] Wrapper lowering and direct `SemanticsProfile` construction are
  equivalent for the canonical branch target shape.
- [x] Direct `SemanticsProfile.rule_projection.pyreason` branch targets are
  validated at adapter consumption time.
- [x] `PyReasonRuleExt` carries branch-specific head bounds without leaking
  SDK branch ids.
- [x] `where_compile.py` emits per-branch head annotations.
- [x] Branch-specific bounds override global `head_bound` for the specified
  branch and leave other branches on the global default.
- [x] Single-branch derivations support fallback `b0`.
- [x] Global `head_bound` existing behavior remains green.
- [x] ProbLog / Track 2 wrapper behavior remains green.
- [x] Service and compiled wrapper boundaries remain green.
- [x] Track 2 branch_bounds rejection guard is inverted to positive.
- [x] Release-facing docs document `branch_bounds` as current behavior after
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

### 10.1 Final Landed Behavior

1. `kernel.sdk.PyReasonSemantics` now accepts
   `branch_bounds={branch_id: [lower, upper]}`.
2. `branch_bounds` keys may be explicit `Branch(id=...)` values or fallback
   positional ids such as `b0` / `b1`.
3. Empty `branch_bounds={}` is a no-op and behaves like omitting
   branch-specific overrides.
4. SDK lowering resolves branch ids while the SDK `Derivation` object is
   still available.
5. Public branch ids lower to canonical `SemanticsProfile.rule_projection.pyreason`
   entries with `target="branch:{index}", kind="interval"`.
6. Direct canonical `SemanticsProfile` users may provide the same branch
   target shape without using the SDK wrapper.
7. PyReason adapter consumption materializes branch entries into
   `PyReasonRuleExt.branch_head_bounds`.
8. `branch_head_bounds` is index-keyed and adapter-internal; SDK branch id
   strings do not cross the SDK/core boundary.
9. Branch-specific head bounds override global `head_bound` for that branch.
10. Branches without a branch-specific override keep the global `head_bound`.
11. Single-branch derivations support `branch_bounds={"b0": ...}`.
12. Service and compiled evaluation preserve Track 2's canonical-only
    boundary for public wrappers.
13. Existing PyReason lanes (`head_bound`, `timestep_delay`, temporal
    projection, body atom advanced profile entries) remain supported.
14. ProbLog semantics, Track 1 branch inspect, Track 2 wrapper behavior, and
    Track 3 C/D/E call-site behavior remain green.

### 10.2 Validation

- G1 baseline: Track 3-post suite introduced 16 forward/guard tests with
  expected 11 errors, 4 failures, and 1 guard pass; Track 2 carried one
  expected error from the inverted `branch_bounds` guard.
- G2 implementation:
  - Track 3-post suite: 16/16 OK.
  - Track 2 public semantics suite: 17/17 OK.
  - Track 1+B/C/D/E preservation suite: 103/103 OK.
  - PyReason regression with `kernel.application` primer: 71/71 OK.
- G3 docs sync:
  - Track 3-post + Track 2 combined: 33/33 OK.
  - Track 1+B/C/D/E preservation suite: 103/103 OK.
  - `git diff --check` clean.
  - Grep gates clean: stale Track 3-post future/deferred wording absent from
    current docs; `branch_bounds` current teaching present; `branch_head_bounds`
    classified as adapter/internal.

### 10.3 Commit Lineage

```text
c33bb07d docs(pyreason): document branch bounds carrier
90f126c5 feat(pyreason): add branch bounds carrier
35a3ed99 test(pyreason): add branch bounds carrier baseline
c96905e5 docs(blueprints): scope pyreason branch bounds carrier
c7b2aab7 docs(blueprints): draft pyreason branch bounds carrier
```

The G4 archive commit closes the lineage and is not included above.

### 10.4 Deviations

1. G2 stayed smaller than projected. The final production change was about
   125 net lines because Track 1 branch identity, Track 2 wrapper lowering,
   and Track 3 / D PyReason profile consumption already provided the needed
   substrate.
2. The implementation normalized `PyReasonRuleExt.branch_head_bounds` in
   `__post_init__` so list inputs become tuple pairs on the frozen carrier.
   This is stricter than the minimum G1 expectation and keeps direct carrier
   construction consistent with SDK wrapper normalization.
3. G3 updated the post-Track-3 working design point more extensively than
   ordinary release docs because this slice completes the final planned
   step in that design note.

### 10.5 Archive Notes

Track 3-post completes the 3-track post-Track-3 plan:

- Track 1 added stable branch identity, rule inspection, and the single-head
  public derivation cut.
- Track 2 added ergonomic public `ProbLogSemantics` / `PyReasonSemantics`
  wrappers plus engine auto-derivation.
- Track 3-post added the missing PyReason branch-level head-bound carrier,
  carrying `PyReasonSemantics.branch_bounds` through canonical profile
  lowering, adapter-local normalization, and per-branch compiled rule head
  annotations.

The resulting architecture is now coherent end to end:

```text
Branch(id="sensor_path")
  -> PyReasonSemantics(branch_bounds={"sensor_path": [0.8, 1.0]})
  -> SemanticsProfile.rule_projection.pyreason target="branch:0"
  -> PyReasonRuleExt.branch_head_bounds[0]
  -> derived_rule_b0 head annotation : [0.8, 1.0]
```

The post-Track-3 sequential plan is complete. Remaining future work is no
longer dependency-ordered:

- shell profile flow for Check / Diagnose / Fact Overlay / Why-not;
- multi-interval validity / recurrence data contracts;
- release packaging for the next rc candidate after `v0.1.0-rc.1`;
- optional public atom-level PyReason bounds if a concrete user need appears.
