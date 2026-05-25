# D17 Decision: T5 Result / Row DTO Foundation

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks public result / row DTO ownership, field surfaces, and CandidateSet mapping principles.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md` Q2, Q4, F1, F2, F6, F11, and §6 C64-C65 triage.
  - D16 `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md` §4.1, §4.5, §4.7, and §4.8.
  - Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §5.8.2, C64, and C65.
  - Shipped `src/factgraph/sdk/__init__.py:28-56` and `:88-108`.
  - Shipped `src/factgraph/core/derivation/candidates.py:13-70`.
  - Shipped `src/factgraph/application/protocol/derivation.py:21-126`.
  - Shipped `src/factgraph/application/protocol/derivation_check.py:62-160`.
  - Shipped `src/factgraph/core/store/_support.py:96-162`.
  - Shipped `src/factgraph/core/store/ledger.py:21-27`.
- Outputs / Downstream:
  - D18 return-shape transition strategy.
  - D19 digest source-of-truth.
  - D20 explanation envelope and Check/Diagnose/EvidenceGraph integration.
  - D21 `row.close()` and closed-head gate.
  - D24 T1.3 final SDK `Rule` flip.
  - Stage 3 T5 synthesis and T5 Core implementation blueprints.
- Related:
  - `workflow/design/decisions/active/2026-05-25_t5-d16-tranche-boundary.md`
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`
  - `workflow/design/decisions/active/2026-05-25_t3-later-d10-evaluation-result-evidence-boundary.md`
- Branch: `v0.2.0-t5-result-evidence-explain-audit-2026-05-25`
- Depends on: D16 reviewed clean v2.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

Parent §5.8.2 replaces public evaluation rows with a Rainbird-style row-centric model:

- `EvaluateResult` is the evaluation-session envelope.
- `EvaluateRow` is the result fact / decision claim.
- `Claim` is the first-class explained fact.
- `EvidenceRef` is row-local opaque audit/ref plumbing.
- `DetachedRowError` is raised when row methods need a live result resolver but the row is detached.

Stage 1 audit found that shipped `fg.eval.evaluate(...)` still returns `list[CandidateSet]`, and that `CandidateSet` is not an `EvaluateRow`. `CandidateSet` carries candidate/runtime fields such as derivation id, target, payload, support digest/kind, candidate id/key, state, and confidence. It does not carry `claim`, `evidence_ref`, `_result_resolver`, live/detached behavior, `row.explain()`, `row.close()`, or the proposed row/result digest fields.

D16 split T5 into Core and Semantics lanes. D17 is a T5 Core decision. It locks the DTO foundation without deciding return-shape migration mechanics, digest formulas, `Explanation` envelope fields, `row.close()` behavior, why-not, or final SDK `Rule` naming.

## 2. Scope

This decision locks:

- public DTO ownership and import/export paths;
- which DTOs are public versus private;
- field surfaces for `EvaluateResult`, `EvaluateRow`, `Claim`, and `EvidenceRef`;
- the `DetachedRowError` boundary;
- live/detached row behavior at the DTO level;
- `CandidateSet` fate and mapping principles;
- the storage-ledger `Claim` name collision boundary;
- generic head Rule naming discipline before D24.

## 3. Non-Scope

This decision does not lock:

- whether `fg.eval.evaluate(...)` changes return shape through hard-cut or additive transition; D18 owns it;
- exact digest formulas or source-of-truth fields; D19 owns them;
- `Explanation` field matrix, failure classes, and EvidenceGraph integration; D20 owns them;
- exact `row.explain()` resolver logic; D20 owns it;
- exact `row.close()` closed-head construction; D21 owns it;
- why-not disposition; D22 owns it;
- old API hard-cut mechanics; D23 owns them;
- final SDK public `Rule` naming; D24 owns it;
- evaluate/explain semantics consistency; D25 owns it;
- C73-C78 semantics wrapper details; D26 owns them;
- implementation slice order.

## 4. Decision

### 4.1 Application protocol owns the DTO definitions; SDK re-exports them

The authoritative definitions for T5 result DTOs live in `factgraph.application.protocol`, not in `factgraph.core`, not in `factgraph.sdk.store`, and not in a new top-level `factgraph.eval` package.

Implementation may use one or more application-protocol modules, but the public import surface must include:

```python
from factgraph.application.protocol import EvaluateResult, EvaluateRow, Claim, EvidenceRef, DetachedRowError
from factgraph.sdk import EvaluateResult, EvaluateRow, Claim, EvidenceRef, DetachedRowError
```

`Explanation` is also a public T5 Core DTO, but D20 owns its field surface. D17 reserves the same public export requirement for `Explanation` once D20 adopts it:

```python
from factgraph.application.protocol import Explanation
from factgraph.sdk import Explanation
```

This follows the existing pattern where application protocol owns DTOs and SDK re-exports selected public types.

### 4.2 Public DTOs are narrow; support carriers and resolver plumbing remain private

Public T5 Core DTOs:

- `EvaluateResult`;
- `EvaluateRow`;
- `Claim`;
- `EvidenceRef`;
- `DetachedRowError`;
- `Explanation` after D20.

Private or internal-only carriers:

- `CandidateSet`;
- `SupportArtifact`;
- `ProvenanceEnvelope`;
- `EvidenceEnvelope`;
- T3/T4 private RuleExpr lowering traces;
- T4.2 head-port link materializations;
- result resolver callables;
- evidence lookup registries or caches.

Public rows may carry `EvidenceRef`, but they must not expose `SupportArtifact`, `ProvenanceEnvelope`, or adapter-native evidence payloads directly.

### 4.3 `EvaluateRow` has exactly six canonical data fields plus one non-data resolver

D17 adopts the parent Wave 1 row field set:

```python
@dataclass(frozen=True)
class EvaluateRow:
    row_id: str
    bindings: Mapping[str, object]
    claim: Claim
    raw_kind: Literal["probabilistic", "possibilistic"] | None = None
    bound: tuple[float, float] | None = None
    evidence_ref: EvidenceRef
    _result_resolver: Callable[[], EvaluateResult] | None = field(
        default=None,
        repr=False,
        compare=False,
        hash=False,
    )
```

Field rules:

- `bindings` keys are output column names from the application head Rule, not internal variable names.
- `raw_kind` and `bound` are nullable quantitative fields. D17 only locks the carrier; D25/D26 own semantics consistency and projection behavior.
- `_result_resolver` is non-data plumbing. It must not participate in equality, hash, repr, serialization, row digest, or public JSON.
- `EvaluateRow` has no `status` field. Success rows live in `EvaluateResult`; failure / unsupported / invalid states live in `Explanation`, decided by D20.

### 4.4 `Claim` is a new public eval claim DTO, distinct from ledger `Claim`

The public T5 `Claim` has the parent Wave 1 shape:

```python
@dataclass(frozen=True)
class Claim:
    kind: Literal["fact_triple", "rule_head", "aggregate_result", "projection"]
    name: str
    arguments: Mapping[str, object]
    repr: str
    digest: str
```

This `Claim` is not `src/factgraph/core/store/ledger.py`'s storage-layer `Claim`, which has fields `asrt_id`, `pred_id`, `e_ref`, and `rest_terms`.

D17 keeps the public eval claim in application protocol to avoid exposing ledger row shape as the user-facing explained fact. Implementation must avoid importing or re-exporting the ledger `Claim` under the T5 public `Claim` name.

`Claim.digest` formula belongs to D19. D17 only locks that `EvaluateRow.evidence_ref.fact_digest == EvaluateRow.claim.digest` must become an invariant once `EvidenceRef` is constructed.

### 4.5 `EvidenceRef` is row-local opaque plumbing, not an explain entrypoint

D17 adopts the parent Wave 1 `EvidenceRef` shape:

```python
@dataclass(frozen=True)
class EvidenceRef:
    ref_id: str
    result_id: str
    row_id: str
    fact_digest: str
    closed_head_digest: str
```

`EvidenceRef` is public as row metadata but not as a public explain entrypoint. Users call:

- `row.explain()`;
- `result[i].explain()`;
- advanced `fg.eval.explain(expr, head=closed_head)` after D20.

They do not call `fg.eval.explain(evidence_ref)` and D17 does not add public `explain_ref`.

`EvidenceRef` formulas and stale detection behavior belong to D19/D20. D17 locks only the field surface and invariant:

```python
row.evidence_ref.result_id == result.result_id
row.evidence_ref.row_id == row.row_id
row.evidence_ref.fact_digest == row.claim.digest
```

### 4.6 `EvaluateResult` is the session envelope and shared audit context

