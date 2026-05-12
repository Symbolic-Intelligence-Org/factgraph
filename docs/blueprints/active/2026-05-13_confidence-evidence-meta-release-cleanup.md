# Task Blueprint: Confidence / Evidence Meta Release Cleanup

- Status: scoped
- Created: 2026-05-13
- Last Updated: 2026-05-13
- Related Modules:
  - `src/kernel/core/derivation`
  - `src/kernel/core/evidence`
  - `src/kernel/core/store`
  - `src/kernel/adapters/problog`
  - `src/kernel/adapters/pyreason`
  - `src/service`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
- Audit Log:
  - [2026-05-13_confidence-evidence-meta-release-cleanup.audit.md](./2026-05-13_confidence-evidence-meta-release-cleanup.audit.md)

## 1. Problem

The pre-release audit found that legacy candidate-level `confidence` and
`confidence_kind` have become part of the default public and persisted
evidence surface:

`CandidateSet.confidence/confidence_kind` -> derivation accept assertion meta
-> shared annotations -> duplicate checks, ProbLog export, evidence trees,
certainty summaries, static UI, audit surfaces, docs, and tests.

This makes an internal/legacy confidence carrier look like canonical assertion
metadata and can change runtime behavior such as duplicate detection and
probabilistic export.

## 2. Goals

- Stop default assertion writes from persisting candidate confidence fields into
  claim meta.
- Stop generic `meta.confidence` from becoming a default shared derived
  annotation.
- Keep adapter-native uncertainty diagnostics in adapter namespaces.
- Keep old candidate fields as internal/legacy carriers only for this release
  cleanup.
- Preserve backward compatibility for clients that still echo old candidate
  fields into accept calls.

## 3. Non-goals

- Do not redesign confidence, certainty, or probability modeling.
- Do not remove `CandidateSet.confidence` or `CandidateSet.confidence_kind`
  from internal dataclasses.
- Do not remove adapter-native annotations such as
  `problog/semantic/probability` or `pyreason/semantic/bound_*`.
- Do not redesign read-time display confidence aggregation.

## 4. Current Context

- Current implementation entry points:
  - `src/kernel/core/derivation/accept.py`
  - `src/kernel/core/evidence/write_protocol.py`
  - `src/service/runtime_v1.py`
  - `src/kernel/adapters/problog/problog_export.py`
  - `src/kernel/adapters/pyreason/session.py`
  - `src/kernel/core/store/_candidate_evidence_tree.py`
- Current constraints:
  - Public runtime accept must tolerate old candidate DTOs.
  - Release-facing APIs should not stabilize old confidence fields as default
    candidate or assertion semantics.
  - Adapter diagnostics can remain available through explicit adapter lanes.
- Current related historical material:
  - Recent confidence/evidence audit discussion in the current session.

## 5. Proposed Shape

The release surface treats candidates as value + identity + support/evidence.
`confidence` and `confidence_kind` remain internal compatibility fields, but
default public DTOs, assertion meta writes, evidence tree carriers, and ProbLog
export no longer consume generic confidence metadata as semantic uncertainty.

Adapter-native uncertainty remains in adapter namespaces. Future confidence
redesign can introduce a new explicit public contract without inheriting this
legacy propagation path.

### 5.1 Behavior Matrix

| Module | Old behavior | New behavior |
| --- | --- | --- |
| `core/derivation/accept.py` | Accepted candidates wrote `candidate.confidence` / `confidence_kind` into assertion meta by default. | Accept still parses legacy candidate fields, but default assertion meta omits generic candidate confidence fields. |
| `core/evidence/write_protocol.py` | Generic `meta.confidence` could become shared derived annotation and participate in duplicate/evidence projection. | Generic `meta.confidence` is not a default shared semantic annotation. Adapter-native semantic annotations remain explicit. |
| `service/runtime_v1.py` | Runtime candidate DTOs could expose legacy confidence fields by default and accept echoed values. | Runtime DTOs do not expose legacy confidence fields by default; accept remains parse-compatible with old echoed fields. |
| `adapters/problog/problog_export.py` | ProbLog export could fall back to generic `meta.confidence` as probability semantics. | ProbLog probability export uses adapter-native ProbLog semantic annotations only. |
| `adapters/pyreason/session.py` | PyReason input could derive bounds from generic `meta.confidence`. | PyReason bound diagnostics use adapter-native PyReason semantic annotations only. |
| `core/store/_candidate_evidence_tree.py` | Evidence/certainty display could surface generic assertion `meta.confidence`. | Evidence/certainty display does not treat generic assertion `meta.confidence` as canonical semantics. |

### 5.2 Compatibility Contract

Old accept payloads remain parseable when they include `confidence` or
`confidence_kind`. The fields may still hydrate the internal
`CandidateSet.confidence` / `confidence_kind` legacy carrier, but they are not
propagated into assertion meta, shared annotations, adapter export, evidence
tree display, or static UI default semantics.

This means candidates that differ only by legacy confidence fields collapse to
the same default semantic candidate for duplicate detection. That behavior
change is intentional release cleanup.

Candidates that previously relied on generic `meta.confidence` to produce
ProbLog probability or PyReason bound output will no longer produce
adapter-specific semantic output from that generic key. Adapter output must use
the explicit adapter-native semantic lanes.

## 6. Boundaries And Invariants

- Must keep old accept payloads parseable when they include `confidence` or
  `confidence_kind`; the values remain internal compatibility carriers only.
- Must not persist candidate confidence into assertion meta during accept.
- Must not let legacy confidence differences affect duplicate detection.
- Must preserve ProbLog adapter probability annotations as the semantic source
  for probabilistic export.
- Must preserve PyReason bound annotations as adapter diagnostics.
- Must not rewrite unrelated docs, notebooks, or pending user changes.

## 7. Acceptance

- [ ] Code behavior satisfies the task goals
- [ ] No scope crosses the boundaries above
- [ ] Affected module docs are synchronized
- [ ] If a durable docs entry is added, `docs/README.md` is updated

## 8. Implementation Plan

1. Update derivation accept and write protocol so candidate confidence fields
   are not persisted or projected into shared annotations.
2. Update runtime candidate serialization, accept parsing, and candidate
   inventory so public DTOs do not expose legacy confidence fields by default
   while accepting old echoed fields.
3. Update ProbLog and PyReason adapters to avoid generic `meta.confidence`
   as a semantic fallback or auto-filled shared metadata.
4. Update evidence tree and static UI carriers so generic assertion
   `meta.confidence` is not used for default evidence/certainty display.
5. Update focused tests and module docs to encode the release contract.

G1 baseline is expected to be smaller than the schema lifecycle slices: roughly
15-25 tests covering each matrix row, legacy parse compatibility, duplicate
detection, adapter fallback removal, static/evidence display behavior, and
preservation guards for adapter-native semantics.

## 9. Docs To Update

- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/03_rules_and_inferences.en.md`
- `src/kernel/adapters/docs/02_problog_adapter.md`
- `src/kernel/adapters/docs/03_pyreason_adapter.md`
- `src/service/docs/02_runtime_sessions.md`
- `src/service/docs/03_runtime_queries_policy.md`

## 10. Outcome / Deviations

Task completion notes will be filled after implementation and verification.
