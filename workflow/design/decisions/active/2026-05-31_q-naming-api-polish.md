# Q-NAMING Decision: API naming polish for v0.2.0 alpha

- Status: proposed
- Created: 2026-05-31
- Last Updated: 2026-05-31
- Authority: design constraint; locks public API naming for v0.2.0 alpha release before any naming-rename blueprint enters scoped status.
- Inputs:
  - [`workflow/audit/active/2026-05-31_naming-polish-feasibility.md`](../../../audit/active/2026-05-31_naming-polish-feasibility.md) §§2-9 (feasibility audit at commit `10de33b9`)
  - `docs/references/working/change-requests-2026-05-27/` (PDF working copy: "Change Requests for FactGraph")
  - User conversation locks 2026-05-30..2026-05-31 (Module 1-7 module-by-module decisions + Sub-Q1-Q5 resolutions)
- Outputs / Downstream:
  - Q-NAMING-AD blueprint (Audit Batches A + D — Assertions naming polish + Persistence rename)
  - Q-NAMING-C blueprint (Audit Batch C — flat shell delete with combined refactor)
  - Q-NAMING-E blueprint (Audit Batch E — Rule/Inference DSL rename)
  - Q-NAMING-B1 blueprint (Audit Batch B safe — class renames without wire field changes)
  - Q-NAMING-B2 blueprint (Audit Batch B cascade — wire/persistence field renames; gated by stop check)
  - Q-NAMING-F blueprint (Audit Batch F — engine config rename; gated by stop check)
- Related:
  - [`workflow/blueprints/archive/`](../../../blueprints/archive/) Slice 6 archive HEAD `4c472b50` (form-i debt cleanup) — branch base
  - Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` (immutable across all sub-slices)
- Branch: `v0.2.0-naming-polish-feasibility-2026-05-31` (decision authored on top of audit commit `10de33b9`)

> ADR 4-state lifecycle (per Q2 §4.5): `proposed` → `adopted` (current binding constraint, stays in `active/`) → `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` → `proposed` re-opening.

## 1. Inputs

The PDF "Change Requests for FactGraph" (working copy at `docs/references/working/change-requests-2026-05-27/`) proposed naming changes across 7 chapters: Schema, Read/Write, Assertions, Rules/Inferences, Semantics/Engine Config, Evidence/What-if, and Persistence.

User reviewed proposals chapter-by-chapter 2026-05-30 (PDF Module 1 Schema rejections + PDF Module 4 Rules/Inferences carve-out + cross-chapter principles: alpha hard-cut, what-if removed, evidence current state) and module-by-module 2026-05-30..05-31 (module-level adopt/reject decisions for each chapter's specific proposals).

Codex then ran a feasibility audit at commit `10de33b9` measuring hit counts and risk by batch:

- Batch A (Assertions polish): Yellow, 800 hits / 146 files
- Batch B (Advanced type renames + atom/branch cascade): Red, 3726 hits / 331 files
- Batch C (Legacy SDK flat shell hard-cut): Yellow with refactor precondition, 132 hits / 33 files
- Batch D (Persistence workspace rename): Yellow, 299 hits / 43 files
- Batch E (Inference and Rule DSL): Red, 358 hits / 115 files
- Batch F (Semantics → engine config): Red, 1956 hits / 155 files

Audit §8 flagged blockers requiring lock-time decisions:
1. B2 cascade may be wire/persistence behavior change (diagnostic keys, recorded payloads)
2. F SemanticsProfile in digest fields + adapter-facing payloads
3. E `.where(...)` alias-vs-hard-cut policy
4. C requires internal delegation refactor before shell delete
5. A `by_ids(strict=True)` must be implemented on every public by-ids surface

Sub-Q1 through Sub-Q5 were resolved 2026-05-31:
- **Sub-Q1** (B2, F wire/persistence compatibility): **hard-cut at v0.2** — no aliases, no dual-emit. Per user "有hard cut的选项统一选择hard cut".
- **Sub-Q2** (`.where()` policy): **hard-cut** — no alias. Per user "有hard cut的选项统一选择hard cut".
- **Sub-Q3** (Batch C refactor approach): **single slice** — combined refactor + shell delete. Claude judgment; matches Slice 3a Step 7 precedent.
- **Sub-Q4** (`atom_bounds` cascade boundary): **narrow — exclude** `atom_bounds` from atom→condition cascade. Claude judgment; preserves adapter semantics wording per audit §3 caveat.
- **Sub-Q5** (Q-NAMING doc structure): **single Q-NAMING decision** with 6 phased sub-slices. Claude judgment; matches Slice 3a Q10-Q14 pattern.

## 2. Scope

This decision locks:

- 2.1 PDF Module 1 Schema: all proposals rejected — §4.1
- 2.2 Audit Batch A (Assertions): adopted renames — §4.2
- 2.3 Audit Batch B (class renames + atom/branch cascade): adopted with `atom_bounds` carve-out — §4.3
- 2.4 Audit Batch C (legacy flat shell hard-cut): adopted with single-slice refactor — §4.4
- 2.5 Audit Batch D (persistence workspace rename): adopted with pre-lock check — §4.5
- 2.6 Audit Batch E (Rule/Inference DSL): adopted 4.1 + 4.2 only, Rule→NamedQuery rejected — §4.6
- 2.7 Audit Batch F (Semantics → engine config): adopted hard-cut — §4.7
- 2.8 Cross-cutting policy: alpha hard-cut, sacred constraints, historical carve-out — §4.8
- 2.9 Phased implementation plan: 6 sub-slice blueprints with stop gates before B2 and F — §4.9

## 3. Non-scope

This decision does NOT lock:

- Implementation step order within any sub-slice (each blueprint's own Step 1–8 cadence)
- Specific test rewrite strategy per sub-slice (test churn budget per blueprint)
- Doc rewriting strategy per sub-slice; historical workflow/archive material is carved out per §4.8
- Adapter semantics terminology (`atom_bounds`, `head_bound`) — preserve adapter wording (per Sub-Q4, audit §3 caveat)
- Public SDK contract changes outside naming (no method removals beyond the explicit flat-shell delete list in §4.4)
- Substrate / core internal naming where the public boundary is unchanged (private helpers may keep legacy names — audit §2 explicitly permits this for the audit query layer)
- Workspace file format binary structure (per audit §5: format unchanged — only method names change in Batch D)
- Q-PR1 sacred paths (§4.8) — 0-diff invariant across all sub-slices
- Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` (§4.8)
- Dirty baseline preservation (§4.8)

