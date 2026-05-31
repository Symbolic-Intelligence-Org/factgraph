# Q-NAMING Implementation Feasibility Audit

- Branch: `v0.2.0-naming-polish-feasibility-2026-05-31`
- Fork point: `4c472b50` (Slice 6 archive HEAD)
- Mode: doc-only feasibility audit
- Purpose: pre-lock blocker discovery for the Q-NAMING decision matrix
- Date: 2026-05-31
- Output: this report only; no runtime, test, doc-site, or blueprint edits

## §1 Scope

This audit checks implementation feasibility for the proposed Q-NAMING matrix before
the user locks a decision. It does not adopt, reject, or draft the decision. It
answers whether the requested batches are straightforward rename work or whether
they hide protocol, persistence, test, documentation, or internal dependency
risks that should change the lock shape.

Counts below are from tracked `HEAD` on `4c472b50` using grep-style identifier
searches across `src/`, `tests/`, `docs/`, `workflow/`, examples, tutorials, and
tools. The counts intentionally include historical workflow material unless a
row explicitly says otherwise; this makes documentation blast visible, but it
does not imply historical/archive files should be rewritten.

Risk legend:

- Green: straightforward rename, low hidden dependency risk.
- Yellow: feasible, but broad enough to require careful commit boundaries.
- Red: blocker-class design or compatibility decision required before locking a
  hard-cut implementation.

## §2 Batch A Audit - Module 1 Assertions

Risk: Yellow.

| Identifier / surface | Hits | Files | Src files | Test files | Docs/workflow files |
|---|---:|---:|---:|---:|---:|
| `fg.views` | 268 | 41 | 5 | 5 | 29 |
| `FrozenAssertionView` | 259 | 45 | 7 | 4 | 33 |
| `fg.assertions.by_ids` / `by_ids` | 78 | 22 | 6 | 1 | 14 |
| `def by_ids` | 8 | 5 | 2 | 0 | 3 |
| `explain_fact` | 79 | 35 | 8 | 0 | 26 |
| `fg.audit.explain` | 0 | 0 | 0 | 0 | 0 |
| `fg.audit.conflicts` | 13 | 10 | 1 | 0 | 9 |

Feasibility notes:

- `fg.assertion_views` has no shipped runtime conflict. The rename from
  `fg.views` is mechanically feasible, but it spans SDK docs, tests, and current
  examples. It should be treated as a public SDK hard-cut, not a local rename.
- `FrozenAssertionView` exists in both SDK-facing and core database-facing code.
  The requested `FrozenAssertionSet` name is cleaner, but the implementation must
  decide whether the core database object is renamed too or whether only SDK
  presentation changes. Renaming both is feasible but wider.
- `fg.assertions.by_ids(..., strict=True)` is additive and safe, but there are two
  user-visible implementations to check: the SDK assertions manager and the
  assertion view object. Current behavior appears permissive, so strict mode must
  define missing-ID and duplicate-ID behavior explicitly.
- `fg.audit.explain_fact(pred_id, e_ref)` and
  `fg.audit.conflicts(pred_id, e_ref)` hard-cuts are feasible at the SDK boundary,
  but the replacement signatures are not just names. `explain(asrt_id|record)`
  needs a concrete overload policy, and `conflicts(record|entity, field)` must
  define how record inputs map back to the existing core query functions. The
  lower-level store queries can remain private under old internal names if the
  public SDK boundary changes.

Hidden dependencies:

- `_SDKAuditManager` delegates to `SDKStore` flat methods today. If Batch C
  also removes flat shells, Batch A should not depend on those shell methods as
  implementation internals.
- Documentation and workflow references dominate the count. Historical workflow
  material should be carved out, while current SDK docs and quickstarts should
  be migrated.

Test/doc estimate:

- Tests: small to medium, roughly 5-8 direct test files.
- Docs/current examples: medium, roughly 10-15 current docs/examples after
  historical carve-outs.

Recommendation:

- Batch A is feasible as an early naming slice if it excludes deep protocol work
  and keeps old core query helper names private where useful.

## §3 Batch B Audit - Module 3 Advanced Type Renames And Cascade

Risk: Red.

