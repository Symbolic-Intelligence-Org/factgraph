# Service layer current state (kernel-core perspective)

- Scope: the dependency relationship between the HTTP/BFF delivery
  layer and `kernel.core`
- Last updated: 2026-05-06 (post Round Story Completion routemap
  closure @ `6b32972`)
- Perspective: this document describes the service layer **from the
  core perspective** — how core expects service to call it and
  which core invariants service must respect. Detailed service-side
  routes / DTOs are documented by the service module's own overview
  (monorepo; not in the kernel-only package).

## 1. Entry points and dependencies

- Service entry: `service.app_v1`
- ASGI app: `service.app_v1:app`
- Optional dependency: `pip install -e '.[service]'`

Recommended startup:

```bash
python -m uvicorn service.app_v1:app --reload
```

## 2. Layer position

Service sits above `kernel.core` as the HTTP / BFF delivery facade.

Service is responsible for:

- HTTP routes and JSON DTOs
- runtime session lifecycle and orchestration
- a uniform error envelope (`ok / errors / meta`)
- a registry-file read facade
- API key authentication (`X-FactPy-API-Key`)

Service is not responsible for (these are owned by core):

- core semantic definitions (policy / chosen / where / evaluate /
  accept)
- live `Ledger` / `Store` internal state management
- dependency ordering and atomic rollback for
  `accept_many_candidate_sets(...)`
- adapter registration via `register_engine_evaluator(...)` (which
  is triggered by the adapter at its own import time)
- the field semantics of the ProjectorAudit contract
- HTTP wrappers for Batch 3-7 application capabilities (per the
  Batch 8 public-surface decision; these go via advanced importable)

## 3. Current v1 route overview

The detailed route list + DTOs live in §4 of the service module's
own overview doc (monorepo; not in the kernel-only package). This
section does not duplicate the route list; it only lists the
categories:

- **rules**: validate / compile-preview / profiles
- **runtime session**: open / get / delete + writes (set / add /
  retract) + claims
- **runtime queries**: explain-fact / conflicts / resolve-mapping /
  view-facts
- **runtime views**: create / update / delete / get / list
- **runtime rule/derivation/package**: rules.run / derivations.evaluate
  / derivations.accept / packages.export
- **registry**: manifest / schema.read / assets.list / rules.read /
  derivations.read

## 4. Service-to-core delegation pattern

Service routes go through stable entry points of `kernel.core`;
**service does not reimplement core semantics**. Typical delegation:

| Service route | Core / application entry point |
|---|---|
| `POST /v1/runtime/sessions/open` | `Ledger(path=...)` construction |
| `POST /v1/runtime/sessions/{id}/writes/{set,add,retract}` | `kernel.core.write_protocol.{set,add,retract}_write(...)` |
| `POST /v1/runtime/sessions/{id}/queries/view-facts` | `kernel.core.store.queries.project_view_facts_with_audit(...)` |
| `POST /v1/runtime/sessions/{id}/rules/run` | `kernel.core.rules.run_rule(...)` |
| `POST /v1/runtime/sessions/{id}/derivations/evaluate` | `Store.evaluate(mode=...)` over `native | souffle | problog | pyreason` |
| `POST /v1/runtime/sessions/{id}/derivations/accept` | `Store.accept_many_candidate_sets(...)` |
| `POST /v1/runtime/sessions/{id}/packages/export` | adapter export (e.g. `package_kind="audit"`) |

Service rejects the following anti-patterns (which would break core
invariants):

- bypassing `write_protocol` to mutate the `Ledger` SQLite tables
  directly
- reimplementing `evaluate_where(...)` argument logic (rule action
  overlay extensions go through application runtime, not service)
- maintaining a schema-digest cache at the service layer (owned by
  core's `Store`)
- consuming `kernel.application.protocol.*` internal dataclasses
  directly (only via application runtime entry points)

## 5. DTO adapter responsibility

Service acts as a **DTO adapter** at the HTTP boundary, converting
JSON request/response into core / application protocol DTOs:

- **Inbound** — request JSON → strictly construct core / application
  protocol DTOs (running full `__post_init__` validation); **no
  half-DTOs** (no partial-fill of fields).
- **Outbound** — core / application result DTOs → JSON envelope
  `{ok, data, errors, meta}`; **never expose internal core
  dataclass `repr`**.
- **No adding/removing DTO fields** — service may not add
  service-only fields to core / application DTOs; service-only
  metadata goes through the envelope's `meta`.

DTO adapter shared helpers:

- `kernel.application.protocol.common._validate_*` (protocol DTO
  validation)
- `service._common.{ok, error}` (envelope wrapping)

## 6. Error propagation across layers

Errors raised by core / application are mapped to the envelope in
specific → generic order. **Core / application themselves do not
care about HTTP / envelope shape**; raw exceptions are wrapped by
service:

| Core / application exception | Envelope shape | HTTP status |
|---|---|---|
| `ProtocolShapeError` (application protocol DTO validation failure) | `errors[0].kind="shape"`, `path` points at the field | 200 |
| `AuditQueryError` (generic audit query error) | `errors[0].kind="audit"` | 200 |
| `AuditOptionalDomainError` (missing domain bundle, kernel-only wheel) | `errors[0].kind="audit_optional_domain"` | 200 |
| Authentication failure | (does not enter the envelope; HTTP error directly) | 401 / 503 |
| Other uncaught exceptions | `app_v1` global handler wraps them as `errors[0].kind="runtime"`, `details.message=str(exc)` | 200 |

**Core principle:** core / application raise raw exceptions
(`ValueError` / `TypeError` / specific `*Error`); service is solely
responsible for envelope wrapping and **does not** leak the
envelope concept back into core / application.

## 7. Key behavioral contracts (current implementation)

### 7.1 `view-facts`

- When `include_audit=true`, `view.audit` returns a
  `ProjectorAudit` from the core projector
- `temporal_view` has been removed; passing it returns a shape
  error
- `view_name` and `view` are mutually exclusive; if neither is
  provided, the session default view is used

### 7.2 derivation and rule runtime

- The runtime path also rejects `temporal_view` (explicit shape
  error)
- `derivations/evaluate` returns candidates that
  `derivations/accept` then echoes back
- `derivations/accept` returns a serialized `AcceptResult`
  (including `diagnostics_contract_version`)
- `rules/compile-preview` and the registry read interface preserve
  declarative metadata such as `description / tags` from the
  compiled assets; service does not interpret the runtime semantics
  of these fields

### 7.3 Global exception envelope

Uncaught exceptions are uniformly wrapped by the `app_v1` global
handler (HTTP 200):

- `ok=false`
- `errors[0].kind="runtime"`
- `errors[0].path="$"`
- `errors[0].details.message=str(exc)`

## 8. Cross-references

- Service's own complete documentation: the service module's own
  overview doc (monorepo; not in the kernel-only package)
- Core public contract:
  [`04_public_contract_v1.md`](./04_public_contract_v1.md)
- Application advanced-importable surface:
  [`src/kernel/application/docs/01_overview_en.md`](../../application/docs/01_overview_en.md)
- Audit package contract:
  [`src/kernel/audit/docs/03_audit_package_contract.md`](../../audit/docs/03_audit_package_contract.md)
- Batch 8 public-surface decision: archived `public-surface`
  blueprint inside the routemap (monorepo; not in the kernel-only
  package)

## 9. Notes

- service v1 is no longer a thin rules-only layer; it now carries
  the first usable batch of runtime / BFF interfaces.
- The service-to-core contract should be kept in sync; the core
  side lives in
  [`04_public_contract_v1.md`](./04_public_contract_v1.md).
- Post-routemap state (2026-05-06): the service layer has not
  introduced new HTTP routes wrapping Batch 3-7 application
  capabilities (per the Batch 8 public-surface decision); Check /
  Diagnose / Fact Overlay / Why-not / ProofFrame / rule actions /
  round events / proof_frame_diff all go through the advanced
  importable surface (in-process Python calls into
  `kernel.application` / `kernel.audit`).
