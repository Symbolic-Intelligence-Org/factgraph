# Blueprint: Populate EvidenceAtom `Holds.support` in modern explains

- Status: implemented (2026-06-23; native + problog verified; 627-test regression green)
- Branch: `v0.2.0-fix-explain-composite-closed-head-2026-06-22` (continuation)
- Owner: Claude (impl) / user (gate)
- Paired audit: none (small; record outcome here)

## 1. Problem

`Holds.support: tuple[Source, …]` carries the provenance source(s) backing a
holding atom and is serialized into the EvidenceGraph dict. It is populated ONLY
by the legacy provenance / support-artifact paths (`adapters/*/provenance.py`,
`store.py` support-artifact). The modern reach-chain + native explains — the path
`fg.eval.explain` / `row.explain()` uses — build `Holds(certainty=…)` with the
default empty support, even though the matched-fact data is in hand. So every atom
in a reach/native explanation has `support=()`. Pre-existing; not from the
closed_head_false / per-occurrence work.

## 2. Design

For a **holding PRED (Fact) atom**, attach one `Source` identifying the matched
EDB fact. **Compare / Builtin / Aggregate** atoms have no backing fact → support
stays empty (correct). Non-holding verdicts (Fails / NotReached) carry no support.

`Source(ref=f"{engine}:{atom_id}", value=repr_text, meta={"engine", "predicate",
"terms", ["probability"]})` — mirrors the souffle-provenance Source shape
(`ref` id + readable `value` + engine `meta`).

Data sources:
- **reach** (`diagnostic_assemble`): the per-atom `atom_witnesses`
  (`DiagnosticWitnessProbability.terms`) + the atom's `pred_id` + the atom's
  `repr_text`; probability from the witness. Covers souffle + problog reach.
- **native** (`prober._probe_atom`): the holding atom's `form` (`Fact` with bound
  terms) + `repr_text`.
- pyreason: already populates support via its provenance trace — untouched.

Shared helper `fact_source_for_atom(...) -> Source | None` (returns None for
non-Fact forms) so both paths build identical Sources.

## 3. Slices

1. **Shared helper + reach support** — add the helper; `diagnostic_assemble`
   builds support from `atom_witnesses` for holding Fact atoms and threads it into
   the Holds verdict (`_verdict_for_atom` gains a `support` arg). Verify a holding
   problog/souffle explain has non-empty support on Fact atoms, empty on compares.
2. **Native support** — `prober._probe_atom` attaches a Source (from `form`) to
   `Holds` for holding Fact atoms. Verify the native holding explain.
3. **Tests + docs** — conformance test (native + problog: Fact atoms carry one
   Source naming the matched fact; compares empty); explain docs note.

## 4. Acceptance

- A holding `row.explain()` / `fg.eval.explain` (native + problog) has non-empty
  `support` on every holding Fact atom (a `Source` for the matched EDB fact);
  compare/builtin atoms keep empty support.
- Existing serialization round-trip (`_source_to_dict` / `_source_from_dict`) and
  all narrate / conformance tests stay green.
- No change to certainty / verdict status / the per-occurrence probability work.

## 5. Outcome / Deviations

**Implemented 2026-06-23** (all slices in one pass — shared helper, small surface).
- `prober.fact_source_for_atom(form, atom_id, *, engine, repr_text)` → `Source` for
  a holding Fact atom; `None` for Compare / Builtin / Aggregate forms.
- `prober._probe_atom`: native Holds verdicts on Fact atoms carry the Source
  (`engine="native"`).
- `diagnostic_assemble` atom loop: reach (souffle/problog) Holds verdicts on Fact
  atoms carry the Source, preserving the verdict's certainty.
- `Source(ref=f"{engine}:{atom_id}", value=repr_text, meta={"engine","predicate"})`.
  Structured terms deliberately omitted (the readable `value` + predicate suffice;
  can extend later if a consumer needs them).
- Verified: native + problog holding `works_on_project` → its 7 Fact atoms each
  carry one Source, the `30 > 20` compare stays empty. Test
  `tests/sdk/test_explain_atom_support.py` (native + problog). Regression: explain/
  narrate/conformance/problog/souffle/reach sweep **627 passed / 2 skipped**.

Deviation from §3 slicing: reach + native + helper landed together (one coherent
change) rather than three separate slices. pyreason untouched (its provenance
trace already populates support).

**Follow-on (same session): fail-support.** At the user's request, `Fails` gained
a symmetric `support` field (+ serialization round-trip in `evidence_tree`).
`prober.refuting_sources_for_atom(form, atom_id, view_facts, *, engine)` returns
the *refuting* fact(s) for a failing Fact atom — the actual EDB fact(s) that share
the atom's owner key (term0) but carry a different value (`meta["role"]="refuting"`,
`meta["actual"]` = the actual terms). Wired into native `_probe_atom` (both Fails
returns) and the reach assembler (`elif isinstance(verdict, Fails)`). Unary
existence / pure absence (no fact for the owner) → empty support. Verified native +
problog: `assignment:user(AP1, Carol)` fail → `actual=(AP1, Alice)`;
`project:active(P1, True)` fail → `actual=(P1, False)`. `test_explain_atom_support.py`
extended to 4 cases (holds + fails, native + problog). Regression **629 passed**.
