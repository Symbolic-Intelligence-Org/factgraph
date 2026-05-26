# Audit: Quickstart WHY-Explanation Batch Fix

- Status: scoped
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_quickstart-why-explanation-batch-fix.md`
- Stage: scoped
- Class: M (predicted; may escalate L)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: 6 modified + 1 untracked preserved
- Ownership: self-owned (Claude as both owner and reviewer; Codex on parallel work)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | scoped | pending | Blueprint pair drafted with 21-finding inventory pre-locked | Self-owned cycle. Source inventory from sub-agent audit `acbc5b94ba313ef05`. C110 anchor home pre-decided: new §"Canonical quantitative carrier" in `assertions.md`; `semantics.md` + `evidence.md` cross-link forward. |

## 2. Source Reads

| Source | Reason |
|---|---|
| Sub-agent audit output `/private/tmp/.../acbc5b94ba313ef05.output` | 26 findings; 21 in scope (High + Medium), 5 deferred (Low). |
| `rule-expression-and-proof-attempt.zh.md` §3.10 + C9 + C81 + C110 + C111 + C113 | Inference legacy/compat status; RuleRef rejection by build_application_rule; closed-head distinction; quantitative carrier contract; deterministic carrier convention; no-double-write rule. |
| `evidence-tree-rainbird-style-v1.zh.md` §2 / §2.3 / §3.1 / O3 / O8 | EvidenceGraph DAG invariants; EvidenceRef Rainbird factID equivalence; stateless evaluation rationale; cycle detection. |
| `database-view-fg-layered-architecture.zh.md` §3.1 / §6.3 / I4-I6 / I12 / A2 / A15 / §17 | FactGraph runtime / Database persistent write boundary; attach must not have rules=; schema migration deferred. |
| `src/factgraph/sdk/__init__.py` | `Rule` / `Inference` / `build_application_rule` / `RuleRef` public exports. |
| `src/factgraph/sdk/dsl/application_rule.py:46-82` | `build_application_rule` factory: lowers SDK DSL → Rule, validates AND-only body, canonicalizes Vars, rejects Branch/OR/legacy Pred-raw/legacy AttrRef. |
| `src/factgraph/application/protocol/rule.py:53` | `Rule` frozen dataclass: `where: tuple[Atom, ...]`, `ports: Mapping[str, Var]`. |
| `src/factgraph/sdk/store.py:1078-1114` | `FactGraph.attach(...)` signature (no `rules=`). |
| `src/factgraph/core/store/database.py:478-512` | `Database.create_view(...)` only (no update/delete/get/list). |

## 3. Initial Inventory

The 26 sub-agent findings were classified by severity. 21 in scope (8 High + 13 Medium). 5 deferred Low.

| Severity | Count | Treatment |
|---|---|---|
| **High** | 8 | All in scope. User-blocking. |
| **Medium** | 13 | All in scope. Same-file batch with High where possible. |
| **Low** | 5 | Deferred to future polish cycle. Listed in §9 below. |
| **Cross-cutting** | 1 (C110) | In scope. New named section in `assertions.md`. |

## 4. Step 4.6 Scoped Inventory Plan

Pre-implementation inventory locked inline below in §5. Self-owned cycle means survey is done before draft.

## 5. Step 4.6 Scoped Inventory Results

For each finding, the audit lock includes: source/design-doc citation, current file location, severity, action.

### F-table (in-scope findings, 21 + 1 cross-cutting)

| # | File | Lines | Severity | Concept | Source citation | Action |
|---|---|---|---|---|---|---|
| F1 | first-factgraph.md | 16-30 | H | `Identity(primary_key=True)` semantics | schema.md:9-17 (existing) | Add 1-sentence forward pointer to schema.md §"Multi-field identity" + clarifying note |
| F2 | first-factgraph.md | 38-46 | M | schema_classes compile relationship | database.md §"Define a schema IR" table (existing) | 2-sentence forward pointer |
| F3 | schema.md | 36-46 | M | `Identity(default="en")` ref-construction-time semantics | Code at `src/factgraph/sdk/entity.py` Identity default behavior | 1-paragraph clarification |
| F4 | schema.md | 222-249 | M | `schema.add` additive-only as named deferred boundary | `database-view-fg-layered-architecture.zh.md` §6.3 + §17 | 1-paragraph "deferred by design" framing |
| F5 | read-write.md | 36-43 | M | `idref_v1` token nature anchor | Code at idref generation; cross-file recurrence | Short paragraph naming opaque-token + non-parseable invariant |
| F6 | read-write.md | 117-149 | M | Retract as append-only WHY | `evidence-tree-rainbird-style-v1.zh.md` §3.1 + O3 (stateless evaluation) | Short paragraph linking append-only to evidence reproducibility |
| **F7** | **assertions.md** | **148-214** | **H** | **C110 canonical quantitative carrier — NEW §** | parent C110 + C113 + `src/factgraph/core/store/assertion_record.py` | **NEW §"Canonical quantitative carrier" subsection (~50 LOC); names the contract; becomes C110 anchor for F17/F19 cross-links** |
| F8 | assertions.md | 200-203 | H | `shared/semantic/raw_kind`/`bound` annotation mirror lanes | parent C110 + code at meta-row write path | 1-paragraph explanation: what lanes are, when populated, why mirror invariant |
| F9 | assertions.md | 472-488 | H | Frozen views WHY (session-scoped, not persisted) | database.md immutability rationale (already shipped); contrast with durable view | 1-paragraph contrast |
| F10 | assertions.md | 218-239 | M | `probability` / `bound_lower` / `bound_upper` key rejection framing | parent C113 (no-double-write) | Rewrite rejection text to name C113 anti-double-write |
| **F11** | **rules-and-inferences.md** | **27-78** | **H** | **`Rule` + `Inference` + `build_application_rule` co-existence** | `src/factgraph/sdk/dsl/application_rule.py:46-82` + parent C1/C9 | **NEW short subsection "Why build_application_rule instead of Rule(...)"; high-level-factory vs low-level-data-shape framing** |
| F12 | rules-and-inferences.md | 429-457 | H | `Inference` legacy/compat label | parent §3.10 (Inference is v0.2 compat) + track-plan T5 | Add explicit "v0.2 compatibility surface" callout at Inference intro |
| F13 | rules-and-inferences.md | 495-509 | H | `RuleRef` anchor | parent C9 (no Rule-in-Rule); `build_application_rule` reject | 1-paragraph: RuleRef is for future Rule-in-Rule, rejected by build_application_rule(C9) in v0.2 |
| F14 | rules-and-inferences.md | 322-402 | M | `head=` invariants → closed-head naming | parent C72 / C81 / evidence.md §3.1 closed_head | 1-paragraph naming closed-head/open-head distinction |
| F15 | semantics.md | 19-30 | M | `SemanticsProfile` vs wrappers relationship | `inspect_semantics` `lowered_profile` field; code at SemanticsProfile lowering | Add explicit table or paragraph (same pattern as schema_classes/schema_ir) |
| F16 | semantics.md | 149-154 | M | `branch_probabilities` / `branch_bounds` single-Rule rejection | parent C1/C2 (AND-only body); Inference/RuleExpr is OR concept | 1-paragraph naming AND-only body invariant for Rule |
| F17 | semantics.md | 175-195 | M | `raw_kind` / `bound` row propagation | parent C110 + C111 | **Cross-link to F7 C110 anchor; do NOT duplicate contract** |
| F18 | evidence.md | 232-242 | M | `EvidenceGraph` "deferred" → named invariants | `evidence-tree-rainbird-style-v1.zh.md` O1/O8 + §10/§11 | Name locked invariants + "intentionally opaque until §10/§11" framing |
| F19 | evidence.md | 76-94 | M | DetachedRow contract clarification | parent essay §5.8.3 (programming error, not failure_class) | 1-paragraph distinguishing DetachedRowError from `status="failed"` rows; **cross-link to F7 C110 anchor** for raw_kind/bound on rows |
| F20 | persistence.md | 132-145 | M | Durable views as separate surface relationship | `database-view-fg-layered-architecture.zh.md` I4-I6 | Add explicit runtime-vs-persistent boundary cross-link sentence |
| F21 | namespace-map.md | 130-138 | H | `fg.inferences` "(empty namespace)" WHY | parent §3.10 + track-plan T5 | 1-paragraph: compatibility placeholder for v0.2 → RuleExpr-runtime fold |
| F22 | namespace-map.md | 67-75 | M | `FactGraph.attach(...)` signature must NOT contain `rules=` | `database-view-fg-layered-architecture.zh.md` I12 + A15 | Add note citing I12/A15 |
| F23 | namespace-map.md | 19-58 | M | Namespace principles owner anchor | `database-view-fg-layered-architecture.zh.md` §3.1 + A2 | Anchor principles to FactGraph-runtime / Database-write boundary |
| **C110** | **assertions.md** | **NEW §** | **H** | **Canonical quantitative carrier anchor** | parent C110 + C111 + C113 | **New §"Canonical quantitative carrier" subsection (placed after raw_kind/bound intro paragraphs, before per-key reject tables); F17 + F19 + F10 cross-link in** |

### Cross-link map (no duplication)

```
assertions.md §"Canonical quantitative carrier"  (CANONICAL anchor; F7)
   ↑ cross-link from semantics.md §"raw_kind / bound row propagation"  (F17)
   ↑ cross-link from evidence.md §"DetachedRow contract"  (F19)
   ↑ cross-link from assertions.md §"probability key rejection" (F10)

