# T1.3 SDK Top-Level Rule Naming

Status: draft
Last Updated: 2026-05-23
Class: M
Decision Doc: workflow/design/decisions/active/2026-05-23_t1-3-sdk-rule-top-level-naming.md

## 1. Problem

Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §3.8 and §3.10 commits to a future user-facing `Rule` object whose meaning is an atomic AND-only rule, not the existing SDK `Rule` object that still carries `select` / `head` / legacy proof-attempt shape. The parent essay explicitly identifies this naming conflict in §3.10 and lists replacement / namespace isolation / mode-transition alternatives.

T1.1 shipped the new application protocol DTO at `factgraph.application.protocol.Rule`. T1.2 shipped `factgraph.sdk.dsl.build_application_rule(...)` as the bridge from SDK DSL conditions to the application `Rule`. Both slices intentionally deferred SDK top-level naming. Current shipped state still exports legacy `Rule` from `factgraph.sdk` and `factgraph.sdk.dsl`, so top-level SDK import semantics remain ambiguous for the new workflow.

This slice resolves TPQ-2 at the M-class design level and implements the transitional SDK export surface chosen by the decision doc.

## 2. Goals

### 2.1 TPQ-2 Decision Lock

Adopt a documented public API naming decision for SDK top-level `Rule` exposure. The decision must compare at least:

- immediate replacement of `factgraph.sdk.Rule`
- namespace isolation such as a future `sdk.v2.Rule`
- mode/flag transition on the legacy `Rule`
- a staged replacement path with explicit transitional aliases

### 2.2 Transitional Top-Level SDK Exports

Expose a narrow, backward-compatible transition surface from `factgraph.sdk`:

- keep `Rule` bound to the existing legacy SDK DSL rule for now
- add `LegacyRule` as an explicit alias for the current SDK DSL `Rule`
- add `ApplicationRule` as an explicit alias for `factgraph.application.protocol.Rule`
- add `build_application_rule`
- add `DSLToApplicationRuleError`

### 2.3 Preserve Existing Legacy Callers

Existing imports such as `from factgraph.sdk import Rule` and `from factgraph.sdk.dsl import Rule` continue to resolve to the current legacy SDK `Rule` during this slice. This avoids changing existing tests, examples, and domain integrations before the larger legacy `.eval` / old rule hard-cut.

### 2.4 Document Final Direction

SDK docs must state that `ApplicationRule` is the transitional explicit name for the new application protocol rule and that the final target remains making top-level `Rule` mean the new atomic AND-only rule after the later hard-cut.

### 2.5 M-Class Governance

Because this slice changes public SDK naming and locks TPQ-2, it must carry the M-class decision doc through review before implementation starts.

## 3. Non-Goals

- Do not make `factgraph.sdk.Rule` point to `factgraph.application.protocol.Rule` in this slice.
- Do not rename the existing legacy class implementation file `src/factgraph/sdk/dsl/rule.py`.
- Do not delete or deprecate legacy `sdk.dsl.Rule` behavior at runtime.
- Do not introduce `factgraph.sdk.v2`.
- Do not add mode flags to legacy `Rule`.
- Do not change `build_application_rule(...)` behavior.
- Do not change application protocol `Rule`.
- Do not touch T2 aggregate, arithmetic, or adapter implementations.
- Do not update examples wholesale beyond docs that explain the naming transition.
- Do not push or merge branches.

## 4. Current Context

### 4.1 Parent Design

- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:274` frames the new `Rule` as a user-facing first-class object.
- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:308-315` states that the current `Rule` and new `Rule` are not the same object.
- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:316-323` lists replacement, namespace isolation, and mode-transition alternatives.
- `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:325` says a new user seeing `Rule` should mean atomic AND-only behavior, not `select` / `head`.

### 4.2 Track Plan

- `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:113` classifies T1.3 as M-class because public API naming and TPQ-2 are load-bearing.
- `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:137` scopes T1.3 to naming conflict resolution and execution.
- `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:329` records the initial TPQ-2 inclination toward full replacement with `LegacyRule`, with formal decision required before hard-cut.

### 4.3 Current SDK Exports

- `src/factgraph/sdk/__init__.py:31` imports `Rule` from `.dsl`.
- `src/factgraph/sdk/__init__.py:64` includes `"Rule"` in top-level `__all__`.
- `src/factgraph/sdk/dsl/__init__.py:5` exports `DSLToApplicationRuleError` and `build_application_rule`.
- `src/factgraph/sdk/dsl/__init__.py:7` imports `Rule` from `.rule`.
- `src/factgraph/sdk/dsl/__init__.py:14-16` includes `build_application_rule`, `DSLToApplicationRuleError`, and `Rule` in DSL `__all__`.

### 4.4 Existing Legacy Rule

- `src/factgraph/sdk/dsl/rule.py:53-116` defines the current legacy SDK `Rule`.
- `src/factgraph/sdk/dsl/rule.py:61-74` includes legacy fields such as `select`, `where`, and `when`.
- `src/factgraph/sdk/dsl/rule.py:28-32` lets `RuleRef` accept a legacy `Rule` instance.

### 4.5 New Application Rule

- `src/factgraph/application/protocol/rule.py:43-51` defines the new application protocol `Rule`.
- `src/factgraph/application/protocol/rule.py:47` stores `where: tuple[Atom, ...]`.
- `src/factgraph/application/protocol/rule.py:48` stores explicit `ports`.
- `src/factgraph/sdk/dsl/application_rule.py:6` imports it as `ApplicationRule`.
- `src/factgraph/sdk/dsl/application_rule.py:46-82` builds an application `Rule` through `build_application_rule(...)`.

### 4.6 Current Docs

- `src/factgraph/sdk/docs/04_api_surface.en.md:88-99` currently lists `Rule` as the declarative rule surface with legacy head/body behavior.
- `src/factgraph/sdk/docs/04_api_surface.en.md:101-113` lists aggregate helpers and `build_application_rule` under `factgraph.sdk.dsl`.
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md:155-180` documents aggregate-backed application rule authoring via `factgraph.sdk.dsl`.

