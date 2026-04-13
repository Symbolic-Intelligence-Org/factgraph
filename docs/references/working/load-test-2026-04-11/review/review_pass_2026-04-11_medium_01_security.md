# Review Pass 2026-04-11 — medium_01_security

## Header

- sample_id: `medium_01_security`
- sample_path: `/Users/zhenzhili/hnsm-backend/docs/references/working/load-test-2026-04-11/samples/medium/medium_01_security.md`
- doc_id: `8e729d68d5deab3a`
- total_segments: 22
- total_proposal_count (regen): 14
- total_valid_count (regen): 9
- total_rejection_count (regen): 5
- generated_at: 2026-04-10T20:57:19.328743+00:00

### Archived iter 4 reference

- archived_run_record: `/Users/zhenzhili/hnsm-backend/docs/references/working/load-test-2026-04-11/run_records/b3_20260410T194444Z_medium_01_security.json`
- archived_bundle_id: `bundle_5cd1b343998c` (in-memory only, not reproducible)
- archived_valid_count: 14 — **drift from archived iter 4: -5**

### Variance caveat (added 2026-04-11, read before reviewing)

**This packet is ONE sample from the iter 4 distribution, not the definitive iter 4 bundle.**

After this packet was generated, a third canonical run was taken on the same pair of samples for a stability check. Three runs on `medium_01_security` produced `14 / 9 / 7` valid drafts, and three runs on `long_01_kernel_p0` produced `57 / 77 / 60` valid drafts — all with identical prompt, schema, manifest, and `temperature=0.0`. See:

- [iteration 4 report §8 Addendum](../report/load_test_report_2026-04-11_iter4.md#8-addendum--2026-04-11-variance-correction)
- [cross-run observations OBS-01](../cross_run_observations.md#obs-01-p2-llm-extraction-counts-have-visible-variance-at-temperature00)

**Implications for this review pass**:

1. The 9 drafts in this packet are a valid **sample** of what the current prompt produces on `medium_01_security`. They are NOT the same 9 drafts the archived iter 4 bundle would have contained.
2. The review's purpose is **semantic quality assessment** — "of these 9 drafts, how many are correct?" — not count reconciliation against the archived run_record.
3. **Do NOT backfill these review results into the archived iter 4 run_record** (`b3_20260410T194444Z_medium_01_security.json`). That record refers to a different in-memory bundle that no longer exists. If any backfill is appropriate, it should go into a new summary artifact, not the archived JSON.
4. Rejection shape is 100% stable across all three runs: 100% `schema_field_type_mismatch`, 100% on `document:mentions`, 100% `got 2, expected 1` Pattern A subject leakage. Count variance is independent of error-mode analysis.

The archived iter 4 bundle IDs died with the process that created them (`BundleManager` is in-memory only). This packet references newly regenerated specs.

## Review instructions

For each draft below, fill in the `REVIEW` block at the bottom:

- `approve`: one of `yes` | `no` | `partial`
  - `yes` — the extracted fact is supported by `raw_text` and semantically correct
  - `no` — the fact is wrong, hallucinated, or unsupported by `raw_text`
  - `partial` — the fact is partially correct but needs rewording, scoping, or a different predicate
- `reason_code`: one of
  - `CORRECT` — no issue (use with `approve: yes`)
  - `HALLUCINATED` — fact is not present in raw_text at all
  - `OVERGENERAL` — fact is in raw_text but the object is too broad / too vague
  - `WRONG_ENTITY` — subject entity is mis-identified
  - `WRONG_PREDICATE` — relation should use a different pred_id
  - `WRONG_ARG` — the object/field_values value is factually wrong
  - `DUPLICATE` — same fact as another approved draft in this packet
  - `AMBIGUOUS` — raw_text is genuinely ambiguous; cannot judge
  - `OTHER` — fill in notes
- `notes`: free-text, optional

Summary metrics will be backfilled into the run_record `review` block after the pass is complete. This packet is the source of truth for per-draft decisions.

---

## Drafts

### Draft 001

```yaml
draft_index: 0
entity_type: "Document"
entity_identity:
  title: "current repository-level security hygiene rules for local development and operator workflows"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "repository-level security hygiene rules for local development and operator workflows"
confidence: 0.9
note: null

provenance:
  source_document_id: "8e729d68d5deab3a"
  segment_id: "8e729d68_0002"
  char_offset_start: 28
  char_offset_end: 147
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    This document records the current repository-level security hygiene rules for local development and operator workflows.
```

**Summary**: `Document(title=current repository-level security hygie…) -- document:mentions --> string=repository-level security hygiene rules…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The text supports that this document is about repository-level security hygiene rules, but the extracted Document.title is inferred from body prose rather than a stable document identity/title."
```

---

### Draft 002

```yaml
draft_index: 1
entity_type: "Document"
entity_identity:
  title: "8e729d68d5deab3a"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "local secret handling via .env"
confidence: 0.9
note: null

provenance:
  source_document_id: "8e729d68d5deab3a"
  segment_id: "8e729d68_0004"
  char_offset_start: 171
  char_offset_end: 273
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - local secret handling via `.env`
    - kernel service API key authentication
    - key rotation expectations
```

**Summary**: `Document(title=8e729d68d5deab3a) -- document:mentions --> string=local secret handling via .env`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The bullet clearly supports this mention, but the subject entity is keyed by the internal doc_id instead of a real document title/identity."
```

---

### Draft 003

```yaml
draft_index: 2
entity_type: "Document"
entity_identity:
  title: "8e729d68d5deab3a"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "kernel service API key authentication"
confidence: 0.9
note: null

provenance:
  source_document_id: "8e729d68d5deab3a"
  segment_id: "8e729d68_0004"
  char_offset_start: 171
  char_offset_end: 273
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - local secret handling via `.env`
    - kernel service API key authentication
    - key rotation expectations
```

**Summary**: `Document(title=8e729d68d5deab3a) -- document:mentions --> string=kernel service API key authentication`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Supported mention, but the Document identity is again the opaque doc_id rather than a stable document title."
```

---

### Draft 004

```yaml
draft_index: 3
entity_type: "Document"
entity_identity:
  title: "8e729d68d5deab3a"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "key rotation expectations"
confidence: 0.9
note: null

provenance:
  source_document_id: "8e729d68d5deab3a"
  segment_id: "8e729d68_0004"
  char_offset_start: 171
  char_offset_end: 273
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - local secret handling via `.env`
    - kernel service API key authentication
    - key rotation expectations
```

**Summary**: `Document(title=8e729d68d5deab3a) -- document:mentions --> string=key rotation expectations`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The content is present in the source bullet list, but the extracted subject entity is mis-identified as the doc_id."
```

---

### Draft 005

```yaml
draft_index: 4
entity_type: "Document"
entity_identity:
  title: "8e729d68d5deab3a"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "Kernel service v1 routes are protected by `X-FactPy-API-Key` unless authentication is explicitly disabled for local development."
confidence: 0.9
note: null

provenance:
  source_document_id: "8e729d68d5deab3a"
  segment_id: "8e729d68_0012"
  char_offset_start: 1053
  char_offset_end: 1181
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    Kernel service v1 routes are protected by `X-FactPy-API-Key` unless authentication is explicitly disabled for local development.
```

**Summary**: `Document(title=8e729d68d5deab3a) -- document:mentions --> string=Kernel service v1 routes are protected …`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The sentence is supported verbatim, but the subject should be the security document itself, not Document(title=<doc_id>)."
```

---

### Draft 006

```yaml
draft_index: 5
entity_type: "Module"
entity_identity:
  module_name: "FACTPY_KERNEL_API_KEYS"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "Comma-separated allow-list of valid API keys."
confidence: 0.9
note: null

provenance:
  source_document_id: "8e729d68d5deab3a"
  segment_id: "8e729d68_0014"
  char_offset_start: 1207
  char_offset_end: 1391
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `FACTPY_KERNEL_API_KEYS`
      - Comma-separated allow-list of valid API keys.
    - `FACTPY_KERNEL_AUTH_DISABLED`
      - Local-development escape hatch. Must be unset or `false` in production.
```

**Summary**: `Module(module_name=FACTPY_KERNEL_API_KEYS) -- module:description --> string=Comma-separated allow-list of valid API…`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Correct extraction: env var name is the module identity and the description text matches the source."
```

---

### Draft 007

```yaml
draft_index: 6
entity_type: "Module"
entity_identity:
  module_name: "FACTPY_KERNEL_AUTH_DISABLED"
pred_id: "module:description"
field_values:
  - tag: "string"
    value: "Local-development escape hatch. Must be unset or false in production."
confidence: 0.9
note: null

provenance:
  source_document_id: "8e729d68d5deab3a"
  segment_id: "8e729d68_0014"
  char_offset_start: 1207
  char_offset_end: 1391
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `FACTPY_KERNEL_API_KEYS`
      - Comma-separated allow-list of valid API keys.
    - `FACTPY_KERNEL_AUTH_DISABLED`
      - Local-development escape hatch. Must be unset or `false` in production.
```

**Summary**: `Module(module_name=FACTPY_KERNEL_AUTH_DISABLED) -- module:description --> string=Local-development escape hatch. Must be…`

```yaml
REVIEW:
  approve: "yes"         # yes | no | partial
  reason_code: "CORRECT"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "Correct extraction: the variable name and its description are both directly supported by the bullet list."
```

---

### Draft 008

```yaml
draft_index: 7
entity_type: "Document"
entity_identity:
  title: "FACTPY_KERNEL_API_KEY"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "Single key used by HTTP callers such as HttpRuntimeAPI"
confidence: 0.9
note: null

provenance:
  source_document_id: "8e729d68d5deab3a"
  segment_id: "8e729d68_0016"
  char_offset_start: 1427
  char_offset_end: 1514
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    - `FACTPY_KERNEL_API_KEY`
      - Single key used by HTTP callers such as `HttpRuntimeAPI`.
```

**Summary**: `Document(title=FACTPY_KERNEL_API_KEY) -- document:mentions --> string=Single key used by HTTP callers such as…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_PREDICATE"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The source supports a description of FACTPY_KERNEL_API_KEY, but this should be Module(module_name=FACTPY_KERNEL_API_KEY) with module:description, not Document(... ) with document:mentions."
```

---

### Draft 009

```yaml
draft_index: 8
entity_type: "Document"
entity_identity:
  title: "8e729d68d5deab3a"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "scripts/check_no_secrets_in_env_example.sh"
confidence: 0.9
note: null

provenance:
  source_document_id: "8e729d68d5deab3a"
  segment_id: "8e729d68_0020"
  char_offset_start: 1816
  char_offset_end: 1885
  page_number: null
  extraction_method: "llm_refined"
  merged_from_count: 0
  raw_text: |
    The repository includes `scripts/check_no_secrets_in_env_example.sh`.
```

**Summary**: `Document(title=8e729d68d5deab3a) -- document:mentions --> string=scripts/check_no_secrets_in_env_example…`

```yaml
REVIEW:
  approve: "partial"         # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The document does mention this script, but the extracted subject entity is keyed by doc_id rather than a proper document title/identity."
```

---
