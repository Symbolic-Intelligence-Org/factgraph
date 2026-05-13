"""Core semantic API for factgraph factgraph."""

from factgraph.core.derivation.accept import AcceptOptions, AcceptResult, accept_candidate_set
from factgraph.core.derivation.candidates import CandidateSet
from factgraph.core.evidence.write_protocol import (
    add_field,
    replace_field,
    retract_by_asrt,
    set_field,
)
from factgraph.core.protocol.idref_v1 import encode_idref_v1
from factgraph.core.rules.rule_ir import RuleRegistry, RuleSpec, run_rule
from factgraph.core.schema.schema_ir import ensure_schema_ir, schema_digest
from factgraph.core.store.runtime import Store
from factgraph.core.store.ledger import Ledger

__all__ = [
    "AcceptOptions",
    "AcceptResult",
    "CandidateSet",
    "Ledger",
    "RuleRegistry",
    "RuleSpec",
    "Store",
    "accept_candidate_set",
    "add_field",
    "encode_idref_v1",
    "ensure_schema_ir",
    "replace_field",
    "retract_by_asrt",
    "run_rule",
    "schema_digest",
    "set_field",
]
