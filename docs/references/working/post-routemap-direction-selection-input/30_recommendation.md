# 30 — Recommendation: A + B (with conditional C)

> See [README.md](README.md) for context. Cross-references: [00_inventory.md](00_inventory.md), [10_implicit-gaps.md](10_implicit-gaps.md), [20_candidates.md](20_candidates.md), [40_walker-mechanism-design-sketch.md](40_walker-mechanism-design-sketch.md).

---

## Recommendation summary

**Primary recommendation:** Ship **A** (application-layer ergonomic helpers, extending the Batch 2 pattern to Q1/Q2/Batch 4-7) and **B** (walker mechanism — lifting the `check-operation-conceptual-interaction.md` §6 *draft* "walkable view" exploration out of draft and into actual scoping) as two **independent, parallel-safe blueprints**.

**Conditional follow-up:** After A + B land, **consider C** (narrow Check+Diagnose SDK shell) as a Step 0 spike per [Batch 8 §5.5.5 row 1](../../../blueprints/archive/2026-05-06_public-surface.md) reactivation trigger. C strongly benefits from B's walker mechanism already shipped.

**Explicitly defer for now:**

- **D (dialog agent revival)** — v0.2+ scope, no current user signal. But recommend declaring v0.1's audience-narrowing decision (Gap 1) as a separate short blueprint, so the implicit drift becomes explicit.
- **E (release publish)** — purely user-gated. Decoupled from layer choice; user can call it any time without affecting A/B work.
- **F (demo refresh)** — downstream; will resolve naturally as A/B land.
- **G (Batch 4 `rule_refs` hardening)** — parallel-safe, not blocking, but also no urgency. Ship if there's idle capacity; otherwise leave.
- **H (unified status vocabulary)** — premature, no consumer signal.
- **I (new engine onboarding)** — premature, no engine candidate.

---

## Design principles for this work (verified 2026-05-07)

The following principles ground all subsequent scoping. Each is annotated with citation accuracy from the 2026-05-07 verification round (3 parallel Explore agents). **#1, #2, #5, #6 are exact-citation source-grounded. #3 is faithful to source but with corrected attribution. #4 is split into a canonical part (#4a) and a downgraded "design exploration" part (#4b). #7, #8, #9 are derived patterns aligned with verified prior art. #10 adopts the user's precise wording on the DTO-backed vs store-backed walker distinction. #11-#19 and #P0/#P1 are post-verification walker-contract additions accepted on 2026-05-07; they do not define implemented behavior until adopted by a real blueprint.**

### #1 — Application-first runtime authority

> "新 capability 必须在 `kernel/application/protocol/` 起 DTO,纯函数 `(request, store) → result` 在 `kernel/application/<capability>_runtime.py`,SDK shell 只 wrapper。**不允许新 substrate 长在 `kernel/sdk/`**。"

— [60_lessons-learned.md:40](../rule-replay-line-redesign-input/60_lessons-learned.md), exact verified

**For this work:** All ergonomics added in `kernel.application` (and `kernel.audit` where audit-side); never as substrate in SDK.

### #2 — Evidence is read-only, structurally not just presentationally

> "Evidence trees should be **read-only views over an evaluation or check result.** 'Read-only' should be **structural, not only presentational**." (lines 96-98)
>
> "Evidence boxes should not directly create `RulePatch` objects." (line 108)

— [rule-replay-design-synthesis-2026-05-01.md §2 "Stable Design Principles"](../rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/rule-replay-design-synthesis-2026-05-01.md), exact verified

**For this work:** Walker views are observation interfaces. They never mutate source, never derive `RulePatch`/`Action`/etc. "Read-only != no computation" — derived computations like `check_fact_overlay_binding(...)` are read-only because they don't mutate source ledger; that's the standard to apply.

### #3 — Capability heterogeneity (no single SDK method family)

> "The capability set is structurally heterogeneous: status-only check, localized diagnose, overlay before/after/diff, ProofFrame atom verdicts, rule-action variant rows plus nested ProofFrame, Why-not boards, and audit diffs."
>
> "**One SDK method family would be false merge**."