## 4. Decision

### §4.1 PDF Module 1 Schema — REJECT all

Per user 2026-05-30: all Module 1 Schema proposals are rejected; current shipped behavior is preserved.

- `Entity.__default_eref_pattern__`: **REJECT**
  - Rationale: explicitly rejected in prior decision (user reference). Current shipped behavior uses the `pattern` keyword on Entity DSL, which corresponds to the PDF's `eref_pattern` proposal; the rename is moot because the current name already aligns.
- Factory-generated entity IDs: **REJECT**
  - Rationale: "没有采纳的必要" (user).
- `fg.entities.create_with_id(...)`: **REJECT**
  - Rationale: "没有采纳的必要" (user).
- Any Schema proposal that conflicts with current shipped identity / entity semantics: **REJECT**
  - Rationale: per user "对于涉及概念冲突的部分以当前的代码行为为准".

### §4.2 Audit Batch A (Assertions) — ADOPT

Per user module-by-module review of Assertions (one item rejected, five adopted). Hard-cut per §4.8.

- `fg.views` → `fg.assertion_views` (audit §2: 268 hits / 41 files)
  - Public SDK namespace rename; hard-cut, no alias.
- `FrozenAssertionView` → `FrozenAssertionSet` (audit §2: 259 hits / 45 files)
  - Renamed on **both** the SDK-facing surface **and** the core database-facing class. Naming consistency between layers (audit §2 feasibility note: "Renaming both is feasible but wider" — we accept the wider scope).
- `fg.assertions.by_ids(strict=True)` — additive `strict=` flag (audit §2: 78 hits / 22 files)
  - Implemented on **every** public by-ids surface (top-level assertions manager AND the assertion view object — audit §2 blocker 5).
  - `strict=True` raises explicitly on missing IDs and on duplicate IDs (semantics defined in Q-NAMING-AD blueprint).
  - Current permissive default behavior unchanged when `strict=False` (default).
- `fg.audit.explain_fact(pred_id, e_ref)` → `fg.audit.explain(asrt_id | record)` (audit §2: 79 hits / 35 files)
  - **Semantic clarification**: `fg.audit` explains chosen-policy among multiple active claims for a (pred, eref) cell — i.e., which active claim is the policy winner. It does NOT explain derivation reasoning. See `src/factgraph/core/store/_queries.py:13`.
  - Lower-level core query function (`explain_fact` in `_queries.py`) MAY remain private under its existing name; only the public SDK boundary signature changes (audit §2 explicitly permits this).
  - New signature: takes `asrt_id` (existing) or `AssertionRecord` (added) — overload policy defined in Q-NAMING-AD blueprint.
- `fg.audit.conflicts(pred_id, e_ref)` → `fg.audit.conflicts(record | entity, field)` (audit §2: 13 hits / 10 files)
  - **Semantic clarification**: returns active-claim set plus policy-chosen winner for the (pred, eref) cell. Same semantics as today (`src/factgraph/core/store/_queries.py:51`); only public signature changes.
  - New signature: takes `AssertionRecord` OR `(Entity, field_name)` tuple.

