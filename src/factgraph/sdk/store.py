from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from factgraph.application import apply_write_plan, is_entity_identity_bundle_active, plan_write_command
from factgraph.application.schema_mutation_runtime import (
    SchemaAddResult,
    add_schema_classes as app_add_schema_classes,
)
from factgraph.application.workspace_runtime import load_workspace as app_load_workspace
from factgraph.application.workspace_runtime import resolve_workspace_paths
from factgraph.application.workspace_runtime import save_workspace as app_save_workspace
from factgraph.application.derivation_runtime import evaluate_derivation_plans
from factgraph.application.explain import EvidenceGraph, probe_native
from factgraph.application.explain.evidence_tree import (
    Const,
    EvidenceAtom,
    EvidenceRule,
    EvidenceTree,
    Fact,
    Holds,
    LAYOUT_TREE,
    Source,
)
from factgraph.adapters.problog.provenance import (
    ProbLogEvidenceContext,
    problog_trace_from_dict,
    problog_trace_to_evidence_graph,
)
from factgraph.adapters.problog.reach_explain import problog_reach_explain_to_evidence_graph
from factgraph.adapters.pyreason.provenance import pyreason_trace_from_dict, pyreason_trace_to_evidence_graph
from factgraph.adapters.souffle.reach_explain import souffle_reach_explain_to_evidence_graph
from factgraph.application.retract_guard import (
    RetractGuardError,
    check_retract_allowed,
)
from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DerivationEvaluateRequest,
    DetachedRowError,
    EntityRef as AppEntityRef,
    EntitySelector as AppEntitySelector,
    EntityWriteCommand,
    ErrorDTO,
    Explanation,
    FieldMutation,
    FieldPath,
    Rule as ApplicationRule,
    RuleExprError,
)
from factgraph.application.protocol.certainty import BOOLEAN_CERTAINTY, Certainty
from factgraph.application.protocol.evaluate_result import (
    EvaluateResult,
    ResultFingerprint,
    _FORM1_ROW_SUPPORT_KINDS,
    _build_closed_head_from_row,
    _build_minimal_row_evidence_graph,
    _candidate_set_to_evaluate_row,
    _legacy_candidate_payload_for_row_result,
    _public_term_value,
    _row_digest_for,
    canonical_bytes_for_evaluate,
    closed_head_digest_for,
    expr_digest_for_payload,
    new_run_id,
    result_digest_for,
    result_id_for,
    rule_set_digest_for_entries,
    config_digest_for,
    view_snapshot_digest_for_parts,
)
from factgraph.application.protocol.rule_expr import _RuleExpr, _coerce_rule_expr_operand, _iter_rule_operands
from factgraph.application.protocol.rule_expr_inspect import _inspect_closed_head, pin_specs_for_closed_head
from factgraph.application.protocol.rule_expr_lowering import (
    RuleExprAdapterSupport,
    RuleExprLoweringPlan,
    _classify_pyreason_rule_expr_support,
    _lower_application_rule,
    _lower_rule_expr,
    _materialize_adapter_derivation_plan,
    _validate_rule_expr_head_foundation,
    probe_seed_vars_by_head_port,
)
from factgraph.application.schema_runtime import build_schema_index, display_value, entity_type_from_ref
from factgraph.authoring.derivations import compile_authoring_derivation_v1
from factgraph.authoring.rules import compile_authoring_rule_v1
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import WriteProtocolError, retract_by_asrt
from factgraph.core.protocol.digests import sha256_hex
from factgraph.core.rules.where_ast import PredAtom, Var
from factgraph.core.semantics import SemanticsProfile, inspect_semantics_profile
from factgraph.core.schema.schema_ir import schema_digest
from factgraph.adapters.souffle.package import ExportOptions, export_package
from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.rules.rule_ir import RuleRegistry, RuleSpec
from factgraph.core.store._artifact_sidecar import FileArtifactSidecar
from factgraph.core.store._support import (
    PROBLOG_PROVENANCE_KIND,
    PYREASON_PROVENANCE_KIND,
    SOUFFLE_WITNESS_KIND,
    ProvenanceEnvelope,
    ProofReceipt,
    binding_dict_from_items,
)
from factgraph.adapters.souffle.runner import run_package
from factgraph.core.store.database import (
    AssertionInput,
    CommitResult,
    Database,
    DatabaseError,
    FrozenAssertionSet as DatabaseFrozenAssertionSet,
    _read_tx_object,
    schema_object_exists_for_workspace,
    validate_schema_object_for_workspace,
    write_schema_object_for_workspace,
)
from factgraph.core.store.premise_filter import MetaExclusion, PredicatePremiseAllowance
from factgraph.core.store.runtime import Store
from factgraph.core.store.ledger import AnnotationRow, Claim, ClaimArg, Ledger, MetaRow, Revokes
from factgraph.core.view.projector import build_args_for_claim, canonical_fact_sort_key, project_view_facts

from .compile import compile_schema_from_classes
from .dsl.branch import Case
from .facade import _ASSERTION_FILTER_MISSING
from .errors import (
    CardinalityError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    FrozenSnapshotError,
    SchemaConflictError,
    SchemaNonAdditiveError,
    SchemaNotFoundError,
    SDKStoreError,
    SDKValueError,
)
from .schema import Entity, Field, Identity
from .semantics import ProbLogConfig, PyReasonConfig

if TYPE_CHECKING:
    from factgraph.audit.proof_frame_diff import ProofFrameDiff


@dataclass(frozen=True)
class FrozenAssertionSet:
    name: str
    asrt_ids: frozenset[str]


_VIEW_TOMBSTONE = object()
_POLICY_TOMBSTONE = object()
_PROFILE_KWARG_UNSET = object()
_SEMANTICS_PROFILE_ENGINES = {"problog", "pyreason"}
_READPOLICY_REMOVED_MESSAGE = "ReadPolicy was removed. Use raw_kind / bound for uncertainty inputs."
_ATTACH_REJECTED_KWARGS = {
    "artifact_store_root",
    "ledger",
    "ledger_path",
    "path",
    "policy",
    "registry",
    "registry_root",
    "rules",
    "workspace_path",
}
_ATTACHED_WRITE_ERROR = (
    "attached FactGraph runtimes route writes only through fg.commit_assertions(...); "
    "{method_name} is not available on attached runtimes"
)
_RULE_EXPR_DEFAULT_ALIAS_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


class _ViewScopedLedger(Ledger):
    """Read-only Ledger view that exposes a durable Database view subset."""

    def __init__(
        self,
        base: Ledger,
        *,
        view: DatabaseFrozenAssertionSet,
        base_asrt_ids: frozenset[str],
    ) -> None:
        self._base = base
        self._view = view
        self._base_asrt_ids = base_asrt_ids
        self._visible_asrt_ids = frozenset(view.asrt_ids).intersection(base_asrt_ids)

    def _is_visible(self, asrt_id: str) -> bool:
        return asrt_id in self._visible_asrt_ids

    def _filter_claims(self, claims: Iterable[Claim]) -> list[Claim]:
        return [claim for claim in claims if self._is_visible(claim.asrt_id)]

    def get_claim(self, asrt_id: str) -> Claim | None:
        if not self._is_visible(asrt_id):
            return None
        return self._base.get_claim(asrt_id)

    def find_claims(self, pred_id: str | None = None, e_ref: str | None = None) -> list[Claim]:
        return self._filter_claims(self._base.find_claims(pred_id=pred_id, e_ref=e_ref))

    def find_claim_args(
        self,
        asrt_id: str | None = None,
        idx: int | None = None,
        tag: str | None = None,
    ) -> list[ClaimArg]:
        if asrt_id is not None and not self._is_visible(asrt_id):
            return []
        rows = self._base.find_claim_args(asrt_id=asrt_id, idx=idx, tag=tag)
        return [row for row in rows if self._is_visible(row.asrt_id)]

    def find_meta(
        self,
        asrt_id: str | None = None,
        key: str | None = None,
        kind: str | None = None,
    ) -> list[MetaRow]:
        if asrt_id is not None and not self._is_visible(asrt_id):
            return []
        rows = self._base.find_meta(asrt_id=asrt_id, key=key, kind=kind)
        return [row for row in rows if self._is_visible(row.asrt_id)]

    def find_annotations(
        self,
        asrt_id: str | None = None,
        namespace: str | None = None,
        category: str | None = None,
        key: str | None = None,
    ) -> list[AnnotationRow]:
        if asrt_id is not None and not self._is_visible(asrt_id):
            return []
        rows = self._base.find_annotations(
            asrt_id=asrt_id,
            namespace=namespace,
            category=category,
            key=key,
        )
        return [row for row in rows if self._is_visible(row.asrt_id)]

    def has_active_revocation(self, revoked_asrt_id: str) -> bool:
        if not self._is_visible(revoked_asrt_id):
            return False
        return any(
            row.revoked_asrt_id == revoked_asrt_id and row.revoker_asrt_id in self._base_asrt_ids
            for row in self._base.revokes
        )

    def find_revoker(self, revoked_asrt_id: str) -> str | None:
        if not self._is_visible(revoked_asrt_id):
            return None
        for row in self._base.revokes:
            if row.revoked_asrt_id == revoked_asrt_id and row.revoker_asrt_id in self._base_asrt_ids:
                return row.revoker_asrt_id
        return None

    @property
    def claims(self) -> list[Claim]:
        return self._filter_claims(self._base.claims)

    @property
    def claim_args(self) -> list[ClaimArg]:
        return [row for row in self._base.claim_args if self._is_visible(row.asrt_id)]

    @property
    def meta_rows(self) -> list[MetaRow]:
        return [row for row in self._base.meta_rows if self._is_visible(row.asrt_id)]

    @property
    def annotation_rows(self) -> list[AnnotationRow]:
        return [row for row in self._base.annotation_rows if self._is_visible(row.asrt_id)]

    @property
    def revokes(self) -> list[Revokes]:
        return [row for row in self._base.revokes if row.revoker_asrt_id in self._base_asrt_ids]

    def get_ledger_meta(self, key: str) -> str | None:
        if key == "db_id":
            return self._view.db_id
        if key == "head_tx_id":
            return self._view.base_tx_id
        if key == "schema_digest":
            return self._view.schema_digest
        return self._base.get_ledger_meta(key)

    def _reject_read_only(self) -> None:
        raise SDKStoreError("view-attached FactGraph runtimes are read-only")

    def append_assertion(self, **kwargs: Any) -> Any:
        self._reject_read_only()

    def append_revocation(self, *args: Any, **kwargs: Any) -> Any:
        self._reject_read_only()

    def append_claim(self, claim: Claim) -> None:
        self._reject_read_only()

    def append_claim_args(self, rows: list[ClaimArg]) -> None:
        self._reject_read_only()

    def append_meta(self, rows: list[MetaRow]) -> None:
        self._reject_read_only()

    def append_annotations(self, rows: list[AnnotationRow]) -> None:
        self._reject_read_only()

    def append_revokes(self, row: Revokes) -> None:
        self._reject_read_only()

    def set_ledger_meta(self, key: str, value: str) -> None:
        self._reject_read_only()

    def replace_ledger_meta(self, key: str, value: str) -> None:
        self._reject_read_only()


def _ledger_for_durable_database_view(db: Database, view: object) -> Ledger:
    if not isinstance(view, DatabaseFrozenAssertionSet):
        raise SDKStoreError(
            "FactGraph.attach(db, view=...) expects a durable Database view from db.create_view(...); "
            "SDK in-memory fg.assertion_views.create(...) views are not Database-anchored"
        )
    if view.db_id != db.db_id:
        raise SDKStoreError(
            f"view db_id mismatch: view.db_id={view.db_id!r}, Database.db_id={db.db_id!r}"
        )
    if view.schema_digest != db.schema_digest:
        raise SDKStoreError(
            f"view schema mismatch: view.schema_digest={view.schema_digest!r}, "
            f"Database.schema_digest={db.schema_digest!r}"
        )
    paths = getattr(db, "_workspace_paths", None)
    if paths is None:
        raise SDKStoreError("FactGraph.attach(db, view=...) requires a durable Database workspace")
    try:
        base_asrt_ids = _database_asrt_ids_at_tx(db, view.base_tx_id)
    except DatabaseError as exc:
        raise SDKStoreError(f"view base_tx_id not found in Database: {view.base_tx_id!r}") from exc
    missing_ids = sorted(set(view.asrt_ids) - base_asrt_ids)
    if missing_ids:
        sample = ", ".join(missing_ids[:3])
        suffix = "" if len(missing_ids) <= 3 else f", ... (+{len(missing_ids) - 3} more)"
        raise SDKStoreError(
            f"view references assertion ids not present at base_tx_id={view.base_tx_id!r}: {sample}{suffix}"
        )
    return _ViewScopedLedger(db._ledger_for_attach(), view=view, base_asrt_ids=frozenset(base_asrt_ids))


def _database_asrt_ids_at_tx(db: Database, tx_id: str) -> set[str]:
    paths = getattr(db, "_workspace_paths", None)
    if paths is None:
        raise DatabaseError("tx lookup requires a durable Database workspace")
    current_tx_id: str | None = tx_id
    asrt_ids: set[str] = set()
    while current_tx_id is not None:
        payload = _read_tx_object(paths, current_tx_id)
        asrt_ids.update(payload["added_asrt_ids"])
        current_tx_id = payload["parent_tx_id"]
    return asrt_ids


class _SDKAssertionViewsManager:
    """Read-only namespace for named frozen assertion-id selections.

    `fg.assertion_views` stores assertion-id sets and has no built-in
    `default` entry. The name `default` is just another user-defined frozen
    assertion set name when callers create it.
    """

    def __init__(self, sdk: "SDKStore") -> None:
        # Read-only attribute boundary per post-L redesign §5.4 lock.
        # Internal init bypasses ``__setattr__`` via ``object.__setattr__``;
        # external assignment (``fg.assertion_views.foo = ...``) raises
        # ``FrozenSnapshotError``. Dict mutation against ``self._views``
        # via ``create`` / ``update`` / ``delete`` is unaffected (it
        # mutates the dict, not the attribute).
        object.__setattr__(self, "_sdk", sdk)
        object.__setattr__(self, "_views", {})

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.assertion_views namespace is read-only")

    def create(
        self,
        name: str,
        *,
        asrt_ids: Iterable[str] | None = None,
        asrts: Iterable[Any] | None = None,
    ) -> FrozenAssertionSet:
        """Create a named frozen assertion set.

        An assertion set stores assertion ids only. It does not store a read
        policy and it is not included in `fg.save_workspace(...)` persistence.
        """
        self._sdk._reject_attached_write("fg.assertion_views.create")
        normalized = _normalize_view_name(name)
        if normalized in self._views:
            raise SDKStoreError(f"view already exists: {normalized}")
        entry = _build_view_entry(
            normalized,
            asrt_ids=asrt_ids,
            asrts=asrts,
        )
        self._views[normalized] = entry
        return entry

    def update(
        self,
        name: str,
        *,
        asrt_ids: Iterable[str] | None = None,
        asrts: Iterable[Any] | None = None,
    ) -> FrozenAssertionSet:
        """Replace the assertion ids for an existing frozen assertion set."""
        self._sdk._reject_attached_write("fg.assertion_views.update")
        normalized = _normalize_view_name(name)
        if normalized not in self._views:
            raise SDKStoreError(f"view not found: {normalized}")
        entry = _build_view_entry(
            normalized,
            asrt_ids=asrt_ids,
            asrts=asrts,
        )
        self._views[normalized] = entry
        return entry

    def delete(self, name: str) -> None:
        """Delete a named frozen assertion set."""
        self._sdk._reject_attached_write("fg.assertion_views.delete")
        normalized = _normalize_view_name(name)
        if normalized not in self._views:
            raise SDKStoreError(f"view not found: {normalized}")
        self._views.pop(normalized, None)

    def get(self, name: str) -> FrozenAssertionSet:
        """Return a named frozen assertion set."""
        normalized = _normalize_view_name(name)
        if normalized not in self._views:
            raise SDKStoreError(f"view not found: {normalized}")
        return self._views[normalized]

    def list(self) -> dict[str, FrozenAssertionSet]:
        """Return all frozen assertion sets keyed by set name."""
        return {name: spec for name, spec in self._views.items()}


