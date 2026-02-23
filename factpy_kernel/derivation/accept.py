from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from factpy_kernel.derivation.candidates import CandidateSet
from factpy_kernel.evidence.write_protocol import WriteProtocolError, set_field
from factpy_kernel.protocol.idref_v1 import encode_idref_v1
from factpy_kernel.protocol.digests import sha256_hex, sha256_token
from factpy_kernel.store.ledger import Ledger


@dataclass(frozen=True)
class AcceptOptions:
    approved_by: str | None = None
    note: str | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class AcceptResult:
    materialize_id: str
    run_id: str
    accepted_count: int
    skipped_count: int
    written_assertions: list[dict[str, Any]]
    skipped_reason_counts: dict[str, int]


def accept_candidate_set(
    ledger: Ledger,
    candidate_set: CandidateSet,
    options: AcceptOptions,
    derived_rule_id: str,
    derived_rule_version: str,
    *,
    schema_digest_token: str | None = None,
    policy_digest_token: str | None = None,
) -> AcceptResult:
    if not isinstance(ledger, Ledger):
        raise WriteProtocolError("ledger must be Ledger")
    if not isinstance(candidate_set, CandidateSet):
        raise WriteProtocolError("candidate_set must be CandidateSet")
    if not isinstance(options, AcceptOptions):
        raise WriteProtocolError("options must be AcceptOptions")
    if not isinstance(derived_rule_id, str) or not derived_rule_id:
        raise WriteProtocolError("derived_rule_id must be non-empty string")
    if not isinstance(derived_rule_version, str) or not derived_rule_version:
        raise WriteProtocolError("derived_rule_version must be non-empty string")

    payload = candidate_set.payload
    if not isinstance(payload, dict):
        raise WriteProtocolError("candidate payload must be object")
    if not isinstance(candidate_set.target, str) or not candidate_set.target:
        raise WriteProtocolError("candidate target must be non-empty string")
    if not isinstance(candidate_set.key_tuple_digest, str) or not candidate_set.key_tuple_digest.startswith("sha256:"):
        raise WriteProtocolError("candidate key_tuple_digest must start with sha256:")

    materialize_kind = payload.get("materialize_as", "fact")
    if materialize_kind not in {"fact", "record"}:
        raise WriteProtocolError("candidate payload materialize_as must be 'fact' or 'record'")

    if materialize_kind == "record":
        return _accept_record_candidate(
            ledger=ledger,
            candidate_set=candidate_set,
            payload=payload,
            options=options,
            derived_rule_id=derived_rule_id,
            derived_rule_version=derived_rule_version,
            schema_digest_token=schema_digest_token,
            policy_digest_token=policy_digest_token,
        )

    e_ref = payload.get("e_ref")
    rest_terms = payload.get("rest_terms")

    if not isinstance(e_ref, str) or not e_ref:
        raise WriteProtocolError("candidate payload missing e_ref")
    if not isinstance(rest_terms, list):
        raise WriteProtocolError("candidate payload missing rest_terms")

    computed_materialize_id = _compute_materialize_id(candidate_set)

    if options.dry_run:
        return AcceptResult(
            materialize_id=computed_materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=1,
            skipped_count=0,
            written_assertions=[
                {
                    "asrt_id": "<dry_run>",
                    "pred_id": candidate_set.target,
                    "key_tuple_digest": candidate_set.key_tuple_digest,
                }
            ],
            skipped_reason_counts={},
        )

    materialize_id = _existing_materialize_id(
        ledger=ledger,
        pred_id=candidate_set.target,
        e_ref=e_ref,
        key_tuple_digest=candidate_set.key_tuple_digest,
    )
    if materialize_id is None:
        materialize_id = computed_materialize_id

    cand_key_digest = _compute_cand_key_digest(candidate_set.target, candidate_set.key_tuple_digest)

    existing_written = _find_existing_written_assertions(
        ledger=ledger,
        pred_id=candidate_set.target,
        e_ref=e_ref,
        key_tuple_digest=candidate_set.key_tuple_digest,
        materialize_id=materialize_id,
        cand_key_digest=cand_key_digest,
    )
    if existing_written:
        _assert_duplicate_meta_compatible(ledger=ledger, written_assertions=existing_written, options=options)
        return AcceptResult(
            materialize_id=materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"duplicate": 1},
        )

    write_meta: dict[str, Any] = {
        "source": "derivation.accept",
        "source_loc": f"{derived_rule_id}:{derived_rule_version}",
        "trace_id": candidate_set.run_id,
        "derived_rule_id": derived_rule_id,
        "derived_rule_version": derived_rule_version,
        "run_id": candidate_set.run_id,
        "materialize_id": materialize_id,
        "key_tuple_digest": candidate_set.key_tuple_digest,
        "cand_key_digest": cand_key_digest,
        "support_digest": candidate_set.support_digest,
        "support_kind": candidate_set.support_kind,
    }
    if isinstance(schema_digest_token, str) and schema_digest_token:
        write_meta["schema_digest"] = schema_digest_token
    if isinstance(policy_digest_token, str) and policy_digest_token:
        write_meta["policy_digest"] = policy_digest_token
    if options.approved_by is not None:
        write_meta["approved_by"] = options.approved_by
    if options.note is not None:
        write_meta["note"] = options.note

    asrt_id = set_field(
        ledger=ledger,
        pred_id=candidate_set.target,
        e_ref=e_ref,
        rest_terms=rest_terms,
        meta=write_meta,
    )

    return AcceptResult(
        materialize_id=materialize_id,
        run_id=candidate_set.run_id,
        accepted_count=1,
        skipped_count=0,
        written_assertions=[
            {
                "asrt_id": asrt_id,
                "pred_id": candidate_set.target,
                "key_tuple_digest": candidate_set.key_tuple_digest,
            }
        ],
        skipped_reason_counts={},
    )


