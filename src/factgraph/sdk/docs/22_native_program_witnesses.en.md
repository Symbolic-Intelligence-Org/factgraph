# Native RuleProgram result-local witnesses

`fg.eval.evaluate_program(program, goal).explain().witness_report` captures
`RuleProgramWitnessReportV1` during that evaluation. It is separate from the
live [Store witness report](21_support_witnesses.en.md): it neither changes
original ProofReceipt bytes/digests nor extends closed EvaluationRun or runtime
ABI formats. No ledger, side-index or historical-evidence write occurs.

```python
from factgraph.sdk import RuleProgramWitnessReportV1

result = fg.eval.evaluate_program(program, goal)
report = result.explain().witness_report
assert report is not None  # None is reserved for legacy/manual uncaptured results.
frozen_bytes = report.to_json()
restored = RuleProgramWitnessReportV1.from_json(frozen_bytes)
for item in restored.to_dict()["occurrences"]:
    print(item["support_digest"], item["condition_key"], item["witness_ref"],
          item["kind"], item["availability"], item["reason"])
```

One occurrence is the original `(support_digest, condition_key, witness_ref)`;
the same ref in several conditions is retained several times. Origins are
`assertion`, `program_fact`, `virtual`, or `unknown`. Ledger/projector metadata
assigns original origins. Only **actual** program overlay insertions are
`program_fact`; equal-tuple skips retain the selected existing row's origin.
Contradictory selected ref reuse fails with `program_witness_ref_collision`.
Ref spelling and failed assertion lookup never classify a witness.

Availability has basis `captured_evaluation`. It means material was captured,
not current visibility, activity, permission, truth or cross-call snapshot
consistency. Unknown origin is unavailable (`origin_not_captured`); unavailable
material uses `material_not_captured`. Program provenance is caller-supplied
finite JSON, not assertion/span/label authority. Values preserve schema-owned
tup_v1 tags and canonical storage, including entity_ref/string and bool/int/float.
Original binary EvidenceGraph leaves use FactGraph's existing canonical
`{"__bytes_hex__": "..."}` receipt-JSON representation in the report; `report.evidence`
and later Explain restore the original binary values without changing support.

The closed report includes goal/engine/view/rule/scope pins, the original
recursive support steps, exact EvidenceGraph and their digests. `source_links`
maps each canonical evidence JSON pointer to original occurrence coordinates,
recorded while rendering with receipt context. Why-not sources are
`diagnostic_only` and never invented successful assertions. Missing child
support is a `support_not_captured` issue with its original digest. Status is
`complete`, `partial`, or `not_applicable` (no successful root). It does not
replace the result's entailment outcome.

`to_dict()` returns detached JSON data; `to_json()` returns canonical UTF-8 bytes.
`from_dict()` / `from_json()` validate the closed version, original receipts,
source associations, typed values, completeness and independent report digest.
Duplicate JSON keys are rejected. SHA-256 covers all fields except
`report_digest`; it is integrity, not authenticity or access authorization.
Invalid shapes/links/digests raise `RuleProgramWitnessError` with a stable `code`,
not normal absence. No wall-clock field enters the report digest.

Explain reads the frozen capture only. Later nested caller mutation, ledger
changes or loss of support cache cannot change it. The temporary origin
inventory is discarded; no whole ledger or portable evaluator is embedded.
Old results are never reconstructed from current Store state, and the existing
Store witness API may still report `not_captured` for these unchanged receipts.
