from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from service.auth import AuthConfig, load_auth_config


class ServiceAuthConfigTests(unittest.TestCase):
    def test_load_auth_config_enabled_with_keys(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FACTPY_KERNEL_API_KEYS": "k1, k2 ",
                "FACTPY_KERNEL_AUTH_DISABLED": "false",
            },
            clear=False,
        ):
            config = load_auth_config()
        self.assertTrue(config.enabled)
        self.assertTrue(config.has_keys)
        self.assertEqual(config.allowed_keys, ("k1", "k2"))

    def test_load_auth_config_disabled(self) -> None:
        with patch.dict(
            os.environ,
            {"FACTPY_KERNEL_AUTH_DISABLED": "true"},
            clear=False,
        ):
            config = load_auth_config()
        self.assertFalse(config.enabled)

    def test_verify_accepts_valid_key(self) -> None:
        config = AuthConfig(allowed_keys=("abc",))
        self.assertTrue(config.verify("abc"))

    def test_verify_rejects_missing_key(self) -> None:
        config = AuthConfig(allowed_keys=("abc",))
        self.assertFalse(config.verify(None))

    def test_verify_rejects_invalid_key(self) -> None:
        config = AuthConfig(allowed_keys=("abc",))
        self.assertFalse(config.verify("zzz"))
