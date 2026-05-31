"""Cross-cutting invariants for G5 ProofFrame Diff SDK shell.

Mirrors G1's `test_sdk_g1_invariants.py`, G4's
`test_sdk_g4_invariants.py`, G2's `test_sdk_g2_invariants.py`, and
G3's `test_sdk_g3_invariants.py` 6-class structure under the
`factgraph/sdk/shells/` subpackage layout (now hosting 9 modules
post-G5).

Active classes:

1. `test_sdk_all_unchanged_and_g5_result_types_not_exported` — §5.3 / §5.4
2. `test_g5_flat_method_is_removed_and_no_scenario_method_shipped` — Q-NAMING-C
3. `test_g5_module_lives_in_shells_subpackage` — §5.5 + §5.6
4. `test_g5_module_does_not_import_internal_or_walker_layers` — §6 layer
   isolation (with the explicit `factgraph.audit.proof_frame_diff` +
   `factgraph.audit.round_events` allowlist per §6 G5 carve)
5. `test_private_helper_holds_capability_logic` — Q-NAMING-C private helper retention
6. `test_store_method_docstring_records_boundary_contract` — §5.7 + §6 docstring
"""

from __future__ import annotations

import inspect
import pathlib
import unittest
from importlib import import_module

from factgraph import sdk as factgraph_sdk
from factgraph.sdk import SDKStore
from factgraph.sdk.shells.proof_frame_diff import sdk_diff_proof_frames


G5_MODULES = (
    "factgraph.sdk.shells.proof_frame_diff",
)
# Forbidden production imports for G5. NOTE: per §6 G5 carve,
# `factgraph.audit.proof_frame_diff` and `factgraph.audit.round_events` are
# the explicit allowed A-side dependencies for G5 (the diff function
# and `RoundEvent` type both live at `factgraph.audit`). The audit-allowlist
# check below enforces that ONLY those two modules are imported from
# the broader `factgraph.audit` namespace, distinct from broader audit
# privates which remain forbidden.
FORBIDDEN_PRODUCTION_IMPORT_TEXT = (
    "factgraph.application.capability_helpers._binding",
    "_reject_sdk_origin",
    "from factgraph.application.walker",
    "import factgraph.application.walker",
    "from factgraph.application.walker import",
    "factgraph.core.rules.frontier",
)
ALLOWED_AUDIT_IMPORT_PREFIXES_G5 = (
    "factgraph.audit.proof_frame_diff",
    "factgraph.audit.round_events",
)


