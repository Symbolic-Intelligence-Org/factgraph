# Task Blueprint: Faithful, full-coverage explanation of a non-holding composite (closed_head_false)

- Status: implemented (Slices 1–5 gated 2026-06-22; problog+native end-to-end faithful; 606-test regression green; uncommitted — archive after commit)
- Created: 2026-06-22
- Last Updated: 2026-06-22
- Related Modules:
  - `src/factgraph/sdk/store.py` (closed_head_false routing → per-engine reach_explain on a pin seed)
  - `src/factgraph/adapters/souffle/reach_explain.py` (transitive seed via `_seed_values_for_row`; **bool/literal-encoding fix**)
  - `src/factgraph/adapters/problog/reach_explain.py` (transitive seed via `_seed_values_for_row`; metadata label)
  - `src/factgraph/application/explain/prober.py` (fold failing join/head-link verdicts into tree status — native path + the same-project class)
  - `src/factgraph/application/protocol/rule_expr_inspect.py` (NEW pin extractor → head-port seed) + a shared transitive-seed builder over plan eq-atoms
  - `src/factgraph/application/protocol/evaluate_result.py` (status↔graph guard)
  - `src/factgraph/application/protocol/rule_expr_lowering.py` — **NO change** (transitive seed reads its existing eq-atoms; no reorder)
- Related Docs:
  - [docs/quickstart/evaluate_and_evidence.md](../../../docs/quickstart/evaluate_and_evidence.md) (§3.3 / §4.3 / §4.4)
  - [src/factgraph/application/protocol/docs/README.md](../../../src/factgraph/application/protocol/docs/README.md)
  - roadmap: `workflow/design/design-points/active/explanation-completion-roadmap.zh.md` §6.2 (D1 diagnose, D5 why-not)
- Audit Log:
  - [2026-06-22_explain-composite-closed-head-false.audit.md](./2026-06-22_explain-composite-closed-head-false.audit.md)

## 1. Problem

`fg.eval.explain(expr, head=closed_head)` on a **non-holding COMPOSITE** conclusion (e.g. `teammates(Alice,Carol)`, expr = `colleagues & works_a & works_b`) returns `status="failed", failure_class="closed_head_false"` whose EvidenceGraph shows **only the head's own pin atoms** (`User Alice exists` … all Holds), **not the expr body**. The user cannot see WHY it failed — which atom/occurrence/join did not hold. Confirmed root cause (15-agent investigation + adversarial review, see audit):

