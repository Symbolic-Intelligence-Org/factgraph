# B3 Format Coverage Plan — 2026-04-11

- Date: 2026-04-11
- Author: agent B3 working tracker
- Kind: **working tracker** (not a blueprint, not a report, not a review summary)
- Status: **FINAL** — all steps complete. Format coverage phase closed 2026-04-11 with **parser-path verdict: PARSER_OK on all 3 samples**. Reviewer chose Option Y (seal, no packet generation, no human review). OBS-02 upgraded from P3 to P2 in `cross_run_observations.md` based on new evidence. Next B3 line candidate (flagged by reviewer, not committed): runner commit path.
- Follows: [β.1 sample expansion plan](./sample_expansion_plan_2026-04-11.md) (closed 2026-04-11 with verdict δ)
- Related:
  - [B3 README §1.1 sample set plan](./README.md#11-覆盖要求) — original 9-sample coverage specification
  - [β.1 review summary](./review/iter5/review_summary_beta1_2026-04-11.md)
  - [cross-run observations](./cross_run_observations.md)

---

## 0. Goal

**Exercise the 4C1 staging layer's PDF and DOCX parser paths** on real content, and validate that the pipeline correctly handles a scanned-PDF failure case.

This is the natural next step after β.1 because:

- **β.1 closed with verdict δ** (leave iter 5 alone, move on). Further prompt iteration was explicitly deferred.
- **All 6 B3 samples to date are Markdown** (`short_01_readme`, `short_02_agents`, `medium_01_security`, `long_01_kernel_p0`, `short_03_architecture`, `medium_02_blueprint_backref`, `medium_03_audit_report`). Only `PlainTextParser` has been exercised.
- **The B3 README §1.1 plan** called for 9 samples with format coverage: 3 born-digital PDFs + 2 DOCXs + 2 TXT/MD + 1 scanned PDF failure case. Only the TXT/MD slot is populated.
- **Format coverage is parser-path validation**, not semantic quality tuning. Different axis from F-03 / F-04 concerns.
- **A scanned PDF failure case** is specifically needed to validate the `unsupported_format` error path through staging → extraction → run_record.

### 0.1 What this plan answers

Three independent questions:

1. **Does the PDF parser path (PyMuPDF / pymupdf4llm) produce usable segments on real born-digital PDFs?** (staging quality signal)
2. **Does the DOCX parser path (python-docx) produce usable segments?** (staging quality signal)
3. **Does a scanned (image-only) PDF correctly trip the failure path?** (error-handling validation)

All three are **structural** questions about the staging layer. Semantic quality of extracted drafts is a secondary observation — if parser output is usable, we can inspect extraction and review later; if parser output is broken, semantic quality is moot until it's fixed.

### 0.2 What this plan is NOT

- NOT an iter 6 prompt iteration. `SYSTEM_PROMPT_TEMPLATE` is frozen at iter 5 state. No code changes under `src/factpy_kernel/`.
- NOT a schema expansion (γ). `test_schema_ir.json` unchanged.
- NOT a B3 completion claim. Even after this plan finishes, the B3 sample set will not reach the full 9-sample target unless more samples are added later.
- NOT a record-replay cache (FUP-01). Defferred.
- NOT a runner commit-path wiring. Deferred.

---

## 1. Plan steps

```
Step 1 — Candidate inventory ........................... IN PROGRESS
  → identify 3 candidate files (1 born-digital PDF + 1 DOCX + 1 scanned PDF)
  → determine sourcing path: existing repo content / pandoc-generate / user-provide
  → check pandoc + pymupdf + docx optional deps
  → report to user for approval; do NOT copy files yet

Step 2 — Copy + manifest + tracker update ............... pending
  → copy selected files to samples/ under appropriate length_class buckets
  → append 3 entries to samples_manifest.yaml (smoke-2 → smoke-3)
  → update §2 of this plan with finalized candidate list

Step 3 — Canonical runs .................................. pending
  → run_load_test.py --sample <new_id> sequentially
  → capture per-sample run_records/*.json
  → metrics of interest (different from β.1):
    - staging.success (bool — parser_name, parser_version)
    - staging.total_segments, total_chars, high_clarity_count
    - staging.avg_structural_clarity, pattern_type_distribution
    - staging.error_kind, error_message (for scanned PDF — expected failure path)
    - extraction_reachable (bool — did batch_extractor run at all?)
    - If extraction ran: proposals / valid / rejection shape (secondary)

Step 4 — Staging quality analysis ........................ pending
  → per-sample staging quality summary
  → classify by axis:
    - PARSER_FAIL: parser crashed / no segments / unsupported format
    - PARSER_DEGRADED: parser succeeded but segments are low-quality (e.g. OCR noise, page-break artifacts)
    - PARSER_OK: segments are comparable to MD-parsed content
  → for each sample, identify which failures are parser-layer vs prompt/schema-layer

Step 5 — (Optional) packet generation ..................... pending
  → only for samples where staging passed and extraction produced ≥1 valid draft
  → use existing generate_review_packet.py workflow (no changes)
  → packet header marks sample as "format coverage" phase, not iter 6 evaluation

Step 6 — (Optional) human review .......................... pending
  → only if packets were generated
  → purpose is to distinguish "valid draft but wrong because parser noise" from "valid draft but wrong because F-03/F-04"
  → not a strict-rate measurement — format coverage is about parser-path validation

Step 7 — Format coverage summary ........................... pending
  → §4 per-sample staging table
  → §5 axis classification: PARSER vs PROMPT vs SCHEMA failures per sample
  → §6 decision on next B3 priority based on findings:
    - If parser layer is broken → open 4C1 fix blueprint
    - If parser layer is fine but extraction is dominated by F-03/F-04 on new formats → confirms schema is the bottleneck, γ gets prioritized
    - If parser layer is fine and extraction works well → B3's format coverage goal is met, move to other B3 items (commit path, record-replay, or more samples)
```

---

## 2. Candidate inventory (COMPLETE — Step 2 applied)

### 2.0 Sourcing decision

Reviewer chose **Option I — Python-generate all 3 samples from existing MD** (2026-04-11).

Rationale:
- Path A (existing repo binaries): NOT AVAILABLE (zero PDFs/DOCXs in repo)
- Path B (system-side pandoc/libreoffice/wkhtmltopdf): NOT AVAILABLE (zero system conversion tools)
- Path B′ (Python-side reportlab + python-docx + pymupdf + PIL): **AVAILABLE** — all libs verified present
- Path C (user-provide): not needed when Python-generate works

**Benefit of Option I**: using `medium_01_security.md` as the source for both the born-digital PDF and the scanned PDF gives a **3-way comparison on identical content** (MD baseline + PDF parser path + scanned failure path).

### 2.1 Finalized candidate inventory

Reviewer approved mapping (2026-04-11):

- PDF: `medium_01_security.md` → `medium_04_pdf_security.pdf`
- DOCX: **`medium_03_audit_report.md`** → `medium_05_docx_audit.docx` (changed from `medium_02_blueprint_backref.md` to extend content surface — audit/reference content stresses DOCX parsing differently)
- Scanned PDF: `medium_01_security.md` → `short_04_scanned_security.pdf`

### 2.2 Sample 1 — `medium_04_pdf_security` (born-digital PDF)

| field | value |
|---|---|
| source MD | `samples/medium/medium_01_security.md` (1,986 bytes) |
| generator | `format_coverage_generators/generate_pdf_born_digital.py` |
| output path | `samples/medium/medium_04_pdf_security.pdf` |
| output size | **5,444 bytes** (2.7× MD source) |
| pages | 2 |
| generation approach | `reportlab.platypus.SimpleDocTemplate` with `UnicodeCIDFont('STSong-Light')` for CJK + latin; H1/H2/H3/body/bullet styles |
| length_class | `medium` |
| domain | `regulation` |
| expected_result | `success` |
| expected_min_valid_specs | 0 |
| B3 parser path | `pymupdf.get_text("blocks")` via `src/factpy_kernel/agent/documents/parsers/pdf.py` |
| sanity check (pymupdf) | **1,913 chars** extracted across 2 pages — real text layer confirmed |
| predicted staging | success with ~20-40 segments from block-level extraction |
| predicted F-03 behavior | should produce similar content to `medium_01_security.md`'s MD run (1 valid draft, doc_id hash WRONG_ENTITY) — if parser path is clean, cross-format results should match |

### 2.3 Sample 2 — `medium_05_docx_audit` (DOCX)

| field | value |
|---|---|
| source MD | `samples/medium/medium_03_audit_report.md` (10,581 bytes) |
| generator | `format_coverage_generators/generate_docx.py` |
| output path | `samples/medium/medium_05_docx_audit.docx` |
| output size | **42,303 bytes** (4× MD source, DOCX XML overhead) |
| paragraphs | 168 non-empty |
| generation approach | `python-docx Document.add_heading()` for `#`/`##`/`###`/`####`; `style='List Bullet'` for `- `/`* `; `style='List Number'` for `\d+.`; tables rendered as plain pipe-separated paragraphs; fenced code blocks as `No Spacing` + Courier |
| length_class | `medium` |
| domain | `audit` |
| expected_result | `success` |
| expected_min_valid_specs | 0 |
| B3 parser path | `python-docx Document(BytesIO(content))` via `src/factpy_kernel/agent/documents/parsers/docx.py` |
| sanity check (python-docx) | **168 paragraphs**, all non-empty, first=`'FactPy Kernel 产品落地就绪度审计报告'`, last=`'**市场判定**: 三范式推理编排...'` |
| predicted staging | success with ~168 segments (one per paragraph — much higher density than the MD version which had 81 segments via `PlainTextParser`) |
| predicted F-03 behavior | may produce very different extraction numbers than `medium_03_audit_report.md`'s MD run because segment count is 2× higher — this is a secondary observation, not the primary goal |

### 2.4 Sample 3 — `short_04_scanned_security` (image-only PDF, expected failure)

| field | value |
|---|---|
| source MD | `samples/medium/medium_01_security.md` (1,986 bytes) — same as sample 1 |
| generator | `format_coverage_generators/generate_pdf_scanned.py` |
| output path | `samples/short/short_04_scanned_security.pdf` |
| output size | **4,804,057 bytes (4.8 MB)** (large due to embedded PNG pages) |
| pages | 2 |
| generation approach | PIL `Image.new()` + `ImageDraw.text()` using PingFang/Helvetica system TTF → PNG → `pymupdf.insert_image()` into blank PDF page; **no text layer at all** |
| length_class | `short` |
| domain | `regulation` |
| expected_result | **`staging_error`** (this is the failure case) |
| expected_min_valid_specs | 0 |
| B3 parser path | `pymupdf.get_text("blocks")` returns empty → `ParseError("empty_document", "document has no extractable text")` |
| sanity check (pymupdf) | **0 chars** extracted on both pages — confirmed no text layer |
| sanity check (pymupdf4llm) | 2,081 chars extracted via Tesseract OCR — but B3 staging does NOT use pymupdf4llm, so this is informational only |
| predicted staging | **failure** with `error_kind='empty_document'` |
| predicted extraction | not reached (staging error short-circuits before batch_extractor) |

### 2.5 Important finding from code inspection: B3 PDF parser is basic

During Step 2 sanity checking, I initially saw `pymupdf4llm.to_markdown()` return 2,081 chars from the scanned PDF (via Tesseract OCR), which would have invalidated the failure-case design. Inspection of `src/factpy_kernel/agent/documents/parsers/pdf.py` revealed:

```python
# line 74 — B3 PDF parser
blocks = page.get_text("blocks")
```

The B3 PDF parser calls `pymupdf.get_text("blocks")` directly, NOT `pymupdf4llm.to_markdown()`. The `pymupdf4llm` import at line 33 is annotated `# noqa: F401` — it's an availability gate, not an active dependency. **The B3 PDF parser path does not have OCR fallback**.

This has implications beyond this plan:

- Scanned PDFs will always fail at staging with `empty_document`
- Complex PDFs with multi-column layouts or embedded images may have degraded extraction quality compared to `pymupdf4llm`'s richer extraction
- If B3 ever wants to support scanned/image-heavy PDFs (OCR fallback), it requires a parser-layer change

This is NOT in scope for the current format coverage plan — just a factual observation worth recording. If scanned-PDF OCR ever becomes a priority, a separate 4C1 blueprint should be opened to switch from `get_text("blocks")` to `pymupdf4llm.to_markdown(...)`.

### 2.6 Generators directory

All 3 one-shot generators live at `format_coverage_generators/` (sibling of `samples/`, NOT gitignored):

- `format_coverage_generators/generate_pdf_born_digital.py`
- `format_coverage_generators/generate_docx.py`
- `format_coverage_generators/generate_pdf_scanned.py`

Each script is idempotent (overwrites output if exists) and can be re-run from repo root. They are provenance, not reusable tooling — if format coverage ever needs more samples of the same shape, new generators should be written per-sample rather than parameterizing these.

---

## 3. Per-sample run results (COMPLETE)

Execution order per reviewer's Step 3 instruction (cheapest/most-certain first):

1. `short_04_scanned_security` (expected failure — smoke test)
2. `medium_04_pdf_security` (born-digital PDF)
3. `medium_05_docx_audit` (DOCX, longest)

Both gate conditions held throughout:
- Gate 1 (after short_04): must produce `staging_error` with `empty_document` — **PASSED**
- Gate 2 (after medium_04): must produce staging success with nonzero segments — **PASSED**

### 3.1 `short_04_scanned_security` (expected failure)

| field | value |
|---|---|
| canonical run_record | `run_records/b3_20260411T134150Z_short_04_scanned_security.json` |
| outcome.actual_result | **`staging_error`** |
| outcome.matches_expectation | **true** (matches manifest's `expected_result: staging_error`) |
| staging.success | **false** |
| parser_name | `None` (staging failed before any parser handed a valid result) |
| parser_version | `None` |
| **error_kind** | **`empty_document`** |
| error_message | `document has no extractable text` |
| total_segments | 0 |
| total_chars | 0 |
| pattern_type_distribution | `{if_then:0, entity_relation:0, definition:0, narrative:0}` |
| extraction_reachable | **no** (staging short-circuited) |
| proposals / valid / rejected | n/a |
| run_duration_ms | **610 ms** (no LLM call, ~$0.00 cost) |
| parser-path judgment | **PARSER_OK** — failure path validated correctly. See §4. |

**Finding**: the B3 PDF parser (`pymupdf.get_text("blocks")` at `parsers/pdf.py:74`) correctly returns zero blocks on an image-only PDF. The `parsers/pdf.py:68-69` empty-segment check then raises `ParseError("empty_document", "document has no extractable text")`, which the staging layer converts to a `StagingError` with `error_kind='empty_document'`, which the runner records as `actual_result='staging_error'`. The runner correctly matches this against the manifest's `expected_result: staging_error` and sets `matches_expectation: true`. **Full failure path validated end-to-end**.

### 3.2 `medium_04_pdf_security` (born-digital PDF)

| field | value |
|---|---|
| canonical run_record | `run_records/b3_20260411T134217Z_medium_04_pdf_security.json` |
| outcome.actual_result | `success` |
| outcome.matches_expectation | true |
| staging.success | true |
| **parser_name** | **`pymupdf`** |
| parser_version | `0.1.0` |
| doc_id | `50bfcceb994296da` |
| **total_segments** | **23** |
| total_chars | 1,926 |
| high_clarity_count | 0 |
| avg_structural_clarity | 0.2130 |
| **pattern_type_distribution** | `{if_then:0, entity_relation:1, definition:0, narrative:22}` |
| error_kind | None |
| proposals | 12 |
| valid | 6 |
| rejected | 6 |
| segment hit rate | **52.2%** (12 / 23) |
| rejection shapes (sampled) | 2× Pattern A + **1× Pattern B crossover** (`document:mentions` `got 3, expected 1`) — remaining 3 rejections unsampled |
| bundle draft_count | 6 |
| batch_duration_ms | 38,761 (~39 s) |
| parser-path judgment | **PARSER_OK** — see §4 |

**Cross-format comparison against `medium_01_security.md` (MD baseline)**:

| | MD (iter 5 canonical) | PDF (Step 3 canonical) | delta |
|---|---:|---:|---:|
| parser | `txt` (PlainTextParser) | `pymupdf` | — |
| total_segments | 22 | 23 | +1 |
| total_chars | 1,984 | 1,926 | −58 (−2.9%) |
| avg_structural_clarity | 0.2136 | 0.2130 | −0.0006 (flat) |
| pattern_type_distribution | 21 narrative + 1 entity_relation | 22 narrative + 1 entity_relation | +1 narrative |
| proposals | 1 | 12 | **+11 (12×)** |
| valid | 1 | 6 | **+5 (6×)** |
| segment hit rate | 4.5% | 52.2% | **+47.7pp** |

**Parser paths produce near-identical segmentation (±1 segment, −58 chars)** — both paths segment the content the same way structurally. But extraction output differs by a factor of 12 on proposal count. This delta is far larger than the staging delta would predict. See Finding 1 in §4.3 for the variance interpretation — **do not read this as a parser-path finding**; it is an LLM variance signal that happens to be scoped to the parser axis.

### 3.3 `medium_05_docx_audit` (DOCX)

| field | value |
|---|---|
| canonical run_record | `run_records/b3_20260411T134637Z_medium_05_docx_audit.json` |
| outcome.actual_result | `success` |
| outcome.matches_expectation | true |
| staging.success | true |
| **parser_name** | **`python_docx`** |
| parser_version | `0.1.0` |
| doc_id | `637ae6c94ed52ded` |
| **total_segments** | **168** |
| total_chars | 6,845 |
| high_clarity_count | 1 |
| avg_structural_clarity | 0.2274 |
| **pattern_type_distribution** | `{if_then:1, entity_relation:13, definition:0, narrative:154}` |
| error_kind | None |
| proposals | 26 |
| valid | 18 |
| rejected | 8 |
| segment hit rate | 15.5% (26 / 168) |
| rejection shapes (sampled) | 1× Pattern A + **2× Pattern B crossover** (`document:mentions` `got 3, expected 1`) — remaining 5 rejections unsampled |
| **bundle draft_count** | **17** (first nonzero `merge_count` observed in B3: 18 valid − 1 merged = 17 drafts) |
| batch_duration_ms | 183,493 (~3 min) |
| parser-path judgment | **PARSER_OK** — see §4 |

**Cross-format comparison against `medium_03_audit_report.md` (MD baseline)**:

| | MD (β.1 canonical) | DOCX (Step 3 canonical) | delta |
|---|---:|---:|---:|
| parser | `txt` (PlainTextParser) | `python_docx` | — |
| total_segments | 81 | **168** | +87 (**2.07×**) |
| total_chars | 10,581 (source bytes) | 6,845 | parser-derived, not comparable |
| proposals | 29 | 26 | −3 |
| valid | 16 | 18 | +2 |
| rejected | 13 | 8 | −5 |
| bundle draft_count | 16 | **17** (1 merged) | — |

**The DOCX parser produces ~2× the segment count for the same source content** because `python-docx` emits one segment per paragraph while `PlainTextParser` merges adjacent lines into blocks. Yet proposal counts are comparable (26 vs 29), which means the LLM is producing **fewer proposals per segment** on the DOCX path. The segment hit rate drops from 35.8% (MD) to 15.5% (DOCX). This is expected — more granular segments mean more segments that contain no extractable fact.

**First nonzero merge signal**: the resolver merged 1 spec during deduplication (18 valid → 17 bundle drafts). This is the first merge we've seen in iter 4, iter 5, β.1, or format coverage. Likely driven by the DOCX path's higher segment count producing duplicate mentions of the same fact across paragraph boundaries. Not verified at packet level (reviewer chose Option Y — no review).

### 3.4 Aggregate Step 3 metrics

| | short_04 | medium_04 | medium_05 | **Step 3 total** |
|---|---:|---:|---:|---:|
| segments | 0 (fail) | 23 | 168 | **191** |
| proposals | 0 | 12 | 26 | **38** |
| valid | 0 | 6 | 18 | **24** |
| rejected | 0 | 6 | 8 | **14** |
| bundle drafts | 0 | 6 | 17 | **23** |
| duration_ms | 610 | 38,761 | 183,493 | **222,864 (~3.7 min)** |

LLM cost for Step 3 (estimated): **~$0.05** total. Within budget.

---

## 4. Staging quality axis classification (COMPLETE)

### 4.1 Axis definitions (reference)

| axis | what it means | what to do next |
|---|---|---|
| **PARSER_OK** | segments are comparable to MD-parsed content; staging clarity and pattern distribution look reasonable | extraction can proceed; any failures are prompt/schema-level |
| **PARSER_DEGRADED** | parser succeeded but segments have visible quality issues (page break artifacts, extracted tables as flat text, formatting noise) | useful for downstream inspection but may need parser tuning before scaling up; blueprint-worthy if systematic |
| **PARSER_FAIL** | parser crashed, produced no segments, or produced unreadable segments | 4C1 fix blueprint needed; blocks further B3 work on this format |

### 4.2 Per-sample classification

| sample | parser | axis | reasoning |
|---|---|:---:|---|
| `short_04_scanned_security` | pymupdf (failure path) | **PARSER_OK** | Correctly trips `ParseError("empty_document")` on image-only PDF. The failure path is a validated behavior, not a parser bug. Staging short-circuits cleanly, runner records `staging_error`, manifest expectation matches. |
| `medium_04_pdf_security` | `pymupdf get_text("blocks")` | **PARSER_OK** | 23 segments vs MD baseline's 22 (+1). avg_structural_clarity matches MD to 4 decimal places. pattern_type_distribution essentially identical. No extraction errors. Segments reached extraction on 100% of segment count (23/23 success_segment_count). |
| `medium_05_docx_audit` | `python-docx` block iteration | **PARSER_OK** | 168 segments vs MD baseline's 81 (2.07× — expected given python-docx's per-paragraph granularity). No empty paragraphs. All 168 segments reached extraction successfully. pattern_type_distribution sensibly reflects mixed narrative + structured content (154 narrative + 13 entity_relation + 1 if_then). |

**All 3 samples: PARSER_OK.** Zero PARSER_DEGRADED. Zero PARSER_FAIL.

### 4.3 Cross-format observations (informational, not part of parser-path verdict)

These observations are **informational** — they are not the parser-path validation signal, which is answered above. They describe secondary behaviors that surfaced during the runs and are worth noting for future B3 work.

#### 4.3.1 LLM extraction variance dominates cross-format comparison

The `medium_01_security` MD vs `medium_04` PDF comparison showed a **12× difference in proposal count** (1 vs 12) on nearly-identical staging output (22 vs 23 segments, 1984 vs 1926 chars). This is much larger than any segmentation delta could explain.

**Interpretation**: This is not a parser-path finding. It is an LLM variance signal, consistent with OBS-01 (LLM extraction counts have visible variance at temperature=0.0, envelope ±20 valid on similar-sized samples). The plan's original prediction of "cross-format comparison on identical content" is therefore **invalidated as a parser-quality probe** — OBS-01 variance dominates the parser-path signal on small samples.

**Implication**: if future B3 work wants to compare parser quality across formats, it should use either (a) much larger samples where variance averages out, (b) n≥3 runs per format per sample and compare means, or (c) parser-layer unit tests that bypass the LLM entirely. Single-run same-content comparison is not meaningful at iter 5's current variance envelope.

This observation is NOT being filed as OBS-03. It is a property of the measurement methodology, already captured under OBS-01. The format coverage plan's original assumption was wrong but the axis-classification verdict (PARSER_OK on all 3) does not depend on that assumption.

#### 4.3.2 First nonzero `merge_count` in B3 history

`medium_05_docx_audit` produced `merge_count=1` (18 valid → 17 bundle drafts). This is the first nonzero merge observed across iter 4, iter 5, β.1, and format coverage — 10 prior canonical runs all had `merge_count=0`.

Likely explanation: the DOCX path's higher segment count (168 vs MD's 81 on the same content) increases the chance that the same fact is mentioned across multiple paragraph boundaries, and the resolver merges the duplicates. This is the EntityResolver's intended behavior.

