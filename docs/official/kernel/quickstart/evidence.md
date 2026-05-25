# Evidence And Replay

Evaluation is read-only and returns an `EvaluateResult`.

```python
result = fg.eval.evaluate(inference)
row = result.first()
assert row is not None
```

Use row methods for the public evidence path:

```python
explanation = row.explain()
closed_head = row.close()
manual = fg.eval.explain(inference, head=closed_head)
```

| Surface | Purpose |
| --- | --- |
| `EvaluateResult` | Evaluation envelope with run id, result id, digests, head Rule, and rows |
| `EvaluateRow` | Bindings, Claim, raw quantitative carriers, and EvidenceRef |
| `row.explain()` | Row-level `Explanation` |
| `row.close()` | Closed application `Rule` for replay |
| `fg.eval.explain(expr, head=closed_head)` | Manual closed-head explanation |
| `fg.audit.*` | Persisted fact explanation and cross-round audit |

Failed explanations use `Explanation(status="failed")` and `failure_class`.
There is no public candidate-universe why-not or `what_if.*` shell in T5.