1. **store.py:2632** — the failure branch lowers `head.as_("head")` (the head ALONE → `_head_binding` classifies `kind="inline"` → single-occurrence plan of only the head's pins). The expr body occurrences are never in the probed plan. Compounded: `_probe_evidence_graph_for_lowering_plan` is called without `rules_by_id` (2633), defaulting to `{plan.head.id: plan.head}` (3133).
2. **prober.py latent gaps** — even if the expr plan is fed in: head-link CmpAtoms (`trace.head_port_link_materializations`) are emitted nowhere (excluded from body_rules 279, head_atoms 312, never in `_joins_for_trace` 439); and per-tree status `_tree_status((head_rule,*body_rules))` (165) ignores `joins` (154) and head-links. So a composite whose body atoms all Hold but whose **join/head-link fails** aggregates to `holds` while the envelope hardcodes `status="failed"` (2645) → a self-contradictory tree, strictly worse than today.

Why it exists: the holding path never re-lowers — it replays a per-row `_row_graph_builder` captured at evaluate time (store.py:2811-2812), keyed by `row.row_id`; on failure there is no matching row, so the author probed the closed head alone (self-contained, trivially Holds, passes the one weak test `test_rule_expr_evaluate.py:343` where head body == expr body).

## 2. Goals

- **G1 (PRIMARY — 全量 / full coverage):** for a non-holding composite, **every** body atom, join, and head-link gets exactly one of `Holds` / `Fails` / `NotReached`. No atom is omitted; the user knows each atom's state in this inference.
- **G2 (per-engine faithful — 尽可能用引擎原生信息, avoid bias):** the failure evidence must not misrepresent any engine. Honest labeling + native-input enrichment (see §5 Layer 2). No fabricated derived verdict.
- **G3 (reliable, no regression):** holding path + cross-engine conformance unchanged; landed slice-by-slice with adversarial tests; status↔graph never self-contradictory.

## 3. Non-goals

- **Probabilistic / derived why-not for problog** (deferred D5): we do NOT synthesize a derived WMC verdict for a conclusion the engine never derived. A non-derivation has no native derived trace.
- **OR-branch ranking / minimal-blame attribution** (deferred): Phase 2 shows all DNF branches faithfully, no ranking (verbosity accepted; `_DNF_BRANCH_LIMIT=32`).
- **pyreason support** for these ref-based entity-DSL rules (it cannot run them; documented pins-only fallback).
- **Reusing `diagnose_runtime` / `why_not_runtime`** — rejected: flat single-rule, stops at first failing atom, RAISES `DiagnoseRuntimeError` on ruleref atoms (exactly what composite occurrences lower to) → would regress a weak-but-passing path into a hard error.

## 4. Current Context

- Entry: `SDKStore._explain` (store.py:2603-2665); failure branch 2631-2643; replay-head logic `_manual_explain_replay_head` 2688-2694 (returns SOURCE, not closed head, when source is an ApplicationRule with a different id/digest).
- Holding path: per-row `_row_graph_builder` captured at 2811-2812, replayed via `first.explain()` (2654); plan/rules carried as evaluate params (2823-2824).
- Prober: `application/explain/prober.py` — `_probe_branch` 154-173, `_tree_status` 973-981, `_joins_for_trace` 433-452; head-links dropped at 279/312; always `probe_native` + `BOOLEAN_CERTAINTY` (83).
- Lowering: `rule_expr_lowering.py` — external-head fold-in 917-919, head_port_link materialization 951-977, `_head_binding` external classification 1034-1038 (these already produce the right plan; no change expected).
- Engines: native (boolean); problog/souffle holding paths carry probabilistic/WMC certainty (store.py:3004-3019); souffle arity cap `SOUFFLE_MAX_SUPPORTED_ARITY=22` (`adapters/souffle/where_compile.py`); pyreason cannot run these rules.

## 5. Proposed Shape

Two layers that together satisfy G1 + G2.

**CORRECTED 2026-06-22 (feasibility workflow wi81dp6la + user proposal).** The draft's "a non-holding conclusion has no native derived trace" was **FALSE for souffle/problog** (TRUE only for pyreason). `reach_explain` re-runs a **guarded forward chain seeded only by a `{head_port: value}` map** — it consumes NO holding row/derivation — and its parse loop verdicts every atom even when nothing holds (`< failed_at` → Holds; `== failed_at` → Fails + culprit witness; `> failed_at` → NotReached). So each engine HAS a native, per-step **structural-reachability** trace for a fully non-holding pinned conclusion.

**Design: HYBRID, per-engine**, mirroring the holding path's `_row_graph_builder_for_engine` dispatch (store.py:2908-2935) but **keyed on a synthesized pin seed** instead of a holding row:
- **souffle → `souffle_reach_explain_to_evidence_graph` (Proposal B).** Fail-guard structural + free: `generate_view_dl` `.decl`s every predicate (referenced-but-zero-fact → declared-empty → failure branch). Arity cap raises only when `failed_at is None AND truncated_at is not None` (benign for early-failing subjects) → try/except → pin-seeded native prober.
- **problog → `problog_reach_explain_to_evidence_graph` (Proposal B).** One guard `edb_fact(_,_,_,_):-fail.` (all preds funnel through `edb_fact/4`); prob-0 filtered as non-match → same Fails/NotReached path. Per-node WMC on the holding **PREFIX only** (no derived WMC for the non-derived conclusion) → metadata-labeled.
- **native → corrected Design A.** No reach adapter; feed `probe_native` the FULL BODY plan + the pin seed (fixes today's head-alone + `initial_bindings={}` at store.py:3126).
- **pyreason → corrected Design A (pin-seeded prober) or minimal.** event_log replay needs a holding row → the ONE engine where "no native trace" genuinely holds.
- **Fallback** (souffle arity raise / problog unsupported atom) → the **pin-seeded native prober** (Design A), NEVER `_build_minimal_row_evidence_graph` (minimal loses coverage).

**Why B where it fits (not pure-A):** (1) maximally engine-faithful — each engine's own runtime output; (2) joins & head-links materialize as eq atoms IN the chain (souffle 240 / problog 279) → a join/head-link failure halts the chain as a `fails` atom that feeds body status, **sidestepping the native prober's two gaps** (head-links dropped; `_tree_status` ignores the joins list, prober.py:973-981) for these engines; (3) reuses already-shipped/tested reach machinery — the work is **routing + a pin-seed extractor**, not new trace logic. Pure-A for souffle/problog is REJECTED: it re-derives in Python and the problog audit found it unfaithful on full-SAR composites (reopens why the shared companion was retired).

**Faithfulness contract:** the failure graph is a STRUCTURAL reachability trace, stamped `probe_kind="structural_reachability"` + `engine_requested` + certainty-source, so problog's prefix-WMC is never misread as the conclusion's derived verdict. Satisfies "用引擎原生信息 + 避免偏差".

### Slice V VERIFIED (2026-06-22 PoC, both engines, pasted output) — design refined

A head-port-only seed is **unfaithful** for composites: the lowering appends join/head-link eq-atoms LAST (rule_expr_lowering.py:912-979), so occurrence-local vars (`$wa__xa`/`$wb__xb`) run FREE in the linear reach chain → false culprits (souffle blamed `project:active`; problog bound `wb` to Alice's assignment, masking Carol). **The fix is a JOIN-GRAPH-TRANSITIVE seed (seed-side, NO lowering reorder):** from each pinned head port, propagate over the plan's eq-atoms to a fixpoint and seed EVERY var equal to it (`$wb__xb=Carol`, `$wa__xa=Alice`); purely-existential vars stay free. **PROVEN:** problog faithful with the transitive seed ALONE (`tree=fails`; `wb` scoped to Carol; `✗ assignment:user(AP1, Carol)`; downstream NotReached); souffle faithful with the transitive seed **+ the bool fix below**. Builds as a shared seed-builder feeding `_seed_values_for_row` in both adapters; `probe_seed_vars_by_head_port` gives the base roots.

Two orthogonal local fixes the PoC surfaced (NOT seed-side, NOT lowering):
- **souffle bool/literal encoding** (`souffle/reach_explain.py` `_term_for_relation`/`_term_for_compare`, ~590): `str(True)`=="True" ≠ EDB canonical "true" (`where_compile._literal_to_text`) → a referenced bool atom matches 0 rows → false culprit. Pre-existing; affects ALL souffle reach explains with bool/typed literals (good to fix regardless).
- **prober join/head-link status** (`prober.py` `_body_rules_for_branch` 274-280 / `_head_atom_indexes_for_branch` 308-317 / `_tree_status` 960-981): a failure living ONLY in a cross-occurrence join (e.g. same-project `$wa__pa=$wb__pb`, neither side pinned) is detected by the reach chain (atom fails, branch empty) but **dropped from tree status** → wrongly reads `holds`. Fold failing join/head-link verdicts into branch status. (= the same Part B the first workflow flagged; now confirmed required for the same-project class on every engine.)

**No lowering reorder.** The transitive seed reads the eq-atoms the lowering already emits. UNVERIFIED: OR-composites / multi-branch (PoC was single-branch `c0`) — must be tested before shipping.

## 6. Boundaries And Invariants

- **Holding path unchanged**: prober fold must **downgrade only, never upgrade**; existing native conformance + prober tests stay green (`test_explain_conformance_native.py:314/344/364`, `test_prober.py:216-331`).
- **Cross-engine conformance unchanged** for holding rows.
- **DTO shape stable**: Explanation / EvidenceGraph surface unchanged; `evidence.paths` becomes richer (additive only).
- **status↔aggregation contract**: `status="failed"` ⇒ graph aggregates to non-holds (guard, §4.4).
- **Faithfulness boundary**: never fabricate a derived verdict for a non-derivation; problog failure trees are labeled structural, not WMC.
- **No `git push` / no master / no factgraph push** without separate explicit authorization.

## 7. Acceptance

- [ ] G1: a non-holding composite (`teammates(Alice,Carol)`, `works_b(Carol)` missing assignment) yields a tree where `colleagues` Holds, `works_a(Alice)` Holds, `works_b(Carol)` Fails/NotReached — **every** atom/join/head-link verdicted.
- [ ] Adversarial: wrong-entity head-link, join-mismatch (both bound), zero-fact NotReached → tree status is non-holds in each.
- [ ] G3: holding path + native/problog/souffle conformance tests unchanged.
- [ ] G2: failure graph labeled `structural_reachability` + `engine_requested`; problog Holds atoms carry native fact-certainties (or, if enrichment is deferred after the feasibility slice, documented as such).
- [ ] status↔graph guard active; no self-contradictory artifact ships.
- [ ] Affected module docs synced; `docs/README.md` updated if a new durable entry is added.

## 8. Implementation Plan

**Slice V is DONE (green — see §5).** Remaining slices; each: implement → targeted + regression tests (holding path + native/problog/souffle conformance green) → Claude gate → user "可以推进".

1. **Slice 1 — transitive-seed builder + pin extractor.** New pin extractor in `rule_expr_inspect.py` (`{head_port: idref|scalar}` from `closed_head.when`; entity-ref → idref token, bool/scalar → public scalar) + a shared transitive expander over the plan's eq-atoms (fixpoint from the `probe_seed_vars_by_head_port` roots). Wire into `_seed_values_for_row` in BOTH `souffle/reach_explain.py` and `problog/reach_explain.py`. Test: reproduce the (Alice,Carol) PoC as a unit test (problog faithful seed-alone; per-atom Fails on `assignment:user(_, Carol)`).
2. **Slice 2 — souffle bool/literal encoding fix** (`souffle/reach_explain.py` `_term_for_relation`/`_term_for_compare`, ~590): route reach-atom literals through canonical `_literal_to_text` (bool→"true"/"false"). Test: souffle (Alice,Carol) faithful (`project:active` Holds, `wb` Fails); existing souffle reach + holding tests green.
3. **Slice 3 — prober join/head-link status fold** (`prober.py` `_body_rules_for_branch` 274-280 / `_head_atom_indexes_for_branch` 308-317 / `_tree_status` 960-981): include failing join + head-link verdicts in branch/tree status (downgrade-only). Test: same-project (Alice@P1, Carol@P2) composite → tree=`fails` with the join atom failing; **holding native/conformance tests unchanged**.
4. **Slice 4 — store.py closed_head_false routing** (2631-2643): build the pin seed (not row=None); lower the FULL expr (args[0], head=closed_head) for the body plan (not `head.as_("head")`); non-row per-engine dispatch shim mirroring `_row_graph_builder_for_engine` (souffle/problog → reach_explain w/ transitive seed; native/pyreason → pin-seeded prober); try/except → pin-seeded prober fallback (NOT minimal); pass `rules_by_id`; let `_probe_evidence_graph_for_lowering_plan` accept a pin seed when row=None (today `initial_bindings={}` at 3126). + structural metadata stamp + `Explanation.__post_init__` status↔graph guard.
5. **Slice 5 — docs + conformance/adversarial tests:** README + evaluate_and_evidence.md §3.3/4.3/4.4; cross-engine parity (arity ≤ 22); `failed_at==0`; **OR-composite / multi-branch (the UNVERIFIED case)**; wide-souffle divergence.
6. **Phase 2 (follow-up blueprint):** broader OR-branch attribution / verbosity policy (D5 stays deferred).

Order rationale: 1+2 make the adapters faithful in isolation (testable via direct reach_explain calls like the PoC); 3 fixes the cross-occurrence-join class; 4 wires it into the SDK closed_head_false path; 5 documents + guards boundaries.

## 9. Docs To Update

- `src/factgraph/application/protocol/docs/README.md` (closed_head_false rows ~161, 184-188)
- `docs/quickstart/evaluate_and_evidence.md` (§3.3 / §4.3 / §4.4)
- `docs/README.md` (only if a new durable entry is added)

## 10. Outcome / Deviations

**Implemented across Slices 1–5 (2026-06-22), each gated (impl → tests → adversarial verify → Claude gate → user GO).** `fg.eval.explain(composite, head=closed_head)` on a non-holding subject now returns `status="failed"` + a full-coverage `EvidenceGraph` verdicting every body atom + join (全量), per-engine-faithfully — problog + native end-to-end.

Delivered:
- **Slice 1** — `transitively_expand_seed` (`rule_expr_lowering`) wired into both reach builders' `_build_reach_program`: scopes occurrence-local vars transitively pinned by the seed over the join/head-link eq-atoms. No lowering reorder.
- **Slice 2** — souffle `_term_for_relation` bool encoding (canonical `"true"/"false"`, matching `_literal_to_text`).
- **Slice 3** — `prober._fold_join_status` folded into BOTH tree-status sites (`_probe_branch` + `diagnostic_assemble`): cross-occurrence join failures reach tree status (same-project class).
- **Slice 4** — store failure-branch routing: `pin_specs_for_closed_head` + `_pin_bindings_for_closed_head` (seed-parity via `_ref`) + full-expr body plan + `_closed_head_false_evidence_graph` per-engine dispatch + pin-seeded native fallback + `probe_native` transitive seed.
- **Slice 5** — `tests/sdk/test_explain_composite_closed_head_false.py` (7 cases incl OR multi-branch) + explain `docs/README.md` §3/§6/§7.

Deviations from the §8 plan:
- The pin-extractor shipped in Slice 4 (not Slice 1) — it is consumed only by the store routing.
- The join-status gap existed at TWO sites (native `_probe_branch` AND the shared reach assembler `diagnostic_assemble`), not one; both folded.
- `probe_native` itself gained the transitive seed (the native analog of Slice 1), making the native fallback faithful.

Known limits (documented, not defects):
- **souffle large composites** (witness arity > 22) raise at the witness-evaluate (`store.py` `_evaluate`), UPSTREAM + pre-existing (constrains holding souffle explain too); large composites use problog/native. User decision (2026-06-22): document, do not fix.
- **head-port links** are not folded into tree status — they hold by construction under the consistent pin seed (latent only if that invariant breaks).
- **native vs reach downstream-of-culprit display** differs (native per-atom truth vs reach derivation-flow `NotReached`); culprit attribution identical on both.
- **bare single-rule heads** route via `head.as_("head")`; full-body lowering applies to `RuleExpr` composites.

Verification: 4 adversarial-refuter passes (2 background workflows) + a 606-test regression sweep. Branch `v0.2.0-fix-explain-composite-closed-head-2026-06-22`, **uncommitted** at sign-off (archive after commit).
