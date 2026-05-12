# Task Blueprint: Branch Identity, Rule Inspect, And Single-Head Cleanup

- Status: scoped
- Created: 2026-05-12
- Last Updated: 2026-05-12
- Related Modules:
  - `src/kernel/sdk/dsl/branch.py`
  - `src/kernel/sdk/dsl/rule.py`
  - `src/kernel/sdk/dsl/expr.py`
  - `src/kernel/sdk/store.py`
  - `src/kernel/authoring/rule_compile.py`
  - `src/kernel/authoring/rule_dsl_parse.py`
  - `src/kernel/core/rules/rule_ir.py`
  - `src/kernel/application/protocol/derivation.py`
  - `src/kernel/application/derivation_runtime.py`
- Related Docs:
  - [docs/references/working/design-points/post-track3-semantics-public-api.zh.md](../../references/working/design-points/post-track3-semantics-public-api.zh.md)
  - [docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md](../../references/working/design-points/rule-policy-function-tree-and-syntax.zh.md)
  - [docs/blueprints/archive/2026-05-11_branch-confidence-decomposition.md](../archive/2026-05-11_branch-confidence-decomposition.md)
  - [docs/blueprints/archive/2026-05-12_semantics-callsite-integration.md](../archive/2026-05-12_semantics-callsite-integration.md)
  - [docs/blueprints/archive/2026-05-12_pyreason-semantics-profile-migration.md](../archive/2026-05-12_pyreason-semantics-profile-migration.md)
- Audit Log:
  - [2026-05-12_branch-identity-rule-inspect.audit.md](./2026-05-12_branch-identity-rule-inspect.audit.md)

## 1. Problem

Track 3 completed the engine-semantics migration:

- public runtime calls use `engine=` and optional `semantics=`;
- core/application internals use `mode=` and `semantics_profile`;
- ProbLog and PyReason consume profiles at adapter time;
- `Rule` and `Derivation` remain logical business templates.

The next public-semantics simplification needs stable branch references. Today `Branch` has no user-visible identity, no rule inspection API exposes branch structure, and public multi-head derivations are still documented as accepted by `register_derivation(...)` / `fg.eval.evaluate(...)` even though capability shells already require single-head plans.

This creates three design gaps:

1. Future engine-specific public semantics such as `ProbLogSemantics(branch_probabilities={...})` and `PyReasonSemantics(branch_bounds={...})` need stable branch names.
2. Users need a way to inspect a rule/derivation and discover the branch ids or fallback positions they can reference.
3. PyReason branch-bound semantics are simpler if public derivations have one head; current public multi-head support complicates `head_bound` / branch-bound shape.

## 2. Goals

- Add a scoped design for branch identity on public `Branch(...)` objects without reintroducing engine semantics onto branches.
- Define a public rule/derivation inspection surface that exposes normalized branch identity and structure.
- Decide whether Track 1 hard-cuts public multi-head `Derivation` support and where that cut lives.
- Preserve Track 3's public/internal engine-semantics boundary: no `confidence`, `probability`, `engine_ext`, or adapter-specific values on `Branch`.
- Provide the branch-id substrate needed by a later public `*Semantics` API redesign.

## 3. Non-goals

- Do not redesign `SemanticsProfile` in this slice.
- Do not introduce `ProbLogSemantics`, `PyReasonSemantics`, or engine inference from semantics object type.
- Do not change ProbLog or PyReason adapter consumption behavior.
- Do not implement PyReason branch-level head-bound carriers yet.
- Do not introduce multi-interval validity support.
- Do not change release refs or milestone refs.

## 4. Current Context

### 4.1 Branch Has No Identity

Current public `Branch` is a frozen dataclass with one field:

```python
@dataclass(frozen=True)
class Branch:
    atoms: list[Any]
```

It validates only that `atoms` is a non-empty list and defensively copies the list. There is no `id`, `name`, or `version`.

### 4.2 Lowering Erases Branch Wrapper Metadata

The SDK lowering path normalizes `Branch(...)` into raw branch atom lists:

- `src/kernel/sdk/dsl/expr.py` unwraps `Branch.atoms` in `lower_where(...)`.
- `src/kernel/sdk/dsl/rule.py` serializes `Rule` / `Derivation` `where` through `lower_where(...)`.
- `src/kernel/sdk/store.py::_normalize_where_branch_wrappers(...)` returns only `list(branch.atoms)`.
- `src/kernel/authoring/rule_dsl_parse.py::_where_branch_call(...)` returns a marker plus atom list, then `_normalize_where_with_branch_wrappers(...)` returns raw branch lists.

Any future branch identity must therefore either:

- be inspect-only and derived from SDK objects before lowering, or
- be explicitly carried through authoring payloads and compiled structures.

This is a G0 decision.

### 4.3 Existing Condition Keys Use Positional Branch/Atom Locators

`src/kernel/authoring/rule_compile.py::_collect_condition_keys(...)` currently accepts condition weight keys such as `b0.a0`, derived from positional branch/atom indexes. Older rule-replay references also mention existing `b{branch}.a{atom}` locators.

Any named-branch scheme needs a compatibility story with these positional locators.

### 4.4 Public Multi-Head Is A SDK Convenience, Not A Deep Authoring Primitive

`Derivation` accepts one or more heads in the SDK and serializes multiple heads as `head: [...]`. `src/kernel/sdk/store.py::_expand_authoring_derivation_heads(...)` then expands multi-head SDK payloads into separate authoring payloads before compile.

The authoring compiler itself expects a single head object, and capability shells already reject multi-head plans:

- Check rejects plans with `len(plan.heads) != 1`;
- Diagnose rejects multi-head plans;
- Fact Overlay rejects multi-head plans;
- Why-not rejects multi-head plans.

Release-facing SDK docs still teach multi-head as accepted by `register_derivation(...)` and `fg.eval.evaluate(...)`.

### 4.5 PyReason Already Compiles Branches As Separate Rules

`src/kernel/adapters/pyreason/where_compile.py` names per-branch compiled rules with a positional suffix:

```python
rule_name = base_name if len(branches) == 1 else f"{base_name}_b{branch_idx}"
```

This confirms that branch-level PyReason bounds can be implemented later by mapping public branch ids to the branch-specific compiled rule head annotation. This slice does not implement that mapping; it creates the public identity and inspect substrate.

### 4.6 No Public Rule Inspect Namespace Yet

The SDK has `fg.eval.inspect_semantics(profile)` after Track 3 / E. There is no corresponding public rule/derivation inspect API. The working design note recommends `fg.rules.inspect(rule_or_derivation)` because inspection is about rule structure, not evaluation.

The SDK store currently has namespace managers for `read`, `write`, `eval`, `what_if`, `audit`, and `package`, but no `rules` namespace.

## 5. Proposed Shape

G0 locks Track 1 as a narrow SDK-layer substrate slice:

1. Add branch identity as structural metadata only.
2. Add public `fg.rules.inspect(...)` to expose normalized rule/derivation shape.
3. Hard-cut public multi-head `Derivation` support at construction and SDK runtime boundaries, while preserving core/application internals as needed for compatibility and tests.
4. Keep branch metadata inspect-only in Track 1; no authoring payload, rule IR, compiled plan, registry, or adapter changes.

### 5.1 Branch Identity

Decision D1:

- `Branch([...], id="sensor_path")` is the public identity shape.
- `id` is optional and keyword-only.
- `Branch([...])` remains the positional default.
- `Branch(id="sensor_path", atoms=[...])` is not introduced in Track 1.
- UUID or random generated ids are rejected.

Decision D3:

- Branch id must match `^[A-Za-z_][A-Za-z0-9_]*$`.
- Branch id must be unique within one inspected `Rule` or `Derivation`.
- Branch id validation lives in SDK construction and inspect validation.
- Dotted or dashed ids are deferred until a real product need appears.

This preserves current `Branch([...])` syntax while giving future public semantics objects a readable key space.

### 5.2 Branch Id Fallback

Decision D2:

Unnamed branches inspect as positional ids `b0`, `b1`, ... to align with:

- existing `b{branch}.a{atom}` condition locators;
- PyReason compiled rule suffixes `_b{branch_idx}`;
- previous design-point notes.

The inspect output exposes both `id` and `fallback_id`:

- if a branch has an explicit id, `id` is the explicit id and `fallback_id` is positional;
- if a branch has no explicit id, `id == fallback_id`;
- `is_explicit_id` disambiguates the two cases.