**Implication**: if future B3 work wants to test merge semantics specifically, `medium_05_docx_audit` is the first sample that actively exercises the merge path. Previously the merge path was covered by unit tests but not by any canonical B3 sample.

This observation is NOT being filed as OBS-03 either — it's a positive diagnostic signal (resolver working as designed), not a failure mode. Just noted.

#### 4.3.3 Pattern B predicate crossover has now appeared on all 3 non-MD-native samples

Step 3 rejection samples show Pattern B crossover (`document:mentions` with `got 3, expected 1`) on **both** `medium_04_pdf_security` and `medium_05_docx_audit`, in addition to the earlier observation on `short_03_architecture` (β.1). Three distinct samples, two different parser paths, same failure shape.

This upgrades OBS-02's evidence from thin to recurring. **OBS-02 has been upgraded from P3 to P2** in `cross_run_observations.md` (not a blueprint trigger; still observation-only; severity reflects that it now has credible cross-sample evidence rather than a single-instance pattern).

### 4.4 Parser-path verdict summary

| axis | sample count | samples |
|---|---:|---|
| PARSER_OK | **3 / 3** | short_04, medium_04, medium_05 |
| PARSER_DEGRADED | 0 / 3 | — |
| PARSER_FAIL | 0 / 3 | — |

**Format coverage goal achieved.** All three parser paths are validated:
1. `pymupdf get_text("blocks")` handles born-digital PDFs cleanly
2. `pymupdf get_text("blocks")` correctly fails on image-only PDFs via `empty_document`
3. `python-docx` handles DOCX files cleanly with higher segment density than `PlainTextParser`

