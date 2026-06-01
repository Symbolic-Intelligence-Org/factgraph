# Audit: docs/official/kernel/quickstart/*.md vs Shipped Runtime

- Status: complete
- Created: 2026-06-01
- Last Updated: 2026-06-01
- Authority: working triage document; informs `workflow/blueprints/active/2026-06-01_quickstart-docs-sync.md`. Implementation decisions follow only after audit-row review.
- Inputs:
  - 12 quickstart docs at `docs/official/kernel/index.md` + `docs/official/kernel/quickstart/{index,first-factgraph,schema,read-write,assertions,database,rules-and-inferences,semantics,evidence,persistence,namespace-map}.md`
  - Shipped source: `src/factgraph/` (entire tree)
  - Audit source ref: branch HEAD `d12352e4` (docs-sync slice after v0.2.0 release-surface-audit cycle)
- Outputs:
  - 33 actionable findings: 18 DRIFT + 13 AMBIGUOUS + 2 BUG
  - Recommended fix slice covering P0 (user-blocker) + P1 (broken links) + P2 (signature drift) + P3 (prose polish)
- Related:
  - 7 parallel general-purpose agents executed 2026-06-01 produced 28 findings
  - Supplementary "查缺补漏" verification added 5 more findings
  - Predecessor: `workflow/blueprints/archive/2026-06-01_release-surface-audit.md` (just-archived)
- Source intent: post-Q-NAMING-F + post-Baseline-Cleanup + post-release-surface-audit alignment of user-facing quickstart docs with shipped code
- Branch: `v0.2.0-blueprint-quickstart-vs-shipped-audit-2026-06-01` (forked from `d12352e4`)

## 1. Scope

Primary surface (read completely per Rule 1):

| Doc | LOC | Audited by |
|---|---|---|
| `docs/official/kernel/index.md` | 12 | agent 1 + supplementary |
| `docs/official/kernel/quickstart/index.md` | 15 | supplementary |
| `docs/official/kernel/quickstart/first-factgraph.md` | 120+ | agent 1 |
| `docs/official/kernel/quickstart/schema.md` | 320+ | agent 4 |
| `docs/official/kernel/quickstart/read-write.md` | 220+ | agent 3 |
| `docs/official/kernel/quickstart/assertions.md` | 310+ | agent 3 |
| `docs/official/kernel/quickstart/database.md` | 510+ | agent 4 |
| `docs/official/kernel/quickstart/rules-and-inferences.md` | 700+ | agent 5 |
| `docs/official/kernel/quickstart/semantics.md` | 470+ | agent 7 |
| `docs/official/kernel/quickstart/evidence.md` | 580+ | agent 6 |
| `docs/official/kernel/quickstart/persistence.md` | 310+ | agent 4 |
| `docs/official/kernel/quickstart/namespace-map.md` | 250+ | agent 2 + supplementary |

Out of scope:
- Module docs at `src/factgraph/*/docs/` (covered by `src/factgraph/AGENTS.md` convention, not this audit)
- Workflow docs at `workflow/` (governance, not user-facing)
- Non-quickstart docs at `docs/` root (e.g., SECURITY.md)

## 2. Inputs

- 7 parallel general-purpose agents (~393 claims audited, 28 findings produced)
- Supplementary 查缺补漏 verification by Claude after agent results (5 additional findings)
- Source-of-truth verification via direct read + grep of `src/factgraph/`
- Cross-reference verification of inter-doc links/anchors

## 3. Triage Table

5-state classification per CADENCE Stage 1.

### 3.1 P0 — User-executable failure (2 sites)

| # | Doc:Line | Claim | Code Reality | Class |
|---|---|---|---|---|
| 1 | namespace-map.md:143 | "`fg.rules.inspect(rule_or_inference_or_query)` shows structure for in-memory `Rule`, `Inference`, or `Query` values" | Code rejects `Query` with `SDKStoreError("rules.inspect(...) expects SDK Rule or Inference")` at `sdk/store.py:_inspect_rule_or_inference` | (c) shape conflict |
| 2 | rules-and-inferences.md:84 | "`Rule.when` field accepts core-level atom objects (`PredAtom`, `CmpAtom`, `BuiltinAtom`, `NotAtom`, `InAtom`, `AggregateAtom`)" | `AggregateAtom` is a `Term`, NOT an `Atom`. Code at `core/rules/where_ast.py:97` defines `Atom = PredAtom \| RuleRefAtom \| CmpAtom \| InAtom \| BuiltinAtom \| NotAtom`. Rule `_ALLOWED_ATOM_TYPES` at `application/protocol/rule.py:42` excludes `AggregateAtom`. | (c) shape conflict |