| Identifier / surface | Hits | Files | Src files | Test files | Docs/workflow files |
|---|---:|---:|---:|---:|---:|
| `SupportArtifact` | 949 | 211 | 42 | 33 | 132 |
| `EvaluationOverlay` | 522 | 84 | 22 | 24 | 34 |
| `FactValueOverride` | 177 | 50 | 10 | 19 | 19 |
| `FactRemoveAction` | 51 | 20 | 7 | 7 | 6 |
| `RuleAddedAtom` | 96 | 25 | 9 | 6 | 8 |
| `RuleAddedAtomKind` | 5 | 3 | 2 | 0 | 1 |
| `RuleLiteralPath` | 109 | 28 | 10 | 8 | 8 |
| `engine_payload` | 110 | 37 | 9 | 9 | 15 |
| `AtomDescriptor` | 52 | 14 | 5 | 1 | 8 |
| `DiagnoseAtomLocator` | 82 | 24 | 4 | 5 | 15 |
| `WhyNotAtomLocator` | 50 | 16 | 4 | 2 | 10 |
| `ProofFrameAtomVerdict` | 83 | 28 | 9 | 10 | 9 |
| `_atom_index_from_key` | 6 | 3 | 1 | 0 | 2 |
| `atom_index` | 380 | 74 | 23 | 19 | 29 |
| `materialized_atom_index` | 23 | 9 | 1 | 2 | 6 |
| `atom_bounds` | 152 | 26 | 4 | 1 | 21 |
| `atom_key` | 240 | 60 | 17 | 18 | 18 |
| `branch_index` | 630 | 113 | 30 | 31 | 46 |
| `runtime_branch_index` | 9 | 4 | 1 | 1 | 2 |
| WhyNot green partition wording | 519 | 220 | 5 | 7 | 200 |
| WhyNot red partition wording | 379 | 105 | 4 | 11 | 81 |

Feasibility notes:

- The top-level class renames (`SupportArtifact` to `ProofReceipt`,
  `EvaluationOverlay` to `FactOverlay`, `FactValueOverride` to `ReplaceFact`,
  `FactRemoveAction` to `RemoveFact`) are mechanically feasible, but the blast
  radius is large. `SupportArtifact` alone crosses core store support capture,
  application protocol DTOs, SDK result surfaces, tests, and historical design
  records.
- `engine_payload` to `proof` is not only a cosmetic field rename. It appears in
  protocol DTOs and evidence envelopes. A hard-cut needs a compatibility decision
  for any serialized round events, recorded result payloads, or application
  protocol records that may be loaded by older consumers.
- The atom to condition cascade is broad and deep. `atom_index`, `atom_key`, and
  `_atom_index_from_key` participate in locator parsing, proof frame diagnostics,
  and support key conventions. This cannot be treated as a simple text rename
  unless the decision explicitly says whether durable key strings change.
- The branch to case cascade is the highest-risk part of Batch B. `branch_index`
  appears in DTO fields, walker state, support capture, evaluation rows, tests,
  and docs. Changing it to `case_index` may improve language, but it may also
  alter wire payload names and diagnostic key material.
- The WhyNot green/red wording counts are noisy because "green" and "red" appear
  broadly in documentation. The implementation should target WhyNot partitions
  and row types only, not every color mention.

Hidden dependencies and possible blockers:

- `b{branch}.a{atom}` style diagnostic keys and support artifact paths may be
  externalized in audit records or saved explanation payloads. If those strings
  change, this is a wire/persistence behavior change.
- `branch_index` and `atom_index` are likely part of structured JSON payloads
  returned from application protocols. The decision must specify hard-cut versus
  compatibility alias behavior for incoming records and fixture data.
- `atom_bounds` overlaps semantics terminology and should not be blindly renamed
  everywhere. Some occurrences may still belong to engine semantics rather than
  rule condition wording.

Test/doc estimate:

- Tests: large, roughly 50+ files before historical carve-outs.
- Docs/current examples: large, likely 40+ current or semi-current files, plus
  many historical workflow hits that should remain untouched.

Recommendation:

- Do not lock Batch B as a single implementation batch. Split it into:
  1. safe public type/class renames with current-doc updates;
  2. protocol field and wire alias decisions for `engine_payload`,
     `branch_index`, `atom_index`, `atom_key`, and related locator fields;
  3. WhyNot status wording cleanup with a narrow target list.

## §4 Batch C Audit - Module 3 Legacy SDK Flat Shells Hard-Cut

Risk: Yellow, with one required internal-refactor precondition.