No 4C1 parser layer fix is needed based on this evidence. The B3 PDF/DOCX parser paths are production-viable for the content types tested.

---

## 5. Decision (FINAL)

### 5.1 Parser-path verdicts

- [x] **PDF parser-path judgment**: **PARSER_OK**. `pymupdf.get_text("blocks")` extracts content cleanly from born-digital PDFs. Produces segment counts and clarity scores comparable to the MD baseline.
- [x] **DOCX parser-path judgment**: **PARSER_OK**. `python-docx` block iteration extracts content cleanly. Produces ~2× the segment count of `PlainTextParser` on identical content due to per-paragraph granularity — this is expected, not a degradation.
- [x] **Scanned PDF failure-path judgment**: **PARSER_OK**. `ParseError("empty_document")` correctly trips on image-only PDFs. Staging short-circuits, runner correctly records `staging_error`, manifest expectation matches.

### 5.2 Next B3 priority selection

Reviewer chose **Option Y** (seal format coverage line, no packet generation, no human review) on 2026-04-11.

**Reasoning** (reviewer quote):
> "这条线的目标是 format coverage / parser-path validation，不是再开一轮 semantic review。3 个格式样本已经把结论跑清了... 再生成 packet 会把这条线重新拖回 semantic-quality / prompt-variance 问题，偏离当前目标。"

