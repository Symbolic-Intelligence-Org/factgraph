# Q6B Decision: EvaluationRun bundle capture before replay

- Status: adopted
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: design constraint for the F4B1 implementation slice only.
- Inputs:
  - 2026-08-12 user authorization to continue after the independent F4A CLEAR review
  - Q6A / F4A identity-only Run anchors
  - 2026-08-12 three-way read-only F4B snapshot, Explain and red-team audit
- Outputs / Downstream:
  - [`2026-08-12_factgraph-evaluation-run-bundle-capture.md`](../../../blueprints/archive/2026-08-12_factgraph-evaluation-run-bundle-capture.md)
  - F4B2 isolated replay verification
  - F4B3 detached inner Explain
  - F4C Policy-aware explanation overlay
- Branch: `codex/v0.3.0-f4b-evaluation-run-replay-2026-08-12`
- Base: `b7eea261`

## 1. Problem

F4A deliberately records only Run identity. Its view digest and assertion-id
inventory do not contain the facts, query values, executable plan or support
needed to reproduce an old execution. Calling the current Store with those
digests would silently combine an old Run identity with current facts and is
not replay.

Three further operations must remain distinct:

1. detached playback: decode and inspect captured rows and support without an evaluator;
2. replay verification: execute captured inputs in an isolated runtime and compare semantic results;
3. rerun: resolve current Policy/facts/config and create a new ordinary Run.

The bundle contract must exist before replay so that replay does not define its
own incomplete snapshot semantics by accident.

## 2. Decision

### 2.1 Split F4B into three narrow slices

- **F4B1** ships opt-in, atomic `EvaluationRunBundleV0` capture, strict canonical
  codec and detached inspection only.
- **F4B2** consumes only a decoded F4B1 bundle, runs the captured native plan
  against its captured effective relation in isolation, and emits a new
  verification record. It never recreates the old random Run identity.
- **F4B3** produces detached single-row inner `EvidenceGraph` from the same
  bundle. F4C alone maps that evidence onto authored Policy topology.

F4B1 therefore states `replay_availability=not_implemented`; neither its name,
digest nor successful decode is a replay claim.

### 2.2 Capture is opt-in and synchronous with execution

The narrow SDK surface is:

```python
result = fg.eval.evaluate(compiled_query, capture="run_bundle_v0")
bundle = result.run_bundle
payload = bundle.to_bytes()  # or the equivalent strict codec function
```

Default Query evaluation still produces only the F4A identity anchor. A Run
without capture cannot be retroactively upgraded by reading the later Store.

For a captured Run, native evaluation projects one effective relation and the
evaluator and capture path consume that same immutable projection. The live
view guard still runs before and after execution. A concurrent change rejects
the whole result and bundle.

### 2.3 F4B1 captures evaluator input, not a general historical database

The bundle captures the complete relation for every predicate in the exact
materialized plan dependency set, including explicit empty relations. The
evaluator itself consumes that same reduced relation; capture must never filter
an already-different evaluator input. Each row retains its assertion witness,
canonical typed tuple and observed relation order. It also captures:

- full canonical schema IR bytes and schema identity digest;
- actual normalized Query binding values, selections and projection head;
- a strict DTO/codec representation of the exact materialized native plan;
- F4A target, PolicyStructure, lineage and occurrence-qualified Rule pins;
- typed result rows, semantic-row multiset and zero-row summary;
- exactly one canonical native `ProofReceipt` emitted for each positive row;
  its binding, selected-branch structure and witnesses must reconstruct from
  the captured plan/relation, and every witness resolves uniquely there. This
  is structural playback validation, not re-evaluation of non-fact truth;
  isolated logical verification belongs to F4B2;
- native/config-none/premise-empty and runtime/codec/order pins.

The effective relation is post-active/revocation/chosen/premise projection. It
is sufficient to reproduce the captured execution input, but it is not a raw
Ledger snapshot. In particular it cannot make an older single-cardinality value
reappear after a future What-if deletion. F5 must use a richer base snapshot for
that scenario.

### 2.4 Strictness, privacy and trust boundary

- The codec is versioned, canonical, bounded and fail-closed on unknown or
  missing fields, duplicate JSON keys, unsupported tagged values, digest
  mismatch or cross-bundle splice.
- V0 ceilings are 1 MiB encoded input, 128 predicates, 20,000 projected facts,
  1,000 result rows, 64 values per fact/row and 64 nested JSON levels.
- Pickle, `repr`, importable Python object identity, callbacks, Store/DB paths,
  registry lookup and `latest` are forbidden.
- SHA-256 establishes content integrity only. The bundle explicitly reports
  authenticity as unverified; tenant authorization, signatures/MAC, encryption,
  retention and erasure belong to the Meander/custody boundary.
- Effective facts and Query/result values are cleartext sensitive data. Capture
  is opt-in and subject to explicit predicate/row/byte ceilings. Exceeding a
  limit refuses capture rather than producing a partial replay candidate.

### 2.5 Native v0 boundary

F4B1 accepts only successful `CompiledEvaluationQueryV0` execution with:

- `engine="native"`;
- `config=None`;
- empty premise exclusions, allowances and blocks;
- no RuleRegistry, external Operator, network access, Action or Scenario.

Missing runtime build pins remain visible. Until F4B2 defines and satisfies
runtime compatibility, the bundle must not claim exact cross-version replay.

## 3. Non-scope

- Running the evaluator from decoded material, semantic comparison or any
  `replay()` method.
- Eager or detached `Explanation`, Policy-node verdict aggregation, UI overlay
  or `ProvenanceIndex`.
- General Database snapshots, historical Ledger reconstruction, What-if,
  premises, expectations, completeness, limits/pagination or truth from zero rows.
- Non-native engines, Rule registry calls, Operators and Actions.
- Run repository, tenant store, signing, encryption or retention service.

## 4. Stop Conditions

Stop and split if implementation requires post-hoc reads from the Store,
captures only digests/witnesses rather than complete dependency relations,
cannot distinguish an empty relation from a missing artifact, uses a loose
Python serialization, leaks callbacks/Store objects, accepts an unsupported
execution profile, interprets zero rows as false, calls playback replay, or
expands into F4C/F5 semantics.

## 5. Consequences

F4B1 is already useful as a portable audit record: old rows and their captured
support remain inspectable after the originating Store changes or disappears.
It deliberately does not yet prove deterministic re-execution. F4B2 receives a
small, explicit and adversarially testable input contract rather than needing
to infer one from live SDK behavior.

## 6. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | proposed | F4B entry audit completed | Snapshot, Explain and red-team audits independently rejected digest-only pseudo replay. |
| 2026-08-12 | adopted | User authorized continuation after F4A CLEAR | F4B is split into capture/codec, isolated verification and detached Explain; this decision authorizes F4B1 only. |
| 2026-08-12 | clarified | ProofReceipt validation boundary made explicit | F4B1 validates canonical structural reconstruction and witness resolution; it does not execute non-fact truth verification reserved for F4B2. |
| 2026-08-12 | verified | User-side independent review returned CLEAR | The implementation passed 480 application/SDK tests plus 108 subtests, static checks and approximately 40 independent adversarial checks with zero P0/P1/P2. F4B1 closes without consuming F4B2/F4B3/F4C. |