class AssertionsManager:
    """Layer 3 namespace manager for assertion records and asrt_id retraction."""

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.assertions namespace is read-only")

    def by_id(self, asrt_id: str) -> Any:
        if not isinstance(asrt_id, str) or not asrt_id:
            raise SDKStoreError("fg.assertions.by_id(asrt_id) expects non-empty string")
        return _assertion_record_by_id(self._sdk, asrt_id)

    def by_ids(self, asrt_ids: Iterable[str], *, strict: bool = False) -> Any:
        if isinstance(asrt_ids, (str, bytes)):
            raise SDKStoreError("fg.assertions.by_ids(asrt_ids) expects iterable[str], not string")
        if not isinstance(strict, bool):
            raise SDKStoreError("fg.assertions.by_ids(..., strict=...) expects bool")
        try:
            normalized = tuple(asrt_ids)
        except TypeError as exc:
            raise SDKStoreError("fg.assertions.by_ids(asrt_ids) expects iterable[str]") from exc
        for value in normalized:
            if not isinstance(value, str) or not value:
                raise SDKStoreError("fg.assertions.by_ids(asrt_ids) expects non-empty string ids")
        if strict:
            seen: set[str] = set()
            for asrt_id in normalized:
                if asrt_id in seen:
                    raise SDKStoreError(f"by_ids strict mode: duplicate assertion id {asrt_id!r} in input")
                seen.add(asrt_id)

        from .facade import AssertionRecordSet

        records = []
        for asrt_id in sorted(set(normalized)):
            record = _assertion_record_by_id(self._sdk, asrt_id)
            if record is None:
                if strict:
                    raise SDKStoreError(f"by_ids strict mode: assertion id {asrt_id!r} not found")
                continue
            records.append(record)
        return AssertionRecordSet(records)

    @property
    def active(self) -> Any:
        from .facade import AssertionRecordSet

        return AssertionRecordSet(record for record in self.all if record.is_active)

    @property
    def all(self) -> Any:
        from .facade import AssertionRecordSet, _assertion_record_from_claim, _claim_sort_key

        records = [
            _assertion_record_from_claim(self._sdk, claim, schema_pred=_schema_pred_by_pred_id(self._sdk, claim.pred_id))
            for claim in sorted(self._sdk.ledger.find_claims(), key=lambda claim: _claim_sort_key(self._sdk, claim))
        ]
        return AssertionRecordSet(records)

    def field(self, field: Field) -> Any:
        if not isinstance(field, Field):
            raise SDKStoreError("fg.assertions.field(...) expects sdk.Field descriptor; string names are ambiguous")
        schema_pred = self._sdk._schema_pred_for_field(field)
        pred_id = schema_pred.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            raise SDKStoreError("schema predicate missing pred_id for field")

        from .facade import AssertionView, _assertion_record_from_claim, _claim_sort_key

        claims = self._sdk.ledger.find_claims(pred_id=pred_id)
        history_records = tuple(
            _assertion_record_from_claim(self._sdk, claim, schema_pred=schema_pred)
            for claim in sorted(claims, key=lambda claim: _claim_sort_key(self._sdk, claim))
        )
        return AssertionView(
            entity_type=str(schema_pred.get("owner_type", "")),
            field_name=str(getattr(field, "sdk_attr_name", schema_pred.get("py_field_name", ""))),
            cardinality=str(schema_pred.get("cardinality", getattr(field, "cardinality", "single"))),
            active_records=tuple(record for record in history_records if record.is_active),
            history_records=history_records,
        )

    def where(
        self,
        *,
        field: Any = _ASSERTION_FILTER_MISSING,
        e_ref: Any = _ASSERTION_FILTER_MISSING,
        value: Any = _ASSERTION_FILTER_MISSING,
        value_tag: Any = _ASSERTION_FILTER_MISSING,
        _meta: Any = _ASSERTION_FILTER_MISSING,
    ) -> Any:
        """Filter active assertion records by canonical Layer 3 criteria.

        Step 6 intentionally scopes manager-level `where` to active assertions.
        Historical filtering remains available by chaining from `all()` until
        Step 8/9 unify AssertionView and hard-remove flat meta kwargs.
        """
        from .facade import AssertionRecordSet, _assertion_record_from_claim, _claim_sort_key

        pred_id_filter: str | None = None
        if field is not _ASSERTION_FILTER_MISSING:
            if not isinstance(field, Field):
                raise SDKStoreError(
                    "fg.assertions.where(field=...) expects sdk.Field descriptor; "
                    "pass assertion ids to by_id/by_ids or use fg.entities/fg.fields "
                    "for other navigation keys. See ADR-API §4.1.1."
                )
            schema_pred = self._sdk._schema_pred_for_field(field)
            pred_id = schema_pred.get("pred_id")
            if not isinstance(pred_id, str) or not pred_id:
                raise SDKStoreError("schema predicate missing pred_id for field")
            pred_id_filter = pred_id

        if e_ref is not _ASSERTION_FILTER_MISSING and not isinstance(e_ref, str):
            raise SDKStoreError("fg.assertions.where(e_ref=...) expects e_ref string")
        if value_tag is not _ASSERTION_FILTER_MISSING and not isinstance(value_tag, str):
            raise SDKStoreError("fg.assertions.where(value_tag=...) expects string tag")
        if _meta is not _ASSERTION_FILTER_MISSING and not isinstance(_meta, dict):
            raise SDKStoreError("fg.assertions.where(_meta=...) expects dict when provided")

        records = []
        claims = self._sdk.ledger.find_claims(
            pred_id=pred_id_filter,
            e_ref=e_ref if e_ref is not _ASSERTION_FILTER_MISSING else None,
        )
        for claim in sorted(claims, key=lambda claim: _claim_sort_key(self._sdk, claim)):
            if self._sdk.ledger.has_active_revocation(claim.asrt_id):
                continue
            schema_pred = _schema_pred_by_pred_id(self._sdk, claim.pred_id)
            record = _assertion_record_from_claim(self._sdk, claim, schema_pred=schema_pred)
            if value is not _ASSERTION_FILTER_MISSING and record.value != value:
                continue
            if value_tag is not _ASSERTION_FILTER_MISSING:
                claim_tag = claim.rest_terms[-1][0] if claim.rest_terms else None
                if claim_tag != value_tag:
                    continue
            if _meta is not _ASSERTION_FILTER_MISSING:
                if any(record.meta.raw.get(key) != expected for key, expected in _meta.items()):
                    continue
            records.append(record)
        return AssertionRecordSet(records)

    def retract(
        self,
        asrt_id: Any,
        *,
        meta: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str | None:
        """Retract one assertion by id with Slice 2 guard semantics preserved."""
        self._sdk._reject_attached_write("fg.assertions.retract")
        if kwargs:
            raise SDKStoreError(
                "fg.assertions.retract requires asrt_id (Layer 3); pass "
                "EntityClass + identity to fg.entities.delete(...). "
                "See ADR-API §4.1.1."
            )
        if not isinstance(asrt_id, str) or not asrt_id:
            raise SDKStoreError(
                "fg.assertions.retract(asrt_id) expects non-empty string "
                "(Layer 3); use fg.entities.delete(...) for entity-level "
                "delete. See ADR-API §4.1.1."
            )

        try:
            check_retract_allowed(
                asrt_id,
                ledger=self._sdk._store.ledger,
                schema_index=self._sdk._application_schema_index,
            )
        except RetractGuardError as guard_exc:
            if guard_exc.classification == "identity":
                raise SDKStoreError(
                    f"Identity Claim {guard_exc.asrt_id} "
                    f"(pred_id={guard_exc.pred_id}) is immutable per INV-7c. "
                    "Identity Claims can only be: "
                    "(a) created via fg.entities.create(EntityCls, **identity_kwargs); "
                    "(b) removed as part of fg.entities.delete(e_ref) "
                    "(atomic full-entity revoke). "
                    "To modify the identity bundle of an entity, delete the old entity "
                    "and create a new one with the new identity values "
                    "(Identity is immutable per INV-7a). See ADR-IC §4.1.",
                    code=guard_exc.code,
                ) from guard_exc
            raise SDKStoreError(
                f"<EntityType>:exists Claim {guard_exc.asrt_id} "
                f"(pred_id={guard_exc.pred_id}) cannot be retracted independently. "
                "The :exists Claim is co-emitted atomically with Identity Claims "
                "and can only be removed via fg.entities.delete(e_ref) "
                "(atomic full-entity revoke). "
                "This guard is transitional — Step 2+ may remove :exists emission "
                "entirely (see ADR-IC §4.4).",
                code=guard_exc.code,
            ) from guard_exc
        try:
            return retract_by_asrt(self._sdk._store.ledger, asrt_id, meta)
        except WriteProtocolError as exc:
            code = "ASSERTION_NOT_FOUND" if "unknown revoked_asrt_id" in str(exc) else None
            raise SDKStoreError(str(exc), code=code) from exc

    def append_meta(self, asrt_id: str, key: str, value: Any) -> None:
        """Append one meta row to an existing assertion (public reclassification seam).

        Meta rows are append-only: the new row never replaces earlier rows, it
        extends the assertion's meta history. Every canonical read resolves a
        key LAST-WINS — ``record.meta.raw`` (``_meta_raw_for_assertion``,
        sdk/facade.py) and the premise admissibility filter
        (``core/store/premise_filter.py::is_premise_excluded``) both take the
        most recently written row. Appending e.g. a new ``provenance_class``
        value therefore reclassifies the assertion for rule evaluation (moves
        it INTO or OUT OF an excluded class) while the full history stays
        auditable via ``fg.ledger.find_meta(asrt_id=..., key=...)``.

        This is the supported public surface for post-write meta
        reclassification. ``Ledger.append_meta`` remains a deprecated
        compatibility seam and may be downgraded to private in a later
        cleanup phase; consumers should call this method instead.

        ``value`` must be a scalar (str/bool/int/float — the same shape free
        meta keys accept at write time); the row kind is derived from the
        Python type. Raises ``SDKStoreError`` for invalid input or an unknown
        ``asrt_id``.
        """
        self._sdk._reject_attached_write("fg.assertions.append_meta")
        if not isinstance(asrt_id, str) or not asrt_id:
            raise SDKStoreError(
                "fg.assertions.append_meta(asrt_id, ...) expects non-empty string asrt_id"
            )
        if not isinstance(key, str) or not key:
            raise SDKStoreError(
                "fg.assertions.append_meta(..., key, ...) expects non-empty string key"
            )
        if isinstance(value, bool):
            kind = "bool"
        elif isinstance(value, str):
            kind = "str"
        elif isinstance(value, int):
            kind = "int"
        elif isinstance(value, float):
            kind = "float"
        else:
            raise SDKStoreError(
                "fg.assertions.append_meta(..., value) expects a scalar "
                f"(str/bool/int/float), got {type(value).__name__}"
            )
        try:
            self._sdk._store.ledger.append_meta(
                [MetaRow(asrt_id=asrt_id, key=key, kind=kind, value=value)]
            )
        except ValueError as exc:
            code = "ASSERTION_NOT_FOUND" if "unknown asrt_id" in str(exc) else None
            raise SDKStoreError(str(exc), code=code) from exc


class _SDKSchemaManager:
    """Namespace manager for schema registration and extension."""

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.schema namespace is read-only")

    def ingest(self, *args: Any, **kwargs: Any) -> Any:
        return self._sdk._ingest(*args, **kwargs)

    def validate_provenance(self, *args: Any, **kwargs: Any) -> Any:
        return self._sdk._validate_provenance(*args, **kwargs)

    def register(self, entity_cls: type[Entity]) -> SchemaAddResult:
        """Register a new Entity type."""
        entity_type = _entity_type_for_schema_class(entity_cls, field_name="entity_cls")
        if entity_type in self._sdk._entity_types_by_class_registry():
            raise SchemaConflictError(
                f"entity_type already registered: {entity_type}",
                code="SCHEMA_CONFLICT",
            )
        return self._sdk._apply_schema_class_update(
            entity_cls,
            operation="register",
            non_additive_error_type=SchemaConflictError,
        )

    def extend(self, entity_cls: type[Entity]) -> SchemaAddResult:
        """Add non-identity Fields to an existing Entity type."""
        entity_type = _entity_type_for_schema_class(entity_cls, field_name="entity_cls")
        if entity_type not in self._sdk._entity_types_by_class_registry():
            raise SchemaNotFoundError(
                f"entity_type not registered: {entity_type}",
                code="SCHEMA_NOT_FOUND",
            )
        return self._sdk._apply_schema_class_update(
            entity_cls,
            operation="extend",
            non_additive_error_type=SchemaNonAdditiveError,
        )

    def apply(self, entity_cls: type[Entity]) -> SchemaAddResult:
        """Register a new Entity or extend an existing Entity."""
        entity_type = _entity_type_for_schema_class(entity_cls, field_name="entity_cls")
        if entity_type in self._sdk._entity_types_by_class_registry():
            return self.extend(entity_cls)
        return self.register(entity_cls)


class _SDKFieldsManager:
    """Layer 2 namespace manager for field-cell operations(per ADR-API §4.1).

    Layer 2 navigation key:`Field descriptor + e_ref (+ optional value)`.
    Assertion ids belong to Layer 3(``fg.assertions.*``);entity macros belong
    to Layer 1(``fg.entities.*``).

    Slice 3a Step 7 removes the historical flat write shortcuts. This manager
    now owns all Field + e_ref user-facing cell operations.
    """

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.fields namespace is read-only")

    def _reject_non_field_descriptor(
        self,
        field: Any,
        *,
        method: str,
        allow_identity: bool = False,
    ) -> None:
        if isinstance(field, Field):
            return
        if allow_identity and isinstance(field, Identity):
            return
        if isinstance(field, str):
            raise SDKStoreError(
                f"fg.fields.{method}() requires a Field descriptor (Layer 2 "
                "navigation key); got str/asrt_id — pass assertion ids to "
                "fg.assertions.* (Layer 3) instead. See ADR-API §4.1.1."
            )
        if isinstance(field, type) and issubclass(field, Entity):
            raise SDKStoreError(
                f"fg.fields.{method}() requires a Field descriptor (Layer 2 "
                "navigation key); got Entity class — use fg.entities.* "
                "(Layer 1) instead. See ADR-API §4.1.1."
            )
        if isinstance(field, Identity):
            raise SDKStoreError(
                f"fg.fields.{method}() does not accept Identity descriptors for "
                "value writes; Identity Claims are immutable anchors per INV-7c. "
                "Use fg.entities.delete + fg.entities.create for identity-bundle "
                "changes. See ADR-API §4.1.1."
            )
        raise SDKStoreError(
            f"fg.fields.{method}() requires a Field descriptor (Layer 2 "
            f"navigation key); got {type(field).__name__}. See ADR-API §4.1.1."
        )

    def _schema_pred_for_descriptor(
        self,
        field: Field | Identity,
        *,
        method: str,
        allow_identity: bool = False,
    ) -> dict[str, Any]:
        self._reject_non_field_descriptor(field, method=method, allow_identity=allow_identity)
        if isinstance(field, Field):
            return self._sdk._schema_pred_for_field(field)

        owner_cls = getattr(field, "sdk_owner_cls", None)
        owner_type = getattr(owner_cls, "__name__", None)
        field_name = getattr(field, "sdk_attr_name", None)
        if not isinstance(owner_type, str) or not isinstance(field_name, str):
            raise SDKStoreError("Identity descriptor is not bound in this SDKStore schema")
        pred_info = self._sdk._application_schema_index.field_predicates.get((owner_type, field_name))
        if pred_info is None:
            self._sdk._raise_if_superseded_entity_class(owner_cls)
            raise SDKStoreError(f"schema predicate not found for {owner_type}.{field_name}")
        return {
            "pred_id": pred_info.pred_id,
            "owner_type": pred_info.owner_type,
            "py_field_name": pred_info.py_field_name,
            "cardinality": pred_info.cardinality,
            "arg_specs": [
                {"type_domain": "entity_ref"},
                {"type_domain": pred_info.value_type_domain},
            ],
        }

    def _active_claims_for_field(self, schema_pred: dict[str, Any], e_ref: str) -> list[Claim]:
        pred_id = schema_pred.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            raise SDKStoreError("schema predicate missing pred_id for field")
        return [
            claim
            for claim in self._sdk.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)
            if not self._sdk.ledger.has_active_revocation(claim.asrt_id)
        ]

    def _decode_claim_value(self, claim: Claim) -> Any:
        if not claim.rest_terms:
            return None
        return claim.rest_terms[-1][1]

    def set(
        self,
        field: Field,
        e_ref: str,
        value: Any,
        *,
        meta: dict[str, Any] | None = None,
    ) -> str:
        """Write a single-cardinality Field value."""
        self._reject_non_field_descriptor(field, method="set")
        self._sdk._reject_attached_write("fg.fields.set")
        return self._sdk._apply_field_mutation(op="set", field=field, e_ref=e_ref, value=value, meta=meta)

    def add(
        self,
        field: Field,
        e_ref: str,
        value: Any,
        *,
        meta: dict[str, Any] | None = None,
    ) -> str:
        """Append a multi-cardinality Field value."""
        self._reject_non_field_descriptor(field, method="add")
        self._sdk._reject_attached_write("fg.fields.add")
        return self._sdk._apply_field_mutation(op="add", field=field, e_ref=e_ref, value=value, meta=meta)

    def retract(
        self,
        field: Field | Identity,
        e_ref: str,
        value: Any,
        *,
        meta: dict[str, Any] | None = None,
    ) -> str | None:
        """Retract the unique active assertion matching ``(field, e_ref, value)``.

        Step 5 delegates the chosen assertion id to shipped ``SDKStore.retract``.
        That preserves Slice 2 INV-7c / `:exists` guard behavior without
        duplicating the Layer 3 retract guard in Layer 2.
        """
        schema_pred = self._schema_pred_for_descriptor(field, method="retract", allow_identity=True)
        expected_terms = self._sdk._rest_terms_for_field(schema_pred, value=value)
        matches = [
            claim
            for claim in self._active_claims_for_field(schema_pred, e_ref)
            if claim.rest_terms == expected_terms
        ]
        field_label = _field_label_for_pred(schema_pred)
        if not matches:
            raise SDKStoreError(
                f"no active assertion matching field={field_label}, "
                f"e_ref={e_ref!r}, value={value!r}"
            )
        if len(matches) > 1:
            raise SDKStoreError(
                f"ambiguous active assertions matching field={field_label}, "
                f"e_ref={e_ref!r}, value={value!r};pass asrt_id to "
                "fg.assertions.retract(asrt_id)"
            )
        return self._sdk.assertions.retract(matches[0].asrt_id, meta=meta)

    def delete(
        self,
        field: Field | Identity,
        e_ref: str,
        *,
        meta: dict[str, Any] | None = None,
    ) -> int:
        """Retract all active assertions for ``(field, e_ref)``.

        Partial-failure semantics are **fail-fast first-error**:claims are
        retracted sequentially through shipped ``SDKStore.retract`` and the
        first error is raised immediately. No rollback or best-effort behavior
        is introduced in Step 5.
        """
        schema_pred = self._schema_pred_for_descriptor(field, method="delete", allow_identity=True)
        count = 0
        for claim in self._active_claims_for_field(schema_pred, e_ref):
            self._sdk.assertions.retract(claim.asrt_id, meta=meta)
            count += 1
        return count

    def get(self, field: Field, e_ref: str) -> Any:
        """Return the current value for ``(field, e_ref)`` from active claims."""
        schema_pred = self._schema_pred_for_descriptor(field, method="get")
        claims = self._active_claims_for_field(schema_pred, e_ref)
        if str(schema_pred.get("cardinality", "single")) == "multi":
            claims = sorted(
                claims,
                key=lambda claim: canonical_fact_sort_key(build_args_for_claim(self._sdk.ledger, claim)),
            )
            values = [self._decode_claim_value(claim) for claim in claims]
            return tuple(values)
        values = [self._decode_claim_value(claim) for claim in claims]
        if not values:
            return None
        return values[-1]


class _SDKEntitiesManager:
    """Layer 1 namespace manager for entity-macro operations(per ADR-API §4.1).

    Layer 1 navigation key:`EntityClass + identity_kwargs` or managed `e_ref`.
    Layer 1 排他 enforcement(per ADR-API §4.1.1):this namespace does NOT
    accept ``asrt_id`` parameters(use ``fg.assertions.by_id(asrt_id)`` or
    ``fg.assertions.retract(asrt_id)`` instead)nor ``(Field, e_ref)`` value
    writes(use ``fg.fields.*`` for per-cell mutations).

    Slice 3a Step 7 removes the historical ``fg.read.*`` namespace and flat
    top-level shortcuts. This manager now owns all Layer 1 user-facing entity
    operations.
    """

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.entities namespace is read-only")

    def _reject_non_entity_class(self, entity_cls: Any, *, method: str) -> None:
        """Layer 1 排他 enforcement per ADR-API §4.1.1.

        Raises before delegating when the first positional arg is not an
        ``Entity`` subclass — surfaces a layer-specific error before the
        downstream ``_validate_entity_cls`` would raise the generic
        ``"unknown Entity class"`` message。
        """
        if isinstance(entity_cls, type) and issubclass(entity_cls, Entity):
            return
        if isinstance(entity_cls, str):
            raise SDKStoreError(
                f"fg.entities.{method}() requires an Entity subclass + identity_kwargs "
                f"(Layer 1 navigation key); got str — pass asrt_id to "
                f"fg.assertions.by_id(asrt_id) or fg.assertions.retract(asrt_id) "
                f"instead. See ADR-API §4.1.1."
            )
        if isinstance(entity_cls, Field):
            raise SDKStoreError(
                f"fg.entities.{method}() requires an Entity subclass (Layer 1 "
                f"navigation key); got Field descriptor — pass Field + e_ref + value "
                f"to fg.fields.* (Layer 2) instead. See ADR-API §4.1.1."
            )
        raise SDKStoreError(
            f"fg.entities.{method}() requires an Entity subclass + identity_kwargs "
            f"(Layer 1 navigation key); got {type(entity_cls).__name__}. "
            f"See ADR-API §4.1.1."
        )

    def get(self, entity_cls: type[Entity], **identity_kwargs: Any) -> Any:
        """Read one entity snapshot by identity values."""
        self._reject_non_entity_class(entity_cls, method="get")
        from .facade import sdk_get

        return sdk_get(self._sdk, entity_cls, **identity_kwargs)

    def where(
        self,
        entity_cls: type[Entity],
        *,
        policy: Any = _POLICY_TOMBSTONE,
        limit: int | None = None,
        _meta: dict[str, Any] | None = None,
        **field_filters: Any,
    ) -> Any:
        """Find entity snapshots by exact field filters(canonical signature)。

        Per ADR-API §4.1.2 + §4.4:``where`` is the canonical verb(rename of
        shipped ``find``)with **unified meta input** — flat ``source=`` /
        ``trace_id=`` / ``version=`` / ``meta=`` kwargs are rejected;canonical
        meta filtering accepted via ``_meta`` dict。

        **Slice 3a scope**:field-filter delegation to shipped
        ``sdk_find`` remains the underlying read implementation;flat meta
        kwargs are rejected with ADR-API §4.4 pointer。 ``_meta``
        parameter is accepted in the canonical signature but entity-query
        metadata projection is not yet implemented; assertion-level metadata
        filtering lives on ``fg.assertions.where`` and ``AssertionView.where``。
        """
        self._reject_non_entity_class(entity_cls, method="where")

        # Reject flat meta kwargs per ADR-API §4.4(no double-track)
        for forbidden in ("source", "trace_id", "version", "meta"):
            if forbidden in field_filters:
                raise SDKStoreError(
                    f"fg.entities.where() does not accept '{forbidden}=' flat kwarg; "
                    f"use _meta={{'{forbidden}': ...}} per ADR-API §4.4."
                )

        # Validate _meta shape; entity-query meta projection is not implemented.
        if _meta is not None:
            if not isinstance(_meta, dict):
                raise SDKStoreError(
                    "fg.entities.where(_meta=...) expects a dict when provided"
                )
            if _meta:
                # The entity query path cannot yet project assertion metadata
                # into entity rows; surfacing this explicitly is safer than
                # silently ignoring user input.
                raise SDKStoreError(
                    "fg.entities.where(_meta=...) entity metadata filtering is "
                    "not implemented; use fg.assertions.where(_meta=...) or "
                    "snapshot.assertions.where(_meta=...) for assertion metadata "
                    "filters."
                )

        from .facade import sdk_find

        self._sdk._reject_removed_read_policy(policy, api_path="fg.entities.where")
        return sdk_find(self._sdk, entity_cls, limit=limit, **field_filters)

    def match(
        self,
        entity_cls: type[Entity],
        template: Any,
        *,
        limit: int | None = None,
        **port_constraints: Any,
    ) -> Any:
        """Match visible snapshots against an application Rule or AND RuleExpr.

        Delegates to the shipped match runtime implementation.
        """
        self._reject_non_entity_class(entity_cls, method="match")
        from .match_runtime import sdk_match

        return sdk_match(self._sdk, entity_cls, template, limit=limit, **port_constraints)

    def ref(self, entity_cls: type[Entity], **identity_values: Any) -> str:
        """Return a managed e_ref for the entity identified by kwargs。

        Records the supplied identity into the SDKStore shadow store so that
        downstream ``fg.fields.set`` / ``fg.fields.add`` can resolve the e_ref。Does NOT write to the
        ledger — per ADR-IC §4.2.3 + Slice 2 Step 7,shadow store is the
        legacy lazy-materialization compatibility path,not a Layer 2 contract。
        """
        self._reject_non_entity_class(entity_cls, method="ref")
        return self._sdk._ref(entity_cls, **identity_values)

    def create(
        self,
        entity_cls: type[Entity],
        *,
        meta: dict[str, Any] | None = None,
        **identity: Any,
    ) -> str:
        """Eager-emit Identity Claims + ``<EntityType>:exists`` Claim atomically。

        Per ADR-IC §4.2(application 层 derive)+ ADR-API §4.1.2(entities
        namespace)+ Slice 3a SF4(eager emission + populate shadow store)。

        Flow:
        1. Layer 1 排他 enforcement(non-Entity-class reject per ADR-API §4.1.1)。
        2. Identity bundle completeness validation + shadow store populate via
           shipped ``SDKStore.ref(EC, **identity)`` path(per Slice 2 Step 7
           shadow store legacy documentation)。
        3. Build ``EntityCreateCommand`` DTO + delegate to application-layer
           ``plan_create_command`` + ``apply_create_plan``(per PF-S3 INV-6
           application-first;SDK manager NEVER does inline planner logic)。
        4. Return the deterministic e_ref。

        Raises:
            ``EntityAlreadyExistsError``(code=``ENTITY_ALREADY_EXISTS``)when
            an entity with the supplied identity is already visible in the
            ledger Active set(per blueprint §13.1 duplicate-create rejection)。
            ``SDKStoreError``(layer-specific)on bad Entity class or missing
            identity field。

        Notes:
            Coexists with the lazy ``fg.entities.ref + fg.fields.set``
            materialization path per SF4 — shadow store is the
            legacy compat surface;Step 2+ ``fg.entities.create`` is the eager
            path. Slice 3a does NOT remove the shadow store。
        """
        self._reject_non_entity_class(entity_cls, method="create")

        # Step 1+2: identity bundle completeness + shadow store populate via
        # shipped _ref path. SDKStore._ref raises SDKStoreError for missing
        # identity fields("missing identity field: <EC>.<name>")— the
        # canonical "complete identity bundle" check per ADR-IC §4.2.1。
        try:
            e_ref = self._sdk._ref(entity_cls, **identity)
        except SDKStoreError:
            raise

        # Step 3: application layer call(per PF-S3 INV-6 application-first)。
        from factgraph.application import apply_create_plan, plan_create_command
        from factgraph.application.protocol import EntityCreateCommand
        from factgraph.application.protocol import EntitySelector as AppEntitySelector

        command = EntityCreateCommand(
            target=AppEntitySelector(
                entity_type=entity_cls.__name__,
                identity=dict(identity),
                encoded_ref=e_ref,
            ),
            command_meta=dict(meta) if meta else {},
        )
        plan = plan_create_command(
            command,
            store=self._sdk._store,
            index=self._sdk._application_schema_index,
        )
        if not plan.can_apply:
            self._raise_create_error(plan.errors[0], entity_cls=entity_cls, identity=identity)

        result = apply_create_plan(
            plan,
            store=self._sdk._store,
            index=self._sdk._application_schema_index,
        )
        if result.errors:
            self._raise_create_error(result.errors[0], entity_cls=entity_cls, identity=identity)

        # Step 4: return deterministic e_ref。
        return e_ref

    def _raise_create_error(
        self,
        err: Any,  # ErrorDTO
        *,
        entity_cls: type[Entity],
        identity: dict[str, Any],
    ) -> None:
        """Map ErrorDTO from create planner/executor to SDK-layer error types。

        ``ENTITY_ALREADY_EXISTS`` → ``EntityAlreadyExistsError``(typed,
        carries entity_type/identity_kwargs/e_ref attrs);other codes →
        generic ``SDKStoreError`` with the code preserved。
        """
        if err.code == "ENTITY_ALREADY_EXISTS":
            raise EntityAlreadyExistsError(
                err.message,
                entity_type=entity_cls.__name__,
                identity_kwargs=dict(identity),
                e_ref=err.details.get("e_ref"),
                code=err.code,
            )
        raise SDKStoreError(err.message, code=err.code)

    def delete(
        self,
        e_ref_or_cls: Any,
        *,
        meta: dict[str, Any] | None = None,
        **identity: Any,
    ) -> int:
        """Whole-entity revoke per ADR-IC §4.1 强制点 3 + Slice 3a §5.4。

        ``fg.entities.delete`` is the **唯一合法整批撤销 path** for Identity
        Claims and Field Claims under the e_ref。 Legacy ``<EntityType>:exists``
        Claims,when present,are retracted through the same path-bound whole-
        entity revoke path。

        **PF-S2 discriminated signature**(per blueprint §6.1 SF2 lock):

        - Form A:``fg.entities.delete(e_ref: str, *, meta=None)`` — pass a
          managed e_ref string produced by ``fg.entities.ref(EC, **id)`` or
          ``fg.entities.create(EC, **id)``。
        - Form B:``fg.entities.delete(EntityCls, *, meta=None, **identity)`` —
          pass the EntityClass + full identity_kwargs。

        Tuple selectors are **explicitly forbidden**(per PF-S2 lock)。

        Implementation:per SF3 P1 amend,the SDK shell is a thin normalizer
        — it builds an ``EntityDeleteCommand`` and delegates to the application-
        layer planner/executor。 The retract guard bypass for Identity /
        ``:exists`` Claims is implemented as a **path-bound** structural
        guarantee in the application layer(``_apply_entity_delete_retract``
        private helper),NOT a metadata signal on ``PlannedOpDTO``。

        Returns:
            The number of Active Claims atomically retracted。

        Raises:
            ``SDKStoreError`` if the input shape does not match Form A or B,
            if Form A's e_ref is not managed(``UNRESOLVABLE_E_REF``),or if
            Form B's identity bundle is incomplete(``missing identity field``)。
            ``EntityNotFoundError``(``ENTITY_NOT_FOUND``)if the target
            entity is not visible in the active view。
        """
        # Form A vs Form B vs forbidden tuple — discriminate per PF-S2。
        if isinstance(e_ref_or_cls, str):
            # Form A: e_ref-based。 Reject extra identity kwargs(Form A 不
            # accepts identity since e_ref already encodes the bundle)。
            if identity:
                raise SDKStoreError(
                    "fg.entities.delete(e_ref: str) Form A does not accept "
                    "identity kwargs; pass either an e_ref string OR an "
                    "EntityClass + full identity bundle. See ADR-API §4.1.2."
                )
            e_ref = e_ref_or_cls
            shadow_identity = self._sdk._identity_values_by_e_ref.get(e_ref)
            if not isinstance(shadow_identity, dict) or not shadow_identity:
                raise SDKStoreError(
                    f"fg.entities.delete: e_ref is not managed by this SDKStore: "
                    f"{e_ref!r};call fg.entities.ref(...) or fg.entities.create(...) "
                    "first.",
                    code="UNRESOLVABLE_E_REF",
                )
            entity_type = entity_type_from_ref(e_ref)
            if not isinstance(entity_type, str) or not entity_type:
                raise SDKStoreError(
                    f"fg.entities.delete: e_ref is not a canonical idref_v1 "
                    f"token: {e_ref!r}.",
                    code="UNRESOLVABLE_E_REF",
                )
            normalized_entity_type = entity_type
            normalized_identity = dict(shadow_identity)
            normalized_e_ref = e_ref
        elif isinstance(e_ref_or_cls, type) and issubclass(e_ref_or_cls, Entity):
            # Form B: EntityClass + identity kwargs。
            normalized_entity_type = e_ref_or_cls.__name__
            # self._sdk._ref(...) validates identity bundle completeness + computes
            # deterministic e_ref + populates shadow store(legacy compat)。
            normalized_e_ref = self._sdk._ref(e_ref_or_cls, **identity)
            normalized_identity = dict(identity)
        else:
            # Forbidden:tuple selector or any other shape per PF-S2 lock。
            raise SDKStoreError(
                "fg.entities.delete requires e_ref string OR EntityClass + full "
                "identity bundle; see ADR-API §4.1.2. "
                f"got first positional arg of type {type(e_ref_or_cls).__name__}。"
            )

        # Build application command + delegate to planner/executor(per SF3
        # INV-6 — SDK is a thin shell,application layer is source of truth)。
        from factgraph.application import apply_delete_plan, plan_delete_command
        from factgraph.application.protocol import EntityDeleteCommand
        from factgraph.application.protocol import EntitySelector as AppEntitySelector

        command = EntityDeleteCommand(
            target=AppEntitySelector(
                entity_type=normalized_entity_type,
                identity=normalized_identity,
                encoded_ref=normalized_e_ref,
            ),
            command_meta=dict(meta) if meta else {},
        )
        plan = plan_delete_command(
            command,
            store=self._sdk._store,
            index=self._sdk._application_schema_index,
        )
        if not plan.can_apply:
            self._sdk._raise_from_application_error(plan.errors[0], op="delete")

        result = apply_delete_plan(
            plan,
            store=self._sdk._store,
            index=self._sdk._application_schema_index,
        )
        if result.errors:
            self._sdk._raise_from_application_error(result.errors[0], op="delete")

        return len(result.applied)

    def exists(self, entity_cls: type[Entity], **identity: Any) -> bool:
        """Return whether the entity is visible via active Identity Claims.

        ``self._sdk._ref`` supplies the Form I complete-identity validation and
        deterministic e_ref encoding while preserving the Slice 2 shadow-store
        compatibility behavior until the future eager-create-only migration.
        """
        self._reject_non_entity_class(entity_cls, method="exists")
        e_ref = self._sdk._ref(entity_cls, **identity)
        identity_values = self._sdk._identity_values_by_e_ref.get(e_ref, identity)
        return is_entity_identity_bundle_active(
            store=self._sdk._store,
            schema_index=self._sdk._application_schema_index,
            entity_type=entity_cls.__name__,
            e_ref=e_ref,
            identity_values=dict(identity_values),
        )

    def edit(self, entity_cls: type[Entity], **identity_kwargs: Any) -> Any:
        """Open an EntityEditor for an existing entity."""
        self._reject_non_entity_class(entity_cls, method="edit")
        self._sdk._reject_attached_write("fg.entities.edit")
        from .facade import sdk_edit

        return sdk_edit(self._sdk, entity_cls, **identity_kwargs)


