# Captured support witnesses (V1)

`fg.audit.support_witnesses(support_digest)` reads classification for the exact
predicate witnesses in one retained support artifact. It returns
`SupportWitnessReportV1` (also exported from `factgraph.sdk`). This compatibility
read does not evaluate a Rule, select a new proof, query current domain membership
or write assertions/sidecar data.

```python
report = fg.audit.support_witnesses(candidate.support_digest)
for witness in report.items:
    print(witness.condition_key, witness.witness_ref,
          witness.kind, witness.availability, witness.reason)
```

The report preserves each original condition/reference pair, including one ref
used by multiple conditions. `kind` is captured origin: `assertion`, `virtual`,
or `unknown`. Only the projector/capture producer assigns it; the reader never
classifies by ID prefix, missing lookup or predicate spelling.

Availability is separate. `available` assertions have matching ledger material
at read time; `assertion_missing`/`assertion_mismatch` retain kind `assertion` but
are unavailable. This is not current activity, premise visibility, authorization
or truth. Virtual availability means classification/grounded terms were captured,
not that the Entity still exists in the current view. It provides no assertion
citation and no authority to use Identity assertions as label basis.

Unknown origins return `unsupported_witness_kind`. Old receipts without metadata
return status `not_captured` and unavailable/unknown items with reason
`not_captured`, even if their refs currently resolve. Missing root support returns
status `support_missing` and no items. Root `available` means capture is present;
callers must still examine every item's availability. A consumer's later material
lookup may fail and must degrade conservatively, never infer virtual support.

New SDK Rule/Inference Store-support captures have `witness_capture_version = 1` and exact
per-reference metadata. New canonical support digests include it. Old receipts
retain their bytes/digests; no backfill, evidence rewrite or migration occurs.
Independent sealed EvaluationRun capture/replay retains its existing closed
format; its legacy receipts do not acquire this extension. The shared internal
builder enables classification capture explicitly at the SDK support-recording
seam, not during reconstruction of old or sealed evidence.
`SupportWitnessError.code` identifies `invalid_support_digest`,
`invalid_support_capture` (including unsupported version/invalid inventory), or
`support_digest_mismatch`. Corruption never becomes a normal unavailable result.

`report.to_dict()` is the V1 digest payload; `report.report_digest` is SHA-256 of
its canonical UTF-8 JSON (sorted keys, compact separators, non-ASCII preserved).
It binds `factgraph.support-witness-report.v1`, original support digest, capture
version, status and every item. It is a read report, not sealed replay: changed
assertion material may change availability/report digest, never the original
support. The attached Store/workspace is the read scope; applications retain
responsibility for authorization and user-facing projection.
