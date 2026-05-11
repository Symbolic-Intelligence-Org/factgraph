# Task Blueprint: Condition Weights Decomposition

- Status: draft
- Created: 2026-05-11
- Last Updated: 2026-05-11
- Related Modules:
  - `src/kernel/sdk/`
  - `src/kernel/authoring/`
  - `src/kernel/core/annotation/`
  - `src/kernel/core/store/`
  - `src/service/`
  - `src/agent/`
- Related Docs:
  - [docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md](../../references/working/design-points/rule-policy-function-tree-and-syntax.zh.md)
  - [docs/references/working/design-points/possibility-probability-transmission.zh.md](../../references/working/design-points/possibility-probability-transmission.zh.md)
  - [docs/blueprints/archive/2026-03-20_certainty-weight-vocabulary.md](../archive/2026-03-20_certainty-weight-vocabulary.md)
  - [docs/blueprints/archive/2026-03-20_rule-condition-weight-metadata.md](../archive/2026-03-20_rule-condition-weight-metadata.md)
  - [docs/blueprints/archive/2026-05-11_derivation-mode-to-callsite.md](../archive/2026-05-11_derivation-mode-to-callsite.md)
  - [docs/blueprints/archive/2026-05-11_branch-confidence-decomposition.md](../archive/2026-05-11_branch-confidence-decomposition.md)
  - [docs/blueprints/archive/2026-05-11_engine-ext-decomposition.md](../archive/2026-05-11_engine-ext-decomposition.md)
- Audit Log:
  - [2026-05-11_condition-weights-decomposition.audit.md](./2026-05-11_condition-weights-decomposition.audit.md)

## 1. Problem

Track 3 is decomposing public rule / derivation surfaces before introducing
`SemanticsProfile`.

A1 removed public `Derivation.mode`.
A2 replaced `Body` with structure-only `Branch` and removed branch-level
`confidence`.
A3 removed public `Rule.engine_ext` / `Derivation.engine_ext`.

A4 handles `condition_weights`, but it is not the same kind of surface as
A1-A3:

- `condition_weights` is not an adapter-specific engine parameter.
- It was deliberately introduced as version-scoped rule asset metadata in the
  March certainty / weight vocabulary work.
- It is already consumed by the certainty-summary / explain chain through
  registry lookup and `core.annotation._certainty`.
- It does not affect where execution or adapter query semantics.

The Track 3 tension is therefore narrower:

```text
Rule / Derivation = standard business template
Condition weights = certainty/explain semantics attached to rule conditions
SemanticsProfile = future runtime projection / interpretation surface
```

A4 must decide whether `condition_weights` should remain public rule asset
metadata, be removed from public rule objects like the earlier A-slices, or be
bridged until SemanticsProfile can own certainty projection explicitly.

## 2. Goals

- Catalog every current `condition_weights` entry and consumer.
- Decide whether `condition_weights` belongs in the A-slice public-surface
  decomposition, in SemanticsProfile B, or in a separate certainty metadata
  migration.
- Preserve the distinction between logical rule structure and
  certainty/explain value semantics.
- Avoid accidentally breaking the existing certainty-summary / explain chain.
- If scope-freeze chooses a code change, define testable public-surface,
  payload, service, agent, and docs gates before implementation.

## 3. Non-goals

- Do not introduce `SemanticsProfile` in A4.
- Do not redesign certainty aggregation math.
- Do not change `derive_certainty_summary(...)` bottleneck / additive
  semantics.
- Do not change ProbLog or PyReason adapter semantics.
- Do not change `raw_kind` / `bound` fact-level uncertainty semantics.
- Do not change where execution, RuleRef evaluation, or support artifact
  structure.
- Do not move condition weights into `where`, `where_ast`, or native
  evaluator IR.
- Do not touch A1/A2/A3 archived milestones or release refs.

## 4. Current Context

### 4.1 Track 3 Roadmap

```text
A1. Derivation.mode -> call-site engine selection        done
A2. Body.confidence + Body -> Branch                     done
A3. engine_ext public surface -> internal adapter target done
A4. condition_weights -> this blueprint
B.  SemanticsProfile data shape and transmission scaffolding
C.  ProbLog adapter migration
D.  PyReason adapter migration
E.  SDK call-site shape and optional projection inspection API
```

### 4.2 Source Audit Summary

The initial A4 audit found `condition_weights` in roughly these layers:

| Layer | Current shape | A4 implication |
| --- | --- | --- |
| SDK DSL | `Rule.condition_weights: dict[str, float]` and `Rule.to_authoring_payload()` emission | Main public SDK field under review |
| Authoring compile | `compile_authoring_rule_v1(...)` validates `condition_weights` as positive finite values keyed by `b{branch}.a{atom}` | Public authoring payload currently accepts and validates it |
| Service rule registry | `service/rules_v1.py` forwards `condition_weights` into compile-preview / registry flow | Service public rule-authoring payload currently accepts it |
| Agent rule tools | `agent.tools.rules.RuleSpec.condition_weights` serializes to rule dict | Agent authoring surface also exposes it |
| Registry / certainty service | `service._certainty_service._lookup_condition_weights_for_candidate(...)` reads registry rule payload by support `rule_ref_edge` | Existing production consumer; not just metadata storage |
| Core certainty routing | `core.store._confidence_kind_resolver` routes candidate confidence kind to `"certainty"` only when rule payload has non-empty `condition_weights` | Removing weights changes confidence-kind behavior |
| Core materialization | `core.store._certainty_materializer` passes weights to `derive_certainty_summary(...)` | Existing explain/certainty output depends on it |
| Core annotation | `core.annotation._certainty` computes per-condition impacts and aggregate certainty | Math is out of A4 scope |
| Docs | SDK / authoring / service / core / audit docs describe `condition_weights` as rule metadata and explain input | Docs need sync to whatever G0 decides |