| Flat shell | Call hits | Files | Src files | Test files | Notes |
|---|---:|---:|---:|---:|---|
| `fg.check(...)` | 5 | 2 | 0 | 0 | Mostly workflow docs. |
| `fg.diagnose(...)` | 2 | 1 | 0 | 0 | Mostly workflow docs. |
| `fg.why_not(...)` | 3 | 3 | 0 | 0 | Mostly workflow docs. |
| `fg.evaluate(...)` | 17 | 7 | 1 | 0 | One source/internal-style call. |
| `fg.run(...)` | 62 | 14 | 1 | 1 | Mixed docs and tests. |
| `fg.accept(...)` | 1 | 1 | 0 | 0 | Minimal callsite use. |
| `fg.accept_many(...)` | 1 | 1 | 0 | 0 | Minimal callsite use. |
| `fg.explain(...)` | 0 | 0 | 0 | 0 | Shell exists, direct calls absent. |
| `fg.explain_fact(...)` | 0 | 0 | 0 | 0 | Shell exists, direct calls absent. |
| `fg.conflicts(...)` | 0 | 0 | 0 | 0 | Shell exists, direct calls absent. |
| `fg.check_fact_overlay(...)` | 0 | 0 | 0 | 0 | Shell exists, direct calls absent. |
| `fg.recheck_proof_frame(...)` | 0 | 0 | 0 | 0 | Shell exists, direct calls absent. |
| `fg.check_rule_disable(...)` | 0 | 0 | 0 | 0 | Shell exists, direct calls absent. |
| `fg.check_rule_literal_replace(...)` | 0 | 0 | 0 | 0 | Shell exists, direct calls absent. |
| `fg.check_rule_add_condition(...)` | 0 | 0 | 0 | 0 | Shell exists, direct calls absent. |
| `fg.diff_proof_frames(...)` | 2 | 2 | 0 | 1 | One test uses the shell. |
| `fg.inspect_rule(...)` | 0 | 0 | 0 | 0 | Shell exists, direct calls absent. |
| `fg.inspect_semantics(...)` | 0 | 0 | 0 | 0 | Shell exists, direct calls absent. |
| `fg.validate_provenance(...)` | 0 | 0 | 0 | 0 | Shell exists, direct calls absent. |
| `fg.commit_assertions(...)` | 37 | 12 | 6 | 3 | Real internal and test use. |
| `fg.ingest(...)` | 2 | 2 | 0 | 1 | Low callsite count. |

Feasibility notes:

- User callsite blast is smaller than the number of shell definitions suggests.
  Many shell methods are already unused outside docs.
- The hidden dependency is internal delegation. Namespaced managers currently
  delegate into flat `SDKStore` methods for several advanced operations. A hard
  delete cannot simply remove the flat methods; implementation must first move
  bodies into private helpers or into the namespaced manager methods, then delete
  public shells.
- `commit_assertions` is not just a legacy ergonomic shell. It has real source
  usage and likely needs either a private helper extraction or a narrower
  decision on whether it is part of this hard-cut.

API contract impact:

- No known persistence schema impact from deleting shell methods.
- High API break at SDK boundary by design.
- Internal source callsites must be remediated before deletion to avoid
  namespaced managers depending on deleted public shells.

Recommendation:

- Feasible as its own hard-cut slice after a manager/private-helper refactor
  plan. Do not merge it into the same commit sequence as Batch B or F.

## §5 Batch D Audit - Module 4 Persistence

Risk: Yellow.

| Identifier / surface | Hits | Files | Src files | Test files | Docs/workflow files |
|---|---:|---:|---:|---:|---:|
| `fg.save(...)` call shape | 166 | 39 | 7 | 5 | 27 |
| `def save` | 3 | 3 | 3 | 0 | 0 |
| `FactGraph.load(...)` | 115 | 34 | 9 | 4 | 21 |
| `def load` | 2 | 2 | 2 | 0 | 0 |
| `save_workspace` | 14 | 9 | 4 | 1 | 4 |
| `load_workspace` | 10 | 8 | 4 | 1 | 3 |

Feasibility notes:

- The target names already exist in limited form, so there is no naming conflict.
- The rename is public and visible, but the implementation is localized compared
  with B/E/F.
- `SDKStore.save`, batch save behavior, and `FactGraph.load` all need consistent
  treatment. If the lock is hard-cut, docs/tests must remove old names. If the
  lock allows aliases, deprecation tests are needed.

API contract impact:

- Workspace file format should remain unchanged if only method names change.
- Persistence schema digests are not expected to change.

Recommendation:

- Feasible as an early low-to-medium risk slice, ideally paired with Batch A or
  implemented alone.

## §6 Batch E Audit - Module 5 Inference And Rule Renames

Risk: Red if locked as a full hard-cut; Yellow only if split and scoped.

