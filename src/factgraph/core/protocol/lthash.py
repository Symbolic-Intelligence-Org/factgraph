"""LtHash16 set accumulator used by the Database state commitment.

Callers must provide a set of unique, canonically framed elements. Each of the
1024 lanes is added or subtracted modulo ``2^16``; wraparound is part of the
construction, not integer overflow. ``from_elements`` rejects duplicate bytes
so accidental multiset use cannot silently cancel the set-level invariant.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Iterable

# Parameter profile follows Meta's 2019 LtHash engineering deployment:
# 1024 lanes of 16-bit integers, i.e. a 2048-byte state in
# (Z / 2^16 Z)^1024.  See:
# https://engineering.fb.com/2019/03/01/security/homomorphic-hashing/
#
# Folly's implementation uses a BLAKE2X-family expander.  The Python
# implementation uses the standard-library SHAKE-256 XOF for the same
# hash-to-vector role, with an explicit factgraph domain separator.
LTHASH_LANES = 1024
LTHASH_LANE_BITS = 16
LTHASH_STATE_BYTES = LTHASH_LANES * (LTHASH_LANE_BITS // 8)
LTHASH_SCHEME = "lthash16-v2"
_TOKEN_PREFIX = f"{LTHASH_SCHEME}:"
_ELEMENT_DOMAIN = b"factgraph\x00lthash16-v2\x00element\x00"
_LANE_MASK = (1 << LTHASH_LANE_BITS) - 1


class LtHashError(ValueError):
    """Raised when an LtHash state or operation is malformed."""


def empty_state() -> bytes:
    return bytes(LTHASH_STATE_BYTES)


def hash_element(element: bytes) -> bytes:
    if not isinstance(element, bytes):
        raise TypeError("LtHash element must be bytes")
    framed = _ELEMENT_DOMAIN + len(element).to_bytes(8, "big") + element
    return hashlib.shake_256(framed).digest(LTHASH_STATE_BYTES)


def add(state: bytes, element: bytes) -> bytes:
    return _combine(state, hash_element(element), subtract=False)


def remove(state: bytes, element: bytes) -> bytes:
    return _combine(state, hash_element(element), subtract=True)


def from_elements(elements: Iterable[bytes]) -> bytes:
    state = empty_state()
    seen: set[bytes] = set()
    for element in elements:
        if not isinstance(element, bytes):
            raise TypeError("LtHash elements must be bytes")
        if element in seen:
            raise LtHashError("LtHash set input contains a duplicate element")
        seen.add(element)
        state = add(state, element)
    return state


def encode_state(state: bytes) -> str:
    _require_state(state)
    payload = base64.urlsafe_b64encode(state).decode("ascii").rstrip("=")
    return _TOKEN_PREFIX + payload


def decode_state(token: str) -> bytes:
    if not isinstance(token, str) or not token.startswith(_TOKEN_PREFIX):
        raise LtHashError(f"state digest must start with {_TOKEN_PREFIX!r}")
    payload = token[len(_TOKEN_PREFIX) :]
    if not payload:
        raise LtHashError("state digest payload is empty")
    padding = "=" * (-len(payload) % 4)
    try:
        state = base64.b64decode(payload + padding, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise LtHashError("state digest payload is not canonical base64url") from exc
    _require_state(state)
    if encode_state(state) != token:
        raise LtHashError("state digest token is not canonically encoded")
    return state


def _combine(state: bytes, vector: bytes, *, subtract: bool) -> bytes:
    _require_state(state)
    _require_state(vector)
    result = bytearray(LTHASH_STATE_BYTES)
    for offset in range(0, LTHASH_STATE_BYTES, 2):
        left = state[offset] | (state[offset + 1] << 8)
        right = vector[offset] | (vector[offset + 1] << 8)
        value = (left - right if subtract else left + right) & _LANE_MASK
        result[offset] = value & 0xFF
        result[offset + 1] = value >> 8
    return bytes(result)


def _require_state(state: bytes) -> None:
    if not isinstance(state, bytes):
        raise TypeError("LtHash state must be bytes")
    if len(state) != LTHASH_STATE_BYTES:
        raise LtHashError(
            f"LtHash state must be exactly {LTHASH_STATE_BYTES} bytes, got {len(state)}"
        )


__all__ = [
    "LTHASH_LANES",
    "LTHASH_LANE_BITS",
    "LTHASH_SCHEME",
    "LTHASH_STATE_BYTES",
    "LtHashError",
    "add",
    "decode_state",
    "empty_state",
    "encode_state",
    "from_elements",
    "hash_element",
    "remove",
]
