# Task Blueprint: Quickstart WHY-Explanation Batch Fix

- Status: scoped
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Class: M (predicted; may escalate L)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Claude
- Reviewer: Claude (self-owned; Codex on parallel work)
- Related audit: `workflow/blueprints/active/2026-05-26_quickstart-why-explanation-batch-fix.audit.md`
- Audit source: general-purpose sub-agent report `acbc5b94ba313ef05` (audit run 2026-05-26)
- Reference cycles (recently shipped following same pattern):
  - `workflow/blueprints/archive/2026-05-26_quickstart-database-view-rebase-onto-t11-1.md` + Step 4.8 fixes `00029fdd` / `2c556189` / `eff86ad0`
- Related modules (read-only):
  - `src/factgraph/sdk/__init__.py`
  - `src/factgraph/application/protocol/rule.py`
  - `src/factgraph/sdk/dsl/application_rule.py`
  - `src/factgraph/core/store/database.py`
- Active design sources (read-only):
  - `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md`
  - `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md`
  - `workflow/design/design-points/active/database-view-fg-layered-architecture.zh.md`

## 0. Scope Locks

### In scope

Batch-fix 21 quickstart documentation gaps (8 High + 13 Medium severity) plus
the cross-cutting C110 canonical quantitative carrier anchor, across 8 files
under `docs/official/kernel/quickstart/`. Each finding is a "WHAT explained but
WHY not explained" pattern: the SDK enforces / structures something but the
doc doesn't name the design intent, the named invariant, or the
high-level-factory-vs-low-level-data-shape relationship.

### Per-file scope

| File | High | Medium | LoC est. |
|---|---|---|---|
| `first-factgraph.md` | 1 (Identity primary_key) | 1 (schema_classes compile) | ~30 |
| `schema.md` | 0 | 2 (default semantics; schema.add additive) | ~40 |
| `read-write.md` | 0 | 2 (idref_v1 token; retract append-only why) | ~40 |
| `assertions.md` | 3 (C110 anchor; annotation lanes; frozen views WHY) | 1 (probability key rejection) | ~120 (includes C110 §) |
| `rules-and-inferences.md` | 3 (Rule+Inference+build_application_rule; Inference legacy; RuleRef) | 1 (head invariants closed-head) | ~100 |
| `semantics.md` | 0 | 3 (wrappers→profile; branch_probabilities reject; raw_kind row propagation) | ~60 |
| `evidence.md` | 0 | 2 (EvidenceGraph deferred; DetachedRow contract) | ~40 |
| `persistence.md` | 0 | 1 (durable views surface relationship) | ~20 |
| `namespace-map.md` | 1 (fg.inferences empty namespace) | 2 (attach no rules=; namespace owner story) | ~40 |
| **Totals** | **8 H** | **13 M** | **~490 LOC** |

Plus the C110 anchor:

- **C110 home**: new §"Canonical quantitative carrier" subsection inside
  `assertions.md` (place after the existing `raw_kind`/`bound` introduction
  paragraphs, before the per-key reject tables).
- **C110 cross-links**: short `→ See [Canonical quantitative carrier](assertions.md#canonical-quantitative-carrier)`
  pointer added at the relevant `raw_kind`/`bound` mention in `semantics.md`
  and `evidence.md`.

### Out of scope

- 5 Low severity findings (GNF naming; EvidenceRef; migration CLI; namespace
  principles owner; "what is not on this surface" deferred provenance).
  Deferred to a future polish cycle.
- `database.md` (excluded from audit — heavily revised in the
  `quickstart-database-view-rebase-onto-t11-1` cycle + its Step 4.8 fixes).
- `index.md` (no findings above Low).
- Any production code edits.
- Introducing new API surface, renaming exports, or changing shipped
  behavior.
- New quickstart pages (no `concepts.md`).
- Pre-existing 6 M + 1 untracked dirty baseline must remain isolated.

### M-to-L / stop-and-amend triggers

Pause and amend if implementation requires:

- production code edits (any `.py` change);
- new public exports / new module surface;
- changing shipped error messages or behaviors to match documentation;
- introducing a new quickstart page (would escalate to L);
- discovering a finding's stated invariant does not actually exist in code
  (would require re-scoping that finding to "remove the stale claim" rather
  than "name the contract");
- expanded scope beyond the 21 enumerated findings (would re-open audit and
  re-scope).

## 1. Problem

A general-purpose sub-agent audit cross-referenced 9 quickstart files
against 4 active design-point documents and identified 26+ gaps where the
quickstart explains WHAT (signatures, examples, mechanics) but omits WHY
(design intent, named invariants, surface relationships, deferred-by-design
boundaries). Users encounter the gap in three forms:

1. **Real wall**: an operation they expect doesn't exist (e.g., "why can't
   I `update_view`?", "why does `build_application_rule` exist when I can
   import `Rule`?"); now resolved in `database.md` but the same pattern
   recurs in 7 other quickstart pages.
2. **Silent contract**: an invariant the SDK enforces but the user only
   discovers via cryptic errors (e.g., C110 canonical quantitative carrier:
   `(1.0, 1.0)` rejected, independent `probability` rejected, but no
   anchor explains the underlying rule).
3. **Lost provenance**: design decisions whose rationale lives only in the
   design-point docs, never surfaced in user-facing form (e.g.,
   `fg.inferences` empty namespace; durable view immutability rationale —
   the latter now fixed by `eff86ad0`).

This blueprint addresses 21 of those findings in one batch pass.

## 2. Inputs

| Source | Reason |
|---|---|
| Sub-agent audit report `acbc5b94ba313ef05` (2026-05-26) | Source inventory; 26 findings with severity + category + design-doc anchor citations. |
| `rule-expression-and-proof-attempt.zh.md` C9 / C110 / C111 / C81 / §3.10 | Named invariants for `RuleRef` rejection, canonical quantitative carrier, deterministic carrier convention, closed-head distinction, Inference legacy/compat status. |
| `evidence-tree-rainbird-style-v1.zh.md` §2 / §3.1 / O3 / O8 | EvidenceGraph DAG invariants; stateless evaluation rationale; Rainbird factID equivalence for EvidenceRef. |
| `database-view-fg-layered-architecture.zh.md` §3.1 / §6.3 / I12 / A2 / A15 / I4-I6 | FactGraph-runtime vs Database-persistent-write boundary; schema migration deferral; attach signature has no `rules=`. |
| `src/factgraph/sdk/__init__.py` exports | `Rule` / `Inference` / `build_application_rule` / `RuleRef` actual public surface. |
| `src/factgraph/sdk/dsl/application_rule.py:46-82` | `build_application_rule` factory body, lowering steps, validation rejects. |
| `src/factgraph/application/protocol/rule.py` | `Rule` frozen dataclass shape (core-Atom tuple `where`, `Mapping[str, Var]` ports). |

## 3. Proposed Shape — finding-by-finding

Each finding gets an edit. See §5 (audit Step 4.6 inventory) for the exact
anchor lines and proposed wording sketch.

### 3.1 first-factgraph.md

- **F1 (H)** Identity vs `primary_key=True` semantics. Add a one-sentence
  forward pointer to schema.md §"Multi-field identity" + a clarifying note
  that `primary_key=True` is one of potentially many Identity fields.
- **F2 (M)** schema_classes compile relationship. Two-sentence forward
  pointer to database.md §"Define a schema IR" table.

### 3.2 schema.md

- **F3 (M)** `Identity(default="en")` ref-construction-time semantics.
  One-paragraph clarification.
- **F4 (M)** `schema.add` additive-only as named deferred boundary.
  One-paragraph "deferred by design" framing with link to
  `database-view-fg-layered-architecture.zh.md` §6.3 / Deferred §17.

### 3.3 read-write.md

- **F5 (M)** `idref_v1` token nature anchor. Short paragraph naming the
  token as opaque + cross-link.
- **F6 (M)** Retract as append-only WHY. Short paragraph linking to
  audit/evidence reproducibility (O3 stateless evaluation).

### 3.4 assertions.md

- **F7 (H)** **C110 canonical quantitative carrier** — **new
  §"Canonical quantitative carrier" subsection (~50 LOC)**. Names the
  contract:
  - `raw_kind=None ⇔ bound=None` exactly;
  - Independent `probability` field rejected;
  - `(1.0, 1.0)` for deterministic rejected (deterministic = `None`/`None`);
  - 3 surfaces enforce this contract: write (assertions), evaluate
    (semantics), audit (evidence row + explanation).
  This subsection becomes the cross-link target for F12 / F14 / F19.
- **F8 (H)** `shared/semantic/raw_kind` / `bound` annotation mirror lanes.
  One-paragraph explanation: what the lanes are, when they're populated,
  why the mirror is invariant.
- **F9 (H)** Frozen views WHY (session-scoped, not persisted).
  One-paragraph contrast with durable view (database.md anchor): session
  views have no Database identity anchors and are intentionally outside
  workspace persistence + audit chain.
- **F10 (M)** `probability` / `bound_lower` / `bound_upper` key rejection
  framed as anti-double-write per C113.