### §4.3 Audit Batch B (advanced types + atom/branch cascade) — ADOPT with `atom_bounds` carve-out

Per user "B, 还是 worth rename 的, 但是要先判断哪些应该变" (rename worthwhile but selective). Hard-cut on wire/persistence per Sub-Q1. `atom_bounds` excluded per Sub-Q4.

**§4.3.1 Top-level class renames (audit §3) — ADOPT:**

- `SupportArtifact` → `ProofReceipt` (949 hits / 211 files)
- `EvaluationOverlay` → `FactOverlay` (522 hits / 84 files)
- `FactValueOverride` → `ReplaceFact` (177 hits / 50 files)
- `FactRemoveAction` → `RemoveFact` (51 hits / 20 files)

**§4.3.2 atom → condition cascade (audit §3) — ADOPT:**

- `atom_index` → `condition_index` (380 hits / 74 files)
- `atom_key` → `condition_key` (240 hits / 60 files)
- `_atom_index_from_key` → `_condition_index_from_key`
- `materialized_atom_index` → `materialized_condition_index`
- `RuleAddedAtom` → `RuleAddedCondition`
- `RuleAddedAtomKind` → `RuleAddedConditionKind`
- `AtomDescriptor` → `ConditionDescriptor`
- `DiagnoseAtomLocator` → `DiagnoseConditionLocator`
- `WhyNotAtomLocator` → `WhyNotConditionLocator`
- `ProofFrameAtomVerdict` → `ProofFrameConditionVerdict`
- `RuleLiteralPath`: **VERIFY in Q-NAMING-B1** whether corresponding rename is warranted (audit §3 lists 109 hits but no explicit rename target; decide during sub-slice draft).

**§4.3.3 atom_bounds — EXCLUDE (Sub-Q4):**

- `atom_bounds` is partially adapter semantics wording (audit §3: "Some occurrences may still belong to engine semantics rather than rule condition wording"). Preserved as-is in adapter code and adapter-facing docs. Q-NAMING-B2 scope must explicitly exclude `atom_bounds` from cascade.

**§4.3.4 branch → case cascade (audit §3) — ADOPT (hard-cut on wire/persistence):**

- `branch_index` → `case_index` (630 hits / 113 files) — DTO fields, walker state, support capture, evaluation rows
- `runtime_branch_index` → `runtime_case_index`
- `engine_payload` → `proof` (110 hits / 37 files) — wire/serialized field rename, hard-cut per Sub-Q1
- `b{branch}.a{atom}` diagnostic key format → `c{case}.c{condition}` — hard-cut per Sub-Q1 (audit §3 §8 blocker 1)

**§4.3.5 WhyNot wording cleanup (audit §3) — NARROW target:**

- Apply rename only to WhyNot partition row types / status field values, NOT every "green" or "red" mention in repo. Q-NAMING-B2 blueprint enumerates the exact target list in its scope section.

**§4.3.6 Wire/persistence compatibility (Sub-Q1):**

- All §4.3 field renames are hard-cut at v0.2. No alias support. No dual-emit. Old field names removed in same commit as new names introduced.
- Recorded payloads and diagnostic key strings change in v0.2 (per audit §3 §8 blocker 1). Acceptable because alpha — no historical consumers.

### §4.4 Audit Batch C (legacy SDK flat shells) — DELETE all, single slice

Per user "D, 删除flat" and Sub-Q3 (single slice). Combined refactor + shell delete in same blueprint.

**§4.4.1 Flat shells to delete (audit §4):**

`fg.check`, `fg.diagnose`, `fg.why_not`, `fg.evaluate`, `fg.run`, `fg.accept`, `fg.accept_many`, `fg.explain`, `fg.explain_fact`, `fg.conflicts`, `fg.check_fact_overlay`, `fg.recheck_proof_frame`, `fg.check_rule_disable`, `fg.check_rule_literal_replace`, `fg.check_rule_add_condition`, `fg.diff_proof_frames`, `fg.inspect_rule`, `fg.inspect_semantics`, `fg.validate_provenance`, `fg.ingest`.

**§4.4.2 `fg.commit_assertions` — TBD in Q-NAMING-C:**

Not on auto-delete list. Audit §4 records 37 hits / 12 files with real source usage. Q-NAMING-C blueprint decides during draft: keep as named operation, migrate to namespaced manager, or include in delete with internal helper extraction. Decision is sub-slice-local.

**§4.4.3 Single-slice refactor + delete (Sub-Q3):**

Sequence within Q-NAMING-C blueprint:
1. Move flat-shell bodies into namespaced manager method bodies OR into private helpers under `_internal/`
2. Update all internal callers (namespaced managers, application protocol code) to reach private helpers, not deleted public shells
3. Delete the public flat shells from `SDKStore` surface
4. Migrate docs and tests to namespaced manager call form

