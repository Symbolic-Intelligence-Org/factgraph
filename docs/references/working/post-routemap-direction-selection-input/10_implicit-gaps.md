# 10 — Implicit Strategic Gaps (Not Yet Declared)

> See [README.md](README.md) for context.

These are items that **shape current product behavior** but are **not** in any deferred-with-trigger catalog. They surfaced during the 2026-05-07 source-trace review. None are surprises — but their cumulative effect is that v0.1's actual user-facing posture is more developer-narrow than the original product vision intended, and that drift is not formally recorded in any blueprint.

---

## Gap 1 — "We serve developers, not domain experts, until further notice"

**Source:** [30_drift-analysis-2026-05-02.md:280-287](../rule-replay-line-redesign-input/30_drift-analysis-2026-05-02.md)

> "the original vision had the agent as the **primary** user surface for non-technical experts. Without it, the kernel-only surface only serves Python-fluent rule authors...The drift is principled (focus before scaling) but the implication — **'we serve developers, not domain experts, until further notice'** — has not been declared anywhere."

**What this means in practice:**

- Original vision (per [00_brainstorm-original.md:49-50](../rule-replay-line-redesign-input/00_brainstorm-original.md)): dialog agent as primary user surface; "interactive UI 只是作为设计参考, 为将来有 UI 的情况提前准备, 不是我们要实现的目标" — but the dialog agent itself **was** the target for non-technical compliance officers.
- Current state: dialog agent is `draft` blueprint, not implemented; v0.1 ships only Python SDK + advanced importable surfaces. Service/agent layers are excluded from OSS projection.
- The pivot from "primary surface = dialog agent" to "primary surface = Python SDK" is **implicit**, never written down as an explicit narrowing.

**Why it matters for direction selection:**

- Any "product-friendliness" investment in v0.1 must accept this constraint: the audience is Python-fluent developers/integrators. Any wrapper that targets "non-technical user" personas requires reactivating the dialog agent track (Direction D in [20_candidates.md](20_candidates.md)).
- Conversely, accepting "v0.1 = developer-first" lets us optimize SDK / application layer for Python ergonomics without pretending it serves domain experts.

**What "declaring" would look like:**

- A short addendum to [README.md](../../../../README.md) and [SDK alignment matrix](../../../../src/kernel/sdk/docs/01_alignment_matrix.en.md) explicitly stating the v0.1 audience and the deferral of the dialog agent layer.
- Possibly a `2026-05-07_v0.1-audience-narrowing.md` blueprint that records this as an explicit decision (with reactivation trigger = dialog agent revival).

---

## Gap 2 — Walkable evidence wrapper (concept-design deferred, no trigger tracked)

**Source (REVISED 2026-05-07 after verification):** [80_conceptual-interaction-design/check-operation-conceptual-interaction.md §6 *draft discussion*](../rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md). Note: §6 of that file is explicitly marked draft per the document's own §1.0 ordering rule ("若 §6 早期 iteration 与 §1-§5 冲突,以 §1-§5 为准"). The walker direction is **design exploration** in that draft, not a settled principle. Closing this gap means *lifting the §6 draft exploration into actual scoping*, not implementing an already-locked principle.

> "用户读 evidence 是高频操作(check/evaluate 之后)...application 层加一个 walkable wrapper 是合理 ergonomics 投资,与'用户能 for 遍历'心智完全匹配" — §6 draft

**What's actually missing — REFINED scope (verification 2026-05-07 found most DTOs already structured):**

Most application/audit DTOs are already frozen dataclass tuples and iterate fine today. The real raw-tuple-unpacking gaps are limited:

| Object | Current state | Walker need |
|---|---|---|
| `RuleSpec.where` ([src/kernel/core/rules/rule_ir.py:32](../../../../src/kernel/core/rules/rule_ir.py)) | raw `list[Any]` IR tuple | **YES** — IR walker (kind/pred/args/branch/index views) |
| `CompiledDerivationPlan.body_ir` ([src/kernel/application/protocol/derivation.py:37](../../../../src/kernel/application/protocol/derivation.py)) | raw `list[Any]` IR tuple | **YES** — same IR walker as Rule.where |
| `WhyNotUniverseResult.green` ([src/kernel/application/protocol/derivation_why_not.py:298](../../../../src/kernel/application/protocol/derivation_why_not.py)) | raw `tuple[BindingItems, ...]` | YES — minor (BindingView wrap) |
| `Store.active_facts` ([src/kernel/core/store/runtime.py:67](../../../../src/kernel/core/store/runtime.py)) | raw generator of `Ledger.Claim` | **YES, but live** — needs `EntityWalker(store).snapshot()` per principle #10 |
| `DiagnoseAtomLocator.attempted_binding` ([src/kernel/application/protocol/derivation_diagnose.py:81](../../../../src/kernel/application/protocol/derivation_diagnose.py)) | raw tuple | YES — minor (BindingView wrap) |
| `SupportArtifact.pred_witnesses` / `non_fact_steps` / `rule_ref_edges` | already frozen dataclass tuples | **NO walker class needed**, but **YES** cross-reference helper (`asrt_id → AssertionView` lazy lookup, atom-key parsing helper) |
| `ProofFrameRecheckResult.atom_verdicts` | already frozen dataclass tuple | NO walker class needed |
| `ProofFrameDiff.frame_deltas` / `atom_deltas` | already frozen dataclass tuples | NO walker class needed |
| `RoundEvent` (audit) | already frozen dataclass | NO walker, but YES filter/find protocol (audit B3 sub-batch — optional) |
| `WhyNotUniverseResult.red` | already frozen dataclass tuple | NO walker class needed |

**Verification finding (Agent 2 2026-05-07):** What looked like "10+ objects need walker" is actually **2-3 objects need full walker classes** + **shared filter/find/first protocol over already-frozen dataclasses** + **cross-reference helpers** for SupportArtifact's atom-key format conventions and `asrt_id → fact tuple` lookup.

**Prior art aligned with:** [src/kernel/sdk/facade.py:102-217](../../../../src/kernel/sdk/facade.py) `EntitySnapshot` / `AssertionNamespace` / `FieldAssertions` already implements namespace-walker pattern in SDK layer (`snap.assertions.field.active` / `.history` / `.at(t)` / `.version(v)`). The new walker mechanism aligns naming/conventions with this prior art rather than reinventing.

**Reconciliation with Evidence Graph (verified 2026-05-07):** [2026-03-28_evidence-graph-unified-explain.md](../../../blueprints/active/2026-03-28_evidence-graph-unified-explain.md)'s `EvidenceGraph` is a **rendering / serialization DTO** (one-shot snapshot for HTML render etc.), NOT a traversal abstraction. Walker mechanism operates **before** Graph construction. **No overlap, no conflict, complement.**

**Why it matters for direction selection:**

- This is design exploration the concept design draft **identified as worthwhile**, but it was never scheduled out of draft.
- It is **not** in [Batch 8 §5.5.5 reactivation triggers](../../../blueprints/archive/2026-05-06_public-surface.md), **not** in [Round Story Plan §3 deferred items](../../../blueprints/active/2026-05-05_round-story-completion-plan.md). It exists only as a draft-section design exploration.
- Without it, all advanced-importable consumers (audit tools, automation scripts, demo notebooks) reinvent the same IR-tuple unpacking and atom-key format parsing ad-hoc.
- See [40_walker-mechanism-design-sketch.md](40_walker-mechanism-design-sketch.md) for the refined sub-batch design (B1 IR walker + B2 cross-reference helpers, both mandatory; B3 audit walker, optional based on consumer signal).

---

## Gap 3 — Application-layer ergonomic helpers cover only Q3/Q4/Q5

**Source:** [Batch 2 Capability Ergonomics blueprint](../../../blueprints/archive/2026-05-05_capability-ergonomics.md)

Batch 2 shipped exactly three helpers in `kernel.application.capability_helpers`:

- `build_fact_value_override(...)` — Q3
- `build_why_not_candidate_universe(...)` — Q4
- `build_frontier_view_facts(...)` — Q5

**What's missing:**

| Capability | Has helper? | Missing helper shape (proposal) |
|---|---|---|
| Q1 Check | ❌ | `build_check_request(rule_or_derivation, binding_dict, *, store, engine='native')` |
| Q2 Diagnose | ❌ | `build_diagnose_request(rule_or_derivation, binding_dict, *, store, engine='native')` |
| Q3 Fact Overlay | ✅ | (Batch 2) |
| Q4 Why-not Universe | ✅ | (Batch 2) |
| Q5 Frontier Trace | ✅ | (Batch 2) |
| Batch 4 ProofFrame Recheck | ❌ | `build_proof_frame_recheck_request(check_result, *, overlay_actions=()) ` |
| Batch 5a Rule Disable | ❌ | `build_rule_disable_request(rule, branch, atom_index, support, store)` |
| Batch 5b Rule Literal Replace | ❌ | `build_rule_literal_replace_request(rule, branch, atom_index, old, new, support, store)` |
| Batch 5c Rule Add Condition | ❌ | `build_rule_add_condition_request(rule, branch, added_atom, support, store)` |
| Batch 6 Round Recorder | ❌ | `build_round_event_payload(kind, capability_request, capability_result)` (replaces manual `project_*_event_payload(...)` calls) |
| Batch 7 ProofFrame Diff | ❌ | `build_proof_frame_diff_request(...)` (less critical — diff is already a method on AuditQuery) |

**Why this gap exists:**

Batch 2 was scoped to "the three surfaces with the most setup ceremony." Q1/Q2 were considered low-ceremony at the time, and Batch 4-7 hadn't shipped yet. The Batch 2 pattern was never extended to cover the rest of the capability set.

**Why it matters for direction selection:**

- This gap is **not in any deferred catalog** — neither Batch 8 nor the master plan tracks it.
- Without it, every demo / automation tool / audit caller reinvents `CheckRequest(plan=CompiledDerivationPlan(...))` ceremony from scratch.
- This is **the lowest-risk, highest-leverage** filler: pure additions to `kernel.application`, no SDK shell, no public-API commitment, no service/agent dependency.

---

## Gap 4 — Demo framing pending (this session's leftover)

**State:**

- 4 chaptered notebooks (`examples/0[1-4]_*.ipynb`) shipped earlier in this session, in inline-API style modeled on `archive/11_capabilities_e2e_demo.ipynb`.
- Mid-discussion the framing was reconsidered: notebooks 01+02 should arguably be SDK-high-level (mirror archive/01-02 + user_guide §1-§7), and 03+04 should be application/audit-advanced (per the public boundary tiers from Batch 8 §5.5.1).
- Decision was paused pending the broader direction-selection question this bundle records.

**Why it matters for direction selection:**

- Demo direction is downstream of layer choice. If we ship Gap 3's missing helpers (Direction A in [20_candidates.md](20_candidates.md)), the "advanced" notebooks will naturally become less advanced and the framing problem partly dissolves.
- If we instead ship a narrow SDK shell (Direction C), notebook 01+02 expand to cover the new SDK surface and 03+04 may consolidate or be archived.
- Either way, demo work is not the right starting point — it's the right finishing point.

---

## Summary

| Gap | Severity | Tracked anywhere? | Resolves with which candidate direction? |
|---|---|---|---|
| 1. Audience narrowing undeclared | strategic, non-technical | No | Either an explicit declaration blueprint, or Direction D (dialog agent revival) |
| 2. Walkable evidence wrapper deferred | medium ergonomic, recurring | No | Direction B |
| 3. Ergonomic helpers cover only Q3/Q4/Q5 | medium ergonomic, broad | No | Direction A |
| 4. Demo framing pending | low | session-local | Downstream of A/B/C/D — defer |

Gaps 2 and 3 are the most actionable: in-layer additions to `kernel.application`, no public-API risk, no architectural debate required. Gap 1 is most strategically loaded — it should be declared one way or the other before any v0.2 scoping.
