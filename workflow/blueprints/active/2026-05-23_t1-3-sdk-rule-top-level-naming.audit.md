# T1.3 SDK Top-Level Rule Naming Audit Log

Status: implemented
Last Updated: 2026-05-23 (Step 4.8 closure)
Blueprint: workflow/blueprints/active/2026-05-23_t1-3-sdk-rule-top-level-naming.md
Decision Doc: workflow/design/decisions/active/2026-05-23_t1-3-sdk-rule-top-level-naming.md

## Event Log

| Date | Event | Notes |
|---|---|---|
| 2026-05-23 | draft | Initial M-class blueprint + decision doc drafted from source-grep audit. |
| 2026-05-23 | Step 4.2 v2 tightening | Applied 4 Required + 3 Worth-considering findings from first M-class review. |
| 2026-05-23 | scoped | Step 4.2 v2 re-review passed with 0 Blocker / 0 Required; decision doc accepted concurrent with scoped anchor. |
| 2026-05-23 | G7 precondition | Recorded current SDK Rule identities and missing transitional top-level aliases before implementation. |
| 2026-05-23 | implemented | Step 4.7 review passed with 0 findings; blueprint Outcome filled. |

## G1-G7 Mapping

### G1 Parent / Canonical Source

- Parent essay §3.8 and §3.10 identify the new `Rule` and the old/new naming conflict.
- Track plan §1.2.6 classifies T1.3 as M-class.
- Track plan TPQ-2 records the naming question and replacement inclination.

### G2 Source-Grep Audit

Read and/or grep:

- `src/factgraph/sdk/__init__.py`
- `src/factgraph/sdk/dsl/__init__.py`
- `src/factgraph/sdk/dsl/rule.py`
- `src/factgraph/sdk/dsl/application_rule.py`
- `src/factgraph/application/protocol/rule.py`
- SDK docs `03_rules_and_inferences` and `04_api_surface`
- current tests / examples importing `Rule`
- T1.1 and T1.2 archived blueprint sections documenting deferral

### G3 File-Line Precision

Blueprint §4 cites current source with line precision. Step 4.2 reviewer should independently verify at least:

- `sdk/__init__.py` top-level `Rule`
- `sdk/dsl/rule.py` legacy `Rule`
- `application/protocol/rule.py` application `Rule`
- `sdk/dsl/application_rule.py` bridge alias
- parent essay §3.10 alternatives

### G4 Goal Mapping

- §2.1 maps to TPQ-2 decision lock.
- §2.2 maps to transitional top-level SDK surface.
- §2.3 maps to backward compatibility.
- §2.4 maps to final replacement direction.
- §2.5 maps to M-class governance.

### G5 Deviations

The parent essay inclination is full replacement. This draft chooses A-staged replacement for T1.3 while preserving the final full-replacement direction. The decision doc now explicitly frames this as a timing refinement of parent alternative A and defers parent §3.10 line 325's final `Rule` semantics until the T5 hard-cut.

### G6 Reviewer Spot-Check

Reviewer should verify:

- immediate replacement would break existing top-level `Rule` callers
- `ApplicationRule` alias is identity-equal to `factgraph.application.protocol.Rule`
- no SDK top-level `ApplicationRule` / `LegacyRule` currently exists
- docs currently present legacy `Rule` semantics

### G7 Pre-Impl Preconditions

Before implementation, record:

- current top-level identities
- current missing transitional aliases
- decision doc accepted status
- target tests to be added
- sacred + dirty set state

## Decision Notes

### Initial Scope Lock

T1.3 is M-class because the public top-level SDK namespace is a durable API surface and TPQ-2 is explicitly load-bearing. The implementation remains small, but the naming decision has future compatibility consequences.

### Initial Decision Direction

The draft decision selects staged replacement:

- Keeps `factgraph.sdk.Rule` stable in T1.3.
- Adds `LegacyRule` to make legacy status explicit.
- Adds `ApplicationRule` to make the new path explicit.
- Keeps final replacement of `Rule` available for a later hard-cut.