| Identifier / surface | Hits | Files | Src files | Test files | Docs/workflow files |
|---|---:|---:|---:|---:|---:|
| Exact `Inference.Branch` | 0 | 0 | 0 | 0 | 0 |
| `class Branch` | 2 | 2 | 1 | 0 | 1 |
| `class Case` | 0 | 0 | 0 | 0 | 0 |
| `.where(...)` call shape | 398 | 57 | 8 | 10 | 36 |
| `def where` | 12 | 5 | 2 | 0 | 3 |
| `.when(...)` / `def when` | 0 | 0 | 0 | 0 | 0 |
| `head_vars` | 291 | 87 | 39 | 18 | 29 |
| Inference `target` keyword/field estimate | 229 | 97 | 27 | 27 | 33 |
| `emits` | 182 | 94 | 9 | 4 | 81 |
| `Not(...)` | 23 | 11 | 6 | 0 | 4 |

Feasibility notes:

- `Inference.Branch` as a dotted expression is absent, but a standalone `Branch`
  DSL class exists and is exported. Renaming to `Case` has no direct naming
  conflict, but import/export surfaces and docs must move together.
- `where` to `when` is broad and affects both Rule and Inference DSL surfaces.
  There is no existing `when` implementation, which is good, but a hard-cut will
  touch many tests, examples, docs, and possibly query-style language.
- `target` is a noisy term in the repo. The implementation must scope to
  Inference DSL and protocol fields rather than all target-like variables.
- `head_vars` is broad enough to require a dedicated migration plan. The
  replacement `Inference.emits` already appears in unrelated docs and language,
  so grep counts for the new word are not a blocker but are not proof of shipped
  support either.
- `Not(condition)` syntax appears present in source and docs. The feasibility
  task should treat this as verification and docs polish, not a risky rename.

Hidden dependencies:

- Rule and Inference share naming concepts but have different compatibility
  needs. The decision says `Inference.target + head_vars` becomes
  `Inference.emits` only, while `Rule` target/head semantics are not renamed.
  The implementation must avoid accidentally renaming Rule internals.
- If `where` changes on both Rule and Inference, examples and tests that teach
  query syntax will all need to move in the same slice.

Recommendation:

- Split into a dedicated Rule/Inference naming slice. Before locking, specify
  whether old `.where(...)` remains as an alias temporarily or is a hard-cut. A
  hard-cut is feasible but high blast radius.

## §7 Batch F Audit - Module 6 Semantics To Engine Config

Risk: Red.

| Identifier / surface | Hits | Files | Src files | Test files | Docs/workflow files |
|---|---:|---:|---:|---:|---:|
| `ProbLogSemantics` | 203 | 61 | 12 | 13 | 36 |
| `PyReasonSemantics` | 306 | 69 | 12 | 14 | 43 |
| `SemanticsProfile` | 842 | 129 | 31 | 16 | 82 |
| `branch_probabilities` | 135 | 38 | 10 | 5 | 22 |
| `branch_bounds` | 196 | 36 | 10 | 2 | 24 |
| `head_bound` | 214 | 46 | 10 | 6 | 30 |
| `semantics=` keyword estimate | 206 | 52 | 10 | 4 | 38 |
| Existing `config=` keyword estimate | 86 | 31 | 17 | 6 | 7 |
| `fg.eval.inspect_semantics` / `inspect_semantics` | 60 | 29 | 4 | 2 | 23 |
| `preview_config` | 0 | 0 | 0 | 0 | 0 |
| `EngineProfile` | 0 | 0 | 0 | 0 | 0 |
| `ProbLogConfig` | 0 | 0 | 0 | 0 | 0 |
| `PyReasonConfig` | 0 | 0 | 0 | 0 | 0 |
| `case_probabilities` | 0 | 0 | 0 | 0 | 0 |
| `case_bounds` | 0 | 0 | 0 | 0 | 0 |

Feasibility notes:

- The target names are mostly free, which reduces naming conflict risk.
- The blast radius is large. `SemanticsProfile` is a core concept and appears in
  SDK wrappers, engine adapters, evaluate result protocols, docs, and historical
  design records.
- `semantics=` to `config=` is user-visible and potentially confusing because
  `config=` already exists in unrelated code. That is not a direct conflict, but
  it makes grep validation and docs harder.
- `branch_probabilities` and `branch_bounds` are engine payload fields. Renaming
  them to `case_probabilities` and `case_bounds` has the same wire compatibility
  concern as Batch B branch/case fields.
- Legacy `head_bound` cleanup should be handled as a removal or normalization
  decision, not a simple rename. Some occurrences are likely part of adapter
  projection semantics.