### 3.2 P1 — Broken cross-references (4 sites, includes new BUG from supplementary)

| # | Doc:Line | Claim | Code Reality | Class |
|---|---|---|---|---|
| 3 | evidence.md:113 | `[Canonical quantitative carrier](assertions.md#canonical-quantitative-carrier)` | `assertions.md` has NO heading "Canonical quantitative carrier". Available headings: Writes return assertion ids / AssertionRecord shape / Field and entity assertion views / Canonical filtering / Graph-level assertion lookup / Retracting one assertion / Complete example / Syntax checklist | (c) shape conflict |
| 4 | semantics.md:143 | `[Write assertions](assertions.md#raw-uncertainty-raw_kind-and-bound)` | `assertions.md` has NO heading "Raw uncertainty: raw_kind and bound" | (c) shape conflict |
| 5 | semantics.md:326 | Prose "See assertions.md 'Canonical quantitative carrier'" | Same missing section as #3 | (c) shape conflict |
| 6 (**NEW**) | namespace-map.md:144 | `[Rules and inferences](rules-and-inferences.md#evaluate-an-inference)` | Actual heading is `## Legacy compatibility: evaluate an Inference` at line 504 → GitHub anchor `#legacy-compatibility-evaluate-an-inference`, NOT `#evaluate-an-inference` | (b) small gap |

### 3.3 P2 — Signature/wording drift (13 sites, includes 4 new factpy-kernel rename from supplementary)

| # | Doc:Line | Doc says | Code reality | Class |
|---|---|---|---|---|
| 7 | namespace-map.md:109 | `fg.entities.where(EntityCls, **partial_filters)` | `where(entity_cls, *, policy=_POLICY_TOMBSTONE, limit=None, _meta=None, **field_filters)` — missing `*, policy=, limit=, _meta=` | (b) small gap |
| 8 | namespace-map.md:109 | `fg.entities.match(EntityCls, rule_or_expr, **ports)` | `match(entity_cls, template, *, limit=None, **port_constraints)` — missing `*, limit=` + param name mismatches | (b) small gap |
| 9 | namespace-map.md:111 | `fg.assertions.by_ids(asrt_ids)` | `by_ids(asrt_ids, *, strict=False)` | (b) small gap |
| 10 | namespace-map.md:127 | `fg.assertion_views.create(name, asrt_ids=[...])` / `update(name, asrt_ids=[...])` | `create(name, *, asrt_ids=None, asrts=None)` / `update(name, *, asrt_ids=None, asrts=None)` | (b) small gap |
| 11 | namespace-map.md:224 | `fg.batch(meta=...)` | `batch(*, meta=None)` — kw-only marker missing | (b) small gap |
| 12 | namespace-map.md:176-191 | Table "Everything in `factgraph.sdk.__all__`, grouped by purpose" | `__all__` has 64 entries; namespace-map.md table backticks ~46 — ~18 omissions | (b) small gap |
| 13 | database.md:32-33 | "`FactGraph.save_workspace()` and `FactGraph.load_workspace(...)` remain the high-level workspace path" | `save_workspace` is an **instance** method (`fg.save_workspace()`); only `load_workspace` is classmethod | (b) small gap |
| 14 | database.md:205-206 | "`ingested_at` is required for snapshot projection policies" | `commit_assertions` itself does NOT validate `ingested_at`; required ONLY for downstream `:active` projection | (b) small gap |
| 15 | database.md:339 | "SDK views are different" table contrasts SDK view shape as `(name, asrt_ids)` only vs Database view's 6 fields | Both use the **same** `FrozenAssertionSet` dataclass (6 fields: name, db_id, base_tx_id, schema_digest, asrt_ids, view_digest); only persistence + anchors differ | (b) small gap |
| 16 | read-write.md:40 | "`fg.entities.ref(...)` returns the deterministic reference and is useful when the graph has already seen that coordinate" | `ref()` registers shadow store for ANY identity (including unseen); no "already seen" precondition | (b) small gap |
| 17 (**NEW**) | index.md:1-3 | "factpy-kernel official docs" and "canonical user documentation for `factpy-kernel`" (2 occurrences on these lines) | Package renamed to `factgraph` (`pyproject.toml: name = "factgraph"`); should be `factgraph` | (b) small gap |
| 18 (**NEW**) | namespace-map.md:196 | "some are out of scope for `factpy-kernel` entirely" | Same — should be `factgraph` | (b) small gap |
| 19 (**NEW**) | quickstart/index.md:3 | "A sequential path through the public `factpy-kernel` API" | Same — should be `factgraph` | (b) small gap |

