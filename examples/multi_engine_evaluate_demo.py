#!/usr/bin/env python3
"""Multi-Engine Evaluate Demo: Unified Dispatch + Annotation Persistence.

Demonstrates the framework's unified evaluate surface with annotation delivery:
1. Define Entity schema using factpy SDK
2. Write facts via SDK
3. Evaluate with mode="pyreason" through Store.evaluate() (not adapter-local)
4. Accept results and persist engine semantic annotations
5. Query annotations from Ledger

This demo uses mocked PyReason execution (no real pyreason dependency needed).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from factpy_kernel.sdk import Entity, Identity, Field, Relationship
from factpy_kernel.sdk.store import SDKStore
from factpy_kernel.sdk.dsl import Derivation, Pred, vars as sdk_vars
from factpy_kernel.sdk.compile import compile_schema_from_classes
from factpy_kernel.core.derivation.accept import AcceptOptions


# ════════════════════════════════════════════════════════════════
# 1. Schema Definition
# ════════════════════════════════════════════════════════════════

class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    popular: str = Field(cardinality="single")


class Friends(Relationship):
    from_entity = User
    to_entity = User
    strength: str = Field(cardinality="single")


schema_ir = compile_schema_from_classes([User, Friends])
# Ensure relationship predicates have owner_type for SDK compatibility
for pred in schema_ir.get("predicates", []):
    if isinstance(pred, dict) and pred.get("relationship_type") and not pred.get("owner_type"):
        pred["owner_type"] = pred["relationship_type"]

sdk = SDKStore([User, Friends], schema_ir=schema_ir)
print("Schema compiled:", [p["pred_id"] for p in schema_ir["predicates"]])


# ════════════════════════════════════════════════════════════════
# 2. Write EDB Facts via SDK
# ════════════════════════════════════════════════════════════════

from factpy_kernel.core.evidence.write_protocol import set_field

alice_ref = sdk.ref(User, user_id="Alice")
bob_ref = sdk.ref(User, user_id="Bob")

set_field(sdk.ledger, pred_id="user:name", e_ref=alice_ref,
          rest_terms=[("string", "Alice")],
          meta={"source": "demo", "confidence": 1.0})
set_field(sdk.ledger, pred_id="user:name", e_ref=bob_ref,
          rest_terms=[("string", "Bob")],
          meta={"source": "demo", "confidence": 1.0})
set_field(sdk.ledger, pred_id="friends:strength", e_ref=alice_ref,
          rest_terms=[("entity_ref", bob_ref), ("string", "0.9")],
          meta={"source": "demo", "confidence": 1.0})

print(f"\nEDB facts written: {len(sdk.ledger.claims)} assertions")


# ════════════════════════════════════════════════════════════════
# 3. Evaluate with mode="pyreason" (unified dispatch)
# ════════════════════════════════════════════════════════════════

# Import registers the pyreason engine evaluator
import factpy_kernel.adapters.pyreason  # noqa: F401
from factpy_kernel.adapters.pyreason.rule_ext import PyReasonRuleExt
from factpy_kernel.adapters.pyreason.accept import persist_pyreason_annotations

with sdk_vars("u", "name") as (u, name):
    derivation = Derivation(
        id="drv.popular",
        version="v1",
        where=[Pred("user:name", u, name)],
        target="user:popular",
        head_vars=[u],
        mode="pyreason",
        # engine_ext: definition-time rule semantics
        engine_ext=PyReasonRuleExt(timestep_delay=1),
    )

print(f"\nDerivation created: mode={derivation.mode}, engine_ext={derivation.engine_ext}")

try:
    # engine_options: call-time runtime config (not persisted)
    candidates = sdk.evaluate(derivation, engine_options={"timesteps": 3})
    print(f"Candidates: {len(candidates)}")
except Exception as exc:
    print(f"\n[NOTE] PyReason evaluate failed: {exc}")
    print("This is expected if pyreason is not installed or has numba issues.")
    print("The demo shows the API pattern; real execution requires pyreason==3.0.0.")
    sys.exit(0)


# ════════════════════════════════════════════════════════════════
# 4. Accept + Annotation Persistence
# ════════════════════════════════════════════════════════════════

if candidates:
    candidate = candidates[0]
    print(f"\nCandidate: target={candidate.target}, confidence={candidate.confidence}")

    result = sdk.store.accept(
        derivation_id=candidate.derivation_id,
        version=candidate.derivation_version,
        candidate_set=candidate,
        options=AcceptOptions(),
    )
    print(f"Accepted: {result.accepted_count} assertions")

    # Persist PyReason semantic annotations (post-accept)
    annotation_count = persist_pyreason_annotations(
        sdk.ledger, candidate.run_id, sdk.store, result,
    )
    print(f"Annotations persisted: {annotation_count}")

    # ════════════════════════════════════════════════════════════════
    # 5. Query Annotations from Ledger
    # ════════════════════════════════════════════════════════════════

    if result.written_assertions:
        asrt_id = result.written_assertions[0]["asrt_id"]
        print(f"\nAnnotations for {asrt_id}:")

        # PyReason semantic annotations
        pyreason_anns = sdk.ledger.find_annotations(asrt_id=asrt_id, namespace="pyreason")
        for ann in pyreason_anns:
            print(f"  [{ann.namespace}/{ann.category}] {ann.key} = {ann.value} (origin={ann.origin})")

        # Shared derived annotations
        shared_anns = sdk.ledger.find_annotations(asrt_id=asrt_id, namespace="shared")
        for ann in shared_anns:
            print(f"  [{ann.namespace}/{ann.category}] {ann.key} = {ann.value} (origin={ann.origin})")
else:
    print("\nNo candidates produced.")


# ════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════

print(f"\n{'='*60}")
print("MULTI-ENGINE EVALUATE DEMO")
print(f"{'='*60}")
print("Key concepts demonstrated:")
print("  1. Store.evaluate(mode='pyreason') — unified dispatch, not adapter-local")
print("  2. Derivation.engine_ext — definition-time rule semantics (timestep_delay)")
print("  3. engine_options — call-time runtime config (timesteps), not persisted")
print("  4. persist_pyreason_annotations() — post-accept annotation persistence")
print("  5. Annotation Store — pyreason/semantic/* + shared/derived/* queryable")
print(f"{'='*60}")