### 3.5 rules-and-inferences.md

- **F11 (H)** `Rule` + `Inference` + `build_application_rule`
  co-existence — the user's earlier question. Add a short subsection
  "Why `build_application_rule` instead of `Rule(...)`" with the
  high-level-factory vs low-level-data-shape framing (same pattern as
  schema_classes-vs-schema_ir table in database.md). Clarify that
  `Rule` import is for type hints / `isinstance` checks; construction
  goes through `build_application_rule`.
- **F12 (H)** `Inference` legacy/compat label. Add an explicit "v0.2
  compatibility surface" callout where `Inference` is first introduced,
  with forward pointer to new-code preference (build_application_rule +
  RuleExpr).
- **F13 (H)** `RuleRef` anchor. Add one paragraph: `RuleRef` is the
  body-side raw atom for the future `Rule-in-Rule` composition, which
  is **rejected by `build_application_rule` (C9)** for v0.2 — included
  in the public surface for protocol completeness, not as a
  recommended construction.
- **F14 (M)** `head=` invariants → closed-head/open-head naming.
  Add one paragraph naming the closed-head distinction with link to
  `evidence.md` and parent design C81.

### 3.6 semantics.md

- **F15 (M)** `SemanticsProfile` vs wrapper relationship.
  Same C-pattern as schema_classes/schema_ir: add explicit table or
  paragraph showing `ProbLogSemantics(...)` / `PyReasonSemantics(...)`
  are user-facing wrappers that lower into the canonical
  `SemanticsProfile` (visible via `inspect_semantics` `lowered_profile`).
- **F16 (M)** `branch_probabilities` / `branch_bounds` rejection for
  single Rule. One-paragraph: application `Rule` has AND-only bodies
  per C1/C2, so no public branch ids; branch-specific config is an
  `Inference`/`RuleExpr` OR concept.
- **F17 (M)** `raw_kind` / `bound` row propagation → cross-link to
  C110 anchor in assertions.md.

### 3.7 evidence.md

- **F18 (M)** `EvidenceGraph` "deferred" → name the locked invariants
  (O1 cycle detection, O8 DAG with branch convergence, `engine_meta`
  namespace) and frame as "intentionally opaque until §10/§11
  implementation".
- **F19 (M)** Detached row contract clarification: `DetachedRowError`
  is a Python programming error per parent essay §5.8.3, NOT a
  `failure_class`; users should not catch it as a business case.

### 3.8 persistence.md

- **F20 (M)** Durable views as separate surface — add explicit cross-
  link sentence to database.md anchoring the runtime-vs-persistent
  boundary (I4-I6).

### 3.9 namespace-map.md

- **F21 (H)** `fg.inferences` empty namespace WHY. One-paragraph: it
  exists as a v0.2 compatibility placeholder for `Inference`-based
  authoring that will fold into RuleExpr-based runtime entry (parent
  §3.10 / track-plan T5).
- **F22 (M)** `FactGraph.attach(...)` signature must NOT contain
  `rules=`. Add note citing I12/A15: rules are code artifacts,
  `rule_set_digest` is evaluate-time, not attach-time.
- **F23 (M)** Namespace principles → anchor to
  `database-view-fg-layered-architecture.zh.md` §3.1 / A2 (FactGraph
  is runtime / Database is persistent write point).

## 4. Expected Code / Docs Changes

Docs-only:

- 8 quickstart files modified (~490 LOC total).
- `assertions.md` gains the **new §"Canonical quantitative carrier"
  subsection** (highest leverage, ~50 LOC).
- 2 cross-links from `semantics.md` and `evidence.md` to the C110 anchor.
- 8 forward / cross-reference pointers added between quickstart pages.

Plus blueprint pair + INVENTORY (after archive).

Zero production files. Zero src changes. Zero test changes.

## 5. Tests / Verification

No SDK smoke (pure docs cycle).

Verification:

- `git diff --check` clean.
- Diff stays within the 8 quickstart files + blueprint pair.
- Pre-existing 6 M + 1 untracked dirty baseline preserved end-to-end.
- Each cross-link target anchor resolves correctly (markdown anchor
  conventions for §"Canonical quantitative carrier" →
  `#canonical-quantitative-carrier`).
- Each finding ID (F1–F23) is checked off in the Acceptance list below.
- A spot-check that no surface claim contradicts shipped behavior
  (manual code reference where the design-doc claim could drift).

## 6. Risks