### 3.4 P3 — Prose/ambiguity (13 sites)

| # | Doc:Line | Issue | Recommended improvement | Class |
|---|---|---|---|---|
| 20 | first-factgraph.md:55-57 | `fg.entities.ref()` framed as lookup for "already-known" coordinate | Same fix as #16: `ref()` also registers shadow-store regardless of prior visibility | (b) small gap |
| 21 | first-factgraph.md:119-120 | Syntax checklist repeats the same "already known" framing | Same fix as #16/#20 | (b) small gap |
| 22 | namespace-map.md:110 | `fg.fields.*` signatures use `ref` as param name; code uses `e_ref`. Also `retract`/`delete` accept Identity descriptor | Update param name to `e_ref` (or note alias); document Identity descriptor acceptance | (b) small gap |
| 23 | namespace-map.md:111 | `fg.assertions.retract(asrt_id, meta=None)` — `meta=` is keyword-only | Add `*,` to signature | (b) small gap |
| 24 | namespace-map.md:145 | `fg.eval.evaluate(...)` lists accepted kwargs but omits the wide explicit-rejection set (`view=`, `policy=`, `semantics_profile=`, `mode=`, `temporal_view=`, `registry=`, `engine_options=`) | Add note about explicit-rejection kwargs | (b) small gap |
| 25 | namespace-map.md:173 | `fg.package.export_package(out_dir, options)` — `options` should be typed as `ExportOptions` | Add type hint `options: ExportOptions` | (b) small gap |
| 26 | namespace-map.md:236 | "`fg.assertions.field(...)` returns `AssertionRecordSet`" mixed with chain-from-AssertionView | Clarify: `field(...)` returns `AssertionView`; `active`/`all` properties return `AssertionRecordSet` | (b) small gap |
| 27 | read-write.md:36 | "It is an opaque `idref_v1` token" — technically parseable via `entity_type_from_ref` | Rephrase as "Treat as opaque; internal canonical encoding via `idref_v1` prefix" | (b) small gap |
| 28 | read-write.md:145 / assertions.md (multiple) | "raises `INV_7C_IDENTITY_PROTECTED`" — actually raises `SDKStoreError` with that code | Rephrase as "raises `SDKStoreError` with code `INV_7C_IDENTITY_PROTECTED`" | (b) small gap |
| 29 | schema.md:195 | No warning about reusing the original class after `fg.schema.extend(new_User)` raising `SDKStoreError` | Add brief note about the runtime guard | (b) small gap |
| 30 | database.md:278-283 | Snippet references `other_record.asrt_id` without prior definition | Add a defining line for `other_record` | (b) small gap |
| 31 | evidence.md:36 | `engine_version` / `adapter_version` not noted as `str | None` (optional) while `config_digest` is explicitly noted | Add "or `None`" qualifier | (b) small gap |
| 32 | evidence.md:236-237 | Failed-explanation example uses `fg.fields.set(...)` to mutate state; would reject on attached SDKStores | Note example assumes non-attached SDKStore | (b) small gap |
| 33 | semantics.md:174-175 | "ProbLog point export supports `lower`, `midpoint`, `upper`" — enumeration not exhaustive (`reject` also valid policy) | Note `reject` also valid policy (which blocks export) | (b) small gap |

## 4. Open Questions

None. All findings have clear fix paths — no semantic conflicts requiring user decision.

## 5. Frictions

- **F1**: `factpy-kernel` legacy name in 4 sites is a systematic drift caught only by supplementary check (7 agents focused on API claims, not project naming). Lesson: future audit prompts should explicitly include "project naming consistency" as a verification axis.

