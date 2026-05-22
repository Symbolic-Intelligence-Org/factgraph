# Audit Log: certainty-additive-aggregation-v1

| Date | Status | Event | Details |
|------|--------|-------|---------|
| 2026-03-21 | scoped | Blueprint created | Second aggregation strategy: weighted additive contribution alongside existing bottleneck/min. Strategy selectable via explain-side query option. |
| 2026-03-21 | scoped | Design frozen | impact semantics change with strategy: bottleneck=absolute, additive=normalized contribution. CertaintySummary.aggregation disambiguates. No impact_kind field needed. |
| 2026-03-21 | implementing | Phase 1 start | Core aggregation: _certainty.py changes. |
| 2026-03-21 | implementing | Phase 1 complete | _certainty.py dual strategy, CertaintySummary.aggregation field. 227 tests green. |
| 2026-03-21 | implementing | Phase 2 complete | Service wiring: materializer/service/runtime_v1/narrative all thread aggregation. 227 tests green. |
| 2026-03-21 | implemented | Phase 3 complete | 6 additive unit tests + 1 e2e test. 234 tests green. Docs synced. |