class _SDKRulesManager:
    """Read-only namespace manager for rule structure inspection and persistence."""

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.rules namespace is read-only")

    def inspect(self, *args: Any, **kwargs: Any) -> Any:
        """Inspect a rule or inference without executing it.

        Returns structural metadata such as kind, branches, fallback branch
        ids, and body atom identifiers. This is a read-only view for debugging
        rule shape and branch semantics.
        """
        return self._sdk._inspect_rule(*args, **kwargs)

    def structure(self, *args: Any, **kwargs: Any) -> Any:
        """Return the RuleStructure static projection for a Rule or RuleExpr."""
        return self._sdk._structure_rule(*args, **kwargs)


class _SDKInferencesManager:
    """Read-only namespace manager for Inference (post-Q8 Phase 2: empty namespace).

    SavedInference persistence methods (``save`` / ``load`` / ``list`` / ``get``)
    were removed in Slice 6. ``fg.inferences`` attribute access is preserved
    for forward compatibility but exposes no public methods after Phase 2.
    Future in-memory inference inspection (parallel to ``fg.rules.inspect``) is
    a separate decision out of slice 6 scope.
    """

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.inferences namespace is read-only")


class _SDKEvalManager:
    """Read-only namespace manager for T5 evaluation and explanation."""

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.eval namespace is read-only")

    def evaluate(self, *args: Any, **kwargs: Any) -> Any:
        """Evaluate an `Inference`, application `Rule`, or RuleExpr."""
        return self._sdk._evaluate(*args, **kwargs)

    def evaluate_candidates(self, *args: Any, **kwargs: Any) -> Any:
        """Evaluate an Inference/derivation and return its raw CandidateSets.

        Read-only: candidates are hypothetical until accepted on a writing
        surface; this method never writes to the ledger.
        """
        return self._sdk._evaluate_candidates(*args, **kwargs)

    def explain(self, *args: Any, **kwargs: Any) -> Any:
        """Explain a closed-head evaluation replay."""
        return self._sdk._explain(*args, **kwargs)

    def preview_config(self, *args: Any, **kwargs: Any) -> Any:
        """Inspect semantics configuration without evaluating an inference.

        Accepts `SemanticsProfile`, `ProbLogConfig`, or `PyReasonConfig`
        and returns a JSON-like structural preview. Public wrappers include
        their lowered canonical profile preview.
        """
        return self._sdk._preview_config(*args, **kwargs)


class _SDKAuditManager:
    """Read-only namespace manager for the `audit` taxonomy group.

    Per §5.2 §5.2.1 placement #2, ``diff_proof_frames`` (G5) lives here
    because it consumes recorded round events and compares persisted
    proof-frame outcomes — post-hoc audit, not hypothetical evaluation.
    """

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.audit namespace is read-only")

    def _resolve_record_asrt_id(self, target: Any, *, method: str) -> str:
        if isinstance(target, str) and target:
            return target
        asrt_id = getattr(target, "asrt_id", None)
        if isinstance(asrt_id, str) and asrt_id:
            return asrt_id
        raise SDKStoreError(f"fg.audit.{method}(...) expects asrt_id string or AssertionRecord")

    def _claim_for_audit_target(self, target: Any, *, method: str) -> Claim:
        asrt_id = self._resolve_record_asrt_id(target, method=method)
        claim = self._sdk.ledger.get_claim(asrt_id)
        if claim is None:
            raise SDKStoreError(f"fg.audit.{method}(...) assertion id not found: {asrt_id!r}")
        return claim

    def _conflict_cell_for_target(self, target: Any) -> tuple[str, str]:
        if isinstance(target, tuple) and len(target) == 2:
            entity, field = target
            if isinstance(field, Field):
                schema_pred = self._sdk._schema_pred_for_field(field)
            elif isinstance(field, str) and field:
                e_ref_for_type = entity if isinstance(entity, str) else getattr(entity, "ref", None)
                if not isinstance(e_ref_for_type, str) or not e_ref_for_type:
                    raise SDKStoreError(
                        "fg.audit.conflicts((entity, field_name)) expects entity ref string or EntitySnapshot"
                    )
                entity_type = entity_type_from_ref(e_ref_for_type)
                pred_info = self._sdk._application_schema_index.field_predicates.get((entity_type, field))
                if pred_info is None:
                    raise SDKStoreError(f"schema predicate not found for {entity_type}.{field}")
                schema_pred = {
                    "pred_id": pred_info.pred_id,
                    "owner_type": pred_info.owner_type,
                    "py_field_name": pred_info.py_field_name,
                }
            else:
                raise SDKStoreError("fg.audit.conflicts((entity, field)) expects sdk.Field descriptor or field name")
            pred_id = schema_pred.get("pred_id")
            if not isinstance(pred_id, str) or not pred_id:
                raise SDKStoreError("schema predicate missing pred_id for field")
            e_ref = entity if isinstance(entity, str) else getattr(entity, "ref", None)
            if not isinstance(e_ref, str) or not e_ref:
                raise SDKStoreError("fg.audit.conflicts((entity, field)) expects entity ref string or EntitySnapshot")
            return pred_id, e_ref
        claim = self._claim_for_audit_target(target, method="conflicts")
        return claim.pred_id, claim.e_ref

    def explain(self, target: Any) -> Any:
        """Explain chosen-policy state for the assertion's predicate/entity cell."""
        claim = self._claim_for_audit_target(target, method="explain")
        val_atoms = tuple(value for _tag, value in claim.rest_terms)
        result = self._sdk._store.explain_fact(claim.pred_id, claim.e_ref, *val_atoms)
        result["asrt_id"] = claim.asrt_id
        result["chosen"] = result.get("chosen_asrt_id") == claim.asrt_id
        return result

    def conflicts(self, target: Any) -> Any:
        """Return conflict diagnostics for an assertion record or entity field cell."""
        pred_id, e_ref = self._conflict_cell_for_target(target)
        return self._sdk._store.conflicts(pred_id, e_ref)

    def diff_proof_frames(self, *args: Any, **kwargs: Any) -> Any:
        """Compare two recorded proof-frame outcomes."""
        return self._sdk._diff_proof_frames(*args, **kwargs)


class _SDKMetaManager:
    """Read-only namespace for runtime introspection.

    Currently exposes `capabilities()` reporting which value-kinds,
    scalar tags, and cardinalities the shipped runtime accepts. All
    values are mirrored from shipped constants — see
    `factgraph.application.capabilities`.
    """

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.meta namespace is read-only")

    def capabilities(self) -> Mapping[str, frozenset[str]]:
        from factgraph.application.capabilities import compute_capabilities

        return compute_capabilities()


class _SDKPackageManager:
    """Read-only namespace manager for the `package` taxonomy group."""

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.package namespace is read-only")

    def export_package(self, *args: Any, **kwargs: Any) -> Any:
        """Export a runnable package from the graph.

        Package export is separate from `fg.save_workspace(...)`: it creates an
        execution artifact, not a FactGraph workspace.
        """
        return self._sdk.export_package(*args, **kwargs)

    def run_package(self, *args: Any, **kwargs: Any) -> Any:
        """Run an exported package with the selected engine."""
        return self._sdk.run_package(*args, **kwargs)


_REGISTRY_ROOT_REMOVED_MESSAGE = (
    "registry_root= and registry= were removed by A20(E) / Q6-A. "
    "FactGraph workspace schema anchor lives at db/objects/schema/<digest>.json. "
    "Pass workspace path via `path=` only; avoid explicit registry_root= / registry=. "
    "Run `python -m factgraph migrate-workspace <path>` to migrate legacy workspaces."
)


def _raise_registry_root_removed() -> None:
    raise SDKStoreError(_REGISTRY_ROOT_REMOVED_MESSAGE)