— [2026-05-06_public-surface.md:173-183, §5.4.A Step 0 Spike Verdict #3](../../../blueprints/archive/2026-05-06_public-surface.md), exact verified (citation attribution corrected from earlier "§5.4 falsifier #3 row" to "§5.4.A Spike Verdict #3")

**For this work:** Each capability gets its own builder (A); each walker view shape stays distinct (#7 below). What unifies is **access pattern**, not output shape.

### #4a — Application input is intent-minimal (canonical)

> "application 层从 user 接受: rule reference / binding / engine / 不含 facts overlay" (§2.1)

— [check-operation-conceptual-interaction.md:72-88, §2.1 "最小输入 set"](../rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md), canonical (§1-§5 binding section per the document's own §1.0 ordering rule)

**For this work:** A's builders accept intent-shaped inputs (rule reference, binding dict, engine), normalize to protocol DTO internally. **Note:** intent-minimal is per-layer — SDK builders take the most intent-shaped form; application functions still accept normalized DTOs. A is the SDK-layer-side of intent normalization (even though it lives in `kernel.application`, it's positioned as "what an SDK shell would call into").

### #4b — Walker output is design exploration in §6 draft, NOT yet a settled principle

The following appears in [check-operation-conceptual-interaction.md §6 (draft discussion)](../rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md):

> "用户读 evidence 是高频操作(check/evaluate 之后)...application 层加一个 walkable wrapper 是合理 ergonomics 投资,与'用户能 for 遍历'心智完全匹配"

**Verification finding:** §6 is explicitly marked draft; the document's own §1.0 ordering rule says "若 §6 早期 iteration 与 §1-§5 冲突,以 §1-§5 为准". This is **design exploration**, not a settled principle.

**For this work:** B is **the action of lifting this exploration out of draft and into actual scoping**, not the implementation of an already-settled principle. The walker-mechanism design sketch ([40_walker-mechanism-design-sketch.md](40_walker-mechanism-design-sketch.md)) is the artifact that takes the §6 draft, validates it against EntitySnapshot prior art (verified to exist in [src/kernel/sdk/facade.py:102-217](../../../../src/kernel/sdk/facade.py)), and proposes a sub-batched implementation. B's blueprint must explicitly cite this status: "lifting §6 draft exploration."

### #5 — Layer isolation invariants

Two distinct sources, separated for citation honesty:

**Cross-layer (Batch 8 §6):**
- "`kernel.application` must not import `kernel.sdk`"
- "application runtimes must not import `kernel.audit`"

— [2026-05-06_public-surface.md:322-324](../../../blueprints/archive/2026-05-06_public-surface.md)

**Helper-layer (Batch 2 §6):**
- "Helpers do not import from `kernel.sdk`"
- "Helpers do not call sibling runtime functions"
- "Helpers do not import `kernel.core.rules.frontier`"

— [2026-05-05_capability-ergonomics.md:74-80](../../../blueprints/archive/2026-05-05_capability-ergonomics.md)

**For this work:** A's builders inherit Batch 2's helper-layer constraints (no sibling runtime calls, no frontier import). B's walker, being cross-cutting across application + audit, inherits Batch 8's cross-layer constraint: **walker protocol is per-layer, not shared across application/audit boundary.** Each layer wraps its own DTOs in its own walker; the audit walker (B3 sub-batch, optional) lives in `kernel.audit` and does not depend on application walker types.

### #6 — No outward compat without user signal

> "v0.1.3 disable_condition 实现时,我推荐扩 `SDKStore.evaluate(disabled_locators=...)` kwarg 'for consistency';用户改成内部 `_evaluate_with_overlay`-style 路径,不出 public surface。事后证明用户的选择对 — 那个 kwarg 反正 reset 时也要 strip。"

— [60_lessons-learned.md:62-64, §2.3 example](../rule-replay-line-redesign-input/60_lessons-learned.md), exact verified

**For this work:** A and B add types/helpers to `kernel.application` (and `kernel.audit` for B3) that remain advanced importable. They do not enter `kernel.sdk.__all__`. They do not appear in README quickstart. They are documented in `kernel.application/docs/` as advanced importable additions, not as outward-stable contracts.

### #7 — Walker uniformity (access pattern), not output uniformity

Same access pattern across all walkers — `for x in walker:`, `walker.filter(...)`, `walker.find(...)`, `walker.first(...)`. **But each walker's view shape stays distinct (heterogeneous, per #3).**

**Prior art aligned with:** [src/kernel/sdk/facade.py:102-217](../../../../src/kernel/sdk/facade.py) `EntitySnapshot` / `AssertionNamespace` / `FieldAssertions` already implements this as namespace walker (`snap.assertions.field.active` / `.history` / `.at(t)` / `.version(v)`), with read-only enforced via `__setattr__` raising `FrozenSnapshotError`. New walker mechanism aligns with this naming/convention; does not reinvent it.

**Per-layer scope (resolves #5 conflict):** Walker uniformity holds **within a layer**. Application walker and audit walker may differ in shape across the application/audit boundary; what they share is the protocol vocabulary (`.filter`, `.find`, `for x in walker:`), not common base class.

### #8 — Walker is structurally read-only

Extends #2 from "evidence walker" to "all walkers." Walker exposes no `.set(...)`, `.append(...)`, `.delete(...)` — mutation goes through canonical write paths (SDK Rule DSL re-author / overlay re-recheck / RoundRecorder API / SDK batch).

**For this work:** All view classes are frozen dataclasses or `__setattr__`-guarded namespaces (mirroring `EntitySnapshot` pattern in #7).

### #9 — Lazy traversal

Walker is a lazy view — holds source object reference or immutable snapshot, computes view on demand, and avoids materializing a full view list at construction. Construction is normally O(1) (reference + index), except mutable-source DTO walkers may perform an immutable construction-time snapshot per #10. Actual view access is on-demand.

Implementations may employ private memoization to optimize lazy traversal, but cache is not a contract surface in v1. Memoization **MUST NOT** change any of: view equality (#17), `.stats` reported counters (#13), traversal result (#10 determinism), error timing (#12), or memory lifecycle (#16). Caching that affects any of these dimensions becomes part of the walker's observable contract and requires #P1 bundle revision before introduction.

### #10 — Determinism with explicit walker-class distinction

Adopting user's precise wording from 2026-05-07 review:

**DTO-backed walker.** Source is a frozen DTO (e.g. `SupportArtifact`, `ProofFrameRecheckResult`, `RoundEvent`). The same walker, traversed multiple times, **must** be deterministic — same view sequence, same view contents.

**Store-backed live walker.** Source includes mutable state (e.g. `Store.ledger`, `EntityWalker(store, ... )` over active facts). Snapshot semantics **must be declared explicitly**:

- **Preferred:** bind a read projection / snapshot at walker construction time; the walker reflects that snapshot for all subsequent traversals.
- **Permitted with caveats:** if only live-read is feasible, the walker may **not** claim cross-mutation repeatability. It may only claim within-traversal consistency (i.e. one `for x in walker:` loop sees a consistent view, but a second traversal after store mutation may differ).

**No silent race.** A live walker (one that does not bind a snapshot at construction) **must** make its live-read nature explicit either in API name (e.g. `LiveLedgerWalker` vs `LedgerSnapshotWalker`) or in docstring + module-level documentation. Walker classes that present as deterministic but secretly live-read **are forbidden by this principle**.

**Mutable-source DTO walker.** If a DTO-backed walker wraps a mutable structure (for example, `RuleSpec.where` or `CompiledDerivationPlan.body_ir`, both currently `list[Any]`), it must snapshot that structure into immutable internal state during `__init__` (for example, `tuple(source)`). Post-construction source mutation must not affect walker traversal. Snapshot failure raises `WalkerSnapshotError` (#12).

See #9 for caching constraints; memoization must not affect this principle's invariants.

### #11 — DTO subset projection + `.underlying` escape hatch

Walker views are stable subset projections, not mirrors of every source DTO field. DTOs remain canonical authority; walker views are ergonomic shells. Adding a field to a source DTO does not automatically require surfacing it on the walker view.

Each view class exposes `.underlying` as the explicit escape hatch to the wrapped underlying object:

```python
@property
def underlying(self):
    """Escape hatch to the wrapped underlying object. NOT a stable walker API."""
    if isinstance(self._underlying, Mapping) and not isinstance(self._underlying, MappingProxyType):
        return MappingProxyType(dict(self._underlying))
    return self._underlying
```

Rules:

- API name is `.underlying` only. No `.source`, `.carrier`, or `.raw` alias.
- For frozen dataclass / DTO-like sources, `.underlying` returns the original object reference.
- For dict / JSON mapping sources, `.underlying` returns `MappingProxyType(dict(source_dict))`: a shallow frozen copy at access time.
- `view.underlying` is an escape hatch, not a stable walker API.
- `.underlying` is excluded from structural equality and hash computation (#17).
- The `.underlying` escape hatch inherits the underlying object's mutability and deep-freeze properties; walker API itself remains read-only. Callers obtaining `.underlying` must treat it as read-only. Mutations through mutable nested objects are outside walker guarantees.

**Manual review gate:** When `kernel.application.protocol.*` or `kernel.core.store._support.*` adds a field, blueprint reviewer must explicitly confirm whether walker view should surface it or not. No pre-commit hook in v1. Upgrade trigger: walker extends to 2+ DTO families and a missed-surfacing incident has occurred at least once.

**Naming collision check:** When adding a new public view type, method, or property name, reviewer must explicitly check it does not collide with existing SDK / audit / core semantic vocabulary (for example, `source` for provenance, `carrier` for evidence carrier, `at` for time filter, `get` for None-on-miss).

### #12 — Error boundaries and exact-access naming

Walker APIs must encode miss semantics in names:

```python
# Lookup-by-criteria: miss is normal control flow
walker.find(branch_index=0, atom_index=99) -> AtomView | None

# Exact access: miss is a bug signal
walker.require_key("b0.a1:person:age") -> AtomView
walker.require_position(branch_index=0, atom_index=99) -> AtomView

# Parse: invalid input raises
parse_atom_key("invalid_format") -> AtomKeyView

# Follow declared reference: miss means data inconsistency
support.lookup_assertion(unknown_asrt_id) -> AssertionView
```

Rules:

- `find(...)` may miss and returns `None`.
- `require_key(...)` and `require_position(...)` raise `WalkerLookupError` on miss. They replace the earlier `get` / `at` wording to avoid SDK collisions (`SDKStore.get(...)` is None-on-miss; `FieldAssertions.at(t)` is temporal filtering).
- `parse_atom_key(...)` raises `WalkerParseError` on invalid input.
- `lookup_<thing>(...)` follows a declared reference and raises `WalkerReferenceError` on miss.

Error hierarchy:

```text
WalkerError(Exception)
├── WalkerLookupError
├── WalkerParseError
├── WalkerReferenceError
├── WalkerSnapshotError
└── UnboundedStreamError
```

Every `WalkerError` subclass exposes nullable standard fields:

```python
query: object | None = None
source_id: str | None = None
locator: object | None = None
```

See #11 for naming-collision review discipline. See #9 for caching constraints; memoization must not affect this principle's invariants.

### #13 — Observability isolation

B1/B2 walker modules emit no logs, warnings, or audit events. They use introspection rather than side-effect observability:

- `__repr__` is mandatory on walker classes and should include `source_id`, current position, and last filter where applicable.
- `.stats` returns a frozen access-time snapshot of internal counters. Accessing `.stats` does not advance traversal or mutate walker state.
- `WalkerError` subclasses expose `.query`, `.source_id`, and `.locator` (#12).
- No `find(..., explain=True)` or similar verbose-mode parameters in B1/B2.

B3 may later define a caller-provided progress callback, but B1/B2 do not predefine that callback contract.

See #9 for caching constraints; memoization must not affect this principle's invariants.

### #14 — Bounded scope: `Walker` vs future `StreamWalker`

DTO-backed `Walker` instances need no bound parameter. Their source must be an in-memory structure that is immutable or snapshotted into immutable internal state (#10).

Future store-backed / live `StreamWalker` is out of B1/B2 scope, but any future B3 implementation must satisfy at least one bound condition at construction time, or raise `UnboundedStreamError` fail-fast:

| Bound condition | Satisfies |
|---|---|
| Hard cap | `limit` is a positive int |
| Snapshot | `snapshot=True` and `max_snapshot_items` is a positive int |
| Pre-bounded source | source exposes `bounded_size_hint() -> int` returning a non-negative int |

Rules:

- At least one bound condition is required; multiple bounds are allowed and concrete combination semantics are implementation-specific.
- `snapshot=True` without positive `max_snapshot_items` raises `UnboundedStreamError`.
- `bounded_size_hint()` return value must be validated as a non-negative int; `0` is valid for an empty source.
- `__len__` alone is not accepted as proof of boundedness.
- `filter` is always allowed but never alone constitutes a bound.
- `UnboundedStreamError` is raised during `__init__`, not during first traversal.

### #15 — Single-thread walker instances

Walker instances are single-thread objects; share source, not walker.

The source a walker wraps may be shared across threads if it is frozen or otherwise safe to share. Construct a separate walker per thread. Stats counters, filters, and lazy traversal state are not atomic and do not promise cross-thread correctness.

### #16 — Memory / lifecycle

DTO-backed walkers have no close lifecycle. Materialized views do not depend on walker state after creation.

If the original input was mutable and the walker snapshotted it during construction (#10), post-construction mutation does not affect walker traversal or already-created views. B3 may later define `StreamWalker.close()` / context-manager behavior, but that lifecycle is out of B1/B2 scope.

See #9 for caching constraints; memoization must not affect this principle's invariants.

### #17 — Equality, identity, and hashability

View equality is structural where defined; identity is not stable; hashability is only guaranteed for simple locator-like views.

Rules:

- Repeated `find(...)` calls may return equal views but do not guarantee the same object identity.
- Structural equality covers surfaced view fields only.
- `.underlying` is explicitly excluded from equality and hash computation.
- Full payload views may be non-hashable if surfaced fields contain non-hashable structures. Simple locator-like views should prefer hashable surfaced fields.
- Walkers themselves use default object identity; callers should not compare walker instances for semantic equality.

See #9 for caching constraints; memoization must not affect this principle's invariants.

### #18 — Serialization

Walkers and views have no stable serialization contract; walker pickling is explicitly rejected.

Do not rely on pickled walker or view round-trips for compatibility. If serialization is needed, serialize the canonical source DTO / audit package through its existing serializer, or design a separate outward DTO in a future blueprint.

### #19 — Test contract

Every walker family needs common contract tests plus behavior-specific tests.

V1 testing posture:

- Use the repository's existing `unittest`-first, flat `tests/test_*.py` style.
- Keep shared fixtures flat, e.g. `_walker_fixtures.py`, rather than introducing `tests/walker/`.
- No Hypothesis dependency in v1.
- No coverage threshold added by this bundle.
- Contract tests should cover: `find` miss returns `None`; `require_key` / `require_position` miss raises; `.stats` is frozen access-time snapshot; DTO-backed determinism; `.underlying` escape hatch behavior; walker pickling rejected.
- Behavior-specific tests cover concrete walker semantics, such as IR atom parsing or `SupportArtifact.lookup_assertion(...)`.

### #P0 — Conflict resolution meta-principle

Known conflicts must be documented in the bundle with intended resolution. Surface conflicts may be listed as "resolved by interpretation" and are not carve-outs.

For new conflicts during implementation, use conservative interpretation first:

1. Preserve authority / layer / read-only boundaries first.
2. Narrow ergonomic surface second.
3. Avoid creating new outward API commitments.
4. If conservative interpretation blocks implementation, trigger #P1 revision flow.
5. A task blueprint may carve out a principle but may not silently override or rewrite it.

Fallback heuristic, not strict numeric priority:

| Tier | Meaning | Principles |
|---|---|---|
| 1 | Authority | #1, #4a |
| 2 | Layer isolation | #5, #7 layer aspect |
| 3 | Read-only / no source mutation | #2, #8, #16 read-only aspect |
| 4 | Ergonomic walker surface | #7 access aspect, #11-#14 |
| 5 | No new outward commitment | #6 |

Tier 5 is not "lowest and sacrificable"; it constrains Tier 4. Ergonomic surface may be narrowed, but must not create new outward compatibility commitments.

When a principle spans multiple tiers, the higher-tier aspect dominates. For #7, per-layer scope takes precedence over access-pattern uniformity.

Known conflicts:

| Conflict | Resolution |
|---|---|
| #6 no outward compat vs #14 explicit future names like `StreamWalker` | Explicit names are design discipline, not outward compatibility commitments. v0.x may rename them under #6; users accept preview instability. |
| #3 heterogeneity vs #19 common contract tests | Contract tests cover access-pattern uniformity (#7), not output-shape uniformity. |
| #9 lazy traversal vs #15 single-thread walker | Lazy semantics hold inside single-thread traversal. Sharing a walker across threads is caller misuse. |
| #2/#8 read-only vs future B3 close lifecycle | `close()` is lifecycle state, not source-data mutation. |
| #7 per-layer walker vs cross-layer caller use | Walkers remain per-layer. Cross-layer bridging is caller-owned explicit conversion. |

### #P1 — Principle revision flow meta-principle

Principles are defaults. Each implementation blueprint must either align with relevant principles or explicitly carve out a deviation.

Rules:

1. A carve-out must include principle id, reason, scope, impact, and reviewer ack.
2. In v0.1, "reviewer ack" means explicit user approval in the blueprint/audit trail.
3. A single context-specific deviation may stay inside the task blueprint.
4. Context-specific means the deviation is justified by this blueprint's specific scope and would not naturally apply to other walker or capability work.
5. Repeated carve-outs against the same principle across multiple blueprints trigger bundle revision.
6. Newly discovered missing principle or misframed principle triggers bundle revision directly.
7. Bundle revision is a discrete event recorded in this bundle README's `Verification log`.
8. Bundle revision proposal must state historical implementation handling: `grandfather`, `retrofit`, or `deprecate`. The proposal may specify different handling per historical implementation, but each affected implementation must be explicitly named with its chosen handling. When the revision involves rename or deprecation, the proposal must additionally state whether affected docs, tests, and examples are synchronously updated, deferred for follow-on, or explicitly carved out of the revision scope.
9. No hard revision-frequency cap. If revisions churn, the audit log is the signal; do not add process throttling now.
10. Carve-outs persist for as long as the implementation persists. Refactoring, deprecating, or replacing the implementation triggers carve-out review.

---

## What this principle set forbids

A consolidated negative list, derived from the principles above:

| Forbidden | By which principle(s) |
|---|---|
| Adding builder / walker / view substrate in `kernel.sdk` | #1 |
| Walker exposing `.set` / `.append` / `.delete` / `.mutate` interfaces | #2, #8 |
| Walker generating `RulePatch` / `Action` / suggested rewrites | #2 |
| Designing one unified `Walker[T]` base class to cover all capabilities | #3 (heterogeneity) — but uniform protocol methods are OK (#7) |
| Walker eagerly materializing all view data at construction | #9 |
| Cache behavior that changes equality, stats, traversal result, error timing, or memory lifecycle | #9 |
| Live store-backed walker not declaring its live nature in name or docs | #10 (silent race ban) |
| Application walker types imported by audit walker (or vice versa) | #5 (per-layer isolation), #7 (per-layer scope) |
| Adding new helpers / walker classes to `kernel.sdk.__all__` | #6 |
| Adding new helpers / walker classes to README quickstart | #6 |
| Promoting walker types as outward compat contracts before user signal | #6 |
| Naming walker escape hatch `.source`, `.carrier`, or `.raw` | #11 |
| Using raise-on-miss `get(...)` or positional `at(...)` in walkers | #12 |
| In-application Rule mutation API (use SDK Rule DSL re-author instead) | #4a (intent-only at SDK), #2/#8 (read-only) |
| Refactoring existing protocol DTOs to "fit walker shape better" | #1 (application-first; protocol is canonical), #6 |
| Treating future `StreamWalker` naming as an outward-compat promise | #6, #P0 |
| Silently overriding a principle inside a task blueprint | #P1 |

---

## Why A + B over the alternatives

### Five reasons A + B is the right starting point

**1. Both fix implicit debt that no current deferred catalog tracks.**

Per [10_implicit-gaps.md](10_implicit-gaps.md):

- Gap 2 (walker mechanism, refined per verification): identified as deferred concept in §6 draft of [check-operation-conceptual-interaction.md](../rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md) but never scheduled. Not in §5.5.5, not in master plan §3. **Refined scope: only ~4-5 raw-tuple objects need walker; most DTOs are already structured (per Agent 2 verification finding).**
- Gap 3 (ergonomic helpers Q1/Q2/Batch 4-7): the [Batch 2 pattern](../../../blueprints/archive/2026-05-05_capability-ergonomics.md) covered Q3/Q4/Q5 only. Extending to remaining capabilities was never explicitly scheduled.

These gaps will keep biting us in every future direction. Closing them now prevents repeated rework.

**2. Both are pure additions to `kernel.application` (and `kernel.audit` for B3 only) with zero public-API commitment.**

- No SDK shell → no outward compatibility lock-in
- No service/agent dependency → no cross-layer coordination
- No protocol DTO change → no cross-cutting drift risk
- Conforms to Decision 1 ("SDK wrapper 推到第二步") and the application-first authority principle (#1)

**3. Both are precedented and have proven patterns.**

- A literally extends Batch 2's already-shipped helpers
- B aligns with `EntitySnapshot` namespace walker pattern that already exists in `kernel.sdk.facade` (verified 2026-05-07 — see #7 prior art citation). B is the application-layer counterpart of an already-shipped SDK-layer pattern.

**4. Both are downstream multipliers.**

After A + B:
- Demo work (F) becomes much smaller — "advanced" notebooks become less advanced
- Future SDK shells (C) have a much cleaner foundation — `sdk.explain(...)` can return walker views (B) instead of raw `SupportArtifact`, and use intent-shaped builders (A) internally
- Audit and automation tools (the actual current consumers per Gap 1) immediately benefit

**5. Effort is bounded and parallel-safe.**

- A: ~1-2 weeks (9 helpers × focused tests + module docs)
- B: ~2-3 weeks total split across sub-batches B1 + B2 (mandatory) + B3 (optional) — see [40_walker-mechanism-design-sketch.md](40_walker-mechanism-design-sketch.md)
- Independent files, independent test suites; can run in either order or simultaneously

---

## Why not start with C (SDK shell)

**Two reasons C should wait:**

1. **C without B exposes raw evidence shape as outward API.** If `sdk.explain(...)` returns a `SupportArtifact` directly, we lock in its current raw-tuple shape as outward-compat surface. Better to land B first so the SDK shell can return walker views (designed for outward consumption).

2. **C carries outward compatibility commitment.** Once `sdk.explain(...)` ships, its shape is locked. Per Batch 8 falsifier #18 (PARTIAL): "A narrow SDK shell for Check/Diagnose could be designed later, but source evidence does not prove it is needed for v0.1 public close-out." The evidence basis is still no stronger than it was at Batch 8. Wait until A + B land and a real consumer surfaces.

**That said:** if a real user-facing workflow appears (e.g. someone wants to ship a `factpy explain` CLI, or the dialog agent track restarts and needs a clean entry point), C becomes immediately viable.

---

## Why not pursue D (dialog agent) now

D is strategically sound but:

- Multi-week to multi-month effort
- Requires service layer + multi-LLM provider integration (new dependencies)
- Zero current user signal (per [Gap 1](10_implicit-gaps.md))
- v0.1 is developer-first by design and execution

**However:** D's existence suggests we should declare Gap 1 explicitly. Suggested side action:

> Draft a short blueprint, e.g. `2026-05-08_v0.1-audience-narrowing-declaration.md`, that records:
> - v0.1 audience = Python-fluent developers / integrators (per [SDK alignment matrix](../../../../src/kernel/sdk/docs/01_alignment_matrix.en.md))
> - Dialog agent layer formally deferred to v0.2+ (cite [2026-03-29_dialog-agent-blueprint-v1.md](../../../blueprints/active/2026-03-29_dialog-agent-blueprint-v1.md))
> - Reactivation trigger: explicit product decision to invest in non-technical SME entry point
>
> This declaration would resolve Gap 1 without requiring any code work.

This side action is independent of A/B and could be done in a single small commit.

---

## Suggested execution order

```
Week 1-2:  [A]   Application ergonomic helpers
              ↓ (parallel-safe)
Week 1-3:  [B1] IR walker + common find/filter protocol  (mandatory)
           [B2] Evidence cross-reference helpers          (mandatory)
           [B3] Audit walker                              (optional — only if AuditQuery / RoundEvents prove first real consumer)
              ↓ (also: side action)
              [Gap 1 declaration] short blueprint
              ↓ (after A+B)
Week 4+:   [C]  Step 0 spike for narrow Check+Diagnose SDK shell
              ↓ (after C decision)
              [F]  Demo refresh — naturally easier
              ↓ (when ready)
              [E]  Release publish (user-gated, can fire any time)
```

A and B are genuinely independent and can be one developer-pair per blueprint, parallel. The Gap 1 declaration can land in the same week. C should not start until A + (at least B1 + B2) land — B3 is not required for C because Check+Diagnose return DTO-backed evidence (already structured), not store-backed live data.

---

## What "scoping next" looks like — concrete first action

**Concrete first action recommended:** Draft two Step 0 / scoping blueprints (no code yet):

1. **`docs/blueprints/active/2026-05-08_application-ergonomic-helpers-extension.md`** — Direction A
   - Problem: Gap 3 from this bundle
   - Goal: Extend Batch 2 pattern to cover Q1/Q2/Batch 4-7 (9 helpers; see [10_implicit-gaps.md §3](10_implicit-gaps.md) for proposed signatures)
   - Non-goals: No SDK shell, no DTO shape change, no public surface change
   - Acceptance: each helper builds the same DTO as the manual demo path, focused tests, module docs updated
   - Implementation plan: per-capability helper file or one consolidated module (extending `kernel.application.capability_helpers`)
   - Cite: this bundle (`docs/references/working/post-routemap-direction-selection-input/`), Batch 2 (`2026-05-05_capability-ergonomics`), Decision 1 (`docs/references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md`)
   - Boundaries-and-Invariants section: lock principles #1, #4a, #5 (helper-layer), #6, plus Batch 2 §6 helper-layer constraints

2. **`docs/blueprints/active/2026-05-08_walker-mechanism.md`** — Direction B
   - Problem: Gap 2 from this bundle
   - Goal: **Lift the walker concept from §6 draft of `check-operation-conceptual-interaction.md` into actual scoping**, aligned with EntitySnapshot prior art (`src/kernel/sdk/facade.py:102-217`), and implement sub-batches B1 + B2 (mandatory) + B3 (optional based on consumer signal). See [40_walker-mechanism-design-sketch.md](40_walker-mechanism-design-sketch.md) for sub-batch design.
   - Status framing: this is **not** "implement a settled concept design"; this is **lift design exploration out of draft and validate it through implementation**. The blueprint must explicitly state this status framing in §1 Problem.
   - Non-goals: No SDK exposure, no protocol DTO change, no audit walker (B3) unless consumer signal arrives; no walker `Walker[T]` base class (heterogeneity per #3); no live walker without explicit snapshot semantics (per #10); no `.source` / `.carrier` / `.raw` escape hatch; no raise-on-miss `get(...)` or positional `at(...)` exact-access API
   - Reconciliation requirement: read [2026-03-28_evidence-graph-unified-explain.md](../../../blueprints/active/2026-03-28_evidence-graph-unified-explain.md) and explicitly confirm walker mechanism complements (not overlaps) Evidence Graph DTO. Verification 2026-05-07 already confirmed: Evidence Graph is rendering DTO, walker is iteration abstraction — no overlap. Blueprint records this conclusion.
   - Acceptance: walker exposes `for x in walker:` / `.filter` / `.find` / `.first` / `.require_key` / `.require_position` over targeted objects (B1: Rule.where + Plan.body_ir IR walker with construction-time snapshot; B2: SupportArtifact cross-reference + AssertionView lookup); read-only enforced structurally (per #8); determinism honored per #10; no new export to `kernel.sdk.__all__`
   - Cite: this bundle, conceptual interaction design §6 (draft, explicitly marked), Decision 1, EntitySnapshot prior art at `src/kernel/sdk/facade.py:102-217`
   - Boundaries-and-Invariants section: lock principles #1, #2, #3, #5, #6, #7, #8, #9, #10-#19, #P0, and #P1

Each blueprint follows the standard project workflow: draft → scoped → user review → implementing → implemented → archived.

After A + B archive, revisit this bundle's [20_candidates.md](20_candidates.md) for the next direction (likely C with a Step 0 spike, possibly E if user calls publish).

---

## What this recommendation is NOT

- **Not a commitment:** This is a recommendation to be reviewed and accepted/rejected/modified by the project lead.
- **Not a critique of Batch 8:** Batch 8 made the right call for what it was scoped to do. The ergonomic gaps surfaced here are unscheduled additions, not unfinished Batch 8 work.
- **Not the only valid path:** Going straight to E (publish) is also valid if the goal is "ship what we have and gather real signal." Going to D (dialog agent) is also valid if v0.2 scope is being seriously considered. The recommendation here optimizes for "fix implicit debt before adding new commitments."
- **Not asserting walker is a settled principle.** Per #4b, walker is design exploration we are choosing to lift out of draft. The new blueprint (B) is the venue where it gets validated through implementation. If implementation surfaces fundamental issues with the §6 draft direction, B's Step 0 may legitimately re-scope or reject the walker direction.

---

## Verification log (2026-05-07)

This recommendation was hardened through a 3-agent parallel verification round. Findings driving revisions:

| Issue found | Fixed in |
|---|---|
| Principle #4 cited §6.3.B.3 / §6.4.B.2 from draft section the document declares non-binding | Split into #4a (canonical §2.1) + #4b (downgraded to "design exploration we are lifting out of draft") |
| Principle #3 attribution slightly off (cited "§5.4 falsifier #3 row" — actually §5.4.A Spike Verdict #3) | Citation corrected |
| Principle #5 conflated Batch 8 §6 + Batch 2 §6 sources | Disaggregated; cross-layer vs helper-layer constraints separated |
| Walker scope over-estimated (claimed ~10 objects need walker; actually most DTOs already structured) | Refined to 4-5 raw-tuple objects; sub-batched into B1 + B2 + optional B3; total effort revised 3-5w → 2-3w |
| Determinism principle missing (lazy walker without snapshot semantics is a race risk) | Added #10 with user's precise wording (DTO-backed vs store-backed live walker, snapshot semantics, no silent race) |
| EntitySnapshot prior art not cited | Added to #7; B blueprint will cite as alignment target |
| Per-layer walker scope (application vs audit) ambiguous in #7 | Resolved: walker protocol is per-layer, not cross-layer shared (consistent with #5) |

Later 2026-05-07 synthesis added #11-#19 and #P0/#P1 after SDK syntax research and minimal transcription verification. Key corrections from that later pass are recorded in [README.md §Verification log](README.md): `.underlying` replaces `.source`/`.carrier`, exact access uses `require_key` / `require_position` rather than `get` / `at`, mutable IR walkers snapshot at construction, #9 is the single source of truth for cache constraints, and the only finalized B blueprint acceptance gate from D is "no new export to `kernel.sdk.__all__`."