def _accept_record_candidate(
    *,
    ledger: Ledger,
    candidate_set: CandidateSet,
    payload: dict[str, Any],
    options: AcceptOptions,
    derived_rule_id: str,
    derived_rule_version: str,
    schema_digest_token: str | None = None,
    policy_digest_token: str | None = None,
) -> AcceptResult:
    record_type = payload.get("record_type", candidate_set.target)
    if not isinstance(record_type, str) or not record_type:
        raise WriteProtocolError("record payload missing record_type")
    if candidate_set.target != record_type:
        raise WriteProtocolError("candidate target must equal record_type for materialize_as='record'")

    id_policy = payload.get("id_policy")
    record_exists_pred_id = payload.get("record_exists_pred_id")
    if not isinstance(record_exists_pred_id, str) or not record_exists_pred_id:
        raise WriteProtocolError("record payload missing record_exists_pred_id")

    roles_raw = payload.get("roles")
    if not isinstance(roles_raw, list) or not roles_raw:
        raise WriteProtocolError("record payload roles must be non-empty list")
    roles = _normalize_record_roles(roles_raw)
    record_e_ref = _derive_record_e_ref(
        record_type=record_type,
        id_policy=id_policy,
        candidate_set=candidate_set,
        roles=roles,
    )

    computed_materialize_id = _compute_materialize_id(candidate_set)

    if options.dry_run:
        dry_rows = [{"asrt_id": "<dry_run>", "pred_id": record_exists_pred_id, "key_tuple_digest": candidate_set.key_tuple_digest}]
        for role in roles:
            dry_rows.append({"asrt_id": "<dry_run>", "pred_id": role["pred_id"], "key_tuple_digest": candidate_set.key_tuple_digest})
        return AcceptResult(
            materialize_id=computed_materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=1,
            skipped_count=0,
            written_assertions=dry_rows,
            skipped_reason_counts={},
        )

    materialize_id = _existing_materialize_id(
        ledger=ledger,
        pred_id=record_exists_pred_id,
        e_ref=record_e_ref,
        key_tuple_digest=candidate_set.key_tuple_digest,
    )
    if materialize_id is None:
        materialize_id = computed_materialize_id
    cand_key_digest = _compute_cand_key_digest(candidate_set.target, candidate_set.key_tuple_digest)

    existing_written = _find_existing_written_assertions_record(
        ledger=ledger,
        materialize_id=materialize_id,
        cand_key_digest=cand_key_digest,
        key_tuple_digest=candidate_set.key_tuple_digest,
    )
    if existing_written:
        _assert_duplicate_meta_compatible(ledger=ledger, written_assertions=existing_written, options=options)
        return AcceptResult(
            materialize_id=materialize_id,
            run_id=candidate_set.run_id,
            accepted_count=0,
            skipped_count=1,
            written_assertions=existing_written,
            skipped_reason_counts={"duplicate": 1},
        )

    write_meta: dict[str, Any] = {
        "source": "derivation.accept",
        "source_loc": f"{derived_rule_id}:{derived_rule_version}",
        "trace_id": candidate_set.run_id,
        "derived_rule_id": derived_rule_id,
        "derived_rule_version": derived_rule_version,
        "run_id": candidate_set.run_id,
        "materialize_id": materialize_id,
        "key_tuple_digest": candidate_set.key_tuple_digest,
        "cand_key_digest": cand_key_digest,
        "support_digest": candidate_set.support_digest,
        "support_kind": candidate_set.support_kind,
        "materialize_kind": "record",
        "record_type": record_type,
        "record_e_ref": record_e_ref,
        "record_id_policy": _record_id_policy_kind(id_policy),
    }
    if isinstance(schema_digest_token, str) and schema_digest_token:
        write_meta["schema_digest"] = schema_digest_token
    if isinstance(policy_digest_token, str) and policy_digest_token:
        write_meta["policy_digest"] = policy_digest_token
    if options.approved_by is not None:
        write_meta["approved_by"] = options.approved_by
    if options.note is not None:
        write_meta["note"] = options.note

    written: list[dict[str, str]] = []
    exists_asrt = set_field(
        ledger=ledger,
        pred_id=record_exists_pred_id,
        e_ref=record_e_ref,
        rest_terms=[],
        meta=write_meta,
    )
    written.append(
        {"asrt_id": exists_asrt, "pred_id": record_exists_pred_id, "key_tuple_digest": candidate_set.key_tuple_digest}
    )
    for role in roles:
        asrt_id = set_field(
            ledger=ledger,
            pred_id=role["pred_id"],
            e_ref=record_e_ref,
            rest_terms=role["rest_terms"],
            meta=write_meta,
        )
        written.append(
            {"asrt_id": asrt_id, "pred_id": role["pred_id"], "key_tuple_digest": candidate_set.key_tuple_digest}
        )
    written.sort(key=lambda row: (row["pred_id"], row["asrt_id"]))

    return AcceptResult(
        materialize_id=materialize_id,
        run_id=candidate_set.run_id,
        accepted_count=1,
        skipped_count=0,
        written_assertions=written,
        skipped_reason_counts={},
    )


