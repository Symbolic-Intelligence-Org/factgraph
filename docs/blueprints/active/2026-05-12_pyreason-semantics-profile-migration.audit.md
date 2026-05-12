# Task Blueprint Audit: PyReason SemanticsProfile Migration

- Blueprint: [2026-05-12_pyreason-semantics-profile-migration.md](./2026-05-12_pyreason-semantics-profile-migration.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed records D-first path after C, source audit of PyReason extension/runtime surfaces, and G0 questions for rule projection targets, rule delay, temporal mode minimum shape, and carrier conflict rules. |
| 2026-05-12 | design note | Temporal taxonomy refined | Split time-step source and partition method: `fixed_timesteps` is the 1:1 surface for existing `engine_options.timesteps`; `valid_time_boundaries` is a distinct boundary-derived mode with explicit universe; `custom_timeline` and recurrence / multi-interval validity remain future work. |
| 2026-05-12 | scoped | Scope frozen | Locked D1-D15: C2-style core PyReason profile entry, path-style body/head targets, rule delay inclusion, `fixed_timesteps`, `valid_time_boundaries`, carrier conflict rules, internal bridge preservation, adapter import boundaries, and SDK/service rejection preservation. |
| 2026-05-12 | red+guard baseline | Added forward-failing PyReason profile tests | Added `test_pyreason_semantics_profile_migration` with 25 tests: 21 forward-failing tests cover missing PyReason profile resolver, temporal mode acceptance, mode/profile gate, interval projection, rule delay, fixed timesteps, valid-time boundary mapping, and conflict messages; 4 guards preserve existing PyReasonRuleExt, engine_options, ProbLog profile consumption, and profile-agnostic PyReason compiler behavior. Updated `BridgeGuardTests` to expect PyReason imports after D while keeping Souffle non-consumption; current result is 5 tests with 1 expected failure. |

## Decision Notes

- 2026-05-12: C left Track 3 in a half-consumed adapter state: ProbLog consumes `SemanticsProfile.rule_projection.problog`, while PyReason still consumes only `PyReasonRuleExt` and `engine_options`. The draft follows the user's recommendation to do D before E so E's public call-site design can assume both major adapters consume profiles.
- 2026-05-12: Scope-control principle for D: add only the G0-locked PyReason temporal modes and keep all other temporal modes rejected. This preserves B's conservative temporal boundary while giving D enough surface to validate PyReason temporal consumption.
- 2026-05-12: The draft mirrors C's adapter-consumption pattern: generic `SemanticsProfile` validation remains core shape validation; adapter-specific target resolution and interval validation happen at PyReason consumption time.
- 2026-05-12: The draft leaves G0 to lock target spelling and temporal behavior. Recommended defaults are path-style `body_atom:{branch}:{atom}` targets, `head:0`, inclusion of `timestep_delay`, `fixed_timesteps` as the profile form of `engine_options.timesteps`, and minimal `valid_time_boundaries` using explicit universe boundaries.
- 2026-05-12: Temporal projection taxonomy was corrected before G0. `valid_time_boundaries` should not be used as a disguised fixed-step count. D should implement `fixed_timesteps` as the direct profile form of existing PyReason `engine_options.timesteps`, and implement minimal `valid_time_boundaries` with explicit caller-provided universe boundaries and ordinal mapping.
- 2026-05-12: The proposed `valid_time_boundaries` algorithm is scope-controlled: collect caller-provided universe start/end plus assertion `valid_from` / `valid_to` boundaries, sort/deduplicate, and map each boundary to an ordinal PyReason timestep. Missing `valid_from` maps to universe start; missing `valid_to` maps to open-ended active end.
- 2026-05-12: Recurring or multi-interval validity is a data-contract issue, not a PyReason adapter migration issue. D assumes one continuous interval per assertion; applications can materialize recurring validity into multiple assertions, and a future Uncertainty Phase 2 can revisit multi-interval validity if needed.
- 2026-05-12: G0 locks `valid_time_boundaries` collection scope to selected assertions materialized into the current PyReason EDB session. Implementation may switch `_materialize_edb_session` from tuple-only projection to witness-preserving projection so assertion metadata remains available without changing the public view projection contract.
- 2026-05-12: G0 includes `timestep_delay` in `rule_projection.pyreason` because it already exists as `PyReasonRuleExt.timestep_delay` and is rule-local projection, not a new temporal partitioning feature.
- 2026-05-12: G0 preserves B/E boundary: SDK/service profile payloads continue to reject, and E still owns public `semantics=` acceptance plus the `engine=` naming decision.
