from __future__ import annotations

import hashlib
import re
from typing import Any

from .digests import b32_nopad_lower
from .tup_v1 import TAG_CODE_BY_NAME, encode_value_bytes


IDREF_V1_PREFIX = b"factpy\x00idref_v1\x00"
ENTITY_TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")


def _u32be(number: int) -> bytes:
    return number.to_bytes(4, "big", signed=False)


def _validate_entity_type(entity_type: str) -> None:
    if not isinstance(entity_type, str):
        raise ValueError("entity_type must be str")
    if not ENTITY_TYPE_RE.fullmatch(entity_type):
        raise ValueError(
            "entity_type must match [A-Za-z][A-Za-z0-9_.-]{0,127}"
        )


def canonical_bytes_idref_v1(
    entity_type: str, identity_fields: list[tuple[str, str, Any]]
) -> bytes:
    _validate_entity_type(entity_type)
    try:
        entity_type_bytes = entity_type.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("entity_type is not valid UTF-8") from exc

    out = bytearray(IDREF_V1_PREFIX)
    out.extend(_u32be(len(entity_type_bytes)))
    out.extend(entity_type_bytes)
    out.extend(_u32be(len(identity_fields)))

    for field in identity_fields:
        if not isinstance(field, tuple) or len(field) != 3:
            raise ValueError(
                "identity_fields entries must be tuple(field_name, type_domain, value)"
            )
        field_name, type_domain, value = field
        if not isinstance(field_name, str) or not field_name:
            raise ValueError("field_name must be non-empty str")
        try:
            field_name_bytes = field_name.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("field_name is not valid UTF-8") from exc

        if type_domain not in TAG_CODE_BY_NAME:
            raise ValueError(f"unknown type_domain: {type_domain}")
        payload = encode_value_bytes(type_domain, value)
        tag_code = TAG_CODE_BY_NAME[type_domain]

        out.extend(_u32be(len(field_name_bytes)))
        out.extend(field_name_bytes)
        out.append(tag_code)
        out.extend(_u32be(len(payload)))
        out.extend(payload)

    return bytes(out)


def encode_idref_v1(
    entity_type: str, identity_fields: list[tuple[str, str, Any]]
) -> str:
    canonical = canonical_bytes_idref_v1(entity_type, identity_fields)
    digest = hashlib.sha256(canonical).digest()
    digest_b32 = b32_nopad_lower(digest)
    return f"idref_v1:{entity_type}:{digest_b32}"
