# Task Blueprint Audit: Inference Wire And Registry Vocabulary

- Blueprint: [2026-05-12_inference-wire-registry-vocabulary.md](./2026-05-12_inference-wire-registry-vocabulary.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed created after Blueprint 1 shipped public SDK `Inference` + `FactGraph.create(...)`. Source audit found the remaining user-visible derivation vocabulary concentrated in service runtime routes/payloads, registry service route/DTOs, SDKRegistry/FileAuthoringRegistry method names, and file-registry manifest/path shape. Deep substrate remains broad: authoring compiler, application DTOs, `CandidateSet.derivation_id`, core store, proof/audit/static UI. Draft frames G0 around that split. |

## Decision Notes

- 2026-05-12 draft: The load-bearing question is whether this slice renames durable registry storage (`derivations/` manifest/path) or only public service/registry wrappers.
- 2026-05-12 draft: Candidate payload fields are intentionally called out as a likely non-goal because runtime accept echoes `CandidateSet` objects and core/audit/proof consumers all depend on `derivation_id`.
- 2026-05-12 draft: Application/core DTO names such as `CompiledDerivationPlan` are treated as substrate unless G0 explicitly expands into a much larger proof/candidate protocol rename.

