from __future__ import annotations


class SDKError(Exception):
    def __init__(self, message: str, *, code: str | None = None, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path


class SDKSchemaError(SDKError):
    pass


class SDKStoreError(SDKError):
    pass


class SDKValueError(SDKStoreError):
    pass


class SDKDSLError(SDKError):
    pass


class EntityNotFoundError(SDKStoreError):
    def __init__(
        self,
        message: str,
        entity_type: str | None = None,
        identity_kwargs: dict | None = None,
        code: str | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message, code=code, path=path)
        self.entity_type = entity_type
        self.identity_kwargs = dict(identity_kwargs or {})


class EntityAlreadyExistsError(SDKStoreError):
    """Raised by ``fg.entities.create`` when an entity with the supplied
    identity bundle is already visible in the ledger.

    Per ADR-IC §4.2.1 + ADR-API §4.1 — ``fg.entities.create`` is the eager
    emission entry point for Identity Claims;duplicate create is a contract
    violation because the underlying ``_materialization_ops`` path is dedup-
    aware but the user-facing ``create`` semantics demand explicit rejection
    on second attempt(per Slice 3a §13.1 design-point + blueprint §5.3)。

    Use ``fg.entities.get(EC, **identity)`` to check entity existence cheaply
    or ``fg.entities.exists(EC, **identity)``(Step 4)to query directly。
    """

    def __init__(
        self,
        message: str,
        entity_type: str | None = None,
        identity_kwargs: dict | None = None,
        e_ref: str | None = None,
        code: str | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message, code=code, path=path)
        self.entity_type = entity_type
        self.identity_kwargs = dict(identity_kwargs or {})
        self.e_ref = e_ref


class SchemaConflictError(SDKStoreError):
    pass


class SchemaNotFoundError(SDKStoreError):
    pass


class SchemaNonAdditiveError(SDKStoreError):
    pass


class FrozenSnapshotError(SDKStoreError):
    pass


class CardinalityError(SDKStoreError):
    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        actual_cardinality: str | None = None,
        operation: str | None = None,
        code: str | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message, code=code, path=path)
        self.field_name = field_name
        self.actual_cardinality = actual_cardinality
        self.operation = operation


class EditorClosedError(SDKStoreError):
    pass


__all__ = [
    "CardinalityError",
    "EditorClosedError",
    "EntityAlreadyExistsError",
    "EntityNotFoundError",
    "FrozenSnapshotError",
    "SchemaConflictError",
    "SchemaNonAdditiveError",
    "SchemaNotFoundError",
    "SDKDSLError",
    "SDKError",
    "SDKSchemaError",
    "SDKStoreError",
    "SDKValueError",
]
