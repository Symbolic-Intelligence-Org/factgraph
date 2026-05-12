# Task Blueprint Audit: Inference Wire And Registry Vocabulary

- Blueprint: [2026-05-12_inference-wire-registry-vocabulary.md](./2026-05-12_inference-wire-registry-vocabulary.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed created after Blueprint 1 shipped public SDK `Inference` + `FactGraph.create(...)`. Source audit found the remaining user-visible derivation vocabulary concentrated in service runtime routes/payloads, registry service route/DTOs, SDKRegistry/FileAuthoringRegistry method names, and file-registry manifest/path shape. Deep substrate remains broad: authoring compiler, application DTOs, `CandidateSet.derivation_id`, core store, proof/audit/static UI. Draft frames G0 around that split. |
| 2026-05-12 | draft-polish | Candidate/substrate boundary clarified | Added explicit acknowledgement that `/inferences/*` routes may still return `CandidateSet` payloads containing `derivation_id` / `derivation_version` under the recommended boundary; added Path A/Path B decision summary; documented W6b as a weak middle path; added pre-release developer workspace guidance if registry storage moves to `inferences/`; and recorded the stale service-test `Derivation` import as G1 cleanup independent of G0 decisions. |
| 2026-05-12 | draft-polish | Per-spec registry JSON question added | Added Q13 to resolve the W6a/W9a crossing: registry manifest/path may move to inference vocabulary while the authoring compiler keeps `derivation_id`. Recommended W13a translates at the `FileAuthoringRegistry` boundary so per-spec JSON files use `inference_id` while compiler/core substrate stays unchanged. |

## Decision Notes

- 2026-05-12 draft: The load-bearing question is whether this slice renames durable registry storage (`derivations/` manifest/path) or only public service/registry wrappers.
- 2026-05-12 draft: Candidate payload fields are intentionally called out as a likely non-goal because runtime accept echoes `CandidateSet` objects and core/audit/proof consumers all depend on `derivation_id`.
- 2026-05-12 draft: Application/core DTO names such as `CompiledDerivationPlan` are treated as substrate unless G0 explicitly expands into a much larger proof/candidate protocol rename.
- 2026-05-12 draft polish: Preferred path is aggressive public/service/registry vocabulary cleanup while preserving deep candidate/proof substrate. Conservative path is runtime service-only cleanup. The partial route of public inference naming over durable `derivations/` storage is discouraged unless source audit finds a hard blocker.
- 2026-05-12 draft polish: Q13 makes the registry workspace boundary explicit. If W13a locks, developer-visible registry files use inference vocabulary, while compiler/core continue to consume derivation vocabulary via a narrow translation at the file-registry boundary.
