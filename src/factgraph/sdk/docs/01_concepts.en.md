# SDK Concepts

The conceptual model behind `factgraph.sdk`. Read this once to understand
how the pieces fit together; refer to
[`04_api_surface.en.md`](04_api_surface.en.md) for the exact API.

---

## 1. Four object lifecycles

Every interaction with FactPy involves at most four kinds of objects:

```
Declaration    →    Candidate    →    Assertion    →    Proof Trace
(authoring)        (eval output)      (in ledger)        (why/how evidence)
```

### Declaration

A *declaration* is what you write at design time: an `Entity` class,
a `Field` descriptor, a `Rule`, an `Inference`. Declarations have no
identity yet — they describe shapes and patterns.

```python
class User(Entity):                   # entity declaration
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")

with vars("u",) as (u,):              # rule declaration
    r = build_application_rule(
        id="rule_alice",
        version="1.0.0",
        where=[User(u), User(u).name == "Alice"],
        ports={"user": u},
    )
```

### Evaluation Row

An *evaluation row* is an `EvaluateResult` row produced by
`fg.eval.evaluate(...)`. Evaluation is read-only; rows carry bindings, a Claim,
raw quantitative carriers, and an EvidenceRef.

```python
result = fg.eval.evaluate(deriv)
row = result.first()
assert row is not None
row.bindings
row.claim.digest
row.raw_kind
row.bound
row.evidence_ref.ref_id
```

The supporting evidence is reachable through `row.explain()`. A row can also
produce a closed replay head with `row.close()`.

### Assertion

An *assertion* is the persisted record of a fact in the ledger. Every
write (`set`, `add`, `accept`, `ingest`) produces one or more
assertions. Each carries an `asrt_id`, a value, a `meta` dict, and
provenance (source, trace_id, ingested_at, etc.).

```python
snap.field("name").active             # AssertionRecordSet of current records
snap.field("name").history            # AssertionRecordSet of active + revoked records
snap.field("name").history.at("2026-05-01T00:00:00Z")  # valid at business time t
snap.field("name").history.version("v1")               # version metadata filter
snap.field("name").history.by_id(asrt_id)              # exact assertion-id filter
[r.value for r in snap.field("name").active]           # the underlying values
```

Assertions are **append-only**. Retracting an assertion creates a
new "retraction" assertion that marks the original inactive; the
original record is preserved for audit.

Retraction also defines the default snapshot boundary. `active` exposes
currently non-revoked assertions, while `history` keeps the append-only
record including revoked assertions. Use `history` when audit or review
work needs to inspect retracted claims.

### Derivation (proof structure)

A *derivation* in proof terms is the structured trace showing how a
candidate or assertion came to exist: which rule fired, which body
literals supported it, which sub-proofs were chained. This proof
vocabulary is not the public SDK `Inference` value-object type. The typed
representation is `SupportArtifact`
(`factgraph.core.store._support`). "ProofFrame" in this doc is an
informal umbrella for the audit-log shapes that wrap or compare
support artifacts — concretely `ProofFrameRecheckResult`
(`factgraph.application.protocol.proofframe`) and `ProofFrameDiff`
(`factgraph.audit.proof_frame_diff`). There is no class literally
named `ProofFrame`.

```python
result = fg.eval.evaluate(my_deriv)
row = result.first()
assert row is not None
row.explain()
```

Persisted proof-frame comparison remains under `fg.audit.*`.

---

## 2. Frozen assertion views

`fg.views` is for **named frozen assertion membership**.

```python
# Named frozen assertion-id membership.
review = fg.views.create("review_set", asrt_ids=[asrt_id])
records = fg.assertions.by_ids(review.asrt_ids)
```

`fg.views` stores only `FrozenAssertionView` objects. A frozen view is a
named set of concrete `asrt_id` strings captured at creation time. The
membership does not grow automatically when new assertions are written.
The view is useful when users need a stable review set, audit selection,
or hand-curated assertion universe.

There is no built-in `default` view. The name `"default"` is not
reserved: if users create `fg.views.create("default", asrt_ids=[...])`,
it is just another frozen assertion-id selection and has no special read
behavior. Frozen views are read back through `fg.assertions.by_ids(...)`;
they are not accepted as `fg.read.find(...)` or
`fg.eval.evaluate(...)` inputs.

---

## 3. FactGraph as facade vs application as authority

