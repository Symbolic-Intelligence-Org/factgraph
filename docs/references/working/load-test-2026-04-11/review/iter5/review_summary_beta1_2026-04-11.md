# B3 β.1 Review Summary — 2026-04-11

- Date: 2026-04-11
- Author: agent B3 review pass (β.1 sample expansion)
- Phase: β.1 (sample expansion for F-03 cross-validation, NOT a new iteration)
- Pipeline state: iter 5 `SYSTEM_PROMPT_TEMPLATE` unchanged from archival — no code modifications in β.1
- Related:
  - [β.1 working plan](../../sample_expansion_plan_2026-04-11.md) (living tracker, §4 cross-sample table, §5 decision proposal)
  - [iter 5 review summary](./review_summary_iter5_2026-04-11.md) (original iter 5 findings)
  - [iter 5 blueprint (archived)](../../../../blueprints/archive/2026-04-11_agent-extraction-prompt-semantic-grounding.md)
  - [cross-run observations](../../cross_run_observations.md) (OBS-01 variance, OBS-02 Pattern B crossover)
  - [iter 4 review summary](../review_summary_2026-04-11.md) (iter 4 baseline)
  - β.1 review packets (filled):
    - [short_03_architecture](./review_pass_2026-04-11_short_03_architecture.md)
    - [medium_02_blueprint_backref](./review_pass_2026-04-11_medium_02_blueprint_backref.md)
    - [medium_03_audit_report](./review_pass_2026-04-11_medium_03_audit_report.md)

---

## 0. TL;DR

β.1 expanded the B3 sample set by 3 documents (45 new drafts across 3 human-reviewed packets) to cross-validate the F-03 Module routing regression introduced by iter 5. The expansion used **iter 5 prompt state unchanged** — no code modifications, no new iteration.

**Headline findings**:

1. **F-03 is content-style-dependent**, not content-density-proportional.
   - **PRESENT (strong)** on task blueprints without explicit module enumeration: `long_01_kernel_p0` (70.8%), `medium_02_blueprint_backref` (100% on tiny sample)
   - **ABSENT** on architecture docs with explicit subsystem listings: `short_03_architecture` (0%)
   - **WEAK** on audit/reference content: `medium_03_audit_report` (15.4%)
2. **β.1 combined strict approval rate: 26.7%** (12/45) — above iter 5's 16.2% but **driven mostly by one sample** (`short_03` at 55.6%)
3. **All-5-sample combined strict rate: 16.8%** (22/131) — essentially flat vs iter 5's 16.2%
4. **Salvageable rate: 100%** on all 5 samples. No hallucination regression.
5. **OBS-02 confirmed**: Pattern B overpacking crossed over to `document:mentions` on short_03 canonical. Logged as P3, non-blocking.

**Verdict (proposed)**: β.1 provides sufficient diagnostic signal. The next direction is a judgment call among four options (α prompt fix / β continuation / γ schema expansion / δ leave-alone). My recommendation: **δ (leave iter 5 alone)** with an explicit second-choice fallback of α (narrow-scoped iter 6). Rationale details in §6.

---

## 1. Scope and method

### 1.1 What β.1 is (and isn't)

β.1 is a **sample expansion pass**, not a new iteration. It executes the iter 5 verdict's chosen next direction (Option β) to answer one specific question: does F-03 generalize across content types, or is it specific to `long_01_kernel_p0`?

What changed in β.1:
- Added 3 new samples to the B3 set (short_03, medium_02, medium_03)
- Ran 3 canonical runs with `run_load_test.py` using the iter 5 prompt state
- Generated 3 review packets via `generate_review_packet.py`
- Conducted human review pass on 45 new drafts

What did NOT change in β.1:
- `src/factpy_kernel/agent/extraction/prompts.py` (iter 5 `SYSTEM_PROMPT_TEMPLATE` is the same)
- Any code under `src/factpy_kernel/`
- `test_schema_ir.json` (still the provisional 2-entity-type schema)
- `run_load_test.py`, `generate_review_packet.py`
- Any archived iter 4 or iter 5 artifact
- Reason code taxonomy (still iter 4's 9-code set; no new codes added)

### 1.2 The 3 new samples

| sample_id | size | source | original β.1 role |
|---|---:|---|---|
| `short_03_architecture` | 2.8 KB / 66 lines | `docs/architecture_principles.md` | negative control (**invalidated by run data** — see §3.1) |
| `medium_02_blueprint_backref` | 8.9 KB / 214 lines | `docs/blueprints/archive/2026-03-17_candidate-id-support-backref.md` | positive control |
| `medium_03_audit_report` | 10.6 KB / 266 lines | `docs/references/working/product-readiness-audit-2026-04-09.md` | gradient test |

### 1.3 Pipeline state confirmed

- `SYSTEM_PROMPT_TEMPLATE`: iter 5 state (rules 1-10 + Examples 1-2 + Semantic Examples 3-4)
- Full regression: 977 tests, 2 skipped (same as iter 5 closing state)
- Model: `gpt-4o-mini`, temperature 0.0

### 1.4 Reviewer's calibration rules (locked in during review)

The reviewer established three judgment rules during the review pass, documented here for reproducibility:

1. **Subsystem names explicitly listed as modules** (`core`, `authoring`, `application`, `service`, `sdk`) count as **valid** `Module` identities, even if the source is narrative prose. The test is "is this thing explicitly declared as a subsystem/component in the source?"
2. **File paths, function names, internal hashes, abstract concept labels** used as `Document.title` or `Module.module_name` generally fall to `WRONG_ENTITY`. The grounding test is "does this stable identifier appear verbatim in the source in a way that's semantically a title/name?"
3. **Status, impact, risk, rationale, metadata** (`完整`, `implemented`, risk statements, trade-off explanations) used as `module:description` or `document:mentions` field values fall to `WRONG_ARG` — these are not declarative descriptions of what the entity IS or DOES.

These rules were consistent across all 3 packets and match iter 5's explicit F-01/F-02 criteria from the blueprint.

---

## 2. Aggregate metrics

### 2.1 Strict and salvageable rates (per sample + combined)

| sample | total | yes | partial | no | strict rate | salvageable rate |
|---|---:|---:|---:|---:|---:|---:|
| `short_03_architecture` | 9 | 5 | 4 | 0 | **55.6%** | 100% |
| `medium_02_blueprint_backref` | 10 | 2 | 8 | 0 | **20.0%** | 100% |
| `medium_03_audit_report` | 26 | 5 | 21 | 0 | **19.2%** | 100% |
| **β.1 combined** | **45** | **12** | **33** | **0** | **26.7%** | **100%** |

### 2.2 All-5-sample combined (iter 5 + β.1)

Adding β.1 to the iter 5 sample pool:

| metric | iter 5 (86 drafts) | β.1 (45 drafts) | combined (131 drafts) |
|---|---:|---:|---:|
| yes | 10 | 12 | 22 |
| partial | 76 | 33 | 109 |
| no | 0 | 0 | 0 |
| strict rate | 11.6% | **26.7%** | **16.8%** |
| salvageable rate | 100% | 100% | 100% |

**Important**: β.1's 26.7% is higher than iter 5's 16.2% but is driven mostly by `short_03_architecture`'s 55.6% (outlier on an explicit-enumeration sample). All-5-sample combined strict rate is **16.8%**, essentially flat with iter 5's 16.2%.

### 2.3 Target compliance (SG-14)

| metric | target | all-5 result | status |
|---|---|---:|:---:|
| combined strict approval rate | ≥40% | **16.8%** | **MISS by 23.2pp** |
| combined salvageable rate | ≥95% | **100%** | **PASS** |

No material change from iter 5's target compliance.

### 2.4 Reason code distribution (β.1 only)

| reason_code | short_03 | medium_02 | medium_03 | β.1 total | β.1 % of partials |
|---|---:|---:|---:|---:|---:|
| CORRECT | 5 | 2 | 5 | 12 | — |
| WRONG_ENTITY | 4 | 2 | 11 | 17 | 51.5% |
| WRONG_ARG | 0 | 6 | 10 | 16 | 48.5% |
| WRONG_PREDICATE | 0 | 0 | 0 | 0 | 0% |
| OVERGENERAL | 0 | 0 | 0 | 0 | 0% |
| HALLUCINATED | 0 | 0 | 0 | 0 | 0% |
| DUPLICATE | 0 | 0 | 0 | 0 | 0% |
| AMBIGUOUS | 0 | 0 | 0 | 0 | 0% |

**WRONG_ENTITY** (17) and **WRONG_ARG** (16) split almost evenly. Same shape as iter 5 review, where WRONG_ENTITY (20) and WRONG_ARG (8) dominated. Interesting shift: β.1 has relatively more WRONG_ARG — driven by medium_02 (6 cases of "implemented" as field value inherited from blueprint metadata) and medium_03 (10 cases of Module description content not being declarative).

### 2.5 Per-entity-type strict rates

| sample | Module total | Module CORRECT | Module strict | Document total | Document CORRECT | Document strict |
|---|---:|---:|---:|---:|---:|---:|
| `short_03_architecture` | 5 | 5 | **100%** | 4 | 0 | 0% |
| `medium_02_blueprint_backref` | 2 | 0 | **0%** | 8 | 2 | 25% |
| `medium_03_audit_report` | 13 | 1 | **7.7%** | 13 | 4 | 30.8% |
| **β.1 combined** | **20** | **6** | **30.0%** | **25** | **6** | **24.0%** |

For comparison (iter 5 baselines):

| sample | Module total | Module strict | Document total | Document strict |
|---|---:|---:|---:|---:|
| `medium_01_security` (iter 5) | 0 | n/a | 1 | 0% |
| `long_01_kernel_p0` (iter 5) | 24 | 8.3% | 12 | 33.3% |
| **iter 5 combined** | 24 | 8.3% | 13 | 30.8% |

**All-5-sample Module strict rate**: (6 + 2) / (24 + 20) = 8 / 44 = **18.2%**. This is a modest improvement over iter 5-only's 8.3%. But the gain is concentrated on one sample (short_03's 5/5 perfect rate).

**All-5-sample Document strict rate**: (6 + 4) / (13 + 25) = 10 / 38 = **26.3%**. Down slightly from iter 5-only's 30.8% because β.1 introduced many Document drafts with the new "WRONG_ARG inherited status" failure mode.

---

## 3. F-03 cross-sample findings

### 3.1 The key diagnostic table

| sample | content style | Module drafts | Module WRONG_ENTITY | **F-03 rate** | F-03 judgment |
|---|---|---:|---:|---:|---|
| `medium_01_security` (iter 5) | narrative, low code-literal | 0 | 0 | **n/a** | absent (no data) |
| `long_01_kernel_p0` (iter 5) | blueprint, high code-literal, no enumeration | 24 | 17 | **70.8%** | **PRESENT (strong)** |
| `short_03_architecture` (β.1) | architecture, explicit subsystem enumeration | 5 | 0 | **0.0%** | **ABSENT** |
| `medium_02_blueprint_backref` (β.1) | blueprint, high code-literal, no enumeration | 2 | 2 | **100.0%** | **PRESENT (on tiny sample)** |
| `medium_03_audit_report` (β.1) | audit/reference, mixed content | 13 | 2 | **15.4%** | **WEAK** |

**All-5-sample aggregate**: Module WRONG_ENTITY = 17 + 0 + 2 + 2 = **21**, Module drafts = 24 + 5 + 2 + 13 = **44**. F-03 rate = **47.7%**. But this masks the bimodal distribution: blueprint-style samples cluster at ~70-100%, other styles cluster at 0-15%.

### 3.2 The discriminating factor: explicit enumeration

The five CORRECT Module drafts on `short_03_architecture` all come from one specific source passage:

```
2. 模块边界优先于一次性大统一
  - `core` 负责运行时语义内核。
  - `authoring` 负责编译、预检、registry 工作流。
  - `application` 负责 core 之上的中性运行层。
  - `service` 负责前端/BFF 形态的 HTTP 交付面。
  - `sdk` 负责 Python authoring 与 facade 体验。
```

This is an **explicit declarative enumeration** of subsystems with their descriptions. It's the exact shape iter 5's Example 4 taught: "Module(module_name=X) with declarative description of what X does". The LLM applies the pattern perfectly and produces 5/5 correct Module extractions.

The two F-03-strong samples (`long_01_kernel_p0`, `medium_02_blueprint_backref`) do **not** have explicit enumerations. They have code literals embedded in narrative text or blueprint sections, and the LLM has no anchor pattern to match. It falls back to routing any code-shaped token into `Module`, producing file paths, function names, HTTP headers, stdlib classes, and hazard IDs as module_name values.

**Conclusion**: iter 5's existing examples work when the content matches the example shape. They fail when it doesn't. The fix is not to add more examples that cover more shapes — it's either to teach **abstention by default** (only route to Module when explicitly declared) or to **expand the schema** so the LLM has better routing targets for non-module code literals.

### 3.3 Secondary finding: Module failures shift axis on mixed content

`medium_03_audit_report`'s Module draft failures are dominated by WRONG_ARG (10/13) rather than WRONG_ENTITY (2/13). This is the opposite of `long_01_kernel_p0`'s pattern.

Interpretation: on audit/reference content with diverse entity candidates, the LLM is more cautious about Module routing — it doesn't pull random code literals in. But it struggles to produce declarative description values; most Module descriptions are risk/impact/rationale content from the audit, not "what the module does" statements.

This suggests **two distinct Module failure modes** that different content types activate:
- **Identity-axis failure** (F-03 proper): blueprint content without enumeration
- **Description-axis failure** (F-02 residual on rich content): audit/reference content with metadata

### 3.4 Document-side failures are heterogeneous across samples

| sample | Document CORRECT | Document WRONG_ENTITY | Document WRONG_ARG | dominant failure mode |
|---|---:|---:|---:|---|
| `short_03_architecture` | 0/4 | 4/4 | 0/4 | concept-label synthesis (e.g., "principle document", "historical blueprint") |
| `medium_02_blueprint_backref` | 2/8 | 0/8 | 6/8 | metadata-inheritance (correct filenames + "implemented" as field value) |
| `medium_03_audit_report` | 4/13 | 9/13 | 0/13 | title fabrication (similar to iter 4 pattern) |

Three distinct Document failure modes across three samples. The underlying issue is the Document entity type's `title` and `field_values` being semantically under-specified — the LLM fills them opportunistically with whatever fits.

---

## 4. What is NOT a problem

### 4.1 Zero hallucination — STILL zero on all 5 samples

All 131 drafts across iter 5 + β.1 are grounded in real source text. No `no` verdicts, no `HALLUCINATED` reason codes, salvageable rate 100%. The pipeline's structural correctness baseline is fully preserved.

### 4.2 Pipeline layer is clean

- Zero `schema_entity_type_unknown` across all β.1 runs
- Zero `schema_pred_id_unknown`
- Zero `spec_construction_failure`
- Zero `scope_*` rejections
- Zero per-segment errors (all 162 new β.1 segments processed successfully)
- Bundles generated correctly on all 3 samples

### 4.3 Per-type abstention invariant held on β.1

Iter 5's P1 fix (per-type abstention independent of rule 4) held across all 3 β.1 samples:
- `short_03` produced valid drafts (no segment-level collapse despite only 9 drafts from 23 segments)
- `medium_02` produced 10 drafts with 0 rejections (cleanest structural outcome in β.1)
- `medium_03` produced 26 drafts from 81 segments with clean rejection shape (~16% rejection rate)

### 4.4 OBS-01 variance envelope held

All 3 regen-vs-canonical drifts were within OBS-01's envelope:
- `short_03`: +1 valid (canonical 8 → regen 9)
- `medium_02`: +1 valid (canonical 9 → regen 10)
- `medium_03`: **+10 valid** (canonical 16 → regen 26) — at the upper boundary of OBS-01 (iter 4 max was +20)

The `medium_03` drift is notable but still within the envelope. The review was conducted on the high-end sample; proportional rates are more stable than absolute counts.

### 4.5 Reason code taxonomy is sufficient

Zero new codes needed for β.1. The existing 9-code set covers every failure mode observed. `OVERGENERAL` and `DUPLICATE` and `AMBIGUOUS` remain unused in β.1 (same as iter 5 review for DUPLICATE/AMBIGUOUS; iter 5 had 3 OVERGENERAL cases on long_01).

---

## 5. New observations recorded during β.1

### 5.1 OBS-02 — Pattern B overpacking crosses over to `document:mentions`

Logged in [cross_run_observations.md](../../cross_run_observations.md) as P3 during β.1 canonical runs. Summary:

- One canonical rejection on `short_03_architecture` showed Pattern B's multi-entry overpacking shape applied to `document:mentions` (`got 4, expected 1`) instead of the previously-only-observed `module:description`
- 1 confirmed instance out of 162 new β.1 segments (~0.6% rate)
- Non-blocking; didn't cause β.1 to halt
- Implication: Pattern A and Pattern B are defined by **shape**, not by **predicate**. Future reports should classify by shape.

### 5.2 Revised `short_03_architecture` control role

The original β.1 framing labeled `short_03` as a "negative control" on the assumption that narrative philosophy prose would have low extraction pressure. Canonical run data invalidated this: 43.5% segment hit rate (highest in any B3 run). The backtick'd subsystem names and numbered principle headers produced strong extraction candidates.

The plan file §2.1 now carries both the original framing (struck through / flagged invalidated) and the revised framing ("unexpected high-pressure sample"). This is the β.1 record of a prediction that didn't hold.

### 5.3 `medium_02`'s zero-rejection finding is partial good news

`medium_02_blueprint_backref` produced **zero structural rejections** on its canonical run, sharply contrasting with `long_01_kernel_p0`'s iter 5 rejection rate (~16%). Human review revealed the reason: structural cleanness and semantic correctness are independent axes. Medium_02 has 0 rejections but its 2 Module drafts are 100% F-03 failures (both file paths misrouted to Module).

This finding confirms that **structural rejection count is an unreliable proxy for semantic quality**. Future B3 analyses should always measure both axes independently.

---

## 6. Verdict proposal + next-direction options

See [plan file §5](../../sample_expansion_plan_2026-04-11.md#5-decision-proposal-pending-user-verdict) for the complete 4-option breakdown. Summary here:

### 6.1 The four options

- **α — iter 6 prompt fix on Module identity grounding.** Add one example block teaching the LLM to abstain from Module routing when source doesn't explicitly declare modules. Cheapest. Risk: 4th consecutive prompt iteration with diminishing returns.
- **β continuation — more samples.** Add 2-4 more docs with different content styles. Cheap, low risk. Delays any actual fix.
- **γ — schema expansion.** Decompose `Module` into multiple specific entity types (`ClassName`, `FunctionName`, `FilePath`, `ExternalProduct`, etc.). Addresses root cause. Largest scope.
- **δ — leave iter 5 alone.** Accept current state. Move to other B3 priorities (format coverage, commit path, FUP-01 record-replay).

### 6.2 My recommendation: **δ (leave iter 5 alone)**

Reasoning:
1. **Prompt iteration has hit diminishing returns.** OBS-02 appeared in β.1 with no code change — just by expanding the sample set we surfaced a new behavioral observation. Adding another prompt block (α) is likely to introduce a 5th side effect before closing F-03 cleanly.
2. **The root cause is schema coarseness, not prompt inadequacy.** The `medium_03_audit_report` finding (Module failures shift to WRONG_ARG, not WRONG_ENTITY, on audit content) hints that the LLM routes things to Module largely *because there is no better place*. More entity types (γ) would let the LLM route correctly. But γ is a bigger project than a prompt iteration.
3. **Other B3 work is untouched and may be higher-value.** The original README plan called for 9 samples including PDF/DOCX parser path coverage and a scanned-PDF failure case. These have not been exercised. They may reveal different failure modes that inform a better eventual fix than F-03-only prompt iteration.
4. **16.8% strict rate across 5 samples is not a crisis.** It's below SG-14 target but the trend is positive (iter 4 → iter 5 → β.1 confirms iter 5 is real improvement). Pausing prompt iteration here is not abandoning the quality work — it's acknowledging that the next good move is somewhere else.

### 6.3 Explicit second choice

If short-term strict-rate improvement is the priority over diagnostic clarity: **α with narrow scope** — one example block targeting Module identity grounding, combined with an explicit commit-in-advance that if iter 6 also misses SG-14, iter 7 opens γ (schema expansion) instead of continuing prompt iteration. This bounds the prompt iteration fatigue risk.

### 6.4 What this summary does NOT commit

- No iter 6 blueprint opened
- No `SYSTEM_PROMPT_TEMPLATE` changes
- No schema changes
- No sample removal or reclassification
- No archived iter 4/5 artifact modifications
- No `cross_run_observations.md` OBS-02 severity upgrade
- No decision on any of the 4 options — that's your call

---

## 7. Known limitations

1. **n=5 total sample cohort** is still thin for F-03 claims. The "F-03 strong on blueprints, absent on enumerations, weak on audits" pattern is based on 5 data points. A proper generalization claim would need ~15-20 samples.
2. **Bimodal F-03 distribution on blueprint samples** (long_01 70.8% / medium_02 100%) may be partly a small-sample artifact. medium_02 had only 2 Module drafts; 100% of 2 is statistically thin.
3. **Document failure modes are heterogeneous**. The summary collapses them into "WRONG_ENTITY / WRONG_ARG / OVERGENERAL" counts but the underlying failure shapes are distinct (concept-label synthesis, metadata-inheritance, title fabrication). Future iteration summaries should track these as separate sub-codes or extend the taxonomy.
4. **No CORRECT Module retention data** across iterations. Iter 4 had 8 CORRECT Module drafts on long_01; iter 5 kept 2; β.1 adds 5 on short_03 (new) + 1 on medium_03 (new). We cannot track "did the same CORRECT draft survive" across iterations because samples are re-extracted fresh each time.
5. **Variance amplification on small samples**. `short_03`'s 5/9 = 55.6% strict rate and `medium_02`'s 0/2 = 0% Module strict rate both have wide confidence intervals at n < 15. The combined β.1 26.7% is more robust than per-sample numbers.
6. **`short_03`'s 100% CORRECT Module rate depends on one specific passage**. All 5 correct Module drafts come from the same 5-line "module boundaries" enumeration. If that passage didn't exist, F-03 might be ABSENT on the rest of the document too (because there's nothing else that looks Module-y), or it might appear on other passages. Single-passage signal.
7. **Reviewer's calibration rules were formulated mid-review**, not pre-committed. The rules are sensible and internally consistent, but a second reviewer with different priors could mark some drafts differently (e.g., whether `FactPy Kernel` as `Module` is CORRECT or WRONG_ENTITY).

---

## 8. Next steps (pending user decision)

- [ ] User chooses verdict: α / β continuation / γ / δ / mixed
- [ ] If α: open iter 6 blueprint at `draft` status, scoped to Module identity grounding example
- [ ] If β continuation: propose 2-4 more sample candidates, repeat inventory + copy + canonical + packet + review cycle
- [ ] If γ: open schema expansion blueprint (larger scope, not a scoped prompt iteration)
- [ ] If δ: identify next B3 priority (format coverage, commit path, FUP-01, etc.) and open a plan for it
- [ ] Regardless of choice: this β.1 review summary is authoritative for β.1 findings. The plan file will stay as the living tracker until β.1 is formally closed; then it joins this summary as frozen evidence.

No next-step action happens without user confirmation.