def _normalize_workspace_path(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    if not isinstance(path, (str, Path)):
        raise SDKStoreError("path must be str | Path")
    return Path(path)


def _path_equivalent(left: str | Path, right: str | Path) -> bool:
    return Path(left).expanduser().resolve(strict=False) == Path(right).expanduser().resolve(strict=False)


def _resolve_workspace_constructor_paths(
    *,
    path: str | Path | None,
    ledger_path: str | None,
) -> tuple[Path | None, str | None]:
    workspace_path = _normalize_workspace_path(path)
    if workspace_path is None:
        return None, ledger_path

    workspace_paths = resolve_workspace_paths(workspace_path)
    expected_ledger = workspace_paths.ledger

    if ledger_path is not None:
        if not _path_equivalent(ledger_path, expected_ledger):
            raise SDKStoreError("ledger_path conflicts with workspace path")
        resolved_ledger_path = ledger_path
    else:
        resolved_ledger_path = str(expected_ledger)

    return workspace_path, resolved_ledger_path


def _reject_legacy_registry_marker(workspace_path: str | Path) -> None:
    workspace_paths = resolve_workspace_paths(workspace_path)
    legacy_registry = workspace_paths.root / "registry"
    if legacy_registry.exists():
        raise SDKStoreError(
            f"workspace contains legacy registry/ marker (path={legacy_registry}); "
            "run `python -m factgraph migrate-workspace <workspace>` "
            "before loading."
        )


def _entity_type_for_schema_class(value: Any, *, field_name: str) -> str:
    if not isinstance(value, type) or not issubclass(value, Entity) or value is Entity:
        raise SDKStoreError(f"{field_name} must be Entity subclass")
    spec = value.sdk_entity_spec()
    entity_type = spec.get("entity_type")
    if not isinstance(entity_type, str) or not entity_type:
        raise SDKStoreError(f"{field_name}.entity_type must be non-empty string")
    return entity_type


def _schema_non_additive_message(exc: SDKStoreError) -> str:
    return (
        f"schema mutation is non-additive: {exc}. "
        "Identity bundle redesign requires entity-type migration for Identity "
        "changes; <EntityType>:exists is structurally immutable while the "
        "transitional existence guard is active. See ADR-IC §4.3.6."
    )


def _ensure_workspace_schema_object(path: str | Path, schema_ir: dict[str, Any]) -> None:
    expected_digest = schema_digest(schema_ir)
    if schema_object_exists_for_workspace(path, expected_digest):
        try:
            validate_schema_object_for_workspace(path, schema_ir)
        except DatabaseError as exc:
            raise SDKStoreError(f"workspace schema object invalid: {exc}") from exc
        return
    raise SDKStoreError("workspace schema object missing")


class SDKStore:
    """Main SDK graph object, exported to users as `FactGraph`.

    `FactGraph` is a literal alias of this class and is the recommended public
    name. It owns the compiled schema, append-only ledger, optional authoring
    registry, optional workspace path, and user-facing namespaces such as
    `schema`, `read`, `write`, `rules`, `inferences`, `eval`, `audit`,
    `package`, and `assertion_views`.

    `FactGraph.attach(db, schema_classes=...)` is the Database-owned lifecycle
    for new DB/view substrate work. Attached runtimes expose
    `fg.commit_assertions(...)` for Database-routed writes; shipped
    `create` / `from_schema_classes` / `load_workspace` constructors remain available as
    compatibility lifecycles.
    """

    def __init__(
        self,
        classes: list[type[Entity]],
        *,
        store: Store | None = None,
        schema_ir: dict | None = None,
        artifact_store_root: str | None = None,
        registry_root: str | Path | None = None,
        registry: Any | None = None,
        workspace_path: str | Path | None = None,
        default_row_format: str | None = None,
    ) -> None:
        # Q6-A (e.1): registry_root= and registry= are kept in the signature
        # for one-version grace, but raise immediately when provided.
        if registry_root is not None or registry is not None:
            _raise_registry_root_removed()
        if not isinstance(classes, list) or not classes:
            raise SDKStoreError("classes must be non-empty list[Entity]")
        self._classes = list(classes)
        for index, cls in enumerate(self._classes):
            if not isinstance(cls, type) or not issubclass(cls, Entity):
                raise SDKStoreError(f"classes[{index}] must be Entity subclass")

        if store is not None and schema_ir is not None and store.schema_ir is not schema_ir:
            raise SDKStoreError("provide either store or schema_ir (or matching store.schema_ir)")
        if store is not None:
            self._store = store
        else:
            _sidecar = FileArtifactSidecar(artifact_store_root) if artifact_store_root is not None else None
            self._store = Store(
                schema_ir=schema_ir or compile_schema_from_classes(self._classes),
                artifact_sidecar=_sidecar,
            )
        self._schema_ir = self._store.schema_ir
        self._schema_digest = schema_digest(self._schema_ir)
        self._workspace_path = _normalize_workspace_path(workspace_path)
        self._database: Database | None = None
        self._attached_writable = False
        self._application_schema_index = build_schema_index(self._schema_ir)
        self._field_pred_by_descriptor: dict[Field, dict[str, Any]] = {}
        self._field_decl_by_descriptor: dict[Field, dict[str, Any]] = {}
        self._entity_spec_by_class: dict[type[Entity], dict[str, Any]] = {}
        # _identity_values_by_e_ref: LEGACY / INTERNAL COMPATIBILITY only.
        # Per ADR-IC §4.2.3, the SDK shell shadow store is NOT part of the
        # Layer 2 fields API contract; it exists as a compatibility detail to
        # let `fg.fields.set(Field, e_ref_string, value)` succeed when the shadow store
        # has previously seen this e_ref (via a prior `fg.entities.ref()` call).
        # - e_ref NOT in shadow store → fail-fast UNRESOLVABLE_E_REF
        #   (per ADR-IC §4.2.1 emission input contract; raised at
        #   `_apply_field_mutation` target check + `_build_application_write_value`
        #   entity_ref value check).
        # - e_ref in shadow store → lazy materialization through
        #   `_materialization_ops` (legacy compat path that auto-emits Identity
        #   Claims + `:exists` on first Field write).
        # Step 2+ direction (per ADR-IC §4.2.4): eager emission at
        # `fg.entities.create(...)` + shadow store removal. Slice 2 does NOT
        # remove the shadow store (Slice 3a ADR-API Q10 namespace migration
        # carry-forward; compatibility preservation in Slice 2).
        self._identity_values_by_e_ref: dict[str, dict[str, Any]] = {}
        self._assertion_views_manager = _SDKAssertionViewsManager(self)
        self._assertions_manager = AssertionsManager(self)
        self._schema_manager = _SDKSchemaManager(self)
        self._entities_manager = _SDKEntitiesManager(self)
        self._fields_manager = _SDKFieldsManager(self)
        self._rules_manager = _SDKRulesManager(self)
        self._inferences_manager = _SDKInferencesManager(self)
        self._eval_manager = _SDKEvalManager(self)
        self._audit_manager = _SDKAuditManager(self)
        self._meta_manager = _SDKMetaManager(self)
        self._package_manager = _SDKPackageManager(self)
        self._default_row_format = default_row_format
        # Read once at init time; do not re-read env on each run().
        self._env_row_format = os.environ.get("FACTPY_ROW_FORMAT")
        self._index_schema()

    def __repr__(self) -> str:
        return f"SDKStore(entities={len(self._classes)}, schema={self._schema_digest!r})"

    def _is_attached(self) -> bool:
        return self._database is not None

    def _reject_attached_write(self, method_name: str) -> None:
        if self._is_attached():
            raise SDKStoreError(_ATTACHED_WRITE_ERROR.format(method_name=method_name))

    @classmethod
    def create(
        cls,
        schema_classes: list[type[Entity]],
        *,
        ledger: Ledger | None = None,
        ledger_path: str | None = None,
        path: str | Path | None = None,
        artifact_store_root: str | None = None,
        registry_root: str | Path | None = None,
        registry: Any | None = None,
        default_row_format: str | None = None,
    ) -> "SDKStore":
        """Create a `FactGraph` from Python `Entity` classes.

        This is the normal SDK constructor. Pass `path=` when the graph should
        own a durable workspace that can later be saved with
        `fg.save_workspace()` and restored with `FactGraph.load_workspace(...)`.

        Args:
            schema_classes: Non-empty list of `Entity` subclasses.
            ledger: Optional existing ledger object.
            ledger_path: Optional SQLite ledger path; mutually exclusive with
                `ledger`.
            path: Optional workspace directory.
            artifact_store_root: Optional artifact sidecar root.
            registry_root: REMOVED by A20(E) / Q6-A; raises `SDKStoreError`
                immediately if provided. Pass workspace path via `path=` only.
            registry: REMOVED by A20(E) / Q6-A; raises `SDKStoreError`
                immediately if provided.
            default_row_format: Optional default output row format for rule
                evaluation.

        Returns:
            A `FactGraph` / `SDKStore` bound to the compiled schema.

        Raises:
            SDKStoreError: If `registry_root=` or `registry=` is provided, or
                if constructor paths or schema classes are invalid.
        """
        # Q6-A (e.1): explicit reject before any workspace path resolution so
        # users get the migration message without ambiguous downstream errors.
        if registry_root is not None or registry is not None:
            _raise_registry_root_removed()
        workspace_path, resolved_ledger_path = _resolve_workspace_constructor_paths(
            path=path,
            ledger_path=ledger_path,
        )
        schema_ir = compile_schema_from_classes(schema_classes)
        if workspace_path is not None:
            try:
                write_schema_object_for_workspace(workspace_path, schema_ir)
            except DatabaseError as exc:
                raise SDKStoreError(f"workspace schema object write failed: {exc}") from exc
        return cls._from_schema_classes_impl(
            schema_classes,
            ledger=ledger,
            ledger_path=resolved_ledger_path,
            artifact_store_root=artifact_store_root,
            schema_ir=schema_ir,
            workspace_path=workspace_path,
            default_row_format=default_row_format,
        )

    @classmethod
    def from_schema_classes(
        cls,
        classes: list[type[Entity]],
        *,
        ledger: Ledger | None = None,
        ledger_path: str | None = None,
        artifact_store_root: str | None = None,
        registry_root: str | Path | None = None,
        registry: Any | None = None,
        default_row_format: str | None = None,
    ) -> "SDKStore":
        # Q6-A (e.1): same rejection as create(...).
        if registry_root is not None or registry is not None:
            _raise_registry_root_removed()
        return cls._from_schema_classes_impl(
            classes,
            ledger=ledger,
            ledger_path=ledger_path,
            artifact_store_root=artifact_store_root,
            workspace_path=None,
            default_row_format=default_row_format,
        )

    @classmethod
    def load_workspace(
        cls,
        path: str | Path,
        *,
        schema_classes: list[type[Entity]] | None = None,
        default_row_format: str | None = None,
    ) -> "SDKStore":
        """Load a saved FactGraph workspace from disk.

        Workspace load restores the ledger and validates the workspace schema
        digest against the supplied `schema_classes`. Class-less dynamic load
        is not supported. Legacy workspaces still carrying a `registry/`
        directory must first be migrated via
        ``python -m factgraph migrate-workspace <path>``.

        Args:
            path: Workspace directory created by `fg.save_workspace(...)`.
            schema_classes: Entity classes matching the saved workspace schema.
            default_row_format: Optional default output row format.

        Raises:
            SDKStoreError: If the workspace contains a legacy `registry/`
                marker (Q6-A (d.3): run the migration CLI first), or if the
                schema digest does not match.
        """
        if schema_classes is None:
            raise SDKStoreError("schema_classes is required for FactGraph.load_workspace(...)")
        schema_ir = compile_schema_from_classes(schema_classes)
        digest = schema_digest(schema_ir)
        try:
            _reject_legacy_registry_marker(path)
            paths = app_load_workspace(path, schema_digest=digest)
            _ensure_workspace_schema_object(paths.root, schema_ir)
            return cls._from_schema_classes_impl(
                schema_classes,
                ledger=Ledger(path=paths.ledger),
                schema_ir=schema_ir,
                workspace_path=paths.root,
                default_row_format=default_row_format,
            )
        except Exception as exc:
            if isinstance(exc, SDKStoreError):
                raise
            raise SDKStoreError(str(exc)) from exc

    @classmethod
    def attach(
        cls,
        db: Database,
        *,
        schema_classes: list[type[Entity]],
        view: DatabaseFrozenAssertionSet | None = None,
        default_row_format: str | None = None,
        **kwargs: Any,
    ) -> "SDKStore":
        if not isinstance(db, Database):
            raise SDKStoreError("FactGraph.attach(db) expects a Database instance")
        if kwargs:
            rejected = sorted(_ATTACH_REJECTED_KWARGS.intersection(kwargs))
            unknown = sorted(set(kwargs) - _ATTACH_REJECTED_KWARGS)
            raise SDKStoreError(
                "FactGraph.attach(...) does not accept keyword(s): "
                + ", ".join(rejected + unknown)
            )

        schema_ir = compile_schema_from_classes(schema_classes)
        digest = schema_digest(schema_ir)
        if digest != db.schema_digest:
            raise SDKStoreError(
                f"schema mismatch: Database has schema_digest={db.schema_digest!r}, "
                f"but schema_classes compile to {digest!r}"
            )
        ledger = db._ledger_for_attach()
        attached_writable = True
        if view is not None:
            ledger = _ledger_for_durable_database_view(db, view)
            attached_writable = False

        store = Store(schema_ir=schema_ir, ledger=ledger)
        attached = cls(schema_classes, store=store, default_row_format=default_row_format)
        attached._database = db
        attached._attached_writable = attached_writable
        return attached

    @classmethod
    def _from_schema_classes_impl(
        cls,
        classes: list[type[Entity]],
        *,
        ledger: Ledger | None = None,
        ledger_path: str | None = None,
        artifact_store_root: str | None = None,
        schema_ir: dict[str, Any] | None = None,
        workspace_path: str | Path | None = None,
        default_row_format: str | None = None,
    ) -> "SDKStore":
        if ledger is not None and ledger_path is not None:
            raise SDKStoreError("provide either ledger or ledger_path, not both")

        if schema_ir is None:
            schema_ir = compile_schema_from_classes(classes)
        digest = schema_digest(schema_ir)

        if ledger_path is not None:
            ledger = Ledger(path=ledger_path)

        if ledger is not None:
            stored_digest = ledger.get_ledger_meta("schema_digest")
            if stored_digest is None:
                ledger.set_ledger_meta("schema_digest", digest)
            elif stored_digest != digest:
                raise SDKStoreError(
                    f"schema mismatch: ledger file was written with schema_digest={stored_digest!r}, "
                    f"but current schema has digest={digest!r}. "
                    "Use the same Entity classes that were used when this ledger was created."
                )

        _sidecar = FileArtifactSidecar(artifact_store_root) if artifact_store_root is not None else None
        return cls(
            classes,
            store=Store(schema_ir=schema_ir, ledger=ledger, artifact_sidecar=_sidecar),
            workspace_path=workspace_path,
            default_row_format=default_row_format,
        )

    @property
    def store(self) -> Store:
        return self._store

    @property
    def ledger(self) -> Ledger:
        return self._store.ledger

    @property
    def premise_exclusions(self) -> tuple[MetaExclusion, ...]:
        """Configured meta-based premise admissibility exclusions (empty = disabled)."""
        return self._store.premise_exclusions

    def set_premise_exclusions(
        self,
        exclusions: MetaExclusion | Iterable[MetaExclusion] | None,
    ) -> None:
        """Configure meta-based premise admissibility exclusions for evaluation.

        Assertions whose meta rows carry one of the configured key/value
        pairs become invisible to every rule evaluation (all engine modes,
        proof-frame recheck, derivation check): they can neither support a
        derivation nor block one through negation. Read/query paths outside
        evaluation (entity views, assertion listings, audit, history) stay
        unfiltered — the assertions remain fully visible there. Key and
        values are pure configuration; passing ``None`` or an empty iterable
        disables filtering (zero-behavior-change default). See
        ``factgraph/core/store/premise_filter.py``.
        """
        try:
            self._store.set_premise_exclusions(exclusions)
        except ValueError as exc:
            raise SDKStoreError(str(exc)) from exc

    @property
    def premise_allowances(self) -> tuple[PredicatePremiseAllowance, ...]:
        """Configured per-predicate premise admissibility allowances (empty = disabled)."""
        return self._store.premise_allowances

    def set_premise_allowances(
        self,
        allowances: PredicatePremiseAllowance | Iterable[PredicatePremiseAllowance] | None,
    ) -> None:
        """Configure per-predicate premise admissibility allowances for evaluation.

        For each configured predicate, an assertion of that predicate is
        visible to every rule evaluation (all engine modes, proof-frame
        recheck, derivation check) only when its meta ``key`` last-value is in
        the predicate's ``allowed_values``; an assertion of that predicate
        missing the key is admitted only when ``absent_ok`` is set. Predicates
        without an entry are unaffected. This is OR-combined with
        ``set_premise_exclusions``: an assertion excluded by either dimension is
        invisible, so the global exclusion floor is never lifted. Read/query
        paths outside evaluation stay unfiltered. Predicate, key and values are
        pure configuration; passing ``None`` or an empty iterable disables
        per-predicate filtering. See ``factgraph/core/store/premise_filter.py``.
        """
        try:
            self._store.set_premise_allowances(allowances)
        except ValueError as exc:
            raise SDKStoreError(str(exc)) from exc

    @property
    def schema_ir(self) -> dict[str, Any]:
        return self._schema_ir

    @property
    def assertion_views(self) -> _SDKAssertionViewsManager:
        return self._assertion_views_manager

    @property
    def assertions(self) -> AssertionsManager:
        return self._assertions_manager

    @property
    def schema(self) -> _SDKSchemaManager:
        """`schema` taxonomy namespace (post-L redesign §5.2 lock).

        Read-only manager exposing ``ingest`` and ``validate_provenance``.
        Delegates to flat ``SDKStore.<method>`` per §5.4 Option 2 lock.
        """
        return self._schema_manager

    @property
    def entities(self) -> _SDKEntitiesManager:
        """`entities` Layer 1 namespace per ADR-API §4.1。

        Slice 3a Step 7 owns Layer 1 user-facing entity operations after
        removing the historical ``fg.read.*`` namespace and flat shortcuts。
        """
        return self._entities_manager

    @property
    def fields(self) -> _SDKFieldsManager:
        """`fields` Layer 2 namespace per ADR-API §4.1。

        Slice 3a Step 7 owns Layer 2 user-facing field-cell operations after
        removing the historical ``fg.write.*`` namespace and flat shortcuts。
        """
        return self._fields_manager

    @property
    def rules(self) -> _SDKRulesManager:
        """`rules` taxonomy namespace exposing pure rule/derivation structure inspection."""
        return self._rules_manager

    @property
    def inferences(self) -> _SDKInferencesManager:
        """`inferences` taxonomy namespace exposing persisted Inference asset handles."""
        return self._inferences_manager

    @property
    def eval(self) -> _SDKEvalManager:
        """`eval` taxonomy namespace exposing T5 evaluate/explain APIs."""
        return self._eval_manager

    @property
    def audit(self) -> _SDKAuditManager:
        """`audit` taxonomy namespace exposing ``explain`` / ``conflicts`` / ``diff_proof_frames``."""
        return self._audit_manager

    @property
    def meta(self) -> _SDKMetaManager:
        """`meta` namespace exposing read-only runtime introspection (`capabilities()`)."""
        return self._meta_manager

    @property
    def package(self) -> _SDKPackageManager:
        """`package` taxonomy namespace exposing ``export_package`` / ``run_package``."""
        return self._package_manager

    def commit_assertions(self, assertions: Sequence[AssertionInput]) -> CommitResult:
        if self._database is None:
            raise SDKStoreError(
                "fg.commit_assertions(...) is only available on FactGraph.attach(db) runtimes; "
                "use fg.fields.set / fg.fields.add for non-attached SDKStores"
            )
        if not self._attached_writable:
            raise SDKStoreError(
                "fg.commit_assertions(...) is not available on FactGraph.attach(db, view=view) runtimes; "
                "view-attached runtimes are read-only"
            )
        return self._database.commit_assertions(assertions)

    def batch(self, *, meta: dict[str, Any] | None = None):
        self._reject_attached_write("fg.batch")
        from .batch import SDKBatchTx

        return SDKBatchTx(self, meta=meta)

    def _ingest(
        self,
        data: Any,
        *,
        meta: dict[str, Any] | None = None,
        allow_sensitive_meta: bool = False,
    ):
        self._reject_attached_write("fg.ingest")
        from .ingest import sdk_ingest

        return sdk_ingest(self, data, meta=meta, allow_sensitive_meta=allow_sensitive_meta)

    def _validate_provenance(self, obj: Any, *, standard: str = "derivation_v1"):
        from .ingest import sdk_validate_provenance

        return sdk_validate_provenance(self, obj, standard=standard)

    def add_schema_classes(
        self,
        *schema_class_args: type[Entity],
        schema_classes: list[type[Entity]] | None = None,
    ) -> SchemaAddResult:
        self._reject_attached_write("fg.add_schema_classes")
        if schema_class_args and schema_classes is not None:
            raise SDKStoreError("pass either positional schema classes or schema_classes=, not both")
        if schema_classes is None:
            if len(schema_class_args) == 1:
                additions = [schema_class_args[0]]
            else:
                additions = list(schema_class_args)
        else:
            additions = schema_classes
        if len(additions) == 1:
            entity_type = _entity_type_for_schema_class(additions[0], field_name="schema_classes[0]")
            op = "extend" if entity_type in self._entity_types_by_class_registry() else "register"
            error_type = SchemaNonAdditiveError if op == "extend" else SchemaConflictError
            return self._apply_schema_class_update(
                additions[0],
                operation=op,
                non_additive_error_type=error_type,
            )

        return self._apply_schema_class_batch(additions, operation="add_schema_classes")

    def _apply_schema_class_update(
        self,
        entity_cls: type[Entity],
        *,
        operation: str,
        non_additive_error_type: type[SDKStoreError],
    ) -> SchemaAddResult:
        _entity_type_for_schema_class(entity_cls, field_name="entity_cls")
        self._reject_attached_write(f"fg.schema.{operation}")
        try:
            return self._apply_schema_class_batch(
                [entity_cls],
                operation=operation,
                non_additive_error_type=non_additive_error_type,
            )
        except non_additive_error_type:
            raise
        except SDKStoreError as exc:
            raise non_additive_error_type(
                _schema_non_additive_message(exc),
                code="SCHEMA_NON_ADDITIVE" if non_additive_error_type is SchemaNonAdditiveError else "SCHEMA_CONFLICT",
            ) from exc

    def _apply_schema_class_batch(
        self,
        additions: list[type[Entity]],
        *,
        operation: str,
        non_additive_error_type: type[SDKStoreError] = SDKStoreError,
    ) -> SchemaAddResult:
        old_digest = self._schema_digest
        try:
            result = app_add_schema_classes(
                current_classes=self._classes,
                schema_classes=additions,
            )
        except SDKStoreError as exc:
            if non_additive_error_type is SDKStoreError:
                raise
            raise non_additive_error_type(
                _schema_non_additive_message(exc),
                code="SCHEMA_NON_ADDITIVE" if non_additive_error_type is SchemaNonAdditiveError else "SCHEMA_CONFLICT",
            ) from exc
        if (
            result.schema_digest == old_digest
            and not result.added_entities
            and not result.added_fields
        ):
            return SchemaAddResult(
                old_digest=old_digest,
                new_digest=old_digest,
                added_entities=[],
                added_fields=[],
            )

        self._preflight_schema_digest_anchors(old_digest)
        self._refresh_schema_state(
            classes=result.classes,
            schema_ir=result.schema_ir,
            schema_digest_value=result.schema_digest,
        )
        self._update_schema_digest_anchors(
            schema_ir=result.schema_ir,
            schema_digest_value=result.schema_digest,
        )
        return SchemaAddResult(
            old_digest=old_digest,
            new_digest=result.schema_digest,
            added_entities=list(result.added_entities),
            added_fields=list(result.added_fields),
        )

    def _entity_types_by_class_registry(self) -> dict[str, type[Entity]]:
        return {
            _entity_type_for_schema_class(cls, field_name="classes[*]"): cls
            for cls in self._classes
        }

    def _diff_proof_frames(
        self,
        round_a_id: Any,
        round_b_id: Any,
        round_a_events: Any,
        round_b_events: Any,
        *,
        warnings: Any = (),
        include_unchanged: bool = False,
    ) -> "ProofFrameDiff":
        """Diff two rounds' proof-frame events.

        Args:
            round_a_id: Non-empty string identifying the A-side round.
            round_b_id: Non-empty string identifying the B-side round.
            round_a_events: Raw ``tuple[RoundEvent, ...]`` from
                ``factgraph.audit.round_events`` (e.g., loaded via
                ``factgraph.audit.load_audit_package`` or held from a
                fresh recorder). Per §5.3 lock the SDK never wraps
                ``RoundEvent`` and never reads files internally.
            round_b_events: Raw ``tuple[RoundEvent, ...]`` for the
                B-side round.
            warnings: Optional ``tuple[WarningDTO, ...]``; defaults to
                empty tuple.
            include_unchanged: Whether to emit deltas for unchanged
                frames; mirrors the A-side parameter at
                ``factgraph.audit.proof_frame_diff.build_proof_frame_diff``.

        Returns:
            The application-canonical ``ProofFrameDiff`` DTO directly.
            The runtime represents helper-internal validation failures
            (malformed payloads, duplicate frame identity) as
            ``ProofFrameDiffError`` exceptions which the SDK shell
            remaps to ``$.diff_proof_frames.request`` per §5.8 lock.

        Raises:
            SDKStoreError: For non-SDK exceptions crossing the SDK
                boundary. The ``path`` field locates the failure:
                ``$.diff_proof_frames.round_a_id`` for non-string /
                empty ``round_a_id``;
                ``$.diff_proof_frames.round_b_id`` for non-string /
                empty ``round_b_id``;
                ``$.diff_proof_frames.round_a_events`` for non-tuple
                or non-``RoundEvent`` element in ``round_a_events``;
                ``$.diff_proof_frames.round_b_events`` for non-tuple
                or non-``RoundEvent`` element in ``round_b_events``;
                ``$.diff_proof_frames.warnings`` for non-tuple or
                non-``WarningDTO`` element in ``warnings``;
                ``$.diff_proof_frames.include_unchanged`` for
                non-``bool`` ``include_unchanged``;
                ``$.diff_proof_frames.request`` for ``ProofFrameDiffError``
                from helper-internal validation (malformed event
                payloads, duplicate frame identity, etc.); and
                ``$.diff_proof_frames`` for unexpected runtime
                exceptions. Original exceptions are preserved as
                ``__cause__``.

        Notes:
            Recorder lifecycle is intentionally NOT a SDK shell per
            G5 §5.1 — capture stays at advanced-importable
            ``factgraph.audit.round_events`` (``start_round`` /
            ``record_round_event`` / ``finalize_round``); G5 ships
            only the pure query side (this method).
        """
        from .shells.proof_frame_diff import sdk_diff_proof_frames

        return sdk_diff_proof_frames(
            self,
            round_a_id,
            round_b_id,
            round_a_events,
            round_b_events,
            warnings=warnings,
            include_unchanged=include_unchanged,
        )

    def _ref(self, entity_cls: type[Entity], **identity_values: Any) -> str:
        """Return a managed e_ref string for the entity identified by kwargs.

        Records the supplied identity into this SDKStore's local cache so
        that ``fg.fields.set`` / ``fg.fields.add`` can later resolve the e_ref into a
        full ``EntitySelector`` for the application write-plan. Does NOT
        write to the ledger; ``ref`` is only an in-memory registration.

        Args:
            entity_cls: An ``Entity`` subclass passed to this SDKStore in
                the ``classes=[...]`` constructor arg.
            **identity_values: Identity field values. All declared identity
                fields must be supplied explicitly.

        Returns:
            A canonical ``idref_v1:<entity_type>:<digest>`` token. The same
            identity inputs always produce the same e_ref (deterministic
            encoding).

        Raises:
            SDKStoreError: if ``entity_cls`` was not registered with this
                SDKStore, if extra identity kwargs are passed, or if a
                required identity field has no value.
        """
        spec = self._entity_spec_by_class.get(entity_cls)
        if spec is None:
            self._raise_if_superseded_entity_class(entity_cls)
            raise SDKStoreError(f"unknown Entity class: {getattr(entity_cls, '__name__', entity_cls)!r}")

        expected_names = {field["name"] for field in spec["identity_fields"]}
        extra_keys = sorted(set(identity_values.keys()) - expected_names)
        if extra_keys:
            raise SDKStoreError(f"unknown identity fields for {entity_cls.__name__}: {extra_keys}")

        tuples: list[tuple[str, str, Any]] = []
        for field in spec["identity_fields"]:
            name = field["name"]
            tag = field["type_domain"]
            if name in identity_values:
                raw_value = identity_values[name]
            else:
                raise SDKStoreError(f"missing identity field: {entity_cls.__name__}.{name}")
            tuples.append((name, tag, _coerce_sdk_value_to_tag(tag, raw_value)))
        e_ref = encode_idref_v1(spec["entity_type"], tuples)
        self._identity_values_by_e_ref[e_ref] = {name: value for name, _, value in tuples}
        return e_ref

    def _apply_field_mutation(
        self,
        *,
        op: str,
        field: Field,
        e_ref: str,
        value: Any,
        meta: dict[str, Any] | None,
    ) -> str:
        pred = self._schema_pred_for_field(field)
        owner_type = pred.get("owner_type")
        if not isinstance(owner_type, str) or not owner_type:
            raise SDKStoreError(f"field has no owner_type: {pred.get('pred_id')!r}")
        field_name = pred.get("py_field_name")
        if not isinstance(field_name, str) or not field_name:
            raise SDKStoreError(f"field has no py_field_name: {pred.get('pred_id')!r}")

        target_identity = self._identity_values_by_e_ref.get(e_ref)
        if not isinstance(target_identity, dict) or not target_identity:
            raise SDKStoreError(
                f"e_ref is not managed by this SDKStore: {e_ref!r}; "
                f"call fg.entities.ref({owner_type}, **identity_kwargs) to obtain a managed e_ref",
                code="UNRESOLVABLE_E_REF",
            )

        write_value = self._build_application_write_value(pred=pred, value=value)

        command = EntityWriteCommand(
            target=AppEntitySelector(
                entity_type=owner_type,
                identity=dict(target_identity),
            ),
            mutations=(
                FieldMutation(
                    op=op,
                    field=FieldPath(entity_type=owner_type, field_name=field_name),
                    value=write_value,
                    meta=dict(meta) if meta else {},
                ),
            ),
            create_if_missing=True,
            include_dependencies=True,
        )

        plan = plan_write_command(command, store=self._store, index=self._application_schema_index)
        if not plan.can_apply:
            self._raise_from_application_error(plan.errors[0], op=op)

        result = apply_write_plan(plan, store=self._store, index=self._application_schema_index)
        if result.errors:
            self._raise_from_application_error(result.errors[0], op=op)

        if not result.applied:
            raise SDKStoreError(f"{op} produced no applied operations")
        last = result.applied[-1]
        if last.assertion_id is None:
            raise SDKStoreError(f"{op} returned no assertion id")
        return last.assertion_id

    def _build_application_write_value(self, *, pred: dict[str, Any], value: Any) -> Any:
        arg_specs = pred.get("arg_specs", [])
        if not isinstance(arg_specs, list) or len(arg_specs) < 2:
            raise SDKStoreError("schema predicate arg_specs invalid")
        value_spec = arg_specs[1] if isinstance(arg_specs[1], dict) else {}
        value_tag = value_spec.get("type_domain")

        if value_tag == "entity_ref":
            if not isinstance(value, str):
                raise SDKStoreError(f"entity_ref field expects e_ref string, got {type(value).__name__}")
            value_entity_type = entity_type_from_ref(value)
            if not isinstance(value_entity_type, str) or not value_entity_type:
                raise SDKStoreError(f"entity_ref value is not a canonical idref_v1 token: {value!r}")
            value_identity = self._identity_values_by_e_ref.get(value)
            if not isinstance(value_identity, dict) or not value_identity:
                raise SDKStoreError(
                    f"value e_ref is not managed by this SDKStore: {value!r}; "
                    f"call fg.entities.ref({value_entity_type}, **identity_kwargs) for the value entity first",
                    code="UNRESOLVABLE_E_REF",
                )
            return AppEntityRef(
                entity_type=value_entity_type,
                identity=dict(value_identity),
                encoded_ref=value,
            )

        return _coerce_sdk_value_to_tag(value_tag or "", value)

    def _raise_from_application_error(self, err: ErrorDTO, *, op: str) -> None:
        if err.code == "FIELD_CARDINALITY_MISMATCH":
            raise CardinalityError(
                err.message,
                field_name=err.details.get("field_name"),
                actual_cardinality=err.details.get("cardinality"),
                operation=op,
                code=err.code,
            )
        if err.code == "ENTITY_NOT_FOUND":
            raise EntityNotFoundError(
                err.message,
                entity_type=err.details.get("entity_type"),
                code=err.code,
            )
        if err.code == "FIELD_VALUE_VALIDATION_FAILED":
            path = ".".join(err.path) if err.path else None
            raise SDKValueError(err.message, code=err.code, path=path)
        raise SDKStoreError(err.message, code=err.code)

    def _reject_removed_read_policy(self, policy: Any, *, api_path: str) -> None:
        if policy is _POLICY_TOMBSTONE:
            return
        raise SDKStoreError(f"{api_path}: {_READPOLICY_REMOVED_MESSAGE}")

    def _preview_config(self, profile: Any) -> dict[str, Any]:
        if isinstance(profile, SemanticsProfile):
            return inspect_semantics_profile(profile)
        if isinstance(profile, (ProbLogConfig, PyReasonConfig)):
            lowered = _preview_public_semantics(profile)
            inspected = inspect_semantics_profile(lowered)
            inspected["semantics_type"] = type(profile).__name__
            inspected["lowered_profile"] = _semantics_profile_preview(lowered)
            return inspected
        raise SDKStoreError("preview_config(profile) expects SemanticsProfile or SDK public semantics")

    def _inspect_rule(self, obj: Any) -> Any:
        from factgraph.application.protocol import Rule as ApplicationRule
        from factgraph.application.protocol.rule_expr import _RuleExpr
        from factgraph.application.protocol.rule_expr_inspect import _inspect_application_rule, _inspect_rule_expr

        if isinstance(obj, ApplicationRule):
            return _inspect_application_rule(obj, schema_index=self._application_schema_index)
        if isinstance(obj, _RuleExpr):
            return _inspect_rule_expr(obj)
        return _inspect_rule_or_inference(obj)

    def _structure_rule(self, obj: Any, **kwargs: Any) -> Any:
        from factgraph.application.protocol import Rule as ApplicationRule
        from factgraph.application.protocol.rule import _is_projection_rule
        from factgraph.application.protocol.rule_expr import _RuleExpr, _coerce_rule_expr_operand
        from factgraph.application.protocol.rule_expr_lowering import _lower_application_rule, _lower_rule_expr
        from factgraph.application.rule_structure import assemble_static_structure

        if isinstance(obj, ApplicationRule):
            if kwargs:
                unknown = ", ".join(sorted(kwargs))
                raise SDKStoreError(f"rules.structure(rule) got unknown keyword(s): {unknown}")
            source_expr = (
                _coerce_rule_expr_operand(obj.as_("head"))
                if _is_projection_rule(obj)
                else _coerce_rule_expr_operand(obj)
            )
            plan = _lower_rule_expr(source_expr, head=obj) if _is_projection_rule(obj) else _lower_application_rule(obj, head=obj)
            return assemble_static_structure(plan, schema_index=self._application_schema_index, rule_expr=source_expr)
        if isinstance(obj, _RuleExpr):
            head = kwargs.pop("head", None)
            if kwargs:
                unknown = ", ".join(sorted(kwargs))
                raise SDKStoreError(f"rules.structure(rule_expr, ...) got unknown keyword(s): {unknown}")
            if not isinstance(head, ApplicationRule):
                raise SDKStoreError("rules.structure(rule_expr, ...) requires head= Rule")
            plan = _lower_rule_expr(obj, head=head)
            return assemble_static_structure(plan, schema_index=self._application_schema_index, rule_expr=obj)
        raise SDKStoreError("rules.structure(...) expects application Rule or RuleExpr input")

    def save_workspace(self, path: str | Path | None = None) -> dict[str, Any]:
        """Persist this graph as a FactGraph workspace.

        A workspace contains the ledger, schema metadata, authoring registry,
        and a workspace manifest. If `path` is omitted, the graph must already
        be bound to a workspace path through `FactGraph.create(path=...)` or an
        earlier `fg.save_workspace(path)`.
        """
        self._reject_attached_write("fg.save_workspace")
        workspace_path = _normalize_workspace_path(path) or self._workspace_path
        if workspace_path is None:
            raise SDKStoreError(
                "workspace path not bound; pass fg.save_workspace(path=...) or create with FactGraph.create(path=...)"
            )
        try:
            write_schema_object_for_workspace(workspace_path, self.schema_ir)
            paths = app_save_workspace(
                workspace_path,
                schema_digest=self._schema_digest,
                ledger=self.ledger,
            )
        except Exception as exc:
            if isinstance(exc, SDKStoreError):
                raise
            raise SDKStoreError(str(exc)) from exc
        self._workspace_path = paths.root
        return {"path": str(paths.root), "manifest": str(paths.manifest)}

    @staticmethod
    def _resolve_public_engine(raw_engine: Any, *, api_path: str) -> str:
        engine = "native" if raw_engine is None else raw_engine
        allowed = {"native", "souffle", "problog", "pyreason"}
        if not isinstance(engine, str) or engine not in allowed:
            raise SDKStoreError(f"{api_path}: engine= must be one of: native, problog, pyreason, souffle")
        return engine

    @staticmethod
    def _resolve_public_semantics(raw: Any, *, engine: str, api_path: str) -> SemanticsProfile | None:
        if raw is None:
            return None
        if not isinstance(raw, SemanticsProfile):
            raise SDKStoreError(f"{api_path}: config= expects SemanticsProfile or None")
        if engine not in _SEMANTICS_PROFILE_ENGINES:
            raise SDKStoreError(f"engine='{engine}' does not consume SemanticsProfile")
        if raw.engine != engine:
            raise SDKStoreError(f"SemanticsProfile.engine='{raw.engine}' does not match engine='{engine}'")
        return raw

    def _resolve_public_engine_and_semantics(
        self,
        raw_engine: Any,
        raw_config: Any,
        *,
        derivation: Any | None,
        api_path: str,
    ) -> tuple[str, SemanticsProfile | None]:
        if raw_config is None:
            return (self._resolve_public_engine(raw_engine, api_path=api_path), None)

        semantics_engine = _public_semantics_engine(raw_config)
        if semantics_engine is None:
            raise SDKStoreError(f"{api_path}: config= expects SemanticsProfile or SDK public semantics")

        if isinstance(raw_config, SemanticsProfile):
            if raw_engine is None:
                engine = semantics_engine
            else:
                engine = self._resolve_public_engine(raw_engine, api_path=api_path)
                if engine not in _SEMANTICS_PROFILE_ENGINES:
                    raise SDKStoreError(f"engine='{engine}' does not consume SemanticsProfile")
                if raw_config.engine != engine:
                    raise SDKStoreError(
                        f"SemanticsProfile.engine='{raw_config.engine}' does not match engine='{engine}'"
                    )
            return (engine, raw_config)

        if raw_engine is None:
            engine = semantics_engine
        else:
            engine = self._resolve_public_engine(raw_engine, api_path=api_path)
            if engine != semantics_engine:
                raise SDKStoreError(
                    f"engine='{engine}' does not match semantics.engine='{semantics_engine}'"
                )

        if derivation is None:
            raise SDKStoreError("SDK public semantics require Rule, RuleExpr, or Inference object input")
        return (engine, _lower_public_semantics(raw_config, derivation=derivation))

    def _candidates_for_derivation(
        self, derivation: Any, *, raw_engine: Any, raw_config: Any
    ) -> tuple[list[CandidateSet], list[dict[str, Any]], str, "SemanticsProfile | None"]:
        """Erzeugt die rohen CandidateSets für eine Inference oder ein Derivation-Dict.

        Gemeinsamer Kern von _evaluate und _evaluate_candidates: engine/semantics
        auflösen, bei einer Inference zusätzlich die runtime registry, kompilieren,
        evaluieren. Kein Wrap in EvaluateResult, kein Schreiben. Verhaltenswahrend
        gegenüber den zwei bisherigen _evaluate-Zweigen — der einzige Unterschied
        (registry-Auflösung und derivation= nur für eine Inference) hängt an
        `to_authoring_payload`.
        """
        is_inference = hasattr(derivation, "to_authoring_payload")
        engine, semantics_profile = self._resolve_public_engine_and_semantics(
            raw_engine,
            raw_config,
            derivation=derivation if is_inference else None,
            api_path="evaluate()",
        )
        runtime_registry = (
            self._resolve_runtime_registry(derivation, explicit_registry=None)
            if is_inference
            else None
        )
        compiled_plans = self._compile_derivation_input(derivation)
        candidates = self._evaluate_compiled_derivation_plans(
            compiled_plans,
            mode=engine,
            registry=runtime_registry,
            semantics_profile=semantics_profile,
        )
        return candidates, compiled_plans, engine, semantics_profile

    def _evaluate(self, *args: Any, **kwargs: Any) -> EvaluateResult:
        if "view" in kwargs:
            raise SDKStoreError(
                "method-level view= is not supported by evaluate(); use FactGraph.attach(db, view=view) instead"
            )
        if "policy" in kwargs:
            raise SDKStoreError("policy= was removed for read APIs and is not accepted for inference evaluation")
        if "semantics_profile" in kwargs:
            raise SDKStoreError("evaluate() does not accept semantics_profile= in SDK; use config=")
        if "mode" in kwargs:
            raise SDKStoreError("evaluate() does not accept mode= in E; use engine=")
        if "temporal_view" in kwargs:
            # TODO: temporal_view for evaluate() remains blocked.
            # Snapshot read views (.at/.version) are already implemented in sdk.facade.
            # Re-enable only after derivation/runtime temporal write semantics are defined.
            raise SDKStoreError("temporal_view is removed from evaluate(); use active/history views on read APIs")
        registry = kwargs.pop("registry", None)
        engine_options = kwargs.pop("engine_options", None)
        if registry is not None:
            raise SDKStoreError("evaluate() does not accept registry= in T5; register dependencies on the inference object")
        if engine_options is not None:
            raise SDKStoreError("evaluate() does not accept engine_options= in T5; use config= or engine-specific configuration")
        raw_engine = kwargs.pop("engine", None)
        raw_config = kwargs.pop("config", None)
        if args and isinstance(args[0], str):
            raise SDKStoreError(
                "string derivation DSL is not supported in SDK v1; use Inference object or structured derivation dict"
            )
        if args and isinstance(args[0], (ApplicationRule, _RuleExpr)):
            return self._evaluate_rule_expr_input(
                args,
                kwargs,
                raw_engine=raw_engine,
                raw_config=raw_config,
            )
        if args and hasattr(args[0], "to_authoring_payload"):
            candidates, compiled_plans, engine, semantics_profile = (
                self._candidates_for_derivation(
                    args[0], raw_engine=raw_engine, raw_config=raw_config
                )
            )
            app_plans = _application_plans_from_compiled_dicts(compiled_plans, mode=engine)
            head = _head_rule_for_compiled_plans(app_plans)
            return self._candidate_sets_to_evaluate_result(
                candidates,
                compiled_plans=app_plans,
                head=head,
                engine=engine,
                semantics_profile=semantics_profile,
            )
        if args and isinstance(args[0], dict) and ("derivation_id" in args[0] or "target_pred_id" in args[0] or "head" in args[0]):
            candidates, compiled_plans, engine, semantics_profile = (
                self._candidates_for_derivation(
                    args[0], raw_engine=raw_engine, raw_config=raw_config
                )
            )
            app_plans = _application_plans_from_compiled_dicts(compiled_plans, mode=engine)
            head = _head_rule_for_compiled_plans(app_plans)
            return self._candidate_sets_to_evaluate_result(
                candidates,
                compiled_plans=app_plans,
                head=head,
                engine=engine,
                semantics_profile=semantics_profile,
            )
        raise SDKStoreError(
            "direct Store.evaluate-style calls are not supported by SDK evaluate() after the T5 result-envelope "
            "hard-cut; use an application Rule/RuleExpr with head=, an Inference object, or a structured "
            "derivation dict"
        )

    def _evaluate_candidates(self, *args: Any, **kwargs: Any) -> list[CandidateSet]:
        if "view" in kwargs:
            raise SDKStoreError(
                "method-level view= is not supported by evaluate_candidates(); use FactGraph.attach(db, view=view) instead"
            )
        if "policy" in kwargs:
            raise SDKStoreError("policy= was removed for read APIs and is not accepted for inference evaluation")
        if "semantics_profile" in kwargs:
            raise SDKStoreError("evaluate_candidates() does not accept semantics_profile= in SDK; use config=")
        if "mode" in kwargs:
            raise SDKStoreError("evaluate_candidates() does not accept mode=; use engine=")
        if "temporal_view" in kwargs:
            raise SDKStoreError("temporal_view is removed from evaluate_candidates(); use active/history views on read APIs")
        registry = kwargs.pop("registry", None)
        engine_options = kwargs.pop("engine_options", None)
        if registry is not None:
            raise SDKStoreError("evaluate_candidates() does not accept registry=; register dependencies on the inference object")
        if engine_options is not None:
            raise SDKStoreError("evaluate_candidates() does not accept engine_options=; use config= or engine-specific configuration")
        raw_engine = kwargs.pop("engine", None)
        raw_config = kwargs.pop("config", None)
        head = kwargs.pop("head", None)
        if args and isinstance(args[0], str):
            raise SDKStoreError(
                "string derivation DSL is not supported in SDK v1; use Inference object or structured derivation dict"
            )
        if args and isinstance(args[0], (ApplicationRule, _RuleExpr)):
            # RuleExpr/Rule candidates come from the SAME lowering + evaluation as
            # evaluate(rule_expr, head=): the returned CandidateSets are exactly the
            # ones whose EvaluateResult rows explain()/narrate(). This is the write
            # leg of the RuleExpr path (feed accept_derivation_candidate_set), with no
            # second evaluator and no recompute outside the FactGraph evaluation.
            if not isinstance(head, ApplicationRule):
                raise SDKStoreError(
                    "evaluate_candidates(rule_expr, head=) requires a closed application Rule head "
                    "(same head you would pass to evaluate(rule_expr, head=))"
                )
            candidates, *_rest = self._rule_expr_candidates_core(
                args[0],
                head=head,
                raw_engine=raw_engine,
                raw_config=raw_config,
                api_path="evaluate_candidates(rule_expr)",
            )
            return candidates
        if head is not None:
            raise SDKStoreError(
                "head= is only accepted by evaluate_candidates(rule_expr, head=); "
                "Inference / derivation-dict inputs declare their head on the input object"
            )
        if args and (
            hasattr(args[0], "to_authoring_payload")
            or (
                isinstance(args[0], dict)
                and (
                    "derivation_id" in args[0]
                    or "target_pred_id" in args[0]
                    or "head" in args[0]
                )
            )
        ):
            candidates, _compiled_plans, _engine, _semantics = (
                self._candidates_for_derivation(
                    args[0], raw_engine=raw_engine, raw_config=raw_config
                )
            )
            return candidates
        raise SDKStoreError(
            "evaluate_candidates() requires an Inference object or a structured derivation dict"
        )

    def _explain(self, *args: Any, **kwargs: Any) -> Explanation:
        if len(args) != 1:
            raise SDKStoreError("eval.explain(expr, ...) accepts exactly one RuleExpr or Rule input")
        if "head" not in kwargs:
            raise SDKStoreError("eval.explain(expr, ...) requires head= closed Rule")
        head = kwargs.pop("head")
        raw_engine = kwargs.pop("engine", None)
        raw_config = kwargs.pop("config", None)
        if "view" in kwargs:
            raise SDKStoreError(
                "method-level view= is not supported by eval.explain(...); use FactGraph.attach(db, view=view) instead"
            )
        if kwargs:
            unknown = ", ".join(sorted(kwargs))
            raise SDKStoreError(f"unknown eval.explain(...) keyword(s): {unknown}")
        if not isinstance(head, ApplicationRule):
            raise SDKStoreError("eval.explain(...) head= must be Rule")
        self._require_manual_explain_closed_head(head)

        evaluate_kwargs: dict[str, Any] = {"head": head}
        if raw_engine is not None:
            evaluate_kwargs["engine"] = raw_engine
        if raw_config is not None:
            evaluate_kwargs["config"] = raw_config
        evaluate_kwargs["head"] = self._manual_explain_replay_head(args[0], head)
        result = self._evaluate(args[0], **evaluate_kwargs)
        checked_scope = self._manual_explain_checked_scope(result, closed_head=head)
        first = self._manual_explain_matching_row(result, closed_head=head)
        if first is None:
            # Faithful full-coverage failure explain: lower the FULL expr body
            # against the closed head (NOT just head.as_("head"), which probed the
            # head alone), then route the head pins as the seed through the same
            # per-engine evidence builders the holding path uses. A bare single-rule
            # input has no separate body (it IS the head structurally), so lower the
            # closed head as one occurrence — which also sidesteps the bare-Rule
            # auto-alias coercion error for non-identifier rule ids.
            body_source = args[0] if isinstance(args[0], _RuleExpr) else head.as_("head")
            body_plan = _lower_rule_expr(_coerce_rule_expr_operand(body_source), head=head)
            pin_bindings = self._pin_bindings_for_closed_head(head)
            evidence = self._closed_head_false_evidence_graph(
                body_plan,
                pin_bindings,
                result=result,
                checked_scope=checked_scope,
            )
            return Explanation(
                status="failed",
                evidence=evidence,
                row=None,
                result_id=result.result_id,
                failure_class="closed_head_false",
                checked_scope=checked_scope,
                suggested_next_steps=("Re-evaluate with a closed head that matches at least one result row.",),
            )

        row_explanation = first.explain()
        return Explanation(
            status=row_explanation.status,
            evidence=row_explanation.evidence,
            row=row_explanation.row,
            result_id=result.result_id,
            failure_class=row_explanation.failure_class,
            checked_scope=checked_scope,
            suggested_next_steps=row_explanation.suggested_next_steps,
            errors=row_explanation.errors,
            warnings=row_explanation.warnings,
        )

    def _require_manual_explain_closed_head(self, head: ApplicationRule) -> None:
        inspected = _inspect_closed_head(head, schema_index=self._application_schema_index)
        if not inspected.is_closed:
            missing = ", ".join(inspected.unbound_ports)
            raise RuleExprError(f"manual explain head must be closed; unbound ports: {missing}")

    def _manual_explain_checked_scope(self, result: EvaluateResult, *, closed_head: ApplicationRule) -> Mapping[str, Any]:
        fingerprint = result.fingerprint
        return {
            "config_digest": fingerprint.config_digest,
            "semantics_source": "manual_standalone",
            "evaluate_config_digest": None,
            "explain_config_digest": fingerprint.config_digest,
            "semantics_match": None,
            "result_id": result.result_id,
            "expr_digest": fingerprint.expr_digest,
            "rule_set_digest": fingerprint.rule_set_digest,
            "view_snapshot_digest": fingerprint.view_snapshot_digest,
            "closed_head_digest": closed_head_digest_for(closed_head),
        }

    @staticmethod
    def _manual_explain_replay_head(source: Any, closed_head: ApplicationRule) -> ApplicationRule:
        if isinstance(source, ApplicationRule) and source.id != closed_head.id:
            return source
        if isinstance(source, ApplicationRule) and source.content_digest != closed_head.content_digest:
            return source
        return closed_head

    def _manual_explain_matching_row(
        self,
        result: EvaluateResult,
        *,
        closed_head: ApplicationRule,
    ) -> Any | None:
        expected_digest = closed_head.content_digest
        for row in result:
            try:
                if self._close_evaluate_row(row, result).content_digest == expected_digest:
                    return row
            except (DetachedRowError, RuleExprError, SDKStoreError):
                continue
        return None

    def _evaluate_compiled_derivation_plans(
        self,
        compiled_plans: list[dict[str, Any]],
        *,
        mode: str | None,
        registry: RuleRegistry | None,
        engine_options: dict[str, Any] | None = None,
        semantics_profile: SemanticsProfile | None = None,
    ) -> list[CandidateSet]:
        if not compiled_plans:
            return []
        resolved_mode = _resolve_compiled_derivation_mode(compiled_plans, explicit_mode=mode)
        request = DerivationEvaluateRequest(
            plans=tuple(
                _compiled_derivation_plan_to_application(
                    compiled,
                    mode=resolved_mode,
                    engine_options=engine_options,
                )
                for compiled in compiled_plans
            ),
            run_id=(
                self._derive_shared_run_id(compiled_plans[0]["derivation_id"])
                if len(compiled_plans) > 1
                else None
            ),
            engine=resolved_mode,
            semantics_profile=semantics_profile,
        )
        return evaluate_derivation_plans(
            request,
            store=self._store,
            registry=registry,
        )

    def _evaluate_rule_expr_input(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        raw_engine: Any,
        raw_config: Any,
    ) -> EvaluateResult:
        if len(args) != 1:
            raise SDKStoreError("evaluate(rule_expr, ...) accepts exactly one RuleExpr or application Rule input")
        if "head" not in kwargs:
            raise SDKStoreError("evaluate(rule_expr, ...) requires head= Rule")
        head = kwargs.pop("head")
        if kwargs:
            unknown = ", ".join(sorted(kwargs))
            raise SDKStoreError(f"unknown evaluate(rule_expr, ...) keyword(s): {unknown}")
        if not isinstance(head, ApplicationRule):
            raise SDKStoreError(
                "evaluate(rule_expr, ...) head= must be Rule; "
                "legacy SDK Rule, Inference, dict, string, and inspect objects are not accepted"
            )

        candidates, compiled, plan, rules_by_id, engine, semantics_profile = (
            self._rule_expr_candidates_core(
                args[0],
                head=head,
                raw_engine=raw_engine,
                raw_config=raw_config,
                api_path="evaluate(rule_expr)",
            )
        )
        return self._candidate_sets_to_evaluate_result(
            candidates,
            compiled_plans=[compiled],
            head=head,
            engine=engine,
            semantics_profile=semantics_profile,
            lowering_plan=plan if engine in {"native", "problog", "souffle"} else None,
            lowering_rules_by_id=rules_by_id if engine in {"native", "problog", "souffle"} else None,
        )

    def _rule_expr_candidates_core(
        self,
        source: Any,
        *,
        head: Any,
        raw_engine: Any,
        raw_config: Any,
        api_path: str,
    ) -> tuple[list[CandidateSet], Any, Any, Any, str, Any]:
        """Lower a RuleExpr/Rule (+ closed head) and evaluate it to CandidateSets.

        The single shared RuleExpr evaluation path. ``evaluate(rule_expr)`` wraps the
        returned candidates into an EvaluateResult (whose rows ``explain()``/``narrate()``);
        ``evaluate_candidates(rule_expr, head=)`` returns the same candidates raw (for
        ``accept_derivation_candidate_set``). Identical lowering + identical
        ``evaluate_derivation_plans`` call, so the accepted CandidateSet is exactly the
        one the narration explains — no second evaluator.
        """
        if isinstance(source, ApplicationRule):
            if _RULE_EXPR_DEFAULT_ALIAS_RE.fullmatch(source.id):
                plan = _lower_application_rule(source, head=head)
            else:
                plan = _lower_rule_expr(_coerce_rule_expr_operand(source.as_("head")), head=head)
        elif isinstance(source, _RuleExpr):
            plan = _lower_rule_expr(source, head=head)
        else:  # pragma: no cover - guarded by caller classification
            raise SDKStoreError(f"{api_path} expects application Rule or RuleExpr input")

        _validate_rule_expr_head_foundation(plan)
        rules_by_id = _rule_expr_rules_by_id(source, head=head)
        engine, semantics_profile = self._resolve_public_engine_and_semantics(
            raw_engine,
            raw_config,
            derivation=_semantics_context_for_ruleexpr_plan(source, head=head, plan=plan),
            api_path=api_path,
        )

        if engine == "pyreason":
            support = _classify_pyreason_rule_expr_support(plan)
            if not support.supported:
                raise _rule_expr_adapter_support_error(support)
            compiled, _traces = _materialize_adapter_derivation_plan(plan, engine="native")
        else:
            compiled, _traces = _materialize_adapter_derivation_plan(plan, engine=engine)

        candidates = evaluate_derivation_plans(
            DerivationEvaluateRequest(
                plans=(compiled,),
                engine=engine,
                semantics_profile=semantics_profile,
            ),
            store=self._store,
            registry=None,
        )
        return candidates, compiled, plan, rules_by_id, engine, semantics_profile

    def _candidate_sets_to_evaluate_result(
        self,
        candidates: list[CandidateSet],
        *,
        compiled_plans: Sequence[CompiledDerivationPlan],
        head: ApplicationRule,
        engine: str,
        semantics_profile: SemanticsProfile | None,
        lowering_plan: RuleExprLoweringPlan | None = None,
        lowering_rules_by_id: Mapping[str, ApplicationRule] | None = None,
    ) -> EvaluateResult:
        run_id = new_run_id()
        expr_digest = expr_digest_for_payload(
            "compiled_derivation_plans",
            {"plans": [_compiled_plan_digest_payload(plan) for plan in compiled_plans]},
        )
        rule_set_digest = rule_set_digest_for_entries(_rule_set_entries_for_result(compiled_plans, head=head))
        view_snapshot_digest = self._view_snapshot_digest()
        config_digest = config_digest_for(semantics_profile)
        result_id = result_id_for(
            run_id=run_id,
            expr_digest=expr_digest,
            rule_set_digest=rule_set_digest,
            view_snapshot_digest=view_snapshot_digest,
            config_digest=config_digest,
            engine=engine,
            head_id=head.id,
            head_content_digest=head.content_digest,
        )
        closed_head_digest = closed_head_digest_for(head)
        try:
            rows = tuple(
                _candidate_set_to_evaluate_row(
                    candidate,
                    head=head,
                    result_id=result_id,
                    run_id=run_id,
                    closed_head_digest=closed_head_digest,
                    claim_name=head.id,
                )
                for candidate in candidates
            )
            row_support_artifacts = self._row_support_artifacts_for_candidates(candidates, rows)
            row_provenance_envelopes = self._row_provenance_envelopes_for_candidates(candidates, rows)
            row_digests = tuple(_row_digest_for(row, result_id=result_id, claim_name=head.id) for row in rows)
            result_digest = result_digest_for(
                result_id=result_id,
                run_id=run_id,
                row_digests=row_digests,
                head_id=head.id,
                head_content_digest=head.content_digest,
                engine=engine,
                engine_version=None,
                adapter_version=None,
                expr_digest=expr_digest,
                rule_set_digest=rule_set_digest,
                view_snapshot_digest=view_snapshot_digest,
                config_digest=config_digest,
            )
            fingerprint = ResultFingerprint(
                expr_digest=expr_digest,
                rule_set_digest=rule_set_digest,
                view_snapshot_digest=view_snapshot_digest,
                config_digest=config_digest,
                result_digest=result_digest,
                run_id=run_id,
            )
            return EvaluateResult(
                result_id=result_id,
                rows=rows,
                head=head,
                engine=engine,
                evaluated_at=datetime.now(timezone.utc),
                fingerprint=fingerprint,
                engine_meta={"engine_version": None, "adapter_version": None},
                _schema_index=self._application_schema_index,
                _row_close_builder=self._close_evaluate_row,
                _row_graph_builder=self._row_graph_builder_for_engine(
                    engine=engine,
                    lowering_plan=lowering_plan,
                    lowering_rules_by_id=lowering_rules_by_id,
                    semantics_profile=semantics_profile,
                    row_support_artifacts=row_support_artifacts,
                    row_provenance_envelopes=row_provenance_envelopes,
                ),
                _row_support_artifacts=row_support_artifacts,
                _row_provenance_envelopes=row_provenance_envelopes,
            )
        except Exception as exc:
            if isinstance(exc, SDKStoreError):
                raise
            raise SDKStoreError(f"failed to build EvaluateResult: {exc}") from exc

    def _row_graph_builder_for_engine(
        self,
        *,
        engine: str,
        lowering_plan: RuleExprLoweringPlan | None,
        lowering_rules_by_id: Mapping[str, ApplicationRule] | None,
        semantics_profile: SemanticsProfile | None,
        row_support_artifacts: Mapping[str, ProofReceipt],
        row_provenance_envelopes: Mapping[str, ProvenanceEnvelope],
    ):
        if engine == "native" and lowering_plan is not None:
            return self._row_graph_builder_for_lowering_plan(lowering_plan, rules_by_id=lowering_rules_by_id or {})
        if engine == "souffle":
            return self._souffle_row_graph_builder(
                row_support_artifacts,
                lowering_plan=lowering_plan,
                rules_by_id=lowering_rules_by_id or {},
            )
        if engine == "problog":
            return self._problog_row_graph_builder(
                row_provenance_envelopes,
                lowering_plan=lowering_plan,
                rules_by_id=lowering_rules_by_id or {},
                semantics_profile=semantics_profile,
            )
        if engine == "pyreason":
            return self._pyreason_row_graph_builder(row_provenance_envelopes)
        return None

    def _row_graph_builder_for_lowering_plan(
        self,
        plan: RuleExprLoweringPlan,
        *,
        rules_by_id: Mapping[str, ApplicationRule],
    ):
        def _builder(row: Any, result: EvaluateResult, metadata: Mapping[str, Any]) -> EvidenceGraph:
            return self._probe_evidence_graph_for_lowering_plan(
                plan,
                result=result,
                row=row,
                metadata=metadata,
                rules_by_id=rules_by_id,
            )

        return _builder

    def _souffle_row_graph_builder(
        self,
        row_support_artifacts: Mapping[str, ProofReceipt],
        *,
        lowering_plan: RuleExprLoweringPlan | None,
        rules_by_id: Mapping[str, ApplicationRule],
    ):
        def _builder(row: Any, result: EvaluateResult, metadata: Mapping[str, Any]) -> EvidenceGraph:
            if lowering_plan is not None:
                try:
                    return souffle_reach_explain_to_evidence_graph(
                        self._store,
                        plan=lowering_plan,
                        row_bindings=_public_bindings_for_row(row),
                        graph_id=f"{result.result_id}:{row.row_id}",
                        engine=result.engine,
                        schema_index=self._application_schema_index,
                        rules_by_id=rules_by_id or {lowering_plan.head.id: lowering_plan.head},
                        subject_binding=self._display_bindings_for_row(row),
                        metadata=metadata,
                        graph_certainty=row.certainty,
                    )
                except Exception:
                    pass
            artifact = row_support_artifacts.get(row.row_id)
            if artifact is None or artifact.kind != SOUFFLE_WITNESS_KIND:
                return _build_minimal_row_evidence_graph(row, result, metadata)
            try:
                return _souffle_support_artifact_to_evidence_graph(
                    artifact,
                    row=row,
                    result=result,
                    metadata=metadata,
                )
            except Exception:
                return _build_minimal_row_evidence_graph(row, result, metadata)

        return _builder

    def _problog_row_graph_builder(
        self,
        row_provenance_envelopes: Mapping[str, ProvenanceEnvelope],
        *,
        lowering_plan: RuleExprLoweringPlan | None,
        rules_by_id: Mapping[str, ApplicationRule],
        semantics_profile: SemanticsProfile | None,
    ):
        def _builder(row: Any, result: EvaluateResult, metadata: Mapping[str, Any]) -> EvidenceGraph:
            if lowering_plan is not None:
                try:
                    return problog_reach_explain_to_evidence_graph(
                        self._store,
                        plan=lowering_plan,
                        row_bindings=_public_bindings_for_row(row),
                        graph_id=f"{result.result_id}:{row.row_id}",
                        engine=result.engine,
                        schema_index=self._application_schema_index,
                        rules_by_id=rules_by_id or {lowering_plan.head.id: lowering_plan.head},
                        subject_binding=self._display_bindings_for_row(row),
                        metadata=metadata,
                        graph_certainty=row.certainty,
                        uncertainty_projection=None
                        if semantics_profile is None
                        else dict(semantics_profile.uncertainty_projection),
                        engine_options=None if semantics_profile is None else dict(semantics_profile.engine_options),
                        input_certainty_for_goal=self._problog_input_certainty_for_goal,
                    )
                except Exception:
                    pass
            envelope = row_provenance_envelopes.get(row.row_id)
            if envelope is None or envelope.engine != "problog" or envelope.payload_type != "proof_trace":
                return _build_minimal_row_evidence_graph(row, result, metadata)
            try:
                trace = problog_trace_from_dict(envelope.payload)
                display_bindings = self._display_bindings_for_row(row)
                graph = problog_trace_to_evidence_graph(
                    trace,
                    candidate_id=envelope.candidate_id,
                    candidate_payload=_legacy_candidate_payload_for_row_result(row, result),
                    support_kind=PROBLOG_PROVENANCE_KIND,
                    context=ProbLogEvidenceContext(
                        head_rule_id=result.head.id,
                        head_repr_text=result.head.render_repr(display_bindings) or None,
                        head_ports=display_bindings,
                        subject_binding=display_bindings,
                        input_certainty_for_goal=self._problog_input_certainty_for_goal,
                    ),
                )
                return EvidenceGraph(
                    graph_id=f"{result.result_id}:{row.row_id}",
                    engine=result.engine,
                    layout_hint=graph.layout_hint,
                    subject_binding=graph.subject_binding,
                    paths=graph.paths,
                    certainty=graph.certainty,
                    metadata=dict(metadata),
                )
            except Exception:
                return _build_minimal_row_evidence_graph(row, result, metadata)

        return _builder

    def _display_bindings_for_row(self, row: Any) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in _public_bindings_for_row(row).items():
            out[key] = self._display_binding_value(value)
        return out

    def _display_binding_value(self, value: Any) -> Any:
        return display_value(
            self._application_schema_index,
            value,
            entity_identity_resolver=self._identity_for_entity_ref_binding,
        )

    def _problog_input_certainty_for_goal(self, goal_name: str, goal_args: tuple[Any, ...]) -> Certainty | None:
        if goal_name != "edb_fact" or len(goal_args) < 4:
            return None
        pred_id = _normalize_problog_goal_value(goal_args[1])
        e_ref = _normalize_problog_goal_value(goal_args[2])
        rest_values = tuple(_normalize_problog_goal_value(arg) for arg in goal_args[3:])
        if not pred_id or not e_ref:
            return None
        for claim in reversed(self.ledger.find_claims(pred_id=pred_id, e_ref=e_ref)):
            if self.ledger.has_active_revocation(claim.asrt_id):
                continue
            if not _claim_rest_terms_match_values(claim.rest_terms, rest_values):
                continue
            raw_kind = _claim_meta_value(self.ledger, claim.asrt_id, "raw_kind")
            bound = _claim_meta_value(self.ledger, claim.asrt_id, "bound")
            if raw_kind != "probabilistic" or not isinstance(bound, list) or len(bound) != 2:
                return None
            return Certainty(lo=float(bound[0]), hi=float(bound[1]), kind="probabilistic")
        return None

    def _pyreason_row_graph_builder(self, row_provenance_envelopes: Mapping[str, ProvenanceEnvelope]):
        def _builder(row: Any, result: EvaluateResult, metadata: Mapping[str, Any]) -> EvidenceGraph:
            envelope = row_provenance_envelopes.get(row.row_id)
            if envelope is None or envelope.engine != "pyreason" or envelope.payload_type != "event_log":
                return _build_minimal_row_evidence_graph(row, result, metadata)
            try:
                trace = pyreason_trace_from_dict(envelope.payload)
                graph = pyreason_trace_to_evidence_graph(
                    trace,
                    candidate_id=envelope.candidate_id,
                    candidate_payload=_legacy_candidate_payload_for_row_result(row, result),
                    support_kind=PYREASON_PROVENANCE_KIND,
                )
                return EvidenceGraph(
                    graph_id=f"{result.result_id}:{row.row_id}",
                    engine=result.engine,
                    layout_hint=graph.layout_hint,
                    subject_binding=graph.subject_binding,
                    paths=graph.paths,
                    certainty=graph.certainty,
                    metadata=dict(metadata),
                )
            except Exception:
                return _build_minimal_row_evidence_graph(row, result, metadata)

        return _builder

    def _probe_evidence_graph_for_lowering_plan(
        self,
        plan: RuleExprLoweringPlan,
        *,
        result: EvaluateResult,
        row: Any | None,
        metadata: Mapping[str, Any],
        rules_by_id: Mapping[str, ApplicationRule] | None = None,
        pin_bindings: Mapping[str, Any] | None = None,
    ) -> EvidenceGraph:
        view_facts = project_view_facts(self.ledger, self._schema_ir)
        if pin_bindings is not None:
            # closed_head_false: seed from the head pins (probe_native then expands
            # the seed transitively over the join / head-link eq-atoms).
            initial_bindings = _initial_probe_bindings_from_port_values(pin_bindings, plan)
            display_bindings = self._display_pin_bindings(pin_bindings)
        elif row is not None:
            initial_bindings = _initial_probe_bindings_for_row(row, plan)
            display_bindings = self._display_bindings_for_row(row)
        else:
            initial_bindings = {}
            display_bindings = {}
        probed = probe_native(
            plan,
            initial_bindings,
            view_facts,
            schema_index=self._application_schema_index,
            rules_by_id=rules_by_id or {plan.head.id: plan.head},
            subject_binding=display_bindings,
        )
        row_id = getattr(row, "row_id", "closed_head_false")
        return EvidenceGraph(
            graph_id=f"{result.result_id}:{row_id}",
            engine=result.engine,
            layout_hint="tree",
            subject_binding=display_bindings,
            paths=probed.paths,
            certainty=probed.certainty,
            metadata=dict(metadata),
        )

    def _pin_bindings_for_closed_head(self, head: ApplicationRule) -> dict[str, Any]:
        """Recover ``{port_name: idref|scalar}`` pins from a CLOSED explain head.

        Entity-ref pins are minted into idref tokens via ``_ref`` — the same path
        the EDB / view facts use — so the failure-explain seed is byte-identical to
        engine facts (seed-parity). Value pins pass through as the raw public scalar
        (the reach builder / native prober encode them per engine)."""
        specs = pin_specs_for_closed_head(head, schema_index=self._application_schema_index)
        cls_by_type = {
            spec["entity_type"]: cls
            for cls, spec in self._entity_spec_by_class.items()
            if isinstance(spec.get("entity_type"), str)
        }
        out: dict[str, Any] = {}
        for port_name, pin in specs.items():
            if pin[0] == "value":
                out[port_name] = pin[1]
                continue
            _kind, entity_type, fields = pin
            entity_cls = cls_by_type.get(entity_type)
            if entity_cls is None:
                raise SDKStoreError(
                    f"closed-head port {port_name!r} references unregistered entity type {entity_type!r}"
                )
            out[port_name] = self._ref(entity_cls, **fields)
        return out

    def _display_pin_bindings(self, pin_bindings: Mapping[str, Any]) -> dict[str, Any]:
        return {key: self._display_binding_value(value) for key, value in pin_bindings.items()}

    def _closed_head_false_evidence_graph(
        self,
        plan: RuleExprLoweringPlan,
        pin_bindings: Mapping[str, Any],
        *,
        result: EvaluateResult,
        checked_scope: Mapping[str, Any],
    ) -> EvidenceGraph:
        """Build the full-coverage evidence graph for a non-holding closed head.

        Routes the FULL expr-body plan (head = closed head) seeded by the head pins
        through the engine-own reach-chain explainer (souffle / problog) — the same
        builders the holding path uses, only seeded by the closed-head pins instead
        of a result row. native / pyreason / a reach-unsupported fallback all use
        the pin-seeded native prober (never the minimal head-only graph, which would
        lose body coverage). The probe is structural (a non-holding conclusion has
        no derived WMC), so it is labelled accordingly."""
        metadata = {
            "result_id": result.result_id,
            "failure_class": "closed_head_false",
            "closed_head_digest": checked_scope["closed_head_digest"],
            "engine": result.engine,
            "probe_kind": "structural_reachability",
        }
        graph_id = f"{result.result_id}:closed_head_false"
        rules_by_id = {plan.head.id: plan.head}
        subject_binding = self._display_pin_bindings(pin_bindings)
        engine = result.engine
        if engine == "souffle":
            try:
                return souffle_reach_explain_to_evidence_graph(
                    self._store,
                    plan=plan,
                    row_bindings=pin_bindings,
                    graph_id=graph_id,
                    engine=engine,
                    schema_index=self._application_schema_index,
                    rules_by_id=rules_by_id,
                    subject_binding=subject_binding,
                    metadata=metadata,
                    graph_certainty=BOOLEAN_CERTAINTY,
                )
            except Exception:
                pass
        elif engine == "problog":
            try:
                return problog_reach_explain_to_evidence_graph(
                    self._store,
                    plan=plan,
                    row_bindings=pin_bindings,
                    graph_id=graph_id,
                    engine=engine,
                    schema_index=self._application_schema_index,
                    rules_by_id=rules_by_id,
                    subject_binding=subject_binding,
                    metadata=metadata,
                    graph_certainty=BOOLEAN_CERTAINTY,
                    uncertainty_projection=None,
                    engine_options=None,
                    input_certainty_for_goal=self._problog_input_certainty_for_goal,
                )
            except Exception:
                pass
        return self._probe_evidence_graph_for_lowering_plan(
            plan,
            result=result,
            row=None,
            metadata=metadata,
            rules_by_id=rules_by_id,
            pin_bindings=pin_bindings,
        )

    def _row_support_artifacts_for_candidates(
        self,
        candidates: Sequence[CandidateSet],
        rows: Sequence[Any],
    ) -> Mapping[str, ProofReceipt]:
        out: dict[str, ProofReceipt] = {}
        for candidate, row in zip(candidates, rows):
            if candidate.support_kind not in _FORM1_ROW_SUPPORT_KINDS:
                continue
            artifact = self._store._lookup_support_artifact(candidate.support_digest)
            if isinstance(artifact, ProofReceipt):
                out[row.row_id] = artifact
        return out

    def _row_provenance_envelopes_for_candidates(
        self,
        candidates: Sequence[CandidateSet],
        rows: Sequence[Any],
    ) -> Mapping[str, ProvenanceEnvelope]:
        out: dict[str, ProvenanceEnvelope] = {}
        for candidate, row in zip(candidates, rows):
            if candidate.support_kind not in {PROBLOG_PROVENANCE_KIND, PYREASON_PROVENANCE_KIND}:
                continue
            envelope = self._store._lookup_provenance_envelope(candidate.support_digest)
            if isinstance(envelope, ProvenanceEnvelope):
                out[row.row_id] = envelope
        return out

    def _close_evaluate_row(self, row: Any, result: Any) -> ApplicationRule:
        return _build_closed_head_from_row(
            row,
            result,
            schema_index=self._application_schema_index,
            entity_identity_resolver=self._identity_for_entity_ref_binding,
        )

    def _identity_for_entity_ref_binding(
        self,
        entity_type: str,
        value: object,
        _schema_index: object | None,
    ) -> Mapping[str, Any]:
        if isinstance(value, AppEntityRef):
            if value.entity_type != entity_type:
                raise RuleExprError(
                    f"cannot close entity-ref port for {entity_type}: row binding has entity_type {value.entity_type!r}"
                )
            return value.identity
        if isinstance(value, Mapping):
            identity = value.get("identity")
            if isinstance(identity, Mapping):
                return identity
            return value
        if not isinstance(value, str):
            raise RuleExprError(f"cannot close entity-ref port for {entity_type}: unsupported row binding")
        ref_entity_type = entity_type_from_ref(value)
        if ref_entity_type != entity_type:
            raise RuleExprError(f"cannot close entity-ref port for {entity_type}: row binding is not an {entity_type} ref")

        entity = self._application_schema_index.entities.get(entity_type)
        if entity is None:
            raise RuleExprError(f"cannot close entity-ref port for {entity_type}: unknown entity type")
        identity: dict[str, Any] = {}
        for field_info in entity.identity_fields:
            field_name = field_info.name
            predicate = entity.identity_predicates.get(field_name)
            pred_id = getattr(predicate, "pred_id", None)
            if not isinstance(pred_id, str) or not pred_id:
                raise RuleExprError(
                    f"cannot close entity-ref port for {entity_type}: missing identity predicate for {field_name!r}"
                )
            active_claims = [
                claim
                for claim in self.ledger.find_claims(pred_id=pred_id, e_ref=value)
                if not self.ledger.has_active_revocation(claim.asrt_id)
            ]
            if not active_claims:
                raise RuleExprError(
                    f"cannot close entity-ref port for {entity_type}: missing identity field {field_name!r}"
                )
            rest_terms = active_claims[-1].rest_terms
            if not rest_terms:
                raise RuleExprError(
                    f"cannot close entity-ref port for {entity_type}: empty identity value for {field_name!r}"
                )
            identity[field_name] = rest_terms[0][1]
        return identity

    def _view_snapshot_digest(self) -> str:
        schema_token = self._schema_digest
        ledger = self.ledger
        db_id = ledger.get_ledger_meta("db_id")
        if db_id is None:
            db_id = "mem:" + sha256_hex(canonical_bytes_for_evaluate("sdk_evaluate_mem_db_v1", schema_token))
        base_tx_id = ledger.get_ledger_meta("head_tx_id")
        if base_tx_id is None:
            base_tx_id = "tx:" + sha256_hex(
                canonical_bytes_for_evaluate(
                    "sdk_evaluate_mem_tx_v1",
                    {
                        "claims": [
                            {
                                "asrt_id": claim.asrt_id,
                                "e_ref": claim.e_ref,
                                "pred_id": claim.pred_id,
                                "rest_terms": claim.rest_terms,
                            }
                            for claim in sorted(ledger.find_claims(), key=lambda claim: claim.asrt_id)
                        ],
                        "revokes": [
                            {
                                "revoked_asrt_id": revoke.revoked_asrt_id,
                                "revoker_asrt_id": revoke.revoker_asrt_id,
                            }
                            for revoke in sorted(
                                ledger.revokes,
                                key=lambda revoke: (revoke.revoked_asrt_id, revoke.revoker_asrt_id),
                            )
                        ],
                        "schema_digest": schema_token,
                    },
                )
            )
        active_asrt_ids = tuple(
            _view_snapshot_asrt_id_for_claim(claim)
            for claim in sorted(ledger.find_claims(), key=lambda claim: claim.asrt_id)
            if not ledger.has_active_revocation(claim.asrt_id)
        )
        return view_snapshot_digest_for_parts(
            db_id=db_id,
            base_tx_id=base_tx_id,
            schema_digest=schema_token,
            asrt_ids=active_asrt_ids,
        )

    @staticmethod
    def _derive_shared_run_id(derivation_id: Any) -> str:
        if isinstance(derivation_id, str) and derivation_id:
            return f"{derivation_id}:{uuid4().hex[:8]}"
        return f"derive:{uuid4().hex[:8]}"

    def export_package(self, out_dir, options: ExportOptions, **kwargs: Any):
        return export_package(self._store, out_dir, options, **kwargs)

    def run_package(self, package_dir, *, entrypoints: list[str], engine: str = "souffle"):
        return run_package(package_dir, entrypoints=entrypoints, engine=engine)

    def _compile_rule_input(self, rule: Any) -> dict[str, Any]:
        if isinstance(rule, RuleSpec):
            return {
                "rule_id": rule.rule_id,
                "version": rule.version,
                "select_vars": list(rule.select_vars),
                "where": list(rule.where),
                "expose": rule.expose,
            }
        if hasattr(rule, "to_authoring_payload"):
            payload = rule.to_authoring_payload()
        elif isinstance(rule, dict):
            payload = dict(rule)
        else:
            raise SDKStoreError("rule must be RuleSpec, SDK Rule object, or authoring rule payload dict")
        for key in ("where", "body"):
            if key not in payload:
                continue
            normalized_where, used_wrapper = _normalize_where_branch_wrappers(
                payload[key],
                path=f"$.{key}",
            )
            if used_wrapper:
                payload[key] = normalized_where
        try:
            return compile_authoring_rule_v1(payload, schema_ir=self._schema_ir)
        except Exception as exc:
            raise SDKStoreError(f"invalid rule input: {exc}") from exc

    def _register_rule_dependencies(self, registry: RuleRegistry, rule: Any) -> None:
        if not hasattr(rule, "dependency_rules"):
            return
        deps = rule.dependency_rules()
        if not isinstance(deps, list):
            return
        visited: set[tuple[str, str]] = set()

        def add_dep(dep_rule: Any) -> None:
            if not hasattr(dep_rule, "to_authoring_payload"):
                return
            dep_compiled = self._compile_rule_input(dep_rule)
            key = (dep_compiled["rule_id"], dep_compiled["version"])
            if key in visited:
                return
            visited.add(key)
            if hasattr(dep_rule, "dependency_rules"):
                for child in dep_rule.dependency_rules():
                    add_dep(child)
            registry.register(
                RuleSpec(
                    rule_id=dep_compiled["rule_id"],
                    version=dep_compiled["version"],
                    select_vars=list(dep_compiled["select_vars"]),
                    where=list(dep_compiled["where"]),
                    expose=bool(dep_compiled.get("expose", False)),
                )
            )

        for dep in deps:
            add_dep(dep)

    def _resolve_runtime_registry(
        self,
        obj: Any,
        *,
        explicit_registry: RuleRegistry | None,
    ) -> RuleRegistry | None:
        if explicit_registry is not None:
            return explicit_registry
        if not hasattr(obj, "dependency_rules"):
            return None
        deps = obj.dependency_rules()
        if not isinstance(deps, list) or not deps:
            return None
        registry = RuleRegistry()
        self._register_rule_dependencies(registry, obj)
        return registry

    def _compile_derivation_input(self, derivation: Any) -> list[dict[str, Any]]:
        if isinstance(derivation, dict) and {
            "derivation_id",
            "version",
            "target_pred_id",
            "head_vars",
            "where",
        }.issubset(set(derivation.keys())) and not isinstance(derivation.get("head"), list):
            compiled = dict(derivation)
            body_confidences = _coerce_body_confidences(
                compiled.get("body_confidences"),
                path="$.body_confidences",
            )
            if body_confidences is not None:
                _validate_body_confidences_arity(where=compiled.get("where"), body_confidences=body_confidences)
                compiled["body_confidences"] = body_confidences
            return [compiled]
        if hasattr(derivation, "to_authoring_payload"):
            payload, body_confidences = _authoring_derivation_payload_from_sdk_object(derivation)
        elif isinstance(derivation, dict):
            payload = dict(derivation)
            payload, body_confidences = _normalize_authoring_derivation_payload(payload)
        else:
            raise SDKStoreError(
                "derivation must be SDK Inference object, compiled derivation dict, or authoring derivation payload dict"
            )
        payloads = _expand_authoring_derivation_heads(payload)
        try:
            compiled_payloads: list[dict[str, Any]] = []
            for single_payload in payloads:
                compiled = compile_authoring_derivation_v1(single_payload, schema_ir=self._schema_ir)
                selected_confidences = _coerce_body_confidences(
                    body_confidences,
                    path="$.body_confidences",
                )
                if selected_confidences is not None:
                    _validate_body_confidences_arity(where=compiled.get("where"), body_confidences=selected_confidences)
                    compiled["body_confidences"] = selected_confidences
                compiled_payloads.append(compiled)
            return compiled_payloads
        except Exception as exc:
            raise SDKStoreError(f"invalid derivation input: {exc}") from exc

    def _index_schema(self) -> None:
        pred_index: dict[tuple[str, str], dict[str, Any]] = {}
        for pred in self._schema_ir.get("predicates", []):
            if not isinstance(pred, dict):
                continue
            owner_type = pred.get("owner_type")
            py_field_name = pred.get("py_field_name")
            if isinstance(owner_type, str) and isinstance(py_field_name, str):
                pred_index[(owner_type, py_field_name)] = pred

        for cls in self._classes:
            spec = cls.sdk_entity_spec()
            self._entity_spec_by_class[cls] = spec
            for field_decl in spec.get("fields", []):
                py_name = field_decl["py_name"]
                descriptor = getattr(cls, py_name, None)
                if not isinstance(descriptor, Field):
                    continue
                key = (spec["entity_type"], py_name)
                pred = pred_index.get(key)
                if pred is None:
                    raise SDKStoreError(f"schema predicate not found for {spec['entity_type']}.{py_name}")
                self._field_pred_by_descriptor[descriptor] = pred
                self._field_decl_by_descriptor[descriptor] = field_decl

    def _refresh_schema_state(
        self,
        *,
        classes: list[type[Entity]],
        schema_ir: dict[str, Any],
        schema_digest_value: str,
    ) -> None:
        self._classes = list(classes)
        self._schema_ir = schema_ir
        self._store.schema_ir = schema_ir
        self._schema_digest = schema_digest_value
        self._application_schema_index = build_schema_index(schema_ir)
        self._field_pred_by_descriptor.clear()
        self._field_decl_by_descriptor.clear()
        self._entity_spec_by_class.clear()
        self._index_schema()

    def _preflight_schema_digest_anchors(self, old_digest: str) -> None:
        ledger_digest = self.ledger.get_ledger_meta("schema_digest")
        if ledger_digest is not None and ledger_digest != old_digest:
            raise SDKStoreError(
                f"ledger schema_digest mismatch: expected {old_digest!r}, got {ledger_digest!r}"
            )

        if self._workspace_path is not None:
            if not schema_object_exists_for_workspace(self._workspace_path, old_digest):
                raise SDKStoreError("workspace schema object missing")
            try:
                validate_schema_object_for_workspace(self._workspace_path, self.schema_ir)
            except DatabaseError as exc:
                raise SDKStoreError(f"workspace schema object invalid: {exc}") from exc

    def _update_schema_digest_anchors(
        self,
        *,
        schema_ir: dict[str, Any],
        schema_digest_value: str,
    ) -> None:
        self.ledger.replace_ledger_meta("schema_digest", schema_digest_value)
        if self._workspace_path is not None:
            try:
                write_schema_object_for_workspace(self._workspace_path, schema_ir)
            except DatabaseError as exc:
                raise SDKStoreError(f"workspace schema object update failed: {exc}") from exc

    def _schema_pred_for_field(self, field: Field) -> dict[str, Any]:
        if not isinstance(field, Field):
            raise SDKStoreError("field must be sdk.Field descriptor (e.g. Person.country)")
        pred = self._field_pred_by_descriptor.get(field)
        if pred is None:
            self._raise_if_superseded_entity_class(getattr(field, "sdk_owner_cls", None))
            owner_name = getattr(getattr(field, "sdk_owner_cls", None), "__name__", "<unknown>")
            attr_name = getattr(field, "sdk_attr_name", "<unknown>")
            raise SDKStoreError(f"field is not bound in this SDKStore schema: {owner_name}.{attr_name}")
        return pred

    def _raise_if_superseded_entity_class(self, entity_cls: Any) -> None:
        if not isinstance(entity_cls, type):
            return
        try:
            candidate_spec = entity_cls.sdk_entity_spec()
        except Exception:
            return
        entity_type = candidate_spec.get("entity_type")
        if not isinstance(entity_type, str):
            return
        active_cls = self._active_entity_class_for_type(entity_type)
        if active_cls is not None and active_cls is not entity_cls:
            raise SDKStoreError(
                "schema declaration was superseded; use the post-add class object"
            )

    def _active_entity_class_for_type(self, entity_type: str) -> type[Entity] | None:
        for cls in self._classes:
            try:
                spec = cls.sdk_entity_spec()
            except Exception:
                continue
            if spec.get("entity_type") == entity_type:
                return cls
        return None

    def _rest_terms_for_field(
        self,
        schema_pred: dict[str, Any],
        *,
        value: Any,
    ) -> list[tuple[str, Any]]:
        arg_specs = schema_pred.get("arg_specs")
        if not isinstance(arg_specs, list) or len(arg_specs) != 2:
            raise SDKStoreError("schema predicate arg_specs invalid")
        value_tag = arg_specs[1].get("type_domain")
        if not isinstance(value_tag, str):
            raise SDKStoreError("value type_domain missing")
        return [(value_tag, _coerce_sdk_value_to_tag(value_tag, value))]

def _normalize_view_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise SDKStoreError("view name must be non-empty string")
    return name.strip()


def _field_label_for_pred(schema_pred: dict[str, Any]) -> str:
    owner = schema_pred.get("owner_type")
    name = schema_pred.get("py_field_name")
    if isinstance(owner, str) and owner and isinstance(name, str) and name:
        return f"{owner}.{name}"
    pred_id = schema_pred.get("pred_id")
    return str(pred_id) if pred_id is not None else "<unknown>"


def _build_view_entry(
    name: str,
    *,
    asrt_ids: Iterable[str] | None,
    asrts: Iterable[Any] | None,
) -> FrozenAssertionSet:
    payload_count = sum(value is not None for value in (asrt_ids, asrts))
    if payload_count != 1:
        raise SDKStoreError("provide exactly one view payload: asrt_ids=... or asrts=...")
    if asrts is not None:
        return FrozenAssertionSet(
            name=name,
            asrt_ids=_normalize_asrt_ids_from_records(asrts),
        )
    return FrozenAssertionSet(
        name=name,
        asrt_ids=_normalize_asrt_ids(asrt_ids),
    )


def _normalize_asrt_ids(values: Iterable[str] | None) -> frozenset[str]:
    if values is None:
        raise SDKStoreError("asrt_ids must be iterable[str]")
    if isinstance(values, (str, bytes)):
        raise SDKStoreError("asrt_ids must be iterable[str], not string")
    try:
        items = tuple(values)
    except TypeError as exc:
        raise SDKStoreError("asrt_ids must be iterable[str]") from exc
    for index, value in enumerate(items):
        if not isinstance(value, str) or not value:
            raise SDKStoreError(f"asrt_ids[{index}] must be non-empty string")
    return frozenset(items)


def _normalize_asrt_ids_from_records(records: Iterable[Any]) -> frozenset[str]:
    if isinstance(records, (str, bytes)):
        raise SDKStoreError("asrts must be iterable objects with asrt_id, not string")
    try:
        items = tuple(records)
    except TypeError as exc:
        raise SDKStoreError("asrts must be iterable objects with asrt_id") from exc
    out: list[str] = []
    for index, record in enumerate(items):
        asrt_id = getattr(record, "asrt_id", None)
        if not isinstance(asrt_id, str) or not asrt_id:
            raise SDKStoreError(f"asrts[{index}] must expose non-empty string asrt_id")
        out.append(asrt_id)
    return frozenset(out)


def _assertion_record_by_id(sdk: SDKStore, asrt_id: str) -> Any:
    claim = sdk.ledger.get_claim(asrt_id)
    if claim is None:
        return None
    schema_pred = _schema_pred_by_pred_id(sdk, claim.pred_id)
    from .facade import _assertion_record_from_claim

    return _assertion_record_from_claim(sdk, claim, schema_pred=schema_pred)


def _schema_pred_by_pred_id(sdk: SDKStore, pred_id: str) -> dict[str, Any]:
    for pred in sdk.schema_ir.get("predicates", []):
        if isinstance(pred, dict) and pred.get("pred_id") == pred_id:
            return pred
    raise SDKStoreError(f"schema predicate not found for assertion predicate: {pred_id}")


def _coerce_sdk_value_to_tag(tag: str, value: Any) -> Any:
    if tag == "entity_ref":
        if not isinstance(value, str) or not value.startswith("idref_v1:"):
            raise SDKStoreError("entity_ref value must be canonical idref_v1 token")
        return value
    if tag == "string":
        if not isinstance(value, str):
            raise SDKStoreError("string field expects str")
        return value
    if tag == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SDKStoreError("int field expects int")
        return value
    if tag == "bool":
        if not isinstance(value, bool):
            raise SDKStoreError("bool field expects bool")
        return value
    if tag == "bytes":
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, memoryview):
            return value.tobytes()
        raise SDKStoreError("bytes field expects bytes-like")
    if tag == "time":
        if isinstance(value, bool):
            raise SDKStoreError("time field expects epoch-nanos int or aware datetime")
        if isinstance(value, int):
            return value
        if isinstance(value, datetime):
            if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
                raise SDKStoreError("time datetime must be timezone-aware")
            value_utc = value.astimezone(timezone.utc)
            return int(value_utc.timestamp() * 1_000_000_000)
        raise SDKStoreError("time field expects epoch-nanos int or aware datetime")
    if tag == "uuid":
        if isinstance(value, UUID):
            return str(value).lower()
        if isinstance(value, str):
            return value.lower()
        raise SDKStoreError("uuid field expects UUID or canonical string")
    if tag == "float64":
        if isinstance(value, (float, str)):
            return value
        raise SDKStoreError("float64 field expects float or 0x<16hex> string")
    raise SDKStoreError(f"unsupported type_domain: {tag}")


