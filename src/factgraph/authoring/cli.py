from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from factgraph.authoring.dsl_bridge import (
    build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_dto,
    build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_safe_dto,
    build_authoring_session_from_dsl_inputs_dto,
    build_authoring_session_from_dsl_inputs_safe_dto,
)
from factgraph.authoring.session import build_authoring_session_dto
from factgraph.authoring.workflow import build_authoring_publish_workflow_dry_run_bundle_dto


# Slice 7C / Q6-A (a.2): apply-execute pipeline retired. CLI is now
# schema-only with `preflight` (session preview) and `workflow-dry-run`
# (publish-plan + apply-dry-run bundle) subcommands. The legacy
# `apply-execute`, `registry-list`, and `registry-show` subcommands were
# removed alongside `FileAuthoringRegistry`. For workspace migration, use
# the top-level `python -m factgraph migrate-workspace ...` CLI instead.


class AuthoringCLIError(Exception):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        payload = _dispatch(args)
    except AuthoringCLIError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factpy-authoring")
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight")
    _add_common_payload_args(preflight)

    workflow = sub.add_parser("workflow-dry-run")
    _add_common_payload_args(workflow)

    return parser


def _add_common_payload_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--authoring-schema")
    parser.add_argument("--schema-dsl")
    parser.add_argument("--safe", action="store_true")


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    authoring_schema = _maybe_read_json_file(getattr(args, "authoring_schema", None))
    schema_dsl = _maybe_read_text_file(getattr(args, "schema_dsl", None))
    _reject_mixed_json_and_dsl_inputs(
        authoring_schema=authoring_schema,
        schema_dsl=schema_dsl,
    )
    has_any_json = authoring_schema is not None
    has_any_dsl = schema_dsl is not None

    if args.command == "preflight":
        if not has_any_json and not has_any_dsl:
            raise AuthoringCLIError(
                "preflight requires at least one payload input (--authoring-schema or --schema-dsl)"
            )
        if has_any_dsl:
            if args.safe:
                return build_authoring_session_from_dsl_inputs_safe_dto(
                    schema_dsl=schema_dsl,
                )
            return build_authoring_session_from_dsl_inputs_dto(
                schema_dsl=schema_dsl,
            )
        if args.safe:
            raise AuthoringCLIError("--safe is only supported with DSL inputs")
        return build_authoring_session_dto(authoring_schema=authoring_schema)

    if args.command == "workflow-dry-run":
        if not has_any_json and not has_any_dsl:
            raise AuthoringCLIError("workflow-dry-run requires at least one payload input")
        if has_any_dsl:
            if args.safe:
                return build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_safe_dto(
                    schema_dsl=schema_dsl,
                )
            return build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_dto(
                schema_dsl=schema_dsl,
            )
        if args.safe:
            raise AuthoringCLIError("--safe is only supported with DSL inputs")
        session_dto = build_authoring_session_dto(authoring_schema=authoring_schema)
        return build_authoring_publish_workflow_dry_run_bundle_dto(session_dto)

    raise AuthoringCLIError(f"unsupported command: {args.command}")


def _maybe_read_json_file(path_value: str | None) -> dict[str, Any] | None:
    if path_value is None:
        return None
    path = Path(path_value)
    if not path.exists():
        raise AuthoringCLIError(f"missing JSON file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuthoringCLIError(f"invalid JSON at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuthoringCLIError(f"JSON payload must be object: {path}")
    return payload


def _maybe_read_text_file(path_value: str | None) -> str | None:
    if path_value is None:
        return None
    path = Path(path_value)
    if not path.exists():
        raise AuthoringCLIError(f"missing DSL file: {path}")
    return path.read_text(encoding="utf-8")


def _reject_mixed_json_and_dsl_inputs(
    *,
    authoring_schema: dict[str, Any] | None,
    schema_dsl: str | None,
) -> None:
    if authoring_schema is not None and schema_dsl is not None:
        raise AuthoringCLIError("cannot provide both --authoring-schema and --schema-dsl")


if __name__ == "__main__":
    raise SystemExit(main())
