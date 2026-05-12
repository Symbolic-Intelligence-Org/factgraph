# Task Blueprint Audit: PyReason SemanticsProfile Migration

- Blueprint: [2026-05-12_pyreason-semantics-profile-migration.md](./2026-05-12_pyreason-semantics-profile-migration.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed records D-first path after C, source audit of PyReason extension/runtime surfaces, and G0 questions for rule projection targets, rule delay, temporal mode minimum shape, and carrier conflict rules. |

## Decision Notes

- 2026-05-12: C left Track 3 in a half-consumed adapter state: ProbLog consumes `SemanticsProfile.rule_projection.problog`, while PyReason still consumes only `PyReasonRuleExt` and `engine_options`. The draft follows the user's recommendation to do D before E so E's public call-site design can assume both major adapters consume profiles.
- 2026-05-12: Scope-control principle for D: add only one non-`none` temporal mode and keep all other temporal modes rejected. This preserves B's conservative temporal boundary while giving D enough surface to validate PyReason temporal consumption.
- 2026-05-12: The draft mirrors C's adapter-consumption pattern: generic `SemanticsProfile` validation remains core shape validation; adapter-specific target resolution and interval validation happen at PyReason consumption time.
- 2026-05-12: The draft leaves G0 to lock target spelling and temporal behavior. Recommended defaults are path-style `body_atom:{branch}:{atom}` targets, `head:0`, inclusion of `timestep_delay`, and temporal T2 (`valid_time_boundaries` with timesteps projection and conflict checks).
