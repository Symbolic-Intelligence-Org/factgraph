"""Mapper interface for exporting IR to target languages."""

from __future__ import annotations

from abc import ABC, abstractmethod

from symir.ir.types import IRProgram


class Mapper(ABC):
    """Base class for mapping IR programs into target languages."""

    @abstractmethod
    def to_language(self, program: IRProgram) -> str:
        """Serialize an IR program into the target language."""

        raise NotImplementedError