All four steps land within one blueprint per Sub-Q3 (matches Slice 3a Step 7 precedent).

### §4.5 Audit Batch D (Persistence) — ADOPT with pre-lock check

Per user "1.ok; 2.ok; 3.ok 在 lock 之前可以先和 codex 对接, 确认没有明确的阻塞".

- `fg.save(...)` → `fg.save_workspace(...)` (audit §5: 166 hits / 39 files)
- `FactGraph.load(...)` → `FactGraph.load_workspace(...)` (audit §5: 115 hits / 34 files)
- `SDKStore.save`, batch save behavior, and `FactGraph.load` all migrated together for consistent treatment (audit §5).
- Hard-cut per §4.8 (no alias). Docs/tests remove old names.

**Pre-lock check (per user):**

Before Q-NAMING-AD blueprint enters scoped status, Codex confirms with user that `branch_index → case_id` impact on persisted formats (covered in §4.3.4) has no blocker beyond what audit §3 already identified. If blocker surfaces, B2 wire compatibility is re-examined before A/D scope-freeze.

**Workspace file format:** binary structure unchanged (audit §5).

**Persistence schema digests:** unchanged unless explicitly listed in §4.7 F batch.

### §4.6 Audit Batch E (Rule/Inference DSL) — ADOPT 4.1 + 4.2 only

Per user "Module 4, 同意只有 2 个 valid 提议 (4.1 + 4.2) 采纳". Hard-cut on `.where()` per Sub-Q2.

**§4.6.1 ADOPT — 4.1 Branch → Case:**

- `Branch` DSL class → `Case` (audit §6: `class Branch` 2 hits / 2 files)
- Applies to **legacy `Inference` class only**. The new `Rule` class is NOT affected by this rename (no `Branch` concept in new Rule DSL).
- Imports / exports move together; SDK surface updates `__all__`.

**§4.6.2 ADOPT — 4.2 where → when:**

- `.where(...)` → `.when(...)` (audit §6: 398 call-shape hits / 57 files; 12 `def where` / 5 files)
- Applies to **both** new `Rule` DSL and legacy `Inference` DSL.
- Hard-cut per Sub-Q2 — no `.where(...)` alias retained.
- Examples, tests, and docs that teach query syntax migrate in the same slice (audit §6 hidden dependency: "If `where` changes on both Rule and Inference, examples and tests that teach query syntax will all need to move in the same slice").

**§4.6.3 ADOPT — `target + head_vars → emits` (Inference only):**

- Per user PDF chapter response: "针对 C2... target + head_vars → emits 可以考虑, 不过主要是针对旧的 Inference 类". For new Rule class only `where → when` applies; target/head semantics on new Rule unchanged.
- Implementation must avoid accidentally renaming Rule internals (audit §6 hidden dependency: "Rule and Inference share naming concepts but have different compatibility needs").

**§4.6.4 REJECT — Rule → NamedQuery:**

- Per user 2026-05-30: "不采用所有和 'Rule => NamedQuery' 相关的变化, 因为我们的 rule 不仅限于此".
- All renames or restructures that recast `Rule` as `NamedQuery` are rejected.

**§4.6.5 REJECT — All other Module 4 proposals (4.3 and beyond):**

- Per user "Module 4, 同意只有 2 个 valid 提议 (4.1 + 4.2) 采纳".

**§4.6.6 VERIFY only (docs work, no rename):**

- `Pred` documented as "low-level escape hatch" per user; docs work in Q-NAMING-E blueprint, no rename.
- `Not(condition)`: verify whether current grammar supports it (audit §6: 23 hits / 11 files). If supported, docs work only. If unsupported, raise as separate proposal — out of Q-NAMING scope.

### §4.7 Audit Batch F (Semantics → engine config) — ADOPT hard-cut

Per user "Module 5, 同意" and Sub-Q1 (hard-cut on wire/digests). `atom_bounds` excluded per Sub-Q4 (cross-references §4.3.3).

**§4.7.1 ADOPT — class and wrapper renames (audit §7):**

- `ProbLogSemantics` → `ProbLogConfig` (203 hits / 61 files)
- `PyReasonSemantics` → `PyReasonConfig` (306 hits / 69 files)
- `SemanticsProfile` → `EngineProfile` (842 hits / 129 files)

**§4.7.2 ADOPT — keyword renames (audit §7):**

- `semantics=` → `config=` (206 hits / 52 files)
  - Disambiguation from existing `config=` keyword in unrelated code is a docs/test responsibility within Q-NAMING-F (audit §7 caveat).

**§4.7.3 ADOPT — engine payload field renames (audit §7, cross-ref §4.3.4):**

- `branch_probabilities` → `case_probabilities` (135 hits / 38 files)
- `branch_bounds` → `case_bounds` (196 hits / 36 files)
  - Same wire compatibility concern as §4.3.4 branch/case cascade. Hard-cut per Sub-Q1.

