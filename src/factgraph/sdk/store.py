from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import warnings
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from factgraph.application import apply_write_plan, plan_write_command
from factgraph.application.schema_mutation_runtime import (
    SchemaAddResult,
    add_schema_classes as app_add_schema_classes,
)
from factgraph.application.workspace_runtime import load_workspace as app_load_workspace
from factgraph.application.workspace_runtime import resolve_workspace_paths
from factgraph.application.workspace_runtime import save_workspace as app_save_workspace
from factgraph.application.derivation_runtime import evaluate_derivation_plans
from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DerivationEvaluateRequest,
    EntityRef as AppEntityRef,
    EntitySelector as AppEntitySelector,
    EntityWriteCommand,
    ErrorDTO,
    FieldMutation,
    FieldPath,
)
from factgraph.application.schema_runtime import build_schema_index, entity_type_from_ref
from factgraph.authoring.derivations import compile_authoring_derivation_v1
from factgraph.authoring.registry_fs import FileAuthoringRegistry
from factgraph.authoring.rules import compile_authoring_rule_v1
from factgraph.core.derivation.accept import AcceptOptions, AcceptRequest, AcceptResult
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import WriteProtocolError, retract_by_asrt
from factgraph.core.semantics import SemanticsProfile, inspect_semantics_profile
from factgraph.core.schema.schema_ir import schema_digest
from factgraph.adapters.souffle.package import ExportOptions, export_package
from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.rules.rule_ir import RuleRegistry, RuleSpec, run_rule
from factgraph.core.store._artifact_sidecar import FileArtifactSidecar
from factgraph.adapters.souffle.runner import run_package
from factgraph.core.store.database import (
    AssertionInput,
    CommitResult,
    Database,
    DatabaseError,
    schema_object_exists_for_workspace,
    validate_schema_object_for_workspace,
    write_schema_object_for_workspace,
)
from factgraph.core.store.runtime import Store
from factgraph.core.store.ledger import Ledger

from .compile import compile_schema_from_classes
from .dsl.branch import Branch
from .error_codes import (
    INVALID_ROW_FORMAT,
    QUERY_INVALID_ROW_FORMAT,
)
from .errors import CardinalityError, EntityNotFoundError, FrozenSnapshotError, SDKStoreError
from .query_lower import QueryPlan, lower_query
from .query_runtime import execute_query_plan
from .schema import Entity, Field
from .semantics import ProbLogSemantics, PyReasonSemantics

if TYPE_CHECKING:
    from factgraph.application.protocol import (
        CheckResult,
        DiagnoseResult,
        FactOverlayCheckResult,
        ProofFrameRecheckResult,
        RuleAddConditionResult,
        RuleDisableResult,
        RuleLiteralReplaceResult,
        WhyNotUniverseResult,
    )
    from factgraph.audit.proof_frame_diff import ProofFrameDiff


@dataclass(frozen=True)
class FrozenAssertionView:
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
    "view",
    "workspace_path",
}
_ATTACHED_WRITE_ERROR = (
    "attached FactGraph runtimes route writes only through fg.commit_assertions(...); "
    "{method_name} is not available on attached runtimes"
)
class _SDKViewsManager:
    """Read-only namespace for named frozen assertion-id selections.

    `fg.views` no longer stores read policies and has no built-in
    `default` entry. The name `default` is just another user-defined frozen
    assertion view name when callers create it.
    """

    def __init__(self, sdk: "SDKStore") -> None:
        # Read-only attribute boundary per post-L redesign §5.4 lock.
        # Internal init bypasses ``__setattr__`` via ``object.__setattr__``;
        # external assignment (``fg.views.foo = ...``) raises
        # ``FrozenSnapshotError``. Dict mutation against ``self._views``
        # via ``create`` / ``update`` / ``delete`` is unaffected (it
        # mutates the dict, not the attribute).
        object.__setattr__(self, "_sdk", sdk)
        object.__setattr__(self, "_views", {})

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.views namespace is read-only")

    def create(
        self,
        name: str,
        *,
        asrt_ids: Iterable[str] | None = None,
        asrts: Iterable[Any] | None = None,
    ) -> FrozenAssertionView:
        """Create a named frozen assertion view.

        A view stores assertion ids only. It does not store a read policy and
        it is not included in `fg.save(...)` workspace persistence.
        """
        self._sdk._reject_attached_write("fg.views.create")
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
    ) -> FrozenAssertionView:
        """Replace the assertion ids for an existing frozen view."""
        self._sdk._reject_attached_write("fg.views.update")
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
        """Delete a named frozen assertion view."""
        self._sdk._reject_attached_write("fg.views.delete")
        normalized = _normalize_view_name(name)
        if normalized not in self._views:
            raise SDKStoreError(f"view not found: {normalized}")
        self._views.pop(normalized, None)

    def get(self, name: str) -> FrozenAssertionView:
        """Return a named frozen assertion view."""
        normalized = _normalize_view_name(name)
        if normalized not in self._views:
            raise SDKStoreError(f"view not found: {normalized}")
        return self._views[normalized]

    def list(self) -> dict[str, FrozenAssertionView]:
        """Return all frozen assertion views keyed by view name."""
        return {name: spec for name, spec in self._views.items()}


class _SDKAssertionsManager:
    """Read-only namespace manager for graph-scoped assertion records."""

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.assertions namespace is read-only")

    def by_id(self, asrt_id: str) -> Any:
        if not isinstance(asrt_id, str) or not asrt_id:
            raise SDKStoreError("fg.assertions.by_id(asrt_id) expects non-empty string")
        return _assertion_record_by_id(self._sdk, asrt_id)

    def by_ids(self, asrt_ids: Iterable[str]) -> Any:
        if isinstance(asrt_ids, (str, bytes)):
            raise SDKStoreError("fg.assertions.by_ids(asrt_ids) expects iterable[str], not string")
        try:
            normalized = tuple(asrt_ids)
        except TypeError as exc:
            raise SDKStoreError("fg.assertions.by_ids(asrt_ids) expects iterable[str]") from exc
        for value in normalized:
            if not isinstance(value, str) or not value:
                raise SDKStoreError("fg.assertions.by_ids(asrt_ids) expects non-empty string ids")

        from .facade import AssertionRecordSet

        records = []
        for asrt_id in sorted(set(normalized)):
            record = _assertion_record_by_id(self._sdk, asrt_id)
            if record is not None:
                records.append(record)
        return AssertionRecordSet(records)

    def active(self) -> Any:
        from .facade import AssertionRecordSet

        return AssertionRecordSet(record for record in self.all() if record.is_active)

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

        from .facade import FieldAssertions, _assertion_record_from_claim, _claim_sort_key

        claims = self._sdk.ledger.find_claims(pred_id=pred_id)
        history_records = tuple(
            _assertion_record_from_claim(self._sdk, claim, schema_pred=schema_pred)
            for claim in sorted(claims, key=lambda claim: _claim_sort_key(self._sdk, claim))
        )
        return FieldAssertions(
            field_name=str(getattr(field, "sdk_attr_name", schema_pred.get("py_field_name", ""))),
            cardinality=str(schema_pred.get("cardinality", getattr(field, "cardinality", "single"))),
            active_records=tuple(record for record in history_records if record.is_active),
            history_records=history_records,
        )


class _SDKSchemaManager:
    """Read-only namespace manager for the `schema` taxonomy group.

    Delegates to flat ``SDKStore`` methods per §5.2 teaching taxonomy +
    §5.4 Option 2 (additive aliases) lock. Manager class is private;
    `FactGraph.schema` property returns this manager.
    """

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.schema namespace is read-only")

    def ingest(self, *args: Any, **kwargs: Any) -> Any:
        return self._sdk.ingest(*args, **kwargs)

    def validate_provenance(self, *args: Any, **kwargs: Any) -> Any:
        return self._sdk.validate_provenance(*args, **kwargs)

    def add(self, *schema_classes: type[Entity], **kwargs: Any) -> SchemaAddResult:
        """Add entity classes or non-identity fields to the active schema.

        Accepts positional `Entity` classes or `schema_classes=[...]`.
        Additions are immediate for the in-memory graph and return a
        `SchemaAddResult` with the old digest, new digest, added entity names,
        and added field names. Destructive schema changes are rejected.
        """
        return self._sdk.add_schema_classes(*schema_classes, **kwargs)


class _SDKReadManager:
    """Read-only namespace manager for the `read` taxonomy group."""

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.read namespace is read-only")

    def get(self, *args: Any, **kwargs: Any) -> Any:
        """Read one entity snapshot by identity values.

        Delegates to `FactGraph.get(EntityCls, **identity)` and returns the
        current snapshot, or `None` when the entity is not visible.
        """
        return self._sdk.get(*args, **kwargs)

    def find(self, *args: Any, **kwargs: Any) -> Any:
        """Find entity snapshots by exact field filters.

        Delegates to `FactGraph.find(EntityCls, **filters)`. Single fields use
        exact-value matching; multi fields use containment matching. Optional
        `policy=` and `limit=` arguments are forwarded to the read facade.
        """
        return self._sdk.find(*args, **kwargs)

    def ref(self, *args: Any, **kwargs: Any) -> Any:
        """Build an entity reference from identity values without writing.

        Use the returned `idref_v1` token as the entity handle for
        `fg.write.set(...)` and `fg.write.add(...)`.
        """
        return self._sdk.ref(*args, **kwargs)