def _expand_authoring_derivation_heads(payload: dict[str, Any]) -> list[dict[str, Any]]:
    head = payload.get("head")
    if not isinstance(head, list):
        return [dict(payload)]
    if not head:
        raise SDKStoreError("derivation head list must be non-empty", path="$.head")
    raise SDKStoreError("multi-head Inference is not accepted in Track 1; use one Inference per head", path="$.head")


def _authoring_derivation_payload_from_sdk_object(
    derivation: Any,
) -> tuple[dict[str, Any], list[float] | None]:
    where_value = getattr(derivation, "when", None)
    normalized_where, used_branch_wrapper = _normalize_where_branch_wrappers(
        where_value,
        path="$.when",
    )
    if not used_branch_wrapper:
        payload = derivation.to_authoring_payload()
        return _normalize_authoring_derivation_payload(payload)

    payload = _build_authoring_derivation_payload_with_where(
        derivation=derivation,
        normalized_where=normalized_where,
    )
    normalized_payload, normalized_confidences = _normalize_authoring_derivation_payload(payload)
    return normalized_payload, normalized_confidences


def _public_semantics_engine(value: Any) -> str | None:
    if isinstance(value, SemanticsProfile):
        return value.engine
    if isinstance(value, ProbLogConfig):
        return value.engine
    if isinstance(value, PyReasonConfig):
        return value.engine
    return None


