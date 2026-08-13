from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from .common import ProtocolShapeError
from .evaluation_run import _plain, _sha_hex, _sha_token, _token
from .policy import PolicyStructureV0
from .semantic_address import SemanticPortAddress

PolicyExplanationState: TypeAlias = Literal[
    "holds", "fails", "not_reached", "not_applicable", "indeterminate",
]
PolicyBranchParticipation: TypeAlias = Literal[
    "contributes", "policy_failed", "outside_policy_filtered", "blocked", "unknown",
]
PolicyEvidenceKind: TypeAlias = Literal["atom", "join", "condition"]
_STATES = {"holds", "fails", "not_reached", "not_applicable", "indeterminate"}
_TREE_STATES = {"holds", "fails", "not_reached"}
_PARTICIPATION = {
    "contributes", "policy_failed", "outside_policy_filtered", "blocked", "unknown",
}

class PolicyExplanationProjectionError(ProtocolShapeError):
    """Raised when engine evidence cannot be totally mapped to authored Policy."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code

@dataclass(frozen=True)
class PolicyEvidenceLocatorV0:
    """A direct locator into the unchanged inner ``EvidenceGraph``."""

    branch_id: str
    evidence_kind: PolicyEvidenceKind
    evidence_id: str
    status: Literal["holds", "fails", "not_reached"]
    occurrence_alias: str | None = None
    left: SemanticPortAddress | None = None
    right: SemanticPortAddress | None = None
    policy_node_id: str | None = None
    condition_id: str | None = None
    condition_role: Literal["left_field", "right_field", "compare"] | None = None
    source_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.branch_id, "branch_id")
        _text(self.evidence_id, "evidence_id")
        if self.evidence_kind not in {"atom", "join", "condition"}:
            raise ProtocolShapeError("Policy evidence kind must be atom, join, or condition")
        if self.status not in _TREE_STATES:
            raise ProtocolShapeError("Policy evidence status is invalid")
        atom_shape = (
            self.occurrence_alias is not None
            and self.left is None
            and self.right is None
            and self.policy_node_id is None
            and self.condition_id is None
            and self.condition_role is None
        )
        join_shape = (
            self.occurrence_alias is None
            and isinstance(self.left, SemanticPortAddress)
            and isinstance(self.right, SemanticPortAddress)
            and self.left != self.right
            and self.policy_node_id is None
            and self.condition_id is None
            and self.condition_role is None
        )
        condition_shape = (
            self.occurrence_alias is None
            and self.left is None
            and self.right is None
            and isinstance(self.policy_node_id, str)
            and bool(self.policy_node_id)
            and isinstance(self.condition_id, str)
            and bool(self.condition_id)
            and self.condition_role in {"left_field", "right_field", "compare"}
        )
        if (self.evidence_kind == "atom" and not atom_shape) or (
            self.evidence_kind == "join" and not join_shape
        ) or (
            self.evidence_kind == "condition" and not condition_shape
        ):
            raise ProtocolShapeError("Policy evidence fields do not match evidence kind")
        if self.occurrence_alias is not None:
            _text(self.occurrence_alias, "occurrence_alias")
        _canonical_text_tuple(self.source_refs, "source_refs")

@dataclass(frozen=True)
class PolicyNodeBranchStateV0:
    branch_id: str
    state: PolicyExplanationState

    def __post_init__(self) -> None:
        _text(self.branch_id, "branch_id")
        _state(self.state, "state")

@dataclass(frozen=True)
class PolicyNodeEvaluationV0:
    node_id: str
    kind: Literal["occurrence", "all", "any", "unify", "compare"]
    state: PolicyExplanationState
    branch_states: tuple[PolicyNodeBranchStateV0, ...]

    def __post_init__(self) -> None:
        _text(self.node_id, "node_id")
        if self.kind not in {"occurrence", "all", "any", "unify", "compare"}:
            raise ProtocolShapeError("Policy explanation node kind is invalid")
        _state(self.state, "state")
        _typed_tuple(self.branch_states, PolicyNodeBranchStateV0, "branch_states")
        branch_ids = tuple(item.branch_id for item in self.branch_states)
        if not branch_ids or branch_ids != tuple(sorted(set(branch_ids))):
            raise ProtocolShapeError("Policy node branch states must be non-empty and canonical")

@dataclass(frozen=True)
class PolicyBranchEvaluationV0:
    branch_id: str
    policy_root_state: Literal["holds", "fails", "not_reached"]
    evidence_path_state: Literal["holds", "fails", "not_reached"]
    participation: PolicyBranchParticipation

    def __post_init__(self) -> None:
        _text(self.branch_id, "branch_id")
        if self.policy_root_state not in _TREE_STATES or self.evidence_path_state not in _TREE_STATES:
            raise ProtocolShapeError("Policy branch state is invalid")
        if self.participation not in _PARTICIPATION:
            raise ProtocolShapeError("Policy branch participation is invalid")

@dataclass(frozen=True)
class PolicyEvaluationProjectionV0:
    root_node_id: str
    root_state: PolicyExplanationState
    nodes: tuple[PolicyNodeEvaluationV0, ...]
    branches: tuple[PolicyBranchEvaluationV0, ...]

    def __post_init__(self) -> None:
        _text(self.root_node_id, "root_node_id")
        _state(self.root_state, "root_state")
        _typed_tuple(self.nodes, PolicyNodeEvaluationV0, "nodes")
        _typed_tuple(self.branches, PolicyBranchEvaluationV0, "branches")
        node_ids = tuple(item.node_id for item in self.nodes)
        branch_ids = tuple(item.branch_id for item in self.branches)
        if not node_ids or node_ids != tuple(sorted(set(node_ids))):
            raise ProtocolShapeError("Policy explanation nodes must be non-empty and canonical")
        if self.root_node_id not in set(node_ids):
            raise ProtocolShapeError("Policy explanation root node is absent")
        if not branch_ids or branch_ids != tuple(sorted(set(branch_ids))):
            raise ProtocolShapeError("Policy explanation branches must be non-empty and canonical")
        root = next(item for item in self.nodes if item.node_id == self.root_node_id)
        if root.state != self.root_state:
            raise ProtocolShapeError("Policy explanation root state does not match root node")
        if any(
            tuple(item.branch_id for item in node.branch_states) != branch_ids
            for node in self.nodes
        ):
            raise ProtocolShapeError("Every Policy node must cover every projected branch")

@dataclass(frozen=True)
class PolicyNodeProvenanceV0:
    node_id: str
    locators: tuple[PolicyEvidenceLocatorV0, ...]

    def __post_init__(self) -> None:
        _text(self.node_id, "node_id")
        _typed_tuple(self.locators, PolicyEvidenceLocatorV0, "locators")
        if self.locators != tuple(sorted(self.locators, key=_locator_key)):
            raise ProtocolShapeError("Policy evidence locators must be canonically ordered")
        keys = tuple(_locator_key(item) for item in self.locators)
        if len(keys) != len(set(keys)):
            raise ProtocolShapeError("Policy evidence locators must be unique")

@dataclass(frozen=True)
class PolicyProvenanceIndexV0:
    node_evidence: tuple[PolicyNodeProvenanceV0, ...]
    outside_policy_lineage: tuple[PolicyEvidenceLocatorV0, ...]
    coverage: Literal["lineage_total_for_projected_branches"]
    source_identity: Literal["inner_evidence_source_refs"]
    authenticity: Literal["unverified"]

    def __post_init__(self) -> None:
        _typed_tuple(self.node_evidence, PolicyNodeProvenanceV0, "node_evidence")
        _typed_tuple(
            self.outside_policy_lineage,
            PolicyEvidenceLocatorV0,
            "outside_policy_lineage",
        )
        node_ids = tuple(item.node_id for item in self.node_evidence)
        if not node_ids or node_ids != tuple(sorted(set(node_ids))):
            raise ProtocolShapeError("Policy provenance nodes must be non-empty and canonical")
        if self.outside_policy_lineage != tuple(
            sorted(self.outside_policy_lineage, key=_locator_key)
        ):
            raise ProtocolShapeError("Outside-Policy evidence must be canonically ordered")
        outside_keys = tuple(_locator_key(item) for item in self.outside_policy_lineage)
        direct_keys = tuple(
            _locator_key(locator)
            for entry in self.node_evidence
            for locator in entry.locators
        )
        if len(outside_keys) != len(set(outside_keys)) or set(outside_keys) & set(direct_keys):
            raise ProtocolShapeError("Policy provenance evidence inventory is not disjoint")
        if (
            self.coverage,
            self.source_identity,
            self.authenticity,
        ) != (
            "lineage_total_for_projected_branches",
            "inner_evidence_source_refs",
            "unverified",
        ):
            raise ProtocolShapeError("Policy provenance semantics are outside v0")

@dataclass(frozen=True)
class PolicyExplanationViewV0:
    run_anchor_digest: str
    semantic_row_anchor_digest: str
    query_digest: str
    policy_id: str
    policy_version: str | None
    policy_digest: str
    structure_digest: str
    evidence_graph_id: str
    structure: PolicyStructureV0
    evaluation: PolicyEvaluationProjectionV0
    provenance: PolicyProvenanceIndexV0
    interpretation: Literal["logical_policy_evidence_not_authorization"]
    projection_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _sha_token(self.run_anchor_digest, "run_anchor_digest")
        _sha_token(self.semantic_row_anchor_digest, "semantic_row_anchor_digest")
        _sha_hex(self.query_digest, "query_digest")
        _text(self.policy_id, "policy_id")
        if self.policy_version is not None:
            _text(self.policy_version, "policy_version")
        _sha_hex(self.policy_digest, "policy_digest")
        _sha_hex(self.structure_digest, "structure_digest")
        _text(self.evidence_graph_id, "evidence_graph_id")
        if not isinstance(self.structure, PolicyStructureV0):
            raise ProtocolShapeError("Policy explanation structure is invalid")
        if not isinstance(self.evaluation, PolicyEvaluationProjectionV0):
            raise ProtocolShapeError("Policy explanation evaluation is invalid")
        if not isinstance(self.provenance, PolicyProvenanceIndexV0):
            raise ProtocolShapeError("Policy explanation provenance is invalid")
        if self.structure.structure_digest != self.structure_digest:
            raise ProtocolShapeError("Policy explanation structure digest mismatch")
        if self.structure.root_node_id != self.evaluation.root_node_id:
            raise ProtocolShapeError("Policy explanation structure and evaluation roots disagree")
        structure_nodes = tuple(node.node_id for node in self.structure.nodes)
        if structure_nodes != tuple(node.node_id for node in self.evaluation.nodes):
            raise ProtocolShapeError("Policy explanation evaluation does not cover structure")
        if structure_nodes != tuple(item.node_id for item in self.provenance.node_evidence):
            raise ProtocolShapeError("Policy explanation provenance does not cover structure")
        if self.interpretation != "logical_policy_evidence_not_authorization":
            raise ProtocolShapeError("Policy explanation interpretation is outside v0")
        values = tuple(
            getattr(self, name)
            for name in self.__dataclass_fields__
            if name != "projection_digest"
        )
        object.__setattr__(
            self,
            "projection_digest",
            _token("policy_explanation_view_v0", _plain(values)),
        )

def _locator_key(locator: PolicyEvidenceLocatorV0) -> tuple[str, str, str, str, str, str, str]:
    return (
        locator.branch_id,
        locator.evidence_kind,
        locator.evidence_id,
        locator.occurrence_alias or "",
        locator.policy_node_id or "",
        locator.condition_id or "",
        locator.condition_role or "",
    )

def _typed_tuple(value: object, item_type: type[object], name: str) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, item_type) for item in value):
        raise ProtocolShapeError(f"Policy explanation {name} has invalid shape")

def _canonical_text_tuple(value: object, name: str) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, str) and item for item in value):
        raise ProtocolShapeError(f"Policy explanation {name} must be a string tuple")
    if value != tuple(sorted(set(value))):
        raise ProtocolShapeError(f"Policy explanation {name} must be unique and canonical")

def _state(value: object, name: str) -> None:
    if value not in _STATES:
        raise ProtocolShapeError(f"Policy explanation {name} is invalid")

def _text(value: object, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ProtocolShapeError(f"Policy explanation {name} must be non-empty string")

__all__ = [
    "PolicyBranchEvaluationV0", "PolicyBranchParticipation", "PolicyEvaluationProjectionV0",
    "PolicyEvidenceKind", "PolicyEvidenceLocatorV0", "PolicyExplanationProjectionError",
    "PolicyExplanationState", "PolicyExplanationViewV0", "PolicyNodeBranchStateV0",
    "PolicyNodeEvaluationV0", "PolicyNodeProvenanceV0", "PolicyProvenanceIndexV0",
]