D17 adopts the parent Wave 1 result field surface:

```python
@dataclass(frozen=True)
class EvaluateResult:
    result_id: str
    run_id: str
    rows: tuple[EvaluateRow, ...]
    head: object  # application head Rule; D24 owns SDK public naming.
    engine: str
    engine_version: str | None
    adapter_version: str | None
    expr_digest: str
    rule_set_digest: str
    view_snapshot_digest: str
    semantics_digest: str | None
    evaluated_at: object
    result_digest: str
```

Container behavior:

- `__iter__`;
- `__len__`;
- `__getitem__`;
- `first()`;
- `exists()`;
- `count()`.

Rows obtained from an `EvaluateResult` are live rows because they carry resolver plumbing back to the owning result. D17 does not lock resolver implementation details; D20/D21 own explain and close behavior.

D19 owns every digest formula and source-of-truth. D17 only locks that these fields exist on the public session envelope.

### 4.7 `CandidateSet` becomes an internal evaluation artifact, not the public row model

D17 classifies `CandidateSet` as an internal adapter/runtime artifact for T5 Core.

Final public T5 evaluate output must not be `list[CandidateSet]`. D18 decides whether migration is hard-cut or temporarily additive, but D17 locks the final target:

- public users receive `EvaluateResult`;
- public rows are `EvaluateRow`;
- `CandidateSet` may remain in core/runtime code and tests;
- `CandidateSet` may remain importable from its existing internal module;
- SDK should not re-export `CandidateSet` as the new result model.

Mapping principles:

- `CandidateSet.payload` is normalized into `EvaluateRow.bindings` under output column names from the application head Rule.
- `CandidateSet.target`, derivation id/version, and head metadata may inform `Claim.kind`, `Claim.name`, and `Claim.arguments`, but D17 does not lock the full claim-builder algorithm.
- `CandidateSet.confidence` / `confidence_kind` may inform `EvaluateRow.raw_kind` / `bound`; D25/D26 own final semantics consistency.
- `CandidateSet.support_digest`, `support_kind`, candidate id/key, and adapter support payloads feed private resolver / evidence lookup state and `EvidenceRef` construction; they do not become direct public `EvaluateRow` fields.
- `CandidateSet.state` does not become `EvaluateRow.status`; success rows are rows, while failure states belong to `Explanation`.

### 4.8 Live / detached row behavior is part of DTO foundation

`EvaluateRow` has two states:

- **Live**: produced through an `EvaluateResult` container with `_result_resolver` populated.
- **Detached**: manually constructed, deserialized, copied without resolver, or otherwise missing `_result_resolver`.

Required behavior:

- data fields remain readable in both states;
- `row.explain()` and `row.close()` exist on the row class but require a live resolver;
- detached calls raise `DetachedRowError`;
- `DetachedRowError` is a programming error, not an `Explanation.status` or business failure.

D20 owns `row.explain()` result behavior. D21 owns `row.close()` closed-head construction.

### 4.9 D17 uses generic head Rule terminology before D24

Per D16, D17 uses "head Rule" and "application head Rule" instead of locking final SDK public names.

D17 does not decide whether SDK top-level `Rule` will be application `Rule`, whether legacy query `Rule` is renamed, or how `LegacyRule` survives. D24 owns that final flip.

## 5. Rejected Alternatives

### Option A: Define T5 result DTOs only in the SDK layer

- **Why rejected**: Check, Diagnose, WhyNot, RuleExpr inspect, and other public protocol DTOs are application-protocol owned and SDK-reexported. SDK-only definitions would duplicate protocol shape and complicate application runtime tests.

### Option B: Put `EvaluateResult` / `EvaluateRow` in `core.derivation`

- **Why rejected**: Core derivation owns low-level candidate artifacts. T5 result rows are public SDK/application protocol DTOs with explain plumbing and public semantics.

### Option C: Reuse `CandidateSet` as `EvaluateRow`

- **Why rejected**: `CandidateSet` lacks claim, evidence ref, live/detached resolver behavior, and row-centric methods. Mutating it into `EvaluateRow` would blur internal adapter output and public result API.

### Option D: Reuse ledger `Claim` as public T5 `Claim`

- **Why rejected**: ledger `Claim` is storage-shaped (`asrt_id`, `pred_id`, `e_ref`, `rest_terms`). T5 `Claim` is result-fact-shaped (`kind`, `name`, `arguments`, `repr`, `digest`). Reuse would leak storage internals into public explain output.