Key justifications:

1. **The stated goal is met**: parser-path validation is answered. All 3 parsers work as designed.
2. **Packet review would re-open semantic-quality questions**: those are the exact questions β.1 closed with verdict δ. Reopening them here would violate the "stop prompt tuning, move on" commitment from β.1 §5.6.
3. **`medium_04` same-content cross-format signal is dominated by LLM variance** (Finding 4.3.1): continuing to human review on that sample would not yield parser-path evidence, only more variance noise.
4. **`medium_05` `merge_count=1` is an incidental positive finding**, not a format-coverage gating question. It doesn't require review-level validation to be worth recording.

### 5.3 Follow-up artifacts created / modified

- [x] `samples_manifest.yaml` — bumped `smoke-2 → smoke-3` with 3 new entries (medium_04, medium_05, short_04)
- [x] `samples/medium/medium_04_pdf_security.pdf` — born-digital PDF (Python-generated, 5.4 KB)
- [x] `samples/medium/medium_05_docx_audit.docx` — DOCX (Python-generated, 42 KB, 168 paragraphs)
- [x] `samples/short/short_04_scanned_security.pdf` — image-only PDF (Python-generated, 4.8 MB)
- [x] `format_coverage_generators/generate_pdf_born_digital.py` — one-shot PDF generator
- [x] `format_coverage_generators/generate_docx.py` — one-shot DOCX generator
- [x] `format_coverage_generators/generate_pdf_scanned.py` — one-shot image-only PDF generator
- [x] `run_records/b3_20260411T134150Z_short_04_scanned_security.json` — staging_error record
- [x] `run_records/b3_20260411T134217Z_medium_04_pdf_security.json` — canonical extraction record
- [x] `run_records/b3_20260411T134637Z_medium_05_docx_audit.json` — canonical extraction record
- [x] This plan file (`format_coverage_plan_2026-04-11.md`) — populated through §5
- [x] `cross_run_observations.md` — **OBS-02 upgraded from P3 to P2** based on new evidence across 3 samples

