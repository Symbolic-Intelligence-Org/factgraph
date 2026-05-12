# Core Semantics Module

`kernel.core.semantics` contains value objects and helpers for runtime
projection semantics. Track 3 / B introduced `SemanticsProfile` as a
validated core value object:

- no SDK namespace export;
- no service endpoint;
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
- Track 3 / E will decide the durable SDK/service runtime call-site.

Adapter import boundary:

- ProbLog and PyReason may import `kernel.core.semantics.SemanticsProfile`
  because they consume profile data in C/D.
- Souffle remains profile-agnostic.
- Native evaluation is implemented in core, not as a
  `src/kernel/adapters/native/` package; E owns any durable public
  call-site shape for native/profile interaction.
