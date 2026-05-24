# Task Blueprint Audit: T3.5 RuleExpr Inspect

- Blueprint: [2026-05-24_t3-5-ruleexpr-inspect.md](./2026-05-24_t3-5-ruleexpr-inspect.md)
- Status: scoped
- Created: 2026-05-24
- Last Updated: 2026-05-24

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-24 | draft | Blueprint created | Initial T3.5 M-class scope recorded from D3 inspect coexistence, D4 alias identity, D5 §4.6 split allowance, Stage 3 synthesis §3 T3.5, track plan T3.5 row, parent C32/C49/C50/C51/C59, and archived T3.1-T3.4 substrate. |
| 2026-05-24 | draft-amend | Step 4.2 P2 precision amendments | T3.5-F1 atom_id schema locked to T1.1 `Rule.atom_ids[index]`; T3.5-F2 `unjoined_same_name_ports` key shape specified without adding a fifth DTO; T3.5-F3 `OccurrenceInspect.ports` string names vs `RuleExprInspect.ports` `PortInspect` descriptors clarified. |
| 2026-05-24 | scoped | Scope locked + P3 precision | T3.5-F4 AtomDescriptor derivation pseudocode added for PredAtom entity-existence/field-predicate dispatch and CmpAtom best-effort `cmp` classification. |
| 2026-05-24 | pre-impl | Step 4.6 grep found F5 alignment risk | Grep confirmed new DTO/module names are clean and legacy inspect paths are isolated, but T1.4 `:exists` inference accepts any matching term while §5.6 pseudocode currently requires `len(atom.terms) == 1`; needs a pre-feat A-fallback precision amendment before G7/implementation. |
| 2026-05-24 | scoped-amend | Step 4.6 (A-fallback) precision alignment | T3.5 §5.6 PredAtom entity_existence dispatch relaxed from `len(atom.terms) == 1` to `atom.terms` non-empty, aligning with shipped T1.4 `_find_entity_ref_type_in_atom` any-term semantics; `subject=atom.terms[0]` retained as inspect convention. |
| 2026-05-24 | baseline | G7 baseline recorded | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v` ran 63 tests OK after Step 4.6.5 F5 A-fallback alignment. |

## Decision Notes

### Source Chain

- Stage 1 audit: `workflow/audit/active/2026-05-24_t3-ruleexpr-vs-shipped.md`
- D3 inspect coexistence: `workflow/design/decisions/active/2026-05-24_t3-d3-inspect-coexistence.md` §4.1-§4.6
- D4 structural equality/hash: `workflow/design/decisions/active/2026-05-24_t3-d4-structural-equality-hash.md` §4.3 and §7.3
- D5 slice split: `workflow/design/decisions/active/2026-05-24_t3-d5-slice-split-bool-guard.md` §4.6
- Stage 3 synthesis: `workflow/audit/active/2026-05-24_post-q-t3-ruleexpr-synthesis.md` §3 T3.5
- Track plan: `workflow/design/design-points/active/rule-expression-and-proof-track-plan.zh.md:190-195` synced at `9c857d0c`
- Parent design: `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §4.7 / §4.10 C32-C35+C49-C51 / §5.10 C59
- T1.4 archive: `workflow/blueprints/archive/2026-05-23_t1-4-alias-port-contract.md`
- T3.1 archive: `workflow/blueprints/archive/2026-05-24_t3-1-base-ruleexpr-bool-guards.md`
- T3.2 archive: `workflow/blueprints/archive/2026-05-24_t3-2-expression-scope-validation.md`
- T3.3 archive: `workflow/blueprints/archive/2026-05-24_t3-3-joins-and-reach-rule.md`
- T3.4 archive: `workflow/blueprints/archive/2026-05-24_t3-4-join-by-ports.md`

### G1-G7 Visible Mapping

| Gate | T3.5 mapping |
|---|---|
| G1 | Canonical source chain includes D3, D4, D5, synthesis, track plan, parent C32/C49/C50/C51/C59, and T3.1-T3.4 archives. |
| G2 | Blueprint §4 cites shipped SDK inspect path and shipped RuleExpr substrate with file:line ranges. |
| G3 | File citations include `src/factgraph/sdk/store.py:379-386`, `:2088-2089`, `:2907-2964`, `rule_expr.py:20-347`, and export blocks. |
| G4 | Goals map to D3 three-way dispatch, parent C32/C49/C50/C51/C59, and D5 T3.5 ownership/split allowance. |
| G5 | Non-goals and §5.9 preserve legacy inspect, T1.4, T3.1-T3.4, execution lowering, docs/examples, and error subclass boundaries. |
| G6 | Reviewer should spot-check SDK inspect dispatch preservation, DTO export strategy, split decision, render contract, and C32/C49/C50/C51/C59 coverage. |
| G7 | §8 step 1 requires baseline checks recorded in this audit log before implementation. |

