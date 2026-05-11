# Core Semantics Module

`kernel.core.semantics` contains value objects and helpers for runtime
projection semantics. In Track 3 / B it introduces `SemanticsProfile`
as scaffolding only:

- no SDK namespace export;
- no service endpoint;
- no adapter consumption;
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

Adapter migration is intentionally deferred:

- Track 3 / C will decide ProbLog consumption.
- Track 3 / D will decide PyReason temporal and interval consumption.
- Track 3 / E will decide the durable SDK/service runtime call-site.