### 5.4 Artifacts explicitly NOT created

- **No review packets** — reviewer chose Option Y, skipping packet generation and human review
- **No iter 6 blueprint** — β.1 verdict δ committed to no further prompt iteration on iter 5 state
- **No schema expansion blueprint** (γ) — same reason
- **No 4C1 parser fix blueprint** — all 3 parsers passed; no parser layer fix needed based on this evidence
- **No OCR fallback blueprint** — the observation that B3 PDF parser lacks OCR fallback (noted in §2.5) is informational; there is no current evidence that OCR support is needed

### 5.5 Reviewer's forward-looking note

Reviewer (quote): "如果 format coverage 收口后要选下一条，我会优先看 **runner commit path**，不是继续 prompt tuning。"

**Runner commit path** is flagged as the likely next B3 priority after format coverage closes. Current state: `run_load_test.py` has a stubbed commit path (see runner docstring §Commit path (non-dry-run)). It builds a real bundle preview but does not open a runtime session or commit to a ledger. A future B3 phase would wire `AgentSession + DraftManager + BundleManager + WriteTools` through a runtime adapter.

**This plan does NOT open the commit-path work.** That's a separate blueprint-worthy task if the reviewer decides to pursue it.

### 5.6 Plan sealed as FINAL

This plan is now historical evidence of the B3 format coverage phase. §3 and §4 are the authoritative record of what was measured and classified. §5 is the authoritative record of the reviewer's decisions.