@dataclass(frozen=True)
class _SemanticsLoweringContext:
    name: str
    case_indexes: Mapping[str, int]
    known_rule_ids: frozenset[str]
    atom_ids: tuple[str, ...] = ()
    branch_specific_allowed: bool = True


def _preview_public_semantics(value: ProbLogConfig | PyReasonConfig) -> SemanticsProfile:
    if isinstance(value, ProbLogConfig):
        rule_params = _rule_param_entries(value.rule_params, known_rule_ids=None)
        return SemanticsProfile(
            name=value.name or "problog",
            engine="problog",
            rule_projection={"sdk_rule_params": rule_params} if rule_params else {},
            uncertainty_projection=dict(value.uncertainty_projection),
            fallback=value.fallback,
        )
    if isinstance(value, PyReasonConfig):
        rule_entries: list[dict[str, Any]] = []
        rule_entries.extend(_preview_pyreason_bound_entries(value))
        for case_index, interval in _preview_case_bounds(value.case_bounds):
            rule_entries.append({"target": f"branch:{case_index}", "kind": "interval", "value": list(interval)})
        if value.timestep_delay:
            rule_entries.append({"target": "rule", "kind": "timestep_delay", "value": value.timestep_delay})
        rule_projection: dict[str, list[dict[str, Any]]] = {}
        if rule_entries:
            rule_projection["pyreason"] = rule_entries
        rule_params = _rule_param_entries(value.rule_params, known_rule_ids=None)
        if rule_params:
            rule_projection["sdk_rule_params"] = rule_params
        return SemanticsProfile(
            name=value.name or "pyreason",
            engine="pyreason",
            iteration_count=_pyreason_iteration_count_carrier(value),
            rule_projection=rule_projection,
            temporal_projection=dict(value.temporal_projection),
            uncertainty_projection=dict(value.uncertainty_projection),
            fallback=value.fallback,
        )
    raise SDKStoreError("unsupported public semantics wrapper")


def _lower_public_semantics(value: Any, *, derivation: Any) -> SemanticsProfile:
    context = _semantics_lowering_context(derivation)
    if isinstance(value, ProbLogConfig):
        entries: list[dict[str, Any]] = []
        if value.case_probabilities and not context.branch_specific_allowed:
            raise SDKStoreError(
                "ProbLogConfig.case_probabilities requires RuleExpr branches or legacy Inference branches; "
                "single application Rule inputs only accept empty case_probabilities"
            )
        for branch_id, probability in value.case_probabilities.items():
            case_index = context.case_indexes.get(branch_id)
            if case_index is None:
                raise SDKStoreError(f"unknown branch id {branch_id!r} for ProbLogConfig.case_probabilities")
            entries.append(
                {
                    "target": f"branch:{case_index}",
                    "kind": "branch_probability",
                    "value": probability,
                }
            )
        rule_projection: dict[str, list[dict[str, Any]]] = {}
        if entries:
            rule_projection["problog"] = entries
        rule_params = _rule_param_entries(value.rule_params, known_rule_ids=context.known_rule_ids)
        if rule_params:
            rule_projection["sdk_rule_params"] = rule_params
        return SemanticsProfile(
            name=value.name or _default_semantics_name(context, engine="problog"),
            engine="problog",
            rule_projection=rule_projection,
            uncertainty_projection=dict(value.uncertainty_projection),
            fallback=value.fallback,
        )
    if isinstance(value, PyReasonConfig):
        rule_entries: list[dict[str, Any]] = []
        rule_entries.extend(_lower_pyreason_bound_entries(value, context=context))
        if value.case_bounds and not context.branch_specific_allowed:
            raise SDKStoreError(
                "PyReasonConfig.case_bounds requires RuleExpr branches or legacy Inference branches; "
                "single application Rule inputs only accept empty case_bounds"
            )
        for branch_id, interval in value.case_bounds.items():
            case_index = context.case_indexes.get(branch_id)
            if case_index is None:
                known = ", ".join(sorted(context.case_indexes)) or "<none>"
                raise SDKStoreError(
                    f"case_bounds contains unknown branch id {branch_id!r}; known branch ids: {known}"
                )
            rule_entries.append({"target": f"branch:{case_index}", "kind": "interval", "value": list(interval)})
        if value.timestep_delay:
            rule_entries.append({"target": "rule", "kind": "timestep_delay", "value": value.timestep_delay})
        rule_projection = {}
        if rule_entries:
            rule_projection["pyreason"] = rule_entries
        rule_params = _rule_param_entries(value.rule_params, known_rule_ids=context.known_rule_ids)
        if rule_params:
            rule_projection["sdk_rule_params"] = rule_params
        return SemanticsProfile(
            name=value.name or _default_semantics_name(context, engine="pyreason"),
            engine="pyreason",
            iteration_count=_pyreason_iteration_count_carrier(value),
            rule_projection=rule_projection,
            temporal_projection=dict(value.temporal_projection),
            uncertainty_projection=dict(value.uncertainty_projection),
            fallback=value.fallback,
        )
    raise SDKStoreError("unsupported public semantics wrapper")


def _preview_case_bounds(
    case_bounds: dict[str, tuple[float, float]],
) -> list[tuple[int, tuple[float, float]]]:
    preview: list[tuple[int, tuple[float, float]]] = []
    for idx, interval in enumerate(case_bounds.values()):
        preview.append((idx, interval))
    return preview


def _preview_pyreason_bound_entries(value: PyReasonConfig) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    head_interval = value.derived_bound if value.derived_bound is not None else value.head_bound
    if head_interval is not None:
        entries.append({"target": "head:0", "kind": "interval", "value": list(head_interval)})
    for atom_id, interval in value.atom_bounds.items():
        _rule_id, condition_index = _parse_pyreason_atom_bound_id(
            atom_id,
            field_name="PyReasonConfig.atom_bounds",
        )
        entries.append(
            {
                "target": f"body_atom:0:{condition_index}",
                "kind": "interval_threshold",
                "value": list(interval),
            }
        )
    return entries


