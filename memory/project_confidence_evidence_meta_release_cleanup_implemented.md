# Confidence / Evidence Meta Release Cleanup Implemented

Date: 2026-05-13

Source commit: `843cf515`

Milestone branch:

- `origin/milestone/confidence-evidence-meta-release-cleanup-2026-05-13 = 843cf515`

## Summary

The confidence / evidence meta release cleanup slice is implemented, archived,
and published. It is a defensive pre-release cleanup that stops legacy
candidate-level confidence fields and generic `meta.confidence` from becoming
default public or persisted semantics.

## Landed Behavior

- `CandidateSet.confidence` and `CandidateSet.confidence_kind` remain
  internal/session compatibility carriers.
- Runtime accept remains parse-compatible with old candidate payloads that echo
  `confidence` or `confidence_kind`.
- `accept(...)` no longer writes candidate confidence fields into assertion
  meta by default.
- Generic `meta.confidence` remains a ledger meta row but is not projected into
  shared derived annotations.
- Legacy confidence differences do not affect duplicate detection.
- ProbLog export no longer falls back to generic `meta.confidence`; adapter
  probability must come from `problog/semantic/probability` or the internal
  shared semantic probability lane, otherwise default `1.0`.
- PyReason sessions keep adapter-native `pyreason/semantic/bound_*` lanes and
  filter generic `confidence` / `confidence_source` from shared metadata.
- Service candidate DTOs and candidate inventory omit legacy confidence fields
  by default.
- Candidate evidence trees do not lift generic assertion `meta.confidence` into
  default evidence/certainty display.

## Validation

- Confidence cleanup baseline: 11/11 OK.
- Full kernel discovery: 2198 OK / 1 skipped.
- `git diff --check`: clean.
- Post-publish verification confirmed `origin/master`, the milestone branch,
  release branch, and rc tags.

## Remaining Work

- A future confidence/certainty/probability redesign can introduce an explicit
  public confidence model if needed.
- Explain/evidence user surface design remains independent.
- Read-time display confidence aggregation remains unchanged.
