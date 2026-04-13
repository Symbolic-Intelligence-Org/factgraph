# B3 Sample Expansion Plan — β.1 (2026-04-11)

- Date: 2026-04-11
- Author: agent B3 working tracker
- Kind: **working tracker** (not a blueprint, not a report, not a review summary)
- Status: **FINAL** — Steps 1–8 complete. User verdict: **δ (leave iter 5 alone)** on 2026-04-11. β.1 is sealed as frozen evidence. No further prompt iteration on iter 5 state. Next line: B3 format coverage (separate working plan at `format_coverage_plan_2026-04-11.md`).
- Related:
  - [samples_manifest.yaml](./samples_manifest.yaml) — updated to `smoke-2`
  - [iter 5 review summary](./review/iter5/review_summary_iter5_2026-04-11.md)
  - [iter 5 blueprint (archived)](../../../blueprints/archive/2026-04-11_agent-extraction-prompt-semantic-grounding.md)
  - [cross-run observations](./cross_run_observations.md)
  - [iter 4 report §8 Addendum](./report/load_test_report_2026-04-11_iter4.md#8-addendum--2026-04-11-variance-correction)

---

## 0. Goal

**Answer one question**: is F-03 (Module routing breadth regression introduced by iter 5) specific to `long_01_kernel_p0`'s code-literal-heavy content, or does it generalize across document types?

This determines the next direction after iter 5:

- If F-03 is **specific** to `long_01`-like content → iter 5 is "good enough for most documents", no iter 6 prompt fix needed urgently. Follow-up is schema-level (γ) or corpus curation (more samples).
- If F-03 is **general** across content types → iter 5 introduced a real prompt-level regression. Iter 6 prompt fix (α) is justified, targeted at Module entity routing.
- If F-03 is **content-density-proportional** → a gradient fix is appropriate (α) but may benefit from schema expansion (γ) as a deeper lever.

Per the iter 5 verdict, **no new prompt blueprint (α) is opened before this question is answered**. No iter 6 direction committed until Step 7 data is in.

---

## 1. Plan (β.1 steps)

```
Step 1 — Inventory candidates ........................ COMPLETE (2026-04-11)
  → 3 samples picked from existing repo content
  → each assigned an explicit F-03 control role
  → see §2 below for full inventory

Step 2 — Copy + manifest + tracker ................... COMPLETE (2026-04-11)
  → Step 2a: files copied to samples/
  → Step 2b: samples_manifest.yaml bumped to smoke-2 with 3 new entries
  → Step 2c: this tracker created
  → no LLM calls, no code changes, no run records produced

Step 3 — Canonical runs ............................... PENDING user go
  → run_load_test.py --sample <new_id> sequentially for each of the 3
  → capture per-sample run_records/*.json
  → record 4 metrics each: proposal_count, valid_count, rejection shape, segment hit rate
  → fill §3 per-sample run results table below

Step 4 — Packet generation ............................ PENDING user go
  → for each sample with ≥1 valid draft, generate iter 5 packet via
    generate_review_packet.py --output-dir review/iter5/
  → packet header inherits iter 5 context block style
  → fill §3 with packet paths

Step 5 — Human review pass ............................. PENDING user go
  → review the new packets
  → same REVIEW block taxonomy as iter 4 / iter 5
  → expected order: short_03 → medium_02 → medium_03
  → record strict approval rate + reason_code distribution per sample

Step 6 — Per-sample aggregate ........................... PENDING
  → for each sample: compute strict rate, Module WRONG_ENTITY count, per-entity-type split
  → fill §3 with review results

Step 7 — F-03 cross-sample table ........................ PENDING
  → fill §4 — the key diagnostic table
  → rows: all 5 samples with F-03 measurements (2 from iter 5 + 3 new from β.1)
  → columns: content profile, Module WRONG_ENTITY count, Module total, F-03 rate,
            judgment (F-03 present / absent / weak)

Step 8 — Decision ...................................... PENDING
  → based on §4, fill §5
  → options: α (iter 6 prompt fix), β continuation (more samples), γ (schema expansion),
            or "leave iter 5 alone"
  → no direction committed before this step
```

---

## 2. Candidate sample inventory (COMPLETE)

All 3 samples approved by reviewer on 2026-04-11. Copied to `samples/` and registered in `samples_manifest.yaml` as of Step 2.

### Sample 1: `short_03_architecture` — **F-03 control role: NEGATIVE (original) / UNEXPECTED HIGH-PRESSURE (revised)**

**⚠ Original framing INVALIDATED by canonical run data**. See revision note below.

| field | value |
|---|---|
| sample_id | `short_03_architecture` |
| source | `docs/architecture_principles.md` |
| destination | `samples/short/short_03_architecture.md` |
| size | 2,789 bytes |
| lines | 66 |
| length_class | `short` |
| domain | `architecture` |
| **control role (original framing)** | negative control — assumed to have low extraction pressure on the grounds that it is narrative Chinese prose about design philosophy |
| **control role (revised framing, post-canonical)** | **unexpected high-pressure sample**. Canonical segment hit rate is **43.5%** — the highest observed in any B3 run to date. The backtick-wrapped module/directory names (`core`, `authoring`, `application`, `service`, `sdk`, `docs/`, `memory/`) plus numbered principle headers (`### 1. 结构化优先...`, `### 2. 模块边界优先...`, etc.) produce strong entity candidates. This is NOT a negative control for F-03; it's a **mid-density sample whose pressure comes from backtick'd module terms rather than code literals per se**. |
| content profile | Narrative Chinese prose about design philosophy and module boundaries. Contains ~10 backtick-wrapped module/directory names. Zero classes, zero functions, zero file paths, zero HTTP headers, zero stdlib references — **but also zero absence of extraction pressure**. |
| F-03 prediction (original) | Should produce ≤2 Module WRONG_ENTITY drafts. |
| F-03 prediction (revised) | Likely produces several Module drafts routed from backtick'd subsystem names. Whether those count as F-03 depends on whether `core`/`authoring`/`application` should be considered "modules" semantically. Reviewer's judgment call during review will decide. |
| est. segments | ~15-25 |
| actual segments (canonical) | **23** |
| est. canonical run time | ~30-60 s |
| actual canonical run time | **25 s** |

### Sample 2: `medium_02_blueprint_backref` — **F-03 control role: POSITIVE**

| field | value |
|---|---|
| sample_id | `medium_02_blueprint_backref` |
| source | `docs/blueprints/archive/2026-03-17_candidate-id-support-backref.md` |
| destination | `samples/medium/medium_02_blueprint_backref.md` |
| size | 8,866 bytes |
| lines | 214 |
| length_class | `medium` |
| domain | `spec` |
| **control role** | **positive control** |
| content profile | High code-literal density. Task blueprint with dense class/function/file references: `Store`, `CandidateSet`, `candidate_id`, `support_digest`, `BindingSupportCapture`, `_builders.py`, `_evaluate.py`, `explain_support(...)`, file paths to `src/factpy_kernel/core/store/runtime.py`, REST endpoint `POST /queries/explain-support`. Same structural pattern as `long_01_kernel_p0` at ~1/5 size. |
| F-03 prediction | Expected to reproduce F-03 at roughly proportional intensity: file paths, function names with trailing parens, class names. If F-03 does NOT appear here, F-03 was `long_01`-specific and probably related to its KP0/hazard-id content. |
| est. segments | ~45-75 |
| est. canonical run time | ~2-3 min |

### Sample 3: `medium_03_audit_report` — **F-03 control role: GRADIENT**

| field | value |
|---|---|
| sample_id | `medium_03_audit_report` |
| source | `docs/references/working/product-readiness-audit-2026-04-09.md` |
| destination | `samples/medium/medium_03_audit_report.md` |
| size | 10,581 bytes |
| lines | 266 |
| length_class | `medium` |
| domain | `audit` |
| **control role** | **gradient test** |
| content profile | Mixed. FactPy Kernel production readiness audit. Mix of market-comparison tables (competitor products: `Neo4j`, `Stardog`, `RDFox`, `AllegroGraph`, `ReasoningLayer`), engine names (`Souffle`, `ProbLog`, `PyReason`), project class names (`ArtifactSidecar`, `CandidateSet`, `EvidenceGraph`, `AnnotationRow`), file paths, and substantive narrative. |
| F-03 prediction | Gradient test. Should show F-03 at lower intensity than positive control. Interesting probe: the competitor product names (`Neo4j`, `Stardog`) are clearly NOT project modules. If the LLM routes these to `Module` entity, that's a new F-03 failure shape (competitor name leakage). |
| est. segments | ~55-100 |
| est. canonical run time | ~3-4 min |

### Coverage claim of these 3 samples together

- **Code literal density axis**: architecture (low) → audit (mid) → backref (high)
- **Content type axis**: narrative philosophy → reference/audit → structured blueprint
- **Entity type pressure**: audit has the most diverse candidates (project classes + competitor product names + engine names); backref has the densest project-code references; architecture has the lightest pressure
- **F-03 control shape**: negative + positive + gradient (3-point regression line, not a yes/no test)

### Combined budget estimate (Step 3 + Step 4)

| item | estimate |
|---|---:|
| total new source size | ~22 KB |
| total new source lines | ~546 |
| total est. segments | ~115-200 |
| Step 3 canonical LLM time | ~6-8 min |
| Step 4 packet regen LLM time | ~6-8 min |
| combined LLM cost | ~$0.06 |
| Step 5 human review time (reviewer) | ~30-60 min, depending on draft counts |

---

## 3. Per-sample run results

_Steps 3 and 4 complete (canonical + packet). Steps 5+ pending user review pass._

### 3.1 `short_03_architecture` (unexpected high-pressure, revised from negative control)

| field | value |
|---|---|
| canonical run_record | `run_records/b3_20260411T114046Z_short_03_architecture.json` |
| proposals / valid / rejected (canonical) | **10 / 8 / 2** |
| proposals / valid / rejected (packet regen) | **10 / 9 / 1** (+1 valid, −1 rejected vs canonical) |
| segment hit rate | **43.5%** (10 / 23 — highest observed in any B3 run) |
| rejection shape (canonical) | 1× Pattern A (`document:mentions`, `got 2 expected 1`) + **1× NEW: Pattern B crossover** (`document:mentions`, `got 4 expected 1` — see OBS-02) |
| packet path | `review/iter5/review_pass_2026-04-11_short_03_architecture.md` |
| draft count in packet | 9 |
| review: yes / partial / no | **5 / 4 / 0** |
| review: reason codes | CORRECT=5, WRONG_ENTITY=4 |
| strict approval rate | **5/9 = 55.6%** |
| salvageable rate | 9/9 = 100% |
| **F-03 metric: Module WRONG_ENTITY / Module total** | **0 / 5 = 0.0%** |
| **F-03 judgment** | **ABSENT** — all 5 Module drafts (`core`, `authoring`, `application`, `service`, `sdk`) explicitly listed as subsystems in source text and correctly routed. 4 WRONG_ENTITY cases are on Document entity (synthesized concept labels like `principle document`, `historical blueprint`, `reconstructed archive`, `Historical Source`), not Module. |

### 3.2 `medium_02_blueprint_backref` (positive control)

| field | value |
|---|---|
| canonical run_record | `run_records/b3_20260411T105211Z_medium_02_blueprint_backref.json` |
| proposals / valid / rejected (canonical) | **9 / 9 / 0** |
| proposals / valid / rejected (packet regen) | **10 / 10 / 0** (+1 proposal, +1 valid vs canonical) |
| segment hit rate | **15.5%** (9 / 58) |
| rejection shape (canonical) | **none** — zero structural rejections of any kind |
| packet path | `review/iter5/review_pass_2026-04-11_medium_02_blueprint_backref.md` |
| draft count in packet | 10 |
| review: yes / partial / no | **2 / 8 / 0** |
| review: reason codes | CORRECT=2, WRONG_ARG=6, WRONG_ENTITY=2 |
| strict approval rate | **2/10 = 20.0%** |
| salvageable rate | 10/10 = 100% |
| **F-03 metric: Module WRONG_ENTITY / Module total** | **2 / 2 = 100.0%** |
| **F-03 judgment** | **PRESENT (strong on a tiny sample)** — both Module drafts are file paths (`src/factpy_kernel/tests/test_phase3_contracts_v1.py`, `_evaluate.py`) routed to `module_name`. This is exactly the long_01 F-03 failure shape at smaller scale. Note: only 2 Module drafts total, so the 100% rate is structurally significant but statistically thin. |

**Notable findings**:
1. **Zero structural rejections did NOT mean zero F-03.** The 10 valid drafts contain 2/2 = 100% F-03 failures on the Module side. Structural cleanness and semantic correctness are independent axes.
2. **Document-side failures were WRONG_ARG, not WRONG_ENTITY.** 6 Document drafts had verbatim-correct filenames as `title` but `implemented` as the field value — the "implemented" status was inherited from the blueprint header rather than being a grounded fact about the related document. This is a new subtype of F-04 (OVERGENERAL-adjacent).
3. **Only 2 CORRECT drafts**: both are Document drafts with verbatim filenames AND a real grounded field value (`CANDIDATE_PROTOCOL_V2.md`, `src/factpy_kernel/core/docs/01_architecture.md`). Both reference project-internal documentation files.

### 3.3 `medium_03_audit_report` (gradient test)

| field | value |
|---|---|
| canonical run_record | `run_records/b3_20260411T124044Z_medium_03_audit_report.json` |
| proposals / valid / rejected (canonical) | **29 / 16 / 13** |
| proposals / valid / rejected (packet regen) | **38 / 26 / 12** (+9 proposals, **+10 valid**, −1 rejected vs canonical) |
| segment hit rate | **35.8%** (29 / 81) |
| rejection shape (canonical, first 3 sampled) | all 3 Pattern A (`document:mentions`, `got 2 expected 1`); 10 more rejections not sampled in run_record |
| packet path | `review/iter5/review_pass_2026-04-11_medium_03_audit_report.md` |
| draft count in packet | 26 |
| review: yes / partial / no | **5 / 21 / 0** |
| review: reason codes | CORRECT=5, WRONG_ENTITY=11, WRONG_ARG=10 |
| strict approval rate | **5/26 = 19.2%** |
| salvageable rate | 26/26 = 100% |
| **F-03 metric: Module WRONG_ENTITY / Module total** | **2 / 13 = 15.4%** |
| **F-03 judgment** | **WEAK** — 13 Module drafts total, only 2 tagged WRONG_ENTITY. The dominant Module failure mode shifted from routing (WRONG_ENTITY) to description content (WRONG_ARG = 10/13 Module drafts). The LLM is mostly routing things to Module correctly on audit content, but struggles to pick declarative description values. 1 CORRECT Module draft (`FactPy Kernel`). Note: 9 Document drafts had WRONG_ENTITY (title grounding issues) — Document-side identity failures outnumber Module-side identity failures on this sample. |

**Notable findings**:
1. **F-03 is weak on audit-style mixed content** (15.4% of Module drafts). Most competitor product names (`Neo4j`, `Stardog`, `RDFox`) were NOT routed to Module — this is a *good* sign. The LLM recognized them as something other than project modules.
2. **Module failures shifted axis**: from identity (F-03, WRONG_ENTITY) to description (F-02-adjacent, WRONG_ARG). 10 of 13 Module drafts have correct identity but wrong `module:description` content.
3. **Document-side failures dominate**: 9 Document WRONG_ENTITY (title grounding) + 1 Document WRONG_ARG. This echoes iter 5's F-01 residual — when source content is mixed narrative, the LLM still sometimes fabricates Document.title values.

### 3.4 Aggregate β.1 canonical metrics

| sample | total_segments | proposals | valid | rejected | hit% | rejection shapes |
|---|---:|---:|---:|---:|---:|---|
| short_03_architecture | 23 | 10 | 8 | 2 | 43.5% | 1 Pattern A + 1 NEW Pattern B crossover |
| medium_02_blueprint_backref | 58 | 9 | 9 | 0 | 15.5% | none |
| medium_03_audit_report | 81 | 29 | 16 | 13 | 35.8% | ≥3 Pattern A (remaining 10 not sampled) |
| **β.1 total (canonical)** | **162** | **48** | **33** | **15** | **29.6%** | mix |
| iter 5 total (long_01 + medium_01) | 229 | 44 | 37 | 7 | 19.2% | Pattern A + Pattern B |

β.1 canonical aggregate: **33 valid drafts across 48 proposals and 162 segments**. Rejection rate 31% (higher than iter 5's 16%), driven mostly by medium_03_audit_report's 13 rejections.

### 3.5 Canonical vs regen drift summary (OBS-01 envelope check)

| sample | canonical valid | regen valid | Δ | within OBS-01 envelope? |
|---|---:|---:|---:|:---:|
| short_03_architecture | 8 | 9 | +1 | ✅ yes |
| medium_02_blueprint_backref | 9 | 10 | +1 | ✅ yes |
| medium_03_audit_report | 16 | **26** | **+10** | ⚠ high end (previous max +20 on iter 4 long) |

No sample broke OBS-01's envelope, but medium_03 sits at the upper boundary. Review is still meaningful because the proportional metrics should be stable even when absolute counts drift.

---

## 4. F-03 cross-sample table (COMPLETE)

### 4.1 Full 5-sample F-03 table

| sample | content profile | control role | Module drafts | Module CORRECT | Module WRONG_ENTITY | F-03 rate | F-03 judgment |
|---|---|---|---:|---:|---:|---:|---|
| `medium_01_security` | narrative (low code-literal) | iter 5 baseline | **0** | 0 | 0 | n/a | **ABSENT** (no data — all abstained) |
| `long_01_kernel_p0` | blueprint (high code-literal, KP0/hazard IDs, stdlib refs) | iter 5 baseline | **24** | 2 | 17 | **70.8%** | **PRESENT (strong)** |
| `short_03_architecture` | architecture (explicit subsystem enumeration) | β.1 unexpected high-pressure | **5** | 5 | 0 | **0.0%** | **ABSENT** |
| `medium_02_blueprint_backref` | blueprint (high code-literal, smaller scale) | β.1 positive control | **2** | 0 | 2 | **100.0%** | **PRESENT (on tiny sample)** |
| `medium_03_audit_report` | audit/reference (mixed, competitor products, project classes) | β.1 gradient | **13** | 1 | 2 | **15.4%** | **WEAK** |

### 4.2 The pattern is **content-style-dependent, not content-density-proportional**

Reading the table vertically reveals a pattern that doesn't quite match any of the 5 interpretive patterns I locked in advance:

- **F-03 PRESENT (strong)** on two samples: `long_01` (70.8%) and `medium_02` (100%). Both are **task blueprints** with dense code references (class names, function names, file paths) but no explicit "here are the modules" enumeration.
- **F-03 ABSENT** on one sample: `short_03` (0%). This is the architecture principles doc with an **explicit subsystem enumeration** ("- `core` 负责运行时语义内核。- `authoring` 负责...."). When the source text directly lists modules, the LLM extracts them correctly.
- **F-03 WEAK** on one sample: `medium_03` (15.4%). Audit report with competitor product names and mixed content. The LLM **did NOT** route competitor product names (`Neo4j`, `Stardog`, `RDFox`) to Module — so the F-03 generalization probe returned negative for that specific failure shape.
- **F-03 n/a** on one sample: `medium_01` (no Module drafts at all — iter 5 abstained from all Module candidates on that sample, which is a different story entirely).

### 4.3 New read: the discriminating factor is **explicit-enumeration vs implicit-reference**

All 5 CORRECT Module drafts on `short_03_architecture` are subsystem names that appear in an explicit list:

```
2. 模块边界优先于一次性大统一
  - `core` 负责运行时语义内核。
  - `authoring` 负责编译、预检、registry 工作流。
  - `application` 负责 core 之上的中性运行层。
  - `service` 负责前端/BFF 形态的 HTTP 交付面。
  - `sdk` 负责 Python authoring 与 facade 体验。
```

This is the **exact shape** that iter 5's Example 4 teaches: "Module(module_name=X) with a declarative description of what X does". The LLM learns the pattern and applies it cleanly.

Conversely, `medium_02` and `long_01` — the two strong-F-03 samples — have dense code literals (function names, file paths, test names) but **no equivalent explicit listing**. The LLM has no anchor pattern to match, so it falls back to routing whatever looks code-shaped into `Module`.

This reframes the interpretive framework:

| pattern | was predicted | actually observed | direction implication |
|---|---|---|---|
| F-03 on all 3 | maybe | no | — |
| F-03 on pos+gradient, absent on neg | maybe | **close match** — but gradient is weak not strong | — |
| F-03 only on pos | maybe | **close match** — F-03 strong on both pos and long_01, weak on gradient, absent on "neg" (which isn't really negative) | **the closest match** |
| F-03 absent on all 3 | maybe | no | — |
| F-03 weak on all 3 | maybe | no — it's not uniformly weak, it's bimodal (0% / weak / strong) | — |

The observed pattern is **approximately "F-03 present on blueprint-style samples without explicit module enumeration, absent otherwise"**.

### 4.4 Secondary finding: Module failures shift axis on mixed-content samples

On `medium_03_audit_report`, 10 of 13 Module drafts are WRONG_ARG (description axis) rather than WRONG_ENTITY (identity axis). This is the opposite of `long_01_kernel_p0`'s iter 5 pattern (where Module failures were mostly identity-axis). Interpretation: on audit/reference content, the LLM routes entities to Module more cautiously and correctly — but struggles to pick declarative description values. Different content types produce different Module failure modes.

### 4.5 New observation: Document-side failures are heterogeneous

| sample | Document drafts | Document CORRECT | Document WRONG_ENTITY | Document WRONG_ARG |
|---|---:|---:|---:|---:|
| `short_03_architecture` | 4 | 0 | 4 | 0 |
| `medium_02_blueprint_backref` | 8 | 2 | 0 | 6 |
| `medium_03_audit_report` | 13 | 4 | 9 | 0 |

Pattern:
- `short_03`: 100% Document WRONG_ENTITY (synthesized concept labels as titles)
- `medium_02`: 75% Document WRONG_ARG (filename correct, "implemented" inherited as wrong field value)
- `medium_03`: 69% Document WRONG_ENTITY (fabricated titles) + 31% CORRECT

These are **three distinct Document failure modes** (concept-label synthesis, metadata-inheritance, title fabrication). All three reduce to the same underlying issue: the Document entity type's `title` and `field_values` are both semantically under-specified, and the LLM fills them opportunistically.

---

## 5. Decision (proposal, pending user verdict)

### 5.1 F-03 cross-sample pattern (observed)

**F-03 is content-style-dependent, not content-density-proportional.** Specifically:

- **Present strongly** on task blueprints with dense code references but no explicit module enumeration (`long_01_kernel_p0`: 70.8%, `medium_02_blueprint_backref`: 100% on 2 drafts)
- **Absent** on architecture docs with explicit subsystem listings (`short_03_architecture`: 0% on 5 drafts)
- **Weak** on mixed audit/reference content (`medium_03_audit_report`: 15.4%)
- **Unmeasurable** on low-pressure narrative content where Module extraction never happens (`medium_01_security`: 0 Module drafts at all)

The discriminating factor is **whether the source text explicitly enumerates things as modules/subsystems**. Iter 5's Example 4 teaches the LLM to extract modules from explicit declarative enumerations — that lesson transfers cleanly to `short_03`. On samples without such enumerations, the LLM falls back to routing any code-literal to `Module`, which produces F-03.

### 5.2 β.1 strict approval rate signal

| sample | strict rate | note |
|---|---:|---|
| `short_03_architecture` | **55.6%** (5/9) | above SG-14 target of 40% |
| `medium_02_blueprint_backref` | **20.0%** (2/10) | below SG-14 target |
| `medium_03_audit_report` | **19.2%** (5/26) | below SG-14 target |
| **β.1 combined** | **26.7%** (12/45) | below SG-14 target of 40%, but higher than iter 5's 16.2% |

Adding β.1 to the iter 5 sample pool gives an **all-5-sample combined strict rate** of (10 + 12) / (86 + 45) = **22 / 131 = 16.8%**. This is close to iter 5's 16.2%. β.1's elevated 26.7% is driven mostly by `short_03`'s 55.6% — an outlier because the content is unusually amenable to iter 5's existing examples.

### 5.3 Candidate next directions (4 options)

#### Option α — iter 6 prompt fix targeting Module identity grounding

**Scope**: narrow prompt iteration. Add one new example block teaching the LLM what counts as a valid `module_name`. Show WRONG: file path, function name, test file name, HTTP header, stdlib class. Show RIGHT: explicit subsystem declaration (via enumeration, like `short_03`'s `- core 负责...`). Add per-type abstention teaching: when the source does not explicitly declare something as a module/subsystem/component, do NOT route it to Module — emit nothing for Module on that segment.

**Evidence in favor**:
- F-03 is real and reproducible on 2 of 5 samples (long_01, medium_02)
- The fix is narrowly scoped (one prompt block, same pattern as iter 5)
- `short_03` proves the prompt CAN learn this pattern when given the right anchor

**Evidence against**:
- Prompt iteration fatigue: iter 3/4/5 were three consecutive prompt rounds with diminishing returns. Iter 6 would be the 4th.
- Each iteration has introduced new side effects (iter 5 introduced F-03 itself, plus Document OVERGENERAL; OBS-02 Pattern B crossover appeared in β.1 on the same iter 5 prompt)
- The fix is structural ("teach the LLM what is a valid Module") but the underlying issue is semantic (the schema has only 2 entity types, forcing the LLM to choose between wrong options)

**Cost**: ~1 day of blueprint + patch + regression + iter 6 canonical + iter 6 review.

#### Option β continuation — expand B3 sample set further

**Scope**: add 2-4 more samples with different content styles before committing to α. Specifically: test whether F-03 reproduces on (a) a third kind of blueprint with explicit module listings (negative check), (b) a regulatory / spec document (new style), (c) a README/overview doc (new style).

**Evidence in favor**:
- The 5-sample cohort is informative but thin. Particularly, the "blueprint without explicit enumeration" category has only 2 data points (long_01 and medium_02), and medium_02's 100% F-03 rate is based on only 2 Module drafts total.
- Sample expansion is cheaper than prompt iteration and tests the reproducibility of the pattern
- Could reveal new failure modes or validate existing ones more confidently

**Evidence against**:
- Diminishing returns: we already have enough signal to identify F-03 as content-style-dependent
- Running more samples without acting on existing findings delays any real fix
- The F-03 evidence is already strong enough to justify action

**Cost**: ~4-8 hours of curation + runs + reviews for 2-4 new samples.

#### Option γ — schema expansion (decompose `Module` into multiple entity types)

**Scope**: extend `test_schema_ir.json` with new entity types: `ClassName`, `FunctionName`, `FilePath`, `EnvVar`, `BlueprintID`, `RepoFile`, `ExternalProduct`, etc. Let the LLM route code literals to the RIGHT entity type instead of misrouting them to `Module`.

**Evidence in favor**:
- This addresses the root cause (schema is too coarse) rather than papering over symptoms with prompt examples
- It would cleanly fix F-03 on the "blueprint without enumeration" case: file paths would go to `FilePath`, function names to `FunctionName`, etc.
- The audit report's success on `medium_03` (only 15.4% F-03 rate, lots of WRONG_ARG instead) hints that Module routing is NOT the main problem — the schema's over-loading of Module IS
- Longer-term durable: future B3 samples benefit automatically

**Evidence against**:
- Schema changes touch multiple layers (schema IR, prompt generation, validator, possibly response model)
- The `test_schema_ir.json` is explicitly provisional; schema work belongs in canonical SchemaIR territory
- Scope is much larger than α or β — not a scoped prompt iteration, more like a medium blueprint
- May introduce new failure modes (e.g., LLM doesn't know when to prefer `ClassName` vs `FunctionName`)

**Cost**: ~2-3 days of schema design + blueprint + patch + regression + iter 6+ canonical + review.

#### Option δ — leave iter 5 alone; move to other B3 priorities

**Scope**: archive β.1 findings as evidence. Accept iter 5's current state as the baseline. Move to other B3 items from the original README plan — format coverage (PDF, DOCX, scanned PDF), commit path wiring, record-replay cache (FUP-01), etc.

**Evidence in favor**:
- Iter 5 achieved 16.2% combined strict rate, up from iter 4's 11.6% — the trend is positive
- β.1 added 12 more CORRECT drafts (5 from `short_03`, 2 from `medium_02`, 5 from `medium_03`) — real improvements on samples iter 4 never saw
- F-03 is bounded and understood — we know when it happens and when it doesn't
- Other B3 work is untouched (format coverage, commit path) and may reveal different failure modes that inform a better eventual fix
- OBS-01 variance means more prompt tuning on a 5-sample cohort is noise-risk-high

**Evidence against**:
- F-03 is real and costs us semantic quality on exactly the kind of content B3 is built to process (blueprints, specs)
- Leaving it in place means iter 5's "implemented with deviations" status becomes de-facto permanent

**Cost**: 0 on iter 6. Reprioritizes toward other work.

### 5.4 My recommendation

**I lean toward δ (leave iter 5 alone, move on)** for two reasons:

1. **Prompt iteration has hit diminishing returns.** Every prompt iteration since iter 3 has introduced new observations (OBS-02 just confirmed this again in β.1). Adding another example block to `SYSTEM_PROMPT_TEMPLATE` is likely to introduce a 5th side effect before closing F-03.

2. **The schema is the real bottleneck.** The audit report (`medium_03`) data is the most informative finding: when the schema has only 2 entity types, Module failures shift to the description axis rather than the identity axis. More entity types would give the LLM cleaner routing targets. But γ is a bigger project than a prompt iteration and deserves its own blueprint design, not a rushed iter 6.

**But this is a judgment call with real trade-offs**, and the 4 options are genuinely competitive. If the priority is short-term strict-rate improvement on blueprint samples, **α** is the cheapest path. If the priority is broader evidence, **β** adds data. If the priority is durable fix, **γ** is right but expensive.

Explicit second choice: **α with narrower scope** — add a Module identity grounding example, but commit in advance that if iter 6 also misses SG-14 (strict rate ≥40%), we stop prompt iteration and open γ.

### 5.5 What I won't do without your direction

- Open any iter 6 blueprint (α)
- Collect new samples (β continuation)
- Open a schema expansion blueprint (γ)
- Modify iter 5 `SYSTEM_PROMPT_TEMPLATE` or any other code under `src/factpy_kernel/`
- Modify archived iter 4 or iter 5 artifacts

Awaiting user verdict: α / β continuation / γ / δ / mixed.

### 5.6 FINAL — user verdict locked on 2026-04-11

**Verdict**: **δ — leave iter 5 alone, reprioritize to B3 format coverage**

**Reasoning** (reviewer, 2026-04-11):

> "β.1 已经把关键信号测清了：F-03 是真实的，但更像 schema 过粗带来的路由问题，不是再加一段 prompt 就能稳收掉的问题。再做 α 大概率只是继续在 prompt 上打补丁。γ 方向是对的，但现在太大，不适合直接从 β.1 跳进去。所以最合理的是冻结 iter 5 现状，转去别的 B3 优先项。"

**Decisions made**:

1. **Iter 5 `SYSTEM_PROMPT_TEMPLATE` is frozen** as the current baseline. No rollback, no iter 6 prompt iteration.
2. **β.1 is closed** as final evidence. No additional β sub-phase, no re-review, no additional sampling.
3. **Next B3 priority is `format coverage`** — validating 4C1/4C3 parser paths on non-MD content (born-digital PDF, DOCX, scanned PDF failure case).
4. **α, β continuation, γ are all deferred** — not rejected, but not the immediate next step.
5. **FUP-01 record-replay cache** and **runner commit path** remain deferred.
6. **α → γ escalation** is the fallback path if format coverage eventually reveals that F-03 is the dominant B3 blocker — at that point γ (schema expansion) becomes the default, not α.

**Next artifact**: new working plan at
`docs/references/working/load-test-2026-04-11/format_coverage_plan_2026-04-11.md`

It will be a lightweight tracker like this one (not a blueprint), with its own inventory → copy → run → review → findings cycle targeted at parser-path validation rather than semantic quality.

### 5.7 What this plan freezes

This plan is now **historical evidence**. Further edits to it should be minimal (typo fixes, link updates). The findings, decision, and rationale in §3–§6 are the authoritative β.1 record. The companion artifact is `review/iter5/review_summary_beta1_2026-04-11.md` which contains the full review pass summary with the full F-03 cross-sample diagnostic.

**What cannot be changed without reopening β.1**:

- The 5-sample F-03 diagnostic table in §4
- The per-sample review results in §3
- The decision in §5.6
- The revised `short_03_architecture` control role framing in §2.1

**What can still be linked from here going forward**:

- The format coverage plan (when it surfaces findings that bear on F-03 or the schema question)
- A future iter 6 / iter 7 blueprint (if one is ever opened based on format coverage evidence)
- An OBS-03+ entry in `cross_run_observations.md` (if a new cross-run finding is discovered that bears on β.1's conclusions)

---

## 6. Stop conditions (for the full β.1 pass)

This plan is **complete** when §4 and §5 are filled. After that, this document freezes as an archived tracker and the chosen next direction either:

- Opens a new blueprint (α or γ) in `docs/blueprints/active/`
- Extends this plan into a β.2 phase with more samples (if data is inconclusive)
- Does nothing further (if F-03 is absent on all 3 new samples and iter 5 can be left alone)

No step in this plan modifies archived iter 5 artifacts. No step modifies `SYSTEM_PROMPT_TEMPLATE` or any code under `src/factpy_kernel/`.

---

## 7. What is frozen during this plan

- **Iter 5 `SYSTEM_PROMPT_TEMPLATE`**: current state of `prompts.py`, unchanged. Every canonical run in this plan uses the iter 5 prompt.
- **Iter 5 review packets** (medium + long in `review/iter5/`): frozen evidence.
- **Iter 5 review summary**: frozen evidence.
- **Iter 5 canonical run records**: frozen evidence.
- **Archived iter 4 artifacts**: fully frozen (per iter 4 variance caveat).
- **Archived iter 5 blueprint**: fully frozen (per iter 5 archival action).
- **`test_schema_ir.json`**: unchanged. This plan does not touch schema.
- **`run_load_test.py`** and **`generate_review_packet.py`**: unchanged. Same scripts as used in iter 5.

The only files this plan modifies are:
1. `samples_manifest.yaml` (version bump `smoke-1` → `smoke-2`, + 3 new entries)
2. `samples/short/short_03_architecture.md` (new file)
3. `samples/medium/medium_02_blueprint_backref.md` (new file)
4. `samples/medium/medium_03_audit_report.md` (new file)
5. `sample_expansion_plan_2026-04-11.md` (this file)

After Step 3 begins, additionally:
6. `run_records/b3_*_short_03_architecture.json` (new canonical record)
7. `run_records/b3_*_medium_02_blueprint_backref.json` (new canonical record)
8. `run_records/b3_*_medium_03_audit_report.json` (new canonical record)
9. `review/iter5/review_pass_2026-04-11_*.md` (new packets, if valid drafts produced)
