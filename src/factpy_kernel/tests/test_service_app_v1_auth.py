from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from factpy_kernel.service.app_v1 import app
from factpy_kernel.service.auth import require_api_key


class ServiceAppV1AuthTests(unittest.TestCase):
    def test_all_v1_routes_require_api_key_dependency(self) -> None:
        protected_routes = [
            route
            for route in app.routes
            if isinstance(route, APIRoute) and route.path.startswith("/v1/")
        ]
        self.assertTrue(protected_routes)
        for route in protected_routes:
            deps = [dep.call for dep in route.dependant.dependencies]
            self.assertIn(require_api_key, deps, msg=f"missing auth dependency on {route.path}")

    def test_enabled_without_keys_returns_503(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FACTPY_KERNEL_API_KEYS": "",
                "FACTPY_KERNEL_AUTH_DISABLED": "false",
            },
            clear=False,
        ):
            with TestClient(app) as client:
                resp = client.get("/v1/profiles")
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()["detail"], "API authentication not configured")

    def test_disabled_auth_allows_request(self) -> None:
        with patch.dict(
            os.environ,
            {"FACTPY_KERNEL_AUTH_DISABLED": "true"},
            clear=False,
        ):
            with TestClient(app) as client:
                resp = client.get("/v1/profiles")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

    def test_enabled_missing_or_invalid_key_returns_401(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FACTPY_KERNEL_API_KEYS": "valid-key",
                "FACTPY_KERNEL_AUTH_DISABLED": "false",
            },
            clear=False,
        ):
            with TestClient(app) as client:
                missing = client.get("/v1/profiles")
                invalid = client.get("/v1/profiles", headers={"X-FactPy-API-Key": "wrong"})
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)

    def test_enabled_valid_key_returns_200(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FACTPY_KERNEL_API_KEYS": "valid-key",
                "FACTPY_KERNEL_AUTH_DISABLED": "false",
            },
            clear=False,
        ):
            with TestClient(app) as client:
                resp = client.get("/v1/profiles", headers={"X-FactPy-API-Key": "valid-key"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