### Class Trigger Analysis

T3.5 is M-class.

M-class reasons:

- Adds four public DTOs and about four SDK exports.
- Extends the public `fg.rules.inspect(...)` dispatch surface while preserving legacy behavior.
- Consumes multiple adopted decisions and parent commitments: D3, D4, D5, C32, C49, C50, C51, C59.
- Introduces a new inspect projection module and traversal/render helpers.
- Requires a split decision for T3.5a/T3.5b risk management.
- Needs broad cross-slice preservation: T1.4, T1.3, T2.3, T3.1-T3.4.

Why not L:

- The full T3 L-class audit/decision/synthesis ladder is already complete.
- T3.5 consumes accepted decisions rather than reopening RuleExpr architecture.
- No adapter execution lowering, evidence semantics, or T5 hard-cut behavior is included.
- Split trigger in §5.1 contains scope pressure without broadening this blueprint.

M-to-L triggers:

- Changing D3 return-shape policy.
- Replacing `fg.rules.inspect(...)` with a separate entry point.
- Touching execution lowering, adapters, evidence/proof narratives, or T5 hard-cut.
- Requiring a second decision doc for inspect semantics not covered by D3/D5.

### Split Decision Record

Draft chooses one M-class T3.5 blueprint shipping C32 core plus C49/C50/C51/C59 rich descriptors. It explicitly keeps a split trigger: if preflight or implementation planning shows scope pressure, pause for (A-fallback) scope amendment and split into T3.5a/T3.5b before code.

### Preemptive Scope Check

T3.5 applies the T3.3/T3.4 zero-deviation pattern:

- `SDKStore.inspect_rule(...)`: dispatch extended, entry point preserved.
- `_inspect_rule_or_inference(...)`: legacy dict behavior preserved and not rewritten.
- Legacy SDK Rule / Inference: no conversion to `RuleExprInspect`.
- T1.4 DTOs: no new methods or fields.
- T3.1-T3.4 authoring substrate: no semantics changes.
- Error subclasses: none added; reuse `RuleExprError`.
- SDK import cycles: use lazy imports in SDK dispatch.
- Execution/docs/examples: deferred.

### Reviewer Focus Areas

- Whether the single-blueprint T3.5 split decision is defensible for M-class.
- Whether D3 legacy dict preservation is strict enough.
- Whether application Rule inspect truly follows C35 one-occurrence RuleExpr semantics.
- Whether DTO shapes cover C32/C49/C50/C51/C59 without inventing execution/evidence semantics.
- Whether `templates`, `port_visibility`, and `ports` shipping in T3.5 is justified.
- Whether `rule_expr_inspect.py` is the right module boundary.
- Whether render contract is authoring narrative and pure.
- Whether unsupported inputs keep explicit SDK-style errors.
- Whether export strategy mirrors T3.3 public DTO pattern.
- Whether preemptive scope locks are strong enough for a third consecutive zero-deviation target.

### Cross-Slice Contract Preservation

| Prior slice | Expected preservation |
|---|---|
| T1.1 Rule DTO | Application Rule fields, content digest, ports, and atom storage unchanged. |
| T1.2 DSL bridge | `build_application_rule(...)` still returns application `Rule`; bridge behavior unchanged. |
| T1.3 SDK naming | `factgraph.sdk.Rule` remains legacy; new inspect DTOs are additive exports only. |
| T1.4 alias/port substrate | `Rule.as_`, `RuleOccurrence`, `RulePortRef`, alias regex, port APIs, and `RulePortRef.__eq__` unchanged. |
| T2.3 aggregate track | Aggregate AST/eval/adapter behavior untouched; AtomDescriptor may describe aggregate-containing atoms only if already present as application atoms. |
| T3.1 base RuleExpr | Bool guards, public exports, internal composition, and negative-action gates preserved. |
| T3.2 expression-scope validation | Alias uniqueness, explicit aliases, and alias-aware canonical operands preserved. |
| T3.3 joins + reach rule | `RuleJoinConstraint`, joins, reach validation, symmetry/dedupe, and negative-action gates preserved. |
| T3.4 join_by_ports | `.join_by_ports(...)` behavior, strict no-export lock, and two-file implementation remain unchanged. |

