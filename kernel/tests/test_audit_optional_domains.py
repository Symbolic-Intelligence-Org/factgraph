from __future__ import annotations

import builtins
from unittest import TestCase
from unittest.mock import patch

from kernel.audit import AuditOptionalDomainError, AuditQuery


class AuditOptionalDomainTests(TestCase):
    def test_list_compliance_matrix_reports_missing_domains_as_optional(self) -> None:
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
            if name == "domains.ecss.compliance":
                raise ModuleNotFoundError("No module named 'domains'", name="domains")
            return real_import(name, globals, locals, fromlist, level)

        query = object.__new__(AuditQuery)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(AuditOptionalDomainError) as raised:
                query.list_compliance_matrix()

        message = str(raised.exception)
        self.assertIn("optional domains.ecss package", message)
        self.assertIn("kernel-only", message)
