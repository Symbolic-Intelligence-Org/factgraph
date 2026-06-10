# Security Guide

## Scope

This document covers security hygiene for the FactGraph package and local repository development.

It covers:

- local secret handling via `.env`
- `.env.example` hygiene
- release-surface expectations for the `factgraph` package

It does not cover:

- HTTP service authentication (monorepo-only; see `docs/SECURITY_monorepo.md`)
- RBAC or per-user permissions
- API audit logging
- rate limiting
- external secret-manager integration

The `factgraph` wheel does not expose network endpoints, does not implement remote authentication, and does not contact external services unless user code explicitly does so through optional adapters or application-specific integrations.

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

## Optional Guardrail

The repository includes `scripts/check_no_secrets_in_env_example.sh`.

It is a lightweight guardrail that fails if `.env.example` contains uncommented non-empty values.

## Reporting Vulnerabilities

Before public release, finalize the reporting channel in the public repository. Preferred target: GitHub Security Advisories for the public `factgraph` repository.
