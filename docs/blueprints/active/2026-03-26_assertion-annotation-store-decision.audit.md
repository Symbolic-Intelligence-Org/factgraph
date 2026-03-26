# Audit Log: Assertion Annotation Store Decision

| Date | Status | Event | Notes |
|------|--------|-------|-------|
| 2026-03-26 | draft | Blueprint created | Triggered by PyReason integration exposing `meta` semantic flaws: `bound=[0.6,0.9] → confidence=0.6` is lossy and semantically incorrect. Four decisions drafted: four-layer architecture, confidence as derived summary, semantic annotation ≠ claim, engine-native term scoping. Supersedes ADR-14c specific measures while preserving its spirit. |
| 2026-03-26 | draft | Decisions 5-6 added | Decision 5: engine-specific semantics carrier split (assertion → annotation, rule → typed extension payload, run → engine_options). Rule layer does NOT use annotation mechanism; ADR-14d direction maintained but implementation narrowed to `engine_ext` payload instead of full subclass family. Decision 6: rule params must separate definition-time (engine_ext) from run-time (engine_options). |
| 2026-03-26 | draft | P1 fixes applied |
| 2026-03-26 | scoped | Promoted to scoped | (1) Parent ADR sync: ADR-14a/14c/14d rewritten to reference Annotation Store, eliminating dual-truth conflict. ADR-14c now explicitly marked "superseded 2026-03-26" with full rewrite. ADR-14d updated to engine_ext payload. (2) Decision 5: engine_ext portability claim narrowed from "any engine can consume" to "eligible for cross-engine consumption, subject to capability gate and adapter coverage". (3) Non-blocking: Derivation/Query scope added to Decisions 5-6. |
