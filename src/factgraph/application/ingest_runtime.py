"""Application-layer ingest runtime executor.

Commit 1 scope: thin orchestrator over existing application write primitives.

- IngestSetItem / IngestAddItem -> EntityWriteCommand -> plan_write_command -> apply_write_plan
- IngestRetractItem -> check_retract_allowed -> retract_by_asrt for unprotected/unknown asrt
- collect_mode='stop' aborts on first error; collect_mode='collect' aggregates and continues

SDK descriptor parsing / coercion is intentionally not performed here — SDK adapters
are expected to produce already-validated FieldPath / FieldValue / EntitySelector
instances before calling this executor.
"""
from __future__ import annotations

from typing import Any

from factgraph.core.evidence.write_protocol import retract_by_asrt
from factgraph.core.store import Database, RevocationInput
from factgraph.core.store.runtime import Store

from .entity_write import (
    EntityWriteError,
    _revocation_meta_entries,
    apply_write_plan,
    plan_write_command,
)
from .protocol import (
    EntityWriteCommand,
    ErrorDTO,
    FieldMutation,
    IngestAddItem,
    IngestRequest,
    IngestResult,
    IngestRetractItem,
    IngestSetItem,
    WarningDTO,
)
from .retract_guard import RetractGuardError, check_retract_allowed
from .schema_runtime import SchemaIndex, SchemaResolutionError


class IngestRuntimeError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        path: tuple[str, ...] = (),
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.path = tuple(path)
        self.details = dict(details or {})

    def to_error_dto(self) -> ErrorDTO:
        return ErrorDTO(
            code=self.code,
            message=str(self),
            path=self.path,
            details=self.details,
        )


def apply_ingest_request(
    request: IngestRequest,
    *,
    store: Store,
    index: SchemaIndex,
    database: Database | None = None,
) -> IngestResult:
    written: list[str] = []
    skipped: list[int] = []
    duplicate: list[int] = []
    errors: list[ErrorDTO] = []
    warnings: list[WarningDTO] = []

    for idx, item in enumerate(request.items):
        item_errors, item_warnings, item_written, item_skipped = _apply_item(
            idx,
            item,
            store=store,
            index=index,
            database=database,
        )
        errors.extend(item_errors)
        warnings.extend(item_warnings)
        written.extend(item_written)
        skipped.extend(item_skipped)
        if item_errors and request.collect_mode == "stop":
            break

    return IngestResult(
        written_assertion_ids=tuple(written),
        skipped_indices=tuple(skipped),
        duplicate_indices=tuple(duplicate),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _apply_item(
    idx: int,
    item: IngestSetItem | IngestAddItem | IngestRetractItem,
    *,
    store: Store,
    index: SchemaIndex,
    database: Database | None,
) -> tuple[list[ErrorDTO], list[WarningDTO], list[str], list[int]]:
    if isinstance(item, IngestRetractItem):
        return _apply_retract(idx, item, store=store, index=index, database=database)
    if isinstance(item, (IngestSetItem, IngestAddItem)):
        return _apply_write(idx, item, store=store, index=index, database=database)
    raise IngestRuntimeError(
        f"unsupported ingest item type: {type(item).__name__}",
        code="INGEST_UNSUPPORTED_ITEM",
        path=("items", str(idx)),
    )


def _apply_write(
    idx: int,
    item: IngestSetItem | IngestAddItem,
    *,
    store: Store,
    index: SchemaIndex,
    database: Database | None,
) -> tuple[list[ErrorDTO], list[WarningDTO], list[str], list[int]]:
    op = "set" if isinstance(item, IngestSetItem) else "add"
    command = EntityWriteCommand(
        target=item.target,
        mutations=(
            FieldMutation(
                op=op,
                field=item.field,
                value=item.value,
                meta=item.meta,
            ),
        ),
        create_if_missing=True,
    )
    try:
        plan = plan_write_command(command, store=store, index=index)
    except (EntityWriteError, SchemaResolutionError) as exc:
        return ([_exc_to_error_dto(exc, path=("items", str(idx)))], [], [], [])
    except Exception as exc:  # pragma: no cover - defensive  # noqa: BLE001 - write planning crosses the schema index and store adapters; every fault becomes the INGEST_PLAN_FAILED item error.
        return (
            [
                ErrorDTO(
                    code="INGEST_PLAN_FAILED",
                    message=str(exc),
                    path=("items", str(idx)),
                    details={"exception": type(exc).__name__},
                )
            ],
            [],
            [],
            [],
        )
    if not plan.can_apply:
        return (list(plan.errors), list(plan.warnings), [], [])
    result = apply_write_plan(plan, store=store, index=index, database=database)
    written: list[str] = []
    skipped: list[int] = []
    for applied in result.applied:
        if applied.status == "applied" and applied.assertion_id is not None:
            written.append(applied.assertion_id)
        elif applied.status == "skipped":
            skipped.append(idx)
    return (list(result.errors), list(result.warnings), written, skipped)


def _apply_retract(
    idx: int,
    item: IngestRetractItem,
    *,
    store: Store,
    index: SchemaIndex,
    database: Database | None,
) -> tuple[list[ErrorDTO], list[WarningDTO], list[str], list[int]]:
    # Slice 2 Step 4: application ingest path leg of three-layer retract guard.
    # check_retract_allowed raises RetractGuardError for INV-7c-protected
    # Identity Claims or :exists Claims (existence-claim transitional guard).
    # Field Claims and unknown asrt pass-through to retract_by_asrt unchanged.
    try:
        check_retract_allowed(
            item.assertion_id,
            ledger=store.ledger,
            schema_index=index,
        )
    except RetractGuardError as guard_exc:
        if guard_exc.classification == "identity":
            message = (
                f"Identity Claim {guard_exc.asrt_id} "
                f"(pred_id={guard_exc.pred_id}) is immutable per INV-7c; "
                "Identity bundle modification requires delete + recreate of the entity. "
                "See ADR-IC §4.1."
            )
        else:  # classification == "exists"
            message = (
                f"<EntityType>:exists Claim {guard_exc.asrt_id} "
                f"(pred_id={guard_exc.pred_id}) cannot be retracted independently; "
                ":exists is co-emitted atomically with Identity Claims (existence-claim "
                "transitional guard). See ADR-IC §4.4."
            )
        return (
            [
                ErrorDTO(
                    code=guard_exc.code,  # propagated directly, NOT wrapped in INGEST_RETRACT_FAILED
                    message=message,
                    path=("items", str(idx)),
                    details={
                        "assertion_id": guard_exc.asrt_id,
                        "pred_id": guard_exc.pred_id,
                        "classification": guard_exc.classification,
                    },
                )
            ],
            [],
            [],
            [],
        )
    try:
        if database is None:
            revoker_id = retract_by_asrt(
                store.ledger,
                item.assertion_id,
                dict(item.meta) or None,
            )
        else:
            existing_revoker = store.ledger.find_revoker(item.assertion_id)
            if existing_revoker is not None:
                revoker_id = existing_revoker
            else:
                committed = database.commit_changes(
                    assertions=(),
                    revocations=(
                        RevocationInput(
                            revoked_asrt_id=item.assertion_id,
                            meta=_revocation_meta_entries(
                                item.assertion_id,
                                dict(item.meta) or None,
                            ),
                        ),
                    ),
                )
                revoker_id = committed.revocations[0].revoker_asrt_id
    except Exception as exc:  # noqa: BLE001 - ledger/SQLite retraction boundary; every fault becomes the INGEST_RETRACT_FAILED item error instead of a silent no-op.
        return (
            [
                ErrorDTO(
                    code="INGEST_RETRACT_FAILED",
                    message=str(exc),
                    path=("items", str(idx)),
                    details={"exception": type(exc).__name__, "assertion_id": item.assertion_id},
                )
            ],
            [],
            [],
            [],
        )
    if revoker_id is None:
        return ([], [], [], [idx])
    return ([], [], [revoker_id], [])


def _exc_to_error_dto(exc: Exception, *, path: tuple[str, ...]) -> ErrorDTO:
    code = getattr(exc, "code", None) or "INGEST_PLAN_FAILED"
    exc_path = getattr(exc, "path", None)
    final_path = tuple(exc_path) if exc_path else path
    details = getattr(exc, "details", None)
    return ErrorDTO(
        code=code,
        message=str(exc),
        path=final_path,
        details=dict(details or {}),
    )


__all__ = [
    "IngestRuntimeError",
    "apply_ingest_request",
]