```
┌────────────────────────────────────────────────────────────┐
│                  Your Code                                  │
│                     │                                       │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  factgraph.sdk (FactGraph / SDKStore)                   │  │
│  │  • Schema authoring (Entity, Field, Identity)        │  │
│  │  • Ergonomic facade (read.get, write.add, eval)      │  │
│  │  • DSL lowering (Rule → RuleSpec)                    │  │
│  │  • Outward shapes (EntitySnapshot, IngestResult)     │  │
│  │  • Compatibility errors                              │  │
│  └─────────────────┬────────────────────────────────────┘  │
│                    │ delegates runtime to                  │
│                    ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  factgraph.application (canonical runtime authority)    │  │
│  │  • Read/write planning + execution                   │  │
│  │  • Compiled derivation evaluate / accept             │  │
│  │  • What-if shells (Check, Diagnose, ...)             │  │
│  │  • Frozen DTOs (CheckResult, EvaluationOverlay, ...) │  │
│  └─────────────────┬────────────────────────────────────┘  │
│                    │ uses                                  │
│                    ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  factgraph.core (substrate)                             │  │
│  │  • Ledger / store / rules / evidence                 │  │
│  │  • Native evaluator                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

The split exists so that:

- **Service / agent code** never imports from `factgraph.sdk` for
  runtime operations — it uses `factgraph.application` directly. The SDK
  is for product code that wants ergonomics.
- **Cross-language consumers** (wire bridges, JSON APIs) work against
  `factgraph.application` DTOs, not SDK objects.
- **Test boundaries** are clear: SDK tests verify the facade; application
  tests verify the runtime authority.

For most users this split is invisible — `fg.write.add(...)` Just
Works. The split matters when you're building tooling on top of
factgraph.

RuleExpr uses this split deliberately. User-facing examples should start from
SDK ergonomics (`build_application_rule(...)`) or the top-level `Rule` export,
while the expression values themselves are application protocol objects.
`fg.rules.inspect(...)` also reflects the split: legacy SDK `Inference` inputs
return the preserved dict shape, while application `Rule` and RuleExpr inputs
return `RuleExprInspect`.
Execution follows the same boundary. `fg.eval.evaluate(expr, head=rule, engine=...)`
accepts application `Rule` / RuleExpr inputs and returns `EvaluateResult`;
private lowering, trace, and adapter-support DTOs are not SDK exports.
For application `Rule` inspect values, `RuleExprInspect.is_closed` and
`RuleExprInspect.unbound_ports` report the strict closed-head inspect subset.
Structural RuleExpr inspect carries default fields for shape consistency but
does not define closed-head semantics.

---

## 4. Frozen DTO boundary

Some DTOs cross the SDK/application boundary as **frozen, public
types**. Other internal types stay inside their layer.

### Crosses the boundary

| DTO | Used in |
|---|---|
| `EvaluationOverlay`, `FactOverlayAction`, `RuleOverlayAction` | `fact_overlay.check`, rule overlays |
| `RuleLiteralPath`, `RuleAddedAtom` | `rule.literal_replace`, `rule.add_condition` |
| `SupportArtifact` | Returned inside `CheckResult.evidence_envelope.engine_payload`; consumed by `recheck_proof_frame` |
| `ProofFrameRecheckResult` | Returned by `recheck_proof_frame` |
| `RoundEvent`, `WarningDTO` | `audit.diff_proof_frames` |
| `ProofFrameDiff`, `FrameDelta`, `AtomDelta`, `FrameIdentity`, `FrameStatusChange`, `EventReference` | Returned by `audit.diff_proof_frames` |
| `RuleExpr`, `RuleJoinConstraint`, `RuleExprInspect`, `OccurrenceInspect`, `AtomDescriptor`, `PortInspect` | RuleExpr authoring and inspect; execution reuses `fg.eval.evaluate(..., head=...)` without new public result DTOs |

These mostly live in `factgraph.application.protocol` and `factgraph.audit`.
They are frozen dataclasses with `__post_init__` validation —
constructing one with bad shape raises `ProtocolShapeError`.

> Footnote on `SupportArtifact`: defined in
> `factgraph.core.store._support` (substrate-private module) but referenced
> as a frozen DTO at the protocol boundary
> (`factgraph.application.protocol.derivation_check.EvidenceEnvelope.engine_payload`).
> The `_support` location reflects that it's also produced by the
> native evaluator inside `factgraph.core`.

### Stays internal

| Type | Why not exposed |
|---|---|
| `factgraph.core.rules.rule_ir.RuleSpec` | Substrate IR; SDK accepts SDK `Rule` and lowers internally |
| Engine-specific intermediate plans | Engine-private optimization detail |
| Ledger row formats | `factgraph.core.ledger` private |

The SDK explicitly **rejects** raw `RuleSpec` at its boundary. Pass
SDK `Rule` objects; the SDK lowers them via `_compile_rule_input(...)`.

---

## 5. Three stability tiers

Behaviors in the docs are labeled with one of:

| Label | Meaning |
|---|---|
| **stable contract** | Public API. Will not change in a breaking way without a deprecation cycle. Safe to assert against in tests. |
| **current behavior** | Implemented but not yet promoted to stable. May evolve in minor versions. Useful for in-house code; double-check on upgrade. |
| **current boundary** | A deliberate non-feature. The factgraph team chose not to support this. Building around it is fragile. |

`factgraph.sdk.__all__` is itself a stable contract: removing or
renaming an exported name requires a major version bump.

---

## 6. What the SDK does not do

Some capabilities live outside the SDK on purpose. Reach them via
direct import; see [`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md).

| Capability | Where to import |
|---|---|
| Round events recorder lifecycle | `factgraph.audit.round_events` |
| Frontier trace | `factgraph.core.rules.frontier` |
| Walker views (`ProofFrameDiffView`, etc.) | `factgraph.application.walker` |
| Engine adapter registration | `factgraph.adapters.{souffle,problog,pyreason}` |
| Optional domain bundles (e.g. ECSS) | Direct import at the call site (`import factgraph.adapters.ecss as ecss`); guard with `try/except ImportError` if the bundle may be absent |

