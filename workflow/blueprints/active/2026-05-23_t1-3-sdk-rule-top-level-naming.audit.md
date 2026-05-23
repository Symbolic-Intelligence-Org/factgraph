# T1.3 SDK Top-Level Rule Naming Audit Log

Status: draft
Last Updated: 2026-05-23
Blueprint: workflow/blueprints/active/2026-05-23_t1-3-sdk-rule-top-level-naming.md
Decision Doc: workflow/design/decisions/active/2026-05-23_t1-3-sdk-rule-top-level-naming.md

## Event Log

| Date | Event | Notes |
|---|---|---|
| 2026-05-23 | draft | Initial M-class blueprint + decision doc drafted from source-grep audit. |

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

The parent essay inclination is full replacement. This draft chooses staged replacement for T1.3 while preserving the final full-replacement direction. The deviation is documented in the decision doc as a timing refinement, not a change to final semantics.

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

### Cross-Slice Contract Preservation

- T1.1 application `Rule` implementation remains untouched.
- T1.2 `build_application_rule(...)` behavior remains untouched.
- T2 aggregate/arithmetic/adapter slices remain untouched.
- SDK docs may change to describe naming transition.

## Review Surface

Expected Step 4.2 review focus:

- Is staged replacement strong enough to satisfy parent §3.10, or does T1.3 need immediate `Rule` replacement?
- Should `ApplicationRule` be named `ProtocolRule`, `AtomicRule`, or another alias?
- Is `LegacyRule` enough as a migration signal without warnings?
- Should `build_application_rule` be promoted top-level now or remain DSL-only?
- Are docs sufficient to avoid users thinking `factgraph.sdk.Rule` has already flipped?
