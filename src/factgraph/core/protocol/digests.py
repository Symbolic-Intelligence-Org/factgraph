from __future__ import annotations

import base64
import hashlib


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_token(data: bytes) -> str:
    return f"sha256:{sha256_hex(data)}"


def b32_nopad_lower(data: bytes) -> str:
    return base64.b32encode(data).decode("ascii").rstrip("=").lower()