The SDK does not auto-wrap these surfaces. The boundary is intentional:
each wrapper commits the SDK to a stable contract, and the team
prefers to add wrappers after seeing real usage patterns.

---

## Appendix A: Layer ownership matrix

| Layer | Responsibility |
|---|---|
| `factgraph.application` | Canonical Python runtime authority; owns read/write/query/ingest/compiled derivation runtime DTOs and executors |
| `factgraph.sdk` | Python product surface; owns schema/DSL authoring, facade, snapshot/editor/batch outward objects, compatibility errors |
| `factgraph.audit` | Audit DTOs (`RoundEvent`, `ProofFrameDiff`), package loader, recorder lifecycle |
| `factgraph.core` | Low-level ledger / store / rules / evidence semantics |
| `factgraph.adapters` | Engine adapters (Souffle, ProbLog, PyReason) |
| service / agent code | Delivery / product consumers; production runtime code does not add SDK runtime imports |

---

## Appendix B: Hard boundaries (current semantics)

| Topic | Behavior |
|---|---|
| SDK product surface | `factgraph.sdk.__all__` exposes only user-facing surface; no application internals |
| Application protocol | Does not accept SDK facade objects, SDK `Field` descriptors, or SDK DSL objects |
| service / agent imports | **Convention** (not enforced in code today): production runtime code does not add `factgraph.sdk` runtime imports beyond `compile_schema_from_classes`. Authoring tools and tests are exempt. |
| Legacy field semantics | `functional`, `temporal`, `dims`, `fact_key` are removed |
| `vars()` runtime unpack | `with vars() as (a, b)` is unsupported; use named or factory forms |
| String DSL | `sdk.run("...")` / `sdk.evaluate("...")` are unsupported |
| `find(...)` | No `temporal_view`; identity filters may be partial, including primary-only filters |
| Assertion view surface | `.chosen` is removed; field assertion collections expose `active`, `history`, `at`, `version`; `AssertionRecordSet` also supports `where`, `at`, `version`, `by_id`, `one`, `first`, `all` |
| Frozen assertion views | `fg.views` supports named frozen assertion-id selections only; no built-in `default` view and no read-policy registry |
| Snapshot history | `active` returns currently non-revoked assertions; `history` returns the append-only field assertion history |
| `sdk.run(...)` dispatch | Removed by the T5 hard-cut; use `fg.eval.evaluate(...)` for Rule/Inference evidence paths |
| `sdk.evaluate(...)` params | `temporal_view` is removed and fails explicitly |
| Rule `row_format` detail | `"tuple"` still works but emits `DeprecationWarning`; prefer `"dict"` |
| `SDKBatchTx` context | `__exit__` does not auto-commit or auto-rollback; call explicitly |
| Wire export restriction | `BatchPlan.export()` / `to_json()` forbids raw `idref_v1` token values |
| `single` field semantics | `single` is a read-side scalar view; writes do not auto-prune older assertions |
| Inference `head` semantics | Primary-key fields in `head` are compile-time hard errors |
| Cross-coordinate attr comparison | Only `==` on the same entity type and same `primary_key` field is allowed |
| `RuleRef` constraints | Target must be `expose=True`; `RuleRef` is forbidden inside `Not(...)` body |
| Query head constraints | Only `Entity(var)` or `Entity.field(...)`; field projection supports only `single` fields |
| Branch identity | `Branch([...], id="name")` adds optional structural SDK metadata for `fg.rules.inspect(...)`. Unnamed branches inspect as `b0`, `b1`, ... fallback ids. Branch ids are not serialized into authoring payloads, compiled plans, registries, or adapters. |
| Single-head inferences | Public SDK `Inference` accepts one head. Multi-head public inferences are removed in Track 1; define one inference per head. Capability shells were already single-head surfaces. |
| Public semantics wrappers | Track 2 adds SDK-local `ProbLogSemantics` and `PyReasonSemantics` as preferred Python authoring wrappers for `evaluate(..., semantics=...)`. The SDK can derive `engine=` from these objects, lower them into canonical `SemanticsProfile`, and keep service / compiled paths on the canonical shape. |

---

## Appendix C: Deferred items

| Item | Status |
|---|---|
| `sdk.create(...)` | Deferred |
| `sdk.save(plain_entity)` / `snapshot.to_entity()` | Deferred |
| Formal typed ingest schema (`TypedDict` / dataclass) | Deferred |
| Temporal write semantics in `Rule` / `Inference` head (`valid_from`, `valid_to`, `version`) | Deferred |
| Native multi-head publishing semantics in Registry | Removed from public SDK surface in Track 1; use one derivation per head |
| Physical SDK file split (`store.py` / `batch.py` / `facade.py`) | Deferred; runtime delegation completed, line-count reduction not |
| Full exception hierarchy migration | Deferred; application runtime uses DTO error shapes, SDK product-domain errors remain SDK-owned |
