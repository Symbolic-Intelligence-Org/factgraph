# B3 Cross-Run Observations

This file holds findings that span **multiple** B3 runs of the same sample,
that is, findings which cannot be attributed to a single iteration report.
Each entry is lightweight — **not** a blueprint. Entries may eventually
graduate to a blueprint if they trigger engineering work.

Entries are append-only (new findings go to the end). Do not edit or
remove historical entries without updating their status inline.

---

## OBS-01 (P2): LLM extraction counts have visible variance at `temperature=0.0`

- **Status**: observed, accepted as baseline for B3 v1
- **Date first observed**: 2026-04-11
- **Related**:
  - [iteration 4 report §8 Addendum](./report/load_test_report_2026-04-11_iter4.md#8-addendum--2026-04-11-variance-correction)
  - Three run_records on the same sample pair: archived iter 4 (`b3_20260410T194444Z_*` / `b3_20260410T194711Z_*`), canonical stability rerun (`b3_20260410T214607Z_*` / `b3_20260410T214655Z_*`)
- **Category**: methodology / observability

### Finding

Three independent runs of `run_load_test.py` on the same two samples,
same manifest, same `test_schema_ir.json`, same prompt template, same
`gpt-4o-mini` model, same `temperature=0.0`, produced the following
spread in extraction metrics:

| run | medium valid / proposals | long valid / proposals |
|---|---:|---:|
| run 1 (archived iter 4) | 14 / 15 | 57 / 79 |
| run 2 (packet generation regen) | 9 / 14 | 77 / 108 |
| run 3 (canonical rerun) | 7 / 13 | 60 / 81 |

Absolute count variance on **long_01_kernel_p0**:
- valid: min 57, max 77, range 20 (≈35% relative swing)
- proposals: min 79, max 108, range 29 (≈36% relative swing)

Absolute count variance on **medium_01_security**:
- valid: min 7, max 14, range 7 (≈100% relative swing)
- proposals: min 13, max 15, range 2 (≈15% relative swing)

The medium sample's large relative swing in `valid` is dominated by
**small-N noise** (the sample only produces ~13-15 proposals total, so
a 1-2 proposal shift = 10-15% relative change).

### What IS stable across all three runs

- **Rejection category shape**: 100% `schema_field_type_mismatch`, 100%
  on `document:mentions`, 100% `got 2, expected 1` Pattern A subject leakage
- **Long sample valid rate**: 72%, 71%, 74% (range 3pp)
- **Qualitative conclusions**: Pattern A is the only dominant residual;
  no new rejection classes appeared

### What is NOT stable

- **Absolute counts** (proposals, valid, rejected) per sample
- **Medium sample valid rate**: 93%, 64%, 54% (large relative swing,
  but dominated by small-N noise on ~13-15 proposals)

### Root cause

`temperature=0.0` is not a guarantee of determinism on OpenAI's current
gpt-4o-mini deployment. Known contributors to residual variance include:

- Internal batching/routing across backend instances
- Non-deterministic floating-point reductions on GPU kernels
- Sampling-time token-tie breaking even when logits are theoretically
  identical

This is a well-documented property of production LLM APIs and is **not**
a bug in the FactPy Kernel agent pipeline.

### What this changes

**Changes**:
1. Single-run counts are **samples**, not ground truth. Iteration reports
   that quote `X% valid rate` should note whether X is a single
   observation or a multi-run mean.
2. Iteration 4's headline `76%` was a single observation; the 3-run mean
   is ~72% ± ~3pp. See iter 4 §8 Addendum for the correction.
3. Future iteration report templates should encourage recording at least
   the `valid_count ± variance` envelope when absolute counts are used as
   acceptance criteria.

**Does NOT change**:
1. Rejection shape analysis and dominant-pattern identification (these
   have been 100% stable across runs).
2. Qualitative iteration-over-iteration improvement claims when the
   delta is well outside sampling noise (e.g., iter 3's 57% → iter 4's
   ~72% is a ≥+15pp improvement, far larger than the ±3pp observed
   variance).
3. The 4C2 human review pass — semantic quality per-draft does not depend
   on exact count reproducibility.
4. Blueprint quality criteria. Blueprints still target structural
   correctness, not particular numeric thresholds.

### Not in scope

- **Not a P1** — does not block any iteration, does not produce wrong
  conclusions when interpreted correctly, does not mask bugs
- **Not a blueprint** — no engineering work is planned on this right now
- **Not a P0** — the extraction pipeline is working correctly; this is
  strictly a measurement reproducibility issue at the API boundary
- The variance is not growing; it appears to be stationary

### Follow-up options (not scheduled)

See FUP-01 below for the natural engineering response (record-replay
cache). No commitment to when it lands.

---

## FUP-01 (deferred): B3 LLM record-replay cache

- **Status**: deferred; not scheduled; not blocking any current iteration
- **Filed**: 2026-04-11
- **Triggered by**: OBS-01
- **Kind**: potential future blueprint (not opened yet)

### Motivation

OBS-01 shows that `run_load_test.py` cannot reliably reproduce its own
prior runs, even with identical inputs. This is a **methodological**
limitation, not a functional one — the pipeline works, but its
empirical measurements are noisy.

A small record-replay cache in front of the extraction LLM call would
let a single run be reproduced bit-for-bit offline, which in turn would
let iteration reports make stronger claims about delta significance.

### Rough shape (for whenever it lands)

- **Cache key**: `hash(prompt_text + schema_ir_json + model_name + temperature)`
- **Cache value**: the raw LLM response bytes (before Pydantic parsing)
- **Location**: a new module under `src/factpy_kernel/agent/extraction/`
  (e.g., `llm_cache.py`), gated behind an `ExtractionConfig.cache_path`
  field that defaults to `None` (no caching)
- **Write path**: on cache miss, call the real LLM, write to cache,
  return value. Record the cache key and a timestamp in the run_record.
- **Read path**: on cache hit, return cached bytes without calling LLM.
  Record "cache_hit" in the run_record.
- **Eviction**: out of scope; cache grows unbounded unless manually cleared
- **Hash stability**: requires JSON canonicalization of schema_ir (sort
  keys, no whitespace) to avoid spurious misses

### Why deferred

1. **Not blocking**: the 4C2 human review pass can proceed today using
   one variance-aware packet; the review's conclusions are about semantic
   quality per-draft and do not depend on count reproducibility.
2. **Iteration 5 scope is uncertain**: we will know what iteration 5 is
   after human review finishes. If human review reveals semantic problems,
   record-replay is not the right lever — prompt or schema changes are.
3. **Implementation cost is nontrivial**: ~1 day of careful work including
   canonicalization, test suite updates, config plumbing, and docs. Better
   to schedule it when its value is clearly needed, not speculatively.
4. **Alternative is cheaper**: if iteration 5 needs tighter statistics,
   running `n=3` and reporting the mean (as done in iter 4 §8 Addendum)
   gives comparable epistemic value with zero new code.

### Acceptance criteria for opening a blueprint (not met yet)

- [ ] Human review on the current iter 4 variance packet has completed
- [ ] Iteration 5 scope is defined
- [ ] Iteration 5 has a concrete measurement claim whose validity depends
      on count reproducibility (e.g., "prompt change X drops rejection
      rate from A% to B% with B-A < ±3pp variance envelope")
- [ ] Only at that point does record-replay become the cheaper path vs.
      repeating n=3 runs per iteration

If any of the above becomes true, graduate FUP-01 to a standalone
blueprint in `docs/blueprints/active/`.

---

## OBS-02 (P2): Pattern B overpacking crosses over to `document:mentions`

- **Status**: observed on **3 distinct samples across 2 parser paths**. Upgraded from **P3 → P2 on 2026-04-11** based on format coverage Step 3 evidence. Still **non-blocking, observation-only, not a blueprint trigger** — severity reflects that evidence is now recurring across samples and predicates rather than a single-instance pattern.
- **Date first observed**: 2026-04-11 (during β.1 canonical run on `short_03_architecture`)
- **Date severity raised**: 2026-04-11 (after format coverage Step 3 on `medium_04_pdf_security` and `medium_05_docx_audit`)
- **Related**:
  - [β.1 sample expansion plan](./sample_expansion_plan_2026-04-11.md)
  - [format coverage plan §4.3.3](./format_coverage_plan_2026-04-11.md#433-pattern-b-predicate-crossover-has-now-appeared-on-all-3-non-md-native-samples)
  - `run_records/b3_20260411T114046Z_short_03_architecture.json`
  - `run_records/b3_20260411T134217Z_medium_04_pdf_security.json`
  - `run_records/b3_20260411T134637Z_medium_05_docx_audit.json`
  - [iter 5 review summary §5.3](./review/iter5/review_summary_iter5_2026-04-11.md)

### Finding

During β.1 Step 3 (canonical run on `short_03_architecture` using iter 5
prompt state), one rejection emerged with a previously unobserved shape:

```
schema_field_type_mismatch: field_values length mismatch
  for pred_id 'document:mentions': got 4, expected 1
```

Previously Pattern B (multi-entry overpacking, `got N≥3, expected 1`)
was observed **only on `module:description`**. Pattern A (subject
leakage, `got 2, expected 1`) was observed only on `document:mentions`.

This rejection is **Pattern B's overpacking shape applied to
`document:mentions`** — a predicate crossover. The reason class
(`schema_field_type_mismatch`) and validator trigger (length mismatch)
are both known; the new behavior is **Pattern B appearing on a
predicate where we had only seen Pattern A before**.

### Interpretation

The LLM is packing multiple items into `field_values` on
`document:mentions` when the source segment contains an enumerable
list. Architecture docs with numbered principles or bulleted
subsystem lists (`- core 负责...`, `- authoring 负责...`) appear to
trigger this shape. Iter 5's Example 2 (the structural multi-entry
overpacking example from iter 4's residual-patterns fix) uses the
generic `doc:has_topic` predicate, so the rule should apply to any
unary predicate — but the lesson apparently didn't fully transfer to
`document:mentions` in practice.

### Evidence scope

**As of OBS-02 filing (β.1, 2026-04-11 morning)**:

- **1 observed instance** on `short_03_architecture` (canonical run, β.1)
- **0 observed instances** on `medium_02_blueprint_backref` (0 rejections total)
- **0 sampled instances** on `medium_03_audit_report` (first 3 of 13 rejections are all Pattern A; remaining 10 unsampled)
- **Unknown on `long_01_kernel_p0`**: iter 5 canonical had 7 rejections of which the first 3 sampled were all Pattern B on `module:description` and 1 Pattern A on `document:mentions`. The remaining 3 are unsampled; could include Pattern B crossover but we don't know.

**As of OBS-02 severity raise (format coverage Step 3, 2026-04-11 afternoon)** — adds 2 new samples:

- **1 new confirmed instance** on `medium_04_pdf_security` canonical (1 of 3 sampled rejections is Pattern B crossover `got 3, expected 1` on `document:mentions`; 3 more rejections unsampled)
- **2 new confirmed instances** on `medium_05_docx_audit` canonical (2 of 3 sampled rejections are Pattern B crossover `got 3, expected 1` on `document:mentions`; 5 more rejections unsampled)

**Aggregate visible evidence** (across β.1 + format coverage Step 3):

| sample | parser path | Pattern B crossover instances in rejection_samples | total rejections (sampled + unsampled) |
|---|---|---:|---:|
| short_03_architecture | `txt` (PlainTextParser on MD) | 1 | 2 |
| medium_04_pdf_security | `pymupdf get_text("blocks")` | 1 | 6 |
| medium_05_docx_audit | `python_docx` block iteration | 2 | 8 |
| **aggregate** | **3 parser paths** | **4 confirmed** | **16 total (4 sampled of first 3 each + 7 unsampled = unknown upper bound)** |

**Key observations raising severity**:

1. **Cross-sample recurrence** — observed on 3 distinct samples (not 1). Evidence is no longer "single-instance pattern".
2. **Cross-parser recurrence** — observed on `txt` (PlainTextParser), `pymupdf`, AND `python_docx` parser paths. This means the behavior is **extraction-side** (LLM output), not parser-side (it happens regardless of how the document gets into the prompt).
3. **Consistent shape** — all 4 confirmed instances have `got 3, expected 1` (not got 2, not got 4+). This is a stable behavioral signature.
4. **Thin sampling means actual count could be higher** — `rejection_samples` is capped at 3 per run_record. True Pattern B crossover count across these 3 samples could be anywhere from 4 (confirmed minimum) to 16 (if all unsampled rejections are also Pattern B crossover). The 4-confirmed number is a lower bound.

### Severity and scope

**Severity: P2** (upgraded from P3 on 2026-04-11 based on format coverage Step 3 evidence)

- **P2** (risk annotation for future readers), **NOT P1, NOT a blueprint trigger**
- **Not a new reason class**: validator behavior is unchanged
- **Not a crash or regression in per-type abstention**: pipeline runs cleanly
- **Not a new failure mode in the blueprint sense**: it's a shape of an existing mode on a different predicate
- **Still observation-only** — reviewer explicitly stated on 2026-04-11: "这仍然是 observation, 不是 blueprint trigger; 但作为未来读者的风险标注, P2 更准确"
- **Signal is now recurring across samples and parser paths** — no longer "thin / single-instance". The 4 confirmed instances (lower bound) span 3 samples and 3 parser paths. If the unsampled rejections are representative, actual Pattern B crossover rate across format coverage + β.1 samples could be 25-50% of all rejections.

### What this changes

**Does NOT change**:

1. iter 5 verdict (already "implemented with deviations")
2. β.1 execution flow (did not block Step 3 → Step 4)
3. Any target metrics (SG-14 targets remain as stated)
4. Pattern A/B classification semantics in prior reports — Pattern B
   was always defined as "multi-entry overpacking" regardless of
   predicate; the previous observation that it appeared only on
   `module:description` was descriptive, not definitional

**Does change**:

1. The implicit assumption "Pattern A is document-side, Pattern B is
   module-side" is now falsified. Both shapes can appear on either
   predicate, given the right source content. Future reports should
   classify by **shape**, not by **predicate**.
2. Iter 5's Example 2 (the iter 4 multi-entry overpacking lesson)
   transfers imperfectly across predicates. This is a known prompt
   limitation; not actionable until we have more data volume.

### Follow-up

**Still not scheduled.** OBS-02 is purely descriptive / risk annotation, and that is the reviewer's explicit position even after the severity raise.

Escalation triggers to consider, in increasing order of action weight:

- **Upgrade to P1 (trigger blueprint)**: only if a future iteration finds Pattern B crossover in >60% of rejections AND it's specifically causing quality issues visible at the review level. The current evidence is 4/16 minimum (25%), so not yet.
- **Note in any future prompt iteration blueprint**: that examples should cover multiple predicates or use fully generic predicate names to improve cross-predicate transfer. Iter 5's Example 2 used `doc:has_topic` as the generic predicate but the rule didn't transfer cleanly to `document:mentions`.
- **Possibly adjust iter 5's Example 2** to explicitly show the overpacking rule applies to any unary predicate — but only in the context of a future prompt iteration blueprint that's already scoped for other reasons (i.e., don't open a new iter for OBS-02 alone).

**Current state (2026-04-11 afternoon)**: no blueprint opened, no scheduled action. Severity raised to P2 as a factual accuracy update. Next B3 line after format coverage is candidate-flagged as **runner commit path**, which is unrelated to OBS-02.
