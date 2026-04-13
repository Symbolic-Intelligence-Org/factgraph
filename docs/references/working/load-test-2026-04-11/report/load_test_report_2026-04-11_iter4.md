# B3 真实文档负载测试报告 — Iteration 4

- Date: 2026-04-11
- Author: agent B3 harness
- Iteration: 4
- Related:
  - [README.md](../README.md)
  - [Iteration 3 report](./load_test_report_2026-04-11_iter3.md)
  - [Prompt residual-patterns fix blueprint](../../../blueprints/archive/2026-04-11_agent-extraction-prompt-residual-patterns-fix.md)

---

## 0. TL;DR

**Prompt examples worked, but only partially.** Iteration 4 added two
wrong/right examples to `SYSTEM_PROMPT_TEMPLATE`, targeting:

1. subject leakage (`got 2, expected 1`)
2. multi-entry overpacking (`got 3/4, expected 1`)

Result:

| sample | proposals | valid | rejected | valid rate |
|---|---:|---:|---:|---:|
| medium_01_security | 15 | **14** | 1 | **93%** |
| long_01_kernel_p0 | 79 | **57** | 22 | **72%** |
| **combined** | **94** | **71** | **23** | **76%** |

Compared with iteration 3:

- combined valid rate improved from **57% → 76%**
- Pattern B on `medium_01_security` dropped from **7 rejections → 1**
- Pattern A on `long_01_kernel_p0` dropped from **41 rejections → 22**

So the fix clearly helped, but **did not hit the iteration-4 target of
≥90% combined valid rate**. The remaining blocker is now much narrower:
almost all residual noise is still the same `got 2, expected 1`
subject-leakage shape on long_01.

---

## 1. 跑批概览

| # | Sample | Segments | Proposals | Valid | Rejected | Bundle | Outcome |
|---|--------|---:|---:|---:|---:|---|:---:|
| 1 | medium_01_security | 22 | 15 | **14** | 1 | `bundle_5cd1b343998c` | `success` ✓ |
| 2 | long_01_kernel_p0 | 207 | 79 | **57** | 22 | `bundle_172f0fcd7765` | `success` ✓ |

### 1.1 Sources

- medium_01_security record: `run_records/b3_20260410T194444Z_medium_01_security.json`
- long_01_kernel_p0 record: `run_records/b3_20260410T194711Z_long_01_kernel_p0.json`

---

## 2. Iteration 3 → 4 delta

### 2.1 Per-sample comparison

| sample | iter 3 valid/proposals | iter 4 valid/proposals | delta |
|---|---:|---:|---:|
| medium_01_security | 4 / 11 (36%) | 14 / 15 (**93%**) | **+57pp** |
| long_01_kernel_p0 | 60 / 101 (59%) | 57 / 79 (**72%**) | **+13pp** |
| combined | 64 / 112 (57%) | 71 / 94 (**76%**) | **+19pp** |

### 2.2 Rejection comparison

| sample | iter 3 rejected | iter 4 rejected | dominant shape |
|---|---:|---:|---|
| medium_01_security | 7 | **1** | `got 2, expected 1` |
| long_01_kernel_p0 | 41 | **22** | `got 2, expected 1` |

The examples almost completely removed the **multi-entry overpacking**
shape. The surviving error on medium_01 has converged to the same
subject-leakage shape that already dominated long_01.

---

## 3. What Improved

### 3.1 Pattern B mostly eliminated

Iteration 3 medium rejections were all `got 3/4, expected 1`. After the
examples landed, medium_01 now has only **1** rejection, and that one is
`got 2, expected 1`. This is strong evidence that the explicit
"one paragraph with several items -> several proposals, not one bloated
proposal" example was understood by the model.

### 3.2 Pattern A reduced but not removed

Long_01 still fails on the same `got 2, expected 1` subject-leakage
shape, but the count fell from **41 → 22**. The subject/field split
example clearly helps, but not enough to fully dislodge the model's
"copy all arg slots" heuristic on longer, more narrative material.

### 3.3 Throughput changed

Long_01 proposals dropped from **101 → 79** while valid specs only fell
slightly (**60 → 57**). That is a net quality improvement: fewer total
proposals, fewer malformed ones, similar volume of valid output.

---

## 4. Residual Problems

### P-08: Subject leakage remains the dominant residual pattern

- **Category**: prompt / LLM alignment
- **Severity**: P2
- **Evidence**:
  - medium_01: 1 rejection, `got 2, expected 1`
  - long_01: 22 rejections, all `got 2, expected 1`
- **Interpretation**: The wrong/right example reduced leakage, but the
  model still sometimes duplicates the subject entity into
  `field_values`.
- **Next diagnostic question**: is the remaining leakage concentrated in
  certain segment shapes, predicates, or wording patterns?

### P-09: Combined target missed

- **Category**: acceptance / prompt quality
- **Severity**: P2
- **Evidence**: combined valid rate is **76%**, below the blueprint
  target of **≥90%**
