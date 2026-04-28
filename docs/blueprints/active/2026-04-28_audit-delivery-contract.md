# Task Blueprint: Audit Delivery Contract

- Status: implemented
- Created: 2026-04-28
- Last Updated: 2026-04-28
- Related Modules:
  - `src/kernel/audit/`(audit package reader / query / DTO / evidence graph consumer surface)
  - `src/service/static_ui.py`(rendered static audit site delivery)
  - `src/domains/ecss/`(ECSS compliance row semantics and predicate presets)
  - `docs/README.md`(durable docs entrypoint)
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/active/2026-04-28_runtime-authority-cleanup.md](./2026-04-28_runtime-authority-cleanup.md)(kept separate; runtime authority cleanup does not own audit delivery)
- Audit Log:
  - [2026-04-28_audit-delivery-contract.audit.md](./2026-04-28_audit-delivery-contract.audit.md)

## 1. Problem

The audit layer has a substantial offline consumption surface, but its current documentation has drifted after the namespace split:

- `kernel.audit.__init__` says `render_audit_static_site` moved to `service.static_ui`, while `src/kernel/audit/docs/01_overview.md` still says audit owns static site rendering.
- ECSS compliance row assembly now lives in `domains.ecss.compliance`, while audit and ECSS docs still describe `audit.compliance` / `kernel.ecss` era ownership.
- `site_manifest.json` / `ui_index.json` and audit package optional files are real delivery contracts, but the stable vs generated parts are not documented in one place.
- Provenance carriers exist across `provenance_trees`, `provenance_statuses`, `evidence_graphs`, and `provenance_timelines`, but the minimum responsibility mapping is not stated.

This is a documentation and contract-productization task. It must not be folded into runtime-authority cleanup.

## 2. Goals

- Correct module docs so they match current code ownership:
  - `kernel.audit` = audit package reader / query / DTO / evidence graph consumer surface
  - `service.static_ui` = rendered static site owner
  - `domains.ecss.compliance` = ECSS compliance row assembly owner
- Document audit package contract:
  - required files
  - optional files and backward compatibility
  - query-derived vs durable package surfaces
  - minimum provenance carrier mapping
- Document rendered static site contract:
  - caller-provided `out_dir`
  - generated pages
  - `site_manifest.json` stable fields
  - `ui_index.json` consumer-facing index role
- Update durable docs entrypoints.

## 3. Non-goals

- No code behavior changes.
- No package exporter changes.
- No static site template redesign.
- No full W3C PROV implementation.
- No migration of runtime authority or SDK/application boundaries.
- No branch / commit in this local pass.

## 4. Current Context

- `src/kernel/audit/__init__.py` already records the namespace split notes for static UI and ECSS compliance.
- `src/service/static_ui.py` owns `render_audit_static_site(package_dir, out_dir)` and returns `site_manifest`.
- `AuditQuery.list_compliance_matrix()` lazily imports `domains.ecss.compliance` to avoid an import-time domain dependency.
- Existing tests already cover audit package loading, static site rendering, provenance statuses, evidence graphs, compliance matrix, and old-package compatibility.
- Current docs are stale in:
  - `src/kernel/audit/docs/01_overview.md`
  - `src/kernel/audit/docs/README.md`
  - `src/domains/ecss/docs/README.md`
  - `src/domains/ecss/docs/01_overview.md`
  - `docs/README.md`

## 5. Proposed Shape

Add two durable docs:

- `src/kernel/audit/docs/03_audit_package_contract.md`
  - audit package reader contract
  - required / optional audit files
  - query-derived surfaces
  - provenance carrier mapping
- `src/service/docs/05_audit_static_site_contract.md`
  - `service.static_ui` ownership
  - rendered files and directories
  - stable manifest/index fields
  - non-goals and compatibility notes

Then update existing overview/README docs to point to the new contract docs and remove obsolete ownership claims.

## 6. Boundaries And Invariants

- Keep `kernel.audit` free of static-site ownership claims.
- Keep `service.static_ui` as the rendered static site owner.
- Keep `domains.ecss.compliance` as compliance row assembly owner.
- Do not claim `site_manifest.json` or `ui_index.json` fields are all stable; explicitly separate stable consumer fields from generated lookup details.
- Do not claim full PROV conformance; document only the current minimum mapping.
- Keep runtime-authority blueprint unchanged except as a related context reference.

## 7. Acceptance

- [x] Audit docs no longer list `static_ui.py` or `compliance.py` as `src/kernel/audit` modules.
- [x] Audit overview states the current boundary between `kernel.audit`, `service.static_ui`, and `domains.ecss.compliance`.
- [x] Audit package contract doc exists and documents required/optional files.
- [x] Static site contract doc exists and documents `site_manifest.json` / `ui_index.json`.
- [x] ECSS docs state that compliance row assembly belongs to `domains.ecss.compliance`, while audit exposes a lazy query convenience.
- [x] Root docs and module READMEs point to the new docs.
- [x] No production code changes.

## 8. Implementation Plan

1. Create this blueprint and audit log.
2. Add audit package contract doc under `src/kernel/audit/docs/`.
3. Add static site contract doc under `src/service/docs/`.
4. Patch audit overview/README to match current ownership.
5. Patch ECSS docs to match current ownership.
6. Patch service README and root docs README.
7. Run text grep checks for obsolete owner claims.

## 9. Docs To Update

- `src/kernel/audit/docs/README.md`
- `src/kernel/audit/docs/01_overview.md`
- `src/kernel/audit/docs/03_audit_package_contract.md`
- `src/service/docs/README.md`
- `src/service/docs/05_audit_static_site_contract.md`
- `src/domains/ecss/docs/README.md`
- `src/domains/ecss/docs/01_overview.md`
- `docs/README.md`
- This blueprint audit log

## 10. Outcome / Deviations

- 最终落地结果:
  - Added `src/kernel/audit/docs/03_audit_package_contract.md`.
  - Added `src/service/docs/05_audit_static_site_contract.md`.
  - Updated audit, service, ECSS, and root docs so current ownership is explicit.
- 与 blueprint 不同的地方:
  - Also touched `src/kernel/audit/docs/02_evidence_graph.md` to replace ambiguous `static_ui.py` wording with `service.static_ui`.
- 为什么会有这些调整:
  - The stale wording was not a module list entry, but it could still imply the old audit-local static UI ownership.
- 归档说明:
  - Per the v0.1 archive policy:archive after actual v0.1 publish + short stability window. The four `implemented` blueprints under `docs/blueprints/active/`(OS-prep readiness,runtime-authority cleanup,audit-delivery contract,RC verification)are bundled together for archive after the same gate.
