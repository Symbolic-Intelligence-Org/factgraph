# Core Semantics Module

`kernel.core.semantics` contains value objects and helpers for runtime
projection semantics. Track 3 / B introduced `SemanticsProfile` as a
validated core value object:

- no SDK namespace export;
- no service endpoint;
- ProbLog adapter consumption exists for `rule_projection.problog` through
  the core `Store.evaluate(..., mode="problog", semantics_profile=...)`
  path;
- no projected values written back to stored assertions.

The initial public import for advanced/core consumers is:

```python
from kernel.core.semantics import SemanticsProfile, inspect_semantics_profile
```

`SemanticsProfile` validates profile shape, generic rule-projection
entries, uncertainty projection policy names, and the B-time temporal
no-op boundary. `inspect_semantics_profile(profile)` returns a JSON-like
summary of which projection lanes are configured without running an
adapter or mutating the profile.

Adapter migration is intentionally staged:

- Track 3 / C consumes `SemanticsProfile.rule_projection.problog` and
  normalizes `kind="branch_probability"` entries into the adapter-local
  `ProbLogRuleExt` bridge. Omitted branches default to `1.0`.
- Track 3 / D will decide PyReason temporal and interval consumption.
- Track 3 / E will decide the durable SDK/service runtime call-site.
