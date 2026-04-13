# Review Pass 2026-04-11 — medium_01_security

## Header

- sample_id: `medium_01_security`
- sample_path: `/Users/zhenzhili/hnsm-backend/docs/references/working/load-test-2026-04-11/samples/medium/medium_01_security.md`
- doc_id: `8e729d68d5deab3a`
- total_segments: 22
- total_proposal_count (regen): 1
- total_valid_count (regen): 1
- total_rejection_count (regen): 0
- generated_at: 2026-04-10T23:54:42.856074+00:00

### Iter 4 historical baseline

- archived_run_record: `run_records/b3_20260410T194444Z_medium_01_security.json`
- archived_bundle_id: `bundle_5cd1b343998c` (in-memory only, not reproducible)
- archived_valid_count: 14

This is the **pre-fix** iter 4 state, retained for historical reference only. The large drift between iter 4's 14 valid drafts and this packet's 1 valid draft is **not** run-to-run variance — it reflects the intentional semantic grounding fix applied between iter 4 and iter 5 (see §Iter 5 context below).

### Iter 5 context (read before reviewing)

**This packet is an iter 5 sample**, not an iter 4 sample. The pipeline has received the semantic grounding fix from the iter 5 blueprint:

- Blueprint: [`docs/blueprints/active/2026-04-11_agent-extraction-prompt-semantic-grounding.md`](../../../../blueprints/active/2026-04-11_agent-extraction-prompt-semantic-grounding.md) (status: `scoped`, applied to `prompts.py`, full regression green at **977 tests**)
- Iter 5 canonical run record: `run_records/b3_20260410T233354Z_medium_01_security.json` (canonical: 1 proposal / 1 valid / 0 rejected)

**Canonical vs. this packet**: this packet was regenerated via `generate_review_packet.py` separately from the canonical run. For medium, the regen matched canonical **exactly** (1/1/0 in both). Per OBS-01 the regen could have differed, but didn't.

**What the iter 5 fix was supposed to do**:

- **F-01 — Document title grounding**: teach the LLM that `Document.title` must be a stable identifier that appears **verbatim** in the source text (filenames, blueprint IDs, section anchors, explicit self-references). Drafts whose `title` is a doc_id hash, body prose synthesis, or section heading paraphrase should be tagged `WRONG_ENTITY`.
- **F-02 — `module:description` narrowing**: teach the LLM that `module:description` field values must be **declarative** descriptions of what the module is or does — not plans, checklists, test expectations, acceptance criteria, or coverage labels. Drafts whose description is a task or operational expectation should be tagged `WRONG_ARG`.
- **Per-type abstention**: teach the LLM to omit a proposal of a specific entity type when grounding for that type is weak, while still emitting valid proposals of other types for the same segment. Expected side effect: absolute proposal volume may drop. A volume decrease accompanied by a strict-rate increase is a pure win (SG-15).

**Iter 5 targets** (from blueprint SG-14):

| metric | iter 4 baseline | iter 5 target |
|---|---:|---:|
| combined strict approval rate `yes / total` | 11.6% | **≥40%** |
| combined salvageable rate `(yes + partial) / total` | 100% | **≥95% guardrail** (must not drop) |

**Review is NOT a backfill operation**. Do NOT:

- Backfill into the iter 4 archived run_record (`b3_20260410T194444Z_*`) — it refers to a different in-memory bundle
- Backfill into the iter 5 canonical run_record (`b3_20260410T233354Z_*`) — it carries pipeline metrics, not per-draft review decisions
- Modify any previously archived artifacts (iter 4 review packet, iter 4 report, `cross_run_observations.md`, etc.)

**What to do instead**: fill in the `REVIEW` block below each draft. After both iter 5 packets (medium + long) are reviewed, a new `review_summary_iter5_2026-04-11.md` will be written to aggregate strict approval rate, `reason_code` distribution, and the iter 4 → iter 5 qualitative delta.

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
  title: "8e729d68d5deab3a"
pred_id: "document:mentions"
field_values:
  - tag: "string"
    value: "scripts/check_no_secrets_in_env_example.sh"
confidence: 1.0
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
  approve: "partial"  # yes | no | partial
  reason_code: "WRONG_ENTITY"     # CORRECT | HALLUCINATED | OVERGENERAL | WRONG_ENTITY | WRONG_PREDICATE | WRONG_ARG | DUPLICATE | AMBIGUOUS | OTHER
  notes: "The mentioned script is supported by the raw text, but the subject identity is wrong: `8e729d68d5deab3a` is the internal doc_id, not a stable identifier that appears verbatim in the source text."
```

---