def _compute_materialize_id(candidate_set: CandidateSet) -> str:
    parts = [
        b"factpy\x00mat_v1\x00",
        candidate_set.run_id.encode("utf-8"),
        b"\x00",
        candidate_set.derivation_id.encode("utf-8"),
        b"\x00",
        candidate_set.derivation_version.encode("utf-8"),
        b"\x00",
    ]
    return f"mat_v1:{sha256_hex(b''.join(parts))}"


def _compute_cand_key_digest(target: str, key_tuple_digest: str) -> str:
    parts = [
        b"factpy\x00cand_key_v1\x00",
        target.encode("utf-8"),
        b"\x00",
        key_tuple_digest.encode("utf-8"),
        b"\x00",
    ]
    return sha256_token(b"".join(parts))


def _existing_materialize_id(
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    key_tuple_digest: str,
) -> str | None:
    for claim in ledger.find_claims(pred_id=pred_id, e_ref=e_ref):
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        if _meta_value(ledger, claim.asrt_id, "key_tuple_digest") != key_tuple_digest:
            continue
        materialize_id = _meta_value(ledger, claim.asrt_id, "materialize_id")
        if materialize_id:
            return materialize_id
    return None


def _find_existing_written_assertions(
    ledger: Ledger,
    pred_id: str,
    e_ref: str,
    key_tuple_digest: str,
    materialize_id: str,
    cand_key_digest: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for claim in ledger.find_claims(pred_id=pred_id, e_ref=e_ref):
        if ledger.has_active_revocation(claim.asrt_id):
            continue

        if _meta_value(ledger, claim.asrt_id, "materialize_id") != materialize_id:
            continue
        if _meta_value(ledger, claim.asrt_id, "cand_key_digest") != cand_key_digest:
            continue
        if _meta_value(ledger, claim.asrt_id, "key_tuple_digest") != key_tuple_digest:
            continue

        rows.append(
            {
                "asrt_id": claim.asrt_id,
                "pred_id": claim.pred_id,
                "key_tuple_digest": key_tuple_digest,
            }
        )
    return rows


def _find_existing_written_assertions_record(
    *,
    ledger: Ledger,
    materialize_id: str,
    cand_key_digest: str,
    key_tuple_digest: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for claim in ledger.find_claims():
        if ledger.has_active_revocation(claim.asrt_id):
            continue
        if _meta_value(ledger, claim.asrt_id, "materialize_kind") != "record":
            continue
        if _meta_value(ledger, claim.asrt_id, "materialize_id") != materialize_id:
            continue
        if _meta_value(ledger, claim.asrt_id, "cand_key_digest") != cand_key_digest:
            continue
        if _meta_value(ledger, claim.asrt_id, "key_tuple_digest") != key_tuple_digest:
            continue
        rows.append(
            {"asrt_id": claim.asrt_id, "pred_id": claim.pred_id, "key_tuple_digest": key_tuple_digest}
        )
    rows.sort(key=lambda row: (row["pred_id"], row["asrt_id"]))
    return rows


def _assert_duplicate_meta_compatible(
    *,
    ledger: Ledger,
    written_assertions: list[dict[str, str]],
    options: AcceptOptions,
) -> None:
    if options.approved_by is None and options.note is None:
        return

    for row in written_assertions:
        asrt_id = row["asrt_id"]
        if options.approved_by is not None:
            existing_approved_by = _meta_value(ledger, asrt_id, "approved_by")
            if existing_approved_by != options.approved_by:
                raise WriteProtocolError("duplicate accept approved_by mismatch")
        if options.note is not None:
            existing_note = _meta_value(ledger, asrt_id, "note")
            if existing_note != options.note:
                raise WriteProtocolError("duplicate accept note mismatch")


def _record_id_policy_kind(id_policy: Any) -> str:
    if isinstance(id_policy, str):
        return id_policy
    if isinstance(id_policy, dict):
        kind = id_policy.get("kind")
        if isinstance(kind, str):
            return kind
    raise WriteProtocolError("record payload id_policy must be string or object with kind")


def _derive_record_e_ref(
    *,
    record_type: str,
    id_policy: Any,
    candidate_set: CandidateSet,
    roles: list[dict[str, Any]],
) -> str:
    kind = _record_id_policy_kind(id_policy)
    if kind != "key_tuple_digest_v1":
        if kind == "identity_fields_v1":
            return _derive_record_e_ref_from_identity_fields(
                record_type=record_type,
                id_policy=id_policy,
                roles=roles,
            )
        raise WriteProtocolError(
            "record id_policy.kind must be 'key_tuple_digest_v1' or 'identity_fields_v1' in v1"
        )
    return encode_idref_v1(
        record_type,
        [("key_tuple_digest", "string", candidate_set.key_tuple_digest)],
    )


def _derive_record_e_ref_from_identity_fields(
    *,
    record_type: str,
    id_policy: Any,
    roles: list[dict[str, Any]],
) -> str:
    if not isinstance(id_policy, dict):
        raise WriteProtocolError("record id_policy identity_fields_v1 must be object")
    fields = id_policy.get("fields")
    if not isinstance(fields, list) or not fields:
        raise WriteProtocolError("record id_policy.fields must be non-empty list")

    role_map: dict[str, tuple[str, Any]] = {}
    for idx, role in enumerate(roles):
        field_name = role.get("field_name")
        pred_id = role.get("pred_id")
        if not isinstance(field_name, str) or not field_name:
            if isinstance(pred_id, str) and ":" in pred_id:
                field_name = pred_id.split(":", 1)[1]
            elif isinstance(pred_id, str) and pred_id:
                field_name = pred_id
            else:
                raise WriteProtocolError(f"record roles[{idx}] missing field_name")
        rest_terms = role.get("rest_terms")
        if not isinstance(rest_terms, list) or len(rest_terms) != 1:
            raise WriteProtocolError(
                f"record roles[{idx}].rest_terms must contain exactly one term for identity_fields_v1"
            )
        term = rest_terms[0]
        if not (isinstance(term, tuple) and len(term) == 2):
            raise WriteProtocolError(f"record roles[{idx}].rest_terms[0] must be (tag,value)")
        tag, value = term
        if not isinstance(tag, str) or not tag:
            raise WriteProtocolError(f"record roles[{idx}] role term tag must be non-empty string")
        if field_name in role_map:
            raise WriteProtocolError(f"duplicate record role field_name for id_policy: {field_name}")
        role_map[field_name] = (tag, value)

    identity_fields: list[tuple[str, str, Any]] = []
    for idx, item in enumerate(fields):
        if not isinstance(item, dict):
            raise WriteProtocolError(f"id_policy.fields[{idx}] must be object")
        name = item.get("name")
        role_name = item.get("role", item.get("from_role"))
        type_domain = item.get("type_domain")
        if not isinstance(name, str) or not name:
            raise WriteProtocolError(f"id_policy.fields[{idx}].name must be non-empty string")
        if not isinstance(role_name, str) or not role_name:
            raise WriteProtocolError(f"id_policy.fields[{idx}].role must be non-empty string")
        if not isinstance(type_domain, str) or not type_domain:
            raise WriteProtocolError(f"id_policy.fields[{idx}].type_domain must be non-empty string")
        role_term = role_map.get(role_name)
        if role_term is None:
            raise WriteProtocolError(f"id_policy.fields[{idx}] references unknown role: {role_name}")
        actual_tag, value = role_term
        if actual_tag != type_domain:
            raise WriteProtocolError(
                f"id_policy.fields[{idx}].type_domain mismatches role tag: {actual_tag}"
            )
        identity_fields.append((name, type_domain, value))

    return encode_idref_v1(record_type, identity_fields)


def _normalize_record_roles(roles_raw: list[Any]) -> list[dict[str, Any]]:
    roles: list[dict[str, Any]] = []
    for idx, item in enumerate(roles_raw):
        if not isinstance(item, dict):
            raise WriteProtocolError(f"record roles[{idx}] must be object")
        pred_id = item.get("pred_id")
        field_name = item.get("field_name")
        rest_terms = item.get("rest_terms")
        if not isinstance(pred_id, str) or not pred_id:
            raise WriteProtocolError(f"record roles[{idx}].pred_id must be non-empty string")
        if field_name is not None and (not isinstance(field_name, str) or not field_name):
            raise WriteProtocolError(f"record roles[{idx}].field_name must be non-empty string when provided")
        if not isinstance(rest_terms, list):
            raise WriteProtocolError(f"record roles[{idx}].rest_terms must be list")
        normalized: dict[str, Any] = {"pred_id": pred_id, "rest_terms": rest_terms}
        if isinstance(field_name, str):
            normalized["field_name"] = field_name
        type_domain = item.get("type_domain")
        if type_domain is not None:
            if not isinstance(type_domain, str) or not type_domain:
                raise WriteProtocolError(f"record roles[{idx}].type_domain must be non-empty string when provided")
            normalized["type_domain"] = type_domain
        roles.append(normalized)
    return roles


def _meta_value(ledger: Ledger, asrt_id: str, key: str) -> str | None:
    for row in ledger.find_meta(asrt_id=asrt_id, key=key):
        if isinstance(row.value, str):
            return row.value
    return None