**What cannot be changed without reopening format coverage**:
- The per-sample run_record metrics in §3 (they correspond to actual canonical runs on disk)
- The parser-path axis classifications in §4.2
- The verdicts in §5.1
- The reviewer's decision in §5.2

**What can still be linked from here going forward**:
- Future B3 phase plans (e.g., `commit_path_plan_2026-04-NN.md`) referencing format coverage as a preceding phase
- A future 4C1 fix blueprint (if ever needed) citing §2.5 or §4.3 findings
- An OBS-03 entry in `cross_run_observations.md` if new parser-path findings surface

### 5.7 What format coverage did NOT test

Honest limitations for future work awareness:

1. **Real-world PDF complexity**: all generated PDFs are reportlab-synthetic. Multi-column layouts, embedded tables, scanned-mixed-with-text PDFs, PDF/A-3, and tagged PDFs are not exercised. A reportlab PDF is cleaner than most real-world PDFs that a production B3 pipeline would encounter.
2. **Real-world DOCX complexity**: similarly, the generated DOCX is python-docx-synthetic. Embedded images, complex tables with merged cells, tracked changes, comments, and legacy .doc files are not exercised.
3. **OCR path**: intentionally not tested (B3 PDF parser has no OCR fallback — §2.5 noted this as a code-inspection finding).
4. **Multi-page boundary artifacts**: only 2-page samples were used. Real PDFs with dozens or hundreds of pages may expose different segmentation artifacts.
5. **Non-Latin-only DOCX content**: the DOCX sample has mixed Chinese + English, validating CJK handling in python-docx. But it does not test non-CJK non-Latin scripts (Arabic, Cyrillic, Hindi).
6. **Sample volume at scale**: only 3 new samples were added. Full B3 README plan called for 3+2+1 = 6 non-MD samples plus MD samples to reach 9 total. Format coverage added 3 of those.

