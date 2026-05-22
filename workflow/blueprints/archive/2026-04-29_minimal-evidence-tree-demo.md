# Task Blueprint: Minimal Evidence Tree Demo

- Status: implemented
- Created: 2026-04-29
- Last Updated: 2026-04-29
- Related Modules:
  - `src/kernel/sdk`
  - `src/kernel/core/store`
- Related Docs:
  - [examples/README.md](../../../examples/README.md)
  - [src/kernel/sdk/docs/03_rules_and_derivations.md](../../../src/kernel/sdk/docs/03_rules_and_derivations.md)
  - [src/kernel/core/docs/01_architecture.md](../../../src/kernel/core/docs/01_architecture.md)
- Audit Log:
  - [2026-04-29_minimal-evidence-tree-demo.audit.md](./2026-04-29_minimal-evidence-tree-demo.audit.md)

## 1. Problem

The public examples currently jump from SDK basics and derivations to larger compliance or multi-engine walkthroughs. There is no meeting-friendly, rigorous example that moves directly from source-backed definitions to a candidate evidence tree and explains why that tree matters.

The requested demo must not use toy/fake business facts. It should keep the scenario simple while preserving the full reasoning flow: define schema, record source-backed facts, define a rule/derivation, evaluate, and render the evidence tree.

## 2. Goals

- Add a new `examples/03_*` notebook focused on the shortest credible path from definitions to evidence tree.
- Use public regulatory source anchors rather than fabricated entity facts.
- Show the candidate evidence tree as the central artifact, including rule-reference recursion and source-backed assertion leaves.
- Explain the tree's role in reviewer terms: derived conclusion, rule path, supporting facts, and source locations.
- Keep the notebook runnable without external engines, network calls, or LLM calls.

## 3. Non-goals

- No runtime, SDK, store, service, or evidence-tree schema changes.
- No real compliance decision about a financial entity.
- No LLM extraction or PDF download.
- No replacement for the comprehensive multi-engine notebook `07`.

## 4. Current Context

- Current implementation entrance:
  - `SDKStore.from_schema_classes(...)`
  - SDK `Rule`, `RuleRef`, and `Derivation`
  - `Store.get_candidate_support_digest(...)`
  - `Store.explain_support(...)`
  - `build_candidate_evidence_tree(...)`
  - `summarize_candidate_evidence_tree_dict(...)`
  - `render_candidate_evidence_tree_narrative(...)`
- Current known constraints:
  - Notebook examples are the canonical public example shape.
  - Evidence tree entrypoint is candidate-oriented and uses the candidate support digest.
  - Full runtime HTML is available elsewhere; this demo should keep the visible path compact.
- Current related historical blueprints:
  - Native candidate evidence tree and evidence graph archive entries establish the current tree contract.

## 5. Proposed Shape

Add `examples/03_dora_minimal_evidence_tree.ipynb`.

The notebook uses DORA/EUR-Lex source anchors:

- Regulation (EU) 2022/2554 Article 5(1)
- Regulation (EU) 2022/2554 Article 8(1)
- Delegated Regulation (EU) 2024/1774 Article 5(1)

The rule/derivation derives a narrow review finding: source-backed DORA ICT risk-management anchors are present. The conclusion is intentionally a review artifact, not a statement of entity compliance.

The evidence tree is printed in a reviewer-friendly form and summarized with the deterministic summary/narrative helpers.

## 6. Boundaries And Invariants

- Must preserve existing notebook numbering and mention the new `03` in the learning path.
- Must not require external engine CLIs, API keys, or network access at notebook runtime.
- Must not use invented people/company compliance facts.
- Must keep legal-source text paraphrased; source URLs and article identifiers carry provenance.
- Must not change public behavior or contracts.

## 7. Acceptance

- [x] Notebook runs from a clean kernel with `PYTHONPATH` insertion used by existing examples.
- [x] Notebook produces exactly one candidate for the review finding.
- [x] Evidence tree contains a rule-reference section and source-backed witness leaves.
- [x] Examples README points to the new notebook and next-step flow.
- [x] No module docs update is required because implementation behavior is unchanged.

## 8. Implementation Plan

1. Add the scoped blueprint and audit log before editing examples.
2. Add the new notebook with source-backed DORA anchors and compact tree rendering helpers.
3. Update `examples/README.md` learning path and prerequisites.
4. Execute the notebook or equivalent code path locally and verify the candidate/tree summary.
5. Complete the blueprint outcome and archive the blueprint pair.

## 9. Docs To Update

- `examples/README.md`
- Module docs are not changed because this is an examples-only addition over existing SDK/core behavior.

## 10. Outcome / Deviations

- 最终落地结果：Added `examples/03_dora_minimal_evidence_tree.ipynb`, updated `examples/README.md`, and retargeted notebook `02` next-step links to the new minimal evidence-tree bridge.
- 与 blueprint 不同的地方：The rule was tightened to include instrument and article facts in addition to obligation and source URL so the printed evidence tree exposes the legal source location directly.
- 为什么会有这些调整：Meeting review needs visible article-level provenance in the tree, not only source URLs.
- 归档说明：Implementation and verification completed; archive this blueprint pair under `docs/blueprints/archive/`.
