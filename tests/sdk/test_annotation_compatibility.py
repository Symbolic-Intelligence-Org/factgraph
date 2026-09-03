from __future__ import annotations

import importlib
import sys
from typing import get_type_hints

import pytest


@pytest.mark.parametrize(
    ("module_name", "member_path", "field_name", "py310", "py311"),
    [
        (
            "factgraph.adapters.souffle.provenance",
            "SouffleProofNodeV0",
            "children",
            "tuple['SouffleProofNodeV0', ...]",
            "tuple[factgraph.adapters.souffle.provenance.SouffleProofNodeV0, ...]",
        ),
        (
            "factgraph.adapters.souffle.provenance",
            "SouffleProofNodeV0.__init__",
            "children",
            "tuple['SouffleProofNodeV0', ...]",
            "tuple[factgraph.adapters.souffle.provenance.SouffleProofNodeV0, ...]",
        ),
        (
            "factgraph.application.portable_evaluation_runtime",
            "_ValidatedPortableInput",
            "execution_branches",
            "tuple['_PortableExecutionBranch', ...]",
            "tuple[factgraph.application.portable_evaluation_runtime._PortableExecutionBranch, ...]",
        ),
        (
            "factgraph.application.portable_evaluation_runtime",
            "_ValidatedPortableInput.__init__",
            "execution_branches",
            "tuple['_PortableExecutionBranch', ...]",
            "tuple[factgraph.application.portable_evaluation_runtime._PortableExecutionBranch, ...]",
        ),
        (
            "factgraph.application.protocol.derivation_why_not",
            "_validate_ordered_partition",
            "failed",
            "tuple['WhyNotFailedRow', ...]",
            "tuple[factgraph.application.protocol.derivation_why_not.WhyNotFailedRow, ...]",
        ),
        (
            "factgraph.application.protocol.proofframe",
            "_validate_atom_verdicts",
            "return",
            "tuple['ProofFrameConditionVerdict', ...]",
            "tuple[factgraph.application.protocol.proofframe.ProofFrameConditionVerdict, ...]",
        ),
        (
            "factgraph.application.protocol.proofframe",
            "aggregate_proof_frame_status",
            "atom_verdicts",
            "tuple['ProofFrameConditionVerdict', ...]",
            "tuple[factgraph.application.protocol.proofframe.ProofFrameConditionVerdict, ...]",
        ),
        (
            "factgraph.sdk.batch",
            "ManagedEntityHandle._dependencies",
            "return",
            "list['ManagedEntityHandle']",
            "list[factgraph.sdk.batch.ManagedEntityHandle]",
        ),
        (
            "factgraph.sdk.facade",
            "AssertionView.__init__",
            "field_map",
            "typing.Optional[dict[str, 'AssertionView']]",
            "dict[str, factgraph.sdk.facade.AssertionView] | None",
        ),
        (
            "factgraph.sdk.product_authoring",
            "FunctionOccurrenceHandleV1.__init__",
            "function_occurrences",
            "collections.abc.Mapping[str, 'FunctionOccurrenceHandleV1']",
            "collections.abc.Mapping[str, factgraph.sdk.product_authoring.FunctionOccurrenceHandleV1]",
        ),
        (
            "factgraph.sdk.product_authoring",
            "_policy_logical_identity",
            "choices",
            "tuple['WeightedChoiceTopologyV1', ...]",
            "tuple[factgraph.sdk.product_authoring.WeightedChoiceTopologyV1, ...]",
        ),
        (
            "factgraph.sdk.product_authoring",
            "_policy_logical_identity",
            "functions",
            "tuple['FunctionOccurrenceTopologyV1', ...]",
            "tuple[factgraph.sdk.product_authoring.FunctionOccurrenceTopologyV1, ...]",
        ),
        (
            "factgraph.sdk.store",
            "FactGraph._outputs_for_derivation",
            "return",
            "tuple[list[factgraph.core.derivation.candidates.DerivationOutput], list[dict[str, typing.Any]], str, 'SemanticsProfile | None']",
            "tuple[list[factgraph.core.derivation.candidates.DerivationOutput], list[dict[str, typing.Any]], str, factgraph.core.semantics.profile.SemanticsProfile | None]",
        ),
        (
            "factgraph.sdk.store",
            "SDKStore._outputs_for_derivation",
            "return",
            "tuple[list[factgraph.core.derivation.candidates.DerivationOutput], list[dict[str, typing.Any]], str, 'SemanticsProfile | None']",
            "tuple[list[factgraph.core.derivation.candidates.DerivationOutput], list[dict[str, typing.Any]], str, factgraph.core.semantics.profile.SemanticsProfile | None]",
        ),
    ],
)
def test_nested_forward_hints_preserve_supported_python_behavior(
    module_name, member_path, field_name, py310, py311
):
    member = importlib.import_module(module_name)
    for part in member_path.split("."):
        member = getattr(member, part)
    expected = py310 if sys.version_info[:2] == (3, 10) else py311
    assert repr(get_type_hints(member)[field_name]) == expected

