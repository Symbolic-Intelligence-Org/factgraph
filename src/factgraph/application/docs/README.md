# FactPy Application Docs

This directory records the current implementation contract for
`src/factgraph/application`. `application` is the canonical Python
runtime authority on top of `core`; `sdk` is responsible for the
Python product surface, DSL authoring, and outward facade
compatibility.

> **Audience note**
>
> If you are writing ordinary Python product code and want to use
> `Entity` / `Field` / `Identity` classes, the Query DSL, snapshots,
> batches, or user-facing exceptions, read `src/factgraph/sdk/docs/`
> first and start from `factgraph.sdk`.
>
> This directory targets integration / automation / pipeline / RPC
> bridge authors: callers who may only hold JSON-like payloads,
> schema identity strings, field paths, and error DTOs, and who
> should not depend on SDK descriptors or Python DSL objects. What
> this directory records is the Layer 2 runtime contract beneath
> the SDK.

## Current documents

- `src/factgraph/application/docs/01_overview_en.md`
  - English overview of the application module.
- `src/factgraph/application/docs/rule.md`
  - Application-layer Rule DTO contract. Stores core rule AST atoms directly
    and remains below SDK ergonomic authoring. Also records the optional
    in-process semantic-port binding and authored occurrence/direct-port
    address space used by managed Rule consumers, the head-independent managed
    Policy v0 compiler and structural-lineage boundary, and the compile-only
    `EvaluationQuery` typed bind/select projection contract plus opt-in,
    detached `EvaluationRunBundleV0` capture/codec, isolated verification,
    single-row evidence playback, and readonly `PolicyExplanationViewV0`
    projection semantics; also records the narrow replacement-only
    `ScenarioFieldSubstitutionV0` and atomic
    `ScenarioFieldSubstitutionSetV0` boundaries.
- `src/factgraph/application/explain/docs/README.md`
  - Paths-model evidence tree types (`EvidenceGraph`, `EvidenceTree`,
    `EvidenceRule`, `EvidenceAtom`, `Certainty`, `AtomForm`, `Verdict`) and
    native prober (`probe_native`), plus the `RuleStructure` static projection
    contract and node-identity alignment with `EvidenceGraph`. Canonical type
    site for the explain layer; `factgraph.audit.evidence_graph` re-exports
    from here.
- `src/factgraph/application/protocol/docs/README.md`
  - `EvaluateResult` / `EvaluateRow` / `Explanation` / `ResultFingerprint`
    protocol contract; `EvaluateRow.explain()` dispatch; S5 evidence invariant
    (`{passed,failed} ↔ evidence is not None`); ProbLog/PyReason rich evidence
    builder dispatch; `walk_evidence` text renderer; optional F4A Run anchors
    and strict F4B1 detached bundle attachment.
- `src/factgraph/application/walker/docs/README.md`
  - Current implementation contract for the application-layer walker
    module.
- `src/factgraph/application/schema_mutation_runtime.py`
  - Additive entity and non-identity field extension validation and transition
    planning used by `fg.schema.register(...)`, `fg.schema.extend(...)`, and
    `fg.schema.apply(...)`; application-first runtime module, documented in the
    application overview.

## Conventions

- Documents in this directory reflect current implementation
  behavior, not standalone design drafts.
- When adding or adjusting public `application` entry points, update
  the corresponding doc and tests in the same change.
- The application protocol does not accept SDK facade objects, SDK
  `Field` descriptors, or SDK DSL objects; SDK is responsible for
  lowering / adapting ergonomic inputs into application runtime DTOs.
