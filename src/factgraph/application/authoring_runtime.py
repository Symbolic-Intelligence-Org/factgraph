"""Application-layer authoring asset error type.

Q8 Phase 2 removed the SavedRule/SavedInference persistence helpers that
previously lived in this module. ``AuthoringRuntimeError`` is preserved as a
forward-compat application-layer error import. Slice 6 verified zero current
external consumers via preflight `511d83f5` PF-8; the minimal-module lock keeps
``application.authoring_runtime.AuthoringRuntimeError`` importable for any
future application-layer error path without re-introducing SavedRule
persistence. Rules and inferences now live in user Python code as in-memory
``Rule(...)`` / ``Inference(...)`` values and reach evaluators via
``_register_rule_dependencies`` + ``RuleRegistry``.
"""
from __future__ import annotations


class AuthoringRuntimeError(ValueError):
    pass


__all__ = ["AuthoringRuntimeError"]
