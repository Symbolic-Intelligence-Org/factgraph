# Core Semantics Module

`kernel.core.semantics` contains value objects and helpers for runtime
projection semantics. Track 3 / B introduced `SemanticsProfile` as a
validated core value object:

- SDK namespace export exists through `kernel.sdk.SemanticsProfile`
  for advanced/canonical users; Track 2 also exposes SDK-local
  `ProbLogSemantics` and `PyReasonSemantics` wrappers that lower into
  `SemanticsProfile` at the SDK boundary;
- service runtime accepts top-level inline `semantics` in canonical
  `SemanticsProfile` JSON shape for derivation evaluation;
- ProbLog adapter consumption exists for `rule_projection.problog` through
  the core `Store.evaluate(..., mode="problog", semantics_profile=...)`
  path;
- PyReason adapter consumption exists for `rule_projection.pyreason` and
  `temporal_projection` through the core
  `Store.evaluate(..., mode="pyreason", semantics_profile=...)` path;
- no projected values written back to stored assertions.

The initial public import for advanced/core consumers is:

```python
from kernel.core.semantics import SemanticsProfile, inspect_semantics_profile
```

`SemanticsProfile` validates profile shape, generic rule-projection
entries, uncertainty projection policy names, and the D-time temporal
modes `none`, `fixed_timesteps`, and `valid_time_boundaries`.
`inspect_semantics_profile(profile)` returns a JSON-like
summary of which projection lanes are configured without running an
adapter or mutating the profile.

Adapter migration is intentionally staged:

- Track 3 / C consumes `SemanticsProfile.rule_projection.problog` and
  normalizes `kind="branch_probability"` entries into the adapter-local
  `ProbLogRuleExt` bridge. Omitted branches default to `1.0`.
- Track 3 / D consumes `SemanticsProfile.rule_projection.pyreason` and
  `SemanticsProfile.temporal_projection` for PyReason. Adapter-specific
  validation still happens at PyReason consumption time, not in the core
  profile constructor.
- Track 3 / E exposed the durable SDK/service runtime call-site.
  Track 2 adds preferred SDK wrappers: `fg.eval.evaluate(...,
  semantics=ProbLogSemantics(...))` or `PyReasonSemantics(...)`.
  Service callers still pass canonical top-level JSON `"semantics": {...}`.
- Track 3-post adds the PyReason branch-bound lane. SDK
  `PyReasonSemantics(branch_bounds=...)` lowers to canonical
  `rule_projection.pyreason` `branch:{index}` interval entries; adapter
  consumption normalizes those entries into `PyReasonRuleExt.branch_head_bounds`.

Adapter import boundary:

- ProbLog and PyReason may import `kernel.core.semantics.SemanticsProfile`
  because they consume profile data in C/D.
- Souffle remains profile-agnostic.
- Native evaluation is implemented in core, not as a
  `src/kernel/adapters/native/` package; public SDK/service calls reject
  profile use with `engine="native"` and `engine="souffle"`.