schema.md §"Multi-field identity"
   ↑ cross-link from first-factgraph.md  (F1)

database.md §"Define a schema IR" (existing table)
   ↑ cross-link from first-factgraph.md  (F2)

database.md §"Durable views are immutable" (existing, shipped via eff86ad0)
   ↑ cross-link from assertions.md §"Frozen views"  (F9)
   ↑ cross-link from persistence.md §"Durable views"  (F20)
```

### Scoped decisions

- C110 anchor home: **assertions.md** (write side; data invariant first surface).
- No new `concepts.md` page (avoid index sequence repack for one concept).
- 5 Low findings deferred:
  - schema.md "graph fact model / GNF" naming (L, B)
  - evidence.md `EvidenceRef` non-public-explanation-entry WHY (L, A)
  - persistence.md migration CLI design context (L, A)
  - namespace-map.md "what is not on this surface" deferred provenance (L, D)
  - schema.md additional low items if any
- Each finding's wording must cite the design-doc anchor as evidence; this audit lists those citations.
- Cross-links use GitHub-flavored markdown anchor conventions (`#canonical-quantitative-carrier`, lowercase hyphenated from `##`/`###` headings).

## 6. Verification Plan

- `git diff --check` clean.
- Diff stays within 8 quickstart files + blueprint pair (verifiable via `git diff --stat`).
- Each F# checkbox in blueprint §9 Acceptance checked off after implementation.
- 5 Low-severity files/sections NOT touched (verifiable in diff).
- Pre-existing 6 modified + 1 untracked dirty baseline preserved.
- Sacred master at `562c74195df43e933bed92a3ff25de94dd8ce666` unchanged.
- Manual spot-check: each High finding's text against source code anchor (e.g., F11 `build_application_rule` rejects at `application_rule.py:85-91`).
- Cross-link sanity: each `#anchor` referenced exists as a heading in the target file.

