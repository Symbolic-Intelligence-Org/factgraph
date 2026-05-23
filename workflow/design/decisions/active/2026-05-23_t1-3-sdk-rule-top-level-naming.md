# Decision: T1.3 SDK Top-Level Rule Naming

Status: accepted
Last Updated: 2026-05-23 (Step 4.6 scoped anchor)
Related Blueprint: workflow/blueprints/active/2026-05-23_t1-3-sdk-rule-top-level-naming.md

## Context

The rule-expression parent design introduces a new user-facing `Rule` object: an atomic AND-only rule over a condition block. The current SDK already exports `Rule`, but that object is the legacy SDK DSL rule with legacy head/body fields and old proof-attempt semantics.

T1.1 shipped the new application protocol `Rule` at `factgraph.application.protocol.Rule`. T1.2 shipped `build_application_rule(...)` under `factgraph.sdk.dsl`. T1.3 must decide what the SDK top-level namespace should expose now and what it should reserve for the final hard-cut.

## Decision Drivers

- New users should eventually read `Rule` as the atomic AND-only rule.
- Existing callers of `factgraph.sdk.Rule` must not be broken before the legacy hard-cut.
- The transition should make the new rule path discoverable from the SDK top-level namespace.
- The naming should avoid a long-lived `v2` namespace unless unavoidable.
- The implementation should preserve T1.1 / T1.2 behavior and avoid touching adapters or core.

## Alternatives

Parent §3.10 lists replacement, namespace isolation, and mode-transition alternatives. The selected option below is framed as **A-staged**: a timing refinement of replacement, not a fourth permanent semantic model.

### A. Immediate Replacement

Make `factgraph.sdk.Rule` point to `factgraph.application.protocol.Rule` in T1.3 and rename the current SDK DSL class to `LegacyRule`.

Benefits:

- Matches the parent essay's final user-facing meaning immediately.
- Removes ambiguity from `from factgraph.sdk import Rule`.

Costs:

- Breaks existing tests, examples, and domain integrations that construct legacy `Rule`.
- Requires updating 15 current `from factgraph.sdk import Rule` caller sites identified during Step 4.2 review: 13 tests plus 2 docs.
- Requires broader migration work before the legacy `.eval` / old rule workflow is ready to be cut.
- Turns a narrow naming slice into a larger compatibility migration.

### B. Namespace Isolation

Introduce a separate namespace such as `factgraph.sdk.v2.Rule` for the new application rule while leaving `factgraph.sdk.Rule` untouched.

Benefits:

- Avoids breaking existing callers.
- Makes the new object name `Rule` within a clean namespace.

Costs:

- Creates a parallel SDK namespace before the project has committed to a broader v2 split.
- Makes examples and docs noisier.
- Risks keeping the old/new split permanent.

### C. Mode Flag On Legacy Rule

Keep one `Rule` class and add a mode, constructor variant, or flag that can represent both legacy and new application semantics.

Benefits:

- Single public name.
- No import-level churn.

Costs:

- Mixes two incompatible models in one class.
- Preserves the exact confusion the parent essay identifies: `Rule` with `select` / `head` versus atomic AND-only rule.
- Makes validation and docs harder.

### D. A-Staged Replacement With Explicit Aliases

Keep `factgraph.sdk.Rule` as the legacy SDK DSL rule for T1.3. Add:

- `factgraph.sdk.LegacyRule` as an explicit alias for the current legacy rule
- `factgraph.sdk.ApplicationRule` as an explicit alias for `factgraph.application.protocol.Rule`
- `factgraph.sdk.build_application_rule`
- `factgraph.sdk.DSLToApplicationRuleError`

Document that final direction remains flipping top-level `Rule` to the application rule at the T5 legacy `.eval` / old rule hard-cut. This is parent alternative A delayed to the hard-cut point, not a separate long-lived model.

Benefits:

- Preserves backward compatibility now.
- Makes the new application rule path discoverable from the SDK top-level namespace.
- Gives users an explicit `LegacyRule` spelling before the future hard-cut.
- Avoids introducing a `v2` namespace or a confusing mode flag.
- Keeps implementation narrow.

Costs:

- `factgraph.sdk.Rule` remains legacy for now, so the parent essay's final naming state is not fully achieved in T1.3.
- Parent §3.10 line 325's "new user sees `Rule` as atomic AND-only" promise is explicitly deferred during the staged period.
- Docs must be precise to avoid implying the final flip already happened.
- A later hard-cut still needs to update `Rule`.

## Decision

Choose **D. A-Staged Replacement With Explicit Aliases**.

T1.3 implements a transitional top-level SDK surface:

- `Rule` remains the current legacy SDK DSL rule.
- `LegacyRule` is added as an explicit alias for that same legacy rule.
- `ApplicationRule` is added as an alias for `factgraph.application.protocol.Rule`.
- `build_application_rule` is promoted to the SDK top-level as an alias.
- `DSLToApplicationRuleError` is promoted to the SDK top-level as an alias.

The final target remains replacing top-level `Rule` with the new application rule during the T5 legacy `.eval` / old rule hard-cut. Until then, the final parent §3.10 user-facing `Rule` promise is deferred as a timing matter.

## Lifecycle

- `proposed`: initial draft commit
- `reviewed`: after Step 4.2 review passes
- `accepted`: concurrent with the blueprint Step 4.6 scoped anchor; implementation may begin only after this transition
- `superseded`: if a later decision doc replaces this one; this document remains historical record

## Consequences

- Existing callers keep working.
- New code can import `ApplicationRule` and `build_application_rule` from `factgraph.sdk`.
- Docs must clearly state the transition status.
- T2.3b's SDK docs guidance evolves: `build_application_rule` becomes available from `factgraph.sdk` as well as `factgraph.sdk.dsl`, while `agg_*` helpers remain DSL-only.
- T1.3 does not emit `DeprecationWarning` from legacy `Rule`; warnings are deferred to the final hard-cut to avoid noisy output across the current caller set.
- A future decision or hard-cut slice must flip `Rule` and decide whether `LegacyRule` remains temporarily or is removed.
- Tests must assert alias identity to prevent wrappers or accidental semantic drift.

## Related Commitments

- Parent essay §3.8: new rule as first-class user-facing object.
- Parent essay §3.10: old/new `Rule` naming conflict and alternatives.
- Track plan TPQ-2: naming conflict solution.
- T1.1: application protocol `Rule` introduced.
- T1.2: SDK DSL to application `Rule` bridge introduced.
