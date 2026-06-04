# vs-shipped Audit: `Rule.desc` Auto-Render into `Explanation.repr`

Status: complete
Date: 2026-06-04
Branch: `v0.2.0-impl-query-style-head-2026-06-03`
Class: tiny local fix (per [`workflow/CADENCE.md`](../../CADENCE.md) Scope-and-Applicability) — no blueprint pair
Trigger: doc-revision review of `docs/quickstart/evaluate_and_evidence.md` §4.1 / §5.3 surfaced that Slice ε's claimed D21 §6.6 path C closure was implementation-incomplete

## 1. Purpose

Record discovery + closure of a gap between Slice ε's published closure claim and shipped behavior. Slice ε §10 Outcome line 282 (archived at `workflow/blueprints/archive/2026-06-03_explanation-repr-walker-slice-epsilon.md`) declares:

> D21 §6.6 path C is closed for the shipped Explanation payload via `Explanation.repr`

…and the parent design-point `explanation-completion-roadmap.zh.md §6.6 path C` is "desc-driven explain output as part of shipped Explanation payload, not a manual-render exercise".

The walker mechanics shipped (per Slice ε): `walk_evidence(graph, ...)` traverses NODE_CONCLUSION → NODE_RULE_EXPR → NODE_RULE → NODE_ATOM → NODE_SEED and renders connector + summary per node.

**What was NOT actually wired** (the gap): `_row_conclusion_node(...)` at `src/factgraph/application/protocol/evaluate_result.py:947-975` hardcoded:
- `engine_meta["desc_template"] = None` (line 960)
- `value_summary = _claim_repr_for_row_result(row, result)` (line 973) — produces `f"{head.id}{dict(bindings)!r}"`, e.g. `"adults_in_us{'user': 'idref_v1:User:<digest>'}"`

The walker reads `value_summary` for the Conclusion node, so `Explanation.repr`'s first line was the Python dict repr form, NOT the rendered desc template.

`Rule.render_desc(bindings)` (`rule.py:115-128`) was implemented + tested + reachable via `row.close().render_desc(...)`, but never invoked by the layered-graph builder.

## 2. 5-state classification

| Bucket | Item |
|---|---|
| **drift — claim overstated** | Slice ε §10 D21 closure assertion + child memory `project_explanation_repr_walker_slice_epsilon_implemented.md` "Closes parent design §7.3 D21 §6.6 path C deferred work" |
| **already aligned** | Desc render machinery (`Rule.desc` field, `Rule.render_desc`, `_render_desc_template`, closed-head desc preservation, `RuleExprInspect.render`) |
| **fix delivered this commit** | `_row_conclusion_node` now calls `head.render_desc(public_bindings)` for value_summary + sets `engine_meta["desc_template"] = result.head.desc` |
| **no independent action** | None |
| **deferred** | Atom-level NL render (atom `value_summary` still `"satisfied"` / seed still `"ledger assertion"`); composite `and`/`or` RuleExpr `ast_form` |

## 3. Fix scope

**Code change** (1 file, ~6 lines net):

- `src/factgraph/application/protocol/evaluate_result.py:947-975` `_row_conclusion_node`:
  - Build `public_bindings = {port: _public_term_value(term) for port, term in row.bindings.items()}` (unwraps typed term dicts to public values)
  - Compute `rendered_desc = result.head.render_desc(public_bindings) if result.head.desc is not None else ""`
  - Change `engine_meta["desc_template"]` from hardcoded `None` to `result.head.desc`
  - Change `value_summary` from `_claim_repr_for_row_result(...)` to `rendered_desc or _claim_repr_for_row_result(...)` (fallback when head has no desc)

**Tests added** (1 file, +2 cases / ~75 lines):

- `tests/application/protocol/test_evaluate_result_dtos.py` new `class RowConclusionNodeDescTests`:
  - `test_value_summary_uses_rendered_desc_when_head_has_desc` — Rule with `desc="Adult user %user lives in the US"` + entity_ref bindings → asserts `value_summary == "Adult user idref_v1:User:alice lives in the US"`, `engine_meta["desc_template"]` carries raw template
  - `test_value_summary_falls_back_to_repr_when_head_has_no_desc` — Rule without desc → asserts `engine_meta["desc_template"] is None`, `value_summary` falls back to repr form

**Doc updates** (1 file):

- `docs/quickstart/evaluate_and_evidence.md`:
  - §4.1 example: added `desc="Adult user %user lives in the US"` to `adults_in_us` rule
  - §4.1 walker output: Conclusion line now shows rendered desc, not Python repr
  - §5.3 "Auto-rendered into Explanation.repr": rewrote to precisely describe `_row_conclusion_node → head.render_desc(row.bindings) → value_summary` chain + fallback semantics

## 4. Verification

```
PYTHONPATH=src python -m pytest tests/application/protocol tests/sdk/test_evaluate_result_exports.py
→ 145 passed in 0.32s (2 new RowConclusionNodeDescTests pass; 143 prior tests no regression)
```

## 5. Why no blueprint pair

Per [`workflow/CADENCE.md`](../../CADENCE.md) Scope-and-Applicability and [`workflow/blueprints/README.md`](../../blueprints/README.md):

- Single-file additive code change (no signature change, no protocol shape change, no DTO addition/removal)
- Test coverage in same commit batch
- Doc updated in same commit batch
- No cross-module touch points

Falls under "tiny local fix" exemption. Recorded here for traceability of the D21 closure delta.

## 6. Implication for Slice ε record

Slice ε archived blueprint + audit + memory **predate** this fix and **all overclaim D21 closure**:
- `workflow/blueprints/archive/2026-06-03_explanation-repr-walker-slice-epsilon.md` §10 Outcome line 282
- `workflow/blueprints/archive/2026-06-03_explanation-repr-walker-slice-epsilon.audit.md` (relevant closure rows)
- Memory `project_explanation_repr_walker_slice_epsilon_implemented.md`

**No retroactive edit** of archive material — archive integrity preserved (per archive immutability convention). This audit doc + memory update (TBD next turn) carry the correction forward.

## 7. Follow-ups (out of scope here)

- Memory update: amend [[project_explanation_repr_walker_slice_epsilon_implemented]] with a "post-archive correction 2026-06-04" addendum noting the D21 closure actually completed today, not at ε archive
- Optional next-cycle item: atom-level NL summary (so `Atom[0]: satisfied — support` becomes `Atom[0]: user:region(u, "US") — support` and `is supported by ledger fact: user:region(alice, "US")`); this is a separate gap to D21 path C and was always future scope
