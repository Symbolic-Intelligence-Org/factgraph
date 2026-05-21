from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from factgraph.authoring.apply_execute import build_authoring_publish_workflow_apply_bundle_dto
from factgraph.authoring.dsl_bridge import (
    build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_dto,
    build_authoring_publish_workflow_from_dsl_inputs_dry_run_bundle_safe_dto,
    build_authoring_session_from_dsl_inputs_dto,
    build_authoring_session_from_dsl_inputs_safe_dto,
)
from factgraph.authoring.registry_fs import FileAuthoringRegistry
from factgraph.authoring.schema_dsl_parse import (
    AuthoringSchemaDSLParseError,
    parse_authoring_schema_dsl_v1,
)
from factgraph.authoring.session import build_authoring_session_dto
from factgraph.authoring.workflow import build_authoring_publish_workflow_dry_run_bundle_dto


# Q8 Phase 2 (Slice 6): rule/inference CLI surface removed alongside the
# SavedRule persistence layer. The CLI is schema-only:
#   * `--rule-request` / `--derivation-request` / `--rule-dsl` / `--derivation-dsl`
#     payload args are removed.
#   * `registry-list --kind rule_ids|inference_ids|rule_versions|inference_versions`
#     subcommand kinds are removed.
#   * `registry-show --kind rule|inference` subcommand kinds are removed.
#   * `_rule_request_from_dsl` / `_derivation_request_from_dsl` helpers are removed.
# Schema-only flows (`--authoring-schema`, `--schema-dsl`) and schema-related
# `registry-list --kind apply_run_ids` / `registry-show --kind manifest|schema|apply-run`
# are preserved.


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

    apply_execute = sub.add_parser("apply-execute")
    _add_common_payload_args(apply_execute)
    apply_execute.add_argument("--registry-dir", required=True)
    apply_execute.add_argument("--apply-request-id")
    apply_execute.add_argument("--transaction-policy")

    registry_list = sub.add_parser("registry-list")
    registry_list.add_argument("--registry-dir", required=True)
    registry_list.add_argument(
        "--kind",
        required=True,
        choices=("apply_run_ids",),
    )

    registry_show = sub.add_parser("registry-show")
    registry_show.add_argument("--registry-dir", required=True)
    registry_show.add_argument(
        "--kind",
        required=True,
        choices=("manifest", "schema", "apply-run"),
    )
    registry_show.add_argument("--id")
    registry_show.add_argument("--version")
    registry_show.add_argument("--latest", action="store_true")

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

    if args.command == "apply-execute":
        if not has_any_json and not has_any_dsl:
            raise AuthoringCLIError("apply-execute requires at least one payload input")
        if args.safe and has_any_dsl:
            raise AuthoringCLIError("--safe is not supported for apply-execute; use workflow-dry-run --safe")
        if args.safe and not has_any_dsl:
            raise AuthoringCLIError("--safe is only supported with DSL inputs")
        if has_any_dsl:
            authoring_schema = _parse_schema_dsl(schema_dsl)
        registry = FileAuthoringRegistry(args.registry_dir)
        return build_authoring_publish_workflow_apply_bundle_dto(
            registry=registry,
            authoring_schema=authoring_schema,
            apply_request_id=args.apply_request_id,
            transaction_policy=args.transaction_policy,
        )

    if args.command == "registry-list":
        registry = FileAuthoringRegistry(args.registry_dir)
        list_kind = str(args.kind)
        if list_kind == "apply_run_ids":
            items = registry.list_apply_run_ids()
        else:
            raise AuthoringCLIError(f"unsupported registry list kind: {list_kind}")
        return {
            "kind": "authoring_registry_list_result",
            "list_kind": list_kind,
            "registry_dir": str(registry.root_dir),
            "count": len(items),
            "items": items,
        }

    if args.command == "registry-show":
        registry = FileAuthoringRegistry(args.registry_dir)
        show_kind = str(args.kind)
        item: dict[str, Any] | None = None
        if show_kind == "manifest":
            item = registry.read_manifest()
        elif show_kind == "schema":
            item = registry.get_schema_entry()
        elif show_kind == "apply-run":
            if not args.id:
                raise AuthoringCLIError("--id is required for --kind apply-run")
            if args.version:
                raise AuthoringCLIError("--version is not supported for --kind apply-run")
            if args.latest:
                raise AuthoringCLIError("--latest is not supported for --kind apply-run")
            item = registry.find_apply_execute_run(args.id)
        else:
            raise AuthoringCLIError(f"unsupported registry show kind: {show_kind}")
        return {
            "kind": "authoring_registry_show_result",
            "show_kind": show_kind,
            "registry_dir": str(registry.root_dir),
            "id": args.id,
            "version": args.version,
            "latest": bool(args.latest),
            "item": item,
        }

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


def _parse_schema_dsl(schema_dsl: str | None) -> dict[str, Any] | None:
    if schema_dsl is None:
        return None
    try:
        return parse_authoring_schema_dsl_v1(schema_dsl)
    except AuthoringSchemaDSLParseError as exc:
        raise AuthoringCLIError(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