### 4.3 Historical Constraint

The archived `2026-03-20_rule-condition-weight-metadata` blueprint froze an
important boundary:

- `condition_weights` is version-scoped rule metadata.
- Keys use atom-position form `b{branch}.a{atom}`.
- `RuleSpec`, `where_ast`, and where evaluators must remain pure logical
  execution contracts.
- Annotation / certainty layers may consume weights but do not own them.

A4 must either preserve that historical boundary or explicitly supersede it.

## 5. Proposed Shape

This draft does not lock the final implementation. It frames three possible
scope-freeze paths.

### 5.1 Option A: Keep As Rule Metadata, Clarify Boundary

Retain public `Rule.condition_weights` and authoring/service payload
`condition_weights`, but update docs/tests to classify it as
certainty/explain metadata rather than engine semantics.

Pros:

- Preserves existing certainty-summary functionality.
- Respects the March 2026 rule metadata decision.
- Avoids introducing a functionality gap before SemanticsProfile exists.

Cons:

- Leaves one value-semantics field on public `Rule`.
- Track 3 public-surface decomposition remains incomplete if the target is
  "no value semantics on Rule at all".

### 5.2 Option B: Hard Remove Public Field / Payload

Remove public SDK `Rule.condition_weights`, reject authoring/service/agent
payload `condition_weights`, and keep only internal registry fixtures or test
helpers until SemanticsProfile lands.

Pros:

- Matches A1/A2/A3 hard-cut style.
- Makes public `Rule` purely structural.

Cons:

- Breaks the existing certainty-summary / explain authoring path.
- Creates a larger public functionality gap than A3 because no current
  `engine_ext`-style fallback remains.
- Supersedes the March rule-metadata decision and must document why.

### 5.3 Option C: Bridge And Rename Toward Certainty Projection

Keep the current storage / registry / certainty consumer path, but start a
decomposition bridge:

- stop describing `condition_weights` as generic rule metadata;
- classify it as `certainty_projection` input;
- potentially keep the public key temporarily with explicit future redirect
  to `SemanticsProfile.certainty_projection` or
  `SemanticsProfile.rule_projection.certainty`;
- defer hard removal until B defines the replacement shape.

Pros:

- Keeps certainty functionality alive.
- Aligns with Track 3 SemanticsProfile direction.
- Avoids locking the final field name before B.

Cons:

- A4 becomes a scoped design / docs / guard slice rather than a hard-removal
  slice.
- Requires clear G0 wording so later sessions do not mistake the bridge for a
  permanent endpoint.

### 5.4 Draft Direction

The current draft direction is **Option C**, with G0 required to decide whether
A4 is:

1. an implementation slice that removes public `condition_weights`; or
2. a boundary-clarification slice that preserves current behavior until B.

## 6. Boundaries And Invariants

Draft invariants to tighten at G0:

- `condition_weights` must not enter `where`, `where_ast`, native evaluator
  IR, ProbLog rule syntax, or PyReason rule syntax.
- If retained, `condition_weights` remains value-semantics metadata consumed
  by certainty/explain logic only.
- If removed, public rejections must redirect to future SemanticsProfile
  certainty projection and tests must cover the temporary functionality gap.
- Existing certainty-summary math must not change in A4.
- A4 must not introduce a SemanticsProfile implementation.
- A4 must not alter A1/A2/A3 public-surface decisions.

## 7. Acceptance

Draft gates to tighten at G0:

- [ ] G0 locks Option A, B, or C explicitly.
- [ ] Source audit table is complete enough to identify every public entry
      and every existing consumer.
- [ ] Tests reflect the chosen public contract.
- [ ] Existing certainty-summary / explain tests either remain green or are
      intentionally updated with documented functionality-gap rationale.
- [ ] No SemanticsProfile implementation appears in A4.
- [ ] Release-facing docs no longer imply that `condition_weights` is an
      engine adapter parameter.
- [ ] If public syntax is retained, docs classify it as certainty/explain
      metadata with future SemanticsProfile migration notes.
- [ ] If public syntax is removed, stale-syntax grep proves release-facing docs
      teach only rejection / migration / internal bridge context.

## 8. Implementation Plan

Expected cadence, subject to G0:

1. G0 scope-freeze:
   - choose Option A/B/C;
   - lock public entry fates for SDK, authoring, service, and agent;
   - tighten §6 / §7 into testable form;
   - record scope-freeze in audit.
2. G1 red baseline or guard baseline:
   - if Option B, add forward-failing public-removal tests;
   - if Option A/C, add guard tests that prove current certainty behavior and
     public syntax are intentionally retained.
3. G2 implementation:
   - implement the chosen public-surface decision;
   - preserve or intentionally retire certainty-summary paths according to G0.
4. G3 docs sync:
   - update SDK, authoring, service, core, audit, and agent docs as needed;
   - run chosen stale/retained syntax grep gates.
5. G4 close-out:
   - fill Outcome / Deviations;
   - mark blueprint implemented;
   - archive blueprint pair and update archive inventory.

## 9. Docs To Update

Expected active docs to inspect:

- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/authoring/docs/01_overview.md`
- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/core/annotation/docs/README.md`
- `src/kernel/audit/docs/01_overview.en.md`
- `src/service/docs/01_overview.md`
- `src/service/docs/03_runtime_queries_policy.md`
- `src/service/docs/04_rules_registry.md`
- agent docs if a current rules-tool doc exists for `src/agent/tools/rules.py`

## 10. Outcome / Deviations

Task completion will fill:

- Final landed behavior:
- Deviations from blueprint:
- Rationale for deviations:
- Archive notes:
