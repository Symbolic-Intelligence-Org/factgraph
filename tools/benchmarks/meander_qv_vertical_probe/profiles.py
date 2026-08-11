"""AssignedProfileSnapshotV0 loading/digesting for the vertical probe.

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT
"""
from __future__ import annotations

import json
import os
from typing import Any

from contracts import digest

_HERE = os.path.dirname(os.path.abspath(__file__))


def load_fixture(cell_id: str) -> dict:
    with open(os.path.join(_HERE, "fixtures", f"{cell_id}.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_golden(cell_id: str) -> dict:
    with open(os.path.join(_HERE, "golden", f"{cell_id}.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


def profile_snapshot(fixture: dict) -> dict:
    """Immutable run-input snapshot (§5.4.1): profile content + digests.

    Extension keys (e.g. resolver_identity_matching) participate in
    profile_digest per SCHEMA.md ruling #8 (whole-object hash).
    """
    prof: dict[str, Any] = fixture["profile"]
    return {
        "profile_ref": prof["profile_ref"],
        "profile_digest": digest(prof),
        "task_kind": prof["task_kind"],
        "policy_ref": prof["policy"]["policy_ref"],
        "policy_digest": digest(prof["policy"]),
        "profile": prof,
    }
