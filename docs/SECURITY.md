# Security Guide

## Scope

This document records the current repository-level security hygiene rules for local development and operator workflows.

It currently covers:

- local secret handling via `.env`
- kernel service API key authentication
- key rotation expectations

It does not yet cover:

- RBAC or per-user permissions
- API audit logging
- rate limiting
- external secret-manager integration

## Secret Handling

- Local development uses `.env`, which is gitignored.
- `.env.example` is committed and must never contain real values.
- Production deployments should inject secrets as environment variables or via a secret manager.
- Do not bake `.env` into container images or deployment artifacts.
- If you suspect a secret was exposed, rotate it immediately.

## `.env` Rules

- Create `.env` by copying `.env.example`.
- Keep real values only in `.env`, never in `.env.example`.
- Do not paste secrets into notebooks, markdown files, or test fixtures.
- Verify `.env` remains ignored with `git check-ignore .env`.

## Kernel API Key Auth

Kernel service v1 routes are protected by `X-FactPy-API-Key` unless authentication is explicitly disabled for local development.

Server-side variables:

- `FACTPY_KERNEL_API_KEYS`
  - Comma-separated allow-list of valid API keys.
- `FACTPY_KERNEL_AUTH_DISABLED`
  - Local-development escape hatch. Must be unset or `false` in production.

Client-side variable convention:

- `FACTPY_KERNEL_API_KEY`
  - Single key used by HTTP callers such as `HttpRuntimeAPI`.

## Rotation Checklist

- [ ] Generate a new key at the provider.
- [ ] Update local `.env`.
- [ ] Update deployed environment variables or secret manager entries.
- [ ] Verify the new key works.
- [ ] Revoke the old key.
- [ ] Record the rotation date in your operator notes.

## Optional Guardrail

The repository includes `scripts/check_no_secrets_in_env_example.sh`.

It is a lightweight guardrail that fails if `.env.example` contains uncommented non-empty values.