These are all **parking lot items** for potential future work. None of them are open questions in this plan.

---

## 6. What is frozen during this plan

- **Iter 5 `SYSTEM_PROMPT_TEMPLATE`**: current state of `prompts.py`, unchanged. Every canonical run uses the iter 5 prompt.
- **`test_schema_ir.json`**: unchanged. This plan does not touch schema.
- **`run_load_test.py`** and **`generate_review_packet.py`**: unchanged. Same scripts as used in β.1.
- **β.1 artifacts**: fully frozen (`sample_expansion_plan_2026-04-11.md`, `review_summary_beta1_2026-04-11.md`, 3 β.1 packets, 3 β.1 run_records).
- **iter 4 and iter 5 archived blueprints**: frozen.
- **cross_run_observations.md**: frozen unless a new cross-run finding specific to format coverage is discovered.

The only files this plan modifies are:

1. `samples_manifest.yaml` (version bump `smoke-2` → `smoke-3`, + 3 new entries)
2. `samples/<class>/<new_pdf>.pdf` (new binary file)
3. `samples/<class>/<new_docx>.docx` (new binary file)
4. `samples/short/<new_scanned_pdf>.pdf` (new binary file)
5. `format_coverage_plan_2026-04-11.md` (this file)

After Step 3 begins, additionally:

