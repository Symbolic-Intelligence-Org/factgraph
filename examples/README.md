# Examples

This directory now keeps one canonical current demo pair at the repository root:

- `round_story_full_demo.py` — authoritative, deterministic, assertion-bearing
  script for the current v0.1 round story.
- `round_story_full_demo.ipynb` — readable notebook wrapper around the script.

Run the script from the repository root:

```bash
python examples/round_story_full_demo.py
```

The demo uses the default native engine only. It covers SDK-authored setup,
Q1-Q5 application capabilities, ProofFrame recheck, the three rule overlay
operations, durable round events, ProofFrame diff, and the Batch 8 public
boundary: SDK shells and service routes for Batch 3-7 are intentionally not
shipped in v0.1.

Historical sectional notebooks and scripts live in `examples/archive/`. They
are retained for reference, but they are not the recommended current journey.
