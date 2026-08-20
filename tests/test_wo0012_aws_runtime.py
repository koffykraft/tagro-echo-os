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

    def test_config_reports_database_ready_only_when_required_values_exist(self) -> None:
        self.assertTrue(RuntimeConfig.from_env().database_configured())

    def test_health_is_public_but_does_not_touch_database(self) -> None:
        response = lambda_handler(
            {"rawPath": "/health", "requestContext": {"http": {"method": "GET"}}},
            None,
        )
        body = json.loads(response["body"])
        self.assertEqual(200, response["statusCode"])
        self.assertEqual("ok", body["status"])
        self.assertTrue(body["database_configured"])

    def test_protected_route_rejects_missing_jwt_claims(self) -> None:
        response = lambda_handler(
            {"rawPath": "/whoami", "requestContext": {"http": {"method": "GET"}}},
            None,
        )
        self.assertEqual(401, response["statusCode"])

    def test_whoami_projects_authenticated_claims_only(self) -> None:
        response = lambda_handler(
            {
                "rawPath": "/whoami",
                "requestContext": {
                    "http": {"method": "GET"},
                    "authorizer": {
                        "jwt": {
                            "claims": {
                                "sub": "staff-001",
                                "email": "staff@example.com",
                                "cognito:username": "staff-001",
                            }
                        }
                    },
                },
            },
            None,
        )
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
        response = lambda_handler(
            {
                "rawPath": "/db-health",
                "requestContext": {
                    "http": {"method": "GET"},
                    "authorizer": {"jwt": {"claims": {"sub": "staff-001"}}},
                },
            },
            None,
        )
        body = json.loads(response["body"])
        self.assertEqual(200, response["statusCode"])
        self.assertEqual("database_reachable", body["status"])
        probe_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
