# Audit Log: Faithful, full-coverage explanation of a non-holding composite (closed_head_false)

Paired with [2026-06-22_explain-composite-closed-head-false.md](./2026-06-22_explain-composite-closed-head-false.md).

## 2026-06-22 — Open (draft): root cause + scope + design (Claude, 15-agent workflow + adversarial review)

### 由来
User probing the demo (`examples/rule_composition_demo.ipynb` §7) found `fg.eval.explain(composite, head=closed_head)` on a non-holding pair shows only the head's pins, not the body. Iterative discussion established the head-only failure probe. User set two requirements: **(1) per-engine faithful** (use each engine's native info, avoid deviation/bias); **(2) core = 全量** (every atom's state known, none omitted). User: "如果你能确保修改可靠, 我们可以尝试修复, 但还是起新的分支".

### 调查方法
15-agent workflow (`explain-failed-composite-rootcause`, ~1.31M subagent tokens): 6 parallel readers (sdk-explain / lowering / prober / per-engine / holding-reuse / why-not-diagnose) → root-cause+scope synthesis → 3 candidate designs merged → 3 adversarial skeptics → finalize.

### 根因(实证 file:line)
1. **store.py:2632** failure branch lowers `head.as_("head")` only (`_head_binding` → `kind="inline"`, single-occurrence pin plan); expr body never probed. `_probe_evidence_graph_for_lowering_plan` called without `rules_by_id` (2633 → default 3133).
2. **prober.py** head-links dropped (279/312/`_joins_for_trace` 439) AND `_tree_status` (165, 973-981) ignores joins+head-links → a join/head-link failure can aggregate to `holds` under hardcoded `status="failed"` (2645). **Self-contradictory.** Refutes the initial "ZERO prober changes" framing.
- Why: holding path replays a per-row builder (2811-2812) keyed by row.row_id; failure has no row → author probed the closed head alone. Masked by the one weak test (`test_rule_expr_evaluate.py:343`, head body == expr body).

### 对抗验证(2/3 lenses returned holds_up=false, all confirmed in code)
- **HEAD-LINK INVISIBILITY (critical):** failing head-link emitted nowhere → promoted prober changes from "deferred/test-only" to **required Phase 1**.
- **JOIN-STATUS-NOT-IN-TREE-STATUS (critical):** `_probe_branch:165` folds rule.status only → added join/head-link fold + status↔graph guard.
- **APPLICATIONRULE REPLAY-HEAD DIVERGENCE (medium):** `_manual_explain_replay_head` (2690-2693) lowers against SOURCE head, not closed head → only read back the stash when replay-head==closed-head, else re-lower against the ORIGINAL closed_head.
- **PER-ENGINE honesty (medium):** failure probe is always native/boolean while problog/souffle holding carry prob/WMC → label `probe_kind="structural_reachability"`; wide-souffle is a documented divergence, not parity.

### 设计选型(user 两诉求的调和)
- **G1 全量** = Layer-1 structural backbone (engine-agnostic; objective structural states verdict every atom/join/head-link). This is the must-have.
- **G2 per-engine faithful** = honest labeling + native-INPUT enrichment. **Hard truth (adopted):** a non-derivation has no native *derived* trace (closed-world: no proof for a non-fact); faithfulness therefore = objective structural states + native input certainties (problog fact-probabilities on Holds atoms) + honest labels — **not** a fabricated derived verdict. This both satisfies "用引擎原生信息尽可能" and avoids "偏差" (the structural states are engine-independent, so showing them is not a deviation; labeling prevents misreading as WMC).
- **Rejected:** reuse `diagnose_runtime`/`why_not_runtime` (raises on ruleref = composite occurrences). Confirmed in code.

### Scope (not yet frozen — pending Slice V)
store.py (`_explain` failure branch + `_candidate_sets_to_evaluate_result`), prober.py (`_probe_branch` fold + head-link emission), evaluate_result.py (2 private fields + guard), docs (README + evaluate_and_evidence.md), tests (extend 343 + 4 adversarial + cross-engine parity + wide-souffle divergence). Phase 2 = OR-branch faithful display (no ranking, D5 deferred).

### Cadence
draft → **Slice V verify (GATE: full-coverage backbone feasibility + problog certainty-enrichment feasibility) + user sign-off** → scoped → per-slice impl (Part A → B → C → docs) with Claude gate + user "可以推进" between slices. No src edits before Slice V + sign-off. No push/master/factgraph without separate authorization.

### 待确认(before scoped)
1. User confirms the **"faithful" interpretation** (structural backbone + native-input certainties + honest labels; no fabricated derived why-not for non-derivations).
2. Slice V: does pin fold-in fully substitute for row-seeding on a real multi-occurrence composite (order-sensitivity)? Is problog Holds-atom certainty enrichment cleanly feasible or deferred?

## 2026-06-22 (later) — Feasibility workflow (wi81dp6la, 9 agents): **design shift A → hybrid-B; prior claim corrected**

### 触发
User proposed: instead of a native structural probe, reuse the **engine-own reach-chain explain + fail-guard** (from the 2026-06-21 reach-chain fix) on the pinned non-holding conclusion — "构造保护性 proof 代码,定位非事实 atom,前面 Holds、该 atom Fails、后面 NotReached". Ran a focused feasibility workflow.

### 修正(claim was wrong)
The draft §5 "a non-holding conclusion has no native derived trace" is **FALSE for souffle/problog**, TRUE only for pyreason. Verified in code: `reach_explain` re-runs a guarded forward chain seeded **only by a `{port: value}` map** — NO row_id / derivation / receipt (souffle reach_explain.py:485-491/122-124; problog 525-531/145-147); `previous_rows` bootstrapped to `[_seed_row(seed)]` (souffle 331 / problog 349); parse loop emits Holds-prefix / Fails-at-`failed_at` / NotReached-downstream over ALL branch atoms (souffle 373-402 / problog 391-423). A fully non-holding subject just takes the `failed_at!=None` (possibly `==0`) path. pyreason is the genuine exception (event_log replay needs a holding row, store.py:3089-3114).

### 结论:HYBRID(per-engine),feasibility = CONDITIONAL YES
- souffle → `souffle_reach_explain_to_evidence_graph` (B); fail-guard structural+free (`generate_view_dl` `.decl`s all, souffle_view_gen.py:39/68); arity raise only `failed_at is None AND truncated_at is not None` (350-355) → try/except → seeded prober.
- problog → `problog_reach_explain_to_evidence_graph` (B); one guard `edb_fact(_,_,_,_):-fail.` (189); prob-0 filtered as non-match (354-358); prefix-WMC only, metadata-labeled.
- native → corrected Design A (no reach adapter; feed `probe_native` the BODY plan + pin seed; fixes head-alone + `initial_bindings={}` at store.py:3126).
- pyreason → corrected-A / minimal.
- Fallback → **pin-seeded native prober, NEVER minimal** (minimal loses coverage).
- **Bonus:** B's joins/head-links are eq atoms IN the chain (souffle 240 / problog 279) → they get verdicts + feed status, **sidestepping the native prober gaps** (Part B fix from the first workflow now needed only for the native path).
- **Pure-A for souffle/problog REJECTED**: re-derives in Python; problog audit found it unfaithful on full-SAR (reopens the retired-companion reason).

### 三道可靠性门(before src)
1. **Seed-parity (HIGH):** pin-extracted token must be byte-identical under `str()` to souffle view facts / problog `edb_fact` (`_public_value` souffle 504-507) — mismatch → silent all-Fails FALSE culprit. **Parity-test first.**
2. **FULL-expr body plan** must be threaded (head=closed_head), NOT `head.as_("head")` (store.py:2632) — else reproduces the defect.
3. **`failed_at==0` / fully-non-holding corner**: sound by reading, UNTESTED (all PoCs at test_rule_expr_evaluate.py:657/705/741 have a holding top conclusion). Needs a targeted PoC + the witness-loss edge (atom_0 non-seed var → souffle 437-438 / problog 459-460).

### 待确认 / cadence
User signs off **A vs B vs hybrid** (recommend hybrid-B) → run **Slice V PoC + seed-parity** (prototype only, no src) → if green, scoped → per-slice impl. New genuinely-new logic = the pin-extractor (`rule_expr_inspect.py`); the rest is routing. §5/§8 above updated to hybrid-B.

## 2026-06-22 (later) — Slice V PoC: **GREEN** (2 background agents, both engines, pasted output); blueprint draft→scoped

User signed off hybrid-B ("同意, 在新分支上进行"). Ran the Slice V PoC (read-only, /tmp, on the fix branch).

### PoC-1: head-port seed → DISPROVEN (unfaithful for composites)
Invoking `souffle/problog_reach_explain_to_evidence_graph` with a head-port-only seed for non-holding `teammates(Alice,Carol)` returns a graph but **wrong per-atom verdicts**: the lowering appends join/head-link eq-atoms LAST (rule_expr_lowering.py:912-979), so `$wa__xa`/`$wb__xb` run FREE in the linear reach chain → souffle blamed `project:active` (false culprit), problog bound `wb` to Alice's assignment and reported `tree=holds` (masked Carol). `probe_seed_vars_by_head_port` seeds only head+col vars. Seed-parity confirmed: token MUST be the idref (`fg.entities.ref`), raw user_id → all-Fails false culprit at atom 0. `failed_at==0` corner clean (witness preserved).

### PoC-2: JOIN-GRAPH-TRANSITIVE seed → **GREEN, no lowering reorder**
Propagating each pinned head port over the plan's eq-atoms to a fixpoint and seeding EVERY equal var (`$wb__xb=Carol`, `$wa__xa=Alice`; existential vars free) makes it faithful. **PROVEN (pasted):** problog faithful with the transitive seed ALONE (`tree=fails`; `wb` scoped to Carol; `✗ assignment:user(AP1, Carol)`; downstream NotReached). souffle faithful with the transitive seed **+ a bool-encoding fix**. Injection point = `_seed_values_for_row` in both adapters (the reach builder consumes occurrence-local seed vars correctly — a pre-seeded var becomes a seed column carried through every reach relation). Purely seed-side; **lowering untouched** (the transitive seed reads the eq-atoms it already emits).

### Two orthogonal local fixes the PoC surfaced (NOT seed, NOT lowering)
1. **souffle bool/literal encoding** (`souffle/reach_explain.py` `_term_for_relation`/`_term_for_compare` ~590): `str(True)`="True" ≠ EDB "true" → bool reach atom matches 0 rows → false culprit. Pre-existing; affects all souffle reach explains with bool/typed literals.
2. **prober join/head-link status** (`prober.py` 274-280 / 308-317 / 960-981): a failure living ONLY in a cross-occurrence join (same-project `$wa__pa=$wb__pb`, neither side pinned) is detected by the reach chain (atom fails, branch empty) but DROPPED from tree status → wrongly `holds`. Fold failing join/head-link verdicts into status. (= the Part B the first workflow flagged.)

### Verdict + scope (now scoped, see §5/§8)
Fix is **RELIABLE** (user's condition met) and **bounded**: transitive-seed builder (Slice 1) + souffle bool fix (Slice 2) + prober join-status fold (Slice 3) + store routing/pin-extractor/metadata/guard/fallback (Slice 4) + docs/tests (Slice 5). **No lowering reorder.** Satisfies 全量 (every atom verdicted — proven in-occurrence; Slice 3 covers cross-occurrence-join) + per-engine faithful. UNVERIFIED: OR-composites / multi-branch (PoC was single-branch c0) → tested in Slice 5. PoC scripts: /tmp/slice_v_*.py.

### Cadence
**Pending user GO for the FIRST src edit (Slice 1).** Then per-slice: impl → tests (holding + conformance green) → Claude gate → user "可以推进". No push/master/factgraph without separate authorization.

## 2026-06-22 (impl) — Slices 1+2 landed + gated (Claude; per-slice cadence)

Branch `v0.2.0-fix-explain-composite-closed-head-2026-06-22` (uncommitted). User GO for Slice 1 ("可以推进"), then GO for Slice 2.

### Slice 1 — transitive-seed builder (DONE, gated)
- `rule_expr_lowering.py`: new shared `transitively_expand_seed(valued, branches)` — fixpoint over the materialized body's eq-atoms (join + head-link); a purely-existential join (both endpoints unseeded, e.g. `$wa__pa=$wb__pb`) stays dormant; base seed only extended, never narrowed. Placed right after `probe_seed_vars_by_head_port`. Uses builtin generics only (no new imports; `from __future__ import annotations` in effect).
- `souffle/reach_explain.py` + `problog/reach_explain.py`: `_build_reach_program` calls it immediately after `_seed_values_for_row`, reusing the already-materialized `branches` (no re-materialize, **no lowering change**).
- Verify (REAL code, no monkeypatch): non-holding `teammates(Alice,Carol)` → **problog fully faithful** — `tree=fails`; `col`/`wa` holds; `wb` fails at `✗ assignment:user(AP1,Carol)`; downstream NotReached.
- **Pin-extractor DEFERRED to Slice 4** (it is used only by the store failure-routing + needs the store's idref resolution; this keeps Slice 1 to the verified-critical seed piece). Minor re-grouping vs §8.
- Regression: explain/lowering/rule_expr/prober sweep **224 passed / 2 skipped / 12 subtests**; conformance + rule_expr_evaluate **70 passed / 0 skipped**. Holding + cross-engine parity unaffected (transitive expansion is an identity extension on holding rows; existing fixtures route the non-bool path).

### Slice 2 — souffle bool/literal encoding (DONE, gated)
- `souffle/reach_explain.py` `_term_for_relation`: a bool Const now encodes as the canonical EDB symbol `"true"/"false"` (matching `where_compile._literal_to_text`), not `str(True)="True"`. New `isinstance(term,bool)` branch only; non-bool path byte-identical. (`_term_for_compare` left as-is — its bool→`"1"/"0"` is for numeric compares; the verified bug is a relation lookup → `_term_for_relation`.)
- Verify: souffle `teammates(Alice,Carol)` now **fully faithful** (identical shape to problog) — `project:active(P1,True)` Holds (was the false-culprit Fails); `wb` fails at `assignment:user(AP1,Carol)`.
- Regression: explain/reach/lowering/rule_expr/prober/souffle sweep **292 passed / 2 skipped / 12 subtests**.

### Slice 3 — prober join status fold (DONE + gated)
- Root scope corrected during impl: the SAME gap exists at **two** sites, not one — both compute `_tree_status(rules)` while `_joins_for_trace(...)` is built separately and dropped from status:
  - `prober.py` `_probe_branch:165` (native path);
  - `diagnostic_assemble.py:145` `diagnostic_problog_result_to_evidence_graph` (the SHARED reach assembler — **both** souffle `reach_explain.py:100` and problog `reach_explain.py:117` route here). So the §7c same-project class is a reach-path bug, fixed in the assembler.
- New shared helper `prober._fold_join_status(status, joins)` (after `_tree_status`): downgrade-only — `any join.status=="fails" → fails`; `holds + any not_reached join → not_reached`; else unchanged. On a holding row every join holds → no-op (no regression). Wired into both sites (diagnostic_assemble imports it; joins hoisted to a var, reused for both the fold and `EvidenceTree(joins=...)`).
- Head-links: appended-last eq-atoms seeded consistently by Slice 1 → hold by construction; if materialized into `tree.joins` they are folded too; if not, they cannot fail with the seed. Sound either way (to be confirmed by the coverage lens).
- Verify (REAL code, no monkeypatch): same-project scenario B (Alice@P1, Carol@P2 — both `works_*` hold individually) now **tree=fails on BOTH engines** while head/col/wa/wb all holds (join is the sole culprit) — `/tmp/slice3_verify.py`. (Alice,Carol) in-occurrence failure unchanged (fold no-op; wb fails via body atom) — `/tmp/slice1_verify.py`.
- Regression: explain/reach/lowering/rule_expr/prober/souffle/diagnostic/evidence sweep **412 passed / 2 skipped / 12 subtests**.
- Adversarial verification (workflow `slice3-fold-adversarial-verify`, 3 refuter lenses, 190k subagent tokens): **over-downgrade** not refuted (holding-branch `failed_at is None` forces all join atoms holds → "non-holding join" and "rules all-holds" are mutually exclusive; empirical holding case `/tmp/slice3_holding.py` Alice@P1+Carol@P1 → fold no-op). **semantics** not refuted (fold mirrors the existing Kleene-AND lattice exactly; `not_reached × fails → fails` is the stronger/faithful answer; join verdict grounded in the closed three-way `Verdict` union, no misclassification). **coverage** refuted at **LOW** severity, NO correctness counterexample: the two fold sites are confirmed the only composite tree-status points and souffle+problog both route the shared assembler, BUT head-links live in `trace.head_port_link_materializations` (NOT `join_materializations`), so they are NOT in `tree.joins` and NOT folded — the docstring's "(and head-link)" was inaccurate.
- **Resolution:** docstring corrected (accurately scopes the fold to cross-occurrence joins; documents that head-links hold by construction under the consistent head-port seed — both endpoints seeded equal + materialized last — so cannot be a sole culprit, and flags the latent fragility if that seed invariant is broken by a projection/external head). **Head-link fold + visibility carried to Slice 4** (which introduces the store routing + pin-seeded native fallback + closed/external-head handling — the live home for the seed-invariant question); Slice 5 adds the external-head adversarial test. Re-ran regression after the docstring edit: unchanged (doc-only).
- **Gate: PASS.** Fold is correct + faithful + regression-clean; the one finding is a doc fix (done) + a tracked latent (non-shipping) item.

### Slice 4 — store failure-branch routing (DONE pending adversarial verify)
Six pieces:
1. **`prober.probe_native`**: applies `transitively_expand_seed` to its seed after materializing branches (the native analog of Slice 1's reach change) — without it the pin/row seed reaches only the head-exposing occurrence and the native prober (threads envs, joins last) mis-attributes a non-holding culprit to a head-link. Holding rows: identity extension (regression-clean, 599 passed).
2. **`rule_expr_inspect.pin_specs_for_closed_head`** (+ `_value_port_pin_value` / `_entity_ref_port_pin_values` / `_entity_identity_literal_value`): pure value-returning twin of the `_is_closed` helpers — `{port: ("value", scalar) | ("entity", entity_type, {field: value})}` from the closed head's `when`.
3. **`store._pin_bindings_for_closed_head`**: mints entity pins to idref tokens via `self._ref` (the SAME path the EDB uses → seed-parity); value pins pass through.
4. **`store._initial_probe_bindings_from_port_values`** + **`_probe_evidence_graph_for_lowering_plan(pin_bindings=...)`**: native base seed from the pin map (probe_native expands transitively).
5. **`store._closed_head_false_evidence_graph`**: lowers the FULL expr body (head = closed head) and dispatches the pin seed — souffle/problog via the engine-own reach builders (same as holding, seeded by pins), native/pyreason/reach-fallback via the pin-seeded native prober (never minimal). `probe_kind="structural_reachability"`, `graph_certainty=BOOLEAN_CERTAINTY`.
6. **`store._explain` failure branch rewrite**: `head.as_("head")` (head-only — the defect) → full body plan + `_closed_head_false_evidence_graph`. Bare single-rule input keeps `head.as_("head")` (body == head structurally; also sidesteps the bare-Rule non-identifier auto-alias coercion error). `Explanation.__post_init__` already enforces status=failed ⇒ evidence non-None (status↔graph guard).

**Verify (REAL `fg.eval.explain`, no monkeypatch)** — non-holding composite `teammates(Alice,Carol)`, closed head pinned via identity PredAtoms:
- **problog + native: end-to-end faithful** — `status=failed`, `failure_class=closed_head_false`, `tree c0 status=fails` with the FULL body tree (head/col/wa/wb per-atom verdicts; wa@P1 & wb@P2 each hold; the same-project join `wa.Pa=wb.Pb` is the sole culprit, surfaced via the Slice-3 fold). The head-only defect is gone.
- **souffle: blocked by a PRE-EXISTING limit** — `fg.eval.explain` runs the witness-building souffle evaluate at `store.py:2628` (UPSTREAM of the failure branch I changed), which raises `WhereValidationError: souffle witness relation arity exceeds supported limit (arity=25 > 22)` for this 25-atom composite. Confirmed via the traceback (frame at 2628 → `compile_where_to_per_branch_witness_dl`). This is independent of the closed_head_false fix (the old code's 2628 is identical; it affects HOLDING souffle explain of large composites equally). The souffle reach routing itself is correct (proven by the Slice-V direct calls; `_closed_head_false_evidence_graph` calls the identical builder). **DECISION (user, 2026-06-22): document as a KNOWN LIMIT** — souffle explain (holding OR failing) of a composite whose witness relation exceeds arity 22 raises at the evaluate; large composites use problog/native. Not addressed in Slice 4 (separate souffle-engine concern); Slice 5 docs record it. Graceful-fallback / witness-free-evaluate options were declined as out of scope.
- Regression: bare-Rule `closed_head_false` test (the failure-branch regression) PASSES after the coercion fix; broad sweep **599 passed / 2 skipped / 63 subtests**.
- Adversarial verification (workflow `slice4-routing-adversarial-verify`, 3 lenses, 214k subagent tokens): **seed-parity** not refuted (pin idref byte-identical to the EDB — both `fg.entities.create` and `_pin_bindings_for_closed_head` run the identical `_ref`→`_coerce_sdk_value_to_tag`→`encode_idref_v1`; verified single/multi-field/value-port; type-mismatched Const raises loudly, no silent divergence; no atom-0 all-Fails collapse). **culprit-faithfulness** not refuted, LOW notes (the transitive seed in `probe_native` is *load-bearing* — disabling it reproduces the head-link mis-attribution, confirming the Slice-4 change is required; culprit `atom:17 assignment:user(AP1,Carol) Fails` correct on native+problog). **fallback-guard** not refuted (forced reach-raise → native fallback returns the full body 4 rules/26 atoms, not minimal; `Explanation.__post_init__` enforces status=failed⇒evidence; souffle arity confirmed upstream at 2628/pre-existing).
- **Two LOW / by-design findings (documented, not fixed in Slice 4):**
  1. *Native downstream-of-culprit display*: after the culprit atom Fails, the native prober shows the occurrence's remaining atoms as Holds (it threads the partial assignment binding forward), whereas the reach engines show them NotReached. Culprit attribution is correct on both; this is a per-engine display nuance (native = per-atom truth threaded from terminal envs; reach = derivation-flow). Pre-existing native-prober behavior. → Slice 5 docs note it.
  2. *Bare single-rule value-port closed head*: routes via `head.as_("head")`, so if the head does not itself carry the rule body, the body atoms do not appear. The composite (`_RuleExpr`) case — the actual target — is fully faithful; the standard single-rule head (= rule + identity pins) still carries its body. → Slice 5 docs note the bare-Rule routing.
- **Gate: PASS.** The closed_head_false routing is correct, seed-parity-safe, fallback-robust, and faithful for composites on problog + native; the findings are a documented souffle pre-existing arity limit + two LOW per-engine/by-design display nuances.

### Cumulative state after Slices 1+2
Both engines' `reach_explain` now produce the faithful, full-coverage per-atom tree for a non-holding multi-occurrence composite (in-occurrence failure class). **NOT yet user-facing**: `store.py:2632` failure branch still lowers head-only → `fg.eval.explain(composite, head=closed_head)` on a non-holding pair still shows head-only until Slice 4 wires the reach path in. Remaining: **Slice 3** (prober join/head-link status fold — the same-project *pure-join* failure class, where the failure lives only in an existential join eq-atom and is dropped from tree status; also needed by the native fallback), **Slice 4** (store failure-branch routing: pin-extractor + full-expr body plan + per-engine dispatch + metadata/labels + status↔graph guard + pin-seeded native fallback), **Slice 5** (docs + OR-composite/multi-branch conformance + adversarial tests).

## 2026-06-22 (impl) — Slice 5 landed + blueprint COMPLETE

### Slice 5 — docs + conformance + adversarial (DONE + gated)
- **Durable conformance test** `tests/sdk/test_explain_composite_closed_head_false.py` (7 cases, self-contained — supersedes the `/tmp` PoCs): in-occurrence failure (Carol unassigned → `wb` culprit `assignment:user(…,Carol)`) and same-project join failure (every occurrence holds; a cross-occurrence join fails) on BOTH native + problog; OR-composite multi-branch (2 trees, both `fails`, each branch's `works` occurrence is its culprit) on both; pin seed-parity (`_pin_bindings_for_closed_head` idref == `fg.entities.ref` idref).
- **OR-composite / multi-branch** (the prior UNVERIFIED case): VERIFIED — native + problog produce one tree per branch, every branch `fails`, the graph aggregates to `failed`.
- **Docs**: `application/explain/docs/README.md` §3 (transitive-seed paragraph + updated `probe_native` signature) + new **§6 Closed-Head-False (full-coverage failure explain)** (per-engine routing, `structural_reachability` label, the join fold, OR aggregation, and the four known limits/nuances: souffle arity, native-vs-reach downstream display, head-links, bare-Rule routing) + §7 test entry. No adapter-doc / `docs/README.md` change needed (no adapter doc documents reach internals; not a new durable docs entry).
- **Adversarial tests** = the Slice 3 + Slice 4 refuter workflows (run + gated above).
- Final regression: explain/reach/lowering/rule_expr/prober/souffle/diagnostic/evidence/native/conformance sweep **606 passed / 2 skipped / 63 subtests**.

### Blueprint COMPLETE — closed_head_false defect FIXED end-to-end
The user-facing defect ("explaining a non-holding composite shows only the head") is resolved on problog + native: `fg.eval.explain(composite, head=closed_head)` on a non-holding subject now returns `status=failed` + a full-coverage `EvidenceGraph` that verdicts **every** body atom + join (全量), per-engine-faithfully (structural label, no fabricated WMC; native + reach both surface the genuine culprit). Slices 1–5 each gated (impl → tests → adversarial verify → Claude gate → user GO). souffle large-composite arity is a documented pre-existing limit (user decision: document, not fix). Branch `v0.2.0-fix-explain-composite-closed-head-2026-06-22`, **UNCOMMITTED** — awaiting user commit/merge decision; blueprint → `implemented` (archive after commit).