- **F2**: Broken anchors are easy to miss (1 caught by agents, 1 caught by supplementary). Lesson: future audit prompts should explicitly include "all cross-references resolve to existing anchors".

- **F3**: Agent 2's "27 omissions from `__all__`" was a rough estimate; supplementary confirmed actual `__all__ = 64` entries vs ~46 backticked = ~18 omissions. The "27" figure is wrong but the underlying drift is real.

## 6. Cross-doc seams (out of scope)

- Module docs at `src/factgraph/*/docs/`: per `src/factgraph/AGENTS.md` convention, module docs are the "current implementation truth" — may have their own drift but out of this audit's scope (this audit focuses on docs/official/kernel/ which is the publish surface).

- Workflow audit + blueprint docs at `workflow/`: internal governance, not user-facing.

## 7. Recommendations for blueprint

### 7.1 Required fixes (P0 + P1, 6 sites)

These are runtime-error / broken-link sites that any user following the doc would hit:

- **PF-R1**: Fix namespace-map.md:143 (`fg.rules.inspect(Query)` claim) — remove `Query` from supported types
- **PF-R2**: Fix rules-and-inferences.md:84 (`AggregateAtom` in Atom list) — remove `AggregateAtom`
- **PF-R3**: Fix 3 dead links by ADDING the missing sections to assertions.md (since the references come from multiple docs and signal a real content gap):
  - Add section "Canonical quantitative carrier" describing `raw_kind` / `bound` pairing (referenced by evidence.md:113 + semantics.md:326)
  - Add section "Raw uncertainty: raw_kind and bound" (referenced by semantics.md:143)
- **PF-R4**: Fix namespace-map.md:144 anchor `#evaluate-an-inference` → `#legacy-compatibility-evaluate-an-inference`

### 7.2 Required fixes (P2, 13 sites)

Signature drift + project name fixes — important for v0.2.0 publish surface quality:

- **PF-R5**: Update all namespace-map.md signatures with correct kw-only markers and full parameter sets (#7-#11)
- **PF-R6**: Soften namespace-map.md:176-191 "Everything in `__all__`" to "Selected exports, grouped by purpose" (or expand to actual 64-entry table) (#12)
- **PF-R7**: Fix database.md inaccuracies (#13-#15): save_workspace classmethod confusion, ingested_at requirement scope, SDK view shape contrast
- **PF-R8**: Rephrase read-write.md:40 `ref()` description (#16) — same fix needed at first-factgraph.md:55-57 + :119-120 (#20-#21)
- **PF-R9**: Rename `factpy-kernel` → `factgraph` in 4 sites: index.md ×2, namespace-map.md ×1, quickstart/index.md ×1 (#17-#19)

### 7.3 Recommended fixes (P3, 13 sites)

Prose polish — improves clarity but not blocking:

- **PF-r1 to PF-r13**: Apply each P3 fix per the recommendation column in §3.4

### 7.4 Stack-ready determination

- **Tentative**: stack-ready YES after PF-R1..PF-R9 (P0 + P1 + P2) land in Step 4.7 fix slice. PF-r1..PF-r13 (P3) recommended but not blocking.

## 8. Audit method notes

- 7 parallel general-purpose agents executed; each given a focused subset of docs and source paths
- Supplementary verification by Claude found 5 additional findings (1 BUG + 4 DRIFT)
- All findings verified by direct source read + grep
- 0 src/ touches (read-only audit)
- Q-PR1 5 sacred paths 0-diff vs `4c472b50` preserved through audit
- Sacred master `562c74195df4...` unchanged
- Dirty baseline 8 entries preserved
- 7 agent reports retained as conversation context for later cross-reference

## 9. Audit completeness checklist

- [x] All 12 quickstart docs scope-covered
- [x] 393 claims audited (estimated)
- [x] 33 actionable findings classified (18 DRIFT + 13 AMBIGUOUS + 2 BUG)
- [x] Cross-references verified (4 broken anchors total)
- [x] Project naming consistency verified (4 `factpy-kernel` residuals)
- [x] `__all__` exports inventory verified (64 vs ~46 backticked)
- [x] Out-of-scope items listed (§6)
- [x] PF-R1..PF-R9 + PF-r1..PF-r13 recommendations provided
- [x] Q-PR1 5 paths 0-diff at audit HEAD verified

Status: skeleton → complete ✓ — all rows filled.