**§4.7.4 ADOPT — SDK helper rename (audit §7):**

- `fg.eval.inspect_semantics` / top-level `inspect_semantics` → `preview_config` (60 hits / 29 files)

**§4.7.5 head_bound — CLEANUP, not 1:1 rename (audit §7):**

- `head_bound` occurrences are partially adapter projection semantics (audit §7: "Some occurrences are likely part of adapter projection semantics").
- Q-NAMING-F blueprint handles as removal / normalization where applicable, NOT as `head_bound → candidate_bound` rename. Adapter semantics terminology preserved.

**§4.7.6 atom_bounds — EXCLUDED (Sub-Q4):**

- Cross-references §4.3.3. Preserved as adapter semantics wording.

**§4.7.7 Wire / persistence / digest compatibility (Sub-Q1):**

- All §4.7 renames are hard-cut at v0.2. No alias support. No dual-emit.
- `semantics_digest` field (or equivalent) renamed to match `config` naming. Stored digest field name changes.
- Adapter-facing payload field names change. Acceptable because alpha — no external adapter consumers.

### §4.8 Cross-cutting policy

**§4.8.1 Hard-cut at v0.2** (Sub-Q1, Sub-Q2):

- No alias methods or aliased properties for old names.
- No dual-emit on wire / persistence / digest payloads.
- No backward-compatibility shims. Alpha release; no historical users to protect.
- Old name removed in same commit as new name introduced.

**§4.8.2 `atom_bounds` excluded from cascade** (Sub-Q4):

- Applies to §4.3 Batch B and §4.7 Batch F.
- Q-NAMING-B2 and Q-NAMING-F scope sections must explicitly list `atom_bounds` as excluded.
- Adapter semantics wording preserved.

**§4.8.3 `head_bound` cleanup not a rename** (audit §7):

- `head_bound` handled as normalization / removal where appropriate, not 1:1 rename.
- Q-NAMING-F blueprint decides per-occurrence whether to remove, leave, or normalize.

**§4.8.4 WhyNot wording narrow target** (audit §3):

- Q-NAMING-B2 blueprint's scope section lists explicit "green"/"red" occurrences to rename.
- Historical workflow refs and unrelated color mentions left untouched.

**§4.8.5 Historical workflow carve-out** (audit §8 recommendation):

- All sub-slices: historical references in `workflow/heritage/`, `workflow/blueprints/archive/`, `workflow/audit/archive/`, and equivalent archived material remain untouched unless the decision specifically targets historical wording (none do).
- Current SDK docs (`docs/`), module docs (`src/factgraph/*/docs/`), quickstarts, current examples, and active tests are migrated.

**§4.8.6 Q-PR1 sacred carve-out** (all sub-slices):

The following 5 paths preserve 0-diff against `4c472b50` across all sub-slices:

- `src/factgraph/core/evidence/write_protocol.py`
- `src/factgraph/core/store/ledger.py`
- `src/factgraph/core/store/_builders.py`
- `src/factgraph/adapters/pyreason/`
- `src/factgraph/core/derivation/accept.py`

Per-commit verification: `git diff 4c472b50 -- <path>` returns empty for all five.

**§4.8.7 Sacred master** (all sub-slices):

`562c74195df43e933bed92a3ff25de94dd8ce666` immutable. Verified per-commit: `git rev-parse 562c74195df43e933bed92a3ff25de94dd8ce666` resolves; no rewrites.

**§4.8.8 Dirty baseline preserved** (all sub-slices):

Existing working-tree state at audit time:
- Modified: `docs/references/working/design-points/readme.md`, `examples/01_sdk_check_diagnose.ipynb`, `examples/02_overlay_why_not_frontier.ipynb`, `examples/archive/01_sdk_basics.ipynb`
- Deleted: `workflow/design/decisions/archive/.gitkeep`, `workflow/working/.gitkeep`
- Untracked: `docs/references/working/change-requests-2026-05-27/`, `"rainbird-ai sdk code/"`

These are NEVER committed by any Q-NAMING sub-slice. Per-commit ritual checks that none of these paths appear in `git diff --cached`.

**§4.8.9 Push policy** (all sub-slices):

No `git push` without explicit per-slice user authorization. Prior push approval does not roll forward.

### §4.9 Phased implementation plan

Six sub-slice blueprints in this order, with stop gates before B2 and F (per audit §9 + Sub-Q5):

