# Task Blueprint: FactGraph complete public SDK docstring surface

- Status: implemented
- Created: 2026-08-15
- Last Updated: 2026-08-15
- Supersedes:
  - [2026-08-15_factgraph-sdk-docstrings.md](./2026-08-15_factgraph-sdk-docstrings.md)
- Audit Log:
  - [2026-08-15_factgraph-sdk-docstrings-complete-surface.audit.md](./2026-08-15_factgraph-sdk-docstrings-complete-surface.audit.md)

## 1. Problem

The first docstring slice tested representative SDK entry points but did not
inventory every exported class member. ``factgraph.sdk.__all__`` contains 208
names and its exported classes expose 312 public methods/properties; the first
complete census found 155 members with no docstring and 46 with only a terse
single-line description.

## 2. Goal

Make the complete reachable public SDK surface discoverable through
``help(...)`` and IDE inspection, including Query/bind/select, lifecycle and
namespace managers, exported protocol/result objects, compatibility APIs and
Product V2 builders/views.

## 3. Scope

- Every name in ``factgraph.sdk.__all__``.
- Every public method/property exposed by an exported SDK class.
- Every public method/property reachable through ``FactGraph`` namespaces.
- Google-style sections for behavioral functions; concise semantic docstrings
  are sufficient for immutable DTO properties and wire helpers.

Private helpers and non-exported lower-layer objects remain out of scope unless
they are the concrete type returned through a public SDK namespace.

## 4. Acceptance

- [x] Census test reports no missing top-level export docstrings.
- [x] Census test reports no missing public member/property docstrings.
- [x] Query construction and all terminals are explicitly covered.
- [x] FactGraph namespace objects are explicitly covered.
- [x] Full application + SDK regression, Ruff, focused mypy and diff-check pass.
- [x] Direct/staged Product builders, the Query-to-run chain, Outcome/Explain,
      and Database ownership methods have workflow-level Google sections.
- [x] The complete Product notebook executes durable create/load and
      caller-owned Database attach paths, not only an in-memory fixture.

## 5. Outcome / Deviations

The initial complete census covers 208 top-level exports (182 classes, 17 functions and
9 exported values), 312 exported-class public method/property occurrences and
52 concrete ``FactGraph`` namespace member occurrences. All three inventories
report zero missing docstrings, and generated dataclass signature-only class
documentation is rejected by the test.

Verification completed with 782 application/SDK tests plus 816 subtests,
Ruff check, focused mypy and ``git diff --check``. The repository still has
pre-existing formatter debt in several older protocol/SDK modules, and
``sdk/schema.py`` retains two pre-existing dynamic-metaclass mypy diagnostics;
neither was introduced or expanded by this documentation-only slice.

The task was reopened after user review: a non-empty docstring is not a
sufficient discoverability contract. The corrective slice follows the actual
product journey from connection ownership through direct/staged authoring,
Query planning and invocation execution to structured Outcome/Explain/replay.
It also includes returned concrete types such as
``ProductEvaluationInvocationV2`` even though they are not members of
``factgraph.sdk.__all__``.

The corrective implementation now pins direct and staged Product authoring,
Scenario/profile build, every Query terminal, V2 invocation ``run``, explicit
row Explain targeting, Outcome/Explain/replay, and Database
create/open/load/attach/close/head ownership contracts. The complete Product
notebook executes 15 code cells against real durable and caller-owned Database
workspaces before cleaning its temporary directories.

Final verification completed with 783 application/SDK tests plus 838
subtests. The focused docstring/quickstart cohort reports 7 tests plus 656
subtests; Ruff check, focused mypy, focused formatter check and
``git diff --check`` pass.

A final IDE-hover audit found that the graph-scoped Product methods still
returned ``Any`` in ``SDKStore`` annotations. Their runtime docstrings existed,
but language servers lost the fluent type immediately after
``fg.policy_builder(...)``. The public methods now return concrete
``RuleBuilder`` / ``FunctionBuilder`` / ``PolicyBuilder`` / Product asset /
``ScenarioBuilderV2`` / ``EvaluationQueryBuilderV1`` types, and Query planning
returns the concrete V1/V2 invocation union. A regression rejects ``Any`` on
all of these fluent entry points. Final verification after this correction is
784 tests plus 853 subtests.
