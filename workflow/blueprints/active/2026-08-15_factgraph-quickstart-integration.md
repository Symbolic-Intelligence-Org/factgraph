# Task Blueprint: FactGraph quickstart integration

- Status: implemented
- Created: 2026-08-15
- Last Updated: 2026-08-15
- Related Modules:
  - `src/factgraph/sdk`
  - `src/factgraph/application`
- Related Docs:
  - `docs/README.md`
  - `docs/quickstart/README.md`
  - `docs/quickstart/product_workflow_v2.md`
- Audit Log:
  - [2026-08-15_factgraph-quickstart-integration.audit.md](./2026-08-15_factgraph-quickstart-integration.audit.md)

## 1. Problem

The implementation and module docs covered the Q19/Q20/Q21 Product surface,
but the repository README and public quickstart still taught mostly legacy
schema/evaluation APIs. There was no ordered quickstart index or single
current tutorial connecting Product Rule, Function and Policy authoring to
Query, Scenario, execution profiles, structured Result/Explain and replay.

## 2. Goals

- Make Product V2 the explicit default teaching path for new code.
- Preserve and clearly label V0/V1 compatibility documentation.
- Add one complete public-SDK workflow and an executable drift test.
- Integrate Product concepts into the existing Rule, engine, evidence, data,
  lifecycle and capability chapters.
- Remove stale public links and obsolete unlabelled API examples.

## 3. Non-goals

- Remove or rewrite legacy V0/V1 contracts.
- Change runtime behavior or public API.
- Claim an EvidenceGraph where Product V2 only captures structured Explain
  data.
- Turn workspace persistence into EvaluationRun persistence.

## 4. Acceptance

- [x] Root README uses the current schema/read/write API and routes to an
      ordered quickstart index.
- [x] A complete Product V2 tutorial covers Rule/Function/Policy, Query,
      Scenario metadata, profiles, Result/Explain, replay, probability and
      WeightedChoice.
- [x] Existing quickstart chapters explain current/legacy boundaries rather
      than presenting both generations as interchangeable.
- [x] Scenario metadata, source/evidence, workspace/run persistence and
      capability boundaries are explicit.
- [x] All local Markdown links in root/docs/SDK docs resolve.
- [x] The documented core product path runs as a public SDK test.

## 5. Outcome

The public documentation now has one recommended path:
`README -> docs/quickstart/README -> product_workflow_v2.md`, backed by the
fully executed Product V2 notebook and `test_quickstart_product_v2.py`.
Reference chapters retain the detailed legacy contracts while leading with
the current Product V2 surface and its fail-closed boundaries.

Verification on 2026-08-15:

- local Markdown link validation covered the root README, all public docs and
  SDK docs with zero missing targets;
- focused Product/quickstart regression: 69 tests + 7 subtests passed;
- new quickstart smoke test: 1 passed;
- Ruff check/format for the new test and `git diff --check` passed.