| Phase | Sub-slice | Audit Batch | Scope summary | Risk |
|---|---|---|---|---|
| 1 | Q-NAMING-AD | A + D | Assertions naming polish (§4.2: `fg.views`→`fg.assertion_views`, `FrozenAssertionView`→`FrozenAssertionSet`, `by_ids(strict=True)`, `fg.audit.explain`/`conflicts` signature change) + Persistence rename (§4.5: `save_workspace`/`load_workspace`). Includes pre-lock check on §4.3.4 branch/case persistence impact before scope-freeze. | Yellow |
| 2 | Q-NAMING-C | C | Flat shell hard-cut (§4.4). Single slice per Sub-Q3: move bodies into namespaced manager / private helpers, then delete `fg.*` public shells, then migrate docs/tests. Decide `fg.commit_assertions` fate during slice. | Yellow |
| 3 | Q-NAMING-E | E | Rule/Inference DSL (§4.6): `Branch`→`Case` (Inference only), `.where()`→`.when()` (Rule + Inference, hard-cut), `target + head_vars`→`emits` (Inference only). `Pred` and `Not(condition)` docs polish / verify. | Red |
| 4 | Q-NAMING-B1 | B (safe) | Class renames that do NOT alter wire field names (§4.3.1 + §4.3.2 class-level): `SupportArtifact`→`ProofReceipt`, `EvaluationOverlay`→`FactOverlay`, `FactValueOverride`→`ReplaceFact`, `FactRemoveAction`→`RemoveFact`, all `*Atom*`→`*Condition*` descriptor/locator/verdict class renames (no field-level wire rename yet). | Yellow |
| — | **STOP GATE** | — | After AD + C + E + B1 archived. Codex confirms wire/persistence change is acceptable. User explicitly authorizes B2 + F scope. | — |
| 5 | Q-NAMING-B2 | B (cascade) | Field/key migration (§4.3.2 field-level + §4.3.4 + §4.3.5): `atom_index`→`condition_index`, `atom_key`→`condition_key`, `_atom_index_from_key`→`_condition_index_from_key`, `materialized_atom_index`→`materialized_condition_index`, `engine_payload`→`proof`, `branch_index`→`case_index` (DTO/wire/persistence — hard-cut per Sub-Q1), `b{branch}.a{atom}`→`c{case}.c{condition}` diagnostic keys, WhyNot green/red narrow cleanup. **EXCLUDES** `atom_bounds` (Sub-Q4). | Red |
| — | **STOP GATE** | — | After B2 archived. Codex confirms F engine-config rename does not destabilize adapter consumers. User explicitly authorizes F scope. | — |
| 6 | Q-NAMING-F | F | Engine config (§4.7): `ProbLogSemantics`→`ProbLogConfig`, `PyReasonSemantics`→`PyReasonConfig`, `SemanticsProfile`→`EngineProfile`, `semantics=`→`config=`, `branch_probabilities`→`case_probabilities`, `branch_bounds`→`case_bounds`, `inspect_semantics`→`preview_config`. Digest field renames per Sub-Q1 hard-cut. `head_bound` cleanup (not 1:1 rename, §4.7.5). **EXCLUDES** `atom_bounds` (Sub-Q4). | Red |

**Stop gate definition**: prior sub-slice fully archived (blueprint moved to `workflow/blueprints/archive/`), per-commit verification ritual confirmed (§4.8.6–§4.8.8), AND user provides explicit "可以推进" authorization. No B2 or F draft begins without both.

**Single decision document** (per Sub-Q5): all decisions captured in this file. Each implementing blueprint cites this decision's §-numbers (e.g., "per Q-NAMING §4.3.2") rather than repeating decision content. This file is the single source of truth.

## 5. Rejected Alternatives

### Option (a): Rule → NamedQuery rename
- **Why rejected**: User explicit 2026-05-30 — "不采用所有和 'Rule => NamedQuery' 相关的变化, 因为我们的 rule 不仅限于此". Rule semantics broader than named queries; restructure would lose generality.

### Option (b): PDF Module 1 Schema rename block
- **Why rejected**: User explicit 2026-05-30 — preserve current shipped behavior. `Entity.__default_eref_pattern__` previously rejected; `pattern` keyword already matches PDF's intent; Factory-generated IDs and `fg.entities.create_with_id(...)` not needed.

### Option (c): Dual-emit / alias mode for wire and persistence (Sub-Q1)
- **Why rejected**: Alpha release, no backward-compat burden (per user "我们是 alpha 版, 不用担心用户学习成本, 历史兼容等问题"). Hard-cut chosen at v0.2 boundary. Sub-Q1 selected per user "有 hard cut 的选项统一选择 hard cut".

### Option (d): `.where(...)` alias kept temporarily (Sub-Q2)
- **Why rejected**: Hard-cut chosen per user "有 hard cut 的选项统一选择 hard cut". Examples / tests / docs migrate in single E sub-slice.

### Option (e): Two-slice Batch C (refactor first, delete later) (Sub-Q3)
- **Why rejected**: Single-slice combined refactor + delete chosen — matches Slice 3a Step 7 precedent. Internal delegation refactor is a precondition step within the slice, not a separately reviewable cycle. Reduces inter-slice coordination overhead.