### Option E: Expose `SupportArtifact` / `ProvenanceEnvelope` directly on rows

- **Why rejected**: T5 wants row-local lightweight evidence refs and `row.explain()` as the main path. Exposing engine support carriers directly would make adapter-native shapes part of public row contract.

### Option F: Add `status` to `EvaluateRow`

- **Why rejected**: Parent design separates result rows from explanation outcomes. Rows represent successful evaluated facts/claims; status and failure classes belong to `Explanation`.

### Option G: Lock `Explanation` fields in D17

- **Why rejected**: D20 owns Explanation envelope, Check/Diagnose integration, EvidenceGraph metadata, and failure classes. D17 only reserves public export ownership.

### Option H: Add a new top-level `factgraph.eval` import package

- **Why rejected**: The shipped public pattern is SDK namespace plus application-protocol DTO exports. A new import package is unnecessary for D17 and would preempt D24 naming and docs decisions.

## 6. Supporting Evidence

- Parent C64 defines `EvaluateRow` with claim/evidence_ref/live resolver and detached behavior.
- Parent C65 defines `EvaluateResult` as frozen evaluation session envelope and shared audit context.
- Stage 1 audit F1/F2 found shipped `evaluate` still returns `list[CandidateSet]` and `CandidateSet` is not an `EvaluateRow`.
- Shipped `CandidateSet` carries candidate/runtime fields but no claim, evidence ref, row resolver, or row methods.
- Shipped SDK exports no `EvaluateResult`, `EvaluateRow`, `Claim`, `EvidenceRef`, `Explanation`, or `DetachedRowError`.
- Shipped ledger already has a storage-layer `Claim`, so D17 must avoid accidental reuse under the public eval `Claim` name.
- D16 requires generic head Rule naming until D24 finalizes the SDK `Rule` flip.

## 7. Consequences

### 7.1 Downstream unblocking

D17 unblocks:

- D18 return-shape strategy, because the final target result type is now fixed.
- D19 digest decisions, because the fields requiring formulas are now named.
- D20 explanation envelope, because row resolver and EvidenceRef boundaries are fixed.
- D21 row.close, because live/detached and head Rule carrier boundaries are fixed.
- Stage 3 T5 Core blueprint slicing.

### 7.2 Implementation constraints

Future T5 implementation must:

- add DTOs in application protocol and SDK re-exports;
- not expose `CandidateSet` as the new public result shape;
- keep `SupportArtifact`, `ProvenanceEnvelope`, and `EvidenceEnvelope` out of public row data fields;
- keep `_result_resolver` out of equality, hash, repr, serialization, and digests;
- avoid reusing storage ledger `Claim`;
- use generic head Rule terminology until D24 lands.

### 7.3 Stage 3 gating

Stage 3 synthesis must not create a return-shape flip blueprint before D18 and D19 are reviewed. It must not create an explanation blueprint before D20 is reviewed. It must not create a row.close blueprint before D21 is reviewed.

## 8. Acceptance Criteria

- [ ] D18 cites D17 for final `EvaluateResult` target shape and `CandidateSet` internal-artifact classification.
- [ ] D19 supplies formulas / source-of-truth for every D17 digest field.
- [ ] D20 uses D17 `EvidenceRef` as row-local plumbing, not as a public explain entrypoint.
- [ ] D21 uses D17 live/detached `DetachedRowError` contract for `row.close()`.
- [ ] T5 implementation does not reuse `core.store.ledger.Claim` as public eval `Claim`.
- [ ] SDK exports the adopted public DTOs after their implementation slice.
- [ ] `CandidateSet.state` does not become a public row status field.
- [ ] `_result_resolver` remains non-data plumbing.
- [ ] D17 does not force current SDK `ApplicationRule` alias names before D24.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | T5 Stage 1 audit Q2/Q4 mapped to D17. D17 locks application-protocol-owned result DTOs with SDK re-exports, final `EvaluateResult` / `EvaluateRow` / `Claim` / `EvidenceRef` / `DetachedRowError` field surfaces, `CandidateSet` as internal artifact, ledger-Claim name separation, and live/detached row behavior while deferring return-shape migration, digest formulas, Explanation, row.close, hard-cut, Rule naming, and semantics decisions. |