## 5. Proposed Shape

### 5.1 Decision Outcome

Adopt the decision documented in `workflow/design/decisions/active/2026-05-23_t1-3-sdk-rule-top-level-naming.md`:

> Staged replacement. Keep top-level `Rule` legacy-compatible in T1.3, add explicit `LegacyRule` and `ApplicationRule` aliases, and reserve the eventual `Rule` flip for the later legacy hard-cut.

### 5.2 SDK Top-Level Export Patch

`src/factgraph/sdk/__init__.py` should add:

```python
from factgraph.application.protocol import Rule as ApplicationRule
from .dsl import DSLToApplicationRuleError, build_application_rule
from .dsl import Rule as LegacyRule
```

The existing `Rule` import remains unchanged and continues to point at the legacy SDK DSL `Rule`.

`__all__` adds:

```python
"ApplicationRule",
"LegacyRule",
"build_application_rule",
"DSLToApplicationRuleError",
```

### 5.3 Docs Patch

Update SDK docs to explain:

- `Rule` is currently legacy-compatible.
- `LegacyRule` is an explicit name for the current legacy SDK rule.
- `ApplicationRule` is the explicit transitional name for the new application protocol rule.
- `build_application_rule(...)` is available from both `factgraph.sdk.dsl` and `factgraph.sdk`.
- Final target is a later hard-cut where `Rule` can become the new application rule.

### 5.4 Tests

Add focused SDK export tests:

- `factgraph.sdk.Rule is factgraph.sdk.dsl.Rule`
- `factgraph.sdk.LegacyRule is factgraph.sdk.dsl.Rule`
- `factgraph.sdk.ApplicationRule is factgraph.application.protocol.Rule`
- `factgraph.sdk.build_application_rule is factgraph.sdk.dsl.build_application_rule`
- `factgraph.sdk.DSLToApplicationRuleError is factgraph.sdk.dsl.DSLToApplicationRuleError`
- existing legacy top-level `Rule(...)` construction still works
- top-level `build_application_rule(...)` returns `ApplicationRule`

### 5.5 M-Class Trigger Analysis

| Trigger | Result |
|---|---|
| Public API naming | YES: SDK top-level symbols change |
| Public API rename pressure | YES: `Rule` final meaning is load-bearing |
| Cross-commitment question | YES: TPQ-2 locks naming path |
| Decision doc required | YES |
| Full L-class audit required | NO: implementation is a narrow export/docs/test patch after decision lock |

## 6. Boundaries And Invariants

- `factgraph.sdk.Rule` remains legacy-compatible in this slice.
- `factgraph.sdk.LegacyRule` is exactly the current legacy `sdk.dsl.Rule`.
- `factgraph.sdk.ApplicationRule` is exactly `factgraph.application.protocol.Rule`.
- `factgraph.sdk.dsl.Rule` remains unchanged.
- `factgraph.sdk.dsl.build_application_rule` remains unchanged.
- Top-level `build_application_rule` is an alias, not a wrapper.
- No adapter, core, application protocol, or aggregate implementation changes occur.
- The decision doc is the canonical record for TPQ-2 until a later decision supersedes it.
- Implementation cannot start until the decision doc is reviewed and accepted.

## 7. Acceptance

- Decision doc exists and reaches accepted status before implementation.
- SDK top-level export tests pass.
- Existing legacy SDK rule tests continue to pass.
- T1.1 / T1.2 application rule tests continue to pass.
- T2.1 / T2.2 / T2.3a / T2.3b / T2.3c / T2.3d targeted non-regression suites continue to pass where relevant.
- SDK docs mention the staged transition and do not claim `factgraph.sdk.Rule` has already flipped.
- `git diff` shows no changes under `src/factgraph/adapters/`, `src/factgraph/core/`, or `src/factgraph/application/protocol/rule.py`.
- Sacred `master` remains unchanged.
- Dirty set remains preserved.

## 8. Implementation Plan

1. Record M-class G7 precondition in the audit log:
   - current `factgraph.sdk.Rule` identity
   - current `factgraph.sdk.dsl.Rule` identity
   - current application `Rule` identity
   - current top-level absence of `ApplicationRule` / `LegacyRule` / `build_application_rule`
   - decision doc status accepted
2. Add top-level SDK aliases in `src/factgraph/sdk/__init__.py`.
3. Add focused tests for alias identity and top-level bridge access.
4. Update SDK docs.
5. Run targeted tests.
6. Run ruff on touched source/tests.
7. Fill §10 Outcome and mark blueprint implemented.
8. Archive blueprint pair and decision doc.

## 9. Docs To Update

- `src/factgraph/sdk/docs/04_api_surface.en.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- potentially `src/factgraph/sdk/docs/00_user_guide.en.md` if it currently implies top-level `Rule` final semantics

## 10. Outcome

Pending implementation.