6. `run_records/b3_*_<new_sample_id>.json` (new canonical records)
7. Optionally: `review/iter5/review_pass_2026-04-11_<new_sample_id>.md` if packets are generated

**Note**: samples/ is gitignored per the README so binary sample files will not enter the git index.

---

## 7. Open questions (CLOSED)

All open questions were answered during plan execution. Captured here for the historical record.

- [x] **Sourcing path preference**: **Option I** (Python-generate all 3 from existing MD). Path A (existing binaries) unavailable; Path B (pandoc/libreoffice) unavailable; Path B′ (Python libs) available and chosen.
- [x] **Scanned PDF synthesis strategy**: Python synthesis chosen (PIL render → pymupdf image embed). No external/reviewer-provided file needed.
- [x] **Length_class buckets**: `medium` for both PDF and DOCX; `short` for scanned PDF. Committed in manifest smoke-3.
- [x] **Is format coverage expected to produce valid drafts**: yes for `medium_04`/`medium_05`, **no** for `short_04` (expected staging failure). All 3 used `expected_min_valid_specs: 0` per reviewer's standing instruction.
- [x] **Should the scanned PDF's `expected_result` be `staging_error`**: yes. Committed in manifest. Runner correctly matched `actual_result=staging_error` against `expected_result=staging_error` on the canonical run.
