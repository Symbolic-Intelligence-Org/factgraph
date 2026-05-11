# SDK Concepts

The conceptual model behind `kernel.sdk`. Read this once to understand
how the pieces fit together; refer to
[`04_api_surface.en.md`](04_api_surface.en.md) for the exact API.

---

## 1. Four object lifecycles

Every interaction with FactPy involves at most four kinds of objects:

```
Declaration    →    Candidate    →    Assertion    →    Derivation
(authoring)        (eval output)      (in ledger)        (proof structure)
```

### Declaration

A *declaration* is what you write at design time: an `Entity` class,
a `Field` descriptor, a `Rule`, a `Derivation`. Declarations have no
identity yet — they describe shapes and patterns.

```python
class User(Entity):                   # entity declaration
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")

with vars("u",) as (u,):              # rule declaration
    r = Rule(
        id="rule_alice",
        version="1.0.0",
        select=[u],
        where=[User(u), u.name == "Alice"],
    )
```

### Candidate

A *candidate* is an `Eval` output that has not been written yet. When
`fg.eval.evaluate(...)` runs a derivation, it returns a list of
`CandidateSet`s — proposed facts plus their evidence. Nothing is in
the ledger until you `accept(...)` them.

```python
candidates = fg.eval.evaluate(deriv)
candidates[0].candidate_kind          # "fact" or "entity"
candidates[0].payload                 # the proposed fact / entity body
candidates[0].confidence              # float | None (engine-dependent)
candidates[0].confidence_kind         # "none" | "probability" | "certainty"
candidates[0].support_digest          # sha256 token of the supporting evidence
```

The supporting evidence itself (a `SupportArtifact`) is reachable
*only* via `fg.what_if.check(...)` — see the Derivation block below.
`CandidateSet` deliberately keeps just the digest so the run/accept
path stays narrow.

### Assertion

An *assertion* is the persisted record of a fact in the ledger. Every
write (`set`, `add`, `accept`, `ingest`) produces one or more
assertions. Each carries an `asrt_id`, a value, a `meta` dict, and
provenance (source, trace_id, ingested_at, etc.).

```python
snap.field("name").active             # property -> AssertionRecordSet of current records
snap.field("name").history            # property -> AssertionRecordSet of active + revoked records
snap.field("name").history.at("2026-05-01T00:00:00Z")  # valid at business time t
snap.field("name").history.version("v1")               # version metadata filter
snap.field("name").history.by_id(asrt_id)              # exact assertion-id filter
[r.value for r in snap.field("name").active]           # the underlying values
```

Assertions are **append-only**. Retracting an assertion creates a
new "retraction" assertion that marks the original inactive; the
original record is preserved for audit.

### Derivation (proof structure)

A *derivation* in proof terms is the structured trace showing how a
candidate or assertion came to exist: which rule fired, which body
literals supported it, which sub-proofs were chained. The typed
representation is `SupportArtifact`
(`kernel.core.store._support`). "ProofFrame" in this doc is an
informal umbrella for the audit-log shapes that wrap or compare
support artifacts — concretely `ProofFrameRecheckResult`
(`kernel.application.protocol.proofframe`) and `ProofFrameDiff`
(`kernel.audit.proof_frame_diff`). There is no class literally
named `ProofFrame`.

```python
result = fg.what_if.check(my_deriv, binding)
result.evidence_envelope.engine_payload  # SupportArtifact
```

The same proof structure powers `diagnose`, `recheck_proof_frame`,
`why_not`, and `diff_proof_frames`.

---

## 2. FactGraph as facade vs application as authority