### Option (f): Full `atom_bounds` cascade (Sub-Q4)
- **Why rejected**: `atom_bounds` is partially adapter semantics wording per audit §3 ("Some occurrences may still belong to engine semantics rather than rule condition wording"). Renaming to `condition_bounds` would conflate rule-DSL terminology with engine-projection terminology, weakening the very layer separation the rename is meant to clarify.

### Option (g): Six separate Q-NAMING decision documents (Sub-Q5)
- **Why rejected**: Matches Slice 3a Q10-Q14 precedent of single multi-§ decision. Six standalone decisions would force inter-decision cross-references for shared cross-cutting policy (Sub-Q1, Sub-Q2, sacred constraints), creating duplication and drift risk.

### Option (h): `ProofFrame` → `ReasoningRound` rename (PDF)
- **Why rejected**: Not in user's adopted list. `ProofFrame` is shipped (per `kernel.sdk.diff_proof_frames`, post-L surface). Rename would touch G5 ProofFrame Diff sub-slice's archived surface without user adoption signal.

### Option (i): `head_bound` → `candidate_bound` rename (PDF)
- **Why rejected**: `head_bound` is partially adapter projection semantics (audit §7). Treated as cleanup / normalization not 1:1 rename per §4.7.5. A `candidate_bound` rename would import the same adapter-vs-DSL confusion as `atom_bounds`.

### Option (j): All Module 4 (Rules/Inferences) proposals beyond 4.1 + 4.2
- **Why rejected**: User explicit 2026-05-31 — "Module 4, 同意只有 2 个 valid 提议 (4.1 + 4.2) 采纳". Items 4.3+ not adopted; current Rule/Inference DSL otherwise preserved.

### Option (k): Implement all 6 sub-slices as one combined commit sequence
- **Why rejected**: Audit §8 explicit recommendation: "Do not lock A-F as one implementation slice. The combined matrix is too large and mixes simple public SDK polish with high-risk wire/protocol language changes." Stop gates before B2 and F preserve reviewability.

## 6. Supporting Evidence

**Audit citations** (`workflow/audit/active/2026-05-31_naming-polish-feasibility.md` at commit `10de33b9`):

- §1 Scope and protocol
- §2 Batch A Assertions: 800 hits, Yellow risk; feasibility notes on `fg.views` / `FrozenAssertionView` / `by_ids` / `explain_fact` / `conflicts`
- §3 Batch B Advanced types + cascade: 3726 hits, Red; blockers in §8 items (1) wire/persistence and (3) atom_bounds adapter wording
- §4 Batch C Flat shell hard-cut: 132 hits, Yellow with refactor precondition (audit §4 hidden dependency)
- §5 Batch D Persistence: 299 hits, Yellow; workspace file format unchanged
- §6 Batch E Rule/Inference: 358 hits, Red; `.where()` policy required (audit §8 item 3)
- §7 Batch F Semantics/Engine: 1956 hits, Red; digest / wire / adapter compatibility required (audit §8 item 2)
- §8 Cross-batch risk summary + blockers + recommendations
- §9 Recommended implementation sequence (6 sub-slice ordering)
- §10 Verification: sacred paths 0-diff, dirty baseline preserved, master untouched, no push

**Shipped behavior citations**:

- `src/factgraph/core/store/_queries.py:13` (`explain_fact`) and `:51` (`conflicts`) — confirms `fg.audit` explains chosen-policy among active claims, not derivation reasoning (informs §4.2 semantic clarification)
- `src/factgraph/sdk/store.py:1402` (`_SDKAuditManager`) — confirms namespaced audit manager delegates to flat `SDKStore` methods (informs §4.4.3 refactor precondition)
- `src/factgraph/application/protocol/derivation_fact_overlay.py`, `derivation_why_not.py`, `derivation_check.py`, `derivation_diagnose.py` — current DTO field names (informs §4.3 cascade scope)

**User conversation locks** (2026-05-30 to 2026-05-31):
- PDF Module 1 Schema rejection
- Module 4 carve-out (4.1 + 4.2 only; Rule → NamedQuery rejected)
- Module 5 / 6 / 7 module-level agreement
- Alpha hard-cut directive: "我们是 alpha 版, 不用担心用户学习成本, 历史兼容等问题"
- Sub-Q1-Q5 directive: "有 hard cut 的选项统一选择 hard cut, 其他可以按照你专业角度来选择"

## 7. Consequences

### 7.1 Downstream unblocking

This decision (once adopted) unblocks:
- **Q-NAMING-AD blueprint draft** (Phase 1, next slice)
- **Q-NAMING-C blueprint draft** (Phase 2, after AD archived)
- **Q-NAMING-E blueprint draft** (Phase 3, after C archived)
- **Q-NAMING-B1 blueprint draft** (Phase 4, after E archived)
- Q-NAMING-B2 and Q-NAMING-F are **stop-gated** per §4.9; not unblocked by this decision alone.

