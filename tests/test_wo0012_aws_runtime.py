from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from src.aws_runtime.config import RuntimeConfig
from src.aws_runtime.handler import lambda_handler


class Wo0012AwsRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(
            os.environ,
            {
                "ECHO_ENV": "nonprod",
                "AWS_REGION": "ap-south-1",
                "DB_SECRET_ARN": "arn:aws:secretsmanager:ap-south-1:272037674623:secret:test",
                "DB_HOST": "private.example.rds.amazonaws.com",
                "DB_PORT": "5432",
                "DB_NAME": "echoos",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()

    def _event(self, path: str, subject: str = "staff-001") -> dict:
        return {
            "rawPath": path,
            "requestContext": {
                "http": {"method": "GET"},
                "authorizer": {"jwt": {"claims": {"sub": subject, "email": "staff@example.com"}}},
            },
        }

    def test_config_reports_database_ready_only_when_required_values_exist(self) -> None:
        self.assertTrue(RuntimeConfig.from_env().database_configured())

    def test_health_is_public_but_does_not_touch_database(self) -> None:
        response = lambda_handler(
            {"rawPath": "/health", "requestContext": {"http": {"method": "GET"}}}, None
        )
        body = json.loads(response["body"])
        self.assertEqual(200, response["statusCode"])
        self.assertEqual("ok", body["status"])
        self.assertTrue(body["database_configured"])

    def test_protected_route_rejects_missing_jwt_claims(self) -> None:
        response = lambda_handler(
            {"rawPath": "/whoami", "requestContext": {"http": {"method": "GET"}}}, None
        )
        self.assertEqual(401, response["statusCode"])

    def test_whoami_projects_authenticated_claims_only(self) -> None:
        response = lambda_handler(self._event("/whoami"), None)
        body = json.loads(response["body"])
        self.assertEqual(200, response["statusCode"])
        self.assertEqual("staff-001", body["subject"])
        self.assertEqual("staff@example.com", body["email"])

    @patch("src.aws_runtime.handler.probe")
    def test_db_health_requires_authentication_and_is_read_only_probe(self, probe_mock) -> None:
        probe_mock.return_value = {
            "database": "echoos",
            "user": "echo_admin",
            "engine": "postgresql",
            "version": "PostgreSQL 17",
        }
        response = lambda_handler(self._event("/db-health"), None)
        body = json.loads(response["body"])
        self.assertEqual(200, response["statusCode"])
        self.assertEqual("database_reachable", body["status"])
        probe_mock.assert_called_once()

    @patch("src.aws_runtime.handler.tenant_context")
    def test_tenant_context_uses_authenticated_subject_and_server_membership(self, tenant_context_mock) -> None:
        tenant_context_mock.return_value = {
            "principal_id": "principal-1",
            "display_name": "Owner",
            "enterprises": [{"enterprise_code": "TAGRO", "role_code": "OWNER", "capabilities": ["SELL"]}],
        }
        response = lambda_handler(self._event("/tenant-context", "cognito-sub-1"), None)
        body = json.loads(response["body"])
        self.assertEqual(200, response["statusCode"])
        self.assertEqual("tenant_context_resolved", body["status"])
        tenant_context_mock.assert_called_once()
        self.assertEqual("cognito-sub-1", tenant_context_mock.call_args.args[1])

    @patch("src.aws_runtime.handler.tenant_context")
    def test_tenant_context_rejects_identity_without_membership(self, tenant_context_mock) -> None:
        tenant_context_mock.return_value = None
        response = lambda_handler(self._event("/tenant-context", "unknown-sub"), None)
        self.assertEqual(403, response["statusCode"])


if __name__ == "__main__":
    unittest.main()
