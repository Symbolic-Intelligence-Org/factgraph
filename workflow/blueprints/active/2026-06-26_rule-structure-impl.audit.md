# Task Blueprint Audit: 实现 `fg.rules.structure` + `RuleStructure`

- Blueprint: [2026-06-26_rule-structure-impl.md](./2026-06-26_rule-structure-impl.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-26 | scoped | Blueprint created (scoped) | Consumes adopted decision 2026-06-26_evidencegraph-readonly-and-rule-structure-type (§4) + design-point rule-structure-static-projection (§3 contract). Collaboration: Codex-impl / Claude-gate / user-merge. |

## Decision Notes

### 2026-06-26 — scope freeze

- **Upstream lock**: decision §4.1 (EvidenceGraph 只读派生定位 + 机械明线) + §4.2 (独立中立类型 / 共享 backbone / `Evidence*` 零改动 / Tree-only) are adopted constraints; this blueprint must not deviate. The full `RuleStructure` field-level contract is the design-point §3.2 draft, to be finalized in-impl (slice 2).
- **Scope frozen to**: the 8-slice plan (§8). `Evidence*` (`evidence_tree.py`) is strictly read-only/unchanged — if any slice appears to need an `Evidence*` change, that is a scope breach → stop + escalate (it would mean the "don't mix" decision is being violated).
- **Collaboration cadence**: Codex implements each slice; Claude gates against the matching Acceptance item (verify + regression) before the next slice; user merges at scoped-unit completion. Per `feedback_no_autonomous_code_edits` + `feedback_push_master_gate`, Claude does not modify shipped `src/` autonomously and does not auto-push.
- **Open items carried from design-point** (resolve during impl, record here):
  - Q2: exact home of `assemble_static_structure` + prober split granularity (slice 1/3).
  - Q3: `fg.rules.structure` return shape (direct `RuleStructure` vs wrapper) (slice 5).
  - Q4: pyreason/Timeline cross-model mapping — out of scope here; documented as a boundary (slice 8).

### Gate log (append per slice)

| Date | Slice | Codex result | Claude gate verdict | Notes |
| --- | --- | --- | --- | --- |
| 2026-06-26 | 1-3 + smoke | `structure_keys.py` (single-source key helper) + `Structure*`/`FreeVar`/`HeadClosure` types + `assemble_static_structure(plan)` + OR/join 对位 test | **PASS** (GO for slice 4-8) | Independently re-verified (not pasted): `evidence_tree.py` zero-diff; `src/agent\|service\|domains` zero-diff; **no reverse edge** (`core/` ZERO hits for RuleStructure/EvidenceGraph); node-identity 对位 `equal=True` across **native/problog/souffle** (souffle WAS available here, contra Codex env); regression green (36 passed + broad sweeps). Deviation rulings — (1) `ast`=DNF-rebuilt → **ACCEPT-with-slice-4-condition**: slice 4 must restore **authored** ast (thread `rule_expr` into assemble; keep DNF only in `branches[]`/separate field, never as `ast`; plan-only fallback → `ast=()`, not silent DNF); do NOT amend the contract. (2) `structure_id=repr(canonical_key)` ACCEPT (non-对位 container id). (3) body `repr_text=None` ACCEPT-w/-slice-4. (4) Q2 placement ACCEPT. (5) Q3 SDK-shell deferred ACCEPT. |
| 2026-06-26 | 4-8 | authored-ast threading (`ast=()` fallback, no silent DNF) + `render`/`render_compact` parity + derived-props parity (`StructurePort` field-drop) + `HeadClosure\|None` + body `repr_text` + `fg.rules.structure` thin shell + mechanical guard test + docs | **PASS** (GO for user-merge) | Independently re-verified in THIS env (pytest + problog + souffle all work; Codex segfault env-local). **All 5 slice-4 carry-forward conditions MET**: authored `ast` byte-equal (NOT DNF; `ast=()` fallback) across OR / non-DNF `(a\|b)&c` / single; render parity; derived-props parity + `PortInspect.field/value_type` dropped on `StructurePort`; `HeadClosure\|None` routing; body `repr_text` to inspect-floor. `evidence_tree.py` + `rule_expr_inspect.py` + `agent/service/domains` zero-diff; **no reverse edge** into `core/`/derivation; **3-engine node-identity ran+green** (native/problog/souffle); mechanical guard test passes. NON-BLOCKING: **N1** Codex slice-4-8 manifest omitted `prober.py`(mod)+`structure_keys.py` (those are the slice-1-3 single-source key extraction; byte-preserving; correct, just record). **N2** `render()`/`render_compact()` raise IndexError on the sanctioned `ast=()` state — **unreachable via SDK** (`fg.rules.structure` always threads `rule_expr`); one-line guard recommended as follow-up. |