### 7.2 Required follow-up actions

Each sub-slice blueprint must:
- Cite this decision's §-numbers in the blueprint's Inputs section
- Apply per-commit verification ritual: branch / sacred master / Q-PR1 / dirty baseline / `git diff --check` (§4.8.6–§4.8.8)
- Preserve all five Q-PR1 sacred paths at 0-diff vs `4c472b50` (§4.8.6)
- Preserve sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` (§4.8.7)
- Preserve dirty baseline (§4.8.8)
- Request explicit user authorization before push (§4.8.9)
- Update affected module docs under `src/factgraph/*/docs/` post-implementation
- Leave historical workflow / archive material untouched (§4.8.5)

### 7.3 No-retroactive boundary

This decision applies to v0.2.0 alpha release naming. Sub-slices land within v0.2.0 development branch lineage. No backports to v0.1.x sacred branches or `release/0.1.x`. Prior v0.1.x snapshots remain untouched.

### 7.4 Cross-pillar interactions

- **Module docs** (`src/factgraph/*/docs/README.md`): each sub-slice updates affected module docs in same commit cluster as code rename. Q-NAMING-C may touch many module docs (flat shell removal documented).
- **Tests**: each sub-slice migrates test fixtures and assertion strings in same commit sequence as code rename. No two-pass test+code; one-pass per file.
- **Workflow archive**: untouched per §4.8.5 historical carve-out.
- **Adapter code**: Q-NAMING-F sub-slice touches adapter-facing payloads (hard-cut per Sub-Q1). `atom_bounds` preserved per Sub-Q4. `head_bound` cleanup not 1:1 rename per §4.7.5.

### 7.5 Stop gate enforcement

Q-NAMING-B2 and Q-NAMING-F must not enter `scoped` status without ALL of:
1. All preceding sub-slices archived in `workflow/blueprints/archive/`
2. Per-commit verification ritual confirmed for each preceding sub-slice
3. User explicit "可以推进" authorization
4. Sacred constraints (Q-PR1, sacred master, dirty baseline) verified preserved through each archived slice

### 7.6 Test/doc footprint estimate

Per audit aggregate hits (§8):
- Tests across all phases: ~115 test files touched (deduplicated, after historical carve-outs)
- Current docs across all phases: ~150 current doc/quickstart/example files touched
- Source files across all phases: ~80 source files touched
- Workflow / historical: untouched (carve-out)

Each blueprint allocates per-slice budget within these totals.

## 8. Acceptance Criteria

This decision is honored when:

- [ ] All six sub-slice blueprints archived in `workflow/blueprints/archive/` with `Status: implemented`
- [ ] No alias / no dual-emit for any renamed name across all sub-slices (Sub-Q1, Sub-Q2)
- [ ] `atom_bounds` retained in adapter code with zero rename (Sub-Q4)
- [ ] `head_bound` cleanup matches adapter semantics (not 1:1 rename) (§4.7.5)
- [ ] Q-PR1 sacred paths 0-diff vs `4c472b50` across all archived sub-slice HEADs (§4.8.6)
- [ ] Sacred master `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged through all sub-slices (§4.8.7)
- [ ] Dirty baseline preserved (uncommitted) through all sub-slices (§4.8.8)
- [ ] Stop gate records present in Q-NAMING-B2 and Q-NAMING-F blueprints (§4.9)
- [ ] All module docs in `src/factgraph/*/docs/` updated for renames touched in each slice
- [ ] `docs/` quickstart, README, and current-examples references updated
- [ ] No flat shells remain in `SDKStore` public surface after Q-NAMING-C (§4.4.1)
- [ ] Workspace file format binary unchanged (§4.5)
- [ ] Wire payloads use new field names only after Q-NAMING-B2 + Q-NAMING-F (Sub-Q1)
- [ ] Engine config `config_digest` (or equivalent) replaces `semantics_digest` after Q-NAMING-F (§4.7.7)
- [ ] `fg.audit.explain` and `fg.audit.conflicts` signatures match new shape after Q-NAMING-AD (§4.2)
- [ ] `Branch` class only renamed on legacy `Inference`, not new `Rule` (§4.6.1)
- [ ] `.when()` replaces `.where()` on both Rule and Inference DSL (§4.6.2)

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-31 | proposed | Decision drafted by Claude | Captures user PDF chapter responses 2026-05-30 + module-by-module locks 2026-05-30..05-31 + Sub-Q1-Q5 resolutions 2026-05-31. Sourced from audit `10de33b9` (`workflow/audit/active/2026-05-31_naming-polish-feasibility.md`). Phased per audit §9. Awaiting user adopt action. |