## 7. Review Checklist

- [x] Step 4.6 scoped inventory recorded before implementation.
- [ ] All 21 F# findings + C110 anchor land in single feat commit (or split if commit exceeds reasonable size).
- [ ] C110 anchor is the canonical source; no contract duplication in semantics.md or evidence.md.
- [ ] No production files touched; dirty baseline preserved.
- [ ] 5 Low findings explicitly NOT touched.
- [ ] No new public exports / module surface; no shipped-behavior changes.

## 8. Closure Notes

(Filled at closure.)

## 9. Deferred (Low-severity, out of scope)

| # | File | Concept | Why deferred |
|---|---|---|---|
| L1 | schema.md | "graph fact model / GNF" naming user-vs-internal vocabulary anchor | Polish-only; doc reads fine without anchor; revisit if user vocabulary debt expands |
| L2 | evidence.md | `EvidenceRef` not-public-explanation-entry WHY | Polish-only; current "not the entry point" wording is functional |
| L3 | persistence.md | Migration CLI design context (why CLI vs method) | Polish-only; CLI is rarely-touched operator path |
| L4 | namespace-map.md | "What is not on this surface" deferred provenance back-link | Polish-only; current deferral list is functional, just not provenance-anchored |
| L5 | (potential) future audit pass | Cross-cutting "Concepts" page consideration | Out of scope unless cross-cutting concepts beyond C110 emerge |
