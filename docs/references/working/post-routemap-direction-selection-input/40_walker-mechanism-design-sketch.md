# 40 — Walker Mechanism Design Sketch

> See [README.md](README.md) for context. Cross-references: [10_implicit-gaps.md Gap 2](10_implicit-gaps.md), [20_candidates.md Candidate B](20_candidates.md), [30_recommendation.md Principles #2 / #7 / #8 / #9 / #10-#19 / #P0 / #P1](30_recommendation.md).

---

## Status framing (READ FIRST)

This document is **not** an implementation specification.

This document is the **scoping artifact that lifts the §6 *draft* "walkable view" exploration in [check-operation-conceptual-interaction.md](../rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md) out of draft and into a structured proposal**. The §6 of that file is explicitly marked draft per its own §1.0 ordering rule ("若 §6 早期 iteration 与 §1-§5 冲突,以 §1-§5 为准") — meaning the walker direction is **design exploration**, not a settled principle.

What this sketch does:

1. Validates the §6 draft direction against EntitySnapshot prior art (verified to exist in [src/kernel/sdk/facade.py:102-217](../../../../src/kernel/sdk/facade.py))
2. Refines scope per the 2026-05-07 verification finding that most application/audit DTOs are already structured frozen dataclasses (only ~4-5 raw-tuple objects truly need walker classes)
3. Splits the work into B1 + B2 (mandatory) + B3 (optional based on consumer signal)
4. Operationalizes principles #2, #7, #8, #9, #10-#19, #P0, and #P1 from [30_recommendation.md](30_recommendation.md) into concrete contracts the implementation blueprint must enforce

The actual implementation blueprint (`docs/blueprints/active/2026-05-08_walker-mechanism.md`) is what owns implementation decisions.

---

## 1. Prior art alignment — `EntitySnapshot` namespace walker

[src/kernel/sdk/facade.py:102-217](../../../../src/kernel/sdk/facade.py) already implements the walker pattern in SDK layer. New walker mechanism aligns with this prior art rather than reinventing.

**Existing API shape (verified 2026-05-07):**

```python
# SDK (already shipped)
snap: EntitySnapshot = sdk.get(User, user_id="u-001", locale="zh")

# namespace walker — attribute-based, lazy
snap.assertions               # AssertionNamespace (lazy gateway)
snap.assertions.age           # FieldAssertions (per-field walker)
snap.assertions.age.active    # tuple[AssertionRecord, ...]  — frozen
snap.assertions.age.history   # tuple[AssertionRecord, ...]  — frozen
snap.assertions.age.at(t)     # tuple[AssertionRecord, ...]  — filtered
snap.assertions.age.version("v2")  # tuple[AssertionRecord, ...]  — filtered

# read-only enforced
snap.foo = 1                  # raises FrozenSnapshotError
snap.assertions.foo = 1       # raises FrozenSnapshotError
```

**Conventions to align with:**

- **Lazy attribute / property access** — view objects expose data via property getters, not eagerly materialized fields
- **Frozen returns** — collections returned are tuples (immutable); mappings are `MappingProxyType`
- **Read-only structural enforcement** — `__setattr__` raises a typed error (`FrozenSnapshotError` precedent)
- **Filter / refine via method calls** — `.at(t)`, `.version(v)` — not via raw indexing
- **Naming hierarchy** — `<root>.<aspect>.<dimension>.<predicate>` reads as English

New walker mechanism reuses this pattern; does not invent a parallel naming scheme.

### Syntax collision rules from SDK/codebase research

The implementation blueprint must avoid names that already carry different meaning in SDK / audit / core:

| Avoid | Existing meaning | Walker replacement |
|---|---|---|
| `.source` escape hatch | provenance source in assertion metadata / source references | `.underlying` |
| `.carrier` escape hatch | evidence carrier terminology around `SupportArtifact` | `.underlying` |
| `.raw` escape hatch | ambiguous raw-data convention; not accepted in final contract | `.underlying` |
| `get(...)` raise-on-miss | `SDKStore.get(...)` is None-on-miss | `require_key(...)` |
| `at(...)` positional exact access | `FieldAssertions.at(t)` is temporal filtering | `require_position(...)` |

Accepted B1/B2 vocabulary:

```python
walker.find(...) -> View | None
walker.require_key("b0.a1:person:age") -> View
walker.require_position(branch_index=0, atom_index=2) -> View
view.underlying  # escape hatch; not stable walker API
```

`view.underlying` is excluded from equality and hash computation. Dict / JSON underlying objects are exposed as `MappingProxyType(dict(mapping))`, a shallow frozen copy at access time.

---

## 2. Scope refinement — what actually needs walker

Verification finding (Agent 2 2026-05-07): most application/audit DTOs are already frozen structured dataclasses. The "raw tuple unpacking" pain is concentrated in 4-5 specific spots.

### Truly raw, walker needed

| Object | Source file | Today | Walker class |
|---|---|---|---|
| `RuleSpec.where` | [src/kernel/core/rules/rule_ir.py:32](../../../../src/kernel/core/rules/rule_ir.py) | `list[Any]` IR tuple | `IRBodyWalker` (B1) |
| `CompiledDerivationPlan.body_ir` | [src/kernel/application/protocol/derivation.py:37](../../../../src/kernel/application/protocol/derivation.py) | `list[Any]` IR tuple | same `IRBodyWalker` (B1) |
| `WhyNotUniverseResult.green` | [src/kernel/application/protocol/derivation_why_not.py:298](../../../../src/kernel/application/protocol/derivation_why_not.py) | `tuple[BindingItems, ...]` | `BindingsView` mixin (B2) |
| `DiagnoseAtomLocator.attempted_binding` | [src/kernel/application/protocol/derivation_diagnose.py:81](../../../../src/kernel/application/protocol/derivation_diagnose.py) | raw tuple | `BindingView` (B2) |
| `Store.active_facts (by entity)` | [src/kernel/core/store/runtime.py:67](../../../../src/kernel/core/store/runtime.py) | raw `Ledger.Claim` generator | **Live walker — B3 only if triggered** |

### Already structured, walker NOT needed (just need protocol mixin)

These already iterate fine; just need a shared `.filter` / `.find` / `.first` protocol:

- `SupportArtifact.pred_witnesses` / `non_fact_steps` / `rule_ref_edges` — frozen dataclass tuples
- `ProofFrameRecheckResult.atom_verdicts` — frozen dataclass tuple
- `ProofFrameDiff.frame_deltas` / `atom_deltas` — frozen dataclass tuples
- `WhyNotUniverseResult.red` — frozen dataclass tuple
- `RoundEvent` — frozen dataclass

### Cross-reference helpers needed

| Helper | What it solves | Sub-batch |
|---|---|---|
| `SupportArtifact.lookup_assertion(asrt_id) -> AssertionView` | Lazy `asrt_id → fact tuple + meta` lookup, instead of users walking ledger themselves | B2 |
| `parse_atom_key(key: str) -> AtomKeyView` | `b{branch}.a{index}:{pred_id}` format helper, instead of users splitting strings | B2 |
| `AssertionView` (lazy) | Single `asrt_id` resolved on demand to `(pred_id, key_tuple, args, meta)` view | B2 |

---

## 3. Sub-batch design

### B1 — IR walker + common find/filter protocol (mandatory)

**Scope:**

- One `IRBodyWalker` class wrapping `list[Any]` IR (used by both `RuleSpec.where` and `CompiledDerivationPlan.body_ir`)
- View types: `IRPredAtomView` (kind, pred_id, args, branch_index, atom_index), `IREqAtomView`, `IRLtAtomView`, `IRNotAtomView`, etc. — one per IR node kind
- Shared protocol mixin (e.g. `_FilterFindMixin`) added to existing frozen-tuple-bearing DTOs (SupportArtifact members, ProofFrameRecheckResult.atom_verdicts, etc.) — pure ergonomic addition, no DTO shape change
- Construction-time snapshot: because `RuleSpec.where` and `CompiledDerivationPlan.body_ir` are mutable `list[Any]`, `IRBodyWalker.__init__` snapshots them to immutable internal state (for example, `tuple(source)`) before traversal. Snapshot failure raises `WalkerSnapshotError`.

**Effort:** ~1 week.

**API sketch:**

```python
# IR walker
walker = IRBodyWalker(rule_spec.where)
for atom in walker:
    # atom is IRPredAtomView | IREqAtomView | IRLtAtomView | ...
    if atom.kind == 'pred':
        print(atom.pred_id, atom.args, atom.branch_index, atom.atom_index)
walker.filter(kind='pred').first()  # → IRPredAtomView | None
walker.find(branch_index=0, atom_index=2)  # → atom view | None
walker.require_position(branch_index=0, atom_index=2)  # → atom view or WalkerLookupError
walker.require_key('b0.a1:person:age')  # → atom view or WalkerLookupError

# Protocol mixin on frozen tuple DTOs (already-structured, just adds ergonomics)
support.pred_witnesses.filter(pred_atom_key__startswith='b0.')
support.pred_witnesses.find(pred_atom_key='b0.a1:person:age')
support.pred_witnesses.require_key('b0.a1:person:age')
result.atom_verdicts.filter(verdict='invalidated')
```

**Invariant enforcement:**

- IR walker: read-only by structural design (#8) — no `.append()`, `.set()`, etc.
- Lazy traversal (#9) — view object created on iteration, not eagerly; snapshotting mutable IR at construction does not materialize a view list
- Determinism (#10) — DTO-backed but mutable-source, so deterministic by construction-time snapshot
- Aligned with EntitySnapshot prior art naming (no `Walker[T]` base class — heterogeneity #3)

### B2 — Evidence cross-reference helpers (mandatory)

**Scope:**

- `SupportArtifact.atoms` property exposing combined `pred_witnesses + non_fact_steps` as `AtomCollectionView` with parsed atom keys
- `parse_atom_key(key: str) -> AtomKeyView` standalone helper
- `AssertionView` lazy lookup — given `asrt_id`, resolve to `(pred_id, key_tuple, args, meta)` through the implementation blueprint's chosen DTO-backed or explicit snapshot/live semantics
- `BindingView` wrapping for `tuple[(var, value), ...]` raw bindings (DiagnoseAtomLocator.attempted_binding, WhyNotUniverseResult.green elements)

**Effort:** ~1 week.

**API sketch:**

```python
# AtomKeyView: friendly access to b{branch}.a{index}:{pred_id} format
key = parse_atom_key('b0.a1:person:age')
key.branch_index   # 0
key.atom_index     # 1
key.pred_id        # 'person:age'

# SupportArtifact: combined atoms walker
for atom in support.atoms:
    print(atom.key, atom.kind, atom.witness_count)
    for asrt_id in atom.assertion_ids:
        asrt = support.lookup_assertion(asrt_id)
        print(asrt.pred_id, asrt.fact_tuple, asrt.meta)

# BindingView: friendly access to (var, value) tuples
binding = BindingView(diag.attempted_binding)
binding['$p']      # alice e_ref
binding.as_dict()  # {'$p': '...', '$age': 99, '$region': 'us'}
binding.values()   # tuple of values in canonical sort order
```

**Invariant enforcement:**

- `lookup_assertion(...)` follows a declared reference; missing `asrt_id` raises `WalkerReferenceError`.
- `parse_atom_key(...)` raises `WalkerParseError` on invalid format.
- View escape hatch is `.underlying`, excluded from equality / hash and documented as non-stable API (#11/#17).
- If any helper requires store-backed live lookup, snapshot/live semantics must be explicit per #10. B1/B2 should prefer DTO-backed or explicit snapshot-backed behavior; a live-read helper must not present as deterministic.

### B3 — Audit walker (OPTIONAL — only if AuditQuery / RoundEvents prove first real consumer)

**Scope (only if triggered):**

- `RoundEventStream` walker over `audit/round_events.jsonl` rows — supports `.filter(kind=...)`, `.filter(round_id=...)`, `.group_by('round_id')`, etc.
- `AuditPackageWalker` over the multiple ledgers (`run_ledger`, `candidate_ledger`, etc.) — uniform interface for filter/find across ledger types
- `AssertionTrace` — given an `asrt_id`, walk its history (additions, retractions) across audit ledgers

**Effort:** ~1 week if triggered.

**Why NOT auto-triggered with B1+B2:**

- Per principle #5 (layer isolation) and #7 (per-layer walker scope), audit walker lives in `kernel.audit`, not `kernel.application`. Bundling B3 with B1+B2 risks coupling we don't have evidence we need.
- Per principle #6 (no outward compat without user signal), shipping audit walker before there's a concrete audit consumer adds API surface no one asked for.
- AuditPackage today is read via `load_audit_package(...)` which returns structured `AuditPackageData` — current consumers find this adequate.

**Trigger:** Explicit user statement that an audit consumer needs filter/group on round events or ledgers, with the consumer named.

---

## 4. Cross-cutting invariants (operationalized from principles)

### From #2 + #8 — Read-only by structural design

All view classes:

- Are frozen dataclasses, OR
- Have `__setattr__` overridden to raise typed error (mirror `FrozenSnapshotError` pattern from `EntitySnapshot`)
- Return tuples (not lists) and `MappingProxyType` (not dicts) from any collection-returning property
- Expose **no** `.set()` / `.append()` / `.delete()` / `.mutate()` methods
- Expose **no** methods that return suggested rewrites / patches / actions

### From #7 + #12 — Walker uniformity, output heterogeneity, exact-access naming

Walker classes share access pattern via duck-typed protocol (NOT a `Walker[T]` ABC):

```python
# Conceptual protocol — implementation may use Protocol from typing, or just convention
class WalkerLike:  # not a base class — duck-typed
    def __iter__(self) -> Iterator[ViewT]: ...
    def filter(self, **kwargs) -> Self: ...      # narrowing
    def find(self, **kwargs) -> ViewT | None: ... # first match or None
    def first(self) -> ViewT | None: ...
    def require_key(self, key: str) -> ViewT: ... # exact lookup, raises WalkerLookupError
    def require_position(self, **position: int) -> ViewT: ... # exact lookup, raises WalkerLookupError
    def to_tuple(self) -> tuple[ViewT, ...]: ...  # eager materialize
```

But each walker's `ViewT` is its own frozen dataclass, distinct from others' (heterogeneity #3).

**Per-layer scope:** application walkers and audit walkers may diverge in shape entirely; what they share is the access pattern protocol vocabulary, not common types.

Do not use `get(...)` or positional `at(...)` for exact-access walker APIs. Those names conflict with shipped SDK semantics.

### From #9 — Lazy traversal and cache non-contract

- Walker construction stores source + indexes/filters and does not materialize a view list. Mutable-source walkers may perform an immutable construction-time snapshot (#10).
- View object creation on iteration step, not in walker `__init__`
- `.to_tuple()` is the explicit eager-materialize escape hatch; default access is lazy
- Private memoization is allowed only if it does not change equality (#17), `.stats` (#13), traversal result (#10), error timing (#12), or memory lifecycle (#16). Cache is not a v1 contract surface.

### From #10 — Determinism with explicit walker-class distinction

**DTO-backed walker** (B1 IR walker, B2 cross-reference views over frozen `SupportArtifact`):

- Source is frozen or snapshotted to immutable internal state during `__init__`; same walker traversed twice MUST give identical view sequence + contents
- For mutable IR lists, construction-time snapshot provides the repeatability guarantee

**Store-backed live walker** (B3 audit walker if triggered, possible AssertionView in B2):

- MUST declare snapshot semantics explicitly:
  - **Preferred:** bind a read projection / snapshot at walker construction. The walker reflects that snapshot for all subsequent traversals
  - **Permitted with caveats:** if only live-read is feasible, the walker may NOT claim cross-mutation repeatability. It may only claim within-traversal consistency (i.e. one `for x in walker:` loop sees a consistent view, but a second traversal after store mutation may differ)

**No silent race:** A live walker (one that does not bind a snapshot at construction) MUST make its live-read nature explicit either:
- in API name (e.g. `LiveLedgerWalker` vs `LedgerSnapshotWalker`), OR
- in docstring + module-level documentation

Walker classes that present as deterministic but secretly live-read **are forbidden by this principle**.

### From #11 + #17 — `.underlying`, equality, and hash

- View escape hatch is `.underlying` only; no `.source`, `.carrier`, or `.raw` alias.
- `view.underlying` is an escape hatch, not a stable walker API.
- For mappings, `.underlying` returns `MappingProxyType(dict(mapping))`, a shallow frozen copy at access time.
- `.underlying` is excluded from equality and hash.
- View identity is not stable; structural equality covers surfaced view fields where defined.
- Hashability is only guaranteed for simple locator-like views.

### From #13 — Observability isolation

- No B1/B2 logs, warnings, or audit event emission.
- `__repr__` should expose inspection context such as `source_id`, current position, and last filter.
- `.stats` returns a frozen access-time snapshot and does not advance traversal.
- Walker errors carry nullable `.query`, `.source_id`, and `.locator`.

### From #14 — Future `StreamWalker` bounds (B3 only)

B1+B2 ship no `StreamWalker` class, no `on_progress` callback, and no snapshot machinery for stream traversal. If B3 is reactivated, any store-backed / live `StreamWalker` must satisfy at least one bound condition during `__init__`:

- `limit` is a positive int
- `snapshot=True` and `max_snapshot_items` is a positive int
- source exposes `bounded_size_hint() -> int` returning a non-negative int

`filter` alone is never a bound. `__len__` alone is not accepted. Missing bound raises `UnboundedStreamError` fail-fast.

### From #15 + #16 + #18 + #19 — lifecycle and tests

- Walker instances are single-thread objects; share frozen/safe source, not walker instances.
- DTO-backed walkers have no close lifecycle. B3 close/context-manager behavior is deferred until B3 exists.
- Walker pickling is explicitly rejected; no stable serialization contract for walkers or views.
- Every walker family needs common contract tests plus behavior-specific tests, using flat `unittest`-style test layout and shared `_walker_fixtures.py` if needed.

### From #6 — Import surface

B1/B2 add no new export to `kernel.sdk.__all__`. Any future SDK shell is Direction C and requires a separate blueprint.

### From #5 + #7 — Per-layer, no cross-layer protocol

- Application walker types live in `kernel.application` (likely new module `kernel.application.walker`)
- Audit walker types (B3 if triggered) live in `kernel.audit` (likely new module `kernel.audit.walker`)
- Audit walker does NOT import application walker types
- Application walker does NOT import audit walker types
- Each layer reuses the duck-typed `WalkerLike` access vocabulary (definition probably in `kernel.application.walker.protocol` if needed, or just convention) — but no shared concrete base class

---

## 5. Consumer migration (after walker lands)

Demos, automation, tests can opt-in to walker incrementally. Existing direct-tuple-iteration code keeps working (walker is additive, not breaking).

**Demo notebook impact:** [examples/03_proofframe_rule_overlays.ipynb](../../../../examples/03_proofframe_rule_overlays.ipynb) ProofFrame chapter currently does:

```python
for verdict in result.atom_verdicts:
    print(f'  atom {verdict.atom_key}: verdict={verdict.verdict} '
          f'affected_action_indices={verdict.affected_action_indices}')
```

With walker (B2 protocol mixin):

```python
for verdict in result.atom_verdicts.filter(verdict='invalidated'):
    key = parse_atom_key(verdict.atom_key)  # B2 helper
    print(f'  atom branch={key.branch_index} idx={key.atom_index} '
          f'pred={key.pred_id}: verdict={verdict.verdict}')
```

This is a small win in a single demo. Larger wins appear in audit-tool / automation code where atom-key parsing happens repeatedly.

**`round_story_full_demo.py` impact:** mostly `_seed_person` and `_phase_*` glue benefit from intent-shaped builders (A), not walker (B). Walker mainly helps in the cross-reference parts (looking up `asrt_id` to print fact tuples in verbose mode).

---

## 6. Decisions deferred to B's blueprint Step 0

Items the implementation blueprint must resolve before scope-freeze; not pre-decided here:

1. Module location: one `kernel.application.walker` module or split (e.g. `kernel.application.walker.ir`, `kernel.application.walker.evidence`, etc.)?
2. `WalkerLike` protocol: explicit `typing.Protocol` declaration, or convention only?
3. AssertionView semantics: DTO-backed, explicit snapshot-backed, or explicitly live-read (per §3 B2 above) — pick one and document repeatability guarantees
4. IR walker view types: one `IRAtomView` union type or one class per kind (`IRPredAtomView`, `IREqAtomView`, …)?
5. Whether the protocol mixin (`_FilterFindMixin`) is added to existing DTO classes via subclass, mixin import, or external function (`filter_view(tuple, **kwargs)`)
6. Whether walker exports go into `kernel.application.__all__` (advanced importable, per #6) or only via submodule import (`from kernel.application.walker import IRBodyWalker`)

---

## 7. Reactivation triggers for B3

If B1 + B2 ship and B3 is left optional, B3 reactivates when ANY of:

- An audit-tool consumer (named) needs `RoundEventStream` filter/group
- Public-facing audit reporting (e.g. an admin web view) needs structured ledger walking
- A future SDK shell (C, D follow-ons) needs walker output across application + audit boundary
- A demo or tutorial naturally needs audit walker to explain a workflow

Until then, audit walker stays deferred — `AuditPackage` + `load_audit_package(...)` + `AuditQuery` adequate for current consumers.

---

## 8. What this sketch does NOT cover

- No PyReason / ProbLog adapter walker scope. If those engines need walker integration, separate trigger and separate sub-batch.
- No serialization / rendering format. Walker is iteration; rendering remains [Evidence Graph DTO](../../../blueprints/active/2026-03-28_evidence-graph-unified-explain.md)'s job.
- No `__rich__` / `__pretty__` / Jupyter `_repr_html_` integration. Could be added later if useful, but not in B1/B2 scope.
- No SDK shell wrapping walker (`sdk.explain(...).evidence` returning walker). That's Direction C, separately tracked, gated on B1+B2 landing.