def _lower_pyreason_bound_entries(
    value: PyReasonConfig,
    *,
    context: _SemanticsLoweringContext,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    head_interval = value.derived_bound if value.derived_bound is not None else value.head_bound
    if head_interval is not None:
        entries.append({"target": "head:0", "kind": "interval", "value": list(head_interval)})
    if not value.atom_bounds:
        return entries
    if not context.atom_ids:
        raise SDKStoreError(
            "PyReasonConfig.atom_bounds requires application Rule atom ids; "
            "use direct SemanticsProfile.rule_projection.pyreason body_atom targets for legacy branched inputs"
        )
    atom_index_by_id = {atom_id: idx for idx, atom_id in enumerate(context.atom_ids)}
    known = ", ".join(context.atom_ids)
    for atom_id, interval in value.atom_bounds.items():
        _parse_pyreason_atom_bound_id(atom_id, field_name="PyReasonConfig.atom_bounds")
        condition_index = atom_index_by_id.get(atom_id)
        if condition_index is None:
            raise SDKStoreError(
                f"PyReasonConfig.atom_bounds contains unknown atom id {atom_id!r}; known atom ids: {known}"
            )
        entries.append(
            {
                "target": f"body_atom:0:{condition_index}",
                "kind": "interval_threshold",
                "value": list(interval),
            }
        )
    return entries


def _parse_pyreason_atom_bound_id(value: str, *, field_name: str) -> tuple[str, int]:
    rule_id, marker, atom_index_text = value.rpartition(":atom_")
    if not rule_id or marker != ":atom_" or not atom_index_text:
        raise SDKStoreError(f"{field_name} keys must use <rule_id>:atom_<index>")
    if not atom_index_text.isdigit():
        raise SDKStoreError(f"{field_name} keys must use non-negative condition indexes")
    return (rule_id, int(atom_index_text))


def _pyreason_iteration_count_carrier(value: PyReasonConfig) -> int | None:
    mode = value.temporal_projection.get("mode", "none")
    if mode != "none" and value.iteration_count == 1:
        return None
    return value.iteration_count


def _semantics_profile_preview(profile: SemanticsProfile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "version": profile.version,
        "engine": profile.engine,
        "fallback": profile.fallback,
        "iteration_count": profile.iteration_count,
        "rule_projection": profile.rule_projection,
        "engine_options": profile.engine_options,
        "uncertainty_projection": profile.uncertainty_projection,
        "temporal_projection": profile.temporal_projection,
        "certainty_projection": profile.certainty_projection,
        "output_readback": profile.output_readback,
    }


def _rule_param_entries(
    rule_params: Mapping[str, Mapping[str, Any]],
    *,
    known_rule_ids: frozenset[str] | None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for rule_id in sorted(rule_params):
        if known_rule_ids is not None and rule_id not in known_rule_ids:
            known = ", ".join(sorted(known_rule_ids)) or "<none>"
            raise SDKStoreError(f"rule_params contains unknown Rule.id {rule_id!r}; known Rule ids: {known}")
        entries.append({"target": f"rule:{rule_id}", "kind": "rule_params", "value": dict(rule_params[rule_id])})
    return entries


def _semantics_lowering_context(derivation: Any) -> _SemanticsLoweringContext:
    if isinstance(derivation, _SemanticsLoweringContext):
        return derivation
    if isinstance(derivation, ApplicationRule):
        return _SemanticsLoweringContext(
            name=derivation.id,
            case_indexes={},
            known_rule_ids=frozenset({derivation.id}),
            atom_ids=tuple(derivation.atom_ids),
            branch_specific_allowed=False,
        )
    case_indexes = _branch_id_index_for_derivation(derivation)
    derivation_id = getattr(derivation, "id", None)
    known_rule_ids = frozenset({derivation_id}) if isinstance(derivation_id, str) and derivation_id else frozenset()
    return _SemanticsLoweringContext(
        name=derivation_id if isinstance(derivation_id, str) and derivation_id else "semantics",
        case_indexes=case_indexes,
        known_rule_ids=known_rule_ids,
    )


def _semantics_context_for_ruleexpr_plan(
    source: Any,
    *,
    head: ApplicationRule,
    plan: Any,
) -> _SemanticsLoweringContext:
    if isinstance(source, ApplicationRule):
        return _SemanticsLoweringContext(
            name=source.id,
            case_indexes={},
            known_rule_ids=frozenset({source.id, head.id}),
            atom_ids=tuple(source.atom_ids),
            branch_specific_allowed=False,
        )
    case_indexes = {branch.branch_id: index for index, branch in enumerate(plan.branches)}
    known_rule_ids = {head.id}
    known_rule_ids.update(binding.rule_id for binding in plan.occurrence_map)
    return _SemanticsLoweringContext(
        name=head.id,
        case_indexes=case_indexes,
        known_rule_ids=frozenset(rule_id for rule_id in known_rule_ids if rule_id),
    )


def _branch_id_index_for_derivation(derivation: Any) -> dict[str, int]:
    where = getattr(derivation, "when", None)
    branches = _inspect_where_branches(where)
    out: dict[str, int] = {}
    for branch in branches:
        branch_id = branch["id"]
        fallback_id = branch["fallback_id"]
        index = branch["index"]
        if isinstance(branch_id, str) and isinstance(index, int):
            out[branch_id] = index
        if isinstance(fallback_id, str) and isinstance(index, int):
            out[fallback_id] = index
    return out


def _default_semantics_name(context: Any, *, engine: str) -> str:
    if isinstance(context, _SemanticsLoweringContext):
        if context.name:
            return f"{context.name}:{engine}"
        return engine
    derivation_id = getattr(context, "id", None)
    if isinstance(derivation_id, str) and derivation_id:
        return f"{derivation_id}:{engine}"
    return engine


def _inspect_rule_or_inference(obj: Any) -> dict[str, Any]:
    from .dsl.rule import Inference as SDKInference
    from .dsl.rule import Rule as SDKRule

    if isinstance(obj, SDKRule):
        return {
            "kind": "Rule",
            "id": obj.id,
            "version": obj.version,
            "heads": [],
            "branches": _inspect_where_branches(obj.where),
        }
    if isinstance(obj, SDKInference):
        return {
            "kind": "Inference",
            "id": obj.id,
            "version": obj.version,
            "heads": [head.to_authoring_head() for head in obj.heads],
            "branches": _inspect_where_branches(obj.when),
        }
    raise SDKStoreError("rules.inspect(...) expects SDK Rule or Inference")


def _inspect_where_branches(where: Any) -> list[dict[str, Any]]:
    if not isinstance(where, list) or not where:
        raise SDKStoreError("rules.inspect(...) requires non-empty where")

    if all(isinstance(item, Case) for item in where):
        raw_branches = [(item.id, list(item.atoms)) for item in where]
    elif any(isinstance(item, Case) for item in where):
        raise SDKStoreError("where/case cannot mix Case(...) with bare cases")
    elif _where_items_are_atoms(where):
        raw_branches = [(None, list(where))]
    else:
        raw_branches = [(None, list(branch)) for branch in where if isinstance(branch, list)]
        if len(raw_branches) != len(where) or not raw_branches:
            raise SDKStoreError("rules.inspect(...) where must be atoms or branch lists")

    out: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    for idx, (explicit_id, atoms) in enumerate(raw_branches):
        fallback_id = f"c{idx}"
        branch_id = explicit_id if explicit_id is not None else fallback_id
        if branch_id in seen_ids:
            raise SDKStoreError(f"duplicate Case.id {branch_id!r} in inspected when")
        seen_ids[branch_id] = idx
        out.append(
            {
                "id": branch_id,
                "fallback_id": fallback_id,
                "is_explicit_id": explicit_id is not None,
                "index": idx,
                "atom_count": len(atoms),
                "atoms": _lower_inspect_atoms(atoms),
                "atom_ids": [
                    f"{fallback_id}.c{condition_idx}"
                    for condition_idx, _condition in enumerate(atoms)
                ],
            }
        )
    return out


def _where_items_are_atoms(where: list[Any]) -> bool:
    return bool(where) and all(not isinstance(item, list) and not isinstance(item, Case) for item in where)


def _lower_inspect_atoms(atoms: list[Any]) -> list[Any]:
    from .dsl.expr import lower_where

    return list(lower_where(atoms))


def _normalize_authoring_derivation_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[float] | None]:
    normalized = dict(payload)
    if "body_confidences" in normalized:
        raise SDKStoreError(
            "body_confidences is not accepted in public derivation payloads; "
            "use ProbLogRuleExt.case_probabilities or future SemanticsProfile.rule_projection.problog",
            path="$.body_confidences",
        )

    for field_name, field_path in (("where", "$.where"), ("body", "$.body")):
        if field_name not in normalized:
            continue
        field_value, used_branch_wrapper = _normalize_where_branch_wrappers(
            normalized[field_name],
            path=field_path,
        )
        if used_branch_wrapper:
            normalized[field_name] = field_value
    return normalized, None


def _build_authoring_derivation_payload_with_where(
    *,
    derivation: Any,
    normalized_where: Any,
) -> dict[str, Any]:
    from .dsl.expr import lower_where

    derivation_id = getattr(derivation, "id", None)
    if not isinstance(derivation_id, str) or not derivation_id:
        raise SDKStoreError("derivation.id must be non-empty string", path="$.derivation_id")
    version = getattr(derivation, "version", None)
    if not isinstance(version, str) or not version:
        raise SDKStoreError("derivation.version must be non-empty string", path="$.version")

    payload: dict[str, Any] = {
        "derivation_id": derivation_id,
        "version": version,
        "where": lower_where(normalized_where),
    }

    heads = getattr(derivation, "heads", None)
    if isinstance(heads, list) and heads:
        payload["head"] = heads[0].to_authoring_head() if len(heads) == 1 else [head.to_authoring_head() for head in heads]

    emits = getattr(derivation, "emits", None)
    if emits is not None:
        target = getattr(emits, "target", None)
        vars_ = getattr(emits, "vars", None)
        if not isinstance(target, str) or not target:
            raise SDKStoreError("derivation.emits.target must be non-empty string", path="$.emits.target")
        if not isinstance(vars_, list):
            raise SDKStoreError("derivation.emits.vars must be list", path="$.emits.vars")
        payload["emits"] = {
            "target": target,
            "vars": [_lower_derivation_head_var(item) for item in vars_],
        }

    status = getattr(derivation, "status", None)
    if status is not None:
        payload["status"] = status

    description = getattr(derivation, "description", None)
    if description is not None:
        payload["description"] = description

    tags = getattr(derivation, "tags", None)
    if tags is not None:
        payload["tags"] = list(tags) if isinstance(tags, list) else tags

    return payload


def _lower_derivation_head_var(value: Any) -> Any:
    token = getattr(value, "token", None)
    if isinstance(token, str):
        return token
    return value


def _normalize_where_branch_wrappers(
    raw_where: Any,
    *,
    path: str,
) -> tuple[Any, bool]:
    if not isinstance(raw_where, list) or not raw_where:
        return raw_where, False

    has_branch_wrapper = any(isinstance(item, Case) for item in raw_where)
    if not has_branch_wrapper:
        return raw_where, False
    if not all(isinstance(item, Case) for item in raw_where):
        raise SDKStoreError("where/case cannot mix Case(...) with bare cases", path=path)

    branches: list[list[Any]] = []
    for idx, branch in enumerate(raw_where):
        atoms = list(branch.atoms)
        if not atoms:
            raise SDKStoreError("Case.atoms must be non-empty list", path=f"{path}[{idx}]")
        branches.append(atoms)
    return branches, True


def _coerce_body_confidences(raw_value: Any, *, path: str) -> list[float] | None:
    if raw_value is None:
        return None
    if not isinstance(raw_value, list) or not raw_value:
        raise SDKStoreError("body_confidences must be non-empty list[float] when provided", path=path)

    out: list[float] = []
    for idx, value in enumerate(raw_value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SDKStoreError("body_confidences entries must be float in (0,1]", path=f"{path}[{idx}]")
        normalized = float(value)
        if normalized <= 0.0 or normalized > 1.0:
            raise SDKStoreError("body_confidences entries must be within (0,1]", path=f"{path}[{idx}]")
        out.append(normalized)
    return out


def _resolve_compiled_derivation_mode(
    compiled_plans: list[dict[str, Any]],
    *,
    explicit_mode: str | None,
) -> str:
    if explicit_mode is not None:
        return explicit_mode
    modes = {
        str(compiled.get("mode", "native"))
        for compiled in compiled_plans
    }
    if len(modes) != 1:
        raise SDKStoreError(
            "compiled derivation plans must use the same mode unless evaluate(mode=...) is provided",
            path="$.mode",
        )
    return next(iter(modes))


def _rule_expr_adapter_support_error(support: RuleExprAdapterSupport) -> SDKStoreError:
    feature = support.unsupported_feature or "unknown"
    source = support.rejection_source or "unknown"
    alternatives = ", ".join(support.alternative_engines) if support.alternative_engines else "none known"
    return SDKStoreError(
        "evaluate(rule_expr, ...) unsupported for "
        f"engine='{support.engine}': unsupported feature '{feature}' from {source}; "
        f"supported alternative engines: {alternatives}"
    )


def _compiled_derivation_plan_to_application(
    compiled: dict[str, Any],
    *,
    mode: str,
    engine_options: dict[str, Any] | None,
) -> CompiledDerivationPlan:
    body_confidences = _coerce_body_confidences(
        compiled.get("body_confidences"),
        path="$.body_confidences",
    )
    resolved_engine_ext = _resolve_engine_ext_for_evaluate_plan(
        mode=mode,
        where=compiled.get("where"),
        compiled_engine_ext=compiled.get("engine_ext"),
        legacy_body_confidences=body_confidences,
    )
    return CompiledDerivationPlan(
        derivation_id=compiled["derivation_id"],
        version=compiled["version"],
        body_ir=list(compiled["where"]),
        heads=(
            CompiledHeadCall(
                target_pred_id=compiled["target_pred_id"],
                head_var_names=tuple(compiled["head_vars"]),
            ),
        ),
        head_spec=compiled.get("head"),
        engine_ext=resolved_engine_ext,
        engine_options=dict(engine_options or {}),
    )


def _application_plans_from_compiled_dicts(
    compiled_plans: Sequence[dict[str, Any]],
    *,
    mode: str,
) -> tuple[CompiledDerivationPlan, ...]:
    return tuple(
        _compiled_derivation_plan_to_application(
            compiled,
            mode=mode,
            engine_options=None,
        )
        for compiled in compiled_plans
    )


def _head_rule_for_compiled_plans(plans: Sequence[CompiledDerivationPlan]) -> ApplicationRule:
    if not plans:
        raise SDKStoreError("cannot build EvaluateResult head from empty compiled plans")
    first = plans[0]
    if not first.heads:
        raise SDKStoreError("cannot build EvaluateResult head from compiled plan without heads")
    head = first.heads[0]
    if not head.head_var_names:
        raise SDKStoreError("cannot build EvaluateResult head from compiled plan without head variables")
    vars_by_port = tuple(Var(name) for name in head.head_var_names)
    ports: dict[str, Var] = {}
    for idx, var in enumerate(vars_by_port):
        base = var.name.removeprefix("$") or f"arg{idx}"
        port_name = base if base not in ports else f"{base}_{idx}"
        ports[port_name] = var
    return ApplicationRule(
        id=head.target_pred_id,
        when=(PredAtom(head.target_pred_id, list(vars_by_port)),),
        ports=ports,
    )


def _initial_probe_bindings_for_row(row: Any, plan: RuleExprLoweringPlan) -> dict[str, Any]:
    row_bindings = getattr(row, "bindings", None)
    if not isinstance(row_bindings, Mapping):
        return {}
    seed_names_by_port = probe_seed_vars_by_head_port(plan)
    out: dict[str, Any] = {}
    for port_name, value in row_bindings.items():
        seed_names = seed_names_by_port.get(port_name, ())
        if not seed_names:
            continue
        public_value = _public_term_value(value)
        for seed_name in seed_names:
            out[seed_name] = public_value
    return out


def _initial_probe_bindings_from_port_values(
    port_values: Mapping[str, Any], plan: RuleExprLoweringPlan
) -> dict[str, Any]:
    """Base native seed ``{seed_var: value}`` from a ``{port_name: public_value}``
    pin map — the closed_head_false twin of ``_initial_probe_bindings_for_row``.
    Pin values are already public idref/scalar tokens (minted via ``_ref`` for
    seed-parity), so no ``_public_term_value`` coercion is applied. ``probe_native``
    expands this base seed transitively over the join / head-link eq-atoms."""
    seed_names_by_port = probe_seed_vars_by_head_port(plan)
    out: dict[str, Any] = {}
    for port_name, value in port_values.items():
        for seed_name in seed_names_by_port.get(str(port_name), ()):
            out[seed_name] = value
    return out


def _public_bindings_for_row(row: Any) -> dict[str, Any]:
    row_bindings = getattr(row, "bindings", None)
    if not isinstance(row_bindings, Mapping):
        return {}
    return {str(port_name): _public_term_value(value) for port_name, value in row_bindings.items()}


def _normalize_problog_goal_value(value: Any) -> str:
    text = str(value).strip()
    if len(text) >= 2 and ((text[0] == "'" and text[-1] == "'") or (text[0] == '"' and text[-1] == '"')):
        return text[1:-1]
    return text


def _claim_rest_terms_match_values(rest_terms: Sequence[tuple[str, Any]], values: Sequence[str]) -> bool:
    if len(rest_terms) != len(values):
        return False
    for (_tag, value), expected in zip(rest_terms, values, strict=True):
        if str(value) != str(expected):
            return False
    return True


def _claim_meta_value(ledger: Ledger, asrt_id: str, key: str) -> Any:
    rows = ledger.find_meta(asrt_id=asrt_id, key=key)
    if not rows:
        return None
    return rows[-1].value


def _rule_expr_rules_by_id(source: Any, *, head: ApplicationRule) -> dict[str, ApplicationRule]:
    out: dict[str, ApplicationRule] = {head.id: head}
    try:
        expr = _coerce_rule_expr_operand(source)
    except RuleExprError:
        if isinstance(source, ApplicationRule):
            out[source.id] = source
        return out
    for operand in _iter_rule_operands(expr):
        out[operand.rule.id] = operand.rule
    return out


def _souffle_support_artifact_to_evidence_graph(
    artifact: ProofReceipt,
    *,
    row: Any,
    result: EvaluateResult,
    metadata: Mapping[str, Any],
) -> EvidenceGraph:
    body_atoms: list[EvidenceAtom] = []
    for witness in artifact.pred_witnesses:
        pred_id = _condition_pred_id(witness.pred_condition_key)
        source = Source(
            ref=f"souffle:{row.row_id}:{witness.pred_condition_key}",
            value=tuple(witness.asrt_ids),
            meta={"pred_condition_key": witness.pred_condition_key, "asrt_ids": witness.asrt_ids},
        )
        body_atoms.append(
            EvidenceAtom(
                form=Fact(predicate=pred_id, terms=()),
                verdict=Holds(support=(source,)),
                atom_id=f"souffle:{row.row_id}:{witness.pred_condition_key}",
                repr_text=_souffle_witness_repr(pred_id, witness.asrt_ids),
            )
        )
    for step in artifact.non_fact_steps:
        source = Source(
            ref=f"souffle:{row.row_id}:{step.step_key}",
            value=step.status,
            meta={"step_key": step.step_key, "kind": step.kind, "details": dict(step.details)},
        )
        body_atoms.append(
            EvidenceAtom(
                form=Fact(predicate=step.kind, terms=(Const(step.status),)),
                verdict=Holds(support=(source,)),
                atom_id=f"souffle:{row.row_id}:{step.step_key}",
                repr_text=f"{step.kind}: {step.status}",
            )
        )

    rules = (
        EvidenceRule(
            occurrence_alias=result.head.id,
            rule_id=result.head.id,
            role="head",
            status="holds",
            ports=getattr(row, "bindings", {}),
            atoms=(),
        ),
        EvidenceRule(
            occurrence_alias=f"souffle:{row.row_id}:body",
            rule_id=result.head.id,
            role="body",
            status="holds",
            ports=binding_dict_from_items(artifact.binding_items),
            atoms=tuple(body_atoms),
        ),
    )
    return EvidenceGraph(
        graph_id=f"{result.result_id}:{row.row_id}",
        engine=result.engine,
        layout_hint=LAYOUT_TREE,
        subject_binding=getattr(row, "bindings", {}),
        paths=(
            EvidenceTree(
                tree_id=row.row_id,
                status="holds",
                rules=rules,
                joins=(),
                certainty=getattr(row, "certainty", None),
                metadata={"support_kind": artifact.kind, "source": "souffle_proof_receipt"},
            ),
        ),
        certainty=getattr(row, "certainty", None),
        metadata=dict(metadata),
    )


def _condition_pred_id(condition_key: str) -> str:
    return condition_key.split(":", 1)[1] if ":" in condition_key else condition_key


def _souffle_witness_repr(pred_id: str, asrt_ids: Sequence[str]) -> str:
    if not asrt_ids:
        return f"{pred_id} supported by souffle witness"
    return f"{pred_id} supported by {', '.join(asrt_ids)}"


def _compiled_plan_digest_payload(plan: CompiledDerivationPlan) -> dict[str, Any]:
    return {
        "body_ir": [repr(atom) for atom in plan.body_ir],
        "derivation_id": plan.derivation_id,
        "engine_ext": repr(plan.engine_ext) if plan.engine_ext is not None else None,
        "engine_options": _evaluate_digest_safe(plan.engine_options),
        "head_spec": _evaluate_digest_safe(plan.head_spec),
        "heads": [
            {
                "head_var_names": tuple(head.head_var_names),
                "target_pred_id": head.target_pred_id,
            }
            for head in plan.heads
        ],
        "version": plan.version,
    }


def _rule_set_entries_for_result(
    plans: Sequence[CompiledDerivationPlan],
    *,
    head: ApplicationRule,
) -> tuple[tuple[str, str], ...]:
    entries: list[tuple[str, str]] = [(f"head:{head.id}", head.content_digest)]
    for plan in plans:
        content_digest = sha256_hex(
            canonical_bytes_for_evaluate(
                "evaluate_compiled_plan_rule_set_entry_v1",
                _compiled_plan_digest_payload(plan),
            )
        )
        entries.append((f"plan:{plan.derivation_id}:{plan.version}", content_digest))
    return tuple(entries)


def _evaluate_digest_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, tuple):
        return tuple(_evaluate_digest_safe(item) for item in value)
    if isinstance(value, list):
        return [_evaluate_digest_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): _evaluate_digest_safe(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    return repr(value)


def _view_snapshot_asrt_id_for_claim(claim: Any) -> str:
    asrt_id = getattr(claim, "asrt_id", None)
    if isinstance(asrt_id, str) and re.fullmatch(r"asrt:[0-9a-f]{64}", asrt_id):
        return asrt_id
    return "asrt:" + sha256_hex(
        canonical_bytes_for_evaluate(
            "sdk_evaluate_view_claim_asrt_v1",
            {
                "asrt_id": asrt_id,
                "e_ref": getattr(claim, "e_ref", None),
                "pred_id": getattr(claim, "pred_id", None),
                "rest_terms": getattr(claim, "rest_terms", None),
            },
        )
    )


def _validate_body_confidences_arity(*, where: Any, body_confidences: list[float]) -> None:
    branch_count = 1
    if isinstance(where, list) and where and all(isinstance(item, list) for item in where):
        branch_count = len(where)
    if len(body_confidences) != branch_count:
        raise SDKStoreError(
            "body_confidences length must match where branch count",
            path="$.body_confidences",
        )


def _resolve_engine_ext_for_evaluate_plan(
    *,
    mode: Any,
    where: Any,
    compiled_engine_ext: object | None,
    legacy_body_confidences: list[float] | None,
) -> object | None:
    if mode != "problog":
        return compiled_engine_ext

    from factgraph.adapters.problog.rule_ext import resolve_problog_engine_ext

    return resolve_problog_engine_ext(
        where=where,
        engine_ext=compiled_engine_ext,
        legacy_body_confidences=legacy_body_confidences,
    )


# Post-L SDK ergonomics redesign (locked at §5.3 / §5.7) — `FactGraph` is
# the canonical user-facing entrypoint name. Literal alias of `SDKStore`
# per §5.7 non-commitment #1 ("NOT a replacement of `SDKStore`"); both
# names resolve to the same class. `SDKStore` stays as the canonical
# implementation behind the `FactGraph` taxonomy and remains permanently
# callable per §5.4 Option 2 lock.
FactGraph = SDKStore