- **Interpretation**: The scoped prompt iteration is clearly beneficial,
  but not sufficient to declare extraction-shape noise "good enough"
  without either another prompt iteration or an operator decision to
  accept the residual error rate.

---

## 5. Resolution and Bundle

| sample | output_spec_count | merge_count | bundle_draft_count |
|---|---:|---:|---:|
| medium_01_security | 14 | 0 | 14 |
| long_01_kernel_p0 | 57 | 0 | 57 |

Resolution still runs cleanly, but `merge_count=0` remains unchanged.
This report does not add new evidence on dedupe quality; it mainly
confirms that better extraction quality flows through to larger, cleaner
bundle previews.

---

## 6. Recommendation

Iteration 4 is a **real improvement**, but not a close-out. The best
next step is now narrower than before:

1. either run one more **prompt-only micro-iteration** focused solely on
   residual subject leakage (`got 2, expected 1`)
2. or accept the current 76% baseline and move to **4C2 human review**
   with explicit awareness that ~1/4 of proposals are still malformed and
   filtered by the validator

I would prefer the first option before spending human review effort on
larger bundles.

---

## 7. Environment snapshot

- Python: `/Users/zhenzhili/miniforge3/bin/python`
- Model: `gpt-4o-mini`
- Prompt state: residual-patterns examples applied
- Full test suite at run time: `972 tests`, `2 skipped`

---

## 8. Addendum — 2026-04-11 variance correction

Added after iteration 4 was archived, when preparing the 4C2 human review
packet. Two additional observations of the same pipeline (same prompt,
same schema, same manifest, same model) were taken on the same day:

| run | medium valid / proposals | long valid / proposals | combined valid rate |
|---|---:|---:|---:|
| run 1 (archived iter 4, §1 of this report) | 14 / 15 (93%) | 57 / 79 (72%) | 71 / 94 = **76%** |
| run 2 (regen for packet generation) | 9 / 14 (64%) | 77 / 108 (71%) | 86 / 122 = **70%** |
| run 3 (canonical rerun for stability check) | 7 / 13 (54%) | 60 / 81 (74%) | 67 / 94 = **71%** |
| **3-run mean** | **10 / 14 (71%)** | **64.7 / 89.3 (72%)** | **74.7 / 103.3 ≈ 72.3%** |

### Correction to §0 TL;DR

The headline "combined valid rate improved from **57% → 76%**" in the
original §0 was based on a single observation. Re-sampled twice on the
same day, the combined valid rate settles around **~72% ± ~3pp**, not
76%. The iteration-3 baseline of 57% was similarly a single observation
and may be subject to the same variance (±3pp), though it has not been
re-sampled.

**The improvement is real** — 57% (iter 3, one sample) → ~72% (iter 4
three-sample mean) is a durable ≥+15pp delta, well outside noise. But
the exact magnitude of "19pp" advertised in the original §0 was
optimistically inflated by a lucky medium_01 sample in run 1.

**Specifically**: run 1's medium_01 valid rate of 93% was an upper
outlier. Runs 2 and 3 both land ~54-64%. The typical per-sample rate
for medium_01 under the current prompt is ~60%, not 93%.

### Pattern A invariance (unchanged)

Across all three runs, the rejection shape is 100% stable:
- 100% `schema_field_type_mismatch`
- 100% on `document:mentions`
- 100% `got 2, expected 1` (subject leakage, Pattern A)

The residual error mode has not changed at all between the three
observations. Only the absolute counts drift within variance. This
confirms that the qualitative conclusion of §4.P-08 ("subject leakage
remains the dominant residual pattern") is not affected by the
variance correction — it would stand even on a single run.

### What stays in the report vs. what moves out

- **Stays in §0-§7**: qualitative pattern analysis (Pattern A/B behavior,
  §3 improvement narrative, §4 residual problems, §6 recommendation)
- **Corrected in §8 (this addendum)**: only the headline numbers
  (`76% → ~72%`) and the magnitude of the iter 3 → iter 4 delta
- **Moved to cross-run observations**: the non-determinism observation
  itself (see `cross_run_observations.md` in this directory — short
  P2 note, not a blueprint)

### Methodological lesson

`temperature=0.0` is **not** deterministic on OpenAI's backends in
practice. Future B3 rounds should either (a) treat each run as one
sample from a distribution and report the mean of ≥3 runs, or (b)
land a record-replay LLM cache so that a single run is reproducible
offline. Option (b) is filed as a deferred follow-up in
`cross_run_observations.md`; this iteration does not pursue either.

### Run records for the new observations

- run 2 (regen): no run_record written (generated by
  `generate_review_packet.py` which is read-only for run_records);
  counts captured only in the review packet header
- run 3 (canonical): `run_records/b3_20260410T214607Z_medium_01_security.json`
  and `run_records/b3_20260410T214655Z_long_01_kernel_p0.json`

Both run 2 and run 3 used exactly the same prompt, schema, and manifest
as archived iter 4 (no code changes between them; the only difference is
LLM backend stochasticity).
