# Task Blueprint Audit: Round Story Demo Suite

- Blueprint: [2026-05-07_round-story-demo-suite.md](./2026-05-07_round-story-demo-suite.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-07 | scoped | Blueprint created | User identified that the all-in-one notebook loses the thematic chapter structure that made the archived examples useful. |

## Decision Notes

### 2026-05-07 — Script vs Notebook Roles

`round_story_full_demo.py` remains the deterministic smoke harness and source of
truth. Root notebooks become focused presentation chapters that import the
script and run chapter-specific functions.
