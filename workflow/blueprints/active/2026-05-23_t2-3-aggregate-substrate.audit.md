# Task Blueprint Audit: T2.3 — AggregateExpr substrate (IR + Python eval + SDK ergonomic)

- Status: draft
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: paired blueprint audit log
- Inputs:
  - [2026-05-23_t2-3-aggregate-substrate.md](./2026-05-23_t2-3-aggregate-substrate.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md)
  - [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md)
  - Archived T2.2 [2026-05-23_t2-2-arith-expr.md](../archive/2026-05-23_t2-2-arith-expr.md)
  - Archived T1.1 [2026-05-22_t1-1-rule-class-additive.md](../archive/2026-05-22_t1-1-rule-class-additive.md)
- Blueprint: [2026-05-23_t2-3-aggregate-substrate.md](./2026-05-23_t2-3-aggregate-substrate.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-23 | draft | Blueprint created | T2 Track 3rd sub-slice (after T2.1 ne adapter dispatch + T2.2 ArithExpr substrate). 100% genuinely new substrate (verified via G2 source-grep). Class assessment: S with documented size override. |

## Decision Notes

### 2026-05-23 — Initial scope lock

- T2.3 is the T2 Track closing slice (Atom 语言闭合 final piece) — adds AggregateExpr substrate net-new.
- G2 audit confirms shipped Aggregate substrate empty: `where_ast.py` no AggregateAtom, no `_AGGREGATE_KINDS`; `where_ast_validate.py` no aggregate validation; `where_eval.py` no aggregate eval; adapters no aggregate dispatch.
- Parent essay §10.6.3-§10.6.9 + §8.8 fully lock C99-C105 semantics — no load-bearing decision pending.
- Scope narrowed to **substrate + Python eval + SDK ergonomic + bridge passthrough**. Adapter wires (Souffle aggregate body / ProbLog findall) deferred to T2.3.b and T2.3.c follow-up sub-slices.

### 2026-05-23 — S vs M class assessment

User explicitly flagged this slice as S → 可能 M during T2.2 review:
> "T2.3 AggregateExpr | S → 可能 M | C99-C105 7 commitments 紧耦合 + AggregateExpr 是 100% genuinely new;若 impl 期出现 cross-commitment 决策点 → 升 M"

Drafter assessment for S-class with size override:

| Factor | T2.3 reality | Trigger fire? |
|---|---|---|
| Public API rename / replacement | None | No |
| Cross-commitment Q load-bearing | None — parent essay fully locks C99-C105 | No |
| Design vs shipped ≥ 3 commitments conflict | No conflict — 100% genuinely new additive | No |
| Sub-slice count vs Track plan §2 prediction | Track plan §2 listed T2.3 as one row | Within prediction |
| Public API impact | None / internal substrate | No |
| Cross-commitment 复杂度 | High (C99-C105 interrelated) — but no load-bearing decision needed | Triggers vs no decision needed = no fire |
| Size budget | ~1160 LOC est — 4x above ~300 LOC S guideline | Size flags concern, not a hard trigger |

**Conclusion**: §1.2.4 trigger conditions do not fire. Size is the only S-class concern. Drafter recommends S-class with size override + escalation contingency.

If reviewer disagrees on size, blueprint §5.10 prepares two-way split:
- T2.3.a: IR + validation + Python eval + tests (~400 LOC)
- T2.3.b: SDK ergonomic + bridge passthrough + tests (~250 LOC)

This split keeps each piece comfortably within S budget.

### 2026-05-23 — G1-G7 visible gate mapping

- **G1** — Blueprint §1 + §2 cite parent essay §10.6.3-§10.6.9 (C99-C105) + §8.8 explicitly. Every §2 sub-goal headers reference a C-number.
- **G2** — Blueprint §4 documents complete G2 source-grep audit across 6 files (where_ast / where_ast_validate / where_eval / sdk dsl expr / sdk dsl application_rule / application protocol rule). Verified all empty.
- **G3** — Blueprint §4 uses file:line citations (where_ast.py:31 / :77 / :95-96; where_ast_validate.py:33-34; where_eval.py:38; sdk/dsl/expr.py specific function locations; application/protocol/rule.py:_ALLOWED_ATOM_TYPES).
- **G4** — Blueprint §2 sub-goals 2.1-2.10 each labeled with C-number or specific responsibility (2.10 is bridge passthrough; 2.11 is allowlist verification).
- **G5** — Blueprint §3 Non-goals explicitly lists 10 deferred items with rationale and where each lands (T2.3.b / T2.3.c / parent essay extension candidate / parent §10.5 deferred).
- **G6** — Reviewer should independently spot-check: (1) `_BUILTIN_TAGS` contents at where_ast.py:96, (2) absence of AggregateAtom in where_ast.py, (3) absence of aggregate eval in where_eval.py, (4) T1.1 archived `_ALLOWED_ATOM_TYPES` unchanged by T2.3 scope, (5) parent essay §10.6.3-§10.6.9 semantic completeness (no ambiguity demanding decision doc).
- **G7** — Blueprint §5.8 lists 5 pre-impl precondition checks. Check #5 specifically gates S → M escalation if C99-C105 semantic ambiguity surfaces.

### 2026-05-23 — Cross-slice contract preservation

- T1.1 `_ALLOWED_ATOM_TYPES` MUST stay `(PredAtom, CmpAtom, InAtom, BuiltinAtom, NotAtom)` — AggregateAtom is Term-position, not top-level Atom. Verified by §2.11, §4.6, §5.7, §6 invariant, §7 acceptance.
- T1.2 bridge passthrough chain (`lower_where → parse_where_ir_to_ast → application Rule construction`) handles new IR kinds automatically. T2.3 only extends `_serialize_term` + `_collect_term_vars` for AggregateAtom (content_digest correctness). No behavioral change to existing bridge logic.
- T2.1 ne adapter dispatch unchanged (no adapter touched in T2.3).
- T2.2 ArithExpr substrate unchanged (`_ARITH_KINDS` not modified, `_BUILTIN_TAGS` not extended).
- ProbLog hygiene boundary unchanged (no `audit/round_events.py` touched).
- meta-confidence fixture cleanup unchanged (no test fixtures touched in T2.3 production code path).

### 2026-05-23 — Reviewer attention points

Per user's Step 4.2 review focus areas:

1. **C99-C105 拆为 S-class substrate vs 升 M with decision doc**: drafter chose S-class with size override. Reviewer should verify §1.2.4 triggers truly don't fire OR push for M / split if size-only concern warrants.
2. **三端语义一致性**: T2.3 scope intentionally excludes Souffle / ProbLog wires (deferred to T2.3.b / T2.3.c). Python eval is the only "end" landing in this slice. Reviewer should accept this split or push for inclusion.
3. **G7 gate verifying shipped substrate empty + semantic boundaries**: §5.8 5 checks. Verify check #5 is sufficient to catch C99-C105 ambiguity before impl.

### 2026-05-23 — Potential reviewer P-finding candidates

Drafter anticipates these as likely review points:

- **Size override**: 1160 LOC vs 300 LOC S guideline is real. Reviewer may P1 require split into T2.3.a + T2.3.b before scoped anchor.
- **NoValue propagation tests**: §5.9 lists tests but should explicitly include "NoValue inside ArithExpr operand → result NoValue" cross-T2.2 interaction test. Drafter included this in mental list but may not be explicit enough in §5.9 test outline.
- **C104 variable scoping algorithm specifics**: §5.3 shows skeleton but doesn't fully spec the algorithm. Reviewer may require tightening on "exactly when a Var is considered aggregate-local vs correlated".
- **AggregateAtom inside CmpAtom serialization for content_digest**: §5.6 covers `_serialize_term` extension but does not specify ordering/canonicalization for filter atoms within serialized aggregate. Reviewer may P1 require explicit canonical ordering.
