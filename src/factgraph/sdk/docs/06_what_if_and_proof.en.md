# Evidence And Replay

T5 removed the public candidate-universe and `what_if.*` evidence shells from
the SDK user path. The supported evidence workflow is:

```python
result = fg.eval.evaluate(inference)
row = result.first()
assert row is not None

explanation = row.explain()
closed_head = row.close()
manual = fg.eval.explain(inference, head=closed_head)
```

- `EvaluateResult` is the public evaluation envelope.
- `EvaluateRow` carries bindings, row-owned conclusion/evidence digests, and
  raw quantitative carriers.
- `row.explain()` returns an `Explanation`.
- `row.close()` returns a closed application `Rule` for manual replay.
- `fg.eval.explain(expr, head=closed_head)` replays a closed-head explanation.

Persisted-fact inspection remains under `fg.audit.*`.