### Step 4.6 Pre-Implementation Grep

| Check | Command | Result |
|---|---|---|
| New public DTO names | `rg 'RuleExprInspect|OccurrenceInspect|AtomDescriptor|PortInspect' src/factgraph/ tests/` | Clean: 0 shipped code/test hits. |
| New module name | `rg 'rule_expr_inspect|RuleExprInspect' src/factgraph/ tests/` | Clean: 0 shipped code/test hits. |
| `SDKStore.inspect_rule` callers | `rg 'inspect_rule\(|\.inspect_rule\b' src/factgraph/ tests/` | Clean: only `_SDKRulesManager.inspect(...)` delegates to `SDKStore.inspect_rule(...)`; method definition remains the single store entry point. |
| Legacy inspect helper callers | `rg '_inspect_rule_or_inference' src/factgraph/ tests/` | Clean: only `SDKStore.inspect_rule(...)` calls `_inspect_rule_or_inference(...)`; no external helper dependency. |
| Public rules inspect callers | `rg '_SDKRulesManager|rules\.inspect\(' src/factgraph/ tests/` | Clean: existing docs/tests call `fg.rules.inspect(...)`; no alternate public entry point discovered. |
| T1.1 atom id schema | `rg 'atom_ids' src/factgraph/ tests/` | Clean with expected split: application `Rule.atom_ids` uses `<rule_id>:atom_<index>`; legacy SDK branch inspect keeps `b0.a0` dict shape. T3.5 F1 application inspect should reuse `Rule.atom_ids[index]`. |
| Legacy branch inspect helper | `rg '_inspect_where_branches' src/factgraph/ tests/` | Clean: internal legacy helper only, called from `_inspect_rule_or_inference(...)`. |
| `:exists` inference alignment | `rg ':exists' src/factgraph/application/protocol/` + `rg '_find_entity_ref_type' src/factgraph/application/protocol/` | Risk: T1.4 `_find_entity_ref_type_in_atom(...)` accepts `PredAtom` whose `pred_id` ends with `:exists` and any term equals the target `Var`; §5.6 pseudocode currently says `len(atom.terms) == 1`. Amend §5.6 before implementation. |

### G7 Baseline Record

| Check | Result |
|---|---|
| Branch and sacred state | T3.5 branch `v0.2.0-t3-5-ruleexpr-inspect-2026-05-24`; sacred `master` remains `562c7419`; dirty 4M+1U preserved. |
| T3.4 join_by_ports substrate | Step 4.6 grep already confirmed T3.4 substrate boundaries; F5 risk was inspect atom-derivation precision, not T3.4 substrate. |
| New DTO names and module placement | Step 4.6 grep confirmed `RuleExprInspect` / `OccurrenceInspect` / `AtomDescriptor` / `PortInspect` and `rule_expr_inspect` have 0 shipped code/test hits. |
| Requested pytest baseline | Deferred per T3.1-T3.4 environment lock: pytest has known SIGSEGV in this environment; unittest fallback is the G7 runner. |
| Fallback unittest baseline | `PYTHONPATH=src python -m unittest tests.application.protocol.test_rule tests.application.protocol.test_rule_expr -v` -> 63 tests OK. |

### Step 4.2 Draft Review Checklist

- [ ] M-class declaration justified and no L trigger left implicit.
- [ ] Split decision is explicit and includes a real pre-code split trigger.
- [ ] D3/D4/D5/synthesis/track-plan/parent cite chain is complete.
- [ ] Goals cover three-way dispatch and C32/C49/C50/C51/C59.
- [ ] Legacy SDK Rule / Inference dict inspect preservation is explicit.
- [ ] Four public DTOs and SDK export strategy are explicit.
- [ ] `fg.rules.inspect(application_rule)` C35 coercion shape is explicit.
- [ ] `fg.rules.inspect(rule_expr)` traversal shape is explicit.
- [ ] D3-deferred `templates`, `port_visibility`, and `ports` decision is explicit.
- [ ] Preemptive scope locks continue T3.3/T3.4 zero-deviation discipline.
- [ ] Acceptance gates cover DTO immutability, dispatch, render, descriptors, docs, cross-slice preservation, and ruff.