| Risk | Mitigation |
|---|---|
| Wording drift from shipped behavior | Each High-severity finding cites a source-code anchor; review claim text against that anchor. |
| Cross-link anchors break | Use GitHub-flavored markdown anchor conventions; verify each cross-link by anchor name in the same commit. |
| Adding too many "see also" links makes pages noisy | Keep cross-links to 1-2 per finding; do not duplicate explanations between pages — use the anchor target as the single source. |
| Inference legacy/compat callout creates new question "when will it be removed?" | Use the exact framing from parent essay §3.10 / track-plan T5 — "v0.2 compatibility surface, preferred for new code: build_application_rule + RuleExpr"; do not promise removal date. |
| C110 anchor placed in assertions.md but evaluate-side readers may not find it | Cross-link from `semantics.md` + `evidence.md` is mandatory; both sources mention raw_kind/bound and must link forward. |
| Scope creep into Low-severity findings as we touch files | Stay strict: only the 21 enumerated findings; record any newly-discovered gaps in audit Outcome as deferred. |

## 7. Implementation Plan

1. (this commit) Open scoped blueprint pair with 21-finding inventory
   + C110 anchor placement locked.
2. Apply edits file-by-file in one feat commit:
   1. assertions.md (F7-F10) — start here because §"Canonical
      quantitative carrier" anchor is dependency for F17 and F19
      cross-links.
   2. rules-and-inferences.md (F11-F14) — heavy file, build_application_rule
      explanation is the user's original question.
   3. namespace-map.md (F21-F23) — table additions.
   4. semantics.md (F15-F17) — wrappers→profile relationship + C110
      cross-link.
   5. evidence.md (F18-F19) — EvidenceGraph naming + DetachedRow contract
      + C110 cross-link.
   6. first-factgraph.md (F1-F2) — small.
   7. schema.md (F3-F4) — small.
   8. read-write.md (F5-F6) — small.
   9. persistence.md (F20) — single cross-link.
3. Self-review fresh-read pass.
4. Closure commit (mark blueprint implemented, fill Outcome).
5. Archive commit (move blueprint pair + update INVENTORY).

## 8. Reviewer Focus

Self-review must verify:

- C110 anchor (§"Canonical quantitative carrier") is the canonical source;
  semantics.md and evidence.md do not duplicate the contract — they
  cross-link.
- `Inference` legacy/compat callout matches parent §3.10 framing without
  promising a removal date.
- `RuleRef` paragraph is honest that `build_application_rule` rejects it
  (C9) and v0.2 does not support Rule-in-Rule composition.
- The "schema_classes vs schema_ir" / "wrappers vs SemanticsProfile" /
  "Rule vs build_application_rule" follow the same explanatory pattern
  (high-level-factory → low-level-data-shape table).
- No production file edits leak into the diff.
- 5 Low-severity findings explicitly NOT touched (verify in diff).

## 9. Acceptance

- [ ] F1: first-factgraph.md Identity primary_key forward pointer
- [ ] F2: first-factgraph.md schema_classes compile pointer
- [ ] F3: schema.md `Identity(default=)` semantics
- [ ] F4: schema.md `schema.add` deferred boundary
- [ ] F5: read-write.md `idref_v1` token anchor
- [ ] F6: read-write.md retract append-only WHY
- [ ] **F7**: assertions.md **new §"Canonical quantitative carrier"** (C110 anchor)
- [ ] F8: assertions.md annotation mirror lanes
- [ ] F9: assertions.md frozen views WHY
- [ ] F10: assertions.md probability/bound_* key rejection framing
- [ ] **F11**: rules-and-inferences.md Rule/build_application_rule subsection
- [ ] F12: rules-and-inferences.md Inference legacy/compat callout
- [ ] F13: rules-and-inferences.md RuleRef anchor
- [ ] F14: rules-and-inferences.md closed-head naming
- [ ] F15: semantics.md wrappers → SemanticsProfile relationship
- [ ] F16: semantics.md branch_probabilities single-Rule rejection
- [ ] F17: semantics.md raw_kind row propagation → C110 cross-link
- [ ] F18: evidence.md EvidenceGraph deferred → named invariants
- [ ] F19: evidence.md DetachedRow contract clarification
- [ ] F20: persistence.md durable views cross-link
- [ ] F21: namespace-map.md fg.inferences empty namespace WHY
- [ ] F22: namespace-map.md attach no rules= contract
- [ ] F23: namespace-map.md namespace principles owner anchor
- [ ] Diff stays within 8 quickstart files + blueprint pair.
- [ ] Dirty baseline preserved at 6 M + 1 untracked.
- [ ] Sacred master at `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged.
- [ ] 5 Low-severity findings NOT touched (verify in diff).

## 10. Outcome / Deviations

(Filled at closure.)
