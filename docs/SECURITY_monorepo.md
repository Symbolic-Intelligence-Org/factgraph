# Monorepo Security Notes

This document is for private monorepo operators. It is not part of the v0.1 kernel-only wheel contract. Public kernel users should start with `docs/SECURITY.md`.

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
