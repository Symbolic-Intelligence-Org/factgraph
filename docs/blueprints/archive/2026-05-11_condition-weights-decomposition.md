# Task Blueprint: Condition Weights Decomposition

- Status: implemented
- Created: 2026-05-11
- Last Updated: 2026-05-12
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

This blueprint considered four possible scope-freeze paths.

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

### 5.4 Option D: Skip A4 And Jump To SemanticsProfile B

Do not implement a separate A4 slice. Start B (`SemanticsProfile`) next and
let the SemanticsProfile shape absorb `condition_weights` / certainty
projection directly.

Pros:

- Avoids an intermediate docs / guard slice.
- Lets the final SemanticsProfile data shape decide the replacement
  vocabulary before any migration language is written.

Cons:

- Leaves A4's current ambiguity unresolved in module docs while B is being
  designed.
- Skips the explicit Track 3 follow-up to the March 2026 certainty metadata
  decision.

### 5.5 Scope Freeze Decisions

G0 locks **Option C** over A/B/D.

Rationale:

- Option A undercommits: it preserves behavior but does not align the wording
  with Track 3's future SemanticsProfile projection model.
- Option B is premature: it would break certainty-summary / explain authoring
  without a replacement public path.
- Option D is defensible, but A4-C is small and records the boundary before B;
  B can then inherit an explicit `certainty_projection` migration target rather
  than rediscovering the March 2026 decision.

Locked decisions:

| ID | Decision |
| --- | --- |
| D1 | Retain public SDK `Rule.condition_weights` as a typed `dict[str, float]` field for this slice. |
| D2 | Retain authoring, service rule-registry, and agent rules-tool payload `condition_weights` entries for this slice. |
| D3 | Reclassify `condition_weights` in docs as certainty/explain projection input, not engine adapter semantics and not where execution semantics. |
| D4 | Point future migration language to `SemanticsProfile.certainty_projection`. This appears in docs / migration notes only, not as runtime warnings or rejection errors. |
| D5 | Preserve the March 2026 boundary: `condition_weights` remains out of `where`, `where_ast`, evaluator IR, ProbLog rule syntax, and PyReason rule syntax. |
| D6 | Keep certainty-summary math and `derive_certainty_summary(...)` unchanged. |
| D7 | Treat agent serialization (`agent.tools.rules.RuleSpec.condition_weights`) the same as SDK / authoring: retained, classified as certainty projection input, and documented as future-migrating to SemanticsProfile. |
| D8 | Use a guard-baseline cadence, not an A1/A2/A3 forward-failing red baseline. Tests must prove retained public syntax and live certainty behavior still work. |

## 6. Boundaries And Invariants

- SDK `Rule.condition_weights` remains public and retains its current
  validation: dict keys are non-empty strings and values are positive finite
  numbers.
- Authoring compile continues validating `condition_weights` against existing
  atom-position keys (`b{branch}.a{atom}`).
- Service rule registry and agent rule tools continue accepting and forwarding
  `condition_weights`.
- `_confidence_kind_resolver` continues routing to
  `confidence_kind="certainty"` when the resolved rule payload has non-empty
  `condition_weights`.
- `_certainty_service._lookup_condition_weights_for_candidate(...)` continues
  resolving weights through support `rule_ref_edge -> registry rule payload`.
- `materialize_certainty_summary(...)` and `derive_certainty_summary(...)`
  continue producing the same certainty summaries for weighted rules.
- `condition_weights` must not enter `where`, `where_ast`, native evaluator
  IR, ProbLog rule syntax, or PyReason rule syntax.
- A4 must not introduce a SemanticsProfile implementation.
- A4 must not alter A1/A2/A3 public-surface decisions.

## 7. Acceptance

- [ ] G0 locks Option C explicitly and records why Option D was not chosen.
- [ ] Guard tests prove `Rule.condition_weights` remains a public SDK field.
- [ ] Guard tests prove SDK `Rule(..., condition_weights=...)` still emits
      sorted authoring payload `condition_weights`.
