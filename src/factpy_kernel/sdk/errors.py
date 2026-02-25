from __future__ import annotations


class SDKError(Exception):
    pass


class SDKSchemaError(SDKError):
    pass


class SDKStoreError(SDKError):
    pass


class SDKRegistryError(SDKError):
    pass


class EntityNotFoundError(SDKStoreError):
    def __init__(
        self,
        *args: object,
        entity_type: str | None = None,
        identity_kwargs: dict | None = None,
    ) -> None:
        super().__init__(*args)
        self.entity_type = entity_type
        self.identity_kwargs = dict(identity_kwargs or {})


class FrozenSnapshotError(SDKStoreError):
    pass


class CardinalityError(SDKStoreError):
    def __init__(
        self,
        *args: object,
        field_name: str | None = None,
        actual_cardinality: str | None = None,
        operation: str | None = None,
    ) -> None:
        super().__init__(*args)
        self.field_name = field_name
        self.actual_cardinality = actual_cardinality
        self.operation = operation


class EditorClosedError(SDKStoreError):
    pass