### Step 4.2 v2 Tightening

| Finding | Resolution |
|---|---|
| P1 Required: Alternative D outside parent A/B/C + missing final trigger | Renamed the choice to A-staged, stated it is a timing refinement of parent alternative A, reconciled parent §3.10 line 325 as deferred, and locked the final flip trigger to the T5 legacy `.eval` / old rule hard-cut. |
| P2 Required: `when` field cite inaccurate | Replaced `when` with shipped legacy fields `expose` and `condition_weights`, and tightened the field cite to `sdk/dsl/rule.py:67-74`. |
| P3 Required: T2.3b docs guidance reversal unhandled | Blueprint and decision doc now explicitly state that `build_application_rule` becomes available from top-level SDK while `agg_*` helpers remain DSL-only. |
| P4 Required: Decision status lifecycle unspecified | Added proposed/reviewed/accepted/superseded lifecycle and made accepted status a Step 4.6 implementation gate. |
| P5 Worth-considering: deprecation signal | Chose no `DeprecationWarning` in T1.3; warning policy deferred to final hard-cut. |
| P6 Worth-considering: concrete caller count | Added the 15-site caller count to Alternative A cost. |
| P7 Worth-considering: docs scope completeness | Added `06_what_if_and_proof.en.md` as explicit out-of-scope unless it claims final application-rule semantics. |

### Cross-Slice Contract Preservation

- T1.1 application `Rule` implementation remains untouched.
- T1.2 `build_application_rule(...)` behavior remains untouched.
- T2 aggregate/arithmetic/adapter slices remain untouched.
- SDK docs may change to describe naming transition and to broaden T2.3b's `build_application_rule` import guidance; aggregate helper top-level export remains out of scope.

### G7 Precondition Results

Recorded on impl branch before implementation code changes:

```text
PYTHONPATH=src python - <<'PY'
import factgraph.sdk as sdk
import factgraph.sdk.dsl as dsl
from factgraph.application.protocol import Rule as ApplicationRule
print('sdk.Rule is dsl.Rule', sdk.Rule is dsl.Rule)
print('has LegacyRule', hasattr(sdk, 'LegacyRule'))
print('has ApplicationRule', hasattr(sdk, 'ApplicationRule'))
print('has top build_application_rule', hasattr(sdk, 'build_application_rule'))
print('has top DSLToApplicationRuleError', hasattr(sdk, 'DSLToApplicationRuleError'))
print('application Rule name', ApplicationRule.__module__ + '.' + ApplicationRule.__name__)
PY
```

Observed:

- `sdk.Rule is dsl.Rule`: `True`
- `has LegacyRule`: `False`
- `has ApplicationRule`: `False`
- `has top build_application_rule`: `False`
- `has top DSLToApplicationRuleError`: `False`
- application rule identity: `factgraph.application.protocol.rule.Rule`

Decision doc status at this point: `accepted`, so implementation is unblocked.

### Step 4.8 Closure

Implementation commits:

- `dd323698` — G7 precondition record, before code changes.
- `c846af09` — feature implementation.

Step 4.7 review result:

- 0 Blocker
- 0 Required
- 0 Worth-considering

Verification reported by reviewer:

- T1.3 tests: 6 pass.
- Cross-slice sweep: 145 pass.
- Ruff: clean.
- No diff in adapters, core, or application protocol Rule.
- Sacred master and dirty set preserved.

Decision doc remains `accepted`; no superseding decision was created.

## Review Surface

Expected Step 4.2 review focus:

- Is staged replacement strong enough to satisfy parent §3.10, or does T1.3 need immediate `Rule` replacement?
- Should `ApplicationRule` be named `ProtocolRule`, `AtomicRule`, or another alias?
- Is `LegacyRule` enough as a migration signal without warnings?
- Should `build_application_rule` be promoted top-level now or remain DSL-only?
- Are docs sufficient to avoid users thinking `factgraph.sdk.Rule` has already flipped?
