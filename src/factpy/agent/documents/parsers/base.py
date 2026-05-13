from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import DocumentSegment, DocumentSource


@dataclass(frozen=True)
class ParseError(ValueError):
    kind: str
    message: str

    def __str__(self) -> str:
        return self.message


class DocumentParser(Protocol):
    parser_name: str
    parser_version: str
    supported_doc_types: tuple[str, ...]

    def can_parse(self, doc_type: str) -> bool: ...

    def parse(
        self,
        source: DocumentSource,
        content: bytes,
    ) -> list[DocumentSegment]: ...
