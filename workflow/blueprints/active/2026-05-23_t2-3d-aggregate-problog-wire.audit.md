# Task Blueprint Audit: T2.3d — Aggregate ProbLog adapter wire

- Status: draft
- Created: 2026-05-23
- Last Updated: 2026-05-23 (draft)
- Authority: paired blueprint audit log
- Inputs:
  - [2026-05-23_t2-3d-aggregate-problog-wire.md](./2026-05-23_t2-3d-aggregate-problog-wire.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md)
  - [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md)
  - Archived T2.3a [2026-05-23_t2-3-aggregate-substrate.md](../archive/2026-05-23_t2-3-aggregate-substrate.md)
  - Archived T2.3b [2026-05-23_t2-3b-aggregate-sdk-bridge.md](../archive/2026-05-23_t2-3b-aggregate-sdk-bridge.md)
  - Archived T2.3c [2026-05-23_t2-3c-aggregate-souffle-wire.md](../archive/2026-05-23_t2-3c-aggregate-souffle-wire.md)
- Blueprint: [2026-05-23_t2-3d-aggregate-problog-wire.md](./2026-05-23_t2-3d-aggregate-problog-wire.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-23 | draft | Blueprint created | User-drafts / Claude-reviews pattern restored per T2.3c retrospective. T2.3d scope is ProbLog adapter-only aggregate wire over T2.3a substrate + T2.3b SDK + T2.3c query-variable extraction. No SDK/core/application/Souffle changes. |

## Decision Notes

### 2026-05-23 — Initial scope lock

- **T2.3d closes only ProbLog adapter aggregate export**. It does not revisit T2.3a substrate semantics, T2.3b SDK authoring, or T2.3c Souffle lowering.
- **ProbLog lowering strategy follows parent essay §8.8 / §1719**: `findall/3` + list predicates. There is no native aggregate operator analogous to Souffle.
- **Empty-set semantics mirror C101 without a sentinel object**:
  - count/sum emit 0 via `length` / `sum_list`
  - min/max/mean use `L = [_|_]` guard so empty set fails the enclosing rule body
- **Docs status flip is in scope** because existing docs explicitly defer ProbLog aggregates to T2.3.d.

### 2026-05-23 — S-class assessment

| Factor | T2.3d reality | Trigger |
|---|---|---|
| Public API impact | None; no new SDK symbol | No |
| Core/substrate change | None; consumes T2.3a unchanged | No |
| Cross-engine semantic decision | None; ProbLog-specific lowering mirrors C101 and T2.3c semantics | No |
| Size | Estimated 250-450 LOC code+tests after T2.3c calibration | S with caution |
| Public API rename | None | No |
| New commitment conflict | None known | No |

Conclusion: S-class lightweight blueprint is appropriate. If G7 reveals missing ProbLog list predicates or incompatible empty-list semantics requiring a new design decision, pause and amend/escalate.

### 2026-05-23 — G1-G7 visible mapping

- **G1**: Blueprint §1 and §2 cite parent essay C99-C104 plus §8.8/§1719 lowering strategy. Hygiene/source-of-truth drivers are explicitly tied to prior archive rows.
- **G2**: Draft-time source read covered `problog_export.py:1-359`, `tests/test_problog_export.py`, `tests/test_problog_engine_eval.py`, T2.3a/b/c archive docs, current SDK/application docs rows, and track plan/memory T2.3.d rows.
- **G3**: Blueprint §4 uses concrete file:line cites for ProbLog dispatch, term conversion, tests, and docs rows.
- **G4**: Goals §2.1-§2.7 map to C99/C100/C101/C104 or docs/gate obligations.
- **G5**: Non-goals explicitly exclude SDK/core/application/Souffle/PyReason/probability semantic changes and runtime binary execution requirement.
- **G6**: Reviewer should independently verify `problog_export.py` dispatch lines, current absence of aggregate handling, list-predicate algorithm, query-var behavior from T2.3c, and docs rows.
- **G7**: Blueprint §5.9 defines pre-impl checks, including T2.3a/b/c contract presence and current ProbLog aggregate gap.

### 2026-05-23 — Cross-slice contract preservation table

| Prior slice | Contract in T2.3d |
|---|---|
| T1.1 Rule DTO | 0 diff expected in `application/protocol/rule.py` |
| T1.2 DSL bridge | 0 diff expected in `sdk/dsl/application_rule.py` |
| T2.1 `ne` | Existing ProbLog `\=` dispatch stays intact |
| T2.2 ArithExpr | Existing `is/2` arithmetic builtin export stays intact |
| ProbLog hygiene | Import-cycle boundary remains intact |
| meta-confidence fixture cleanup | ProbLog export tests should stay fully runnable |
| T2.3a substrate | 0 diff expected in `core/rules/*` and `application/protocol/rule.py` |
| T2.3b SDK | 0 diff expected in `sdk/dsl/*` and `sdk/docs/04_api_surface.en.md`; `sdk/docs/03_rules_and_inferences.en.md` row may flip |
| T2.3c Souffle | 0 diff expected in `adapters/souffle/where_compile.py`; `extract_where_variables` consumed unchanged |

### 2026-05-23 — Review focus areas for Claude Step 4.2

1. **Mean derivation correctness**: verify `Mean is Sum / Count` after `L = [_|_]` is sufficient and uses valid ProbLog/Prolog syntax.
2. **Empty sum assumption**: verify `sum_list([], 0)` assumption or require fallback.
3. **Variable scoping inside `findall/3`**: confirm aggregate-local variables do not escape and correlated outer variables remain visible.
4. **Two-aggregate comparison**: ensure blueprint acceptance covers both sides aggregate and fresh variable collision avoidance.
5. **`not` in aggregate filter**: confirm existing `_compile_atom` recursion can be reused safely.
6. **Validation boundary**: decide whether unknown aggregate-like tuple operands should be rejected specifically as aggregate shape errors or generic unsupported term errors.
7. **Runtime smoke scope**: decide whether exported-text tests are enough or local ProbLog binary smoke should be required if available.

### 2026-05-23 — Branch state at draft commit time

- Branch: `v0.2.0-blueprint-t2-3d-aggregate-problog-wire-2026-05-23`
- Base: `7331a152` (T2.3c memory sync)
- Sacred `master`: `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty set preserved: 4 M + 1 untracked
