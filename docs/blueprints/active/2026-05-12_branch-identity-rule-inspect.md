# Task Blueprint: Branch Identity, Rule Inspect, And Single-Head Cleanup

- Status: draft
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

This draft intentionally leaves final decisions open for G0. The recommended path is:

1. Add branch identity as structural metadata only.
2. Add public `fg.rules.inspect(...)` to expose normalized rule/derivation shape.
3. Hard-cut public multi-head `Derivation` support at the SDK authoring/evaluate boundary, while preserving core/application internals as needed for compatibility and tests.

### 5.1 Branch Identity Options

| Option | Shape | Trade-off |
| --- | --- | --- |
| B1a | `Branch([...], id="sensor_path")` | Best compatibility with current positional `Branch([...])`; explicit id is opt-in. |
| B1b | `Branch(id="sensor_path", atoms=[...])` | Reads well but breaks the current one-positional-argument mental model unless custom init supports both. |
| B1c | Auto-generated UUID | Stable inside one object, but bad for docs, diffs, and profile authoring; not recommended. |

Recommended for G0: B1a, with optional keyword-only `id` and no engine-semantic kwargs.

### 5.2 Branch Id Fallback

Unnamed branches should inspect as positional ids `b0`, `b1`, ... to align with:

- existing `b{branch}.a{atom}` condition locators;
- PyReason compiled rule suffixes `_b{branch_idx}`;
- previous design-point notes.

Open question: should fallback `b0` ids be accepted in future public semantics, or should semantics require explicit branch ids? Recommended: accept fallback ids for inspectability but warn in docs that explicit ids are more durable.

### 5.3 Branch Id Validation

Potential validation:

- non-empty string;
- unique within one `Rule` / `Derivation`;
- identifier-like by default (`^[A-Za-z_][A-Za-z0-9_]*$`) to keep profile keys readable.

Open question: allow `-` / `.` for business ids? G0 should lock the regex.

### 5.4 Inspect API Options

| Option | Shape | Trade-off |
| --- | --- | --- |
| I1a | `fg.rules.inspect(rule_or_derivation)` | Clean taxonomy; starts first-class `rules` namespace. |
| I1b | `fg.eval.inspect_rule(rule_or_derivation)` | Pairs with `inspect_semantics`, but structure inspection is not evaluation. |
| I1c | object method `rule.inspect()` | Easy local use, but does not fit existing SDK manager pattern. |

Recommended for G0: I1a.

Draft return shape:

```python
{
    "kind": "Rule" | "Derivation",
    "id": "...",
    "version": "...",
    "heads": [...],
    "branches": [
        {
            "id": "sensor_path",
            "fallback_id": "b0",
            "index": 0,
            "atoms": [...],
            "atom_ids": ["b0.a0", "b0.a1"],
        },
    ],
}
```

Open question: should `atoms` be returned as SDK-ish display strings, authoring payload dicts, or both? G0 should lock the first implementation shape.

### 5.5 Metadata Persistence Options

| Option | Shape | Trade-off |
| --- | --- | --- |
| P1a | Inspect-only metadata from SDK objects | Smallest implementation; branch ids are not available after registry compile. |
| P1b | Carry branch metadata through authoring payload and compiled plans | More durable; bigger cross-module touch. |
| P1c | Store branch metadata in registry sidecar only | Avoids rule IR changes but adds registry-specific state. |

Recommended for G0: decide explicitly. Track 2 public semantics may need ids at runtime, so P1a is likely too narrow unless Track 2 re-lowers from SDK objects only.

### 5.6 Single-Head Cut Options

| Option | Shape | Trade-off |
| --- | --- | --- |
| H1a | SDK public `Derivation` rejects multi-head at construction | Strongest public cleanup; may require broad test/doc migration. |
| H1b | SDK construction allows, `register_derivation` / `evaluate` reject | Preserves object construction, cuts runtime public behavior. |
| H1c | Keep multi-head evaluate and only document future removal | Lowest risk now, keeps Track 2 complexity. |

Recommended for G0: H1b or H1a. If this slice is meant to prepare public `PyReasonSemantics.head_bound`, a real hard-cut is preferable to documentation-only deferral.

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

## 6. Boundaries And Invariants

- `Branch` remains logical structure only; no probability, confidence, interval, bound, engine, or engine_ext fields.
- Branch identity must not change deterministic native/Souffle/ProbLog/PyReason evaluation results.
- Existing Track 3 `SemanticsProfile` behavior remains intact.
- Existing C/D adapter consumption remains intact.
- Public multi-head decision must not silently change capability shell semantics; those shells already reject multi-head.
- If branch metadata is carried past SDK objects, it must not be stored as profile-derived facts or engine registry state.
- Documentation must clearly distinguish public `fg.rules.inspect(...)` from internal compile/runtime structures.

## 7. Acceptance

Draft acceptance is intentionally high-level until G0 locks D-decisions:

- [ ] G0 locks branch id syntax, validation, fallback behavior, metadata persistence, inspect namespace, inspect return shape, and single-head cut scope.
- [ ] G1 adds red/guard tests for the locked public surface.
- [ ] Branch identity is structural only and rejects engine-semantic kwargs.
- [ ] Rule/derivation inspect exposes stable branch ids and positional fallback ids.
- [ ] Single-head policy is enforced at the locked public boundary.
- [ ] Existing Track 3 B/C/D/E semantics-profile suites remain green.
- [ ] Existing deterministic evaluation behavior remains green for single-head rules/derivations.
- [ ] Affected SDK docs and reference notes are updated.
- [ ] No release or milestone refs are touched.

## 8. Implementation Plan

Projected cadence if G0 adopts this draft:

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