class _SDKWriteManager:
    """Read-only namespace manager for the `write` taxonomy group."""

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.write namespace is read-only")

    def set(self, *args: Any, **kwargs: Any) -> Any:
        """Write a single-cardinality field value.

        Delegates to `FactGraph.set(field, e_ref, value, meta=None)` and
        returns the assertion id for the appended write.
        """
        return self._sdk.set(*args, **kwargs)

    def add(self, *args: Any, **kwargs: Any) -> Any:
        """Append a value to a multi-cardinality field.

        Delegates to `FactGraph.add(field, e_ref, value, meta=None)` and
        returns the assertion id for the appended write.
        """
        return self._sdk.add(*args, **kwargs)

    def retract(self, *args: Any, **kwargs: Any) -> Any:
        """Retract a previously written assertion by assertion id.

        Pass an `asrt_id` returned by `fg.write.set(...)` or
        `fg.write.add(...)`. Retraction is append-only: the original assertion
        remains in the ledger and the retraction changes read-time visibility.
        """
        return self._sdk.retract(*args, **kwargs)

    def edit(self, *args: Any, **kwargs: Any) -> Any:
        return self._sdk.edit(*args, **kwargs)


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
        return self._sdk.inspect_rule(*args, **kwargs)


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
    """Read-only namespace manager for the `eval` taxonomy group.

    Per §5.2 §5.2.5 placement #4, ``accept*`` stays in `eval` because
    the mental workflow is evaluation lifecycle (evaluate → accept).
    """

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.eval namespace is read-only")

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run a `Rule` or `Query` against the current graph projection.

        `run` returns matching rows and does not write assertions. Use it for
        reads over existing facts; use `evaluate` for inference candidates.
        """
        return self._sdk.run(*args, **kwargs)

    def evaluate(self, *args: Any, **kwargs: Any) -> Any:
        """Evaluate an `Inference` and return candidate fact sets.

        Evaluation is read-only: candidates are proposed but not committed to
        the ledger. Pass the returned `CandidateSet` to `accept` when a
        candidate should become an assertion.
        """
        return self._sdk.evaluate(*args, **kwargs)

    def inspect_semantics(self, *args: Any, **kwargs: Any) -> Any:
        """Inspect semantics configuration without evaluating an inference.

        Accepts `SemanticsProfile`, `ProbLogSemantics`, or `PyReasonSemantics`
        and returns a JSON-like structural preview. Public wrappers include
        their lowered canonical profile preview.
        """
        return self._sdk.inspect_semantics(*args, **kwargs)

    def accept(self, *args: Any, **kwargs: Any) -> Any:
        """Accept candidate facts into the ledger.

        The common path is `fg.eval.accept(candidate_set)` after
        `fg.eval.evaluate(inference)`. This is the step that appends accepted
        candidate assertions to the graph.
        """
        return self._sdk.accept(*args, **kwargs)

    def accept_many(self, *args: Any, **kwargs: Any) -> Any:
        """Accept multiple candidate sets or accept requests.

        `mode="atomic"` is the default. This is the bulk form of
        `fg.eval.accept(...)` for callers that already have several candidate
        sets or request dictionaries.
        """
        return self._sdk.accept_many(*args, **kwargs)


class _SDKWhatIfFactOverlayManager:
    """Read-only sub-namespace manager for `what_if.fact_overlay` (G2)."""

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.what_if.fact_overlay namespace is read-only")

    def check(self, *args: Any, **kwargs: Any) -> Any:
        """Check a proposed fact overlay without committing it."""
        return self._sdk.check_fact_overlay(*args, **kwargs)

    def recheck_proof_frame(self, *args: Any, **kwargs: Any) -> Any:
        """Re-run a fact-overlay check from a recorded proof frame."""
        return self._sdk.recheck_proof_frame(*args, **kwargs)


class _SDKWhatIfRuleManager:
    """Read-only sub-namespace manager for `what_if.rule` (G3)."""

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.what_if.rule namespace is read-only")

    def disable(self, *args: Any, **kwargs: Any) -> Any:
        """Check a what-if result with one rule disabled."""
        return self._sdk.check_rule_disable(*args, **kwargs)

    def literal_replace(self, *args: Any, **kwargs: Any) -> Any:
        """Check a what-if result with one rule literal replaced."""
        return self._sdk.check_rule_literal_replace(*args, **kwargs)

    def add_condition(self, *args: Any, **kwargs: Any) -> Any:
        """Check a what-if result with an extra rule condition."""
        return self._sdk.check_rule_add_condition(*args, **kwargs)


class _SDKWhatIfManager:
    """Read-only namespace manager for the `what_if` taxonomy group.

    Per §5.2 Option B split: G1 + G4 methods (check, diagnose, why_not)
    are direct on this manager; G2 routed under ``fact_overlay`` sub-
    namespace; G3 routed under ``rule`` sub-namespace. G5 ``diff_proof_
    frames`` lives under ``audit`` per §5.2.1 placement decision.
    """

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)
        object.__setattr__(self, "_fact_overlay", _SDKWhatIfFactOverlayManager(sdk))
        object.__setattr__(self, "_rule", _SDKWhatIfRuleManager(sdk))

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.what_if namespace is read-only")

    def check(self, *args: Any, **kwargs: Any) -> Any:
        """Run a one-shot what-if check for an inference."""
        return self._sdk.check(*args, **kwargs)

    def diagnose(self, *args: Any, **kwargs: Any) -> Any:
        """Diagnose why a requested inference outcome did or did not appear."""
        return self._sdk.diagnose(*args, **kwargs)

    def why_not(self, *args: Any, **kwargs: Any) -> Any:
        """Ask for missing support paths for a desired inference result."""
        return self._sdk.why_not(*args, **kwargs)

    @property
    def fact_overlay(self) -> _SDKWhatIfFactOverlayManager:
        return self._fact_overlay

    @property
    def rule(self) -> _SDKWhatIfRuleManager:
        return self._rule


class _SDKAuditManager:
    """Read-only namespace manager for the `audit` taxonomy group.

    Per §5.2 §5.2.1 placement #2, ``diff_proof_frames`` (G5) lives here
    rather than under ``what_if`` because it consumes recorded round
    events and compares persisted proof-frame outcomes — post-hoc
    audit, not hypothetical evaluation.
    """

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.audit namespace is read-only")

    def explain_fact(self, *args: Any, **kwargs: Any) -> Any:
        """Explain the recorded support for a fact in the current graph."""
        return self._sdk.explain_fact(*args, **kwargs)

    def conflicts(self, *args: Any, **kwargs: Any) -> Any:
        """Return conflict diagnostics for the current graph state."""
        return self._sdk.conflicts(*args, **kwargs)

    def diff_proof_frames(self, *args: Any, **kwargs: Any) -> Any:
        """Compare two recorded proof-frame outcomes."""
        return self._sdk.diff_proof_frames(*args, **kwargs)


class _SDKPackageManager:
    """Read-only namespace manager for the `package` taxonomy group."""

    def __init__(self, sdk: "SDKStore") -> None:
        object.__setattr__(self, "_sdk", sdk)

    def __setattr__(self, name: str, value: Any) -> None:
        raise FrozenSnapshotError("FactGraph.package namespace is read-only")

    def export_package(self, *args: Any, **kwargs: Any) -> Any:
        """Export a runnable package from the graph.

        Package export is separate from `fg.save(...)`: it creates an execution
        artifact, not a FactGraph workspace.
        """
        return self._sdk.export_package(*args, **kwargs)

    def run_package(self, *args: Any, **kwargs: Any) -> Any:
        """Run an exported package with the selected engine."""
        return self._sdk.run_package(*args, **kwargs)


def _resolve_authoring_registry(
    *,
    registry_root: str | Path | None,
    registry: FileAuthoringRegistry | None,
) -> FileAuthoringRegistry | None:
    if registry is not None and not isinstance(registry, FileAuthoringRegistry):
        raise SDKStoreError("registry must be FileAuthoringRegistry")
    if registry is not None and registry_root is not None:
        root = Path(registry_root)
        if root != registry.root_dir:
            raise SDKStoreError("registry_root conflicts with registry.root_dir")
        return registry
    if registry is not None:
        return registry
    if registry_root is not None:
        return FileAuthoringRegistry(Path(registry_root))
    return None


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
    registry_root: str | Path | None,
) -> tuple[Path | None, str | None, str | Path | None]:
    workspace_path = _normalize_workspace_path(path)
    if workspace_path is None:
        return None, ledger_path, registry_root

    workspace_paths = resolve_workspace_paths(workspace_path)
    expected_ledger = workspace_paths.ledger
    expected_registry = workspace_paths.registry

    if ledger_path is not None:
        if not _path_equivalent(ledger_path, expected_ledger):
            raise SDKStoreError("ledger_path conflicts with workspace path")
        resolved_ledger_path = ledger_path
    else:
        resolved_ledger_path = str(expected_ledger)

    if registry_root is not None:
        if not _path_equivalent(registry_root, expected_registry):
            raise SDKStoreError("registry_root conflicts with workspace path")
        resolved_registry_root = registry_root
    else:
        resolved_registry_root = None

    return workspace_path, resolved_ledger_path, resolved_registry_root


def _registry_schema_digest(registry_root: str | Path) -> str | None:
    try:
        entry = FileAuthoringRegistry(Path(registry_root)).get_schema_entry()
    except Exception as exc:
        raise SDKStoreError(f"workspace registry schema digest unavailable: {exc}") from exc
    if entry is None:
        return None
    actual_digest = entry.get("schema_digest")
    if not isinstance(actual_digest, str):
        return None
    return actual_digest


def _validate_legacy_registry_schema(registry_root: str | Path, expected_digest: str) -> bool:
    actual_digest = _registry_schema_digest(registry_root)
    if actual_digest is None:
        return False
    if actual_digest != expected_digest:
        raise SDKStoreError(
            f"workspace schema digest mismatch: registry={actual_digest!r}, expected={expected_digest!r}"
        )
    return True


def _ensure_workspace_schema_object(path: str | Path, schema_ir: dict[str, Any], *, legacy_registry: Path | None) -> None:
    expected_digest = schema_digest(schema_ir)
    if schema_object_exists_for_workspace(path, expected_digest):
        try:
            validate_schema_object_for_workspace(path, schema_ir)
        except DatabaseError as exc:
            raise SDKStoreError(f"workspace schema object invalid: {exc}") from exc
        if legacy_registry is not None and legacy_registry.exists():
            registry_digest = _registry_schema_digest(legacy_registry)
            if registry_digest is not None and registry_digest != expected_digest:
                raise SDKStoreError(
                    "workspace schema digest mismatch: "
                    f"db_object={expected_digest!r}, registry={registry_digest!r}"
                )
        return

    if legacy_registry is None or not legacy_registry.exists():
        raise SDKStoreError("workspace schema object missing")
    if not _validate_legacy_registry_schema(legacy_registry, expected_digest):
        raise SDKStoreError("workspace registry schema digest missing")
    try:
        write_schema_object_for_workspace(path, schema_ir)
    except DatabaseError as exc:
        raise SDKStoreError(f"workspace schema object migration failed: {exc}") from exc


class SDKStore:
    """Main SDK graph object, exported to users as `FactGraph`.

    `FactGraph` is a literal alias of this class and is the recommended public
    name. It owns the compiled schema, append-only ledger, optional authoring
    registry, optional workspace path, and user-facing namespaces such as
    `schema`, `read`, `write`, `rules`, `inferences`, `eval`, `what_if`,
    `audit`, `package`, and `views`.

    `FactGraph.attach(db, schema_classes=...)` is the Database-owned lifecycle
    for new DB/view substrate work. Attached runtimes expose
    `fg.commit_assertions(...)` for Database-routed writes; shipped
    `create` / `from_schema_classes` / `load` constructors remain available as
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
        registry: FileAuthoringRegistry | None = None,
        workspace_path: str | Path | None = None,
        default_row_format: str | None = None,
    ) -> None:
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
        self._authoring_registry = _resolve_authoring_registry(
            registry_root=registry_root,
            registry=registry,
        )
        self._application_schema_index = build_schema_index(self._schema_ir)
        self._field_pred_by_descriptor: dict[Field, dict[str, Any]] = {}
        self._field_decl_by_descriptor: dict[Field, dict[str, Any]] = {}
        self._entity_spec_by_class: dict[type[Entity], dict[str, Any]] = {}
        self._identity_values_by_e_ref: dict[str, dict[str, Any]] = {}
        self._views_manager = _SDKViewsManager(self)
        self._assertions_manager = _SDKAssertionsManager(self)
        self._schema_manager = _SDKSchemaManager(self)
        self._read_manager = _SDKReadManager(self)
        self._write_manager = _SDKWriteManager(self)
        self._rules_manager = _SDKRulesManager(self)
        self._inferences_manager = _SDKInferencesManager(self)
        self._eval_manager = _SDKEvalManager(self)
        self._what_if_manager = _SDKWhatIfManager(self)
        self._audit_manager = _SDKAuditManager(self)
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
        registry: FileAuthoringRegistry | None = None,
        default_row_format: str | None = None,
    ) -> "SDKStore":
        """Create a `FactGraph` from Python `Entity` classes.

        This is the normal SDK constructor. Pass `path=` when the graph should
        own a durable workspace that can later be saved with `fg.save()` and
        restored with `FactGraph.load(...)`.

        Args:
            schema_classes: Non-empty list of `Entity` subclasses.
            ledger: Optional existing ledger object.
            ledger_path: Optional SQLite ledger path; mutually exclusive with
                `ledger`.
            path: Optional workspace directory. When provided, default ledger
                and registry paths are derived from it.
            artifact_store_root: Optional artifact sidecar root.
            registry_root: Optional authoring registry directory.
            registry: Optional `FileAuthoringRegistry` instance.
            default_row_format: Optional default output row format for rule
                evaluation.

        Returns:
            A `FactGraph` / `SDKStore` bound to the compiled schema.

        Raises:
            SDKStoreError: If constructor paths or schema classes are invalid.
        """
        workspace_path, resolved_ledger_path, resolved_registry_root = _resolve_workspace_constructor_paths(
            path=path,
            ledger_path=ledger_path,
            registry_root=registry_root,
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
            registry_root=resolved_registry_root,
            registry=registry,
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
        registry: FileAuthoringRegistry | None = None,
        default_row_format: str | None = None,
    ) -> "SDKStore":
        return cls._from_schema_classes_impl(
            classes,
            ledger=ledger,
            ledger_path=ledger_path,
            artifact_store_root=artifact_store_root,
            registry_root=registry_root,
            registry=registry,
            workspace_path=None,
            default_row_format=default_row_format,
        )

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        schema_classes: list[type[Entity]] | None = None,
        default_row_format: str | None = None,
    ) -> "SDKStore":
        """Load a saved FactGraph workspace from disk.

        Workspace load restores the ledger and authoring registry, then
        validates the workspace schema digest against the supplied
        `schema_classes`. Class-less dynamic load is not supported.

        Args:
            path: Workspace directory created by `fg.save(...)`.
            schema_classes: Entity classes matching the saved workspace schema.
            default_row_format: Optional default output row format.
        """
        if schema_classes is None:
            raise SDKStoreError("schema_classes is required for FactGraph.load(...)")
        schema_ir = compile_schema_from_classes(schema_classes)
        digest = schema_digest(schema_ir)
        try:
            paths = app_load_workspace(path, schema_digest=digest)
            _ensure_workspace_schema_object(paths.root, schema_ir, legacy_registry=paths.registry)
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

        store = Store(schema_ir=schema_ir, ledger=db._ledger_for_attach())
        attached = cls(schema_classes, store=store, default_row_format=default_row_format)
        attached._database = db
        attached._attached_writable = True
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
        registry_root: str | Path | None = None,
        registry: FileAuthoringRegistry | None = None,
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
            registry_root=registry_root,
            registry=registry,
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
    def schema_ir(self) -> dict[str, Any]:
        return self._schema_ir

    @property
    def views(self) -> _SDKViewsManager:
        return self._views_manager

    @property
    def assertions(self) -> _SDKAssertionsManager:
        return self._assertions_manager

    @property
    def schema(self) -> _SDKSchemaManager:
        """`schema` taxonomy namespace (post-L redesign §5.2 lock).

        Read-only manager exposing ``ingest`` and ``validate_provenance``.
        Delegates to flat ``SDKStore.<method>`` per §5.4 Option 2 lock.
        """
        return self._schema_manager

    @property
    def read(self) -> _SDKReadManager:
        """`read` taxonomy namespace exposing ``get`` / ``find`` / ``ref``."""
        return self._read_manager

    @property
    def write(self) -> _SDKWriteManager:
        """`write` taxonomy namespace exposing ``set`` / ``add`` / ``retract`` / ``edit``."""
        return self._write_manager

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
        """`eval` taxonomy namespace exposing the evaluate→accept lifecycle."""
        return self._eval_manager

    @property
    def what_if(self) -> _SDKWhatIfManager:
        """`what_if` taxonomy namespace (G1+G4 direct; G2 / G3 sub-namespaced)."""
        return self._what_if_manager

    @property
    def audit(self) -> _SDKAuditManager:
        """`audit` taxonomy namespace exposing ``explain_fact`` / ``conflicts`` / ``diff_proof_frames``."""
        return self._audit_manager

    @property
    def package(self) -> _SDKPackageManager:
        """`package` taxonomy namespace exposing ``export_package`` / ``run_package``."""
        return self._package_manager

    def commit_assertions(self, assertions: Sequence[AssertionInput]) -> CommitResult:
        if self._database is None:
            raise SDKStoreError(
                "fg.commit_assertions(...) is only available on FactGraph.attach(db) runtimes; "
                "use shipped fg.set / fg.add / fg.write.* for non-attached SDKStores"
            )
        return self._database.commit_assertions(assertions)

    def batch(self, *, meta: dict[str, Any] | None = None):
        self._reject_attached_write("fg.batch")
        from .batch import SDKBatchTx

        return SDKBatchTx(self, meta=meta)

    def get(self, entity_cls: type[Entity], **identity_kwargs: Any):
        """Return an ``EntitySnapshot`` for the entity identified by kwargs.

        Reads the active (chosen) view of the entity. The snapshot is
        read-only; attribute assignment raises ``FrozenSnapshotError``.

        Args:
            entity_cls: An ``Entity`` subclass registered with this
                SDKStore.
            **identity_kwargs: Identity field values identifying the
                entity.

        Returns:
            An ``EntitySnapshot`` exposing each declared field as an
            attribute, or ``None`` if the entity is not visible (no
            ``<T>:exists`` assertion in the active view).

        Raises:
            SDKStoreError: if ``entity_cls`` was not registered with this
                SDKStore, or if identity kwargs are malformed.
        """
        from .facade import sdk_get

        return sdk_get(self, entity_cls, **identity_kwargs)

    def find(
        self,
        entity_cls: type[Entity],
        *,
        policy: Any = _POLICY_TOMBSTONE,
        limit: int | None = None,
        **filter_kwargs: Any,
    ):
        from .facade import sdk_find

        if "view" in filter_kwargs:
            raise SDKStoreError("view= is not supported by fg.read.find()", path="$.find.view")
        self._reject_removed_read_policy(policy, api_path="fg.read.find")
        return sdk_find(
            self,
            entity_cls,
            limit=limit,
            **filter_kwargs,
        )

    def edit(self, entity_cls: type[Entity], **identity_kwargs: Any):
        self._reject_attached_write("fg.edit")
        from .facade import sdk_edit

        return sdk_edit(self, entity_cls, **identity_kwargs)

    def ingest(
        self,
        data: Any,
        *,
        meta: dict[str, Any] | None = None,
        allow_sensitive_meta: bool = False,
    ):
        self._reject_attached_write("fg.ingest")
        from .ingest import sdk_ingest

        return sdk_ingest(self, data, meta=meta, allow_sensitive_meta=allow_sensitive_meta)

    def validate_provenance(self, obj: Any, *, standard: str = "derivation_v1"):
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

        old_digest = self._schema_digest
        result = app_add_schema_classes(
            current_classes=self._classes,
            schema_classes=additions,
        )
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

    def check(
        self,
        inference: Any,
        binding: Mapping[str, Any],
        *,
        engine: str = "native",
        registry: RuleRegistry | None = None,
        semantics: Any = _PROFILE_KWARG_UNSET,
        semantics_profile: Any = _PROFILE_KWARG_UNSET,
    ) -> "CheckResult":
        """Check one SDK ``Inference`` against a concrete binding.

        Args:
            inference: SDK ``Inference`` authoring object. ``Rule`` and
                application ``CompiledDerivationPlan`` inputs are rejected at
                the SDK boundary.
            binding: Mapping of ``$``-prefixed variable names to Python
                values. Tuple-form ``BindingItems`` are intentionally not part
                of the SDK shell contract.
            engine: Runtime engine name passed through to the application
                Check request builder.
            registry: Optional runtime registry override.

        Returns:
            The application ``CheckResult`` DTO directly. For ergonomic
            evidence traversal, advanced callers may opt into
            ``factgraph.application.walker.SupportArtifactView`` outside the SDK.

        Raises:
            SDKStoreError: For SDK input-shape errors or application helper
                validation errors. Helper errors are preserved as
                ``__cause__``.
        """
        from .shells.check import sdk_check

        self._reject_shell_semantics(semantics=semantics, semantics_profile=semantics_profile)
        return sdk_check(self, inference, binding, engine=engine, registry=registry)

    def diagnose(
        self,
        inference: Any,
        binding: Mapping[str, Any],
        *,
        engine: str = "native",
        registry: RuleRegistry | None = None,
        semantics: Any = _PROFILE_KWARG_UNSET,
        semantics_profile: Any = _PROFILE_KWARG_UNSET,
    ) -> "DiagnoseResult":
        """Diagnose one SDK ``Inference`` against a concrete binding.

        Args:
            inference: SDK ``Inference`` authoring object. ``Rule`` and
                application ``CompiledDerivationPlan`` inputs are rejected at
                the SDK boundary.
            binding: Mapping of ``$``-prefixed variable names to Python
                values.
            engine: Runtime engine name passed through to the application
                Diagnose request builder.
            registry: Optional runtime registry override.

        Returns:
            The application ``DiagnoseResult`` DTO directly. Locator parsing
            remains an opt-in application-layer workflow; this SDK shell does
            not import walker helpers.

        Raises:
            SDKStoreError: For SDK input-shape errors or application helper
                validation errors. Helper errors are preserved as
                ``__cause__``.
        """
        from .shells.diagnose import sdk_diagnose

        self._reject_shell_semantics(semantics=semantics, semantics_profile=semantics_profile)
        return sdk_diagnose(self, inference, binding, engine=engine, registry=registry)

    def why_not(
        self,
        inference: Any,
        candidates: Sequence[Mapping[str, Any] | Sequence[Any]],
        *,
        engine: str = "native",
        registry: RuleRegistry | None = None,
        semantics: Any = _PROFILE_KWARG_UNSET,
        semantics_profile: Any = _PROFILE_KWARG_UNSET,
    ) -> "WhyNotUniverseResult":
        """Run Why-not for one SDK ``Inference`` against an explicit candidate universe.

        Args:
            inference: SDK ``Inference`` authoring object. ``Rule`` and
                application ``CompiledDerivationPlan`` inputs are rejected at
                the SDK boundary (per §5.1 lock).
            candidates: Sequence of candidate rows. Each row is either a
                ``Mapping[str, Any]`` keyed by the head variable names, or a
                positional ``Sequence[Any]`` matching the head variable
                order. Rows are normalized internally against the plan
                head variable order.
            engine: Runtime engine name passed through to the application
                Why-not request DTO.
            registry: Optional runtime registry override.

        Returns:
            The application ``WhyNotUniverseResult`` DTO directly. The SDK
            shell does not wrap or re-export the result; advanced callers
            can import ``WhyNotUniverseResult`` from
            ``factgraph.application.protocol`` if a typed reference is needed.

        Raises:
            SDKStoreError: For non-SDK exceptions crossing the SDK boundary.
                The ``path`` field locates the failure: ``$.why_not.inference``
                for SDK input-shape and inference-lowering failures,
                ``$.why_not.dependencies`` for dependency registration
                failures, ``$.why_not.candidates`` for candidate-row
                validation errors, ``$.why_not.request`` for request DTO
                shape errors, and ``$.why_not`` for runtime Why-not
                failures. Original exceptions are preserved as
                ``__cause__``.
        """
        from .shells.why_not import sdk_why_not

        self._reject_shell_semantics(semantics=semantics, semantics_profile=semantics_profile)
        return sdk_why_not(self, inference, candidates, engine=engine, registry=registry)

    def check_fact_overlay(
        self,
        inference: Any,
        binding: Mapping[str, Any],
        overlay: Any,
        *,
        engine: str = "native",
        registry: RuleRegistry | None = None,
        semantics: Any = _PROFILE_KWARG_UNSET,
        semantics_profile: Any = _PROFILE_KWARG_UNSET,
    ) -> "FactOverlayCheckResult":
        """Run Fact Overlay Check for one SDK ``Inference`` + binding + overlay.

        Args:
            inference: SDK ``Inference`` authoring object. ``Rule`` and
                application ``CompiledDerivationPlan`` inputs are rejected
                at the SDK boundary (per §5.1 lock).
            binding: Mapping of ``$``-prefixed variable names to Python
                values; validated through ``factgraph.sdk.shells._validation``.
            overlay: Raw application ``EvaluationOverlay`` protocol DTO
                (per §5.1 lock — author-time intent, not a lowered plan).
                Wrong-type or malformed overlay shape is caught by
                ``FactOverlayCheckRequest`` construction and remapped to
                ``$.check_fact_overlay.request`` per §5.8.
            engine: Runtime engine name passed through to the application
                Fact Overlay request DTO.
            registry: Optional runtime registry override.

        Returns:
            The application ``FactOverlayCheckResult`` DTO directly. The
            runtime represents unsupported overlay / runtime conditions as
            ``invalid_request`` result DTOs (not raised exceptions); the
            SDK shell passes the result through unchanged per §5.8 lock.

        Raises:
            SDKStoreError: For non-SDK exceptions crossing the SDK
                boundary. The ``path`` field locates the failure:
                ``$.check_fact_overlay.inference`` for SDK input-shape
                and inference-lowering failures,
                ``$.check_fact_overlay.binding`` for binding shape errors,
                ``$.check_fact_overlay.overlay`` for non-
                ``EvaluationOverlay`` overlay input (the SDK rejects
                ``tuple[FactValueOverride, ...]`` form even though the
                application request DTO would tolerate it),
                ``$.check_fact_overlay.dependencies`` for dependency
                registration failures,
                ``$.check_fact_overlay.request`` for request DTO shape
                errors, and base ``$.check_fact_overlay`` for unexpected
                runtime exceptions (the runtime ordinarily returns
                ``FactOverlayCheckResult(status="invalid_request")`` for
                unsupported overlay / runtime conditions, which is
                passed through unchanged). Original exceptions are
                preserved as ``__cause__``.
        """
        from .shells.fact_overlay import sdk_fact_overlay_check

        self._reject_shell_semantics(semantics=semantics, semantics_profile=semantics_profile)
        return sdk_fact_overlay_check(
            self, inference, binding, overlay, engine=engine, registry=registry
        )

    def recheck_proof_frame(
        self,
        support_artifact: Any,
        overlay: Any,
    ) -> "ProofFrameRecheckResult":
        """Recheck a previously captured support frame under a fact-side overlay.

        Args:
            support_artifact: Raw application ``SupportArtifact`` (frozen
                dataclass) obtained from a prior Check run's
                ``CheckResult.evidence_envelope.engine_payload``. Per §5.2
                lock, the SDK never wraps ``SupportArtifact``, never
                extracts it from a ``CheckResult`` argument, and never
                calls ``sdk.check(...)`` internally to obtain it.
            overlay: Raw application ``EvaluationOverlay`` protocol DTO
                (per §5.2 lock — author-time intent).

        Returns:
            The application ``ProofFrameRecheckResult`` DTO directly. The
            runtime represents unsupported support kinds, rule-ref edges,
            and rule actions as result DTOs; the SDK shell passes the
            result through unchanged per §5.8 lock.

        Raises:
            SDKStoreError: For non-SDK exceptions crossing the SDK
                boundary. The ``path`` field locates the failure:
                ``$.recheck_proof_frame.support_artifact`` for non-
                ``SupportArtifact`` input, ``$.recheck_proof_frame.overlay``
                for non-``EvaluationOverlay`` input,
                ``$.recheck_proof_frame.request`` for request DTO shape
                errors, and ``$.recheck_proof_frame`` for unexpected
                runtime exceptions. Original exceptions are preserved as
                ``__cause__``.
        """
        from .shells.proof_frame import sdk_proof_frame_recheck

        return sdk_proof_frame_recheck(self, support_artifact, overlay)

    def check_rule_disable(
        self,
        rule: Any,
        support: Any,
        *,
        branch_index: int,
        atom_index: int,
        overlay: Any = None,
        note: str | None = None,
    ) -> "RuleDisableResult":
        """Check a Rule Disable rule-overlay action against captured support.

        Args:
            rule: SDK ``Rule`` describing the target rule. Lowered through
                ``SDKStore._compile_rule_input(...)`` to a substrate
                ``RuleSpec`` per §5.2 lock; raw ``RuleSpec`` is rejected.
            support: Raw application ``SupportArtifact`` from a prior
                Check run's ``CheckResult.evidence_envelope.engine_payload``.
                Per §5.3 lock the SDK never wraps it, never extracts it
                from a ``CheckResult`` argument, and never calls
                ``sdk.check(...)`` internally.
            branch_index: Non-negative branch locator into
                ``rule_spec.where`` per §5.4 lock.
            atom_index: Non-negative atom locator into
                ``rule_spec.where[branch_index]`` per §5.4 lock.
            overlay: ``None`` or an empty ``EvaluationOverlay``. The
                rule-action overlay is constructed internally by the A
                helper ``build_rule_disable_request(...)``; non-empty
                overlay is rejected at the SDK boundary per §5.4 + §5.8
                locks.
            note: Optional human-readable annotation forwarded to the
                ``RuleDisableAction`` per §5.4 lock.

        Returns:
            The application ``RuleDisableResult`` DTO directly. The
            runtime represents unsupported support kinds, rule-ref
            edges, target-not-found, rule-id/version mismatch, and
            native evaluation failures as result DTOs; the SDK shell
            passes the result through unchanged per §5.8 lock.

        Raises:
            SDKStoreError: For non-SDK exceptions crossing the SDK
                boundary. The ``path`` field locates the failure:
                ``$.check_rule_disable.rule`` for non-``Rule`` SDK
                input or invalid rule shape after lowering;
                ``$.check_rule_disable.support`` for non-
                ``SupportArtifact`` input;
                ``$.check_rule_disable.overlay`` for non-
                ``EvaluationOverlay`` non-None or non-empty
                ``EvaluationOverlay`` input;
                ``$.check_rule_disable.dependencies`` for dependency
                rule registration / RuleRef resolution failures;
                ``$.check_rule_disable.request`` for action / request
                DTO shape errors; and ``$.check_rule_disable`` for
                unexpected runtime exceptions. Original exceptions are
                preserved as ``__cause__``.
        """
        from .shells.rule_disable import sdk_rule_disable

        return sdk_rule_disable(
            self,
            rule,
            support,
            branch_index=branch_index,
            atom_index=atom_index,
            overlay=overlay,
            note=note,
        )

    def check_rule_literal_replace(
        self,
        rule: Any,
        support: Any,
        *,
        branch_index: int,
        atom_index: int,
        literal_path: Any,
        old_literal: Any,
        new_literal: Any,
        overlay: Any = None,
        note: str | None = None,
    ) -> "RuleLiteralReplaceResult":
        """Check a Rule Literal Replace rule-overlay action against captured support.

        Args:
            rule: SDK ``Rule`` describing the target rule. Lowered through
                ``SDKStore._compile_rule_input(...)`` to a substrate
                ``RuleSpec`` per §5.2 lock; raw ``RuleSpec`` is rejected.
            support: Raw application ``SupportArtifact`` from a prior
                Check run's ``CheckResult.evidence_envelope.engine_payload``.
                Per §5.3 lock the SDK never wraps it.
            branch_index: Non-negative branch locator into
                ``rule_spec.where`` per §5.4 lock.
            atom_index: Non-negative atom locator into
                ``rule_spec.where[branch_index]`` per §5.4 lock.
            literal_path: Raw application ``RuleLiteralPath`` per §5.4
                lock (frozen application-canonical, no SDK alternative
                without inventing outward surface — G2 §5.1+§5.2
                cross-cutting precedent applies).
            old_literal: Existing literal value at the locator. ``Any``
                typing matches the application protocol.
            new_literal: Replacement literal value at the locator.
                ``Any`` typing matches the application protocol.
            overlay: ``None`` or an empty ``EvaluationOverlay``. The
                rule-action overlay is constructed internally by the A
                helper ``build_rule_literal_replace_request(...)``;
                non-empty overlay is rejected at the SDK boundary per
                §5.4 + §5.8 locks.
            note: Optional human-readable annotation forwarded to the
                ``RuleLiteralReplaceAction`` per §5.4 lock.

        Returns:
            The application ``RuleLiteralReplaceResult`` DTO directly.
            The runtime represents unsupported support kinds, rule-ref
            edges, target-not-found, rule-id/version mismatch, and
            native evaluation failures as result DTOs; the SDK shell
            passes the result through unchanged per §5.8 lock.

        Raises:
            SDKStoreError: For non-SDK exceptions crossing the SDK
                boundary. The ``path`` field locates the failure:
                ``$.check_rule_literal_replace.rule`` for non-``Rule``
                SDK input or invalid rule shape after lowering;
                ``$.check_rule_literal_replace.support`` for non-
                ``SupportArtifact`` input;
                ``$.check_rule_literal_replace.overlay`` for non-
                ``EvaluationOverlay`` non-None or non-empty
                ``EvaluationOverlay`` input;
                ``$.check_rule_literal_replace.dependencies`` for
                dependency rule registration / RuleRef resolution
                failures; ``$.check_rule_literal_replace.request`` for
                ``RuleLiteralPath`` shape errors / action / request
                DTO shape errors; and ``$.check_rule_literal_replace``
                for unexpected runtime exceptions. Original exceptions
                are preserved as ``__cause__``.
        """
        from .shells.rule_literal_replace import sdk_rule_literal_replace

        return sdk_rule_literal_replace(
            self,
            rule,
            support,
            branch_index=branch_index,
            atom_index=atom_index,
            literal_path=literal_path,
            old_literal=old_literal,
            new_literal=new_literal,
            overlay=overlay,
            note=note,
        )

    def check_rule_add_condition(
        self,
        rule: Any,
        support: Any,
        *,
        branch_index: int,
        added_atom: Any,
        overlay: Any = None,
        note: str | None = None,
    ) -> "RuleAddConditionResult":
        """Check a Rule Add Condition rule-overlay action against captured support.

        Args:
            rule: SDK ``Rule`` describing the target rule. Lowered through
                ``SDKStore._compile_rule_input(...)`` to a substrate
                ``RuleSpec`` per §5.2 lock; raw ``RuleSpec`` is rejected.
            support: Raw application ``SupportArtifact`` from a prior
                Check run's ``CheckResult.evidence_envelope.engine_payload``.
                Per §5.3 lock the SDK never wraps it.
            branch_index: Non-negative branch locator into
                ``rule_spec.where`` per §5.4 lock. Note Add Condition
                has no ``atom_index`` argument — it appends a new atom
                to the branch rather than pointing at an existing
                locator.
            added_atom: Raw application ``RuleAddedAtom`` per §5.4
                lock (frozen application-canonical, no SDK alternative
                without inventing outward surface — G2 §5.1+§5.2
                cross-cutting precedent applies).
            overlay: ``None`` or an empty ``EvaluationOverlay``. The
                rule-action overlay is constructed internally by the A
                helper ``build_rule_add_condition_request(...)``;
                non-empty overlay is rejected at the SDK boundary per
                §5.4 + §5.8 locks.
            note: Optional human-readable annotation forwarded to the
                ``RuleAddConditionAction`` per §5.4 lock.

        Returns:
            The application ``RuleAddConditionResult`` DTO directly.
            The runtime represents unsupported support kinds, rule-ref
            edges, rule-id/version mismatch, and native evaluation
            failures as result DTOs; the SDK shell passes the result
            through unchanged per §5.8 lock.

        Raises:
            SDKStoreError: For non-SDK exceptions crossing the SDK
                boundary. The ``path`` field locates the failure:
                ``$.check_rule_add_condition.rule`` for non-``Rule``
                SDK input or invalid rule shape after lowering;
                ``$.check_rule_add_condition.support`` for non-
                ``SupportArtifact`` input;
                ``$.check_rule_add_condition.overlay`` for non-
                ``EvaluationOverlay`` non-None or non-empty
                ``EvaluationOverlay`` input;
                ``$.check_rule_add_condition.dependencies`` for
                dependency rule registration / RuleRef resolution
                failures; ``$.check_rule_add_condition.request`` for
                ``RuleAddedAtom`` shape errors / action / request DTO
                shape errors; and ``$.check_rule_add_condition`` for
                unexpected runtime exceptions. Original exceptions are
                preserved as ``__cause__``.
        """
        from .shells.rule_add_condition import sdk_rule_add_condition

        return sdk_rule_add_condition(
            self,
            rule,
            support,
            branch_index=branch_index,
            added_atom=added_atom,
            overlay=overlay,
            note=note,
        )

    def diff_proof_frames(
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

    def ref(self, entity_cls: type[Entity], **identity_values: Any) -> str:
        """Return a managed e_ref string for the entity identified by kwargs.

        Records the supplied identity into this SDKStore's local cache so
        that ``sdk.set`` / ``sdk.add`` can later resolve the e_ref into a
        full ``EntitySelector`` for the application write-plan. Does NOT
        write to the ledger; ``ref`` is only an in-memory registration.

        Args:
            entity_cls: An ``Entity`` subclass passed to this SDKStore in
                the ``classes=[...]`` constructor arg.
            **identity_values: Identity field values. All declared identity
                fields must be supplied unless they have ``default=`` or
                ``default_factory=``.

        Returns:
            A canonical ``idref_v1:<entity_type>:<digest>`` token. The same
            identity inputs always produce the same e_ref (deterministic
            encoding).

        Raises:
            SDKStoreError: if ``entity_cls`` was not registered with this
                SDKStore, if extra identity kwargs are passed, or if a
                required identity field has no value and no default.
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
            elif "default" in field:
                raw_value = field["default"]
            elif field.get("default_factory") == "uuid4":
                raw_value = _default_uuid4_for_tag(tag)
            else:
                raise SDKStoreError(f"missing identity field: {entity_cls.__name__}.{name}")
            tuples.append((name, tag, _coerce_sdk_value_to_tag(tag, raw_value)))
        e_ref = encode_idref_v1(spec["entity_type"], tuples)
        self._identity_values_by_e_ref[e_ref] = {name: value for name, _, value in tuples}
        return e_ref

    def set(
        self,
        field: Field,
        e_ref: str,
        value: Any,
        *,
        meta: dict[str, Any] | None = None,
    ) -> str:
        """Append a ``set`` assertion writing ``value`` to a single-cardinality field.

        The write is routed through ``factgraph.application``'s write-plan adapter:
        the first time an entity is written, identity predicates and
        ``<T>:exists`` are auto-materialized so that subsequent ``sdk.get`` /
        ``sdk.run`` / inference calls see the entity. ``set`` produces a new
        assertion (the ledger is append-only); the chosen view reflects the
        latest assertion.

        Args:
            field: A ``Field`` descriptor obtained from an Entity class
                (e.g. ``User.name``). Must reference a ``cardinality="single"``
                field.
            e_ref: A managed e_ref string returned by ``sdk.ref(EntityCls, ...)``.
                Externally-constructed strings are rejected.
            value: The value to write. Type is constrained by the field's
                declared ``type_domain`` (str / int / bool / entity_ref / ...).
                For ``entity_ref`` fields, pass another managed e_ref string.
            meta: Optional metadata dict attached to the assertion.

        Returns:
            The assertion id (str) of the field-mutation write. Auto-materialized
            identity / exists assertion ids are not returned.

        Raises:
            SDKStoreError: ``code="UNRESOLVABLE_E_REF"`` if ``e_ref`` (or an
                entity_ref ``value``) was not produced by ``sdk.ref``.
            CardinalityError: ``code="FIELD_CARDINALITY_MISMATCH"`` if ``field``
                is multi-cardinality (use ``sdk.add`` instead).
            SDKStoreError: ``code="FIELD_VALUE_TYPE_MISMATCH"`` if ``value``
                does not match the field's declared type domain.
        """
        self._reject_attached_write("fg.set")
        return self._apply_field_mutation(op="set", field=field, e_ref=e_ref, value=value, meta=meta)

    def add(
        self,
        field: Field,
        e_ref: str,
        value: Any,
        *,
        meta: dict[str, Any] | None = None,
    ) -> str:
        """Append an ``add`` assertion adding ``value`` to a multi-cardinality field.

        Unlike ``set``, ``add`` is the multi-set accumulator: each call appends
        a new value to the field's value set without replacing prior writes.
        The entity is auto-materialized on first write (see ``set`` docstring
        for materialization details).

        Args:
            field: A ``Field`` descriptor obtained from an Entity class
                (e.g. ``User.tag``). Must reference a ``cardinality="multi"``
                field.
            e_ref: A managed e_ref string returned by ``sdk.ref(EntityCls, ...)``.
            value: The value to add. Type is constrained by the field's
                declared ``type_domain``. For ``entity_ref`` fields, pass
                another managed e_ref string.
            meta: Optional metadata dict attached to the assertion.

        Returns:
            The assertion id (str) of the field-mutation write.

        Raises:
            SDKStoreError: ``code="UNRESOLVABLE_E_REF"`` if ``e_ref`` (or an
                entity_ref ``value``) was not produced by ``sdk.ref``.
            CardinalityError: ``code="FIELD_CARDINALITY_MISMATCH"`` if ``field``
                is single-cardinality (use ``sdk.set`` instead).
            SDKStoreError: ``code="FIELD_VALUE_TYPE_MISMATCH"`` if ``value``
                does not match the field's declared type domain.
        """
        self._reject_attached_write("fg.add")
        return self._apply_field_mutation(op="add", field=field, e_ref=e_ref, value=value, meta=meta)

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
                f"call sdk.ref({owner_type}, **identity_kwargs) to obtain a managed e_ref",
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
                    f"call sdk.ref({value_entity_type}, **identity_kwargs) for the value entity first",
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
        raise SDKStoreError(err.message, code=err.code)

    def retract(self, asrt_id: str, *, meta: dict[str, Any] | None = None) -> str | None:
        """Append a retraction assertion that supersedes a prior assertion.

        ``retract`` is append-only: the original assertion is preserved in
        the ledger; the retraction marks it as no longer authoritative for
        the chosen view. The retraction itself is recorded as a new
        assertion.

        Args:
            asrt_id: The assertion id to retract (e.g. a value previously
                returned by ``sdk.set`` / ``sdk.add``).
            meta: Optional metadata dict attached to the retraction
                assertion.

        Returns:
            The assertion id (str) of the retraction record, or ``None`` if
            no retraction was emitted (e.g. the target assertion is already
            retracted).
        """
        self._reject_attached_write("fg.retract")
        try:
            return retract_by_asrt(self._store.ledger, asrt_id, meta)
        except WriteProtocolError as exc:
            code = "ASSERTION_NOT_FOUND" if "unknown revoked_asrt_id" in str(exc) else None
            raise SDKStoreError(str(exc), code=code) from exc

    def run(
        self,
        obj: Any,
        *,
        row_format: str | None = None,
        policy: Any = _POLICY_TOMBSTONE,
        view: Any = _VIEW_TOMBSTONE,
        return_display_meta: bool = False,
        registry: RuleRegistry | None = None,
    ) -> list[Any]:
        if not isinstance(return_display_meta, bool):
            raise SDKStoreError("return_display_meta must be bool", path="$.run.return_display_meta")
        if view is not _VIEW_TOMBSTONE:
            raise SDKStoreError("view= is not supported by fg.run()", path="$.run.view")
        self._reject_removed_read_policy(policy, api_path="fg.run")
        if return_display_meta:
            raise SDKStoreError(_READPOLICY_REMOVED_MESSAGE, path="$.run.return_display_meta")
        dispatch_key = self._run_dispatch_key(obj)
        dispatch_map = {
            "query": self._run_dispatch_query,
            "derivation": self._run_dispatch_derivation,
            "rule": self._run_dispatch_rule,
        }
        return dispatch_map[dispatch_key](
            obj,
            row_format=row_format,
            registry=registry,
        )

    def _run_dispatch_key(self, obj: Any) -> str:
        detectors = (
            ("query", _is_sdk_query_object),
            ("derivation", _is_derivation_run_object),
        )
        for key, detector in detectors:
            if detector(obj):
                return key
        return "rule"

    def _run_dispatch_query(
        self,
        query: Any,
        *,
        row_format: str | None,
        registry: RuleRegistry | None,
    ) -> list[Any]:
        resolved_row_format = _resolve_query_row_format(row_format)
        runtime_registry = self._resolve_runtime_registry(query, explicit_registry=registry)
        return self._run_query(query, row_format=resolved_row_format, registry=runtime_registry)

    def _run_dispatch_derivation(
        self,
        derivation: Any,
        *,
        row_format: str | None,
        registry: RuleRegistry | None,
    ) -> list[tuple[Any, ...]] | list[dict[str, Any]]:
        del derivation, row_format, registry
        raise SDKStoreError(
            "Inference is not supported by run(); use sdk.evaluate() instead",
            code=QUERY_INVALID_ROW_FORMAT,
            path="$.run.obj",
        )

    def _run_dispatch_rule(
        self,
        rule: Any,
        *,
        row_format: str | None,
        registry: RuleRegistry | None,
    ) -> list[tuple[Any, ...]] | list[dict[str, Any]]:
        resolved_row_format = _resolve_row_format(
            call_site=row_format,
            store_default=self._default_row_format,
            env_var=self._env_row_format,
        )
        return self._run_rule(
            rule,
            row_format=resolved_row_format,
            registry=registry,
        )

    def _run_rule(
        self,
        rule: Any,
        *,
        row_format: str,
        registry: RuleRegistry | None,
    ) -> list[tuple[Any, ...]] | list[dict[str, Any]]:
        if isinstance(rule, str):
            raise SDKStoreError(
                "string rule DSL is not supported in SDK v1; use Rule object, RuleSpec, or structured rule dict"
            )
        compiled = self._compile_rule_input(rule)
        rule_spec = RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )
        active_registry = registry if registry is not None else RuleRegistry()
        if registry is None:
            self._register_rule_dependencies(active_registry, rule)
        rows = run_rule(self._store, rule_spec, active_registry)
        return _format_rule_rows(rows, select_vars=list(rule_spec.select_vars), row_format=row_format)

    def _run_query(
        self,
        query: Any,
        *,
        row_format: str = "dict",
        registry: RuleRegistry | None = None,
    ) -> list[Any]:
        plan = self._lower_query(query, return_mode=row_format)
        return execute_query_plan(self, plan, registry=registry)

    def _lower_query(self, query: Any, *, return_mode: str = "dict") -> QueryPlan:
        try:
            from .dsl import Query as SDKQuery
        except Exception as exc:
            raise SDKStoreError(f"Query DSL is unavailable: {exc}", path="$.run.obj") from exc

        if not isinstance(query, SDKQuery):
            raise SDKStoreError("query must be Query", path="$.run.obj")

        return lower_query(
            query,
            schema_ir=self._schema_ir,
            schema_digest=self._schema_digest,
            return_mode=return_mode,
        )

    def _reject_removed_read_policy(self, policy: Any, *, api_path: str) -> None:
        if policy is _POLICY_TOMBSTONE:
            return
        raise SDKStoreError(f"{api_path}: {_READPOLICY_REMOVED_MESSAGE}")

    def inspect_semantics(self, profile: Any) -> dict[str, Any]:
        if isinstance(profile, SemanticsProfile):
            return inspect_semantics_profile(profile)
        if isinstance(profile, (ProbLogSemantics, PyReasonSemantics)):
            lowered = _preview_public_semantics(profile)
            inspected = inspect_semantics_profile(lowered)
            inspected["semantics_type"] = type(profile).__name__
            inspected["lowered_profile"] = _semantics_profile_preview(lowered)
            return inspected
        raise SDKStoreError("inspect_semantics(profile) expects SemanticsProfile or SDK public semantics")

    def inspect_rule(self, obj: Any) -> dict[str, Any]:
        return _inspect_rule_or_inference(obj)

    def save(self, path: str | Path | None = None) -> dict[str, Any]:
        """Persist this graph as a FactGraph workspace.

        A workspace contains the ledger, schema metadata, authoring registry,
        and a workspace manifest. If `path` is omitted, the graph must already
        be bound to a workspace path through `FactGraph.create(path=...)` or an
        earlier `fg.save(path)`.
        """
        self._reject_attached_write("fg.save")
        workspace_path = _normalize_workspace_path(path) or self._workspace_path
        if workspace_path is None:
            raise SDKStoreError(
                "workspace path not bound; pass fg.save(path=...) or create with FactGraph.create(path=...)"
            )
        try:
            write_schema_object_for_workspace(workspace_path, self.schema_ir)
            if self._authoring_registry is not None:
                self._authoring_registry.upsert_schema_ir(self.schema_ir)
            paths = app_save_workspace(
                workspace_path,
                schema_digest=self._schema_digest,
                ledger=self.ledger,
                source_registry=self._authoring_registry,
                schema_ir=self.schema_ir,
            )
        except Exception as exc:
            if isinstance(exc, SDKStoreError):
                raise
            raise SDKStoreError(str(exc)) from exc
        self._workspace_path = paths.root
        return {"path": str(paths.root), "manifest": str(paths.manifest)}

    @staticmethod
    def _reject_shell_semantics(*, semantics: Any, semantics_profile: Any) -> None:
        if semantics is not _PROFILE_KWARG_UNSET:
            raise SDKStoreError("semantics= is not accepted by SDK what_if shells in E; use fg.eval.evaluate(...)")
        if semantics_profile is not _PROFILE_KWARG_UNSET:
            raise SDKStoreError(
                "semantics_profile= is not accepted by SDK what_if shells in E; use fg.eval.evaluate(..., semantics=...)"
            )

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
            raise SDKStoreError(f"{api_path}: semantics= expects SemanticsProfile or None")
        if engine not in _SEMANTICS_PROFILE_ENGINES:
            raise SDKStoreError(f"engine='{engine}' does not consume SemanticsProfile")
        if raw.engine != engine:
            raise SDKStoreError(f"SemanticsProfile.engine='{raw.engine}' does not match engine='{engine}'")
        return raw

    def _resolve_public_engine_and_semantics(
        self,
        raw_engine: Any,
        raw_semantics: Any,
        *,
        derivation: Any | None,
        api_path: str,
    ) -> tuple[str, SemanticsProfile | None]:
        if raw_semantics is None:
            return (self._resolve_public_engine(raw_engine, api_path=api_path), None)

        semantics_engine = _public_semantics_engine(raw_semantics)
        if semantics_engine is None:
            raise SDKStoreError(f"{api_path}: semantics= expects SemanticsProfile or SDK public semantics")

        if isinstance(raw_semantics, SemanticsProfile):
            if raw_engine is None:
                engine = semantics_engine
            else:
                engine = self._resolve_public_engine(raw_engine, api_path=api_path)
                if engine not in _SEMANTICS_PROFILE_ENGINES:
                    raise SDKStoreError(f"engine='{engine}' does not consume SemanticsProfile")
                if raw_semantics.engine != engine:
                    raise SDKStoreError(
                        f"SemanticsProfile.engine='{raw_semantics.engine}' does not match engine='{engine}'"
                    )
            return (engine, raw_semantics)

        if raw_engine is None:
            engine = semantics_engine
        else:
            engine = self._resolve_public_engine(raw_engine, api_path=api_path)
            if engine != semantics_engine:
                raise SDKStoreError(
                    f"engine='{engine}' does not match semantics.engine='{semantics_engine}'"
                )

        if derivation is None or not hasattr(derivation, "where"):
            raise SDKStoreError("SDK public semantics require SDK Rule or Inference object input")
        return (engine, _lower_public_semantics(raw_semantics, derivation=derivation))

    def evaluate(self, *args: Any, **kwargs: Any) -> list[CandidateSet]:
        if "view" in kwargs or "policy" in kwargs:
            raise SDKStoreError(
                "evaluate() does not accept view=; policy= was removed for read APIs and is not accepted for inference evaluation"
            )
        if "semantics_profile" in kwargs:
            raise SDKStoreError("evaluate() does not accept semantics_profile= in SDK; use semantics=")
        if "mode" in kwargs:
            raise SDKStoreError("evaluate() does not accept mode= in E; use engine=")
        if "temporal_view" in kwargs:
            # TODO: temporal_view for evaluate() remains blocked.
            # Snapshot read views (.at/.version) are already implemented in sdk.facade.
            # Re-enable only after derivation/runtime temporal write semantics are defined.
            raise SDKStoreError("temporal_view is removed from evaluate(); use active/history views on read APIs")
        registry = kwargs.pop("registry", None)
        engine_options = kwargs.pop("engine_options", None)
        raw_engine = kwargs.pop("engine", None)
        raw_semantics = kwargs.pop("semantics", None)
        if args and isinstance(args[0], str):
            raise SDKStoreError(
                "string derivation DSL is not supported in SDK v1; use Inference object or structured derivation dict"
            )
        if args and hasattr(args[0], "to_authoring_payload"):
            derivation = args[0]
            engine, semantics_profile = self._resolve_public_engine_and_semantics(
                raw_engine,
                raw_semantics,
                derivation=derivation,
                api_path="evaluate()",
            )
            runtime_registry = self._resolve_runtime_registry(derivation, explicit_registry=registry)
            compiled_plans = self._compile_derivation_input(derivation)
            return self._evaluate_compiled_derivation_plans(
                compiled_plans,
                mode=engine,
                registry=runtime_registry,
                engine_options=engine_options,
                semantics_profile=semantics_profile,
            )
        if args and isinstance(args[0], dict) and ("derivation_id" in args[0] or "target_pred_id" in args[0] or "head" in args[0]):
            engine, semantics_profile = self._resolve_public_engine_and_semantics(
                raw_engine,
                raw_semantics,
                derivation=None,
                api_path="evaluate()",
            )
            compiled_plans = self._compile_derivation_input(args[0])
            return self._evaluate_compiled_derivation_plans(
                compiled_plans,
                mode=engine,
                registry=registry,
                engine_options=engine_options,
                semantics_profile=semantics_profile,
            )
        engine, semantics_profile = self._resolve_public_engine_and_semantics(
            raw_engine,
            raw_semantics,
            derivation=None,
            api_path="evaluate()",
        )
        if registry is not None:
            kwargs["registry"] = registry
        if engine_options is not None:
            kwargs["engine_options"] = engine_options
        kwargs["mode"] = engine
        if semantics_profile is not None:
            kwargs["semantics_profile"] = semantics_profile
        return self._store.evaluate(*args, **kwargs)

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

    @staticmethod
    def _derive_shared_run_id(derivation_id: Any) -> str:
        if isinstance(derivation_id, str) and derivation_id:
            return f"{derivation_id}:{uuid4().hex[:8]}"
        return f"derive:{uuid4().hex[:8]}"

    def accept(self, *args: Any, **kwargs: Any) -> AcceptResult:
        self._reject_attached_write("fg.accept")
        if args and isinstance(args[0], CandidateSet):
            if len(args) != 1:
                raise SDKStoreError("accept(candidate_set, ...) accepts exactly one positional argument")
            candidate_set = args[0]
            options = self._accept_options_from_user_kwargs(kwargs)
            if kwargs:
                unknown = ", ".join(sorted(kwargs.keys()))
                raise SDKStoreError(f"unknown accept keyword(s): {unknown}")
            return self._store.accept(
                derivation_id=candidate_set.derivation_id,
                version=candidate_set.derivation_version,
                candidate_set=candidate_set,
                options=options,
            )
        return self._store.accept(*args, **kwargs)

    def accept_many(
        self,
        requests: list[AcceptRequest | CandidateSet | dict[str, Any]],
        *,
        mode: str = "atomic",
        idempotent_duplicate_ok: bool = True,
    ) -> list[dict[str, Any]]:
        self._reject_attached_write("fg.accept_many")
        return self._store.accept_many(
            requests,
            mode=mode,
            idempotent_duplicate_ok=idempotent_duplicate_ok,
        )

    def explain_fact(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._store.explain_fact(*args, **kwargs)

    def conflicts(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._store.conflicts(*args, **kwargs)

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

    @staticmethod
    def _accept_options_from_user_kwargs(kwargs: dict[str, Any]) -> AcceptOptions:
        raw_meta_overrides = kwargs.pop("meta_overrides", None)
        if raw_meta_overrides is None:
            meta_overrides: dict[str, Any] = {}
        elif isinstance(raw_meta_overrides, dict):
            meta_overrides = dict(raw_meta_overrides)
        else:
            raise SDKStoreError("meta_overrides must be dict when provided")

        # Blueprints commonly use meta_overrides={"approved_by": ...}; also support keyword sugar.
        for key in ("approved_by", "note", "dry_run", "identity_override"):
            if key in kwargs:
                if key in meta_overrides:
                    raise SDKStoreError(f"duplicate accept option: {key} provided in meta_overrides and keyword")
                meta_overrides[key] = kwargs.pop(key)

        approved_by = meta_overrides.pop("approved_by", None)
        note = meta_overrides.pop("note", None)
        dry_run = meta_overrides.pop("dry_run", False)
        identity_override = meta_overrides.pop("identity_override", None)
        if identity_override is not None and not isinstance(identity_override, dict):
            raise SDKStoreError("identity_override must be dict when provided")
        if meta_overrides:
            unknown = ", ".join(sorted(meta_overrides.keys()))
            raise SDKStoreError(f"unsupported meta_overrides keys for accept(): {unknown}")
        return AcceptOptions(
            approved_by=approved_by,
            note=note,
            dry_run=bool(dry_run),
            identity_override=dict(identity_override) if isinstance(identity_override, dict) else None,
        )

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

        registry = self._authoring_registry
        if registry is None:
            return
        try:
            entry = registry.get_schema_entry()
        except Exception as exc:
            raise SDKStoreError(f"registry schema_digest unavailable: {exc}") from exc
        if entry is None:
            return
        registry_digest = entry.get("schema_digest")
        if registry_digest != old_digest:
            raise SDKStoreError(
                f"registry schema_digest mismatch: expected {old_digest!r}, got {registry_digest!r}"
            )

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
        registry = self._authoring_registry
        if registry is None:
            return
        try:
            registry.upsert_schema_ir(schema_ir)
        except Exception as exc:
            raise SDKStoreError(f"registry schema_digest update failed: {exc}") from exc

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


def _build_view_entry(
    name: str,
    *,
    asrt_ids: Iterable[str] | None,
    asrts: Iterable[Any] | None,
) -> FrozenAssertionView:
    payload_count = sum(value is not None for value in (asrt_ids, asrts))
    if payload_count != 1:
        raise SDKStoreError("provide exactly one view payload: asrt_ids=... or asrts=...")
    if asrts is not None:
        return FrozenAssertionView(
            name=name,
            asrt_ids=_normalize_asrt_ids_from_records(asrts),
        )
    return FrozenAssertionView(
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


def _default_uuid4_for_tag(tag: str) -> str:
    if tag == "uuid":
        return str(uuid4()).lower()
    if tag == "string":
        return uuid4().hex
    raise SDKStoreError(f"default_factory='uuid4' not supported for type_domain={tag}")


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
    where_value = getattr(derivation, "where", None)
    normalized_where, used_branch_wrapper = _normalize_where_branch_wrappers(
        where_value,
        path="$.where",
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
    if isinstance(value, ProbLogSemantics):
        return value.engine
    if isinstance(value, PyReasonSemantics):
        return value.engine
    return None


def _preview_public_semantics(value: ProbLogSemantics | PyReasonSemantics) -> SemanticsProfile:
    if isinstance(value, ProbLogSemantics):
        return SemanticsProfile(
            name=value.name or "problog",
            engine="problog",
            fallback=value.fallback,
        )
    if isinstance(value, PyReasonSemantics):
        rule_entries: list[dict[str, Any]] = []
        if value.head_bound is not None:
            rule_entries.append({"target": "head:0", "kind": "interval", "value": list(value.head_bound)})
        for branch_index, interval in _preview_branch_bounds(value.branch_bounds):
            rule_entries.append({"target": f"branch:{branch_index}", "kind": "interval", "value": list(interval)})
        if value.timestep_delay:
            rule_entries.append({"target": "rule", "kind": "timestep_delay", "value": value.timestep_delay})
        return SemanticsProfile(
            name=value.name or "pyreason",
            engine="pyreason",
            rule_projection={"pyreason": rule_entries} if rule_entries else {},
            temporal_projection=dict(value.temporal_projection),
            uncertainty_projection=dict(value.uncertainty_projection),
            fallback=value.fallback,
        )
    raise SDKStoreError("unsupported public semantics wrapper")


def _lower_public_semantics(value: Any, *, derivation: Any) -> SemanticsProfile:
    if isinstance(value, ProbLogSemantics):
        branch_indexes = _branch_id_index_for_derivation(derivation)
        entries: list[dict[str, Any]] = []
        for branch_id, probability in value.branch_probabilities.items():
            branch_index = branch_indexes.get(branch_id)
            if branch_index is None:
                raise SDKStoreError(f"unknown branch id {branch_id!r} for ProbLogSemantics.branch_probabilities")
            entries.append(
                {
                    "target": f"branch:{branch_index}",
                    "kind": "branch_probability",
                    "value": probability,
                }
            )
        return SemanticsProfile(
            name=value.name or _default_semantics_name(derivation, engine="problog"),
            engine="problog",
            rule_projection={"problog": entries} if entries else {},
            fallback=value.fallback,
        )
    if isinstance(value, PyReasonSemantics):
        rule_entries: list[dict[str, Any]] = []
        if value.head_bound is not None:
            rule_entries.append({"target": "head:0", "kind": "interval", "value": list(value.head_bound)})
        branch_indexes = _branch_id_index_for_derivation(derivation)
        for branch_id, interval in value.branch_bounds.items():
            branch_index = branch_indexes.get(branch_id)
            if branch_index is None:
                known = ", ".join(sorted(branch_indexes)) or "<none>"
                raise SDKStoreError(
                    f"branch_bounds contains unknown branch id {branch_id!r}; known branch ids: {known}"
                )
            rule_entries.append({"target": f"branch:{branch_index}", "kind": "interval", "value": list(interval)})
        if value.timestep_delay:
            rule_entries.append({"target": "rule", "kind": "timestep_delay", "value": value.timestep_delay})
        return SemanticsProfile(
            name=value.name or _default_semantics_name(derivation, engine="pyreason"),
            engine="pyreason",
            rule_projection={"pyreason": rule_entries} if rule_entries else {},
            temporal_projection=dict(value.temporal_projection),
            uncertainty_projection=dict(value.uncertainty_projection),
            fallback=value.fallback,
        )
    raise SDKStoreError("unsupported public semantics wrapper")


def _preview_branch_bounds(
    branch_bounds: dict[str, tuple[float, float]],
) -> list[tuple[int, tuple[float, float]]]:
    preview: list[tuple[int, tuple[float, float]]] = []
    for idx, interval in enumerate(branch_bounds.values()):
        preview.append((idx, interval))
    return preview


def _semantics_profile_preview(profile: SemanticsProfile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "version": profile.version,
        "engine": profile.engine,
        "fallback": profile.fallback,
        "rule_projection": profile.rule_projection,
        "engine_options": profile.engine_options,
        "uncertainty_projection": profile.uncertainty_projection,
        "temporal_projection": profile.temporal_projection,
        "certainty_projection": profile.certainty_projection,
        "output_readback": profile.output_readback,
    }


def _branch_id_index_for_derivation(derivation: Any) -> dict[str, int]:
    where = getattr(derivation, "where", None)
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


def _default_semantics_name(derivation: Any, *, engine: str) -> str:
    derivation_id = getattr(derivation, "id", None)
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
            "branches": _inspect_where_branches(obj.where),
        }
    raise SDKStoreError("rules.inspect(...) expects SDK Rule or Inference")


def _inspect_where_branches(where: Any) -> list[dict[str, Any]]:
    if not isinstance(where, list) or not where:
        raise SDKStoreError("rules.inspect(...) requires non-empty where")

    if all(isinstance(item, Branch) for item in where):
        raw_branches = [(item.id, list(item.atoms)) for item in where]
    elif any(isinstance(item, Branch) for item in where):
        raise SDKStoreError("where/branch cannot mix Branch(...) with bare branches")
    elif _where_items_are_atoms(where):
        raw_branches = [(None, list(where))]
    else:
        raw_branches = [(None, list(branch)) for branch in where if isinstance(branch, list)]
        if len(raw_branches) != len(where) or not raw_branches:
            raise SDKStoreError("rules.inspect(...) where must be atoms or branch lists")

    out: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    for idx, (explicit_id, atoms) in enumerate(raw_branches):
        fallback_id = f"b{idx}"
        branch_id = explicit_id if explicit_id is not None else fallback_id
        if branch_id in seen_ids:
            raise SDKStoreError(f"duplicate Branch.id {branch_id!r} in inspected where")
        seen_ids[branch_id] = idx
        out.append(
            {
                "id": branch_id,
                "fallback_id": fallback_id,
                "is_explicit_id": explicit_id is not None,
                "index": idx,
                "atom_count": len(atoms),
                "atoms": _lower_inspect_atoms(atoms),
                "atom_ids": [f"{fallback_id}.a{atom_idx}" for atom_idx, _atom in enumerate(atoms)],
            }
        )
    return out


def _where_items_are_atoms(where: list[Any]) -> bool:
    return bool(where) and all(not isinstance(item, list) and not isinstance(item, Branch) for item in where)


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
            "use ProbLogRuleExt.branch_probabilities or future SemanticsProfile.rule_projection.problog",
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

    target = getattr(derivation, "target", None)
    if target is not None:
        payload["target"] = target

    head_vars = getattr(derivation, "head_vars", None)
    if head_vars is not None:
        if not isinstance(head_vars, list):
            raise SDKStoreError("derivation.head_vars must be list when provided", path="$.head_vars")
        payload["head_vars"] = [_lower_derivation_head_var(item) for item in head_vars]

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

    has_branch_wrapper = any(isinstance(item, Branch) for item in raw_where)
    if not has_branch_wrapper:
        return raw_where, False
    if not all(isinstance(item, Branch) for item in raw_where):
        raise SDKStoreError("where/branch cannot mix Branch(...) with bare branches", path=path)

    branches: list[list[Any]] = []
    for idx, branch in enumerate(raw_where):
        atoms = list(branch.atoms)
        if not atoms:
            raise SDKStoreError("Branch.atoms must be non-empty list", path=f"{path}[{idx}]")
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


def _resolve_row_format(*, call_site: Any, store_default: Any, env_var: Any) -> str:
    for raw_value, path, source in (
        (call_site, "$.run.row_format", "call_site"),
        (store_default, "$.store.default_row_format", "store_default"),
        (env_var, "env:FACTPY_ROW_FORMAT", "env_var"),
    ):
        normalized = _normalize_row_format_value(raw_value, path=path)
        if normalized is not None:
            _warn_deprecated_tuple_row_format_if_needed(normalized, source=source)
            return normalized
    return "dict"


def _resolve_query_row_format(value: Any) -> str:
    if value is None:
        return "dict"
    if not isinstance(value, str):
        raise SDKStoreError(
            "Query row_format must be 'dict' or 'instance'",
            code=QUERY_INVALID_ROW_FORMAT,
            path="$.run.row_format",
        )
    normalized = value.strip().lower()
    if normalized not in {"dict", "instance"}:
        raise SDKStoreError(
            "Query row_format must be 'dict' or 'instance'",
            code=QUERY_INVALID_ROW_FORMAT,
            path="$.run.row_format",
        )
    return normalized


def _normalize_row_format_value(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SDKStoreError(
            "row_format must be 'tuple' or 'dict'",
            code=INVALID_ROW_FORMAT,
            path=path,
        )
    normalized = value.strip().lower()
    if normalized not in {"tuple", "dict"}:
        raise SDKStoreError(
            "row_format must be 'tuple' or 'dict'",
            code=INVALID_ROW_FORMAT,
            path=path,
        )
    return normalized


def _warn_deprecated_tuple_row_format_if_needed(normalized: str, *, source: str) -> None:
    if normalized != "tuple":
        return
    warnings.warn(
        "row_format='tuple' is deprecated and will be removed in a future release "
        f"(source={source}); use row_format='dict' or set FACTPY_ROW_FORMAT=dict.",
        DeprecationWarning,
        stacklevel=4,
    )


def _format_rule_rows(
    rows: list[tuple[Any, ...]],
    *,
    select_vars: list[str],
    row_format: str,
) -> list[tuple[Any, ...]] | list[dict[str, Any]]:
    if row_format == "tuple":
        return rows
    if row_format != "dict":
        raise SDKStoreError(
            "row_format must be 'tuple' or 'dict'",
            code=INVALID_ROW_FORMAT,
            path="$.run.row_format",
        )

    columns: list[str] = []
    seen: set[str] = set()
    for idx, var in enumerate(select_vars):
        if not isinstance(var, str) or not var:
            raise SDKStoreError(
                "rule select_vars must be non-empty strings for row_format='dict'",
                code=INVALID_ROW_FORMAT,
                path=f"$.rule.select_vars[{idx}]",
            )
        key = var[1:] if var.startswith("$") else var
        if not key:
            raise SDKStoreError(
                "rule select_vars must not be empty for row_format='dict'",
                code=INVALID_ROW_FORMAT,
                path=f"$.rule.select_vars[{idx}]",
            )
        if key in seen:
            raise SDKStoreError(
                f"rule select_vars are not unique after alias normalization: {key}",
                code=INVALID_ROW_FORMAT,
                path=f"$.rule.select_vars[{idx}]",
            )
        seen.add(key)
        columns.append(key)

    out: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        if len(row) != len(columns):
            raise SDKStoreError(
                f"row arity mismatch at row {row_index}: expected {len(columns)}, got {len(row)}",
                code=INVALID_ROW_FORMAT,
                path="$.run.result",
            )
        out.append({col: row[col_index] for col_index, col in enumerate(columns)})
    return out


def _is_sdk_query_object(obj: Any) -> bool:
    try:
        from .dsl import Query
    except Exception:
        return False
    return isinstance(obj, Query)


def _is_derivation_run_object(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(key in obj for key in ("derivation_id", "target_pred_id", "head"))
    try:
        from .dsl import Inference
    except Exception:
        return False
    return isinstance(obj, Inference)


# Post-L SDK ergonomics redesign (locked at §5.3 / §5.7) — `FactGraph` is
# the canonical user-facing entrypoint name. Literal alias of `SDKStore`
# per §5.7 non-commitment #1 ("NOT a replacement of `SDKStore`"); both
# names resolve to the same class. `SDKStore` stays as the canonical
# implementation behind the `FactGraph` taxonomy and remains permanently
# callable per §5.4 Option 2 lock.
FactGraph = SDKStore