- `inspect_semantics` to `preview_config` is feasible, but it depends on whether
  the rest of the eval namespace has already moved to config naming.

API, wire, and persistence impact:

- Evaluate result payloads include semantic/config information and digest fields.
  The decision must specify whether `semantics_digest` or other serialized names
  change. Renaming public classes without changing stored digest keys is feasible
  but must be explicit.
- Adapter-facing payload fields may be consumed outside the SDK layer. A hard-cut
  without alias support is high risk.

Recommendation:

- Do not lock Batch F as part of a single naming polish implementation. It needs
  a separate engine-config decision or a sub-decision inside Q-NAMING that
  defines alias/digest/wire compatibility.

## §8 Cross-Batch Risk Summary

Upper-bound affected-file estimate by batch, before de-duplicating overlaps:

| Batch | Aggregate hits | Aggregate files | Src files | Test files | Docs/workflow files | Risk |
|---|---:|---:|---:|---:|---:|---|
| A Assertions | 800 | 146 | 25 | 8 | 108 | Yellow |
| B Advanced type cascade | 3726 | 331 | 70 | 54 | 194 | Red |
| C Flat shell hard-cut | 132 | 33 | 4 | 2 | 27 | Yellow |
| D Persistence | 299 | 43 | 9 | 5 | 29 | Yellow |
| E Inference/Rule naming | 358 | 115 | 41 | 18 | 55 | Red |
| F Semantics/Engine config | 1956 | 155 | 34 | 22 | 97 | Red |

Blockers or lock-time risks found:

1. Batch B branch/atom cascades are not merely naming. They likely touch
   structured protocol fields, diagnostic key strings, support capture paths, and
   possibly recorded payloads.
2. Batch F semantics/config renames touch core profile classes, adapter payloads,
   evaluate protocols, and digest naming. The lock must define compatibility
   behavior before implementation.
3. Batch E `.where(...)` to `.when(...)` is broad and public. It is feasible, but
   alias versus hard-cut must be decided before scope freeze.
4. Batch C has low external callsite counts, but many namespaced managers delegate
   to flat shell implementations. Hard-cut requires internal helper extraction or
   manager-owned implementations first.
5. Batch A `by_ids(strict=True)` is additive but must be implemented on every
   public by-ids surface, not only the top-level assertions manager.

Recommended changes to the decision matrix before lock:

- Do not lock A-F as one implementation slice. The combined matrix is too large
  and mixes simple public SDK polish with high-risk wire/protocol language
  changes.
- Mark B and F as requiring explicit wire/persistence compatibility decisions.
- Mark C as requiring an internal delegation refactor before shell deletion.
- Mark E as requiring a hard-cut versus compatibility-alias decision for
  `.where(...)`.
- Allow historical workflow/archive references to remain untouched unless the
  decision specifically targets historical wording.

## §9 Recommended Implementation Sequence

Recommended split if the user wants high confidence and reviewable commits:

1. Q-NAMING-A/D public SDK naming polish:
   `fg.views` to `fg.assertion_views`, `FrozenAssertionView` to
   `FrozenAssertionSet`, `by_ids(strict=True)`, and persistence
   `save_workspace` / `load_workspace`. This is the smallest useful slice.
2. Q-NAMING-C flat shell hard-cut:
   first extract private implementation helpers or move bodies into namespaced
   managers, then delete the public flat shells and migrate docs/tests.
3. Q-NAMING-E Rule/Inference DSL naming:
   `Branch` to `Case`, `where` to `when`, and Inference `emits`, with explicit
   alias policy.
4. Q-NAMING-B1 safe advanced type/class renames:
   rename high-level DTO classes that do not alter wire field names.
5. Q-NAMING-B2 branch/atom to case/condition field/key migration:
   proceed only after the decision defines old-field alias support and diagnostic
   key compatibility.
6. Q-NAMING-F engine config rename:
   proceed after the profile/digest/adapter compatibility decision is locked.

If the user still wants one Q-NAMING decision document, the decision should
record these as separate implementation phases with explicit stop gates before
B2 and F.

## §10 Verification

Verification performed for this doc-only audit branch:

- `python -m compileall -q src`: clean.
- `git diff --check`: clean.
- Q-PR1 sacred paths against `4c472b50..HEAD`: 0 diff.
- `master`: remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline: preserved; existing working-tree changes remain untouched,
  including dirty notebooks and unrelated deleted `.gitkeep` entries.
- No runtime/test/doc-site files changed by this audit.
- No push performed.

