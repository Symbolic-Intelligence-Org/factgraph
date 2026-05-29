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
    "EntityNotFoundError",
    "FrozenSnapshotError",
    "SDKDSLError",
    "SDKError",
    "SDKSchemaError",
    "SDKStoreError",
    "SDKValueError",
]