class SDKG5InvariantTests(unittest.TestCase):
    """G5 invariants — must hold across all G5 phases."""

    def test_sdk_all_unchanged_and_g5_result_types_not_exported(self) -> None:
        """§5.3 + §5.4 lock: G5 result DTO + supporting `factgraph.audit`
        DTOs are not re-exported from SDK; recorder lifecycle stays at
        advanced importable per §5.1."""
        self.assertIn("SchemaAddResult", factgraph_sdk.__all__)
        self.assertIn("FactGraph", factgraph_sdk.__all__)
        self.assertIn("SemanticsProfile", factgraph_sdk.__all__)
        self.assertIn("ProbLogConfig", factgraph_sdk.__all__)
        self.assertIn("PyReasonConfig", factgraph_sdk.__all__)
        for name in (
            # §5.4 result DTO + §5.3 input/supporting DTOs
            "ProofFrameDiff",
            "FrameDelta",
            "AtomDelta",
            "FrameIdentity",
            "FrameStatusChange",
            "EventReference",
            "RoundEvent",
            "RoundSummary",
            # §5.7 method name + §5.6 shell function name
            "diff_proof_frames",
            "sdk_diff_proof_frames",
            # §5.1 deferred recorder lifecycle (must stay advanced importable)
            "RoundRecorder",
            "start_round",
            "record_round_event",
            "finalize_round",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, factgraph_sdk.__all__)
                self.assertFalse(hasattr(factgraph_sdk, name))

    def test_g5_flat_method_is_removed_and_no_scenario_method_shipped(
        self,
    ) -> None:
        """Q-NAMING-C lock: G5 flat method is removed from `SDKStore`."""
        self.assertFalse(hasattr(SDKStore, "diff_proof_frames"))
        for scenario_name in (
            # Group B (rejected — collides with DTO name `ProofFrameDiff`)
            "proof_frame_diff",
            # Other rejected candidates from §5.7 falsifier
            "compare_proof_frames",
            # §5.1 recorder lifecycle (deliberately NOT shipped)
            "start_round",
            "record_round_event",
            "finalize_round",
            "record_round",
        ):
            with self.subTest(name=scenario_name):
                self.assertFalse(hasattr(SDKStore, scenario_name))

    def test_g5_module_lives_in_shells_subpackage(self) -> None:
        """§5.5 + §5.6 lock: G5 shell lives at
        ``factgraph/sdk/shells/proof_frame_diff.py``. Flat
        ``factgraph/sdk/proof_frame_diff.py`` location must not exist.
        Total `factgraph/sdk/shells/` module count is 9 post-G5 (8 prior
        shells + new G5 shell)."""
        sdk_dir = pathlib.Path(factgraph_sdk.__file__).parent
        self.assertTrue((sdk_dir / "shells").is_dir())
        self.assertTrue((sdk_dir / "shells" / "__init__.py").is_file())
        self.assertTrue((sdk_dir / "shells" / "proof_frame_diff.py").is_file())
        self.assertFalse((sdk_dir / "proof_frame_diff.py").exists())

    def test_g5_module_does_not_import_internal_or_walker_layers(self) -> None:
        """§6 lock: G5 SDK shell must not import application
        internals, walker, frontier, or `factgraph.audit` privates.

        Per §6 G5 carve: `factgraph.audit.proof_frame_diff` and
        `factgraph.audit.round_events` ARE allowed as the explicit A-side
        dependencies (the diff function and `RoundEvent` type live
        there). Other `factgraph.audit.*` modules (e.g.,
        `factgraph.audit.assertions`, `.query`, `.reader`,
        `.evidence_graph`) remain forbidden.
        """
        for module_name in G5_MODULES:
            module = import_module(module_name)
            source = pathlib.Path(inspect.getfile(module)).read_text(encoding="utf-8")
            for forbidden in FORBIDDEN_PRODUCTION_IMPORT_TEXT:
                with self.subTest(module=module_name, forbidden=forbidden):
                    self.assertNotIn(forbidden, source)
            # Audit-import allowlist: any `factgraph.audit.*` import line
            # must reference one of the two allowed modules.
            for line_no, line in enumerate(source.splitlines(), start=1):
                stripped = line.strip()
                if not (stripped.startswith("from ") or stripped.startswith("import ")):
                    continue
                if "factgraph.audit" not in line:
                    continue
                with self.subTest(module=module_name, line_no=line_no):
                    self.assertTrue(
                        any(allowed in line for allowed in ALLOWED_AUDIT_IMPORT_PREFIXES_G5),
                        f"unexpected `factgraph.audit` import in {module_name} "
                        f"line {line_no}: {stripped!r} — allowed prefixes are "
                        f"{ALLOWED_AUDIT_IMPORT_PREFIXES_G5}",
                    )

    def test_private_helper_holds_capability_logic(self) -> None:
        """Q-NAMING-C keeps the proof-frame diff shell as a private helper."""
        diff_source = inspect.getsource(sdk_diff_proof_frames)

        self.assertIn("build_proof_frame_diff(", diff_source)
        self.assertIn("RoundEvent", diff_source)
        self.assertIn("WarningDTO", diff_source)
        self.assertIn("isinstance(", diff_source)

    def test_store_method_docstring_records_boundary_contract(self) -> None:
        """§5.7 + §6 lock: `fg.audit.diff_proof_frames` docstring records
        boundary contract + all 8 locked `$.diff_proof_frames.*` paths
        (post-pre-publish-Blocker fix: 7-path → 8-path with new
        `.include_unchanged` boundary check)."""
        diff_doc = sdk_diff_proof_frames.__doc__ or ""

        for required in (
            "ProofFrameDiff",
            "build_proof_frame_diff",
        ):
            with self.subTest(required=required):
                self.assertIn(required, diff_doc)


if __name__ == "__main__":
    unittest.main()
