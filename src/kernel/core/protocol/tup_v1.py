from __future__ import annotations

import base64
import math
import re
import struct
from typing import Any


TUP_V1_PREFIX = b"factpy\x00tup_v1\x00"
INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1

CANONICAL_TAGS = (
    "entity_ref",
    "string",
    "int",
    "float64",
    "bool",
    "bytes",
    "time",
    "uuid",
)

TAG_CODE_BY_NAME = {
    "string": 0x01,
    "int": 0x02,
    "float64": 0x03,
    "bool": 0x04,
    "bytes": 0x05,
    "time": 0x06,
    "uuid": 0x07,
    "entity_ref": 0x08,
}
TAG_NAME_BY_CODE = {code: name for name, code in TAG_CODE_BY_NAME.items()}

UUID_CANONICAL_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
FLOAT64_HEX_RE = re.compile(r"^0x[0-9a-f]{16}$")
ENTITY_REF_PREFIX = "idref_v1:"


def _u32be(number: int) -> bytes:
    return number.to_bytes(4, "big", signed=False)


def _require_int64(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be int64")
    if value < INT64_MIN or value > INT64_MAX:
        raise ValueError(f"{field} is out of int64 range")
    return value


def _encode_string(value: Any) -> bytes:
    if not isinstance(value, str):
        raise ValueError("string value must be str")
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("string value is not valid UTF-8") from exc


def _encode_entity_ref(value: Any) -> bytes:
    if not isinstance(value, str):
        raise ValueError("entity_ref value must be str")
    if not value.startswith(ENTITY_REF_PREFIX):
        raise ValueError("entity_ref must start with idref_v1:")
    return _encode_string(value)


def _int_to_canonical_text(value: int) -> str:
    if value == 0:
        return "0"
    return str(value)


def _float64_bits(value: Any) -> int:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("float64 must be finite")
        canonical = 0.0 if value == 0.0 else value
        bits = struct.unpack(">Q", struct.pack(">d", canonical))[0]
    elif isinstance(value, str):
        if not FLOAT64_HEX_RE.fullmatch(value):
            raise ValueError("float64 hex form must be 0x + 16 lowercase hex digits")
        bits = int(value[2:], 16)
    else:
        raise ValueError("float64 value must be float or 0x<16hex> string")

    if bits == 0x8000000000000000:
        bits = 0

    as_float = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
    if not math.isfinite(as_float):
        raise ValueError("float64 must be finite")
    return bits


def _encode_bool(value: Any) -> bytes:
    if not isinstance(value, bool):
        raise ValueError("bool value must be bool")
    return b"\x01" if value else b"\x00"


def _to_raw_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    raise ValueError("bytes value must be bytes-like")


def _uuid_bytes(value: Any) -> bytes:
    if not isinstance(value, str):
        raise ValueError("uuid value must be canonical lowercase string")
    if not UUID_CANONICAL_RE.fullmatch(value):
        raise ValueError("uuid must match lowercase 8-4-4-4-12 form")
    return bytes.fromhex(value.replace("-", ""))


def _normalize_tag(tag: Any) -> str:
    if not isinstance(tag, str):
        raise ValueError("tag must be str")
    if tag not in TAG_CODE_BY_NAME:
        raise ValueError(f"unknown tag: {tag}")
    return tag


def encode_value_bytes(tag: str, value: Any) -> bytes:
    canonical_tag = _normalize_tag(tag)
    if canonical_tag == "entity_ref":
        return _encode_entity_ref(value)
    if canonical_tag == "string":
        return _encode_string(value)
    if canonical_tag == "int":
        int_value = _require_int64(value, field="int")
        return _int_to_canonical_text(int_value).encode("ascii")
    if canonical_tag == "float64":
        return _float64_bits(value).to_bytes(8, "big", signed=False)
    if canonical_tag == "bool":
        return _encode_bool(value)
    if canonical_tag == "bytes":
        return _to_raw_bytes(value)
    if canonical_tag == "time":
        epoch_nanos = _require_int64(value, field="time")
        return struct.pack(">q", epoch_nanos)
    if canonical_tag == "uuid":
        return _uuid_bytes(value)
    raise ValueError(f"unknown tag: {canonical_tag}")


def canonical_bytes_tup_v1(rest_terms: list[tuple[str, Any]]) -> bytes:
    out = bytearray(TUP_V1_PREFIX)
    out.extend(_u32be(len(rest_terms)))
    for item in rest_terms:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("each rest term must be tuple(tag, value)")
        tag, value = item
        canonical_tag = _normalize_tag(tag)
        payload = encode_value_bytes(canonical_tag, value)
        out.append(TAG_CODE_BY_NAME[canonical_tag])
        out.extend(_u32be(len(payload)))
        out.extend(payload)
    return bytes(out)


def _val_atom_for_claim_arg(tag: str, value: Any) -> Any:
    if tag == "entity_ref":
        return _encode_entity_ref(value).decode("utf-8")
    if tag == "string":
        return _encode_string(value).decode("utf-8")
    if tag == "int":
        return _require_int64(value, field="int")
    if tag == "float64":
        return f"0x{_float64_bits(value):016x}"
    if tag == "bool":
        if not isinstance(value, bool):
            raise ValueError("bool value must be bool")
        return value
    if tag == "bytes":
        raw = _to_raw_bytes(value)
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    if tag == "time":
        return _require_int64(value, field="time")
    if tag == "uuid":
        if not isinstance(value, str) or not UUID_CANONICAL_RE.fullmatch(value):
            raise ValueError("uuid must match lowercase 8-4-4-4-12 form")
        return value
    raise ValueError(f"unknown tag: {tag}")


def claim_args_from_rest_terms(rest_terms: list[tuple[str, Any]]) -> list[tuple[int, Any, str]]:
    rows: list[tuple[int, Any, str]] = []
    for idx, item in enumerate(rest_terms):
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("each rest term must be tuple(tag, value)")
        tag, value = item
        canonical_tag = _normalize_tag(tag)
        val_atom = _val_atom_for_claim_arg(canonical_tag, value)
        rows.append((idx, val_atom, canonical_tag))

    for expected_idx, row in enumerate(rows):
        if row[0] != expected_idx:
            raise ValueError("claim_arg idx must be 0-based and contiguous")

    return rows