- [ ] Guard tests prove invalid SDK `condition_weights` still reject.
- [ ] Guard tests prove authoring compile accepts valid `condition_weights`
      and rejects keys that do not match existing atom positions.
- [ ] Guard tests prove service rule compile-preview / registry payloads
      continue preserving `condition_weights`.
- [ ] Guard tests prove agent `RuleSpec.condition_weights` serialization
      continues emitting the field.
- [ ] Guard tests prove `_confidence_kind_resolver` still routes weighted
      rules to `confidence_kind="certainty"`.
- [ ] Guard tests prove certainty-summary materialization remains unchanged
      for a weighted rule.
- [ ] No SemanticsProfile implementation appears in A4.
- [ ] Release-facing docs classify `condition_weights` as certainty/explain
      projection input with future `SemanticsProfile.certainty_projection`
      migration notes.
- [ ] Release-facing docs do not describe `condition_weights` as an engine
      adapter parameter or where execution semantics.

## 8. Implementation Plan

Expected cadence:

1. G0 scope-freeze:
   - record Option C over A/B/D;
   - lock D1-D8;
   - tighten §6 / §7 into testable form;
   - record scope-freeze in audit.
2. G1 guard baseline:
   - add passing guard tests that prove current certainty behavior and public
     syntax are intentionally retained.
3. G2 implementation:
   - add any small code-level marker or helper needed by G1/G3;
   - do not remove public syntax or alter certainty math.
4. G3 docs sync:
   - update SDK, authoring, service, core, audit, and agent docs as needed;
   - run certainty-classification grep gates.
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

### Final Landed Behavior

A4 closed as the Option C boundary-clarification slice:

- `Rule.condition_weights` remains public SDK syntax.
- Authoring, service registry, and agent rule payloads continue to accept
  and preserve `condition_weights`.
- `condition_weights` remains keyed by atom position:
  `b{branch}.a{atom}`.
- `_confidence_kind_resolver` still routes eligible candidates to
  `confidence_kind="certainty"` when rule payloads contain non-empty
  weights.
- `_certainty_service` and `materialize_certainty_summary(...)` still
  consume pre-resolved weights without changing aggregation math.
- The March 2026 boundary is preserved: weights do not enter `where`,
  `where_ast`, evaluator IR, ProbLog rule syntax, or PyReason rule syntax.
- Public docs classify weights as certainty/explain projection input, not
  engine adapter semantics.
- Future runtime configuration for this lane is explicitly pointed at
  `SemanticsProfile.certainty_projection`.

### Validation

- G1 guard baseline added `test_condition_weights_decomposition.py`;
  A4 guard suite passed 9/9.
- Declaration metadata + core certainty annotation regression passed 43/43.
- A4 + certainty explain contract regression passed 50/50.
- G3 docs grep verified `SemanticsProfile.certainty_projection` appears
  across release-facing docs.
- G3 docs grep verified `engine adapter` proximity appears only in explicit
  negative classification text.
- `git diff --check` passed during G2/G3 verification.

### Commit Lineage

- `9bb2817c` — draft condition weights decomposition.
- `aa1c1143` — scope condition weights decomposition.
- `64d17e90` — add guard baseline for condition weights decomposition.
- `46bb77ea` — mark condition weights projection semantics.
- `b88c4ab6` — classify condition weights projection semantics.

### Deviations

- G2 used the small marker path rather than an empty implementation step.
  The marker is intentionally non-behavioral and exists only to anchor the
  retained field to the Track 3 / B migration target.
- G3 updated `src/kernel/authoring/docs/README.md` in addition to the
  expected §9 list, because the README summarized declaration metadata and
  otherwise would have omitted the retained `condition_weights` lane.

### Archive Notes

A4 is the final Track 3 A-slice after A1 (`Derivation.mode`), A2
(`Body` / branch confidence), and A3 (`engine_ext`). It deliberately does
not remove `condition_weights`; it records the retained certainty/explain
lane so Track 3 / B can introduce `SemanticsProfile.certainty_projection`
without rediscovering the March 2026 metadata boundary.