Future public semantics may accept both explicit ids and fallback ids, but docs must warn that explicit ids are more durable than positional fallback ids.

### 5.3 Inspect API

Decision D4:

- add `fg.rules.inspect(rule_or_derivation)`;
- `rules` becomes a read-only SDK namespace manager;
- inspect supports both `Rule` and `Derivation` (D9);
- the API is pure and does not compile, evaluate, register, or mutate anything.

Locked return shape:

```python hl_lines="8 9 10 11 12 13 14"
{
    "kind": "Rule" | "Derivation",
    "id": "...",
    "version": "...",
    "heads": [...],
    "branches": [
        {
            "id": "sensor_path",          # explicit id or fallback id
            "fallback_id": "b0",          # always positional
            "is_explicit_id": True,
            "index": 0,
            "atom_count": 2,
            "atoms": [...],
            "atom_ids": ["b0.a0", "b0.a1"],
        },
    ],
}
```

`atoms` are normalized SDK-level / authoring-compatible atom payloads. Track 1 does not promise pretty display strings; those can be layered later.

### 5.4 Metadata Persistence

Decision D5:

- Track 1 chooses P1a: inspect-only metadata from SDK objects.
- No authoring payload field is added (D8).
- No rule IR field is added.
- No compiled plan field is added.
- No registry sidecar is added.
- No adapter receives branch ids.

This keeps Track 1 scoped to public SDK structure. Future public semantics objects can resolve explicit/fallback ids to positional branch indexes at the SDK boundary before constructing internal `SemanticsProfile` / adapter projection shapes.

### 5.5 Single-Head Cut

Decision D6:

- Track 1 uses H1a + H1b defense in depth.
- SDK public `Derivation` construction rejects multiple heads.
- SDK `register_derivation(...)`, `fg.eval.evaluate(...)`, and related public runtime entry points also reject multi-head if one reaches them.
- Core/application internals may retain tuple/list support where needed for existing internal structures and regression tests.
- Capability shells already reject multi-head and remain aligned.

This hard-cut removes documented-but-functionally-dead surface. It does not remove a capability currently usable by Check / Diagnose / Fact Overlay / Why-not.

### 5.6 Condition Weights And Authoring Payload

Decision D7:

- `condition_weights` keys stay positional (`b0.a0`, `b1.a2`, ...).
- Track 1 does not add id-based condition weight keys.
- This preserves A4's certainty/explain projection classification and avoids mixing branch identity with certainty-projection migration work.

Decision D8:

- Authoring payload remains unchanged.
- `Branch.id` is not serialized into authoring `where`.
- String DSL `Branch(...)` keywords remain unchanged unless a later slice explicitly updates that parser.

### 5.7 Relation To Future Public Semantics Objects

This slice should create the substrate for a later API such as:

```python
fg.eval.evaluate(
    derivation,
    semantics=PyReasonSemantics(
        branch_bounds={"sensor_path": [0.2, 0.8]},
        head_bound=[0.8, 1.0],
        timestep_delay=2,
    ),
)
```

That later slice may map `PyReasonSemantics` to current `SemanticsProfile` internally, but this blueprint does not introduce those objects.

### 5.8 Scope Freeze Decisions

| ID | Decision |
| --- | --- |
| D1 | Branch identity shape is `Branch([...], id="..." or None)`; `id` is optional and keyword-only. |
| D2 | Unnamed branches inspect with fallback id `b{branch_idx}`; inspect exposes `id`, `fallback_id`, and `is_explicit_id`. |
| D3 | Branch ids must be non-empty, unique within a `Rule` / `Derivation`, and match `^[A-Za-z_][A-Za-z0-9_]*$`. |
| D4 | Add public pure `fg.rules.inspect(rule_or_derivation)` with locked dict shape. |
| D5 | Branch metadata is inspect-only in Track 1; no authoring, IR, compiled plan, registry, or adapter propagation. |
| D6 | Public multi-head is hard-cut at SDK construction and public register/evaluate boundaries. |
| D7 | `condition_weights` keys remain positional; no id-based condition keys in Track 1. |
| D8 | Authoring payload is unchanged; no `branch_id` field is serialized. |
| D9 | Inspect supports both `Rule` and `Derivation`. |
| D10 | Public docs migrate from "multi-head accepted" to "single-head required". |

### 5.9 Resolved G0 Questions Map

| Draft question | Resolution |
| --- | --- |
| Branch identity API | D1 |
| Fallback id semantics | D2 |
| Branch id validation | D3 |
| Inspect namespace and return shape | D4 |
| Metadata persistence / lowering erasure | D5 + D8 |
| Single-head cut scope | D6 + D10 |
| Existing `condition_weights` positional keys | D7 |
| Rule support, not only Derivation | D9 |

## 6. Boundaries And Invariants

- `Branch` remains logical structure only; no probability, confidence, interval, bound, engine, or engine_ext fields.
- Branch identity must not change deterministic native/Souffle/ProbLog/PyReason evaluation results.
- Existing Track 3 `SemanticsProfile` behavior remains intact.
- Existing C/D adapter consumption remains intact.
- Public multi-head decision must not silently change capability shell semantics; those shells already reject multi-head.
- Branch metadata is not carried past SDK objects in Track 1.
- `condition_weights` remains positional and is not migrated to branch ids in Track 1.
- Authoring payloads stay unchanged.
- Documentation must clearly distinguish public `fg.rules.inspect(...)` from internal compile/runtime structures.

## 7. Acceptance

- [ ] G0 locks D1-D10 and records the scope-freeze audit row.
- [ ] G1 red baseline covers `Branch([...], id=...)` import/construction/validation and fails before implementation.
- [ ] G1 red baseline covers `fg.rules.inspect(...)` namespace/return shape for both `Rule` and `Derivation`.
- [ ] G1 red baseline covers duplicate branch id rejection within one inspected object.
- [ ] G1 red baseline covers invalid id regex rejection.
- [ ] G1 red baseline covers unnamed branch fallback ids `b0`, `b1`, ...
- [ ] G1 red baseline covers explicit branch ids plus positional `fallback_id` and `atom_ids`.
- [ ] G1 red baseline covers SDK multi-head construction rejection.
- [ ] G1 red baseline covers SDK register/evaluate multi-head rejection if a malformed object reaches runtime.
- [ ] G1 guard covers `condition_weights` still only accepting positional keys.
- [ ] G1 guard covers authoring payloads staying branch-id-free.
- [ ] G1 guard covers Track 3 B/C/D/E semantics profile suites staying green.
- [ ] G2 implements `Branch.id` as structural metadata only.
- [ ] G2 implements `fg.rules.inspect(...)` as a pure SDK inspect helper.
- [ ] G2 adds a read-only `fg.rules` namespace manager.
- [ ] G2 enforces single-head at the locked SDK public boundaries.
- [ ] G2 does not alter authoring compiler, rule IR, compiled plans, registry, or adapters for branch ids.
- [ ] G3 updates release-facing docs to teach branch identity, inspect, and single-head requirement.
- [ ] G3 removes release-facing "multi-head accepted" public teaching.
- [ ] G3 keeps `condition_weights` documented as positional where mentioned.
- [ ] No release or milestone refs are touched.

## 8. Implementation Plan

Projected cadence:

1. G0 scope-freeze: lock branch id syntax/validation, inspect API shape, metadata persistence, and single-head policy.
2. G1 red+guard baseline: add tests for branch ids, inspect output, single-head rejection, and Track 3 preservation.
3. G2 implementation: add branch identity, inspect namespace/helper, and single-head enforcement at the chosen boundary.
4. G3 docs sync: update SDK docs and working design references from "proposal" to current behavior where adopted.
5. G4 close-out: fill Outcome / Deviations, archive blueprint, and update archive README.

## 9. Docs To Update

Expected if this proceeds past G0:

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/01_concepts.en.md`
- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/sdk/docs/06_what_if_and_proof.en.md`
- `src/kernel/core/docs/01_architecture.en.md` if metadata crosses into core/application structures
- `docs/references/working/design-points/post-track3-semantics-public-api.zh.md`
- `docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md` if its syntax direction is materially updated

## 10. Outcome / Deviations

Task completion will fill:

- Final landed result:
- Validation:
- Commit lineage:
- Deviations:
- Archive notes:
