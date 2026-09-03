from __future__ import annotations

import json
import math
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import TYPE_CHECKING, Any, Literal

from factgraph.application import (
    apply_write_plan,
    apply_write_plans,
    entity_type_from_ref,
    plan_write_command,
)
from factgraph.application.protocol import (
    EntityRef as AppEntityRef,
)
from factgraph.application.protocol import (
    EntitySelector as AppEntitySelector,
)
from factgraph.application.protocol import (
    EntityWriteCommand,
    EntityWritePlan,
    FieldMutation,
    FieldPath,
    PlannedOpDTO,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.protocol.digests import sha256_token

from .errors import SDKStoreError, SDKValueError
from .schema import Entity, Field, Identity

if TYPE_CHECKING:
    from .store import SDKStore


_ValueKind = Literal["scalar", "entity_ref", "handle"]


@dataclass(frozen=True)
class RefOp:
    handle_id: int
    entity_type: str
    entity_cls: type[Entity]
    identity_values: dict[str, Any]
    path: str


@dataclass(frozen=True)
class SetOp:
    handle_id: int
    entity_type: str
    field_name: str
    field: Field = dc_field(repr=False, compare=False)
    value_kind: _ValueKind = "scalar"
    value: Any = None
    meta: dict[str, Any] = dc_field(default_factory=dict)
    path: str = ""


@dataclass(frozen=True)
class AddOp:
    handle_id: int
    entity_type: str
    field_name: str
    field: Field = dc_field(repr=False, compare=False)
    value_kind: _ValueKind = "scalar"
    value: Any = None
    meta: dict[str, Any] = dc_field(default_factory=dict)
    path: str = ""


@dataclass(frozen=True)
class RetractOp:
    handle_id: int
    entity_type: str
    pred_id: str
    field_name: str
    assertion_id: str
    meta: dict[str, Any] = dc_field(default_factory=dict)
    path: str = ""


@dataclass(frozen=True)
class RecordExistsOp:
    handle_id: int
    entity_type: str
    pred_id: str
    meta: dict[str, Any] = dc_field(default_factory=dict)
    path: str = ""


BatchOp = RefOp | SetOp | AddOp | RetractOp | RecordExistsOp


@dataclass(frozen=True)
class BatchApplyResult:
    refs_by_handle_id: dict[int, str]
    assertion_ids: list[str]


@dataclass(frozen=True)
class BatchCommitResult:
    plan: BatchPlan
    apply_result: BatchApplyResult


@dataclass(frozen=True)
class BatchPlan:
    ops: list[BatchOp]
    warnings: list[str] = dc_field(default_factory=list)
    _application_handle_order: tuple[int, ...] = dc_field(default_factory=tuple, repr=False, compare=False)
    _application_plans_by_handle_id: dict[int, EntityWritePlan] = dc_field(default_factory=dict, repr=False, compare=False)

    # Wire plan is the commit-equivalent serialized representation of this in-memory BatchPlan.
    def export(self, sdk: SDKStore) -> WireBatchPlan:
        ref_index: dict[int, RefOp] = {}
        wire_ops: list[WireBatchOp] = []
        for op in self.ops:
            if isinstance(op, RefOp):
                wire_ref = WireRefOp(
                    kind="ref",
                    handle_id=op.handle_id,
                    entity_type=op.entity_type,
                    identity=_normalize_wire_identity(op.identity_values, path=op.path),
                    path=op.path,
                )
                ref_index[op.handle_id] = op
                wire_ops.append(wire_ref)
                continue
            if isinstance(op, (SetOp, AddOp)):
                schema_pred = sdk._schema_pred_for_field(op.field)
                pred_id = schema_pred.get("pred_id")
                if not isinstance(pred_id, str) or not pred_id:
                    raise SDKStoreError(f"invalid schema predicate for {op.path}: missing pred_id")
                value = _export_wire_value(op, ref_index=ref_index)
                wire_ops.append(
                    WireWriteOp(
                        kind="set" if isinstance(op, SetOp) else "add",
                        handle_id=op.handle_id,
                        entity_type=op.entity_type,
                        pred_id=pred_id,
                        field_name=op.field_name,
                        value=value,
                        meta=_normalize_json_object(op.meta, path=f"{op.path}.meta", allow_nested=True),
                        path=op.path,
                    )
                )
                continue
            if isinstance(op, RetractOp):
                wire_ops.append(
                    WireRetractOp(
                        kind="retract",
                        handle_id=op.handle_id,
                        entity_type=op.entity_type,
                        pred_id=op.pred_id,
                        field_name=op.field_name,
                        assertion_id=op.assertion_id,
                        meta=_normalize_json_object(op.meta, path=f"{op.path}.meta", allow_nested=True),
                        path=op.path,
                    )
                )
                continue
            if isinstance(op, RecordExistsOp):
                wire_ops.append(
                    WireRecordExistsOp(
                        kind="record_exists",
                        handle_id=op.handle_id,
                        entity_type=op.entity_type,
                        pred_id=op.pred_id,
                        meta=_normalize_json_object(op.meta, path=f"{op.path}.meta", allow_nested=True),
                        path=op.path,
                    )
                )
                continue
            raise SDKStoreError(f"unsupported batch op in export: {type(op).__name__}")
        return WireBatchPlan(
            wire_version="sdk_batch_plan_v1",
            schema_digest=_sdk_wire_schema_digest(sdk),
            ops=wire_ops,
        )

    def to_json(self, sdk: SDKStore) -> str:
        return self.export(sdk).to_json()

    def apply(self, sdk: SDKStore) -> BatchApplyResult:
        if not self.ops:
            return BatchApplyResult(refs_by_handle_id={}, assertion_ids=[])
        if self._application_handle_order:
            return _apply_application_batch_plan(self, sdk)
        if sdk._database is not None:
            sdk._database_for_application_write("fg.batch")
            path, reason = _first_unrepresentable_batch_op(self, sdk)
            raise SDKStoreError(
                f"{path}: attached batch operation cannot be represented by the "
                f"application write-plan protocol ({reason}); no writes were committed"
            )
        refs_by_handle_id: dict[int, str] = {}
        assertion_ids: list[str] = []
        identity_pred_index = _sdk_identity_pred_index(sdk)
        for op in self.ops:
            if isinstance(op, RefOp):
                identity_values = dict(op.identity_values)
                e_ref = sdk.entities.ref(op.entity_cls, **identity_values)
                refs_by_handle_id[op.handle_id] = e_ref
                _write_identity_predicates_for_ref(
                    sdk=sdk,
                    identity_pred_index=identity_pred_index,
                    e_ref=e_ref,
                    entity_type=op.entity_type,
                    identity_values=identity_values,
                    path=op.path,
                    assertion_ids=assertion_ids,
                )
                continue
            if isinstance(op, (SetOp, AddOp)):
                e_ref = refs_by_handle_id.get(op.handle_id)
                if e_ref is None:
                    raise SDKStoreError(f"plan invalid: missing RefOp before field op at {op.path or op.field_name}")
                value = _resolve_planned_value(op, refs_by_handle_id)
                meta = dict(op.meta) if op.meta else None
                if isinstance(op, SetOp):
                    asrt_id = sdk.fields.set(op.field, e_ref, value, meta=meta)
                else:
                    asrt_id = sdk.fields.add(op.field, e_ref, value, meta=meta)
                assertion_ids.append(asrt_id)
                continue
            if isinstance(op, RetractOp):
                meta = dict(op.meta) if op.meta else None
                try:
                    revoker_id = sdk.assertions.retract(op.assertion_id, meta=meta)
                except Exception as exc:
                    raise SDKStoreError(f"{op.path}: retract failed: {exc}") from exc
                if isinstance(revoker_id, str):
                    assertion_ids.append(revoker_id)
                continue
            if isinstance(op, RecordExistsOp):
                e_ref = refs_by_handle_id.get(op.handle_id)
                if e_ref is None:
                    raise SDKStoreError(f"plan invalid: missing RefOp before entity exists op at {op.path}")
                meta = dict(op.meta) if op.meta else None
                try:
                    asrt_id = set_field(sdk.ledger, op.pred_id, e_ref, [], meta)
                except Exception as exc:
                    raise SDKStoreError(f"{op.path}: entity exists write failed: {exc}") from exc
                assertion_ids.append(asrt_id)
                continue
            raise SDKStoreError(f"unsupported batch op: {type(op).__name__}")
        return BatchApplyResult(refs_by_handle_id=refs_by_handle_id, assertion_ids=assertion_ids)


@dataclass(frozen=True)
class WireRefOp:
    kind: Literal["ref"]
    handle_id: int
    entity_type: str
    identity: dict[str, Any]
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "handle_id": self.handle_id,
            "entity_type": self.entity_type,
            "identity": dict(self.identity),
            "path": self.path,
        }


@dataclass(frozen=True)
class WireWriteOp:
    kind: Literal["set", "add"]
    handle_id: int
    entity_type: str
    pred_id: str
    field_name: str
    value: dict[str, Any]
    meta: dict[str, Any]
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "handle_id": self.handle_id,
            "entity_type": self.entity_type,
            "pred_id": self.pred_id,
            "field_name": self.field_name,
            "value": dict(self.value),
            "meta": dict(self.meta),
            "path": self.path,
        }


@dataclass(frozen=True)
class WireRetractOp:
    kind: Literal["retract"]
    handle_id: int
    entity_type: str
    pred_id: str
    field_name: str
    assertion_id: str
    meta: dict[str, Any]
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "handle_id": self.handle_id,
            "entity_type": self.entity_type,
            "pred_id": self.pred_id,
            "field_name": self.field_name,
            "assertion_id": self.assertion_id,
            "meta": dict(self.meta),
            "path": self.path,
        }


@dataclass(frozen=True)
class WireRecordExistsOp:
    kind: Literal["record_exists"]
    handle_id: int
    entity_type: str
    pred_id: str
    meta: dict[str, Any]
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "handle_id": self.handle_id,
            "entity_type": self.entity_type,
            "pred_id": self.pred_id,
            "meta": dict(self.meta),
            "path": self.path,
        }


WireBatchOp = WireRefOp | WireWriteOp | WireRetractOp | WireRecordExistsOp


@dataclass(frozen=True)
class WireBatchPlan:
    wire_version: str
    schema_digest: str
    ops: list[WireBatchOp]

    def to_dict(self) -> dict[str, Any]:
        return {
            "wire_version": self.wire_version,
            "schema_digest": self.schema_digest,
            "ops": [op.to_dict() for op in self.ops],
        }

    def to_json(self) -> str:
        payload = self.to_dict()
        # Canonical JSON (sorted keys, compact separators) is required for stable snapshots and replay.
        return _canonical_json_dumps(payload)

    @classmethod
    def from_json(cls, text: str) -> WireBatchPlan:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SDKStoreError(f"invalid wire batch plan json: {exc}") from exc
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WireBatchPlan:
        if not isinstance(payload, dict):
            raise SDKStoreError("wire batch plan must be object")
        wire_version = payload.get("wire_version")
        schema_digest = payload.get("schema_digest")
        raw_ops = payload.get("ops")
        if wire_version != "sdk_batch_plan_v1":
            raise SDKStoreError(f"unsupported wire_version: {wire_version!r}")
        if not isinstance(schema_digest, str) or not schema_digest:
            raise SDKStoreError("wire batch plan schema_digest must be non-empty string")
        if not isinstance(raw_ops, list):
            raise SDKStoreError("wire batch plan ops must be list")

        ops: list[WireBatchOp] = []
        for idx, raw in enumerate(raw_ops):
            if not isinstance(raw, dict):
                raise SDKStoreError(f"wire ops[{idx}] must be object")
            kind = raw.get("kind")
            if kind == "ref":
                ops.append(_parse_wire_ref_op(raw, path=f"$.ops[{idx}]"))
            elif kind in {"set", "add"}:
                ops.append(_parse_wire_write_op(raw, path=f"$.ops[{idx}]"))
            elif kind == "retract":
                ops.append(_parse_wire_retract_op(raw, path=f"$.ops[{idx}]"))
            elif kind == "record_exists":
                ops.append(_parse_wire_record_exists_op(raw, path=f"$.ops[{idx}]"))
            else:
                raise SDKStoreError(f"wire ops[{idx}] unknown kind: {kind!r}")
        return cls(wire_version=wire_version, schema_digest=schema_digest, ops=ops)

    def apply(self, sdk: SDKStore, *, strict_schema: bool = True) -> BatchApplyResult:
        actual_digest = _sdk_wire_schema_digest(sdk)
        if strict_schema and self.schema_digest != actual_digest:
            raise SDKStoreError(
                f"wire plan schema_digest mismatch: expected {self.schema_digest}, actual {actual_digest}"
            )
        if not self.ops:
            return BatchApplyResult(refs_by_handle_id={}, assertion_ids=[])
        if sdk._database is not None:
            return _apply_attached_wire_batch_plan(self, sdk)

        entity_cls_by_type = _sdk_entity_cls_by_type(sdk)
        pred_index = _sdk_pred_field_index(sdk)
        record_exists_pred_index = _sdk_record_exists_pred_index(sdk)
        identity_pred_index = _sdk_identity_pred_index(sdk)
        refs_by_handle_id: dict[int, str] = {}
        entity_type_by_handle_id: dict[int, str] = {}
        assertion_ids: list[str] = []

        for op in self.ops:
            if isinstance(op, WireRefOp):
                if op.handle_id in refs_by_handle_id:
                    raise SDKStoreError(f"{op.path}: duplicate ref handle_id={op.handle_id}")
                entity_cls = entity_cls_by_type.get(op.entity_type)
                if entity_cls is None:
                    raise SDKStoreError(f"{op.path}: unknown entity_type for sdk schema: {op.entity_type}")
                identity_values = dict(op.identity)
                e_ref = sdk.entities.ref(entity_cls, **identity_values)
                refs_by_handle_id[op.handle_id] = e_ref
                entity_type_by_handle_id[op.handle_id] = op.entity_type
                _write_identity_predicates_for_ref(
                    sdk=sdk,
                    identity_pred_index=identity_pred_index,
                    e_ref=e_ref,
                    entity_type=op.entity_type,
                    identity_values=identity_values,
                    path=op.path,
                    assertion_ids=assertion_ids,
                )
                continue

            if isinstance(op, WireWriteOp):
                e_ref = refs_by_handle_id.get(op.handle_id)
                if e_ref is None:
                    raise SDKStoreError(f"{op.path}: missing preceding ref op for handle_id={op.handle_id}")
                handle_entity_type = entity_type_by_handle_id.get(op.handle_id)
                if handle_entity_type != op.entity_type:
                    raise SDKStoreError(
                        f"{op.path}: entity_type mismatch for handle_id={op.handle_id}: {op.entity_type} != {handle_entity_type}"
                    )
                field_desc = _resolve_wire_field_for_write_op(sdk=sdk, pred_index=pred_index, op=op)
                value = _resolve_wire_value_for_apply(op.value, sdk=sdk, path=f"{op.path}.value")
                meta = dict(op.meta) if op.meta else None
                if op.kind == "set":
                    asrt_id = sdk.fields.set(field_desc, e_ref, value, meta=meta)
                else:
                    asrt_id = sdk.fields.add(field_desc, e_ref, value, meta=meta)
                assertion_ids.append(asrt_id)
                continue

            if isinstance(op, WireRetractOp):
                if op.handle_id not in refs_by_handle_id:
                    raise SDKStoreError(f"{op.path}: missing preceding ref op for handle_id={op.handle_id}")
                handle_entity_type = entity_type_by_handle_id.get(op.handle_id)
                if handle_entity_type != op.entity_type:
                    raise SDKStoreError(
                        f"{op.path}: entity_type mismatch for handle_id={op.handle_id}: {op.entity_type} != {handle_entity_type}"
                    )
                _validate_wire_retract_binding(sdk=sdk, pred_index=pred_index, op=op)
                try:
                    revoker_id = sdk.assertions.retract(op.assertion_id, meta=(dict(op.meta) if op.meta else None))
                except Exception as exc:
                    raise SDKStoreError(f"{op.path}: retract failed: {exc}") from exc
                if isinstance(revoker_id, str):
                    assertion_ids.append(revoker_id)
                continue

            if isinstance(op, WireRecordExistsOp):
                e_ref = refs_by_handle_id.get(op.handle_id)
                if e_ref is None:
                    raise SDKStoreError(f"{op.path}: missing preceding ref op for handle_id={op.handle_id}")
                handle_entity_type = entity_type_by_handle_id.get(op.handle_id)
                if handle_entity_type != op.entity_type:
                    raise SDKStoreError(
                        f"{op.path}: entity_type mismatch for handle_id={op.handle_id}: {op.entity_type} != {handle_entity_type}"
                    )
                _validate_wire_record_exists_binding(
                    record_exists_pred_index=record_exists_pred_index,
                    op=op,
                )
                try:
                    asrt_id = set_field(sdk.ledger, op.pred_id, e_ref, [], (dict(op.meta) if op.meta else None))
                except Exception as exc:
                    raise SDKStoreError(f"{op.path}: entity exists write failed: {exc}") from exc
                assertion_ids.append(asrt_id)
                continue

            raise SDKStoreError(f"unsupported wire batch op: {type(op).__name__}")

        return BatchApplyResult(refs_by_handle_id=refs_by_handle_id, assertion_ids=assertion_ids)


def _first_unrepresentable_batch_op(plan: BatchPlan, sdk: SDKStore) -> tuple[str, str]:
    """Describe the first legacy-only op before an attached batch fails closed."""
    refs_by_handle_id: dict[int, RefOp] = {}
    for op in plan.ops:
        path = op.path or f"{op.entity_type}#{op.handle_id}"
        if isinstance(op, RefOp):
            refs_by_handle_id[op.handle_id] = op
            try:
                _normalize_json_object(op.identity_values, path=f"{path}.identity", allow_nested=False)
            except SDKStoreError as exc:
                return path, str(exc)
            continue
        if isinstance(op, (SetOp, AddOp)):
            try:
                _normalize_json_object(op.meta, path=f"{path}.meta", allow_nested=True)
            except SDKStoreError as exc:
                return path, str(exc)
            if op.value_kind == "handle":
                if not isinstance(op.value, int) or op.value not in refs_by_handle_id:
                    return path, "staged handle value could not be resolved to an application EntityRef"
                continue
            if op.value_kind == "entity_ref":
                if not isinstance(op.value, str):
                    return path, "raw entity_ref value is not a canonical string token"
                identity = sdk._identity_values_by_e_ref.get(op.value)
                if not isinstance(identity, dict) or not identity:
                    return path, "raw entity_ref value is not managed by this runtime"
                continue
            try:
                schema_pred = sdk._schema_pred_for_field(op.field)
                rest_terms = sdk._rest_terms_for_field(schema_pred, value=op.value)
            except Exception as exc:
                return path, str(exc)
            if len(rest_terms) != 1:
                return path, "field value does not lower to exactly one canonical term"
            tag, _value = rest_terms[0]
            if tag == "entity_ref":
                return path, "scalar value lowered unexpectedly to entity_ref"
            continue
        if isinstance(op, (RetractOp, RecordExistsOp)):
            try:
                _normalize_json_object(op.meta, path=f"{path}.meta", allow_nested=True)
            except SDKStoreError as exc:
                return path, str(exc)

    first = plan.ops[0]
    return first.path or f"{first.entity_type}#{first.handle_id}", "operation lowering failed"


def _resolve_planned_value(op: SetOp | AddOp, refs_by_handle_id: dict[int, str]) -> Any:
    if op.value_kind == "handle":
        ref_handle_id = op.value
        if not isinstance(ref_handle_id, int):
            raise SDKStoreError(f"plan invalid handle ref at {op.path}")
        e_ref = refs_by_handle_id.get(ref_handle_id)
        if e_ref is None:
            raise SDKStoreError(f"plan invalid: missing dependency RefOp for {op.path}")
        return e_ref
    return op.value


def _apply_application_batch_plan(plan: BatchPlan, sdk: SDKStore) -> BatchApplyResult:
    if sdk._database is not None:
        return _apply_attached_application_batch_plan(plan, sdk)

    refs_by_handle_id: dict[int, str] = {}
    assertion_ids: list[str] = []
    for handle_id in plan._application_handle_order:
        app_plan = plan._application_plans_by_handle_id.get(handle_id)
        if app_plan is None:
            raise SDKStoreError(f"delegated batch plan missing application plan for handle_id={handle_id}")
        result = apply_write_plan(
            app_plan,
            store=sdk.store,
            index=sdk._application_schema_index,
        )
        if result.errors:
            error = result.errors[0]
            path = ".".join(error.path) if error.path else ""
            prefix = f"{path}: " if path else ""
            if error.code == "FIELD_VALUE_VALIDATION_FAILED":
                raise SDKValueError(f"{prefix}{error.message}", code=error.code, path=(path or None))
            raise SDKStoreError(f"{prefix}{error.message}")
        if app_plan.resolved_target is None:
            raise SDKStoreError(f"delegated batch plan missing resolved target for handle_id={handle_id}")
        e_ref = app_plan.resolved_target.encoded_ref
        if not isinstance(e_ref, str) or not e_ref:
            raise SDKStoreError(f"delegated batch plan missing encoded_ref for handle_id={handle_id}")
        refs_by_handle_id[handle_id] = e_ref
        for applied in result.applied:
            if isinstance(applied.assertion_id, str):
                assertion_ids.append(applied.assertion_id)
    return BatchApplyResult(refs_by_handle_id=refs_by_handle_id, assertion_ids=assertion_ids)


def _apply_attached_application_batch_plan(plan: BatchPlan, sdk: SDKStore) -> BatchApplyResult:
    database = sdk._database_for_application_write("fg.batch")
    assert database is not None
    plans: list[EntityWritePlan] = []
    for handle_id in plan._application_handle_order:
        app_plan = plan._application_plans_by_handle_id.get(handle_id)
        if app_plan is None:
            raise SDKStoreError(f"delegated batch plan missing application plan for handle_id={handle_id}")
        plans.append(app_plan)
    results = apply_write_plans(
        tuple(plans),
        store=sdk.store,
        index=sdk._application_schema_index,
        database=database,
    )

    refs_by_handle_id: dict[int, str] = {}
    assertion_ids: list[str] = []
    for handle_id, app_plan, result in zip(
        plan._application_handle_order,
        plans,
        results,
        strict=True,
    ):
        if result.errors:
            _raise_application_batch_error(result.errors[0])
        if app_plan.resolved_target is None or not app_plan.resolved_target.encoded_ref:
            raise SDKStoreError(f"delegated batch plan missing resolved target for handle_id={handle_id}")
        refs_by_handle_id[handle_id] = app_plan.resolved_target.encoded_ref
        assertion_ids.extend(
            row.assertion_id
            for row in result.applied
            if isinstance(row.assertion_id, str)
        )
    return BatchApplyResult(refs_by_handle_id=refs_by_handle_id, assertion_ids=assertion_ids)


def _apply_attached_wire_batch_plan(plan: WireBatchPlan, sdk: SDKStore) -> BatchApplyResult:
    database = sdk._database_for_application_write("WireBatchPlan.apply")
    assert database is not None
    entity_cls_by_type = _sdk_entity_cls_by_type(sdk)
    pred_index = _sdk_pred_field_index(sdk)
    record_exists_pred_index = _sdk_record_exists_pred_index(sdk)
    refs_by_handle_id: dict[int, str] = {}
    targets_by_handle_id: dict[int, AppEntityRef] = {}
    planned_ops: list[PlannedOpDTO] = []

    for op in plan.ops:
        if isinstance(op, WireRefOp):
            if op.handle_id in targets_by_handle_id:
                raise SDKStoreError(f"{op.path}: duplicate ref handle_id={op.handle_id}")
            entity_cls = entity_cls_by_type.get(op.entity_type)
            if entity_cls is None:
                raise SDKStoreError(f"{op.path}: unknown entity_type for sdk schema: {op.entity_type}")
            identity = dict(op.identity)
            e_ref = sdk.entities.ref(entity_cls, **identity)
            target = AppEntityRef(
                entity_type=op.entity_type,
                identity=identity,
                encoded_ref=e_ref,
            )
            refs_by_handle_id[op.handle_id] = e_ref
            targets_by_handle_id[op.handle_id] = target
            info = sdk._application_schema_index.entities.get(op.entity_type)
            if info is None:
                raise SDKStoreError(f"{op.path}: entity_type missing from application schema: {op.entity_type}")
            planned_ops.extend(
                PlannedOpDTO(
                    op="set",
                    target=target,
                    field=FieldPath(entity_type=op.entity_type, field_name=identity_field.name),
                    value=identity[identity_field.name],
                )
                for identity_field in info.identity_fields
            )
            continue

        target = targets_by_handle_id.get(op.handle_id)
        if target is None:
            raise SDKStoreError(f"{op.path}: missing preceding ref op for handle_id={op.handle_id}")
        if target.entity_type != op.entity_type:
            raise SDKStoreError(
                f"{op.path}: entity_type mismatch for handle_id={op.handle_id}: "
                f"{op.entity_type} != {target.entity_type}"
            )
        if isinstance(op, WireWriteOp):
            _resolve_wire_field_for_write_op(sdk=sdk, pred_index=pred_index, op=op)
            value = _wire_application_value(op.value, sdk=sdk, path=f"{op.path}.value")
            planned_ops.append(
                PlannedOpDTO(
                    op=op.kind,
                    target=target,
                    field=FieldPath(entity_type=op.entity_type, field_name=op.field_name),
                    value=value,
                    meta=dict(op.meta),
                )
            )
            continue
        if isinstance(op, WireRetractOp):
            _validate_wire_retract_binding(sdk=sdk, pred_index=pred_index, op=op)
            planned_ops.append(
                PlannedOpDTO(
                    op="retract",
                    target=target,
                    field=FieldPath(entity_type=op.entity_type, field_name=op.field_name),
                    assertion_id=op.assertion_id,
                    meta=dict(op.meta),
                )
            )
            continue
        if isinstance(op, WireRecordExistsOp):
            _validate_wire_record_exists_binding(
                record_exists_pred_index=record_exists_pred_index,
                op=op,
            )
            planned_ops.append(PlannedOpDTO(op="record_exists", target=target, meta=dict(op.meta)))
            continue
        raise SDKStoreError(f"unsupported wire batch op: {type(op).__name__}")

    if not targets_by_handle_id:
        return BatchApplyResult(refs_by_handle_id={}, assertion_ids=[])
    first_target = next(iter(targets_by_handle_id.values()))
    app_plan = EntityWritePlan(
        command=EntityWriteCommand(
            target=AppEntitySelector(
                entity_type=first_target.entity_type,
                identity=dict(first_target.identity),
                encoded_ref=first_target.encoded_ref,
            ),
        ),
        resolved_target=first_target,
        planned_ops=tuple(planned_ops),
        can_apply=True,
    )
    result = apply_write_plans(
        (app_plan,),
        store=sdk.store,
        index=sdk._application_schema_index,
        database=database,
    )[0]
    if result.errors:
        _raise_application_batch_error(result.errors[0])
    return BatchApplyResult(
        refs_by_handle_id=refs_by_handle_id,
        assertion_ids=[
            row.assertion_id
            for row in result.applied
            if isinstance(row.assertion_id, str)
        ],
    )


def _wire_application_value(value: dict[str, Any], *, sdk: SDKStore, path: str) -> Any:
    kind = value.get("kind")
    if kind == "scalar":
        return value.get("data")
    if kind == "ref_identity":
        entity_type = value.get("entity_type")
        identity = value.get("identity")
        if not isinstance(entity_type, str) or not isinstance(identity, dict):
            raise SDKStoreError(f"{path}: invalid ref_identity value")
        entity_cls = _sdk_entity_cls_by_type(sdk).get(entity_type)
        if entity_cls is None:
            raise SDKStoreError(f"{path}: unknown entity_type for sdk schema: {entity_type}")
        e_ref = sdk.entities.ref(entity_cls, **dict(identity))
        return AppEntityRef(
            entity_type=entity_type,
            identity=dict(identity),
            encoded_ref=e_ref,
        )
    raise SDKStoreError(f"{path}.kind unsupported: {kind!r}")


def _raise_application_batch_error(error: Any) -> None:
    path = ".".join(error.path) if error.path else ""
    prefix = f"{path}: " if path else ""
    if error.code == "FIELD_VALUE_VALIDATION_FAILED":
        raise SDKValueError(f"{prefix}{error.message}", code=error.code, path=(path or None))
    raise SDKStoreError(f"{prefix}{error.message}")


def _parse_wire_ref_op(raw: dict[str, Any], *, path: str) -> WireRefOp:
    handle_id = raw.get("handle_id")
    entity_type = raw.get("entity_type")
    identity = raw.get("identity")
    raw_path = raw.get("path", "")
    if isinstance(handle_id, bool) or not isinstance(handle_id, int) or handle_id <= 0:
        raise SDKStoreError(f"{path}.handle_id must be positive int")
    if not isinstance(entity_type, str) or not entity_type:
        raise SDKStoreError(f"{path}.entity_type must be non-empty string")
    if not isinstance(raw_path, str):
        raise SDKStoreError(f"{path}.path must be string")
    return WireRefOp(
        kind="ref",
        handle_id=handle_id,
        entity_type=entity_type,
        identity=_normalize_wire_identity(identity, path=f"{path}.identity"),
        path=raw_path,
    )


def _parse_wire_write_op(raw: dict[str, Any], *, path: str) -> WireWriteOp:
    kind = raw.get("kind")
    handle_id = raw.get("handle_id")
    entity_type = raw.get("entity_type")
    pred_id = raw.get("pred_id")
    field_name = raw.get("field_name")
    value = raw.get("value")
    meta = raw.get("meta")
    raw_path = raw.get("path", "")
    if kind not in {"set", "add"}:
        raise SDKStoreError(f"{path}.kind must be 'set' or 'add'")
    if isinstance(handle_id, bool) or not isinstance(handle_id, int) or handle_id <= 0:
        raise SDKStoreError(f"{path}.handle_id must be positive int")
    if not isinstance(entity_type, str) or not entity_type:
        raise SDKStoreError(f"{path}.entity_type must be non-empty string")
    if not isinstance(pred_id, str) or not pred_id:
        raise SDKStoreError(f"{path}.pred_id must be non-empty string")
    if not isinstance(field_name, str) or not field_name:
        raise SDKStoreError(f"{path}.field_name must be non-empty string")
    if not isinstance(raw_path, str):
        raise SDKStoreError(f"{path}.path must be string")
    return WireWriteOp(
        kind=kind,
        handle_id=handle_id,
        entity_type=entity_type,
        pred_id=pred_id,
        field_name=field_name,
        value=_normalize_wire_value(value, path=f"{path}.value"),
        meta=_normalize_json_object(meta, path=f"{path}.meta", allow_nested=True),
        path=raw_path,
    )


def _parse_wire_retract_op(raw: dict[str, Any], *, path: str) -> WireRetractOp:
    handle_id = raw.get("handle_id")
    entity_type = raw.get("entity_type")
    pred_id = raw.get("pred_id")
    field_name = raw.get("field_name")
    assertion_id = raw.get("assertion_id")
    meta = raw.get("meta")
    raw_path = raw.get("path", "")
    if isinstance(handle_id, bool) or not isinstance(handle_id, int) or handle_id <= 0:
        raise SDKStoreError(f"{path}.handle_id must be positive int")
    if not isinstance(entity_type, str) or not entity_type:
        raise SDKStoreError(f"{path}.entity_type must be non-empty string")
    if not isinstance(pred_id, str) or not pred_id:
        raise SDKStoreError(f"{path}.pred_id must be non-empty string")
    if not isinstance(field_name, str) or not field_name:
        raise SDKStoreError(f"{path}.field_name must be non-empty string")
    if not isinstance(assertion_id, str) or not assertion_id:
        raise SDKStoreError(f"{path}.assertion_id must be non-empty string")
    if not isinstance(raw_path, str):
        raise SDKStoreError(f"{path}.path must be string")
    return WireRetractOp(
        kind="retract",
        handle_id=handle_id,
        entity_type=entity_type,
        pred_id=pred_id,
        field_name=field_name,
        assertion_id=assertion_id,
        meta=_normalize_json_object(meta, path=f"{path}.meta", allow_nested=True),
        path=raw_path,
    )


def _parse_wire_record_exists_op(raw: dict[str, Any], *, path: str) -> WireRecordExistsOp:
    handle_id = raw.get("handle_id")
    entity_type = raw.get("entity_type")
    pred_id = raw.get("pred_id")
    meta = raw.get("meta")
    raw_path = raw.get("path", "")
    if isinstance(handle_id, bool) or not isinstance(handle_id, int) or handle_id <= 0:
        raise SDKStoreError(f"{path}.handle_id must be positive int")
    if not isinstance(entity_type, str) or not entity_type:
        raise SDKStoreError(f"{path}.entity_type must be non-empty string")
    if not isinstance(pred_id, str) or not pred_id:
        raise SDKStoreError(f"{path}.pred_id must be non-empty string")
    if not isinstance(raw_path, str):
        raise SDKStoreError(f"{path}.path must be string")
    return WireRecordExistsOp(
        kind="record_exists",
        handle_id=handle_id,
        entity_type=entity_type,
        pred_id=pred_id,
        meta=_normalize_json_object(meta, path=f"{path}.meta", allow_nested=True),
        path=raw_path,
    )


def _export_wire_value(op: SetOp | AddOp, *, ref_index: dict[int, RefOp]) -> dict[str, Any]:
    if op.value_kind == "scalar":
        return {
            "kind": "scalar",
            "data": _normalize_json_scalar(op.value, path=f"{op.path}.value"),
        }
    if op.value_kind == "entity_ref":
        raise SDKStoreError(f"{op.path}: wire export forbids raw entity_ref token values; use staged handles for references")
    if op.value_kind == "handle":
        ref_handle_id = op.value
        if isinstance(ref_handle_id, bool) or not isinstance(ref_handle_id, int):
            raise SDKStoreError(f"{op.path}: invalid staged handle reference in value")
        ref_op = ref_index.get(ref_handle_id)
        if ref_op is None:
            raise SDKStoreError(f"{op.path}: missing RefOp for referenced handle_id={ref_handle_id}")
        return {
            "kind": "ref_identity",
            "entity_type": ref_op.entity_type,
            "identity": _normalize_wire_identity(ref_op.identity_values, path=f"{op.path}.value.identity"),
        }
    raise SDKStoreError(f"{op.path}: unsupported value_kind for wire export: {op.value_kind!r}")


def _normalize_wire_value(raw: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SDKStoreError(f"{path} must be object")
    kind = raw.get("kind")
    if kind == "scalar":
        if "data" not in raw:
            raise SDKStoreError(f"{path}.data is required for scalar value")
        return {"kind": "scalar", "data": _normalize_json_scalar(raw.get("data"), path=f"{path}.data")}
    if kind == "ref_identity":
        entity_type = raw.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type:
            raise SDKStoreError(f"{path}.entity_type must be non-empty string")
        return {
            "kind": "ref_identity",
            "entity_type": entity_type,
            "identity": _normalize_wire_identity(raw.get("identity"), path=f"{path}.identity"),
        }
    raise SDKStoreError(f"{path}.kind must be 'scalar' or 'ref_identity'")


def _resolve_wire_value_for_apply(value: dict[str, Any], *, sdk: SDKStore, path: str) -> Any:
    kind = value.get("kind")
    if kind == "scalar":
        return value.get("data")
    if kind == "ref_identity":
        entity_type = value.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type:
            raise SDKStoreError(f"{path}.entity_type must be non-empty string")
        entity_cls = _sdk_entity_cls_by_type(sdk).get(entity_type)
        if entity_cls is None:
            raise SDKStoreError(f"{path}: unknown entity_type for sdk schema: {entity_type}")
        identity = value.get("identity")
        if not isinstance(identity, dict):
            raise SDKStoreError(f"{path}.identity must be object")
        return sdk.entities.ref(entity_cls, **dict(identity))
    raise SDKStoreError(f"{path}.kind unsupported: {kind!r}")


def _normalize_wire_identity(raw: Any, *, path: str) -> dict[str, Any]:
    ident = _normalize_json_object(raw, path=path, allow_nested=False)
    if not ident:
        raise SDKStoreError(f"{path} must be non-empty object")
    has_uid = "uid" in ident
    has_source = ("source_id" in ident) or ("source_system" in ident)
    if has_uid and has_source:
        raise SDKStoreError(f"{path}: source_* identity and uid are mutually exclusive in wire plan v0")
    return ident


def _normalize_json_object(raw: Any, *, path: str, allow_nested: bool) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SDKStoreError(f"{path} must be object")
    out: dict[str, Any] = {}
    for key in sorted(raw.keys()):
        if not isinstance(key, str) or not key:
            raise SDKStoreError(f"{path} keys must be non-empty strings")
        val = raw[key]
        if allow_nested:
            out[key] = _normalize_json_value(val, path=f"{path}.{key}")
        else:
            out[key] = _normalize_json_scalar(val, path=f"{path}.{key}")
    return out


def _normalize_json_value(raw: Any, *, path: str) -> Any:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        if not math.isfinite(raw):
            raise SDKStoreError(f"{path} must not be NaN/Infinity")
        return raw
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return [_normalize_json_value(item, path=f"{path}[{idx}]") for idx, item in enumerate(raw)]
    if isinstance(raw, dict):
        return _normalize_json_object(raw, path=path, allow_nested=True)
    raise SDKStoreError(f"{path} contains unsupported JSON value type: {type(raw).__name__}")


def _normalize_json_scalar(raw: Any, *, path: str) -> Any:
    val = _normalize_json_value(raw, path=path)
    if isinstance(val, (list, dict)):
        raise SDKStoreError(f"{path} must be JSON scalar (null/bool/int/float/str)")
    return val


def _canonical_json_dumps(payload: Any) -> str:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SDKStoreError(f"failed to serialize canonical JSON: {exc}") from exc


def _canonical_json_bytes(payload: Any) -> bytes:
    return _canonical_json_dumps(payload).encode("utf-8")


def _sdk_entity_cls_by_type(sdk: SDKStore) -> dict[str, type[Entity]]:
    out: dict[str, type[Entity]] = {}
    for entity_cls, spec in sdk._entity_spec_by_class.items():
        entity_type = spec.get("entity_type")
        if isinstance(entity_type, str) and entity_type:
            out[entity_type] = entity_cls
    return out


def _sdk_pred_field_index(sdk: SDKStore) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for field_desc, pred in sdk._field_pred_by_descriptor.items():
        if not isinstance(pred, dict):
            continue
        pred_id = pred.get("pred_id")
        owner_type = pred.get("owner_type")
        field_name = pred.get("py_field_name")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if pred_id in out:
            # Keep the first stable mapping; ambiguous duplicates are rejected on resolve.
            out[pred_id].setdefault("_ambiguous", []).append((field_desc, pred))
            continue
        out[pred_id] = {
            "field": field_desc,
            "pred": pred,
            "owner_type": owner_type,
            "field_name": field_name,
        }
    return out


def _sdk_record_exists_pred_index(sdk: SDKStore) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for pred in sdk.schema_ir.get("predicates", []):
        if not isinstance(pred, dict):
            continue
        pred_id = pred.get("pred_id")
        owner_type = pred.get("owner_type")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if not isinstance(owner_type, str) or not owner_type:
            continue
        if pred.get("is_entity_exists") is not True:
            continue
        out[pred_id] = {"owner_type": owner_type, "pred": pred}
    return out


def _sdk_identity_pred_index(sdk: SDKStore) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for pred in sdk.schema_ir.get("predicates", []):
        if not isinstance(pred, dict):
            continue
        if pred.get("is_identity_field") is not True:
            continue
        pred_id = pred.get("pred_id")
        owner_type = pred.get("owner_type")
        field_name = pred.get("py_field_name")
        arg_specs = pred.get("arg_specs")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if not isinstance(owner_type, str) or not owner_type:
            continue
        if not isinstance(field_name, str) or not field_name:
            continue
        if not isinstance(arg_specs, list) or len(arg_specs) != 2:
            raise SDKStoreError(f"identity predicate arg_specs invalid for {pred_id}")
        value_spec = arg_specs[1] if isinstance(arg_specs[1], dict) else None
        type_domain = value_spec.get("type_domain") if isinstance(value_spec, dict) else None
        if not isinstance(type_domain, str) or not type_domain:
            raise SDKStoreError(f"identity predicate arg_specs[1].type_domain invalid for {pred_id}")
        out.setdefault(owner_type, []).append(
            {
                "pred_id": pred_id,
                "field_name": field_name,
                "type_domain": type_domain,
            }
        )
    for rows in out.values():
        rows.sort(key=lambda row: str(row.get("field_name")))
    return out


def _write_identity_predicates_for_ref(
    *,
    sdk: SDKStore,
    identity_pred_index: dict[str, list[dict[str, Any]]],
    e_ref: str,
    entity_type: str,
    identity_values: dict[str, Any],
    path: str,
    assertion_ids: list[str],
) -> None:
    preds = identity_pred_index.get(entity_type, [])
    for row in preds:
        field_name = row.get("field_name")
        pred_id = row.get("pred_id")
        type_domain = row.get("type_domain")
        if not isinstance(field_name, str) or field_name not in identity_values:
            continue
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if not isinstance(type_domain, str) or not type_domain:
            continue
        value = identity_values[field_name]
        try:
            asrt_id = set_field(sdk.ledger, pred_id, e_ref, [(type_domain, value)], None)
        except Exception as exc:
            raise SDKStoreError(
                f"{path}: identity predicate write failed for {entity_type}.{field_name}: {exc}"
            ) from exc
        assertion_ids.append(asrt_id)


def _resolve_wire_field_for_write_op(*, sdk: SDKStore, pred_index: dict[str, dict[str, Any]], op: WireWriteOp) -> Field:
    row = pred_index.get(op.pred_id)
    if row is None:
        raise SDKStoreError(f"{op.path}: pred_id not found in sdk schema: {op.pred_id}")
    if "_ambiguous" in row:
        raise SDKStoreError(f"{op.path}: pred_id resolves ambiguously in sdk schema: {op.pred_id}")
    owner_type = row.get("owner_type")
    field_name = row.get("field_name")
    if not isinstance(owner_type, str) or owner_type != op.entity_type:
        raise SDKStoreError(
            f"{op.path}: pred_id/entity_type mismatch: pred_id={op.pred_id} owner_type={owner_type!r} wire_entity_type={op.entity_type!r}"
        )
    if not isinstance(field_name, str) or field_name != op.field_name:
        raise SDKStoreError(
            f"{op.path}: pred_id/field_name mismatch: pred_id={op.pred_id} schema_field={field_name!r} wire_field={op.field_name!r}"
        )
    field_desc = row.get("field")
    if not isinstance(field_desc, Field):
        raise SDKStoreError(f"{op.path}: resolved schema field is invalid for pred_id={op.pred_id}")
    # Defensive check against accidental schema drift in internal indexes.
    pred = sdk._schema_pred_for_field(field_desc)
    if pred.get("pred_id") != op.pred_id:
        raise SDKStoreError(f"{op.path}: resolved field pred_id drifted for {op.pred_id}")
    return field_desc


def _validate_wire_retract_binding(*, sdk: SDKStore, pred_index: dict[str, dict[str, Any]], op: WireRetractOp) -> None:
    row = pred_index.get(op.pred_id)
    if row is None:
        raise SDKStoreError(f"{op.path}: pred_id not found in sdk schema: {op.pred_id}")
    if "_ambiguous" in row:
        raise SDKStoreError(f"{op.path}: pred_id resolves ambiguously in sdk schema: {op.pred_id}")
    owner_type = row.get("owner_type")
    field_name = row.get("field_name")
    if not isinstance(owner_type, str) or owner_type != op.entity_type:
        raise SDKStoreError(
            f"{op.path}: retract pred_id/entity_type mismatch: pred_id={op.pred_id} owner_type={owner_type!r} wire_entity_type={op.entity_type!r}"
        )
    if not isinstance(field_name, str) or field_name != op.field_name:
        raise SDKStoreError(
            f"{op.path}: retract pred_id/field_name mismatch: pred_id={op.pred_id} schema_field={field_name!r} wire_field={op.field_name!r}"
        )


def _validate_wire_record_exists_binding(
    *,
    record_exists_pred_index: dict[str, dict[str, Any]],
    op: WireRecordExistsOp,
) -> None:
    row = record_exists_pred_index.get(op.pred_id)
    if row is None:
        raise SDKStoreError(f"{op.path}: entity exists pred_id not found in sdk schema: {op.pred_id}")
    owner_type = row.get("owner_type")
    if not isinstance(owner_type, str) or owner_type != op.entity_type:
        raise SDKStoreError(
            f"{op.path}: entity exists pred_id/entity_type mismatch: pred_id={op.pred_id} owner_type={owner_type!r} wire_entity_type={op.entity_type!r}"
        )


def _sdk_wire_schema_digest(sdk: SDKStore) -> str:
    rows: list[dict[str, Any]] = []
    for field_desc, pred in sdk._field_pred_by_descriptor.items():
        if not isinstance(pred, dict):
            continue
        field_decl = sdk._field_decl_by_descriptor.get(field_desc, {})
        pred_id = pred.get("pred_id")
        owner_type = pred.get("owner_type")
        field_name = pred.get("py_field_name")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        if not isinstance(owner_type, str) or not owner_type:
            continue
        if not isinstance(field_name, str) or not field_name:
            continue
        arg_specs = pred.get("arg_specs")
        if not isinstance(arg_specs, list):
            arg_specs = []
        norm_arg_specs: list[dict[str, Any]] = []
        for idx, spec in enumerate(arg_specs):
            if not isinstance(spec, dict):
                raise SDKStoreError(f"schema predicate {pred_id} arg_specs[{idx}] must be object")
            name = spec.get("name")
            tag = spec.get("type_domain")
            if not isinstance(name, str) or not name:
                raise SDKStoreError(f"schema predicate {pred_id} arg_specs[{idx}].name invalid")
            if not isinstance(tag, str) or not tag:
                raise SDKStoreError(f"schema predicate {pred_id} arg_specs[{idx}].type_domain invalid")
            norm_arg_specs.append({"name": name, "type_domain": tag})
        rows.append(
            {
                "pred_id": pred_id,
                "entity_type": owner_type,
                "field_name": field_name,
                "cardinality": field_decl.get("cardinality"),
                "arg_specs": norm_arg_specs,
            }
        )
    rows_sorted = sorted(rows, key=lambda row: (str(row.get("entity_type")), str(row.get("field_name")), str(row.get("pred_id"))))
    payload = {
        "wire_schema_digest_version": "sdk_batch_pred_table_v1",
        "predicates": rows_sorted,
    }
    return sha256_token(_canonical_json_bytes(payload))


@dataclass
class _StagedFieldOp:
    kind: Literal["set", "add", "retract"]
    field_name: str
    field: Field
    value: Any
    meta: dict[str, Any]
    op_index: int
    path: str


class ManagedFieldHandle:
    def __init__(self, tx: SDKBatchTx, owner: ManagedEntityHandle, field_name: str, field: Field) -> None:
        self._tx = tx
        self._owner = owner
        self._field_name = field_name
        self._field = field

    def set(
        self,
        value: Any,
        *,
        meta: dict[str, Any] | None = None,
    ) -> ManagedEntityHandle:
        if self._field.cardinality != "single":
            raise SDKStoreError(f"{self._owner.path}.{self._field_name}: multi field only supports add(...) in batch staging v1")
        self._tx._stage_field_op(self._owner, "set", self._field_name, self._field, value, meta=meta)
        return self._owner

    def add(
        self,
        value: Any,
        *,
        meta: dict[str, Any] | None = None,
    ) -> ManagedEntityHandle:
        if self._field.cardinality != "multi":
            raise SDKStoreError(f"{self._owner.path}.{self._field_name}: single field only supports set(...) in batch staging v1")
        self._tx._stage_field_op(self._owner, "add", self._field_name, self._field, value, meta=meta)
        return self._owner

    def retract(
        self,
        assertion_id: str,
        *,
        meta: dict[str, Any] | None = None,
    ) -> ManagedEntityHandle:
        self._tx._stage_retract_op(self._owner, self._field_name, self._field, assertion_id, meta=meta)
        return self._owner


class _IdentityWriteGuard:
    def __init__(self, owner: ManagedEntityHandle, field_name: str) -> None:
        self._owner = owner
        self._field_name = field_name

    @property
    def value(self) -> Any:
        return self._owner.identity_values.get(self._field_name)

    def __repr__(self) -> str:
        return repr(self.value)

    __str__ = __repr__

    def __bool__(self) -> bool:
        return bool(self.value)

    def __eq__(self, other: Any) -> bool:  # type: ignore[override]
        return self.value == other

    def set(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise SDKStoreError(
            f"{self._owner.path}.{self._field_name}: identity fields are immutable; "
            "use handle.bind(...) before writes"
        )

    def add(self, *args: Any, **kwargs: Any) -> None:
        self.set(*args, **kwargs)

    def retract(self, *args: Any, **kwargs: Any) -> None:
        self.set(*args, **kwargs)


class ManagedEntityHandle:
    def __init__(
        self,
        tx: SDKBatchTx,
        *,
        handle_id: int,
        creation_index: int,
        entity_cls: type[Entity],
        e_ref: str | None,
        identity_values: dict[str, Any],
        entity_meta: dict[str, Any],
    ) -> None:
        self._tx = tx
        self.handle_id = handle_id
        self.creation_index = creation_index
        self.entity_cls = entity_cls
        self.e_ref = e_ref
        self.identity_values = dict(identity_values)
        self.entity_meta = dict(entity_meta)
        self._field_handles: dict[str, ManagedFieldHandle] = {}
        self._staged_ops: list[_StagedFieldOp] = []
        self.path = f"{entity_cls.__name__}#{creation_index}"

        spec = self._tx._sdk._entity_spec_by_class.get(entity_cls)
        if not isinstance(spec, dict):
            raise SDKStoreError(f"unknown Entity class: {entity_cls.__name__}")
        order: dict[str, int] = {}
        for idx, field_decl in enumerate(spec.get("fields", [])):
            py_name = field_decl.get("py_name")
            if isinstance(py_name, str):
                order[py_name] = idx
        self._field_order = order

    def bind(self, **identity_values: Any) -> ManagedEntityHandle:
        self._tx._bind_identity(self, identity_values)
        return self

    def __getattr__(self, name: str) -> Any:
        descriptor = getattr(self.entity_cls, name, None)
        if isinstance(descriptor, Field):
            fh = self._field_handles.get(name)
            if fh is None:
                fh = ManagedFieldHandle(self._tx, self, name, descriptor)
                self._field_handles[name] = fh
            return fh
        if isinstance(descriptor, Identity):
            return _IdentityWriteGuard(self, name)
        if name in self.identity_values:
            return self.identity_values[name]
        raise AttributeError(name)

    def _append_staged(self, op: _StagedFieldOp) -> None:
        self._staged_ops.append(op)

    def _dependencies(self) -> list["ManagedEntityHandle"]:  # noqa: UP037 - Preserve Python 3.10 runtime hint shape.
        seen: set[int] = set()
        out: list[ManagedEntityHandle] = []
        for op in self._staged_ops:
            if isinstance(op.value, ManagedEntityHandle) and op.value.handle_id not in seen:
                seen.add(op.value.handle_id)
                out.append(op.value)
        return out

    def _field_sort_key(self, field_name: str) -> tuple[int, str]:
        return (self._field_order.get(field_name, 10**9), field_name)


class SDKBatchTx:
    def __init__(self, sdk: SDKStore, *, meta: dict[str, Any] | None = None) -> None:
        self._sdk = sdk
        self._batch_meta = _copy_meta(meta)
        self._handles_by_e_ref: dict[str, ManagedEntityHandle] = {}
        self._handles_by_id: dict[int, ManagedEntityHandle] = {}
        self._creation_order: list[ManagedEntityHandle] = []
        self._retract_ops_by_assertion_id: dict[str, tuple[ManagedEntityHandle, _StagedFieldOp]] = {}
        self._next_handle_id = 1
        self._next_op_index = 1

    def __enter__(self) -> SDKBatchTx:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def entity(
        self,
        entity_cls: type[Entity],
        *,
        meta: dict[str, Any] | None = None,
        **identity_values: Any,
    ) -> ManagedEntityHandle:
        if not isinstance(entity_cls, type) or not issubclass(entity_cls, Entity):
            raise SDKStoreError("tx.entity(...) requires Entity subclass")
        self._validate_identity_keys(entity_cls, identity_values, path="tx.entity(...)")
        materialized_identity, missing = self._materialize_identity_values(entity_cls, identity_values)
        if missing:
            raise SDKStoreError(
                f"tx.entity(...): identity is incomplete for {entity_cls.__name__}; missing: {sorted(missing)}"
            )
        e_ref = self._sdk.entities.ref(entity_cls, **materialized_identity)

        existing = self._handles_by_e_ref.get(e_ref) if isinstance(e_ref, str) else None
        if existing is not None:
            if meta:
                existing.entity_meta = {**existing.entity_meta, **dict(meta)}
            return existing
        handle = ManagedEntityHandle(
            self,
            handle_id=self._next_handle_id,
            creation_index=len(self._creation_order) + 1,
            entity_cls=entity_cls,
            e_ref=e_ref,
            identity_values=dict(materialized_identity),
            entity_meta=_copy_meta(meta),
        )
        self._next_handle_id += 1
        if isinstance(e_ref, str):
            self._handles_by_e_ref[e_ref] = handle
        self._handles_by_id[handle.handle_id] = handle
        self._creation_order.append(handle)
        return handle

    def save(
        self,
        obj: ManagedEntityHandle,
        *,
        include_deps: bool = True,
        meta: dict[str, Any] | None = None,
    ) -> BatchCommitResult:
        return self.commit(objects=[obj], include_deps=include_deps, commit_meta=meta)

    def preview(
        self,
        *,
        objects: list[ManagedEntityHandle] | None = None,
        include_deps: bool = True,
        commit_meta: dict[str, Any] | None = None,
    ) -> BatchPlan:
        selected = self._resolve_selected_handles(objects)
        ordered = self._ordered_handles(selected, include_deps=include_deps)
        commit_meta_norm = _copy_meta(commit_meta)
        delegated = self._preview_via_application(ordered, commit_meta=commit_meta_norm)
        if delegated is not None:
            return delegated
        return self._preview_legacy(ordered, commit_meta=commit_meta_norm)

    def _preview_legacy(
        self,
        ordered: list[ManagedEntityHandle],
        *,
        commit_meta: dict[str, Any],
    ) -> BatchPlan:
        ops: list[BatchOp] = []
        for handle in ordered:
            field_ops = self._compile_handle_field_ops(handle, commit_meta=commit_meta)
            if not field_ops:
                continue
            ops.append(
                RefOp(
                    handle_id=handle.handle_id,
                    entity_type=handle.entity_cls.__name__,
                    entity_cls=handle.entity_cls,
                    identity_values=dict(handle.identity_values),
                    path=handle.path,
                )
            )
            ops.extend(field_ops)
        return BatchPlan(ops=ops, warnings=[])

    def _preview_via_application(
        self,
        ordered: list[ManagedEntityHandle],
        *,
        commit_meta: dict[str, Any],
    ) -> BatchPlan | None:
        ops: list[BatchOp] = []
        handle_order: list[int] = []
        plans_by_handle_id: dict[int, EntityWritePlan] = {}
        delegated_target_refs: set[str] = set()
        field_ops_by_handle_id: dict[int, list[BatchOp]] = {}

        for handle in ordered:
            field_ops = self._compile_handle_field_ops(handle, commit_meta=commit_meta)
            if not field_ops:
                continue
            field_ops_by_handle_id[handle.handle_id] = field_ops
            command = self._application_write_command_for_handle(handle, field_ops=field_ops)
            if command is None:
                return None
            plan = plan_write_command(
                command,
                store=self._sdk.store,
                index=self._sdk._application_schema_index,
            )
            if not plan.can_apply or plan.resolved_target is None:
                return None
            target_ref = plan.resolved_target.encoded_ref or handle.e_ref
            if not isinstance(target_ref, str) or not target_ref:
                return None
            delegated_target_refs.add(target_ref)
            handle_order.append(handle.handle_id)
            plans_by_handle_id[handle.handle_id] = plan
            ops.append(
                RefOp(
                    handle_id=handle.handle_id,
                    entity_type=handle.entity_cls.__name__,
                    entity_cls=handle.entity_cls,
                    identity_values=dict(plan.resolved_target.identity),
                    path=handle.path,
                )
            )
            ops.extend(field_ops)

        if not handle_order:
            return BatchPlan(ops=ops, warnings=[])

        pruned_plans = {
            handle_id: self._prune_application_plan(
                handle=self._handles_by_id[handle_id],
                plan=plan,
                field_ops=field_ops_by_handle_id[handle_id],
                delegated_target_refs=delegated_target_refs,
            )
            for handle_id, plan in plans_by_handle_id.items()
        }
        return BatchPlan(
            ops=ops,
            warnings=[],
            _application_handle_order=tuple(handle_order),
            _application_plans_by_handle_id=pruned_plans,
        )

    def commit(
        self,
        *,
        objects: list[ManagedEntityHandle] | None = None,
        include_deps: bool = True,
        commit_meta: dict[str, Any] | None = None,
    ) -> BatchCommitResult:
        plan = self.preview(objects=objects, include_deps=include_deps, commit_meta=commit_meta)
        result = plan.apply(self._sdk)
        return BatchCommitResult(plan=plan, apply_result=result)

    def _resolve_selected_handles(self, objects: list[ManagedEntityHandle] | None) -> list[ManagedEntityHandle]:
        if objects is None:
            return list(self._creation_order)
        if not isinstance(objects, list) or not objects:
            raise SDKStoreError("objects must be non-empty list[ManagedEntityHandle] when provided")
        out: list[ManagedEntityHandle] = []
        seen: set[int] = set()
        for idx, obj in enumerate(objects):
            if not isinstance(obj, ManagedEntityHandle) or obj._tx is not self:
                raise SDKStoreError(f"objects[{idx}] must be handle from this tx")
            if obj.handle_id in seen:
                continue
            seen.add(obj.handle_id)
            out.append(obj)
        return out

    def _ordered_handles(self, roots: list[ManagedEntityHandle], *, include_deps: bool) -> list[ManagedEntityHandle]:
        selected_ids = {h.handle_id for h in roots}
        order: list[ManagedEntityHandle] = []
        visiting: set[int] = set()
        visited: set[int] = set()

        def visit(handle: ManagedEntityHandle) -> None:
            if handle.handle_id in visited:
                return
            if handle.handle_id in visiting:
                raise SDKStoreError(f"dependency cycle in batch staging at {handle.path}")
            visiting.add(handle.handle_id)
            deps = handle._dependencies()
            deps = sorted(deps, key=lambda h: h.creation_index)
            for dep in deps:
                if not include_deps and dep.handle_id not in selected_ids:
                    raise SDKStoreError(f"{handle.path}: missing dependency {dep.path} (include_deps=False)")
                visit(dep)
            visiting.remove(handle.handle_id)
            visited.add(handle.handle_id)
            order.append(handle)

        for handle in sorted(roots, key=lambda h: h.creation_index):
            visit(handle)
        return order

    def _compile_handle_field_ops(self, handle: ManagedEntityHandle, *, commit_meta: dict[str, Any]) -> list[BatchOp]:
        if not handle._staged_ops:
            return []
        self._ensure_handle_resolved(handle, path=handle.path)

        set_latest: dict[str, _StagedFieldOp] = {}
        add_kept: list[_StagedFieldOp] = []
        retract_ops: list[_StagedFieldOp] = []
        add_seen: set[tuple[str, str]] = set()
        for op in handle._staged_ops:
            if op.kind == "retract":
                retract_ops.append(op)
                continue
            if op.kind == "set":
                set_latest[op.field_name] = op
                continue
            value_key = self._value_dedup_key(op.value)
            dedup_key = (op.field_name, value_key)
            if dedup_key in add_seen:
                continue
            add_seen.add(dedup_key)
            add_kept.append(op)

        grouped: dict[str, list[_StagedFieldOp]] = {}
        for op in add_kept:
            grouped.setdefault(op.field_name, []).append(op)
        for field_name, op in set_latest.items():
            grouped.setdefault(field_name, []).append(op)

        out: list[BatchOp] = []
        for field_name in sorted(grouped.keys(), key=handle._field_sort_key):
            ops = sorted(grouped[field_name], key=lambda row: row.op_index)
            for op in ops:
                value_kind, value_payload = self._plan_value(op.value, path=op.path)
                effective_meta = _merge_meta(self._batch_meta, handle.entity_meta, op.meta, commit_meta)
                if op.kind == "set":
                    out.append(
                        SetOp(
                            handle_id=handle.handle_id,
                            entity_type=handle.entity_cls.__name__,
                            field_name=field_name,
                            field=op.field,
                            value_kind=value_kind,
                            value=value_payload,
                            meta=effective_meta,
                            path=op.path,
                        )
                    )
                else:
                    out.append(
                        AddOp(
                            handle_id=handle.handle_id,
                            entity_type=handle.entity_cls.__name__,
                            field_name=field_name,
                            field=op.field,
                            value_kind=value_kind,
                            value=value_payload,
                            meta=effective_meta,
                            path=op.path,
                        )
                    )
        # Retract ops are always emitted after write ops for the same entity to avoid coupling
        # with staging-time set/add merge rules.
        for op in sorted(retract_ops, key=lambda row: row.op_index):
            schema_pred = self._sdk._schema_pred_for_field(op.field)
            pred_id = schema_pred.get("pred_id")
            if not isinstance(pred_id, str) or not pred_id:
                raise SDKStoreError(f"{op.path}: schema predicate missing pred_id")
            effective_meta = _merge_meta(self._batch_meta, handle.entity_meta, op.meta, commit_meta)
            out.append(
                RetractOp(
                    handle_id=handle.handle_id,
                    entity_type=handle.entity_cls.__name__,
                    pred_id=pred_id,
                    field_name=op.field_name,
                    assertion_id=str(op.value),
                    meta=effective_meta,
                    path=op.path,
                )
            )
        return out

    def _application_write_command_for_handle(
        self,
        handle: ManagedEntityHandle,
        *,
        field_ops: list[BatchOp],
    ) -> EntityWriteCommand | None:
        target = self._application_entity_ref_for_handle(handle)
        if target is None:
            return None
        mutations: list[FieldMutation] = []
        create_if_missing = self._handle_requires_create_if_missing(handle)
        for op in field_ops:
            if isinstance(op, RecordExistsOp):
                if self._application_meta(op.meta, path=f"{op.path}.meta") is None:
                    return None
                create_if_missing = True
                continue
            field_path = FieldPath(entity_type=handle.entity_cls.__name__, field_name=op.field_name)
            meta = self._application_meta(op.meta, path=f"{op.path}.meta")
            if meta is None:
                return None
            if isinstance(op, RetractOp):
                mutations.append(
                    FieldMutation(
                        op="retract",
                        field=field_path,
                        assertion_id=op.assertion_id,
                        meta=meta,
                    )
                )
                continue
            value = self._application_write_value_for_op(op)
            if value is None:
                return None
            mutations.append(
                FieldMutation(
                    op="set" if isinstance(op, SetOp) else "add",
                    field=field_path,
                    value=value,
                    meta=meta,
                )
            )
        return EntityWriteCommand(
            target=AppEntitySelector(
                entity_type=target.entity_type,
                identity=dict(target.identity),
                encoded_ref=target.encoded_ref,
            ),
            mutations=tuple(mutations),
            create_if_missing=create_if_missing,
            include_dependencies=True,
        )

    def _application_write_value_for_op(self, op: SetOp | AddOp) -> Any | None:
        if op.value_kind == "handle":
            ref_handle_id = op.value
            if not isinstance(ref_handle_id, int):
                return None
            ref_handle = self._handles_by_id.get(ref_handle_id)
            if ref_handle is None:
                return None
            return self._application_entity_ref_for_handle(ref_handle)
        if op.value_kind == "entity_ref":
            if not isinstance(op.value, str):
                return None
            identity = self._sdk._identity_values_by_e_ref.get(op.value)
            entity_type = entity_type_from_ref(op.value)
            if not isinstance(identity, dict) or not identity or not isinstance(entity_type, str):
                return None
            return AppEntityRef(
                entity_type=entity_type,
                identity=dict(identity),
                encoded_ref=op.value,
            )

        schema_pred = self._sdk._schema_pred_for_field(op.field)
        try:
            rest_terms = self._sdk._rest_terms_for_field(schema_pred, value=op.value)
        except Exception:
            return None
        if len(rest_terms) != 1:
            return None
        tag, value = rest_terms[0]
        if tag == "entity_ref":
            return None
        return value

    def _application_entity_ref_for_handle(self, handle: ManagedEntityHandle) -> AppEntityRef | None:
        e_ref = self._ensure_handle_resolved(handle, path=handle.path)
        identity_values = self._sdk._identity_values_by_e_ref.get(e_ref)
        if not isinstance(identity_values, dict) or not identity_values:
            return None
        try:
            identity = _normalize_json_object(identity_values, path=f"{handle.path}.identity", allow_nested=False)
        except SDKStoreError:
            return None
        if not identity:
            return None
        return AppEntityRef(
            entity_type=handle.entity_cls.__name__,
            identity=identity,
            encoded_ref=e_ref,
        )

    def _application_meta(self, meta: dict[str, Any], *, path: str) -> dict[str, Any] | None:
        try:
            return _normalize_json_object(meta, path=path, allow_nested=True)
        except SDKStoreError:
            return None

    def _prune_application_plan(
        self,
        *,
        handle: ManagedEntityHandle,
        plan: EntityWritePlan,
        field_ops: list[BatchOp],
        delegated_target_refs: set[str],
    ) -> EntityWritePlan:
        if plan.resolved_target is None:
            return plan
        target_ref = plan.resolved_target.encoded_ref or handle.e_ref
        if not isinstance(target_ref, str) or not target_ref:
            return plan

        retained_ops: list[PlannedOpDTO] = []
        for op in plan.planned_ops:
            op_target_ref = op.target.encoded_ref
            if op_target_ref is None:
                continue
            if op_target_ref != target_ref and op_target_ref in delegated_target_refs:
                continue
            if op_target_ref == target_ref:
                if op.op == "record_exists":
                    continue
                if op.field is not None:
                    pred = self._sdk._application_schema_index.field_predicates.get((op.field.entity_type, op.field.field_name))
                    if pred is not None and pred.is_identity_field:
                        continue
            retained_ops.append(op)

        info = self._sdk._application_schema_index.entities.get(plan.resolved_target.entity_type)
        if info is None:
            return plan

        identity_ops: list[PlannedOpDTO] = []
        for identity_field in info.identity_fields:
            identity_ops.append(
                PlannedOpDTO(
                    op="set",
                    target=plan.resolved_target,
                    field=FieldPath(entity_type=plan.resolved_target.entity_type, field_name=identity_field.name),
                    value=plan.resolved_target.identity[identity_field.name],
                )
            )

        planned_ops: list[PlannedOpDTO] = list(identity_ops)
        planned_ops.extend(retained_ops)
        return EntityWritePlan(
            command=plan.command,
            resolved_target=plan.resolved_target,
            resolved_dependencies=plan.resolved_dependencies,
            planned_ops=tuple(planned_ops),
            can_apply=plan.can_apply,
            errors=plan.errors,
            warnings=plan.warnings,
        )

    def _handle_requires_create_if_missing(self, handle: ManagedEntityHandle) -> bool:
        spec = self._sdk._entity_spec_by_class.get(handle.entity_cls)
        if not isinstance(spec, dict):
            return False
        return any(op.kind in {"set", "add"} for op in handle._staged_ops)

    def _plan_value(self, value: Any, *, path: str) -> tuple[_ValueKind, Any]:
        if isinstance(value, ManagedEntityHandle):
            return ("handle", value.handle_id)
        if isinstance(value, str) and value.startswith("idref_v1:"):
            return ("entity_ref", value)
        return ("scalar", value)

    def _value_dedup_key(self, value: Any) -> str:
        if isinstance(value, ManagedEntityHandle):
            return f"handle:{value.handle_id}"
        if isinstance(value, str) and value.startswith("idref_v1:"):
            return f"entity_ref:{value}"
        return repr(value)

    def _stage_field_op(
        self,
        owner: ManagedEntityHandle,
        kind: Literal["set", "add"],
        field_name: str,
        field: Field,
        value: Any,
        *,
        meta: dict[str, Any] | None,
    ) -> None:
        schema_pred = self._sdk._schema_pred_for_field(field)
        self._ensure_handle_resolved(owner, path=f"{owner.path}.{field_name}")

        # Early validation for local type/cardinality mistakes when possible.
        value_for_validation = value
        if isinstance(value, ManagedEntityHandle):
            self._ensure_handle_resolved(value, path=f"{owner.path}.{field_name}")
            value_for_validation = value.e_ref
        if isinstance(value_for_validation, Entity):
            raise SDKStoreError(f"{owner.path}.{field_name}: plain Entity instance is not supported; use tx.entity(...) handle or entity_ref")
        try:
            self._sdk._rest_terms_for_field(schema_pred, value=value_for_validation)
        except Exception as exc:
            raise SDKStoreError(f"{owner.path}.{field_name}: {exc}") from exc

        op = _StagedFieldOp(
            kind=kind,
            field_name=field_name,
            field=field,
            value=value,
            meta=_copy_meta(meta),
            op_index=self._next_op_index,
            path=self._field_path(owner, field_name),
        )
        self._next_op_index += 1
        owner._append_staged(op)

    def _stage_retract_op(
        self,
        owner: ManagedEntityHandle,
        field_name: str,
        field: Field,
        assertion_id: Any,
        *,
        meta: dict[str, Any] | None,
    ) -> None:
        self._ensure_handle_resolved(owner, path=f"{owner.path}.{field_name}.retract")
        if not isinstance(assertion_id, str) or not assertion_id:
            raise SDKStoreError(f"{owner.path}.{field_name}.retract: assertion_id must be non-empty string")
        meta_norm = _copy_meta(meta)
        path = f"{owner.path}.{field_name}.retract"
        existing_pair = self._retract_ops_by_assertion_id.get(assertion_id)
        if existing_pair is not None:
            existing_owner, existing = existing_pair
            if existing_owner is not owner:
                raise SDKStoreError(
                    f"{path}: duplicate retract assertion_id already staged on {existing.path}"
                )
            existing.meta = meta_norm
            existing.path = path
            existing.op_index = self._next_op_index
            self._next_op_index += 1
            return
        op = _StagedFieldOp(
            kind="retract",
            field_name=field_name,
            field=field,
            value=assertion_id,
            meta=meta_norm,
            op_index=self._next_op_index,
            path=path,
        )
        self._next_op_index += 1
        self._retract_ops_by_assertion_id[assertion_id] = (owner, op)
        owner._append_staged(op)

    @staticmethod
    def _field_path(owner: ManagedEntityHandle, field_name: str) -> str:
        return f"{owner.path}.{field_name}"

    def _bind_identity(self, handle: ManagedEntityHandle, identity_values: dict[str, Any]) -> None:
        if not isinstance(identity_values, dict) or not identity_values:
            raise SDKStoreError(f"{handle.path}.bind(...): identity kwargs must be non-empty")
        self._validate_identity_keys(handle.entity_cls, identity_values, path=f"{handle.path}.bind(...)")
        for key, value in identity_values.items():
            if key in handle.identity_values and handle.identity_values[key] != value:
                raise SDKStoreError(
                    f"{handle.path}.bind(...): identity field '{key}' is immutable once bound "
                    f"({handle.identity_values[key]!r} != {value!r})"
            )
            handle.identity_values[key] = value
        materialized, _ = self._materialize_identity_values(handle.entity_cls, handle.identity_values)
        handle.identity_values = materialized
        if handle.e_ref is not None:
            expected_ref = self._sdk.entities.ref(handle.entity_cls, **materialized)
            if expected_ref != handle.e_ref:
                raise SDKStoreError(
                    f"{handle.path}.bind(...): bound identity no longer matches existing ref; "
                    "identity is immutable after resolution"
                )
            return

        _, missing = self._materialize_identity_values(handle.entity_cls, handle.identity_values)
        if not missing:
            self._ensure_handle_resolved(handle, path=f"{handle.path}.bind(...)")

    def _identity_spec_rows(self, entity_cls: type[Entity]) -> list[dict[str, Any]]:
        spec = self._sdk._entity_spec_by_class.get(entity_cls)
        if not isinstance(spec, dict):
            raise SDKStoreError(f"unknown Entity class: {entity_cls.__name__}")
        rows = spec.get("identity_fields")
        if not isinstance(rows, list):
            raise SDKStoreError(f"invalid entity spec identity_fields for {entity_cls.__name__}")
        out = [row for row in rows if isinstance(row, dict)]
        if not out:
            raise SDKStoreError(f"{entity_cls.__name__} must declare at least one identity field")
        return out

    def _validate_identity_keys(self, entity_cls: type[Entity], identity_values: dict[str, Any], *, path: str) -> None:
        allowed = {str(row.get("name")) for row in self._identity_spec_rows(entity_cls) if isinstance(row.get("name"), str)}
        unknown = sorted(set(identity_values.keys()) - allowed)
        if unknown:
            raise SDKStoreError(f"{path}: unknown identity fields for {entity_cls.__name__}: {unknown}")

    def _materialize_identity_values(
        self,
        entity_cls: type[Entity],
        identity_values: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        materialized = dict(identity_values)
        missing: list[str] = []
        for row in self._identity_spec_rows(entity_cls):
            name = row.get("name")
            if not isinstance(name, str) or not name:
                continue
            if name in materialized:
                continue
            missing.append(name)
        return materialized, missing

    def _ensure_handle_resolved(self, handle: ManagedEntityHandle, *, path: str) -> str:
        if isinstance(handle.e_ref, str):
            return handle.e_ref

        materialized, missing = self._materialize_identity_values(handle.entity_cls, handle.identity_values)
        handle.identity_values = materialized
        if missing:
            missing_sorted = sorted(missing)
            raise SDKStoreError(
                f"{path}: identity is incomplete for {handle.entity_cls.__name__}; missing: {missing_sorted}. "
                "Provide the complete identity bundle at tx.entity(...) time."
            )
        e_ref = self._sdk.entities.ref(handle.entity_cls, **materialized)
        existing = self._handles_by_e_ref.get(e_ref)
        if existing is not None and existing is not handle:
            raise SDKStoreError(
                f"{path}: identity resolves to existing handle {existing.path}; "
                "reuse that handle instead of rebinding a second instance"
            )
        handle.e_ref = e_ref
        self._handles_by_e_ref[e_ref] = handle
        return e_ref

def _copy_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise SDKStoreError("meta must be dict when provided")
    return dict(meta)


def _merge_meta(*parts: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for part in parts:
        if part:
            out.update(part)
    return out