```
┌────────────────────────────────────────────────────────────┐
│                  Your Code                                  │
│                     │                                       │
│                     ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  kernel.sdk (FactGraph / SDKStore)                   │  │
│  │  • Schema authoring (Entity, Field, Identity)        │  │
│  │  • Ergonomic facade (read.get, write.add, eval.run)  │  │
│  │  • DSL lowering (Rule → RuleSpec)                    │  │
│  │  • Outward shapes (EntitySnapshot, IngestResult)     │  │
│  │  • Compatibility errors                              │  │
│  └─────────────────┬────────────────────────────────────┘  │
│                    │ delegates runtime to                  │
│                    ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  kernel.application (canonical runtime authority)    │  │
│  │  • Read/write planning + execution                   │  │
│  │  • Compiled derivation evaluate / accept             │  │
│  │  • What-if shells (Check, Diagnose, ...)             │  │
│  │  • Frozen DTOs (CheckResult, EvaluationOverlay, ...) │  │
│  └─────────────────┬────────────────────────────────────┘  │
│                    │ uses                                  │
│                    ▼                                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  kernel.core (substrate)                             │  │
│  │  • Ledger / store / rules / evidence                 │  │
│  │  • Native evaluator                                  │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

The split exists so that:

- **Service / agent code** never imports from `kernel.sdk` for
  runtime operations — it uses `kernel.application` directly. The SDK
  is for product code that wants ergonomics.
- **Cross-language consumers** (wire bridges, JSON APIs) work against
  `kernel.application` DTOs, not SDK objects.
- **Test boundaries** are clear: SDK tests verify the facade; application
  tests verify the runtime authority.

For most users this split is invisible — `fg.write.add(...)` Just
Works. The split matters when you're building tooling on top of the
kernel.

---

## 3. Frozen DTO boundary

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

These mostly live in `kernel.application.protocol` and `kernel.audit`.
They are frozen dataclasses with `__post_init__` validation —
constructing one with bad shape raises `ProtocolShapeError`.

> Footnote on `SupportArtifact`: defined in
> `kernel.core.store._support` (substrate-private module) but referenced
> as a frozen DTO at the protocol boundary
> (`kernel.application.protocol.derivation_check.EvidenceEnvelope.engine_payload`).
> The `_support` location reflects that it's also produced by the
> native evaluator inside `kernel.core`.

### Stays internal

| Type | Why not exposed |
|---|---|
| `kernel.core.rules.rule_ir.RuleSpec` | Substrate IR; SDK accepts SDK `Rule` and lowers internally |
| Engine-specific intermediate plans | Engine-private optimization detail |
| Ledger row formats | `kernel.core.ledger` private |

The SDK explicitly **rejects** raw `RuleSpec` at its boundary. Pass
SDK `Rule` objects; the SDK lowers them via `_compile_rule_input(...)`.

---

## 4. Three stability tiers

Behaviors in the docs are labeled with one of:

| Label | Meaning |
|---|---|
| **stable contract** | Public API. Will not change in a breaking way without a deprecation cycle. Safe to assert against in tests. |
| **current behavior** | Implemented but not yet promoted to stable. May evolve in minor versions. Useful for in-house code; double-check on upgrade. |
| **current boundary** | A deliberate non-feature. The kernel team chose not to support this. Building around it is fragile. |

`kernel.sdk.__all__` is itself a stable contract: removing or
renaming an exported name requires a major version bump.

---

## 5. What the SDK does not do

Some capabilities live outside the SDK on purpose. Reach them via
direct import; see [`07_walker_and_advanced.en.md`](07_walker_and_advanced.en.md).

| Capability | Where to import |
|---|---|
| Round events recorder lifecycle | `kernel.audit.round_events` |
| Frontier trace | `kernel.core.rules.frontier` |
| Walker views (`ProofFrameDiffView`, etc.) | `kernel.application.walker` |
| Engine adapter registration | `kernel.adapters.{souffle,problog,pyreason}` |
| Optional domain bundles (e.g. ECSS) | Direct import at the call site (`import kernel.adapters.ecss as ecss`); guard with `try/except ImportError` if the bundle may be absent |

The SDK does not auto-wrap these surfaces. The boundary is intentional:
each wrapper commits the SDK to a stable contract, and the team
prefers to add wrappers after seeing real usage patterns.

---

## Appendix A: Layer ownership matrix

| Layer | Responsibility |
|---|---|
| `kernel.application` | Canonical Python runtime authority; owns read/write/query/ingest/compiled derivation runtime DTOs and executors |
| `kernel.sdk` | Python product surface; owns schema/DSL authoring, facade, snapshot/editor/batch outward objects, compatibility errors |
| `kernel.audit` | Audit DTOs (`RoundEvent`, `ProofFrameDiff`), package loader, recorder lifecycle |
| `kernel.core` | Low-level ledger / store / rules / evidence semantics |
| `kernel.adapters` | Engine adapters (Souffle, ProbLog, PyReason) |
| service / agent code | Delivery / product consumers; production runtime code does not add SDK runtime imports |

---

## Appendix B: Hard boundaries (current semantics)

| Topic | Behavior |
|---|---|
| SDK product surface | `kernel.sdk.__all__` exposes only user-facing surface; no application internals |
| Application protocol | Does not accept SDK facade objects, SDK `Field` descriptors, or SDK DSL objects |
| service / agent imports | **Convention** (not enforced in code today): production runtime code does not add `kernel.sdk` runtime imports beyond `compile_schema_from_classes`. Authoring tools and tests are exempt. |
| Legacy field semantics | `functional`, `temporal`, `dims`, `fact_key` are removed |
| `vars()` runtime unpack | `with vars() as (a, b)` is unsupported; use named or factory forms |
| String DSL | `sdk.run("...")` / `sdk.evaluate("...")` are unsupported |
| `find(...)` | No `temporal_view`; identity filters may be partial, including primary-only filters |
| Assertion view surface | `.chosen` is removed; field assertion collections expose `active`, `history`, `at`, `version`; `AssertionRecordSet` also supports `where`, `at`, `version`, `by_id`, `one`, `first`, `all` |
| Frozen assertion views | `fg.views` supports named frozen assertion-id selections; legacy `ViewSpec` remains projection-policy compatibility |
| `sdk.run(...)` dispatch | Rule and Query supported; Derivation is rejected with guidance to use `evaluate()` |
| `sdk.evaluate(...)` params | `temporal_view` is removed and fails explicitly |
| Rule `row_format` detail | `"tuple"` still works but emits `DeprecationWarning`; prefer `"dict"` |
| `SDKBatchTx` context | `__exit__` does not auto-commit or auto-rollback; call explicitly |
| Wire export restriction | `BatchPlan.export()` / `to_json()` forbids raw `idref_v1` token values |
| `single` field semantics | `single` is a read-side scalar view; writes do not auto-prune older assertions |
| Derivation `head` semantics | Primary-key fields in `head` are compile-time hard errors |
| Cross-coordinate attr comparison | Only `==` on the same entity type and same `primary_key` field is allowed |
| `RuleRef` constraints | Target must be `expose=True`; `RuleRef` is forbidden inside `Not(...)` body |
| Query head constraints | Only `Entity(var)` or `Entity.field(...)`; field projection supports only `single` fields |
| Multi-head derivations | `register_derivation(...)` and `fg.eval.evaluate(...)` accept multi-head Derivations (the DSL serializes `head: [...]` as a list when more than one head is present). The single-head constraint lives in capability shells: `fg.what_if.{check, diagnose, why_not}` reject plans with `len(plan.heads) != 1` (`kernel.application.capability_helpers.why_not.py:23` and siblings) |

---

## Appendix C: Deferred items

| Item | Status |
|---|---|
| `sdk.create(...)` | Deferred |
| `sdk.save(plain_entity)` / `snapshot.to_entity()` | Deferred |
| Formal typed ingest schema (`TypedDict` / dataclass) | Deferred |
| Temporal write semantics in `Rule` / `Derivation` head (`valid_from`, `valid_to`, `version`) | Deferred |
| Native multi-head publishing semantics in Registry | Deferred |
| Physical SDK file split (`store.py` / `batch.py` / `facade.py`) | Deferred; runtime delegation completed, line-count reduction not |
| Full exception hierarchy migration | Deferred; application runtime uses DTO error shapes, SDK product-domain errors remain SDK-owned |
